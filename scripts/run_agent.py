"""
CLI Runner for the StockPilot Agent.

Usage:
  python scripts/run_agent.py [task] [--tag NAME]
  python scripts/run_agent.py --offline [--tag NAME]

Default task:
  "Review all inventory and recommend a procurement plan."
"""

import argparse
from datetime import datetime
import json
import os
import sys
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agent.stockpilot_agent import run_agent

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def generate_agent_markdown_report(result: dict, task: str) -> str:
    """Generate markdown containing final answer and audit trace."""
    lines = []
    lines.append("# StockPilot Procurement Decision Report")
    lines.append("")
    lines.append(f"**Task:** {task}")
    lines.append(f"**Generated At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Model:** {result.get('model_used')}")
    lines.append(f"**API Calls:** {result.get('api_call_count')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Executive Procurement Decision")
    lines.append("")
    lines.append(result.get("final_answer", ""))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## How This Was Produced")
    lines.append("")
    lines.append("The StockPilot agent performed the following tool investigations in chronological sequence:")
    lines.append("")

    for i, tc in enumerate(result.get("tool_calls", []), 1):
        args_str = ", ".join(f"{k}={v}" for k, v in tc.get("args", {}).items())
        lines.append(f"{i}. **`{tc['name']}`**({args_str})")
        lines.append(f"   - *Result Summary:* {tc['result_summary']}")
        lines.append("")

    return "\n".join(lines)


def save_agent_run(result: Dict[str, Any], task: str, tag: Optional[str] = None) -> Dict[str, str]:
    """
    Save agent run outputs.
    - If tag is provided: saves under reports/runs/<tag>/ (agent_trace.json, agent_report.md, run.json)
      and does NOT overwrite reports/last_agent_run.json.
    - If tag is None: saves directly under reports/ (agent_trace.json, agent_report.md, last_agent_run.json).
    """
    timestamp = datetime.now().isoformat()
    trace_data = {
        "task": task,
        "model": result.get("model_used"),
        "api_call_count": result.get("api_call_count"),
        "timestamp": timestamp,
        "tool_calls": result.get("tool_calls", []),
    }
    run_data = {
        "task": task,
        "timestamp": timestamp,
        "final_answer": result.get("final_answer"),
        "tool_calls": result.get("tool_calls", []),
        "api_call_count": result.get("api_call_count"),
        "model_used": result.get("model_used"),
        "status": result.get("status"),
    }
    md_content = generate_agent_markdown_report(result, task)

    saved_paths = {}

    if tag:
        tag_dir = os.path.join(REPORTS_DIR, "runs", tag)
        os.makedirs(tag_dir, exist_ok=True)

        trace_path = os.path.join(tag_dir, "agent_trace.json")
        report_path = os.path.join(tag_dir, "agent_report.md")
        run_path = os.path.join(tag_dir, "run.json")

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)

        saved_paths["trace"] = trace_path
        saved_paths["report"] = report_path
        saved_paths["run"] = run_path
    else:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        trace_path = os.path.join(REPORTS_DIR, "agent_trace.json")
        report_path = os.path.join(REPORTS_DIR, "agent_report.md")
        last_run_path = os.path.join(REPORTS_DIR, "last_agent_run.json")

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)

        saved_paths["trace"] = trace_path
        saved_paths["report"] = report_path
        saved_paths["run"] = last_run_path

    return saved_paths


def main():
    parser = argparse.ArgumentParser(description="StockPilot Agent Runner")
    parser.add_argument(
        "task",
        nargs="*",
        default=["Review all inventory and recommend a procurement plan."],
        help="Task prompt for the agent",
    )
    parser.add_argument("--offline", action="store_true", help="Print saved result without calling API")
    parser.add_argument("--tag", type=str, default=None, help="Tag name to organize outputs under reports/runs/<NAME>/")
    parsed_args = parser.parse_args()

    task = " ".join(parsed_args.task) if isinstance(parsed_args.task, list) else parsed_args.task
    tag = parsed_args.tag

    if parsed_args.offline:
        print("=" * 80)
        print(f"STOCKPILOT AGENT - OFFLINE CACHED RESULT{' (TAG: ' + tag + ')' if tag else ''}")
        print("=" * 80)

        if tag:
            target_run_path = os.path.join(REPORTS_DIR, "runs", tag, "run.json")
        else:
            target_run_path = os.path.join(REPORTS_DIR, "last_agent_run.json")

        if not os.path.exists(target_run_path):
            print(f"No previous run found at {target_run_path}. Please execute a run first.")
            sys.exit(1)

        with open(target_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"\nTask: {data.get('task')}")
        print(f"Model: {data.get('model_used')} | Timestamp: {data.get('timestamp')}")
        print(f"API Calls Used: {data.get('api_call_count')}")

        print("\nTool Calls Executed:")
        for tc in data.get("tool_calls", []):
            print(f" - [Step {tc['step']}] {tc['name']}({tc.get('args', {})}) -> {tc.get('result_summary')}")

        print("\nFinal Answer:")
        print("-" * 80)
        print(data.get("final_answer", ""))
        print("-" * 80)
        return

    print("=" * 80)
    print("RUNNING STOCKPILOT AGENT")
    print("=" * 80)
    print(f"Task: {task}")
    if tag:
        print(f"Tag: {tag}")
    print()

    result = run_agent(task=task)

    print("\n" + "=" * 80)
    print("AGENT EXECUTION FINISHED")
    print("=" * 80)
    print(f"Status: {result.get('status')}")
    print(f"Model: {result.get('model_used')}")
    print(f"Total API Calls Used: {result.get('api_call_count')}")

    print("\nTool Calls Record:")
    for tc in result.get("tool_calls", []):
        print(f" - [Step {tc['step']}] {tc['name']}({tc.get('args', {})}) -> {tc.get('result_summary')}")

    print("\nFinal Answer:")
    print("-" * 80)
    print(result.get("final_answer"))
    print("-" * 80)

    # Save artifacts ONLY on successful runs
    if result.get("status") == "success":
        saved_paths = save_agent_run(result, task, tag=tag)
        print(f"\nArtifacts saved successfully:")
        for k, p in saved_paths.items():
            print(f" - {p}")
    else:
        print("\nRun did not succeed; existing reports were preserved without overwrite.")


if __name__ == "__main__":
    main()
