"""
API Ingress Validators.

Validates incoming transactions schemas and applies sanity checks.
"""

from __future__ import annotations

import logging
from src.models.transaction import TransactionInput

logger = logging.getLogger(__name__)

class IngressValidator:
    """Validates raw transaction inputs for structural correctness."""

    @staticmethod
    def validate(txn: TransactionInput) -> tuple[bool, str]:
        """Validate transaction schema and rules."""
        if txn.amount <= 0:
            return False, "Transaction amount must be greater than zero"
        
        # Simple Luhn-like validation check for Card ID format (alphanumeric/numbers)
        if not txn.card_id or len(txn.card_id) < 5:
            return False, "Invalid card_id format"
            
        if not txn.customer_id:
            return False, "Customer identifier is required"
            
        if not txn.merchant_id:
            return False, "Merchant identifier is required"
            
        return True, "Valid"
