from __future__ import annotations

from typing import Sequence

import numpy as np


def generate_baseline_forecast(history: Sequence[float], horizon: int) -> np.ndarray:
    cleaned = np.asarray([float(value) for value in history if value is not None], dtype=float)
    if cleaned.size == 0:
        cleaned = np.asarray([0.0], dtype=float)

    recent_window = cleaned[-min(12, cleaned.size) :]
    recent_level = float(np.mean(recent_window))

    if cleaned.size >= 2:
        x = np.arange(cleaned.size, dtype=float)
        slope, intercept = np.polyfit(x, cleaned, 1)
    else:
        slope, intercept = 0.0, float(cleaned[-1])

    forecast = []
    for step in range(1, horizon + 1):
        trend_value = intercept + slope * (cleaned.size - 1 + step)
        projected = (0.65 * recent_level) + (0.35 * trend_value)
        forecast.append(max(projected, 0.0))

    return np.asarray(forecast, dtype=float)
