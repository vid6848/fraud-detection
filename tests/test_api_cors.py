"""CORS: the dashboard (a different origin) may call the API from the browser."""
import pytest
from fastapi.testclient import TestClient

from api.config import DEFAULT_CORS_ORIGINS, Settings
from api.main import create_app
from tests.api_support import make_settings

DASHBOARD = "http://localhost:5180"
OTHER = "http://evil.example"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(make_settings())) as c:
        yield c


def preflight(client, origin, method="GET", headers="authorization"):
    return client.options("/explain/00000000-0000-0000-0000-000000000000", headers={
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": headers,
    })


def test_preflight_from_dashboard_is_allowed(client):
    r = preflight(client, DASHBOARD)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == DASHBOARD
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_preflight_from_other_origin_is_rejected(client):
    r = preflight(client, OTHER)
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_preflight_rejects_unlisted_method(client):
    assert preflight(client, DASHBOARD, method="DELETE").status_code == 400


def test_simple_request_gets_cors_headers(client):
    r = client.get("/health", headers={"Origin": DASHBOARD})
    assert r.headers["access-control-allow-origin"] == DASHBOARD
    assert "x-request-id" in r.headers["access-control-expose-headers"].lower()
    assert "access-control-allow-origin" not in client.get(
        "/health", headers={"Origin": OTHER}).headers


def test_error_responses_carry_cors_headers(client):
    r = client.get("/explain/not-a-uuid", headers={"Origin": DASHBOARD})
    assert r.status_code >= 400
    assert r.headers["access-control-allow-origin"] == DASHBOARD


def test_preflight_not_counted_in_metrics():
    with TestClient(create_app(make_settings())) as c:
        preflight(c, DASHBOARD)
        assert c.get("/metrics").json()["requests"]["total"] == 0


def test_origins_come_from_settings():
    s = make_settings(cors_origins=(OTHER,))
    with TestClient(create_app(s)) as c:
        assert preflight(c, OTHER).headers["access-control-allow-origin"] == OTHER
        assert preflight(c, DASHBOARD).status_code == 400


def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setattr("api.config.load_dotenv", lambda *a, **k: None)  # ignore local .env
    assert Settings.from_env().cors_origins == DEFAULT_CORS_ORIGINS == (DASHBOARD,)


@pytest.mark.parametrize("value, expected", [
    ("https://a.example, https://b.example/ ,", ("https://a.example", "https://b.example")),
    ("", ()),
])
def test_cors_origins_from_env(monkeypatch, value, expected):
    monkeypatch.setenv("CORS_ORIGINS", value)
    assert Settings.from_env().cors_origins == expected
