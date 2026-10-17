"""Phase 4 step 3: the API against the real Supabase project.

Skipped unless real credentials are in `.env`. Rows it creates are deleted
afterwards (deleting a transaction cascades to its alert).
"""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from tests.api_support import make_settings
from tests.supabase_support import analyst_client, client, require_env
from tests.test_api_predict import FRAUD_ROW

pytestmark = pytest.mark.integration


@pytest.fixture
def service():
    return client("SUPABASE_SERVICE_ROLE_KEY")


@pytest.fixture
def api():
    creds = require_env("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY")
    settings = make_settings(supabase_url=creds["SUPABASE_URL"],
                             supabase_service_role_key=creds["SUPABASE_SERVICE_ROLE_KEY"],
                             supabase_anon_key=creds["SUPABASE_ANON_KEY"])
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def stored_fraud(api, service):
    """POST a known fraud row; TestClient returns after the background save has run."""
    body = api.post("/predict", json=FRAUD_ROW).json()
    yield body
    service.table("transactions").delete().eq("id", body["transaction_id"]).execute()


def test_predict_stores_transaction_and_alert(api, service, stored_fraud):
    assert api.get("/metrics").json()["storage"]["writes_ok"] == 1
    tx = service.table("transactions").select("*").eq("id", stored_fraud["transaction_id"]).execute()
    [row] = tx.data
    assert row["risk_level"] == "HIGH"
    assert row["probability"] == pytest.approx(stored_fraud["probability"])
    assert row["features"]["V14"] == FRAUD_ROW["V14"]
    alerts = (service.table("alerts").select("severity,status")
              .eq("transaction_id", stored_fraud["transaction_id"]).execute())
    assert alerts.data == [{"severity": "HIGH", "status": "open"}]


def test_explain_stored_transaction_as_analyst(api, stored_fraud):
    analyst = analyst_client()
    token = analyst.auth.get_session().access_token
    r = api.get(f"/explain/{stored_fraud['transaction_id']}",
                headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["probability"] == pytest.approx(stored_fraud["probability"])
    assert len(body["top_features"]) == 5


def test_explain_stored_rejects_a_bad_token(api, stored_fraud):
    r = api.get(f"/explain/{stored_fraud['transaction_id']}",
                headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401
