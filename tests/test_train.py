"""End-to-end test of ml/train.py on synthetic data, plus a check of the real saved model."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from ml import config
from ml.models import QUICK_GRIDS
from ml.train import run
from tests.synthetic import make_transactions

ARTIFACT_FILES = ["model.joblib", "base_model.joblib", "metadata.json", "model_comparison.csv", "pr_curves.json"]
FIGURE_FILES = [
    "pr_curves_validation.png",
    "pr_curve_test.png",
    "confusion_matrix_test.png",
    "calibration_curve.png",
    "cost_vs_threshold.png",
    "shap_summary.png",
    "shap_importance.png",
]


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    df = make_transactions(6_000, fraud_rate=0.03)
    grids = {"logistic_regression": QUICK_GRIDS["logistic_regression"],
             "xgboost": {"max_depth": [3], "n_estimators": [30]}}
    metadata = run(df, grids=grids, artifacts_dir=out / "artifacts", figures_dir=out / "figures",
                   n_bootstrap=50, boundaries=(100_000, 140_000), calibration_folds=3,
                   shap_normal_rows=300)
    return out, df, metadata


def test_all_outputs_written(trained):
    out, _, _ = trained
    for name in ARTIFACT_FILES:
        assert (out / "artifacts" / name).exists(), name
    for name in FIGURE_FILES:
        assert (out / "figures" / name).exists(), name


def test_metadata_contents(trained):
    out, _, metadata = trained
    saved = json.loads((out / "artifacts" / "metadata.json").read_text())
    for key in ("model_version", "trained_at", "input_columns", "features", "model", "threshold",
                "threshold_90_precision", "calibration", "validation_metrics", "test_metrics", "shap"):
        assert key in saved, key
    assert saved["input_columns"] == config.RAW_COLUMNS
    assert 0 <= saved["threshold"] <= 1
    assert set(saved["test_metrics"]["ci95"]) >= {"pr_auc", "recall", "cost_saved"}
    assert saved["model"]["name"] in ("logistic_regression", "xgboost")


def test_comparison_table(trained):
    out, _, _ = trained
    table = pd.read_csv(out / "artifacts" / "model_comparison.csv")
    assert len(table) == 2 * 4  # 2 models x 4 strategies x 1 config
    assert table["val_pr_auc"].is_monotonic_decreasing
    assert table["best_in_combo"].all()


def test_saved_model_loads_and_predicts_probabilities(trained):
    out, df, _ = trained
    model = joblib.load(out / "artifacts" / "model.joblib")
    proba = model.predict_proba(df[config.RAW_COLUMNS].head(100))
    assert proba.shape == (100, 2)
    assert np.all((proba >= 0) & (proba <= 1))
    assert np.allclose(proba.sum(axis=1), 1)


REAL_MODEL = config.ARTIFACTS_DIR / "model.joblib"


@pytest.mark.skipif(not (REAL_MODEL.exists() and config.DATA_PATH.exists()),
                    reason="run `python -m ml.train` first (needs the dataset)")
def test_real_saved_model_predicts_probabilities():
    model = joblib.load(REAL_MODEL)
    metadata = json.loads((config.ARTIFACTS_DIR / "metadata.json").read_text())
    rows = pd.read_csv(config.DATA_PATH, nrows=500)
    proba = model.predict_proba(rows[metadata["input_columns"]])[:, 1]
    assert proba.shape == (500,)
    assert np.all((proba >= 0) & (proba <= 1))
