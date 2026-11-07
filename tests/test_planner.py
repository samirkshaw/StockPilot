"""
Test Suite for Deterministic Procurement Planner (StockPilot Step 4).

Validates:
1. All 10 products exist in the procurement plan.
2. P002 and P005 have action 'No order needed'.
3. P001 and P004 appear with risk 'Critical' under the Cheapest strategy.
4. P001 under the Fastest strategy has days_uncovered_before_arrival > 0,
   and its recommended reason states that no supplier avoids a stockout.
5. Every recommended/cheapest/fastest order quantity respects the supplier's minimum order quantity (MOQ).
6. Recommended plan's total units short <= Cheapest strategy's total units short.
7. Plan is fully JSON-serializable without NumPy type errors.
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
    print("STARTING DETERMINISTIC PROCUREMENT PLANNER VERIFICATION")
    print("=" * 80)

    plan = build_procurement_plan(horizon_days=7, coverage_days=14)
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
    # Check 4: P001 under Fastest strategy has uncovered days > 0 and reason states
    # no supplier avoids a stockout
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying P001 under Fastest strategy & Recommended reasoning...")
    fastest_orders = plan["strategies"]["fastest"]["orders"]
    p001_fast = next((o for o in fastest_orders if o["product_id"] == "P001"), None)
    assert p001_fast is not None, "P001 missing from Fastest orders"
    print(f" -> P001 Fastest lead time: {p001_fast['lead_time_days']} days")
    print(f" -> P001 Days uncovered before arrival: {p001_fast['days_uncovered_before_arrival']} days")
    assert p001_fast["days_uncovered_before_arrival"] > 0, (
        f"Expected P001 days_uncovered_before_arrival > 0, got {p001_fast['days_uncovered_before_arrival']}"
    )

    rec_orders = plan["strategies"]["recommended"]["orders"]
    p001_rec = next((o for o in rec_orders if o["product_id"] == "P001"), None)
    assert p001_rec is not None, "P001 missing from Recommended orders"
    reason = p001_rec["reason"].lower()
    print(f" -> P001 Recommended reason: \"{p001_rec['reason']}\"")
    assert "no supplier avoids a stockout" in reason, (
        f"Expected reason to state that no supplier avoids a stockout, got: {p001_rec['reason']}"
    )
    print(" -> PASSED: P001 has uncovered buffer gap and reason confirms no supplier avoids stockout.")

    # --------------------------------------------------------------------------
    # Check 5: Every order_qty is >= supplier's minimum order quantity (MOQ)
    # --------------------------------------------------------------------------
    print("\n[Check 5] Verifying all order quantities respect supplier MOQ...")
    # Preload supplier MOQs
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
    print(" -> PASSED: All order quantities in all strategies strictly satisfy MOQs.")

    # --------------------------------------------------------------------------
    # Check 6: Recommended plan total_units_short <= Cheapest strategy total_units_short
    # --------------------------------------------------------------------------
    print("\n[Check 6] Verifying Recommended total units short <= Cheapest total units short...")
    rec_short = plan["strategies"]["recommended"]["totals"]["total_units_short"]
    cheap_short = plan["strategies"]["cheapest"]["totals"]["total_units_short"]
    print(f" -> Recommended Total Units Short : {rec_short}")
    print(f" -> Cheapest Total Units Short    : {cheap_short}")
    assert rec_short <= cheap_short, (
        f"Recommended short ({rec_short}) should be <= Cheapest short ({cheap_short})"
    )
    print(" -> PASSED: Recommended plan successfully reduces or matches stockout exposure.")

    # --------------------------------------------------------------------------
    # Check 7: JSON serialization succeeds without NumPy types
    # --------------------------------------------------------------------------
    print("\n[Check 7] Verifying JSON serialization (no NumPy types)...")
    try:
        serialized = json.dumps(plan)
        assert len(serialized) > 0
    except TypeError as e:
        assert False, f"JSON serialization failed with TypeError (likely NumPy type present): {e}"
    print(" -> PASSED: Plan serialized to JSON cleanly with zero type errors.")

    print("\n" + "=" * 80)
    print("ALL PLANNER ASSERTIONS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

