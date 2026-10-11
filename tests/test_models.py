"""Tests for ml/models.py — above all, that resampling never touches validation/test."""
import numpy as np
import pytest
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

from ml.config import RAW_COLUMNS
from ml.features import FEATURE_COLUMNS
from ml.models import (
    GRIDS,
    MODELS,
    STRATEGIES,
    build_pipeline,
    expand_grid,
    final_estimator,
    transform_features,
)
from ml.split import time_split
from tests.synthetic import make_transactions


@pytest.fixture(scope="module")
def splits():
    train, val, test = time_split(make_transactions(4_000, fraud_rate=0.05), (100_000, 140_000))
    return [(p[RAW_COLUMNS], p["Class"]) for p in (train, val, test)]


@pytest.mark.parametrize("sampler_cls,strategy", [(SMOTE, "smote"), (RandomUnderSampler, "undersample")])
def test_resampling_only_touches_training_rows(monkeypatch, splits, sampler_cls, strategy):
    (X_train, y_train), (X_val, _), (X_test, _) = splits
    calls = []
    original = sampler_cls.fit_resample

    def spy(self, X, y, **kwargs):
        calls.append(X.index.copy())
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(sampler_cls, "fit_resample", spy)

    pipe = build_pipeline("logistic_regression", strategy, {"C": 1.0}, y_train).fit(X_train, y_train)
    assert len(calls) == 1
    assert calls[0].equals(X_train.index)  # exactly the training rows, nothing else

    p_val = pipe.predict_proba(X_val)[:, 1]
    p_test = pipe.predict_proba(X_test)[:, 1]
    assert len(calls) == 1  # predicting never resamples
    assert len(p_val) == len(X_val) and len(p_test) == len(X_test)  # no rows added/removed


def test_smote_changes_training_class_ratio(splits):
    (X_train, y_train), _, _ = splits
    pipe = build_pipeline("logistic_regression", "smote", {"C": 1.0}, y_train)
    Xt = pipe[:2].fit_transform(X_train)
    _, y_res = pipe.named_steps["sampler"].fit_resample(Xt, y_train)
    assert (y_res == 1).sum() / (y_res == 0).sum() == pytest.approx(0.1, abs=0.01)


def test_class_weights_are_applied(splits):
    (_, y_train), _, _ = splits
    expected_spw = (y_train == 0).sum() / (y_train == 1).sum()
    for model in MODELS:
        params = expand_grid(GRIDS[model])[0]
        weighted = final_estimator(build_pipeline(model, "class_weight", params, y_train))
        plain = final_estimator(build_pipeline(model, "none", params, y_train))
        if model == "xgboost":
            assert weighted.get_params()["scale_pos_weight"] == pytest.approx(expected_spw)
            assert plain.get_params()["scale_pos_weight"] == 1.0
        else:
            assert weighted.class_weight in ("balanced", "balanced_subsample")
            assert plain.class_weight is None


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_every_strategy_has_the_right_steps(splits, strategy):
    (_, y_train), _, _ = splits
    names = [name for name, _ in build_pipeline("decision_tree", strategy, {}, y_train).steps]
    has_sampler = strategy in ("smote", "undersample")
    assert names == ["features", "scaler", *(["sampler"] if has_sampler else []), "model"]


def test_transform_features_skips_sampler(splits):
    (X_train, y_train), (X_val, _), _ = splits
    pipe = build_pipeline("logistic_regression", "smote", {"C": 1.0}, y_train).fit(X_train, y_train)
    Xt = transform_features(pipe, X_val)
    assert list(Xt.columns) == FEATURE_COLUMNS
    assert len(Xt) == len(X_val)


def test_expand_grid():
    assert expand_grid({"a": [1, 2], "b": ["x"]}) == [{"a": 1, "b": "x"}, {"a": 2, "b": "x"}]
    assert len(expand_grid(GRIDS["xgboost"])) == 4


def test_unknown_names_raise(splits):
    (_, y_train), _, _ = splits
    with pytest.raises(ValueError):
        build_pipeline("svm", "none", {}, y_train)
    with pytest.raises(ValueError):
        build_pipeline("xgboost", "magic", {}, y_train)


def test_probabilities_are_valid(splits):
    (X_train, y_train), (X_val, _), _ = splits
    for model in MODELS:
        params = expand_grid(GRIDS[model])[0]
        if model in ("random_forest", "xgboost"):
            params = {**params, "n_estimators": 20}
        pipe = build_pipeline(model, "none", params, y_train).fit(X_train, y_train)
        proba = pipe.predict_proba(X_val)
        assert proba.shape == (len(X_val), 2)
        assert np.all((proba >= 0) & (proba <= 1))
