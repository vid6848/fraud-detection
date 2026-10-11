"""Settings shared by the Phase 2 training pipeline.

Everything that affects results lives here so a run can be reproduced exactly.
"""
from pathlib import Path

from ml.eda_utils import DATA_PATH, TARGET

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "ml" / "artifacts"
FIGURES_DIR = ROOT / "docs" / "figures"
DOCS_DIR = ROOT / "docs"

RANDOM_SEED = 42
MODEL_VERSION = "1.0.0"

# Time-based split from EDA finding 10 (`ml.eda_utils.time_split_boundaries`):
# train: Time < 132_929 s, validation: 132_929 <= Time < 151_329 s, test: the rest.
SPLIT_BOUNDARIES = (132_929, 151_329)

# What one analyst review of an alert costs, in USD. Override with `--review-cost`.
REVIEW_COST_PER_ALERT = 5.0

# Columns the saved model expects (a raw row from creditcard.csv minus `Class`).
RAW_COLUMNS = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount"]
AMOUNT_COLUMN = "Amount"

# SMOTE / undersampling: resample until fraud is 10% of the normal class.
RESAMPLE_RATIO = 0.1

# Probability calibration: folds of TimeSeriesSplit inside the training split.
CALIBRATION_FOLDS = 4

# Precision target for the "recall at 90% precision" metric.
TARGET_PRECISION = 0.90

N_BOOTSTRAP = 1000

# SHAP sanity check (EDA finding 7): these should rank near the top.
EXPECTED_TOP_FEATURES = ["V17", "V14", "V12", "V10"]
SHAP_TOP_K = 10

__all__ = [
    "AMOUNT_COLUMN",
    "ARTIFACTS_DIR",
    "CALIBRATION_FOLDS",
    "DATA_PATH",
    "DOCS_DIR",
    "EXPECTED_TOP_FEATURES",
    "FIGURES_DIR",
    "MODEL_VERSION",
    "N_BOOTSTRAP",
    "RANDOM_SEED",
    "RAW_COLUMNS",
    "RESAMPLE_RATIO",
    "REVIEW_COST_PER_ALERT",
    "ROOT",
    "SHAP_TOP_K",
    "SPLIT_BOUNDARIES",
    "TARGET",
    "TARGET_PRECISION",
]
