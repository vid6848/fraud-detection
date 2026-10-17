"""Load the trained model's Phase 2 results from metadata.json into `model_runs`.

    python scripts/load_model_runs.py             # upsert ml/artifacts/metadata.json
    python scripts/load_model_runs.py --dry-run   # print the row, write nothing

Idempotent: the row is keyed on `version`, so running it again updates that row
instead of adding a duplicate. Uses the service role key from `.env` (writes to
`model_runs` are server-side only; analysts can only read them).
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_METADATA = ROOT / "ml" / "artifacts" / "metadata.json"

# metadata.json keys copied into model_runs.metrics (everything the dashboard's
# model comparison page needs; library versions and timings stay in the file).
METRIC_KEYS = (
    "model", "threshold", "threshold_90_precision", "threshold_selection",
    "review_cost_per_alert", "calibration", "validation_metrics", "test_metrics",
    "model_comparison_best_per_model", "split",
)


def model_run_row(metadata: dict) -> dict:
    missing = [k for k in ("model_version", "trained_at", *METRIC_KEYS) if k not in metadata]
    if missing:
        raise ValueError(f"metadata.json is missing {', '.join(missing)}")
    return {
        "version": metadata["model_version"],
        "trained_at": metadata["trained_at"],
        "metrics": {k: metadata[k] for k in METRIC_KEYS},
    }


def upsert(client, row: dict) -> None:
    client.table("model_runs").upsert(row, on_conflict="version").execute()


def service_client():
    from supabase import create_client

    load_dotenv(ROOT / ".env", override=False)
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(url, key)


def main(argv: list[str] | None = None, client=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--dry-run", action="store_true", help="print the row, write nothing")
    args = parser.parse_args(argv)

    row = model_run_row(json.loads(args.metadata.read_text()))
    if args.dry_run:
        print(json.dumps(row, indent=2))
        return row
    upsert(client or service_client(), row)
    test = row["metrics"]["test_metrics"]
    print(f"model_runs: upserted version {row['version']} (trained {row['trained_at']}; "
          f"test PR-AUC {test['pr_auc']:.3f}, precision {test['precision']:.3f}, "
          f"recall {test['recall']:.3f})")
    return row


if __name__ == "__main__":
    main()
