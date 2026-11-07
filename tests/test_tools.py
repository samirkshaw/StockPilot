"""
Test and Verification Suite for StockPilot Agent Tools.

Verifies the deterministic behavior of:
1. inventory_lookup
2. sales_analysis
3. supplier_comparison
4. reorder_calculation

Performs automated assertions against planted scenarios and prints:
- Supplier catalog table across all 10 products
- Reorder calculation summary using fastest supplier lead time per product
"""

import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.inventory_lookup import inventory_lookup, list_products
from tools.sales_analysis import analyze_sales
from tools.supplier_comparison import compare_suppliers
from tools.reorder_calculation import calculate_reorder


def run_tests():
    print("=" * 80)
    print("STARTING DETERMINISTIC TOOLS VERIFICATION")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Check 1: P001 scenario (lead_time_days = 5)
    # Expected: demand during lead time ~ 50, shortfall ~ 35, risk_level = Critical
    # --------------------------------------------------------------------------
    print("\n[Test 1] Verifying P001 scenario with lead_time_days = 5...")
    r_p001 = calculate_reorder("P001", lead_time_days=5, coverage_days=14)
    assert "error" not in r_p001, f"Unexpected error for P001: {r_p001}"

    dlt = r_p001["demand_during_lead_time"]
    shortfall = r_p001["shortfall_before_arrival"]
    risk = r_p001["risk_level"]

    print(f" -> P001 Demand during lead time: {dlt:.2f} (expected ~50)")
    print(f" -> P001 Shortfall before arrival: {shortfall:.2f} (expected ~35)")
    print(f" -> P001 Risk level: {risk} (expected Critical)")

    assert 45.0 <= dlt <= 55.0, f"P001 demand during lead time ({dlt}) out of expected bounds ~50"
    assert 30.0 <= shortfall <= 40.0, f"P001 shortfall ({shortfall}) out of expected bounds ~35"
    assert risk == "Critical", f"P001 risk_level ({risk}) should be 'Critical'"
    print(" -> PASSED: P001 correctly flagged as Critical with expected shortfall.")

    # --------------------------------------------------------------------------
    # Check 2: P003 demand spike scenario
    # Expected: spike_detected is True, recommended_demand is close to 15 (not 8.58)
    # --------------------------------------------------------------------------
    print("\n[Test 2] Verifying P003 demand spike detection...")
    s_p003 = analyze_sales("P003")
    assert "error" not in s_p003, f"Unexpected error for P003: {s_p003}"

    spike = s_p003["spike_detected"]
    rec_demand = s_p003["recommended_demand"]
    demand_180d = s_p003["avg_daily_demand_180d"]
    trend = s_p003["trend_ratio"]

    print(f" -> P003 Trend ratio: {trend:.2f}")
    print(f" -> P003 Spike detected: {spike} (expected True)")
    print(f" -> P003 Recommended demand: {rec_demand:.2f} (expected ~15.0, not {demand_180d:.2f})")

    assert spike is True, f"P003 spike_detected should be True, got {spike}"
    assert 13.5 <= rec_demand <= 16.5, f"P003 recommended_demand ({rec_demand}) should be ~15.0"
    assert rec_demand != demand_180d, "P003 should use responsive spike demand, not 180-day baseline"
    print(" -> PASSED: P003 spike correctly detected and responsive demand used.")

    # --------------------------------------------------------------------------
    # Check 3: P004 zero stock scenario
    # Expected: risk_level is Critical
    # --------------------------------------------------------------------------
    print("\n[Test 3] Verifying P004 zero stock scenario...")
    r_p004 = calculate_reorder("P004", lead_time_days=3)
    assert "error" not in r_p004, f"Unexpected error for P004: {r_p004}"

    risk_p004 = r_p004["risk_level"]
    stock_p004 = r_p004["inputs"]["current_stock"]
    print(f" -> P004 Current stock: {stock_p004}")
    print(f" -> P004 Risk level: {risk_p004} (expected Critical)")

    assert stock_p004 == 0, f"P004 stock should be 0, got {stock_p004}"
    assert risk_p004 == "Critical", f"P004 risk_level should be 'Critical', got {risk_p004}"
    print(" -> PASSED: P004 zero stock correctly identified as Critical.")

    # --------------------------------------------------------------------------
    # Check 4: P002 (healthy) and P005 (overstocked slow mover) scenarios
    # Expected: risk_level is Low
    # --------------------------------------------------------------------------
    print("\n[Test 4] Verifying P002 and P005 low risk scenarios...")
    # P002 with fastest supplier lead time (7 days)
    r_p002 = calculate_reorder("P002", lead_time_days=7)
    assert "error" not in r_p002, f"Unexpected error for P002: {r_p002}"
    print(f" -> P002 Days of cover: {r_p002['days_of_cover']} days | Risk level: {r_p002['risk_level']} (expected Low)")
    assert r_p002["risk_level"] == "Low", f"P002 risk_level should be 'Low', got {r_p002['risk_level']}"

    # P005 with fastest supplier lead time (6 days)
    r_p005 = calculate_reorder("P005", lead_time_days=6)
    assert "error" not in r_p005, f"Unexpected error for P005: {r_p005}"
    print(f" -> P005 Days of cover: {r_p005['days_of_cover']} days | Risk level: {r_p005['risk_level']} (expected Low)")
    assert r_p005["risk_level"] == "Low", f"P005 risk_level should be 'Low', got {r_p005['risk_level']}"
    print(" -> PASSED: Both P002 and P005 confirmed as Low risk.")

    # --------------------------------------------------------------------------
    # Check 5: Unknown product ID error handling
    # Expected: Returns {"error": "..."} without crashing
    # --------------------------------------------------------------------------
    print("\n[Test 5] Verifying error handling for unknown product ID...")
    unknown_id = "UNKNOWN_PRODUCT_999"
    err_inv = inventory_lookup(unknown_id)
    err_sales = analyze_sales(unknown_id)
    err_sup = compare_suppliers(unknown_id, required_qty=10)
    err_reorder = calculate_reorder(unknown_id, lead_time_days=5)

    assert "error" in err_inv, f"inventory_lookup should return error for unknown ID, got {err_inv}"
    assert "error" in err_sales, f"analyze_sales should return error for unknown ID, got {err_sales}"
    assert "error" in err_sup, f"compare_suppliers should return error for unknown ID, got {err_sup}"
    assert "error" in err_reorder, f"calculate_reorder should return error for unknown ID, got {err_reorder}"
    print(" -> PASSED: All 4 tools gracefully returned error dicts for unknown product ID.")

    # --------------------------------------------------------------------------
    # Check 6: compare_suppliers for P001
    # Expected: At least 2 suppliers, cheapest_supplier_id and fastest_supplier_id
    # --------------------------------------------------------------------------
    print("\n[Test 6] Verifying compare_suppliers for P001...")
    comp_p001 = compare_suppliers("P001", required_qty=35)
    assert "error" not in comp_p001, f"Unexpected error for P001: {comp_p001}"
    suppliers_p001 = comp_p001["suppliers"]
    cheapest_id = comp_p001["cheapest_supplier_id"]
    fastest_id = comp_p001["fastest_supplier_id"]

    print(f" -> P001 Supplier count: {len(suppliers_p001)} (expected >= 2)")
    print(f" -> P001 Cheapest supplier: {cheapest_id}")
    print(f" -> P001 Fastest supplier: {fastest_id}")

    assert len(suppliers_p001) >= 2, f"P001 must have >= 2 suppliers, found {len(suppliers_p001)}"
    assert cheapest_id is not None and isinstance(cheapest_id, str), "cheapest_supplier_id must be populated"
    assert fastest_id is not None and isinstance(fastest_id, str), "fastest_supplier_id must be populated"
    print(" -> PASSED: compare_suppliers returned valid suppliers, cheapest, and fastest IDs.")

    # --------------------------------------------------------------------------
    # Print 1: Full Supplier Table for all 10 products
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FULL SUPPLIER CATALOG ACROSS ALL PRODUCTS")
    print("=" * 80)
    print(f"{'Product ID':<12} {'Supplier ID':<14} {'Unit Cost ($)':<15} {'Lead Time (Days)':<18} {'Min Order Qty':<14}")
    print("-" * 80)

    products = list_products()
    fastest_leads = {}

    for prod in products:
        pid = prod["product_id"]
        comp = compare_suppliers(pid, required_qty=1)
        fastest_supplier_id = comp["fastest_supplier_id"]

        for s in comp["suppliers"]:
            if s["supplier_id"] == fastest_supplier_id:
                fastest_leads[pid] = s["lead_time_days"]
            print(f"{pid:<12} {s['supplier_id']:<14} {s['unit_cost']:<15.2f} {s['lead_time_days']:<18} {s['min_order_qty']:<14}")

    # --------------------------------------------------------------------------
    # Print 2: Reorder Calculation using Fastest Supplier Lead Time per product
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("REORDER CALCULATION SUMMARY (Using Fastest Supplier Lead Time)")
    print("=" * 80)
    print(f"{'Product ID':<12} {'Fastest Lead':<14} {'Days of Cover':<16} {'Risk Level':<14} {'Recommended Order Qty':<22}")
    print("-" * 80)

    for prod in products:
        pid = prod["product_id"]
        fast_lead = fastest_leads.get(pid, 5)
        reorder_info = calculate_reorder(pid, lead_time_days=fast_lead, coverage_days=14)

        days_cover = reorder_info["days_of_cover"]
        risk_lvl = reorder_info["risk_level"]
        rec_qty = reorder_info["recommended_order_qty"]

        print(f"{pid:<12} {fast_lead:<14} {days_cover:<16.2f} {risk_lvl:<14} {rec_qty:<22}")

    print("=" * 80)
    print("ALL ASSERTIONS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

