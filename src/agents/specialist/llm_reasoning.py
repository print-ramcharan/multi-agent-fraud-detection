"""
LLM Reasoning Agent — Specialist

Uses the Google Antigravity SDK to synthesize evidence from all
other agents into a coherent risk assessment with reasoning chain.

NOT AUTHORIZED TO DECIDE — only recommends.

Budget: 20ms (aggressive timeout, LLM may not respond in time)
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import LLMReasoningResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class LLMReasoningAgent(BaseAgent):
    """
    Synthesizes all agent evidence using LLM reasoning.

    Advisory only — this agent CANNOT make decisions.
    Falls back gracefully if LLM is unavailable or times out.
    """

    def __init__(self, budget_ms: float = 20.0, enabled: bool = False):
        super().__init__(
            name="llm_reasoning_agent",
            budget_ms=budget_ms,
            tier="specialist",
        )
        self.enabled = enabled

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []

        # Gather all prior agent results from context
        tier1_results = context.get("tier1_results", {})
        specialist_results = context.get("specialist_results", {})

        if not self.enabled:
            # LLM disabled — return rule-based synthesis
            return self._rule_based_synthesis(
                transaction, tier1_results, specialist_results, evidence
            )

        try:
            # Attempt LLM-based reasoning via Google Antigravity SDK
            synthesis = await self._llm_synthesize(
                transaction, tier1_results, specialist_results
            )
            evidence.append({
                "source": self.name,
                "claim": f"LLM synthesized risk assessment: {synthesis.get('risk_level', 'MEDIUM')}",
                "confidence": 0.75,
                "data": synthesis,
            })

            result = LLMReasoningResult(
                risk_level=synthesis.get("risk_level", "MEDIUM"),
                confidence=synthesis.get("confidence", 0.5),
                recommended_action=synthesis.get("recommended_action", "ESCALATE"),
                reasoning=synthesis.get("reasoning", ""),
                evidence_summary=synthesis.get("evidence_summary", []),
                risk_factors=synthesis.get("risk_factors", []),
                mitigating_factors=synthesis.get("mitigating_factors", []),
            )

            return {
                **result.model_dump(),
                "evidence": evidence,
                "_tool_calls_made": 1,
            }

        except Exception as e:
            logger.warning(f"LLM reasoning failed, falling back to rule-based: {e}")
            return self._rule_based_synthesis(
                transaction, tier1_results, specialist_results, evidence
            )

    async def _llm_synthesize(
        self,
        transaction: NormalizedTransaction,
        tier1_results: dict[str, Any],
        specialist_results: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Use Google Antigravity SDK for LLM reasoning.

        This is wrapped in a try/except and has aggressive timeout
        at the BaseAgent level.
        """
        try:
            from google.antigravity import Agent, LocalAgentConfig
            import pydantic

            class RiskAssessment(pydantic.BaseModel):
                risk_level: str
                confidence: float
                recommended_action: str
                reasoning: str
                evidence_summary: list[str]
                risk_factors: list[str]
                mitigating_factors: list[str]

            config = LocalAgentConfig(
                response_schema=RiskAssessment,
                system_instructions=(
                    "You are a fraud risk analyst. Synthesize the evidence from multiple "
                    "fraud detection agents into a risk assessment. You CANNOT make the "
                    "final decision — you can only RECOMMEND an action. Be concise."
                ),
            )

            prompt = self._build_prompt(transaction, tier1_results, specialist_results)

            async with Agent(config) as agent:
                response = await agent.chat(prompt)
                data = await response.structured_output()
                return data or {}

        except ImportError:
            raise RuntimeError("google-antigravity SDK not available")

    def _build_prompt(
        self,
        transaction: NormalizedTransaction,
        tier1_results: dict[str, Any],
        specialist_results: dict[str, Any],
    ) -> str:
        """Build a concise prompt for the LLM."""
        parts = [
            f"Transaction: ${transaction.amount_usd:.2f} {transaction.channel.value} "
            f"from {transaction.country}, merchant={transaction.merchant_category}",
            "",
            "Agent Evidence:",
        ]

        for agent_name, result in {**tier1_results, **specialist_results}.items():
            if isinstance(result, dict):
                key_facts = {k: v for k, v in result.items()
                             if k not in ("evidence", "_tool_calls_made") and v}
                parts.append(f"  {agent_name}: {key_facts}")

        parts.append("")
        parts.append(
            "Synthesize these signals. Determine risk_level (LOW/MEDIUM/HIGH/CRITICAL), "
            "confidence (0-1), and recommended_action (APPROVE/DECLINE/ESCALATE)."
        )

        return "\n".join(parts)

    @staticmethod
    def _rule_based_synthesis(
        transaction: NormalizedTransaction,
        tier1_results: dict[str, Any],
        specialist_results: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Fallback rule-based evidence synthesis when LLM is unavailable."""
        risk_factors: list[str] = []
        mitigating_factors: list[str] = []

        # Analyze tier1
        blacklist = tier1_results.get("blacklist_agent", {})
        rules = tier1_results.get("rule_agent", {})
        ml_risk = tier1_results.get("ml_risk_agent", {})
        customer = tier1_results.get("customer_agent", {})

        if blacklist.get("blacklisted"):
            risk_factors.append(f"Blacklisted {blacklist.get('source', 'entity')}")

        if rules.get("violation"):
            risk_factors.append(f"Rule violation: {rules.get('rule_name', 'unknown')}")

        ml_score = ml_risk.get("risk_score")
        if ml_score is not None:
            if ml_score > 0.7:
                risk_factors.append(f"High ML risk score: {ml_score:.2f}")
            elif ml_score < 0.3:
                mitigating_factors.append(f"Low ML risk score: {ml_score:.2f}")

        trust_tier = customer.get("trust_tier", "standard")
        if trust_tier in ("platinum", "gold"):
            mitigating_factors.append(f"Trusted customer ({trust_tier} tier)")
        elif trust_tier == "new":
            risk_factors.append("New customer account")

        anomaly = customer.get("spending_anomaly", 0.0)
        if anomaly > 2.0:
            risk_factors.append(f"Spending anomaly: {anomaly:.1f}σ above average")

        # Analyze specialists
        geo = specialist_results.get("geo_agent", {})
        device = specialist_results.get("device_agent", {})
        velocity = specialist_results.get("velocity_agent", {})

        if geo.get("impossible_travel"):
            risk_factors.append("Impossible travel detected")

        if device.get("new_device"):
            risk_factors.append("New/unknown device")

        if velocity.get("burst"):
            risk_factors.append("Transaction velocity burst")

        # Determine risk level
        if len(risk_factors) >= 3:
            risk_level = "CRITICAL"
            confidence = 0.9
            recommended_action = "DECLINE"
        elif len(risk_factors) >= 2:
            risk_level = "HIGH"
            confidence = 0.75
            recommended_action = "ESCALATE"
        elif len(risk_factors) >= 1:
            risk_level = "MEDIUM"
            confidence = 0.6
            recommended_action = "ESCALATE"
        else:
            risk_level = "LOW"
            confidence = 0.85
            recommended_action = "APPROVE"

        evidence.append({
            "source": "llm_reasoning_agent",
            "claim": f"Rule-based synthesis: {risk_level} risk ({len(risk_factors)} risk factors)",
            "confidence": confidence,
            "data": {
                "risk_factors": risk_factors,
                "mitigating_factors": mitigating_factors,
                "mode": "rule_based_fallback",
            },
        })

        result = LLMReasoningResult(
            risk_level=risk_level,
            confidence=confidence,
            recommended_action=recommended_action,
            reasoning=f"Rule-based synthesis identified {len(risk_factors)} risk factor(s) "
                      f"and {len(mitigating_factors)} mitigating factor(s).",
            evidence_summary=[
                f"Risk: {f}" for f in risk_factors
            ] + [
                f"Mitigating: {f}" for f in mitigating_factors
            ],
            risk_factors=risk_factors,
            mitigating_factors=mitigating_factors,
        )

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": 0,
        }
