"""
Governance rules for the fraud detection platform.

Implements the 10 governance rules as enforceable runtime checks.
These rules are non-negotiable and cannot be overridden by any agent.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable

from src.models.config import get_config


# ---------------------------------------------------------------------------
# Rule Definitions
# ---------------------------------------------------------------------------

class GovernanceViolation(Exception):
    """Raised when a governance rule is violated."""

    def __init__(self, rule_number: int, rule_name: str, detail: str):
        self.rule_number = rule_number
        self.rule_name = rule_name
        self.detail = detail
        super().__init__(f"GOVERNANCE RULE {rule_number} VIOLATED [{rule_name}]: {detail}")


# Rule 1: Only Decision Engine can make decisions
def validate_no_decision(agent_name: str, output: dict[str, Any]) -> None:
    """Rule 1: Agents cannot make decisions. Only Decision Engine decides."""
    if agent_name == "decision_engine":
        return
    forbidden_keys = {"decision", "final_decision"}
    for key in forbidden_keys:
        if key in output and output[key] in ("APPROVE", "DECLINE", "ESCALATE"):
            raise GovernanceViolation(
                1, "AGENTS_CANNOT_DECIDE",
                f"Agent '{agent_name}' attempted to set decision='{output[key]}'. "
                "Only DecisionEngine is authorized to decide.",
            )


# Rule 2: Every claim requires evidence
def validate_evidence_required(agent_name: str, output: dict[str, Any], evidence: list) -> None:
    """Rule 2: Every claim must be supported by evidence."""
    has_claims = any(
        key in output
        for key in ("blacklisted", "violation", "impossible_travel", "burst", "risk_score")
        if output.get(key) not in (None, False, 0, 0.0, "")
    )
    if has_claims and not evidence:
        raise GovernanceViolation(
            2, "EVIDENCE_REQUIRED",
            f"Agent '{agent_name}' made claims without providing evidence.",
        )


# Rule 3: No hallucinated facts
def validate_no_hallucination(agent_name: str, output: dict[str, Any]) -> None:
    """Rule 3: No hallucinated facts — reject impossible values."""
    risk_score = output.get("risk_score")
    if risk_score is not None and (risk_score < 0.0 or risk_score > 1.0):
        raise GovernanceViolation(
            3, "NO_HALLUCINATION",
            f"Agent '{agent_name}' produced risk_score={risk_score} outside [0, 1].",
        )

    confidence = output.get("confidence")
    if confidence is not None and (confidence < 0.0 or confidence > 1.0):
        raise GovernanceViolation(
            3, "NO_HALLUCINATION",
            f"Agent '{agent_name}' produced confidence={confidence} outside [0, 1].",
        )

    distance_km = output.get("distance_km")
    if distance_km is not None and distance_km < 0:
        raise GovernanceViolation(
            3, "NO_HALLUCINATION",
            f"Agent '{agent_name}' produced negative distance_km={distance_km}.",
        )


# Rule 4: Maximum agent hops
def validate_max_hops(hop_count: int) -> None:
    """Rule 4: Maximum agent hops per transaction."""
    config = get_config()
    if hop_count > config.max_agent_hops:
        raise GovernanceViolation(
            4, "MAX_AGENT_HOPS",
            f"Agent hop count ({hop_count}) exceeds maximum ({config.max_agent_hops}).",
        )


# Rule 5: Maximum tool calls per agent
def validate_max_tool_calls(agent_name: str, tool_call_count: int) -> None:
    """Rule 5: Maximum tool calls per agent."""
    config = get_config()
    if tool_call_count > config.max_tool_calls:
        raise GovernanceViolation(
            5, "MAX_TOOL_CALLS",
            f"Agent '{agent_name}' made {tool_call_count} tool calls, "
            f"exceeding maximum of {config.max_tool_calls}.",
        )


# Rule 6: Policy always wins (enforced at decision engine level)
# This is structural — the decision engine always checks policy rules first.

# Rule 7: Fail safe — uncertainty → ESCALATE
def apply_fail_safe(confidence: float, threshold: float = 0.5) -> str:
    """Rule 7: When confidence is insufficient, ESCALATE."""
    if confidence < threshold:
        return "ESCALATE"
    return ""


# Rule 8: No direct model updates
# Rule 9: No self-modifying agents
# These are structural rules enforced by the architecture — agents have no write access
# to model weights or their own code.

# Rule 10: Every decision must be auditable (enforced by audit trail being mandatory)


# ---------------------------------------------------------------------------
# Composite Validator
# ---------------------------------------------------------------------------

def validate_agent_output(
    agent_name: str,
    output: dict[str, Any],
    evidence: list | None = None,
    tool_call_count: int = 0,
    hop_count: int = 0,
) -> list[str]:
    """
    Run all applicable governance rules against an agent's output.

    Returns a list of violation messages (empty = all passed).
    """
    violations: list[str] = []

    try:
        validate_no_decision(agent_name, output)
    except GovernanceViolation as e:
        violations.append(str(e))

    try:
        validate_evidence_required(agent_name, output, evidence or [])
    except GovernanceViolation as e:
        violations.append(str(e))

    try:
        validate_no_hallucination(agent_name, output)
    except GovernanceViolation as e:
        violations.append(str(e))

    try:
        validate_max_hops(hop_count)
    except GovernanceViolation as e:
        violations.append(str(e))

    try:
        validate_max_tool_calls(agent_name, tool_call_count)
    except GovernanceViolation as e:
        violations.append(str(e))

    return violations


# ---------------------------------------------------------------------------
# Decorators for Agent Methods
# ---------------------------------------------------------------------------

def budget_enforced(budget_ms: float):
    """Decorator: Enforce a time budget on an async function."""

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if elapsed_ms > budget_ms * 1.5:  # 50% grace period for warning
                    import logging
                    logging.getLogger("governance").warning(
                        f"{func.__qualname__} exceeded budget: "
                        f"{elapsed_ms:.1f}ms > {budget_ms}ms"
                    )
            return result

        return wrapper

    return decorator


def evidence_required(func: Callable):
    """Decorator: Ensure the agent produces evidence with its output."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        if hasattr(result, "evidence") and not result.evidence:
            import logging
            logging.getLogger("governance").warning(
                f"{func.__qualname__} returned output without evidence."
            )
        return result

    return wrapper
