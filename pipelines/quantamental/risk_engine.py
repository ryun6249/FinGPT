from __future__ import annotations

import math
from statistics import mean
from typing import Any

from pipelines.quantamental.fundamental_engine import clamp


def calculate_risk(
    fundamentals: dict[str, Any],
    quant: dict[str, Any],
    factors: dict[str, Any],
    data_quality_score: float | None = None,
) -> dict[str, Any]:
    f_metrics = fundamentals.get("metrics") or {}
    q_metrics = quant.get("metrics") or {}
    missing_fundamentals = fundamentals.get("status") != "ok"
    missing_quant = quant.get("status") != "ok"
    accounting = f_metrics.get("accounting_risk") or {}
    stability = f_metrics.get("stability") or {}
    valuation = f_metrics.get("valuation") or {}
    momentum = q_metrics.get("momentum") or {}
    volatility = q_metrics.get("volatility") or {}
    drawdown = q_metrics.get("drawdown") or {}
    liquidity = q_metrics.get("liquidity") or {}
    flags: list[str] = []

    price_risk = {
        "score": _avg([
            _score_high(momentum.get("momentum_3m"), -0.15, 0.20),
            _score_high(momentum.get("momentum_12m"), -0.25, 0.45),
            _score_low(_abs_or_none(drawdown.get("current_drawdown")), 0.0, 0.35),
        ], fallback=None if missing_quant else 50),
        "current_drawdown": drawdown.get("current_drawdown"),
        "momentum_3m": momentum.get("momentum_3m"),
    }
    volatility_risk = {
        "score": _avg([
            _score_low(volatility.get("realized_volatility_60d"), 0.15, 0.80),
            _score_low(volatility.get("downside_volatility"), 0.10, 0.70),
            _score_low(volatility.get("volatility_percentile"), 0.20, 0.90),
        ], fallback=None if missing_quant else 50),
        "realized_volatility_60d": volatility.get("realized_volatility_60d"),
        "downside_volatility": volatility.get("downside_volatility"),
    }
    drawdown_risk = {
        "score": _avg([
            _score_low(_abs_or_none(drawdown.get("max_drawdown")), 0.05, 0.60),
            _score_low(_abs_or_none(drawdown.get("current_drawdown")), 0.0, 0.35),
        ], fallback=None if missing_quant else 50),
        "max_drawdown": drawdown.get("max_drawdown"),
        "current_drawdown": drawdown.get("current_drawdown"),
        "drawdown_duration": drawdown.get("drawdown_duration"),
    }
    balance_sheet_risk = {
        "score": _avg([
            _score_low(stability.get("debt_to_equity"), 0.2, 3.0),
            _score_low(stability.get("net_debt_to_ebitda"), 0.0, 5.0),
            _score_high(stability.get("current_ratio"), 0.7, 2.0),
        ], fallback=None if missing_fundamentals else 50),
        "debt_to_equity": stability.get("debt_to_equity"),
        "net_debt_to_ebitda": stability.get("net_debt_to_ebitda"),
        "current_ratio": stability.get("current_ratio"),
    }
    valuation_risk = {
        "score": factors.get("value_score") if factors.get("value_score") is not None else _avg([
            _score_low(valuation.get("per"), 12, 45),
            _score_low(valuation.get("pbr"), 1, 12),
            _score_low(valuation.get("ev_to_ebitda"), 8, 35),
        ], fallback=None if missing_fundamentals else 50),
        "per": valuation.get("per"),
        "pbr": valuation.get("pbr"),
        "ev_to_ebitda": valuation.get("ev_to_ebitda"),
    }
    liquidity_risk = {
        "score": factors.get("liquidity_score") if factors.get("liquidity_score") is not None else _avg([
            _score_high(math.log10(liquidity.get("average_dollar_volume")) if liquidity.get("average_dollar_volume") else None, 6, 9)
        ], fallback=None if missing_quant else 50),
        "average_dollar_volume": liquidity.get("average_dollar_volume"),
        "liquidity_risk": liquidity.get("liquidity_risk"),
    }
    data_quality_risk = {
        "score": data_quality_score,
        "quality_level": _quality_level(data_quality_score),
    }

    for key, active in accounting.items():
        if active is True:
            flags.append(key)
    if _finite(drawdown.get("max_drawdown")) is not None and abs(float(drawdown.get("max_drawdown"))) > 0.50:
        flags.append("severe_max_drawdown")
    if _finite(volatility.get("realized_volatility_60d")) is not None and float(volatility.get("realized_volatility_60d")) > 0.80:
        flags.append("elevated_realized_volatility")
    if liquidity.get("liquidity_risk") == "high":
        flags.append("high_liquidity_risk")
    if data_quality_score is not None and data_quality_score < 50:
        flags.append("poor_data_quality")
    if missing_fundamentals:
        flags.append("missing_fundamentals")
    if missing_quant:
        flags.append("missing_quant")

    weighted_score = _weighted(
        [
            (drawdown_risk["score"], 0.30),
            (balance_sheet_risk["score"], 0.30),
            (valuation_risk["score"], 0.20),
            (volatility_risk["score"], 0.20),
        ]
    )
    if missing_fundamentals and missing_quant:
        score = round(float(data_quality_score), 2) if data_quality_score is not None else None
    elif data_quality_score is not None and data_quality_score < 40 and weighted_score is not None:
        score = round(min(float(weighted_score), float(data_quality_score)), 2)
    else:
        score = weighted_score
    return {
        "risk_score": score,
        "risk_level": _risk_level(score),
        "price_risk": price_risk,
        "volatility_risk": volatility_risk,
        "drawdown_risk": drawdown_risk,
        "balance_sheet_risk": balance_sheet_risk,
        "valuation_risk": valuation_risk,
        "liquidity_risk": liquidity_risk,
        "data_quality_risk": data_quality_risk,
        "risk_flags": sorted(set(flags)),
        "risk_summary": _risk_summary(score, flags),
    }


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


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


def _avg(values: list[float | None], fallback: float | None = None) -> float | None:
    nums = [float(value) for value in values if value is not None]
    if not nums:
        return fallback
    return clamp(mean(nums))


def _weighted(values: list[tuple[float | None, float]]) -> float | None:
    total_weight = sum(weight for value, weight in values if value is not None)
    if total_weight <= 0:
        return None
    return round(float(sum(float(value) * weight for value, weight in values if value is not None) / total_weight), 2)


def _risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "low risk"
    if score >= 60:
        return "medium risk"
    if score >= 40:
        return "elevated risk"
    return "high risk"


def _quality_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 80:
        return "good"
    if score >= 60:
        return "usable"
    if score >= 40:
        return "limited"
    return "poor"


def _risk_summary(score: float | None, flags: list[str]) -> str:
    level = _risk_level(score)
    if flags:
        return f"{level}; key flags: {', '.join(sorted(set(flags))[:6])}"
    return f"{level}; no major deterministic red flags detected from available data"
