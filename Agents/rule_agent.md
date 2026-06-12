# Rule Agent

* **Tier**: Tier 1 (Fast-Path)
* **Default Latency Budget**: 5ms
* **Implementation Class**: `RuleAgent` ([rule_agent.py](file:///Users/ram/Desktop/multi-agent-fraud-detection/src/agents/tier1/rule_agent.py))

## 📝 Overview
Executes deterministic, compliance-driven business rules. This agent requires no external database or network lookups, making it highly reliable and extremely fast (<2ms).

## ⚙️ Rules Evaluated
1. **Sanctioned Country Check**: Compares the transaction country against sanctioned territories (`KP`, `IR`, `SY`, `CU`, `SD`). A match raises a **critical** violation (unconditional decline).
2. **High-Risk Country Check**: Flags transactions from high-risk locations.
3. **High-Risk Merchant Category**: Flags risky merchant industries (e.g., casinos, crypto exchanges).
4. **Channel Limit Breaches**: Checks if transaction amount exceeds channel limits:
   * Online: $10,000
   * POS: $5,000
   * ATM: $2,000
   * Mobile: $10,000
   * Banking: $50,000
5. **Suspicious Hour**: Flags transactions occurring during restricted hours (1:00 AM - 5:00 AM UTC).
6. **Very High Amount**: Flags any transaction above $25,000.

## 📥 Input Params
* `NormalizedTransaction` containing `country`, `amount_usd`, `channel`, `merchant_category`, and `timestamp`.

## 📤 Output Structure
* `violation`: `bool` (true if any rule was violated)
* `rule_name`: `str` (the name of the worst rule violated)
* `rule_severity`: `str` ("critical" | "high" | "medium" | "low" | "none")
* `violations`: List of all rules violated.
* `evidence`: Supporting metadata for decision audit trails.
