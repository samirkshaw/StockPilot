"""
Demand Forecasting and Rolling-Origin Backtest Module for StockPilot.

Provides:
- Pure forecasting functions: Moving Average, Exponential Smoothing,
  Weekday Seasonal, and 30-Day Baseline.
- Rolling-origin backtesting with train-only hyperparameter tuning.
- Best-method selection based on Weighted Absolute Percentage Error (WAPE).
"""

import os
from typing import Any, Dict, List, Union
import numpy as np
import pandas as pd

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))


def _ensure_series(series: Union[pd.Series, List[float], np.ndarray]) -> pd.Series:
    """Helper to convert input sequences into a clean pandas Series."""
    if isinstance(series, pd.Series):
        return series.astype(float)
    return pd.Series(series, dtype=float)


def forecast_moving_average(
    series: Union[pd.Series, List[float], np.ndarray],
    horizon: int,
    window: int = 14,
) -> List[float]:
    """
    Flat forecast equal to the mean of the last `window` days.

    Args:
        series: Historical daily sales sequence.
        horizon: Number of days ahead to forecast.
        window: Number of recent days to average (default: 14).

    Returns:
        List of non-negative floats of length `horizon`.
    """
    s = _ensure_series(series)
    if len(s) == 0:
        return [0.0] * max(0, horizon)

    recent = s.iloc[-min(window, len(s)) :]
    mean_val = max(0.0, float(recent.mean()))
    return [mean_val] * max(0, horizon)


def forecast_exp_smoothing(
    series: Union[pd.Series, List[float], np.ndarray],
    horizon: int,
    alpha: float,
) -> List[float]:
    """
    Simple exponential smoothing (SES) flat forecast equal to the final smoothed level.

    Formula:
        S_0 = Y_0
        S_t = alpha * Y_t + (1 - alpha) * S_{t-1}

    Args:
        series: Historical daily sales sequence.
        horizon: Number of days ahead to forecast.
        alpha: Smoothing factor between 0.0 and 1.0.

    Returns:
        List of non-negative floats of length `horizon`.
    """
    s = _ensure_series(series)
    if len(s) == 0:
        return [0.0] * max(0, horizon)

    vals = s.values
    level = float(vals[0])
    for y in vals[1:]:
        level = alpha * float(y) + (1.0 - alpha) * level

    final_level = max(0.0, float(level))
    return [final_level] * max(0, horizon)


def forecast_weekday_seasonal(
    series: Union[pd.Series, List[float], np.ndarray],
    horizon: int,
    weeks: int = 4,
) -> List[float]:
    """
    Weekday seasonal forecast. For each forecast day, computes the mean of
    that same day-of-week over the last `weeks` occurrences.

    Args:
        series: Historical daily sales sequence. If index is DatetimeIndex, uses
                actual calendar weekdays; otherwise assumes sequential daily entries.
        horizon: Number of days ahead to forecast.
        weeks: Number of recent matching weekday occurrences to average (default: 4).

    Returns:
        List of non-negative floats of length `horizon`.
    """
    s = _ensure_series(series)
    if len(s) == 0:
        return [0.0] * max(0, horizon)

    forecast: List[float] = []

    if isinstance(s.index, pd.DatetimeIndex):
        last_date = s.index[-1]
        for step in range(1, horizon + 1):
            target_date = last_date + pd.Timedelta(days=step)
            target_dow = target_date.dayofweek
            matching = s[s.index.dayofweek == target_dow]
            if len(matching) > 0:
                val = max(0.0, float(matching.tail(weeks).mean()))
            else:
                val = max(0.0, float(s.tail(14).mean()))
            forecast.append(val)
    else:
        # Fallback for plain array/Series without DatetimeIndex:
        # assume consecutive daily ordering where index modulo 7 represents day-of-week
        n = len(s)
        for step in range(1, horizon + 1):
            target_dow = (n - 1 + step) % 7
            matching_indices = [i for i in range(n) if i % 7 == target_dow]
            if matching_indices:
                recent_indices = matching_indices[-weeks:]
                val = max(0.0, float(s.iloc[recent_indices].mean()))
            else:
                val = max(0.0, float(s.tail(14).mean()))
            forecast.append(val)

    return forecast


def baseline_30d_average(
    series: Union[pd.Series, List[float], np.ndarray],
    horizon: int,
) -> List[float]:
    """
    Flat forecast equal to the mean of the last 30 days.

    Args:
        series: Historical daily sales sequence.
        horizon: Number of days ahead to forecast.

    Returns:
        List of non-negative floats of length `horizon`.
    """
    s = _ensure_series(series)
    if len(s) == 0:
        return [0.0] * max(0, horizon)

    recent = s.iloc[-min(30, len(s)) :]
    mean_val = max(0.0, float(recent.mean()))
    return [mean_val] * max(0, horizon)


def _load_product_sales_series(product_id: str) -> pd.Series:
    """Load sales history for a product as a date-indexed Series."""
    sales_path = os.path.join(DATA_DIR, "sales_history.csv")
    if not os.path.exists(sales_path):
        raise FileNotFoundError(f"Sales history file not found at {sales_path}")

    df = pd.read_csv(sales_path)
    norm_id = product_id.strip().upper()
    pdf = df[df["product_id"].str.upper() == norm_id].copy()
    if pdf.empty:
        raise KeyError(f"Product ID '{product_id}' not found in sales history.")

    pdf["date"] = pd.to_datetime(pdf["date"])
    pdf = pdf.sort_values("date").reset_index(drop=True)
    return pdf.set_index("date")["units_sold"].astype(float)


def _tune_ses_alpha(train_series: pd.Series, alpha_grid: List[float] = [0.1, 0.2, 0.3, 0.5, 0.7]) -> float:
    """
    Tune SES alpha strictly on training data using 1-step-ahead forecast error (WAPE).
    No test window data is accessed.
    """
    train_vals = train_series.values
    if len(train_vals) < 2:
        return 0.2

    best_alpha = alpha_grid[0]
    best_wape = float("inf")
    tot_actual = float(np.sum(train_vals[1:]))
    if tot_actual == 0:
        return 0.1

    for alpha in alpha_grid:
        level = float(train_vals[0])
        abs_err = 0.0
        for y in train_vals[1:]:
            abs_err += abs(float(y) - level)
            level = alpha * float(y) + (1.0 - alpha) * level
        wape = abs_err / tot_actual
        if wape < best_wape:
            best_wape = wape
            best_alpha = alpha

    return best_alpha


def backtest_product(
    product_id: str,
    horizon: int = 7,
    test_days: int = 60,
) -> Dict[str, Any]:
    """
    Perform a rolling-origin backtest for a product across candidate forecast methods.

    Evaluates:
    - Moving Average (14-day)
    - Simple Exponential Smoothing (alpha tuned only on pre-test data)
    - Weekday Seasonal (4-week matching weekday mean)
    - Baseline 30-Day Average

    Args:
        product_id: Identifier of the product (e.g., 'P001').
        horizon: Forecast horizon in days (default: 7).
        test_days: Number of days at the end of the history used for testing (default: 60).

    Returns:
        dict: Performance metrics per method (MAE, WAPE, bias), best_method,
              and improvement_vs_baseline_pct.
    """
    series = _load_product_sales_series(product_id)
    n = len(series)
    if n <= test_days + horizon:
        raise ValueError(f"Series length {n} is too short for test_days={test_days} and horizon={horizon}")

    # Start of test evaluation window
    start_origin = n - test_days
    # Maximum origin index such that origin + horizon <= n
    end_origin = n - horizon

    # Tune alpha strictly on data prior to the test window (first 120 days)
    train_series = series.iloc[:start_origin]
    tuned_alpha = _tune_ses_alpha(train_series)

    methods = ["moving_average", "exp_smoothing", "weekday_seasonal", "baseline_30d"]
    stats: Dict[str, Dict[str, float]] = {
        m: {"abs_err": 0.0, "tot_actual": 0.0, "err_sum": 0.0, "count": 0} for m in methods
    }

    # Rolling origin loop: origin index 't' uses strictly data before index 't'
    for t in range(start_origin, end_origin + 1):
        history = series.iloc[:t]
        actual = series.iloc[t : t + horizon].values
        actual_sum = float(np.sum(actual))
        h_len = len(actual)

        fcs = {
            "moving_average": forecast_moving_average(history, horizon, window=14),
            "exp_smoothing": forecast_exp_smoothing(history, horizon, alpha=tuned_alpha),
            "weekday_seasonal": forecast_weekday_seasonal(history, horizon, weeks=4),
            "baseline_30d": baseline_30d_average(history, horizon),
        }

        for m in methods:
            fc_arr = np.array(fcs[m], dtype=float)
            diff = fc_arr - actual
            stats[m]["abs_err"] += float(np.sum(np.abs(diff)))
            stats[m]["tot_actual"] += actual_sum
            stats[m]["err_sum"] += float(np.sum(diff))
            stats[m]["count"] += h_len

    metrics: Dict[str, Dict[str, float]] = {}
    for m in methods:
        tot_act = stats[m]["tot_actual"]
        wape = (stats[m]["abs_err"] / tot_act * 100.0) if tot_act > 0 else 0.0
        mae = stats[m]["abs_err"] / stats[m]["count"] if stats[m]["count"] > 0 else 0.0
        bias = stats[m]["err_sum"] / stats[m]["count"] if stats[m]["count"] > 0 else 0.0
        metrics[m] = {
            "mae": round(float(mae), 4),
            "wape": round(float(wape), 2),
            "bias": round(float(bias), 4),
        }

    # Best method has the lowest WAPE
    best_method = min(methods, key=lambda m: metrics[m]["wape"])
    baseline_wape = metrics["baseline_30d"]["wape"]
    best_wape = metrics[best_method]["wape"]

    # Improvement in percentage points lower than baseline
    improvement = round(max(0.0, baseline_wape - best_wape), 2)

    return {
        "product_id": product_id.strip().upper(),
        "tuned_alpha": tuned_alpha,
        "metrics": metrics,
        "moving_average": metrics["moving_average"],
        "exp_smoothing": metrics["exp_smoothing"],
        "weekday_seasonal": metrics["weekday_seasonal"],
        "baseline_30d": metrics["baseline_30d"],
        "best_method": best_method,
        "baseline_wape": baseline_wape,
        "best_wape": best_wape,
        "improvement_vs_baseline_pct": improvement,
    }


def forecast_demand(product_id: str, horizon_days: int = 7) -> Dict[str, Any]:
    """
    Run backtest, select best forecasting method by WAPE, and generate final forecast.

    Args:
        product_id: Identifier of the product (e.g., 'P001').
        horizon_days: Number of future days to forecast (default: 7).

    Returns:
        dict: JSON-serializable dictionary with:
            - product_id (str)
            - method_used (str)
            - avg_daily_forecast (float)
            - total_forecast_over_horizon (float)
            - backtest_wape (float)
            - baseline_wape (float)
            - improvement_vs_baseline_pct (float)
        If product_id is invalid or missing, returns {"error": "..."}.
    """
    if not product_id or not isinstance(product_id, str):
        return {"error": "Invalid product_id. Must be a non-empty string."}

    norm_id = product_id.strip().upper()

    try:
        series = _load_product_sales_series(norm_id)
    except (FileNotFoundError, KeyError) as e:
        return {"error": str(e)}

    # Run backtest to select optimal method
    bt_res = backtest_product(norm_id, horizon=horizon_days, test_days=60)
    best_method = bt_res["best_method"]
    tuned_alpha = bt_res["tuned_alpha"]

    # Generate final forecast using all historical data
    if best_method == "moving_average":
        fc_values = forecast_moving_average(series, horizon=horizon_days, window=14)
    elif best_method == "exp_smoothing":
        fc_values = forecast_exp_smoothing(series, horizon=horizon_days, alpha=tuned_alpha)
    elif best_method == "weekday_seasonal":
        fc_values = forecast_weekday_seasonal(series, horizon=horizon_days, weeks=4)
    else:
        fc_values = baseline_30d_average(series, horizon=horizon_days)

    avg_daily = float(np.mean(fc_values))
    total_fc = float(np.sum(fc_values))

    return {
        "product_id": norm_id,
        "method_used": str(best_method),
        "avg_daily_forecast": round(avg_daily, 2),
        "total_forecast_over_horizon": round(total_fc, 2),
        "backtest_wape": round(float(bt_res["best_wape"]), 2),
        "baseline_wape": round(float(bt_res["baseline_wape"]), 2),
        "improvement_vs_baseline_pct": round(float(bt_res["improvement_vs_baseline_pct"]), 2),
    }

