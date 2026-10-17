"""Running totals for one simulator run, and the JSON report built from them.

Fraud counts use the labels kept locally by the simulator (the API never sees
them): each scored row lands in its risk band, split into fraud / legit.

Rows and requests are counted separately: in batch mode one request carries many
rows, so latency, retries and errors-by-kind are per request, everything else per row.
"""
from collections import Counter, deque

import numpy as np

from simulator.client import Result

LEVELS = ("LOW", "MEDIUM", "HIGH")
LIVE_WINDOW = 500  # live p50/p95 cover the most recent requests


class RunStats:
    def __init__(self, labels: list[int], live_window: int = LIVE_WINDOW):
        self.labels = labels
        self.planned = len(labels)
        self.sent = 0                    # rows
        self.ok = 0
        self.failed = 0
        self.requests = 0
        self.failed_requests = 0
        self.errors = Counter()          # failed requests by kind, e.g. {"http_422": 3}
        self.retries = 0
        self.latencies: list[float] = []         # client round trip, every ok request
        self.server_latencies: list[float] = []  # the API's own latency_ms
        self.recent = deque(maxlen=live_window)
        self.bands = {level: Counter(fraud=0, legit=0) for level in LEVELS}
        self.unscored_frauds = 0                 # frauds whose request failed
        self.first_request_id: str | None = None
        self.last_request_id: str | None = None

    def record(self, results: list[Result]) -> None:
        """The results of one finished request (one per row)."""
        first = results[0]
        self.requests += 1
        self.retries += first.attempts - 1
        if self.first_request_id is None:
            self.first_request_id = first.request_id
        self.last_request_id = first.request_id
        self.sent += len(results)
        if not first.ok:
            self.failed_requests += 1
            self.errors[first.error] += 1
            self.failed += len(results)
            self.unscored_frauds += sum(self.labels[r.index] for r in results)
            return
        self.ok += len(results)
        self.latencies.append(first.latency_ms)
        self.recent.append(first.latency_ms)
        if first.server_latency_ms is not None:
            self.server_latencies.append(first.server_latency_ms)
        for r in results:
            self.bands[r.risk_level]["fraud" if self.labels[r.index] == 1 else "legit"] += 1

    @property
    def error_count(self) -> int:
        return self.failed

    def risk_counts(self) -> dict[str, int]:
        return {level: sum(self.bands[level].values()) for level in LEVELS}

    def frauds(self) -> dict[str, int]:
        """Labelled frauds by outcome: caught as HIGH / MEDIUM, missed (LOW), not scored."""
        caught_high = self.bands["HIGH"]["fraud"]
        caught_medium = self.bands["MEDIUM"]["fraud"]
        missed = self.bands["LOW"]["fraud"]
        return {
            "total_sent": caught_high + caught_medium + missed + self.unscored_frauds,
            "caught_high": caught_high,
            "caught_medium": caught_medium,
            "missed_low": missed,
            "not_scored": self.unscored_frauds,
        }

    def false_alarms(self) -> int:
        """Legit rows flagged MEDIUM or HIGH (each one costs an analyst review)."""
        return self.bands["HIGH"]["legit"] + self.bands["MEDIUM"]["legit"]

    def live_latency(self) -> dict[str, float | None]:
        return percentiles(self.recent, (50, 95))

    def to_report(self, *, run_id: str, config: dict, started_at: str, ended_at: str,
                  duration_s: float, stopped_reason: str) -> dict:
        frauds = self.frauds()
        scored_frauds = frauds["caught_high"] + frauds["caught_medium"] + frauds["missed_low"]
        bands = {}
        for level in LEVELS:
            total = sum(self.bands[level].values())
            bands[level] = {
                "rows": total,
                "frauds": self.bands[level]["fraud"],
                "legit": self.bands[level]["legit"],
                "fraud_rate": _ratio(self.bands[level]["fraud"], total),
            }
        flagged = bands["HIGH"]["rows"] + bands["MEDIUM"]["rows"]
        return {
            "run_id": run_id,
            "config": config,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_s": round(duration_s, 3),
            "stopped_reason": stopped_reason,
            "rows": {
                "planned": self.planned,
                "sent": self.sent,
                "ok": self.ok,
                "errors": self.error_count,
                "not_sent": self.planned - self.sent,
            },
            "requests": {"sent": self.requests, "failed": self.failed_requests},
            "actual_rate_per_s": round(self.sent / duration_s, 2) if duration_s > 0 else None,
            "errors_by_kind": dict(sorted(self.errors.items())),
            "retries": self.retries,
            "latency_ms": {
                "client_round_trip": percentiles(self.latencies),
                "server": percentiles(self.server_latencies),
            },
            "risk_levels": self.risk_counts(),
            "bands": bands,
            "frauds": {
                **frauds,
                # Of the frauds that were scored, the share flagged HIGH / HIGH or MEDIUM
                "recall_high": _ratio(frauds["caught_high"], scored_frauds),
                "recall_high_or_medium": _ratio(frauds["caught_high"] + frauds["caught_medium"],
                                                scored_frauds),
            },
            "false_alarms": self.false_alarms(),
            # Of the rows flagged MEDIUM/HIGH, the share that really were fraud
            "precision_flagged": _ratio(bands["HIGH"]["frauds"] + bands["MEDIUM"]["frauds"],
                                        flagged),
            "precision_high": bands["HIGH"]["fraud_rate"],
            "first_request_id": self.first_request_id,
            "last_request_id": self.last_request_id,
            "note": "Fraud counts use labels kept locally by the simulator; "
                    "the API never receives them.",
        }


def percentiles(values, qs=(50, 95, 99)) -> dict:
    if not values:
        return {"count": 0, **{f"p{q}": None for q in qs}}
    result = np.percentile(np.fromiter(values, dtype=float), qs)
    return {"count": len(values), **{f"p{q}": round(float(v), 3) for q, v in zip(qs, result)}}


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None
