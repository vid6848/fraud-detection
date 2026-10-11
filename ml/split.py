"""Time-based train / validation / test split.

Rows are ordered by `Time` and cut at fixed boundaries, so the model is always
trained on the past and evaluated on the future (never a random split).
"""
import pandas as pd

from ml.config import SPLIT_BOUNDARIES, TARGET


def time_split(
    df: pd.DataFrame, boundaries: tuple[float, float] = SPLIT_BOUNDARIES
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split into (train, validation, test) by `Time`.

    train: Time < boundaries[0]; validation: boundaries[0] <= Time < boundaries[1];
    test: Time >= boundaries[1]. Rows sharing a timestamp always land together.
    """
    val_start, test_start = boundaries
    if not val_start < test_start:
        raise ValueError("boundaries must be increasing")
    ordered = df.sort_values("Time", kind="stable")
    train = ordered[ordered["Time"] < val_start]
    val = ordered[(ordered["Time"] >= val_start) & (ordered["Time"] < test_start)]
    test = ordered[ordered["Time"] >= test_start]
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError("a split is empty; check the boundaries")
    return train, val, test


def split_summary(
    train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, target: str = TARGET
) -> dict:
    """Rows, frauds, fraud rate and time range of each split (JSON-friendly)."""
    out = {}
    for name, part in (("train", train), ("validation", val), ("test", test)):
        out[name] = {
            "rows": len(part),
            "frauds": int(part[target].sum()),
            "fraud_pct": round(float(part[target].mean() * 100), 4),
            "start_time": float(part["Time"].min()),
            "end_time": float(part["Time"].max()),
        }
    return out
