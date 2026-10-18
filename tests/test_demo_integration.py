"""Phase 7 step 2: POST /demo/stream against the real Supabase project.

Skipped unless real credentials are in `.env`. Streams 3 rows and deletes them
afterwards (their alerts go with them).
"""
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from tests.api_support import make_settings
from tests.supabase_support import analyst_client, client, require_env

pytestmark = pytest.mark.integration


@pytest.fixture
def api():
    creds = require_env("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY")
    settings = make_settings(supabase_url=creds["SUPABASE_URL"],
                             supabase_service_role_key=creds["SUPABASE_SERVICE_ROLE_KEY"],
                             supabase_anon_key=creds["SUPABASE_ANON_KEY"],
                             demo_max_rows=3, demo_rate_per_s=20.0)
    with TestClient(create_app(settings)) as c:
        yield c


def test_demo_stream_as_analyst_saves_rows(api):
    service = client("SUPABASE_SERVICE_ROLE_KEY")
    token = analyst_client().auth.get_session().access_token
    started = datetime.now(UTC).isoformat()
    try:
        response = api.post("/demo/stream", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 202, response.text
        deadline = time.monotonic() + 30
        while api.get("/demo/stream").json()["running"] and time.monotonic() < deadline:
            time.sleep(0.05)
        run = api.get("/demo/stream").json()["run"]
        assert (run["state"], run["sent"], run["failed"]) == ("completed", 3, 0)
        rows = (service.table("transactions").select("time_seconds")
                .gte("created_at", started).execute().data)
        expected = {r["Time"] for r in api.app.state.demo.rows[:3]}
        assert expected <= {r["time_seconds"] for r in rows}
    finally:
        demo_times = [r["Time"] for r in api.app.state.demo.rows[:3]]
        (service.table("transactions").delete().gte("created_at", started)
         .in_("time_seconds", demo_times).execute())


def test_demo_stream_rejects_a_fake_token(api):
    response = api.post("/demo/stream", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
    anon = require_env("SUPABASE_ANON_KEY")["SUPABASE_ANON_KEY"]
    response = api.post("/demo/stream", headers={"Authorization": f"Bearer {anon}"})
    assert response.status_code == 401  # the anon key is not a user


def test_drift_with_the_analysts_login(api):
    token = analyst_client().auth.get_session().access_token
    response = api.get("/drift", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    service = client("SUPABASE_SERVICE_ROLE_KEY")
    stored = (service.table("transactions").select("id", count="exact", head=True)
              .eq("model_version", body["model_version"]).execute().count)
    assert body["live_rows"] == min(stored, body["window"])
    assert len(body["bins"]) == 6
