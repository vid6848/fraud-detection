"""Saves scored transactions to Supabase and reads them back for GET /explain/{id}.

Two kinds of access, on purpose:
- Writes use the service role key. It bypasses Row Level Security, so it stays on
  the server (never in the dashboard). Alerts are not written here: a database
  trigger adds one for every MEDIUM/HIGH row in the same insert.
- Reads use the anon key plus the *caller's* login token, so RLS decides what an
  analyst may see, exactly as it does for the dashboard.
- `verify_user` asks Supabase Auth who a login token belongs to (POST /demo/stream
  has no table read that would reject a bad token for us).

Both talk to Supabase's REST API (PostgREST) directly; the full supabase client
adds auth/session machinery the API doesn't need.
"""
from typing import Protocol

import httpx
import pandas as pd
from postgrest import SyncPostgrestClient
from postgrest.exceptions import APIError
from postgrest.types import ReturnMethod

from api.config import Settings
from api.scoring import Score
from ml.config import RAW_COLUMNS
from ml.features import V_COLUMNS, hour_of_day

TABLE = "transactions"
JSON_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
# PostgREST codes for a missing, malformed or expired JWT.
AUTH_ERROR_CODES = {"PGRST301", "PGRST302", "PGRST303"}


class StorageUnavailable(RuntimeError):
    """Supabase could not be reached or answered with an unexpected error."""


class InvalidToken(RuntimeError):
    """The caller's login token was rejected."""


class TransactionStore(Protocol):
    def save(self, rows: list[dict]) -> None: ...

    def get(self, transaction_id: str, user_token: str) -> dict | None: ...

    def verify_user(self, user_token: str) -> str: ...


class SupabaseStore:
    def __init__(self, url: str, service_role_key: str, anon_key: str, timeout: float,
                 transport: httpx.BaseTransport | None = None):
        self._rest_url = f"{url.rstrip('/')}/rest/v1"
        self._auth_url = f"{url.rstrip('/')}/auth/v1"
        self._anon_key = anon_key
        # One pooled HTTP client for every request; headers (and so the key) are
        # set per PostgREST client, which makes sharing it safe.
        self._http = httpx.Client(timeout=timeout, transport=transport)
        self._writer = self._client(service_role_key, service_role_key)

    def _client(self, api_key: str, bearer: str) -> SyncPostgrestClient:
        headers = {**JSON_HEADERS, "apikey": api_key, "Authorization": f"Bearer {bearer}"}
        return SyncPostgrestClient(self._rest_url, headers=headers, http_client=self._http)

    def close(self) -> None:
        self._http.close()

    def save(self, rows: list[dict]) -> None:
        """One bulk insert for all rows (a /predict/batch call is one request)."""
        self._writer.from_(TABLE).insert(rows, returning=ReturnMethod.minimal).execute()

    def get(self, transaction_id: str, user_token: str) -> dict | None:
        """The stored row, or None if it doesn't exist or RLS hides it from this user."""
        reader = self._client(self._anon_key, user_token)
        try:
            result = reader.from_(TABLE).select("*").eq("id", transaction_id).limit(1).execute()
        except APIError as exc:
            if exc.code in AUTH_ERROR_CODES:
                raise InvalidToken(exc.message) from exc
            raise StorageUnavailable(f"Supabase error {exc.code}") from exc
        except httpx.HTTPError as exc:  # network errors, timeouts
            raise StorageUnavailable(type(exc).__name__) from exc
        return result.data[0] if result.data else None

    def verify_user(self, user_token: str) -> str:
        """The id of the signed-in (non-anonymous) user behind `user_token`."""
        headers = {"apikey": self._anon_key, "Authorization": f"Bearer {user_token}"}
        try:
            response = self._http.get(f"{self._auth_url}/user", headers=headers)
        except httpx.HTTPError as exc:  # network errors, timeouts
            raise StorageUnavailable(type(exc).__name__) from exc
        if response.status_code in (401, 403):
            raise InvalidToken("token rejected by Supabase Auth")
        if response.status_code != 200:
            raise StorageUnavailable(f"Supabase Auth HTTP {response.status_code}")
        user = response.json()
        if not user.get("id") or user.get("is_anonymous"):
            raise InvalidToken("not a signed-in analyst")
        return user["id"]


def build_store(settings: Settings) -> SupabaseStore | None:
    """A store when all Supabase settings are present, else None (storage off)."""
    if not settings.storage_configured:
        return None
    return SupabaseStore(settings.supabase_url, settings.supabase_service_role_key,
                         settings.supabase_anon_key, settings.storage_timeout_s)


def build_row(transaction_id: str, transaction: dict, score: Score, model_version: str,
              latency_ms: float) -> dict:
    """One `transactions` row. `transaction` is a raw input row (Time, V1-V28, Amount)."""
    return {
        "id": transaction_id,
        "time_seconds": float(transaction["Time"]),
        "amount": float(transaction["Amount"]),
        "hour_of_day": int(hour_of_day(transaction["Time"])),
        "features": {v: float(transaction[v]) for v in V_COLUMNS},
        "probability": score.probability,
        "risk_level": score.risk_level.value,
        "reasons": [{"code": r.code, "message": r.message} for r in score.reasons],
        "model_version": model_version,
        "latency_ms": latency_ms,
    }


def stored_frame(row: dict) -> pd.DataFrame:
    """Rebuild the raw one-row model input from a stored `transactions` row."""
    values = {"Time": float(row["time_seconds"]), "Amount": float(row["amount"]),
              **{v: float(row["features"][v]) for v in V_COLUMNS}}
    return pd.DataFrame([values], columns=RAW_COLUMNS)
