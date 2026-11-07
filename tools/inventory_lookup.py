"""
Inventory Lookup Tool for StockPilot.

Provides deterministic functions to query current inventory levels,
product catalog information, and list available products.
"""

import os
from typing import Any, Dict, List
import pandas as pd

# Path to the data directory containing CSV files
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def inventory_lookup(product_id: str) -> Dict[str, Any]:
    """
    Look up current inventory stock and catalog details for a single product.

    Args:
        product_id: Product identifier (e.g., 'P001'). Case-insensitive.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - product_id (str): Product identifier
            - name (str): Product name
            - category (str): Category name
            - unit_price (float): Price per unit
            - current_stock (int): Units currently in stock
            - last_updated (str): Snapshot date of the inventory
        If the product_id is not found, returns {"error": "..."}.
    """
    if not product_id or not isinstance(product_id, str):
        return {"error": "Invalid product_id. Must be a non-empty string."}

    norm_id = product_id.strip().upper()

    products_path = os.path.join(DATA_DIR, "products.csv")
    inventory_path = os.path.join(DATA_DIR, "inventory.csv")

    if not os.path.exists(products_path) or not os.path.exists(inventory_path):
        return {"error": f"Data files not found in {DATA_DIR}."}

    products_df = pd.read_csv(products_path)
    inventory_df = pd.read_csv(inventory_path)

    # Filter for the target product
    prod_row = products_df[products_df["product_id"].str.upper() == norm_id]
    if prod_row.empty:
        return {"error": f"Product ID '{product_id}' not found in products catalog."}

    inv_row = inventory_df[inventory_df["product_id"].str.upper() == norm_id]
    if inv_row.empty:
        return {"error": f"Product ID '{product_id}' not found in inventory records."}

    prod_data = prod_row.iloc[0]
    inv_data = inv_row.iloc[0]

    return {
        "product_id": str(prod_data["product_id"]),
        "name": str(prod_data["name"]),
        "category": str(prod_data["category"]),
        "unit_price": float(round(prod_data["unit_price"], 2)),
        "current_stock": int(inv_data["current_stock"]),
        "last_updated": str(inv_data["last_updated"]),
    }


def list_products() -> List[Dict[str, str]]:
    """
    List all available products in the catalog.

    Returns:
        list[dict]: A list of dictionaries, each containing:
            - product_id (str): Unique product identifier
            - name (str): Product name
    """
    products_path = os.path.join(DATA_DIR, "products.csv")
    if not os.path.exists(products_path):
        return []

    products_df = pd.read_csv(products_path)
    return [
        {
            "product_id": str(row["product_id"]),
            "name": str(row["name"]),
        }
        for _, row in products_df.iterrows()
    ]

