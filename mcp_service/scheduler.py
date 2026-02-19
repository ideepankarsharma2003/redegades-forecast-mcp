from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from mcp_service.config import settings
from mcp_service.forecasting.jobs import run_forecast_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("forecast-scheduler")


def _run_single_job() -> None:
    summary = run_forecast_job()
    logger.info("Forecast job completed: %s", summary.to_dict())


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _run_single_job,
        CronTrigger.from_crontab(settings.forecast_cron),
        id="daily-forecast-job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    if settings.forecast_run_on_start:
        _run_single_job()

    logger.info("Scheduler started with cron expression: %s", settings.forecast_cron)
    scheduler.start()


if __name__ == "__main__":
    main()
