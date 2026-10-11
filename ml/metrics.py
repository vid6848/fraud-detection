"""Evaluation metrics for rare-event fraud detection.

A transaction is flagged (an "alert") when its fraud probability is >= threshold.
Business cost of a threshold = fraud dollars we miss + alerts x review cost.
Accuracy is deliberately absent: "always normal" already scores 99.83%.
"""
import numpy as np
from sklearn.metrics import precision_recall_curve

from ml.config import RANDOM_SEED, TARGET_PRECISION


def _as_arrays(*arrays):
    return [np.asarray(a, dtype=float) for a in arrays]


def _pr_summary(y, p, target_precision: float) -> tuple[float, float]:
    """(average precision, recall at target precision) from one PR-curve pass."""
    precision, recall, _ = precision_recall_curve(y, p)
    # Same step-wise formula as sklearn's average_precision_score.
    ap = float(-np.sum(np.diff(recall) * precision[:-1]))
    ok = precision >= target_precision
    return ap, float(recall[ok].max()) if ok.any() else 0.0


def pr_auc(y, p) -> float:
    """Area under the precision-recall curve (average precision)."""
    return _pr_summary(y, p, TARGET_PRECISION)[0]


def recall_at_precision(y, p, target_precision: float = TARGET_PRECISION) -> float:
    """Best recall reachable while keeping precision >= target (0 if never reached)."""
    return _pr_summary(y, p, target_precision)[1]


def threshold_for_precision(y, p, target_precision: float = TARGET_PRECISION) -> float | None:
    """Lowest threshold whose precision is >= target, i.e. the most recall at that precision.

    Returns None if no threshold reaches the target precision.
    """
    precision, recall, thresholds = precision_recall_curve(y, p)
    ok = precision[:-1] >= target_precision  # last PR point has no threshold
    if not ok.any():
        return None
    best = np.flatnonzero(ok)[np.argmax(recall[:-1][ok])]
    return float(thresholds[best])


def threshold_metrics(y, p, threshold: float) -> dict:
    """Confusion matrix, precision, recall and F1 when flagging p >= threshold."""
    y, p = _as_arrays(y, p)
    flagged = p >= threshold
    tp = int(np.sum(flagged & (y == 1)))
    fp = int(np.sum(flagged & (y == 0)))
    fn = int(np.sum(~flagged & (y == 1)))
    tn = int(np.sum(~flagged & (y == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "alerts": tp + fp,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
    }


def cost_curve(y, p, amount, review_cost: float) -> tuple[np.ndarray, np.ndarray]:
    """Business cost at every distinct threshold, from strictest to loosest.

    Returns (thresholds, costs). The first entry is a threshold above every
    score (no alerts at all), whose cost is simply all fraud dollars missed.
    """
    y, p, amount = _as_arrays(y, p, amount)
    order = np.argsort(-p, kind="stable")
    scores = p[order]
    caught = np.cumsum((y * amount)[order])
    alerts = np.arange(1, len(p) + 1)
    # Keep the last row of each run of equal scores: flagging p >= s flags them all.
    last = np.r_[scores[1:] != scores[:-1], True]
    total_fraud = float(np.sum(y * amount))
    thresholds = np.r_[np.nextafter(scores[0], np.inf), scores[last]]
    costs = np.r_[total_fraud, (total_fraud - caught[last]) + alerts[last] * review_cost]
    return thresholds, costs


def best_cost_threshold(y, p, amount, review_cost: float) -> float:
    """Threshold with the lowest business cost (ties go to the stricter threshold)."""
    thresholds, costs = cost_curve(y, p, amount, review_cost)
    return float(thresholds[int(np.argmin(costs))])


def cost_report(y, p, amount, threshold: float, review_cost: float) -> dict:
    """Dollars caught / missed, review spend and savings vs. having no model."""
    y, p, amount = _as_arrays(y, p, amount)
    flagged = p >= threshold
    is_fraud = y == 1
    total_fraud = float(amount[is_fraud].sum())
    caught = float(amount[flagged & is_fraud].sum())
    alerts = int(flagged.sum())
    review = alerts * review_cost
    cost_model = (total_fraud - caught) + review
    return {
        "total_fraud_amount": total_fraud,
        "fraud_amount_caught": caught,
        "fraud_amount_missed": total_fraud - caught,
        "pct_fraud_dollars_caught": 100 * caught / total_fraud if total_fraud else 0.0,
        "alerts": alerts,
        "review_cost_total": review,
        "cost_no_model": total_fraud,
        "cost_with_model": cost_model,
        "cost_saved": total_fraud - cost_model,
    }


def evaluate(y, p, amount, threshold: float, review_cost: float) -> dict:
    """Headline metrics at one threshold, plus threshold-free PR-AUC and recall@90%P."""
    ap, r_at_p = _pr_summary(y, p, TARGET_PRECISION)
    return {
        "pr_auc": ap,
        "recall_at_90_precision": r_at_p,
        **threshold_metrics(y, p, threshold),
        **cost_report(y, p, amount, threshold, review_cost),
    }


BOOTSTRAP_METRICS = [
    "pr_auc",
    "precision",
    "recall",
    "f1",
    "recall_at_90_precision",
    "pct_fraud_dollars_caught",
    "cost_saved",
]


def bootstrap_ci(
    y,
    p,
    amount,
    threshold: float,
    review_cost: float,
    n_resamples: int = 1000,
    seed: int = RANDOM_SEED,
    level: float = 0.95,
) -> dict:
    """Percentile bootstrap confidence intervals (rows resampled with replacement).

    Resamples that happen to contain no fraud are skipped (PR-AUC is undefined).
    """
    y, p, amount = _as_arrays(y, p, amount)
    rng = np.random.default_rng(seed)
    n = len(y)
    samples = {m: [] for m in BOOTSTRAP_METRICS}
    for _ in range(n_resamples):
        idx = rng.integers(0, n, n)
        yb, pb, ab = y[idx], p[idx], amount[idx]
        if yb.sum() == 0:
            continue
        ap, r_at_p = _pr_summary(yb, pb, TARGET_PRECISION)
        tm = threshold_metrics(yb, pb, threshold)
        cr = cost_report(yb, pb, ab, threshold, review_cost)
        values = {"pr_auc": ap, "recall_at_90_precision": r_at_p, **tm, **cr}
        for m in BOOTSTRAP_METRICS:
            samples[m].append(values[m])
    alpha = (1 - level) / 2
    return {
        m: {
            "low": float(np.quantile(v, alpha)),
            "high": float(np.quantile(v, 1 - alpha)),
        }
        for m, v in samples.items()
    }
