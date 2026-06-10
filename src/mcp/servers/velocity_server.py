"""
Velocity MCP Server.

Provides tools for transaction velocity analysis using sliding windows
backed by the InMemoryCache sorted-set operations.

Tools:
- get_transaction_velocity(customer_id, window_seconds?) → tx count in window
- get_amount_velocity(customer_id, window_seconds?)      → total amount in window

Velocity data is stored as sorted sets keyed by customer,
with scores = UNIX timestamp of each transaction.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.infrastructure.cache import InMemoryCache

logger = logging.getLogger(__name__)

# Cache key templates
_TXN_VELOCITY_KEY = "velocity:txn:{customer_id}"
_AMT_VELOCITY_KEY = "velocity:amt:{customer_id}"

# Default windows
DEFAULT_HOUR_WINDOW = 3600
DEFAULT_DAY_WINDOW = 86400

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

velocity_server = FastMCP("velocity-server")

_cache: InMemoryCache | None = None


async def init_velocity_server(cache: InMemoryCache) -> None:
    """Initialise the velocity server with a shared cache.

    Args:
        cache: The shared InMemoryCache instance.
    """
    global _cache
    _cache = cache
    logger.info("Velocity server initialised.")


def _get_cache() -> InMemoryCache:
    assert _cache is not None, "Velocity server not initialised — call init_velocity_server first"
    return _cache


async def record_transaction(
    customer_id: str, amount_usd: float, timestamp: float | None = None
) -> None:
    """Record a transaction for velocity tracking.

    Called by the pipeline when a new transaction is ingested so that
    velocity windows stay current.

    Args:
        customer_id: The customer identifier.
        amount_usd: Transaction amount in USD.
        timestamp: UNIX epoch; defaults to now.
    """
    cache = _get_cache()
    ts = timestamp or time.time()
    member_id = f"{ts}:{uuid.uuid4().hex[:8]}"

    txn_key = _TXN_VELOCITY_KEY.format(customer_id=customer_id)
    amt_key = _AMT_VELOCITY_KEY.format(customer_id=customer_id)

    await cache.zadd(txn_key, {member_id: ts})
    await cache.zadd(amt_key, {f"{member_id}:{amount_usd}": ts})

    # Expire old entries outside the day window (cleanup)
    cutoff = ts - DEFAULT_DAY_WINDOW
    await cache.zremrangebyscore(txn_key, 0, cutoff)
    await cache.zremrangebyscore(amt_key, 0, cutoff)


@velocity_server.tool()
async def get_transaction_velocity(
    customer_id: str,
    window_seconds: int = DEFAULT_HOUR_WINDOW,
) -> dict[str, Any]:
    """Get the number of transactions in a sliding time window.

    Args:
        customer_id: The customer identifier.
        window_seconds: Lookback window in seconds (default: 3600 = 1 hour).

    Returns:
        Dict with ``customer_id``, ``window_seconds``, ``transaction_count``,
        and ``transactions_per_minute``.
    """
    cache = _get_cache()
    now = time.time()
    cutoff = now - window_seconds

    txn_key = _TXN_VELOCITY_KEY.format(customer_id=customer_id)
    members = await cache.zrangebyscore(txn_key, cutoff, now)
    count = len(members)

    # Also compute the day-window count for context
    day_key = _TXN_VELOCITY_KEY.format(customer_id=customer_id)
    day_members = await cache.zrangebyscore(
        day_key, now - DEFAULT_DAY_WINDOW, now
    )

    return {
        "customer_id": customer_id,
        "window_seconds": window_seconds,
        "transaction_count": count,
        "transactions_per_minute": round(count / max(window_seconds / 60, 1), 4),
        "transactions_last_day": len(day_members),
    }


@velocity_server.tool()
async def get_amount_velocity(
    customer_id: str,
    window_seconds: int = DEFAULT_HOUR_WINDOW,
) -> dict[str, Any]:
    """Get the total transaction amount in a sliding time window.

    Args:
        customer_id: The customer identifier.
        window_seconds: Lookback window in seconds (default: 3600 = 1 hour).

    Returns:
        Dict with ``customer_id``, ``window_seconds``, ``total_amount_usd``,
        ``transaction_count``, and ``avg_amount_usd``.
    """
    cache = _get_cache()
    now = time.time()
    cutoff = now - window_seconds

    amt_key = _AMT_VELOCITY_KEY.format(customer_id=customer_id)
    members = await cache.zrangebyscore(amt_key, cutoff, now)

    # Parse amounts from member IDs (format: "ts:hex:amount")
    total_amount = 0.0
    for member in members:
        parts = member.rsplit(":", 1)
        if len(parts) == 2:
            try:
                total_amount += float(parts[1])
            except ValueError:
                pass

    count = len(members)

    # Day-window totals
    day_members = await cache.zrangebyscore(
        amt_key, now - DEFAULT_DAY_WINDOW, now
    )
    day_total = 0.0
    for member in day_members:
        parts = member.rsplit(":", 1)
        if len(parts) == 2:
            try:
                day_total += float(parts[1])
            except ValueError:
                pass

    return {
        "customer_id": customer_id,
        "window_seconds": window_seconds,
        "total_amount_usd": round(total_amount, 2),
        "transaction_count": count,
        "avg_amount_usd": round(total_amount / count, 2) if count else 0.0,
        "amount_last_day_usd": round(day_total, 2),
        "transactions_last_day": len(day_members),
    }
