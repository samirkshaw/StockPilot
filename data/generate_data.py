"""
Simulated Data Generator for StockPilot.
Generates realistic supply chain datasets:
- products.csv: Product catalog (10 items, P001-P010)
- inventory.csv: Current stock levels and snapshot timestamp
- sales_history.csv: 180 days of daily sales per product ending on 2026-11-06
- suppliers.csv: Supplier options with cost vs. lead-time tradeoffs
"""

import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Fix random seed for reproducibility
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_products() -> pd.DataFrame:
    """Generate product catalog with 10 products across various categories."""
    products = [
        {"product_id": "P001", "name": "Ergonomic Office Chair", "category": "Furniture", "unit_price": 199.99},
        {"product_id": "P002", "name": "Wireless Mechanical Keyboard", "category": "Electronics", "unit_price": 89.99},
        {"product_id": "P003", "name": "USB-C Dual 4K Docking Station", "category": "Electronics", "unit_price": 129.99},
        {"product_id": "P004", "name": "Noise-Cancelling Headphones", "category": "Audio", "unit_price": 149.99},
        {"product_id": "P005", "name": "Standing Desk Anti-Fatigue Mat", "category": "Accessories", "unit_price": 39.99},
        {"product_id": "P006", "name": "Ultra-Wide 34-inch Monitor", "category": "Electronics", "unit_price": 349.99},
        {"product_id": "P007", "name": "High-Speed Thermal Receipt Printer", "category": "Office Equipment", "unit_price": 119.99},
        {"product_id": "P008", "name": "Heavy-Duty Dual Monitor Arm", "category": "Accessories", "unit_price": 59.99},
        {"product_id": "P009", "name": "Smart LED Desk Task Lamp", "category": "Lighting", "unit_price": 45.99},
        {"product_id": "P010", "name": "Conference Room Speakerphone", "category": "Audio", "unit_price": 219.99},
    ]
    return pd.DataFrame(products)

def generate_inventory() -> pd.DataFrame:
    """
    Generate inventory snapshot as of 2026-11-06.
    Planted scenarios:
    - P001: 15 units (critical stockout risk, daily demand ~10)
    - P002: 500 units (healthy, covers 30+ days of demand)
    - P003: 95 units (covers ~12 days of baseline demand, but only ~6 days of recent spike demand)
    - P004: 0 units (already out of stock)
    - P005: 250 units (overstocked slow mover, ~1 unit/day demand)
    - P006 to P010: varied realistic stock levels
    """
    inventory = [
        {"product_id": "P001", "current_stock": 15, "last_updated": "2026-11-06"},
        {"product_id": "P002", "current_stock": 500, "last_updated": "2026-11-06"},
        {"product_id": "P003", "current_stock": 95, "last_updated": "2026-11-06"},
        {"product_id": "P004", "current_stock": 0, "last_updated": "2026-11-06"},
        {"product_id": "P005", "current_stock": 250, "last_updated": "2026-11-06"},
        {"product_id": "P006", "current_stock": 180, "last_updated": "2026-11-06"},
        {"product_id": "P007", "current_stock": 125, "last_updated": "2026-11-06"},
        {"product_id": "P008", "current_stock": 90, "last_updated": "2026-11-06"},
        {"product_id": "P009", "current_stock": 360, "last_updated": "2026-11-06"},
        {"product_id": "P010", "current_stock": 25, "last_updated": "2026-11-06"},
    ]
    return pd.DataFrame(inventory)

def generate_sales_history() -> pd.DataFrame:
    """
    Generate 180 days of daily sales ending on 2026-11-06 for every product.
    Includes base demand, weekly seasonality, random noise, and planted scenario for P003.
    """
    end_date = datetime.strptime("2026-11-06", "%Y-%m-%d")
    date_list = [end_date - timedelta(days=i) for i in reversed(range(180))]

    # Base daily demand parameters per product
    # P001: ~10 units/day
    # P003: ~8 units/day earlier, ~16 units/day in the last 14 days (2x spike)
    # P005: ~1 unit/day (slow mover)
    base_demands = {
        "P001": 10.0,
        "P002": 12.0,
        "P003": 8.0,
        "P004": 6.0,
        "P005": 1.0,
        "P006": 15.0,
        "P007": 22.0,
        "P008": 5.0,
        "P009": 18.0,
        "P010": 2.5,
    }

    # Weekly seasonality factors (Monday=0 to Sunday=6)
    # Average across the week is exactly 1.0
    weekday_factors = {
        0: 0.90,  # Monday
        1: 0.90,  # Tuesday
        2: 0.95,  # Wednesday
        3: 0.95,  # Thursday
        4: 1.10,  # Friday
        5: 1.15,  # Saturday (weekend boost)
        6: 1.05,  # Sunday (weekend boost)
    }

    records = []
    spike_cutoff = end_date - timedelta(days=14)

    for current_date in date_list:
        date_str = current_date.strftime("%Y-%m-%d")
        dow = current_date.weekday()
        dow_mult = weekday_factors[dow]

        for product_id, base_demand in base_demands.items():
            # Scenario P003: 2x demand spike in the last 14 days
            if product_id == "P003" and current_date > spike_cutoff:
                effective_base = base_demand * 2.0
            else:
                effective_base = base_demand

            expected = effective_base * dow_mult

            # Gaussian noise proportional to demand scale
            noise_std = max(0.4, expected * 0.15)
            raw_sales = np.random.normal(loc=expected, scale=noise_std)
            units_sold = max(0, int(round(raw_sales)))

            records.append({
                "date": date_str,
                "product_id": product_id,
                "units_sold": units_sold
            })

    return pd.DataFrame(records)

def generate_suppliers() -> pd.DataFrame:
    """
    Generate suppliers data with 2 to 3 suppliers per product.
    Implements a realistic tradeoff:
    - Cheaper unit cost -> longer lead time, higher min order qty (MOQ)
    - Pricier unit cost -> shorter lead time, lower min order qty (MOQ)
    """
    suppliers = [
        # P001: Ergonomic Chair (must include supplier with lead_time_days = 5)
        {"supplier_id": "SUP-101", "supplier_name": "Apex Office Works", "product_id": "P001", "unit_cost": 88.00, "lead_time_days": 14, "min_order_qty": 50},
        {"supplier_id": "SUP-102", "supplier_name": "RapidSeat Logistics", "product_id": "P001", "unit_cost": 108.00, "lead_time_days": 5, "min_order_qty": 20},
        {"supplier_id": "SUP-103", "supplier_name": "SwiftFurnish Express", "product_id": "P001", "unit_cost": 125.00, "lead_time_days": 2, "min_order_qty": 10},

        # P002: Wireless Keyboard
        {"supplier_id": "SUP-104", "supplier_name": "Pacific Keytronics", "product_id": "P002", "unit_cost": 36.00, "lead_time_days": 21, "min_order_qty": 100},
        {"supplier_id": "SUP-105", "supplier_name": "AeroTech Components", "product_id": "P002", "unit_cost": 45.00, "lead_time_days": 7, "min_order_qty": 30},

        # P003: USB-C Docking Station
        {"supplier_id": "SUP-105", "supplier_name": "AeroTech Components", "product_id": "P003", "unit_cost": 58.00, "lead_time_days": 15, "min_order_qty": 40},
        {"supplier_id": "SUP-106", "supplier_name": "NexLink Technologies", "product_id": "P003", "unit_cost": 72.00, "lead_time_days": 4, "min_order_qty": 15},

        # P004: Noise-Cancelling Headphones
        {"supplier_id": "SUP-107", "supplier_name": "SonicWave Global", "product_id": "P004", "unit_cost": 62.00, "lead_time_days": 18, "min_order_qty": 50},
        {"supplier_id": "SUP-108", "supplier_name": "Vanguard Audio Supply", "product_id": "P004", "unit_cost": 78.00, "lead_time_days": 8, "min_order_qty": 20},
        {"supplier_id": "SUP-103", "supplier_name": "SwiftFurnish Express", "product_id": "P004", "unit_cost": 92.00, "lead_time_days": 3, "min_order_qty": 10},

        # P005: Standing Desk Mat
        {"supplier_id": "SUP-101", "supplier_name": "Apex Office Works", "product_id": "P005", "unit_cost": 14.50, "lead_time_days": 16, "min_order_qty": 60},
        {"supplier_id": "SUP-109", "supplier_name": "ErgoCare Distributors", "product_id": "P005", "unit_cost": 19.50, "lead_time_days": 6, "min_order_qty": 25},

        # P006: Ultra-Wide Monitor
        {"supplier_id": "SUP-104", "supplier_name": "Pacific Keytronics", "product_id": "P006", "unit_cost": 175.00, "lead_time_days": 20, "min_order_qty": 30},
        {"supplier_id": "SUP-106", "supplier_name": "NexLink Technologies", "product_id": "P006", "unit_cost": 215.00, "lead_time_days": 6, "min_order_qty": 10},

        # P007: Thermal Receipt Printer
        {"supplier_id": "SUP-108", "supplier_name": "Vanguard Audio Supply", "product_id": "P007", "unit_cost": 54.00, "lead_time_days": 12, "min_order_qty": 40},
        {"supplier_id": "SUP-110", "supplier_name": "DirectPOS Hardware", "product_id": "P007", "unit_cost": 69.00, "lead_time_days": 4, "min_order_qty": 15},

        # P008: Dual Monitor Arm
        {"supplier_id": "SUP-101", "supplier_name": "Apex Office Works", "product_id": "P008", "unit_cost": 24.00, "lead_time_days": 14, "min_order_qty": 50},
        {"supplier_id": "SUP-109", "supplier_name": "ErgoCare Distributors", "product_id": "P008", "unit_cost": 32.00, "lead_time_days": 5, "min_order_qty": 15},

        # P009: Smart LED Desk Lamp
        {"supplier_id": "SUP-104", "supplier_name": "Pacific Keytronics", "product_id": "P009", "unit_cost": 18.00, "lead_time_days": 18, "min_order_qty": 80},
        {"supplier_id": "SUP-105", "supplier_name": "AeroTech Components", "product_id": "P009", "unit_cost": 23.50, "lead_time_days": 8, "min_order_qty": 30},
        {"supplier_id": "SUP-106", "supplier_name": "NexLink Technologies", "product_id": "P009", "unit_cost": 28.00, "lead_time_days": 3, "min_order_qty": 15},

        # P010: Conference Speakerphone
        {"supplier_id": "SUP-107", "supplier_name": "SonicWave Global", "product_id": "P010", "unit_cost": 105.00, "lead_time_days": 15, "min_order_qty": 25},
        {"supplier_id": "SUP-110", "supplier_name": "DirectPOS Hardware", "product_id": "P010", "unit_cost": 135.00, "lead_time_days": 4, "min_order_qty": 8},
    ]
    return pd.DataFrame(suppliers)

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    products_df = generate_products()
    inventory_df = generate_inventory()
    sales_df = generate_sales_history()
    suppliers_df = generate_suppliers()

    products_path = os.path.join(DATA_DIR, "products.csv")
    inventory_path = os.path.join(DATA_DIR, "inventory.csv")
    sales_path = os.path.join(DATA_DIR, "sales_history.csv")
    suppliers_path = os.path.join(DATA_DIR, "suppliers.csv")

    products_df.to_csv(products_path, index=False)
    inventory_df.to_csv(inventory_path, index=False)
    sales_df.to_csv(sales_path, index=False)
    suppliers_df.to_csv(suppliers_path, index=False)

    print(f"Data generation complete (seed={RANDOM_SEED}):")
    print(f" - {products_path} ({len(products_df)} rows)")
    print(f" - {inventory_path} ({len(inventory_df)} rows)")
    print(f" - {sales_path} ({len(sales_df)} rows)")
    print(f" - {suppliers_path} ({len(suppliers_df)} rows)")

if __name__ == "__main__":
    main()

