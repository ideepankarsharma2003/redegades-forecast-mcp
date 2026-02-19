from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.engine import Connection

from mcp_service.config import settings
from mcp_service.database import (
    as_datetime,
    forecast_outputs,
    get_connection,
    ic_orders,
    initialize_schema,
    sales_history,
)
from mcp_service.forecasting.baseline import generate_baseline_forecast
from mcp_service.forecasting.monte_carlo import simulate_quantiles


@dataclass
class ForecastJobSummary:
    generated_at: datetime
    lead_time_series: int
    sales_series: int
    rows_written: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "lead_time_series": self.lead_time_series,
            "sales_series": self.sales_series,
            "rows_written": self.rows_written,
        }


def run_forecast_job(now: datetime | None = None) -> ForecastJobSummary:
    initialize_schema()
    generated_at = (now or datetime.now(UTC)).replace(tzinfo=None, microsecond=0)
    lookback_start = generated_at - timedelta(days=settings.history_lookback_days)

    with get_connection() as connection:
        lead_time_history = _load_lead_time_history(connection, lookback_start)
        sales_history_by_series = _load_sales_history(connection, lookback_start.date())

        lead_rows, lead_series_count = _build_forecast_rows(
            domain="lead_time",
            frequency="daily",
            history_by_series=lead_time_history,
            generated_at=generated_at,
            horizon=settings.forecast_horizon_days,
        )
        sales_rows, sales_series_count = _build_forecast_rows(
            domain="sales",
            frequency="monthly",
            history_by_series=sales_history_by_series,
            generated_at=generated_at,
            horizon=settings.forecast_horizon_months,
        )

        all_rows = lead_rows + sales_rows

        # Keep only the most recent full forecast run to support stable, fast reads.
        connection.execute(delete(forecast_outputs))
        if all_rows:
            connection.execute(forecast_outputs.insert(), all_rows)

    return ForecastJobSummary(
        generated_at=generated_at,
        lead_time_series=lead_series_count,
        sales_series=sales_series_count,
        rows_written=len(all_rows),
    )


def _load_lead_time_history(
    connection: Connection,
    lookback_start: datetime,
) -> dict[str, dict[date, float]]:
    stmt = select(
        ic_orders.c.part_no,
        ic_orders.c.date_entered,
        ic_orders.c.complete_date,
        ic_orders.c.rowstate,
    ).where(
        ic_orders.c.date_entered >= lookback_start,
        ic_orders.c.complete_date.is_not(None),
        ic_orders.c.complete_date > ic_orders.c.date_entered,
        ic_orders.c.rowstate == "Closed",
    )
    raw_rows = connection.execute(stmt).mappings().all()

    part_bucket_values: dict[str, dict[date, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for row in raw_rows:
        part_no = row["part_no"] or "__UNKNOWN__"
        entered_at = _coerce_datetime(row["date_entered"])
        completed_at = _coerce_datetime(row["complete_date"])
        lead_days = (completed_at - entered_at).days
        if lead_days < 0:
            continue
        part_bucket_values[part_no][entered_at.date()].append(float(lead_days))

    result: dict[str, dict[date, float]] = {}
    for part_no, bucket_map in part_bucket_values.items():
        result[part_no] = {
            bucket: float(np.mean(values)) for bucket, values in bucket_map.items()
        }

    # Aggregate all parts into a global series for high-level KPIs.
    global_buckets: dict[date, list[float]] = defaultdict(list)
    for bucket_map in result.values():
        for bucket, value in bucket_map.items():
            global_buckets[bucket].append(value)
    result["__ALL__"] = {
        bucket: float(np.mean(values)) for bucket, values in global_buckets.items()
    }
    return result


def _load_sales_history(
    connection: Connection,
    lookback_start: date,
) -> dict[str, dict[date, float]]:
    stmt = select(
        sales_history.c.part_no,
        sales_history.c.sale_date,
        sales_history.c.quantity,
    ).where(sales_history.c.sale_date >= lookback_start)
    raw_rows = connection.execute(stmt).mappings().all()

    part_bucket_values: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    global_buckets: dict[date, float] = defaultdict(float)

    for row in raw_rows:
        part_no = row["part_no"] or "__UNKNOWN__"
        sale_day = _coerce_date(row["sale_date"])
        month_start = date(sale_day.year, sale_day.month, 1)
        quantity = float(row["quantity"])
        part_bucket_values[part_no][month_start] += quantity
        global_buckets[month_start] += quantity

    result: dict[str, dict[date, float]] = {
        part_no: dict(bucket_map) for part_no, bucket_map in part_bucket_values.items()
    }
    result["__ALL__"] = dict(global_buckets)
    return result


def _build_forecast_rows(
    domain: str,
    frequency: str,
    history_by_series: dict[str, dict[date, float]],
    generated_at: datetime,
    horizon: int,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    series_count = 0
    model_version = "baseline+mc-v1"

    for series_key, bucket_map in sorted(history_by_series.items()):
        ordered = sorted(bucket_map.items(), key=lambda item: item[0])
        if len(ordered) < 3:
            continue

        history = [value for _, value in ordered]
        baseline = generate_baseline_forecast(history, horizon=horizon)
        quantiles = simulate_quantiles(
            history=history,
            baseline=baseline,
            simulations=settings.forecast_simulations,
            seed=settings.forecast_random_seed + _series_seed(series_key),
        )
        series_count += 1

        window_start = as_datetime(ordered[0][0])
        window_end = as_datetime(ordered[-1][0])

        for step in range(horizon):
            timestamp = _next_bucket(
                last_bucket=ordered[-1][0],
                steps_ahead=step + 1,
                frequency=frequency,
            )
            rows.append(
                {
                    "domain": domain,
                    "series_key": series_key,
                    "timestamp": as_datetime(timestamp),
                    "value": float(baseline[step]),
                    "p10": float(quantiles["p10"][step]),
                    "p50": float(quantiles["p50"][step]),
                    "p90": float(quantiles["p90"][step]),
                    "generated_at": generated_at,
                    "model_version": model_version,
                    "source_window_start": window_start,
                    "source_window_end": window_end,
                    "notes": json.dumps({"frequency": frequency}),
                }
            )

    return rows, series_count


def _series_seed(series_key: str) -> int:
    digest = hashlib.sha256(series_key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _next_bucket(last_bucket: date, steps_ahead: int, frequency: str) -> date:
    if frequency == "daily":
        return last_bucket + timedelta(days=steps_ahead)
    if frequency == "monthly":
        return _add_months(last_bucket, steps_ahead)
    raise ValueError(f"Unsupported frequency '{frequency}'")


def _add_months(day: date, months: int) -> date:
    month_index = (day.month - 1) + months
    year = day.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", ""))
    raise TypeError(f"Unsupported datetime value type: {type(value).__name__}")


def _coerce_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"Unsupported date value type: {type(value).__name__}")
