"""Phase 4 step 3: saving scored transactions, storage failures, GET /explain/{id}.

Supabase is never called here: endpoint tests inject a FakeStore, and SupabaseStore
itself is tested against httpx.MockTransport (real PostgREST client, fake server).
"""
import json
import logging
import uuid

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.config import Settings
from api.logging_setup import LOGGER_NAME
from api.main import create_app
from api.risk import Reason, RiskLevel
from api.schemas import EXAMPLE_TRANSACTION
from api.scoring import Score
from api.storage import (
    InvalidToken,
    StorageUnavailable,
    SupabaseStore,
    build_row,
    build_store,
    stored_frame,
)
from ml.config import RAW_COLUMNS
from ml.features import V_COLUMNS
from tests.api_support import make_settings
from tests.test_api_predict import FRAUD_ROW, MEDIUM_ROW

TOKEN = "analyst-jwt"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
STORAGE_SETTINGS = {
    "supabase_url": "https://example.supabase.co",
    "supabase_service_role_key": "service-key",
    "supabase_anon_key": "anon-key",
}


class FakeStore:
    def __init__(self, fail: bool = False, get_error: Exception | None = None):
        self.fail = fail
        self.get_error = get_error
        self.saved: list[list[dict]] = []  # one entry per save() call
        self.rows: dict[str, dict] = {}
        self.tokens: list[str] = []

    def save(self, rows):
        if self.fail:
            raise ConnectionError("supabase is down")
        self.saved.append(rows)
        for row in rows:
            self.rows[row["id"]] = {**row, "created_at": "2026-10-17T10:00:00+00:00"}

    def get(self, transaction_id, user_token):
        self.tokens.append(user_token)
        if self.get_error is not None:
            raise self.get_error
        return self.rows.get(transaction_id)


class Logs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def make_client(store) -> TestClient:
    return TestClient(create_app(make_settings(), storage=store))


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def client(store):
    with make_client(store) as c:
        yield c


@pytest.fixture
def logs():
    handler = Logs()
    logging.getLogger(LOGGER_NAME).addHandler(handler)
    yield handler
    logging.getLogger(LOGGER_NAME).removeHandler(handler)


# --- saving --------------------------------------------------------------------

def test_predict_saves_the_scored_transaction(client, store):
    body = client.post("/predict", json=FRAUD_ROW).json()
    [[row]] = store.saved
    assert row["id"] == body["transaction_id"]
    assert row["probability"] == body["probability"]
    assert row["risk_level"] == "HIGH"
    assert row["reasons"] == body["reasons"]
    assert row["model_version"] == body["model_version"]
    assert row["latency_ms"] == body["latency_ms"]
    assert row["time_seconds"] == FRAUD_ROW["Time"]
    assert row["amount"] == FRAUD_ROW["Amount"]
    assert row["hour_of_day"] == 12  # 133,184 s -> 12:59 on day 2
    assert row["features"] == {v: FRAUD_ROW[v] for v in V_COLUMNS}


def test_batch_is_saved_in_one_call_in_order(client, store):
    rows = [FRAUD_ROW, EXAMPLE_TRANSACTION, MEDIUM_ROW]
    body = client.post("/predict/batch", json={"transactions": rows}).json()
    [saved] = store.saved
    assert [r["id"] for r in saved] == [r["transaction_id"] for r in body["results"]]
    assert [r["risk_level"] for r in saved] == ["HIGH", "LOW", "MEDIUM"]
    assert len({r["id"] for r in saved}) == 3


def test_ids_are_uuids(client):
    body = client.post("/predict", json=EXAMPLE_TRANSACTION).json()
    assert uuid.UUID(body["transaction_id"]).version == 4


def test_successful_writes_are_counted(client):
    client.post("/predict", json=EXAMPLE_TRANSACTION)
    client.post("/predict/batch", json={"transactions": [EXAMPLE_TRANSACTION] * 4})
    storage = client.get("/metrics").json()["storage"]
    assert storage == {"enabled": True, "writes_ok": 2, "writes_failed": 0,
                       "rows_written": 5, "rows_failed": 0}


def test_explain_post_is_not_saved(client, store):
    client.post("/explain", json=FRAUD_ROW)
    assert store.saved == []


def test_storage_failure_does_not_fail_scoring(logs):
    with make_client(FakeStore(fail=True)) as client:
        r = client.post("/predict/batch", json={"transactions": [FRAUD_ROW, MEDIUM_ROW]})
        assert r.status_code == 200
        assert [x["risk_level"] for x in r.json()["results"]] == ["HIGH", "MEDIUM"]
        storage = client.get("/metrics").json()["storage"]
    assert storage["writes_failed"] == 1 and storage["rows_failed"] == 2
    assert storage["writes_ok"] == 0
    [failure] = [rec for rec in logs.records if rec.getMessage() == "storage write failed"]
    assert failure.levelno == logging.ERROR
    assert failure.rows == 2 and failure.error_type == "ConnectionError"
    assert failure.request_id == r.headers["X-Request-ID"]


def test_no_storage_configured():
    with TestClient(create_app(make_settings())) as client:
        assert client.post("/predict", json=EXAMPLE_TRANSACTION).json()["transaction_id"] is None
        assert client.get("/metrics").json()["storage"]["enabled"] is False
        r = client.get(f"/explain/{uuid.uuid4()}", headers=AUTH)
    assert r.status_code == 503
    assert r.json()["error"]["message"] == "Transaction storage is not configured"


def test_startup_warns_when_storage_is_off(logs):
    with TestClient(create_app(make_settings())):
        pass
    assert any(rec.getMessage().startswith("storage disabled") for rec in logs.records)


# --- GET /explain/{id} ---------------------------------------------------------

def test_explain_stored_matches_explain_post(client, store):
    transaction_id = client.post("/predict", json=FRAUD_ROW).json()["transaction_id"]
    stored = client.get(f"/explain/{transaction_id}", headers=AUTH)
    fresh = client.post("/explain", json=FRAUD_ROW).json()
    assert stored.status_code == 200
    body = stored.json()
    assert body["transaction_id"] == transaction_id
    assert body["probability"] == pytest.approx(fresh["probability"])
    assert body["stored_probability"] == pytest.approx(fresh["probability"])
    assert body["stored_model_version"] == fresh["model_version"]
    assert body["top_features"] == fresh["top_features"]
    assert body["created_at"].startswith("2026-10-17T10:00:00")
    assert store.tokens == [TOKEN]  # read with the caller's token, so RLS applies


def test_explain_stored_is_not_counted_as_scored_traffic(client):
    transaction_id = client.post("/predict", json=FRAUD_ROW).json()["transaction_id"]
    client.get(f"/explain/{transaction_id}", headers=AUTH)
    assert client.get("/metrics").json()["risk_levels"]["HIGH"] == 1


def test_explain_stored_needs_a_token(client):
    r = client.get(f"/explain/{uuid.uuid4()}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_explain_stored_unknown_id(client):
    r = client.get(f"/explain/{uuid.uuid4()}", headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_explain_stored_rejects_bad_id(client):
    assert client.get("/explain/not-a-uuid", headers=AUTH).status_code == 422


@pytest.mark.parametrize("error, status", [
    (InvalidToken("JWT expired"), 401),
    (StorageUnavailable("ConnectTimeout"), 503),
])
def test_explain_stored_storage_errors(error, status, logs):
    with make_client(FakeStore(get_error=error)) as client:
        r = client.get(f"/explain/{uuid.uuid4()}", headers=AUTH)
    assert r.status_code == status
    if status == 503:
        assert any(rec.getMessage() == "storage read failed" for rec in logs.records)


# --- rows ----------------------------------------------------------------------

def test_stored_row_rebuilds_the_exact_model_input():
    score = Score(0.5, RiskLevel.MEDIUM, [Reason("TINY_AMOUNT", "tiny")])
    row = build_row("id-1", FRAUD_ROW, score, "1.0.0", 3.2)
    json.dumps(row)  # must be JSON-serializable for PostgREST
    assert row["reasons"] == [{"code": "TINY_AMOUNT", "message": "tiny"}]
    expected = pd.DataFrame([FRAUD_ROW], columns=RAW_COLUMNS)
    pd.testing.assert_frame_equal(stored_frame(row), expected)


def test_stored_frame_accepts_numeric_strings():
    # Postgres numeric can come back from PostgREST as a string.
    row = build_row("id-1", FRAUD_ROW, Score(0.1, RiskLevel.LOW, []), "1.0.0", 1.0)
    row["amount"] = "1335.00"
    assert stored_frame(row)["Amount"].iloc[0] == 1335.0


# --- settings ------------------------------------------------------------------

def test_settings_read_supabase_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-service-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("STORAGE_TIMEOUT_S", "2.5")
    settings = Settings.from_env()
    assert settings.storage_configured
    assert settings.storage_timeout_s == 2.5
    assert "secret-service-key" not in repr(settings)
    assert "anon-key" not in repr(settings)


def test_settings_ignore_placeholders(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://your-project-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "")
    settings = Settings.from_env()
    assert settings.supabase_url is None and settings.supabase_anon_key is None
    assert not settings.storage_configured


def test_build_store():
    assert build_store(make_settings()) is None
    assert build_store(make_settings(supabase_url="https://x.supabase.co")) is None
    store = build_store(make_settings(**STORAGE_SETTINGS))
    assert isinstance(store, SupabaseStore)
    store.close()


def test_app_builds_and_closes_its_own_store():
    app = create_app(make_settings(**STORAGE_SETTINGS))
    with TestClient(app) as client:
        store = app.state.storage
        assert isinstance(store, SupabaseStore)
        assert client.get("/metrics").json()["storage"]["enabled"] is True
    assert store._http.is_closed and app.state.storage is None


# --- SupabaseStore over a fake PostgREST ---------------------------------------

def mock_store(handler) -> tuple[SupabaseStore, list[httpx.Request]]:
    requests = []

    def record(request):
        requests.append(request)
        return handler(request)

    store = SupabaseStore("https://example.supabase.co/", "service-key", "anon-key",
                          timeout=1.0, transport=httpx.MockTransport(record))
    return store, requests


def test_save_posts_rows_with_the_service_key():
    store, requests = mock_store(lambda r: httpx.Response(201))
    store.save([{"id": "a"}, {"id": "b"}])
    [req] = requests
    assert req.method == "POST"
    assert req.url.path == "/rest/v1/transactions"
    assert req.headers["apikey"] == "service-key"
    assert req.headers["Authorization"] == "Bearer service-key"
    assert "return=minimal" in req.headers["Prefer"]
    assert json.loads(req.content) == [{"id": "a"}, {"id": "b"}]


def test_save_raises_on_errors():
    store, _ = mock_store(lambda r: httpx.Response(500, json={"code": "XX000", "message": "boom"}))
    with pytest.raises(APIError):  # caught, logged and counted by the background task
        store.save([{"id": "a"}])


def test_get_reads_with_the_callers_token():
    row = {"id": "a", "probability": 0.9}
    store, requests = mock_store(lambda r: httpx.Response(200, json=[row]))
    assert store.get("a", "user-jwt") == row
    [req] = requests
    assert req.method == "GET"
    assert req.headers["apikey"] == "anon-key"
    assert req.headers["Authorization"] == "Bearer user-jwt"  # not the service key
    assert req.url.params["id"] == "eq.a"


def test_get_returns_none_when_hidden_or_missing():
    store, _ = mock_store(lambda r: httpx.Response(200, json=[]))
    assert store.get("a", "user-jwt") is None


def test_get_maps_rejected_tokens():
    store, _ = mock_store(lambda r: httpx.Response(
        401, json={"code": "PGRST301", "message": "JWT expired", "details": None, "hint": None}))
    with pytest.raises(InvalidToken):
        store.get("a", "old-jwt")


def test_get_maps_server_errors():
    store, _ = mock_store(lambda r: httpx.Response(
        500, json={"code": "XX000", "message": "boom", "details": None, "hint": None}))
    with pytest.raises(StorageUnavailable, match="XX000"):
        store.get("a", "user-jwt")


def test_get_maps_gateway_errors():
    store, _ = mock_store(lambda r: httpx.Response(502, text="<html>Bad gateway</html>"))
    with pytest.raises(StorageUnavailable, match="502"):
        store.get("a", "user-jwt")


def test_get_maps_network_errors():
    def down(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    store, _ = mock_store(down)
    with pytest.raises(StorageUnavailable, match="ConnectTimeout"):
        store.get("a", "user-jwt")
