"""
Blacklist MCP Server.

Provides tools to check whether cards, devices, or merchants appear
on known blacklists.  Uses the infrastructure cache (InMemoryCache)
as the backing store, with pre-seeded blacklist data.

Tools:
- check_card_blacklist(card_id) → bool
- check_device_blacklist(device_id) → bool
- check_merchant_blacklist(merchant_id) → bool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.infrastructure.cache import InMemoryCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-seeded blacklist data
# ---------------------------------------------------------------------------

BLACKLISTED_CARDS: list[str] = [
    "card_stolen_001",
    "card_stolen_002",
    "card_compromised_003",
    "card_cloned_004",
    "card_reported_005",
]

BLACKLISTED_DEVICES: list[str] = [
    "device_botnet_001",
    "device_fraud_002",
    "device_suspicious_003",
    "device_emulator_004",
    "device_rooted_005",
]

BLACKLISTED_MERCHANTS: list[str] = [
    "merchant_scam_001",
    "merchant_fraud_002",
    "merchant_shell_003",
    "merchant_mule_004",
]

# Cache key constants
_CARD_BLACKLIST_KEY = "blacklist:cards"
_DEVICE_BLACKLIST_KEY = "blacklist:devices"
_MERCHANT_BLACKLIST_KEY = "blacklist:merchants"

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

blacklist_server = FastMCP("blacklist-server")

# Shared cache reference — set via ``init_blacklist_server``
_cache: InMemoryCache | None = None


async def init_blacklist_server(cache: InMemoryCache) -> None:
    """Initialise the blacklist server by seeding data into *cache*.

    Args:
        cache: The shared InMemoryCache instance.
    """
    global _cache
    _cache = cache

    # Seed blacklists into cache sets
    if BLACKLISTED_CARDS:
        await cache.sadd(_CARD_BLACKLIST_KEY, *BLACKLISTED_CARDS)
    if BLACKLISTED_DEVICES:
        await cache.sadd(_DEVICE_BLACKLIST_KEY, *BLACKLISTED_DEVICES)
    if BLACKLISTED_MERCHANTS:
        await cache.sadd(_MERCHANT_BLACKLIST_KEY, *BLACKLISTED_MERCHANTS)

    logger.info(
        "Blacklist server initialised: %d cards, %d devices, %d merchants",
        len(BLACKLISTED_CARDS),
        len(BLACKLISTED_DEVICES),
        len(BLACKLISTED_MERCHANTS),
    )


def _get_cache() -> InMemoryCache:
    assert _cache is not None, "Blacklist server not initialised — call init_blacklist_server first"
    return _cache


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@blacklist_server.tool()
async def check_card_blacklist(card_id: str) -> dict[str, Any]:
    """Check if a card ID is on the blacklist.

    Args:
        card_id: The card identifier to check.

    Returns:
        Dict with ``blacklisted`` (bool) and ``card_id``.
    """
    cache = _get_cache()
    is_blacklisted = await cache.sismember(_CARD_BLACKLIST_KEY, card_id)
    logger.debug("Card %s blacklist check: %s", card_id, is_blacklisted)
    return {
        "card_id": card_id,
        "blacklisted": is_blacklisted,
        "list_type": "card",
    }


@blacklist_server.tool()
async def check_device_blacklist(device_id: str) -> dict[str, Any]:
    """Check if a device ID is on the blacklist.

    Args:
        device_id: The device identifier to check.

    Returns:
        Dict with ``blacklisted`` (bool) and ``device_id``.
    """
    cache = _get_cache()
    is_blacklisted = await cache.sismember(_DEVICE_BLACKLIST_KEY, device_id)
    logger.debug("Device %s blacklist check: %s", device_id, is_blacklisted)
    return {
        "device_id": device_id,
        "blacklisted": is_blacklisted,
        "list_type": "device",
    }


@blacklist_server.tool()
async def check_merchant_blacklist(merchant_id: str) -> dict[str, Any]:
    """Check if a merchant ID is on the blacklist.

    Args:
        merchant_id: The merchant identifier to check.

    Returns:
        Dict with ``blacklisted`` (bool) and ``merchant_id``.
    """
    cache = _get_cache()
    is_blacklisted = await cache.sismember(_MERCHANT_BLACKLIST_KEY, merchant_id)
    logger.debug("Merchant %s blacklist check: %s", merchant_id, is_blacklisted)
    return {
        "merchant_id": merchant_id,
        "blacklisted": is_blacklisted,
        "list_type": "merchant",
    }
