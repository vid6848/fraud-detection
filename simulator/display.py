"""Live terminal view and the end-of-run summary.

On a terminal the block is redrawn in place (ANSI cursor moves, no extra
library); when output goes to a file or pipe, a single progress line is printed
every few seconds instead so logs stay readable.
"""
import asyncio
import sys
from typing import TextIO

from simulator.stats import RunStats

CURSOR_UP_AND_CLEAR = "\x1b[{n}F\x1b[J"


def _fmt(value: float | None, unit: str = "") -> str:
    return "-" if value is None else f"{value:.1f}{unit}"


def render(stats: RunStats, elapsed_s: float) -> list[str]:
    """The live block: one line per topic."""
    rate = stats.sent / elapsed_s if elapsed_s > 0 else 0.0
    latency = stats.live_latency()
    risk = stats.risk_counts()
    frauds = stats.frauds()
    errors = ", ".join(f"{k} {v}" for k, v in sorted(stats.errors.items())) or "none"
    return [
        f"sent {stats.sent}/{stats.planned}  ok {stats.ok}  errors {stats.error_count}  "
        f"retries {stats.retries}  |  {rate:.1f} rows/s  |  {elapsed_s:.0f}s",
        f"latency (last {latency['count']})  p50 {_fmt(latency['p50'], ' ms')}  "
        f"p95 {_fmt(latency['p95'], ' ms')}",
        f"risk     LOW {risk['LOW']}  MEDIUM {risk['MEDIUM']}  HIGH {risk['HIGH']}",
        f"frauds   caught HIGH {frauds['caught_high']}  caught MEDIUM {frauds['caught_medium']}  "
        f"missed {frauds['missed_low']}  |  false alarms {stats.false_alarms()}",
        f"failed requests  {errors}",
    ]


def render_summary(report: dict, path: str | None) -> list[str]:
    rows, frauds, lat = report["rows"], report["frauds"], report["latency_ms"]
    rt, server = lat["client_round_trip"], lat["server"]
    risk = report["risk_levels"]

    def pct(x):
        return "-" if x is None else f"{x * 100:.1f}%"

    lines = [
        "",
        f"== run {report['run_id']} {report['stopped_reason']} "
        f"after {report['duration_s']:.1f}s ==",
        f"rows      sent {rows['sent']} of {rows['planned']}  ok {rows['ok']}  "
        f"errors {rows['errors']}  retries {report['retries']}  "
        f"({report['actual_rate_per_s'] or 0:.1f} rows/s, {report['requests']['sent']} requests)",
        f"latency   round trip p50 {_fmt(rt['p50'], ' ms')}  p95 {_fmt(rt['p95'], ' ms')}  "
        f"p99 {_fmt(rt['p99'], ' ms')}  |  server p50 {_fmt(server['p50'], ' ms')}",
        f"risk      LOW {risk['LOW']}  MEDIUM {risk['MEDIUM']}  HIGH {risk['HIGH']}",
        f"frauds    {frauds['total_sent']} sent: caught HIGH {frauds['caught_high']}, "
        f"caught MEDIUM {frauds['caught_medium']}, missed {frauds['missed_low']}"
        + (f", not scored {frauds['not_scored']}" if frauds["not_scored"] else ""),
        f"quality   recall HIGH {pct(frauds['recall_high'])}  "
        f"HIGH+MEDIUM {pct(frauds['recall_high_or_medium'])}  |  "
        f"precision HIGH {pct(report['precision_high'])}  "
        f"flagged {pct(report['precision_flagged'])}  |  false alarms {report['false_alarms']}",
    ]
    if report["errors_by_kind"]:
        lines.append("failed    " + ", ".join(f"{k} {v}"
                                              for k, v in report["errors_by_kind"].items()))
    if path:
        lines.append(f"report    {path}")
    return lines


class LiveView:
    def __init__(self, stats: RunStats, clock, out: TextIO | None = None,
                 interval_s: float = 0.5, plain_every_s: float = 5.0):
        self.stats = stats
        self.clock = clock
        self.out = out or sys.stdout  # looked up now, so a redirected stdout is honoured
        self.tty = self.out.isatty()
        self.interval_s = interval_s if self.tty else plain_every_s
        self._start = clock()
        self._drawn = 0

    def draw(self) -> None:
        lines = render(self.stats, self.clock() - self._start)
        if self.tty:
            if self._drawn:
                self.out.write(CURSOR_UP_AND_CLEAR.format(n=self._drawn))
            self.out.write("\n".join(lines) + "\n")
            self._drawn = len(lines)
        else:
            self.out.write(lines[0] + "\n")
        self.out.flush()

    async def run(self, done: asyncio.Event) -> None:
        """Redraw until `done` is set, then draw the final state once."""
        while not done.is_set():
            self.draw()
            try:
                await asyncio.wait_for(done.wait(), self.interval_s)
            except TimeoutError:
                pass
        self.draw()
