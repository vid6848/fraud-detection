"""The rows to replay: the held-out test split, in time order.

The split itself comes from `ml.split.time_split`, the same function training
used, so the simulator can only ever send data the model never saw.

Labels (`Class`) are split off here and stay inside the simulator: payloads
contain exactly the API's input columns, nothing else.
"""
from dataclasses import dataclass

import pandas as pd

from ml.config import RAW_COLUMNS, TARGET
from ml.eda_utils import load_data
from ml.split import time_split


@dataclass(frozen=True)
class Stream:
    payloads: list[dict]  # what gets sent: Time, V1-V28, Amount
    labels: list[int]     # local only, for the run summary (1 = fraud)
    times: list[float]    # dataset `Time`, used by replay mode

    def __len__(self) -> int:
        return len(self.payloads)


def load_stream(df: pd.DataFrame | None = None, offset: int = 0,
                limit: int | None = None) -> Stream:
    """Test-split rows `offset` .. `offset + limit`, oldest first.

    `df` defaults to data/creditcard.csv; tests pass a synthetic frame instead.
    """
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1")
    _, _, test = time_split(load_data() if df is None else df)  # already sorted by Time
    end = None if limit is None else offset + limit
    rows = test.iloc[offset:end]
    if rows.empty:
        raise ValueError(f"offset {offset} is past the end of the test split ({len(test)} rows)")
    payloads = [{c: float(v) for c, v in row.items()}
                for row in rows[RAW_COLUMNS].to_dict("records")]
    return Stream(payloads=payloads, labels=rows[TARGET].astype(int).tolist(),
                  times=rows["Time"].astype(float).tolist())
