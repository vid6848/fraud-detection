"""POST /demo/stream: replay held-out test rows through the model, server-side.

On the free deployment nobody runs `python -m simulator`, so a logged-in analyst
can start a short stream from the dashboard instead. The rows are a small slice
of the test split with the labels removed (`api/assets/demo_rows.csv.gz`, made
by `scripts/make_demo_rows.py`); the full dataset never reaches the server.

The stream writes to the shared Supabase project, so it is guarded:
- one stream at a time (per process; the API runs a single worker);
- each analyst can start one every `cooldown_s` seconds, and all analysts
  together at most `max_per_hour` in any rolling hour.

`start` runs on the event loop and never awaits between its checks and creating
the task, so two requests can't both pass the "is one running?" check.
"""
import asyncio
import logging
import math
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from api.logging_setup import LOGGER_NAME
from ml.config import RAW_COLUMNS

logger = logging.getLogger(LOGGER_NAME)

HOUR_S = 3600.0
# A stream stops early after this many failed rows in a row (e.g. Supabase is down).
MAX_CONSECUTIVE_FAILURES = 5


class DemoBusy(RuntimeError):
    """A stream is already running."""


class DemoRateLimited(RuntimeError):
    def __init__(self, retry_after_s: float, reason: str):
        super().__init__(reason)
        self.retry_after_s = retry_after_s


@dataclass
class DemoRun:
    id: str
    state: str  # running | completed | failed | cancelled
    total: int
    rate_per_s: float
    started_at: str
    sent: int = 0
    failed: int = 0
    finished_at: str | None = None


def load_demo_rows(path: Path) -> list[dict]:
    """The committed demo rows as API payloads (Time, V1-V28, Amount), in order."""
    df = pd.read_csv(path, float_precision="round_trip")  # exactly the values written
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
    return [{c: float(v) for c, v in row.items()}
            for row in df[RAW_COLUMNS].to_dict("records")]


class DemoStreamer:
    def __init__(self, rows: list[dict], process: Callable[[dict], None], *,
                 rate_per_s: float, max_rows: int, cooldown_s: float, max_per_hour: int,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        """`process` scores and saves one row; it runs in a worker thread and may raise."""
        if not rows:
            raise ValueError("no demo rows")
        self.rows = rows
        self._process = process
        self.rate_per_s = rate_per_s
        self.max_rows = min(max_rows, len(rows))
        self.cooldown_s = cooldown_s
        self.max_per_hour = max_per_hour
        self._clock = clock
        self._sleep = sleep
        self._last_start: dict[str, float] = {}  # user id -> clock time
        self._starts: deque[float] = deque()     # all users, last hour
        self._task: asyncio.Task | None = None
        self.run: DemoRun | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, user_id: str, limit: int | None = None) -> DemoRun:
        """Start a stream of `limit` rows (default and cap: `max_rows`) or raise."""
        if self.running:
            raise DemoBusy("a demo stream is already running")
        now = self._clock()
        last = self._last_start.get(user_id)
        if last is not None and now - last < self.cooldown_s:
            raise DemoRateLimited(self.cooldown_s - (now - last),
                                  "you started a demo stream recently")
        while self._starts and now - self._starts[0] >= HOUR_S:
            self._starts.popleft()
        if len(self._starts) >= self.max_per_hour:
            raise DemoRateLimited(HOUR_S - (now - self._starts[0]),
                                  "the hourly demo stream limit has been reached")
        self._last_start[user_id] = now
        self._starts.append(now)

        total = min(limit or self.max_rows, self.max_rows)
        self.run = DemoRun(id=uuid.uuid4().hex, state="running", total=total,
                           rate_per_s=self.rate_per_s, started_at=_utc_now())
        self._task = asyncio.create_task(self._stream(self.run, self.rows[:total]))
        logger.info("demo stream started", extra={"demo_run_id": self.run.id, "user_id": user_id,
                                                  "rows": total})
        return self.run

    async def _stream(self, run: DemoRun, rows: list[dict]) -> None:
        """Open-loop pacing: row i is due at start + i / rate, however long saving takes."""
        interval = 1 / self.rate_per_s
        start = self._clock()
        consecutive_failures = 0
        try:
            for i, row in enumerate(rows):
                delay = start + i * interval - self._clock()
                if delay > 0:
                    await self._sleep(delay)
                try:
                    await asyncio.to_thread(self._process, row)
                except Exception as exc:
                    run.failed += 1
                    consecutive_failures += 1
                    logger.error("demo stream row failed", extra={
                        "demo_run_id": run.id, "error_type": type(exc).__name__})
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        run.state = "failed"
                        break
                else:
                    run.sent += 1
                    consecutive_failures = 0
            else:
                run.state = "completed"
        except asyncio.CancelledError:
            run.state = "cancelled"
            raise
        finally:
            run.finished_at = _utc_now()
            logger.info("demo stream finished", extra={
                "demo_run_id": run.id, "state": run.state, "sent": run.sent,
                "failed": run.failed})

    def status(self) -> dict:
        return {"running": self.running, "max_rows": self.max_rows,
                "run": asdict(self.run) if self.run else None}

    async def aclose(self) -> None:
        """Cancel a running stream (server shutdown)."""
        if self.running:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            if self.run.state == "running":  # cancelled before its first step ran
                self.run.state = "cancelled"
                self.run.finished_at = _utc_now()


def retry_after_header(seconds: float) -> str:
    return str(max(1, math.ceil(seconds)))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
