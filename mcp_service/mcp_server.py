from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

from mcp_service.api import execute_query, latest_forecast, list_queries
from mcp_service.database import initialize_schema
from mcp_service.models import QueryRequest

mcp = FastMCP("Redegades Forecast MCP")


@mcp.tool(description="List all allowlisted safe query IDs and parameter contracts.")
def available_queries() -> list[dict[str, Any]]:
    initialize_schema()
    return [query.model_dump(mode="json") for query in list_queries()]


@mcp.tool(
    description=(
        "Execute an allowlisted query via controlled DB access. "
        "Only query IDs defined by the server are permitted."
    )
)
def run_safe_query(
    query_id: str,
    params: dict[str, Any] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    initialize_schema()
    try:
        response = execute_query(
            QueryRequest(query_id=query_id, params=params or {}, limit=limit)
        )
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    return response.model_dump(mode="json")


@mcp.tool(
    description=(
        "Get latest precomputed forecast values. "
        "This reads from stored outputs and does not run heavy forecasting on demand."
    )
)
def get_latest_forecast(
    domain: Literal["lead_time", "sales"],
    series_key: str = "__ALL__",
    limit: int = 1,
) -> dict[str, Any]:
    initialize_schema()
    try:
        response = latest_forecast(domain=domain, series_key=series_key, limit=limit)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    return response.model_dump(mode="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
