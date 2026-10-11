"""Shared helpers for the API tests (real tracked artifacts, no dataset needed)."""
from api.config import Settings
from ml.config import ARTIFACTS_DIR


def make_settings(**overrides) -> Settings:
    values = {
        "model_path": ARTIFACTS_DIR / "model.joblib",
        "metadata_path": ARTIFACTS_DIR / "metadata.json",
    }
    return Settings(**{**values, **overrides})
