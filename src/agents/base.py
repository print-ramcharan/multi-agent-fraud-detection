"""
Base agent class for the fraud detection platform.

All agents inherit from BaseAgent, which provides:
- Timeout enforcement
- Output schema validation
- Metrics emission
- Evidence chain tracking
- Circuit breaker pattern
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from src.models.agent_output import AgentEvidence, AgentOutput, AgentStatus
from src.models.decision import AuditEntry
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for agent fault tolerance."""

    def __init__(self, threshold: int = 3, reset_seconds: int = 30):
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open:
            # Check if reset window has elapsed
            if time.time() - self._last_failure_time > self.reset_seconds:
                self._is_open = False
                self._failure_count = 0
                return False
        return self._is_open

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.threshold:
            self._is_open = True
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")

    def record_success(self) -> None:
        self._failure_count = 0
        self._is_open = False


class BaseAgent(ABC):
    """
    Abstract base class for all fraud detection agents.

    Provides timeout enforcement, output validation, metrics,
    and evidence chain tracking.
    """

    def __init__(
        self,
        name: str,
        budget_ms: float,
        tier: str,
        version: str = "1.0.0",
    ):
        self.name = name
        self.budget_ms = budget_ms
        self.tier = tier
        self.version = version
        self.circuit_breaker = CircuitBreaker()
        self._total_executions = 0
        self._total_errors = 0
        self._total_timeouts = 0
        self._total_latency_ms = 0.0

    @abstractmethod
    async def _execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Core agent logic — implemented by each agent.

        Args:
            transaction: The normalized transaction to evaluate.
            context: Shared context (e.g., MCP gateway, cache, other agent results).

        Returns:
            Agent-specific result dictionary.
        """
        ...

    async def execute(
        self, transaction: NormalizedTransaction, context: dict[str, Any] | None = None
    ) -> AgentOutput:
        """
        Execute the agent with timeout enforcement and error handling.

        This is the public API called by the orchestrator.
        """
        context = context or {}
        self._total_executions += 1
        start_time = time.perf_counter()
        evidence: list[AgentEvidence] = []
        tool_calls_made = 0

        # Circuit breaker check
        if self.circuit_breaker.is_open:
            logger.warning(f"Agent '{self.name}' circuit breaker is OPEN — skipping")
            return AgentOutput(
                agent_name=self.name,
                status=AgentStatus.SKIPPED,
                duration_ms=0.0,
                error="Circuit breaker open",
            )

        try:
            # Execute with timeout
            timeout_seconds = self.budget_ms / 1000.0
            result = await asyncio.wait_for(
                self._execute(transaction, context),
                timeout=timeout_seconds,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._total_latency_ms += elapsed_ms

            # Extract evidence if present
            if "evidence" in result:
                evidence = [
                    AgentEvidence(**e) if isinstance(e, dict) else e
                    for e in result.pop("evidence", [])
                ]

            tool_calls_made = result.pop("_tool_calls_made", 0)

            self.circuit_breaker.record_success()

            return AgentOutput(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                duration_ms=elapsed_ms,
                evidence=evidence,
                tool_calls_made=tool_calls_made,
            )

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._total_timeouts += 1
            self._total_latency_ms += elapsed_ms
            self.circuit_breaker.record_failure()
            logger.warning(f"Agent '{self.name}' TIMEOUT after {elapsed_ms:.1f}ms")

            return AgentOutput(
                agent_name=self.name,
                status=AgentStatus.TIMEOUT,
                duration_ms=elapsed_ms,
                error=f"Timeout after {elapsed_ms:.1f}ms (budget: {self.budget_ms}ms)",
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._total_errors += 1
            self._total_latency_ms += elapsed_ms
            self.circuit_breaker.record_failure()
            logger.error(f"Agent '{self.name}' ERROR: {e}", exc_info=True)

            return AgentOutput(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                duration_ms=elapsed_ms,
                error=str(e),
            )

    def create_audit_entry(
        self,
        output: AgentOutput,
        result_data: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Create an audit trail entry from agent output."""
        return AuditEntry(
            agent_name=self.name,
            agent_version=self.version,
            tier=self.tier,
            duration_ms=output.duration_ms,
            budget_ms=self.budget_ms,
            status=output.status.value,
            output=result_data or {},
            tool_calls=[
                {"agent": self.name, "count": output.tool_calls_made}
            ] if output.tool_calls_made > 0 else [],
            error=output.error,
            completed_at=datetime.now(timezone.utc),
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Get agent execution statistics."""
        return {
            "name": self.name,
            "total_executions": self._total_executions,
            "total_errors": self._total_errors,
            "total_timeouts": self._total_timeouts,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_executions
                if self._total_executions > 0
                else 0.0
            ),
            "success_rate": (
                (self._total_executions - self._total_errors - self._total_timeouts)
                / self._total_executions
                if self._total_executions > 0
                else 1.0
            ),
            "circuit_breaker_open": self.circuit_breaker.is_open,
        }
