"""Delete demo data (transactions, alerts, feedback) from Supabase.

    python scripts/reset_demo_data.py         # shows counts, asks you to type "yes"
    python scripts/reset_demo_data.py --yes   # no prompt (scripts / CI)

Deletes every row in `transactions`; their alerts and the feedback on those
alerts go with them (ON DELETE CASCADE). `model_runs` is kept. Uses the service
role key from `.env`, so this only works server-side, never from the dashboard.
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
TABLES = ("transactions", "alerts", "feedback")
EVERYTHING = "1970-01-01"  # PostgREST refuses an unfiltered delete; every row is newer


def counts(client) -> dict[str, int]:
    return {table: client.table(table).select("id", count="exact", head=True).execute().count
            for table in TABLES}


def delete_all(client) -> None:
    client.table("transactions").delete().gte("created_at", EVERYTHING).execute()


def service_client():
    from supabase import create_client

    load_dotenv(ROOT / ".env", override=False)
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(url, key)


def _summary(c: dict[str, int]) -> str:
    return ", ".join(f"{n} {table}" for table, n in c.items())


def main(argv: list[str] | None = None, client=None, ask=input) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="delete without asking")
    args = parser.parse_args(argv)

    client = client or service_client()
    before = counts(client)
    if not any(before.values()):
        print("Nothing to delete: transactions, alerts and feedback are already empty.")
        return 0
    print(f"This deletes {_summary(before)}. model_runs is kept.")
    if not args.yes and ask('Type "yes" to delete: ').strip().lower() != "yes":
        print("Cancelled, nothing deleted.")
        return 1
    delete_all(client)
    print(f"Deleted. Now: {_summary(counts(client))}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
