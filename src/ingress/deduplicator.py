"""
Idempotency and Deduplication logic.
"""

from __future__ import annotations

import logging
from typing import Any
from src.infrastructure.cache import InMemoryCache

logger = logging.getLogger(__name__)

class IngressDeduplicator:
    """Detects and returns cached results for duplicate transaction IDs."""

    def __init__(self, cache: InMemoryCache, ttl_seconds: int = 300):
        self.cache = cache
        self.ttl = ttl_seconds

    async def is_duplicate(self, transaction_id: str) -> tuple[bool, Any | None]:
        """Check cache for transaction_id. If exists, returns True and the cached decision."""
        cache_key = f"dedup:{transaction_id}"
        exists = await self.cache.exists(cache_key)
        if exists:
            logger.info("Duplicate transaction detected for transaction_id %s", transaction_id)
            val = await self.cache.get(cache_key)
            return True, val
        return False, None

    async def register_decision(self, transaction_id: str, decision: Any) -> None:
        """Register the final decision to prevent double-processing."""
        cache_key = f"dedup:{transaction_id}"
        await self.cache.set(cache_key, decision, ttl=self.ttl)
