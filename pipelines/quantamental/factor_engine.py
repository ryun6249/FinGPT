from __future__ import annotations

import math
from statistics import mean
from typing import Any

from pipelines.quantamental.fundamental_engine import clamp


def calculate_factors(
    fundamentals: dict[str, Any],
    quant: dict[str, Any],
    company: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company = company or {}
    f_metrics = fundamentals.get("metrics") or {}
    q_metrics = quant.get("metrics") or {}
    valuation = f_metrics.get("valuation") or {}
    profitability = f_metrics.get("profitability") or {}
    growth = f_metrics.get("growth") or {}
    cash_flow = f_metrics.get("cash_flow_quality") or {}
    momentum = q_metrics.get("momentum") or {}
    volatility = q_metrics.get("volatility") or {}
    drawdown = q_metrics.get("drawdown") or {}
    liquidity = q_metrics.get("liquidity") or {}

    score_inputs = {
        "value_score": [
            _score_low(valuation.get("per"), 12, 45),
            _score_low(valuation.get("pbr"), 1, 12),
            _score_low(valuation.get("psr"), 1, 15),
            _score_low(valuation.get("ev_to_ebitda"), 8, 35),
            _score_high(valuation.get("fcf_yield"), 0, 0.08),
            _score_high(valuation.get("earnings_yield"), 0, 0.08),
        ],
        "quality_score": [
            _score_high(profitability.get("roe"), 0.02, 0.25),
            _score_high(profitability.get("roic"), 0.02, 0.20),
            _score_high(profitability.get("gross_margin"), 0.15, 0.65),
            _score_high(profitability.get("operating_margin"), 0.03, 0.30),
            _score_high(profitability.get("net_margin"), 0.02, 0.25),
            _score_high(cash_flow.get("fcf_conversion"), 0, 1.2),
            _score_high(cash_flow.get("ocf_to_net_income"), 0.3, 1.3),
        ],
        "growth_score": [
            _score_high(_coalesce_none(growth.get("revenue_cagr_3y"), growth.get("revenue_growth")), -0.05, 0.20),
            _score_high(_coalesce_none(growth.get("net_income_cagr_3y"), growth.get("net_income_growth")), -0.10, 0.20),
            _score_high(growth.get("eps_growth"), -0.10, 0.20),
            _score_high(growth.get("fcf_cagr_3y"), -0.10, 0.20),
        ],
        "momentum_score": [
            _score_high(momentum.get("momentum_3m"), -0.10, 0.20),
            _score_high(momentum.get("momentum_6m"), -0.15, 0.35),
            _score_high(momentum.get("momentum_12m"), -0.20, 0.50),
            _score_high(momentum.get("momentum_12m_minus_1m"), -0.20, 0.40),
            _score_high(momentum.get("relative_strength_vs_benchmark"), -0.15, 0.20),
        ],
        "low_volatility_score": [
            _score_low(volatility.get("realized_volatility_60d"), 0.15, 0.80),
            _score_low(volatility.get("downside_volatility"), 0.10, 0.70),
            _score_low(_abs_or_none(drawdown.get("max_drawdown")), 0.05, 0.60),
            _score_low(_abs_or_none(drawdown.get("current_drawdown")), 0.00, 0.35),
        ],
        "liquidity_score": [
            _score_high(math.log10(liquidity.get("average_dollar_volume")) if liquidity.get("average_dollar_volume") else None, 6, 9),
            _score_high(math.log10(company.get("market_cap")) if company.get("market_cap") else None, 9, 12),
            _score_high(liquidity.get("volume_trend"), -0.50, 0.50),
        ],
    }
    scores = {key: _average_score(values) for key, values in score_inputs.items()}
    available_counts = {key: sum(1 for value in values if value is not None) for key, values in score_inputs.items()}
    expected_counts = {key: len(values) for key, values in score_inputs.items()}
    confidence = {
        key.replace("_score", "_confidence"): round(available_counts[key] / expected_counts[key], 3)
        for key in score_inputs
    }
    missing = []
    for key, count in available_counts.items():
        if count < expected_counts[key]:
            missing.append(key)
    return {
        "status": "ok" if any(value is not None for value in scores.values()) else "empty",
        **scores,
        "confidence": confidence,
        "available_metric_counts": available_counts,
        "missing_factor_inputs": missing,
        "score_method": "deterministic_rule_based_v1",
    }


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _coalesce_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _abs_or_none(value: Any) -> float | None:
    parsed = _finite(value)
    return abs(parsed) if parsed is not None else None


def _score_high(value: Any, bad: float, good: float) -> float | None:
    parsed = _finite(value)
    if parsed is None or good == bad:
        return None
    return clamp(((parsed - bad) / (good - bad)) * 100)


def _score_low(value: Any, good: float, bad: float) -> float | None:
    parsed = _finite(value)
    if parsed is None or good == bad:
        return None
    return clamp((1 - ((parsed - good) / (bad - good))) * 100)


def _average_score(values: list[float | None]) -> float | None:
    nums = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not nums:
        return None
    return round(float(clamp(mean(nums)) or 0.0), 2)
