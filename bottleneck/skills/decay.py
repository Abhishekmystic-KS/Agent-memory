"""Decay functions for scoring memory recency.
"""

import math

def compute_recency_score(
    created_at_epoch: float,
    current_time_epoch: float,
    decay_function: str = "exponential",
    decay_rate: float = 0.005,
) -> float:
    """Computes a recency score in [0.0, 1.0] based on delta time in hours."""
    delta_t_seconds = max(current_time_epoch - created_at_epoch, 0.0)
    delta_t_hours = delta_t_seconds / 3600.0

    decay_func = decay_function.lower().strip()

    if decay_func == "none":
        return 1.0

    if decay_func == "exponential":
        return math.exp(-decay_rate * delta_t_hours)

    if decay_func == "linear":
        return max(1.0 - decay_rate * delta_t_hours, 0.0)

    if decay_func == "step":
        # Tiers relative to hours (simulation-friendly)
        # < 2 hours: fresh (1.0)
        # < 12 hours: recent (0.7)
        # < 48 hours: moderate (0.4)
        # older: stale (0.1)
        if delta_t_hours < 2.0:
            return 1.0
        if delta_t_hours < 12.0:
            return 0.7
        if delta_t_hours < 48.0:
            return 0.4
        return 0.1

    # Default to exponential
    return math.exp(-decay_rate * delta_t_hours)
