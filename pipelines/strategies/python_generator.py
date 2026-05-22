from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from core.config.settings import load_settings
from pipelines.backtest.validation import resolve_freshness_policy_request, validate_backtest_inputs
from pipelines.data_mart.storage.repository import get_prices


SUPPORTED_FAMILIES = {"supertrend", "moving_average_crossover", "rsi_reversion"}
PYTHON_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "family": {"type": "string"},
        "rationale": {"type": "string"},
        "parameters": {"type": "object"},
        "search_space": {"type": "object"},
    },
    "required": ["family", "rationale", "parameters", "search_space"],
}
SYSTEM_PROMPT = """
You translate natural-language trading strategy intent into a safe FinGPT Python strategy plan.
Return JSON only. Supported family values: supertrend, moving_average_crossover, rsi_reversion.
Do not return executable code. The backend renders validated Python from the selected family.
Prefer next-bar execution, explicit costs, visible entry/exit markers, and auditable parameter ranges.
""".strip()


@dataclass(frozen=True)
class PythonStrategyRunRequest:
    prompt: str
    ticker: str = "SPY"
    start_date: str | None = None
    end_date: str | None = None
    lookback_days: int = 756
    use_local_llm: bool = True
    timeout_s: float = 120.0
    optimize: bool = True
    max_trials: int = 16
    random_seed: int = 42
    freshness_profile: str = "research_default"
    require_fresh_prices: bool = False
    max_market_calendar_lag_days: int = 3
    parameter_overrides: dict[str, Any] | None = None
    search_space: dict[str, list[Any]] | None = None


def run_python_strategy_lab(request: PythonStrategyRunRequest) -> dict[str, Any]:
    prompt = str(request.prompt or "").strip()
    ticker = _clean_ticker(request.ticker)
    plan = _strategy_plan_from_prompt(
        prompt,
        use_local_llm=bool(request.use_local_llm),
        timeout_s=float(request.timeout_s or 120.0),
        parameter_overrides=dict(request.parameter_overrides or {}),
        search_space_override=dict(request.search_space or {}),
    )
    manifest = _manifest_for_plan(plan)
    code = render_python_strategy_code(plan, manifest)
    validation = validate_python_strategy_code(code, manifest)
    rows = _load_rows(
        ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        limit=max(120, int(request.lookback_days or 756)),
    )
    freshness_policy = resolve_freshness_policy_request(
        {
            "freshness_profile": request.freshness_profile,
            "require_fresh_prices": request.require_fresh_prices,
            "max_market_calendar_lag_days": request.max_market_calendar_lag_days,
        }
    )
    freshness = validate_backtest_inputs({ticker: rows}, **freshness_policy)
    warnings = list(plan.get("warnings") or [])
    if freshness.get("strict_freshness_violation"):
        warnings.append("strict_freshness_violation")
    if not validation.get("valid"):
        warnings.append("python_code_validation_failed")
    backtest = backtest_python_strategy(
        rows,
        plan["parameters"],
        ticker=ticker,
        family=plan["family"],
        allow_failed=not bool(validation.get("valid")) or bool(freshness.get("strict_freshness_violation")),
    )
    optimization = {}
    if request.optimize and backtest.get("status") != "failed":
        optimization = optimize_python_strategy(
            rows,
            plan,
            manifest,
            ticker=ticker,
            max_trials=int(request.max_trials or 16),
            random_seed=int(request.random_seed or 42),
        )
    robustness = {}
    if backtest.get("status") != "failed":
        robustness = validate_python_strategy_robustness(
            rows,
            plan,
            manifest,
            optimization=optimization,
            ticker=ticker,
            max_trials=max(4, min(int(request.max_trials or 16), 16)),
            random_seed=int(request.random_seed or 42),
        )
    explanation = explain_python_strategy_result(
        plan,
        manifest,
        validation=validation,
        freshness=freshness,
        backtest=backtest,
        optimization=optimization,
        robustness=robustness,
    )
    return {
        "status": "success" if backtest.get("status") == "success" and validation.get("valid") else "partial",
        "language": "python",
        "family": plan["family"],
        "ticker": ticker,
        "prompt": prompt,
        "model_status": plan.get("model_status") or "deterministic_template",
        "llm_diagnostics": dict(plan.get("llm_diagnostics") or {}),
        "rationale": plan.get("rationale") or "",
        "code": code,
        "parameter_manifest": manifest,
        "parameters": plan["parameters"],
        "search_space": plan["search_space"],
        "validation": validation,
        "freshness": {
            "status": "failed" if freshness.get("strict_freshness_violation") else "success",
            "policy": dict(freshness.get("freshness_policy") or {}),
            "price_counts": dict(freshness.get("price_counts") or {}),
            "latest_dates": dict(freshness.get("latest_dates") or {}),
            "expected_latest_date": str(freshness.get("expected_latest_date") or "unknown"),
            "stale_assets": list(freshness.get("stale_assets") or []),
            "missing_assets": list(freshness.get("missing_assets") or []),
        },
        "backtest": backtest,
        "optimization": optimization,
        "robustness_validation": robustness,
        "explanation": explanation,
        "warnings": _unique_strings(
            warnings
            + list(backtest.get("warnings") or [])
            + list(optimization.get("warnings") or [])
            + list(robustness.get("warnings") or [])
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def render_python_strategy_code(plan: dict[str, Any], manifest: list[dict[str, Any]]) -> str:
    defaults = {item["name"]: item.get("default") for item in manifest}
    defaults.update(plan.get("parameters") or {})
    family = str(plan.get("family") or "supertrend")
    if family == "moving_average_crossover":
        return _render_moving_average_code(defaults)
    if family == "rsi_reversion":
        return _render_rsi_reversion_code(defaults)
    return f'''# Generated by FinGPT Python Strategy Lab.
# Strategy family: {family}
# Execution: signal is confirmed on one bar and executed on the next bar.
# The backend validates this source and backtests it through the same parameter manifest below.

PARAMETERS = {json.dumps(defaults, ensure_ascii=False, indent=4, sort_keys=True)}


def strategy_parameters():
    return PARAMETERS.copy()


def compute_atr(rows, length):
    true_ranges = []
    for idx, row in enumerate(rows):
        prev_close = rows[idx - 1]["close"] if idx else row["close"]
        true_ranges.append(max(row["high"] - row["low"], abs(row["high"] - prev_close), abs(row["low"] - prev_close)))
    out = []
    for idx, value in enumerate(true_ranges):
        if idx == 0:
            out.append(value)
        elif idx < length:
            out.append(sum(true_ranges[: idx + 1]) / (idx + 1))
        else:
            out.append((out[-1] * (length - 1) + value) / length)
    return out


def compute_supertrend(rows, atr, factor):
    trend = []
    line = []
    final_upper = 0.0
    final_lower = 0.0
    current_trend = -1
    current_line = 0.0
    for idx, row in enumerate(rows):
        hl2 = (row["high"] + row["low"]) / 2.0
        upper = hl2 + factor * atr[idx]
        lower = hl2 - factor * atr[idx]
        if idx == 0:
            final_upper, final_lower = upper, lower
            current_line = upper
            trend.append(current_trend)
            line.append(current_line)
            continue
        prev_close = rows[idx - 1]["close"]
        final_upper = upper if upper < final_upper or prev_close > final_upper else final_upper
        final_lower = lower if lower > final_lower or prev_close < final_lower else final_lower
        if current_line == final_upper:
            if row["close"] <= final_upper:
                current_trend = -1
                current_line = final_upper
            else:
                current_trend = 1
                current_line = final_lower
        else:
            if row["close"] >= final_lower:
                current_trend = 1
                current_line = final_lower
            else:
                current_trend = -1
                current_line = final_upper
        trend.append(current_trend)
        line.append(current_line)
    return line, trend


def generate_signals(rows, params=None):
    params = {{**PARAMETERS, **(params or {{}})}}
    atr = compute_atr(rows, int(params["atr_period"]))
    supertrend, trend = compute_supertrend(rows, atr, float(params["factor"]))
    signals = []
    for idx in range(1, len(rows)):
        long_signal = trend[idx] == 1 and trend[idx - 1] == -1 and bool(params["enable_long"])
        short_signal = trend[idx] == -1 and trend[idx - 1] == 1 and bool(params["enable_short"])
        signals.append({{
            "date": rows[idx]["date"],
            "supertrend": supertrend[idx],
            "trend": trend[idx],
            "long_signal": long_signal,
            "short_signal": short_signal,
        }})
    return signals
'''


def _render_moving_average_code(defaults: dict[str, Any]) -> str:
    return f'''# Generated by FinGPT Python Strategy Lab.
# Strategy family: moving_average_crossover
# Execution: signal is confirmed on one bar and executed on the next bar.

PARAMETERS = {json.dumps(defaults, ensure_ascii=False, indent=4, sort_keys=True)}


def strategy_parameters():
    return PARAMETERS.copy()


def simple_moving_average(values, window):
    out = []
    for idx, _ in enumerate(values):
        start = max(0, idx - window + 1)
        sample = values[start : idx + 1]
        out.append(sum(sample) / len(sample))
    return out


def generate_signals(rows, params=None):
    params = {{**PARAMETERS, **(params or {{}})}}
    closes = [row["close"] for row in rows]
    fast = simple_moving_average(closes, int(params["fast_window"]))
    slow = simple_moving_average(closes, int(params["slow_window"]))
    signals = []
    for idx in range(1, len(rows)):
        long_signal = fast[idx] > slow[idx] and fast[idx - 1] <= slow[idx - 1] and bool(params["enable_long"])
        short_signal = fast[idx] < slow[idx] and fast[idx - 1] >= slow[idx - 1] and bool(params["enable_short"])
        signals.append({{
            "date": rows[idx]["date"],
            "fast_ma": fast[idx],
            "slow_ma": slow[idx],
            "long_signal": long_signal,
            "short_signal": short_signal,
        }})
    return signals
'''


def _render_rsi_reversion_code(defaults: dict[str, Any]) -> str:
    return f'''# Generated by FinGPT Python Strategy Lab.
# Strategy family: rsi_reversion
# Execution: signal is confirmed on one bar and executed on the next bar.

PARAMETERS = {json.dumps(defaults, ensure_ascii=False, indent=4, sort_keys=True)}


def strategy_parameters():
    return PARAMETERS.copy()


def compute_rsi(values, length):
    if not values:
        return []
    out = [50.0]
    avg_gain = 0.0
    avg_loss = 0.0
    for idx in range(1, len(values)):
        change = values[idx] - values[idx - 1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        if idx <= length:
            avg_gain = (avg_gain * (idx - 1) + gain) / idx
            avg_loss = (avg_loss * (idx - 1) + loss) / idx
        else:
            avg_gain = (avg_gain * (length - 1) + gain) / length
            avg_loss = (avg_loss * (length - 1) + loss) / length
        rs = avg_gain / avg_loss if avg_loss else 100.0
        out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def generate_signals(rows, params=None):
    params = {{**PARAMETERS, **(params or {{}})}}
    closes = [row["close"] for row in rows]
    rsi = compute_rsi(closes, int(params["rsi_period"]))
    signals = []
    for idx in range(1, len(rows)):
        long_signal = rsi[idx] <= float(params["oversold"]) and bool(params["enable_long"])
        short_signal = rsi[idx] >= float(params["overbought"]) and bool(params["enable_short"])
        exit_long = rsi[idx] >= float(params["exit_rsi"])
        exit_short = rsi[idx] <= float(params["exit_rsi"])
        signals.append({{
            "date": rows[idx]["date"],
            "rsi": rsi[idx],
            "long_signal": long_signal,
            "short_signal": short_signal,
            "exit_long": exit_long,
            "exit_short": exit_short,
        }})
    return signals
'''


def validate_python_strategy_code(code: str, manifest: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"valid": False, "syntax_valid": False, "warnings": [f"syntax_error:{exc.msg}"]}
    imports: list[str] = []
    functions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.extend(alias.name for alias in getattr(node, "names", []))
        if isinstance(node, ast.FunctionDef):
            functions.add(node.name)
    missing = [name for name in ["strategy_parameters", "generate_signals"] if name not in functions]
    if missing:
        warnings.append(f"missing_interface:{','.join(missing)}")
    manifest_names = [str(item.get("name") or "") for item in manifest]
    return {
        "valid": not missing,
        "syntax_valid": True,
        "interface_valid": not missing,
        "allowed_imports": imports == [],
        "imports": imports,
        "manifest_parameter_count": len(manifest_names),
        "manifest_parameters": manifest_names,
        "warnings": warnings,
    }


def backtest_python_strategy(
    raw_rows: list[dict[str, Any]],
    parameters: dict[str, Any],
    *,
    ticker: str,
    family: str = "supertrend",
    allow_failed: bool = False,
) -> dict[str, Any]:
    rows = [_ohlc_row(row) for row in raw_rows]
    min_rows = max(40, int(parameters.get("atr_period") or 10) * 4)
    if allow_failed:
        return _failed_backtest(ticker, "validation_failed_before_backtest")
    if family not in SUPPORTED_FAMILIES:
        return _failed_backtest(ticker, f"unsupported_family:{family}")
    if family == "moving_average_crossover":
        return _backtest_moving_average_strategy(rows, parameters, ticker=ticker)
    if family == "rsi_reversion":
        return _backtest_rsi_reversion_strategy(rows, parameters, ticker=ticker)
    if len(rows) < min_rows:
        return _failed_backtest(ticker, f"not_enough_price_history:{len(rows)}<{min_rows}")
    params = _normalize_supertrend_parameters(parameters)
    atr = _atr_series(rows, int(params["atr_period"]))
    supertrend, trend = _supertrend_series(rows, atr, float(params["factor"]))
    fee = (float(params["transaction_cost_bps"]) + float(params["slippage_bps"])) / 10000.0
    equity = 1.0
    peak = 1.0
    position = 0
    entry_price = 0.0
    entry_date = ""
    exposure_bars = 0
    returns: list[float] = []
    trades: list[dict[str, Any]] = []
    chart_rows: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    drawdown_curve: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    for idx in range(1, len(rows)):
        row = rows[idx]
        prev = rows[idx - 1]
        if position:
            exposure_bars += 1
        bar_return = _position_return(position, prev["close"], row["close"])
        equity *= 1.0 + bar_return
        returns.append(bar_return)
        signal_idx = idx - 1
        long_signal = signal_idx > 0 and trend[signal_idx] == 1 and trend[signal_idx - 1] == -1 and bool(params["enable_long"])
        short_signal = signal_idx > 0 and trend[signal_idx] == -1 and trend[signal_idx - 1] == 1 and bool(params["enable_short"])
        action = ""
        exit_reason = ""
        exec_price = row["open"] or row["close"]

        if position and bool(params["use_sltp"]):
            if position == 1:
                stop = entry_price * (1.0 - float(params["stop_loss_pct"]) / 100.0)
                limit = entry_price * (1.0 + float(params["take_profit_pct"]) / 100.0)
                if row["low"] <= stop:
                    exec_price = stop
                    exit_reason = "stop_loss"
                elif row["high"] >= limit:
                    exec_price = limit
                    exit_reason = "take_profit"
            elif position == -1:
                stop = entry_price * (1.0 + float(params["stop_loss_pct"]) / 100.0)
                limit = entry_price * (1.0 - float(params["take_profit_pct"]) / 100.0)
                if row["high"] >= stop:
                    exec_price = stop
                    exit_reason = "stop_loss"
                elif row["low"] <= limit:
                    exec_price = limit
                    exit_reason = "take_profit"

        if not exit_reason and position == 1 and short_signal:
            exit_reason = "supertrend_flip_bearish"
        elif not exit_reason and position == -1 and long_signal:
            exit_reason = "supertrend_flip_bullish"

        if exit_reason and position:
            pnl_pct = _trade_pnl(position, entry_price, exec_price) - fee
            equity *= 1.0 - fee
            trades.append(
                {
                    "ticker": ticker,
                    "side": "long" if position == 1 else "short",
                    "entry_date": entry_date,
                    "exit_date": row["date"],
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(exec_price, 6),
                    "pnl_pct": round(pnl_pct, 8),
                    "exit_reason": exit_reason,
                }
            )
            markers.append(
                {
                    "date": row["date"],
                    "price": round(exec_price, 6),
                    "kind": "exit",
                    "side": "long" if position == 1 else "short",
                    "reason": exit_reason,
                }
            )
            position = 0
            entry_price = 0.0
            entry_date = ""
            action = "exit"

        if long_signal and position <= 0:
            position = 1
            entry_price = exec_price
            entry_date = row["date"]
            equity *= 1.0 - fee
            action = "enter_long"
            markers.append({"date": row["date"], "price": round(exec_price, 6), "kind": "entry", "side": "long", "reason": "supertrend_flip_bullish"})
        elif short_signal and position >= 0:
            position = -1
            entry_price = exec_price
            entry_date = row["date"]
            equity *= 1.0 - fee
            action = "enter_short"
            markers.append({"date": row["date"], "price": round(exec_price, 6), "kind": "entry", "side": "short", "reason": "supertrend_flip_bearish"})

        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak else 0.0
        row_payload = {
            "date": row["date"],
            "open": round(row["open"], 6),
            "high": round(row["high"], 6),
            "low": round(row["low"], 6),
            "close": round(row["close"], 6),
            "supertrend": round(supertrend[idx], 6),
            "trend": "bullish" if trend[idx] == 1 else "bearish",
            "position": position,
            "equity": round(equity, 8),
            "drawdown": round(drawdown, 8),
            "action": action,
        }
        chart_rows.append(row_payload)
        equity_curve.append({"date": row["date"], "equity": round(equity, 8)})
        drawdown_curve.append({"date": row["date"], "drawdown": round(drawdown, 8)})

    metrics = _metrics_from_returns(returns, trades, drawdown_curve, exposure_bars=exposure_bars, total_bars=max(len(rows) - 1, 1), ending_equity=equity)
    run_id = _make_id("pystrat", ticker, params, rows[0]["date"], rows[-1]["date"])
    warnings = []
    if metrics["trade_count"] < 2:
        warnings.append("low_trade_count")
    visible_chart_rows = chart_rows[-500:]
    return {
        "run_id": run_id,
        "status": "success",
        "ticker": ticker,
        "family": family,
        "date_range": {"start": rows[0]["date"], "end": rows[-1]["date"]},
        "metrics": metrics,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trades": trades,
        "chart": {
            "rows": visible_chart_rows,
            "markers": markers[-200:],
            "trade_paths": _trade_paths_for_chart(trades, visible_chart_rows),
            "indicators": {
                "overlays": [{"key": "supertrend", "label": "Supertrend", "class_name": "python-supertrend-line"}],
                "panels": [],
            },
        },
        "warnings": warnings,
        "diagnostics": {
            "lookahead_safe": True,
            "execution_assumption": "signal_confirmed_previous_bar_next_bar_open",
            "data_source": "data_mart:prices_daily",
            "price_rows": len(rows),
            "parameter_hash": _hash_payload(params),
        },
    }


def _backtest_moving_average_strategy(rows: list[dict[str, Any]], parameters: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    params = _normalize_moving_average_parameters(parameters)
    min_rows = max(40, int(params["slow_window"]) + 5)
    if len(rows) < min_rows:
        return _failed_backtest(ticker, f"not_enough_price_history:{len(rows)}<{min_rows}")
    closes = [row["close"] for row in rows]
    fast = _sma_series(closes, int(params["fast_window"]))
    slow = _sma_series(closes, int(params["slow_window"]))
    signals: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if idx == 0:
            signals.append({"date": row["date"], "fast_ma": fast[idx], "slow_ma": slow[idx]})
            continue
        signals.append(
            {
                "date": row["date"],
                "fast_ma": fast[idx],
                "slow_ma": slow[idx],
                "long_signal": fast[idx] > slow[idx] and fast[idx - 1] <= slow[idx - 1] and bool(params["enable_long"]),
                "short_signal": fast[idx] < slow[idx] and fast[idx - 1] >= slow[idx - 1] and bool(params["enable_short"]),
            }
        )
    return _run_indicator_backtest(
        rows,
        params,
        ticker=ticker,
        family="moving_average_crossover",
        signal_rows=signals,
        entry_reasons={"long": "fast_ma_cross_above_slow_ma", "short": "fast_ma_cross_below_slow_ma"},
        exit_reasons={"long": "fast_ma_cross_below_slow_ma", "short": "fast_ma_cross_above_slow_ma"},
        indicators={
            "overlays": [
                {"key": "fast_ma", "label": "단기 MA", "class_name": "python-fast-ma-line"},
                {"key": "slow_ma", "label": "장기 MA", "class_name": "python-slow-ma-line"},
            ],
            "panels": [],
        },
    )


def _backtest_rsi_reversion_strategy(rows: list[dict[str, Any]], parameters: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    params = _normalize_rsi_reversion_parameters(parameters)
    min_rows = max(40, int(params["rsi_period"]) * 4)
    if len(rows) < min_rows:
        return _failed_backtest(ticker, f"not_enough_price_history:{len(rows)}<{min_rows}")
    closes = [row["close"] for row in rows]
    rsi = _rsi_series(closes, int(params["rsi_period"]))
    signals: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        signals.append(
            {
                "date": row["date"],
                "rsi": rsi[idx],
                "long_signal": rsi[idx] <= float(params["oversold"]) and bool(params["enable_long"]),
                "short_signal": rsi[idx] >= float(params["overbought"]) and bool(params["enable_short"]),
                "exit_long": rsi[idx] >= float(params["exit_rsi"]),
                "exit_short": rsi[idx] <= float(params["exit_rsi"]),
            }
        )
    return _run_indicator_backtest(
        rows,
        params,
        ticker=ticker,
        family="rsi_reversion",
        signal_rows=signals,
        entry_reasons={"long": "rsi_oversold_reversion", "short": "rsi_overbought_reversion"},
        exit_reasons={"long": "rsi_exit_mean", "short": "rsi_exit_mean"},
        indicators={
            "overlays": [],
            "panels": [
                {
                    "key": "rsi",
                    "label": "RSI",
                    "min": 0,
                    "max": 100,
                    "oversold": params["oversold"],
                    "overbought": params["overbought"],
                    "exit": params["exit_rsi"],
                }
            ],
        },
    )


def _run_indicator_backtest(
    rows: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    ticker: str,
    family: str,
    signal_rows: list[dict[str, Any]],
    entry_reasons: dict[str, str],
    exit_reasons: dict[str, str],
    indicators: dict[str, Any],
) -> dict[str, Any]:
    fee = (float(params["transaction_cost_bps"]) + float(params["slippage_bps"])) / 10000.0
    equity = 1.0
    peak = 1.0
    position = 0
    entry_price = 0.0
    entry_date = ""
    exposure_bars = 0
    returns: list[float] = []
    trades: list[dict[str, Any]] = []
    chart_rows: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []
    drawdown_curve: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []

    for idx in range(1, len(rows)):
        row = rows[idx]
        prev = rows[idx - 1]
        if position:
            exposure_bars += 1
        bar_return = _position_return(position, prev["close"], row["close"])
        equity *= 1.0 + bar_return
        returns.append(bar_return)
        signal = signal_rows[idx - 1] if idx - 1 < len(signal_rows) else {}
        long_signal = bool(signal.get("long_signal"))
        short_signal = bool(signal.get("short_signal"))
        exit_long_signal = bool(signal.get("exit_long")) or short_signal
        exit_short_signal = bool(signal.get("exit_short")) or long_signal
        action = ""
        exit_reason = ""
        exec_price = row["open"] or row["close"]

        if position and bool(params.get("use_sltp")):
            if position == 1:
                stop = entry_price * (1.0 - float(params["stop_loss_pct"]) / 100.0)
                limit = entry_price * (1.0 + float(params["take_profit_pct"]) / 100.0)
                if row["low"] <= stop:
                    exec_price = stop
                    exit_reason = "stop_loss"
                elif row["high"] >= limit:
                    exec_price = limit
                    exit_reason = "take_profit"
            elif position == -1:
                stop = entry_price * (1.0 + float(params["stop_loss_pct"]) / 100.0)
                limit = entry_price * (1.0 - float(params["take_profit_pct"]) / 100.0)
                if row["high"] >= stop:
                    exec_price = stop
                    exit_reason = "stop_loss"
                elif row["low"] <= limit:
                    exec_price = limit
                    exit_reason = "take_profit"

        if not exit_reason and position == 1 and exit_long_signal:
            exit_reason = exit_reasons["long"]
        elif not exit_reason and position == -1 and exit_short_signal:
            exit_reason = exit_reasons["short"]

        if exit_reason and position:
            pnl_pct = _trade_pnl(position, entry_price, exec_price) - fee
            equity *= 1.0 - fee
            side = "long" if position == 1 else "short"
            trades.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "entry_date": entry_date,
                    "exit_date": row["date"],
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(exec_price, 6),
                    "pnl_pct": round(pnl_pct, 8),
                    "exit_reason": exit_reason,
                }
            )
            markers.append({"date": row["date"], "price": round(exec_price, 6), "kind": "exit", "side": side, "reason": exit_reason})
            position = 0
            entry_price = 0.0
            entry_date = ""
            action = "exit"

        if long_signal and position <= 0:
            position = 1
            entry_price = exec_price
            entry_date = row["date"]
            equity *= 1.0 - fee
            action = "enter_long"
            markers.append({"date": row["date"], "price": round(exec_price, 6), "kind": "entry", "side": "long", "reason": entry_reasons["long"]})
        elif short_signal and position >= 0:
            position = -1
            entry_price = exec_price
            entry_date = row["date"]
            equity *= 1.0 - fee
            action = "enter_short"
            markers.append({"date": row["date"], "price": round(exec_price, 6), "kind": "entry", "side": "short", "reason": entry_reasons["short"]})

        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak else 0.0
        row_payload = {
            "date": row["date"],
            "open": round(row["open"], 6),
            "high": round(row["high"], 6),
            "low": round(row["low"], 6),
            "close": round(row["close"], 6),
            "position": position,
            "equity": round(equity, 8),
            "drawdown": round(drawdown, 8),
            "action": action,
        }
        for key, value in (signal_rows[idx] if idx < len(signal_rows) else signal).items():
            if key == "date" or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                row_payload[key] = round(float(value), 6)
        chart_rows.append(row_payload)
        equity_curve.append({"date": row["date"], "equity": round(equity, 8)})
        drawdown_curve.append({"date": row["date"], "drawdown": round(drawdown, 8)})

    metrics = _metrics_from_returns(returns, trades, drawdown_curve, exposure_bars=exposure_bars, total_bars=max(len(rows) - 1, 1), ending_equity=equity)
    warnings = ["low_trade_count"] if metrics["trade_count"] < 2 else []
    visible_chart_rows = chart_rows[-500:]
    return {
        "run_id": _make_id("pystrat", family, ticker, params, rows[0]["date"], rows[-1]["date"]),
        "status": "success",
        "ticker": ticker,
        "family": family,
        "date_range": {"start": rows[0]["date"], "end": rows[-1]["date"]},
        "metrics": metrics,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trades": trades,
        "chart": {
            "rows": visible_chart_rows,
            "markers": markers[-200:],
            "trade_paths": _trade_paths_for_chart(trades, visible_chart_rows),
            "indicators": indicators,
        },
        "warnings": warnings,
        "diagnostics": {
            "lookahead_safe": True,
            "execution_assumption": "signal_confirmed_previous_bar_next_bar_open",
            "data_source": "data_mart:prices_daily",
            "price_rows": len(rows),
            "parameter_hash": _hash_payload(params),
        },
    }


def optimize_python_strategy(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    manifest: list[dict[str, Any]],
    *,
    ticker: str,
    max_trials: int = 16,
    random_seed: int = 42,
) -> dict[str, Any]:
    params = dict(plan.get("parameters") or {})
    search_space = _search_space_from_manifest(manifest, dict(plan.get("search_space") or {}))
    candidates = _candidate_parameters(search_space, max_trials=max_trials, seed=random_seed)
    backend = "optuna_tpe" if _optuna_available() else "deterministic_surrogate"
    if backend == "optuna_tpe":
        candidates = _optuna_candidates(rows, plan, manifest, ticker=ticker, max_trials=max_trials, seed=random_seed)
    trials = []
    for idx, candidate in enumerate(candidates, start=1):
        candidate_params = {**params, **candidate}
        result = backtest_python_strategy(rows, candidate_params, ticker=ticker, family=plan["family"])
        score = _optimization_score(result.get("metrics") or {})
        trials.append(
            {
                "trial_number": idx,
                "parameters": candidate,
                "score": round(score, 8),
                "metrics": result.get("metrics") or {},
                "status": result.get("status") or "failed",
            }
        )
    if not trials:
        return {"status": "failed", "warnings": ["optimization_produced_no_trials"], "trials": []}
    best = max(trials, key=lambda item: item["score"])
    recommended = _recommended_trial(trials)
    sensitivity = _parameter_sensitivity(trials, manifest)
    return {
        "status": "success",
        "method": "bayesian",
        "bayesian_backend": backend,
        "objective": "sharpe_drawdown_trade_quality",
        "trial_count": len(trials),
        "best_parameters": best["parameters"],
        "recommended_parameters": recommended["parameters"],
        "best_score": best["score"],
        "recommended_score": recommended["score"],
        "trials": trials[: min(len(trials), 40)],
        "parameter_sensitivity": sensitivity,
        "warnings": [],
    }


def validate_python_strategy_robustness(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    manifest: list[dict[str, Any]],
    *,
    optimization: dict[str, Any],
    ticker: str,
    max_trials: int = 12,
    random_seed: int = 42,
) -> dict[str, Any]:
    if len(rows) < 160:
        return {
            "status": "insufficient_data",
            "method": "oos_walk_forward_cost_monte_carlo",
            "warnings": [f"not_enough_rows_for_robustness:{len(rows)}<160"],
            "checks": [],
        }
    base_params = dict(plan.get("parameters") or {})
    recommended_params = {**base_params, **dict(optimization.get("recommended_parameters") or {})}
    search_space = _search_space_from_manifest(manifest, dict(plan.get("search_space") or {}))
    validation_trials = max(4, min(int(max_trials or 12), 24))
    split_index = max(80, min(len(rows) - 60, int(len(rows) * 0.70)))
    train_rows = rows[:split_index]
    oos_rows = rows[split_index:]
    train_pick = _optimize_candidate_slice(train_rows, plan, search_space, ticker=ticker, max_trials=validation_trials, seed=random_seed + 11)
    oos_params = {**base_params, **train_pick.get("parameters", {})}
    train_result = backtest_python_strategy(train_rows, oos_params, ticker=ticker, family=plan["family"])
    oos_result = backtest_python_strategy(oos_rows, oos_params, ticker=ticker, family=plan["family"])
    train_metrics = dict(train_result.get("metrics") or {})
    oos_metrics = dict(oos_result.get("metrics") or {})
    split_validation = {
        "status": "success" if train_result.get("status") == "success" and oos_result.get("status") == "success" else "partial",
        "train_range": _date_range(train_rows),
        "oos_range": _date_range(oos_rows),
        "train_parameters": train_pick.get("parameters") or {},
        "train_score": train_pick.get("score"),
        "train_metrics": train_metrics,
        "oos_metrics": oos_metrics,
        "degradation": _metric_degradation(train_metrics, oos_metrics),
    }
    walk_forward = _walk_forward_segments(rows, plan, search_space, ticker=ticker, max_trials=validation_trials, seed=random_seed + 101)
    cost_stress = _cost_stress_results(rows, plan, recommended_params, ticker=ticker)
    recommended_backtest = backtest_python_strategy(rows, recommended_params, ticker=ticker, family=plan["family"])
    monte_carlo = _monte_carlo_trade_resampling(
        recommended_backtest.get("trades") or [],
        random_seed=random_seed + 503,
    )
    checks = _robustness_checks(split_validation, walk_forward, cost_stress, monte_carlo)
    verdict = _robustness_verdict(checks)
    warnings = [check["warning"] for check in checks if check.get("warning")]
    return {
        "status": "success",
        "method": "oos_walk_forward_cost_monte_carlo",
        "verdict": verdict,
        "recommended_parameters": {key: recommended_params[key] for key in recommended_params if key in _all_parameter_names()},
        "split_validation": split_validation,
        "walk_forward": walk_forward,
        "cost_stress": cost_stress,
        "monte_carlo": monte_carlo,
        "checks": checks,
        "warnings": warnings,
    }


def _optimize_candidate_slice(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    search_space: dict[str, list[Any]],
    *,
    ticker: str,
    max_trials: int,
    seed: int,
) -> dict[str, Any]:
    if not search_space or not rows:
        return {"parameters": {}, "score": 0.0, "metrics": {}, "status": "skipped"}
    base_params = dict(plan.get("parameters") or {})
    candidates = _candidate_parameters(search_space, max_trials=max_trials, seed=seed)
    trials = []
    for idx, candidate in enumerate(candidates, start=1):
        result = backtest_python_strategy(rows, {**base_params, **candidate}, ticker=ticker, family=plan["family"])
        score = _optimization_score(result.get("metrics") or {})
        trials.append(
            {
                "trial_number": idx,
                "parameters": candidate,
                "score": round(score, 8),
                "metrics": result.get("metrics") or {},
                "status": result.get("status") or "failed",
            }
        )
    if not trials:
        return {"parameters": {}, "score": 0.0, "metrics": {}, "status": "failed"}
    recommended = _recommended_trial(trials)
    return {
        "parameters": recommended.get("parameters") or {},
        "score": recommended.get("score"),
        "metrics": recommended.get("metrics") or {},
        "status": recommended.get("status") or "success",
    }


def _walk_forward_segments(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    search_space: dict[str, list[Any]],
    *,
    ticker: str,
    max_trials: int,
    seed: int,
) -> dict[str, Any]:
    n = len(rows)
    test_size = max(50, min(140, n // 5))
    segments: list[dict[str, Any]] = []
    for idx in range(3):
        test_end = n - test_size * (2 - idx)
        test_start = test_end - test_size
        train_end = test_start
        if train_end < 80 or test_start < 0 or test_end > n:
            continue
        train_rows = rows[:train_end]
        test_rows = rows[test_start:test_end]
        pick = _optimize_candidate_slice(train_rows, plan, search_space, ticker=ticker, max_trials=max_trials, seed=seed + idx)
        test_params = {**dict(plan.get("parameters") or {}), **dict(pick.get("parameters") or {})}
        test_result = backtest_python_strategy(test_rows, test_params, ticker=ticker, family=plan["family"])
        train_metrics = dict(pick.get("metrics") or {})
        test_metrics = dict(test_result.get("metrics") or {})
        segments.append(
            {
                "segment": idx + 1,
                "train_range": _date_range(train_rows),
                "test_range": _date_range(test_rows),
                "parameters": pick.get("parameters") or {},
                "train_score": pick.get("score"),
                "train_metrics": train_metrics,
                "test_metrics": test_metrics,
                "degradation": _metric_degradation(train_metrics, test_metrics),
                "status": "success" if test_result.get("status") == "success" else "failed",
            }
        )
    viable = [item for item in segments if item.get("status") == "success"]
    positive = [
        item for item in viable
        if _float_or((item.get("test_metrics") or {}).get("total_return"), 0.0) > 0
        and _float_or((item.get("test_metrics") or {}).get("max_drawdown"), 0.0) > -0.35
    ]
    return {
        "status": "success" if viable else "insufficient_data",
        "segment_count": len(segments),
        "positive_segments": len(positive),
        "pass_rate": round(len(positive) / max(len(segments), 1), 8),
        "segments": segments,
    }


def _cost_stress_results(rows: list[dict[str, Any]], plan: dict[str, Any], params: dict[str, Any], *, ticker: str) -> dict[str, Any]:
    scenarios = []
    base_cost = _float_or(params.get("transaction_cost_bps"), 5.0)
    base_slippage = _float_or(params.get("slippage_bps"), 2.0)
    for multiplier in [1.0, 2.0, 3.0]:
        stressed = {
            **params,
            "transaction_cost_bps": round(base_cost * multiplier, 6),
            "slippage_bps": round(base_slippage * multiplier, 6),
        }
        result = backtest_python_strategy(rows, stressed, ticker=ticker, family=plan["family"])
        scenarios.append(
            {
                "multiplier": multiplier,
                "transaction_cost_bps": stressed["transaction_cost_bps"],
                "slippage_bps": stressed["slippage_bps"],
                "metrics": result.get("metrics") or {},
                "status": result.get("status") or "failed",
            }
        )
    worst_return = min((_float_or((item.get("metrics") or {}).get("total_return"), 0.0) for item in scenarios), default=0.0)
    return {
        "status": "success",
        "scenarios": scenarios,
        "worst_total_return": round(worst_return, 8),
        "passes_3x_cost": bool(scenarios and _float_or((scenarios[-1].get("metrics") or {}).get("total_return"), 0.0) > 0),
    }


def _monte_carlo_trade_resampling(trades: list[dict[str, Any]], *, random_seed: int, simulations: int = 300) -> dict[str, Any]:
    returns = [_float_or(trade.get("pnl_pct"), 0.0) for trade in trades if math.isfinite(_float_or(trade.get("pnl_pct"), 0.0))]
    if len(returns) < 5:
        return {
            "status": "insufficient_trades",
            "trade_count": len(returns),
            "warnings": ["not_enough_trades_for_monte_carlo"],
        }
    rng = random.Random(random_seed)
    ending_returns: list[float] = []
    max_drawdowns: list[float] = []
    for _ in range(max(50, min(int(simulations or 300), 1000))):
        equity = 1.0
        peak = 1.0
        worst_dd = 0.0
        for ret in (rng.choice(returns) for _ in returns):
            equity *= 1.0 + ret
            peak = max(peak, equity)
            worst_dd = min(worst_dd, equity / peak - 1.0 if peak else 0.0)
        ending_returns.append(equity - 1.0)
        max_drawdowns.append(worst_dd)
    ending_returns.sort()
    max_drawdowns.sort()
    return {
        "status": "success",
        "trade_count": len(returns),
        "simulations": len(ending_returns),
        "median_total_return": round(_percentile(ending_returns, 0.50), 8),
        "p05_total_return": round(_percentile(ending_returns, 0.05), 8),
        "p95_total_return": round(_percentile(ending_returns, 0.95), 8),
        "p05_max_drawdown": round(_percentile(max_drawdowns, 0.05), 8),
        "loss_probability": round(sum(1 for value in ending_returns if value < 0) / len(ending_returns), 8),
    }


def _robustness_checks(
    split_validation: dict[str, Any],
    walk_forward: dict[str, Any],
    cost_stress: dict[str, Any],
    monte_carlo: dict[str, Any],
) -> list[dict[str, Any]]:
    oos_metrics = dict((split_validation.get("oos_metrics") or {}))
    oos_return = _float_or(oos_metrics.get("total_return"), 0.0)
    oos_dd = _float_or(oos_metrics.get("max_drawdown"), 0.0)
    pass_rate = _float_or(walk_forward.get("pass_rate"), 0.0)
    cost_pass = bool(cost_stress.get("passes_3x_cost"))
    mc_status = str(monte_carlo.get("status") or "")
    mc_p05 = _float_or(monte_carlo.get("p05_total_return"), 0.0)
    mc_loss = _float_or(monte_carlo.get("loss_probability"), 1.0)
    return [
        {
            "name": "Out-of-sample split",
            "status": "pass" if oos_return > 0 and oos_dd > -0.35 else ("warn" if oos_return > -0.05 else "fail"),
            "detail": f"OOS 수익률 {oos_return:.2%}, 최대 낙폭 {oos_dd:.2%}",
            "warning": "" if oos_return > 0 else "oos_return_non_positive",
        },
        {
            "name": "Walk-forward consistency",
            "status": "pass" if pass_rate >= 0.67 else ("warn" if pass_rate >= 0.34 else "fail"),
            "detail": f"{walk_forward.get('positive_segments') or 0}/{walk_forward.get('segment_count') or 0}개 구간 통과",
            "warning": "" if pass_rate >= 0.34 else "walk_forward_low_pass_rate",
        },
        {
            "name": "3x cost stress",
            "status": "pass" if cost_pass else "warn",
            "detail": f"최악 스트레스 수익률 {_float_or(cost_stress.get('worst_total_return'), 0.0):.2%}",
            "warning": "" if cost_pass else "cost_stress_eroded_return",
        },
        {
            "name": "Monte Carlo resampling",
            "status": "pass" if mc_status == "success" and mc_p05 > -0.20 and mc_loss < 0.35 else ("warn" if mc_status == "success" else "warn"),
            "detail": f"p05 수익률 {mc_p05:.2%}, 손실 확률 {mc_loss:.2%}" if mc_status == "success" else "완료 거래 부족",
            "warning": "" if mc_status == "success" else "monte_carlo_insufficient_trades",
        },
    ]


def _robustness_verdict(checks: list[dict[str, Any]]) -> dict[str, str]:
    statuses = [str(check.get("status") or "") for check in checks]
    if any(status == "fail" for status in statuses):
        return {"status": "reject_or_rework", "label": "재검토 필요", "tone": "fail"}
    if statuses and all(status == "pass" for status in statuses):
        return {"status": "robust_candidate", "label": "강건성 후보", "tone": "ok"}
    return {"status": "needs_more_validation", "label": "추가 검증 필요", "tone": "warn"}


def _date_range(rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {"start": "", "end": ""}
    return {"start": str(rows[0].get("date") or ""), "end": str(rows[-1].get("date") or "")}


def _metric_degradation(train_metrics: dict[str, Any], test_metrics: dict[str, Any]) -> dict[str, float]:
    train_sharpe = _float_or(train_metrics.get("sharpe"), 0.0)
    test_sharpe = _float_or(test_metrics.get("sharpe"), 0.0)
    train_return = _float_or(train_metrics.get("total_return"), 0.0)
    test_return = _float_or(test_metrics.get("total_return"), 0.0)
    train_dd = _float_or(train_metrics.get("max_drawdown"), 0.0)
    test_dd = _float_or(test_metrics.get("max_drawdown"), 0.0)
    return {
        "sharpe_delta": round(test_sharpe - train_sharpe, 8),
        "return_delta": round(test_return - train_return, 8),
        "drawdown_delta": round(test_dd - train_dd, 8),
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    pos = max(0.0, min(1.0, pct)) * (len(values) - 1)
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return values[lower]
    weight = pos - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _trade_paths_for_chart(trades: list[dict[str, Any]], chart_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    date_index = {str(row.get("date") or ""): idx for idx, row in enumerate(chart_rows)}
    paths: list[dict[str, Any]] = []
    for trade_number, trade in enumerate(trades, start=1):
        entry_date = str(trade.get("entry_date") or "")
        exit_date = str(trade.get("exit_date") or "")
        if entry_date not in date_index or exit_date not in date_index:
            continue
        pnl_pct = _float_or(trade.get("pnl_pct"), 0.0)
        paths.append(
            {
                "trade_number": trade_number,
                "side": str(trade.get("side") or "long"),
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": round(_float_or(trade.get("entry_price"), 0.0), 6),
                "exit_price": round(_float_or(trade.get("exit_price"), 0.0), 6),
                "pnl_pct": round(pnl_pct, 8),
                "exit_reason": str(trade.get("exit_reason") or ""),
                "duration_bars": max(1, date_index[exit_date] - date_index[entry_date]),
                "result": "win" if pnl_pct >= 0 else "loss",
            }
        )
    return paths[-120:]


def explain_python_strategy_result(
    plan: dict[str, Any],
    manifest: list[dict[str, Any]],
    *,
    validation: dict[str, Any],
    freshness: dict[str, Any],
    backtest: dict[str, Any],
    optimization: dict[str, Any],
    robustness: dict[str, Any],
) -> dict[str, Any]:
    metrics = dict(backtest.get("metrics") or {})
    family = str(plan.get("family") or "strategy")
    recommended = dict(optimization.get("recommended_parameters") or {})
    best = dict(optimization.get("best_parameters") or {})
    trial_count = int(optimization.get("trial_count") or 0)
    trade_count = int(_float_or(metrics.get("trade_count"), 0.0))
    max_drawdown = _float_or(metrics.get("max_drawdown"), 0.0)
    sharpe = _float_or(metrics.get("sharpe"), 0.0)
    total_return = _float_or(metrics.get("total_return"), 0.0)
    validation_ok = bool(validation.get("valid"))
    freshness_ok = not bool(freshness.get("strict_freshness_violation"))
    optimization_ok = optimization.get("status") == "success"
    robustness_verdict = dict(robustness.get("verdict") or {})
    verdict = _strategy_verdict(
        validation_ok=validation_ok,
        freshness_ok=freshness_ok,
        optimization_ok=optimization_ok,
        robustness_ok=robustness_verdict.get("status") == "robust_candidate",
        trade_count=trade_count,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
    )
    robustness_checks = [
        {
            "name": "Python interface validation",
            "status": "pass" if validation_ok else "fail",
            "detail": "strategy_parameters/generate_signals 인터페이스가 유효합니다" if validation_ok else "생성 코드는 사용 전 검토가 필요합니다",
        },
        {
            "name": "Freshness gate",
            "status": "pass" if freshness_ok else "fail",
            "detail": "가격 데이터가 설정된 신선도 정책을 통과했습니다" if freshness_ok else "엄격한 신선도 정책이 리서치 증거를 차단했습니다",
        },
        {
            "name": "Trade sample",
            "status": "pass" if trade_count >= 5 else ("warn" if trade_count >= 2 else "fail"),
            "detail": f"완료 거래 {trade_count}개; 표본이 적으면 OOS/Walk-forward 확인이 필요합니다",
        },
        {
            "name": "Drawdown guard",
            "status": "pass" if max_drawdown >= -0.20 else ("warn" if max_drawdown >= -0.35 else "fail"),
            "detail": f"최대 낙폭 {max_drawdown:.2%}",
        },
        {
            "name": "Bayesian search",
            "status": "pass" if optimization_ok and trial_count >= 4 else ("warn" if optimization_ok else "fail"),
            "detail": f"{trial_count}회 시도 · 백엔드 {optimization.get('bayesian_backend') or 'not_run'}",
        },
    ]
    robustness_checks.extend(
        {
            "name": check.get("name") or "강건성 검증",
            "status": check.get("status") or "warn",
            "detail": check.get("detail") or "",
        }
        for check in list(robustness.get("checks") or [])
    )
    parameter_insights = _parameter_insights(manifest, plan.get("parameters") or {}, recommended, best)
    reasons = [
        f"백테스트 수익률 {total_return:.2%}, Sharpe {sharpe:.2f}, 최대 낙폭 {max_drawdown:.2%}, 거래 수 {trade_count}개.",
        f"최적화 목적함수 {optimization.get('objective') or 'not_run'} 기준으로 {trial_count}회 시도 중 추천 파라미터를 선택했습니다.",
    ]
    if parameter_insights:
        changed = [item for item in parameter_insights if item.get("direction") != "unchanged"]
        reasons.append(f"{len(changed)}개 최적화 파라미터가 생성 기본값과 달라졌습니다.")
    if trade_count < 5:
        reasons.append("거래 표본이 적으므로 Walk-forward와 OOS 검증을 통과하기 전까지는 리서치 후보로만 취급해야 합니다.")
    elif max_drawdown < -0.35:
        reasons.append("낙폭이 커서 승격 전 반려 또는 더 엄격한 리스크 제어가 필요합니다.")
    elif robustness_verdict:
        reasons.append(f"강건성 검증 판정: {robustness_verdict.get('label') or robustness_verdict.get('status')}.")
    else:
        reasons.append("이 결과는 실행 추천이 아니라 리서치 후보로 검토해야 합니다.")
    summary = (
        f"{_family_label(family)} 전략은 검증된 Python 템플릿으로 생성됐고, "
        f"백테스트/최적화 결과는 {verdict['label']} 상태입니다. "
        f"추천 파라미터는 검증 통과와 비용/손실/거래수 조건을 함께 보고 해석해야 합니다."
    )
    return {
        "source": "verified_backtest_and_optimizer",
        "language": "ko",
        "verdict": verdict,
        "summary": summary,
        "reasons": reasons,
        "parameter_insights": parameter_insights,
        "parameter_sensitivity": list(optimization.get("parameter_sensitivity") or []),
        "robustness_validation": {
            "status": robustness.get("status") or "not_run",
            "verdict": robustness_verdict,
            "method": robustness.get("method") or "",
        },
        "robustness_checks": robustness_checks,
        "next_steps": [
            "Run walk-forward and out-of-sample validation before accepting the strategy.",
            "Stress test commission/slippage above the current cost assumptions.",
            "Reject parameter spikes that only work in a narrow trial neighborhood.",
        ],
    }


def _strategy_verdict(
    *,
    validation_ok: bool,
    freshness_ok: bool,
    optimization_ok: bool,
    robustness_ok: bool,
    trade_count: int,
    max_drawdown: float,
    sharpe: float,
) -> dict[str, str]:
    if not validation_ok or not freshness_ok:
        return {"status": "blocked", "label": "검증 차단", "tone": "fail"}
    if not optimization_ok:
        return {"status": "needs_optimization", "label": "최적화 미완료", "tone": "warn"}
    if trade_count < 2:
        return {"status": "insufficient_sample", "label": "표본 부족", "tone": "warn"}
    if max_drawdown < -0.35:
        return {"status": "risk_reject", "label": "위험 과다", "tone": "fail"}
    if robustness_ok and sharpe > 0.8 and trade_count >= 5 and max_drawdown >= -0.25:
        return {"status": "robust_research_candidate", "label": "강건성 리서치 후보", "tone": "ok"}
    if sharpe > 0.8 and trade_count >= 5 and max_drawdown >= -0.25:
        return {"status": "research_candidate", "label": "리서치 후보", "tone": "ok"}
    return {"status": "review_required", "label": "추가 검증 필요", "tone": "warn"}


def _parameter_insights(
    manifest: list[dict[str, Any]],
    defaults: dict[str, Any],
    recommended: dict[str, Any],
    best: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    manifest_by_name = {str(item.get("name") or ""): item for item in manifest}
    for name, value in recommended.items():
        item = manifest_by_name.get(str(name), {})
        default = defaults.get(name, item.get("default"))
        direction = _parameter_direction(default, value)
        out.append(
            {
                "name": name,
                "label": item.get("label") or name,
                "default": default,
                "recommended": value,
                "best": best.get(name),
                "direction": direction,
                "detail": _parameter_change_detail(item.get("label") or name, default, value, direction),
            }
        )
    return out


def _parameter_sensitivity(trials: list[dict[str, Any]], manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manifest_by_name = {str(item.get("name") or ""): item for item in manifest}
    out: list[dict[str, Any]] = []
    for name in manifest_by_name:
        buckets: dict[str, dict[str, Any]] = {}
        for trial in trials:
            params = trial.get("parameters") or {}
            if name not in params:
                continue
            key = json.dumps(params[name], sort_keys=True, default=str)
            bucket = buckets.setdefault(key, {"value": params[name], "scores": [], "trials": 0})
            bucket["scores"].append(_float_or(trial.get("score"), 0.0))
            bucket["trials"] += 1
        if len(buckets) < 2:
            continue
        values = []
        for bucket in buckets.values():
            scores = bucket["scores"]
            values.append(
                {
                    "value": bucket["value"],
                    "avg_score": round(sum(scores) / max(len(scores), 1), 8),
                    "best_score": round(max(scores), 8),
                    "trials": int(bucket["trials"]),
                }
            )
        values.sort(key=lambda item: (item["avg_score"], item["best_score"]), reverse=True)
        spread = values[0]["avg_score"] - values[-1]["avg_score"]
        out.append(
            {
                "name": name,
                "label": manifest_by_name[name].get("label") or name,
                "best_value": values[0]["value"],
                "worst_value": values[-1]["value"],
                "score_spread": round(spread, 8),
                "values": values[:8],
            }
        )
    out.sort(key=lambda item: abs(_float_or(item.get("score_spread"), 0.0)), reverse=True)
    return out[:8]


def _parameter_direction(default: Any, recommended: Any) -> str:
    if isinstance(default, bool) or isinstance(recommended, bool):
        return "changed" if bool(default) != bool(recommended) else "unchanged"
    default_num = _maybe_float(default)
    recommended_num = _maybe_float(recommended)
    if default_num is not None and recommended_num is not None:
        if abs(default_num - recommended_num) <= 1e-9:
            return "unchanged"
        return "increase" if recommended_num > default_num else "decrease"
    return "changed" if str(default) != str(recommended) else "unchanged"


def _parameter_change_detail(label: str, default: Any, recommended: Any, direction: str) -> str:
    if direction == "unchanged":
        return f"{label}은 생성 기본값({default})을 유지했습니다."
    if direction == "increase":
        return f"{label}은 {default}에서 {recommended}(으)로 높아졌습니다."
    if direction == "decrease":
        return f"{label}은 {default}에서 {recommended}(으)로 낮아졌습니다."
    return f"{label}은 {default}에서 {recommended}(으)로 변경됐습니다."


def _family_label(family: str) -> str:
    labels = {
        "supertrend": "Supertrend",
        "moving_average_crossover": "이동평균 교차",
        "rsi_reversion": "RSI 평균회귀",
    }
    return labels.get(family, family)


def _strategy_plan_from_prompt(
    prompt: str,
    *,
    use_local_llm: bool,
    timeout_s: float,
    parameter_overrides: dict[str, Any],
    search_space_override: dict[str, list[Any]],
) -> dict[str, Any]:
    fallback = _fallback_plan(prompt)
    fallback["parameters"].update(_clean_parameter_overrides(parameter_overrides))
    if search_space_override:
        fallback["search_space"].update(_clean_search_space(search_space_override))
    fallback["search_space"] = _search_space_for_family(fallback["family"], fallback["search_space"])
    if not prompt or not use_local_llm:
        fallback["model_status"] = "deterministic_template"
        fallback["llm_diagnostics"] = _llm_diagnostics(use_local_llm, False, "not_requested", fallback_used=True)
        return fallback
    settings = load_settings()
    model = str(getattr(settings, "primary_model", "") or "qwen2.5:7b")
    base_url = str(getattr(settings, "ollama_base_url", "") or "http://localhost:11434")
    try:
        raw = _call_local_llm_plan(
            base_url=base_url,
            model=model,
            prompt=_plan_prompt(prompt, fallback),
            timeout_s=max(8.0, min(float(timeout_s or 120.0), 180.0)),
        )
        parsed = _extract_json(raw)
        family = str(parsed.get("family") or fallback["family"]).strip().lower()
        if family not in SUPPORTED_FAMILIES:
            family = fallback["family"]
        family_warnings: list[str] = []
        prompt_family = _explicit_family_from_prompt(str(prompt or "").lower())
        if prompt_family and prompt_family != family:
            family_warnings.append(f"llm_family_overridden_by_prompt:{family}->{prompt_family}")
            family = prompt_family
        params = {**fallback["parameters"], **_clean_parameter_overrides(parsed.get("parameters") or {}), **_clean_parameter_overrides(parameter_overrides)}
        search_space = {**fallback["search_space"], **_clean_search_space(parsed.get("search_space") or {}), **_clean_search_space(search_space_override)}
        return {
            "family": family,
            "rationale": str(parsed.get("rationale") or fallback["rationale"]).strip(),
            "parameters": _normalize_parameters_for_family(family, params),
            "search_space": _search_space_for_family(family, search_space),
            "model_status": "local_llm_plan_template_python",
            "llm_diagnostics": _llm_diagnostics(True, True, "success", model=model, base_url=base_url, fallback_used=False),
            "warnings": family_warnings,
        }
    except Exception as exc:  # noqa: BLE001
        fallback["model_status"] = "fallback_after_llm_error"
        fallback["llm_diagnostics"] = _llm_diagnostics(
            True,
            True,
            "failed_fallback_used",
            model=model,
            base_url=base_url,
            fallback_used=True,
            error_type=type(exc).__name__,
        )
        fallback["warnings"] = [f"local_llm_plan_failed:{type(exc).__name__}"]
        return fallback


def _fallback_plan(prompt: str) -> dict[str, Any]:
    clean = str(prompt or "").lower()
    family = _family_from_prompt(clean)
    use_short = any(token in clean for token in ["short", "숏", "공매도", "양방향", "long/short"])
    use_sltp = any(token in clean for token in ["stop", "loss", "take profit", "손절", "익절", "sltp", "sl/tp"])
    common = {
        "enable_long": True,
        "enable_short": use_short,
        "use_sltp": use_sltp,
        "stop_loss_pct": 3.0,
        "take_profit_pct": 6.0,
        "transaction_cost_bps": 5.0,
        "slippage_bps": 2.0,
    }
    if family == "moving_average_crossover":
        fast_window = 10 if any(token in clean for token in ["fast", "빠른", "민감", "aggressive"]) else 20
        slow_window = 50 if fast_window <= 10 else 100
        return {
            "family": family,
            "rationale": "이동평균 교차 의도를 단기/장기 SMA 교차, 다음 봉 체결, 수정 가능한 비용/리스크 제어로 매핑했습니다.",
            "parameters": _normalize_moving_average_parameters({**common, "fast_window": fast_window, "slow_window": slow_window}),
            "search_space": _default_moving_average_search_space(),
            "warnings": [],
        }
    if family == "rsi_reversion":
        oversold = 25.0 if any(token in clean for token in ["strict", "보수", "conservative"]) else 30.0
        overbought = 75.0 if oversold <= 25.0 else 70.0
        return {
            "family": family,
            "rationale": "RSI 평균회귀 의도를 과매도/과매수 진입, 평균회귀 청산 기준, 다음 봉 체결, 수정 가능한 비용/리스크 제어로 매핑했습니다.",
            "parameters": _normalize_rsi_reversion_parameters(
                {**common, "rsi_period": 14, "oversold": oversold, "overbought": overbought, "exit_rsi": 50.0}
            ),
            "search_space": _default_rsi_reversion_search_space(),
            "warnings": [],
        }
    factor = 2.0 if any(token in clean for token in ["민감", "fast", "빠른", "aggressive"]) else 3.0
    atr_period = 14 if any(token in clean for token in ["smooth", "완만", "보수", "conservative"]) else 10
    return {
        "family": "supertrend",
        "rationale": "Supertrend 의도를 ATR 추세 전환, 다음 봉 체결, 수정 가능한 손절/익절 파라미터로 매핑했습니다.",
        "parameters": _normalize_supertrend_parameters({**common, "atr_period": atr_period, "factor": factor}),
        "search_space": _default_supertrend_search_space(),
        "warnings": [],
    }


def _family_from_prompt(clean: str) -> str:
    return _explicit_family_from_prompt(clean) or "supertrend"


def _explicit_family_from_prompt(clean: str) -> str | None:
    if any(token in clean for token in ["rsi", "relative strength", "mean reversion", "reversion", "oversold", "overbought", "평균회귀", "과매도", "과매수"]):
        return "rsi_reversion"
    if any(token in clean for token in ["moving average", "ma crossover", "ma cross", "sma", "ema", "golden cross", "death cross", "이동평균", "이평", "골든크로스", "데드크로스"]):
        return "moving_average_crossover"
    if "교차" in clean and any(token in clean for token in ["fast", "slow", "빠른", "느린", "이동평균", "이평"]):
        return "moving_average_crossover"
    if any(token in clean for token in ["supertrend", "슈퍼트렌드"]):
        return "supertrend"
    return None


def _manifest_for_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    family = str(plan.get("family") or "supertrend")
    if family == "moving_average_crossover":
        return _moving_average_manifest(plan)
    if family == "rsi_reversion":
        return _rsi_reversion_manifest(plan)
    params = _normalize_supertrend_parameters(plan.get("parameters") or {})
    return [
        {"name": "atr_period", "label": "ATR 기간", "type": "int", "default": params["atr_period"], "min": 5, "max": 50, "step": 1, "optimize_values": [7, 10, 14, 20]},
        {"name": "factor", "label": "Supertrend 배수", "type": "float", "default": params["factor"], "min": 0.5, "max": 8.0, "step": 0.1, "optimize_values": [1.5, 2.0, 3.0, 4.0]},
        *_common_manifest_items(params),
    ]


def _moving_average_manifest(plan: dict[str, Any]) -> list[dict[str, Any]]:
    params = _normalize_moving_average_parameters(plan.get("parameters") or {})
    return [
        {"name": "fast_window", "label": "단기 MA 기간", "type": "int", "default": params["fast_window"], "min": 2, "max": 250, "step": 1, "optimize_values": [5, 10, 20, 30]},
        {"name": "slow_window", "label": "장기 MA 기간", "type": "int", "default": params["slow_window"], "min": 3, "max": 500, "step": 1, "optimize_values": [50, 100, 150, 200]},
        *_common_manifest_items(params),
    ]


def _rsi_reversion_manifest(plan: dict[str, Any]) -> list[dict[str, Any]]:
    params = _normalize_rsi_reversion_parameters(plan.get("parameters") or {})
    return [
        {"name": "rsi_period", "label": "RSI 기간", "type": "int", "default": params["rsi_period"], "min": 2, "max": 100, "step": 1, "optimize_values": [7, 10, 14, 21]},
        {"name": "oversold", "label": "과매도 진입", "type": "float", "default": params["oversold"], "min": 5.0, "max": 45.0, "step": 0.5, "optimize_values": [20.0, 25.0, 30.0, 35.0]},
        {"name": "overbought", "label": "과매수 진입", "type": "float", "default": params["overbought"], "min": 55.0, "max": 95.0, "step": 0.5, "optimize_values": [65.0, 70.0, 75.0, 80.0]},
        {"name": "exit_rsi", "label": "평균회귀 청산 RSI", "type": "float", "default": params["exit_rsi"], "min": 35.0, "max": 65.0, "step": 0.5, "optimize_values": [45.0, 50.0, 55.0]},
        *_common_manifest_items(params),
    ]


def _common_manifest_items(params: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": "enable_long", "label": "롱 허용", "type": "bool", "default": params["enable_long"], "optimize_values": [True]},
        {"name": "enable_short", "label": "숏 허용", "type": "bool", "default": params["enable_short"], "optimize_values": [False, True]},
        {"name": "use_sltp", "label": "손절/익절 사용", "type": "bool", "default": params["use_sltp"], "optimize_values": [False, True]},
        {"name": "stop_loss_pct", "label": "손절률 (%)", "type": "float", "default": params["stop_loss_pct"], "min": 0.1, "max": 30.0, "step": 0.1, "optimize_values": [1.5, 3.0, 5.0, 8.0]},
        {"name": "take_profit_pct", "label": "익절률 (%)", "type": "float", "default": params["take_profit_pct"], "min": 0.1, "max": 60.0, "step": 0.1, "optimize_values": [3.0, 6.0, 10.0, 15.0]},
        {"name": "transaction_cost_bps", "label": "수수료 (bps)", "type": "float", "default": params["transaction_cost_bps"], "min": 0.0, "max": 100.0, "step": 0.5, "optimize_values": [2.0, 5.0, 10.0]},
        {"name": "slippage_bps", "label": "슬리피지 (bps)", "type": "float", "default": params["slippage_bps"], "min": 0.0, "max": 100.0, "step": 0.5, "optimize_values": [1.0, 2.0, 5.0]},
    ]


def _call_local_llm_plan(*, base_url: str, model: str, prompt: str, timeout_s: float) -> str:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "format": PYTHON_PLAN_SCHEMA,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 900},
            "keep_alive": "5m",
        },
        timeout=timeout_s,
    )
    response.raise_for_status()
    text = str((response.json() or {}).get("response") or "").strip()
    if not text:
        raise ValueError("empty local LLM response")
    return text


def _plan_prompt(prompt: str, fallback: dict[str, Any]) -> str:
    return "\n".join(
        [
            "Map the user's natural-language strategy request to a safe Python strategy plan.",
            "Supported strategy families: supertrend, moving_average_crossover, rsi_reversion.",
            "Return parameter values and search_space arrays for the Python renderer and Bayesian optimizer.",
            "Supertrend parameters: atr_period, factor, enable_long, enable_short, use_sltp, stop_loss_pct, take_profit_pct, transaction_cost_bps, slippage_bps.",
            "Moving-average parameters: fast_window, slow_window, enable_long, enable_short, use_sltp, stop_loss_pct, take_profit_pct, transaction_cost_bps, slippage_bps.",
            "RSI reversion parameters: rsi_period, oversold, overbought, exit_rsi, enable_long, enable_short, use_sltp, stop_loss_pct, take_profit_pct, transaction_cost_bps, slippage_bps.",
            f"Safe fallback plan: {json.dumps(fallback, ensure_ascii=False, sort_keys=True)}",
            f"User prompt: {prompt}",
        ]
    )


def _extract_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM plan was not a JSON object")
    return parsed


def _load_rows(ticker: str, *, start_date: str | None, end_date: str | None, limit: int) -> list[dict[str, Any]]:
    rows = get_prices(ticker, limit=max(2, int(limit or 756)))
    filtered = []
    for row in rows:
        row_date = str(row.get("date") or "")
        if start_date and row_date < str(start_date):
            continue
        if end_date and row_date > str(end_date):
            continue
        filtered.append(row)
    return filtered


def _normalize_supertrend_parameters(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "atr_period": _int_range(values.get("atr_period"), 10, 5, 50),
        "factor": _float_range(values.get("factor"), 3.0, 0.5, 8.0),
        "enable_long": _bool_value(values.get("enable_long"), True),
        "enable_short": _bool_value(values.get("enable_short"), False),
        "use_sltp": _bool_value(values.get("use_sltp"), False),
        "stop_loss_pct": _float_range(values.get("stop_loss_pct"), 3.0, 0.1, 30.0),
        "take_profit_pct": _float_range(values.get("take_profit_pct"), 6.0, 0.1, 60.0),
        "transaction_cost_bps": _float_range(values.get("transaction_cost_bps"), 5.0, 0.0, 100.0),
        "slippage_bps": _float_range(values.get("slippage_bps"), 2.0, 0.0, 100.0),
    }


def _normalize_parameters_for_family(family: str, values: dict[str, Any]) -> dict[str, Any]:
    if family == "moving_average_crossover":
        return _normalize_moving_average_parameters(values)
    if family == "rsi_reversion":
        return _normalize_rsi_reversion_parameters(values)
    return _normalize_supertrend_parameters(values)


def _normalize_moving_average_parameters(values: dict[str, Any]) -> dict[str, Any]:
    fast = _int_range(values.get("fast_window"), 20, 2, 250)
    slow = _int_range(values.get("slow_window"), 100, 3, 500)
    if slow <= fast:
        slow = min(500, fast + 1)
    return {
        "fast_window": fast,
        "slow_window": slow,
        "enable_long": _bool_value(values.get("enable_long"), True),
        "enable_short": _bool_value(values.get("enable_short"), False),
        "use_sltp": _bool_value(values.get("use_sltp"), False),
        "stop_loss_pct": _float_range(values.get("stop_loss_pct"), 3.0, 0.1, 30.0),
        "take_profit_pct": _float_range(values.get("take_profit_pct"), 6.0, 0.1, 60.0),
        "transaction_cost_bps": _float_range(values.get("transaction_cost_bps"), 5.0, 0.0, 100.0),
        "slippage_bps": _float_range(values.get("slippage_bps"), 2.0, 0.0, 100.0),
    }


def _normalize_rsi_reversion_parameters(values: dict[str, Any]) -> dict[str, Any]:
    oversold = _float_range(values.get("oversold"), 30.0, 5.0, 45.0)
    overbought = _float_range(values.get("overbought"), 70.0, 55.0, 95.0)
    exit_rsi = _float_range(values.get("exit_rsi"), 50.0, 35.0, 65.0)
    if exit_rsi <= oversold:
        exit_rsi = min(65.0, oversold + 5.0)
    if exit_rsi >= overbought:
        exit_rsi = max(35.0, overbought - 5.0)
    if oversold >= overbought:
        oversold = min(45.0, exit_rsi - 5.0)
        overbought = max(55.0, exit_rsi + 5.0)
    return {
        "rsi_period": _int_range(values.get("rsi_period"), 14, 2, 100),
        "oversold": oversold,
        "overbought": overbought,
        "exit_rsi": exit_rsi,
        "enable_long": _bool_value(values.get("enable_long"), True),
        "enable_short": _bool_value(values.get("enable_short"), False),
        "use_sltp": _bool_value(values.get("use_sltp"), False),
        "stop_loss_pct": _float_range(values.get("stop_loss_pct"), 3.0, 0.1, 30.0),
        "take_profit_pct": _float_range(values.get("take_profit_pct"), 6.0, 0.1, 60.0),
        "transaction_cost_bps": _float_range(values.get("transaction_cost_bps"), 5.0, 0.0, 100.0),
        "slippage_bps": _float_range(values.get("slippage_bps"), 2.0, 0.0, 100.0),
    }


def _all_parameter_names() -> set[str]:
    names: set[str] = set()
    for family in SUPPORTED_FAMILIES:
        names.update(_normalize_parameters_for_family(family, {}).keys())
    return names


def _clean_parameter_overrides(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    allowed = _all_parameter_names()
    return {key: value for key, value in values.items() if key in allowed}


def _default_supertrend_search_space() -> dict[str, list[Any]]:
    return {
        "atr_period": [7, 10, 14, 20],
        "factor": [1.5, 2.0, 3.0, 4.0],
        "enable_long": [True],
        "enable_short": [False, True],
        "use_sltp": [False, True],
        "stop_loss_pct": [1.5, 3.0, 5.0],
        "take_profit_pct": [3.0, 6.0, 10.0],
        "transaction_cost_bps": [5.0],
        "slippage_bps": [2.0],
    }


def _default_moving_average_search_space() -> dict[str, list[Any]]:
    return {
        "fast_window": [5, 10, 20, 30],
        "slow_window": [50, 100, 150, 200],
        "enable_long": [True],
        "enable_short": [False, True],
        "use_sltp": [False, True],
        "stop_loss_pct": [1.5, 3.0, 5.0],
        "take_profit_pct": [3.0, 6.0, 10.0],
        "transaction_cost_bps": [5.0],
        "slippage_bps": [2.0],
    }


def _default_rsi_reversion_search_space() -> dict[str, list[Any]]:
    return {
        "rsi_period": [7, 10, 14, 21],
        "oversold": [20.0, 25.0, 30.0, 35.0],
        "overbought": [65.0, 70.0, 75.0, 80.0],
        "exit_rsi": [45.0, 50.0, 55.0],
        "enable_long": [True],
        "enable_short": [False, True],
        "use_sltp": [False, True],
        "stop_loss_pct": [1.5, 3.0, 5.0],
        "take_profit_pct": [3.0, 6.0, 10.0],
        "transaction_cost_bps": [5.0],
        "slippage_bps": [2.0],
    }


def _default_search_space_for_family(family: str) -> dict[str, list[Any]]:
    if family == "moving_average_crossover":
        return _default_moving_average_search_space()
    if family == "rsi_reversion":
        return _default_rsi_reversion_search_space()
    return _default_supertrend_search_space()


def _search_space_for_family(family: str, values: Any) -> dict[str, list[Any]]:
    allowed = set(_default_search_space_for_family(family))
    return {key: value for key, value in _clean_search_space(values).items() if key in allowed}


def _all_search_space_keys() -> set[str]:
    return set(_default_supertrend_search_space()) | set(_default_moving_average_search_space()) | set(_default_rsi_reversion_search_space())


def _clean_search_space(values: Any) -> dict[str, list[Any]]:
    if not isinstance(values, dict):
        return {}
    allowed = _all_search_space_keys()
    out: dict[str, list[Any]] = {}
    for key, raw in values.items():
        if key not in allowed or not isinstance(raw, list) or not raw:
            continue
        out[key] = raw[:12]
    return out


def _search_space_from_manifest(manifest: list[dict[str, Any]], override: dict[str, list[Any]]) -> dict[str, list[Any]]:
    out = {}
    for item in manifest:
        values = item.get("optimize_values")
        if isinstance(values, list) and values:
            out[str(item["name"])] = values
    manifest_names = set(out)
    out.update({key: values for key, values in _clean_search_space(override).items() if key in manifest_names})
    return out


def _candidate_parameters(search_space: dict[str, list[Any]], *, max_trials: int, seed: int) -> list[dict[str, Any]]:
    keys = list(search_space)
    rng = random.Random(seed)
    center = {key: values[len(values) // 2] for key, values in search_space.items() if values}
    candidates = [center]
    for _ in range(max(1, max_trials * 4)):
        candidates.append({key: rng.choice(search_space[key]) for key in keys})
    scored = sorted(_dedupe_candidates(candidates), key=_parameter_prior_score, reverse=True)
    return scored[: max(1, min(int(max_trials or 16), 120))]


def _optuna_candidates(
    rows: list[dict[str, Any]],
    plan: dict[str, Any],
    manifest: list[dict[str, Any]],
    *,
    ticker: str,
    max_trials: int,
    seed: int,
) -> list[dict[str, Any]]:
    import optuna

    search_space = _search_space_from_manifest(manifest, dict(plan.get("search_space") or {}))
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed, multivariate=False)
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=optuna.pruners.NopPruner())
    candidates: list[dict[str, Any]] = []

    def objective(trial: Any) -> float:
        params = {key: trial.suggest_categorical(key, values) for key, values in search_space.items()}
        candidates.append(params)
        result = backtest_python_strategy(rows, {**plan["parameters"], **params}, ticker=ticker, family=plan["family"])
        return _optimization_score(result.get("metrics") or {})

    study.optimize(objective, n_trials=max(1, min(int(max_trials or 16), 120)), show_progress_bar=False)
    return _dedupe_candidates(candidates)


def _optuna_available() -> bool:
    return importlib.util.find_spec("optuna") is not None


def _parameter_prior_score(params: dict[str, Any]) -> float:
    stop = float(params.get("stop_loss_pct") or 3.0)
    take = float(params.get("take_profit_pct") or 6.0)
    risk_reward_score = -abs((take / max(stop, 0.1)) - 2.0) / 4
    if "fast_window" in params or "slow_window" in params:
        fast = float(params.get("fast_window") or 20)
        slow = float(params.get("slow_window") or 100)
        spread_score = -0.75 if slow <= fast else -abs((slow / max(fast, 1.0)) - 5.0) / 8
        return -abs(fast - 20) / 80 - abs(slow - 100) / 250 + spread_score + risk_reward_score
    if "rsi_period" in params or "oversold" in params:
        period = float(params.get("rsi_period") or 14)
        oversold = float(params.get("oversold") or 30)
        overbought = float(params.get("overbought") or 70)
        exit_rsi = float(params.get("exit_rsi") or 50)
        return -abs(period - 14) / 40 - abs(oversold - 30) / 25 - abs(overbought - 70) / 25 - abs(exit_rsi - 50) / 20 + risk_reward_score
    atr = float(params.get("atr_period") or 10)
    factor = float(params.get("factor") or 3.0)
    return -abs(atr - 10) / 20 - abs(factor - 3) / 4 + risk_reward_score


def _optimization_score(metrics: dict[str, Any]) -> float:
    sharpe = _float_or(metrics.get("sharpe"), 0.0)
    total_return = _float_or(metrics.get("total_return"), 0.0)
    max_dd = abs(_float_or(metrics.get("max_drawdown"), 0.0))
    trades = _float_or(metrics.get("trade_count"), 0.0)
    win_rate = _float_or(metrics.get("win_rate"), 0.0)
    trade_penalty = 0.25 if trades < 2 else 0.0
    return sharpe + total_return * 0.5 + win_rate * 0.25 - max_dd * 1.5 - trade_penalty


def _recommended_trial(trials: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [
        trial for trial in trials
        if _float_or((trial.get("metrics") or {}).get("trade_count"), 0.0) >= 2
        and _float_or((trial.get("metrics") or {}).get("max_drawdown"), 0.0) > -0.45
    ]
    pool = viable or trials
    return sorted(pool, key=lambda item: (item.get("score") or 0.0, -abs(_float_or((item.get("metrics") or {}).get("max_drawdown"), 0.0))), reverse=True)[0]


def _atr_series(rows: list[dict[str, Any]], length: int) -> list[float]:
    true_ranges: list[float] = []
    for idx, row in enumerate(rows):
        prev_close = rows[idx - 1]["close"] if idx else row["close"]
        true_ranges.append(max(row["high"] - row["low"], abs(row["high"] - prev_close), abs(row["low"] - prev_close)))
    out: list[float] = []
    for idx, value in enumerate(true_ranges):
        if idx == 0:
            out.append(value)
        elif idx < length:
            out.append(sum(true_ranges[: idx + 1]) / (idx + 1))
        else:
            out.append((out[-1] * (length - 1) + value) / length)
    return out


def _sma_series(values: list[float], window: int) -> list[float]:
    length = max(1, int(window or 1))
    out: list[float] = []
    running = 0.0
    for idx, value in enumerate(values):
        running += float(value)
        if idx >= length:
            running -= float(values[idx - length])
            out.append(running / length)
        else:
            out.append(running / (idx + 1))
    return out


def _rsi_series(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    period = max(2, int(length or 14))
    out = [50.0]
    avg_gain = 0.0
    avg_loss = 0.0
    for idx in range(1, len(values)):
        change = float(values[idx]) - float(values[idx - 1])
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        if idx <= period:
            avg_gain = (avg_gain * (idx - 1) + gain) / idx
            avg_loss = (avg_loss * (idx - 1) + loss) / idx
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss else 100.0
        out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def _supertrend_series(rows: list[dict[str, Any]], atr: list[float], factor: float) -> tuple[list[float], list[int]]:
    trend: list[int] = []
    line: list[float] = []
    final_upper = 0.0
    final_lower = 0.0
    current_trend = -1
    current_line = 0.0
    for idx, row in enumerate(rows):
        hl2 = (row["high"] + row["low"]) / 2.0
        upper = hl2 + factor * atr[idx]
        lower = hl2 - factor * atr[idx]
        if idx == 0:
            final_upper, final_lower = upper, lower
            current_line = upper
            trend.append(current_trend)
            line.append(current_line)
            continue
        prev_close = rows[idx - 1]["close"]
        final_upper = upper if upper < final_upper or prev_close > final_upper else final_upper
        final_lower = lower if lower > final_lower or prev_close < final_lower else final_lower
        if current_line == final_upper:
            if row["close"] <= final_upper:
                current_trend = -1
                current_line = final_upper
            else:
                current_trend = 1
                current_line = final_lower
        else:
            if row["close"] >= final_lower:
                current_trend = 1
                current_line = final_lower
            else:
                current_trend = -1
                current_line = final_upper
        trend.append(current_trend)
        line.append(current_line)
    return line, trend


def _metrics_from_returns(
    returns: list[float],
    trades: list[dict[str, Any]],
    drawdown_curve: list[dict[str, Any]],
    *,
    exposure_bars: int,
    total_bars: int,
    ending_equity: float,
) -> dict[str, float]:
    mean = sum(returns) / len(returns) if returns else 0.0
    vol = math.sqrt(sum((ret - mean) ** 2 for ret in returns) / max(len(returns) - 1, 1)) if len(returns) > 1 else 0.0
    downside = [ret for ret in returns if ret < 0]
    downside_vol = math.sqrt(sum(ret * ret for ret in downside) / max(len(downside), 1)) if downside else 0.0
    sharpe = mean / vol * math.sqrt(252) if vol else 0.0
    sortino = mean / downside_vol * math.sqrt(252) if downside_vol else 0.0
    max_drawdown = min([_float_or(row.get("drawdown"), 0.0) for row in drawdown_curve], default=0.0)
    trade_returns = [_float_or(trade.get("pnl_pct"), 0.0) for trade in trades]
    wins = [value for value in trade_returns if value > 0]
    losses = [value for value in trade_returns if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_win / gross_loss if gross_loss else (gross_win if gross_win else 0.0)
    win_rate = len(wins) / len(trade_returns) if trade_returns else 0.0
    return {
        "total_return": round(ending_equity - 1.0, 8),
        "cagr": round(ending_equity - 1.0, 8),
        "sharpe": round(sharpe, 8),
        "sortino": round(sortino, 8),
        "max_drawdown": round(max_drawdown, 8),
        "profit_factor": round(profit_factor, 8),
        "win_rate": round(win_rate, 8),
        "trade_count": float(len(trades)),
        "exposure": round(exposure_bars / max(total_bars, 1), 8),
        "turnover": round(len(trades) * 2.0, 8),
    }


def _position_return(position: int, prev_close: float, close: float) -> float:
    if not position or prev_close <= 0 or close <= 0:
        return 0.0
    if position == 1:
        return close / prev_close - 1.0
    return prev_close / close - 1.0


def _trade_pnl(position: int, entry: float, exit_price: float) -> float:
    if entry <= 0 or exit_price <= 0:
        return 0.0
    if position == 1:
        return exit_price / entry - 1.0
    return entry / exit_price - 1.0


def _ohlc_row(row: dict[str, Any]) -> dict[str, Any]:
    close = _float_or(row.get("adjusted_close"), _float_or(row.get("close"), 0.0))
    open_price = _float_or(row.get("open"), close)
    high = _float_or(row.get("high"), max(open_price, close))
    low = _float_or(row.get("low"), min(open_price, close))
    return {
        "date": str(row.get("date") or ""),
        "open": open_price,
        "high": max(high, open_price, close),
        "low": min(low, open_price, close),
        "close": close,
    }


def _failed_backtest(ticker: str, reason: str) -> dict[str, Any]:
    return {
        "run_id": _make_id("pystrat_failed", ticker, reason),
        "status": "failed",
        "ticker": ticker,
        "metrics": {},
        "equity_curve": [],
        "drawdown_curve": [],
        "trades": [],
        "chart": {"rows": [], "markers": [], "trade_paths": []},
        "warnings": [reason],
        "diagnostics": {"lookahead_safe": True, "execution_assumption": "not_run", "data_source": "data_mart:prices_daily"},
    }


def _int_range(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _float_range(value: Any, default: float, minimum: float, maximum: float) -> float:
    parsed = _float_or(value, default)
    return max(minimum, min(maximum, parsed))


def _float_or(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _maybe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"true", "1", "yes", "y", "on"}:
            return True
        if clean in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _clean_ticker(value: Any) -> str:
    ticker = "".join(ch for ch in str(value or "SPY").strip().upper() if ch.isalnum() or ch in {".", "-", "^"})
    return ticker or "SPY"


def _make_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in candidates:
        digest = _hash_payload(item)
        if digest in seen:
            continue
        seen.add(digest)
        out.append(item)
    return out


def _unique_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _llm_diagnostics(
    requested: bool,
    attempted: bool,
    status: str,
    *,
    model: str = "deterministic_template",
    base_url: str = "",
    fallback_used: bool,
    error_type: str = "",
) -> dict[str, Any]:
    return {
        "requested": requested,
        "attempted": attempted,
        "status": status,
        "model": model,
        "base_url": base_url,
        "fallback_used": fallback_used,
        "error_type": error_type,
    }
