from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query_id: str = Field(min_length=3, max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=5000)


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
