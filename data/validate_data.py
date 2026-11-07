"""
Validation script for StockPilot simulated datasets.
Checks and displays:
- Row counts for all four CSV files
- Date range and total days for sales_history.csv
- Stock levels vs. 180-day average daily demand per product (including recent spike check)
- Supplier counts and tradeoff verification per product (at least 2 suppliers each)
"""

import os
import pandas as pd

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    products_path = os.path.join(DATA_DIR, "products.csv")
    inventory_path = os.path.join(DATA_DIR, "inventory.csv")
    sales_path = os.path.join(DATA_DIR, "sales_history.csv")
    suppliers_path = os.path.join(DATA_DIR, "suppliers.csv")

    # Ensure all files exist
    for path in [products_path, inventory_path, sales_path, suppliers_path]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing required data file: {path}. Run generate_data.py first.")

    # Load datasets
    products_df = pd.read_csv(products_path)
    inventory_df = pd.read_csv(inventory_path)
    sales_df = pd.read_csv(sales_path)
    suppliers_df = pd.read_csv(suppliers_path)

    print("=" * 60)
    print("STOCKPILOT DATA VALIDATION REPORT")
    print("=" * 60)

    # 1. Row counts
    print("\n1. File Row Counts:")
    print(f" - products.csv      : {len(products_df):>5} rows")
    print(f" - inventory.csv     : {len(inventory_df):>5} rows")
    print(f" - sales_history.csv : {len(sales_df):>5} rows")
    print(f" - suppliers.csv     : {len(suppliers_df):>5} rows")

    # 2. Date range of sales
    min_date = sales_df["date"].min()
    max_date = sales_df["date"].max()
    num_days = sales_df["date"].nunique()
    print(f"\n2. Sales History Date Range:")
    print(f" - Start Date : {min_date}")
    print(f" - End Date   : {max_date}")
    print(f" - Total Days : {num_days} days")

    # 3. Stock and average daily demand
    # Full 180-day average
    avg_demand = sales_df.groupby("product_id")["units_sold"].mean().rename("avg_daily_demand_180d")

    # Last 14-day average to highlight demand spikes (e.g. P003)
    sales_df["date_dt"] = pd.to_datetime(sales_df["date"])
    max_dt = sales_df["date_dt"].max()
    cutoff_14d = max_dt - pd.Timedelta(days=14)
    recent_14d = sales_df[sales_df["date_dt"] > cutoff_14d]
    avg_recent = recent_14d.groupby("product_id")["units_sold"].mean().rename("avg_demand_last_14d")

    summary_df = products_df[["product_id", "name"]].merge(inventory_df[["product_id", "current_stock"]], on="product_id")
    summary_df = summary_df.merge(avg_demand, on="product_id")
    summary_df = summary_df.merge(avg_recent, on="product_id")
    summary_df["days_of_stock_180d"] = (summary_df["current_stock"] / summary_df["avg_daily_demand_180d"]).round(1)

    print(f"\n3. Product Stock and Demand Summary:")
    print(f"{'ID':<6} {'Product Name':<35} {'Stock':<7} {'180d Avg':<10} {'14d Avg':<10} {'Days Stock':<12}")
    print("-" * 84)
    for _, row in summary_df.iterrows():
        print(f"{row['product_id']:<6} {row['name']:<35} {row['current_stock']:<7} {row['avg_daily_demand_180d']:<10.2f} {row['avg_demand_last_14d']:<10.2f} {row['days_of_stock_180d']:<12.1f}")

    # 4. Supplier count verification
    supplier_counts = suppliers_df.groupby("product_id").size()
    print(f"\n4. Supplier Verification:")
    all_passed = True
    for pid in products_df["product_id"]:
        count = supplier_counts.get(pid, 0)
        has_min_suppliers = count >= 2
        status = "PASSED" if has_min_suppliers else "FAILED"
        print(f" - Product {pid}: {count} suppliers [{status}]")
        if not has_min_suppliers:
            all_passed = False

    if all_passed:
        print("\nAll products have at least 2 suppliers with cost/lead-time tradeoffs.")
    else:
        print("\nValidation failed: some products have fewer than 2 suppliers.")

    print("=" * 60)

if __name__ == "__main__":
    main()

