"""
Test Suite for StockPilot Operational Scenarios (Step 6).

Asserts and validates:
1. P001 shortfall in Scenario A is between 34 and 37 units.
2. Scenario B reports spike_detected == True, and the naive 180-day quantity is strictly smaller than the plan quantity.
3. Products P002 and P005 have action 'No order needed'.
4. reports/scenarios.md exists and contains all three scenario headings.
"""

import math
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.sales_analysis import analyze_sales
from tools.reorder_calculation import calculate_reorder
from tools.procurement_planner import build_procurement_plan
from scripts.run_scenarios import generate_scenarios

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def run_tests():
    print("=" * 80)
    print("STARTING OPERATIONAL SCENARIOS VERIFICATION (Step 6)")
    print("=" * 80)

    # First ensure scenarios report is generated
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_text = generate_scenarios()
    scenarios_md_path = os.path.join(REPORTS_DIR, "scenarios.md")
    with open(scenarios_md_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    plan = build_procurement_plan(horizon_days=7, coverage_days=14, planning_horizon_days=30)
    prods = {p["product_id"]: p for p in plan["products"]}

    # --------------------------------------------------------------------------
    # Check 1: P001 shortfall in Scenario A is between 34 and 37
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying Scenario A (P001 shortfall with 5-day supplier)...")
    p001_demand = prods["P001"]["daily_demand"]
    r_5d = calculate_reorder("P001", lead_time_days=5, daily_demand_override=p001_demand)
    shortfall_a = r_5d["shortfall_before_arrival"]

    print(f" -> P001 Lead Time: 5 days | Daily Demand: {p001_demand:.2f} | Shortfall: {shortfall_a:.2f}")
    assert 34.0 <= shortfall_a <= 37.0, (
        f"Expected Scenario A shortfall between 34 and 37, got {shortfall_a}"
    )
    print(" -> PASSED: Scenario A shortfall is within expected bounds (34 to 37).")

    # --------------------------------------------------------------------------
    # Check 2: Scenario B spike detection and naive vs plan order quantity
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying Scenario B (P003 demand spike and order quantity)...")
    s_p003 = analyze_sales("P003")
    spike_detected = s_p003["spike_detected"]
    avg180 = s_p003["avg_daily_demand_180d"]
    p003_stock = prods["P003"]["current_stock"]

    qty_180 = int(math.ceil(max(0.0, avg180 * 30 - p003_stock)))
    qty_plan = prods["P003"]["required_qty"]

    print(f" -> P003 Spike Detected: {spike_detected}")
    print(f" -> Naive 180-Day Quantity: {qty_180} units")
    print(f" -> StockPilot Plan Quantity: {qty_plan} units")

    assert spike_detected is True, f"Expected spike_detected True for P003, got {spike_detected}"
    assert qty_180 < qty_plan, (
        f"Expected naive 180-day quantity ({qty_180}) to be strictly smaller than plan quantity ({qty_plan})"
    )
    print(" -> PASSED: Scenario B confirmed spike_detected=True and plan responsive increase.")

    # --------------------------------------------------------------------------
    # Check 3: P002 and P005 have action 'No order needed'
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying Scenario C (Healthy inventory for P002 and P005)...")
    act_p002 = prods["P002"]["action"]
    act_p005 = prods["P005"]["action"]

    print(f" -> P002 Action: {act_p002} (Days cover: {prods['P002']['days_of_cover']})")
    print(f" -> P005 Action: {act_p005} (Days cover: {prods['P005']['days_of_cover']})")

    assert act_p002 == "No order needed", f"P002 action should be 'No order needed', got {act_p002}"
    assert act_p005 == "No order needed", f"P005 action should be 'No order needed', got {act_p005}"
    print(" -> PASSED: Scenario C confirmed both P002 and P005 are 'No order needed'.")

    # --------------------------------------------------------------------------
    # Check 4: reports/scenarios.md exists and contains three scenario headings
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying reports/scenarios.md exists and has all 3 headings...")
    assert os.path.exists(scenarios_md_path), f"File {scenarios_md_path} does not exist"

    with open(scenarios_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "## Scenario A:" in content, "Missing '## Scenario A:' in scenarios.md"
    assert "## Scenario B:" in content, "Missing '## Scenario B:' in scenarios.md"
    assert "## Scenario C:" in content, "Missing '## Scenario C:' in scenarios.md"
    print(" -> PASSED: reports/scenarios.md exists and contains all three scenario headings.")

    print("\n" + "=" * 80)
    print("ALL SCENARIO TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

