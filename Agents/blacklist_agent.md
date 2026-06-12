# Blacklist Agent

* **Tier**: Tier 1 (Fast-Path)
* **Default Latency Budget**: 10ms
* **Implementation Class**: `BlacklistAgent` ([blacklist_agent.py](file:///Users/ram/Desktop/multi-agent-fraud-detection/src/agents/tier1/blacklist_agent.py))

## 📝 Overview
Identifies known bad actors in real-time by cross-referencing transaction attributes against high-speed blacklists.

## 🛠️ Mechanisms & MCP Tools
Queries the `blacklist_server` MCP service:
1. `check_card_blacklist(card_id)`: Checks if the payment instrument is flagged as stolen or compromised.
2. `check_device_blacklist(device_id)`: Checks if the device signature is associated with prior fraud events.
3. `check_merchant_blacklist(merchant_id)`: Checks if the merchant identity matches known fraudulent endpoints.

## 📥 Input Params
* `NormalizedTransaction` containing `card_id`, `device_id`, and `merchant_id`.

## 📤 Output Structure
* `blacklisted`: `bool` (true if any entity is blacklisted)
* `card_blacklisted`: `bool`
* `device_blacklisted`: `bool`
* `merchant_blacklisted`: `bool`
* `source`: `str` ("card" | "device" | "merchant" | "")
* `match_type`: `str` ("exact" | "none")
* `evidence`: List of `AgentEvidence` objects detailing blacklist hits.
