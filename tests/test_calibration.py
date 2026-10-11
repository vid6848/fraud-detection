"""Tests for ml/calibration.py: walk-forward OOF scores and the CalibratedModel wrapper."""
import numpy as np
import pytest
from imblearn.pipeline import Pipeline

from ml import calibration, config
from ml.calibration import CalibratedModel, fit_calibrator, oof_scores
from ml.models import build_pipeline
from ml.split import time_split
from tests.synthetic import make_transactions

PARAMS = {"C": 0.1}


@pytest.fixture(scope="module")
def data():
    train, val, _ = time_split(make_transactions(4_000, fraud_rate=0.04), (100_000, 140_000))
    return (train[config.RAW_COLUMNS], train[config.TARGET],
            val[config.RAW_COLUMNS], val[config.TARGET])


def test_oof_scores_only_use_past_rows(data, monkeypatch):
    X, y, _, _ = data
    fits = []
    real_fit = Pipeline.fit

    def spy(self, X_fit, y_fit=None, **kw):
        fits.append(X_fit.index.copy())
        return real_fit(self, X_fit, y_fit, **kw)

    monkeypatch.setattr(Pipeline, "fit", spy)
    pos, scores = oof_scores("logistic_regression", "none", PARAMS, X, y, folds=3)
    assert len(fits) == 3
    assert len(np.unique(pos)) == len(pos)  # each row scored at most once
    times = X["Time"].to_numpy()
    for fitted_idx in fits:
        assert fitted_idx.equals(X.index[: len(fitted_idx)])  # a prefix of time-ordered train
    # every scored row comes after the rows of the model that scored it
    assert times[pos].min() >= times[: len(fits[0])].max()
    assert np.all((scores >= 0) & (scores <= 1))


@pytest.mark.parametrize("method", calibration.METHODS)
def test_calibrated_model_wraps_full_train_base(data, method):
    X, y, X_val, _ = data
    base = build_pipeline("logistic_regression", "none", PARAMS, y).fit(X, y)
    pos, scores = oof_scores("logistic_regression", "none", PARAMS, X, y, folds=3)
    model = CalibratedModel(base, fit_calibrator(method, scores, y.iloc[pos]), method)
    proba = model.predict_proba(X_val)
    assert proba.shape == (len(X_val), 2)
    assert np.all((proba >= 0) & (proba <= 1)) and np.allclose(proba.sum(axis=1), 1)
    raw = base.predict_proba(X_val)[:, 1]
    order = np.argsort(raw)
    assert np.all(np.diff(proba[order, 1]) >= -1e-12)  # monotonic in the base score
    assert model.base is base


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        fit_calibrator("beta", np.array([0.1, 0.9]), np.array([0, 1]))
