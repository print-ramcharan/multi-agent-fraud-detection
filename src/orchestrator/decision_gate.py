"""
Decision Gate.

Runs fast path validation to avoid specialist agents if possible.
"""

from __future__ import annotations

import logging
from typing import Any

from src.models.agent_output import AgentOutput
from src.models.config import get_config

logger = logging.getLogger(__name__)

class DecisionGate:
    """Evaluates Tier-1 outputs to determine fast paths or escalation."""

    def __init__(self):
        self.config = get_config()

    def evaluate_tier1(
        self,
        outputs: dict[str, AgentOutput],
        results: dict[str, dict[str, Any]]
    ) -> tuple[bool, str]:
        """
        Evaluate Tier-1 results.
        Returns: (is_fast_path_decided, fast_path_decision)
        """
        # 1. Blacklist check
        blacklist_out = results.get("blacklist_agent", {})
        if blacklist_out.get("blacklisted"):
            logger.info("Fast path triggered: DECLINE due to blacklist match")
            return True, "DECLINE"

        # 2. Rule check
        rule_out = results.get("rule_agent", {})
        if rule_out.get("violation") and rule_out.get("rule_severity") == "critical":
            logger.info("Fast path triggered: DECLINE due to critical rule violation")
            return True, "DECLINE"

        # 3. Safe fast approve path check:
        # If ML score is very low, and no violations or blacklist matches, we can fast approve.
        ml_out = results.get("ml_risk_agent", {})
        ml_score = ml_out.get("risk_score")
        
        # If ML model is fully confident it is safe and customer trust tier is solid
        cust_out = results.get("customer_agent", {})
        trust_tier = cust_out.get("trust_tier", "standard")
        
        # Let's define thresholds for fast approve:
        # Platinum, Gold, Silver can fast approve if ML risk < 0.15 and no rule violations
        if trust_tier in ("platinum", "gold", "silver"):
            score_to_check = ml_score if ml_score is not None else 0.05
            if score_to_check < 0.15 and not rule_out.get("violation"):
                logger.info("Fast path triggered: APPROVE for trusted tier with low ML risk")
                return True, "APPROVE"

        # Otherwise, if uncertain, run specialists
        return False, "ESCALATE"
