"""
Orchestration Engine.

Manages the core transaction execution pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.models.config import get_config
from src.models.transaction import NormalizedTransaction
from src.models.decision import DecisionResult, AuditTrail, AuditEntry, Decision
from src.models.agent_output import AgentStatus
from src.agents.tier1.blacklist_agent import BlacklistAgent
from src.agents.tier1.rule_agent import RuleAgent
from src.agents.tier1.ml_risk_agent import MLRiskAgent
from src.agents.tier1.customer_agent import CustomerAgent
from src.agents.specialist.geo_agent import GeoAgent
from src.agents.specialist.device_agent import DeviceAgent
from src.agents.specialist.velocity_agent import VelocityAgent
from src.agents.specialist.llm_reasoning import LLMReasoningAgent
from src.agents.guardrail_agent import GuardrailAgent
from src.agents.decision_engine import DecisionEngine
from src.orchestrator.budget import LatencyBudget
from src.orchestrator.dispatcher import AgentDispatcher
from src.orchestrator.decision_gate import DecisionGate
from src.mcp.gateway import MCPGateway

logger = logging.getLogger(__name__)

class FraudOrchestrator:
    """Core orchestration engine coordinating all agents and MCP services."""

    def __init__(self, cache: Any, audit_store: Any, event_bus: Any, metrics: Any):
        self.config = get_config()
        self.cache = cache
        self.audit_store = audit_store
        self.event_bus = event_bus
        self.metrics = metrics
        
        self.gateway = MCPGateway()
        self.dispatcher = AgentDispatcher(self.gateway, self.cache)
        self.decision_gate = DecisionGate()
        self.guardrail = GuardrailAgent()
        self.decision_engine = DecisionEngine()
        
        # Instantiate agents
        self.tier1_agents = [
            BlacklistAgent(budget_ms=self.config.blacklist_agent_budget_ms),
            RuleAgent(budget_ms=self.config.rule_agent_budget_ms),
            MLRiskAgent(budget_ms=self.config.ml_risk_agent_budget_ms),
            CustomerAgent(budget_ms=self.config.customer_agent_budget_ms),
        ]
        
        self.specialist_agents = [
            GeoAgent(budget_ms=self.config.geo_agent_budget_ms),
            DeviceAgent(budget_ms=self.config.device_agent_budget_ms),
            VelocityAgent(budget_ms=self.config.velocity_agent_budget_ms),
        ]
        if self.config.llm_enabled:
            self.specialist_agents.append(
                LLMReasoningAgent(budget_ms=self.config.llm_reasoning_budget_ms)
            )

    async def evaluate_transaction(self, transaction: NormalizedTransaction) -> DecisionResult:
        """Evaluate a transaction end-to-end within SLA budget."""
        budget = LatencyBudget(self.config.total_budget_ms)
        audit_trail = AuditTrail(
            transaction_id=transaction.transaction_id,
            request_id=transaction.request_id
        )
        
        # Keep track of individual execution records
        tier1_outputs = {}
        tier1_data = {}
        
        # Context to share across executions
        context: dict[str, Any] = {}
        
        # Step 1: Run Tier-1 Agents in parallel
        t1_budget = self.config.tier1_budget_ms
        logger.info("Dispatching Tier-1 agents for transaction %s", transaction.transaction_id)
        t1_results = await self.dispatcher.dispatch_agents(
            self.tier1_agents, transaction, context, t1_budget
        )
        
        for name, output in t1_results.items():
            tier1_outputs[name] = output
            # Extract raw result payload if available
            raw_payload = {}
            if output.status == AgentStatus.SUCCESS:
                # Retrieve from cache/evidence structure or reconstruct
                for ev in output.evidence:
                    raw_payload.update(ev.data)
            
            # Populate fallback keys to prevent KeyErrors
            if name == "blacklist_agent":
                raw_payload.setdefault("blacklisted", False)
            elif name == "rule_agent":
                raw_payload.setdefault("violation", False)
            elif name == "ml_risk_agent":
                raw_payload.setdefault("risk_score", None)
            elif name == "customer_agent":
                raw_payload.setdefault("trust_tier", "standard")
                
            tier1_data[name] = raw_payload
            
            # Guardrail validation of agent output
            gr_context = {
                "target_agent": name,
                "target_output": raw_payload,
                "target_evidence": output.evidence,
                "target_duration_ms": output.duration_ms,
                "target_budget_ms": next(a.budget_ms for a in self.tier1_agents if a.name == name),
                "tool_call_count": output.tool_calls_made,
                "hop_count": audit_trail.agent_hop_count + 1,
            }
            gr_out = await self.guardrail.execute(transaction, gr_context)
            
            audit_entry = next(a for a in self.tier1_agents if a.name == name).create_audit_entry(output, raw_payload)
            audit_entry.guardrail_valid = gr_out.status == AgentStatus.SUCCESS and gr_out.error is None
            audit_trail.add_entry(audit_entry)

        # Step 2: Check Decision Gate for fast path decision
        decided, fast_decision = self.decision_gate.evaluate_tier1(tier1_outputs, tier1_data)
        
        specialist_data = {}
        if decided:
            audit_trail.fast_path_used = True
            logger.info("Decision Gate fast path triggered: %s", fast_decision)
            
            # Run final decision engine directly
            final_result = await self.decision_engine.decide(
                transaction,
                tier1_data,
                specialist_results=None,
                audit_trail=audit_trail,
                processing_time_ms=budget.elapsed_ms(),
                fast_path=True
            )
            audit_trail.finalize(budget.elapsed_ms())
            # Save and publish async
            await self.audit_store.store_decision(final_result)
            await self.event_bus.publish("decisions.out", final_result.model_dump())
            return final_result

        # Step 3: Run Specialist Agents if budget allows
        audit_trail.specialists_invoked = True
        remaining = budget.remaining_ms()
        # Allocate remaining budget minus safety margin for decision/egress (~15ms)
        spec_budget = max(5.0, remaining - 15.0)
        
        logger.info("Fast path skipped. Dispatching specialists with remaining budget: %.1fms", spec_budget)
        
        # Populate context with Tier-1 outputs for specialists to read
        context.update(tier1_data)
        
        spec_results = await self.dispatcher.dispatch_agents(
            self.specialist_agents, transaction, context, spec_budget
        )
        
        for name, output in spec_results.items():
            raw_payload = {}
            if output.status == AgentStatus.SUCCESS:
                for ev in output.evidence:
                    raw_payload.update(ev.data)
            
            # Fallback mappings
            if name == "geo_agent":
                raw_payload.setdefault("impossible_travel", False)
            elif name == "device_agent":
                raw_payload.setdefault("device_risk", 0.0)
            elif name == "velocity_agent":
                raw_payload.setdefault("burst", False)
            elif name == "llm_reasoning_agent":
                raw_payload.setdefault("risk_level", "MEDIUM")
                
            specialist_data[name] = raw_payload
            
            # Guardrail validation of agent output
            gr_context = {
                "target_agent": name,
                "target_output": raw_payload,
                "target_evidence": output.evidence,
                "target_duration_ms": output.duration_ms,
                "target_budget_ms": next(a.budget_ms for a in self.specialist_agents if a.name == name),
                "tool_call_count": output.tool_calls_made,
                "hop_count": audit_trail.agent_hop_count + 1,
            }
            gr_out = await self.guardrail.execute(transaction, gr_context)
            
            audit_entry = next(a for a in self.specialist_agents if a.name == name).create_audit_entry(output, raw_payload)
            audit_entry.guardrail_valid = gr_out.status == AgentStatus.SUCCESS and gr_out.error is None
            audit_trail.add_entry(audit_entry)

        # Step 4: Final Decision Engine Invocation
        final_result = await self.decision_engine.decide(
            transaction,
            tier1_data,
            specialist_results=specialist_data,
            audit_trail=audit_trail,
            processing_time_ms=budget.elapsed_ms(),
            fast_path=False
        )
        
        audit_trail.finalize(budget.elapsed_ms())
        # Store audit trail and emit events asynchronously
        await self.audit_store.store_decision(final_result)
        await self.event_bus.publish("decisions.out", final_result.model_dump())
        
        # Track metrics
        self.metrics.increment("transactions_total")
        self.metrics.increment(f"decisions_total_{final_result.decision.value}")
        self.metrics.record_latency(budget.elapsed_ms())
        
        return final_result
