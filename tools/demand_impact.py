"""
Demand Impact Analysis Tool for StockPilot.

Compares inventory coverage and reorder requirements under the long-run
historical baseline (180 days) versus the recent demand trend and backtested
forecast. Designed to evaluate the operational impact of demand spikes.
"""

import math
from typing import Any, Dict

from tools.sales_analysis import analyze_sales
from tools.demand_forecast import forecast_demand
from tools.inventory_lookup import inventory_lookup
from tools.procurement_planner import build_procurement_plan


def get_demand_impact(product_id: str) -> Dict[str, Any]:
    """
    Compare inventory coverage and procurement quantities between long-run
    historical average demand and the recent trend/forecast.

    Args:
        product_id (str): Unique product identifier (e.g. 'P001', 'P003').

    Returns:
        dict:
            - avg_demand_180d (float): 180-day baseline average daily demand.
            - avg_demand_14d (float): Last 14-day average daily demand.
            - trend_ratio (float): Ratio of recent demand vs prior period.
            - spike_detected (bool): True if recent demand surged > 30%.
            - forecast_demand_per_day (float): Selected forecast daily demand.
            - forecast_method (str): Name of the best-performing forecast model.
            - current_stock (int): Current units in inventory.
            - days_of_cover_at_180d_avg (float): Days stock covers under 180d demand.
            - days_of_cover_at_forecast (float): Days stock covers under forecast.
            - days_of_cover_at_14d_avg (float): Days stock covers under recent 14d demand.
            - qty_if_180d_average (int): Reorder qty required under naive 180d demand.
            - qty_in_plan (int): Official required order qty from procurement plan.
            - qty_difference (int): Extra units ordered due to trend/forecast.
            - planning_horizon_days (int): Planning horizon window (30 days).
    """
    # 1. Fetch sales analysis
    sales = analyze_sales(product_id)
    if "error" in sales:
        return {"error": f"Product '{product_id}' not found or invalid: {sales['error']}"}

    # 2. Fetch inventory
    inv = inventory_lookup(product_id)
    if "error" in inv:
        return {"error": f"Product '{product_id}' not found in inventory: {inv['error']}"}

    # 3. Fetch forecast
    fc = forecast_demand(product_id, horizon_days=7)
    if "error" in fc:
        return {"error": f"Failed forecasting demand for product '{product_id}': {fc['error']}"}

    # 4. Fetch procurement plan
    plan = build_procurement_plan()
    if "error" in plan:
        return {"error": f"Failed building procurement plan: {plan['error']}"}

    # Extract product from plan
    plan_product = None
    for p in plan.get("products", []):
        if p.get("product_id") == product_id:
            plan_product = p
            break

    if plan_product is None:
        return {"error": f"Product '{product_id}' not found in procurement plan."}

    # Calculations
    planning_horizon_days = 30
    current_stock = int(inv["current_stock"])
    avg_demand_180d = round(float(sales["avg_daily_demand_180d"]), 2)
    avg_demand_14d = round(float(sales["avg_daily_demand_14d"]), 2)
    trend_ratio = round(float(sales["trend_ratio"]), 2)
    spike_detected = bool(sales["spike_detected"])

    forecast_demand_per_day = round(float(fc["avg_daily_forecast"]), 2)
    forecast_method = str(fc["method_used"])

    # Days of cover (0 if stock is 0)
    if current_stock == 0:
        doc_180d = 0.0
        doc_forecast = 0.0
        doc_14d = 0.0
    else:
        doc_180d = round(current_stock / avg_demand_180d, 2) if avg_demand_180d > 0 else 0.0
        doc_forecast = round(current_stock / forecast_demand_per_day, 2) if forecast_demand_per_day > 0 else 0.0
        doc_14d = round(current_stock / avg_demand_14d, 2) if avg_demand_14d > 0 else 0.0

    # Naive order quantity under 180-day average
    qty_if_180d_average = int(math.ceil(max(0.0, avg_demand_180d * planning_horizon_days - current_stock)))

    # Official plan quantity
    qty_in_plan = int(plan_product["required_qty"])
    qty_difference = int(qty_in_plan - qty_if_180d_average)

    return {
        "avg_demand_180d": avg_demand_180d,
        "avg_demand_14d": avg_demand_14d,
        "trend_ratio": trend_ratio,
        "spike_detected": spike_detected,
        "forecast_demand_per_day": forecast_demand_per_day,
        "forecast_method": forecast_method,
        "current_stock": current_stock,
        "days_of_cover_at_180d_avg": doc_180d,
        "days_of_cover_at_forecast": doc_forecast,
        "days_of_cover_at_14d_avg": doc_14d,
        "qty_if_180d_average": qty_if_180d_average,
        "qty_in_plan": qty_in_plan,
        "qty_difference": qty_difference,
        "planning_horizon_days": planning_horizon_days,
    }

