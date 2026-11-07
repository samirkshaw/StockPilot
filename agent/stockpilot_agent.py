"""
StockPilot Agent Core Module.

Implements the autonomous supply chain decision agent using the official
google-genai SDK with a manual, observable function-calling loop.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

from agent.tool_registry import clear_tool_cache, execute_tool, get_agent_tools

# Load environment variables once at module import
load_dotenv()

# System instruction defining agent behavior and reporting structure
SYSTEM_INSTRUCTION = (
    "You are StockPilot, a supply chain decision agent analyzing simulated inventory and supplier data. "
    "You must get every number directly from the tools. Never calculate, estimate, or invent numbers yourself. "
    "Prefer get_procurement_plan first, then call other tools only if needed to drill into a specific product. "
    "Always describe the data as simulated, never live. Never make claims about supplier reliability, quality, "
    "or any factor not present in the tool output. "
    "Your final answer must strictly adhere to the following structure: "
    "1. Recommended Orders: For each product that needs an order, state the recommended supplier, order quantity, "
    "total cost, lead time, and the reason. "
    "2. Unavoidable Stockouts: Report unavoidable stockouts ONLY from the plan's unavoidable_stockouts field, "
    "stating product ID, supplier ID, shortfall units, and revenue at risk (mentioning that revenue at risk is "
    "units short times unit price, not profit). "
    "3. Strategy Comparison Table: Present Cheapest, Fastest, and Recommended as three columns of one comparison "
    "table using the exact portfolio totals from the plan (Total Cost, Average Lead Time, Total Units Short, "
    "Total Revenue at Risk, and Critical/High Count). "
    "4. Thin Safety Buffers & Tradeoff: Report thin-buffer products ONLY from the plan's thin_buffer_products field "
    "(with lead time, days of cover, risk level, and cost saved vs fastest). "
    "State the recommended_vs_fastest tradeoff in one or two sentences using the exact numbers from "
    "the recommended_vs_fastest field (cost_saved, extra_lead_time_days_avg, and extra_crit_high_products)."
)


def _summarize_result(name: str, result: Dict[str, Any]) -> str:
    """Create a concise human-readable summary of a tool execution result."""
    if "error" in result:
        return f"Error: {result['error']}"
    if name == "get_procurement_plan":
        prods = result.get("products", [])
        rec_totals = result.get("strategies", {}).get("recommended", {}).get("totals", {})
        cost = rec_totals.get("total_cost", 0.0)
        short = rec_totals.get("total_units_short", 0.0)
        return f"Plan built: {len(prods)} products evaluated. Recommended total cost: ${cost:,.2f}, units short: {short:.1f}"
    if name == "get_inventory":
        return f"Stock: {result.get('current_stock')}, Price: ${result.get('unit_price')}, Category: {result.get('category')}"
    if name == "get_sales_analysis":
        rec_d = result.get("recommended_demand")
        spike = result.get("spike_detected")
        return f"Recommended demand: {rec_d}/day, spike: {spike}"
    if name == "get_demand_forecast":
        fc = result.get("avg_daily_forecast")
        meth = result.get("method_used")
        wape = result.get("backtest_wape")
        return f"Forecast: {fc}/day using {meth} (WAPE {wape}%)"
    if name == "compare_suppliers":
        sups = result.get("suppliers", [])
        fast = result.get("fastest_supplier_id")
        cheap = result.get("cheapest_supplier_id")
        return f"{len(sups)} suppliers compared (Cheapest: {cheap}, Fastest: {fast})"
    if name == "calculate_reorder":
        rec = result.get("recommended_order_qty")
        risk = result.get("risk_level")
        short = result.get("shortfall_before_arrival")
        return f"Reorder qty: {rec}, Risk: {risk}, Shortfall: {short}"
    return "Executed successfully"


def run_agent(
    task: str,
    max_steps: int = 8,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the StockPilot agent on a given user task using manual function calling.

    Args:
        task: Natural language procurement or inventory instruction.
        max_steps: Maximum loop iterations before halting (default: 8).
        client: Optional pre-configured or mock Gemini client. If None,
                instantiates genai.Client using GEMINI_API_KEY from environment.

    Returns:
        dict:
            - final_answer (str): Synthesized response text
            - tool_calls (list): Records of all tools executed
            - api_call_count (int): Total API requests made (including retries)
            - model_used (str): Identifier of the Gemini model used
            - status (str): 'success', 'max_steps_reached', or 'error'
    """
    # Clear caches from previous runs
    clear_tool_cache()

    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL") or ("mock-model" if client is not None else None)
    is_live_run = client is None

    # Validation of credentials and configuration for live runs
    if is_live_run:
        if not api_key:
            return {
                "final_answer": "Error: GEMINI_API_KEY is missing from environment. Please set it in .env.",
                "tool_calls": [],
                "api_call_count": 0,
                "model_used": model_name or "unknown",
                "status": "error",
            }

        if not model_name:
            return {
                "final_answer": "Error: GEMINI_MODEL is missing from environment. Please set it in .env.",
                "tool_calls": [],
                "api_call_count": 0,
                "model_used": "unknown",
                "status": "error",
            }

        print("Warning: Free tier allows about 20 requests per day; this run will use roughly 3-6.")
        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            return {
                "final_answer": f"Error initializing Gemini client: {str(e)}",
                "tool_calls": [],
                "api_call_count": 0,
                "model_used": model_name,
                "status": "error",
            }
    else:
        model_name = model_name or "mock-model"

    api_call_count = 0
    tool_calls_record: List[Dict[str, Any]] = []
    last_api_call_time = 0.0

    # Rate-limiting helper (enforce 7s gap on live calls to respect free tier RPM limits)
    def _rate_limit_gap():
        nonlocal last_api_call_time
        if is_live_run:
            elapsed = time.time() - last_api_call_time
            if elapsed < 7.0:
                time.sleep(7.0 - elapsed)

    # API call with retries on 429 and 5xx errors
    def _call_model_with_retry(contents: List[Any], config: Any) -> Any:
        nonlocal api_call_count, last_api_call_time
        backoff_delays = [2.0, 4.0, 8.0]
        max_attempts = 4

        for attempt in range(max_attempts):
            _rate_limit_gap()
            api_call_count += 1
            last_api_call_time = time.time()

            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                return response
            except Exception as exc:
                err_str = str(exc)
                status_code = getattr(exc, "code", None)
                is_429 = status_code == 429 or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_5xx = (
                    (isinstance(status_code, int) and 500 <= status_code < 600)
                    or any(f"50{i}" in err_str for i in range(6))
                )

                if (is_429 or is_5xx) and attempt < len(backoff_delays):
                    delay = backoff_delays[attempt]
                    time.sleep(delay)
                    continue

                if is_429:
                    raise RuntimeError(
                        "Gemini API quota may be exhausted (429 Resource Exhausted). "
                        "Please check your usage or try again later."
                    )
                raise exc

    # Prepare chat configuration
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=get_agent_tools(),
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    contents: List[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=task)])
    ]

    for step in range(1, max_steps + 1):
        try:
            response = _call_model_with_retry(contents, config)
        except RuntimeError as r_err:
            return {
                "final_answer": str(r_err),
                "tool_calls": tool_calls_record,
                "api_call_count": api_call_count,
                "model_used": model_name,
                "status": "error",
            }
        except Exception as e:
            return {
                "final_answer": f"API error encountered: {str(e)}",
                "tool_calls": tool_calls_record,
                "api_call_count": api_call_count,
                "model_used": model_name,
                "status": "error",
            }

        function_calls = getattr(response, "function_calls", None)

        # If no tool calls requested, we have reached the model's final synthesis
        if not function_calls:
            final_text = getattr(response, "text", "") or ""
            return {
                "final_answer": final_text,
                "tool_calls": tool_calls_record,
                "api_call_count": api_call_count,
                "model_used": model_name,
                "status": "success",
            }

        # Append model output containing the function calls to history
        candidates = getattr(response, "candidates", [])
        if candidates and hasattr(candidates[0], "content") and candidates[0].content:
            contents.append(candidates[0].content)
        else:
            # Fallback representation of model call
            call_parts = [
                types.Part.from_function_call(name=fc.name, args=getattr(fc, "args", {}) or {})
                for fc in function_calls
            ]
            contents.append(types.Content(role="model", parts=call_parts))

        # Execute each requested tool and prepare responses
        response_parts = []
        for fc in function_calls:
            fc_name = fc.name
            fc_args = getattr(fc, "args", {}) or {}
            if hasattr(fc_args, "items"):
                fc_args = dict(fc_args)

            tool_result = execute_tool(fc_name, fc_args)
            summary = _summarize_result(fc_name, tool_result)

            tool_calls_record.append({
                "step": step,
                "name": fc_name,
                "args": fc_args,
                "result_summary": summary,
            })

            resp_part = types.Part.from_function_response(
                name=fc_name,
                response={"result": tool_result},
            )
            response_parts.append(resp_part)

        contents.append(types.Content(role="user", parts=response_parts))

    return {
        "final_answer": "Max steps reached before the model completed the task.",
        "tool_calls": tool_calls_record,
        "api_call_count": api_call_count,
        "model_used": model_name,
        "status": "max_steps_reached",
    }
