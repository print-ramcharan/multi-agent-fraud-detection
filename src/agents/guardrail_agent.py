"""
Guardrail Agent

Validates all agent outputs for evidence integrity, schema compliance,
governance rule adherence, budget compliance, and hallucination detection.

Runs after every agent invocation.
Budget: 5ms
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.governance.rules import validate_agent_output
from src.models.agent_output import GuardrailResult
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class GuardrailAgent(BaseAgent):
    """Validates agent outputs against governance rules and data contracts."""

    def __init__(self, budget_ms: float = 5.0):
        super().__init__(
            name="guardrail_agent",
            budget_ms=budget_ms,
            tier="guardrail",
        )

    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the output of a specific agent."""
        target_agent = context.get("target_agent", "unknown")
        target_output = context.get("target_output", {})
        target_evidence = context.get("target_evidence", [])
        target_duration_ms = context.get("target_duration_ms", 0.0)
        target_budget_ms = context.get("target_budget_ms", 0.0)
        tool_call_count = context.get("tool_call_count", 0)
        hop_count = context.get("hop_count", 0)

        violations: list[str] = []

        # 1. Evidence validation
        evidence_valid = self._validate_evidence(
            target_agent, target_output, target_evidence, violations
        )

        # 2. Schema validation (Pydantic handles this, but we check for None/empty)
        schema_valid = self._validate_schema(target_agent, target_output, violations)

        # 3. Policy/governance validation
        gov_violations = validate_agent_output(
            agent_name=target_agent,
            output=target_output,
            evidence=target_evidence,
            tool_call_count=tool_call_count,
            hop_count=hop_count,
        )
        policy_valid = len(gov_violations) == 0
        violations.extend(gov_violations)

        # 4. Budget validation
        budget_valid = True
        if target_budget_ms > 0 and target_duration_ms > target_budget_ms * 1.2:
            budget_valid = False
            violations.append(
                f"Agent '{target_agent}' exceeded budget: "
                f"{target_duration_ms:.1f}ms > {target_budget_ms}ms"
            )

        # 5. Hallucination detection
        hallucination_detected = self._detect_hallucination(
            target_agent, target_output, violations
        )

        overall_valid = (
            evidence_valid and schema_valid and
            policy_valid and budget_valid and
            not hallucination_detected
        )

        if not overall_valid:
            logger.warning(
                f"Guardrail FAILED for '{target_agent}': {violations}"
            )

        result = GuardrailResult(
            valid=overall_valid,
            violations=violations,
            evidence_valid=evidence_valid,
            schema_valid=schema_valid,
            policy_valid=policy_valid,
            budget_valid=budget_valid,
            hallucination_detected=hallucination_detected,
        )

        evidence = [{
            "source": self.name,
            "claim": (
                f"Guardrail {'PASSED' if overall_valid else 'FAILED'} "
                f"for agent '{target_agent}'"
            ),
            "confidence": 1.0,
            "data": result.model_dump(),
        }]

        return {
            **result.model_dump(),
            "evidence": evidence,
            "_tool_calls_made": 0,
        }

    @staticmethod
    def _validate_evidence(
        agent_name: str,
        output: dict[str, Any],
        evidence: list,
        violations: list[str],
    ) -> bool:
        """Check that significant claims have supporting evidence."""
        has_significant_output = any(
            k in output and output[k] not in (None, False, 0, 0.0, "", "none", [])
            for k in (
                "blacklisted", "violation", "impossible_travel",
                "burst", "risk_score", "new_device", "shared_device",
            )
        )

        if has_significant_output and not evidence:
            violations.append(
                f"Agent '{agent_name}' produced significant output without evidence"
            )
            return False
        return True

    @staticmethod
    def _validate_schema(
        agent_name: str,
        output: dict[str, Any],
        violations: list[str],
    ) -> bool:
        """Basic schema validation beyond Pydantic."""
        if not output:
            violations.append(f"Agent '{agent_name}' produced empty output")
            return False
        return True

    @staticmethod
    def _detect_hallucination(
        agent_name: str,
        output: dict[str, Any],
        violations: list[str],
    ) -> bool:
        """Detect impossible or fabricated values."""
        hallucinated = False

        # Risk scores must be in [0, 1]
        for key in ("risk_score", "confidence", "device_risk"):
            val = output.get(key)
            if val is not None and isinstance(val, (int, float)):
                if val < 0.0 or val > 1.0:
                    violations.append(
                        f"Hallucination: '{agent_name}' produced {key}={val} outside [0, 1]"
                    )
                    hallucinated = True

        # Distances must be non-negative
        dist = output.get("distance_km")
        if dist is not None and isinstance(dist, (int, float)) and dist < 0:
            violations.append(
                f"Hallucination: '{agent_name}' produced negative distance_km={dist}"
            )
            hallucinated = True

        # Transaction counts must be non-negative
        for key in ("transactions_last_hour", "transactions_last_day"):
            val = output.get(key)
            if val is not None and isinstance(val, int) and val < 0:
                violations.append(
                    f"Hallucination: '{agent_name}' produced negative {key}={val}"
                )
                hallucinated = True

        return hallucinated


async def validate_agent_result(
    guardrail: GuardrailAgent,
    transaction: NormalizedTransaction,
    agent_name: str,
    agent_output: dict[str, Any],
    evidence: list,
    duration_ms: float,
    budget_ms: float,
    tool_call_count: int,
    hop_count: int,
) -> GuardrailResult:
    """
    Convenience function to validate an agent's output through the guardrail.

    Returns the GuardrailResult.
    """
    context = {
        "target_agent": agent_name,
        "target_output": agent_output,
        "target_evidence": evidence,
        "target_duration_ms": duration_ms,
        "target_budget_ms": budget_ms,
        "tool_call_count": tool_call_count,
        "hop_count": hop_count,
    }

    output = await guardrail._execute(transaction, context)
    return GuardrailResult(**{
        k: v for k, v in output.items()
        if k not in ("evidence", "_tool_calls_made")
    })
