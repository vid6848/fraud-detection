"""Small helper functions for exploratory data analysis of the credit card dataset.

Kept free of plotting so they are easy to test and can be reused in Phase 2.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "creditcard.csv"
TARGET = "Class"


def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load the Kaggle credit card CSV."""
    return pd.read_csv(path)


def duplicate_summary(df: pd.DataFrame, target: str = TARGET) -> dict:
    """Count fully duplicated rows (extra copies only, the first copy is not counted)."""
    dupes = df.duplicated(keep="first")
    return {
        "duplicate_rows": int(dupes.sum()),
        "duplicate_fraud_rows": int((dupes & (df[target] == 1)).sum()),
        "duplicate_pct": float(dupes.mean() * 100),
    }


def class_balance(df: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    """Count and percentage of each class."""
    counts = df[target].value_counts().sort_index()
    return pd.DataFrame({"count": counts, "pct": counts / counts.sum() * 100})


def add_hour_of_day(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with an `hour` column (0-23) derived from `Time` in seconds.

    `Time` counts seconds from the first transaction, so hour 0 is the hour the
    data starts, which is not necessarily midnight.
    """
    out = df.copy()
    out["hour"] = (out["Time"] // 3600 % 24).astype(int)
    return out


def fraud_rate_by_hour(df: pd.DataFrame, target: str = TARGET) -> pd.DataFrame:
    """Transactions, frauds, and fraud rate (%) for each hour of the day."""
    hours = df if "hour" in df.columns else add_hour_of_day(df)
    grouped = hours.groupby("hour")[target].agg(transactions="count", frauds="sum")
    grouped["fraud_rate_pct"] = grouped["frauds"] / grouped["transactions"] * 100
    return grouped


def rank_features(
    df: pd.DataFrame, target: str = TARGET, random_state: int = 42
) -> pd.DataFrame:
    """Rank features by how well they separate fraud from normal transactions.

    - `std_mean_diff`: |mean(fraud) - mean(normal)| / overall std (scale-free).
    - `mutual_info`: mutual information with the target (captures non-linear links).
    """
    features = df.drop(columns=[target])
    is_fraud = df[target] == 1
    std = features.std().replace(0, np.nan)
    mean_diff = (features[is_fraud].mean() - features[~is_fraud].mean()).abs() / std
    mi = mutual_info_classif(features, df[target], random_state=random_state)
    ranking = pd.DataFrame(
        {"std_mean_diff": mean_diff.fillna(0.0), "mutual_info": mi},
        index=features.columns,
    )
    return ranking.sort_values("mutual_info", ascending=False)


def time_split_boundaries(
    df: pd.DataFrame,
    fractions: tuple[float, float, float] = (0.70, 0.15, 0.15),
    target: str = TARGET,
) -> pd.DataFrame:
    """Split rows in time order into train/validation/test and summarise each part.

    Splits are by row count after sorting on `Time`, so later transactions always
    land in later splits (no peeking into the future).
    """
    if len(fractions) != 3 or not np.isclose(sum(fractions), 1.0):
        raise ValueError("fractions must be three numbers that sum to 1")
    if any(f <= 0 for f in fractions):
        raise ValueError("every fraction must be positive")

    ordered = df.sort_values("Time", kind="stable").reset_index(drop=True)
    n = len(ordered)
    times = ordered["Time"].to_numpy()

    def cut_at(fraction: float) -> int:
        # Move the cut back to the first row of its timestamp so rows sharing a
        # `Time` value never straddle two splits.
        idx = int(round(n * fraction))
        return int(np.searchsorted(times, times[idx], side="left")) if idx < n else n

    train_end = cut_at(fractions[0])
    val_end = cut_at(fractions[0] + fractions[1])
    cuts = {"train": (0, train_end), "validation": (train_end, val_end), "test": (val_end, n)}

    rows = []
    for name, (start, end) in cuts.items():
        part = ordered.iloc[start:end]
        rows.append(
            {
                "split": name,
                "start_time": float(part["Time"].min()),
                "end_time": float(part["Time"].max()),
                "rows": len(part),
                "frauds": int(part[target].sum()),
                "fraud_pct": float(part[target].mean() * 100),
            }
        )
    return pd.DataFrame(rows).set_index("split")
