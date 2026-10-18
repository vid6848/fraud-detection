"""GET /drift: PSI between the latest live scores and the training score distribution.

The reference distribution (`ml/artifacts/score_distribution.json`, made by
`scripts/make_score_distribution.py`) is loaded once at startup and only used if it
was made for the model the API is serving.
"""
import json
from pathlib import Path

from ml.drift import ALERT, WATCH, drift_status, proportions, psi


class DriftUnavailable(RuntimeError):
    pass


def load_reference(path: Path, model_version: str) -> dict:
    if not path.exists():
        raise DriftUnavailable(f"{path.name} not found (run scripts/make_score_distribution.py)")
    reference = json.loads(path.read_text())
    if reference.get("model_version") != model_version:
        raise DriftUnavailable(
            f"{path.name} is for model {reference.get('model_version')}, the API serves "
            f"{model_version} (re-run scripts/make_score_distribution.py)")
    if len(reference["edges"]) != len(reference["proportions"]) + 1:
        raise DriftUnavailable(f"{path.name} is malformed: edges and proportions don't match")
    return reference


def drift_report(reference: dict, rows: list[dict], *, window: int, min_rows: int,
                 model_version: str) -> dict:
    """`rows` are {probability, created_at}, newest first."""
    edges = reference["edges"]
    live = proportions([r["probability"] for r in rows], edges)
    total, contributions = psi(reference["proportions"], live) if rows else (None, None)
    if not rows or len(rows) < min_rows:
        status = "Not enough data"
    else:
        status = drift_status(total)
    return {
        "status": status,
        "psi": None if total is None else round(total, 6),
        "live_rows": len(rows),
        "window": window,
        "min_rows": min_rows,
        "live_from": rows[-1]["created_at"] if rows else None,
        "live_to": rows[0]["created_at"] if rows else None,
        "thresholds": {"watch": WATCH, "alert": ALERT},
        "bins": [
            {"lower": lo, "upper": hi, "reference": ref, "live": float(cur),
             "contribution": 0.0 if contributions is None else float(contributions[i])}
            for i, (lo, hi, ref, cur) in enumerate(
                zip(edges, edges[1:], reference["proportions"], live))
        ],
        "reference": {key: reference[key] for key in ("rows", "source", "model_version",
                                                     "created_at")},
        "model_version": model_version,
    }
