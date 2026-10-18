"""Phase 7 step 2: POST /demo/stream (server-side replay of held-out test rows).

DemoStreamer is tested with a fake clock and sleep (no waiting); the endpoints use
a FakeStore and a fast rate, so Supabase is never called and nothing sleeps long.
"""
import asyncio
import gzip
import time

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.config import DEFAULT_DEMO_ROWS_PATH, Settings
from api.demo import (
    MAX_CONSECUTIVE_FAILURES,
    DemoBusy,
    DemoRateLimited,
    DemoStreamer,
    load_demo_rows,
    retry_after_header,
)
from api.main import create_app
from api.storage import InvalidToken, StorageUnavailable, SupabaseStore
from ml.config import RAW_COLUMNS, ROOT
from tests.api_support import make_settings
from tests.test_api_storage import AUTH, STORAGE_SETTINGS, TOKEN, FakeStore

DEMO_ROWS = ROOT / DEFAULT_DEMO_ROWS_PATH
ROWS = [{c: float(i) for c in RAW_COLUMNS} for i in range(10)]


class FakeTime:
    """A clock that only moves when the streamer sleeps."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_streamer(fake: FakeTime, process=None, **overrides) -> DemoStreamer:
    options = {"rate_per_s": 10.0, "max_rows": 5, "cooldown_s": 60.0, "max_per_hour": 3,
               "clock": fake.clock, "sleep": fake.sleep}
    return DemoStreamer(ROWS, process or (lambda row: None), **{**options, **overrides})


def run(coro):
    return asyncio.run(coro)


async def finish(demo: DemoStreamer) -> None:
    await demo._task


# --- committed demo rows ---------------------------------------------------------

def test_committed_demo_rows_are_unlabelled_test_rows():
    rows = load_demo_rows(DEMO_ROWS)
    assert len(rows) == 200
    assert all(list(r) == RAW_COLUMNS for r in rows)  # no Class column, nothing extra
    header = gzip.open(DEMO_ROWS, "rt").readline().strip().split(",")
    assert header == RAW_COLUMNS
    times = [r["Time"] for r in rows]
    assert times == sorted(times)
    assert times[0] >= 145_000  # inside the test split (last ~2 hours of day 2)


def test_load_demo_rows_rejects_missing_columns(tmp_path):
    path = tmp_path / "rows.csv"
    pd.DataFrame([{"Time": 1.0, "Amount": 2.0}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing columns: V1"):
        load_demo_rows(path)


def test_streamer_needs_rows():
    with pytest.raises(ValueError):
        DemoStreamer([], lambda row: None, rate_per_s=1, max_rows=1, cooldown_s=0,
                     max_per_hour=1)


def test_retry_after_header_rounds_up_to_whole_seconds():
    assert retry_after_header(0.2) == "1"
    assert retry_after_header(12.01) == "13"


# --- DemoStreamer ------------------------------------------------------------------

def test_stream_sends_rows_in_order_at_the_configured_rate():
    fake, sent = FakeTime(), []
    demo = make_streamer(fake, process=sent.append)

    async def go():
        run_info = demo.start("analyst-1")
        assert demo.running and run_info.state == "running"
        await finish(demo)

    run(go())
    assert sent == ROWS[:5]
    assert fake.sleeps == pytest.approx([0.1] * 4)  # first row at once, then every 0.1 s
    status = demo.status()
    assert status["running"] is False
    assert status["run"]["state"] == "completed"
    assert (status["run"]["sent"], status["run"]["failed"], status["run"]["total"]) == (5, 0, 5)
    assert status["run"]["finished_at"] is not None


def test_slow_rows_do_not_slow_the_schedule():
    fake = FakeTime()
    demo = make_streamer(fake, process=lambda row: setattr(fake, "now", fake.now + 0.06))
    run(_start_and_finish(demo))
    assert fake.sleeps == pytest.approx([0.04] * 4)  # due-time based: 0.1 s minus the work


async def _start_and_finish(demo, user="analyst-1", limit=None):
    demo.start(user, limit)
    await finish(demo)


def test_limit_is_capped_by_max_rows_and_available_rows():
    fake = FakeTime()
    demo = make_streamer(fake, max_rows=50)  # only 10 rows exist
    assert demo.max_rows == 10
    run(_start_and_finish(demo, limit=3))
    assert demo.run.total == 3
    fake.now += 61
    run(_start_and_finish(demo, limit=500))
    assert demo.run.total == 10


def test_second_start_while_running_is_refused():
    demo = make_streamer(FakeTime())

    async def go():
        demo.start("analyst-1")
        with pytest.raises(DemoBusy):
            demo.start("analyst-2")
        await finish(demo)

    run(go())


def test_same_analyst_must_wait_for_the_cooldown():
    fake = FakeTime()
    demo = make_streamer(fake)
    run(_start_and_finish(demo))  # takes 0.4 s of fake time
    with pytest.raises(DemoRateLimited) as exc:
        demo.start("analyst-1")
    assert exc.value.retry_after_s == pytest.approx(59.6)
    run(_start_and_finish(demo, user="analyst-2"))  # someone else may start one
    fake.now += 60
    run(_start_and_finish(demo))


def test_hourly_cap_applies_to_all_analysts_together():
    fake = FakeTime()
    demo = make_streamer(fake, max_per_hour=2, cooldown_s=0)
    run(_start_and_finish(demo, user="a"))
    run(_start_and_finish(demo, user="b"))
    with pytest.raises(DemoRateLimited, match="hourly") as exc:
        demo.start("c")
    assert exc.value.retry_after_s == pytest.approx(3600 - 0.8)
    fake.now += 3600  # the window slides
    run(_start_and_finish(demo, user="c"))


def test_refused_starts_do_not_use_up_the_limits():
    fake = FakeTime()
    demo = make_streamer(fake, max_per_hour=1)

    async def go():
        demo.start("a")
        with pytest.raises(DemoBusy):
            demo.start("b")
        await finish(demo)

    run(go())
    assert "b" not in demo._last_start and len(demo._starts) == 1


def test_failed_rows_are_counted_and_the_stream_continues():
    calls = []

    def flaky(row):
        calls.append(row)
        if len(calls) == 2:
            raise ConnectionError("blip")

    demo = make_streamer(FakeTime(), process=flaky)
    run(_start_and_finish(demo))
    assert (demo.run.state, demo.run.sent, demo.run.failed) == ("completed", 4, 1)


def test_stream_stops_after_repeated_failures():
    def down(row):
        raise ConnectionError("supabase is down")

    demo = make_streamer(FakeTime(), process=down, max_rows=10)
    run(_start_and_finish(demo))
    assert demo.run.state == "failed"
    assert demo.run.failed == MAX_CONSECUTIVE_FAILURES and demo.run.sent == 0


def test_aclose_cancels_a_running_stream():
    async def go():
        demo = make_streamer(FakeTime(), sleep=lambda s: asyncio.sleep(3600))
        demo.start("a")
        await asyncio.sleep(0)  # let it send the first row and start waiting
        await demo.aclose()
        return demo

    demo = run(go())
    assert demo.run.state == "cancelled" and not demo.running
    run(demo.aclose())  # nothing running: no-op


def test_aclose_before_the_stream_starts_still_marks_it_cancelled():
    async def go():
        demo = make_streamer(FakeTime())
        demo.start("a")
        await demo.aclose()  # the task never got to run
        return demo

    demo = run(go())
    assert demo.run.state == "cancelled" and demo.run.finished_at is not None
    assert demo.run.sent == 0


def test_status_before_any_run():
    assert make_streamer(FakeTime()).status() == {"running": False, "max_rows": 5, "run": None}


# --- endpoints -----------------------------------------------------------------------

class AuthStore(FakeStore):
    """FakeStore that also answers verify_user."""

    def __init__(self, auth_error: Exception | None = None, **kwargs):
        super().__init__(**kwargs)
        self.auth_error = auth_error
        self.verified: list[str] = []

    def verify_user(self, user_token):
        self.verified.append(user_token)
        if self.auth_error:
            raise self.auth_error
        return f"user-{user_token}"


def demo_client(store, **overrides) -> TestClient:
    settings = {**STORAGE_SETTINGS, "demo_rate_per_s": 1000.0, "demo_max_rows": 5,
                **overrides}
    return TestClient(create_app(make_settings(**settings), storage=store))


def wait_until_done(client, timeout_s: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        status = client.get("/demo/stream").json()
        if not status["running"]:
            return status
        time.sleep(0.01)
    raise AssertionError("demo stream did not finish")


def test_demo_stream_scores_and_saves_rows():
    store = AuthStore()
    with demo_client(store) as client:
        response = client.post("/demo/stream", headers=AUTH)
        assert response.status_code == 202
        assert response.json()["run"]["total"] == 5
        status = wait_until_done(client)
        metrics = client.get("/metrics").json()
    assert status["run"]["state"] == "completed" and status["run"]["sent"] == 5
    assert store.verified == [TOKEN]
    rows = [row for batch in store.saved for row in batch]
    expected = load_demo_rows(DEMO_ROWS)[:5]
    assert [r["time_seconds"] for r in rows] == [e["Time"] for e in expected]
    assert all(r["model_version"] and r["risk_level"] in {"LOW", "MEDIUM", "HIGH"} for r in rows)
    assert sum(metrics["risk_levels"].values()) == 5
    assert metrics["storage"]["rows_written"] == 5


def test_demo_stream_counts_failed_saves():
    store = AuthStore(fail=True)
    with demo_client(store) as client:
        client.post("/demo/stream", headers=AUTH)
        status = wait_until_done(client)
        metrics = client.get("/metrics").json()
    assert status["run"]["state"] == "failed" and status["run"]["failed"] == 5
    assert metrics["storage"]["rows_failed"] == 5 and metrics["storage"]["rows_written"] == 0


def test_demo_stream_accepts_a_smaller_limit():
    store = AuthStore()
    with demo_client(store) as client:
        assert client.post("/demo/stream", headers=AUTH, json={"limit": 2}).status_code == 202
        assert wait_until_done(client)["run"]["sent"] == 2


@pytest.mark.parametrize("body", [{"limit": 0}, {"limit": -3}, {"rows": 5}])
def test_demo_stream_rejects_bad_bodies(body):
    with demo_client(AuthStore()) as client:
        response = client.post("/demo/stream", headers=AUTH, json=body)
    assert response.status_code == 422


def test_demo_stream_needs_a_login():
    store = AuthStore()
    with demo_client(store) as client:
        response = client.post("/demo/stream")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert store.verified == [] and store.saved == []


def test_demo_stream_rejects_an_invalid_token():
    store = AuthStore(auth_error=InvalidToken("bad"))
    with demo_client(store) as client:
        response = client.post("/demo/stream", headers=AUTH)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert store.saved == []


def test_demo_stream_is_503_when_auth_cannot_be_checked():
    with demo_client(AuthStore(auth_error=StorageUnavailable("ConnectTimeout"))) as client:
        response = client.post("/demo/stream", headers=AUTH)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Analyst login could not be checked"


def test_only_one_demo_stream_at_a_time():
    store = AuthStore()
    with demo_client(store, demo_rate_per_s=20.0, demo_max_rows=3) as client:
        assert client.post("/demo/stream", headers=AUTH).status_code == 202
        response = client.post("/demo/stream", headers={"Authorization": "Bearer other"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"
        wait_until_done(client)


def test_demo_stream_is_rate_limited_per_analyst():
    with demo_client(AuthStore()) as client:
        assert client.post("/demo/stream", headers=AUTH).status_code == 202
        wait_until_done(client)
        response = client.post("/demo/stream", headers=AUTH)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_shutdown_cancels_a_running_demo_stream():
    store = AuthStore()
    with demo_client(store, demo_rate_per_s=0.5) as client:  # one row, then a 2 s wait
        client.post("/demo/stream", headers=AUTH)
        demo = client.app.state.demo
    assert demo.run.state == "cancelled"


def test_demo_status_before_any_run():
    with demo_client(AuthStore()) as client:
        assert client.get("/demo/stream").json() == {"running": False, "max_rows": 5, "run": None}


def test_demo_stream_unavailable_without_storage():
    with TestClient(create_app(make_settings())) as client:
        assert client.get("/demo/stream").status_code == 503
        assert client.post("/demo/stream", headers=AUTH).status_code == 503


def test_demo_stream_unavailable_without_the_rows_file(tmp_path):
    with demo_client(AuthStore(), demo_rows_path=tmp_path / "missing.csv.gz") as client:
        response = client.get("/demo/stream")
    assert response.status_code == 503


def test_cors_preflight_allows_the_dashboard_to_start_a_stream():
    with demo_client(AuthStore()) as client:
        response = client.options("/demo/stream", headers={
            "Origin": "http://localhost:5180", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5180"


# --- SupabaseStore.verify_user (real client code, fake Supabase Auth) ------------------

def auth_store(handler) -> SupabaseStore:
    return SupabaseStore("https://example.supabase.co", "service-key", "anon-key", 5.0,
                         transport=httpx.MockTransport(handler))


def test_verify_user_returns_the_user_id_and_sends_the_right_headers():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"id": "user-123", "is_anonymous": False})

    assert auth_store(handler).verify_user(TOKEN) == "user-123"
    [request] = seen
    assert str(request.url) == "https://example.supabase.co/auth/v1/user"
    assert request.headers["apikey"] == "anon-key"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize("response", [
    httpx.Response(401, json={"msg": "invalid JWT"}),
    httpx.Response(403, json={"code": "bad_jwt"}),
    httpx.Response(200, json={"id": "anon-1", "is_anonymous": True}),
    httpx.Response(200, json={}),
])
def test_verify_user_rejects_bad_tokens(response):
    with pytest.raises(InvalidToken):
        auth_store(lambda request: response).verify_user(TOKEN)


def test_verify_user_reports_an_unavailable_auth_service():
    with pytest.raises(StorageUnavailable, match="HTTP 500"):
        auth_store(lambda request: httpx.Response(500)).verify_user(TOKEN)

    def offline(request):
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(StorageUnavailable, match="ConnectTimeout"):
        auth_store(offline).verify_user(TOKEN)


# --- settings ---------------------------------------------------------------------------

def test_demo_settings_from_env(monkeypatch):
    monkeypatch.setenv("DEMO_ROWS_PATH", "custom/rows.csv.gz")
    monkeypatch.setenv("DEMO_RATE_PER_S", "5")
    monkeypatch.setenv("DEMO_MAX_ROWS", "50")
    monkeypatch.setenv("DEMO_COOLDOWN_S", "30")
    monkeypatch.setenv("DEMO_MAX_PER_HOUR", "4")
    settings = Settings.from_env()
    assert settings.demo_rows_path == ROOT / "custom" / "rows.csv.gz"
    assert (settings.demo_rate_per_s, settings.demo_max_rows) == (5.0, 50)
    assert (settings.demo_cooldown_s, settings.demo_max_per_hour) == (30.0, 4)


def test_demo_settings_defaults():
    settings = make_settings()
    assert settings.demo_rows_path == DEMO_ROWS
    assert (settings.demo_rate_per_s, settings.demo_max_rows) == (10.0, 200)
