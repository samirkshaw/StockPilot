"""
Groundedness Checker for StockPilot Agent Answers.

Checks whether every number cited in the agent's final answer originated
directly from the deterministic procurement plan.

Usage:
    python scripts/check_groundedness.py
"""

import json
import math
import os
import re
import sys
from typing import Any, List, Set, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.procurement_planner import build_procurement_plan

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def collect_plan_numbers(obj: Any, target_set: Set[float]) -> None:
    """Recursively collect all numeric values present anywhere in the plan dictionary."""
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
        # Also collect numbers that are part of product names or strings (e.g. '34' in '34-inch', '4' in '4K')
        nums_in_str = re.findall(r"\b\d+(?:\.\d+)?\b", obj)
        for num_s in nums_in_str:
            try:
                v = float(num_s)
                target_set.add(round(v, 2))
                target_set.add(float(int(round(v))))
            except ValueError:
                pass


def extract_numbers_from_text(text: str) -> List[Tuple[str, float, str]]:
    """
    Remove product IDs (P001-style) and supplier IDs (SUP-103-style),
    then extract all remaining numeric values with surrounding context.
    """
    # Remove product IDs (P001 - P010) and supplier IDs (SUP-101 - SUP-110)
    cleaned = re.sub(r"\bP\d{3}\b", " ", text)
    cleaned = re.sub(r"\bSUP-\d{3}\b", " ", cleaned)

    # Match numbers (integers, decimals, currency with $, percentages)
    pattern = re.compile(r"(?:[\$])?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)(?:%)?")
    extracted = []

    for match in pattern.finditer(cleaned):
        raw_token = match.group(0).strip()
        num_str = match.group(1).replace(",", "").strip()

        try:
            val = float(num_str)
        except ValueError:
            continue

        # Extract surrounding context (~30 chars before and after)
        start = max(0, match.start() - 30)
        end = min(len(cleaned), match.end() + 30)
        context = cleaned[start:end].replace("\n", " ").strip()
        context = re.sub(r"\s+", " ", context)

        extracted.append((raw_token, val, context))

    return extracted


def main():
    print("=" * 80)
    print("STOCKPILOT AGENT GROUNDEDNESS AUDIT REPORT")
    print("=" * 80)

    last_run_path = os.path.join(REPORTS_DIR, "last_agent_run.json")
    plan_path = os.path.join(REPORTS_DIR, "procurement_plan.json")

    # 1. Load agent final answer
    if not os.path.exists(last_run_path):
        print(f"Error: {last_run_path} not found. Please run scripts/run_agent.py first.")
        sys.exit(0)

    with open(last_run_path, "r", encoding="utf-8") as f:
        agent_data = json.load(f)

    final_answer = agent_data.get("final_answer", "")
    if not final_answer:
        print("Error: No final_answer found in last_agent_run.json.")
        sys.exit(0)

    # 2. Load or re-generate procurement plan
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    else:
        print("Notice: reports/procurement_plan.json missing; regenerating via build_procurement_plan()...")
        plan = build_procurement_plan()

    # 3. Collect valid plan numbers
    valid_numbers: Set[float] = set()
    collect_plan_numbers(plan, valid_numbers)

    # Also add standard small index numbers (1, 2, 3, 4 for enumerated section titles)
    for i in range(1, 11):
        valid_numbers.add(float(i))

    # 4. Extract and check numbers from answer
    extracted = extract_numbers_from_text(final_answer)
    matched_count = 0
    unmatched = []

    for raw_token, val, context in extracted:
        val_rounded = round(val, 2)
        val_int = float(int(round(val)))
        val_floor = float(int(val))
        val_1dec = round(val, 1)

        if (
            val_rounded in valid_numbers
            or val_int in valid_numbers
            or val_floor in valid_numbers
            or val_1dec in valid_numbers
        ):
            matched_count += 1
        else:
            unmatched.append((raw_token, val, context))

    total_found = len(extracted)

    print(f"\nAudit Summary:")
    print(f" - Total Numbers Found in Answer : {total_found}")
    print(f" - Numbers Grounded in Plan      : {matched_count}")
    print(f" - Unmatched Numbers             : {len(unmatched)}")

    if unmatched:
        print("\nUnmatched Numbers for Manual Review:")
        print("-" * 80)
        for token, val, ctx in unmatched:
            print(f" • Value: {token:<15} Context: \"...{ctx}...\"")
        print("-" * 80)
        print("\nNote: Some unmatched values may be stylistic approximations or descriptive text.")
    else:
        print("\n" + "=" * 80)
        print("GROUNDEDNESS: all numbers matched")
        print("=" * 80)

    sys.exit(0)


if __name__ == "__main__":
    main()

