"""
Test Suite for ScenarioLab: What-If Supply Chain Simulator (Step 7).

Verifies:
1. Execution of all three disruption scenarios (Demand Surge, Supplier Delay, Inventory Reduction).
2. Baseline procurement plan remains strictly unchanged before and after scenarios.
3. Demand surge increases or maintains required procurement quantity.
4. Inventory reduction does not increase available stock.
5. Supplier delay does not reduce lead times.
6. Portfolio-level metrics are internally consistent with product-level results.
7. Unknown scenario names return a clear error dict.
8. All outputs are strictly JSON-serializable.
9. Controlled expected values derived from test fixtures.
"""

import json
import math
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.procurement_planner import build_procurement_plan
from tools.scenario_lab import run_scenario, list_supported_scenarios


def run_tests():
    print("=" * 80)
    print("STARTING SCENARIOLAB VERIFICATION TESTS (Step 7)")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Check 1: Execution of all three scenarios & supported aliases
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying execution of all three scenarios and aliases...")
    res_surge = run_scenario("demand_surge")
    res_delay = run_scenario("supplier_delay")
    res_reduction = run_scenario("inventory_reduction")

    assert isinstance(res_surge, dict) and "error" not in res_surge, f"Demand surge failed: {res_surge.get('error')}"
    assert isinstance(res_delay, dict) and "error" not in res_delay, f"Supplier delay failed: {res_delay.get('error')}"
    assert isinstance(res_reduction, dict) and "error" not in res_reduction, f"Inventory reduction failed: {res_reduction.get('error')}"

    # Verify aliases
    res_alias_a = run_scenario("scenario_a")
    res_alias_b = run_scenario("Scenario B")
    res_alias_c = run_scenario("INVENTORY-REDUCTION")
    assert res_alias_a["scenario_name"] == "demand_surge"
    assert res_alias_b["scenario_name"] == "supplier_delay"
    assert res_alias_c["scenario_name"] == "inventory_reduction"

    # Verify catalog list
    catalog = list_supported_scenarios()
    assert len(catalog) == 3
    print(" -> PASSED: All three scenarios and aliases execute cleanly without error.")

    # --------------------------------------------------------------------------
    # Check 2: Baseline remains strictly unchanged
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying baseline procurement plan remains strictly unchanged...")
    fresh_baseline = build_procurement_plan()
    expected_cost = fresh_baseline["strategies"]["recommended"]["totals"]["total_cost"]
    expected_short = fresh_baseline["strategies"]["recommended"]["totals"]["total_units_short"]
    expected_rev_risk = fresh_baseline["strategies"]["recommended"]["totals"]["total_revenue_at_risk"]

    for name, res in [("Demand Surge", res_surge), ("Supplier Delay", res_delay), ("Inventory Reduction", res_reduction)]:
        base_m = res["baseline"]
        assert base_m["total_cost"] == expected_cost, f"{name}: Baseline cost altered ({base_m['total_cost']} vs {expected_cost})"
        assert base_m["total_shortage_qty"] == expected_short, f"{name}: Baseline shortage altered"
        assert base_m["total_revenue_at_risk"] == expected_rev_risk, f"{name}: Baseline rev at risk altered"

    # Re-verify build_procurement_plan() after all scenario executions
    post_plan = build_procurement_plan()
    assert post_plan["strategies"]["recommended"]["totals"]["total_cost"] == expected_cost
    print(f" -> Baseline Total Cost : ${expected_cost:,.2f}")
    print(f" -> Baseline Shortage   : {expected_short:.2f} units")
    print(" -> PASSED: Baseline data and plan outputs remain 100% immutable.")

    # --------------------------------------------------------------------------
    # Check 3: Demand surge increases or maintains required quantity
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying demand surge (+30%) impacts required quantities...")
    assert res_surge["parameters"]["demand_multiplier"] == 1.3
    increased_count = 0

    for p in res_surge["product_comparison"]:
        pid = p["product_id"]
        base_req = p["baseline_required_qty"]
        sim_req = p["simulated_required_qty"]
        base_demand = p["baseline_daily_demand"]
        sim_demand = p["simulated_daily_demand"]

        # Scaled demand
        expected_demand = round(base_demand * 1.3, 2)
        assert sim_demand == expected_demand, f"{pid}: Expected demand {expected_demand}, got {sim_demand}"

        # Required quantity must be >= baseline
        assert sim_req >= base_req, f"{pid}: sim_req ({sim_req}) < base_req ({base_req})"
        if base_req > 0:
            assert sim_req > base_req, f"{pid}: Expected strictly higher required quantity when ordering"
            increased_count += 1

    assert increased_count == 8, f"Expected 8 products to increase required quantity, got {increased_count}"
    assert res_surge["absolute_change"]["total_cost"] > 0, "Procurement cost must increase under demand surge"
    print(f" -> Demand Surge Total Cost Change : +${res_surge['absolute_change']['total_cost']:,.2f}")
    print(f" -> Products Needing More Stock     : {increased_count} / 10")
    print(" -> PASSED: Demand surge monotonically increases or maintains required order quantities.")

    # --------------------------------------------------------------------------
    # Check 4: Inventory reduction does not increase available stock
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying inventory reduction (-20%) impacts on-hand stock...")
    assert res_reduction["parameters"]["inventory_multiplier"] == 0.8

    for p in res_reduction["product_comparison"]:
        pid = p["product_id"]
        base_stock = p["baseline_stock"]
        sim_stock = p["simulated_stock"]

        # Stock must never increase
        assert sim_stock <= base_stock, f"{pid}: sim_stock ({sim_stock}) > base_stock ({base_stock})"
        expected_stock = int(round(base_stock * 0.8))
        assert sim_stock == expected_stock, f"{pid}: Expected {expected_stock}, got {sim_stock}"

        # If stock was positive, simulated stock must be strictly lower
        if base_stock > 0:
            assert sim_stock < base_stock, f"{pid}: Expected strictly reduced stock"

    assert res_reduction["absolute_change"]["total_cost"] > 0, "Inventory reduction must increase required purchase cost"
    print(f" -> Inventory Reduction Cost Change : +${res_reduction['absolute_change']['total_cost']:,.2f}")
    print(" -> PASSED: Inventory reduction never increases available stock.")

    # --------------------------------------------------------------------------
    # Check 5: Supplier delay does not reduce lead times
    # --------------------------------------------------------------------------
    print("\n[Check 5] Verifying supplier delay (+5 days) on transit duration...")
    assert res_delay["parameters"]["delay_days"] == 5

    for p in res_delay["product_comparison"]:
        pid = p["product_id"]
        base_lt = p["baseline_lead_time_days"]
        sim_lt = p["simulated_lead_time_days"]

        # For the supplier chosen in baseline, its lead time under delay must increase by 5 days
        base_sup_id = p["baseline_chosen_supplier"]
        if base_sup_id:
            matching_sups = [s for s in p.get("supplier_options", []) if s["supplier_id"] == base_sup_id]
            if matching_sups:
                assert matching_sups[0]["lead_time_days"] == matching_sups[0]["base_lead_time_days"] + 5
                assert matching_sups[0]["lead_time_days"] > matching_sups[0]["base_lead_time_days"]

        # Check all supplier options for this product
        for sup_opt in p.get("supplier_options", []):
            b_lt = sup_opt["base_lead_time_days"]
            s_lt = sup_opt["lead_time_days"]
            assert s_lt == b_lt + 5, f"{pid}/{sup_opt['supplier_id']}: Expected lt {b_lt + 5}, got {s_lt}"

    assert res_delay["absolute_change"]["total_shortage_qty"] > 0, "5-day delay must increase shortage"
    print(f" -> Disrupted Shortage Increase : +{res_delay['absolute_change']['total_shortage_qty']:.2f} units")
    print(f" -> Disrupted Rev at Risk       : +${res_delay['absolute_change']['total_revenue_at_risk']:,.2f}")
    print(" -> PASSED: Supplier delay increases all transit durations by exactly 5 days.")

    # --------------------------------------------------------------------------
    # Check 6: Portfolio metrics internally consistent with product-level details
    # --------------------------------------------------------------------------
    print("\n[Check 6] Verifying internal consistency between portfolio and product items...")
    for s_name, res in [("Surge", res_surge), ("Delay", res_delay), ("Reduction", res_reduction)]:
        prods = res["product_comparison"]
        sim_portfolio = res["simulated"]
        diff_portfolio = res["absolute_change"]
        base_portfolio = res["baseline"]

        # Sum of simulated product metrics
        sum_sim_cost = round(sum(p["simulated_cost"] for p in prods), 2)
        sum_sim_shortfall = round(sum(p["simulated_shortfall"] for p in prods), 2)
        sum_sim_rev_risk = round(sum(p["simulated_revenue_at_risk"] for p in prods), 2)

        assert sim_portfolio["total_cost"] == sum_sim_cost, f"{s_name}: Cost mismatch ({sim_portfolio['total_cost']} vs {sum_sim_cost})"
        assert sim_portfolio["total_shortage_qty"] == sum_sim_shortfall, f"{s_name}: Shortage mismatch"
        assert math.isclose(sim_portfolio["total_revenue_at_risk"], sum_sim_rev_risk, abs_tol=0.05), (
            f"{s_name}: Revenue at risk mismatch ({sim_portfolio['total_revenue_at_risk']} vs {sum_sim_rev_risk})"
        )

        # Difference consistency
        expected_cost_diff = round(sim_portfolio["total_cost"] - base_portfolio["total_cost"], 2)
        assert diff_portfolio["total_cost"] == expected_cost_diff, f"{s_name}: Cost diff mismatch"

        expected_short_diff = round(sim_portfolio["total_shortage_qty"] - base_portfolio["total_shortage_qty"], 2)
        assert diff_portfolio["total_shortage_qty"] == expected_short_diff, f"{s_name}: Shortage diff mismatch"

    print(" -> PASSED: All portfolio totals strictly match bottom-up sum of product lines.")

    # --------------------------------------------------------------------------
    # Check 7: Unknown scenario handling
    # --------------------------------------------------------------------------
    print("\n[Check 7] Verifying error handling for unknown scenario names...")
    err_res = run_scenario("freight_strike_at_sea")
    assert isinstance(err_res, dict)
    assert "error" in err_res, "Expected 'error' key for unknown scenario"
    assert "Unknown scenario" in err_res["error"]
    assert "demand_surge" in err_res["error"]

    bad_type = run_scenario(12345)  # type: ignore
    assert isinstance(bad_type, dict) and "error" in bad_type
    print(f" -> Handled unknown name safely : {err_res['error']}")
    print(" -> PASSED: Unknown scenario names return clean error dict.")

    # --------------------------------------------------------------------------
    # Check 8: JSON serializability of all outputs
    # --------------------------------------------------------------------------
    print("\n[Check 8] Verifying JSON serializability across all scenario outputs...")
    for s_name, res in [("Surge", res_surge), ("Delay", res_delay), ("Reduction", res_reduction), ("Error", err_res)]:
        encoded = json.dumps(res)
        assert len(encoded) > 0
        decoded = json.loads(encoded)
        assert isinstance(decoded, dict)

    print(" -> PASSED: All scenario outputs serialize cleanly with zero NumPy/unsupported types.")

    # --------------------------------------------------------------------------
    # Check 9: Custom parameter overrides (surge_pct, delay_days)
    # --------------------------------------------------------------------------
    print("\n[Check 9] Verifying custom parameter overrides (surge_pct=50, delay_days=10)...")
    custom_surge = run_scenario("demand_surge", surge_pct=50.0)
    assert custom_surge["parameters"]["surge_pct"] == 50.0
    assert custom_surge["parameters"]["demand_multiplier"] == 1.50
    # Higher surge should produce higher procurement cost than default 30% surge
    assert custom_surge["simulated"]["total_cost"] > res_surge["simulated"]["total_cost"]
    # Assert actual simulated demand is baseline forecast x 1.50 using implementation rounding
    for p in custom_surge["product_comparison"]:
        expected_demand = round(p["baseline_daily_demand"] * 1.50, 2)
        assert p["simulated_daily_demand"] == expected_demand, (
            f"Product {p['product_id']}: expected simulated demand {expected_demand}, got {p['simulated_daily_demand']}"
        )

    custom_delay = run_scenario("supplier_delay", delay_days=10)
    assert custom_delay["parameters"]["delay_days"] == 10
    # Longer delay should produce higher total shortage than default 5-day delay
    assert custom_delay["simulated"]["total_shortage_qty"] > res_delay["simulated"]["total_shortage_qty"]
    # Assert every supplier offer's simulated lead time equals its baseline lead time + 10
    for p in custom_delay["product_comparison"]:
        for s in p["supplier_options"]:
            assert s["lead_time_days"] == s["base_lead_time_days"] + 10, (
                f"Product {p['product_id']}, supplier {s['supplier_id']}: expected lead time {s['base_lead_time_days'] + 10}, got {s['lead_time_days']}"
            )

    # Confirm default scenarios remain completely unchanged
    res_surge_default_again = run_scenario("demand_surge")
    assert res_surge_default_again["parameters"]["surge_pct"] == 30.0
    assert res_surge_default_again["simulated"]["total_cost"] == res_surge["simulated"]["total_cost"]

    res_delay_default_again = run_scenario("supplier_delay")
    assert res_delay_default_again["parameters"]["delay_days"] == 5
    assert res_delay_default_again["simulated"]["total_shortage_qty"] == res_delay["simulated"]["total_shortage_qty"]

    print(" -> PASSED: Custom parameter overrides behave monotonically and default behavior is preserved.")

    print("\n" + "=" * 80)
    print("ALL SCENARIOLAB UNIT TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
