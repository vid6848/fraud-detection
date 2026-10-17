"""Phase 4: offline checks on the SQL migrations in supabase/migrations/.

These don't touch the database; they catch mistakes before a migration is applied
(a table without RLS, a leaked key, files out of order).
"""
import re

import pytest

from ml.config import ROOT

MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
MIGRATIONS = sorted(MIGRATIONS_DIR.glob("*.sql"))
NAME_PATTERN = re.compile(r"^(\d{14})_[a-z0-9_]+\.sql$")
TABLES = {"transactions", "alerts", "feedback", "model_runs"}


def _sql(path) -> str:
    text = path.read_text()
    return re.sub(r"--[^\n]*", "", text).lower()  # drop comments


def _all_sql() -> str:
    return "\n".join(_sql(p) for p in MIGRATIONS)


def test_migrations_exist():
    assert MIGRATIONS, "no migrations found"


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_migration_file_names_are_timestamped(path):
    assert NAME_PATTERN.match(path.name), path.name


def test_migration_versions_are_unique():
    versions = [NAME_PATTERN.match(p.name).group(1) for p in MIGRATIONS]
    assert len(versions) == len(set(versions))


def test_expected_tables_are_created():
    created = set(re.findall(r"create table public\.(\w+)", _all_sql()))
    assert TABLES <= created


def test_every_table_has_rls_enabled():
    sql = _all_sql()
    created = set(re.findall(r"create table public\.(\w+)", sql))
    with_rls = set(re.findall(r"alter table public\.(\w+) enable row level security", sql))
    assert created <= with_rls, f"tables without RLS: {created - with_rls}"


def test_functions_pin_search_path():
    # Supabase's security advisor flags functions with a mutable search_path.
    for path in MIGRATIONS:
        for body in re.findall(r"create (?:or replace )?function.*?\$\$", _sql(path), re.S):
            assert "set search_path = ''" in body, f"{path.name}: {body[:60]}"


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_no_secrets_in_migrations(path):
    text = path.read_text()
    assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}", text), "JWT-looking string in migration"
    assert not re.search(r"sb_secret_\w+", text), "Supabase secret key in migration"


def test_realtime_on_transactions_and_alerts():
    published = re.findall(r"alter publication supabase_realtime add table ([^;]+);", _all_sql())
    tables = {t.strip().removeprefix("public.") for group in published for t in group.split(",")}
    assert tables == {"transactions", "alerts"}
