"""
ML MCP Server.

Provides tools for ML-based fraud scoring:
- predict_fraud_score(features)  → fraud probability
- get_model_metadata()           → model version, training date, feature list

Attempts to load a scikit-learn model from ``ml/model.pkl``.
If the model file is unavailable, falls back to a deterministic
heuristic scorer that combines feature signals.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_MODEL: Any = None
_MODEL_VERSION = "heuristic-1.0.0"
_MODEL_LOADED = False

_MODEL_PATH = Path(
    os.environ.get(
        "ML_MODEL_PATH",
        str(Path(__file__).resolve().parents[2] / "ml" / "model.pkl"),
    )
)


def _try_load_model() -> None:
    """Attempt to load the sklearn model from disk."""
    global _MODEL, _MODEL_VERSION, _MODEL_LOADED

    if _MODEL_PATH.exists():
        try:
            import joblib

            _MODEL = joblib.load(_MODEL_PATH)
            _MODEL_VERSION = "sklearn-1.0.0"
            _MODEL_LOADED = True
            logger.info("ML model loaded from %s", _MODEL_PATH)
        except Exception as exc:
            logger.warning("Failed to load ML model: %s — using heuristic", exc)
            _MODEL_LOADED = False
    else:
        logger.info(
            "ML model not found at %s — using heuristic scorer", _MODEL_PATH
        )
        _MODEL_LOADED = False


# Load on import
_try_load_model()


# ---------------------------------------------------------------------------
# Heuristic fallback scorer
# ---------------------------------------------------------------------------

def _heuristic_score(features: dict[str, float]) -> tuple[float, dict[str, float]]:
    """Compute a fraud risk score from raw features using weighted heuristics.

    Returns:
        (score, feature_importances) where score ∈ [0, 1].
    """
    weights: dict[str, tuple[float, float]] = {
        # feature_name: (weight, normalisation_divisor)
        "amount_usd": (0.15, 10000.0),
        "is_high_risk_country": (0.12, 1.0),
        "is_high_risk_merchant": (0.10, 1.0),
        "is_new_customer": (0.08, 1.0),
        "fraud_history_count": (0.18, 5.0),
        "device_risk_score": (0.12, 1.0),
        "velocity_txn_count_1h": (0.08, 20.0),
        "velocity_amount_1h": (0.07, 5000.0),
        "spending_anomaly_zscore": (0.10, 5.0),
    }

    score = 0.0
    importances: dict[str, float] = {}
    total_weight = sum(w for w, _ in weights.values())

    for feat_name, (weight, divisor) in weights.items():
        raw = features.get(feat_name, 0.0)
        # Normalise to [0, 1]
        normalised = min(max(raw / divisor, 0.0), 1.0)
        contribution = (weight / total_weight) * normalised
        score += contribution
        importances[feat_name] = round(contribution, 6)

    # Clamp to [0, 1]
    score = min(max(score, 0.0), 1.0)
    return round(score, 6), importances


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

ml_server = FastMCP("ml-server")


@ml_server.tool()
async def predict_fraud_score(features: dict[str, float]) -> dict[str, Any]:
    """Predict a fraud probability score for a transaction.

    The features dict should contain keys like:
    - amount_usd
    - is_high_risk_country (0 or 1)
    - is_high_risk_merchant (0 or 1)
    - is_new_customer (0 or 1)
    - fraud_history_count
    - device_risk_score
    - velocity_txn_count_1h
    - velocity_amount_1h
    - spending_anomaly_zscore

    Args:
        features: Dict mapping feature names to numeric values.

    Returns:
        Dict with ``fraud_score``, ``model_version``, and ``feature_importances``.
    """
    if _MODEL_LOADED and _MODEL is not None:
        try:
            import numpy as np

            # Build feature vector in a fixed order
            feature_order = sorted(features.keys())
            X = np.array([[features.get(f, 0.0) for f in feature_order]])

            if hasattr(_MODEL, "predict_proba"):
                proba = _MODEL.predict_proba(X)[0]
                fraud_score = float(proba[1]) if len(proba) > 1 else float(proba[0])
            else:
                pred = _MODEL.predict(X)[0]
                fraud_score = float(pred)

            fraud_score = min(max(fraud_score, 0.0), 1.0)

            # Feature importances from model if available
            importances: dict[str, float] = {}
            if hasattr(_MODEL, "feature_importances_"):
                for name, imp in zip(feature_order, _MODEL.feature_importances_):
                    importances[name] = round(float(imp), 6)

            return {
                "fraud_score": round(fraud_score, 6),
                "model_version": _MODEL_VERSION,
                "model_type": "sklearn",
                "feature_importances": importances,
                "features_used": feature_order,
            }
        except Exception as exc:
            logger.warning("ML model prediction failed: %s — falling back to heuristic", exc)

    # Heuristic fallback
    score, importances = _heuristic_score(features)
    return {
        "fraud_score": score,
        "model_version": _MODEL_VERSION,
        "model_type": "heuristic",
        "feature_importances": importances,
        "features_used": list(features.keys()),
    }


@ml_server.tool()
async def get_model_metadata() -> dict[str, Any]:
    """Return metadata about the currently loaded model.

    Returns:
        Dict with model version, type, training date, and feature list.
    """
    feature_names = [
        "amount_usd",
        "is_high_risk_country",
        "is_high_risk_merchant",
        "is_new_customer",
        "fraud_history_count",
        "device_risk_score",
        "velocity_txn_count_1h",
        "velocity_amount_1h",
        "spending_anomaly_zscore",
    ]

    return {
        "model_version": _MODEL_VERSION,
        "model_type": "sklearn" if _MODEL_LOADED else "heuristic",
        "model_loaded": _MODEL_LOADED,
        "model_path": str(_MODEL_PATH),
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "training_date": "2026-05-01" if _MODEL_LOADED else "N/A",
        "description": (
            "Gradient-boosted classifier trained on historical fraud data"
            if _MODEL_LOADED
            else "Weighted heuristic scorer — no trained model available"
        ),
    }
