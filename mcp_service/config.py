from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_host: str
    api_port: int
    forecast_cron: str
    forecast_run_on_start: bool
    forecast_horizon_days: int
    forecast_horizon_months: int
    forecast_simulations: int
    forecast_random_seed: int
    history_lookback_days: int
    allowed_query_row_limit: int


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/redegades_forecast.db"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=_int_env("API_PORT", 8080),
        forecast_cron=os.getenv("FORECAST_CRON", "0 3 * * *"),
        forecast_run_on_start=_bool_env("FORECAST_RUN_ON_START", True),
        forecast_horizon_days=_int_env("FORECAST_HORIZON_DAYS", 30),
        forecast_horizon_months=_int_env("FORECAST_HORIZON_MONTHS", 6),
        forecast_simulations=_int_env("FORECAST_SIMULATIONS", 1000),
        forecast_random_seed=_int_env("FORECAST_RANDOM_SEED", 42),
        history_lookback_days=_int_env("HISTORY_LOOKBACK_DAYS", 1460),
        allowed_query_row_limit=_int_env("ALLOWED_QUERY_ROW_LIMIT", 500),
    )


settings = load_settings()
