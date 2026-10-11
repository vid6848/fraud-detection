"""Feature engineering for the fraud model.

- `hour_sin` / `hour_cos`: time of day on a circle, so 23:59 sits next to 00:00
  (EDA finding 5: fraud spikes at night).
- `log_amount`: `log1p(Amount)` tames the heavy right skew (EDA finding 4).
- Raw `Time` is dropped: it only says where a row sits in the 2-day window.

`build_features` is stateless. The scaler in `preprocessing_steps` is the only
fitted step, and because it sits inside the model pipeline it is fitted on
whatever data `fit` sees, i.e. the training split only.
"""
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

SECONDS_PER_DAY = 86_400
V_COLUMNS = [f"V{i}" for i in range(1, 29)]
FEATURE_COLUMNS = [*V_COLUMNS, "log_amount", "hour_sin", "hour_cos"]


def hour_of_day(time) -> np.ndarray:
    """Hour of day in [0, 24) from `Time` (seconds since the first transaction, ~midnight)."""
    return (np.asarray(time, dtype=float) % SECONDS_PER_DAY) / 3600.0


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Turn raw transaction columns (Time, V1-V28, Amount) into model features."""
    hours = hour_of_day(df["Time"])
    angle = 2 * np.pi * hours / 24.0
    out = df[V_COLUMNS].copy()
    out["log_amount"] = np.log1p(df["Amount"].to_numpy(dtype=float))
    out["hour_sin"] = np.sin(angle)
    out["hour_cos"] = np.cos(angle)
    return out[FEATURE_COLUMNS]


def preprocessing_steps() -> list[tuple[str, object]]:
    """Feature builder + StandardScaler, as pipeline steps (imblearn forbids nested pipelines)."""
    features = FunctionTransformer(build_features, feature_names_out=_feature_names)
    return [
        ("features", features.set_output(transform="pandas")),
        ("scaler", StandardScaler().set_output(transform="pandas")),
    ]


def make_preprocessor() -> Pipeline:
    """Feature builder followed by a StandardScaler (fitted on train only)."""
    return Pipeline(preprocessing_steps())


def _feature_names(transformer, input_features) -> np.ndarray:
    return np.asarray(FEATURE_COLUMNS, dtype=object)
