"""Probability calibration that keeps the full-train model.

`CalibratedClassifierCV(cv=TimeSeriesSplit)` would ship an *average of fold
models*, each trained on only part of train (20%, 40%, ...). Instead we:

 1. walk forward through train with `TimeSeriesSplit`: fit a model on each past
    prefix and score the next chunk, giving out-of-fold (OOF) scores that were
    never seen by the model that produced them;
 2. fit a 1-D calibrator (isotonic or sigmoid) on those OOF scores;
 3. apply that calibrator on top of the base model fitted on the *full* train split.

The served model is therefore exactly `base` followed by a monotonic map, so SHAP
on `model.base` explains the same model that produces the score.
"""
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit

from ml.models import build_pipeline

METHODS = ("sigmoid", "isotonic")


def oof_scores(model: str, strategy: str, params: dict, X: pd.DataFrame, y: pd.Series,
               folds: int) -> tuple[np.ndarray, np.ndarray]:
    """Walk-forward out-of-fold fraud scores on time-ordered training rows.

    Returns (positions, scores): row positions that received a score (everything
    after the first chunk) and the score from a model fitted only on earlier rows.
    """
    positions, scores = [], []
    for past, future in TimeSeriesSplit(n_splits=folds).split(X):
        y_past = y.iloc[past]
        pipe = build_pipeline(model, strategy, params, y_past).fit(X.iloc[past], y_past)
        positions.append(future)
        scores.append(pipe.predict_proba(X.iloc[future])[:, 1])
    return np.concatenate(positions), np.concatenate(scores)


def fit_calibrator(method: str, scores: np.ndarray, y) -> object:
    """Fit a monotonic score -> probability map."""
    y = np.asarray(y)
    if method == "isotonic":
        return IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(scores, y)
    if method == "sigmoid":  # Platt scaling on the score
        return LogisticRegression(C=1e6, max_iter=1000).fit(scores.reshape(-1, 1), y)
    raise ValueError(f"unknown calibration method: {method}")


class CalibratedModel:
    """A fitted base pipeline plus a 1-D calibrator. Takes raw transaction columns."""

    def __init__(self, base, calibrator, method: str):
        self.base = base
        self.calibrator = calibrator
        self.method = method
        self.classes_ = base.classes_

    def calibrate_scores(self, scores: np.ndarray) -> np.ndarray:
        if self.method == "isotonic":
            p = self.calibrator.predict(scores)
        else:
            p = self.calibrator.predict_proba(np.asarray(scores).reshape(-1, 1))[:, 1]
        return np.clip(p, 0.0, 1.0)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        p = self.calibrate_scores(self.base.predict_proba(X)[:, 1])
        return np.column_stack([1 - p, p])

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)
