"""
Agent Dispatcher.

Handles parallel agent execution and timeout/error handling.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agents.base import BaseAgent
from src.models.agent_output import AgentOutput, AgentStatus
from src.models.transaction import NormalizedTransaction

logger = logging.getLogger(__name__)

class AgentDispatcher:
    """Dispatches agents and aggregates results with safety limits."""

    def __init__(self, gateway: Any, cache: Any):
        self.gateway = gateway
        self.cache = cache

    async def dispatch_agents(
        self,
        agents: list[BaseAgent],
        transaction: NormalizedTransaction,
        context: dict[str, Any],
        timeout_ms: float,
    ) -> dict[str, AgentOutput]:
        """Dispatch a list of agents in parallel, enforcing a timeout."""
        context_copy = {**context, "gateway": self.gateway, "cache": self.cache}
        
        async def run_agent(agent: BaseAgent) -> tuple[str, AgentOutput]:
            try:
                # Execution has its own internal timeout matching agent budget
                output = await agent.execute(transaction, context_copy)
                return agent.name, output
            except Exception as e:
                logger.error("Error executing agent %s: %s", agent.name, e)
                return agent.name, AgentOutput(
                    agent_name=agent.name,
                    status=AgentStatus.ERROR,
                    error=str(e)
                )

        tasks = [run_agent(agent) for agent in agents]
        
        try:
            # Enforce overall parallel execution timeout
            results = await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=timeout_ms / 1000.0
            )
            return dict(results)
        except asyncio.TimeoutError:
            logger.warning("Parallel dispatch timed out overall after %dms", timeout_ms)
            # Create timeout responses for any pending agents
            return {
                agent.name: AgentOutput(
                    agent_name=agent.name,
                    status=AgentStatus.TIMEOUT,
                    error=f"Parallel dispatch timeout (overall: {timeout_ms}ms)"
                )
                for agent in agents
            }
