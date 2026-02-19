from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, text

from mcp_service.config import settings
from mcp_service.database import (
    forecast_outputs,
    get_connection,
    get_dialect_name,
    initialize_schema,
)
from mcp_service.models import (
    ForecastPoint,
    ForecastResponse,
    QueryDefinitionResponse,
    QueryRequest,
    QueryResponse,
)
from mcp_service.query_filter import validate_and_normalize_params
from mcp_service.query_registry import get_query_registry

ForecastDomain = Literal["lead_time", "sales"]

app = FastAPI(
    title="Redegades Forecast MCP",
    version="0.1.0",
    description=(
        "Controlled query layer + scheduled precomputed forecasting API "
        "for lead time and sales domains."
    ),
)


@app.on_event("startup")
def startup() -> None:
    initialize_schema()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/queries", response_model=list[QueryDefinitionResponse])
def list_queries() -> list[QueryDefinitionResponse]:
    registry = get_query_registry(get_dialect_name())
    responses: list[QueryDefinitionResponse] = []
    for definition in registry.values():
        required = sorted(definition.required_params)
        optional = sorted(set(definition.allowed_params) - set(required))
        responses.append(
            QueryDefinitionResponse(
                query_id=definition.query_id,
                description=definition.description,
                required_params=required,
                optional_params=optional,
            )
        )
    responses.sort(key=lambda item: item.query_id)
    return responses


@app.post("/v1/query/execute", response_model=QueryResponse)
def execute_query(payload: QueryRequest) -> QueryResponse:
    registry = get_query_registry(get_dialect_name())
    definition = registry.get(payload.query_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown query_id '{payload.query_id}'")

    try:
        params = validate_and_normalize_params(definition, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hard_limit = min(payload.limit, settings.allowed_query_row_limit)
    with get_connection() as connection:
        rows = connection.execute(text(definition.sql), params).mappings().all()

    serialized_rows = [
        {key: _serialize_scalar(value) for key, value in row.items()}
        for row in rows[:hard_limit]
    ]

    return QueryResponse(
        query_id=payload.query_id,
        row_count=len(serialized_rows),
        generated_at=datetime.now(UTC).replace(tzinfo=None),
        rows=serialized_rows,
    )


@app.get(
    "/v1/forecast/latest",
    response_model=ForecastResponse,
    summary="Get Latest Precomputed Forecast",
    description=(
        "Returns forecast points from the latest precomputed scheduler run. "
        "No heavy forecasting is executed on-demand."
    ),
)
def latest_forecast(
    domain: ForecastDomain = Query(
        ...,
        description="Forecast domain. Allowed values: 'lead_time' or 'sales'.",
        examples=["lead_time"],
    ),
    series_key: str = Query(
        "__ALL__",
        min_length=1,
        description="Series identifier. Use '__ALL__' for aggregate, or a part number such as 'PART-0001'.",
        examples=["__ALL__"],
    ),
    limit: int = Query(
        1,
        ge=1,
        le=1000,
        description="Maximum forecast points to return from the latest run.",
        examples=[1],
    ),
) -> ForecastResponse:
    hard_limit = min(limit, settings.allowed_query_row_limit)

    with get_connection() as connection:
        latest_generated_at = connection.execute(
            select(func.max(forecast_outputs.c.generated_at)).where(
                forecast_outputs.c.domain == domain,
                forecast_outputs.c.series_key == series_key,
            )
        ).scalar_one_or_none()

        if latest_generated_at is None:
            raise HTTPException(
                status_code=404,
                detail=f"No forecast found for domain='{domain}', series_key='{series_key}'",
            )

        stmt = (
            select(
                forecast_outputs.c.timestamp,
                forecast_outputs.c.value,
                forecast_outputs.c.p10,
                forecast_outputs.c.p50,
                forecast_outputs.c.p90,
            )
            .where(
                forecast_outputs.c.domain == domain,
                forecast_outputs.c.series_key == series_key,
                forecast_outputs.c.generated_at == latest_generated_at,
            )
            .order_by(forecast_outputs.c.timestamp.desc())
            .limit(hard_limit)
        )
        rows = connection.execute(stmt).mappings().all()

    points = [
        ForecastPoint(
            timestamp=row["timestamp"],
            value=float(row["value"]),
            p10=_nullable_float(row["p10"]),
            p50=_nullable_float(row["p50"]),
            p90=_nullable_float(row["p90"]),
        )
        for row in rows
    ]

    return ForecastResponse(
        domain=domain,
        series_key=series_key,
        generated_at=latest_generated_at,
        source="precomputed_table",
        points=points,
    )


def _nullable_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
