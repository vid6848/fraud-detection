"""Tests for ml/features.py."""
import numpy as np
import pandas as pd
import pytest

from ml.features import FEATURE_COLUMNS, build_features, hour_of_day, make_preprocessor
from ml.split import time_split
from tests.synthetic import make_transactions


def _rows(times, amounts=None) -> pd.DataFrame:
    n = len(times)
    df = pd.DataFrame({"Time": times, **{f"V{i}": np.zeros(n) for i in range(1, 29)}})
    df["Amount"] = amounts if amounts is not None else np.zeros(n)
    return df


def test_hour_is_encoded_on_a_circle():
    out = build_features(_rows([0, 6 * 3600, 12 * 3600, 18 * 3600, 86_400, 86_400 + 6 * 3600]))
    assert out["hour_sin"].to_numpy() == pytest.approx([0, 1, 0, -1, 0, 1], abs=1e-12)
    assert out["hour_cos"].to_numpy() == pytest.approx([1, 0, -1, 0, 1, 0], abs=1e-12)


def test_hour_of_day_wraps_each_day():
    assert hour_of_day([0, 3600, 7.5 * 3600, 86_400 + 3600, 172_799]) == pytest.approx(
        [0, 1, 7.5, 1, 24 - 1 / 3600]
    )


def test_midnight_neighbours_are_close():
    out = build_features(_rows([86_400 - 60, 86_400 + 60]))
    a, b = out[["hour_sin", "hour_cos"]].to_numpy()
    assert np.linalg.norm(a - b) < 0.01


def test_log_amount():
    amounts = np.array([0.0, 1.0, 9.25, 2125.87])
    out = build_features(_rows([0, 1, 2, 3], amounts))
    assert out["log_amount"].to_numpy() == pytest.approx(np.log1p(amounts))


def test_raw_time_and_amount_dropped_and_column_order_fixed():
    out = build_features(make_transactions(50))
    assert list(out.columns) == FEATURE_COLUMNS
    assert "Time" not in out.columns and "Amount" not in out.columns
    assert "Class" not in out.columns


def test_input_is_not_modified():
    df = make_transactions(20)
    before = df.copy()
    build_features(df)
    pd.testing.assert_frame_equal(df, before)


def test_scaler_is_fitted_on_train_only():
    df = make_transactions(3_000)
    train, val, _ = time_split(df, boundaries=(100_000, 140_000))
    pre = make_preprocessor().fit(train)
    scaler = pre.named_steps["scaler"]
    assert scaler.mean_ == pytest.approx(build_features(train).mean().to_numpy())
    # Different from what a scaler fitted on all rows would learn.
    assert not np.allclose(scaler.mean_, build_features(df).mean().to_numpy())
    # Train features come out standardised; validation is only transformed.
    scaled = pre.transform(train)
    assert scaled.mean().to_numpy() == pytest.approx(0, abs=1e-9)
    assert list(pre.transform(val).columns) == FEATURE_COLUMNS
