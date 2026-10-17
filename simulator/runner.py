"""Sends a stream to the API on schedule, with a cap on requests in flight.

- Retries: connection errors and 5xx are retried with exponential backoff
  (`retries` times); 4xx such as 422 never are. A retry keeps its request ID.
- Error-rate stop: if more than `max_error_rate` of the last `error_window`
  requests failed (after retries), the run stops instead of hammering a broken API.
- Batch mode (`batch_size` > 1): rows go out in groups via /predict/batch; the
  rate stays rows per second, so a batch leaves when its first row is due.
- Stopping early (Ctrl+C): set the `stop` event. No new requests start, requests
  already in flight get `grace_s` seconds to finish, and the run returns what it
  has, so the summary and report still cover everything that was sent.
"""
import asyncio
import secrets
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime

import httpx

from simulator.client import Result, backoff_delay, check_health, is_retryable, predict
from simulator.data import Stream
from simulator.schedule import send_offsets

MAX_BATCH_SIZE = 1000  # the API's default MAX_BATCH_SIZE


@dataclass(frozen=True)
class Config:
    api_url: str = "http://localhost:8000"
    rate: float = 20.0
    mode: str = "fixed"
    speed: float = 10.0
    concurrency: int = 10
    timeout: float = 10.0
    grace_s: float = 5.0         # after a stop, how long in-flight requests may finish
    retries: int = 3             # extra attempts for connection errors / 5xx
    max_error_rate: float = 0.2  # stop when the recent failure share goes above this
    error_window: int = 100      # ... measured over this many recent requests
    min_requests: int = 20       # ... once at least this many have finished
    batch_size: int = 1          # > 1: use POST /predict/batch


@dataclass(frozen=True)
class Outcome:
    results: list[Result]
    stopped_reason: str   # "completed", "interrupted" or "error_rate"
    cancelled: int = 0    # in-flight requests abandoned after the grace period


def new_run_id() -> str:
    """e.g. 20261017-103000-a1b2: sortable, and safe inside an X-Request-ID."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def request_id(run_id: str, index: int, batch: bool = False) -> str:
    """sim-<run>-<row> for single rows, sim-<run>-b<first row> for batches."""
    return f"sim-{run_id}-{'b' if batch else ''}{index}"


def chunks(n_rows: int, size: int) -> list[list[int]]:
    return [list(range(start, min(start + size, n_rows))) for start in range(0, n_rows, size)]


def validate(config: Config) -> None:
    if config.concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if not 1 <= config.batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch size must be between 1 and {MAX_BATCH_SIZE}")
    if config.retries < 0:
        raise ValueError("retries must be >= 0")
    if not 0 <= config.max_error_rate <= 1:
        raise ValueError("max error rate must be between 0 and 1")


async def run(stream: Stream, config: Config, run_id: str, *,
              transport: httpx.AsyncBaseTransport | None = None,
              on_result: Callable[[list[Result]], None] | None = None,
              stop: asyncio.Event | None = None,
              sleep: Callable[[float], Awaitable[None]] | None = None,
              clock: Callable[[], float] = time.monotonic) -> Outcome:
    """Health-check the API, then send every row at its scheduled time.

    `on_result` gets the results of each finished request (one per row).
    `transport`, `sleep` and `clock` are swapped out in tests (fake API, fake time).
    Raises `ApiUnavailable` if the health check fails; nothing is sent then.
    """
    validate(config)
    stop = stop or asyncio.Event()
    sleep = sleep or _sleep_unless(stop)
    offsets = send_offsets(stream.times, config.mode, config.rate, config.speed)
    groups = chunks(len(stream), config.batch_size)
    limits = httpx.Limits(max_connections=config.concurrency,
                          max_keepalive_connections=config.concurrency)
    results: list[Result] = []
    recent_ok: deque[bool] = deque(maxlen=config.error_window)
    reason: list[str] = []  # becomes ["error_rate"] if the error-rate guard trips

    async with httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout,
                                 limits=limits, transport=transport) as client:
        await check_health(client)
        in_flight = asyncio.Semaphore(config.concurrency)

        async def send(rows: list[int]) -> None:
            rid = request_id(run_id, rows[0], batch=config.batch_size > 1)
            payloads = [stream.payloads[i] for i in rows]
            try:
                attempt = 1
                while True:
                    batch = await predict(client, rows, payloads, rid)
                    retry = (not batch[0].ok and is_retryable(batch[0].status)
                             and attempt <= config.retries and not stop.is_set())
                    if not retry:
                        break
                    await sleep(backoff_delay(attempt))
                    attempt += 1
                batch = [replace(r, attempts=attempt) for r in batch]
                results.extend(batch)
                if on_result is not None:
                    on_result(batch)
                recent_ok.append(batch[0].ok)
                if _too_many_errors(recent_ok, config) and not stop.is_set():
                    reason.append("error_rate")
                    stop.set()
            finally:
                in_flight.release()

        start = clock()
        tasks = []
        for rows in groups:
            delay = start + offsets[rows[0]] - clock()
            if delay > 0:
                await sleep(delay)
            if stop.is_set():
                break
            await in_flight.acquire()  # at the cap: wait, the run falls behind schedule
            if stop.is_set():
                in_flight.release()
                break
            tasks.append(asyncio.create_task(send(rows)))

        cancelled = await _finish(tasks, stop, config.grace_s)

    stopped = reason[0] if reason else ("interrupted" if stop.is_set() else "completed")
    return Outcome(results=sorted(results, key=lambda r: r.index), stopped_reason=stopped,
                   cancelled=cancelled)


def _too_many_errors(recent_ok: deque, config: Config) -> bool:
    if len(recent_ok) < config.min_requests:
        return False
    return recent_ok.count(False) / len(recent_ok) > config.max_error_rate


async def _finish(tasks: list[asyncio.Task], stop: asyncio.Event, grace_s: float) -> int:
    """Wait for in-flight requests. Once `stop` is set, allow `grace_s` more seconds,
    then cancel what's left. Returns how many were cancelled."""
    pending = set(tasks)
    if pending and not stop.is_set():
        stopper = asyncio.create_task(stop.wait())
        while pending and not stop.is_set():
            done, _ = await asyncio.wait(pending | {stopper}, return_when=asyncio.FIRST_COMPLETED)
            pending -= done
        stopper.cancel()
    if pending:
        _, pending = await asyncio.wait(pending, timeout=grace_s)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    return len(pending)


def _sleep_unless(stop: asyncio.Event) -> Callable[[float], Awaitable[None]]:
    """asyncio.sleep that returns early when `stop` is set (long replay gaps)."""
    async def sleep(seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), seconds)
        except TimeoutError:
            pass
    return sleep
