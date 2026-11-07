"""
Supplier Comparison Tool for StockPilot.

Ranks and compares available suppliers for a product based on unit cost,
lead time (delivery speed), and minimum order quantity (MOQ) requirements.
"""

import os
from typing import Any, Dict, List
import pandas as pd

# Path to the data directory containing CSV files
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def compare_suppliers(product_id: str, required_qty: int) -> Dict[str, Any]:
    """
    Compare all available suppliers for a given product and calculate order costs.

    Args:
        product_id: Product identifier (e.g., 'P001'). Case-insensitive.
        required_qty: Quantity of units needed to replenish inventory.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - product_id (str): Identifier of the product
            - required_qty (int): Input quantity requested
            - suppliers (list[dict]): List of supplier options, each containing:
                - supplier_id (str): Supplier identifier
                - supplier_name (str): Company name of the supplier
                - unit_cost (float): Cost per unit
                - lead_time_days (int): Days required for order delivery
                - min_order_qty (int): Minimum order quantity (MOQ)
                - order_qty (int): Effective order quantity = max(required_qty, min_order_qty)
                - total_cost (float): Total purchase cost = order_qty * unit_cost
            - cheapest_supplier_id (str): Supplier offering the lowest unit cost
            - fastest_supplier_id (str): Supplier offering the shortest lead time
        If the product_id is not found, returns {"error": "..."}.
    """
    if not product_id or not isinstance(product_id, str):
        return {"error": "Invalid product_id. Must be a non-empty string."}

    norm_id = product_id.strip().upper()
    req_qty = max(0, int(required_qty)) if isinstance(required_qty, (int, float)) else 0

    suppliers_path = os.path.join(DATA_DIR, "suppliers.csv")
    if not os.path.exists(suppliers_path):
        return {"error": f"Suppliers data file not found at {suppliers_path}."}

    suppliers_df = pd.read_csv(suppliers_path)

    # Filter for the target product
    prod_suppliers = suppliers_df[suppliers_df["product_id"].str.upper() == norm_id].copy()
    if prod_suppliers.empty:
        return {"error": f"Product ID '{product_id}' not found in suppliers catalog."}

    supplier_list: List[Dict[str, Any]] = []

    for _, row in prod_suppliers.iterrows():
        unit_cost = float(round(row["unit_cost"], 2))
        lead_time = int(row["lead_time_days"])
        moq = int(row["min_order_qty"])
        order_qty = int(max(req_qty, moq))
        total_cost = float(round(order_qty * unit_cost, 2))

        supplier_list.append({
            "supplier_id": str(row["supplier_id"]),
            "supplier_name": str(row["supplier_name"]),
            "unit_cost": unit_cost,
            "lead_time_days": lead_time,
            "min_order_qty": moq,
            "order_qty": order_qty,
            "total_cost": total_cost,
        })

    # Identify cheapest (lowest unit cost) and fastest (shortest lead time)
    cheapest = min(supplier_list, key=lambda s: (s["unit_cost"], s["lead_time_days"]))
    fastest = min(supplier_list, key=lambda s: (s["lead_time_days"], s["unit_cost"]))

    return {
        "product_id": norm_id,
        "required_qty": req_qty,
        "suppliers": supplier_list,
        "cheapest_supplier_id": cheapest["supplier_id"],
        "fastest_supplier_id": fastest["supplier_id"],
    }

