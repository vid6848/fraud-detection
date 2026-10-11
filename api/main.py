"""FastAPI app. Run with: uvicorn api.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.config import Settings
from api.model_store import ModelStore
from api.schemas import HealthResponse

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

    return app


app = create_app()
