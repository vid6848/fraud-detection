"""Model zoo, imbalance strategies and hyperparameter grids.

Every candidate is an imblearn `Pipeline`:

    raw columns -> features + scaler -> [SMOTE | undersampler] -> classifier

imblearn only runs samplers during `fit`; at `predict_proba` time they are
skipped. So resampling only ever touches the data the pipeline is fitted on
(the training split), never validation or test rows.
"""
from itertools import product

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from ml.config import RANDOM_SEED, RESAMPLE_RATIO
from ml.features import preprocessing_steps

MODELS = ["logistic_regression", "decision_tree", "random_forest", "xgboost"]
STRATEGIES = ["none", "class_weight", "smote", "undersample"]

MODEL_LABELS = {
    "logistic_regression": "Logistic Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}
STRATEGY_LABELS = {
    "none": "No handling",
    "class_weight": "Class weights",
    "smote": "SMOTE",
    "undersample": "Random undersampling",
}

# Small, sensible grids (same grid for every imbalance strategy).
GRIDS: dict[str, dict[str, list]] = {
    "logistic_regression": {"C": [0.01, 0.1, 1.0]},
    "decision_tree": {"max_depth": [4, 6, 8]},
    "random_forest": {"max_depth": [8, 16]},
    "xgboost": {"max_depth": [3, 6], "learning_rate": [0.05, 0.1]},
}

# Tiny grids for `--quick` runs and tests.
QUICK_GRIDS: dict[str, dict[str, list]] = {
    "logistic_regression": {"C": [0.1]},
    "decision_tree": {"max_depth": [4]},
    "random_forest": {"max_depth": [8], "n_estimators": [50]},
    "xgboost": {"max_depth": [3], "learning_rate": [0.1], "n_estimators": [100]},
}


def expand_grid(grid: dict[str, list]) -> list[dict]:
    """All combinations of a parameter grid, as a list of dicts."""
    keys = list(grid)
    return [dict(zip(keys, values)) for values in product(*(grid[k] for k in keys))]


def make_estimator(model: str, strategy: str, params: dict, y_train: pd.Series):
    """Build an unfitted classifier, with class weights if the strategy asks for them."""
    weighted = strategy == "class_weight"
    if model == "logistic_regression":
        return LogisticRegression(
            max_iter=2000,
            class_weight="balanced" if weighted else None,
            random_state=RANDOM_SEED,
            **params,
        )
    if model == "decision_tree":
        defaults = {"min_samples_leaf": 20}
        return DecisionTreeClassifier(
            class_weight="balanced" if weighted else None,
            random_state=RANDOM_SEED,
            **{**defaults, **params},
        )
    if model == "random_forest":
        defaults = {"n_estimators": 200, "min_samples_leaf": 5, "max_features": "sqrt"}
        return RandomForestClassifier(
            class_weight="balanced_subsample" if weighted else None,
            n_jobs=-1,
            random_state=RANDOM_SEED,
            **{**defaults, **params},
        )
    if model == "xgboost":
        defaults = {"n_estimators": 300, "subsample": 0.8, "colsample_bytree": 0.8}
        y = np.asarray(y_train)
        scale = float((y == 0).sum() / max((y == 1).sum(), 1)) if weighted else 1.0
        return XGBClassifier(
            tree_method="hist",
            eval_metric="aucpr",
            scale_pos_weight=scale,
            n_jobs=-1,
            random_state=RANDOM_SEED,
            **{**defaults, **params},
        )
    raise ValueError(f"unknown model: {model}")


def make_sampler(strategy: str):
    """SMOTE / random undersampler for resampling strategies, else None."""
    if strategy == "smote":
        return SMOTE(sampling_strategy=RESAMPLE_RATIO, k_neighbors=5, random_state=RANDOM_SEED)
    if strategy == "undersample":
        return RandomUnderSampler(sampling_strategy=RESAMPLE_RATIO, random_state=RANDOM_SEED)
    if strategy in ("none", "class_weight"):
        return None
    raise ValueError(f"unknown strategy: {strategy}")


def build_pipeline(model: str, strategy: str, params: dict, y_train: pd.Series) -> Pipeline:
    """Full pipeline from raw columns to a fraud probability."""
    steps = preprocessing_steps()
    sampler = make_sampler(strategy)
    if sampler is not None:
        steps.append(("sampler", sampler))
    steps.append(("model", make_estimator(model, strategy, params, y_train)))
    return Pipeline(steps)


def transform_features(pipe: Pipeline, X: pd.DataFrame) -> pd.DataFrame:
    """Apply a fitted pipeline's preprocessing (skipping samplers) to raw rows."""
    for _, step in pipe.steps[:-1]:
        if not hasattr(step, "fit_resample"):  # samplers only act during fit
            X = step.transform(X)
    return X


def final_estimator(pipe: Pipeline):
    """The classifier at the end of a pipeline."""
    return pipe.named_steps["model"]
