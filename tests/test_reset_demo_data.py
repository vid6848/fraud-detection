"""Phase 5 step 4: scripts/reset_demo_data.py (no database: the client is a fake)."""
import sys
from types import SimpleNamespace

import pytest

from ml.config import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import reset_demo_data  # noqa: E402


class FakeClient:
    """Mimics the supabase query builder for the calls the script makes."""

    def __init__(self, rows: dict[str, int]):
        self.rows = dict(rows)
        self.deletes = []

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, client, table):
        self.client, self.table, self.action = client, table, None

    def select(self, columns, count=None, head=False):
        assert count == "exact" and head
        self.action = "count"
        return self

    def delete(self):
        self.action = "delete"
        return self

    def gte(self, column, value):
        self.filter = (column, value)
        return self

    def execute(self):
        if self.action == "delete":
            self.client.deletes.append((self.table, self.filter))
            for table in reset_demo_data.TABLES:  # cascade
                self.client.rows[table] = 0
            return SimpleNamespace(count=None)
        return SimpleNamespace(count=self.client.rows[self.table])


def make(rows=None):
    return FakeClient(rows or {"transactions": 300, "alerts": 6, "feedback": 1})


def test_asks_and_deletes_on_yes(capsys):
    client = make()
    assert reset_demo_data.main([], client=client, ask=lambda prompt: "yes") == 0
    assert client.deletes == [("transactions", ("created_at", "1970-01-01"))]
    out = capsys.readouterr().out
    assert "300 transactions, 6 alerts, 1 feedback" in out and "model_runs is kept" in out
    assert "Now: 0 transactions, 0 alerts, 0 feedback" in out


@pytest.mark.parametrize("answer", ["no", "", "y"])
def test_anything_but_yes_cancels(answer, capsys):
    client = make()
    assert reset_demo_data.main([], client=client, ask=lambda prompt: answer) == 1
    assert client.deletes == []
    assert "Cancelled" in capsys.readouterr().out


def test_yes_flag_skips_the_prompt():
    def no_prompt(prompt):
        raise AssertionError("should not ask")

    client = make()
    assert reset_demo_data.main(["--yes"], client=client, ask=no_prompt) == 0
    assert len(client.deletes) == 1


def test_nothing_to_delete(capsys):
    client = make({"transactions": 0, "alerts": 0, "feedback": 0})
    assert reset_demo_data.main([], client=client, ask=lambda p: "yes") == 0
    assert client.deletes == []
    assert "Nothing to delete" in capsys.readouterr().out


def test_needs_credentials(monkeypatch):
    monkeypatch.setattr(reset_demo_data, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(SystemExit, match="SUPABASE_URL"):
        reset_demo_data.service_client()
