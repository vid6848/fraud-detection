"""Phase 3 step 4: GET /metrics, request IDs, JSON logging, error format."""
import json
import logging

import pytest
from fastapi.testclient import TestClient

from api.logging_setup import LOGGER_NAME, JsonFormatter
from api.main import create_app
from api.metrics import MetricsCollector
from api.schemas import EXAMPLE_TRANSACTION
from tests.api_support import make_settings
from tests.test_api_predict import FRAUD_ROW, MEDIUM_ROW

SECRET_AMOUNT = 4321.98  # a payload value we can search the logs for


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(self.format(record))

    def entries(self, message="request") -> list[dict]:
        return [e for e in map(json.loads, self.lines) if e["message"] == message]


@pytest.fixture
def client():
    """Fresh app per test, so metrics start from zero."""
    with TestClient(create_app(make_settings())) as c:
        yield c


@pytest.fixture
def logs(client):
    handler = ListHandler()
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


# --- GET /metrics ---

def test_metrics_start_empty(client):
    body = client.get("/metrics").json()
    assert body["requests"] == {"total": 0, "by_endpoint": {}}
    assert body["errors"] == {"total": 0, "by_status": {}}
    assert body["risk_levels"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    assert body["latency_ms"]["count"] == 0 and body["latency_ms"]["p50"] is None
    assert body["uptime_seconds"] >= 0
    assert "reset on restart" in body["scope"]


def test_metrics_count_requests_latency_and_risk(client):
    client.post("/predict", json=FRAUD_ROW)                    # HIGH
    client.post("/predict", json=EXAMPLE_TRANSACTION)          # LOW
    client.post("/predict/batch", json={"transactions": [FRAUD_ROW, MEDIUM_ROW, MEDIUM_ROW]})
    client.post("/explain", json=FRAUD_ROW)                    # not a risk count
    client.get("/health")
    body = client.get("/metrics").json()

    assert body["requests"]["by_endpoint"] == {
        "GET /health": 1, "POST /explain": 1, "POST /predict": 2, "POST /predict/batch": 1,
    }
    assert body["requests"]["total"] == 5
    assert body["risk_levels"] == {"LOW": 1, "MEDIUM": 2, "HIGH": 2}
    latency = body["latency_ms"]
    assert latency["count"] == 5
    assert 0 < latency["p50"] <= latency["p95"] <= latency["p99"]
    assert latency["by_endpoint"]["POST /predict"]["count"] == 2
    assert body["errors"]["total"] == 0


def test_metrics_count_errors(client):
    client.post("/predict", json={"Time": 1})
    client.get("/nope")
    client.get("/also-nope")
    body = client.get("/metrics").json()
    assert body["errors"] == {"total": 3, "by_status": {"404": 2, "422": 1}}
    assert body["requests"]["by_endpoint"]["unmatched"] == 2  # unknown paths share one key
    assert body["risk_levels"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 0}


def test_metrics_counts_itself_after_responding(client):
    client.get("/metrics")
    assert client.get("/metrics").json()["requests"]["by_endpoint"] == {"GET /metrics": 1}


def test_collector_window_is_bounded():
    m = MetricsCollector(window=3)
    for ms in [100.0, 1.0, 2.0, 3.0]:
        m.record_request("GET /x", 200, ms)
    snap = m.snapshot()
    assert snap["requests"]["total"] == 4          # counts are exact
    assert snap["latency_ms"]["count"] == 3        # percentiles use the last 3 only
    assert snap["latency_ms"]["p99"] < 100


# --- request IDs ---

def test_every_response_has_a_request_id(client):
    ids = {client.get("/health").headers["X-Request-ID"] for _ in range(3)}
    assert len(ids) == 3
    assert all(len(i) == 32 for i in ids)


def test_client_request_id_is_kept(client):
    r = client.get("/health", headers={"X-Request-ID": "sim-run-7.42"})
    assert r.headers["X-Request-ID"] == "sim-run-7.42"


@pytest.mark.parametrize("bad", ["has space", "x" * 65, "quote\"inject", ""])
def test_unsafe_request_id_is_replaced(client, bad):
    r = client.get("/health", headers={"X-Request-ID": bad})
    assert r.headers["X-Request-ID"] != bad
    assert len(r.headers["X-Request-ID"]) == 32


# --- structured logging ---

def test_one_json_log_line_per_request(client, logs):
    r = client.post("/predict", json=FRAUD_ROW)
    [entry] = logs.entries()
    assert entry["request_id"] == r.headers["X-Request-ID"]
    assert entry["endpoint"] == "POST /predict"
    assert entry["status"] == 200
    assert entry["latency_ms"] > 0
    assert entry["risk_level"] == "HIGH"
    assert entry["level"] == "INFO"


def test_batch_log_has_counts(client, logs):
    client.post("/predict/batch", json={"transactions": [FRAUD_ROW, MEDIUM_ROW]})
    [entry] = logs.entries()
    assert entry["batch_size"] == 2
    assert entry["risk_levels"] == {"HIGH": 1, "MEDIUM": 1}


def test_logs_never_contain_the_payload(client, logs):
    row = {**EXAMPLE_TRANSACTION, "Amount": SECRET_AMOUNT}
    client.post("/predict", json=row)
    client.post("/explain", json=row)
    client.post("/predict/batch", json={"transactions": [row]})
    client.post("/predict", json={**row, "Time": -1})  # 422 path too
    assert len(logs.entries()) == 4
    assert all(str(SECRET_AMOUNT) not in line for line in logs.lines)


def test_validation_error_logged_with_fields_not_values(client, logs):
    client.post("/predict", json={**EXAMPLE_TRANSACTION, "Amount": -SECRET_AMOUNT})
    [entry] = logs.entries()
    assert entry["level"] == "WARNING"
    assert entry["status"] == 422
    assert entry["error_code"] == "validation_error"
    assert entry["error_fields"] == ["body.Amount"]
    assert str(SECRET_AMOUNT) not in logs.lines[0]


# --- error format ---

def _assert_error(r, status, code):
    assert r.status_code == status
    error = r.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == r.headers["X-Request-ID"]
    return error


def test_422_format_lists_fields_without_values(client):
    r = client.post("/predict", json={**EXAMPLE_TRANSACTION, "Amount": -SECRET_AMOUNT})
    error = _assert_error(r, 422, "validation_error")
    assert error["details"] == [{
        "loc": ["body", "Amount"],
        "message": "Input should be greater than or equal to 0",
        "type": "greater_than_equal",
    }]
    assert str(SECRET_AMOUNT) not in r.text


def test_malformed_json_is_422(client):
    r = client.post("/predict", content=b"{not json", headers={"Content-Type": "application/json"})
    _assert_error(r, 422, "validation_error")


def test_404_format(client):
    error = _assert_error(client.get("/does-not-exist"), 404, "not_found")
    assert error["message"] == "Not Found"


def test_405_format(client):
    r = client.get("/predict")
    _assert_error(r, 405, "method_not_allowed")
    assert r.headers["allow"] == "POST"


def test_500_hides_internals(client, logs, monkeypatch):
    def boom(X):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(client.app.state.store.model, "predict_proba", boom)
    r = client.post("/predict", json=FRAUD_ROW)
    error = _assert_error(r, 500, "internal_error")
    assert error["message"] == "Internal server error"
    assert "secret" not in r.text and "Traceback" not in r.text

    [entry] = logs.entries()  # the details go to the server log instead
    assert entry["level"] == "ERROR"
    assert entry["status"] == 500
    assert entry["request_id"] == error["request_id"]
    assert "RuntimeError: secret internal detail" in entry["exception"]
    assert client.get("/metrics").json()["errors"]["by_status"] == {"500": 1}


def test_503_when_model_not_loaded():
    c = TestClient(create_app(make_settings()))  # no context manager: startup never runs
    _assert_error(c.post("/predict", json=FRAUD_ROW), 503, "service_unavailable")
