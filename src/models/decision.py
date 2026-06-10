"""
Decision domain models.

Defines the final decision outcome, risk levels, audit trail entries,
and the full evidence chain for regulatory compliance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Decision(StrEnum):
    """Final transaction decision."""

    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    ESCALATE = "ESCALATE"


class RiskLevel(StrEnum):
    """Computed risk level from signal aggregation."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationReason(StrEnum):
    """Reason for escalation when decision is ESCALATE."""

    CONFLICTING_SIGNALS = "CONFLICTING_SIGNALS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    ML_MODEL_UNAVAILABLE = "ML_MODEL_UNAVAILABLE"
    HIGH_AMOUNT_NEW_PATTERN = "HIGH_AMOUNT_NEW_PATTERN"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    GUARDRAIL_VIOLATION = "GUARDRAIL_VIOLATION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class AuditEntry(BaseModel):
    """Single audit log entry for one agent invocation."""

    agent_name: str = Field(..., description="Name of the agent")
    agent_version: str = Field(default="1.0.0", description="Agent version")
    tier: str = Field(..., description="Agent tier: tier1, specialist, guardrail, decision")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    duration_ms: float = Field(default=0.0, description="Agent execution time in ms")
    budget_ms: float = Field(..., description="Allocated budget in ms")
    status: str = Field(default="pending", description="success, timeout, error, skipped")
    output: dict[str, Any] = Field(default_factory=dict, description="Agent output payload")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="MCP tool calls made by this agent"
    )
    guardrail_valid: bool | None = Field(
        default=None, description="Whether guardrail validated this output"
    )
    error: str | None = Field(default=None, description="Error message if failed")


class AuditTrail(BaseModel):
    """Complete audit trail for a transaction decision — fully replayable."""

    transaction_id: str
    request_id: str
    entries: list[AuditEntry] = Field(default_factory=list)
    total_duration_ms: float = Field(default=0.0)
    agent_hop_count: int = Field(default=0)
    total_tool_calls: int = Field(default=0)
    governance_violations: list[str] = Field(default_factory=list)
    fast_path_used: bool = Field(
        default=False, description="Whether fast approve/decline was used"
    )
    specialists_invoked: bool = Field(
        default=False, description="Whether specialist agents were needed"
    )

    def add_entry(self, entry: AuditEntry) -> None:
        """Add an audit entry and update counters."""
        self.entries.append(entry)
        self.agent_hop_count += 1
        self.total_tool_calls += len(entry.tool_calls)

    def finalize(self, total_ms: float) -> None:
        """Finalize the audit trail with total processing time."""
        self.total_duration_ms = total_ms


class DecisionResult(BaseModel):
    """Final decision output returned to the caller."""

    transaction_id: str
    decision: Decision
    confidence: float = Field(..., ge=0.0, le=1.0, description="Decision confidence score")
    risk_level: RiskLevel
    reason: str = Field(default="", description="Human-readable decision reason")
    reasons: list[str] = Field(default_factory=list, description="All contributing reasons")
    escalation_reason: EscalationReason | None = Field(
        default=None, description="Specific escalation reason if ESCALATE"
    )
    evidence: list[dict[str, Any]] = Field(
        default_factory=list, description="Evidence chain supporting the decision"
    )
    composite_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Weighted composite risk score"
    )
    processing_time_ms: float = Field(default=0.0, description="Total processing time in ms")
    fast_path: bool = Field(default=False, description="Whether fast path was used")
    audit_trail: AuditTrail | None = Field(default=None, description="Full audit trail")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "transaction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "decision": "APPROVE",
                "confidence": 0.96,
                "risk_level": "LOW",
                "reason": "Low risk transaction from trusted customer",
                "processing_time_ms": 42.5,
                "fast_path": True,
            },
            {
                "transaction_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "decision": "DECLINE",
                "confidence": 0.97,
                "risk_level": "CRITICAL",
                "reason": "Blacklisted device",
                "processing_time_ms": 15.2,
                "fast_path": True,
            },
            {
                "transaction_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                "decision": "ESCALATE",
                "confidence": 0.84,
                "risk_level": "HIGH",
                "reason": "Conflicting risk signals",
                "escalation_reason": "CONFLICTING_SIGNALS",
                "processing_time_ms": 87.3,
                "fast_path": False,
            },
        ]
    }}
