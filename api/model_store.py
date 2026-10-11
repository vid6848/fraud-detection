"""Loads the trained model and its metadata once, at API startup."""
import json
from dataclasses import dataclass
from pathlib import Path

import joblib

import ml  # noqa: F401  (model.joblib pickles ml.calibration.CalibratedModel)
from api.config import Settings
from ml.config import RAW_COLUMNS
from ml.explain import make_explainer
from ml.models import final_estimator


class ModelLoadError(RuntimeError):
    """The model or its metadata is missing or doesn't match what the API expects."""


@dataclass(frozen=True)
class ModelStore:
    model: object
    metadata: dict
    medium_threshold: float
    explainer: object  # SHAP explainer for model.base, built once

    @property
    def version(self) -> str:
        return self.metadata["model_version"]

    @property
    def name(self) -> str:
        return self.metadata["model"]["name"]

    @property
    def trained_at(self) -> str:
        return self.metadata["trained_at"]

    @property
    def high_threshold(self) -> float:
        """Cost-optimal threshold tuned on validation in Phase 2."""
        return float(self.metadata["threshold"])

    @classmethod
    def load(cls, settings: Settings) -> "ModelStore":
        metadata = _read_metadata(settings.metadata_path)
        model = _read_model(settings.model_path)
        if metadata.get("input_columns") != RAW_COLUMNS:
            raise ModelLoadError(
                f"metadata input_columns don't match the API schema {RAW_COLUMNS}"
            )
        if not 0 < settings.medium_threshold < float(metadata["threshold"]):
            raise ModelLoadError(
                f"MEDIUM_THRESHOLD={settings.medium_threshold} must be between 0 and the "
                f"HIGH threshold {metadata['threshold']:.3f}"
            )
        _use_single_thread(model)
        # Tree SHAP needs no background data; a linear model would need training rows here.
        explainer = make_explainer(model.base, train_rows=None)
        return cls(model=model, metadata=metadata, medium_threshold=settings.medium_threshold,
                   explainer=explainer)


def _use_single_thread(model) -> None:
    """Score with one thread. For the 1-1000 rows the API sees, starting a thread pool
    costs more than the trees themselves (1 row: ~15 ms -> ~5 ms). Scores are unchanged."""
    estimator = final_estimator(model.base)
    if hasattr(estimator, "n_jobs"):
        estimator.n_jobs = 1


def _read_metadata(path: Path) -> dict:
    if not path.exists():
        raise ModelLoadError(f"metadata file not found: {path} (run `python -m ml.train`)")
    return json.loads(path.read_text())


def _read_model(path: Path):
    if not path.exists():
        raise ModelLoadError(f"model file not found: {path} (run `python -m ml.train`)")
    model = joblib.load(path)
    if not hasattr(model, "predict_proba"):
        raise ModelLoadError(f"{path} does not contain a classifier with predict_proba")
    return model
