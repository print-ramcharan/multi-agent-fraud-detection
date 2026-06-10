"""
Device Agent — Specialist

Evaluates device trust by checking device age, sharing across
customers, and detecting anomalies.

Budget: 10ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import DeviceResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class DeviceAgent(BaseAgent):
    """Evaluates device trust and detects device-based fraud signals."""

    def __init__(self, budget_ms: float = 10.0):
        super().__init__(
            name="device_agent",
            budget_ms=budget_ms,
            tier="specialist",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        new_device = False
        device_age_days = 0
        shared_device = False
        device_risk = 0.0
        anomalies: list[str] = []

        if not transaction.device_id:
            evidence.append({
                "source": self.name,
                "claim": "No device ID provided — cannot evaluate device trust",
                "confidence": 0.5,
                "data": {},
            })
            return {
                **DeviceResult(
                    new_device=True, device_risk=0.3,
                    anomalies=["no_device_id"],
                ).model_dump(),
                "evidence": evidence,
                "_tool_calls_made": 0,
            }

        if gateway:
            try:
                # Get device profile
                profile = await gateway.call_tool(
                    "device_server", "get_device_profile",
                    {
                        "device_id": transaction.device_id,
                        "customer_id": transaction.customer_id,
                    },
                    agent_name=self.name,
                )
                tool_calls += 1

                new_device = profile.get("new_device", True)
                device_age_days = profile.get("device_age_days", 0)

                # Check device sharing
                sharing = await gateway.call_tool(
                    "device_server", "check_device_sharing",
                    {"device_id": transaction.device_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                shared_device = sharing.get("shared", False)
                shared_count = sharing.get("customer_count", 1)

                # Compute risk score
                risk_components: list[float] = []

                if new_device:
                    risk_components.append(0.4)
                    anomalies.append("new_device")

                if shared_device:
                    risk_components.append(0.3 * min(shared_count / 3, 1.0))
                    anomalies.append(f"shared_device_{shared_count}_customers")

                if device_age_days < 7:
                    risk_components.append(0.2)
                    anomalies.append("device_age_under_7_days")

                device_risk = min(sum(risk_components), 1.0) if risk_components else 0.05

            except Exception as e:
                logger.warning(f"Device lookup failed: {e}")
                device_risk = 0.3
                anomalies.append("lookup_failed")
                evidence.append({
                    "source": self.name,
                    "claim": f"Device lookup failed: {e}",
                    "confidence": 0.0,
                    "data": {"error": str(e)},
                })

        # Build evidence
        if new_device:
            evidence.append({
                "source": self.name,
                "claim": f"Device {transaction.device_id} is new (not previously seen)",
                "confidence": 0.9,
                "data": {"device_id": transaction.device_id, "new": True},
            })

        if shared_device:
            evidence.append({
                "source": self.name,
                "claim": f"Device {transaction.device_id} is shared across multiple customers",
                "confidence": 0.85,
                "data": {"device_id": transaction.device_id, "shared": True},
            })

        if not anomalies:
            evidence.append({
                "source": self.name,
                "claim": f"Device {transaction.device_id} is trusted (age: {device_age_days}d)",
                "confidence": 0.9,
                "data": {
                    "device_id": transaction.device_id,
                    "age_days": device_age_days,
                    "risk": device_risk,
                },
            })

        result = DeviceResult(
            new_device=new_device,
            device_age_days=device_age_days,
            shared_device=shared_device,
            device_risk=round(device_risk, 3),
            anomalies=anomalies,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }
