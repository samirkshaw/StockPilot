"""
Scenario Simulation and Analysis Script for StockPilot.

Generates and documents three key operational supply chain scenarios:
1. Scenario A: Low stock with a 5-day supplier (Product P001)
2. Scenario B: Demand spike detection and responsive ordering (Product P003)
3. Scenario C: Healthy inventory with surplus coverage (Products P002 and P005)

Writes output to reports/scenarios.md.
"""

import math
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.inventory_lookup import inventory_lookup
from tools.sales_analysis import analyze_sales
from tools.demand_forecast import forecast_demand
from tools.reorder_calculation import calculate_reorder
from tools.procurement_planner import build_procurement_plan

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def generate_scenarios() -> str:
    """Run deterministic scenario evaluations and build markdown content."""
    plan = build_procurement_plan(horizon_days=7, coverage_days=14, planning_horizon_days=30)
    prods_by_id = {p["product_id"]: p for p in plan["products"]}
    rec_orders_by_id = {o["product_id"]: o for o in plan["strategies"]["recommended"]["orders"]}

    md = []
    md.append("# StockPilot Operational Scenarios Analysis")
    md.append("")
    md.append("This report presents three core simulated supply chain decision scenarios evaluated by StockPilot.")
    md.append("")

    # =========================================================================
    # SCENARIO A: Low stock with a 5-day supplier (P001)
    # =========================================================================
    md.append("## Scenario A: Low Stock with a 5-Day Supplier (Product P001)")
    md.append("")
    p001_prod = prods_by_id["P001"]
    p001_inv = inventory_lookup("P001")
    p001_demand = p001_prod["daily_demand"]
    p001_stock = p001_inv["current_stock"]

    # Evaluation with lead_time_days = 5
    r_5d = calculate_reorder("P001", lead_time_days=5, daily_demand_override=p001_demand)
    dlt_5d = r_5d["demand_during_lead_time"]
    short_5d = r_5d["shortfall_before_arrival"]
    cover_5d = r_5d["days_of_cover"]
    uncovered_5d = r_5d["days_uncovered_before_arrival"]
    risk_5d = r_5d["risk_level"]

    md.append(f"- **Product ID:** P001 ({p001_prod['name']})")
    md.append(f"- **Current Stock:** {p001_stock} units")
    md.append(f"- **Daily Demand Used:** {p001_demand:.2f} units/day")
    md.append(f"- **Evaluated Supplier Lead Time:** 5 days")
    md.append(f"- **Demand During Lead Time:** {dlt_5d:.2f} units")
    md.append(f"- **Shortfall Before Arrival:** {short_5d:.2f} units")
    md.append(f"- **Days of Cover:** {cover_5d:.2f} days")
    md.append(f"- **Days Uncovered Before Arrival:** {uncovered_5d:.2f} days")
    md.append(f"- **Risk Level:** `{risk_5d}`")
    md.append("")

    md.append("### P001 Supplier Comparison Options")
    md.append("")
    md.append("| Supplier ID | Supplier Name | Unit Cost ($) | Lead Time | Order Qty | Total Cost ($) | Shortfall | Days Uncovered | Rev at Risk ($) |")
    md.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for s in p001_prod["supplier_options"]:
        md.append(
            f"| **{s['supplier_id']}** | {s['supplier_name']} | ${s['unit_cost']:.2f} | {s['lead_time_days']}d | "
            f"{s['order_qty']} | ${s['total_cost']:,.2f} | {s['shortfall_before_arrival']:.2f} | "
            f"{s['days_uncovered_before_arrival']:.2f}d | ${s['revenue_at_risk']:,.2f} |"
        )
    md.append("")

    p001_rec = rec_orders_by_id["P001"]
    md.append(f"- **Recommended Supplier:** **{p001_rec['supplier_id']}** ({p001_rec['supplier_name']})")
    md.append(f"- **Recommendation Reasoning:** *\"{p001_rec['reason']}\"*")
    md.append("")

    # =========================================================================
    # SCENARIO B: Demand Spike (P003)
    # =========================================================================
    md.append("## Scenario B: Demand Spike Detection (Product P003)")
    md.append("")
    p003_sales = analyze_sales("P003")
    p003_fc = forecast_demand("P003", 7)
    p003_prod = prods_by_id["P003"]
    p003_stock = p003_prod["current_stock"]

    avg_180 = p003_sales["avg_daily_demand_180d"]
    avg_14 = p003_sales["avg_daily_demand_14d"]
    trend_ratio = p003_sales["trend_ratio"]
    spike_det = p003_sales["spike_detected"]
    fc_demand = p003_fc["avg_daily_forecast"]
    fc_method = p003_fc["method_used"]

    cover_180 = round(p003_stock / avg_180, 2)
    cover_fc = round(p003_stock / fc_demand, 2)
    cover_14 = round(p003_stock / avg_14, 2)

    md.append(f"- **Product ID:** P003 ({p003_prod['name']})")
    md.append(f"- **Current Stock:** {p003_stock} units")
    md.append(f"- **180-Day Baseline Daily Average:** {avg_180:.2f} units/day")
    md.append(f"- **Last 14-Day Daily Average:** {avg_14:.2f} units/day")
    md.append(f"- **Demand Trend Ratio (14d vs prior):** {trend_ratio:.2f}x")
    md.append(f"- **Spike Detected:** `{spike_det}` (True: surge exceeds +30% threshold)")
    md.append(f"- **Forecast Model Selected by Backtest:** `{fc_method}`")
    md.append(f"- **Forecast Daily Demand in Plan:** {fc_demand:.2f} units/day")
    md.append("")
    md.append("### Days of Inventory Cover Across Demand Perspectives")
    md.append(f"- **Under 180-Day Baseline Demand ({avg_180:.2f}/day):** **{cover_180:.2f} days** of cover (falsely appears safe)")
    md.append(f"- **Under Backtested Forecast Demand ({fc_demand:.2f}/day):** **{cover_fc:.2f} days** of cover (realistic buffer)")
    md.append(f"- **Under Last 14-Day Spike Demand ({avg_14:.2f}/day):** **{cover_14:.2f} days** of cover (critical depletion pace)")
    md.append("")

    # Illustrative comparison
    qty_180 = int(math.ceil(max(0.0, avg_180 * 30 - p003_stock)))
    qty_plan = p003_prod["required_qty"]

    p003_rec = rec_orders_by_id["P003"]
    rec_lead = p003_rec["lead_time_days"]
    dlt_180 = round(avg_180 * rec_lead, 2)
    dlt_fc = round(fc_demand * rec_lead, 2)
    dlt_14 = round(avg_14 * rec_lead, 2)

    md.append("### Illustrative Baseline Calculation vs. StockPilot Plan")
    md.append(
        "A naive inventory planner relying strictly on the 180-day historical mean would calculate required quantity as:"
    )
    md.append(f"- **Naive 180-Day Quantity:** `ceil(max(0, {avg_180:.2f} * 30 - {p003_stock}))` = **{qty_180} units**")
    md.append(f"- **StockPilot Plan Quantity:** `ceil(max(0, {fc_demand:.2f} * 30 - {p003_stock}))` = **{qty_plan} units**")
    md.append(f"- **Replenishment Under-Order Deficit if Naive:** {qty_plan - qty_180} units under-allocated!")
    md.append("")
    md.append(f"During recommended supplier delivery transit ({rec_lead} days with {p003_rec['supplier_id']}):")
    md.append(f"- **Demand under 180-Day Assumption:** {dlt_180:.2f} units (expected buffer remaining: {p003_stock - dlt_180:.2f} units)")
    md.append(f"- **Demand under Forecast Assumption:** {dlt_fc:.2f} units (expected buffer remaining: {p003_stock - dlt_fc:.2f} units)")
    md.append(f"- **Demand under Recent 14d Spike Rate:** {dlt_14:.2f} units (expected buffer remaining: {p003_stock - dlt_14:.2f} units)")
    md.append("")

    # =========================================================================
    # SCENARIO C: Healthy Inventory (P002 and P005)
    # =========================================================================
    md.append("## Scenario C: Healthy Inventory & Surplus Coverage (Products P002 and P005)")
    md.append("")
    md.append("| Product ID | Product Name | Current Stock | Daily Demand | Days of Cover | Plan Action | Risk Level |")
    md.append("|:---|:---|:---:|:---:|:---:|:---:|:---:|")

    for pid in ["P002", "P005"]:
        p = prods_by_id[pid]
        md.append(
            f"| **{p['product_id']}** | {p['name']} | {p['current_stock']} | {p['daily_demand']:.2f} | "
            f"{p['days_of_cover']:.2f} days | **{p['action']}** | `{p['risk_level']}` |"
        )
    md.append("")
    md.append(
        "Both products hold sufficient stock exceeding the 30-day replenishment window without capital commitment."
    )
    md.append("")

    return "\n".join(md)


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_text = generate_scenarios()

    print(report_text)

    scenarios_path = os.path.join(REPORTS_DIR, "scenarios.md")
    with open(scenarios_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n" + "=" * 80)
    print(f"Scenarios analysis report successfully written to: {scenarios_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()

