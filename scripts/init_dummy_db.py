from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_service.config import settings
from mcp_service.database import (
    forecast_outputs,
    get_connection,
    ic_orders,
    initialize_schema,
    part_master,
    sales_history,
)


def seed_dummy_data(order_count: int, part_count: int) -> None:
    initialize_schema()
    randomizer = random.Random(settings.forecast_random_seed)

    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    start_date = now - timedelta(days=730)
    total_days = (now - start_date).days

    categories = ("Aerospace", "Defense", "MRO", "Industrial")
    parts = []
    for idx in range(1, part_count + 1):
        part_no = f"PART-{idx:04d}"
        parts.append(
            {
                "part_no": part_no,
                "part_description": f"Component {idx}",
                "part_category": categories[idx % len(categories)],
            }
        )

    orders = []
    sales = []
    for idx in range(1, order_count + 1):
        part = randomizer.choice(parts)
        entered = start_date + timedelta(days=randomizer.randint(0, total_days))
        planned_lead = max(2, int(randomizer.gauss(mu=18, sigma=5)))
        completed = entered + timedelta(days=planned_lead)
        is_closed = completed < (now - timedelta(days=2))
        need_date = entered + timedelta(days=max(7, planned_lead - 2))

        orders.append(
            {
                "order_no": f"ORD-{idx:07d}",
                "line_no": 1,
                "part_no": part["part_no"],
                "date_entered": entered,
                "need_date": need_date,
                "org_start_date": entered + timedelta(days=1),
                "revised_start_date": entered + timedelta(days=randomizer.randint(1, 3)),
                "complete_date": completed if is_closed else None,
                "real_ship_date": completed + timedelta(days=1) if is_closed else None,
                "division": f"DIV-{(idx % 3) + 1}",
                "rowstate": "Closed" if is_closed else "Released",
            }
        )

        if is_closed:
            sales.append(
                {
                    "part_no": part["part_no"],
                    "sale_date": completed.date(),
                    "quantity": round(max(1.0, randomizer.gauss(mu=30.0, sigma=12.0)), 2),
                }
            )

    with get_connection() as connection:
        connection.execute(delete(forecast_outputs))
        connection.execute(delete(sales_history))
        connection.execute(delete(ic_orders))
        connection.execute(delete(part_master))
        connection.execute(part_master.insert(), parts)
        connection.execute(ic_orders.insert(), orders)
        if sales:
            connection.execute(sales_history.insert(), sales)

    print(
        f"Seeded dummy dataset with {len(parts)} parts, "
        f"{len(orders)} orders, and {len(sales)} sales rows."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed dummy data for forecast MCP service.")
    parser.add_argument("--orders", type=int, default=500, help="Number of dummy orders.")
    parser.add_argument("--parts", type=int, default=20, help="Number of dummy parts.")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    seed_dummy_data(order_count=arguments.orders, part_count=arguments.parts)
