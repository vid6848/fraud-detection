"""Phase 4 step 2: Row Level Security, checked over HTTP against the real project.

Skipped unless real credentials are in `.env`. The full rule-by-rule check lives in
supabase/tests/rls_checks.sql; this file proves the same rules hold through the
public API that the dashboard will use (anon key + analyst login).
"""
import uuid

import pytest
from postgrest.exceptions import APIError

from tests.supabase_support import analyst_client, client

pytestmark = pytest.mark.integration

TABLES = ["transactions", "alerts", "feedback", "model_runs"]


def _transaction_row(risk_level: str = "HIGH") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "time_seconds": 3600.0,
        "amount": 12.5,
        "hour_of_day": 1,
        "features": {"V1": 0.0},
        "probability": 0.9,
        "risk_level": risk_level,
        "reasons": [],
        "model_version": "rls-integration-test",
    }


@pytest.fixture
def service():
    return client("SUPABASE_SERVICE_ROLE_KEY")


@pytest.fixture
def high_transaction(service):
    """A HIGH transaction (and, via the trigger, its alert), deleted afterwards."""
    row = _transaction_row()
    service.table("transactions").insert(row).execute()
    yield row
    service.table("transactions").delete().eq("id", row["id"]).execute()  # cascades to alerts


@pytest.mark.parametrize("table", TABLES)
def test_anon_cannot_read(table):
    anon = client("SUPABASE_ANON_KEY")
    with pytest.raises(APIError):
        anon.table(table).select("*").limit(1).execute()


def test_anon_cannot_insert_transactions():
    anon = client("SUPABASE_ANON_KEY")
    with pytest.raises(APIError):
        anon.table("transactions").insert(_transaction_row()).execute()


def test_service_role_insert_creates_alert(service, high_transaction):
    alerts = service.table("alerts").select("*").eq("transaction_id", high_transaction["id"]).execute()
    assert [(a["severity"], a["status"]) for a in alerts.data] == [("HIGH", "open")]


def test_analyst_can_read_transactions_and_alerts(high_transaction):
    analyst = analyst_client()
    tx = analyst.table("transactions").select("id").eq("id", high_transaction["id"]).execute()
    assert len(tx.data) == 1
    alerts = analyst.table("alerts").select("id").eq("transaction_id", high_transaction["id"]).execute()
    assert len(alerts.data) == 1


def test_analyst_cannot_insert_transactions():
    analyst = analyst_client()
    with pytest.raises(APIError):
        analyst.table("transactions").insert(_transaction_row()).execute()


def test_analyst_reviews_alert_and_leaves_feedback(high_transaction):
    analyst = analyst_client()
    user_id = analyst.auth.get_user().user.id
    alert = analyst.table("alerts").select("id").eq("transaction_id", high_transaction["id"]).single().execute()

    updated = (analyst.table("alerts").update({"status": "confirmed_fraud"})
               .eq("id", alert.data["id"]).execute())
    assert updated.data[0]["status"] == "confirmed_fraud"
    assert updated.data[0]["reviewed_by"] == user_id  # stamped by the trigger

    with pytest.raises(APIError):  # only `status` is writable
        analyst.table("alerts").update({"severity": "MEDIUM"}).eq("id", alert.data["id"]).execute()

    feedback = (analyst.table("feedback")
                .insert({"alert_id": alert.data["id"], "label": "confirmed_fraud", "note": "test"})
                .execute())
    assert feedback.data[0]["analyst"] == user_id
