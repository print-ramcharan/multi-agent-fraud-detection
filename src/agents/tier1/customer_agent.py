"""
Customer Agent — Tier-1

Analyzes customer behavior patterns, spending profile, trust tier,
and historical averages to assess transaction risk in context.

Budget: 20ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import CustomerResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class CustomerAgent(BaseAgent):
    """Analyzes customer behavior and trust level via MCP."""

    def __init__(self, budget_ms: float = 20.0):
        super().__init__(
            name="customer_agent",
            budget_ms=budget_ms,
            tier="tier1",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        # Defaults for when data is unavailable
        trust_tier = "standard"
        avg_amount = 0.0
        spending_anomaly = 0.0
        account_age_days = 0
        total_transactions = 0
        fraud_history = 0

        if gateway:
            try:
                # Get customer profile
                profile = await gateway.call_tool(
                    "customer_server", "get_customer_profile",
                    {"customer_id": transaction.customer_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                trust_tier = profile.get("trust_tier", "standard")
                avg_amount = profile.get("avg_transaction_amount", 0.0)
                account_age_days = profile.get("account_age_days", 0)
                total_transactions = profile.get("total_transactions", 0)
                fraud_history = profile.get("fraud_history", 0)

                # Get spending stats
                stats = await gateway.call_tool(
                    "customer_server", "get_spending_stats",
                    {"customer_id": transaction.customer_id},
                    agent_name=self.name,
                )
                tool_calls += 1

                avg_amount = stats.get("avg_amount", avg_amount)
                std_amount = stats.get("std_amount", avg_amount * 0.5)

                # Calculate spending anomaly (z-score)
                if std_amount > 0:
                    spending_anomaly = (transaction.amount_usd - avg_amount) / std_amount
                else:
                    spending_anomaly = 0.0 if transaction.amount_usd <= avg_amount else 3.0

                evidence.append({
                    "source": self.name,
                    "claim": (
                        f"Customer {transaction.customer_id} is {trust_tier} tier "
                        f"with avg spend ${avg_amount:.2f}"
                    ),
                    "confidence": 0.95,
                    "data": {
                        "trust_tier": trust_tier,
                        "avg_amount": avg_amount,
                        "spending_anomaly": round(spending_anomaly, 2),
                        "account_age_days": account_age_days,
                        "total_transactions": total_transactions,
                        "fraud_history": fraud_history,
                    },
                })

                if spending_anomaly > 2.0:
                    evidence.append({
                        "source": self.name,
                        "claim": (
                            f"Transaction amount ${transaction.amount_usd:.2f} is "
                            f"{spending_anomaly:.1f} standard deviations above average "
                            f"(${avg_amount:.2f})"
                        ),
                        "confidence": 0.9,
                        "data": {
                            "amount": transaction.amount_usd,
                            "avg": avg_amount,
                            "z_score": round(spending_anomaly, 2),
                        },
                    })

                if fraud_history > 0:
                    evidence.append({
                        "source": self.name,
                        "claim": f"Customer has {fraud_history} prior fraud flag(s)",
                        "confidence": 1.0,
                        "data": {"fraud_history": fraud_history},
                    })

            except Exception as e:
                logger.warning(f"Customer profile lookup failed: {e}")
                evidence.append({
                    "source": self.name,
                    "claim": f"Customer profile unavailable: {e}",
                    "confidence": 0.0,
                    "data": {"error": str(e)},
                })
        else:
            evidence.append({
                "source": self.name,
                "claim": "No gateway available — using default customer profile",
                "confidence": 0.3,
                "data": {"trust_tier": trust_tier},
            })

        result = CustomerResult(
            trust_tier=trust_tier,
            avg_transaction_amount=avg_amount,
            spending_anomaly=round(spending_anomaly, 2),
            account_age_days=account_age_days,
            total_transactions=total_transactions,
            fraud_history=fraud_history,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }
