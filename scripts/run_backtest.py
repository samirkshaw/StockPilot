"""
Script to run rolling-origin backtest across all products in StockPilot.

Outputs:
- Formatted console table comparing WAPE across all 4 forecasting methods
- Saves summary table to reports/forecast_backtest.csv
- Displays average baseline WAPE vs. average best-method WAPE
"""

import os
import sys
import pandas as pd

# Add project root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.demand_forecast import backtest_product, forecast_demand

DATA_DIR = os.path.join(REPO_ROOT, "data")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    products_path = os.path.join(DATA_DIR, "products.csv")

    if not os.path.exists(products_path):
        print(f"Error: {products_path} not found. Run generate_data.py first.")
        sys.exit(1)

    products_df = pd.read_csv(products_path)
    product_ids = products_df["product_id"].tolist()

    rows = []

    print("=" * 105)
    print("STOCKPILOT DEMAND FORECASTING BACKTEST REPORT (Horizon = 7 Days, Test Days = 60)")
    print("=" * 105)
    header = (
        f"{'Product':<9} {'MA(14) WAPE':<13} {'SES WAPE':<11} {'Seasonal WAPE':<15} "
        f"{'Base 30d WAPE':<15} {'Best Method':<18} {'Improvement':<13} {'Avg Daily FC':<12}"
    )
    print(header)
    print("-" * 105)

    for pid in product_ids:
        bt = backtest_product(pid, horizon=7, test_days=60)
        fc = forecast_demand(pid, horizon_days=7)

        ma_wape = bt["moving_average"]["wape"]
        ses_wape = bt["exp_smoothing"]["wape"]
        seas_wape = bt["weekday_seasonal"]["wape"]
        base_wape = bt["baseline_30d"]["wape"]
        best_method = bt["best_method"]
        imp = bt["improvement_vs_baseline_pct"]
        avg_fc = fc["avg_daily_forecast"]

        rows.append({
            "product_id": pid,
            "moving_average_wape": ma_wape,
            "exp_smoothing_wape": ses_wape,
            "weekday_seasonal_wape": seas_wape,
            "baseline_30d_wape": base_wape,
            "best_method": best_method,
            "improvement_vs_baseline_pct": imp,
            "avg_daily_forecast": avg_fc,
        })

        print(
            f"{pid:<9} {ma_wape:<13.2f} {ses_wape:<11.2f} {seas_wape:<15.2f} "
            f"{base_wape:<15.2f} {best_method:<18} {imp:<13.2f} {avg_fc:<12.2f}"
        )

    # Save to reports/forecast_backtest.csv
    out_df = pd.DataFrame(rows)
    csv_path = os.path.join(REPORTS_DIR, "forecast_backtest.csv")
    out_df.to_csv(csv_path, index=False)

    avg_baseline = out_df["baseline_30d_wape"].mean()
    # Best-method WAPE per product
    best_wapes = [
        row[f"{row['best_method']}_wape"] if f"{row['best_method']}_wape" in row else row["baseline_30d_wape"]
        for _, row in out_df.iterrows()
    ]
    avg_best = sum(best_wapes) / len(best_wapes)
    overall_reduction = avg_baseline - avg_best

    print("-" * 105)
    print(f"Results successfully saved to: {csv_path}")
    print("\nSummary Metrics Across All Products:")
    print(f" - Average Baseline (30-day Average) WAPE : {avg_baseline:.2f}%")
    print(f" - Average Best-Method Selection WAPE     : {avg_best:.2f}%")
    print(f" - Mean WAPE Reduction vs. Baseline       : {overall_reduction:.2f} percentage points")
    print("=" * 105)


if __name__ == "__main__":
    main()

