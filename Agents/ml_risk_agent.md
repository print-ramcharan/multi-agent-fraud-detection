# ML Risk Agent

* **Tier**: Tier 1 (Fast-Path)
* **Default Latency Budget**: 25ms
* **Implementation Class**: `MLRiskAgent` ([ml_risk_agent.py](file:///Users/ram/Desktop/multi-agent-fraud-detection/src/agents/tier1/ml_risk_agent.py))

## 📝 Overview
Fetches statistical predictions from a serialized Random Forest classifier trained on historical transaction datasets.

## 🛠️ Mechanisms & MCP Tools
Queries the `ml_server` MCP service:
* `predict_fraud_score(...)`: Supplies transaction features (amount, channel, merchant category, country, time, risk flags) and returns a probability score $[0.0, 1.0]$.

### Heuristic Fallback
If the model service is offline, the agent automatically executes a deterministic heuristic:
* Base score: `0.1`
* Amount > $5000: `+0.2`
* High risk country: `+0.25`
* High risk merchant: `+0.15`
* Online channel: `+0.05`
* Night hours (1-4 AM): `+0.1`

## 📥 Input Params
* `NormalizedTransaction` containing `amount_usd`, `channel`, `merchant_category`, `country`, `timestamp`, `is_high_risk_country`, and `is_high_risk_merchant`.

## 📤 Output Structure
* `risk_score`: `float | None` (probability $[0.0, 1.0]$)
* `model_version`: `str` (e.g. `rf-v1.2` or `heuristic-1.0`)
* `feature_importances`: `dict` containing feature weights for SHAP-like explainability.
* `evidence`: Contains inference summaries and top feature importances.
