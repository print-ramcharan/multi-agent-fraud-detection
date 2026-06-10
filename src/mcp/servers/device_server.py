"""
Device MCP Server.

Provides tools for device fingerprint analysis:
- get_device_profile(device_id)        → device metadata
- check_device_sharing(device_id)      → whether device is shared across customers
- get_device_age(device_id)            → age in days since first seen

Pre-seeded with device profiles of varying risk levels.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-seeded device database
# ---------------------------------------------------------------------------

_DEVICE_DB: dict[str, dict[str, Any]] = {
    # Known safe devices
    "device_789": {
        "device_id": "device_789",
        "device_type": "mobile",
        "os": "iOS 17.5",
        "browser": "Safari",
        "owner_customer_id": "cust_123",
        "associated_customers": ["cust_123"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.05,
    },
    "device_456_plat": {
        "device_id": "device_456_plat",
        "device_type": "desktop",
        "os": "macOS 15.1",
        "browser": "Chrome 126",
        "owner_customer_id": "cust_456",
        "associated_customers": ["cust_456"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=900)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.02,
    },
    "device_gold_102": {
        "device_id": "device_gold_102",
        "device_type": "mobile",
        "os": "Android 14",
        "browser": "Chrome Mobile",
        "owner_customer_id": "cust_102",
        "associated_customers": ["cust_102"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=500)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.08,
    },
    "device_silver_105": {
        "device_id": "device_silver_105",
        "device_type": "desktop",
        "os": "Windows 11",
        "browser": "Firefox 127",
        "owner_customer_id": "cust_105",
        "associated_customers": ["cust_105"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.10,
    },
    "device_plat_112": {
        "device_id": "device_plat_112",
        "device_type": "mobile",
        "os": "iOS 18.0",
        "browser": "Safari",
        "owner_customer_id": "cust_112",
        "associated_customers": ["cust_112"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=730)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.03,
    },
    # New device (high risk due to age)
    "device_new_001": {
        "device_id": "device_new_001",
        "device_type": "mobile",
        "os": "Android 14",
        "browser": "Chrome Mobile",
        "owner_customer_id": "cust_789",
        "associated_customers": ["cust_789"],
        "first_seen": datetime.now(timezone.utc).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.45,
    },
    "device_new_107": {
        "device_id": "device_new_107",
        "device_type": "mobile",
        "os": "Android 15",
        "browser": "Samsung Internet",
        "owner_customer_id": "cust_107",
        "associated_customers": ["cust_107"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.40,
    },
    # Shared device (multiple customers → suspicious)
    "device_shared_001": {
        "device_id": "device_shared_001",
        "device_type": "desktop",
        "os": "Windows 10",
        "browser": "Chrome 125",
        "owner_customer_id": "cust_bad",
        "associated_customers": ["cust_bad", "cust_108", "cust_116"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": False,
        "risk_score": 0.70,
    },
    "device_shared_002": {
        "device_id": "device_shared_002",
        "device_type": "mobile",
        "os": "Android 13",
        "browser": "Chrome Mobile",
        "owner_customer_id": "cust_104",
        "associated_customers": ["cust_104", "cust_111"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.55,
    },
    # Rooted/emulated devices (high risk)
    "device_rooted_001": {
        "device_id": "device_rooted_001",
        "device_type": "mobile",
        "os": "Android 12 (Rooted)",
        "browser": "Chrome Mobile",
        "owner_customer_id": "cust_116",
        "associated_customers": ["cust_116"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "is_rooted": True,
        "is_emulator": False,
        "fingerprint_stable": False,
        "risk_score": 0.75,
    },
    "device_emulator_001": {
        "device_id": "device_emulator_001",
        "device_type": "emulator",
        "os": "Android Emulator",
        "browser": "Chrome",
        "owner_customer_id": "cust_bad",
        "associated_customers": ["cust_bad"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "is_rooted": False,
        "is_emulator": True,
        "fingerprint_stable": False,
        "risk_score": 0.85,
    },
    # Stable long-lived devices
    "device_gold_110": {
        "device_id": "device_gold_110",
        "device_type": "tablet",
        "os": "iPadOS 17.5",
        "browser": "Safari",
        "owner_customer_id": "cust_110",
        "associated_customers": ["cust_110"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=450)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.06,
    },
    "device_gold_115": {
        "device_id": "device_gold_115",
        "device_type": "desktop",
        "os": "macOS 14.6",
        "browser": "Safari 18",
        "owner_customer_id": "cust_115",
        "associated_customers": ["cust_115"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=600)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.04,
    },
    "device_silver_109": {
        "device_id": "device_silver_109",
        "device_type": "mobile",
        "os": "Android 14",
        "browser": "Chrome Mobile",
        "owner_customer_id": "cust_109",
        "associated_customers": ["cust_109"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=300)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.12,
    },
    "device_std_113": {
        "device_id": "device_std_113",
        "device_type": "mobile",
        "os": "HarmonyOS 4",
        "browser": "Huawei Browser",
        "owner_customer_id": "cust_113",
        "associated_customers": ["cust_113"],
        "first_seen": (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
        "last_seen": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
        "is_rooted": False,
        "is_emulator": False,
        "fingerprint_stable": True,
        "risk_score": 0.18,
    },
}


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

device_server = FastMCP("device-server")


@device_server.tool()
async def get_device_profile(device_id: str) -> dict[str, Any]:
    """Retrieve the full device profile.

    Args:
        device_id: The device fingerprint identifier.

    Returns:
        Device profile dict, or an error dict if not found.
    """
    device = _DEVICE_DB.get(device_id)
    if device is None:
        logger.warning("Device not found: %s", device_id)
        return {
            "error": "device_not_found",
            "device_id": device_id,
            "new_device": True,
            "risk_score": 0.5,
        }
    return dict(device)


@device_server.tool()
async def check_device_sharing(device_id: str) -> dict[str, Any]:
    """Check whether a device is shared across multiple customers.

    Args:
        device_id: The device fingerprint identifier.

    Returns:
        Dict with ``shared`` (bool), number of associated customers, and list.
    """
    device = _DEVICE_DB.get(device_id)
    if device is None:
        return {
            "device_id": device_id,
            "shared": False,
            "customer_count": 0,
            "associated_customers": [],
            "note": "unknown_device",
        }

    customers = device.get("associated_customers", [])
    shared = len(customers) > 1

    return {
        "device_id": device_id,
        "shared": shared,
        "customer_count": len(customers),
        "associated_customers": customers,
        "owner": device.get("owner_customer_id", ""),
    }


@device_server.tool()
async def get_device_age(device_id: str) -> dict[str, Any]:
    """Get the age of a device in days since first seen.

    Args:
        device_id: The device fingerprint identifier.

    Returns:
        Dict with ``age_days``, ``first_seen``, and ``last_seen``.
    """
    device = _DEVICE_DB.get(device_id)
    if device is None:
        return {
            "device_id": device_id,
            "age_days": 0,
            "new_device": True,
        }

    first_seen = datetime.fromisoformat(device["first_seen"])
    last_seen = datetime.fromisoformat(device["last_seen"])
    age_days = (datetime.now(timezone.utc) - first_seen).days

    return {
        "device_id": device_id,
        "age_days": age_days,
        "first_seen": device["first_seen"],
        "last_seen": device["last_seen"],
        "new_device": age_days < 7,
        "device_type": device.get("device_type", "unknown"),
    }
