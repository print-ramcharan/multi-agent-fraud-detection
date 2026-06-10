"""
Blacklist Agent — Tier-1

Identifies known bad actors by checking card, device, and merchant
against blacklists. Uses MCP gateway for all lookups.

Budget: 10ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import AgentEvidence, BlacklistResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class BlacklistAgent(BaseAgent):
    """Checks card_id, device_id, merchant_id against blacklists."""

    def __init__(self, budget_ms: float = 10.0):
        super().__init__(
            name="blacklist_agent",
            budget_ms=budget_ms,
            tier="tier1",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        card_blacklisted = False
        device_blacklisted = False
        merchant_blacklisted = False

        if gateway:
            # Check card blacklist
            card_result = await gateway.call_tool(
                "blacklist_server", "check_card_blacklist",
                {"card_id": transaction.card_id},
                agent_name=self.name,
            )
            tool_calls += 1
            card_blacklisted = card_result.get("blacklisted", False)
            if card_blacklisted:
                evidence.append({
                    "source": self.name,
                    "claim": f"Card {transaction.card_id} is on the blacklist",
                    "confidence": 1.0,
                    "data": card_result,
                })

            # Check device blacklist
            if transaction.device_id:
                device_result = await gateway.call_tool(
                    "blacklist_server", "check_device_blacklist",
                    {"device_id": transaction.device_id},
                    agent_name=self.name,
                )
                tool_calls += 1
                device_blacklisted = device_result.get("blacklisted", False)
                if device_blacklisted:
                    evidence.append({
                        "source": self.name,
                        "claim": f"Device {transaction.device_id} is on the blacklist",
                        "confidence": 1.0,
                        "data": device_result,
                    })

            # Check merchant blacklist
            merchant_result = await gateway.call_tool(
                "blacklist_server", "check_merchant_blacklist",
                {"merchant_id": transaction.merchant_id},
                agent_name=self.name,
            )
            tool_calls += 1
            merchant_blacklisted = merchant_result.get("blacklisted", False)
            if merchant_blacklisted:
                evidence.append({
                    "source": self.name,
                    "claim": f"Merchant {transaction.merchant_id} is on the blacklist",
                    "confidence": 1.0,
                    "data": merchant_result,
                })

        any_blacklisted = card_blacklisted or device_blacklisted or merchant_blacklisted
        source = ""
        if card_blacklisted:
            source = "card"
        elif device_blacklisted:
            source = "device"
        elif merchant_blacklisted:
            source = "merchant"

        if not any_blacklisted:
            evidence.append({
                "source": self.name,
                "claim": "No blacklist matches found",
                "confidence": 1.0,
                "data": {"card": False, "device": False, "merchant": False},
            })

        result = BlacklistResult(
            blacklisted=any_blacklisted,
            card_blacklisted=card_blacklisted,
            device_blacklisted=device_blacklisted,
            merchant_blacklisted=merchant_blacklisted,
            source=source,
            match_type="exact" if any_blacklisted else "none",
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }
