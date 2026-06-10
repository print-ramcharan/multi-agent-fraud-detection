"""
Decision Engine — Final Decision Maker

The ONLY component authorized to make APPROVE / DECLINE / ESCALATE decisions.
Combines weighted signals from all agents into a composite risk score
and applies configurable thresholds per customer tier.
"""

from __future__ import annotations

import logging
from typing import Any

from src.models.agent_output import (
    BlacklistResult,
    CustomerResult,
    DeviceResult,
    GeoResult,
    LLMReasoningResult,
    MLRiskResult,
    RuleResult,
    VelocityResult,
)
from src.models.config import get_config
from src.models.decision import (
    AuditTrail,
    Decision,
    DecisionResult,
    EscalationReason,
    RiskLevel,
)
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Final decision maker.

    Governance Rule 1: ONLY this component can decide.
    Governance Rule 6: Policy always wins.
    Governance Rule 7: Fail safe → ESCALATE.
    """

    def __init__(self):
        self.config = get_config()

    async def decide(
        self,
        transaction: NormalizedTransaction,
        tier1_results: dict[str, dict[str, Any]],
        specialist_results: dict[str, dict[str, Any]] | None = None,
        audit_trail: AuditTrail | None = None,
        processing_time_ms: float = 0.0,
        fast_path: bool = False,
    ) -> DecisionResult:
        """
        Make the final decision based on all available signals.

        Args:
            transaction: The normalized transaction.
            tier1_results: Results from Tier-1 agents.
            specialist_results: Results from specialist agents (if invoked).
            audit_trail: The audit trail for this transaction.
            processing_time_ms: Total processing time so far.
            fast_path: Whether fast path was used.
        """
        specialist_results = specialist_results or {}
        reasons: list[str] = []
        evidence: list[dict[str, Any]] = []

        # --- Extract signals ---
        blacklist = self._parse_blacklist(tier1_results.get("blacklist_agent", {}))
        rules = self._parse_rules(tier1_results.get("rule_agent", {}))
        ml_risk = self._parse_ml_risk(tier1_results.get("ml_risk_agent", {}))
        customer = self._parse_customer(tier1_results.get("customer_agent", {}))
        geo = self._parse_geo(specialist_results.get("geo_agent", {}))
        device = self._parse_device(specialist_results.get("device_agent", {}))
        velocity = self._parse_velocity(specialist_results.get("velocity_agent", {}))
        llm = self._parse_llm(specialist_results.get("llm_reasoning_agent", {}))

        # --- Hard signals (immediate decision) ---

        # Blacklist hit → DECLINE
        if blacklist.blacklisted:
            reasons.append(f"Blacklisted {blacklist.source}")
            evidence.append({"signal": "blacklist", "source": blacklist.source})
            return self._make_result(
                transaction, Decision.DECLINE, 0.98, RiskLevel.CRITICAL,
                reasons, evidence, 0.95, processing_time_ms, fast_path, audit_trail,
            )

        # Critical rule violation → DECLINE
        if rules.violation and rules.rule_severity == "critical":
            reasons.append(f"Critical rule violation: {rules.rule_name}")
            evidence.append({"signal": "rule", "rule": rules.rule_name})
            return self._make_result(
                transaction, Decision.DECLINE, 0.97, RiskLevel.CRITICAL,
                reasons, evidence, 0.9, processing_time_ms, fast_path, audit_trail,
            )

        # --- Composite score computation ---
        composite_score = self._compute_composite_score(
            blacklist, rules, ml_risk, customer, geo, device, velocity, llm, reasons
        )

        # --- Determine thresholds based on customer tier ---
        approve_threshold, decline_threshold = self._get_thresholds(customer.trust_tier)

        # --- Decision logic ---
        if composite_score <= approve_threshold:
            risk_level = RiskLevel.LOW
            decision = Decision.APPROVE
            confidence = 1.0 - composite_score
            reasons.append("Low composite risk score")

        elif composite_score >= decline_threshold:
            risk_level = RiskLevel.HIGH if composite_score < 0.85 else RiskLevel.CRITICAL
            decision = Decision.DECLINE
            confidence = composite_score
            reasons.append("High composite risk score")

        else:
            # UNCERTAIN → ESCALATE (Governance Rule 7: fail safe)
            risk_level = RiskLevel.MEDIUM if composite_score < 0.5 else RiskLevel.HIGH
            decision = Decision.ESCALATE
            confidence = 1.0 - abs(composite_score - 0.5) * 2

            escalation_reason = self._determine_escalation_reason(
                ml_risk, customer, geo, device, velocity
            )
            reasons.append(f"Uncertain risk — escalated ({escalation_reason.value})")

            return self._make_result(
                transaction, decision, confidence, risk_level,
                reasons, evidence, composite_score, processing_time_ms,
                fast_path, audit_trail, escalation_reason,
            )

        return self._make_result(
            transaction, decision, confidence, risk_level,
            reasons, evidence, composite_score, processing_time_ms,
            fast_path, audit_trail,
        )

    def _compute_composite_score(
        self,
        blacklist: BlacklistResult,
        rules: RuleResult,
        ml_risk: MLRiskResult,
        customer: CustomerResult,
        geo: GeoResult,
        device: DeviceResult,
        velocity: VelocityResult,
        llm: LLMReasoningResult,
        reasons: list[str],
    ) -> float:
        """Compute weighted composite risk score from all signals."""
        w = self.config
        total_weight = 0.0
        weighted_sum = 0.0

        # Blacklist signal
        if blacklist.blacklisted:
            weighted_sum += w.weight_blacklist * 1.0
            total_weight += w.weight_blacklist
            reasons.append(f"Blacklist match: {blacklist.source}")
        else:
            total_weight += w.weight_blacklist

        # Rule signal
        severity_scores = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2, "none": 0.0}
        rule_score = severity_scores.get(rules.rule_severity, 0.0)
        weighted_sum += w.weight_rule * rule_score
        total_weight += w.weight_rule
        if rules.violation:
            reasons.append(f"Rule violation: {rules.rule_name} ({rules.rule_severity})")

        # ML risk signal
        if ml_risk.risk_score is not None:
            weighted_sum += w.weight_ml_risk * ml_risk.risk_score
            total_weight += w.weight_ml_risk
            if ml_risk.risk_score > 0.5:
                reasons.append(f"ML risk score: {ml_risk.risk_score:.2f}")

        # Customer trust signal (inverted — higher trust = lower risk)
        trust_scores = {
            "platinum": 0.05, "gold": 0.1, "silver": 0.2,
            "standard": 0.3, "new": 0.5,
        }
        customer_risk = trust_scores.get(customer.trust_tier, 0.3)

        # Spending anomaly adds risk
        if customer.spending_anomaly > 2.0:
            customer_risk += min(customer.spending_anomaly * 0.1, 0.3)
            reasons.append(f"Spending anomaly: {customer.spending_anomaly:.1f}σ")

        # Fraud history adds risk
        if customer.fraud_history > 0:
            customer_risk += min(customer.fraud_history * 0.15, 0.4)
            reasons.append(f"Prior fraud flags: {customer.fraud_history}")

        weighted_sum += w.weight_customer * min(customer_risk, 1.0)
        total_weight += w.weight_customer

        # Geo signal (specialist — may be 0 if not invoked)
        if geo.impossible_travel:
            weighted_sum += w.weight_geo * 0.9
            total_weight += w.weight_geo
            reasons.append(f"Impossible travel: {geo.distance_km:.0f}km")
        elif geo.cross_border:
            weighted_sum += w.weight_geo * 0.3
            total_weight += w.weight_geo
        elif geo.distance_km > 0:
            total_weight += w.weight_geo

        # Device signal
        if device.device_risk > 0:
            weighted_sum += w.weight_device * device.device_risk
            total_weight += w.weight_device
            if device.new_device:
                reasons.append("New device")
            if device.shared_device:
                reasons.append("Shared device")
        elif device.device_risk == 0 and not device.new_device:
            total_weight += w.weight_device

        # Velocity signal
        if velocity.burst:
            weighted_sum += w.weight_velocity * 0.8
            total_weight += w.weight_velocity
            reasons.append(
                f"Velocity burst: {velocity.transactions_last_hour} txns/hour"
            )
        elif velocity.transactions_last_hour > 0:
            total_weight += w.weight_velocity

        # LLM advisory signal (low weight)
        llm_risk_map = {"LOW": 0.1, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 0.9}
        llm_score = llm_risk_map.get(llm.risk_level, 0.4)
        weighted_sum += w.weight_llm * llm_score
        total_weight += w.weight_llm

        # Normalize
        if total_weight > 0:
            composite = weighted_sum / total_weight
        else:
            composite = 0.5  # No data → uncertain

        return round(min(max(composite, 0.0), 1.0), 4)

    def _get_thresholds(self, trust_tier: str) -> tuple[float, float]:
        """Get decision thresholds adjusted for customer tier."""
        tier_thresholds = {
            "platinum": (self.config.platinum_approve_threshold, 0.75),
            "gold": (self.config.gold_approve_threshold, 0.72),
            "silver": (self.config.silver_approve_threshold, 0.7),
            "standard": (self.config.standard_approve_threshold, 0.68),
            "new": (self.config.new_approve_threshold, 0.6),
        }
        return tier_thresholds.get(
            trust_tier,
            (self.config.approve_threshold, self.config.decline_threshold),
        )

    @staticmethod
    def _determine_escalation_reason(
        ml_risk: MLRiskResult,
        customer: CustomerResult,
        geo: GeoResult,
        device: DeviceResult,
        velocity: VelocityResult,
    ) -> EscalationReason:
        """Determine the most specific escalation reason."""
        if ml_risk.risk_score is None:
            return EscalationReason.ML_MODEL_UNAVAILABLE

        if geo.impossible_travel or (velocity.burst and device.new_device):
            return EscalationReason.CONFLICTING_SIGNALS

        if customer.trust_tier == "new" and customer.total_transactions < 3:
            return EscalationReason.INSUFFICIENT_DATA

        if customer.spending_anomaly > 3.0:
            return EscalationReason.HIGH_AMOUNT_NEW_PATTERN

        return EscalationReason.CONFLICTING_SIGNALS

    @staticmethod
    def _make_result(
        transaction: NormalizedTransaction,
        decision: Decision,
        confidence: float,
        risk_level: RiskLevel,
        reasons: list[str],
        evidence: list[dict[str, Any]],
        composite_score: float,
        processing_time_ms: float,
        fast_path: bool,
        audit_trail: AuditTrail | None,
        escalation_reason: EscalationReason | None = None,
    ) -> DecisionResult:
        return DecisionResult(
            transaction_id=transaction.transaction_id,
            decision=decision,
            confidence=round(min(max(confidence, 0.0), 1.0), 4),
            risk_level=risk_level,
            reason=reasons[0] if reasons else "",
            reasons=reasons,
            escalation_reason=escalation_reason,
            evidence=evidence,
            composite_score=composite_score,
            processing_time_ms=round(processing_time_ms, 2),
            fast_path=fast_path,
            audit_trail=audit_trail,
        )

    # --- Signal parsers (safe extraction from dicts) ---

    @staticmethod
    def _parse_blacklist(data: dict) -> BlacklistResult:
        try:
            return BlacklistResult(**{k: v for k, v in data.items()
                                      if k in BlacklistResult.model_fields})
        except Exception:
            return BlacklistResult()

    @staticmethod
    def _parse_rules(data: dict) -> RuleResult:
        try:
            return RuleResult(**{k: v for k, v in data.items()
                                 if k in RuleResult.model_fields})
        except Exception:
            return RuleResult()

    @staticmethod
    def _parse_ml_risk(data: dict) -> MLRiskResult:
        try:
            return MLRiskResult(**{k: v for k, v in data.items()
                                   if k in MLRiskResult.model_fields})
        except Exception:
            return MLRiskResult()

    @staticmethod
    def _parse_customer(data: dict) -> CustomerResult:
        try:
            return CustomerResult(**{k: v for k, v in data.items()
                                     if k in CustomerResult.model_fields})
        except Exception:
            return CustomerResult()

    @staticmethod
    def _parse_geo(data: dict) -> GeoResult:
        try:
            return GeoResult(**{k: v for k, v in data.items()
                                if k in GeoResult.model_fields})
        except Exception:
            return GeoResult()

    @staticmethod
    def _parse_device(data: dict) -> DeviceResult:
        try:
            return DeviceResult(**{k: v for k, v in data.items()
                                   if k in DeviceResult.model_fields})
        except Exception:
            return DeviceResult()

    @staticmethod
    def _parse_velocity(data: dict) -> VelocityResult:
        try:
            return VelocityResult(**{k: v for k, v in data.items()
                                     if k in VelocityResult.model_fields})
        except Exception:
            return VelocityResult()

    @staticmethod
    def _parse_llm(data: dict) -> LLMReasoningResult:
        try:
            return LLMReasoningResult(**{k: v for k, v in data.items()
                                         if k in LLMReasoningResult.model_fields})
        except Exception:
            return LLMReasoningResult()
