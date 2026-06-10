"""
Policy enforcer for the fraud detection platform.

Provides runtime policy enforcement that wraps agent execution
to ensure compliance with governance rules and business policies.
"""

from __future__ import annotations

import logging
from typing import Any

from src.governance.rules import (
    validate_agent_output,
    validate_max_hops,
    validate_max_tool_calls,
    GovernanceViolation,
)
from src.models.config import get_config

logger = logging.getLogger(__name__)


class PolicyEnforcer:
    """
    Central policy enforcement engine.

    Wraps agent outputs with governance validation and tracks
    system-wide compliance metrics.
    """

    def __init__(self):
        self.config = get_config()
        self._violation_count: int = 0
        self._check_count: int = 0
        self._violations_log: list[dict[str, Any]] = []

    def check_agent_output(
        self,
        agent_name: str,
        output: dict[str, Any],
        evidence: list | None = None,
        tool_call_count: int = 0,
        hop_count: int = 0,
    ) -> tuple[bool, list[str]]:
        """
        Validate an agent's output against all governance rules.

        Returns:
            (is_valid, list_of_violations)
        """
        self._check_count += 1
        violations = validate_agent_output(
            agent_name=agent_name,
            output=output,
            evidence=evidence,
            tool_call_count=tool_call_count,
            hop_count=hop_count,
        )

        if violations:
            self._violation_count += len(violations)
            for v in violations:
                logger.warning(f"Policy violation: {v}")
                self._violations_log.append({
                    "agent": agent_name,
                    "violation": v,
                })

        return (len(violations) == 0, violations)

    def check_budget(self, agent_name: str, elapsed_ms: float, budget_ms: float) -> bool:
        """Check if an agent respected its time budget."""
        if elapsed_ms > budget_ms:
            logger.warning(
                f"Budget violation: {agent_name} took {elapsed_ms:.1f}ms "
                f"(budget: {budget_ms}ms)"
            )
            return False
        return True

    def check_tool_calls(self, agent_name: str, count: int) -> bool:
        """Check if an agent exceeded max tool calls."""
        try:
            validate_max_tool_calls(agent_name, count)
            return True
        except GovernanceViolation:
            return False

    def check_hop_count(self, count: int) -> bool:
        """Check if the transaction has exceeded max agent hops."""
        try:
            validate_max_hops(count)
            return True
        except GovernanceViolation:
            return False

    @property
    def stats(self) -> dict[str, Any]:
        """Get enforcement statistics."""
        return {
            "total_checks": self._check_count,
            "total_violations": self._violation_count,
            "violation_rate": (
                self._violation_count / self._check_count
                if self._check_count > 0
                else 0.0
            ),
            "recent_violations": self._violations_log[-10:],
        }

    def reset_stats(self) -> None:
        """Reset enforcement statistics."""
        self._violation_count = 0
        self._check_count = 0
        self._violations_log.clear()
