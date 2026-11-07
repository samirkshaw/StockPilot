"""
Reorder Calculation Tool for StockPilot.

Determines reorder points, lead-time shortfall, safety stock requirements,
and replenishment order quantities based on demand forecasts and stock levels.
"""

import math
import os
from typing import Any, Dict, Optional
from tools.inventory_lookup import inventory_lookup
from tools.sales_analysis import analyze_sales

# Path to the data directory containing CSV files
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def calculate_reorder(
    product_id: str,
    lead_time_days: int,
    coverage_days: int = 14,
    service_z: float = 1.65,
    daily_demand_override: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate inventory risk metrics and recommended replenishment quantity.

    Args:
        product_id: Product identifier (e.g., 'P001'). Case-insensitive.
        lead_time_days: Expected shipment transit duration in days.
        coverage_days: Target inventory cover duration to replenish post-arrival (default: 14 days).
        service_z: Safety factor for target cycle service level (default: 1.65 for ~95% service level).
        daily_demand_override: Optional daily demand to use instead of sales_analysis.recommended_demand.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - product_id (str): Identifier of the product
            - inputs (dict): Traceable input parameters used in the calculation:
                - daily_demand (float): Recommended daily demand rate
                - std_daily_demand (float): Historical daily demand standard deviation
                - current_stock (int): Units on hand at start
                - lead_time_days (int): Supplier delivery duration
                - coverage_days (int): Planned coverage window after arrival
                - service_z (float): Z-score safety factor
            - demand_during_lead_time (float): Expected demand while waiting for shipment
            - shortfall_before_arrival (float): Stock deficit expected prior to delivery
            - days_of_cover (float): Days current stock will last
            - days_uncovered_before_arrival (float): Gap between delivery lead time and stock cover
            - safety_stock (float): Buffer stock to protect against demand volatility
            - reorder_point (float): Stock threshold that should trigger replenishment
            - recommended_order_qty (int): Ceil integer quantity to order
            - risk_level (str): Urgency rating ('Critical', 'High', 'Medium', or 'Low')
        If the product_id is not found, returns {"error": "..."}.
    """
    if not product_id or not isinstance(product_id, str):
        return {"error": "Invalid product_id. Must be a non-empty string."}

    norm_id = product_id.strip().upper()

    # Retrieve current inventory
    inv_data = inventory_lookup(norm_id)
    if "error" in inv_data:
        return {"error": inv_data["error"]}

    # Retrieve sales metrics
    sales_data = analyze_sales(norm_id)
    if "error" in sales_data:
        return {"error": sales_data["error"]}

    lead_time = max(1, int(lead_time_days))
    cov_days = max(1, int(coverage_days))
    z = float(service_z)

    if daily_demand_override is not None:
        daily_demand = float(round(daily_demand_override, 2))
    else:
        daily_demand = float(sales_data["recommended_demand"])
    std_daily_demand = float(sales_data["std_daily_demand"])
    current_stock = int(inv_data["current_stock"])

    # 1. Expected demand during supplier transit window
    demand_during_lead_time = round(daily_demand * lead_time, 2)

    # 2. Deficit / shortfall before the order arrives
    shortfall_before_arrival = round(max(0.0, demand_during_lead_time - current_stock), 2)

    # 3. Days current on-hand stock will cover
    if current_stock == 0 or daily_demand <= 0:
        days_of_cover = 0.0
    else:
        days_of_cover = round(current_stock / daily_demand, 2)

    # 4. Period without stock prior to arrival
    days_uncovered_before_arrival = round(max(0.0, lead_time - days_of_cover), 2)

    # 5. Buffer safety stock
    safety_stock = round(z * std_daily_demand * math.sqrt(lead_time), 2)

    # 6. Reorder point
    reorder_point = round(demand_during_lead_time + safety_stock, 2)

    # 7. Recommended replenishment order quantity
    gross_target = (daily_demand * (lead_time + cov_days)) + safety_stock - current_stock
    recommended_order_qty = int(math.ceil(max(0.0, gross_target)))

    # 8. Urgency classification
    if current_stock == 0 or days_of_cover < lead_time:
        risk_level = "Critical"
    elif days_of_cover < 1.5 * lead_time:
        risk_level = "High"
    elif days_of_cover < 2.5 * lead_time:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    return {
        "product_id": norm_id,
        "inputs": {
            "daily_demand": daily_demand,
            "std_daily_demand": std_daily_demand,
            "current_stock": current_stock,
            "lead_time_days": lead_time,
            "coverage_days": cov_days,
            "service_z": z,
        },
        "demand_during_lead_time": demand_during_lead_time,
        "shortfall_before_arrival": shortfall_before_arrival,
        "days_of_cover": days_of_cover,
        "days_uncovered_before_arrival": days_uncovered_before_arrival,
        "safety_stock": safety_stock,
        "reorder_point": reorder_point,
        "recommended_order_qty": recommended_order_qty,
        "risk_level": risk_level,
    }

