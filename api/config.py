"""API settings, read from environment variables (and `.env` if present).

Relative paths are resolved against the repo root, so the API works no matter
which directory `uvicorn` is started from.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from ml.config import ROOT

DEFAULT_MODEL_PATH = "ml/artifacts/model.joblib"
DEFAULT_METADATA_PATH = "ml/artifacts/metadata.json"

# LOW < MEDIUM_THRESHOLD <= MEDIUM < high threshold (from metadata.json) <= HIGH.
# 0.05 chosen on the validation set: 18 of 42,722 rows, 4 of them fraud (see README "API").
DEFAULT_MEDIUM_THRESHOLD = 0.05
DEFAULT_MAX_BATCH_SIZE = 1000
DEFAULT_STORAGE_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Settings:
    model_path: Path
    metadata_path: Path
    medium_threshold: float = DEFAULT_MEDIUM_THRESHOLD
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE
    log_level: str = "INFO"
    # Supabase storage (optional: without it the API scores but stores nothing).
    # Keys are kept out of repr() so they can't leak into logs or tracebacks.
    supabase_url: str | None = None
    supabase_service_role_key: str | None = field(default=None, repr=False)
    supabase_anon_key: str | None = field(default=None, repr=False)
    storage_timeout_s: float = DEFAULT_STORAGE_TIMEOUT_S

    @property
    def storage_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key
                    and self.supabase_anon_key)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from the environment; `.env` fills in anything not already set."""
        load_dotenv(ROOT / ".env", override=False)
        return cls(
            model_path=_resolve(os.getenv("MODEL_PATH", DEFAULT_MODEL_PATH)),
            metadata_path=_resolve(os.getenv("METADATA_PATH", DEFAULT_METADATA_PATH)),
            medium_threshold=float(os.getenv("MEDIUM_THRESHOLD", DEFAULT_MEDIUM_THRESHOLD)),
            max_batch_size=int(os.getenv("MAX_BATCH_SIZE", DEFAULT_MAX_BATCH_SIZE)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            supabase_url=_optional("SUPABASE_URL"),
            supabase_service_role_key=_optional("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_anon_key=_optional("SUPABASE_ANON_KEY"),
            storage_timeout_s=float(os.getenv("STORAGE_TIMEOUT_S", DEFAULT_STORAGE_TIMEOUT_S)),
        )


def _optional(name: str) -> str | None:
    """An env var, treating empty values and `.env.example` placeholders as unset."""
    value = os.getenv(name, "").strip()
    return None if not value or "your-" in value else value


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
