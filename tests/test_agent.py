"""
Test Suite for StockPilot Agent (Step 5).

Pure deterministic unit tests with NO real API calls.
Uses mock Gemini clients to verify:
1. Normal function-calling loop execution and API call counting
2. Unknown tool name handling (graceful error returned to model)
3. Infinite loop protection (halts at max_steps with 'max_steps_reached' status)
4. execute_tool exception resistance (never raises on invalid arguments)
5. Missing GEMINI_API_KEY error handling (returns error dict without raising)
"""

import os
import sys
from google.genai import types

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from agent.stockpilot_agent import SYSTEM_INSTRUCTION, run_agent
from agent.tool_registry import execute_tool


class MockModelsService:
    """Mock models service returning programmed GenerateContentResponse objects."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.history = []

    def generate_content(self, model, contents, config):
        self.call_count += 1
        self.history.append({"model": model, "contents": contents, "config": config})
        if self.responses:
            return self.responses.pop(0)
        # Default empty text response if responses exhausted
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text="Default mock response")],
                    )
                )
            ]
        )


class MockGenAIClient:
    """Mock Gemini client wrapper."""

    def __init__(self, responses):
        self.models = MockModelsService(responses)


def make_function_call_response(name: str, args: dict) -> types.GenerateContentResponse:
    """Helper to build a mock response containing a function call."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_function_call(name=name, args=args)],
                )
            )
        ]
    )


def make_text_response(text: str) -> types.GenerateContentResponse:
    """Helper to build a mock response containing final text."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text)],
                )
            )
        ]
    )


def run_tests():
    print("=" * 80)
    print("STARTING STOCKPILOT AGENT UNIT TESTS (MOCK CLIENT, ZERO API COST)")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Check 1: Normal loop (tool call -> final text)
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying normal 2-step function calling loop...")
    r1 = make_function_call_response("get_procurement_plan", {})
    r2 = make_text_response("Procurement plan analyzed: Recommended strategy costs $182,174.")
    client1 = MockGenAIClient([r1, r2])

    res1 = run_agent("Review inventory", max_steps=8, client=client1)
    assert res1["status"] == "success", f"Expected 'success', got {res1['status']}"
    assert res1["api_call_count"] == 2, f"Expected 2 API calls, got {res1['api_call_count']}"
    assert len(res1["tool_calls"]) == 1, f"Expected 1 tool call, got {len(res1['tool_calls'])}"
    assert res1["tool_calls"][0]["name"] == "get_procurement_plan"
    assert "Procurement plan analyzed" in res1["final_answer"]
    print(" -> PASSED: Agent successfully called tool and returned synthesized answer (api_calls=2).")

    # --------------------------------------------------------------------------
    # Check 2: Unknown tool name handling
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying graceful handling of unknown tool name...")
    r_bad = make_function_call_response("unregistered_mystery_tool", {"x": 1})
    r_final = make_text_response("Recovered from unknown tool error.")
    client2 = MockGenAIClient([r_bad, r_final])

    res2 = run_agent("Do something unknown", max_steps=8, client=client2)
    assert res2["status"] == "success", f"Expected success after error recovery, got {res2['status']}"
    assert res2["api_call_count"] == 2
    assert len(res2["tool_calls"]) == 1
    assert res2["tool_calls"][0]["name"] == "unregistered_mystery_tool"
    assert "Error:" in res2["tool_calls"][0]["result_summary"]
    print(" -> PASSED: Unknown tool safely caught and error returned to model without crashing.")

    # --------------------------------------------------------------------------
    # Check 3: Max steps protection (infinite tool call loop)
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying infinite loop protection stops at max_steps...")
    infinite_responses = [
        make_function_call_response("get_inventory", {"product_id": "P001"})
        for _ in range(10)
    ]
    client3 = MockGenAIClient(infinite_responses)

    max_limit = 4
    res3 = run_agent("Infinite task", max_steps=max_limit, client=client3)
    assert res3["status"] == "max_steps_reached", f"Expected 'max_steps_reached', got {res3['status']}"
    assert res3["api_call_count"] == max_limit, f"Expected {max_limit} API calls, got {res3['api_call_count']}"
    assert len(res3["tool_calls"]) == max_limit
    assert "Max steps reached" in res3["final_answer"]
    print(f" -> PASSED: Halts safely at max_steps ({max_limit}) with 'max_steps_reached' status.")

    # --------------------------------------------------------------------------
    # Check 4: execute_tool never raises on invalid arguments
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying execute_tool never raises on malformed arguments...")
    bad_calls = [
        ("unknown_tool", {}),
        (None, {}),
        ("get_inventory", None),
        ("get_inventory", {"invalid_prop": 999}),
        ("compare_suppliers", "not a dict"),
        ("calculate_reorder", {"product_id": 12345, "lead_time_days": "non_integer"}),
        ("get_demand_forecast", {"product_id": "", "horizon_days": -5}),
    ]

    for name, args in bad_calls:
        try:
            res = execute_tool(name, args)
            assert isinstance(res, dict), f"execute_tool must return dict, got {type(res)}"
            assert "error" in res or isinstance(res, dict)
        except Exception as exc:
            assert False, f"execute_tool raised unexpectedly for {name}({args}): {exc}"

    print(" -> PASSED: execute_tool safely handled all malformed / missing argument inputs.")

    # --------------------------------------------------------------------------
    # Check 5: Missing GEMINI_API_KEY handling
    # --------------------------------------------------------------------------
    print("\n[Check 5] Verifying missing GEMINI_API_KEY returns error without raising...")
    orig_key = os.environ.get("GEMINI_API_KEY")
    try:
        # Clear environment key
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]

        res5 = run_agent("Test missing key", client=None)
        assert isinstance(res5, dict), f"Expected dict return, got {type(res5)}"
        assert res5["status"] == "error", f"Expected status 'error', got {res5['status']}"
        assert "GEMINI_API_KEY is missing" in res5["final_answer"]
    finally:
        # Restore environment key
        if orig_key is not None:
            os.environ["GEMINI_API_KEY"] = orig_key

    print(" -> PASSED: Missing GEMINI_API_KEY cleanly returns error dict without stack trace.")

    # --------------------------------------------------------------------------
    # Check 6: System instruction contains required Step 5b terms
    # --------------------------------------------------------------------------
    print("\n[Check 6] Verifying system instruction contains 'simulated' and 'thin_buffer_products'...")
    assert "simulated" in SYSTEM_INSTRUCTION, "SYSTEM_INSTRUCTION must contain the word 'simulated'"
    assert "thin_buffer_products" in SYSTEM_INSTRUCTION, "SYSTEM_INSTRUCTION must contain 'thin_buffer_products'"
    print(" -> PASSED: System instruction contains 'simulated' and 'thin_buffer_products'.")

    print("\n" + "=" * 80)
    print("ALL AGENT UNIT TESTS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

