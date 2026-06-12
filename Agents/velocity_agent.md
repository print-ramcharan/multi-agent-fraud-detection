# Velocity Agent

* **Tier**: Tier 2 (Specialist)
* **Default Latency Budget**: 10ms
* **Implementation Class**: `VelocityAgent` ([velocity_agent.py](file:///Users/ram/Desktop/multi-agent-fraud-detection/src/agents/specialist/velocity_agent.py))

## 📝 Overview
Tracks high-frequency transaction bursts and spending velocity anomalies over rolling time windows (1-hour and 24-hour limits).

## 🛠️ Mechanisms & MCP Tools
Queries the `velocity_server` MCP service:
1. `get_transaction_velocity(customer_id)`: Returns count of transactions in the last hour and last 24 hours, and distinct merchant count.
2. `get_amount_velocity(customer_id)`: Returns sum of transacted amount in the last hour and last 24 hours, and average hourly baseline.

### Burst Flags Evaluated
* **Hourly Count Burst**: $\ge 10$ transactions in 1 hour.
* **Daily Count Burst**: $\ge 30$ transactions in 24 hours.
* **Hourly Amount Burst**: $\ge \$5,000$ in 1 hour.
* **Acceleration Burst**: Hourly spend $> 3.0\times$ baseline average.
* **Merchant Diversity Burst**: $\ge 5$ distinct merchants transacted in under 1 hour.

## 📥 Input Params
* `NormalizedTransaction` containing `customer_id`.

## 📤 Output Structure
* `transactions_last_hour`: `int`
* `transactions_last_day`: `int`
* `amount_last_hour`: `float`
* `amount_last_day`: `float`
* `burst`: `bool` (true if any burst threshold is violated)
* `amount_acceleration`: `float`
* `distinct_merchants_last_hour`: `int`
* `evidence`: Contains detailed logs of burst reasons.
