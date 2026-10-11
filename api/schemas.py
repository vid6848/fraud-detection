"""Request / response schemas.

`Transaction` mirrors one row of creditcard.csv minus `Class`. The 28 PCA
columns are generated from `ml.features.V_COLUMNS` rather than typed out by hand.
"""
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


class PredictResponse(BaseModel):
    probability: float = Field(ge=0, le=1, description="Calibrated fraud probability")
    risk_level: RiskLevel
    reasons: list[ReasonOut]
    model_version: str
    latency_ms: float = Field(description="Server-side scoring time for this request")
