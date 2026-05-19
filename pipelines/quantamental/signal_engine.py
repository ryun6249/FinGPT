from __future__ import annotations

from typing import Any


SIGNAL_LABELS = {
    "strong_buy": "Strong Buy Candidate",
    "buy": "Buy Candidate",
    "accumulate": "Accumulate Watch",
    "neutral": "Neutral / Hold-Watch",
    "avoid": "Avoid",
    "sell_risk": "Sell Risk / Reduce Risk",
    "insufficient": "Insufficient Data",
}


def classify_signal(
    composite: dict[str, Any],
    risk: dict[str, Any],
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    final_score = _float(composite.get("final_score"))
    fundamental_score = _float(composite.get("fundamental_score"))
    quant_score = _float(composite.get("quant_score"))
    risk_score = _float(composite.get("risk_score"))
    factor_scores = composite.get("factor_scores") or {}
    valuation_score = _float(factor_scores.get("value_score"))
    data_quality_score = _float(data_quality.get("data_quality_score"))
    risk_flags = list(risk.get("risk_flags") or [])
    severe_flags = {
        "negative_equity",
        "excessive_leverage",
        "repeated_negative_fcf",
        "poor_data_quality",
        "severe_max_drawdown",
    }
    severe_count = sum(1 for flag in risk_flags if flag in severe_flags)
    missing_sections = list(data_quality.get("missing_sections") or [])

    insufficient = (
        final_score is None
        or fundamental_score is None
        or quant_score is None
        or risk_score is None
        or data_quality_score is None
        or data_quality_score < 40
        or "fundamentals" in missing_sections
        or "quant" in missing_sections
    )
    if insufficient:
        label = SIGNAL_LABELS["insufficient"]
    elif (
        final_score < 40
        and risk_score < 40
        and fundamental_score < 45
        and quant_score < 45
    ) or severe_count >= 2:
        label = SIGNAL_LABELS["sell_risk"]
    elif final_score >= 85 and fundamental_score >= 75 and quant_score >= 70 and risk_score >= 65 and severe_count == 0 and data_quality_score >= 70:
        label = SIGNAL_LABELS["strong_buy"]
    elif final_score >= 75 and fundamental_score >= 65 and quant_score >= 60 and risk_score >= 55 and severe_count == 0:
        label = SIGNAL_LABELS["buy"]
    elif final_score >= 65 and (
        (fundamental_score >= 65 and quant_score < 60)
        or (quant_score >= 70 and (valuation_score is None or valuation_score < 55 or risk_score < 60))
        or (fundamental_score >= 60 and quant_score >= 55)
    ):
        label = SIGNAL_LABELS["accumulate"]
    elif final_score < 50 or fundamental_score < 45 or risk_score < 45 or quant_score < 45:
        label = SIGNAL_LABELS["avoid"]
    else:
        label = SIGNAL_LABELS["neutral"]

    return {
        "signal_label": label,
        "signal_score": None if insufficient else final_score,
        "signal_confidence": _confidence(data_quality_score, severe_count, missing_sections),
        "time_horizon": "medium_to_long_term",
        "rationale": _rationale(label, fundamental_score, quant_score, risk_score, final_score),
        "warnings": _warnings(label, risk_flags, valuation_score, data_quality),
        "not_investment_advice": True,
        "inputs": {
            "final_composite_score": final_score,
            "fundamental_score": fundamental_score,
            "quant_score": quant_score,
            "risk_score": risk_score,
            "valuation_score": valuation_score,
            "data_quality_score": data_quality_score,
            "major_risk_flags": risk_flags,
            "data_conflict_classification": composite.get("data_conflict_classification"),
        },
    }


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence(data_quality_score: float | None, severe_count: int, missing_sections: list[str]) -> str:
    if data_quality_score is None or data_quality_score < 50 or missing_sections:
        return "low"
    if data_quality_score >= 80 and severe_count == 0:
        return "high"
    return "medium"


def _rationale(label: str, fundamental: float | None, quant: float | None, risk: float | None, final: float | None) -> list[str]:
    items = []
    if final is not None:
        items.append(f"Final composite score is {final:.1f}.")
    if fundamental is not None:
        items.append(f"Fundamental score is {fundamental:.1f}.")
    if quant is not None:
        items.append(f"Quant score is {quant:.1f}.")
    if risk is not None:
        items.append(f"Risk score is {risk:.1f}; higher means lower risk.")
    if not items:
        items.append("Core deterministic inputs are insufficient for classification.")
    if label == SIGNAL_LABELS["insufficient"]:
        items.append("Classification is limited by missing core data.")
    return items


def _warnings(label: str, flags: list[str], valuation_score: float | None, data_quality: dict[str, Any]) -> list[str]:
    warnings = []
    if valuation_score is not None and valuation_score < 45:
        warnings.append("Valuation score is weak or expensive relative to deterministic thresholds.")
    warnings.extend(f"Risk flag: {flag}" for flag in flags[:6])
    for warning in data_quality.get("warnings") or []:
        warnings.append(str(warning))
    if label in {SIGNAL_LABELS["strong_buy"], SIGNAL_LABELS["buy"]}:
        warnings.append("This is a research candidate classification, not an instruction to buy.")
    if "Sell Risk" in label:
        warnings.append("Sell-risk language indicates risk classification only, not a direct sell order.")
    return warnings
