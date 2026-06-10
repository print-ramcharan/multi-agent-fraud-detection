"""
System configuration models.

Centralized configuration for the fraud detection platform,
loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SystemConfig(BaseSettings):
    """Global system configuration."""

    # --- Server ---
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server bind port")
    env: str = Field(default="development", description="Environment: development, staging, production")

    # --- Decision Thresholds ---
    approve_threshold: float = Field(
        default=0.3, ge=0.0, le=1.0,
        description="Composite score below this → APPROVE",
    )
    decline_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0,
        description="Composite score above this → DECLINE",
    )

    # --- Latency Budget (ms) ---
    total_budget_ms: float = Field(default=100.0, description="Total latency budget in ms")
    ingress_budget_ms: float = Field(default=10.0)
    orchestrator_budget_ms: float = Field(default=5.0)
    tier1_budget_ms: float = Field(default=25.0)
    gate_budget_ms: float = Field(default=5.0)
    specialist_budget_ms: float = Field(default=35.0)
    guardrail_budget_ms: float = Field(default=5.0)
    decision_budget_ms: float = Field(default=5.0)
    egress_budget_ms: float = Field(default=10.0)

    # --- Agent Budgets (ms) ---
    blacklist_agent_budget_ms: float = Field(default=10.0)
    rule_agent_budget_ms: float = Field(default=5.0)
    ml_risk_agent_budget_ms: float = Field(default=25.0)
    customer_agent_budget_ms: float = Field(default=20.0)
    geo_agent_budget_ms: float = Field(default=15.0)
    device_agent_budget_ms: float = Field(default=10.0)
    velocity_agent_budget_ms: float = Field(default=10.0)
    llm_reasoning_budget_ms: float = Field(default=20.0)

    # --- Governance ---
    max_agent_hops: int = Field(default=5, description="Maximum agent invocations per transaction")
    max_tool_calls: int = Field(default=3, description="Maximum MCP tool calls per agent")
    max_tool_calls_total: int = Field(default=15, description="Maximum total tool calls per transaction")

    # --- Signal Weights ---
    weight_blacklist: float = Field(default=10.0, description="Blacklist signal weight")
    weight_rule: float = Field(default=8.0, description="Rule violation signal weight")
    weight_ml_risk: float = Field(default=5.0, description="ML risk score weight")
    weight_customer: float = Field(default=3.0, description="Customer trust weight")
    weight_geo: float = Field(default=4.0, description="Geo anomaly weight")
    weight_device: float = Field(default=3.0, description="Device risk weight")
    weight_velocity: float = Field(default=4.0, description="Velocity burst weight")
    weight_llm: float = Field(default=2.0, description="LLM recommendation weight (advisory)")

    # --- Trust Tier Overrides ---
    platinum_approve_threshold: float = Field(default=0.4)
    gold_approve_threshold: float = Field(default=0.35)
    silver_approve_threshold: float = Field(default=0.3)
    standard_approve_threshold: float = Field(default=0.25)
    new_approve_threshold: float = Field(default=0.2)

    # --- Infrastructure ---
    redis_url: str = Field(default="", description="Redis connection URL (empty = in-memory)")
    database_url: str = Field(default="", description="PostgreSQL URL (empty = SQLite)")
    kafka_bootstrap_servers: str = Field(default="", description="Kafka servers (empty = in-memory)")

    # --- LLM ---
    gemini_api_key: str = Field(default="", description="Google Gemini API key for LLM agent")
    llm_enabled: bool = Field(default=False, description="Whether to use LLM reasoning agent")

    # --- Deduplication ---
    dedup_ttl_seconds: int = Field(default=300, description="Dedup window in seconds")

    # --- Circuit Breaker ---
    circuit_breaker_threshold: int = Field(
        default=3, description="Failures before agent circuit opens"
    )
    circuit_breaker_reset_seconds: int = Field(default=30, description="Reset window")

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


# Singleton config instance
_config: SystemConfig | None = None


def get_config() -> SystemConfig:
    """Get or create the singleton SystemConfig."""
    global _config
    if _config is None:
        _config = SystemConfig()
    return _config
