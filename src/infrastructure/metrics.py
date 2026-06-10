"""
Prometheus-compatible metrics collector.

Provides counters, histograms, and gauges for observability.
Uses a simple in-memory implementation that can be swapped for
``prometheus_client`` in production.

Pre-defined metrics:
  Counters:
    - transactions_total
    - decisions_total
    - agent_errors_total
  Histograms:
    - transaction_latency_ms
    - agent_latency_ms
  Gauges:
    - active_transactions
    - circuit_breaker_state
"""

from __future__ import annotations

import math
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Metric primitives
# ------------------------------------------------------------------

class Counter:
    """Monotonically increasing counter (mirrors Prometheus Counter)."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[str, float] = {}  # label_key → count

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the counter."""
        key = self._label_key(labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Read the current value."""
        return self._values.get(self._label_key(labels), 0.0)

    def reset(self) -> None:
        """Reset all values (testing only)."""
        self._values.clear()

    @staticmethod
    def _label_key(labels: dict[str, str] | None) -> str:
        if not labels:
            return "__default__"
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def snapshot(self) -> dict[str, float]:
        """Return a copy of all label→value pairs."""
        return dict(self._values)


class Histogram:
    """Distribution tracker with pre-defined buckets (mirrors Prometheus Histogram)."""

    DEFAULT_BUCKETS = (5, 10, 25, 50, 75, 100, 250, 500, 1000, float("inf"))

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._values: dict[str, list[float]] = {}  # label_key → observed values

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record an observation."""
        key = Counter._label_key(labels)
        self._values.setdefault(key, []).append(value)

    def get_count(self, labels: dict[str, str] | None = None) -> int:
        """Total number of observations."""
        return len(self._values.get(Counter._label_key(labels), []))

    def get_sum(self, labels: dict[str, str] | None = None) -> float:
        """Sum of all observations."""
        return sum(self._values.get(Counter._label_key(labels), []))

    def get_avg(self, labels: dict[str, str] | None = None) -> float:
        """Mean of observations."""
        vals = self._values.get(Counter._label_key(labels), [])
        return sum(vals) / len(vals) if vals else 0.0

    def get_percentile(
        self, percentile: float, labels: dict[str, str] | None = None
    ) -> float:
        """Return the *percentile*-th percentile (0–100)."""
        vals = sorted(self._values.get(Counter._label_key(labels), []))
        if not vals:
            return 0.0
        k = (len(vals) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return vals[int(k)]
        return vals[f] * (c - k) + vals[c] * (k - f)

    def get_bucket_counts(
        self, labels: dict[str, str] | None = None
    ) -> dict[str, int]:
        """Return cumulative bucket counts (Prometheus-style)."""
        vals = self._values.get(Counter._label_key(labels), [])
        result: dict[str, int] = {}
        for bound in self._buckets:
            label = f"le={bound}" if not math.isinf(bound) else "le=+Inf"
            result[label] = sum(1 for v in vals if v <= bound)
        return result

    def reset(self) -> None:
        self._values.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a summary of all observations."""
        out: dict[str, Any] = {}
        for key, vals in self._values.items():
            out[key] = {
                "count": len(vals),
                "sum": sum(vals),
                "avg": sum(vals) / len(vals) if vals else 0.0,
                "p50": self.get_percentile(50, None if key == "__default__" else None),
                "p95": self.get_percentile(95, None if key == "__default__" else None),
                "p99": self.get_percentile(99, None if key == "__default__" else None),
            }
        return out


class Gauge:
    """Value that can go up and down (mirrors Prometheus Gauge)."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._values: dict[str, float] = {}

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge to a specific value."""
        self._values[Counter._label_key(labels)] = value

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge."""
        key = Counter._label_key(labels)
        self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge."""
        key = Counter._label_key(labels)
        self._values[key] = self._values.get(key, 0.0) - amount

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Read the current value."""
        return self._values.get(Counter._label_key(labels), 0.0)

    def reset(self) -> None:
        self._values.clear()

    def snapshot(self) -> dict[str, float]:
        return dict(self._values)


# ------------------------------------------------------------------
# Singleton collector
# ------------------------------------------------------------------

class MetricsCollector:
    """Central registry of all platform metrics.

    Access metrics via attribute names, e.g.
    ``metrics.transactions_total.inc()``
    """

    def __init__(self) -> None:
        # Counters
        self.transactions_total = Counter(
            "transactions_total",
            "Total transactions processed",
        )
        self.decisions_total = Counter(
            "decisions_total",
            "Total decisions made (labelled by decision type)",
        )
        self.agent_errors_total = Counter(
            "agent_errors_total",
            "Total agent errors (labelled by agent name)",
        )

        # Histograms
        self.transaction_latency_ms = Histogram(
            "transaction_latency_ms",
            "End-to-end transaction processing latency in ms",
        )
        self.agent_latency_ms = Histogram(
            "agent_latency_ms",
            "Per-agent execution latency in ms",
        )

        # Gauges
        self.active_transactions = Gauge(
            "active_transactions",
            "Number of transactions currently in flight",
        )
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "Circuit breaker state per agent (0=closed, 1=open, 0.5=half-open)",
        )

    def increment(self, name: str, labels: dict[str, str] | None = None) -> None:
        """Helper to increment predefined Counter metrics."""
        if name == "transactions_total":
            self.transactions_total.inc(labels=labels)
        elif name.startswith("decisions_total"):
            decision = name.split("_")[-1]
            self.decisions_total.inc(labels={"decision": decision})
        elif name == "agent_errors_total":
            self.agent_errors_total.inc(labels=labels)

    def record_latency(self, elapsed_ms: float) -> None:
        """Helper to record transaction end-to-end latency."""
        self.transaction_latency_ms.observe(elapsed_ms)

    def reset_all(self) -> None:
        """Reset every metric (testing only)."""
        self.transactions_total.reset()
        self.decisions_total.reset()
        self.agent_errors_total.reset()
        self.transaction_latency_ms.reset()
        self.agent_latency_ms.reset()
        self.active_transactions.reset()
        self.circuit_breaker_state.reset()

    def snapshot(self) -> dict[str, Any]:
        """Return a full snapshot of all metrics."""
        return {
            "counters": {
                "transactions_total": self.transactions_total.snapshot(),
                "decisions_total": self.decisions_total.snapshot(),
                "agent_errors_total": self.agent_errors_total.snapshot(),
            },
            "histograms": {
                "transaction_latency_ms": self.transaction_latency_ms.snapshot(),
                "agent_latency_ms": self.agent_latency_ms.snapshot(),
            },
            "gauges": {
                "active_transactions": self.active_transactions.snapshot(),
                "circuit_breaker_state": self.circuit_breaker_state.snapshot(),
            },
        }


# Module-level singleton
_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get or create the singleton MetricsCollector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
