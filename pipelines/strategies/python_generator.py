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


SUPPORTED_FAMILIES = {"supertrend"}
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
Return JSON only. Supported family values: supertrend.
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
        "warnings": _unique_strings(warnings + list(backtest.get("warnings") or []) + list(optimization.get("warnings") or [])),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def render_python_strategy_code(plan: dict[str, Any], manifest: list[dict[str, Any]]) -> str:
    defaults = {item["name"]: item.get("default") for item in manifest}
    defaults.update(plan.get("parameters") or {})
    return f'''# Generated by FinGPT Python Strategy Lab.
# Strategy family: {plan.get("family", "supertrend")}
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
        "chart": {"rows": chart_rows[-500:], "markers": markers[-200:]},
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
        "warnings": [],
    }


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
        params = {**fallback["parameters"], **_clean_parameter_overrides(parsed.get("parameters") or {}), **_clean_parameter_overrides(parameter_overrides)}
        search_space = {**fallback["search_space"], **_clean_search_space(parsed.get("search_space") or {}), **_clean_search_space(search_space_override)}
        return {
            "family": family,
            "rationale": str(parsed.get("rationale") or fallback["rationale"]).strip(),
            "parameters": _normalize_supertrend_parameters(params),
            "search_space": _clean_search_space(search_space),
            "model_status": "local_llm_plan_template_python",
            "llm_diagnostics": _llm_diagnostics(True, True, "success", model=model, base_url=base_url, fallback_used=False),
            "warnings": [],
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
    clean = prompt.lower()
    use_short = any(token in clean for token in ["short", "숏", "공매도", "양방향", "long/short"])
    use_sltp = any(token in clean for token in ["stop", "loss", "take profit", "손절", "익절", "sltp", "sl/tp"])
    factor = 2.0 if any(token in clean for token in ["민감", "fast", "빠른", "aggressive"]) else 3.0
    atr_period = 14 if any(token in clean for token in ["smooth", "완만", "보수", "conservative"]) else 10
    return {
        "family": "supertrend",
        "rationale": "Supertrend 의도를 ATR 기반 추세 전환, 다음 봉 체결, 선택형 손절/익절 파라미터로 해석했습니다.",
        "parameters": _normalize_supertrend_parameters(
            {
                "atr_period": atr_period,
                "factor": factor,
                "enable_long": True,
                "enable_short": use_short,
                "use_sltp": use_sltp,
                "stop_loss_pct": 3.0,
                "take_profit_pct": 6.0,
                "transaction_cost_bps": 5.0,
                "slippage_bps": 2.0,
            }
        ),
        "search_space": _default_supertrend_search_space(),
        "warnings": [],
    }


def _manifest_for_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    params = _normalize_supertrend_parameters(plan.get("parameters") or {})
    return [
        {"name": "atr_period", "label": "ATR Period", "type": "int", "default": params["atr_period"], "min": 5, "max": 50, "step": 1, "optimize_values": [7, 10, 14, 20]},
        {"name": "factor", "label": "Supertrend Factor", "type": "float", "default": params["factor"], "min": 0.5, "max": 8.0, "step": 0.1, "optimize_values": [1.5, 2.0, 3.0, 4.0]},
        {"name": "enable_long", "label": "Enable Long", "type": "bool", "default": params["enable_long"], "optimize_values": [True]},
        {"name": "enable_short", "label": "Enable Short", "type": "bool", "default": params["enable_short"], "optimize_values": [False, True]},
        {"name": "use_sltp", "label": "Use Stop Loss / Take Profit", "type": "bool", "default": params["use_sltp"], "optimize_values": [False, True]},
        {"name": "stop_loss_pct", "label": "Stop Loss (%)", "type": "float", "default": params["stop_loss_pct"], "min": 0.1, "max": 30.0, "step": 0.1, "optimize_values": [1.5, 3.0, 5.0, 8.0]},
        {"name": "take_profit_pct", "label": "Take Profit (%)", "type": "float", "default": params["take_profit_pct"], "min": 0.1, "max": 60.0, "step": 0.1, "optimize_values": [3.0, 6.0, 10.0, 15.0]},
        {"name": "transaction_cost_bps", "label": "Commission (bps)", "type": "float", "default": params["transaction_cost_bps"], "min": 0.0, "max": 100.0, "step": 0.5, "optimize_values": [2.0, 5.0, 10.0]},
        {"name": "slippage_bps", "label": "Slippage (bps)", "type": "float", "default": params["slippage_bps"], "min": 0.0, "max": 100.0, "step": 0.5, "optimize_values": [1.0, 2.0, 5.0]},
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
            "Only supported strategy family today is supertrend.",
            "Return parameter values and search_space arrays for the Python renderer and Bayesian optimizer.",
            "Parameter names: atr_period, factor, enable_long, enable_short, use_sltp, stop_loss_pct, take_profit_pct, transaction_cost_bps, slippage_bps.",
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


def _clean_parameter_overrides(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        return {}
    allowed = set(_normalize_supertrend_parameters({}).keys())
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


def _clean_search_space(values: Any) -> dict[str, list[Any]]:
    if not isinstance(values, dict):
        return {}
    allowed = set(_default_supertrend_search_space().keys())
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
    out.update(_clean_search_space(override))
    return out


def _candidate_parameters(search_space: dict[str, list[Any]], *, max_trials: int, seed: int) -> list[dict[str, Any]]:
    keys = list(search_space)
    rng = random.Random(seed)
    center = {key: values[len(values) // 2] for key, values in search_space.items() if values}
    candidates = [center]
    for _ in range(max(1, max_trials * 4)):
        candidates.append({key: rng.choice(search_space[key]) for key in keys})
    scored = sorted(_dedupe_candidates(candidates), key=_supertrend_prior_score, reverse=True)
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


def _supertrend_prior_score(params: dict[str, Any]) -> float:
    atr = float(params.get("atr_period") or 10)
    factor = float(params.get("factor") or 3.0)
    stop = float(params.get("stop_loss_pct") or 3.0)
    take = float(params.get("take_profit_pct") or 6.0)
    return -abs(atr - 10) / 20 - abs(factor - 3) / 4 - abs((take / max(stop, 0.1)) - 2.0) / 4


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
        "chart": {"rows": [], "markers": []},
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
