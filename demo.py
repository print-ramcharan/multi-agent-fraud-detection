import time
import requests
import uuid

url = "http://127.0.0.1:8000/api/v1/transactions/evaluate"

# Generate unique run ID using timestamp
run_id = int(time.time())

payloads = [
    {
        "transaction_id": f"demo_txn_approve_vip_{run_id}",
        "customer_id": "cust_456",
        "card_id": "card_safe_vip",
        "merchant_id": "merchant_trusted",
        "merchant_category": "grocery",
        "amount": 100.0,
        "currency": "USD",
        "country": "US",
        "city": "New York",
        "channel": "online",
        "device_id": "device_456_plat"
    },
    {
        "transaction_id": f"demo_txn_decline_stolen_{run_id}",
        "customer_id": "cust_123",
        "card_id": "card_stolen_001",
        "merchant_id": "merchant_trusted",
        "merchant_category": "grocery",
        "amount": 50.0,
        "currency": "USD",
        "country": "US",
        "city": "San Francisco",
        "channel": "pos",
        "device_id": "device_789"
    }
]

print("=== Sending transactions to Fraud Detection API ===\n")

for p in payloads:
    try:
        start = time.perf_counter()
        resp = requests.post(url, json=p)
        elapsed = (time.perf_counter() - start) * 1000.0
        data = resp.json()
        print(f"Transaction: {p['transaction_id']}")
        print(f" -> Decision: {data['decision']}")
        print(f" -> Confidence: {data['confidence']}")
        print(f" -> Reason: {data['reason']}")
        print(f" -> Processing Time: {data['processing_time_ms']:.2f}ms (HTTP roundtrip: {elapsed:.2f}ms)")
        print(f" -> Fast Path: {data['fast_path']}")
        print("-" * 50)
    except Exception as e:
        print(f"Failed to connect to API: {e}")
        print("Make sure you start the server first in another window using: uvicorn src.ingress.server:app --reload")
        break
