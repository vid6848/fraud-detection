"""Evaluation charts for the training pipeline (saved as PNG, no display)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import precision_recall_curve  # noqa: E402


def plot_pr_curves(curves: dict[str, tuple], base_rate: float, title: str, path: Path):
    """PR curves. `curves` maps a label to (y_true, y_score, pr_auc)."""
    fig, ax = plt.subplots(figsize=(7, 6))
    for label, (y, p, ap) in curves.items():
        precision, recall, _ = precision_recall_curve(y, p)
        ax.step(recall, precision, where="post", label=f"{label} (PR-AUC {ap:.3f})")
    ax.axhline(base_rate, color="grey", ls="--", lw=1, label=f"No skill ({base_rate:.2%})")
    ax.axhline(0.9, color="grey", ls=":", lw=1, label="90% precision")
    ax.set(xlabel="Recall (share of frauds caught)", ylabel="Precision (share of alerts that are fraud)",
           xlim=(0, 1), ylim=(0, 1.02), title=title)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_confusion_matrix(cm: dict, title: str, path: Path):
    """2x2 confusion matrix from a {'tn','fp','fn','tp'} dict."""
    grid = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.imshow(np.log1p(grid), cmap="Blues")
    for (i, j), v in np.ndenumerate(grid):
        ax.text(j, i, f"{v:,}", ha="center", va="center", fontsize=14,
                color="white" if np.log1p(v) > np.log1p(grid).max() / 2 else "black")
    ax.set_xticks([0, 1], ["Predicted normal", "Predicted fraud"])
    ax.set_yticks([0, 1], ["Actual normal", "Actual fraud"])
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_calibration(y, probs: dict[str, np.ndarray], path: Path, n_bins: int = 10):
    """Reliability diagram: predicted probability vs. observed fraud rate.

    Equal-width bins; each point is labelled with how many transactions it holds
    (almost all of them sit in the first bin, so upper bins are small and noisy).
    """
    y = np.asarray(y)
    edges = np.linspace(0, 1, n_bins + 1)
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.plot([0, 1], [0, 1], color="grey", ls="--", lw=1, label="Perfectly calibrated")
    for label, p in probs.items():
        bins = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
        xs, ys, ns = [], [], []
        for b in range(n_bins):
            mask = bins == b
            if mask.any():
                xs.append(p[mask].mean()); ys.append(y[mask].mean()); ns.append(int(mask.sum()))
        line, = ax.plot(xs, ys, marker="o", label=label)
        for x_, y_, n_ in zip(xs, ys, ns):
            ax.annotate(f"n={n_:,}", (x_, y_), textcoords="offset points", xytext=(4, -10),
                        fontsize=7, color=line.get_color())
    ax.set(xlim=(0, 1), ylim=(0, 1.02), xlabel="Mean predicted fraud probability (bin)",
           ylabel="Observed fraud rate (bin)", title="Calibration on validation (10 equal-width bins)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_cost_curve(thresholds, costs, chosen: float, review_cost: float, path: Path):
    """Business cost vs. threshold on validation, with the chosen threshold marked."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(thresholds, costs, lw=1.5)
    ax.axvline(chosen, color="#c0392b", ls="--", label=f"Chosen threshold {chosen:.3f}")
    ax.axhline(costs[0], color="grey", ls=":", label=f"No model: \\${costs[0]:,.0f}")
    # Very low thresholds flag thousands of rows; cap the y-axis so the minimum is visible.
    ax.set(xscale="log", ylim=(0, 2.5 * costs[0]), xlabel="Threshold (flag if fraud probability >= threshold)",
           ylabel="Cost in USD",
           title=f"Validation cost = missed fraud \\$ + alerts × \\${review_cost:g}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def pr_curve_points(y, p, max_points: int = 200) -> list[dict]:
    """Downsampled PR curve as JSON-friendly points (for the dashboard)."""
    precision, recall, _ = precision_recall_curve(y, p)
    idx = np.unique(np.linspace(0, len(precision) - 1, min(max_points, len(precision))).astype(int))
    return [{"recall": round(float(recall[i]), 4), "precision": round(float(precision[i]), 4)} for i in idx]
