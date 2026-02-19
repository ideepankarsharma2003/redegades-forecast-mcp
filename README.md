# Redegades Forecast MCP

MCP service for lead-time and sales forecasting with controlled database access, scheduled forecast generation, and fast retrieval of precomputed outputs.

## Scope

This repository is the isolated forecasting MCP module (intended as a Git submodule in the main platform). It implements:

- Controlled DB API wrapper with query allowlisting and parameter filtering.
- Dummy database for local development and testing.
- Statistical baseline forecasting.
- Monte Carlo quantile forecasting (`P10`, `P50`, `P90`).
- Standard forecast response structure (`timestamp` + values).
- Scheduler service for precomputing forecasts (cron-style), not on-demand runtime computation.

## Architecture Decisions (Agreed)

1. Run a separate forecasting MCP server as a modular service.
2. Use a controlled DB execution layer with safe query IDs, not arbitrary SQL input.
3. Precompute forecasts on a schedule and store in `forecast_outputs`.
4. Agent/UI reads precomputed values (default single-row response for low latency).
5. Keep implementation Dockerized for local/prod parity.

## Data Source

### Production Source

- MS SQL Server data lake.
- Primary lead-time extract query is stored in `sql/ic_orders_lead_time.sql`.
- Query is based on `DATA_LAKE.IC_ORDERS` and `DATA_LAKE.PART_MASTER`.

### Local Development Source

- SQLite dummy schema (`ic_orders`, `part_master`, `sales_history`, `forecast_outputs`).
- Seeded using `scripts/init_dummy_db.py`.

## Repository Layout

```text
redegades-forecast-mcp/
  mcp_service/
    api.py
    config.py
    database.py
    models.py
    query_filter.py
    query_registry.py
    scheduler.py
    forecasting/
      baseline.py
      monte_carlo.py
      jobs.py
  scripts/
    init_dummy_db.py
    run_forecast_job.py
  sql/
    ic_orders_lead_time.sql
  docker-compose.yml
  Dockerfile
  requirements.txt
```

## Quick Start (Local)

1. Copy environment file.
```bash
cp .env.example .env
```

2. Build and run services.
```bash
docker compose up --build
```

3. API endpoints:
- `GET http://localhost:8080/` (redirects to Swagger UI at `/docs`)
- `GET http://localhost:8080/health`
- `GET http://localhost:8080/v1/queries`
- `POST http://localhost:8080/v1/query/execute`
- `GET http://localhost:8080/v1/forecast/latest?domain=lead_time&series_key=__ALL__`

### Forecast Endpoint Parameters

For `GET /v1/forecast/latest`:

- `domain` (required):
  - `lead_time`
  - `sales`
- `series_key` (optional, default `__ALL__`):
  - `__ALL__` for aggregate forecast
  - specific part number (for dummy data: `PART-0001`, `PART-0002`, ...)
- `limit` (optional, default `1`):
  - Number of points returned from the latest precomputed run.

Examples:

```bash
curl "http://localhost:8080/v1/forecast/latest?domain=lead_time&series_key=__ALL__&limit=1"
```

```bash
curl "http://localhost:8080/v1/forecast/latest?domain=sales&series_key=PART-0001&limit=6"
```

## Non-Docker Local Run

1. Install dependencies.
```bash
pip install -r requirements.txt
```

2. Initialize dummy data.
```bash
python scripts/init_dummy_db.py
```

3. Run one forecast job manually.
```bash
python scripts/run_forecast_job.py
```

4. Start API.
```bash
uvicorn mcp_service.api:app --host 0.0.0.0 --port 8080
```

5. Start scheduler (separate terminal).
```bash
python -m mcp_service.scheduler
```

6. Start MCP server (stdio transport) for MCP clients.
```bash
python -m mcp_service.mcp_server
```

## Safe Query Model

This service blocks direct arbitrary SQL execution. Query requests must:

1. Use an allowlisted `query_id` from `mcp_service/query_registry.py`.
2. Provide only expected parameters.
3. Pass parameter filtering checks in `mcp_service/query_filter.py`.

## Forecasting Strategy

### Lead Time Forecasting

- Historical series from closed orders (`date_entered` to `complete_date`).
- Product-level forecasts (`series_key = PART_NO`) and aggregate (`__ALL__`).
- Statistical baseline + Monte Carlo quantiles (`P10`, `P50`, `P90`).

### Sales Forecasting

- Monthly quantity aggregation from `sales_history`.
- Product-level and aggregate forecasts.
- Same baseline + quantile output contract.

## Standard Forecast Response

Example response from `GET /v1/forecast/latest`:

```json
{
  "domain": "lead_time",
  "series_key": "__ALL__",
  "generated_at": "2026-02-19T03:00:00",
  "source": "precomputed_table",
  "points": [
    {
      "timestamp": "2026-02-20T00:00:00",
      "value": 17.8,
      "p10": 13.5,
      "p50": 17.7,
      "p90": 22.1
    }
  ]
}
```

## Security Guardrails

- No arbitrary SQL endpoint.
- Query ID allowlist and parameter schema enforcement.
- Dangerous SQL token detection in request params.
- Read-focused API surface for agent consumption.
- Separation between data access and forecasting execution layers.

## UI Integration Notes

This MCP supports the planned platform reporting tab:

- KPI cards read from precomputed forecast rows.
- Forecast sections for lead time and sales.
- Embedded agent panel can request latest forecast records quickly.
- Optional right-click/Ask-Agent interactions should call MCP endpoints for contextual retrieval.

## Task Status

- [x] Implement DB API wrapper with query filter.
- [x] Create dummy database for testing.
- [x] Implement initial forecasting script (statistical baseline).
- [x] Add Monte Carlo module (`P10`, `P50`, `P90`).
- [x] Define standard forecast response structure.
- [x] Dockerize MCP service and compose integration.

## Next Implementation Steps

1. Replace SQLite dummy source with VPN-accessed MS SQL data lake connection.
2. Map production schema names and credentials via environment variables.
3. Validate KPI definitions with Jason (final metric contract).
4. Add model backtesting and error tracking before production rollout.
