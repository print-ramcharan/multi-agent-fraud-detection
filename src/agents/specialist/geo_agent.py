"""
Geo Agent — Specialist

Detects impossible travel by comparing the current transaction
location with the customer's last known transaction location.

Budget: 15ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import GeoResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)

# Approximate country center coordinates for distance calculation
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "US": (39.8, -98.6), "GB": (51.5, -0.1), "DE": (51.2, 10.4), "FR": (46.2, 2.2),
    "JP": (36.2, 138.3), "CA": (56.1, -106.3), "AU": (-25.3, 133.8), "IN": (20.6, 79.0),
    "BR": (-14.2, -51.9), "CN": (35.9, 104.2), "KR": (35.9, 127.8), "MX": (23.6, -102.6),
    "RU": (61.5, 105.3), "ZA": (-30.6, 22.9), "NG": (9.1, 8.7), "AE": (23.4, 53.8),
    "SG": (1.4, 103.8), "HK": (22.4, 114.1), "CH": (46.8, 8.2), "SE": (60.1, 18.6),
    "NO": (60.5, 8.5), "DK": (56.3, 9.5), "NL": (52.1, 5.3), "BE": (50.5, 4.5),
    "AT": (47.5, 14.6), "IT": (41.9, 12.6), "ES": (40.5, -3.7), "PT": (39.4, -8.2),
    "PL": (51.9, 19.1), "CZ": (49.8, 15.5), "HU": (47.2, 19.5), "IE": (53.1, -7.7),
    "IL": (31.0, 34.9), "TR": (39.0, 35.2), "TH": (15.9, 100.9), "PH": (12.9, 121.8),
    "ID": (-0.8, 113.9), "MY": (4.2, 101.9), "VN": (14.1, 108.3), "TW": (23.7, 121.0),
    "NZ": (-40.9, 174.9), "AR": (-38.4, -63.6), "CL": (-35.7, -71.5), "CO": (4.6, -74.3),
    "PE": (-9.2, -75.0), "EG": (26.8, 30.8), "SA": (23.9, 45.1), "KW": (29.3, 47.5),
    "QA": (25.4, 51.2), "BH": (26.0, 50.6), "PK": (30.4, 69.3), "BD": (23.7, 90.4),
    "LK": (7.9, 80.8), "KP": (40.3, 127.5), "IR": (32.4, 53.7), "IQ": (33.2, 43.7),
    "SY": (34.8, 38.9), "CU": (21.5, -77.8), "VE": (6.4, -66.6),
}

# Maximum physically possible speed (commercial aviation ~900 km/h)
MAX_TRAVEL_SPEED_KMH = 900.0


class GeoAgent(BaseAgent):
    """Detects impossible travel between transactions."""

    def __init__(self, budget_ms: float = 15.0):
        super().__init__(
            name="geo_agent",
            budget_ms=budget_ms,
            tier="specialist",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        distance_km = 0.0
        time_since_last_hours = 0.0
        required_speed_kmh = 0.0
        impossible_travel = False
        last_country = ""
        cross_border = False

        if gateway:
            try:
                # Get last known location
                location = await gateway.call_tool(
                    "geo_server", "get_last_location",
                    {"customer_id": transaction.customer_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                last_country = location.get("country", "")
                last_lat = location.get("latitude", 0.0)
                last_lon = location.get("longitude", 0.0)
                time_since_last_hours = location.get("hours_since_last", 0.0)

                # Get current coords
                current_coords = COUNTRY_COORDS.get(
                    transaction.country, (0.0, 0.0)
                )

                if last_lat != 0.0 or last_lon != 0.0:
                    # Calculate distance
                    dist_result = await gateway.call_tool(
                        "geo_server", "calculate_distance",
                        {
                            "lat1": last_lat, "lon1": last_lon,
                            "lat2": current_coords[0], "lon2": current_coords[1],
                        },
                        agent_name=self.name,
                    )
                    tool_calls += 1
                    distance_km = dist_result.get("distance_km", 0.0)

                    # Check impossible travel
                    if time_since_last_hours > 0:
                        required_speed_kmh = distance_km / time_since_last_hours
                        impossible_travel = required_speed_kmh > MAX_TRAVEL_SPEED_KMH

                cross_border = (
                    last_country != "" and
                    last_country != transaction.country
                )

            except Exception as e:
                logger.warning(f"Geo lookup failed: {e}")
                evidence.append({
                    "source": self.name,
                    "claim": f"Geo lookup failed: {e}",
                    "confidence": 0.0,
                    "data": {"error": str(e)},
                })

        if impossible_travel:
            evidence.append({
                "source": self.name,
                "claim": (
                    f"Impossible travel detected: {distance_km:.0f}km in "
                    f"{time_since_last_hours:.1f}h requires {required_speed_kmh:.0f}km/h "
                    f"(max {MAX_TRAVEL_SPEED_KMH}km/h)"
                ),
                "confidence": 0.95,
                "data": {
                    "distance_km": distance_km,
                    "time_hours": time_since_last_hours,
                    "required_speed": required_speed_kmh,
                    "max_speed": MAX_TRAVEL_SPEED_KMH,
                },
            })
        elif cross_border:
            evidence.append({
                "source": self.name,
                "claim": (
                    f"Cross-border transaction: {last_country} → {transaction.country} "
                    f"({distance_km:.0f}km)"
                ),
                "confidence": 0.7,
                "data": {
                    "from_country": last_country,
                    "to_country": transaction.country,
                    "distance_km": distance_km,
                },
            })
        else:
            evidence.append({
                "source": self.name,
                "claim": "No geographic anomalies detected",
                "confidence": 0.9,
                "data": {
                    "distance_km": distance_km,
                    "same_country": not cross_border,
                },
            })

        result = GeoResult(
            distance_km=distance_km,
            time_since_last_hours=time_since_last_hours,
            required_speed_kmh=required_speed_kmh,
            impossible_travel=impossible_travel,
            last_country=last_country,
            cross_border=cross_border,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }
