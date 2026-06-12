# LLM Reasoning Agent

* **Tier**: Tier 2 (Specialist)
* **Default Latency Budget**: 20ms
* **Implementation Class**: `LLMReasoningAgent` ([llm_reasoning.py](file:///Users/ram/Desktop/multi-agent-fraud-detection/src/agents/specialist/llm_reasoning.py))

## 📝 Overview
An advisory agent that leverages the **Google Antigravity (AGY) SDK** to perform a cognitive synthesis of evidence gathered from all preceding agents. 

> [!IMPORTANT]
> **Advisory Only**: In compliance with security standards, the LLM reasoning agent is not authorized to make final block/approve decisions. It only issues recommendations (`APPROVE`, `DECLINE`, `ESCALATE`) along with structured reasoning.

## 🛠️ Mechanisms & Integration
Uses the Google Antigravity SDK:
1. Constructs a structured prompt detailing current transaction attributes and collected Tier 1 + Specialist outputs.
2. Invokes the local agent endpoint using `google.antigravity.Agent` and parses structured JSON output matching a strict `RiskAssessment` Pydantic schema.
3. Automatically falls back to a deterministic rule-based synthesis if the SDK is unavailable, disabled, or times out.

## 📥 Input Params
* `NormalizedTransaction`
* Shared context dictionary containing `tier1_results` and `specialist_results`.

## 📤 Output Structure
* `risk_level`: `str` ("LOW" | "MEDIUM" | "HIGH" | "CRITICAL")
* `confidence`: `float` ($[0.0, 1.0]$)
* `recommended_action`: `str` ("APPROVE" | "DECLINE" | "ESCALATE")
* `reasoning`: `str` (natural language justification)
* `evidence_summary`: List of facts extracted.
* `risk_factors`: List of risk markers identified.
* `mitigating_factors`: List of positive patterns.
