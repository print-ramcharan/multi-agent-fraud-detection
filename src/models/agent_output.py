"""
Agent output schemas.

Defines strongly-typed Pydantic models for every agent's output,
ensuring schema validation at the guardrail layer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Common Types
# ---------------------------------------------------------------------------

class AgentStatus(StrEnum):
    """Execution status of an agent."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


class AgentEvidence(BaseModel):
    """A single piece of evidence supporting an agent's output."""

    source: str = Field(..., description="Agent or tool that produced this evidence")
    claim: str = Field(..., description="What the evidence asserts")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    data: dict[str, Any] = Field(default_factory=dict, description="Raw supporting data")


class AgentOutput(BaseModel):
    """Base wrapper for any agent's output, with metadata."""

    agent_name: str
    status: AgentStatus = AgentStatus.SUCCESS
    duration_ms: float = 0.0
    evidence: list[AgentEvidence] = Field(default_factory=list)
    error: str | None = None
    tool_calls_made: int = 0


# ---------------------------------------------------------------------------
# Tier-1 Agent Outputs
# ---------------------------------------------------------------------------

class BlacklistResult(BaseModel):
    """Output from the Blacklist Agent."""

    blacklisted: bool = Field(False, description="Whether any entity is on a blacklist")
    card_blacklisted: bool = Field(False)
    device_blacklisted: bool = Field(False)
    merchant_blacklisted: bool = Field(False)
    source: str = Field(default="", description="Which blacklist matched (card, device, merchant)")
    match_type: str = Field(default="none", description="Type of match: exact, fuzzy, none")


class RuleResult(BaseModel):
    """Output from the Rule Agent."""

    violation: bool = Field(False, description="Whether any rule was violated")
    rule_name: str = Field(default="", description="Name of the violated rule")
    rule_severity: str = Field(
        default="none", description="Severity: critical, high, medium, low, none"
    )
    violations: list[dict[str, str]] = Field(
        default_factory=list,
        description="All rule violations [{rule, severity, description}]",
    )


class MLRiskResult(BaseModel):
    """Output from the ML Risk Agent."""

    risk_score: float | None = Field(
        None,
        description="Fraud probability score (0.0=safe, 1.0=fraud). None if model unavailable.",
        ge=0.0,
        le=1.0,
    )
    model_version: str = Field(default="1.0.0")
    feature_importances: dict[str, float] = Field(
        default_factory=dict, description="Top contributing features"
    )


class CustomerResult(BaseModel):
    """Output from the Customer Agent."""

    trust_tier: str = Field(
        default="standard", description="Customer trust tier: platinum, gold, silver, standard, new"
    )
    avg_transaction_amount: float = Field(default=0.0, description="Historical average amount (USD)")
    spending_anomaly: float = Field(
        default=0.0,
        description="Z-score of current amount vs. historical average. >2.0 is unusual.",
    )
    account_age_days: int = Field(default=0, description="Days since account creation")
    total_transactions: int = Field(default=0, description="Lifetime transaction count")
    fraud_history: int = Field(default=0, description="Number of past fraud flags")


# ---------------------------------------------------------------------------
# Specialist Agent Outputs
# ---------------------------------------------------------------------------

class GeoResult(BaseModel):
    """Output from the Geo Agent."""

    distance_km: float = Field(default=0.0, description="Distance from last transaction location")
    time_since_last_hours: float = Field(
        default=0.0, description="Hours since last transaction"
    )
    required_speed_kmh: float = Field(
        default=0.0, description="Speed required to travel the distance in given time"
    )
    impossible_travel: bool = Field(False, description="Whether travel is physically impossible")
    last_country: str = Field(default="", description="Country of last transaction")
    cross_border: bool = Field(False, description="Whether this is a cross-border transaction")


class DeviceResult(BaseModel):
    """Output from the Device Agent."""

    new_device: bool = Field(False, description="Device not seen before for this customer")
    device_age_days: int = Field(default=0, description="Days since device first seen")
    shared_device: bool = Field(
        False, description="Device used by multiple customers"
    )
    device_risk: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Composite device risk score"
    )
    anomalies: list[str] = Field(
        default_factory=list, description="Detected device anomalies"
    )


class VelocityResult(BaseModel):
    """Output from the Velocity Agent."""

    transactions_last_hour: int = Field(default=0)
    transactions_last_day: int = Field(default=0)
    amount_last_hour: float = Field(default=0.0, description="Total amount in last hour (USD)")
    amount_last_day: float = Field(default=0.0, description="Total amount in last day (USD)")
    burst: bool = Field(False, description="Abnormal transaction burst detected")
    amount_acceleration: float = Field(
        default=0.0,
        description="Rate of spend increase. >3.0 is suspicious.",
    )
    distinct_merchants_last_hour: int = Field(default=0)


class LLMReasoningResult(BaseModel):
    """Output from the LLM Reasoning Agent (advisory only — cannot decide)."""

    risk_level: str = Field(
        default="MEDIUM", description="Synthesized risk level: LOW, MEDIUM, HIGH, CRITICAL"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_action: str = Field(
        default="ESCALATE", description="Recommended action: APPROVE, DECLINE, ESCALATE"
    )
    reasoning: str = Field(default="", description="Step-by-step reasoning chain")
    evidence_summary: list[str] = Field(
        default_factory=list, description="Summary of key evidence points"
    )
    risk_factors: list[str] = Field(
        default_factory=list, description="Identified risk factors"
    )
    mitigating_factors: list[str] = Field(
        default_factory=list, description="Factors reducing risk"
    )


# ---------------------------------------------------------------------------
# Guardrail Output
# ---------------------------------------------------------------------------

class GuardrailResult(BaseModel):
    """Output from the Guardrail Agent."""

    valid: bool = Field(True, description="Whether the validated output passed all checks")
    violations: list[str] = Field(
        default_factory=list, description="List of guardrail violations"
    )
    evidence_valid: bool = Field(True, description="All claims have supporting evidence")
    schema_valid: bool = Field(True, description="Output matches contract schema")
    policy_valid: bool = Field(True, description="No governance rule violations")
    budget_valid: bool = Field(True, description="Agent respected time budget")
    hallucination_detected: bool = Field(False, description="Invented or impossible facts detected")
