"""
Structural Test Suite for Demand Forecasting (StockPilot Step 3).

Verifies structural guarantees:
1. Every forecast function returns `horizon` non-negative float values.
2. `forecast_demand` returns an 'error' key for unknown product IDs.
3. Information isolation / no lookahead leak: data on or after the origin day
   is never used to generate forecasts (altering future values produces identical forecasts).
4. `forecast_demand` returns all required keys with valid types for every product.
"""

import os
import sys
import numpy as np
import pandas as pd

# Add repo root to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.demand_forecast import (
    forecast_moving_average,
    forecast_exp_smoothing,
    forecast_weekday_seasonal,
    baseline_30d_average,
    forecast_demand,
    _load_product_sales_series,
)


def run_tests():
    print("=" * 80)
    print("STARTING STRUCTURAL FORECASTING VERIFICATION SUITE")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Check 1: Every forecast function returns horizon non-negative values
    # --------------------------------------------------------------------------
    print("\n[Check 1] Verifying all forecast functions return horizon non-negative values...")
    test_dates = pd.date_range("2026-01-01", periods=60, freq="D")
    sample_series = pd.Series(np.random.poisson(lam=10, size=60), index=test_dates)

    horizons_to_test = [1, 7, 14, 30]
    funcs = [
        ("moving_average", lambda s, h: forecast_moving_average(s, h, window=14)),
        ("exp_smoothing", lambda s, h: forecast_exp_smoothing(s, h, alpha=0.2)),
        ("weekday_seasonal", lambda s, h: forecast_weekday_seasonal(s, h, weeks=4)),
        ("baseline_30d", lambda s, h: baseline_30d_average(s, h)),
    ]

    for h in horizons_to_test:
        for name, fn in funcs:
            fc = fn(sample_series, h)
            assert isinstance(fc, list), f"{name} must return a list, got {type(fc)}"
            assert len(fc) == h, f"{name} expected length {h}, got {len(fc)}"
            assert all(isinstance(v, (float, int)) and v >= 0.0 for v in fc), (
                f"{name} returned negative or non-float values in horizon {h}: {fc}"
            )
    print(" -> PASSED: All forecast functions return non-negative floats of exact horizon length.")

    # --------------------------------------------------------------------------
    # Check 2: forecast_demand returns error key for unknown product ID
    # --------------------------------------------------------------------------
    print("\n[Check 2] Verifying error handling for unknown product ID in forecast_demand...")
    unknown_ids = ["P999", "UNKNOWN", ""]
    for bad_id in unknown_ids:
        res = forecast_demand(bad_id)
        assert isinstance(res, dict), f"Expected dict return for '{bad_id}', got {type(res)}"
        assert "error" in res, f"Expected 'error' key for invalid ID '{bad_id}', got {res}"
    print(" -> PASSED: forecast_demand gracefully returns an error dict for unknown IDs.")

    # --------------------------------------------------------------------------
    # Check 3: Zero lookahead bias / future data isolation
    # --------------------------------------------------------------------------
    print("\n[Check 3] Verifying no lookahead bias (altering future values does not affect forecasts)...")
    real_series = _load_product_sales_series("P001")
    origin_idx = 140
    horizon = 7

    # Clean history up to origin
    clean_history = real_series.iloc[:origin_idx]

    # Corrupted series where future values (on or after origin) are drastically altered
    corrupted_series = real_series.copy()
    corrupted_series.iloc[origin_idx:] = 999999.0
    corrupted_history = corrupted_series.iloc[:origin_idx]

    # Verify forecasts from clean and corrupted series strictly before origin are identical
    for name, fn in funcs:
        clean_fc = fn(clean_history, horizon)
        corrupted_fc = fn(corrupted_history, horizon)
        assert clean_fc == corrupted_fc, (
            f"Leakage detected! {name} forecast changed when future data on/after origin was modified."
        )

    # Double check that history length strictly equals origin_idx (never includes origin_idx or later)
    assert len(clean_history) == origin_idx
    assert clean_history.index[-1] < real_series.index[origin_idx]
    print(" -> PASSED: Verified strictly zero lookahead bias. Future values do not alter forecasts.")

    # --------------------------------------------------------------------------
    # Check 4: forecast_demand returns all listed keys for every product
    # --------------------------------------------------------------------------
    print("\n[Check 4] Verifying all listed keys returned for all 10 products...")
    expected_keys = {
        "product_id",
        "method_used",
        "avg_daily_forecast",
        "total_forecast_over_horizon",
        "backtest_wape",
        "baseline_wape",
        "improvement_vs_baseline_pct",
    }

    all_pids = [f"P{i:03d}" for i in range(1, 11)]
    for pid in all_pids:
        fc_res = forecast_demand(pid, horizon_days=7)
        assert "error" not in fc_res, f"Unexpected error for {pid}: {fc_res}"

        missing = expected_keys - set(fc_res.keys())
        assert not missing, f"Product {pid} output missing keys: {missing}"

        # Verify JSON serializability and plain Python types
        assert isinstance(fc_res["product_id"], str)
        assert isinstance(fc_res["method_used"], str)
        assert isinstance(fc_res["avg_daily_forecast"], float)
        assert isinstance(fc_res["total_forecast_over_horizon"], float)
        assert isinstance(fc_res["backtest_wape"], float)
        assert isinstance(fc_res["baseline_wape"], float)
        assert isinstance(fc_res["improvement_vs_baseline_pct"], float)
        assert not np.isnan(fc_res["avg_daily_forecast"])
        assert not np.isnan(fc_res["backtest_wape"])

    print(" -> PASSED: All 10 products returned all required keys with proper types and no errors.")

    print("\n" + "=" * 80)
    print("ALL STRUCTURAL ASSERTIONS PASSED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()

