"""
Velocity Agent — Specialist

Detects transaction bursts by analyzing frequency and amount
patterns within sliding time windows.

Budget: 10ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import VelocityResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)

# Thresholds
BURST_TXN_PER_HOUR = 10
BURST_TXN_PER_DAY = 30
BURST_AMOUNT_PER_HOUR = 5000.0
AMOUNT_ACCELERATION_THRESHOLD = 3.0


class VelocityAgent(BaseAgent):
    """Detects transaction velocity bursts."""

    def __init__(self, budget_ms: float = 10.0):
        super().__init__(
            name="velocity_agent",
            budget_ms=budget_ms,
            tier="specialist",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        txn_last_hour = 0
        txn_last_day = 0
        amount_last_hour = 0.0
        amount_last_day = 0.0
        burst = False
        amount_acceleration = 0.0
        distinct_merchants = 0

        if gateway:
            try:
                # Transaction velocity
                txn_velocity = await gateway.call_tool(
                    "velocity_server", "get_transaction_velocity",
                    {"customer_id": transaction.customer_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                txn_last_hour = txn_velocity.get("count_1h", 0)
                txn_last_day = txn_velocity.get("count_24h", 0)
                distinct_merchants = txn_velocity.get("distinct_merchants_1h", 0)

                # Amount velocity
                amt_velocity = await gateway.call_tool(
                    "velocity_server", "get_amount_velocity",
                    {"customer_id": transaction.customer_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                amount_last_hour = amt_velocity.get("amount_1h", 0.0)
                amount_last_day = amt_velocity.get("amount_24h", 0.0)
                avg_hourly = amt_velocity.get("avg_hourly_amount", 0.0)

                if avg_hourly > 0:
                    amount_acceleration = amount_last_hour / avg_hourly
                else:
                    amount_acceleration = 0.0

            except Exception as e:
                logger.warning(f"Velocity check failed: {e}")
                evidence.append({
                    "source": self.name,
                    "claim": f"Velocity check failed: {e}",
                    "confidence": 0.0,
                    "data": {"error": str(e)},
                })

        # Detect burst conditions
        burst_reasons: list[str] = []

        if txn_last_hour >= BURST_TXN_PER_HOUR:
            burst = True
            burst_reasons.append(
                f"Transaction count ({txn_last_hour}) exceeds hourly limit ({BURST_TXN_PER_HOUR})"
            )

        if txn_last_day >= BURST_TXN_PER_DAY:
            burst = True
            burst_reasons.append(
                f"Daily transaction count ({txn_last_day}) exceeds limit ({BURST_TXN_PER_DAY})"
            )

        if amount_last_hour >= BURST_AMOUNT_PER_HOUR:
            burst = True
            burst_reasons.append(
                f"Hourly amount (${amount_last_hour:.2f}) exceeds limit (${BURST_AMOUNT_PER_HOUR:.2f})"
            )

        if amount_acceleration >= AMOUNT_ACCELERATION_THRESHOLD:
            burst = True
            burst_reasons.append(
                f"Amount acceleration ({amount_acceleration:.1f}x) exceeds threshold "
                f"({AMOUNT_ACCELERATION_THRESHOLD}x)"
            )

        if distinct_merchants >= 5:
            burst = True
            burst_reasons.append(
                f"High merchant diversity ({distinct_merchants} distinct merchants in 1h)"
            )

        # Evidence
        if burst:
            evidence.append({
                "source": self.name,
                "claim": f"Transaction burst detected: {'; '.join(burst_reasons)}",
                "confidence": 0.9,
                "data": {
                    "txn_last_hour": txn_last_hour,
                    "txn_last_day": txn_last_day,
                    "amount_last_hour": amount_last_hour,
                    "amount_acceleration": round(amount_acceleration, 2),
                    "distinct_merchants": distinct_merchants,
                    "reasons": burst_reasons,
                },
            })
        else:
            evidence.append({
                "source": self.name,
                "claim": "No velocity anomalies detected",
                "confidence": 0.85,
                "data": {
                    "txn_last_hour": txn_last_hour,
                    "txn_last_day": txn_last_day,
                    "amount_last_hour": amount_last_hour,
                },
            })

        result = VelocityResult(
            transactions_last_hour=txn_last_hour,
            transactions_last_day=txn_last_day,
            amount_last_hour=amount_last_hour,
            amount_last_day=amount_last_day,
            burst=burst,
            amount_acceleration=round(amount_acceleration, 2),
            distinct_merchants_last_hour=distinct_merchants,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }
