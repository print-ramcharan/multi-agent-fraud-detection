# Project Guide: Multi-Agent Real-Time Fraud Detection & Escalation Platform

This repository contains the architecture design, latency allocations, and agent specifications for a production-grade, low-latency financial fraud detection platform.

---

## The Problem & Operational Context

In modern banking systems, processing card network transactions requires balancing speed with precision. The platform addresses several critical real-time engineering challenges:

1. **Strict Latency Constraints (100ms SLA)**: Payment switches require sync card authorization loops to complete within 100ms. If processing breaches this window, the transaction defaults or fails, causing high friction.
2. **Incomplete Information**: Critical outcome data (disputes, chargebacks, customer refunds) arrives days or weeks after a transaction is approved. Decisions must therefore be made in real-time based on local historical snapshots and dynamic profile calculations.
3. **Asymmetric Error Costs**:
   - *False Positive*: Rejecting a legitimate transaction leads to immediate revenue loss and severe customer friction.
   - *False Negative*: Approving a fraudulent transaction leads to direct chargeback fees, penalty interest, and compliance exposure.
4. **Agent Coordination**: Decoupling risk checks into specialist agents (Geo-location, Device Age, Velocity, Machine Learning Models, and Rule Engines) requires an efficient orchestration layer that runs checks in parallel and can abort/escalate gracefully before SLA exhaustion.

---

## Repository Guide & Shared Deliverables

When reviewing this solution, only the following files and directories are shared and should be read to understand the design:

1. **[README.md](file:///Users/ram/Desktop/multi-agent-fraud-detection/README.md)** (This document): The entry point detailing the problem statement, repository organization, files reading sequence, and developer prompts.
2. **[Solution.md](file:///Users/ram/Desktop/multi-agent-fraud-detection/Solution.md)**: The core system architecture design. It details the complete topology, latency budget tables, the Model Context Protocol (MCP) gateway specification, governance constitutions, and the asynchronous feedback loop.
3. **[Agents/](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents)**: Directory containing comprehensive specifications for each participating agent, including their default latency budgets, tools, execution mechanisms, and exact JSON schemas for inputs and outputs:
   - [Agents Overview](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/overview.md)
   - [Blacklist Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/blacklist_agent.md)
   - [Rule Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/rule_agent.md)
   - [Customer Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/customer_agent.md)
   - [ML Risk Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/ml_risk_agent.md)
   - [Geo Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/geo_agent.md)
   - [Device Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/device_agent.md)
   - [Velocity Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/velocity_agent.md)
   - [LLM Reasoning Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/llm_reasoning_agent.md)
   - [Guardrail Agent](file:///Users/ram/Desktop/multi-agent-fraud-detection/Agents/guardrail_agent.md)

---

## Repository Reference
- **GitHub Repository Link**: [https://github.com/ram/multi-agent-fraud-detection](https://github.com/ram/multi-agent-fraud-detection)

---

## Developer Prompts (Placeholders)

*These sections serve as placeholders for detailed generative prompts which will be added shortly.*

### 1. ChatGPT / Claude Master Prompt
> [!NOTE]
> *Placeholder for the presentation master prompt. Copy and paste your customized system prompts here once defined.*

```text
[INSERT CHATGPT/CLAUDE MASTER PROMPT HERE]
```

### 2. Vibecoding Prompt
> [!NOTE]
> *Placeholder for the developer/vibecoding prompt. Copy and paste your customized code-generation instructions here once defined.*

```text
[INSERT VIBECODING PROMPT HERE]
```
