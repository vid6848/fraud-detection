"""Loads the trained model and its metadata once, at API startup."""
import json
from dataclasses import dataclass
from pathlib import Path

import joblib

import ml  # noqa: F401  (model.joblib pickles ml.calibration.CalibratedModel)
from api.config import Settings
from ml.config import RAW_COLUMNS


class ModelLoadError(RuntimeError):
    """The model or its metadata is missing or doesn't match what the API expects."""


@dataclass(frozen=True)
class ModelStore:
    model: object
    metadata: dict
    medium_threshold: float

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
        return cls(model=model, metadata=metadata, medium_threshold=settings.medium_threshold)


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
