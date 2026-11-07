"""
Unit tests for tools/demand_impact.py (Step 6b).

Verifies demand impact analysis:
- P003 demand spike metrics, order quantities, and days of cover relationships.
- P002 low-risk / no-spike metrics.
- Unknown product ID error handling.
- JSON serializability of all outputs.
"""

import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.demand_impact import get_demand_impact


def run_tests():
    print("=" * 80)
    print("STARTING DEMAND IMPACT UNIT TESTS (Step 6b)")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Check 1: P003 Demand Spike Scenario
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying P003 demand spike analysis...")
    res_p003 = get_demand_impact("P003")

    assert isinstance(res_p003, dict), f"Expected dict, got {type(res_p003)}"
    assert "error" not in res_p003, f"Unexpected error in P003 impact: {res_p003.get('error')}"

    # spike_detected is True
    assert res_p003["spike_detected"] is True, f"Expected spike_detected True, got {res_p003['spike_detected']}"

    # qty_in_plan > qty_if_180d_average
    qty_plan = res_p003["qty_in_plan"]
    qty_naive = res_p003["qty_if_180d_average"]
    assert qty_plan > qty_naive, f"Expected qty_in_plan ({qty_plan}) > qty_if_180d_average ({qty_naive})"

    # qty_difference equals subtraction
    diff = res_p003["qty_difference"]
    assert diff == qty_plan - qty_naive, f"Expected diff {qty_plan - qty_naive}, got {diff}"

    # days_of_cover_at_forecast > days_of_cover_at_14d_avg and < days_of_cover_at_180d_avg
    doc_fc = res_p003["days_of_cover_at_forecast"]
    doc_14d = res_p003["days_of_cover_at_14d_avg"]
    doc_180d = res_p003["days_of_cover_at_180d_avg"]

    assert doc_fc > doc_14d, f"Expected doc_forecast ({doc_fc}) > doc_14d ({doc_14d})"
    assert doc_fc < doc_180d, f"Expected doc_forecast ({doc_fc}) < doc_180d ({doc_180d})"

    print(f" -> P003 spike_detected       : {res_p003['spike_detected']}")
    print(f" -> P003 qty_in_plan          : {qty_plan} units")
    print(f" -> P003 qty_if_180d_average  : {qty_naive} units (difference: +{diff})")
    print(f" -> P003 cover: 14d={doc_14d}d < forecast={doc_fc}d < 180d={doc_180d}d")
    print(" -> PASSED: P003 spike and order quantity assertions verified.")

    # --------------------------------------------------------------------------
    # Check 2: P002 Normal Scenario (no spike)
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying P002 non-spike scenario...")
    res_p002 = get_demand_impact("P002")

    assert isinstance(res_p002, dict), f"Expected dict, got {type(res_p002)}"
    assert "error" not in res_p002, f"Unexpected error in P002 impact: {res_p002.get('error')}"
    assert res_p002["spike_detected"] is False, f"Expected spike_detected False for P002, got {res_p002['spike_detected']}"

    print(f" -> P002 spike_detected       : {res_p002['spike_detected']}")
    print(f" -> P002 qty_in_plan          : {res_p002['qty_in_plan']}")
    print(" -> PASSED: P002 non-spike verified.")

    # --------------------------------------------------------------------------
    # Check 3: Unknown product ID error handling
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying unknown product ID error handling...")
    res_unknown = get_demand_impact("P999")
    assert isinstance(res_unknown, dict)
    assert "error" in res_unknown, f"Expected error key for unknown product, got {res_unknown}"
    print(f" -> Unknown ID error response : {res_unknown['error']}")
    print(" -> PASSED: Unknown product ID cleanly handled.")

    # --------------------------------------------------------------------------
    # Check 4: JSON serializability
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying JSON serialization of outputs...")
    json_str_p003 = json.dumps(res_p003)
    json_str_p002 = json.dumps(res_p002)
    json_str_unknown = json.dumps(res_unknown)
    assert len(json_str_p003) > 0 and len(json_str_p002) > 0 and len(json_str_unknown) > 0
    print(" -> PASSED: All outputs are strictly JSON-serializable.")

    print("\n" + "=" * 80)
    print("ALL DEMAND IMPACT UNIT TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

