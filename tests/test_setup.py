"""Sanity checks that the Kaggle dataset is present and complete."""
from pathlib import Path

import pandas as pd
import pytest

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "creditcard.csv"

# The dataset is gitignored, so CI never has it: skip the whole module there.
pytestmark = pytest.mark.skipif(
    not DATA_PATH.exists(), reason=f"Dataset not found at {DATA_PATH} (download it from Kaggle)"
)


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


def test_dataset_exists():
    assert DATA_PATH.exists(), f"Missing {DATA_PATH}"


def test_row_count(df):
    assert len(df) == 284_807


def test_fraud_count(df):
    assert int(df["Class"].sum()) == 492


def test_expected_columns(df):
    expected = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class"]
    assert list(df.columns) == expected
