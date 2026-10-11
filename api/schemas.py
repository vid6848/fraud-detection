"""Request / response schemas.

`Transaction` mirrors one row of creditcard.csv minus `Class`. The 28 PCA
columns are generated from `ml.features.V_COLUMNS` rather than typed out by hand.
"""
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, create_model

from api.risk import RiskLevel
from ml.config import RAW_COLUMNS
from ml.features import V_COLUMNS

EXAMPLE_TRANSACTION = {
    "Time": 151_400.0,
    **{v: 0.0 for v in V_COLUMNS},
    "Amount": 42.5,
}


Transaction = create_model(
    "Transaction",
    __config__=ConfigDict(
        extra="forbid",  # a typo like "amount" fails loudly instead of being ignored
        allow_inf_nan=False,
        json_schema_extra={"examples": [EXAMPLE_TRANSACTION]},
    ),
    __doc__="One card transaction: Time, anonymized PCA features V1-V28, Amount.",
    Time=(float, Field(ge=0, description="Seconds since the first transaction in the dataset")),
    **{v: (float, Field(description=f"Anonymized PCA feature {v}")) for v in V_COLUMNS},
    Amount=(float, Field(ge=0, description="Transaction amount in USD")),
)


def to_frame(transactions: list[BaseModel]) -> pd.DataFrame:
    """Transactions as a DataFrame with columns in the order the model was trained on."""
    return pd.DataFrame([t.model_dump() for t in transactions], columns=RAW_COLUMNS)


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str | None = None
    model_name: str | None = None
    trained_at: str | None = None


class ReasonOut(BaseModel):
    code: str = Field(description="Machine-readable reason code, e.g. MODEL_HIGH_RISK, TINY_AMOUNT")
    message: str = Field(description="Plain-language explanation")


class ScoredTransaction(BaseModel):
    probability: float = Field(ge=0, le=1, description="Calibrated fraud probability")
    risk_level: RiskLevel
    reasons: list[ReasonOut]


class PredictResponse(ScoredTransaction):
    model_version: str
    latency_ms: float = Field(description="Server-side time to handle this request")


def make_batch_request(max_size: int) -> type[BaseModel]:
    """Batch request schema; the size limit comes from MAX_BATCH_SIZE at app startup."""
    return create_model(
        "BatchPredictRequest",
        transactions=(
            list[Transaction],
            Field(min_length=1, max_length=max_size,
                  description=f"1 to {max_size} transactions, scored in one model call"),
        ),
    )


class BatchPredictResponse(BaseModel):
    results: list[ScoredTransaction] = Field(description="One result per input row, same order")
    count: int
    model_version: str
    latency_ms: float = Field(description="Server-side time for the whole batch")


class FeatureContribution(BaseModel):
    feature: str = Field(description="V1-V28, Amount, or time_of_day")
    value: float = Field(description="Raw input value (hour of day for time_of_day)")
    shap_value: float = Field(description="Push on the model score; positive = towards fraud")
    direction: Literal["raises_risk", "lowers_risk"]
    description: str


class ExplainResponse(PredictResponse):
    model_score: float = Field(
        description="Uncalibrated forest score that SHAP explains; `probability` is its "
        "calibrated (monotonic) version, so the ranking of reasons is the same"
    )
    base_value: float = Field(description="Average model score SHAP starts from")
    top_features: list[FeatureContribution]


class LatencyStats(BaseModel):
    count: int
    p50: float | None
    p95: float | None
    p99: float | None


class Latency(LatencyStats):
    window: int = Field(description="Percentiles cover at most this many recent requests")
    by_endpoint: dict[str, LatencyStats]


class Counts(BaseModel):
    total: int


class RequestCounts(Counts):
    by_endpoint: dict[str, int]


class ErrorCounts(Counts):
    by_status: dict[str, int]


class MetricsResponse(BaseModel):
    uptime_seconds: float
    started_at: str
    requests: RequestCounts
    errors: ErrorCounts
    latency_ms: Latency
    risk_levels: dict[RiskLevel, int] = Field(
        description="Scored transactions per level (/predict and /predict/batch)"
    )
    scope: str
