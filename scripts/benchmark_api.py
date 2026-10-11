"""Benchmark the API over real HTTP with held-out test-split rows.

    python scripts/benchmark_api.py              # starts its own uvicorn on port 8799
    python scripts/benchmark_api.py --url http://localhost:8000   # use a running server

1. POST /predict for N test rows, one at a time over a keep-alive connection
   (like the Phase 5 simulator): p50/p95/p99 round-trip latency + throughput.
2. POST /predict/batch with the same N rows, repeated: round-trip and
   server-side time per batch.

Latency is measured by the client, so it includes HTTP + JSON on localhost.
Needs data/creditcard.csv.
"""
import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.config import RAW_COLUMNS  # noqa: E402
from ml.eda_utils import load_data  # noqa: E402
from ml.split import time_split  # noqa: E402

WARMUP = 20


def test_rows(n: int) -> list[dict]:
    _, _, test = time_split(load_data())
    return test[RAW_COLUMNS].head(n).to_dict("records")


def start_server(port: int) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(port),
           "--no-access-log", "--log-level", "warning"]
    env = {**os.environ, "LOG_LEVEL": "WARNING"}  # keep per-request JSON logs out of the timing
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def wait_until_healthy(client: httpx.Client, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise RuntimeError("API did not become healthy in time")


def stats(ms: list[float]) -> str:
    p50, p95, p99 = np.percentile(ms, [50, 95, 99])
    return f"p50 {p50:.2f} ms | p95 {p95:.2f} ms | p99 {p99:.2f} ms | mean {np.mean(ms):.2f} ms"


def bench_predict(client: httpx.Client, rows: list[dict]) -> None:
    for row in rows[:WARMUP]:
        client.post("/predict", json=row).raise_for_status()
    latencies, server = [], []
    start = time.perf_counter()
    for row in rows:
        t = time.perf_counter()
        r = client.post("/predict", json=row)
        latencies.append((time.perf_counter() - t) * 1000)
        r.raise_for_status()
        server.append(r.json()["latency_ms"])
    elapsed = time.perf_counter() - start
    print(f"POST /predict x {len(rows)} sequential requests")
    print(f"  round-trip : {stats(latencies)}")
    print(f"  server-side: {stats(server)}")
    print(f"  throughput : {len(rows) / elapsed:.0f} requests/s (one client, one connection)")


def bench_batch(client: httpx.Client, rows: list[dict], repeats: int) -> None:
    payload = {"transactions": rows}
    client.post("/predict/batch", json=payload).raise_for_status()  # warm-up
    latencies, server = [], []
    for _ in range(repeats):
        t = time.perf_counter()
        r = client.post("/predict/batch", json=payload)
        latencies.append((time.perf_counter() - t) * 1000)
        r.raise_for_status()
        server.append(r.json()["latency_ms"])
    med = float(np.median(latencies))
    print(f"POST /predict/batch with {len(rows)} rows x {repeats} runs")
    print(f"  round-trip : {stats(latencies)}")
    print(f"  server-side: {stats(server)}")
    print(f"  throughput : {len(rows) / (med / 1000):,.0f} rows/s (median batch)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--batch-repeats", type=int, default=20)
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--url", help="benchmark an already running API instead")
    args = parser.parse_args()

    rows = test_rows(args.rows)
    server = None if args.url else start_server(args.port)
    url = args.url or f"http://127.0.0.1:{args.port}"
    try:
        with httpx.Client(base_url=url, timeout=30) as client:
            wait_until_healthy(client)
            print(f"{platform.platform()} | Python {platform.python_version()} | {url}\n")
            bench_predict(client, rows)
            print()
            bench_batch(client, rows, args.batch_repeats)
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
