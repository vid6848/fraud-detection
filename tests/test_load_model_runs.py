"""Phase 4 step 4: scripts/load_model_runs.py (no database: the client is a fake)."""
import json
import sys

import pytest

from ml.config import ARTIFACTS_DIR, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import load_model_runs  # noqa: E402

METADATA = json.loads((ARTIFACTS_DIR / "metadata.json").read_text())


class FakeClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        self.name = name
        return self

    def upsert(self, row, on_conflict):
        self.calls.append((self.name, row, on_conflict))
        return self

    def execute(self):
        return None


def test_row_comes_from_metadata():
    row = load_model_runs.model_run_row(METADATA)
    assert row["version"] == METADATA["model_version"]
    assert row["trained_at"] == METADATA["trained_at"]
    assert row["metrics"]["test_metrics"] == METADATA["test_metrics"]
    assert row["metrics"]["threshold"] == METADATA["threshold"]
    assert "libraries" not in row["metrics"]
    json.dumps(row)


def test_missing_keys_are_reported():
    with pytest.raises(ValueError, match="test_metrics"):
        load_model_runs.model_run_row({k: v for k, v in METADATA.items() if k != "test_metrics"})


def test_main_upserts_on_version(capsys):
    client = FakeClient()
    row = load_model_runs.main([], client=client)
    assert client.calls == [("model_runs", row, "version")]
    assert "upserted version 1.0.0" in capsys.readouterr().out


def test_dry_run_writes_nothing(capsys):
    row = load_model_runs.main(["--dry-run"], client=None)
    assert json.loads(capsys.readouterr().out) == row


def test_service_client_needs_credentials(monkeypatch):
    monkeypatch.setattr(load_model_runs, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(SystemExit, match="SUPABASE_URL"):
        load_model_runs.service_client()
