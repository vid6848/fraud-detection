"""Talks to the API: health check and POST /predict."""
import time
from dataclasses import dataclass

import httpx


class ApiUnavailable(RuntimeError):
    """The API can't be reached or isn't ready (model not loaded)."""


@dataclass(frozen=True)
class Result:
    index: int                      # position in the stream
    request_id: str
    ok: bool
    status: int | None              # HTTP status, None if no response at all
    latency_ms: float               # client-side round trip
    risk_level: str | None = None
    probability: float | None = None
    server_latency_ms: float | None = None
    transaction_id: str | None = None
    error: str | None = None        # e.g. "http_422", "ConnectError"
    attempts: int = 1               # > 1 when the request was retried


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


async def predict(client: httpx.AsyncClient, index: int, payload: dict,
                  request_id: str) -> Result:
    start = time.perf_counter()
    try:
        r = await client.post("/predict", json=payload, headers={"X-Request-ID": request_id})
    except httpx.TransportError as exc:
        return Result(index, request_id, ok=False, status=None,
                      latency_ms=_ms_since(start), error=type(exc).__name__)
    latency_ms = _ms_since(start)
    if r.status_code != 200:
        return Result(index, request_id, ok=False, status=r.status_code,
                      latency_ms=latency_ms, error=f"http_{r.status_code}")
    body = r.json()
    return Result(index, request_id, ok=True, status=200, latency_ms=latency_ms,
                  risk_level=body["risk_level"], probability=body["probability"],
                  server_latency_ms=body.get("latency_ms"),
                  transaction_id=body.get("transaction_id"))


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)
