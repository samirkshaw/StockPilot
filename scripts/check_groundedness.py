"""
Groundedness Checker for StockPilot Agent Answers.

Checks whether:
1. Every number cited globally in the agent's answer originated from the plan.
2. Every number cited within a product-specific section originated strictly
   from that product's data entries in the plan.

Usage:
    python scripts/check_groundedness.py [path_to_run.json]
"""

import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.procurement_planner import build_procurement_plan

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def collect_plan_numbers(obj: Any, target_set: Set[float]) -> None:
    """Recursively collect all numeric values present anywhere in the object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            collect_plan_numbers(v, target_set)
    elif isinstance(obj, list):
        for item in obj:
            collect_plan_numbers(item, target_set)
    elif isinstance(obj, (int, float)):
        val = float(obj)
        target_set.add(round(val, 2))
        target_set.add(round(val, 1))
        target_set.add(float(int(round(val))))
        target_set.add(float(int(val)))
        target_set.add(float(math.ceil(val)))
    elif isinstance(obj, str):
        # Also extract numbers embedded in product names or descriptions (e.g. '34' in '34-inch', '4' in '4K')
        for num_s in re.findall(r"\b\d+(?:\.\d+)?\b", obj):
            try:
                v = float(num_s)
                target_set.add(round(v, 2))
                target_set.add(float(int(round(v))))
            except ValueError:
                pass


LINE_NUMBERING_RE = re.compile(r"^\s*\d+(?:[\.\)]|\s+[-–—])(?:\s+|$)")


def strip_line_numbering(text: str) -> str:
    """
    Ignore numbers that are list or heading numbering at the start of a line
    (e.g., '1.', '2)', '3 -').
    """
    lines = text.splitlines()
    cleaned_lines = [LINE_NUMBERING_RE.sub(" ", line) for line in lines]
    return "\n".join(cleaned_lines)


def extract_numbers_from_text(text: str) -> List[Tuple[str, float, str]]:
    """
    Remove product IDs (P001-style) and supplier IDs (SUP-103-style),
    strip line numbering, then extract all remaining numeric values with surrounding context.
    """
    cleaned = strip_line_numbering(text)
    cleaned = re.sub(r"\bP\d{3}\b", " ", cleaned)
    cleaned = re.sub(r"\bSUP-\d{3}\b", " ", cleaned)

    pattern = re.compile(r"(?:[\$])?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?:%)?")
    extracted = []

    for match in pattern.finditer(cleaned):
        raw_token = match.group(0).strip()
        num_str = match.group(1).replace(",", "").strip()

        try:
            val = float(num_str)
        except ValueError:
            continue

        start = max(0, match.start() - 30)
        end = min(len(cleaned), match.end() + 30)
        context = cleaned[start:end].replace("\n", " ").strip()
        context = re.sub(r"\s+", " ", context)

        extracted.append((raw_token, val, context))

    return extracted


def build_per_product_number_map(
    plan: Dict[str, Any],
    tool_calls: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Set[float]]:
    """
    Build a dictionary mapping product_id to the set of numbers appearing
    under that product in the plan and in tool results whose args contain that product_id.
    """
    prod_map: Dict[str, Set[float]] = {}
    all_pids = [f"P{i:03d}" for i in range(1, 11)]

    for pid in all_pids:
        s: Set[float] = set()

        # 1. Product record and supplier options in plan['products']
        for p in plan.get("products", []):
            if p.get("product_id") == pid:
                collect_plan_numbers(p, s)

        # 2. Recommended order row
        for o in plan.get("strategies", {}).get("recommended", {}).get("orders", []):
            if o.get("product_id") == pid:
                collect_plan_numbers(o, s)

        # 3. Thin buffer products
        for tb in plan.get("thin_buffer_products", []):
            if tb.get("product_id") == pid:
                collect_plan_numbers(tb, s)

        # 4. Unavoidable stockouts
        for u in plan.get("unavoidable_stockouts", []):
            if u.get("product_id") == pid:
                collect_plan_numbers(u, s)

        # 5. Tool results whose args contain that product_id
        if tool_calls:
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                res = tc.get("result")
                if res is None:
                    continue
                args = tc.get("args", {})
                args_contain_pid = False
                if isinstance(args, dict):
                    args_contain_pid = any(
                        pid == v or (isinstance(v, str) and pid in v)
                        for v in args.values()
                    )
                elif isinstance(args, str):
                    args_contain_pid = pid in args

                if args_contain_pid:
                    collect_plan_numbers(res, s)

        prod_map[pid] = s

    return prod_map


def split_into_product_blocks(text: str) -> List[Tuple[str, List[str]]]:
    """
    Split final answer into blocks that start at a line mentioning a product ID
    and run until the next line mentioning a different product ID or section boundary.
    """
    lines = text.splitlines()
    blocks = []
    current_pid = None
    current_lines = []

    for line in lines:
        pids = re.findall(r"\bP\d{3}\b", line)
        if pids:
            new_pid = pids[0]
            if current_pid and new_pid != current_pid:
                blocks.append((current_pid, current_lines))
                current_lines = []
            current_pid = new_pid
            current_lines.append(line)
        elif line.startswith("#") or line.startswith("---") or line.startswith("|") or "Tradeoff:" in line:
            if current_pid:
                blocks.append((current_pid, current_lines))
                current_pid = None
                current_lines = []
        else:
            if current_pid:
                current_lines.append(line)

    if current_pid and current_lines:
        blocks.append((current_pid, current_lines))

    return blocks


def main():
    print("=" * 80)
    print("STOCKPILOT AGENT GROUNDEDNESS AUDIT REPORT")
    print("=" * 80)

    # Allow custom run json path as first CLI argument
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        run_json_path = os.path.abspath(sys.argv[1])
    else:
        run_json_path = os.path.join(REPORTS_DIR, "last_agent_run.json")

    print(f"Auditing file: {run_json_path}")

    # 1. Load agent run
    if not os.path.exists(run_json_path):
        print(f"Error: {run_json_path} not found.")
        sys.exit(0)

    with open(run_json_path, "r", encoding="utf-8") as f:
        agent_data = json.load(f)

    final_answer = agent_data.get("final_answer", "")
    if not final_answer:
        print("Error: No final_answer found in run data.")
        sys.exit(0)

    # Check available stored tool results in the run data
    stored_tool_results = [
        tc for tc in agent_data.get("tool_calls", [])
        if isinstance(tc, dict) and "result" in tc and tc["result"] is not None
    ]
    tool_results_count = len(stored_tool_results)
    if tool_results_count > 0:
        print(f"Tool results available: {tool_results_count}")
    else:
        print("Tool results available: plan only (no stored tool results)")

    # 2. Load or re-generate procurement plan
    plan_path = os.path.join(REPORTS_DIR, "procurement_plan.json")
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    else:
        plan = build_procurement_plan()

    # -------------------------------------------------------------------------
    # PART A: GLOBAL GROUNDEDNESS CHECK
    # -------------------------------------------------------------------------
    global_plan_numbers: Set[float] = set()
    collect_plan_numbers(plan, global_plan_numbers)
    for i in range(1, 11):
        global_plan_numbers.add(float(i))

    for tc in stored_tool_results:
        collect_plan_numbers(tc.get("result"), global_plan_numbers)

    extracted_global = extract_numbers_from_text(final_answer)
    global_matched = 0
    global_unmatched = []

    for raw_token, val, context in extracted_global:
        val_rounded = round(val, 2)
        val_int = float(int(round(val)))
        val_floor = float(int(val))
        val_1dec = round(val, 1)

        if (
            val_rounded in global_plan_numbers
            or val_int in global_plan_numbers
            or val_floor in global_plan_numbers
            or val_1dec in global_plan_numbers
        ):
            global_matched += 1
        else:
            global_unmatched.append((raw_token, val, context))

    print(f"\n1. Global Groundedness Audit:")
    print(f" - Total Numbers Found in Answer : {len(extracted_global)}")
    print(f" - Numbers Grounded Globally     : {global_matched}")
    print(f" - Globally Unmatched Numbers    : {len(global_unmatched)}")

    if global_unmatched:
        print("\nGlobally Unmatched Numbers for Manual Review:")
        print("-" * 80)
        for token, val, ctx in global_unmatched:
            print(f" • Value: {token:<15} Context: \"...{ctx}...\"")
        print("-" * 80)
    else:
        print("\n" + "=" * 80)
        print("GROUNDEDNESS: all numbers matched")
        print("=" * 80)

    # -------------------------------------------------------------------------
    # PART B: PER-PRODUCT GROUNDEDNESS CHECK
    # -------------------------------------------------------------------------
    prod_number_map = build_per_product_number_map(plan, stored_tool_results)
    product_blocks = split_into_product_blocks(final_answer)

    total_prod_numbers = 0
    matched_prod_numbers = 0
    unmatched_per_prod: List[Tuple[str, str, float, str]] = []

    num_pattern = re.compile(r"(?:[\$])?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?:%)?")

    for pid, blines in product_blocks:
        btext = strip_line_numbering("\n".join(blines))
        cleaned = re.sub(r"\bP\d{3}\b", " ", btext)
        cleaned = re.sub(r"\bSUP-\d{3}\b", " ", cleaned)
        matches = list(num_pattern.finditer(cleaned))
        valid_set = prod_number_map.get(pid, set())

        for m in matches:
            raw_str = m.group(1).replace(",", "").strip()
            try:
                val = float(raw_str)
                total_prod_numbers += 1
                val_rounded = round(val, 2)
                val_int = float(int(round(val)))
                val_floor = float(int(val))
                val_1dec = round(val, 1)

                if (
                    val_rounded in valid_set
                    or val_int in valid_set
                    or val_floor in valid_set
                    or val_1dec in valid_set
                ):
                    matched_prod_numbers += 1
                else:
                    span = m.span()
                    start = max(0, span[0] - 25)
                    end = min(len(cleaned), span[1] + 25)
                    ctx = cleaned[start:end].replace("\n", " ").strip()
                    ctx = re.sub(r"\s+", " ", ctx)
                    unmatched_per_prod.append((pid, m.group(0), val, ctx))
            except ValueError:
                pass

    print(f"\n2. Per-Product Groundedness Audit:")
    print(f" - Total Product-Specific Numbers : {total_prod_numbers}")
    print(f" - Numbers Grounded to Product    : {matched_prod_numbers}")
    print(f" - Unmatched Product Numbers      : {len(unmatched_per_prod)}")

    if unmatched_per_prod:
        print("\nPer-Product Unmatched Numbers for Manual Review:")
        print("-" * 80)
        for pid, token, val, ctx in unmatched_per_prod:
            print(f" • [{pid}] Value: {token:<15} Context: \"...{ctx}...\"")
        print("-" * 80)
    else:
        print("\n" + "=" * 80)
        print("PER-PRODUCT: all numbers matched")
        print("=" * 80)

    sys.exit(0)


if __name__ == "__main__":
    main()
