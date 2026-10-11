"""Tests for ml/split.py."""
import pandas as pd
import pytest

from ml.config import DATA_PATH, SPLIT_BOUNDARIES
from ml.eda_utils import time_split_boundaries
from ml.split import split_summary, time_split
from tests.synthetic import make_transactions

BOUNDS = (100_000, 140_000)


@pytest.fixture
def parts():
    df = make_transactions(4_000).sample(frac=1, random_state=1)  # shuffled input
    return df, time_split(df, BOUNDS)


def test_splits_do_not_overlap_and_cover_everything(parts):
    df, (train, val, test) = parts
    idx = [set(p.index) for p in (train, val, test)]
    assert not (idx[0] & idx[1]) and not (idx[0] & idx[2]) and not (idx[1] & idx[2])
    assert len(train) + len(val) + len(test) == len(df)


def test_splits_are_time_ordered(parts):
    _, (train, val, test) = parts
    assert train["Time"].max() < val["Time"].min() <= val["Time"].max() < test["Time"].min()
    assert train["Time"].max() < BOUNDS[0] <= val["Time"].min()
    assert val["Time"].max() < BOUNDS[1] <= test["Time"].min()
    for part in (train, val, test):
        assert part["Time"].is_monotonic_increasing


def test_equal_timestamps_stay_together():
    df = pd.DataFrame({"Time": [1, 5, 5, 5, 9, 9, 12], "Class": [0, 0, 1, 0, 0, 1, 0]})
    train, val, test = time_split(df, (5, 9))
    assert list(train["Time"]) == [1]
    assert list(val["Time"]) == [5, 5, 5]
    assert list(test["Time"]) == [9, 9, 12]


def test_bad_boundaries_raise():
    df = make_transactions(100)
    with pytest.raises(ValueError):
        time_split(df, (140_000, 100_000))
    with pytest.raises(ValueError):
        time_split(df, (500_000, 600_000))  # validation and test would be empty


def test_split_summary(parts):
    df, (train, val, test) = parts
    summary = split_summary(train, val, test)
    assert sum(s["rows"] for s in summary.values()) == len(df)
    assert sum(s["frauds"] for s in summary.values()) == df["Class"].sum()


@pytest.mark.skipif(not DATA_PATH.exists(), reason="dataset not downloaded")
def test_real_split_matches_eda_boundaries():
    df = pd.read_csv(DATA_PATH)
    train, val, test = time_split(df)
    eda = time_split_boundaries(df)
    assert (eda.loc["validation", "start_time"], eda.loc["test", "start_time"]) == SPLIT_BOUNDARIES
    assert [len(p) for p in (train, val, test)] == eda["rows"].tolist()
    assert [int(p["Class"].sum()) for p in (train, val, test)] == [384, 56, 52]
