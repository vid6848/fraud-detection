"""SHAP explanations for the fraud model.

SHAP explains the *uncalibrated* base pipeline (fitted on the full training
split). Calibration is a monotonic squash of its score, so the features that
push a transaction towards "fraud" are the same; and tree SHAP needs direct
access to the trees, which the calibration wrapper hides.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from ml.models import final_estimator, transform_features  # noqa: E402


def make_explainer(base_pipe, background: pd.DataFrame):
    """SHAP explainer for a fitted pipeline. `background` holds raw training rows."""
    model = final_estimator(base_pipe)
    if isinstance(model, LogisticRegression):
        return shap.LinearExplainer(model, transform_features(base_pipe, background))
    return shap.TreeExplainer(model)


def shap_values(explainer, base_pipe, X: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """SHAP values for the fraud class, plus the transformed features they refer to."""
    Xt = transform_features(base_pipe, X)
    values = explainer.shap_values(Xt)
    if isinstance(values, list):  # older SHAP: one array per class
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:  # (rows, features, classes)
        values = values[:, :, 1]
    return values, Xt


def shap_ranking(values: np.ndarray, feature_names: list[str]) -> pd.Series:
    """Features ranked by mean |SHAP value| (global importance)."""
    return pd.Series(np.abs(values).mean(axis=0), index=feature_names).sort_values(
        ascending=False
    )


def plot_shap_summary(values: np.ndarray, Xt: pd.DataFrame, path: Path, max_display: int = 15):
    """Beeswarm plot: each dot is one transaction, colour is the feature value."""
    shap.summary_plot(values, Xt, max_display=max_display, show=False, plot_size=(9, 7))
    fig = plt.gcf()
    fig.suptitle("SHAP summary (validation sample): what pushes a score towards fraud")
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def plot_shap_importance(ranking: pd.Series, path: Path, highlight: list[str], top: int = 15):
    """Bar chart of mean |SHAP|, highlighting the features EDA expected on top."""
    data = ranking.head(top)[::-1]
    colors = ["#c0392b" if f in highlight else "#7f8c8d" for f in data.index]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(data.index, data.values, color=colors)
    ax.set_xlabel("mean |SHAP value| (impact on model output)")
    ax.set_title(f"Global feature importance (red = top EDA features {', '.join(highlight)})")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
