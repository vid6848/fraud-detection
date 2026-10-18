"""Score drift: is the model seeing the kind of transactions it was trained on?

The Population Stability Index (PSI) compares two distributions over the same bins:

    PSI = sum over bins of (live% - reference%) * ln(live% / reference%)

Here the distributions are of the *served* fraud probability: the reference is the
training split scored by the deployed model, and "live" is the most recent scored
transactions. Rule of thumb (and the labels used here): < 0.1 OK, 0.1-0.25 Watch,
>= 0.25 Alert.

Bins follow the risk bands rather than quantiles: the calibrated score is step-like
(~46 distinct values on train, 93% of rows below 0.0005), so quantile bins would
collapse into one another.
"""
from datetime import UTC, datetime

import numpy as np

WATCH = 0.1
ALERT = 0.25
# Empty bins would make ln(.) infinite; treat them as this share instead.
EPS = 1e-4
# Low-score splits inside LOW (where nearly all traffic sits), then MEDIUM and HIGH.
LOW_SPLITS = (0.0005, 0.001, 0.005)


def bin_edges(medium_threshold: float, high_threshold: float) -> list[float]:
    """[0, LOW splits..., MEDIUM, HIGH, 1]: the last three bins are the risk bands' edges."""
    edges = [0.0, *LOW_SPLITS, medium_threshold, high_threshold, 1.0]
    if any(a >= b for a, b in zip(edges, edges[1:])):
        raise ValueError(f"bin edges must increase: {edges}")
    return edges


def proportions(scores, edges: list[float]) -> np.ndarray:
    """Share of `scores` in each bin; the last bin includes 1.0."""
    scores = np.clip(np.asarray(scores, dtype=float), 0.0, 1.0)
    if scores.size == 0:
        return np.zeros(len(edges) - 1)
    counts, _ = np.histogram(scores, bins=edges)
    return counts / scores.size


def psi(reference, live, eps: float = EPS) -> tuple[float, np.ndarray]:
    """Total PSI and each bin's contribution (all >= 0)."""
    ref = np.clip(np.asarray(reference, dtype=float), eps, None)
    cur = np.clip(np.asarray(live, dtype=float), eps, None)
    contributions = (cur - ref) * np.log(cur / ref)
    return float(contributions.sum()), contributions


def drift_status(value: float) -> str:
    if value >= ALERT:
        return "Alert"
    if value >= WATCH:
        return "Watch"
    return "OK"


def reference_distribution(scores, edges: list[float], *, model_version: str,
                           source: str) -> dict:
    """The JSON saved as ml/artifacts/score_distribution.json."""
    scores = np.asarray(scores, dtype=float)
    counts, _ = np.histogram(np.clip(scores, 0.0, 1.0), bins=edges)
    return {
        "model_version": model_version,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "rows": int(scores.size),
        "edges": [float(e) for e in edges],
        "counts": [int(c) for c in counts],
        "proportions": [float(p) for p in counts / scores.size],
    }
