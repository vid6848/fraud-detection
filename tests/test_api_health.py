"""Phase 3 step 1: settings, model loading, request schema, GET /health.

Uses the real tracked artifacts in ml/artifacts/, so no dataset is needed.
"""
import json
import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.config import DEFAULT_MEDIUM_THRESHOLD, Settings
from api.main import create_app
from api.model_store import ModelLoadError, ModelStore
from api.schemas import EXAMPLE_TRANSACTION, Transaction, to_frame
from ml.config import ARTIFACTS_DIR, RAW_COLUMNS
from tests.api_support import make_settings as settings

METADATA = json.loads((ARTIFACTS_DIR / "metadata.json").read_text())


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(settings())) as c:
        yield c


# --- /health ---

def test_health_reports_loaded_model(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == METADATA["model_version"]
    assert body["model_name"] == METADATA["model"]["name"]
    assert body["trained_at"] == METADATA["trained_at"]


def test_model_loaded_once(client):
    store = client.app.state.store
    client.get("/health")
    client.get("/health")
    assert client.app.state.store is store


def test_health_503_before_startup():
    # Without the context manager the lifespan never runs, so no model is loaded.
    r = TestClient(create_app(settings())).get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable", "model_loaded": False}


def test_bad_model_path_fails_startup(tmp_path):
    app = create_app(settings(model_path=tmp_path / "missing.joblib"))
    with pytest.raises(ModelLoadError, match="model file not found"):
        with TestClient(app):
            pass


# --- model store ---

def test_store_thresholds():
    store = ModelStore.load(settings())
    assert store.high_threshold == pytest.approx(METADATA["threshold"])
    assert store.medium_threshold == DEFAULT_MEDIUM_THRESHOLD < store.high_threshold
    assert hasattr(store.model, "predict_proba")


@pytest.mark.parametrize("medium", [0.0, 0.9])
def test_store_rejects_bad_medium_threshold(medium):
    with pytest.raises(ModelLoadError, match="MEDIUM_THRESHOLD"):
        ModelStore.load(settings(medium_threshold=medium))


def test_store_rejects_mismatched_columns(tmp_path):
    meta = {**METADATA, "input_columns": RAW_COLUMNS[:-1]}
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(meta))
    with pytest.raises(ModelLoadError, match="input_columns"):
        ModelStore.load(settings(metadata_path=path))


def test_store_missing_metadata(tmp_path):
    with pytest.raises(ModelLoadError, match="metadata file not found"):
        ModelStore.load(settings(metadata_path=tmp_path / "nope.json"))


# --- settings ---

def test_settings_defaults(monkeypatch):
    for var in ["MODEL_PATH", "METADATA_PATH", "MEDIUM_THRESHOLD", "MAX_BATCH_SIZE", "LOG_LEVEL"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("api.config.load_dotenv", lambda *a, **k: None)  # ignore local .env
    s = Settings.from_env()
    assert s.model_path == ARTIFACTS_DIR / "model.joblib"
    assert s.metadata_path == ARTIFACTS_DIR / "metadata.json"
    assert s.medium_threshold == DEFAULT_MEDIUM_THRESHOLD
    assert s.max_batch_size == 1000
    assert s.log_level == "INFO"


def test_settings_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "m.joblib"))
    monkeypatch.setenv("METADATA_PATH", "custom/meta.json")
    monkeypatch.setenv("MEDIUM_THRESHOLD", "0.1")
    monkeypatch.setenv("MAX_BATCH_SIZE", "50")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    s = Settings.from_env()
    assert s.model_path == tmp_path / "m.joblib"  # absolute path kept as-is
    assert s.metadata_path == ARTIFACTS_DIR.parent.parent / "custom" / "meta.json"
    assert s.medium_threshold == 0.1
    assert s.max_batch_size == 50
    assert s.log_level == "DEBUG"


# --- Transaction schema ---

def test_transaction_accepts_example():
    t = Transaction(**EXAMPLE_TRANSACTION)
    assert t.Amount == 42.5


def test_to_frame_column_order():
    rows = [Transaction(**EXAMPLE_TRANSACTION), Transaction(**{**EXAMPLE_TRANSACTION, "V3": 1.5})]
    df = to_frame(rows)
    assert list(df.columns) == RAW_COLUMNS
    assert df.shape == (2, 30)
    assert df.loc[1, "V3"] == 1.5


def test_transaction_requires_all_v_columns():
    payload = {k: v for k, v in EXAMPLE_TRANSACTION.items() if k != "V14"}
    with pytest.raises(ValidationError, match="V14"):
        Transaction(**payload)


@pytest.mark.parametrize(
    "field, value",
    [
        ("Amount", -1.0),
        ("Time", -5.0),
        ("V1", math.nan),
        ("V2", math.inf),
        ("Amount", "lots"),
        ("V7", None),
    ],
)
def test_transaction_rejects_bad_values(field, value):
    with pytest.raises(ValidationError, match=field):
        Transaction(**{**EXAMPLE_TRANSACTION, field: value})


def test_transaction_rejects_unknown_field():
    with pytest.raises(ValidationError, match="amount"):
        Transaction(**{**EXAMPLE_TRANSACTION, "amount": 10.0})


def test_transaction_schema_lists_all_fields():
    assert list(Transaction.model_json_schema()["properties"]) == RAW_COLUMNS
