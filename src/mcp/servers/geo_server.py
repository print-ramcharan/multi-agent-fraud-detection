"""
Geo MCP Server.

Provides geolocation-based fraud detection tools:
- get_last_location(customer_id)   → last known lat/lon + country
- calculate_distance(lat1, lon1, lat2, lon2) → km (Haversine)
- check_impossible_travel(customer_id, lat, lon, timestamp)

Impossible travel is flagged when the required speed exceeds 900 km/h
(faster than commercial aviation).
"""

from __future__ import annotations

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-seeded last-known locations
# ---------------------------------------------------------------------------

_LAST_LOCATIONS: dict[str, dict[str, Any]] = {
    "cust_123": {
        "latitude": 37.7749, "longitude": -122.4194,
        "country": "US", "city": "San Francisco",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    "cust_456": {
        "latitude": 40.7128, "longitude": -74.0060,
        "country": "US", "city": "New York",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    },
    "cust_789": {
        "latitude": 30.2672, "longitude": -97.7431,
        "country": "US", "city": "Austin",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
    },
    "cust_bad": {
        "latitude": 36.1699, "longitude": -115.1398,
        "country": "US", "city": "Las Vegas",
        "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    },
    "cust_101": {
        "latitude": 19.4326, "longitude": -99.1332,
        "country": "MX", "city": "Mexico City",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    },
    "cust_102": {
        "latitude": 25.2048, "longitude": 55.2708,
        "country": "AE", "city": "Dubai",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
    },
    "cust_103": {
        "latitude": 35.6762, "longitude": 139.6503,
        "country": "JP", "city": "Tokyo",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
    },
    "cust_104": {
        "latitude": 53.3498, "longitude": -6.2603,
        "country": "IE", "city": "Dublin",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
    },
    "cust_105": {
        "latitude": 52.5200, "longitude": 13.4050,
        "country": "DE", "city": "Berlin",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    "cust_106": {
        "latitude": 1.3521, "longitude": 103.8198,
        "country": "SG", "city": "Singapore",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
    },
    "cust_107": {
        "latitude": 37.5665, "longitude": 126.9780,
        "country": "KR", "city": "Seoul",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    },
    "cust_108": {
        "latitude": 48.1351, "longitude": 11.5820,
        "country": "DE", "city": "Munich",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    },
    "cust_109": {
        "latitude": 30.0444, "longitude": 31.2357,
        "country": "EG", "city": "Cairo",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
    },
    "cust_110": {
        "latitude": 43.6532, "longitude": -79.3832,
        "country": "CA", "city": "Toronto",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    "cust_112": {
        "latitude": 19.0760, "longitude": 72.8777,
        "country": "IN", "city": "Mumbai",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
    },
    "cust_115": {
        "latitude": 51.5074, "longitude": -0.1278,
        "country": "GB", "city": "London",
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    },
}

# Impossible travel speed threshold (km/h)
IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

geo_server = FastMCP("geo-server")


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance in km using the Haversine formula.

    Args:
        lat1, lon1: First point (decimal degrees).
        lat2, lon2: Second point (decimal degrees).

    Returns:
        Distance in kilometres.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@geo_server.tool()
async def get_last_location(customer_id: str) -> dict[str, Any]:
    """Get the last known location for a customer.

    Args:
        customer_id: The customer identifier.

    Returns:
        Dict with latitude, longitude, country, city, and timestamp.
    """
    loc = _LAST_LOCATIONS.get(customer_id)
    if loc is None:
        return {
            "error": "no_location_data",
            "customer_id": customer_id,
        }
    return {"customer_id": customer_id, **loc}


@geo_server.tool()
async def calculate_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> dict[str, Any]:
    """Calculate the great-circle distance between two points.

    Args:
        lat1: Latitude of point A (decimal degrees).
        lon1: Longitude of point A (decimal degrees).
        lat2: Latitude of point B (decimal degrees).
        lon2: Longitude of point B (decimal degrees).

    Returns:
        Dict with ``distance_km``.
    """
    dist = _haversine(lat1, lon1, lat2, lon2)
    return {
        "point_a": {"latitude": lat1, "longitude": lon1},
        "point_b": {"latitude": lat2, "longitude": lon2},
        "distance_km": round(dist, 2),
    }


@geo_server.tool()
async def check_impossible_travel(
    customer_id: str,
    current_lat: float,
    current_lon: float,
    current_timestamp: str,
) -> dict[str, Any]:
    """Check if the customer could have physically traveled to the new location.

    Flags impossible travel if the required speed exceeds 900 km/h
    (faster than commercial jets).

    Args:
        customer_id: The customer identifier.
        current_lat: Current transaction latitude.
        current_lon: Current transaction longitude.
        current_timestamp: Current transaction timestamp (ISO 8601).

    Returns:
        Dict with distance, time delta, required speed, and impossible_travel flag.
    """
    last = _LAST_LOCATIONS.get(customer_id)
    if last is None:
        return {
            "customer_id": customer_id,
            "impossible_travel": False,
            "reason": "no_previous_location",
        }

    dist_km = _haversine(
        last["latitude"], last["longitude"], current_lat, current_lon
    )

    last_ts = datetime.fromisoformat(last["timestamp"])
    try:
        curr_ts = datetime.fromisoformat(current_timestamp)
    except ValueError:
        curr_ts = datetime.now(timezone.utc)

    time_diff_hours = max(
        (curr_ts - last_ts).total_seconds() / 3600.0, 0.001
    )
    required_speed = dist_km / time_diff_hours
    impossible = required_speed > IMPOSSIBLE_TRAVEL_SPEED_KMH

    result = {
        "customer_id": customer_id,
        "last_location": {
            "latitude": last["latitude"],
            "longitude": last["longitude"],
            "country": last.get("country", ""),
            "city": last.get("city", ""),
            "timestamp": last["timestamp"],
        },
        "current_location": {
            "latitude": current_lat,
            "longitude": current_lon,
            "timestamp": current_timestamp,
        },
        "distance_km": round(dist_km, 2),
        "time_diff_hours": round(time_diff_hours, 4),
        "required_speed_kmh": round(required_speed, 2),
        "impossible_travel": impossible,
        "cross_border": last.get("country", "") != "",  # always true if last has country
    }

    if impossible:
        logger.warning(
            "Impossible travel detected for %s: %.0f km/h",
            customer_id,
            required_speed,
        )

    return result
