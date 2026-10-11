"""Synthetic transactions with the same columns as creditcard.csv (no dataset needed)."""
import numpy as np
import pandas as pd


def make_transactions(n: int = 6_000, fraud_rate: float = 0.03, seed: int = 0) -> pd.DataFrame:
    """Rows spread over ~2 days, with fraud shifted on V14/V17 so models can learn it."""
    rng = np.random.default_rng(seed)
    cls = (rng.random(n) < fraud_rate).astype(int)
    data = {"Time": np.sort(rng.uniform(0, 172_800, n)).round()}
    for i in range(1, 29):
        data[f"V{i}"] = rng.normal(size=n)
    data["V14"] -= cls * 3
    data["V17"] -= cls * 3
    data["Amount"] = rng.exponential(80, n).round(2)
    data["Class"] = cls
    return pd.DataFrame(data)
