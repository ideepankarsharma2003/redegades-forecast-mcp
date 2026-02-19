from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.engine import Connection

from mcp_service.config import settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    db_path = database_url.replace("sqlite:///", "", 1)
    if not db_path or db_path == ":memory:":
        return
    absolute_path = Path(db_path)
    if not absolute_path.is_absolute():
        absolute_path = Path.cwd() / absolute_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(settings.database_url)

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

metadata = MetaData()

part_master = Table(
    "part_master",
    metadata,
    Column("part_no", String(64), primary_key=True),
    Column("part_description", String(255), nullable=False),
    Column("part_category", String(64), nullable=False),
)

ic_orders = Table(
    "ic_orders",
    metadata,
    Column("order_no", String(64), primary_key=True),
    Column("line_no", Integer, primary_key=True, nullable=False),
    Column("part_no", String(64), nullable=False),
    Column("date_entered", DateTime, nullable=False),
    Column("need_date", DateTime),
    Column("org_start_date", DateTime),
    Column("revised_start_date", DateTime),
    Column("complete_date", DateTime),
    Column("real_ship_date", DateTime),
    Column("division", String(64)),
    Column("rowstate", String(32), nullable=False),
)

sales_history = Table(
    "sales_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("part_no", String(64), nullable=False),
    Column("sale_date", Date, nullable=False),
    Column("quantity", Float, nullable=False),
)

forecast_outputs = Table(
    "forecast_outputs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("domain", String(64), nullable=False),
    Column("series_key", String(128), nullable=False),
    Column("timestamp", DateTime, nullable=False),
    Column("value", Float, nullable=False),
    Column("p10", Float),
    Column("p50", Float),
    Column("p90", Float),
    Column("generated_at", DateTime, nullable=False),
    Column("model_version", String(64), nullable=False),
    Column("source_window_start", DateTime),
    Column("source_window_end", DateTime),
    Column("notes", Text),
)

Index("ix_ic_orders_part_entered", ic_orders.c.part_no, ic_orders.c.date_entered)
Index("ix_sales_part_date", sales_history.c.part_no, sales_history.c.sale_date)
Index(
    "ix_forecast_lookup",
    forecast_outputs.c.domain,
    forecast_outputs.c.series_key,
    forecast_outputs.c.generated_at,
    forecast_outputs.c.timestamp,
)


def initialize_schema() -> None:
    metadata.create_all(engine)


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    with engine.begin() as connection:
        yield connection


def get_dialect_name() -> str:
    return engine.dialect.name


def as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.min.time())
