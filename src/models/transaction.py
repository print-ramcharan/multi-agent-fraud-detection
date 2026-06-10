"""
Transaction domain models.

Defines the input schema for incoming payment transactions and the
normalized form used throughout the agent pipeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class TransactionChannel(StrEnum):
    """Payment channel through which the transaction originated."""

    ONLINE = "online"
    POS = "pos"
    ATM = "atm"
    MOBILE = "mobile"
    BANKING = "banking"


class TransactionInput(BaseModel):
    """Raw incoming transaction from payment switches, POS, online checkout, or banking channels."""

    transaction_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique transaction identifier (UUID)",
    )
    customer_id: str = Field(..., description="Customer identifier", min_length=1)
    card_id: str = Field(..., description="Card identifier", min_length=1)
    merchant_id: str = Field(..., description="Merchant identifier", min_length=1)
    merchant_category: str = Field(
        ..., description="Merchant category (e.g., electronics, grocery)", min_length=1
    )
    amount: float = Field(..., description="Transaction amount", gt=0)
    currency: str = Field(..., description="ISO 4217 currency code", min_length=3, max_length=3)
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code", min_length=2, max_length=2)
    city: str = Field(default="", description="City of transaction")
    channel: TransactionChannel = Field(..., description="Payment channel")
    device_id: str = Field(default="", description="Device fingerprint identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Transaction timestamp (ISO 8601)",
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("country")
    @classmethod
    def normalize_country(cls, v: str) -> str:
        return v.upper()

    model_config = {"json_schema_extra": {
        "example": {
            "transaction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "customer_id": "cust_123",
            "card_id": "card_123",
            "merchant_id": "merchant_456",
            "merchant_category": "electronics",
            "amount": 4500.00,
            "currency": "USD",
            "country": "US",
            "city": "New York",
            "channel": "online",
            "device_id": "device_789",
            "timestamp": "2026-01-10T12:30:45Z",
        }
    }}


# Static exchange rates to USD (simplified for simulation)
_EXCHANGE_RATES: dict[str, float] = {
    "USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "CAD": 0.74,
    "AUD": 0.66, "CHF": 1.13, "CNY": 0.14, "INR": 0.012, "BRL": 0.20,
    "MXN": 0.058, "KRW": 0.00075, "SGD": 0.75, "HKD": 0.13, "NOK": 0.094,
    "SEK": 0.096, "DKK": 0.15, "NZD": 0.61, "ZAR": 0.055, "RUB": 0.011,
    "TRY": 0.031, "AED": 0.27, "SAR": 0.27, "THB": 0.028, "TWD": 0.031,
    "PLN": 0.25, "PHP": 0.018, "IDR": 0.000063, "MYR": 0.21, "CZK": 0.044,
    "ILS": 0.28, "CLP": 0.0011, "ARS": 0.0011, "COP": 0.00024, "EGP": 0.021,
    "VND": 0.000041, "NGN": 0.00065, "PKR": 0.0036, "BDT": 0.0091,
}

# High-risk countries (OFAC-adjacent, simplified for simulation)
HIGH_RISK_COUNTRIES: set[str] = {
    "KP", "IR", "SY", "CU", "VE", "MM", "BY", "RU", "SD", "SO",
    "YE", "LY", "AF", "IQ", "LB", "CF", "CD", "SS", "ZW",
}

# Merchant categories with elevated risk
HIGH_RISK_CATEGORIES: set[str] = {
    "gambling", "cryptocurrency", "adult", "weapons",
    "money_transfer", "prepaid_cards", "pawnshop",
}


class NormalizedTransaction(BaseModel):
    """Post-ingress normalized transaction with computed risk signals."""

    # --- Original fields (carried forward) ---
    transaction_id: str
    customer_id: str
    card_id: str
    merchant_id: str
    merchant_category: str
    amount: float
    currency: str
    country: str
    city: str
    channel: TransactionChannel
    device_id: str
    timestamp: datetime

    # --- Computed fields ---
    amount_usd: float = Field(..., description="Amount converted to USD")
    is_high_risk_country: bool = Field(False, description="Country on high-risk list")
    is_high_risk_merchant: bool = Field(False, description="Merchant category on high-risk list")
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Internal processing request ID",
    )
    ingress_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the platform received the transaction",
    )

    @classmethod
    def from_input(cls, txn: TransactionInput) -> NormalizedTransaction:
        """Create a NormalizedTransaction from raw TransactionInput."""
        rate = _EXCHANGE_RATES.get(txn.currency, 1.0)
        amount_usd = round(txn.amount * rate, 2)

        return cls(
            transaction_id=txn.transaction_id,
            customer_id=txn.customer_id,
            card_id=txn.card_id,
            merchant_id=txn.merchant_id,
            merchant_category=txn.merchant_category.lower(),
            amount=txn.amount,
            currency=txn.currency,
            country=txn.country,
            city=txn.city,
            channel=txn.channel,
            device_id=txn.device_id,
            timestamp=txn.timestamp,
            amount_usd=amount_usd,
            is_high_risk_country=txn.country in HIGH_RISK_COUNTRIES,
            is_high_risk_merchant=txn.merchant_category.lower() in HIGH_RISK_CATEGORIES,
        )
