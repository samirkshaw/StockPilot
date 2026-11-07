"""
Agent Tool Registry for StockPilot.

Exposes deterministic tools as Gemini function declarations and provides
a safe, exception-handling tool execution dispatcher with plan caching.
"""

from typing import Any, Callable, Dict, List, Optional
from google.genai import types

from tools.inventory_lookup import inventory_lookup
from tools.sales_analysis import analyze_sales
from tools.demand_forecast import forecast_demand
from tools.supplier_comparison import compare_suppliers
from tools.reorder_calculation import calculate_reorder
from tools.procurement_planner import build_procurement_plan

# In-memory cache for get_procurement_plan within an agent run
_PLAN_CACHE: Dict[str, Any] = {}


def clear_tool_cache() -> None:
    """Clear internal tool caches (call at the beginning of an agent run)."""
    _PLAN_CACHE.clear()


def _cached_get_procurement_plan(**kwargs: Any) -> Dict[str, Any]:
    """Execute build_procurement_plan with default arguments, caching the result."""
    cache_key = "default_plan"
    if cache_key not in _PLAN_CACHE:
        _PLAN_CACHE[cache_key] = build_procurement_plan()
    return _PLAN_CACHE[cache_key]


# Function declarations for the Gemini API
FUNCTION_DECLARATIONS: List[types.FunctionDeclaration] = [
    types.FunctionDeclaration(
        name="get_procurement_plan",
        description=(
            "Generate the comprehensive procurement plan across all 10 products. "
            "Ranks products by stockout urgency, evaluates all suppliers, and compares "
            "Cheapest, Fastest, and Recommended strategies with portfolio totals."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {},
        },
    ),
    types.FunctionDeclaration(
        name="get_inventory",
        description="Look up current inventory levels, category, unit price, and last updated date for a product.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "product_id": {
                    "type": "STRING",
                    "description": "Product identifier, e.g. 'P001'.",
                },
            },
            "required": ["product_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_sales_analysis",
        description=(
            "Analyze historical sales data to compute rolling average daily demand (7d, 14d, 30d, 180d), "
            "daily demand standard deviation, trend ratio, and detect sudden demand spikes."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "product_id": {
                    "type": "STRING",
                    "description": "Product identifier, e.g. 'P001'.",
                },
            },
            "required": ["product_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_demand_forecast",
        description=(
            "Execute a 60-day rolling backtest across forecasting models (Moving Average, Exponential Smoothing, "
            "Weekday Seasonal, Baseline 30d), pick the lowest WAPE method, and forecast future demand."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "product_id": {
                    "type": "STRING",
                    "description": "Product identifier, e.g. 'P001'.",
                },
                "horizon_days": {
                    "type": "INTEGER",
                    "description": "Forecast horizon in days (default: 7).",
                },
            },
            "required": ["product_id"],
        },
    ),
    types.FunctionDeclaration(
        name="compare_suppliers",
        description=(
            "Compare supplier pricing, lead times, and minimum order quantities (MOQ) for a product, "
            "calculating effective order quantities and total costs."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "product_id": {
                    "type": "STRING",
                    "description": "Product identifier, e.g. 'P001'.",
                },
                "required_qty": {
                    "type": "INTEGER",
                    "description": "Number of units required.",
                },
            },
            "required": ["product_id", "required_qty"],
        },
    ),
    types.FunctionDeclaration(
        name="calculate_reorder",
        description=(
            "Calculate stockout shortfall before arrival, safety stock, reorder point, "
            "recommended order quantity, and urgency risk level for a supplier's lead time."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "product_id": {
                    "type": "STRING",
                    "description": "Product identifier, e.g. 'P001'.",
                },
                "lead_time_days": {
                    "type": "INTEGER",
                    "description": "Supplier transit duration in days.",
                },
                "coverage_days": {
                    "type": "INTEGER",
                    "description": "Desired inventory cover after delivery (default: 14).",
                },
                "service_z": {
                    "type": "NUMBER",
                    "description": "Safety factor z-score (default: 1.65).",
                },
                "daily_demand_override": {
                    "type": "NUMBER",
                    "description": "Optional forecast daily demand override.",
                },
            },
            "required": ["product_id", "lead_time_days"],
        },
    ),
]


def get_agent_tools() -> List[types.Tool]:
    """Return Tool objects wrapping all function declarations for the Gemini client."""
    return [types.Tool(function_declarations=FUNCTION_DECLARATIONS)]


# Dispatch map mapping tool names to actual Python functions
_TOOL_MAP: Dict[str, Callable[..., Any]] = {
    "get_inventory": inventory_lookup,
    "get_sales_analysis": analyze_sales,
    "get_demand_forecast": forecast_demand,
    "compare_suppliers": compare_suppliers,
    "calculate_reorder": calculate_reorder,
    "get_procurement_plan": _cached_get_procurement_plan,
}


def execute_tool(name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Safely execute a registered tool by name with provided arguments.

    Returns a JSON-serializable dictionary. Catches any exception and returns
    {"error": "<message>"} instead of crashing.
    """
    if not isinstance(name, str) or name not in _TOOL_MAP:
        return {"error": f"unknown tool: {name}"}

    fn = _TOOL_MAP[name]
    call_args = args if isinstance(args, dict) else {}

    try:
        result = fn(**call_args)
        if isinstance(result, dict):
            return result
        return {"result": result}
    except Exception as exc:
        return {"error": f"Error executing tool '{name}': {str(exc)}"}

