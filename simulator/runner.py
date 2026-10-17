"""Sends a stream to the API on schedule, with a cap on requests in flight.

Stopping early (Ctrl+C): set the `stop` event. No new requests start, requests
already in flight get `grace_s` seconds to finish, and the run returns what it
has, so the summary and report still cover everything that was sent.
"""
import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from simulator.client import Result, check_health, predict
from simulator.data import Stream
from simulator.schedule import send_offsets


@dataclass(frozen=True)
class Config:
    api_url: str = "http://localhost:8000"
    rate: float = 20.0
    mode: str = "fixed"
    speed: float = 10.0
    concurrency: int = 10
    timeout: float = 10.0
    grace_s: float = 5.0  # after a stop, how long in-flight requests may finish


@dataclass(frozen=True)
class Outcome:
    results: list[Result]
    stopped_reason: str   # "completed" or "interrupted"
    cancelled: int = 0    # in-flight requests abandoned after the grace period


def new_run_id() -> str:
    """e.g. 20261017-103000-a1b2: sortable, and safe inside an X-Request-ID."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def request_id(run_id: str, index: int) -> str:
    return f"sim-{run_id}-{index}"


async def run(stream: Stream, config: Config, run_id: str, *,
              transport: httpx.AsyncBaseTransport | None = None,
              on_result: Callable[[Result], None] | None = None,
              stop: asyncio.Event | None = None,
              sleep: Callable[[float], Awaitable[None]] | None = None,
              clock: Callable[[], float] = time.monotonic) -> Outcome:
    """Health-check the API, then send every row at its scheduled time.

    `transport`, `sleep` and `clock` are swapped out in tests (fake API, fake time).
    Raises `ApiUnavailable` if the health check fails; nothing is sent then.
    """
    stop = stop or asyncio.Event()
    sleep = sleep or _sleep_unless(stop)
    if config.concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    offsets = send_offsets(stream.times, config.mode, config.rate, config.speed)
    limits = httpx.Limits(max_connections=config.concurrency,
                          max_keepalive_connections=config.concurrency)
    results: list[Result] = []

    async with httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout,
                                 limits=limits, transport=transport) as client:
        await check_health(client)
        in_flight = asyncio.Semaphore(config.concurrency)

        async def send(i: int) -> None:
            try:
                result = await predict(client, i, stream.payloads[i], request_id(run_id, i))
                results.append(result)
                if on_result is not None:
                    on_result(result)
            finally:
                in_flight.release()

        start = clock()
        tasks = []
        for i, offset in enumerate(offsets):
            delay = start + offset - clock()
            if delay > 0:
                await sleep(delay)
            if stop.is_set():
                break
            await in_flight.acquire()  # at the cap: wait, the run falls behind schedule
            tasks.append(asyncio.create_task(send(i)))

        cancelled = await _finish(tasks, stop, config.grace_s)

    return Outcome(results=sorted(results, key=lambda r: r.index),
                   stopped_reason="interrupted" if stop.is_set() else "completed",
                   cancelled=cancelled)


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
