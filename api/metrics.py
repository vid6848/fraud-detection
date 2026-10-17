"""Request metrics behind GET /metrics.

These live in memory: they reset when the server restarts, and with several
uvicorn workers each worker keeps (and reports) its own numbers. That is fine
for a single-process demo; a shared store (e.g. Prometheus) would replace this
in a multi-worker deployment.

Latency percentiles use a rolling window of the most recent requests so memory
stays bounded however long the server runs.
"""
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import UTC, datetime

import numpy as np

LATENCY_WINDOW = 10_000
PERCENTILES = (50, 95, 99)


class MetricsCollector:
    def __init__(self, window: int = LATENCY_WINDOW):
        self._lock = threading.Lock()  # sync endpoints run in a thread pool
        self._window = window
        self._started_monotonic = time.monotonic()
        self.started_at = datetime.now(UTC).isoformat(timespec="seconds")
        self._requests = Counter()
        self._errors = Counter()
        self._risk_levels = Counter({"LOW": 0, "MEDIUM": 0, "HIGH": 0})
        self._latencies = deque(maxlen=window)
        self._latencies_by_endpoint = defaultdict(lambda: deque(maxlen=window))
        self.storage_enabled = False
        self._storage = Counter({"writes_ok": 0, "writes_failed": 0,
                                 "rows_written": 0, "rows_failed": 0})

    def record_request(self, endpoint: str, status: int, latency_ms: float) -> None:
        with self._lock:
            self._requests[endpoint] += 1
            if status >= 400:
                self._errors[str(status)] += 1
            self._latencies.append(latency_ms)
            self._latencies_by_endpoint[endpoint].append(latency_ms)

    def record_risk_levels(self, levels) -> None:
        with self._lock:
            self._risk_levels.update(levels)

    def record_storage_write(self, ok: bool, rows: int) -> None:
        with self._lock:
            if ok:
                self._storage.update(writes_ok=1, rows_written=rows)
            else:
                self._storage.update(writes_failed=1, rows_failed=rows)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "uptime_seconds": round(time.monotonic() - self._started_monotonic, 3),
                "started_at": self.started_at,
                "requests": {
                    "total": sum(self._requests.values()),
                    "by_endpoint": dict(sorted(self._requests.items())),
                },
                "errors": {
                    "total": sum(self._errors.values()),
                    "by_status": dict(sorted(self._errors.items())),
                },
                "latency_ms": {
                    "window": self._window,
                    **_percentiles(self._latencies),
                    "by_endpoint": {
                        endpoint: _percentiles(values)
                        for endpoint, values in sorted(self._latencies_by_endpoint.items())
                    },
                },
                "risk_levels": dict(self._risk_levels),
                "storage": {"enabled": self.storage_enabled, **self._storage},
                "scope": "in-memory, per worker process, reset on restart",
            }


def _percentiles(values) -> dict:
    if not values:
        return {"count": 0, **{f"p{q}": None for q in PERCENTILES}}
    result = np.percentile(np.fromiter(values, dtype=float), PERCENTILES)
    return {"count": len(values), **{f"p{q}": round(float(v), 3) for q, v in zip(PERCENTILES, result)}}
