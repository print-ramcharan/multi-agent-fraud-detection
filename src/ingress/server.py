"""
FastAPI Ingress Server.

Runs the HTTP and WebSocket ingress layers.
"""

from __future__ import annotations

import logging
import time
from typing import Any
import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.models.transaction import TransactionInput
from src.models.config import get_config
from src.infrastructure.cache import InMemoryCache
from src.infrastructure.audit_store import SQLiteAuditStore
from src.infrastructure.event_bus import InMemoryEventBus
from src.infrastructure.metrics import MetricsCollector

from src.ingress.validator import IngressValidator
from src.ingress.normalizer import IngressNormalizer
from src.ingress.deduplicator import IngressDeduplicator
from src.orchestrator.engine import FraudOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
config = get_config()

# Global App Ingress FastAPI
app = FastAPI(
    title="Real-Time Fraud Detection Platform",
    description="Multi-agent low-latency real-time fraud scoring platform",
    version="1.0.0"
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared In-memory simulated infrastructure
cache = InMemoryCache()
audit_store = SQLiteAuditStore()
event_bus = InMemoryEventBus()
metrics = MetricsCollector()

# Ingress components
deduplicator = IngressDeduplicator(cache, ttl_seconds=config.dedup_ttl_seconds)

# Orchestrator
orchestrator: FraudOrchestrator | None = None

# Active dashboard websockets
connected_websockets: list[WebSocket] = []

@app.on_event("startup")
async def startup_event():
    global orchestrator
    logger.info("Initializing SQLite Audit Store...")
    await audit_store.start()
    await event_bus.start()
    
    logger.info("Initializing MCP Server caches and settings...")
    # Initialize servers that rely on cache
    from src.mcp.servers.blacklist_server import init_blacklist_server
    from src.mcp.servers.velocity_server import init_velocity_server
    await init_blacklist_server(cache)
    await init_velocity_server(cache)
    
    orchestrator = FraudOrchestrator(
        cache=cache,
        audit_store=audit_store,
        event_bus=event_bus,
        metrics=metrics
    )
    
    # Run a background listener to broadcast events to connected dashboard sockets
    asyncio.create_task(broadcast_event_listener())
    
    # Run continuous transaction generator to feed dashboard with live traffic
    asyncio.create_task(continuous_transaction_generator())
    logger.info("Server startup complete. Ready for transactions.")

async def continuous_transaction_generator():
    """Generates random transactions periodically to simulate active fraud detection."""
    import random
    from src.models.transaction import TransactionChannel
    
    await asyncio.sleep(3.0) # Wait for startup to complete fully
    logger.info("Continuous Transaction Generator started.")
    
    customer_ids = ["cust_123", "cust_456", "cust_789", "cust_999", "cust_000"]
    card_ids = ["card_safe_vip", "card_stolen_001", "card_suspicious_99", "card_normal_44"]
    merchant_ids = ["merchant_trusted", "merchant_unknown", "merchant_flagged"]
    categories = ["grocery", "retail", "entertainment", "travel", "electronics"]
    countries = ["US", "CA", "GB", "FR", "DE"]
    cities = ["New York", "Toronto", "London", "Paris", "Berlin"]
    devices = ["device_456_plat", "device_789", "device_unknown_1", "device_secure_01"]
    
    tx_count = 0
    while True:
        try:
            tx_count += 1
            txn = TransactionInput(
                transaction_id=f"auto_{tx_count}_{int(time.time())}",
                customer_id=random.choice(customer_ids),
                card_id=random.choice(card_ids),
                merchant_id=random.choice(merchant_ids),
                merchant_category=random.choice(categories),
                amount=round(random.uniform(10.0, 3500.0), 2),
                currency="USD",
                country=random.choice(countries),
                city=random.choice(cities),
                channel=random.choice(list(TransactionChannel)),
                device_id=random.choice(devices)
            )
            await evaluate_transaction(txn)
        except Exception as e:
            logger.error("Failed to generate auto transaction: %s", e)
        await asyncio.sleep(2.0) # send every 2 seconds


async def broadcast_event_listener():
    """Listen for evaluations and broadcast decisions to dashboard websockets."""
    async def on_decision(event):
        logger.info("Broadcasting final decision to %d dashboard clients", len(connected_websockets))
        payload = event.payload
        # Look up and enrich metadata for the dashboard
        import json
        try:
            tx_id = payload.get("transaction_id")
            meta_str = await cache.get(f"meta:{tx_id}")
            if meta_str:
                meta = json.loads(meta_str)
                payload.update(meta)
        except Exception as e:
            logger.warning("Failed to enrich websocket payload: %s", e)

        dead_sockets = []
        for ws in connected_websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            if ws in connected_websockets:
                connected_websockets.remove(ws)
                
    await event_bus.subscribe("decisions.out", on_decision)


@app.post("/api/v1/transactions/evaluate")
async def evaluate_transaction(txn_input: TransactionInput) -> Any:
    """Evaluate a transaction for potential fraud."""
    start_time = time.perf_counter()
    
    # 1. Validation
    is_valid, msg = IngressValidator.validate(txn_input)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
    
    # 2. Check Deduplication
    is_dup, cached_res = await deduplicator.is_duplicate(txn_input.transaction_id)
    if is_dup:
        return cached_res
        
    # 3. Normalization
    normalized_txn = IngressNormalizer.normalize(txn_input)
    
    # Store metadata in cache for dashboard websocket enrichment
    import json
    await cache.set(f"meta:{txn_input.transaction_id}", json.dumps({
        "amount": txn_input.amount,
        "customer": txn_input.customer_id,
        "merchant": txn_input.merchant_id,
        "currency": txn_input.currency,
        "country": txn_input.country,
    }), ttl=600)

    
    # 4. Evaluate using the Multi-Agent Orchestrator
    try:
        decision_res = await orchestrator.evaluate_transaction(normalized_txn)
        
        # 5. Register decision in dedup cache
        await deduplicator.register_decision(txn_input.transaction_id, decision_res.model_dump())
        
        # Log latency
        elapsed = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "Evaluated transaction %s: Decision=%s in %.2fms",
            txn_input.transaction_id,
            decision_res.decision,
            elapsed
        )
        return decision_res.model_dump()
        
    except Exception as e:
        logger.error("Internal evaluation failed: %s", e, exc_info=True)
        # Fail safe -> ESCALATE (Governance rule 7)
        from src.models.decision import DecisionResult, Decision, RiskLevel, EscalationReason
        fail_safe_res = DecisionResult(
            transaction_id=txn_input.transaction_id,
            decision=Decision.ESCALATE,
            confidence=0.0,
            risk_level=RiskLevel.HIGH,
            reason=f"Internal server evaluation error: {e}",
            escalation_reason=EscalationReason.AGENT_TIMEOUT,
            processing_time_ms=(time.perf_counter() - start_time) * 1000.0
        )
        return fail_safe_res.model_dump()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info("New dashboard WebSocket connection accepted.")
    try:
        while True:
            # Keep socket alive, read messages if any
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Dashboard WebSocket client disconnected.")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

@app.get("/health")
async def health():
    return {"status": "healthy", "agents": 11, "mcp_servers": 6}

@app.get("/metrics")
async def get_metrics():
    return metrics.get_metrics()

# Mount the React dashboard production build
app.mount("/", StaticFiles(directory="dashboard-react/dist", html=True), name="dashboard")


