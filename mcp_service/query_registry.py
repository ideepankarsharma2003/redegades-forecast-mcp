from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QueryDefinition:
    query_id: str
    description: str
    sql: str
    allowed_params: tuple[str, ...]
    required_params: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)


def _lead_time_expression(dialect_name: str) -> str:
    if dialect_name.startswith("mssql"):
        return "DATEDIFF(day, o.date_entered, o.complete_date)"
    return "CAST((julianday(o.complete_date) - julianday(o.date_entered)) AS INTEGER)"


def _month_start_expression(dialect_name: str) -> str:
    if dialect_name.startswith("mssql"):
        return "DATEFROMPARTS(YEAR(s.sale_date), MONTH(s.sale_date), 1)"
    return "strftime('%Y-%m-01', s.sale_date)"


def get_query_registry(dialect_name: str) -> dict[str, QueryDefinition]:
    lead_time_days = _lead_time_expression(dialect_name)
    sales_month_start = _month_start_expression(dialect_name)

    return {
        "ic_orders_lead_time_extract": QueryDefinition(
            query_id="ic_orders_lead_time_extract",
            description=(
                "Lead-time extract for closed orders with part metadata. "
                "Use this as the primary input for lead-time forecasting."
            ),
            allowed_params=("start_date", "part_no"),
            required_params=("start_date",),
            defaults={"part_no": None},
            sql=f"""
                SELECT
                    o.order_no,
                    o.line_no,
                    o.part_no,
                    o.date_entered,
                    o.need_date,
                    o.org_start_date,
                    o.revised_start_date,
                    o.complete_date,
                    o.real_ship_date,
                    {lead_time_days} AS lead_time_days,
                    o.division,
                    o.rowstate,
                    p.part_description,
                    p.part_category
                FROM ic_orders o
                LEFT JOIN part_master p
                    ON o.part_no = p.part_no
                WHERE
                    o.rowstate = 'Closed'
                    AND o.date_entered >= :start_date
                    AND o.complete_date IS NOT NULL
                    AND o.complete_date > o.date_entered
                    AND (:part_no IS NULL OR o.part_no = :part_no)
                ORDER BY o.date_entered ASC
            """.strip(),
        ),
        "sales_monthly_history": QueryDefinition(
            query_id="sales_monthly_history",
            description="Monthly part-level sales history from order quantity records.",
            allowed_params=("start_date", "part_no"),
            required_params=("start_date",),
            defaults={"part_no": None},
            sql=f"""
                SELECT
                    s.part_no,
                    {sales_month_start} AS month_start,
                    SUM(s.quantity) AS quantity
                FROM sales_history s
                WHERE
                    s.sale_date >= :start_date
                    AND (:part_no IS NULL OR s.part_no = :part_no)
                GROUP BY
                    s.part_no,
                    {sales_month_start}
                ORDER BY month_start ASC, s.part_no ASC
            """.strip(),
        ),
        "precomputed_forecast_values": QueryDefinition(
            query_id="precomputed_forecast_values",
            description=(
                "Reads forecast rows precomputed by scheduler. "
                "Use for low-latency agent and reporting queries."
            ),
            allowed_params=("domain", "series_key"),
            required_params=("domain", "series_key"),
            sql="""
                SELECT
                    domain,
                    series_key,
                    timestamp,
                    value,
                    p10,
                    p50,
                    p90,
                    generated_at,
                    model_version
                FROM forecast_outputs
                WHERE
                    domain = :domain
                    AND series_key = :series_key
                ORDER BY generated_at DESC, timestamp DESC
            """.strip(),
        ),
    }
