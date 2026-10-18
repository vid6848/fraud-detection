"""Write the small slice of held-out test rows that POST /demo/stream replays.

    python scripts/make_demo_rows.py                # default fraud-rich window
    python scripts/make_demo_rows.py --offset 9700  # another window

The deployed API has no access to data/creditcard.csv, so it ships this slice
instead: `--limit` consecutive rows of the *test* split (via `simulator.data`,
which uses the same time split as training), input columns only. The `Class`
label is never written; the fraud count is only printed here.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from ml.config import RAW_COLUMNS  # noqa: E402
from simulator.data import load_stream  # noqa: E402

OUTPUT = ROOT / "api" / "assets" / "demo_rows.csv.gz"
# 200-row test windows with the most frauds (4) start between offsets 9619 and 9780;
# 9740 puts them 4-8 seconds into a 10 rows/s stream, so alerts show up quickly.
DEFAULT_OFFSET = 9740
DEFAULT_LIMIT = 200


def write_rows(offset: int, limit: int, output: Path = OUTPUT, df: pd.DataFrame | None = None) -> int:
    """Write the rows; returns how many of them are fraud (never stored)."""
    stream = load_stream(df, offset=offset, limit=limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(stream.payloads, columns=RAW_COLUMNS).to_csv(
        output, index=False, compression={"method": "gzip", "mtime": 0})
    return sum(stream.labels)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--offset", type=int, default=DEFAULT_OFFSET, help="test-split row to start at")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="number of rows")
    args = parser.parse_args(argv)
    frauds = write_rows(args.offset, args.limit)
    print(f"wrote {args.limit} rows ({frauds} fraud) to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
