"""
Infrastructure abstractions for the fraud detection platform.

Provides in-memory implementations of cache, event bus, audit store,
and metrics that mirror production Redis/Kafka/PostgreSQL/Prometheus
interfaces for local development and testing.
"""

from __future__ import annotations

from src.infrastructure.cache import InMemoryCache
from src.infrastructure.event_bus import InMemoryEventBus
from src.infrastructure.audit_store import SQLiteAuditStore
from src.infrastructure.metrics import MetricsCollector

__all__ = [
    "InMemoryCache",
    "InMemoryEventBus",
    "SQLiteAuditStore",
    "MetricsCollector",
]
