from __future__ import annotations

from statistics import mean
from typing import Any

from pipelines.quantamental.fundamental_engine import clamp


STYLE_WEIGHTS = {
    "balanced": {"fundamental": 0.50, "quant": 0.35, "risk": 0.15},
    "quality_growth": {"fundamental": 0.60, "quant": 0.25, "risk": 0.15},
    "value": {"fundamental": 0.65, "quant": 0.15, "risk": 0.20},
    "momentum": {"fundamental": 0.30, "quant": 0.55, "risk": 0.15},
    "defensive": {"fundamental": 0.45, "quant": 0.20, "risk": 0.35},
}


def calculate_composite(
    fundamentals: dict[str, Any],
    quant: dict[str, Any],
    factors: dict[str, Any],
    risk: dict[str, Any],
    *,
    style: str = "balanced",
) -> dict[str, Any]:
    style_key = _normalize_style(style)
    weights = STYLE_WEIGHTS[style_key]
    category_scores = fundamentals.get("category_scores") or {}
    quant_components = quant.get("component_scores") or {}
    fundamental_score = _weighted(
        [
            (category_scores.get("growth"), 0.20),
            (category_scores.get("profitability"), 0.25),
            (category_scores.get("stability"), 0.20),
            (category_scores.get("cash_flow_quality"), 0.20),
            (category_scores.get("valuation"), 0.15),
        ]
    )
    quant_score = _weighted(
        [
            (quant_components.get("momentum"), 0.35),
            (quant_components.get("trend"), 0.25),
            (quant_components.get("volatility_quality"), 0.15),
            (quant_components.get("risk_adjusted_return"), 0.15),
            (quant_components.get("liquidity"), 0.10),
        ]
    )
    risk_score = risk.get("risk_score")
    final_score = None
    if fundamental_score is not None and quant_score is not None:
        final_score = _weighted(
            [
                (fundamental_score, weights["fundamental"]),
                (quant_score, weights["quant"]),
                (risk_score, weights["risk"]),
            ]
        )
    return {
        "style": style_key,
        "final_score": final_score,
        "fundamental_score": fundamental_score,
        "quant_score": quant_score,
        "risk_score": risk_score,
        "factor_scores": {
            "value_score": factors.get("value_score"),
            "quality_score": factors.get("quality_score"),
            "growth_score": factors.get("growth_score"),
            "momentum_score": factors.get("momentum_score"),
            "low_volatility_score": factors.get("low_volatility_score"),
            "liquidity_score": factors.get("liquidity_score"),
        },
        "component_scores": {
            "fundamental": category_scores,
            "quant": quant_components,
            "risk": {
                "drawdown_risk": (risk.get("drawdown_risk") or {}).get("score"),
                "balance_sheet_risk": (risk.get("balance_sheet_risk") or {}).get("score"),
                "valuation_risk": (risk.get("valuation_risk") or {}).get("score"),
                "volatility_risk": (risk.get("volatility_risk") or {}).get("score"),
            },
        },
        "score_explanation": {
            "fundamental_weight": weights["fundamental"],
            "quant_weight": weights["quant"],
            "risk_weight": weights["risk"],
            "risk_score_direction": "higher means lower risk",
            "method": "deterministic_weighted_average_v1",
        },
        "data_conflict_classification": classify_conflict(fundamental_score, quant_score),
    }


def classify_conflict(fundamental_score: float | None, quant_score: float | None) -> str:
    if fundamental_score is None or quant_score is None:
        return "mixed_or_insufficient_data"
    fundamental_strong = fundamental_score >= 70
    fundamental_weak = fundamental_score < 55
    quant_strong = quant_score >= 70
    quant_weak = quant_score < 55
    if fundamental_strong and quant_strong:
        return "fundamental_strong_quant_strong"
    if fundamental_strong and quant_weak:
        return "fundamental_strong_quant_weak"
    if fundamental_weak and quant_strong:
        return "fundamental_weak_quant_strong"
    if fundamental_weak and quant_weak:
        return "fundamental_weak_quant_weak"
    return "mixed_or_insufficient_data"


def _normalize_style(style: str) -> str:
    key = str(style or "balanced").strip().lower().replace("-", "_").replace(" ", "_")
    return key if key in STYLE_WEIGHTS else "balanced"


def _weighted(values: list[tuple[float | None, float]]) -> float | None:
    total_weight = sum(weight for value, weight in values if value is not None)
    if total_weight <= 0:
        return None
    return round(float(sum(float(value) * weight for value, weight in values if value is not None) / total_weight), 2)


def average_available(values: list[float | None]) -> float | None:
    nums = [float(value) for value in values if value is not None]
    if not nums:
        return None
    return round(float(clamp(mean(nums)) or 0.0), 2)
