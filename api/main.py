"""FastAPI app. Run with: uvicorn api.main:app --reload

Every request passes through `observe` (below), which gives it a request ID
(returned as the X-Request-ID header), times it, records it in /metrics, writes
one JSON log line, and turns unexpected exceptions into a clean 500.
"""
import logging
import re
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.config import Settings
from api.errors import error_response, register_error_handlers
from api.explanations import explain_row
from api.logging_setup import LOGGER_NAME, configure_logging
from api.metrics import MetricsCollector
from api.model_store import ModelStore
from api.schemas import (
    BatchPredictResponse,
    ExplainResponse,
    HealthResponse,
    MetricsResponse,
    PredictResponse,
    Transaction,
    make_batch_request,
    to_frame,
)
from api.scoring import Score, score_frame

logger = logging.getLogger(LOGGER_NAME)

# A client may send its own X-Request-ID (to trace a call end to end); anything
# else, or nothing, gets a fresh one. The pattern keeps log lines safe.
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        app.state.store = ModelStore.load(settings)  # once per process, not per request
        logger.info("model loaded", extra={"model_version": app.state.store.version,
                                           "model_path": str(settings.model_path)})
        yield
        app.state.store = None

    app = FastAPI(
        title="Fraud Detection API",
        description="Scores credit card transactions for fraud risk.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    BatchPredictRequest = make_batch_request(settings.max_batch_size)
    app.state.store = None
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

    def get_store(request: Request) -> ModelStore:
        store = request.app.state.store
        if store is None:
            raise HTTPException(status_code=503, detail="Model is not loaded yet")
        return store

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
    def predict(transaction: Transaction, request: Request,
                store: ModelStore = Depends(get_store)):
        start = time.perf_counter()
        score = score_frame(store, to_frame([transaction]))[0]
        request.state.risk_level = score.risk_level.value
        request.app.state.metrics.record_risk_levels([score.risk_level.value])
        return PredictResponse(**_scored(score), model_version=store.version,
                               latency_ms=_ms_since(start))

    @app.post("/predict/batch", response_model=BatchPredictResponse)
    def predict_batch(batch: BatchPredictRequest, request: Request,
                      store: ModelStore = Depends(get_store)):
        start = time.perf_counter()
        scores = score_frame(store, to_frame(batch.transactions))  # one model call for all rows
        levels = [s.risk_level.value for s in scores]
        request.state.batch_size = len(scores)
        request.state.risk_levels = dict(Counter(levels))
        request.app.state.metrics.record_risk_levels(levels)
        return BatchPredictResponse(
            results=[_scored(s) for s in scores],
            count=len(scores),
            model_version=store.version,
            latency_ms=_ms_since(start),
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

    @app.get("/metrics", response_model=MetricsResponse)
    def metrics(request: Request):
        """Request counts, latency percentiles, errors and risk levels since startup.

        In-memory and per worker process: numbers reset when the server restarts.
        """
        return request.app.state.metrics.snapshot()

    return app


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
