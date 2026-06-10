"""
End-to-End integration tests for Multi-Agent Fraud Detection Platform.
"""

from __future__ import annotations

import pytest
import asyncio
from datetime import datetime, timezone

from src.models.transaction import TransactionInput, TransactionChannel
from src.ingress.server import app, startup_event, evaluate_transaction

@pytest.fixture(scope="module", autouse=True)
async def setup_app():
    # Run FastAPI startup to pre-seed cache and instantiate components
    await startup_event()

@pytest.mark.asyncio
async def test_approve_vip_flow():
    # cust_456 is a Platinum tier customer with high trust
    txn = TransactionInput(
        transaction_id="test_txn_approve_001",
        customer_id="cust_456",
        card_id="card_safe_vip",
        merchant_id="merchant_trusted",
        merchant_category="grocery",
        amount=100.0,
        currency="USD",
        country="US",
        city="New York",
        channel=TransactionChannel.ONLINE,
        device_id="device_456_plat"
    )
    
    result = await evaluate_transaction(txn)
    assert result["decision"] == "APPROVE"
    assert result["confidence"] > 0.5
    assert result["fast_path"] is True

@pytest.mark.asyncio
async def test_decline_blacklist_flow():
    # card_stolen_001 is on the card blacklist
    txn = TransactionInput(
        transaction_id="test_txn_decline_001",
        customer_id="cust_123",
        card_id="card_stolen_001",
        merchant_id="merchant_trusted",
        merchant_category="grocery",
        amount=50.0,
        currency="USD",
        country="US",
        city="San Francisco",
        channel=TransactionChannel.POS,
        device_id="device_789"
    )
    
    result = await evaluate_transaction(txn)
    assert result["decision"] == "DECLINE"
    assert "Blacklist" in result["reason"] or "blacklisted" in result["reason"].lower()
