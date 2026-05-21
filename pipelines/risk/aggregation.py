from __future__ import annotations

import hashlib
import json
from statistics import mean
from typing import Any

from core.schemas.risk import RiskDriverContribution, RiskLevel


BASE_RISK_WEIGHTS: dict[str, float] = {
    "company_fundamental_vulnerability": 0.25,
    "market_behavior_risk": 0.20,
    "macro_regime_risk": 0.20,
    "credit_liquidity_risk": 0.15,
    "transmission_sensitivity": 0.10,
    "data_quality_penalty": 0.10,
}

PORTFOLIO_RISK_WEIGHTS: dict[str, float] = {
    "weighted_company_risk": 0.30,
    "weighted_market_behavior_risk": 0.15,
    "macro_regime_risk": 0.15,
    "credit_liquidity_risk": 0.15,
    "weighted_transmission_sensitivity": 0.10,
    "concentration_penalty": 0.05,
    "data_quality_penalty": 0.10,
}


def clamp_score(value: Any, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return round(max(0.0, min(100.0, parsed)), 2)


def inverse_score(value: Any) -> float | None:
    parsed = clamp_score(value)
    return None if parsed is None else round(100.0 - parsed, 2)


def risk_level(score: float | None) -> RiskLevel:
    if score is None:
        return "unknown"
    if score <= 24:
        return "low"
    if score <= 49:
        return "moderate"
    if score <= 74:
        return "elevated"
    return "high"


def average_score(values: list[float | None]) -> float | None:
    nums = [float(value) for value in values if value is not None]
    if not nums:
        return None
    return clamp_score(mean(nums))


def weighted_score(values: dict[str, float | None], weights: dict[str, float]) -> float | None:
    available = [(values.get(key), weight) for key, weight in weights.items() if values.get(key) is not None]
    weight_total = sum(weight for _, weight in available)
    if weight_total <= 0:
        return None
    return clamp_score(sum(float(value) * weight for value, weight in available if value is not None) / weight_total)


def driver_contributions(values: dict[str, float | None], weights: dict[str, float]) -> list[RiskDriverContribution]:
    rows: list[RiskDriverContribution] = []
    for key, weight in weights.items():
        score = clamp_score(values.get(key))
        rows.append(
            RiskDriverContribution(
                driver=key,
                score=score,
                weight=weight,
                contribution=None if score is None else round(score * weight, 2),
                level=risk_level(score),
            )
        )
    return rows


def concentration_penalty(weights: list[float]) -> float:
    clean = [max(0.0, float(value)) for value in weights if value is not None]
    total = sum(clean)
    if total <= 0:
        return 0.0
    normalized = [value / total for value in clean]
    hhi = sum(value * value for value in normalized)
    return clamp_score(max(0.0, (hhi - 0.10) * 120.0), default=0.0) or 0.0


def stable_input_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]

