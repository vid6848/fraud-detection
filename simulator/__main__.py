"""Replay held-out test transactions to the API.

    python -m simulator                         # 20 rows/s, whole test split
    python -m simulator --rate 50 --limit 500
    python -m simulator --mode replay --speed 10  # real gaps between transactions, 10x faster

Start the API first (uvicorn api.main:app --no-access-log). --api-url defaults
to API_URL in .env.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter

from dotenv import load_dotenv

from ml.config import ROOT
from simulator.client import ApiUnavailable
from simulator.data import load_stream
from simulator.runner import Config, new_run_id, run
from simulator.schedule import MODES

DEFAULT_API_URL = "http://localhost:8000"


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Config(api_url=args.api_url, rate=args.rate, mode=args.mode, speed=args.speed,
                    concurrency=args.concurrency, timeout=args.timeout)
    stream = load_stream(offset=args.offset, limit=args.limit)
    run_id = new_run_id()
    print(f"run {run_id}: {len(stream)} test rows -> {config.api_url}/predict "
          f"({config.mode} mode)")
    try:
        results = asyncio.run(run(stream, config, run_id))
    except ApiUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    ok = [r for r in results if r.ok]
    levels = Counter(r.risk_level for r in ok)
    print(f"sent {len(results)}, ok {len(ok)}, errors {len(results) - len(ok)} | "
          f"LOW {levels['LOW']}, MEDIUM {levels['MEDIUM']}, HIGH {levels['HIGH']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
