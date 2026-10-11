"""Per-transaction SHAP explanations in plain words.

SHAP runs on `model.base` (the uncalibrated forest; see ml/explain.py). Model
features are grouped back into the inputs a person sent:
- V1-V28 stay as they are,
- log_amount -> Amount,
- hour_sin + hour_cos -> time_of_day (SHAP values add up, so summing them is exact).

"Typical" compares the input with the training data using the pipeline's fitted
StandardScaler: the scaled feature is a z-score (how many standard deviations
away from the training average).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from api.model_store import ModelStore
from ml.explain import shap_values
from ml.features import V_COLUMNS, hour_of_day

TOP_K = 5


@dataclass(frozen=True)
class Contribution:
    feature: str
    value: float
    shap_value: float
    direction: str
    description: str


def explain_row(store: ModelStore, raw: pd.DataFrame) -> tuple[float, float, list[Contribution]]:
    """(model_score, base_value, top-K contributions) for a one-row raw frame."""
    values, Xt = shap_values(store.explainer, store.model.base, raw)
    shap_row = pd.Series(values[0], index=Xt.columns)
    z = Xt.iloc[0]
    row = raw.iloc[0]
    base_value = float(np.atleast_1d(store.explainer.expected_value)[-1])

    grouped = [(v, float(row[v]), float(shap_row[v]), float(z[v])) for v in V_COLUMNS]
    grouped.append(("Amount", float(row["Amount"]), float(shap_row["log_amount"]),
                    float(z["log_amount"])))
    grouped.append(("time_of_day", float(hour_of_day(row["Time"])),
                    float(shap_row["hour_sin"] + shap_row["hour_cos"]), None))

    top = sorted(grouped, key=lambda g: abs(g[2]), reverse=True)[:TOP_K]
    contributions = [
        Contribution(feature=f, value=value, shap_value=s,
                     direction="raises_risk" if s > 0 else "lowers_risk",
                     description=describe(f, value, s, zscore))
        for f, value, s, zscore in top
    ]
    return base_value + float(shap_row.sum()), base_value, contributions


def describe(feature: str, value: float, shap_value: float, zscore: float | None) -> str:
    """e.g. 'V14 = -4.80 (much lower than typical) pushed fraud risk up'."""
    if feature == "time_of_day":
        hours, minutes = divmod(int(round(value * 60)) % (24 * 60), 60)
        subject = f"Time of day {hours:02d}:{minutes:02d}"
    elif feature == "Amount":
        subject = f"Amount ${value:,.2f} ({typical(zscore)})"
    else:
        subject = f"{feature} = {value:.2f} ({typical(zscore)})"
    return f"{subject} pushed fraud risk {'up' if shap_value > 0 else 'down'}"


def typical(zscore: float) -> str:
    size = abs(zscore)
    if size < 1:
        return "close to typical"
    side = "higher" if zscore > 0 else "lower"
    return f"much {side} than typical" if size >= 2 else f"{side} than typical"
