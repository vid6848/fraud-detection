"""Save the training score distribution that GET /drift compares live scores against.

    python scripts/make_score_distribution.py

Scores the *training* split with the deployed model (ml/artifacts/model.joblib) and
writes bin counts to ml/artifacts/score_distribution.json. Re-run it after retraining:
the API refuses to compare against a reference made for another model version.

These are in-sample scores (the forest was fitted on these rows). After isotonic
calibration they sit close to held-out scores: PSI train -> validation is about 0.02,
well inside "OK".
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import joblib  # noqa: E402

import ml  # noqa: E402,F401  (unpickles ml.calibration.CalibratedModel)
from api.config import DEFAULT_MEDIUM_THRESHOLD  # noqa: E402
from ml.config import ARTIFACTS_DIR, RAW_COLUMNS  # noqa: E402
from ml.drift import bin_edges, reference_distribution  # noqa: E402
from ml.eda_utils import load_data  # noqa: E402
from ml.split import time_split  # noqa: E402

OUTPUT = ARTIFACTS_DIR / "score_distribution.json"


def build(model, metadata: dict, train, medium_threshold: float = DEFAULT_MEDIUM_THRESHOLD) -> dict:
    scores = model.predict_proba(train[RAW_COLUMNS])[:, 1]
    edges = bin_edges(medium_threshold, float(metadata["threshold"]))
    return reference_distribution(
        scores, edges, model_version=metadata["model_version"],
        source=f"training split ({len(train):,} rows) scored by the deployed model")


def main() -> None:
    metadata = json.loads((ARTIFACTS_DIR / "metadata.json").read_text())
    model = joblib.load(ARTIFACTS_DIR / "model.joblib")
    train, _, _ = time_split(load_data())
    result = build(model, metadata, train)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    shares = ", ".join(f"{p:.3%}" for p in result["proportions"])
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {result['rows']:,} rows, bins {shares}")


if __name__ == "__main__":
    main()
