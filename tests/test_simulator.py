"""Phase 5: the stream simulator, against a fake API (no server, no dataset, no waiting).

The fake API is an httpx.MockTransport; time is a fake clock whose sleep() just
moves the clock forward, so pacing can be checked exactly and instantly.
"""
import asyncio
import json

import httpx
import pytest

from ml.config import RAW_COLUMNS, SPLIT_BOUNDARIES, TARGET
from simulator import __main__ as cli
from simulator.client import ApiUnavailable
from simulator.data import load_stream
from simulator.runner import Config, new_run_id, request_id, run
from simulator.schedule import send_offsets
from tests.synthetic import make_transactions

DF = make_transactions(6_000, fraud_rate=0.05)
HEALTHY = {"status": "ok", "model_loaded": True, "model_version": "1.0.0"}


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        # Let requests started "now" reach the fake API before time moves on
        # (in real time that gap is microseconds).
        for _ in range(10):
            await asyncio.sleep(0)
        self.now += seconds


class FakeApi:
    """Scores by a simple rule; records every request it receives."""

    def __init__(self, time: FakeTime | None = None, health: tuple[int, dict] = (200, HEALTHY)):
        self.time = time
        self.health = health
        self.requests: list[httpx.Request] = []
        self.sent_at: list[float] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(self.health[0], json=self.health[1])
        self.requests.append(request)
        if self.time is not None:
            self.sent_at.append(self.time.now)
        body = json.loads(request.content)
        probability = 0.9 if body["V14"] < -2 else 0.01
        level = "HIGH" if probability > 0.5 else "LOW"
        return httpx.Response(200, json={
            "probability": probability, "risk_level": level, "reasons": [],
            "transaction_id": None, "model_version": "1.0.0", "latency_ms": 1.5})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def bodies(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests]


def simulate(stream, config=Config(), api=None, time=None, run_id="test-run"):
    time = time or FakeTime()
    api = api or FakeApi(time)
    results = asyncio.run(run(stream, config, run_id, transport=api.transport,
                              sleep=time.sleep, clock=time.clock))
    return results, api


# --- data ----------------------------------------------------------------------

def test_stream_is_the_test_split_in_time_order():
    stream = load_stream(DF)
    test = DF[DF["Time"] >= SPLIT_BOUNDARIES[1]]
    assert len(stream) == len(test)
    assert stream.times == sorted(stream.times)
    assert min(stream.times) >= SPLIT_BOUNDARIES[1]
    assert sum(stream.labels) == int(test[TARGET].sum())


def test_payloads_never_contain_the_label():
    stream = load_stream(DF)
    assert all(list(p) == RAW_COLUMNS for p in stream.payloads)
    assert all(TARGET not in p for p in stream.payloads)


def test_offset_and_limit():
    full = load_stream(DF)
    part = load_stream(DF, offset=10, limit=5)
    assert part.payloads == full.payloads[10:15]
    assert part.labels == full.labels[10:15]


@pytest.mark.parametrize("kwargs", [{"offset": -1}, {"limit": 0}, {"offset": 10**6}])
def test_bad_offset_or_limit(kwargs):
    with pytest.raises(ValueError):
        load_stream(DF, **kwargs)


# --- schedule ------------------------------------------------------------------

def test_fixed_schedule():
    assert send_offsets([5.0, 9.0, 9.0, 30.0], "fixed", rate=4, speed=1) == [0, 0.25, 0.5, 0.75]


def test_replay_schedule_uses_real_gaps_sped_up():
    assert send_offsets([100.0, 102.0, 102.0, 120.0], "replay", rate=1, speed=10) == \
        [0.0, 0.2, 0.2, 2.0]


@pytest.mark.parametrize("mode, rate, speed", [("fixed", 0, 1), ("replay", 1, 0), ("other", 1, 1)])
def test_bad_schedule_settings(mode, rate, speed):
    with pytest.raises(ValueError):
        send_offsets([1.0], mode, rate, speed)


# --- runner ----------------------------------------------------------------------

def test_sends_every_row_in_order_with_request_ids():
    stream = load_stream(DF, limit=30)
    results, api = simulate(stream, run_id="r1")
    assert api.bodies() == stream.payloads
    assert [r.headers["X-Request-ID"] for r in api.requests] == [f"sim-r1-{i}" for i in range(30)]
    assert [r.index for r in results] == list(range(30))
    assert all(r.ok and r.status == 200 for r in results)


def test_label_never_reaches_the_api():
    results, api = simulate(load_stream(DF, limit=50))
    assert all(TARGET not in body for body in api.bodies())


def test_fixed_rate_pacing():
    time = FakeTime()
    _, api = simulate(load_stream(DF, limit=11), Config(rate=5), time=time)
    assert api.sent_at == pytest.approx([i / 5 for i in range(11)])


def test_replay_pacing():
    time = FakeTime()
    stream = load_stream(DF, limit=20)
    _, api = simulate(stream, Config(mode="replay", speed=100), time=time)
    expected = [(t - stream.times[0]) / 100 for t in stream.times]
    assert api.sent_at == pytest.approx(expected)


def test_results_carry_scores():
    results, _ = simulate(load_stream(DF, limit=200))
    assert {r.risk_level for r in results} <= {"LOW", "HIGH"}
    assert all(r.server_latency_ms == 1.5 and r.latency_ms >= 0 for r in results)


def test_concurrency_cap_is_respected():
    in_flight, peak = 0, 0

    async def slow(request):
        nonlocal in_flight, peak
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return httpx.Response(200, json={"probability": 0.0, "risk_level": "LOW", "reasons": []})

    stream = load_stream(DF, limit=40)
    results = asyncio.run(run(stream, Config(rate=10_000, concurrency=3), "r",
                              transport=httpx.MockTransport(slow)))
    assert len(results) == 40
    assert peak == 3


@pytest.mark.parametrize("health", [(503, {"status": "unavailable", "model_loaded": False}),
                                    (200, {"status": "ok", "model_loaded": False})])
def test_health_check_failure_sends_nothing(health):
    api = FakeApi(health=health)
    with pytest.raises(ApiUnavailable, match="not ready"):
        simulate(load_stream(DF, limit=5), api=api)
    assert api.requests == []


def test_unreachable_api():
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ApiUnavailable, match="cannot reach"):
        asyncio.run(run(load_stream(DF, limit=5), Config(), "r",
                        transport=httpx.MockTransport(down)))


def test_http_errors_are_results_not_crashes():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        return httpx.Response(422, json={"error": {"code": "validation_error"}})

    results = asyncio.run(run(load_stream(DF, limit=3), Config(rate=1000), "r",
                              transport=httpx.MockTransport(handler)))
    assert [(r.ok, r.status, r.error) for r in results] == [(False, 422, "http_422")] * 3


def test_bad_concurrency():
    with pytest.raises(ValueError):
        asyncio.run(run(load_stream(DF, limit=1), Config(concurrency=0), "r"))


def test_run_ids_are_valid_request_id_parts():
    from api.main import REQUEST_ID_PATTERN

    rid = request_id(new_run_id(), 42_720)
    assert REQUEST_ID_PATTERN.match(rid) and rid.startswith("sim-")


# --- CLI -------------------------------------------------------------------------

def test_cli_defaults(monkeypatch):
    monkeypatch.setenv("API_URL", "http://api.test:9000")
    args = cli.parse_args([])
    assert (args.rate, args.mode, args.speed, args.concurrency, args.offset, args.limit) == \
        (20.0, "fixed", 10.0, 10, 0, None)
    assert args.api_url == "http://api.test:9000"


def test_cli_rejects_unknown_mode():
    with pytest.raises(SystemExit):
        cli.parse_args(["--mode", "warp"])


def test_cli_main_end_to_end(monkeypatch, capsys):
    api = FakeApi()
    real_run = cli.run

    async def run_with_fake_api(stream, config, run_id):
        return await real_run(stream, config, run_id, transport=api.transport)

    monkeypatch.setattr(cli, "load_stream", lambda offset, limit: load_stream(DF, offset, limit))
    monkeypatch.setattr(cli, "run", run_with_fake_api)
    assert cli.main(["--limit", "20", "--rate", "1000"]) == 0
    out = capsys.readouterr().out
    assert "sent 20, ok 20, errors 0" in out


def test_cli_main_reports_unavailable_api(monkeypatch, capsys):
    async def unavailable(stream, config, run_id):
        raise ApiUnavailable("cannot reach the API")

    monkeypatch.setattr(cli, "load_stream", lambda offset, limit: load_stream(DF, offset, limit))
    monkeypatch.setattr(cli, "run", unavailable)
    assert cli.main(["--limit", "1"]) == 2
    assert "cannot reach the API" in capsys.readouterr().err


def test_connection_error_mid_run_is_a_result():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        raise httpx.ReadTimeout("slow", request=request)

    results = asyncio.run(run(load_stream(DF, limit=2), Config(rate=1000), "r",
                              transport=httpx.MockTransport(handler)))
    assert [(r.ok, r.status, r.error) for r in results] == [(False, None, "ReadTimeout")] * 2


def test_health_check_with_non_json_body():
    api = FakeApi(health=(502, None))
    api.handler = lambda request: httpx.Response(502, text="<html>bad gateway</html>")
    with pytest.raises(ApiUnavailable, match="502"):
        simulate(load_stream(DF, limit=1), api=api)
