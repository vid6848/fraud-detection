"""Helpers for tests that talk to the real Supabase project.

Credentials come from the environment or `.env`; tests that need them are
skipped when they are missing (e.g. in CI), never failed. Keys are never printed.
"""
import os

import pytest
from dotenv import dotenv_values

from ml.config import ROOT


def env(name: str) -> str | None:
    value = os.getenv(name) or dotenv_values(ROOT / ".env").get(name)
    if not value or "your-" in value:  # .env.example placeholders count as missing
        return None
    return value


def require_env(*names: str) -> dict[str, str]:
    values = {name: env(name) for name in names}
    missing = [name for name, value in values.items() if value is None]
    if missing:
        pytest.skip(f"needs {', '.join(missing)} (set in .env)")
    return values


def client(key_name: str):
    """Supabase client using SUPABASE_URL and the key named `key_name`."""
    from supabase import create_client

    values = require_env("SUPABASE_URL", key_name)
    return create_client(values["SUPABASE_URL"], values[key_name])


def analyst_client():
    """Anon-key client signed in as the demo analyst."""
    creds = require_env("DEMO_ANALYST_EMAIL", "DEMO_ANALYST_PASSWORD")
    c = client("SUPABASE_ANON_KEY")
    c.auth.sign_in_with_password(
        {"email": creds["DEMO_ANALYST_EMAIL"], "password": creds["DEMO_ANALYST_PASSWORD"]}
    )
    return c
