"""Phase 3 step 2: risk levels, rules layer, POST /predict.

FRAUD_ROW and MEDIUM_ROW are real validation-split rows (rounded to 6 decimals).
"""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.model_store import ModelStore
from api.risk import (
    TINY_AMOUNT_MAX,
    RiskLevel,
    assess,
    model_risk_level,
    rule_flags,
)
from api.schemas import EXAMPLE_TRANSACTION
from ml.config import ARTIFACTS_DIR, RAW_COLUMNS
from tests.api_support import make_settings

METADATA = json.loads((ARTIFACTS_DIR / "metadata.json").read_text())
HIGH = METADATA["threshold"]
MEDIUM = 0.05

FRAUD_ROW = {  # Class = 1, scores ~0.926
    "Time": 133184.0, "V1": -1.212682, "V2": -2.484824, "V3": -6.397186, "V4": 3.670562,
    "V5": -0.863375, "V6": -1.855855, "V7": 1.017732, "V8": -0.544704, "V9": -1.703378,
    "V10": -3.739659, "V11": 1.738124, "V12": -2.844449, "V13": 0.765864, "V14": -4.799737,
    "V15": -0.011335, "V16": -2.693168, "V17": -3.166955, "V18": -1.0678, "V19": -0.559132,
    "V20": 2.908374, "V21": 1.396872, "V22": 0.092073, "V23": -1.492882, "V24": -0.204227,
    "V25": 0.532511, "V26": -0.293871, "V27": 0.212663, "V28": 0.431095, "Amount": 1335.0,
}
MEDIUM_ROW = {  # scores ~0.070
    "Time": 133481.0, "V1": 1.721867, "V2": 0.667619, "V3": -0.634118, "V4": 4.314196,
    "V5": 0.0263, "V6": -0.103233, "V7": -0.525856, "V8": 0.210457, "V9": -0.226011,
    "V10": 0.073084, "V11": -0.40852, "V12": -1.081614, "V13": -0.633887, "V14": -3.316105,
    "V15": 0.239775, "V16": 2.493199, "V17": 1.44384, "V18": 1.414616, "V19": -2.349375,
    "V20": -0.129211, "V21": -0.118479, "V22": -0.393832, "V23": 0.269933, "V24": -0.359724,
    "V25": -0.583916, "V26": -0.191888, "V27": 0.058059, "V28": 0.054803, "Amount": 53.06,
}
NIGHT_TIME = 3 * 3600.0  # 03:00 on day 1


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings())) as c:
        yield c


def codes(body) -> list[str]:
    return [r["code"] for r in body["reasons"]]


# --- model risk levels ---

@pytest.mark.parametrize(
    "p, expected",
    [
        (0.0, RiskLevel.LOW),
        (MEDIUM - 1e-9, RiskLevel.LOW),
        (MEDIUM, RiskLevel.MEDIUM),
        (HIGH - 1e-9, RiskLevel.MEDIUM),
        (HIGH, RiskLevel.HIGH),
        (1.0, RiskLevel.HIGH),
    ],
)
def test_model_risk_level_boundaries(p, expected):
    assert model_risk_level(p, MEDIUM, HIGH) is expected


# --- rules ---

def _raw(time, amount) -> pd.DataFrame:
    return pd.DataFrame([{**EXAMPLE_TRANSACTION, "Time": time, "Amount": amount}])


@pytest.mark.parametrize(
    "amount, tiny",
    [(0.0, True), (0.99, True), (TINY_AMOUNT_MAX, False), (250.0, False)],
)
def test_tiny_amount_rule(amount, tiny):
    assert bool(rule_flags(_raw(14 * 3600, amount))["TINY_AMOUNT"].iloc[0]) is tiny


@pytest.mark.parametrize(
    "time, night",
    [
        (0.0, False),
        (3600 - 1, False),       # 00:59:59
        (3600, True),            # 01:00
        (7 * 3600 - 1, True),    # 06:59:59
        (7 * 3600, False),       # 07:00
        (86_400 + 2 * 3600, True),  # 02:00 on day 2
        (14 * 3600, False),
    ],
)
def test_night_hours_rule(time, night):
    assert bool(rule_flags(_raw(time, 50.0))["NIGHT_HOURS"].iloc[0]) is night


def test_both_rules_raise_low_to_medium():
    level, reasons = assess(0.0001, {"TINY_AMOUNT": True, "NIGHT_HOURS": True}, MEDIUM, HIGH)
    assert level is RiskLevel.MEDIUM
    assert [r.code for r in reasons] == ["TINY_AMOUNT", "NIGHT_HOURS", "RULES_ESCALATED"]


@pytest.mark.parametrize("rule", ["TINY_AMOUNT", "NIGHT_HOURS"])
def test_one_rule_alone_only_adds_a_reason(rule):
    flags = {"TINY_AMOUNT": False, "NIGHT_HOURS": False, rule: True}
    level, reasons = assess(0.0001, flags, MEDIUM, HIGH)
    assert level is RiskLevel.LOW
    assert [r.code for r in reasons] == [rule]


def test_rules_never_create_high():
    level, _ = assess(HIGH - 1e-6, {"TINY_AMOUNT": True, "NIGHT_HOURS": True}, MEDIUM, HIGH)
    assert level is RiskLevel.MEDIUM


def test_rules_do_not_change_model_high():
    level, reasons = assess(0.95, {"TINY_AMOUNT": True, "NIGHT_HOURS": True}, MEDIUM, HIGH)
    assert level is RiskLevel.HIGH
    assert [r.code for r in reasons] == ["MODEL_HIGH_RISK", "TINY_AMOUNT", "NIGHT_HOURS"]


def test_no_reasons_for_plain_low():
    assert assess(0.0001, {"TINY_AMOUNT": False, "NIGHT_HOURS": False}, MEDIUM, HIGH) == (
        RiskLevel.LOW, []
    )


# --- POST /predict ---

def test_predict_normal_transaction(client):
    r = client.post("/predict", json=EXAMPLE_TRANSACTION)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"probability", "risk_level", "reasons", "transaction_id",
                         "model_version", "latency_ms"}
    assert body["transaction_id"] is None  # storage is off in these tests
    assert body["risk_level"] == "LOW"
    assert 0 <= body["probability"] < MEDIUM
    assert body["reasons"] == []
    assert body["model_version"] == METADATA["model_version"]
    assert body["latency_ms"] > 0


def test_predict_fraud_is_high(client):
    body = client.post("/predict", json=FRAUD_ROW).json()
    assert body["risk_level"] == "HIGH"
    assert body["probability"] >= HIGH
    assert codes(body) == ["MODEL_HIGH_RISK"]


def test_predict_medium_band(client):
    body = client.post("/predict", json=MEDIUM_ROW).json()
    assert body["risk_level"] == "MEDIUM"
    assert MEDIUM <= body["probability"] < HIGH
    assert codes(body) == ["MODEL_MEDIUM_RISK"]


def test_predict_tiny_charge_at_night_is_escalated(client):
    body = client.post("/predict", json={**EXAMPLE_TRANSACTION, "Time": NIGHT_TIME,
                                         "Amount": 0.0}).json()
    assert body["probability"] < MEDIUM  # the model alone says LOW
    assert body["risk_level"] == "MEDIUM"
    assert codes(body) == ["TINY_AMOUNT", "NIGHT_HOURS", "RULES_ESCALATED"]
    assert all(r["message"] for r in body["reasons"])


def test_predict_matches_model_directly(client):
    store = ModelStore.load(make_settings())
    expected = store.model.predict_proba(pd.DataFrame([FRAUD_ROW, MEDIUM_ROW])[RAW_COLUMNS])[:, 1]
    got = [client.post("/predict", json=row).json()["probability"] for row in (FRAUD_ROW, MEDIUM_ROW)]
    assert got == pytest.approx(expected)


def test_predict_ignores_json_key_order(client):
    reordered = dict(reversed(list(FRAUD_ROW.items())))
    assert (client.post("/predict", json=reordered).json()["probability"]
            == client.post("/predict", json=FRAUD_ROW).json()["probability"])


@pytest.mark.parametrize(
    "payload",
    [
        {k: v for k, v in EXAMPLE_TRANSACTION.items() if k != "V14"},
        {**EXAMPLE_TRANSACTION, "Amount": -5},
        {**EXAMPLE_TRANSACTION, "V1": "abc"},
        {**EXAMPLE_TRANSACTION, "extra": 1},
        {},
    ],
    ids=["missing-field", "negative-amount", "string", "extra-field", "empty"],
)
def test_predict_rejects_bad_input(client, payload):
    assert client.post("/predict", json=payload).status_code == 422
