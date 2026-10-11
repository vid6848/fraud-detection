"""Phase 3 step 3: POST /predict/batch and POST /explain."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.explanations import TOP_K, describe, typical
from api.main import create_app
from api.schemas import EXAMPLE_TRANSACTION
from ml.config import RAW_COLUMNS
from tests.api_support import make_settings
from tests.test_api_predict import FRAUD_ROW, MEDIUM_ROW, NIGHT_TIME

TINY_NIGHT = {**EXAMPLE_TRANSACTION, "Time": NIGHT_TIME, "Amount": 0.0}


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings())) as c:
        yield c


@pytest.fixture(scope="module")
def small_client():
    with TestClient(create_app(make_settings(max_batch_size=3))) as c:
        yield c


def _rows(n: int, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        row = {c: float(rng.normal()) for c in RAW_COLUMNS}
        row["Time"] = float(rng.uniform(0, 172_800))
        row["Amount"] = float(rng.exponential(80))
        rows.append(row)
    return rows


# --- POST /predict/batch ---

def test_batch_matches_single_predicts_in_order(client):
    rows = [FRAUD_ROW, EXAMPLE_TRANSACTION, MEDIUM_ROW, TINY_NIGHT]
    r = client.post("/predict/batch", json={"transactions": rows})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert body["latency_ms"] > 0
    assert [x["risk_level"] for x in body["results"]] == ["HIGH", "LOW", "MEDIUM", "MEDIUM"]
    for row, result in zip(rows, body["results"]):
        single = client.post("/predict", json=row).json()
        assert result["probability"] == pytest.approx(single["probability"])
        assert result["reasons"] == single["reasons"]


def test_batch_scores_all_rows_in_one_model_call(client, monkeypatch):
    model = client.app.state.store.model
    calls = []
    original = model.predict_proba

    def spy(X):
        calls.append(len(X))
        return original(X)

    monkeypatch.setattr(model, "predict_proba", spy)
    r = client.post("/predict/batch", json={"transactions": _rows(250)})
    assert r.status_code == 200
    assert calls == [250]


def test_batch_accepts_max_size(client):
    r = client.post("/predict/batch", json={"transactions": _rows(1000)})
    assert r.status_code == 200
    assert r.json()["count"] == 1000


def test_batch_rejects_over_max_size(client):
    assert client.post("/predict/batch", json={"transactions": _rows(1001)}).status_code == 422


def test_batch_limit_comes_from_settings(small_client):
    assert small_client.post("/predict/batch", json={"transactions": _rows(3)}).status_code == 200
    assert small_client.post("/predict/batch", json={"transactions": _rows(4)}).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"transactions": []},
        {},
        {"transactions": EXAMPLE_TRANSACTION},
        [EXAMPLE_TRANSACTION],
    ],
    ids=["empty", "missing-key", "not-a-list", "bare-list"],
)
def test_batch_rejects_bad_shape(client, payload):
    assert client.post("/predict/batch", json=payload).status_code == 422


def test_batch_reports_which_row_is_bad(client):
    rows = [EXAMPLE_TRANSACTION, {**EXAMPLE_TRANSACTION, "Amount": -1}]
    r = client.post("/predict/batch", json={"transactions": rows})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["loc"] == ["body", "transactions", 1, "Amount"]


# --- POST /explain ---

def test_explain_fraud_row(client):
    r = client.post("/explain", json=FRAUD_ROW)
    assert r.status_code == 200
    body = r.json()
    top = body["top_features"]
    assert len(top) == TOP_K
    sizes = [abs(t["shap_value"]) for t in top]
    assert sizes == sorted(sizes, reverse=True)
    for t in top:
        assert t["direction"] == ("raises_risk" if t["shap_value"] > 0 else "lowers_risk")
        assert t["feature"] in t["description"] or t["feature"] in ("Amount", "time_of_day")
    # the strongest push is towards fraud, from a feature EDA flagged (finding 7)
    assert top[0]["direction"] == "raises_risk"
    assert top[0]["feature"] in {"V14", "V17", "V12", "V10", "V4", "V11"}
    assert body["risk_level"] == "HIGH"
    assert body["latency_ms"] > 0


def test_explain_matches_predict_and_base_model(client):
    explained = client.post("/explain", json=FRAUD_ROW).json()
    predicted = client.post("/predict", json=FRAUD_ROW).json()
    assert explained["probability"] == pytest.approx(predicted["probability"])
    assert explained["reasons"] == predicted["reasons"]
    base = client.app.state.store.model.base
    score = base.predict_proba(pd.DataFrame([FRAUD_ROW])[RAW_COLUMNS])[0, 1]
    assert explained["model_score"] == pytest.approx(score, abs=1e-6)  # SHAP adds up
    assert 0 < explained["base_value"] < 1


def test_explain_groups_amount_and_time(client, monkeypatch):
    # With TOP_K covering every input, Amount and time_of_day show up once each.
    monkeypatch.setattr("api.explanations.TOP_K", 100)
    top = client.post("/explain", json=TINY_NIGHT).json()["top_features"]
    features = [t["feature"] for t in top]
    assert len(features) == 30 == len(set(features))
    assert "log_amount" not in features and "hour_sin" not in features
    by_name = {t["feature"]: t for t in top}
    assert by_name["Amount"]["value"] == 0.0
    assert by_name["time_of_day"]["value"] == pytest.approx(3.0)
    assert "03:00" in by_name["time_of_day"]["description"]


def test_explain_rejects_bad_input(client):
    assert client.post("/explain", json={"Time": 1.0}).status_code == 422


@pytest.mark.parametrize(
    "z, words",
    [(0.3, "close to typical"), (-0.99, "close to typical"), (1.5, "higher than typical"),
     (-1.5, "lower than typical"), (2.0, "much higher than typical"),
     (-4.0, "much lower than typical")],
)
def test_typical_wording(z, words):
    assert typical(z) == words


def test_describe_wording():
    assert describe("V14", -4.7997, 0.13, -5.0) == (
        "V14 = -4.80 (much lower than typical) pushed fraud risk up"
    )
    assert describe("Amount", 1335.0, -0.01, 2.5) == (
        "Amount $1,335.00 (much higher than typical) pushed fraud risk down"
    )
    assert describe("time_of_day", 13.5, 0.02, None) == "Time of day 13:30 pushed fraud risk up"
    assert describe("time_of_day", 23.9999, 0.02, None) == "Time of day 00:00 pushed fraud risk up"
