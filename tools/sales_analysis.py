"""
Sales Analysis Tool for StockPilot.

Analyzes historical sales data to calculate average daily demand across
multiple rolling windows (7d, 14d, 30d, 180d), detect demand spikes/trends,
and output a recommended daily demand figure for replenishment planning.
"""

import os
from typing import Any, Dict
import pandas as pd

# Path to the data directory containing CSV files
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def analyze_sales(product_id: str) -> Dict[str, Any]:
    """
    Analyze sales history for a given product and calculate demand metrics.

    Args:
        product_id: Product identifier (e.g., 'P001'). Case-insensitive.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - product_id (str): Identifier of the product
            - avg_daily_demand_7d (float): Average daily sales in the last 7 days
            - avg_daily_demand_14d (float): Average daily sales in the last 14 days
            - avg_daily_demand_30d (float): Average daily sales in the last 30 days
            - avg_daily_demand_180d (float): Average daily sales over the full 180 days
            - std_daily_demand (float): Standard deviation of daily demand over 180 days
            - trend_ratio (float): Ratio of last 14-day average to the prior period average
            - spike_detected (bool): True if trend_ratio > 1.3, indicating a recent surge
            - recommended_demand (float): 14-day average if spike detected, else 30-day average
        If the product_id is not found, returns {"error": "..."}.
    """
    if not product_id or not isinstance(product_id, str):
        return {"error": "Invalid product_id. Must be a non-empty string."}

    norm_id = product_id.strip().upper()

    sales_path = os.path.join(DATA_DIR, "sales_history.csv")
    if not os.path.exists(sales_path):
        return {"error": f"Sales data file not found at {sales_path}."}

    sales_df = pd.read_csv(sales_path)

    # Filter for the target product
    prod_sales = sales_df[sales_df["product_id"].str.upper() == norm_id].copy()
    if prod_sales.empty:
        return {"error": f"Product ID '{product_id}' not found in sales history."}

    # Ensure chronological order
    prod_sales["date"] = pd.to_datetime(prod_sales["date"])
    prod_sales = prod_sales.sort_values("date").reset_index(drop=True)

    total_records = len(prod_sales)
    if total_records == 0:
        return {"error": f"No sales records found for product ID '{product_id}'."}

    units = prod_sales["units_sold"]

    # Rolling window averages
    avg_7d = float(units.tail(min(7, total_records)).mean())
    avg_14d = float(units.tail(min(14, total_records)).mean())
    avg_30d = float(units.tail(min(30, total_records)).mean())
    avg_180d = float(units.mean())

    # Standard deviation over the full history (sample standard deviation)
    std_180d = float(units.std(ddof=1)) if total_records > 1 else 0.0

    # Trend calculation: 14d average vs. average of all days prior to the last 14
    if total_records > 14:
        prior_units = units.iloc[:-14]
        avg_prior = float(prior_units.mean()) if len(prior_units) > 0 else avg_14d
    else:
        avg_prior = avg_14d

    if avg_prior > 0:
        trend_ratio = float(avg_14d / avg_prior)
    else:
        trend_ratio = 1.0 if avg_14d == 0 else 2.0

    spike_detected = bool(trend_ratio > 1.3)

    # Recommended daily demand: responsive to recent spikes, stable under normal conditions
    recommended_demand = avg_14d if spike_detected else avg_30d

    return {
        "product_id": norm_id,
        "avg_daily_demand_7d": round(avg_7d, 2),
        "avg_daily_demand_14d": round(avg_14d, 2),
        "avg_daily_demand_30d": round(avg_30d, 2),
        "avg_daily_demand_180d": round(avg_180d, 2),
        "std_daily_demand": round(std_180d, 2),
        "trend_ratio": round(trend_ratio, 2),
        "spike_detected": spike_detected,
        "recommended_demand": round(recommended_demand, 2),
    }

