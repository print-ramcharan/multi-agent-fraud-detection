"""
ML Risk Agent — Tier-1

Obtains a fraud probability score from the pre-trained ML model
via the MCP gateway. Falls back gracefully if model unavailable.

Budget: 25ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import MLRiskResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class MLRiskAgent(BaseAgent):
    """Gets ML fraud score from the model service via MCP."""

    def __init__(self, budget_ms: float = 25.0):
        super().__init__(
            name="ml_risk_agent",
            budget_ms=budget_ms,
            tier="tier1",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        gateway = context.get("gateway")
        evidence: list[dict[str, Any]] = []
        tool_calls = 0

        risk_score: float | None = None
        model_version = "unknown"
        feature_importances: dict[str, float] = {}

        if gateway:
            try:
                ml_result = await gateway.call_tool(
                    "ml_server", "predict_fraud_score",
                    {
                        "amount": transaction.amount_usd,
                        "channel": transaction.channel.value,
                        "merchant_category": transaction.merchant_category,
                        "country": transaction.country,
                        "hour_of_day": transaction.timestamp.hour,
                        "day_of_week": transaction.timestamp.weekday(),
                        "is_high_risk_country": transaction.is_high_risk_country,
                        "is_high_risk_merchant": transaction.is_high_risk_merchant,
                    },
                    agent_name=self.name,
                )
                tool_calls += 1

                risk_score = ml_result.get("risk_score")
                model_version = ml_result.get("model_version", "1.0.0")
                feature_importances = ml_result.get("feature_importances", {})

                if risk_score is not None:
                    evidence.append({
                        "source": self.name,
                        "claim": f"ML model predicts fraud probability of {risk_score:.3f}",
                        "confidence": 0.85,
                        "data": {
                            "risk_score": risk_score,
                            "model_version": model_version,
                            "top_features": dict(
                                sorted(
                                    feature_importances.items(),
                                    key=lambda x: x[1],
                                    reverse=True,
                                )[:5]
                            ),
                        },
                    })
                else:
                    evidence.append({
                        "source": self.name,
                        "claim": "ML model returned null score — model may be unavailable",
                        "confidence": 0.0,
                        "data": {"reason": "null_score"},
                    })

            except Exception as e:
                logger.warning(f"ML model call failed: {e}")
                evidence.append({
                    "source": self.name,
                    "claim": f"ML model unavailable: {e}",
                    "confidence": 0.0,
                    "data": {"error": str(e)},
                })
        else:
            # No gateway — use heuristic fallback
            risk_score = self._heuristic_score(transaction)
            model_version = "heuristic-1.0"
            evidence.append({
                "source": self.name,
                "claim": f"Heuristic risk score: {risk_score:.3f} (ML model not available)",
                "confidence": 0.5,
                "data": {"risk_score": risk_score, "model": "heuristic"},
            })

        result = MLRiskResult(
            risk_score=risk_score,
            model_version=model_version,
            feature_importances=feature_importances,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": tool_calls,
        }

    @staticmethod
    def _heuristic_score(transaction: NormalizedTransaction) -> float:
        """Simple heuristic fraud score when ML model is unavailable."""
        score = 0.1  # Base score

        # Amount-based risk
        if transaction.amount_usd > 5000:
            score += 0.2
        elif transaction.amount_usd > 1000:
            score += 0.1

        # Country risk
        if transaction.is_high_risk_country:
            score += 0.25

        # Merchant risk
        if transaction.is_high_risk_merchant:
            score += 0.15

        # Channel risk (online is riskier)
        if transaction.channel.value == "online":
            score += 0.05

        # Time-of-day risk
        if transaction.timestamp.hour in (1, 2, 3, 4):
            score += 0.1

        return min(score, 1.0)
