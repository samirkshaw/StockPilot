"""
CLI Runner for the StockPilot Agent.

Usage:
  python scripts/run_agent.py [task]
  python scripts/run_agent.py --offline

Default task:
  "Review all inventory and recommend a procurement plan."
"""

from datetime import datetime
import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agent.stockpilot_agent import run_agent

REPORTS_DIR = os.path.join(REPO_ROOT, "reports")


def generate_agent_markdown_report(result: dict, task: str) -> str:
    """Generate reports/agent_report.md containing final answer and audit trace."""
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


def main():
    args = sys.argv[1:]
    is_offline = "--offline" in args

    last_run_path = os.path.join(REPORTS_DIR, "last_agent_run.json")
    trace_path = os.path.join(REPORTS_DIR, "agent_trace.json")
    report_path = os.path.join(REPORTS_DIR, "agent_report.md")

    if is_offline:
        print("=" * 80)
        print("STOCKPILOT AGENT - OFFLINE CACHED RESULT")
        print("=" * 80)

        if not os.path.exists(last_run_path):
            print(f"No previous run found at {last_run_path}. Please execute a live run first.")
            sys.exit(1)

        with open(last_run_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"\nTask: {data.get('task')}")
        print(f"Model: {data.get('model_used')} | Timestamp: {data.get('timestamp')}")
        print(f"API Calls Used: {data.get('api_call_count')}")

        print("\nTool Calls Executed:")
        for tc in data.get("tool_calls", []):
            print(f" - [Step {tc['step']}] {tc['name']}({tc['args']}) -> {tc['result_summary']}")

        print("\nFinal Answer:")
        print("-" * 80)
        print(data.get("final_answer", ""))
        print("-" * 80)
        return

    # Extract task from arguments
    task_args = [a for a in args if not a.startswith("--")]
    if task_args:
        task = " ".join(task_args)
    else:
        task = "Review all inventory and recommend a procurement plan."

    print("=" * 80)
    print("RUNNING STOCKPILOT AGENT")
    print("=" * 80)
    print(f"Task: {task}\n")

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
        os.makedirs(REPORTS_DIR, exist_ok=True)

        trace_data = {
            "task": task,
            "model": result.get("model_used"),
            "api_call_count": result.get("api_call_count"),
            "timestamp": datetime.now().isoformat(),
            "tool_calls": result.get("tool_calls", []),
        }
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)

        md_content = generate_agent_markdown_report(result, task)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        last_run_data = {
            "task": task,
            "timestamp": datetime.now().isoformat(),
            "final_answer": result.get("final_answer"),
            "tool_calls": result.get("tool_calls", []),
            "api_call_count": result.get("api_call_count"),
            "model_used": result.get("model_used"),
            "status": result.get("status"),
        }
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(last_run_data, f, indent=2)

        print(f"\nArtifacts saved successfully:")
        print(f" - {trace_path}")
        print(f" - {report_path}")
        print(f" - {last_run_path}")
    else:
        print("\nRun did not succeed; existing reports were preserved without overwrite.")


if __name__ == "__main__":
    main()

