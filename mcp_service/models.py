from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    query_id: str = Field(
        min_length=3,
        max_length=128,
        description="Allowlisted query ID from GET /v1/queries.",
        examples=["ic_orders_lead_time_extract"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Query-specific parameters. Required keys depend on query_id. "
            "Use GET /v1/queries to inspect required and optional params."
        ),
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Maximum rows to return (server-side cap may apply).",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query_id": "ic_orders_lead_time_extract",
                    "params": {"start_date": "2024-01-01", "part_no": "PART-0001"},
                    "limit": 100,
                },
                {
                    "query_id": "sales_monthly_history",
                    "params": {"start_date": "2024-01-01"},
                    "limit": 100,
                },
                {
                    "query_id": "precomputed_forecast_values",
                    "params": {"domain": "lead_time", "series_key": "__ALL__"},
                    "limit": 30,
                },
            ]
        }
    )


class QueryDefinitionResponse(BaseModel):
    query_id: str
    description: str
    required_params: list[str]
    optional_params: list[str]


class QueryResponse(BaseModel):
    query_id: str
    row_count: int
    generated_at: datetime
    rows: list[dict[str, Any]]


class ForecastPoint(BaseModel):
    timestamp: datetime
    value: float
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None


class ForecastResponse(BaseModel):
    domain: str
    series_key: str
    generated_at: datetime
    source: str
    points: list[ForecastPoint]
