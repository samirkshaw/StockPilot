"""
Test Suite for Deterministic Procurement Planner (StockPilot Step 4b).

Validates:
1. All 10 products exist in the procurement plan.
2. P002 and P005 have action 'No order needed'.
3. P001 and P004 appear with risk 'Critical' under the Cheapest strategy.
4. For each product needing an order, required_qty is identical across all suppliers
   before minimum order quantity (MOQ) is applied.
5. Every order quantity in all strategies respects the supplier's MOQ.
6. Recommended plan's total_cost <= Fastest strategy's total_cost, AND
   recommended plan's total_units_short <= Cheapest strategy's total_units_short.
7. P001 under every supplier still has shortfall > 0 or days_uncovered > 0 for suppliers
   slower than 2 days, and the P001 reason confirms no supplier avoids a stockout.
8. Plan is fully JSON-serializable without NumPy type errors.

Also prints (without assertion):
- List of products where recommended supplier differs from Fastest supplier
- List of products where recommended supplier differs from Cheapest supplier
"""

import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.procurement_planner import build_procurement_plan
from tools.supplier_comparison import compare_suppliers


def run_tests():
    print("=" * 80)
    print("STARTING DETERMINISTIC PROCUREMENT PLANNER VERIFICATION (Step 4b)")
    print("=" * 80)

    plan = build_procurement_plan(horizon_days=7, coverage_days=14, planning_horizon_days=30)
    assert isinstance(plan, dict), f"Plan must be a dict, got {type(plan)}"
    assert "error" not in plan, f"build_procurement_plan returned error: {plan.get('error')}"

    # --------------------------------------------------------------------------
    # Check 1: Plan contains all 10 products
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying all 10 products are included in the plan...")
    products = plan["products"]
    assert len(products) == 10, f"Expected 10 products, found {len(products)}"
    pids = {p["product_id"] for p in products}
    expected_pids = {f"P{i:03d}" for i in range(1, 11)}
    assert pids == expected_pids, f"Mismatch in product IDs: {pids ^ expected_pids}"
    print(f" -> PASSED: Exactly 10 products present ({sorted(pids)}).")

    # --------------------------------------------------------------------------
    # Check 2: P002 and P005 are 'No order needed'
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying P002 and P005 action is 'No order needed'...")
    action_map = {p["product_id"]: p["action"] for p in products}
    assert action_map["P002"] == "No order needed", f"P002 action should be 'No order needed', got {action_map['P002']}"
    assert action_map["P005"] == "No order needed", f"P005 action should be 'No order needed', got {action_map['P005']}"
    print(" -> PASSED: P002 and P005 correctly marked as 'No order needed'.")

    # --------------------------------------------------------------------------
    # Check 3: P001 and P004 appear with risk Critical under Cheapest strategy
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying P001 and P004 risk is 'Critical' under Cheapest strategy...")
    cheapest_orders = plan["strategies"]["cheapest"]["orders"]
    cheap_risk_map = {o["product_id"]: o["risk_level"] for o in cheapest_orders}

    assert "P001" in cheap_risk_map, "P001 missing from Cheapest orders"
    assert "P004" in cheap_risk_map, "P004 missing from Cheapest orders"
    assert cheap_risk_map["P001"] == "Critical", f"P001 risk should be 'Critical', got {cheap_risk_map['P001']}"
    assert cheap_risk_map["P004"] == "Critical", f"P004 risk should be 'Critical', got {cheap_risk_map['P004']}"
    print(" -> PASSED: P001 and P004 both flagged as 'Critical' under Cheapest strategy.")

    # --------------------------------------------------------------------------
    # Check 4: required_qty is identical across all suppliers before MOQ
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying required_qty is identical across all suppliers before MOQ...")
    for prod in products:
        if prod["action"] == "Order needed":
            base_req = prod["required_qty"]
            assert base_req > 0, f"Expected required_qty > 0 for {prod['product_id']}, got {base_req}"
            for sup_eval in prod["supplier_options"]:
                assert sup_eval["required_qty"] == base_req, (
                    f"Product {prod['product_id']} supplier {sup_eval['supplier_id']} required_qty "
                    f"({sup_eval['required_qty']}) does not match product base ({base_req})"
                )
    print(" -> PASSED: For each product needing an order, required_qty is supplier-independent.")

    # --------------------------------------------------------------------------
    # Check 5: Every order_qty is >= supplier's minimum order quantity (MOQ)
    # --------------------------------------------------------------------------
    print("\n[Check 5] Verifying all order quantities respect supplier MOQ...")
    moq_lookup = {}
    for pid in expected_pids:
        c = compare_suppliers(pid, 0)
        for s in c["suppliers"]:
            moq_lookup[(pid, s["supplier_id"])] = s["min_order_qty"]

    for strat_name in ["cheapest", "fastest", "recommended"]:
        orders = plan["strategies"][strat_name]["orders"]
        for o in orders:
            key = (o["product_id"], o["supplier_id"])
            moq = moq_lookup.get(key, 0)
            assert o["order_qty"] >= moq, (
                f"Order qty {o['order_qty']} for {key} in {strat_name} is below MOQ {moq}"
            )
    print(" -> PASSED: All order quantities across all strategies strictly satisfy MOQs.")

    # --------------------------------------------------------------------------
    # Check 6: Recommended total_cost <= Fastest total_cost AND
    #          Recommended total_units_short <= Cheapest total_units_short
    # --------------------------------------------------------------------------
    print("\n[Check 6] Verifying strategy portfolio comparisons...")
    rec_totals = plan["strategies"]["recommended"]["totals"]
    fast_totals = plan["strategies"]["fastest"]["totals"]
    cheap_totals = plan["strategies"]["cheapest"]["totals"]

    print(f" -> Recommended Total Cost  : ${rec_totals['total_cost']:,.2f}")
    print(f" -> Fastest Total Cost      : ${fast_totals['total_cost']:,.2f}")
    print(f" -> Recommended Units Short : {rec_totals['total_units_short']}")
    print(f" -> Cheapest Units Short    : {cheap_totals['total_units_short']}")

    assert rec_totals["total_cost"] <= fast_totals["total_cost"], (
        f"Recommended cost (${rec_totals['total_cost']}) must be <= Fastest cost (${fast_totals['total_cost']})"
    )
    assert rec_totals["total_units_short"] <= cheap_totals["total_units_short"], (
        f"Recommended short ({rec_totals['total_units_short']}) must be <= Cheapest short ({cheap_totals['total_units_short']})"
    )
    print(" -> PASSED: Recommended plan is more cost-effective than Fastest while maintaining low shortfall.")

    # --------------------------------------------------------------------------
    # Check 7: P001 shortfall/uncovered days and reason confirms no supplier avoids stockout
    # --------------------------------------------------------------------------
    print("\n[Check 7] Verifying P001 supplier shortfall and decision reasoning...")
    p001_prod = next(p for p in products if p["product_id"] == "P001")
    for s in p001_prod["supplier_options"]:
        if s["lead_time_days"] > 2:
            assert s["shortfall_before_arrival"] > 0 or s["days_uncovered_before_arrival"] > 0, (
                f"P001 supplier {s['supplier_id']} (lead {s['lead_time_days']}d) should have shortfall or uncovered days"
            )

    rec_orders = plan["strategies"]["recommended"]["orders"]
    p001_rec = next(o for o in rec_orders if o["product_id"] == "P001")
    reason = p001_rec["reason"].lower()
    print(f" -> P001 Recommended reason: \"{p001_rec['reason']}\"")
    assert "no supplier avoids a stockout" in reason, (
        f"Expected reason to state that no supplier avoids a stockout, got: {p001_rec['reason']}"
    )
    print(" -> PASSED: P001 has deficit under slower suppliers and reason confirms no supplier avoids stockout.")

    # --------------------------------------------------------------------------
    # Check 8: JSON serialization succeeds without NumPy types
    # --------------------------------------------------------------------------
    print("\n[Check 8] Verifying JSON serialization (no NumPy types)...")
    try:
        serialized = json.dumps(plan)
        assert len(serialized) > 0
    except TypeError as e:
        assert False, f"JSON serialization failed with TypeError (likely NumPy type present): {e}"
    print(" -> PASSED: Plan serialized to JSON cleanly with zero type errors.")

    # --------------------------------------------------------------------------
    # Check 9: Step 5b thin_buffer_products and unavoidable_stockouts validation
    # --------------------------------------------------------------------------
    print("\n[Check 9] Verifying thin_buffer_products and unavoidable_stockouts (Step 5b)...")
    thin_buffers = plan.get("thin_buffer_products", [])
    unavoidable = plan.get("unavoidable_stockouts", [])

    assert isinstance(thin_buffers, list), "thin_buffer_products must be a list"
    assert isinstance(unavoidable, list), "unavoidable_stockouts must be a list"

    # thin_buffer_products only contains rows with shortfall 0 and risk High/Critical
    for tb in thin_buffers:
        assert tb["risk_level"] in ("High", "Critical"), (
            f"Product {tb['product_id']} in thin_buffer_products has invalid risk: {tb['risk_level']}"
        )

    # unavoidable_stockouts only contains rows with shortfall > 0
    for u in unavoidable:
        assert u["shortfall_before_arrival"] > 0, (
            f"Product {u['product_id']} in unavoidable_stockouts has non-positive shortfall: {u['shortfall_before_arrival']}"
        )

    tb_pids = {tb["product_id"] for tb in thin_buffers}
    un_pids = {u["product_id"] for u in unavoidable}

    # P001 and P004 are in unavoidable_stockouts and NOT in thin_buffer_products
    assert "P001" in un_pids, "P001 must be in unavoidable_stockouts"
    assert "P004" in un_pids, "P004 must be in unavoidable_stockouts"
    assert "P001" not in tb_pids, "P001 must NOT be in thin_buffer_products"
    assert "P004" not in tb_pids, "P004 must NOT be in thin_buffer_products"

    # Confirm json.dumps succeeds with new fields
    json_str = json.dumps(plan)
    assert len(json_str) > 0
    print(" -> PASSED: thin_buffer_products and unavoidable_stockouts strictly validated.")

    # --------------------------------------------------------------------------
    # INFORMATIONAL PRINTS (Do not assert)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("INFORMATIONAL STRATEGY DIVERGENCE (Recommended vs. Fastest / Cheapest)")
    print("=" * 80)

    fast_sup_map = {o["product_id"]: o["supplier_id"] for o in plan["strategies"]["fastest"]["orders"]}
    cheap_sup_map = {o["product_id"]: o["supplier_id"] for o in plan["strategies"]["cheapest"]["orders"]}
    rec_sup_map = {o["product_id"]: o["supplier_id"] for o in plan["strategies"]["recommended"]["orders"]}

    diff_from_fastest = [
        f"{pid}: Rec={rec_sup_map[pid]} vs Fast={fast_sup_map[pid]}"
        for pid in rec_sup_map
        if rec_sup_map[pid] != fast_sup_map[pid]
    ]

    diff_from_cheapest = [
        f"{pid}: Rec={rec_sup_map[pid]} vs Cheap={cheap_sup_map[pid]}"
        for pid in rec_sup_map
        if rec_sup_map[pid] != cheap_sup_map[pid]
    ]

    print(f"Products where Recommended supplier differs from Fastest ({len(diff_from_fastest)}):")
    if diff_from_fastest:
        for item in diff_from_fastest:
            print(f" - {item}")
    else:
        print(" - None (Recommended chose fastest for all ordering products)")

    print(f"\nProducts where Recommended supplier differs from Cheapest ({len(diff_from_cheapest)}):")
    if diff_from_cheapest:
        for item in diff_from_cheapest:
            print(f" - {item}")
    else:
        print(" - None (Recommended chose cheapest for all ordering products)")

    print("\n" + "=" * 80)
    print("ALL PLANNER ASSERTIONS (Step 4b) PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
