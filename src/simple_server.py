from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import random
import uuid

app = FastAPI(title="Simple Fraud Demo Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/health')
async def health():
    return {"status": "healthy", "agents": 1}

@app.post('/api/v1/transactions/evaluate')
async def evaluate(txn: dict):
    # very small deterministic demo logic
    card = txn.get('card_id', '')
    amount = float(txn.get('amount', 0) or 0)
    # definite decline for known stolen cards
    if 'stolen' in card:
        decision = 'DECLINE'
        confidence = 0.98
        reason = 'Blacklisted'
    # high amount -> escalate with some probability
    elif amount > 2000:
        if random.random() < 0.6:
            decision = 'ESCALATE'
            confidence = 0.85
            reason = 'High amount - manual review'
        else:
            decision = 'DECLINE'
            confidence = 0.7
            reason = 'High amount - automated decline'
    # medium amounts have some chance of decline
    elif amount > 500:
        if random.random() < 0.15:
            decision = 'DECLINE'
            confidence = 0.88
            reason = 'Risky pattern'
        else:
            decision = 'APPROVE'
            confidence = 0.9
            reason = 'Low risk'
    else:
        # small amounts mostly approve
        if random.random() < 0.02:
            decision = 'DECLINE'
            confidence = 0.6
            reason = 'Random sampling decline'
        else:
            decision = 'APPROVE'
            confidence = 0.95
            reason = 'Low risk'
    return {
        'transaction_id': txn.get('transaction_id'),
        'decision': decision,
        'confidence': confidence,
        'reason': reason,
        'processing_time_ms': 1.2,
        'fast_path': True
    }

# Simple WebSocket broadcaster
connected: list[WebSocket] = []

@app.websocket('/ws/live')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected.append(ws)
    try:
        while True:
            # send a heartbeat/demo event every 2 seconds
            # build a richer, randomized transaction payload
            tid = f'auto_{time.time_ns()}'
            amount = round(random.choice([12.34, 19.99, 49.50, 120.00, 600.00, 1500.00, 3200.75]), 2)
            # base risk from amount
            if amount > 2000:
                risk = random.choice(['HIGH', 'CRITICAL'])
            elif amount > 500:
                risk = random.choice(['MEDIUM', 'HIGH', 'LOW'])
            else:
                risk = random.choice(['LOW', 'LOW', 'MEDIUM'])

            # decision probabilities influenced by risk
            r = random.random()
            if risk in ('CRITICAL',) or r < 0.05:
                decision = 'DECLINE'
                confidence = round(0.6 + random.random() * 0.35, 2)
            elif risk == 'HIGH' or r < 0.15:
                decision = 'ESCALATE'
                confidence = round(0.7 + random.random() * 0.25, 2)
            else:
                decision = 'APPROVE'
                confidence = round(0.85 + random.random() * 0.14, 2)

            payload = {
                'transaction_id': tid,
                'timestamp': int(time.time() * 1000),
                'decision': decision,
                'confidence': confidence,
                'processing_time_ms': round(1.0 + random.random() * 10.0, 2),
                'amount': amount,
                'customer': random.choice(['demo_cust', 'demo_vip', 'guest_123', 'acct_42']),
                'risk_level': risk,
                'card_id': random.choice(['card_abc', 'card_def', 'stolen_card_001', 'card_xyz']),
                'audit_trail': {
                    'entries': [
                        {'agent_name': 'Preprocessor', 'duration_ms': round(random.random() * 3, 2), 'status': 'success', 'output': {}},
                        {'agent_name': 'Rule Agent', 'duration_ms': round(2 + random.random() * 8, 2), 'status': 'success', 'output': {}},
                        {'agent_name': 'ML Risk Agent', 'duration_ms': round(5 + random.random() * 15, 2), 'status': 'success' if decision == 'APPROVE' else 'error' if decision == 'DECLINE' else 'success', 'output': {}}
                    ]
                },
            }
            try:
                await ws.send_json(payload)
            except Exception:
                break
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    finally:
        if ws in connected:
            connected.remove(ws)
