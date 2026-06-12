# Multi-Agent Platform Overview
## Enterprise Tier-1 Bank Architecture

The platform uses a layered multi-agent system split into **Tier 1 (Fast-Path)** and **Tier 2 (Specialists)**, routed via an **MCP Gateway Layer**, governed by **Constitutional Rules**, and updated asynchronously by a **Feedback Agent Cluster** consuming from a **Kafka Event Bus**.

---

## Latency Budget Allocation (100ms Total)

To satisfy the payment switch's real-time authorization loop, latency is strictly partitioned:

| Phase / Component | Latency Budget | Responsibility |
| :--- | :--- | :--- |
| **Ingress Validation** | 10ms | Spring Boot gateway, payload normalization, signature validation, Redis idempotency. |
| **Orchestrator** | 5ms | LangGraph / custom orchestrator setup and asynchronous futures scheduling. |
| **Blacklist Agent** | 10ms | Card, device, and merchant lookup via MCP Gateway. |
| **Rule Agent** | 5ms | Deterministic checks (sanctions list, channel limits). |
| **Customer Agent** | 20ms | Trust profile retrieval and spending anomaly calculations. |
| **ML Risk Agent** | 25ms | Random Forest score prediction. |
| **Decision Engine** | 10ms | Weighted scoring synthesis and Constitutional Rule check. |
| **Egress** | 5ms | Response payload serialization and response delivery to switch. |
| **Reserve Buffer** | 10ms | Safety margin for scheduling overhead, GC pauses, and network jitter. |

---

## Agent Routing & MCP Topology

```
[ Payment Switch ]
       │
       ▼
[ Spring Boot Ingress ] (10ms)
       │
       ▼
[ LangGraph Orchestrator ] (5ms)
       │
       ├─────────────────────────┼─────────────────────────┐
       ▼                         ▼                         ▼
[ Blacklist Agent ] (10ms)  [ Customer Agent ] (20ms)   [ ML Risk Agent ] (25ms)
       │                         │                         │
       └─────────────────────────┼─────────────────────────┘
                                 ▼
                         [ MCP Gateway Layer ]
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
   [ Blacklist MCP ]       [ Customer MCP ]          [ Geo MCP ]
         │                       │                       │
         ▼                       ▼                       ▼
   [ Blacklist API ]       [ Customer DB ]         [ Geo Service ]
```

---

## Governance Constitution

All actions must comply with our central policies:
* **no_policy_override**: Governance policies cannot be bypassed by agent logic.
* **no_hallucinated_facts**: Agent scores must reside within $[0.0, 1.0]$.
* **evidence_required**: Any warning flags must contain supporting data elements.
* **budget_enforced**: Execution is terminated when remaining time drops below reserve.

---

## Asynchronous Feedback Cluster

Decision logs are streamed to **Kafka topics** (`fraud.decisions`, `fraud.audit`, `fraud.chargebacks`, `fraud.analyst-verdicts`). 

A specialized **Feedback Agent Cluster** processes this feedback loop:
1. **Feedback Orchestrator**: Coordinates subagents.
2. **Correlation Agent**: Correlates chargebacks with past decisions to determine error root causes.
3. **Pattern Mining Agent**: Identifies novel patterns (e.g. `same_device_many_cards`).
4. **Threshold Optimization Agent**: Suggests threshold shifts for Shadow Mode testing.
5. **Governance & Deployment Agent**: Manages progressive config promotion ($1\% \rightarrow 5\% \rightarrow 25\% \rightarrow 50\% \rightarrow \text{Blue-Green Production}$).
