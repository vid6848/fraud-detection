"""FastAPI app. Run with: uvicorn api.main:app --reload"""
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.config import Settings
from api.model_store import ModelStore
from api.explanations import explain_row
from api.schemas import (
    BatchPredictResponse,
    ExplainResponse,
    HealthResponse,
    PredictResponse,
    Transaction,
    make_batch_request,
    to_frame,
)
from api.scoring import Score, score_frame

logger = logging.getLogger("api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=settings.log_level)
        app.state.store = ModelStore.load(settings)  # once per process, not per request
        logger.info("loaded model %s from %s", app.state.store.version, settings.model_path)
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
    def predict(transaction: Transaction, request: Request):
        start = time.perf_counter()
        store: ModelStore = request.app.state.store
        score = score_frame(store, to_frame([transaction]))[0]
        return PredictResponse(**_scored(score), model_version=store.version,
                               latency_ms=_ms_since(start))

    @app.post("/predict/batch", response_model=BatchPredictResponse)
    def predict_batch(batch: BatchPredictRequest, request: Request):
        start = time.perf_counter()
        store: ModelStore = request.app.state.store
        scores = score_frame(store, to_frame(batch.transactions))  # one model call for all rows
        return BatchPredictResponse(
            results=[_scored(s) for s in scores],
            count=len(scores),
            model_version=store.version,
            latency_ms=_ms_since(start),
        )

    @app.post("/explain", response_model=ExplainResponse)
    def explain(transaction: Transaction, request: Request):
        start = time.perf_counter()
        store: ModelStore = request.app.state.store
        raw = to_frame([transaction])
        score = score_frame(store, raw)[0]
        model_score, base_value, contributions = explain_row(store, raw)
        return ExplainResponse(
            **_scored(score),
            model_version=store.version,
            model_score=model_score,
            base_value=base_value,
            top_features=[asdict(c) for c in contributions],
            latency_ms=_ms_since(start),
        )

    return app


def _scored(score: Score) -> dict:
    return {
        "probability": score.probability,
        "risk_level": score.risk_level,
        "reasons": [asdict(r) for r in score.reasons],
    }


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


app = create_app()
