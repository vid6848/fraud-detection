"""Scores raw transaction rows with the loaded model.

No feature logic lives here: the saved pipeline runs `ml.features.build_features`
itself, exactly as in training.
"""
from dataclasses import dataclass

import pandas as pd

from api.model_store import ModelStore
from api.risk import Reason, RiskLevel, assess_frame


@dataclass(frozen=True)
class Score:
    probability: float
    risk_level: RiskLevel
    reasons: list[Reason]


def score_frame(store: ModelStore, df: pd.DataFrame) -> list[Score]:
    probabilities = store.model.predict_proba(df)[:, 1]
    assessed = assess_frame(probabilities, df, store.medium_threshold, store.high_threshold)
    return [Score(float(p), level, reasons)
            for p, (level, reasons) in zip(probabilities, assessed)]
