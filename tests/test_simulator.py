"""Phase 5: the stream simulator, against a fake API (no server, no dataset, no waiting).

The fake API is an httpx.MockTransport; time is a fake clock whose sleep() just
moves the clock forward, so pacing can be checked exactly and instantly.
"""
import asyncio
import io
import json
import sys

import httpx
import pytest

from ml.config import RAW_COLUMNS, ROOT, SPLIT_BOUNDARIES, TARGET
from simulator import __main__ as cli
from simulator.client import ApiUnavailable, Result
from simulator.display import LiveView, render, render_summary
from simulator.data import load_stream
from simulator.runner import Config, new_run_id, request_id, run
from simulator.schedule import send_offsets
from simulator.stats import RunStats
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


def run_sync(*args, **kwargs):
    return asyncio.run(run(*args, **kwargs)).results


def simulate(stream, config=Config(), api=None, time=None, run_id="test-run"):
    time = time or FakeTime()
    api = api or FakeApi(time)
    results = run_sync(stream, config, run_id, transport=api.transport,
                              sleep=time.sleep, clock=time.clock)
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
    results = run_sync(stream, Config(rate=10_000, concurrency=3), "r",
                              transport=httpx.MockTransport(slow))
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
        run_sync(load_stream(DF, limit=5), Config(), "r",
                        transport=httpx.MockTransport(down))


def test_http_errors_are_results_not_crashes():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        return httpx.Response(422, json={"error": {"code": "validation_error"}})

    results = run_sync(load_stream(DF, limit=3), Config(rate=1000), "r",
                              transport=httpx.MockTransport(handler))
    assert [(r.ok, r.status, r.error) for r in results] == [(False, 422, "http_422")] * 3


def test_bad_concurrency():
    with pytest.raises(ValueError):
        run_sync(load_stream(DF, limit=1), Config(concurrency=0), "r")


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


def fake_cli_run(monkeypatch, api, stop_after=None):
    """Route the CLI's run() to the fake API; optionally 'press Ctrl+C' after N results."""
    real_run = cli.run

    async def run_with_fake_api(stream, config, run_id, **kwargs):
        if stop_after is not None:
            record, stop = kwargs["on_result"], kwargs["stop"]

            def on_result(batch):
                record(batch)
                if batch[-1].index + 1 >= stop_after:
                    stop.set()
            kwargs["on_result"] = on_result
        return await real_run(stream, config, run_id, transport=api.transport, **kwargs)

    monkeypatch.setattr(cli, "load_stream", lambda offset, limit: load_stream(DF, offset, limit))
    monkeypatch.setattr(cli, "run", run_with_fake_api)


def test_cli_main_end_to_end(monkeypatch, capsys, tmp_path):
    fake_cli_run(monkeypatch, FakeApi())
    assert cli.main(["--limit", "20", "--rate", "1000", "--no-live",
                     "--report-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "completed" in out and "sent 20 of 20  ok 20  errors 0" in out
    [path] = tmp_path.glob("run-*.json")
    report = json.loads(path.read_text())
    assert report["rows"]["sent"] == 20 and report["stopped_reason"] == "completed"
    assert report["config"]["limit"] == 20
    assert str(path) in out


def test_ctrl_c_still_writes_the_report(monkeypatch, capsys, tmp_path):
    fake_cli_run(monkeypatch, FakeApi(), stop_after=5)
    code = cli.main(["--limit", "100", "--rate", "50", "--concurrency", "1", "--no-live",
                     "--report-dir", str(tmp_path)])
    assert code == 130
    report = json.loads(next(tmp_path.glob("run-*.json")).read_text())
    assert report["stopped_reason"] == "interrupted"
    assert 5 <= report["rows"]["sent"] < 100
    assert report["rows"]["not_sent"] == 100 - report["rows"]["sent"]
    assert "interrupted" in capsys.readouterr().out


def test_cli_main_reports_unavailable_api(monkeypatch, capsys):
    async def unavailable(stream, config, run_id, **kwargs):
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

    results = run_sync(load_stream(DF, limit=2), Config(rate=1000), "r",
                              transport=httpx.MockTransport(handler))
    assert [(r.ok, r.status, r.error) for r in results] == [(False, None, "ReadTimeout")] * 2


def test_health_check_with_non_json_body():
    api = FakeApi(health=(502, None))
    api.handler = lambda request: httpx.Response(502, text="<html>bad gateway</html>")
    with pytest.raises(ApiUnavailable, match="502"):
        simulate(load_stream(DF, limit=1), api=api)



# --- stats and report ------------------------------------------------------------

def _result(index, level=None, ok=True, error=None, latency=10.0, attempts=1):
    return Result(index, f"sim-r-{index}", ok=ok, status=200 if ok else None, latency_ms=latency,
                  risk_level=level, probability=0.5, server_latency_ms=latency / 2,
                  error=error, attempts=attempts)


def test_stats_bands_use_local_labels():
    labels = [1, 1, 1, 1, 0, 0, 0, 1]
    stats = RunStats(labels)
    for r in [_result(0, "HIGH"), _result(1, "MEDIUM"), _result(2, "LOW"),
              _result(3, ok=False, error="ConnectError", attempts=3),
              _result(4, "HIGH"), _result(5, "MEDIUM"), _result(6, "LOW")]:
        stats.record([r])
    assert stats.frauds() == {"total_sent": 4, "caught_high": 1, "caught_medium": 1,
                              "missed_low": 1, "not_scored": 1}
    assert stats.false_alarms() == 2
    assert stats.risk_counts() == {"LOW": 2, "MEDIUM": 2, "HIGH": 2}
    assert stats.retries == 2 and dict(stats.errors) == {"ConnectError": 1}

    report = stats.to_report(run_id="r", config={}, started_at="a", ended_at="b",
                             duration_s=2.0, stopped_reason="completed")
    assert report["rows"] == {"planned": 8, "sent": 7, "ok": 6, "errors": 1, "not_sent": 1}
    assert report["actual_rate_per_s"] == 3.5
    assert report["bands"]["HIGH"] == {"rows": 2, "frauds": 1, "legit": 1, "fraud_rate": 0.5}
    assert report["frauds"]["recall_high"] == round(1 / 3, 4)
    assert report["frauds"]["recall_high_or_medium"] == round(2 / 3, 4)
    assert report["precision_flagged"] == 0.5
    assert report["latency_ms"]["client_round_trip"]["p50"] == 10.0
    assert report["latency_ms"]["server"]["p50"] == 5.0
    assert (report["first_request_id"], report["last_request_id"]) == ("sim-r-0", "sim-r-6")
    json.dumps(report)


def test_empty_report_has_no_divisions_by_zero():
    report = RunStats([0, 1]).to_report(run_id="r", config={}, started_at="a", ended_at="b",
                                        duration_s=0.0, stopped_reason="interrupted")
    assert report["actual_rate_per_s"] is None
    assert report["precision_high"] is None and report["frauds"]["recall_high"] is None
    assert report["latency_ms"]["client_round_trip"] == {"count": 0, "p50": None,
                                                         "p95": None, "p99": None}
    assert "== run r interrupted" in "\n".join(render_summary(report, None))


def test_live_frame_and_summary_text():
    stats = RunStats([1, 0])
    stats.record([_result(0, "HIGH")])
    stats.record([_result(1, ok=False, error="http_422")])
    frame = "\n".join(render(stats, elapsed_s=2.0))
    assert "sent 2/2  ok 1  errors 1" in frame and "1.0 rows/s" in frame
    assert "caught HIGH 1" in frame and "http_422 1" in frame
    report = stats.to_report(run_id="r", config={}, started_at="a", ended_at="b",
                             duration_s=1.0, stopped_reason="completed")
    summary = "\n".join(render_summary(report, "simulator/reports/run-r.json"))
    assert "caught HIGH 1" in summary and "failed    http_422 1" in summary
    assert "report    simulator/reports/run-r.json" in summary


class FakeTerminal(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


@pytest.mark.parametrize("tty", [True, False])
def test_live_view_redraws_in_place_only_on_a_terminal(tty):
    out = FakeTerminal(tty)
    view = LiveView(RunStats([0]), clock=lambda: 1.0, out=out)
    view.draw()
    view.draw()
    text = out.getvalue()
    assert ("\x1b[" in text) is tty
    assert text.count("sent 0/1") == 2
    assert len(text.splitlines()) == (10 if tty else 2)


def test_live_view_loop_stops_when_done():
    async def go():
        out = FakeTerminal(False)
        done = asyncio.Event()
        view = LiveView(RunStats([0]), clock=lambda: 0.0, out=out, plain_every_s=0.001)
        task = asyncio.create_task(view.run(done))
        await asyncio.sleep(0.01)
        done.set()
        await task
        return out.getvalue()

    assert asyncio.run(go()).count("sent 0/1") >= 2  # periodic draws + a final one


def test_stop_during_the_schedule():
    async def go():
        stop = asyncio.Event()
        results = []

        def on_result(r):
            results.append(r)
            stop.set()

        outcome = await run(load_stream(DF, limit=50), Config(rate=100), "r",
                            transport=FakeApi().transport, on_result=on_result, stop=stop)
        return outcome

    outcome = asyncio.run(go())
    assert outcome.stopped_reason == "interrupted"
    assert 1 <= len(outcome.results) < 50


def test_stop_while_waiting_for_in_flight_requests():
    async def go():
        stop = asyncio.Event()

        async def hang(request):
            if request.url.path == "/health":
                return httpx.Response(200, json=HEALTHY)
            stop.set()                      # Ctrl+C arrives while this request is in flight
            await asyncio.sleep(10)
            return httpx.Response(200, json={})

        return await run(load_stream(DF, limit=1), Config(grace_s=0.01), "r",
                         transport=httpx.MockTransport(hang), stop=stop)

    outcome = asyncio.run(go())
    assert outcome.stopped_reason == "interrupted"
    assert outcome.cancelled == 1 and outcome.results == []


# --- resilience: retries, error-rate stop, batch mode -----------------------------

class ScriptedApi(FakeApi):
    """Answers each scoring request with the next scripted response, then scores normally.

    A script entry is an HTTP status (int) or "drop" for a connection error.
    """

    def __init__(self, script, time=None):
        super().__init__(time)
        self.script = list(script)

    def handler(self, request):
        if request.url.path != "/health" and self.script:
            self.requests.append(request)
            step = self.script.pop(0)
            if step == "drop":
                raise httpx.ConnectError("refused", request=request)
            if step != 200:
                return httpx.Response(step, json={"error": {"code": "x"}})
            self.requests.pop()  # scored normally below (which records it again)
        return super().handler(request)


def test_5xx_is_retried_then_succeeds():
    api = ScriptedApi([503, 500])
    results, _ = simulate(load_stream(DF, limit=1), Config(retries=3), api=api)
    [r] = results
    assert r.ok and r.attempts == 3
    ids = {req.headers["X-Request-ID"] for req in api.requests}
    assert ids == {"sim-test-run-0"}  # a retry keeps its request ID


def test_connection_error_is_retried_then_counted():
    api = ScriptedApi(["drop"] * 4)
    results, _ = simulate(load_stream(DF, limit=1), Config(retries=3), api=api)
    [r] = results
    assert not r.ok and r.error == "ConnectError" and r.attempts == 4
    assert len(api.requests) == 4


def test_422_is_never_retried():
    api = ScriptedApi([422])
    results, _ = simulate(load_stream(DF, limit=2), Config(retries=3), api=api)
    assert [(r.ok, r.status, r.attempts) for r in results] == [(False, 422, 1), (True, 200, 1)]
    assert len(api.requests) == 2  # the 422 once, then the second row


def test_backoff_grows_and_has_jitter():
    from simulator.client import backoff_delay, is_retryable

    assert [backoff_delay(a, jitter=lambda lo, hi: 1.0) for a in (1, 2, 3)] == [0.25, 0.5, 1.0]
    assert 0.2 <= backoff_delay(1) <= 0.3
    assert is_retryable(None) and is_retryable(502)
    assert not is_retryable(422) and not is_retryable(404)


def test_run_stops_when_the_error_rate_is_too_high():
    api = ScriptedApi([500] * 1000)
    config = Config(retries=0, max_error_rate=0.2, min_requests=20, concurrency=1)
    time = FakeTime()
    outcome = asyncio.run(run(load_stream(DF, limit=200), config, "r", transport=api.transport,
                              sleep=time.sleep, clock=time.clock))
    assert outcome.stopped_reason == "error_rate"
    assert 20 <= len(outcome.results) < 200


def test_occasional_errors_do_not_stop_the_run():
    api = ScriptedApi(([500] + [200] * 9) * 10)  # 10% failures: below the 20% limit
    config = Config(retries=0, max_error_rate=0.2, concurrency=1)
    results, _ = simulate(load_stream(DF, limit=100), config, api=api)
    assert len(results) == 100


def test_batch_mode_sends_groups_and_keeps_row_order():
    batches = []

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        assert request.url.path == "/predict/batch"
        rows = json.loads(request.content)["transactions"]
        batches.append((request.headers["X-Request-ID"], rows))
        return httpx.Response(200, json={
            "results": [{"probability": r["Amount"] / 1e6, "risk_level": "LOW", "reasons": [],
                         "transaction_id": None} for r in rows],
            "count": len(rows), "model_version": "1.0.0", "latency_ms": 3.0})

    stream = load_stream(DF, limit=23)
    time = FakeTime()
    outcome = asyncio.run(run(stream, Config(batch_size=10, rate=10), "r",
                              transport=httpx.MockTransport(handler),
                              sleep=time.sleep, clock=time.clock))
    assert [len(rows) for _, rows in batches] == [10, 10, 3]
    assert [rid for rid, _ in batches] == ["sim-r-b0", "sim-r-b10", "sim-r-b20"]
    assert [rows for _, rows in batches] == [stream.payloads[0:10], stream.payloads[10:20],
                                             stream.payloads[20:23]]
    assert [r.index for r in outcome.results] == list(range(23))
    assert [r.probability for r in outcome.results] == \
        [p["Amount"] / 1e6 for p in stream.payloads]
    assert time.now == pytest.approx(2.0)  # batches at 0 s, 1 s, 2 s: still 10 rows/s


def test_batch_failure_fails_every_row_and_counts_one_request():
    api = ScriptedApi([422])
    stream = load_stream(DF, limit=5)
    outcome = asyncio.run(run(stream, Config(batch_size=5), "r", transport=api.transport))
    assert [r.error for r in outcome.results] == ["http_422"] * 5
    stats = RunStats(stream.labels)
    stats.record(outcome.results)
    assert (stats.requests, stats.failed_requests, stats.failed, stats.sent) == (1, 1, 5, 5)


def test_batch_latency_counts_once_per_request():
    stats = RunStats([0, 0, 0])
    stats.record([_result(i, "LOW", latency=30.0) for i in range(3)])
    assert stats.latencies == [30.0] and stats.ok == 3 and stats.requests == 1


@pytest.mark.parametrize("config", [Config(batch_size=0), Config(batch_size=1001),
                                    Config(retries=-1), Config(max_error_rate=1.5)])
def test_bad_resilience_settings(config):
    with pytest.raises(ValueError):
        asyncio.run(run(load_stream(DF, limit=1), config, "r"))


def test_cli_rejects_bad_batch_size(capsys):
    assert cli.main(["--batch", "5000"]) == 2
    assert "batch size" in capsys.readouterr().err


def test_cli_exit_code_when_the_api_keeps_failing(monkeypatch, tmp_path, capsys):
    fake_cli_run(monkeypatch, ScriptedApi([500] * 1000))
    code = cli.main(["--limit", "60", "--rate", "10000", "--retries", "0", "--concurrency", "1",
                     "--no-live", "--report-dir", str(tmp_path)])
    assert code == 3
    report = json.loads(next(tmp_path.glob("run-*.json")).read_text())
    assert report["stopped_reason"] == "error_rate"
    assert report["errors_by_kind"] == {"http_500": report["requests"]["failed"]}



@pytest.mark.parametrize("body", [{"unexpected": True}, [1, 2], "not json"])
def test_malformed_200_is_an_error_not_a_crash(body):
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        if body == "not json":
            return httpx.Response(200, text="<html>")
        return httpx.Response(200, json=body)

    results = run_sync(load_stream(DF, limit=2), Config(retries=3), "r",
                       transport=httpx.MockTransport(handler))
    assert [(r.ok, r.error, r.attempts) for r in results] == [(False, "bad_response", 1)] * 2


def test_batch_with_wrong_number_of_results_is_an_error():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=HEALTHY)
        return httpx.Response(200, json={"results": [{"probability": 0.1, "risk_level": "LOW"}]})

    results = run_sync(load_stream(DF, limit=3), Config(batch_size=3), "r",
                       transport=httpx.MockTransport(handler))
    assert [r.error for r in results] == ["bad_response"] * 3



# --- remaining paths -----------------------------------------------------------

def test_simulate_with_live_view_and_without_signal_support(monkeypatch, capsys):
    """Live view on (non-TTY output), and a loop that can't hook signals (e.g. Windows)."""
    def no_signals(self, sig, callback):
        raise NotImplementedError

    monkeypatch.setattr(asyncio.AbstractEventLoop, "add_signal_handler", no_signals)
    monkeypatch.setattr(type(asyncio.new_event_loop()), "add_signal_handler", no_signals)
    real_run = cli.run
    api = FakeApi()

    async def run_with_fake_api(stream, config, run_id, **kwargs):
        return await real_run(stream, config, run_id, transport=api.transport, **kwargs)

    monkeypatch.setattr(cli, "run", run_with_fake_api)
    stream = load_stream(DF, limit=5)
    stats = RunStats(stream.labels)
    outcome = asyncio.run(cli.simulate(stream, Config(rate=1000), "r", stats, live=True))
    assert outcome.stopped_reason == "completed" and stats.sent == 5
    assert "sent 5/5" in capsys.readouterr().out  # final live frame


def test_result_without_server_latency():
    stats = RunStats([0])
    stats.record([Result(0, "sim-r-0", ok=True, status=200, latency_ms=4.0, risk_level="LOW")])
    assert stats.server_latencies == [] and stats.latencies == [4.0]


def test_report_path_outside_the_repo_is_shown_in_full(tmp_path):
    assert cli._relative(tmp_path / "x.json") == str(tmp_path / "x.json")
    assert cli._relative(cli.REPORT_DIR / "x.json") == "simulator/reports/x.json"


def test_module_entry_point_help():
    import subprocess

    out = subprocess.run([sys.executable, "-m", "simulator", "--help"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    for option in ("--rate", "--limit", "--api-url", "--mode", "--speed", "--batch",
                   "--retries", "--max-error-rate"):
        assert option in out
