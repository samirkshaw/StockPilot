"""
ScenarioLab: What-If Supply Chain Simulator for StockPilot (Step 7).

Deterministic simulation engine enabling users to model supply-chain disruptions
and compare the resulting metrics against the baseline procurement plan:
- Scenario A: Demand Surge (+30% forecast daily demand)
- Scenario B: Supplier Delay (+5 days delivery lead time)
- Scenario C: Inventory Reduction (-20% available on-hand stock)

All simulations reuse existing forecasting, inventory, supplier, and
procurement planning logic without live API calls or data modification.
"""

import math
from typing import Any, Dict, List, Optional

from tools.inventory_lookup import inventory_lookup, list_products
from tools.demand_forecast import forecast_demand
from tools.supplier_comparison import compare_suppliers
from tools.procurement_planner import build_procurement_plan

RISK_RANKS = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


def _classify_risk(current_stock: float, days_of_cover: float, lead_time: float) -> str:
    """Classify inventory urgency risk level based on days of cover vs lead time."""
    if current_stock <= 0 or days_of_cover < lead_time:
        return "Critical"
    elif days_of_cover < 1.5 * lead_time:
        return "High"
    elif days_of_cover < 2.5 * lead_time:
        return "Medium"
    else:
        return "Low"


def simulate_procurement_plan(
    demand_multiplier: float = 1.0,
    lead_time_delay_days: int = 0,
    inventory_multiplier: float = 1.0,
    planning_horizon_days: int = 30,
) -> Dict[str, Any]:
    """
    Simulate a procurement plan under modified demand, lead-time, or inventory assumptions.

    Args:
        demand_multiplier: Factor to scale baseline forecast demand (e.g. 1.30 for +30%).
        lead_time_delay_days: Extra transit days added to all supplier lead times (e.g. 5).
        inventory_multiplier: Factor to scale on-hand inventory (e.g. 0.80 for -20%).
        planning_horizon_days: Replenishment planning horizon in days (default: 30).

    Returns:
        dict: Evaluated products, recommended orders, and portfolio summary totals.
    """
    raw_products = list_products()
    evaluated_products = []
    recommended_orders = []

    for item in raw_products:
        pid = str(item["product_id"]).strip().upper()
        name = str(item["name"])

        # 1. Base demand scaled by multiplier
        fc_res = forecast_demand(pid, horizon_days=7)
        base_demand = float(fc_res["avg_daily_forecast"])
        sim_demand = round(base_demand * demand_multiplier, 2)

        # 2. Base stock scaled by multiplier
        inv_res = inventory_lookup(pid)
        base_stock = int(inv_res["current_stock"])
        sim_stock = int(round(base_stock * inventory_multiplier))
        unit_price = float(inv_res["unit_price"])
        category = str(inv_res["category"])

        # Days of cover
        if sim_stock <= 0 or sim_demand <= 0:
            days_of_cover = 0.0
        else:
            days_of_cover = round(sim_stock / sim_demand, 2)

        # Required quantity across planning horizon
        required_qty = int(math.ceil(max(0.0, sim_demand * planning_horizon_days - sim_stock)))
        action = "No order needed" if required_qty == 0 else "Order needed"

        # 3. Retrieve suppliers and evaluate with optional lead-time delay
        comp = compare_suppliers(pid, required_qty=0)
        supplier_evals = []

        for sup in comp.get("suppliers", []):
            sup_id = str(sup["supplier_id"])
            sup_name = str(sup["supplier_name"])
            unit_cost = float(sup["unit_cost"])
            base_lead = int(sup["lead_time_days"])
            sim_lead = max(1, int(base_lead + lead_time_delay_days))
            moq = int(sup["min_order_qty"])

            order_qty = int(max(required_qty, moq)) if required_qty > 0 else 0
            total_cost = round(order_qty * unit_cost, 2) if required_qty > 0 else 0.0

            demand_during_transit = round(sim_demand * sim_lead, 2)
            shortfall = round(max(0.0, demand_during_transit - sim_stock), 2)
            uncovered_days = round(max(0.0, sim_lead - days_of_cover), 2)
            risk = _classify_risk(sim_stock, days_of_cover, sim_lead)
            revenue_at_risk = round(shortfall * unit_price, 2)

            supplier_evals.append({
                "supplier_id": sup_id,
                "supplier_name": sup_name,
                "unit_cost": unit_cost,
                "base_lead_time_days": base_lead,
                "lead_time_days": sim_lead,
                "min_order_qty": moq,
                "order_qty": order_qty,
                "total_cost": total_cost,
                "shortfall_before_arrival": shortfall,
                "days_uncovered_before_arrival": uncovered_days,
                "revenue_at_risk": revenue_at_risk,
                "risk_level": risk,
            })

        # Recommended supplier selection (consistent with core planner rule)
        if action == "No order needed":
            overall_risk = "Low"
            chosen = None
        else:
            zero_short = [s for s in supplier_evals if s["shortfall_before_arrival"] == 0.0]
            if zero_short:
                chosen = min(zero_short, key=lambda s: (s["total_cost"], s["lead_time_days"]))
            else:
                chosen = min(supplier_evals, key=lambda s: (s["shortfall_before_arrival"], s["total_cost"], s["lead_time_days"]))

            fastest_sup = min(supplier_evals, key=lambda s: s["lead_time_days"])
            overall_risk = fastest_sup["risk_level"]

            rec_order = {
                "product_id": pid,
                "product_name": name,
                "supplier_id": chosen["supplier_id"],
                "supplier_name": chosen["supplier_name"],
                "required_qty": required_qty,
                "order_qty": chosen["order_qty"],
                "unit_cost": chosen["unit_cost"],
                "total_cost": chosen["total_cost"],
                "lead_time_days": chosen["lead_time_days"],
                "shortfall_before_arrival": chosen["shortfall_before_arrival"],
                "days_uncovered_before_arrival": chosen["days_uncovered_before_arrival"],
                "revenue_at_risk": chosen["revenue_at_risk"],
                "risk_level": chosen["risk_level"],
            }
            recommended_orders.append(rec_order)

        evaluated_products.append({
            "product_id": pid,
            "name": name,
            "category": category,
            "unit_price": unit_price,
            "current_stock": sim_stock,
            "daily_demand": sim_demand,
            "days_of_cover": days_of_cover,
            "required_qty": required_qty,
            "action": action,
            "risk_level": overall_risk,
            "chosen_supplier": chosen["supplier_id"] if chosen else None,
            "chosen_lead_time": chosen["lead_time_days"] if chosen else 0,
            "chosen_cost": chosen["total_cost"] if chosen else 0.0,
            "chosen_shortfall": chosen["shortfall_before_arrival"] if chosen else 0.0,
            "chosen_revenue_at_risk": chosen["revenue_at_risk"] if chosen else 0.0,
            "supplier_options": supplier_evals,
        })

    # Portfolio totals
    tot_cost = round(sum(o["total_cost"] for o in recommended_orders), 2)
    avg_lead = round(sum(o["lead_time_days"] for o in recommended_orders) / len(recommended_orders), 2) if recommended_orders else 0.0
    tot_short = round(sum(o["shortfall_before_arrival"] for o in recommended_orders), 2)
    tot_rev_risk = round(sum(o["revenue_at_risk"] for o in recommended_orders), 2)
    crit_high = sum(1 for o in recommended_orders if o["risk_level"] in ("Critical", "High"))

    return {
        "products": evaluated_products,
        "recommended_orders": recommended_orders,
        "totals": {
            "total_cost": tot_cost,
            "average_lead_time": avg_lead,
            "total_shortage_qty": tot_short,
            "total_revenue_at_risk": tot_rev_risk,
            "critical_or_high_count": crit_high,
        },
    }


def run_scenario(scenario_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Execute a what-if supply chain disruption scenario and compare against baseline.

    Supported scenarios:
        - 'demand_surge' (Scenario A): Increase forecast demand (+30% default).
        - 'supplier_delay' (Scenario B): Increase supplier lead time (+5 days default).
        - 'inventory_reduction' (Scenario C): Reduce available stock (-20% default).

    Args:
        scenario_name: Name or alias of the scenario.
        **kwargs: Optional scenario overrides:
            - surge_pct (float): Demand increase percentage (default: 30.0)
            - delay_days (int): Supplier transit delay in days (default: 5)
            - reduction_pct (float): Inventory reduction percentage (default: 20.0)

    Returns:
        dict: Full JSON-serializable scenario evaluation report containing:
            - scenario_name, description, parameters
            - baseline portfolio metrics
            - simulated portfolio metrics
            - absolute_change from baseline
            - products_risk_increased
            - new_shortage_products
            - most_affected_products (ranked by financial and stockout impact)
            - explanation
    """
    if not isinstance(scenario_name, str):
        return {"error": "scenario_name must be a non-empty string."}

    norm_name = scenario_name.strip().lower().replace("-", "_").replace(" ", "_")

    # Match scenario definitions
    if norm_name in ("demand_surge", "scenario_a", "surge"):
        canonical_name = "demand_surge"
        surge_pct = float(kwargs.get("surge_pct", 30.0))
        demand_mult = round(1.0 + (surge_pct / 100.0), 2)
        lead_delay = 0
        inv_mult = 1.0
        description = f"Simulates a {surge_pct:.0f}% surge in daily customer demand across all catalog products."
        params = {"surge_pct": surge_pct, "demand_multiplier": demand_mult}

    elif norm_name in ("supplier_delay", "scenario_b", "delay"):
        canonical_name = "supplier_delay"
        delay_days = int(kwargs.get("delay_days", 5))
        demand_mult = 1.0
        lead_delay = delay_days
        inv_mult = 1.0
        description = f"Simulates a {delay_days}-day delivery lead time disruption across all supplier transit routes."
        params = {"delay_days": delay_days}

    elif norm_name in ("inventory_reduction", "scenario_c", "reduction", "stock_reduction"):
        canonical_name = "inventory_reduction"
        reduction_pct = float(kwargs.get("reduction_pct", 20.0))
        demand_mult = 1.0
        lead_delay = 0
        inv_mult = round(1.0 - (reduction_pct / 100.0), 2)
        description = f"Simulates a {reduction_pct:.0f}% loss/reduction in available on-hand inventory across all products."
        params = {"reduction_pct": reduction_pct, "inventory_multiplier": inv_mult}

    else:
        return {
            "error": (
                f"Unknown scenario '{scenario_name}'. Supported scenarios: "
                "'demand_surge', 'supplier_delay', 'inventory_reduction'."
            )
        }

    # 1. Baseline evaluation
    base_plan = build_procurement_plan()
    if "error" in base_plan:
        return {"error": f"Failed building baseline plan: {base_plan['error']}"}

    base_product_crit_high = sum(1 for p in base_plan["products"] if p.get("risk_level") in ("Critical", "High"))
    base_totals = {
        "total_cost": base_plan["strategies"]["recommended"]["totals"]["total_cost"],
        "total_shortage_qty": base_plan["strategies"]["recommended"]["totals"]["total_units_short"],
        "total_revenue_at_risk": base_plan["strategies"]["recommended"]["totals"]["total_revenue_at_risk"],
        "critical_or_high_count": base_plan["strategies"]["recommended"]["totals"]["critical_or_high_count"],
        "order_level_crit_high_count": base_plan["strategies"]["recommended"]["totals"]["critical_or_high_count"],
        "product_level_crit_high_count": base_product_crit_high,
        "average_lead_time": base_plan["strategies"]["recommended"]["totals"]["average_lead_time"],
    }

    base_orders_by_pid = {o["product_id"]: o for o in base_plan["strategies"]["recommended"]["orders"]}
    base_prods_by_pid = {p["product_id"]: p for p in base_plan["products"]}

    # 2. Simulated evaluation
    sim_result = simulate_procurement_plan(
        demand_multiplier=demand_mult,
        lead_time_delay_days=lead_delay,
        inventory_multiplier=inv_mult,
    )
    sim_product_crit_high = sum(1 for p in sim_result["products"] if p.get("risk_level") in ("Critical", "High"))
    sim_totals = sim_result["totals"]
    sim_totals["order_level_crit_high_count"] = sim_totals["critical_or_high_count"]
    sim_totals["product_level_crit_high_count"] = sim_product_crit_high

    # 3. Absolute change
    absolute_change = {
        "total_cost": round(sim_totals["total_cost"] - base_totals["total_cost"], 2),
        "total_shortage_qty": round(sim_totals["total_shortage_qty"] - base_totals["total_shortage_qty"], 2),
        "total_revenue_at_risk": round(sim_totals["total_revenue_at_risk"] - base_totals["total_revenue_at_risk"], 2),
        "critical_or_high_count": int(sim_totals["critical_or_high_count"] - base_totals["critical_or_high_count"]),
        "order_level_crit_high_count": int(sim_totals["order_level_crit_high_count"] - base_totals["order_level_crit_high_count"]),
        "product_level_crit_high_count": int(sim_product_crit_high - base_product_crit_high),
        "average_lead_time": round(sim_totals["average_lead_time"] - base_totals["average_lead_time"], 2),
    }

    # 4. Product-level comparative analysis
    products_risk_increased = []
    new_shortage_products = []
    product_impacts = []
    product_comparison_table = []

    for sim_p in sim_result["products"]:
        pid = sim_p["product_id"]
        pname = sim_p["name"]
        base_p = base_prods_by_pid.get(pid, {})
        base_order = base_orders_by_pid.get(pid)

        base_risk = base_p.get("risk_level", "Low")
        sim_risk = sim_p.get("risk_level", "Low")

        base_shortfall = base_order["shortfall_before_arrival"] if base_order else 0.0
        sim_shortfall = sim_p.get("chosen_shortfall", 0.0)

        base_rev_risk = base_order["revenue_at_risk"] if base_order else 0.0
        sim_rev_risk = sim_p.get("chosen_revenue_at_risk", 0.0)

        base_cost = base_order["total_cost"] if base_order else 0.0
        sim_cost = sim_p.get("chosen_cost", 0.0)

        base_req_qty = base_p.get("required_qty", 0)
        sim_req_qty = sim_p.get("required_qty", 0)

        delta_short = round(sim_shortfall - base_shortfall, 2)
        delta_rev = round(sim_rev_risk - base_rev_risk, 2)
        delta_cost = round(sim_cost - base_cost, 2)
        delta_qty = sim_req_qty - base_req_qty
        risk_rank_change = RISK_RANKS.get(sim_risk, 0) - RISK_RANKS.get(base_risk, 0)

        # Flag risk increases
        if risk_rank_change > 0:
            products_risk_increased.append({
                "product_id": pid,
                "product_name": pname,
                "baseline_risk": base_risk,
                "simulated_risk": sim_risk,
            })

        # Flag newly introduced shortages
        if base_shortfall == 0.0 and sim_shortfall > 0.0:
            new_shortage_products.append({
                "product_id": pid,
                "product_name": pname,
                "baseline_shortfall": 0.0,
                "simulated_shortfall": sim_shortfall,
                "revenue_at_risk": sim_rev_risk,
            })

        # Track impact for ranking
        product_impacts.append({
            "product_id": pid,
            "product_name": pname,
            "delta_shortfall": delta_short,
            "delta_revenue_at_risk": delta_rev,
            "delta_procurement_cost": delta_cost,
            "delta_required_qty": delta_qty,
            "baseline_risk": base_risk,
            "simulated_risk": sim_risk,
            "baseline_shortfall": base_shortfall,
            "simulated_shortfall": sim_shortfall,
            "baseline_cost": base_cost,
            "simulated_cost": sim_cost,
        })

        product_comparison_table.append({
            "product_id": pid,
            "product_name": pname,
            "baseline_stock": base_p.get("current_stock"),
            "simulated_stock": sim_p.get("current_stock"),
            "baseline_daily_demand": base_p.get("daily_demand"),
            "simulated_daily_demand": sim_p.get("daily_demand"),
            "baseline_required_qty": base_req_qty,
            "simulated_required_qty": sim_req_qty,
            "baseline_chosen_supplier": base_order.get("supplier_id") if base_order else None,
            "simulated_chosen_supplier": sim_p.get("chosen_supplier"),
            "baseline_lead_time_days": base_order.get("lead_time_days") if base_order else None,
            "simulated_lead_time_days": sim_p.get("chosen_lead_time") if sim_p.get("chosen_supplier") else None,
            "baseline_shortfall": base_shortfall,
            "simulated_shortfall": sim_shortfall,
            "baseline_revenue_at_risk": base_rev_risk,
            "simulated_revenue_at_risk": sim_rev_risk,
            "baseline_cost": base_cost,
            "simulated_cost": sim_cost,
            "baseline_risk": base_risk,
            "simulated_risk": sim_risk,
            "supplier_options": sim_p.get("supplier_options", []),
        })

    # Rank most affected products
    # Priority: higher revenue at risk increase, higher shortage increase, higher cost change, risk escalation
    product_impacts.sort(
        key=lambda x: (
            x["delta_revenue_at_risk"],
            x["delta_shortfall"],
            x["delta_procurement_cost"],
            RISK_RANKS.get(x["simulated_risk"], 0) - RISK_RANKS.get(x["baseline_risk"], 0),
        ),
        reverse=True,
    )

    most_affected = []
    for rank, item in enumerate(product_impacts, 1):
        if (
            item["delta_revenue_at_risk"] > 0
            or item["delta_shortfall"] > 0
            or item["delta_procurement_cost"] > 0
            or item["simulated_risk"] != item["baseline_risk"]
        ):
            most_affected.append({
                "rank": rank,
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "delta_revenue_at_risk": item["delta_revenue_at_risk"],
                "delta_shortfall": item["delta_shortfall"],
                "delta_procurement_cost": item["delta_procurement_cost"],
                "baseline_risk": item["baseline_risk"],
                "simulated_risk": item["simulated_risk"],
                "impact_summary": (
                    f"Shortfall {'+' if item['delta_shortfall'] >= 0 else ''}{item['delta_shortfall']:.2f} units, "
                    f"Rev at risk {'+' if item['delta_revenue_at_risk'] >= 0 else ''}${item['delta_revenue_at_risk']:,.2f}, "
                    f"Cost {'+' if item['delta_procurement_cost'] >= 0 else ''}${item['delta_procurement_cost']:,.2f}, "
                    f"Risk: {item['baseline_risk']} -> {item['simulated_risk']}"
                ),
            })

    # 5. Deterministic concise explanation
    top_affected_names = [f"{a['product_name']} ({a['product_id']})" for a in most_affected[:2]]
    top_str = " and ".join(top_affected_names) if top_affected_names else "None"

    if canonical_name == "demand_surge":
        explanation = (
            f"Under a {params['surge_pct']:.0f}% demand surge, portfolio procurement cost rises by "
            f"${absolute_change['total_cost']:,.2f} (+{(absolute_change['total_cost'] / base_totals['total_cost']) * 100:.1f}%), "
            f"while lead-time shortfall increases by {absolute_change['total_shortage_qty']:.2f} units "
            f"(adding ${absolute_change['total_revenue_at_risk']:,.2f} revenue at risk). "
            f"Product-level urgency escalates ({len(products_risk_increased)} product(s) worsened in inherent risk, led by {top_str}). "
            f"Note: average selected lead time drops by {abs(absolute_change['average_lead_time']):.2f} days and order-level High/Critical "
            f"count decreases from {base_totals['critical_or_high_count']} to {sim_totals['critical_or_high_count']} because the planner "
            f"dynamically switches vulnerable products (such as P008 and P009) to faster suppliers to avoid stockouts, improving their post-switch coverage ratios."
        )
    elif canonical_name == "supplier_delay":
        explanation = (
            f"A {params['delay_days']}-day transit delay applies across every supplier offer, expanding total shortage by "
            f"{absolute_change['total_shortage_qty']:.2f} units (from {base_totals['total_shortage_qty']:.2f} to {sim_totals['total_shortage_qty']:.2f} units) "
            f"and generating ${absolute_change['total_revenue_at_risk']:,.2f} in new revenue at risk. "
            f"{len(new_shortage_products)} product(s) developed newly introduced stockouts, and product-level urgency worsened for {len(products_risk_increased)} product(s). "
            f"Although every supplier lead time increased by {params['delay_days']} days, average selected lead time increased by only "
            f"{absolute_change['average_lead_time']:.2f} days because the planner dynamically re-routed products (e.g. P008 and P009) to faster supplier options to mitigate stockouts. "
            f"Most vulnerable items: {top_str}."
        )
    else:  # inventory_reduction
        explanation = (
            f"A {params['reduction_pct']:.0f}% stock reduction cuts safety buffers, forcing an extra "
            f"${absolute_change['total_cost']:,.2f} in replenishment purchasing. "
            f"Shortage increases by {absolute_change['total_shortage_qty']:.2f} units "
            f"(${absolute_change['total_revenue_at_risk']:,.2f} revenue at risk), and product-level urgency worsened for {len(products_risk_increased)} product(s), led by {top_str}. "
            f"Note: average selected lead time drops by {abs(absolute_change['average_lead_time']):.2f} days and order-level High/Critical "
            f"count decreases from {base_totals['critical_or_high_count']} to {sim_totals['critical_or_high_count']} because the planner "
            f"dynamically switches vulnerable products (P008 and P009) to faster suppliers to protect against newly emerging stockout gaps."
        )

    return {
        "scenario_name": canonical_name,
        "description": description,
        "parameters": params,
        "portfolio": {
            "baseline": base_totals,
            "simulated": sim_totals,
            "absolute_change": absolute_change,
        },
        "baseline": base_totals,
        "simulated": sim_totals,
        "absolute_change": absolute_change,
        "products_risk_increased": products_risk_increased,
        "new_shortage_products": new_shortage_products,
        "most_affected_products": most_affected,
        "explanation": explanation,
        "product_comparison": product_comparison_table,
    }


def list_supported_scenarios() -> List[Dict[str, str]]:
    """Return catalog of available simulation scenarios."""
    return [
        {
            "id": "demand_surge",
            "name": "Scenario A: Demand Surge",
            "description": "Increase forecast customer demand by 30%. Recalculates order quantities, costs, and stockout shortfalls.",
        },
        {
            "id": "supplier_delay",
            "name": "Scenario B: Supplier Delay",
            "description": "Increase supplier lead times by 5 days. Recalculates lead-time demand, stockout shortfalls, and revenue at risk.",
        },
        {
            "id": "inventory_reduction",
            "name": "Scenario C: Inventory Reduction",
            "description": "Reduce on-hand inventory by 20%. Recalculates replenishment requirements, shortage exposure, and urgency risks.",
        },
    ]
