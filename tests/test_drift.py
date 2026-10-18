"""Phase 7 step 4: PSI maths (ml/drift.py) and the saved training score distribution."""
import json
import math
import sys

import numpy as np
import pytest

from api.config import DEFAULT_MEDIUM_THRESHOLD
from ml.config import ARTIFACTS_DIR, ROOT
from ml.drift import (
    ALERT,
    EPS,
    WATCH,
    bin_edges,
    drift_status,
    proportions,
    psi,
    reference_distribution,
)
from tests.synthetic import make_transactions

sys.path.insert(0, str(ROOT / "scripts"))
import make_score_distribution  # noqa: E402

EDGES = bin_edges(0.05, 0.4)


def test_bin_edges_follow_the_risk_bands():
    assert EDGES == [0.0, 0.0005, 0.001, 0.005, 0.05, 0.4, 1.0]


@pytest.mark.parametrize("medium, high", [(0.001, 0.4), (0.05, 0.05), (0.5, 0.4), (0.05, 1.0)])
def test_bin_edges_must_increase(medium, high):
    with pytest.raises(ValueError):
        bin_edges(medium, high)


def test_proportions_put_band_edges_in_the_band_above():
    shares = proportions([0.0, 0.0004, 0.05, 0.3999, 0.4, 1.0, 1.2, -0.1], EDGES)
    # 0.05 is MEDIUM, 0.4 is HIGH (>= threshold), 1.0 and clipped 1.2 are in the last bin
    assert shares.tolist() == pytest.approx([3 / 8, 0, 0, 0, 2 / 8, 3 / 8])
    assert shares.sum() == pytest.approx(1)


def test_proportions_of_nothing_are_zero():
    assert proportions([], EDGES).tolist() == [0.0] * 6


def test_psi_is_zero_for_identical_distributions():
    total, parts = psi([0.9, 0.1], [0.9, 0.1])
    assert total == 0 and parts.tolist() == [0, 0]


def test_psi_matches_the_formula():
    ref, live = [0.5, 0.3, 0.2], [0.4, 0.3, 0.3]
    expected = sum((c - r) * math.log(c / r) for r, c in zip(ref, live))
    total, parts = psi(ref, live)
    assert total == pytest.approx(expected)
    assert parts.sum() == pytest.approx(total)
    assert (parts >= 0).all()  # every bin adds, none cancel out


def test_psi_treats_empty_bins_as_a_small_share_instead_of_infinity():
    total, parts = psi([1.0, 0.0], [0.5, 0.5])
    assert math.isfinite(total)
    assert parts[1] == pytest.approx((0.5 - EPS) * math.log(0.5 / EPS))


@pytest.mark.parametrize("value, status", [
    (0.0, "OK"), (WATCH - 1e-9, "OK"), (WATCH, "Watch"), (ALERT - 1e-9, "Watch"),
    (ALERT, "Alert"), (3.0, "Alert"),
])
def test_drift_status(value, status):
    assert drift_status(value) == status


def test_reference_distribution():
    ref = reference_distribution([0.0001, 0.0002, 0.06, 0.9], EDGES, model_version="9.9.9",
                                 source="test")
    assert ref["counts"] == [2, 0, 0, 0, 1, 1]
    assert ref["proportions"] == [0.5, 0, 0, 0, 0.25, 0.25]
    assert (ref["rows"], ref["model_version"], ref["source"]) == (4, "9.9.9", "test")
    json.dumps(ref)  # plain JSON types only


def test_script_scores_the_training_rows_with_the_model():
    class Model:
        def predict_proba(self, X):
            p = np.where(X["Amount"] > 100, 0.9, 0.0001)
            return np.column_stack([1 - p, p])

    train = make_transactions(n=50)
    result = make_score_distribution.build(Model(), {"model_version": "2.0.0", "threshold": 0.4},
                                           train)
    assert result["edges"] == EDGES
    assert result["rows"] == 50
    assert result["counts"][0] + result["counts"][-1] == 50
    assert result["counts"][-1] == int((train["Amount"] > 100).sum())
    assert "50 rows" in result["source"]


def test_committed_reference_matches_the_deployed_model():
    reference = json.loads((ARTIFACTS_DIR / "score_distribution.json").read_text())
    metadata = json.loads((ARTIFACTS_DIR / "metadata.json").read_text())
    assert reference["model_version"] == metadata["model_version"]
    assert reference["edges"] == bin_edges(DEFAULT_MEDIUM_THRESHOLD, metadata["threshold"])
    assert sum(reference["counts"]) == reference["rows"] == metadata["split"]["train"]["rows"]
    assert sum(reference["proportions"]) == pytest.approx(1)
