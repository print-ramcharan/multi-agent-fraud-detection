"""
Rule Agent — Tier-1

Executes deterministic business rules against the transaction.
Pure logic — no external calls, no MCP, no ML.

Budget: 5ms
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import RuleResult
from src.models.transaction import HIGH_RISK_COUNTRIES, HIGH_RISK_CATEGORIES, NormalizedTransaction

logger = logging.getLogger(__name__)

# Sanctioned countries (subset of high-risk, these are hard-block)
SANCTIONED_COUNTRIES: set[str] = {"KP", "IR", "SY", "CU", "SD"}

# Amount limits by channel
AMOUNT_LIMITS: dict[str, float] = {
    "online": 10000.0,
    "pos": 5000.0,
    "atm": 2000.0,
    "mobile": 10000.0,
    "banking": 50000.0,
}

# Restricted hours (UTC) — transactions between 1-5 AM local are suspicious
RESTRICTED_HOURS: set[int] = {1, 2, 3, 4}


class RuleAgent(BaseAgent):
    """Executes deterministic policy rules against transactions."""

    def __init__(self, budget_ms: float = 5.0):
        super().__init__(
            name="rule_agent",
            budget_ms=budget_ms,
            tier="tier1",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        violations: list[dict[str, str]] = []
        evidence: list[dict[str, Any]] = []

        # Rule 1: Sanctioned country
        if transaction.country in SANCTIONED_COUNTRIES:
            violations.append({
                "rule": "SANCTIONED_COUNTRY",
                "severity": "critical",
                "description": f"Transaction from sanctioned country: {transaction.country}",
            })
            evidence.append({
                "source": self.name,
                "claim": f"Country {transaction.country} is on the sanctions list",
                "confidence": 1.0,
                "data": {"country": transaction.country, "list": "SANCTIONS"},
            })

        # Rule 2: High-risk country (not sanctioned, but elevated risk)
        elif transaction.is_high_risk_country:
            violations.append({
                "rule": "HIGH_RISK_COUNTRY",
                "severity": "medium",
                "description": f"Transaction from high-risk country: {transaction.country}",
            })
            evidence.append({
                "source": self.name,
                "claim": f"Country {transaction.country} is on the high-risk list",
                "confidence": 1.0,
                "data": {"country": transaction.country, "list": "HIGH_RISK"},
            })

        # Rule 3: Blocked merchant category
        if transaction.is_high_risk_merchant:
            violations.append({
                "rule": "HIGH_RISK_MERCHANT_CATEGORY",
                "severity": "high",
                "description": f"High-risk merchant category: {transaction.merchant_category}",
            })
            evidence.append({
                "source": self.name,
                "claim": f"Merchant category '{transaction.merchant_category}' is high-risk",
                "confidence": 1.0,
                "data": {"category": transaction.merchant_category},
            })

        # Rule 4: Amount exceeds channel limit
        channel_limit = AMOUNT_LIMITS.get(transaction.channel.value, 10000.0)
        if transaction.amount_usd > channel_limit:
            violations.append({
                "rule": "AMOUNT_EXCEEDS_LIMIT",
                "severity": "high",
                "description": (
                    f"Amount ${transaction.amount_usd:.2f} exceeds "
                    f"{transaction.channel.value} limit of ${channel_limit:.2f}"
                ),
            })
            evidence.append({
                "source": self.name,
                "claim": f"Transaction amount exceeds channel limit",
                "confidence": 1.0,
                "data": {
                    "amount_usd": transaction.amount_usd,
                    "channel": transaction.channel.value,
                    "limit": channel_limit,
                },
            })

        # Rule 5: Suspicious time of day
        txn_hour = transaction.timestamp.hour
        if txn_hour in RESTRICTED_HOURS:
            violations.append({
                "rule": "SUSPICIOUS_TIME",
                "severity": "low",
                "description": f"Transaction at unusual hour: {txn_hour}:00 UTC",
            })
            evidence.append({
                "source": self.name,
                "claim": f"Transaction occurred during restricted hours ({txn_hour}:00 UTC)",
                "confidence": 0.7,
                "data": {"hour_utc": txn_hour},
            })

        # Rule 6: Very high amount (absolute threshold)
        if transaction.amount_usd > 25000.0:
            violations.append({
                "rule": "VERY_HIGH_AMOUNT",
                "severity": "high",
                "description": f"Very high transaction amount: ${transaction.amount_usd:.2f}",
            })
            evidence.append({
                "source": self.name,
                "claim": "Transaction amount exceeds absolute high-value threshold ($25,000)",
                "confidence": 1.0,
                "data": {"amount_usd": transaction.amount_usd, "threshold": 25000.0},
            })

        # No violations
        if not violations:
            evidence.append({
                "source": self.name,
                "claim": "No rule violations detected",
                "confidence": 1.0,
                "data": {"rules_checked": 6, "violations_found": 0},
            })

        # Determine worst severity
        has_violation = len(violations) > 0
        worst_severity = "none"
        worst_rule = ""
        if has_violation:
            severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            worst = max(violations, key=lambda v: severity_order.get(v["severity"], 0))
            worst_severity = worst["severity"]
            worst_rule = worst["rule"]

        result = RuleResult(
            violation=has_violation,
            rule_name=worst_rule,
            rule_severity=worst_severity,
            violations=violations,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": 0,  # Pure logic, no MCP calls
        }
