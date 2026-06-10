"""
Customer MCP Server.

Provides tools to retrieve customer profiles, transaction history,
and spending statistics from an in-memory customer database.

Tools:
- get_customer_profile(customer_id) → profile dict
- get_transaction_history(customer_id, limit?) → list of past txns
- get_spending_stats(customer_id) → spending statistics

Pre-seeded with ~20 customers across all trust tiers.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-seeded customer database
# ---------------------------------------------------------------------------

_CUSTOMER_DB: dict[str, dict[str, Any]] = {
    # --- Key customers from spec ---
    "cust_123": {
        "customer_id": "cust_123",
        "name": "Alice Johnson",
        "trust_tier": "gold",
        "avg_transaction_amount": 180.0,
        "total_transactions": 500,
        "fraud_count": 0,
        "account_age_days": 1095,
        "email": "alice@example.com",
        "country": "US",
        "city": "San Francisco",
        "created_at": "2023-06-15T00:00:00Z",
        "spending_stddev": 95.0,
        "monthly_avg": 3200.0,
    },
    "cust_456": {
        "customer_id": "cust_456",
        "name": "Bob Sterling",
        "trust_tier": "platinum",
        "avg_transaction_amount": 2500.0,
        "total_transactions": 1200,
        "fraud_count": 0,
        "account_age_days": 2555,
        "email": "bob@sterling-corp.com",
        "country": "US",
        "city": "New York",
        "created_at": "2019-07-01T00:00:00Z",
        "spending_stddev": 1200.0,
        "monthly_avg": 45000.0,
    },
    "cust_789": {
        "customer_id": "cust_789",
        "name": "Charlie Newbie",
        "trust_tier": "new",
        "avg_transaction_amount": 50.0,
        "total_transactions": 5,
        "fraud_count": 0,
        "account_age_days": 7,
        "email": "charlie@newmail.com",
        "country": "US",
        "city": "Austin",
        "created_at": "2026-05-28T00:00:00Z",
        "spending_stddev": 20.0,
        "monthly_avg": 150.0,
    },
    "cust_bad": {
        "customer_id": "cust_bad",
        "name": "Dave Suspicious",
        "trust_tier": "standard",
        "avg_transaction_amount": 100.0,
        "total_transactions": 30,
        "fraud_count": 3,
        "account_age_days": 180,
        "email": "dave@tempmail.com",
        "country": "US",
        "city": "Las Vegas",
        "created_at": "2025-12-05T00:00:00Z",
        "spending_stddev": 60.0,
        "monthly_avg": 800.0,
    },
    # --- Additional customers (16 more) ---
    "cust_101": {
        "customer_id": "cust_101",
        "name": "Elena Martinez",
        "trust_tier": "silver",
        "avg_transaction_amount": 120.0,
        "total_transactions": 250,
        "fraud_count": 0,
        "account_age_days": 730,
        "email": "elena@example.com",
        "country": "MX",
        "city": "Mexico City",
        "created_at": "2024-06-10T00:00:00Z",
        "spending_stddev": 55.0,
        "monthly_avg": 2100.0,
    },
    "cust_102": {
        "customer_id": "cust_102",
        "name": "Fatima Al-Rashid",
        "trust_tier": "gold",
        "avg_transaction_amount": 350.0,
        "total_transactions": 800,
        "fraud_count": 0,
        "account_age_days": 1460,
        "email": "fatima@business.ae",
        "country": "AE",
        "city": "Dubai",
        "created_at": "2022-06-15T00:00:00Z",
        "spending_stddev": 180.0,
        "monthly_avg": 6500.0,
    },
    "cust_103": {
        "customer_id": "cust_103",
        "name": "George Tanaka",
        "trust_tier": "platinum",
        "avg_transaction_amount": 3200.0,
        "total_transactions": 950,
        "fraud_count": 0,
        "account_age_days": 3285,
        "email": "george@tanaka.jp",
        "country": "JP",
        "city": "Tokyo",
        "created_at": "2017-06-01T00:00:00Z",
        "spending_stddev": 1500.0,
        "monthly_avg": 55000.0,
    },
    "cust_104": {
        "customer_id": "cust_104",
        "name": "Hannah O'Brien",
        "trust_tier": "standard",
        "avg_transaction_amount": 75.0,
        "total_transactions": 45,
        "fraud_count": 1,
        "account_age_days": 120,
        "email": "hannah@webmail.ie",
        "country": "IE",
        "city": "Dublin",
        "created_at": "2026-02-04T00:00:00Z",
        "spending_stddev": 30.0,
        "monthly_avg": 450.0,
    },
    "cust_105": {
        "customer_id": "cust_105",
        "name": "Ivan Petrov",
        "trust_tier": "silver",
        "avg_transaction_amount": 200.0,
        "total_transactions": 180,
        "fraud_count": 0,
        "account_age_days": 545,
        "email": "ivan@mail.de",
        "country": "DE",
        "city": "Berlin",
        "created_at": "2024-12-01T00:00:00Z",
        "spending_stddev": 90.0,
        "monthly_avg": 2800.0,
    },
    "cust_106": {
        "customer_id": "cust_106",
        "name": "Julia Chen",
        "trust_tier": "gold",
        "avg_transaction_amount": 420.0,
        "total_transactions": 620,
        "fraud_count": 0,
        "account_age_days": 900,
        "email": "julia.chen@tech.sg",
        "country": "SG",
        "city": "Singapore",
        "created_at": "2023-12-15T00:00:00Z",
        "spending_stddev": 200.0,
        "monthly_avg": 7200.0,
    },
    "cust_107": {
        "customer_id": "cust_107",
        "name": "Kevin Park",
        "trust_tier": "new",
        "avg_transaction_amount": 30.0,
        "total_transactions": 3,
        "fraud_count": 0,
        "account_age_days": 2,
        "email": "kevin.park@gmail.com",
        "country": "KR",
        "city": "Seoul",
        "created_at": "2026-06-02T00:00:00Z",
        "spending_stddev": 10.0,
        "monthly_avg": 90.0,
    },
    "cust_108": {
        "customer_id": "cust_108",
        "name": "Lisa Muller",
        "trust_tier": "standard",
        "avg_transaction_amount": 90.0,
        "total_transactions": 85,
        "fraud_count": 2,
        "account_age_days": 365,
        "email": "lisa.m@posteo.de",
        "country": "DE",
        "city": "Munich",
        "created_at": "2025-06-04T00:00:00Z",
        "spending_stddev": 45.0,
        "monthly_avg": 1100.0,
    },
    "cust_109": {
        "customer_id": "cust_109",
        "name": "Mohamed Hassan",
        "trust_tier": "silver",
        "avg_transaction_amount": 150.0,
        "total_transactions": 300,
        "fraud_count": 0,
        "account_age_days": 820,
        "email": "m.hassan@company.eg",
        "country": "EG",
        "city": "Cairo",
        "created_at": "2024-03-15T00:00:00Z",
        "spending_stddev": 70.0,
        "monthly_avg": 2400.0,
    },
    "cust_110": {
        "customer_id": "cust_110",
        "name": "Natasha Volkov",
        "trust_tier": "gold",
        "avg_transaction_amount": 280.0,
        "total_transactions": 450,
        "fraud_count": 0,
        "account_age_days": 1100,
        "email": "natasha@corp.ca",
        "country": "CA",
        "city": "Toronto",
        "created_at": "2023-06-01T00:00:00Z",
        "spending_stddev": 140.0,
        "monthly_avg": 4800.0,
    },
    "cust_111": {
        "customer_id": "cust_111",
        "name": "Oscar Santos",
        "trust_tier": "new",
        "avg_transaction_amount": 40.0,
        "total_transactions": 8,
        "fraud_count": 0,
        "account_age_days": 14,
        "email": "oscar@proton.me",
        "country": "BR",
        "city": "São Paulo",
        "created_at": "2026-05-21T00:00:00Z",
        "spending_stddev": 15.0,
        "monthly_avg": 200.0,
    },
    "cust_112": {
        "customer_id": "cust_112",
        "name": "Priya Sharma",
        "trust_tier": "platinum",
        "avg_transaction_amount": 1800.0,
        "total_transactions": 980,
        "fraud_count": 0,
        "account_age_days": 2190,
        "email": "priya@enterprise.in",
        "country": "IN",
        "city": "Mumbai",
        "created_at": "2020-06-01T00:00:00Z",
        "spending_stddev": 900.0,
        "monthly_avg": 32000.0,
    },
    "cust_113": {
        "customer_id": "cust_113",
        "name": "Quinn Zhang",
        "trust_tier": "standard",
        "avg_transaction_amount": 65.0,
        "total_transactions": 60,
        "fraud_count": 0,
        "account_age_days": 240,
        "email": "quinn.z@mail.cn",
        "country": "CN",
        "city": "Shanghai",
        "created_at": "2025-10-01T00:00:00Z",
        "spending_stddev": 25.0,
        "monthly_avg": 600.0,
    },
    "cust_114": {
        "customer_id": "cust_114",
        "name": "Rachel Kim",
        "trust_tier": "silver",
        "avg_transaction_amount": 160.0,
        "total_transactions": 220,
        "fraud_count": 1,
        "account_age_days": 600,
        "email": "rachel.kim@outlook.kr",
        "country": "KR",
        "city": "Busan",
        "created_at": "2024-10-15T00:00:00Z",
        "spending_stddev": 80.0,
        "monthly_avg": 2200.0,
    },
    "cust_115": {
        "customer_id": "cust_115",
        "name": "Samuel Williams",
        "trust_tier": "gold",
        "avg_transaction_amount": 500.0,
        "total_transactions": 700,
        "fraud_count": 0,
        "account_age_days": 1500,
        "email": "sam@williams.co.uk",
        "country": "GB",
        "city": "London",
        "created_at": "2022-04-20T00:00:00Z",
        "spending_stddev": 250.0,
        "monthly_avg": 9000.0,
    },
    "cust_116": {
        "customer_id": "cust_116",
        "name": "Tina Brown",
        "trust_tier": "standard",
        "avg_transaction_amount": 55.0,
        "total_transactions": 40,
        "fraud_count": 5,
        "account_age_days": 200,
        "email": "tina.b@disposable.com",
        "country": "US",
        "city": "Miami",
        "created_at": "2025-11-15T00:00:00Z",
        "spending_stddev": 35.0,
        "monthly_avg": 500.0,
    },
}

# Simulated transaction history per customer (a few recent transactions)
_TRANSACTION_HISTORY: dict[str, list[dict[str, Any]]] = {}


def _generate_history(customer_id: str) -> list[dict[str, Any]]:
    """Generate synthetic transaction history for a customer."""
    profile = _CUSTOMER_DB.get(customer_id)
    if not profile:
        return []

    rng = random.Random(hash(customer_id))  # deterministic per customer
    avg = profile["avg_transaction_amount"]
    stddev = profile["spending_stddev"]
    n = min(profile["total_transactions"], 50)  # cap at 50 for history
    now = datetime.now(timezone.utc)

    history: list[dict[str, Any]] = []
    for i in range(n):
        amount = max(1.0, round(rng.gauss(avg, stddev), 2))
        ts = now - timedelta(hours=rng.randint(1, 8760))  # up to ~1 year back
        history.append({
            "transaction_id": f"hist_{customer_id}_{i:04d}",
            "customer_id": customer_id,
            "amount_usd": amount,
            "merchant_category": rng.choice([
                "grocery", "electronics", "dining", "travel",
                "clothing", "entertainment", "utilities", "healthcare",
            ]),
            "country": profile.get("country", "US"),
            "channel": rng.choice(["online", "pos", "mobile"]),
            "timestamp": ts.isoformat(),
            "fraud": False,
        })

    # Mark some as fraud for customers with fraud_count > 0
    fraud_count = profile.get("fraud_count", 0)
    for j in range(min(fraud_count, len(history))):
        history[j]["fraud"] = True

    history.sort(key=lambda t: t["timestamp"], reverse=True)
    return history


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

customer_server = FastMCP("customer-server")


@customer_server.tool()
async def get_customer_profile(customer_id: str) -> dict[str, Any]:
    """Retrieve the full profile for a customer.

    Args:
        customer_id: The customer identifier (e.g. ``cust_123``).

    Returns:
        Customer profile dict, or an error dict if not found.
    """
    profile = _CUSTOMER_DB.get(customer_id)
    if profile is None:
        logger.warning("Customer not found: %s", customer_id)
        return {"error": "customer_not_found", "customer_id": customer_id}
    return dict(profile)


@customer_server.tool()
async def get_transaction_history(
    customer_id: str, limit: int = 20
) -> dict[str, Any]:
    """Retrieve recent transaction history for a customer.

    Args:
        customer_id: The customer identifier.
        limit: Maximum number of transactions to return (default 20).

    Returns:
        Dict with ``customer_id``, ``count``, and ``transactions`` list.
    """
    if customer_id not in _CUSTOMER_DB:
        return {"error": "customer_not_found", "customer_id": customer_id}

    if customer_id not in _TRANSACTION_HISTORY:
        _TRANSACTION_HISTORY[customer_id] = _generate_history(customer_id)

    txns = _TRANSACTION_HISTORY[customer_id][:limit]
    return {
        "customer_id": customer_id,
        "count": len(txns),
        "total_available": len(_TRANSACTION_HISTORY[customer_id]),
        "transactions": txns,
    }


@customer_server.tool()
async def get_spending_stats(customer_id: str) -> dict[str, Any]:
    """Compute spending statistics for a customer.

    Args:
        customer_id: The customer identifier.

    Returns:
        Dict with average, stddev, monthly average, max transaction, etc.
    """
    profile = _CUSTOMER_DB.get(customer_id)
    if profile is None:
        return {"error": "customer_not_found", "customer_id": customer_id}

    if customer_id not in _TRANSACTION_HISTORY:
        _TRANSACTION_HISTORY[customer_id] = _generate_history(customer_id)

    txns = _TRANSACTION_HISTORY[customer_id]
    amounts = [t["amount_usd"] for t in txns] if txns else [0.0]

    return {
        "customer_id": customer_id,
        "trust_tier": profile["trust_tier"],
        "avg_transaction_amount": profile["avg_transaction_amount"],
        "spending_stddev": profile["spending_stddev"],
        "monthly_avg": profile["monthly_avg"],
        "total_transactions": profile["total_transactions"],
        "fraud_count": profile["fraud_count"],
        "account_age_days": profile["account_age_days"],
        "history_sample_size": len(txns),
        "history_max": round(max(amounts), 2),
        "history_min": round(min(amounts), 2),
        "history_avg": round(sum(amounts) / len(amounts), 2),
    }
