"""Sends a stream to the API on schedule, with a cap on requests in flight."""
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


def new_run_id() -> str:
    """e.g. 20261017-103000-a1b2: sortable, and safe inside an X-Request-ID."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def request_id(run_id: str, index: int) -> str:
    return f"sim-{run_id}-{index}"


async def run(stream: Stream, config: Config, run_id: str, *,
              transport: httpx.AsyncBaseTransport | None = None,
              on_result: Callable[[Result], None] | None = None,
              sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
              clock: Callable[[], float] = time.monotonic) -> list[Result]:
    """Health-check the API, then send every row at its scheduled time.

    `transport`, `sleep` and `clock` are swapped out in tests (fake API, fake time).
    Raises `ApiUnavailable` if the health check fails; nothing is sent then.
    """
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
            await in_flight.acquire()  # at the cap: wait, the run falls behind schedule
            tasks.append(asyncio.create_task(send(i)))
        await asyncio.gather(*tasks)

    return sorted(results, key=lambda r: r.index)
