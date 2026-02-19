from __future__ import annotations

from typing import Sequence

import numpy as np


def simulate_quantiles(
    history: Sequence[float],
    baseline: np.ndarray,
    simulations: int = 1000,
    seed: int | None = None,
) -> dict[str, np.ndarray]:
    if simulations < 100:
        simulations = 100

    history_values = np.asarray([float(value) for value in history if value is not None], dtype=float)
    if history_values.size == 0:
        history_values = np.asarray([0.0], dtype=float)

    if history_values.size >= 2:
        volatility = float(np.std(np.diff(history_values)))
    else:
        volatility = float(np.std(history_values))

    if volatility <= 0:
        volatility = max(float(np.std(history_values)) * 0.1, 0.5)

    rng = np.random.default_rng(seed)
    simulation_matrix = rng.normal(
        loc=baseline,
        scale=volatility,
        size=(simulations, baseline.size),
    )
    simulation_matrix = np.clip(simulation_matrix, 0.0, None)

    return {
        "p10": np.percentile(simulation_matrix, 10, axis=0),
        "p50": np.percentile(simulation_matrix, 50, axis=0),
        "p90": np.percentile(simulation_matrix, 90, axis=0),
    }
