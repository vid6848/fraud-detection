"""Tests for ml/metrics.py using small hand-checked examples."""
import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from ml.metrics import (
    best_cost_threshold,
    bootstrap_ci,
    cost_curve,
    cost_report,
    evaluate,
    pr_auc,
    recall_at_precision,
    threshold_for_precision,
    threshold_metrics,
)

# 6 rows: frauds at scores 0.9, 0.7, 0.2 with amounts 100, 50, 10.
Y = np.array([1, 0, 1, 0, 1, 0])
P = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
AMT = np.array([100.0, 1.0, 50.0, 1.0, 10.0, 1.0])


def test_threshold_metrics():
    m = threshold_metrics(Y, P, 0.7)
    assert m["confusion_matrix"] == {"tn": 2, "fp": 1, "fn": 1, "tp": 2}
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["alerts"] == 3


def test_no_alerts_gives_zero_precision_not_error():
    m = threshold_metrics(Y, P, 0.99)
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0


def test_cost_report():
    r = cost_report(Y, P, AMT, threshold=0.7, review_cost=5)
    assert r["total_fraud_amount"] == 160
    assert r["fraud_amount_caught"] == 150
    assert r["review_cost_total"] == 15  # 3 alerts x $5
    assert r["cost_with_model"] == 10 + 15
    assert r["cost_saved"] == 160 - 25
    assert r["pct_fraud_dollars_caught"] == pytest.approx(150 / 160 * 100)


def test_cost_curve_matches_cost_report_at_every_threshold():
    thresholds, costs = cost_curve(Y, P, AMT, review_cost=5)
    assert costs[0] == 160  # nothing flagged: all fraud dollars missed
    for thr, cost in zip(thresholds, costs):
        assert cost == pytest.approx(cost_report(Y, P, AMT, thr, 5)["cost_with_model"])


def test_cost_curve_handles_tied_scores():
    y, p, amt = np.array([1, 0, 1]), np.array([0.5, 0.5, 0.1]), np.array([10.0, 1.0, 10.0])
    thresholds, costs = cost_curve(y, p, amt, review_cost=1)
    assert len(thresholds) == 3  # none, >=0.5 (two rows at once), >=0.1
    assert costs.tolist() == [20, 10 + 2, 0 + 3]


def test_best_cost_threshold():
    # Review cost $5: flag down to 0.7 (cost 25); going to 0.2 costs 0 + 5*5 = 25 too,
    # and the tie goes to the stricter threshold.
    assert best_cost_threshold(Y, P, AMT, review_cost=5) == 0.7
    # Expensive reviews: flag only the $100 fraud.
    assert best_cost_threshold(Y, P, AMT, review_cost=40) == 0.9
    # Free reviews: catching everything is cheapest.
    assert best_cost_threshold(Y, P, AMT, review_cost=0) == 0.2


def test_recall_and_threshold_at_precision():
    # Precision >= 0.9 only at the top score (1/1); recall there is 1/3.
    assert recall_at_precision(Y, P, 0.9) == pytest.approx(1 / 3)
    assert threshold_for_precision(Y, P, 0.9) == 0.9
    # Precision >= 0.65 is reached at 0.7 (2/3), recall 2/3 (0.2 only gets 3/5).
    assert recall_at_precision(Y, P, 0.65) == pytest.approx(2 / 3)
    assert threshold_for_precision(Y, P, 0.65) == 0.7
    # Impossible target.
    assert threshold_for_precision(np.array([0, 1]), np.array([0.9, 0.1]), 0.9) is None
    assert recall_at_precision(np.array([0, 1]), np.array([0.9, 0.1]), 0.9) == 0.0


def test_pr_auc_matches_sklearn():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.1).astype(int)
    p = np.clip(y * 0.3 + rng.random(500) * 0.7, 0, 1)
    assert pr_auc(y, p) == pytest.approx(average_precision_score(y, p))


def test_evaluate_has_headline_metrics():
    m = evaluate(Y, P, AMT, threshold=0.7, review_cost=5)
    for key in ("pr_auc", "precision", "recall", "f1", "recall_at_90_precision",
                "pct_fraud_dollars_caught", "cost_saved", "confusion_matrix"):
        assert key in m
    assert "accuracy" not in m


def test_bootstrap_ci_brackets_estimate_and_is_reproducible():
    rng = np.random.default_rng(1)
    y = (rng.random(2_000) < 0.05).astype(int)
    p = np.clip(y * 0.5 + rng.random(2_000) * 0.5, 0, 1)
    amt = rng.exponential(80, 2_000)
    point = evaluate(y, p, amt, 0.5, 5)
    ci = bootstrap_ci(y, p, amt, 0.5, 5, n_resamples=200, seed=3)
    assert ci == bootstrap_ci(y, p, amt, 0.5, 5, n_resamples=200, seed=3)
    for key, bounds in ci.items():
        assert bounds["low"] <= point[key] <= bounds["high"], key
