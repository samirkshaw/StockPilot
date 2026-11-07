"""
Deterministic Procurement Planner for StockPilot.

Builds a comprehensive inventory procurement plan by:
- Using forecast_demand as the single source of daily demand
- Computing a fixed planning-horizon required quantity per product (independent of supplier lead time)
- Evaluating all suppliers per product for order quantities (respecting MOQ), lead-time shortfall,
  revenue at risk, and total purchasing cost
- Generating two alternative strategies ("Cheapest" vs "Fastest")
- Constructing an optimal "Recommended" plan that prioritizes avoiding stockouts,
  then minimizes cost, complete with traceable reasoning for every decision
"""

import math
import os
from typing import Any, Dict, List
import pandas as pd

from tools.demand_forecast import forecast_demand
from tools.inventory_lookup import inventory_lookup, list_products
from tools.reorder_calculation import calculate_reorder
from tools.supplier_comparison import compare_suppliers


def build_procurement_plan(
    horizon_days: int = 7,
    coverage_days: int = 14,
    planning_horizon_days: int = 30,
) -> Dict[str, Any]:
    """
    Build a deterministic procurement plan across all catalog products.

    Args:
        horizon_days: Forecast horizon in days used by forecast_demand (default: 7).
        coverage_days: Target post-arrival inventory coverage in days (default: 14).
        planning_horizon_days: Fixed replenishment planning horizon in days (default: 30)
                               used to determine order quantities across all suppliers.

    Returns:
        dict: A JSON-serializable dictionary containing:
            - planning_horizon_days: Fixed horizon used (30 days)
            - products: List of all products sorted by urgency (Critical, High, Medium, Low)
            - strategies:
                - cheapest: Orders and portfolio totals prioritizing lowest unit cost
                - fastest: Orders and portfolio totals prioritizing shortest lead time
                - recommended: Orders, traceable reasons, and portfolio totals balancing stockout avoidance and cost
    """
    try:
        raw_products = list_products()
    except Exception as e:
        return {"error": f"Failed to retrieve product list: {str(e)}"}

    if not raw_products:
        return {"error": "No products found in catalog."}

    evaluated_products = []
    products_needing_order = []

    for item in raw_products:
        pid = str(item["product_id"]).strip().upper()
        name = str(item["name"])

        # 1. Single demand source: forecast_demand
        fc_res = forecast_demand(pid, horizon_days=horizon_days)
        if "error" in fc_res:
            return {"error": f"Forecasting failed for {pid}: {fc_res['error']}"}

        daily_demand = float(fc_res["avg_daily_forecast"])

        # 2. Inventory lookup
        inv_res = inventory_lookup(pid)
        if "error" in inv_res:
            return {"error": f"Inventory lookup failed for {pid}: {inv_res['error']}"}

        current_stock = int(inv_res["current_stock"])
        category = str(inv_res["category"])
        unit_price = float(inv_res["unit_price"])

        # Calculate days of cover
        if current_stock == 0 or daily_demand <= 0:
            days_of_cover = 0.0
        else:
            days_of_cover = round(current_stock / daily_demand, 2)

        # 3. Fixed required quantity across planning horizon, independent of supplier
        required_qty = int(math.ceil(max(0.0, daily_demand * planning_horizon_days - current_stock)))
        action = "No order needed" if required_qty == 0 else "Order needed"

        # 4. Retrieve supplier catalog for product
        comp_zero = compare_suppliers(pid, required_qty=0)
        if "error" in comp_zero:
            return {"error": f"Supplier lookup failed for {pid}: {comp_zero['error']}"}

        supplier_catalog = comp_zero["suppliers"]

        # 5. Evaluate each supplier option
        supplier_evals = []

        if action == "Order needed":
            for sup in supplier_catalog:
                sup_id = str(sup["supplier_id"])
                sup_name = str(sup["supplier_name"])
                unit_cost = float(sup["unit_cost"])
                lead_time = int(sup["lead_time_days"])
                moq = int(sup["min_order_qty"])

                # Order quantity respects supplier MOQ
                order_qty = int(max(required_qty, moq))
                total_cost = round(order_qty * unit_cost, 2)

                # Risk level and buffer deficit from calculate_reorder
                reorder_info = calculate_reorder(
                    product_id=pid,
                    lead_time_days=lead_time,
                    coverage_days=coverage_days,
                    daily_demand_override=daily_demand,
                )
                shortfall = float(round(max(0.0, daily_demand * lead_time - current_stock), 2))
                uncovered_days = float(reorder_info["days_uncovered_before_arrival"])
                risk_level = str(reorder_info["risk_level"])

                # Revenue at risk = shortfall_before_arrival * unit_price (reported only, not in total_cost)
                revenue_at_risk = round(shortfall * unit_price, 2)

                supplier_evals.append({
                    "product_id": pid,
                    "product_name": name,
                    "supplier_id": sup_id,
                    "supplier_name": sup_name,
                    "unit_cost": unit_cost,
                    "lead_time_days": lead_time,
                    "min_order_qty": moq,
                    "required_qty": required_qty,
                    "order_qty": order_qty,
                    "total_cost": total_cost,
                    "shortfall_before_arrival": shortfall,
                    "days_uncovered_before_arrival": uncovered_days,
                    "revenue_at_risk": revenue_at_risk,
                    "risk_level": risk_level,
                })

        # Determine overall product risk level for urgency ranking
        if action == "No order needed":
            overall_risk = "Low"
        else:
            fastest_sup_eval = min(supplier_evals, key=lambda s: s["lead_time_days"])
            overall_risk = fastest_sup_eval["risk_level"]

        product_record = {
            "product_id": pid,
            "name": name,
            "category": category,
            "unit_price": unit_price,
            "current_stock": current_stock,
            "daily_demand": daily_demand,
            "days_of_cover": days_of_cover,
            "required_qty": required_qty,
            "action": action,
            "risk_level": overall_risk,
            "supplier_options": supplier_evals,
        }
        evaluated_products.append(product_record)

        if action == "Order needed":
            products_needing_order.append(product_record)

    # Sort all products by urgency: Critical, High, Medium, Low; then days_of_cover ascending
    urgency_weights = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    evaluated_products.sort(
        key=lambda p: (urgency_weights.get(p["risk_level"], 99), p["days_of_cover"], p["product_id"])
    )

    # -------------------------------------------------------------------------
    # Helper to calculate portfolio totals
    # -------------------------------------------------------------------------
    def _compute_totals(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not orders:
            return {
                "total_cost": 0.0,
                "average_lead_time": 0.0,
                "total_units_short": 0.0,
                "total_revenue_at_risk": 0.0,
                "revenue_at_risk": 0.0,
                "critical_or_high_count": 0,
            }
        tot_cost = round(sum(o["total_cost"] for o in orders), 2)
        avg_lead = round(sum(o["lead_time_days"] for o in orders) / len(orders), 2)
        tot_short = round(sum(o["shortfall_before_arrival"] for o in orders), 2)
        tot_rev_risk = round(sum(o["revenue_at_risk"] for o in orders), 2)
        crit_high = sum(1 for o in orders if o["risk_level"] in ("Critical", "High"))
        return {
            "total_cost": tot_cost,
            "average_lead_time": avg_lead,
            "total_units_short": tot_short,
            "total_revenue_at_risk": tot_rev_risk,
            "revenue_at_risk": tot_rev_risk,
            "critical_or_high_count": crit_high,
        }

    # -------------------------------------------------------------------------
    # Strategy 1: "Cheapest" (lowest unit_cost per product)
    # -------------------------------------------------------------------------
    cheapest_orders = []
    for prod in products_needing_order:
        best_cheap = min(prod["supplier_options"], key=lambda s: (s["unit_cost"], s["lead_time_days"]))
        cheapest_orders.append({
            "product_id": prod["product_id"],
            "supplier_id": best_cheap["supplier_id"],
            "supplier_name": best_cheap["supplier_name"],
            "required_qty": best_cheap["required_qty"],
            "order_qty": best_cheap["order_qty"],
            "unit_cost": best_cheap["unit_cost"],
            "total_cost": best_cheap["total_cost"],
            "lead_time_days": best_cheap["lead_time_days"],
            "shortfall_before_arrival": best_cheap["shortfall_before_arrival"],
            "days_uncovered_before_arrival": best_cheap["days_uncovered_before_arrival"],
            "revenue_at_risk": best_cheap["revenue_at_risk"],
            "risk_level": best_cheap["risk_level"],
        })
    cheapest_totals = _compute_totals(cheapest_orders)

    # -------------------------------------------------------------------------
    # Strategy 2: "Fastest" (lowest lead_time_days per product)
    # -------------------------------------------------------------------------
    fastest_orders = []
    for prod in products_needing_order:
        best_fast = min(prod["supplier_options"], key=lambda s: (s["lead_time_days"], s["unit_cost"]))
        fastest_orders.append({
            "product_id": prod["product_id"],
            "supplier_id": best_fast["supplier_id"],
            "supplier_name": best_fast["supplier_name"],
            "required_qty": best_fast["required_qty"],
            "order_qty": best_fast["order_qty"],
            "unit_cost": best_fast["unit_cost"],
            "total_cost": best_fast["total_cost"],
            "lead_time_days": best_fast["lead_time_days"],
            "shortfall_before_arrival": best_fast["shortfall_before_arrival"],
            "days_uncovered_before_arrival": best_fast["days_uncovered_before_arrival"],
            "revenue_at_risk": best_fast["revenue_at_risk"],
            "risk_level": best_fast["risk_level"],
        })
    fastest_totals = _compute_totals(fastest_orders)

    # -------------------------------------------------------------------------
    # Recommended Plan (Deterministic Rule)
    # 1. If any supplier gives shortfall_before_arrival == 0:
    #    pick the one with lowest total_cost among those.
    # 2. Otherwise, pick the supplier with smallest shortfall_before_arrival,
    #    ties broken by lowest total_cost.
    # -------------------------------------------------------------------------
    recommended_orders = []
    for prod in products_needing_order:
        sups = prod["supplier_options"]
        zero_shortfall_sups = [s for s in sups if s["shortfall_before_arrival"] == 0.0]

        if zero_shortfall_sups:
            chosen = min(zero_shortfall_sups, key=lambda s: (s["total_cost"], s["lead_time_days"]))
            other_had_shortfall = any(s["shortfall_before_arrival"] > 0 for s in sups)
            if other_had_shortfall:
                reason = (
                    f"{chosen['supplier_id']} chosen: covers demand without stockout "
                    f"(lead time {chosen['lead_time_days']}d) at lowest cost (${chosen['total_cost']:,.2f})."
                )
            else:
                reason = (
                    f"{chosen['supplier_id']} chosen: lowest cost option (${chosen['total_cost']:,.2f}) "
                    f"with zero stockout risk (lead time {chosen['lead_time_days']}d)."
                )
        else:
            chosen = min(sups, key=lambda s: (s["shortfall_before_arrival"], s["total_cost"], s["lead_time_days"]))
            reason = (
                f"No supplier avoids a stockout; {chosen['supplier_id']} minimises the gap "
                f"with {chosen['shortfall_before_arrival']:.2f} units shortfall "
                f"(lead time {chosen['lead_time_days']}d, cost ${chosen['total_cost']:,.2f})."
            )

        recommended_orders.append({
            "product_id": prod["product_id"],
            "supplier_id": chosen["supplier_id"],
            "supplier_name": chosen["supplier_name"],
            "required_qty": chosen["required_qty"],
            "order_qty": chosen["order_qty"],
            "unit_cost": chosen["unit_cost"],
            "total_cost": chosen["total_cost"],
            "lead_time_days": chosen["lead_time_days"],
            "shortfall_before_arrival": chosen["shortfall_before_arrival"],
            "days_uncovered_before_arrival": chosen["days_uncovered_before_arrival"],
            "revenue_at_risk": chosen["revenue_at_risk"],
            "risk_level": chosen["risk_level"],
            "reason": reason,
        })
    recommended_totals = _compute_totals(recommended_orders)

    return {
        "planning_horizon_days": planning_horizon_days,
        "products": evaluated_products,
        "strategies": {
            "cheapest": {
                "orders": cheapest_orders,
                "totals": cheapest_totals,
            },
            "fastest": {
                "orders": fastest_orders,
                "totals": fastest_totals,
            },
            "recommended": {
                "orders": recommended_orders,
                "totals": recommended_totals,
            },
        },
        "cheapest_strategy": {
            "orders": cheapest_orders,
            "totals": cheapest_totals,
        },
        "fastest_strategy": {
            "orders": fastest_orders,
            "totals": fastest_totals,
        },
        "recommended_plan": {
            "orders": recommended_orders,
            "totals": recommended_totals,
        },
    }
