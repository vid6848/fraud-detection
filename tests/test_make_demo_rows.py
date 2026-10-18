"""scripts/make_demo_rows.py: the demo slice is test-split rows with no labels."""
import sys

import pandas as pd

from api.demo import load_demo_rows
from ml.config import RAW_COLUMNS, ROOT
from simulator.data import load_stream
from tests.synthetic import make_transactions

sys.path.insert(0, str(ROOT / "scripts"))
import make_demo_rows  # noqa: E402

DF = make_transactions()


def test_writes_the_requested_test_rows_without_labels(tmp_path):
    output = tmp_path / "rows.csv.gz"
    frauds = make_demo_rows.write_rows(offset=5, limit=20, output=output, df=DF)
    written = pd.read_csv(output)
    assert list(written.columns) == RAW_COLUMNS  # no Class
    expected = load_stream(DF, offset=5, limit=20)
    assert frauds == sum(expected.labels)
    assert load_demo_rows(output) == expected.payloads


def test_output_is_byte_for_byte_reproducible(tmp_path):
    output = tmp_path / "rows.csv.gz"
    make_demo_rows.write_rows(0, 10, output=output, df=DF)
    first = output.read_bytes()
    make_demo_rows.write_rows(0, 10, output=output, df=DF)
    assert output.read_bytes() == first  # gzip mtime fixed: re-running adds no git noise
