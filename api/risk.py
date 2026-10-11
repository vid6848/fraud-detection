"""Risk levels (from the model) plus a small rules layer (from EDA findings).

- The model alone decides HIGH: probability >= the cost-tuned threshold in metadata.json.
- MEDIUM: probability >= MEDIUM_THRESHOLD, or LOW raised by the rules (below).
- Rules always add reason codes. They can raise LOW to MEDIUM, never anything to HIGH.

Rules (docs/eda_findings.md):
- TINY_AMOUNT (#4): 5.5% of frauds are $0.00 vs 0.6% of normal charges ("card testing").
- NIGHT_HOURS (#5): fraud rate is 1.0-1.7% in hours 1-7 vs ~0.1-0.2% during the day.
Only both together escalate: each one alone flags far more normal traffic than fraud.
"""
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from ml.features import hour_of_day

TINY_AMOUNT_MAX = 1.00  # USD, exclusive
NIGHT_START_HOUR, NIGHT_END_HOUR = 1, 7  # [1, 7)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class Reason:
    code: str
    message: str


def model_risk_level(probability: float, medium: float, high: float) -> RiskLevel:
    if probability >= high:
        return RiskLevel.HIGH
    if probability >= medium:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def rule_flags(df: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per rule, for raw transaction rows (vectorized)."""
    hours = hour_of_day(df["Time"])
    return pd.DataFrame(
        {
            "TINY_AMOUNT": df["Amount"].to_numpy(dtype=float) < TINY_AMOUNT_MAX,
            "NIGHT_HOURS": (hours >= NIGHT_START_HOUR) & (hours < NIGHT_END_HOUR),
        },
        index=df.index,
    )


RULE_MESSAGES = {
    "TINY_AMOUNT": f"Charge under ${TINY_AMOUNT_MAX:.2f}, a common card-testing pattern",
    "NIGHT_HOURS": (
        f"Made between {NIGHT_START_HOUR:02d}:00 and {NIGHT_END_HOUR:02d}:00, "
        "when the fraud rate is about 10x higher"
    ),
}


def assess(probability: float, flags: dict[str, bool], medium: float,
           high: float) -> tuple[RiskLevel, list[Reason]]:
    """Final risk level and reasons for one transaction."""
    level = model_risk_level(probability, medium, high)
    reasons = []
    if level is RiskLevel.HIGH:
        reasons.append(Reason("MODEL_HIGH_RISK",
                              f"Model fraud probability {probability:.3f} is at or above "
                              f"the HIGH threshold {high:.3f}"))
    elif level is RiskLevel.MEDIUM:
        reasons.append(Reason("MODEL_MEDIUM_RISK",
                              f"Model fraud probability {probability:.3f} is at or above "
                              f"the MEDIUM threshold {medium:.3f}"))

    fired = [code for code, on in flags.items() if on]
    reasons += [Reason(code, RULE_MESSAGES[code]) for code in fired]

    if level is RiskLevel.LOW and set(fired) >= {"TINY_AMOUNT", "NIGHT_HOURS"}:
        level = RiskLevel.MEDIUM
        reasons.append(Reason("RULES_ESCALATED",
                              "Tiny charge at night: raised from LOW to MEDIUM by rules"))
    return level, reasons


def assess_frame(probabilities: np.ndarray, df: pd.DataFrame, medium: float,
                 high: float) -> list[tuple[RiskLevel, list[Reason]]]:
    """`assess` for every row of a raw transaction frame."""
    flags = rule_flags(df).to_dict("records")
    return [assess(float(p), f, medium, high) for p, f in zip(probabilities, flags)]
