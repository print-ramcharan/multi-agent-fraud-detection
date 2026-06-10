"""
Gateway router for MCP servers.

Manages connections, routes tool calls, and enforces security policies.
"""

from __future__ import annotations

import logging
from typing import Any

from src.mcp.servers.blacklist_server import blacklist_server, check_card_blacklist, check_device_blacklist, check_merchant_blacklist
from src.mcp.servers.customer_server import customer_server, get_customer_profile, get_transaction_history, get_spending_stats
from src.mcp.servers.geo_server import geo_server, get_last_location, calculate_distance, check_impossible_travel
from src.mcp.servers.device_server import device_server, get_device_profile, check_device_sharing, get_device_age
from src.mcp.servers.velocity_server import velocity_server, get_transaction_velocity, get_amount_velocity
from src.mcp.servers.ml_server import ml_server, predict_fraud_score, get_model_metadata

logger = logging.getLogger(__name__)

class MCPGateway:
    """
    Central gateway routing agent requests to specific MCP FastMCP server tools.
    Provides direct Python invocation of tool functions.
    """

    def __init__(self):
        # Register mappings from tool name to callable tool functions
        self.tools = {
            "check_card_blacklist": check_card_blacklist,
            "check_device_blacklist": check_device_blacklist,
            "check_merchant_blacklist": check_merchant_blacklist,
            "get_customer_profile": get_customer_profile,
            "get_transaction_history": get_transaction_history,
            "get_spending_stats": get_spending_stats,
            "get_last_location": get_last_location,
            "calculate_distance": calculate_distance,
            "check_impossible_travel": check_impossible_travel,
            "get_device_profile": get_device_profile,
            "check_device_sharing": check_device_sharing,
            "get_device_age": get_device_age,
            "get_transaction_velocity": get_transaction_velocity,
            "get_amount_velocity": get_amount_velocity,
            "predict_fraud_score": predict_fraud_score,
            "get_model_metadata": get_model_metadata,
        }
        logger.info("MCP Gateway initialized with %d tools", len(self.tools))

    async def call_tool(self, *args, **kwargs) -> Any:
        """
        Execute an MCP tool by name.
        """
        if not args:
            raise ValueError("Tool name must be provided as the first argument")
            
        tool_name = args[-1] if len(args) > 1 and isinstance(args[-1], str) and args[-1] in self.tools else args[0]
        # fallback to second arg if first arg is e.g. "blacklist_server" (server name)
        if len(args) > 1 and args[0] in ("blacklist_server", "customer_server", "geo_server", "device_server", "velocity_server", "ml_server"):
            tool_name = args[1]
            
        if tool_name not in self.tools:
            logger.error("Tool '%s' not found in MCP Gateway", tool_name)
            raise ValueError(f"Tool '{tool_name}' not found")
        
        # Clean extra positional arguments and agent_name from kwargs
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "agent_name"}
        # If the third argument is a dict, it contains kwargs
        for arg in args:
            if isinstance(arg, dict):
                clean_kwargs.update(arg)
                
        # Handle specialized mapping for tools
        target_fn = self.tools[tool_name]
        
        # 1. predict_fraud_score expects 'features' dict
        if tool_name == "predict_fraud_score" and "features" not in clean_kwargs:
            # Map top level fields into features dict
            features_dict = {
                "amount_usd": clean_kwargs.get("amount", 0.0),
                "is_high_risk_country": float(clean_kwargs.get("is_high_risk_country", 0.0)),
                "is_high_risk_merchant": float(clean_kwargs.get("is_high_risk_merchant", 0.0)),
                "is_new_customer": float(clean_kwargs.get("is_new_customer", 0.0)),
                "fraud_history_count": float(clean_kwargs.get("fraud_history_count", 0.0)),
                "device_risk_score": float(clean_kwargs.get("device_risk_score", 0.0)),
                "velocity_txn_count_1h": float(clean_kwargs.get("velocity_txn_count_1h", 0.0)),
                "velocity_amount_1h": float(clean_kwargs.get("velocity_amount_1h", 0.0)),
                "spending_anomaly_zscore": float(clean_kwargs.get("spending_anomaly_zscore", 0.0)),
            }
            clean_kwargs = {"features": features_dict}
            
        # 2. Inspect target function signature to drop unexpected keyword arguments
        import inspect
        sig = inspect.signature(target_fn)
        final_kwargs = {}
        for param_name, param in sig.parameters.items():
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                final_kwargs.update(clean_kwargs)
                break
            if param_name in clean_kwargs:
                final_kwargs[param_name] = clean_kwargs[param_name]
                
        logger.debug("MCP Gateway invoking tool '%s' with args %s", tool_name, final_kwargs)
        try:
            return await target_fn(**final_kwargs)
        except Exception as e:
            logger.error("Error executing tool '%s': %s", tool_name, e, exc_info=True)
            raise
