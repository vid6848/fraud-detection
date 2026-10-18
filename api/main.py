"""FastAPI app. Run with: uvicorn api.main:app --reload

Every request passes through `observe` (below), which gives it a request ID
(returned as the X-Request-ID header), times it, records it in /metrics, writes
one JSON log line, and turns unexpected exceptions into a clean 500.

Scored transactions are saved to Supabase in a background task that runs after
the response has been sent, so storage never slows scoring down, and a storage
outage is logged and counted in /metrics instead of failing the request.

POST /demo/stream (see api/demo.py) replays held-out test rows server-side so the
deployed dashboard can show a live stream without running the simulator.
"""
import logging
import re
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import asdict
from uuid import UUID

import pandas as pd
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import Settings
from api.demo import DemoBusy, DemoRateLimited, DemoStreamer, load_demo_rows, retry_after_header
from api.errors import error_response, register_error_handlers
from api.explanations import explain_row
from api.logging_setup import LOGGER_NAME, configure_logging
from api.metrics import MetricsCollector
from api.model_store import ModelStore
from api.schemas import (
    BatchPredictResponse,
    DemoStreamRequest,
    DemoStreamStatus,
    ExplainResponse,
    HealthResponse,
    MetricsResponse,
    PredictResponse,
    StoredExplainResponse,
    Transaction,
    make_batch_request,
    to_frame,
)
from api.scoring import Score, score_frame
from api.storage import (
    InvalidToken,
    StorageUnavailable,
    TransactionStore,
    build_row,
    build_store,
    stored_frame,
)
from ml.config import RAW_COLUMNS

logger = logging.getLogger(LOGGER_NAME)

# A client may send its own X-Request-ID (to trace a call end to end); anything
# else, or nothing, gets a fresh one. The pattern keeps log lines safe.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None,
               storage: TransactionStore | None = None) -> FastAPI:
    """`storage` overrides the Supabase store built from settings (used by tests)."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        app.state.store = ModelStore.load(settings)  # once per process, not per request
        logger.info("model loaded", extra={"model_version": app.state.store.version,
                                           "model_path": str(settings.model_path)})
        app.state.storage = storage if storage is not None else build_store(settings)
        app.state.metrics.storage_enabled = app.state.storage is not None
        if app.state.storage is None:
            logger.warning("storage disabled: set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY "
                           "and SUPABASE_ANON_KEY to save scored transactions")
        app.state.demo = _build_demo(app, settings)
        yield
        if app.state.demo is not None:
            await app.state.demo.aclose()
        app.state.demo = None
        if storage is None and app.state.storage is not None:
            app.state.storage.close()  # only close a store this app built
        app.state.store = None
        app.state.storage = None

    app = FastAPI(
        title="Fraud Detection API",
        description="Scores credit card transactions for fraud risk.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    BatchPredictRequest = make_batch_request(settings.max_batch_size)
    app.state.store = None
    app.state.storage = None
    app.state.demo = None
    app.state.metrics = MetricsCollector()
    register_error_handlers(app)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")
        if not REQUEST_ID_PATTERN.match(request_id):
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        exc_info = None
        try:
            response = await call_next(request)
        except Exception as exc:  # anything not already turned into an HTTP response
            exc_info = exc
            response = error_response(request, 500, "Internal server error")
        latency_ms = _ms_since(start)
        response.headers["X-Request-ID"] = request_id

        endpoint = _endpoint(request)
        request.app.state.metrics.record_request(endpoint, response.status_code, latency_ms)
        fields = {
            "request_id": request_id,
            "method": request.method,
            "endpoint": endpoint,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
        }
        for key in ("risk_level", "risk_levels", "batch_size", "error_code", "error_fields"):
            if hasattr(request.state, key):
                fields[key] = getattr(request.state, key)
        level = (logging.ERROR if response.status_code >= 500
                 else logging.WARNING if response.status_code >= 400 else logging.INFO)
        logger.log(level, "request", extra=fields, exc_info=exc_info)
        return response

    # Added last so it wraps everything: preflights are answered here (not counted in
    # /metrics) and error responses still carry CORS headers for the dashboard.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    def get_store(request: Request) -> ModelStore:
        store = request.app.state.store
        if store is None:
            raise HTTPException(status_code=503, detail="Model is not loaded yet")
        return store

    def get_storage(request: Request) -> TransactionStore:
        storage = request.app.state.storage
        if storage is None:
            raise HTTPException(status_code=503, detail="Transaction storage is not configured")
        return storage

    bearer = HTTPBearer(auto_error=False)

    def analyst_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Log in as an analyst: send "
                                "'Authorization: Bearer <Supabase access token>'",
                                headers={"WWW-Authenticate": "Bearer"})
        return credentials.credentials

    def analyst_id(request: Request, token: str = Depends(analyst_token)) -> str:
        """Ask Supabase Auth who the token belongs to (runs in a worker thread)."""
        storage = get_storage(request)
        try:
            return storage.verify_user(token)
        except InvalidToken:
            raise HTTPException(status_code=401, detail="Invalid or expired analyst token",
                                headers={"WWW-Authenticate": "Bearer"}) from None
        except StorageUnavailable as exc:
            logger.error("auth check failed", extra={
                "request_id": request.state.request_id, "error_type": str(exc)})
            raise HTTPException(status_code=503,
                                detail="Analyst login could not be checked") from None

    def get_demo(request: Request) -> DemoStreamer:
        demo = request.app.state.demo
        if demo is None:
            raise HTTPException(status_code=503, detail="The demo stream is not available "
                                "(it needs transaction storage and the demo rows file)")
        return demo

    def save_in_background(request: Request, background: BackgroundTasks,
                           transactions: list, scores: list[Score], latency_ms: float) -> list:
        """Give each row an id now and save the rows after the response is sent."""
        if request.app.state.storage is None:
            return [None] * len(scores)
        ids = [str(uuid.uuid4()) for _ in scores]
        background.add_task(_save, request.app, request.state.request_id, ids,
                            [t.model_dump() for t in transactions], scores,
                            request.app.state.store.version, latency_ms)
        return ids

    @app.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
    def health(request: Request):
        store: ModelStore | None = request.app.state.store
        if store is None:
            return JSONResponse(
                status_code=503, content={"status": "unavailable", "model_loaded": False}
            )
        return HealthResponse(
            status="ok",
            model_loaded=True,
            model_version=store.version,
            model_name=store.name,
            trained_at=store.trained_at,
        )

    @app.post("/predict", response_model=PredictResponse)
    def predict(transaction: Transaction, request: Request, background: BackgroundTasks,
                store: ModelStore = Depends(get_store)):
        start = time.perf_counter()
        score = score_frame(store, to_frame([transaction]))[0]
        request.state.risk_level = score.risk_level.value
        request.app.state.metrics.record_risk_levels([score.risk_level.value])
        latency_ms = _ms_since(start)
        [transaction_id] = save_in_background(request, background, [transaction], [score],
                                              latency_ms)
        return PredictResponse(**_scored(score), transaction_id=transaction_id,
                               model_version=store.version, latency_ms=latency_ms)

    @app.post("/predict/batch", response_model=BatchPredictResponse)
    def predict_batch(batch: BatchPredictRequest, request: Request, background: BackgroundTasks,
                      store: ModelStore = Depends(get_store)):
        start = time.perf_counter()
        scores = score_frame(store, to_frame(batch.transactions))  # one model call for all rows
        levels = [s.risk_level.value for s in scores]
        request.state.batch_size = len(scores)
        request.state.risk_levels = dict(Counter(levels))
        request.app.state.metrics.record_risk_levels(levels)
        latency_ms = _ms_since(start)
        ids = save_in_background(request, background, batch.transactions, scores, latency_ms)
        return BatchPredictResponse(
            results=[{**_scored(s), "transaction_id": i} for s, i in zip(scores, ids)],
            count=len(scores),
            model_version=store.version,
            latency_ms=latency_ms,
        )

    @app.post("/explain", response_model=ExplainResponse)
    def explain(transaction: Transaction, request: Request,
                store: ModelStore = Depends(get_store)):
        # An analyst looking at a transaction again: logged, but not added to the
        # risk-level counts in /metrics (those count scored traffic only).
        start = time.perf_counter()
        raw = to_frame([transaction])
        score = score_frame(store, raw)[0]
        request.state.risk_level = score.risk_level.value
        model_score, base_value, contributions = explain_row(store, raw)
        return ExplainResponse(
            **_scored(score),
            model_version=store.version,
            model_score=model_score,
            base_value=base_value,
            top_features=[asdict(c) for c in contributions],
            latency_ms=_ms_since(start),
        )

    @app.get("/explain/{transaction_id}", response_model=StoredExplainResponse,
             responses={401: {"description": "Missing or invalid analyst token"},
                        404: {"description": "No such transaction (or not visible to you)"},
                        503: {"description": "Model or storage unavailable"}})
    def explain_stored(transaction_id: UUID, request: Request,
                       store: ModelStore = Depends(get_store),
                       storage: TransactionStore = Depends(get_storage),
                       token: str = Depends(analyst_token)):
        """Explain a stored transaction. Read with the caller's login, so RLS applies."""
        start = time.perf_counter()
        try:
            row = storage.get(str(transaction_id), token)
        except InvalidToken:
            raise HTTPException(status_code=401, detail="Invalid or expired analyst token",
                                headers={"WWW-Authenticate": "Bearer"}) from None
        except StorageUnavailable as exc:
            logger.error("storage read failed", extra={
                "request_id": request.state.request_id, "error_type": str(exc)})
            raise HTTPException(status_code=503,
                                detail="Transaction storage is unavailable") from None
        if row is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        raw = stored_frame(row)
        score = score_frame(store, raw)[0]
        request.state.risk_level = score.risk_level.value
        model_score, base_value, contributions = explain_row(store, raw)
        return StoredExplainResponse(
            **_scored(score),
            transaction_id=transaction_id,
            created_at=row["created_at"],
            stored_probability=row["probability"],
            stored_model_version=row["model_version"],
            model_version=store.version,
            model_score=model_score,
            base_value=base_value,
            top_features=[asdict(c) for c in contributions],
            latency_ms=_ms_since(start),
        )

    @app.post("/demo/stream", status_code=202, response_model=DemoStreamStatus,
              responses={401: {"description": "Missing or invalid analyst token"},
                         409: {"description": "A demo stream is already running"},
                         429: {"description": "Started too recently (see Retry-After)"},
                         503: {"description": "Demo stream or storage unavailable"}})
    async def start_demo_stream(body: DemoStreamRequest | None = Body(default=None),
                                demo: DemoStreamer = Depends(get_demo),
                                user_id: str = Depends(analyst_id)):
        """Replay up to `max_rows` held-out test rows (~10/s) through the model and storage.

        Analysts only. Returns at once; poll `GET /demo/stream` for progress.
        """
        try:
            demo.start(user_id, body.limit if body else None)
        except DemoBusy:
            raise HTTPException(status_code=409, detail="A demo stream is already running") from None
        except DemoRateLimited as exc:
            raise HTTPException(status_code=429, detail=f"Try again later: {exc}",
                                headers={"Retry-After": retry_after_header(exc.retry_after_s)},
                                ) from None
        return demo.status()

    @app.get("/demo/stream", response_model=DemoStreamStatus,
             responses={503: {"description": "Demo stream unavailable"}})
    def demo_stream_status(demo: DemoStreamer = Depends(get_demo)):
        """Progress of the current or most recent demo stream."""
        return demo.status()

    @app.get("/metrics", response_model=MetricsResponse)
    def metrics(request: Request):
        """Request counts, latency percentiles, errors and risk levels since startup.

        In-memory and per worker process: numbers reset when the server restarts.
        """
        return request.app.state.metrics.snapshot()

    return app


def _save(app: FastAPI, request_id: str, ids: list[str], transactions: list[dict],
          scores: list[Score], model_version: str, latency_ms: float) -> None:
    """Background task: insert the rows; on any failure log it and count it, never raise."""
    try:
        rows = [build_row(i, t, s, model_version, latency_ms)
                for i, t, s in zip(ids, transactions, scores)]
        app.state.storage.save(rows)
    except Exception as exc:
        app.state.metrics.record_storage_write(ok=False, rows=len(ids))
        # Type and code only: database error messages can quote the row's values.
        logger.error("storage write failed", extra={
            "request_id": request_id, "rows": len(ids), "error_type": type(exc).__name__,
            "storage_error_code": getattr(exc, "code", None)})
    else:
        app.state.metrics.record_storage_write(ok=True, rows=len(ids))


def _build_demo(app: FastAPI, settings: Settings) -> DemoStreamer | None:
    """A demo streamer when storage is on and the demo rows file is present."""
    if app.state.storage is None:
        return None
    if not settings.demo_rows_path.exists():
        logger.warning("demo stream disabled: demo rows file not found",
                       extra={"path": str(settings.demo_rows_path)})
        return None
    return DemoStreamer(load_demo_rows(settings.demo_rows_path),
                        lambda row: _score_and_save_demo_row(app, row),
                        rate_per_s=settings.demo_rate_per_s, max_rows=settings.demo_max_rows,
                        cooldown_s=settings.demo_cooldown_s,
                        max_per_hour=settings.demo_max_per_hour)


def _score_and_save_demo_row(app: FastAPI, row: dict) -> None:
    """One demo row: score, count it in /metrics like /predict traffic, save (may raise)."""
    store: ModelStore = app.state.store
    start = time.perf_counter()
    score = score_frame(store, pd.DataFrame([row], columns=RAW_COLUMNS))[0]
    latency_ms = _ms_since(start)
    app.state.metrics.record_risk_levels([score.risk_level.value])
    try:
        app.state.storage.save([build_row(str(uuid.uuid4()), row, score, store.version,
                                          latency_ms)])
    except Exception:
        app.state.metrics.record_storage_write(ok=False, rows=1)
        raise
    app.state.metrics.record_storage_write(ok=True, rows=1)


def _endpoint(request: Request) -> str:
    """Route template (e.g. "POST /predict"), so unknown paths don't create new keys."""
    route = request.scope.get("route")
    return f"{request.method} {route.path}" if route is not None else "unmatched"


def _scored(score: Score) -> dict:
    return {
        "probability": score.probability,
        "risk_level": score.risk_level,
        "reasons": [asdict(r) for r in score.reasons],
    }


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


app = create_app()
