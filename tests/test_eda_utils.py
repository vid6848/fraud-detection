"""Tests for ml/eda_utils.py using small synthetic data (no dataset needed)."""
import numpy as np
import pandas as pd
import pytest

from ml.eda_utils import (
    add_hour_of_day,
    class_balance,
    duplicate_summary,
    fraud_rate_by_hour,
    rank_features,
    time_split_boundaries,
)


@pytest.fixture
def toy() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 1_000
    cls = np.zeros(n, dtype=int)
    cls[::50] = 1  # 20 frauds, evenly spread in time
    return pd.DataFrame(
        {
            "Time": np.arange(n) * 180.0,  # one txn every 3 minutes (~50 hours)
            "signal": cls * 5 + rng.normal(size=n),  # separates fraud
            "noise": rng.normal(size=n),  # does not
            "Class": cls,
        }
    )


def test_duplicate_summary_counts_extra_copies_only():
    df = pd.DataFrame({"Time": [0, 0, 0, 1, 1], "Class": [0, 0, 0, 1, 1]})
    out = duplicate_summary(df)
    assert out["duplicate_rows"] == 3
    assert out["duplicate_fraud_rows"] == 1
    assert out["duplicate_pct"] == pytest.approx(60.0)


def test_class_balance(toy):
    out = class_balance(toy)
    assert out.loc[1, "count"] == 20
    assert out.loc[0, "count"] == 980
    assert out["pct"].sum() == pytest.approx(100.0)


def test_add_hour_of_day_wraps_after_24h():
    df = pd.DataFrame({"Time": [0, 3599, 3600, 86_399, 86_400, 90_000]})
    out = add_hour_of_day(df)
    assert out["hour"].tolist() == [0, 0, 1, 23, 0, 1]
    assert "hour" not in df.columns  # original untouched


def test_fraud_rate_by_hour(toy):
    out = fraud_rate_by_hour(toy)
    assert out.index.min() == 0 and out.index.max() == 23
    assert out["transactions"].sum() == len(toy)
    assert out["frauds"].sum() == 20
    expected = out["frauds"] / out["transactions"] * 100
    assert np.allclose(out["fraud_rate_pct"], expected)


def test_rank_features_puts_signal_first(toy):
    out = rank_features(toy)
    assert out.index[0] == "signal"
    assert out.loc["signal", "std_mean_diff"] > out.loc["noise", "std_mean_diff"]
    assert set(out.columns) == {"std_mean_diff", "mutual_info"}


def test_time_split_is_ordered_and_complete(toy):
    shuffled = toy.sample(frac=1, random_state=1)
    out = time_split_boundaries(shuffled)
    assert out["rows"].tolist() == [700, 150, 150]
    assert out["frauds"].sum() == 20
    assert out.loc["train", "end_time"] < out.loc["validation", "start_time"]
    assert out.loc["validation", "end_time"] < out.loc["test", "start_time"]


def test_time_split_keeps_equal_timestamps_together():
    # 10 rows; rows 6-8 share Time=6, so a 70% cut (row 7) must move back to row 6.
    df = pd.DataFrame({"Time": [0, 1, 2, 3, 4, 5, 6, 6, 6, 9], "Class": [0] * 9 + [1]})
    out = time_split_boundaries(df, fractions=(0.7, 0.2, 0.1))
    assert out["rows"].tolist() == [6, 3, 1]
    assert out.loc["train", "end_time"] < out.loc["validation", "start_time"]


@pytest.mark.parametrize("bad", [(0.5, 0.5, 0.5), (0.7, 0.3), (1.0, 0.0, 0.0)])
def test_time_split_rejects_bad_fractions(toy, bad):
    with pytest.raises(ValueError):
        time_split_boundaries(toy, fractions=bad)
