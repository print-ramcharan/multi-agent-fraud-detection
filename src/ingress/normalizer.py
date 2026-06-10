"""
API Ingress Normalizer.

Normalizes fields like currency rates, timestamps, and standardized formats.
"""

from __future__ import annotations

import logging
from src.models.transaction import TransactionInput, NormalizedTransaction

logger = logging.getLogger(__name__)

class IngressNormalizer:
    """Standardizes input fields for consistent downstream evaluation."""

    @staticmethod
    def normalize(txn: TransactionInput) -> NormalizedTransaction:
        """Construct normalized transaction structure."""
        return NormalizedTransaction.from_input(txn)
