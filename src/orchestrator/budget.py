"""
Latency budget tracker.

Enforces execution bounds aligned with the 100ms end-to-end SLA.
"""

from __future__ import annotations

import time

class LatencyBudget:
    """Tracks latency consumption against allocated budgets."""

    def __init__(self, limit_ms: float):
        self.limit_ms = limit_ms
        self.start_time = time.perf_counter()
        self.allocated_ms: dict[str, float] = {}
        self.consumed_ms: dict[str, float] = {}

    def remaining_ms(self) -> float:
        """Calculate remaining time in budget."""
        elapsed = (time.perf_counter() - self.start_time) * 1000.0
        return max(0.0, self.limit_ms - elapsed)

    def elapsed_ms(self) -> float:
        """Get total elapsed time since tracker start."""
        return (time.perf_counter() - self.start_time) * 1000.0

    def is_expired(self) -> bool:
        """Check if budget is exhausted."""
        return self.elapsed_ms() >= self.limit_ms
