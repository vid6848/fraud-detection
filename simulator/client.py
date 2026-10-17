"""Talks to the API: health check, POST /predict and POST /predict/batch.

Both predict calls return one `Result` per row, so the rest of the simulator
doesn't care which endpoint was used. A failed request gives every row in it
the same error.
"""
import random
import time
from dataclasses import dataclass

import httpx

RETRY_BASE_S = 0.25  # backoff: 0.25 s, 0.5 s, 1 s, ... (each +/- 20% jitter)


class ApiUnavailable(RuntimeError):
    """The API can't be reached or isn't ready (model not loaded)."""


@dataclass(frozen=True)
class Result:
    index: int                      # position in the stream
    request_id: str
    ok: bool
    status: int | None              # HTTP status, None if no response at all
    latency_ms: float               # client-side round trip of the request
    risk_level: str | None = None
    probability: float | None = None
    server_latency_ms: float | None = None
    transaction_id: str | None = None
    error: str | None = None        # e.g. "http_422", "ConnectError"
    attempts: int = 1               # > 1 when the request was retried


def is_retryable(status: int | None) -> bool:
    """Connection errors/timeouts (no status) and 5xx are worth retrying.
    4xx never is: the same request would be rejected again (e.g. 422)."""
    return status is None or status >= 500


def backoff_delay(attempt: int, jitter=random.uniform) -> float:
    """Seconds to wait before retry number `attempt` (1, 2, 3, ...)."""
    return RETRY_BASE_S * 2 ** (attempt - 1) * jitter(0.8, 1.2)


async def check_health(client: httpx.AsyncClient) -> dict:
    try:
        r = await client.get("/health")
    except httpx.TransportError as exc:
        raise ApiUnavailable(f"cannot reach the API at {client.base_url} "
                             f"({type(exc).__name__}). Is uvicorn running?") from exc
    body = _json(r)
    if r.status_code != 200 or not body.get("model_loaded"):
        raise ApiUnavailable(f"API at {client.base_url} is not ready "
                             f"(GET /health -> {r.status_code})")
    return body


async def predict(client: httpx.AsyncClient, indices: list[int], payloads: list[dict],
                  request_id: str) -> list[Result]:
    """One row -> POST /predict; several rows -> one POST /predict/batch."""
    batch = len(payloads) > 1
    path, body = (("/predict/batch", {"transactions": payloads}) if batch
                  else ("/predict", payloads[0]))
    start = time.perf_counter()
    try:
        r = await client.post(path, json=body, headers={"X-Request-ID": request_id})
    except httpx.TransportError as exc:
        return _failed(indices, request_id, None, _ms_since(start), type(exc).__name__)
    latency_ms = _ms_since(start)
    if r.status_code != 200:
        return _failed(indices, request_id, r.status_code, latency_ms, f"http_{r.status_code}")
    try:
        data = r.json()
        scored = data["results"] if batch else [data]
        return [Result(i, request_id, ok=True, status=200, latency_ms=latency_ms,
                       risk_level=s["risk_level"], probability=s["probability"],
                       server_latency_ms=data.get("latency_ms"),
                       transaction_id=s.get("transaction_id"))
                for i, s in zip(indices, scored, strict=True)]
    except (ValueError, KeyError, TypeError):  # 200 but not the expected body
        return _failed(indices, request_id, 200, latency_ms, "bad_response")


def _failed(indices, request_id, status, latency_ms, error) -> list[Result]:
    return [Result(i, request_id, ok=False, status=status, latency_ms=latency_ms, error=error)
            for i in indices]


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)
