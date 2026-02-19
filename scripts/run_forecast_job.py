from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_service.forecasting.jobs import run_forecast_job


if __name__ == "__main__":
    summary = run_forecast_job()
    print(json.dumps(summary.to_dict(), indent=2))
