"""Phase 7 step 4: GET /drift (live scores from storage vs the training distribution)."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.drift import DriftUnavailable, drift_report, load_reference
from api.main import create_app
from api.storage import InvalidToken, StorageUnavailable, SupabaseStore
from ml.config import ARTIFACTS_DIR, ROOT
from tests.api_support import make_settings
from tests.test_api_storage import AUTH, STORAGE_SETTINGS, TOKEN, FakeStore

REFERENCE = json.loads((ARTIFACTS_DIR / "score_distribution.json").read_text())
VERSION = REFERENCE["model_version"]


def rows_like(shares: list[float], n: int) -> list[dict]:
    """n live rows whose scores fill the reference bins in the given shares (newest first)."""
    edges = REFERENCE["edges"]
    rows = []
    for (lo, hi), share in zip(zip(edges, edges[1:]), shares):
        rows += [{"probability": (lo + hi) / 2} for _ in range(round(share * n))]
    return [{**r, "created_at": f"2026-10-18T10:{59 - i // 60:02d}:{59 - i % 60:02d}+00:00"}
            for i, r in enumerate(rows)]


class DriftStore(FakeStore):
    def __init__(self, rows=None, error: Exception | None = None):
        super().__init__()
        self.scores = rows or []
        self.error = error
        self.calls: list[tuple] = []

    def recent_scores(self, user_token, model_version, limit):
        self.calls.append((user_token, model_version, limit))
        if self.error:
            raise self.error
        return self.scores[:limit]


def drift_client(store, **overrides) -> TestClient:
    return TestClient(create_app(make_settings(**{**STORAGE_SETTINGS, **overrides}), storage=store))


def get_drift(store, headers=AUTH, **overrides):
    with drift_client(store, **overrides) as client:
        return client.get("/drift", headers=headers)


# --- report ------------------------------------------------------------------------------

def test_live_scores_like_training_are_ok():
    store = DriftStore(rows_like(REFERENCE["proportions"], 1000))
    body = get_drift(store).json()
    assert body["status"] == "OK"
    assert body["psi"] < 0.01
    assert body["live_rows"] == 1000 and body["window"] == 1000 and body["min_rows"] == 500
    assert store.calls == [(TOKEN, VERSION, 1000)]  # caller's token: RLS applies
    assert [b["reference"] for b in body["bins"]] == pytest.approx(REFERENCE["proportions"])
    assert sum(b["live"] for b in body["bins"]) == pytest.approx(1, abs=0.01)
    assert body["reference"]["rows"] == 199_364 and body["model_version"] == VERSION
    assert body["thresholds"] == {"watch": 0.1, "alert": 0.25}


def test_a_shift_towards_higher_scores_is_an_alert():
    body = get_drift(DriftStore(rows_like([0.6, 0.2, 0.1, 0.05, 0.03, 0.02], 1000))).json()
    assert body["status"] == "Alert" and body["psi"] >= 0.25
    contributions = [b["contribution"] for b in body["bins"]]
    assert sum(contributions) == pytest.approx(body["psi"], abs=1e-5)
    assert max(contributions) > 0.1


def test_a_moderate_shift_is_watch():
    body = get_drift(DriftStore(rows_like([0.82, 0.12, 0.04, 0.012, 0.004, 0.004], 1000))).json()
    assert body["status"] == "Watch", body["psi"]


def test_too_few_live_scores_is_not_enough_data_but_still_reports_psi():
    body = get_drift(DriftStore(rows_like(REFERENCE["proportions"], 300))).json()
    assert body["status"] == "Not enough data"
    assert body["live_rows"] == 300 and body["psi"] is not None


def test_no_live_scores():
    body = get_drift(DriftStore([])).json()
    assert body["status"] == "Not enough data"
    assert body["psi"] is None and body["live_from"] is None and body["live_to"] is None
    assert all(b["live"] == 0 and b["contribution"] == 0 for b in body["bins"])


def test_live_time_range_spans_the_window():
    rows = rows_like(REFERENCE["proportions"], 600)
    body = get_drift(DriftStore(rows)).json()
    assert body["live_to"].startswith("2026-10-18T10:59:59")  # newest
    assert body["live_from"].startswith(rows[-1]["created_at"][:19])  # oldest in the window


def test_window_and_min_rows_come_from_settings():
    store = DriftStore(rows_like(REFERENCE["proportions"], 1000))
    body = get_drift(store, drift_window=250, drift_min_rows=100).json()
    assert store.calls[0][2] == 250
    assert (body["live_rows"], body["window"], body["min_rows"]) == (250, 250, 100)
    assert body["status"] != "Not enough data"


# --- errors ------------------------------------------------------------------------------

def test_drift_needs_a_login():
    store = DriftStore()
    response = get_drift(store, headers={})
    assert response.status_code == 401 and store.calls == []


def test_drift_rejects_an_invalid_token():
    response = get_drift(DriftStore(error=InvalidToken("expired")))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_drift_is_503_when_storage_fails():
    response = get_drift(DriftStore(error=StorageUnavailable("ReadTimeout")))
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Transaction storage is unavailable"


def test_drift_is_503_without_storage():
    with TestClient(create_app(make_settings())) as client:
        assert client.get("/drift", headers=AUTH).status_code == 503


def test_drift_is_503_without_a_reference(tmp_path):
    response = get_drift(DriftStore(), score_distribution_path=tmp_path / "missing.json")
    assert response.status_code == 503
    assert "make_score_distribution" in response.json()["error"]["message"]


def test_load_reference_checks_version_and_shape(tmp_path):
    path = tmp_path / "ref.json"
    with pytest.raises(DriftUnavailable, match="not found"):
        load_reference(path, VERSION)
    path.write_text(json.dumps({**REFERENCE, "model_version": "0.0.1"}))
    with pytest.raises(DriftUnavailable, match="is for model 0.0.1"):
        load_reference(path, VERSION)
    path.write_text(json.dumps({**REFERENCE, "edges": REFERENCE["edges"][:-1]}))
    with pytest.raises(DriftUnavailable, match="malformed"):
        load_reference(path, VERSION)
    path.write_text(json.dumps(REFERENCE))
    assert load_reference(path, VERSION) == REFERENCE


def test_a_reference_for_another_model_disables_drift(tmp_path):
    path = tmp_path / "ref.json"
    path.write_text(json.dumps({**REFERENCE, "model_version": "0.0.1"}))
    assert get_drift(DriftStore(), score_distribution_path=path).status_code == 503


def test_drift_report_rounds_psi():
    report = drift_report(REFERENCE, rows_like([0.9, 0.05, 0.03, 0.01, 0.005, 0.005], 1000),
                          window=1000, min_rows=500, model_version=VERSION)
    assert report["psi"] == round(report["psi"], 6)


# --- SupabaseStore.recent_scores (real PostgREST client, fake server) ----------------------

def test_recent_scores_queries_newest_rows_of_this_model_with_the_callers_token():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[{"probability": 0.1, "created_at": "2026-10-18T10:00:00+00:00"}])

    store = SupabaseStore("https://example.supabase.co", "service-key", "anon-key", 5.0,
                          transport=httpx.MockTransport(handler))
    assert store.recent_scores(TOKEN, "1.0.0", 1000) == [
        {"probability": 0.1, "created_at": "2026-10-18T10:00:00+00:00"}]
    [request] = seen
    params = dict(request.url.params)
    assert params == {"select": "probability,created_at", "model_version": "eq.1.0.0",
                      "order": "created_at.desc", "limit": "1000"}
    assert request.headers["apikey"] == "anon-key"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("response, error", [
    (httpx.Response(401, json={"code": "PGRST301", "message": "JWT expired", "details": None,
                               "hint": None}), InvalidToken),
    (httpx.Response(500, json={"code": "XX000", "message": "boom", "details": None, "hint": None}), StorageUnavailable),
])
def test_recent_scores_maps_errors(response, error):
    store = SupabaseStore("https://example.supabase.co", "service-key", "anon-key", 5.0,
                          transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(error):
        store.recent_scores(TOKEN, "1.0.0", 10)


# --- settings --------------------------------------------------------------------------------

def test_drift_settings_from_env(monkeypatch):
    monkeypatch.setenv("SCORE_DISTRIBUTION_PATH", "custom/ref.json")
    monkeypatch.setenv("DRIFT_WINDOW", "2000")
    monkeypatch.setenv("DRIFT_MIN_ROWS", "800")
    settings = Settings.from_env()
    assert settings.score_distribution_path == ROOT / "custom" / "ref.json"
    assert (settings.drift_window, settings.drift_min_rows) == (2000, 800)
