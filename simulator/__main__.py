"""Replay held-out test transactions to the API.

    python -m simulator                         # 20 rows/s, whole test split
    python -m simulator --rate 50 --limit 500
    python -m simulator --mode replay --speed 10  # real gaps between transactions, 10x faster
    python -m simulator --batch 50                # 50 rows per POST /predict/batch

Start the API first (uvicorn api.main:app --no-access-log). --api-url defaults
to API_URL in .env. Ctrl+C stops gracefully: in-flight requests finish, then the
summary prints and the JSON report is saved to simulator/reports/.
"""
import argparse
import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from ml.config import ROOT
from simulator.client import ApiUnavailable
from simulator.data import Stream, load_stream
from simulator.display import LiveView, render_summary
from simulator.runner import Config, Outcome, new_run_id, run, validate
from simulator.schedule import MODES
from simulator.stats import RunStats

DEFAULT_API_URL = "http://localhost:8000"
REPORT_DIR = ROOT / "simulator" / "reports"
# 130 = stopped by Ctrl+C (shell convention); 3 = gave up on a failing API
EXIT_CODES = {"completed": 0, "error_rate": 3, "interrupted": 130}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(prog="python -m simulator",
                                     description="Replay test-set transactions to the API.")
    parser.add_argument("--rate", type=float, default=20.0,
                        help="rows per second in fixed mode (default 20)")
    parser.add_argument("--limit", type=int, help="send at most this many rows")
    parser.add_argument("--offset", type=int, default=0,
                        help="start at this row of the test split (default 0)")
    parser.add_argument("--api-url", default=os.getenv("API_URL") or DEFAULT_API_URL,
                        help="API base URL (default: API_URL from .env)")
    parser.add_argument("--mode", choices=MODES, default="fixed",
                        help="fixed = steady --rate; replay = real gaps between Time values")
    parser.add_argument("--speed", type=float, default=10.0,
                        help="replay mode: how many times faster than real time (default 10)")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="max requests in flight (default 10)")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="seconds per request (default 10)")
    parser.add_argument("--retries", type=int, default=3,
                        help="retries for connection errors and 5xx, never 4xx (default 3)")
    parser.add_argument("--max-error-rate", type=float, default=0.2,
                        help="stop if more than this share of the last 100 requests "
                             "failed (default 0.2)")
    parser.add_argument("--batch", type=int, default=1, metavar="N",
                        help="send N rows per POST /predict/batch (default 1 = /predict)")
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR,
                        help="where to save the JSON report (default simulator/reports/)")
    parser.add_argument("--no-live", action="store_true",
                        help="no live view, only the final summary")
    return parser.parse_args(argv)


async def simulate(stream: Stream, config: Config, run_id: str, stats: RunStats,
                   live: bool = True) -> Outcome:
    """Run with the live view, stopping gracefully on Ctrl+C (SIGINT) or SIGTERM."""
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    handled = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
            handled.append(sig)
        except (NotImplementedError, RuntimeError):  # e.g. Windows, or not the main thread
            pass
    done = asyncio.Event()
    view = asyncio.create_task(LiveView(stats, time.monotonic).run(done)) if live else None
    try:
        return await run(stream, config, run_id, on_result=stats.record, stop=stop)
    finally:
        done.set()
        if view is not None:
            await view
        for sig in handled:
            loop.remove_signal_handler(sig)


def save_report(report: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"run-{report['run_id']}.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Config(api_url=args.api_url, rate=args.rate, mode=args.mode, speed=args.speed,
                    concurrency=args.concurrency, timeout=args.timeout, retries=args.retries,
                    max_error_rate=args.max_error_rate, batch_size=args.batch)
    try:
        validate(config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    stream = load_stream(offset=args.offset, limit=args.limit)
    run_id = new_run_id()
    endpoint = "/predict/batch" if config.batch_size > 1 else "/predict"
    print(f"run {run_id}: {len(stream)} test rows -> {config.api_url}{endpoint} "
          f"({config.mode} mode, Ctrl+C to stop)", flush=True)
    stats = RunStats(stream.labels)
    started_at, start = _now(), time.monotonic()
    try:
        outcome = asyncio.run(simulate(stream, config, run_id, stats, live=not args.no_live))
    except ApiUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = stats.to_report(
        run_id=run_id,
        config={**asdict(config), "offset": args.offset, "limit": args.limit},
        started_at=started_at, ended_at=_now(), duration_s=time.monotonic() - start,
        stopped_reason=outcome.stopped_reason,
    )
    report["rows"]["cancelled_in_flight"] = outcome.cancelled
    path = save_report(report, args.report_dir)
    print("\n".join(render_summary(report, _relative(path))))
    return EXIT_CODES[outcome.stopped_reason]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
