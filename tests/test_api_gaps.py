"""Phase 3 step 5: edge cases not covered by the per-step API tests."""
import logging
import threading

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.isotonic import IsotonicRegression

from api.logging_setup import LOGGER_NAME, configure_logging
from api.main import create_app
from api.metrics import MetricsCollector
from api.model_store import ModelLoadError, ModelStore
from api.schemas import EXAMPLE_TRANSACTION
from ml.calibration import CalibratedModel
from ml.config import RAW_COLUMNS, TARGET
from ml.models import build_pipeline
from tests.api_support import make_settings
from tests.synthetic import make_transactions
from tests.test_api_predict import FRAUD_ROW


def test_store_rejects_non_classifier(tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump({"not": "a model"}, path)
    with pytest.raises(ModelLoadError, match="predict_proba"):
        ModelStore.load(make_settings(model_path=path))


def test_store_serves_a_model_without_n_jobs(tmp_path):
    """A decision tree has no n_jobs: loading must still work, and /explain too."""
    df = make_transactions(2_000, fraud_rate=0.05)
    X, y = df[RAW_COLUMNS], df[TARGET]
    base = build_pipeline("decision_tree", "none", {"max_depth": 3}, y).fit(X, y)
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(base.predict_proba(X)[:, 1], y)
    path = tmp_path / "tree.joblib"
    joblib.dump(CalibratedModel(base, calibrator, "isotonic"), path)

    with TestClient(create_app(make_settings(model_path=path))) as client:
        assert client.post("/predict", json=FRAUD_ROW).status_code == 200
        assert len(client.post("/explain", json=FRAUD_ROW).json()["top_features"]) == 5


@pytest.mark.parametrize(
    "path, payload",
    [("/predict/batch", {"transactions": [EXAMPLE_TRANSACTION]}),
     ("/explain", EXAMPLE_TRANSACTION)],
)
def test_scoring_endpoints_503_before_startup(path, payload):
    r = TestClient(create_app(make_settings())).post(path, json=payload)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "service_unavailable"


def test_openapi_lists_every_endpoint():
    with TestClient(create_app(make_settings())) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert client.get("/docs").status_code == 200
    assert set(paths) == {"/health", "/predict", "/predict/batch", "/explain",
                          "/explain/{transaction_id}", "/metrics", "/demo/stream", "/drift"}
    assert set(paths["/predict"]) == {"post"}
    assert set(paths["/demo/stream"]) == {"get", "post"}


def test_configure_logging_twice_does_not_duplicate_lines():
    configure_logging("INFO")
    configure_logging("DEBUG")
    logger = logging.getLogger(LOGGER_NAME)
    assert sum(getattr(h, "_api_json", False) for h in logger.handlers) == 1
    assert logger.level == logging.DEBUG
    assert logger.propagate is False
    configure_logging("INFO")


def test_metrics_are_thread_safe():
    m = MetricsCollector()

    def work():
        for _ in range(1_000):
            m.record_request("POST /predict", 200, 1.0)
            m.record_risk_levels(["LOW"])

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = m.snapshot()
    assert snap["requests"]["total"] == 8_000
    assert snap["risk_levels"]["LOW"] == 8_000
    assert snap["latency_ms"]["count"] == 8_000


def test_metrics_percentiles_are_correct():
    m = MetricsCollector()
    for ms in np.arange(1, 101, dtype=float):  # 1..100 ms
        m.record_request("GET /x", 200, ms)
    lat = m.snapshot()["latency_ms"]
    assert (lat["p50"], lat["p95"], lat["p99"]) == pytest.approx((50.5, 95.05, 99.01))
