from __future__ import annotations

from core.schemas.risk import RiskScenarioResult, RiskTransmissionChannel
from pipelines.risk.aggregation import clamp_score


SCENARIO_PRESETS: dict[str, list[tuple[str, str, str, float]]] = {
    "base_adverse_severe": [
        ("base", "Base macro pressure path", "base", 0.0),
        ("adverse", "Adverse risk-off path", "adverse", 8.0),
        ("severe", "Severe liquidity and earnings stress", "severe", 18.0),
    ],
    "rates_credit_liquidity": [
        ("rate_shock", "Rate shock", "adverse", 10.0),
        ("credit_shock", "Credit spread shock", "adverse", 12.0),
        ("liquidity_shock", "Liquidity shock", "severe", 16.0),
    ],
    "inflation_growth_policy": [
        ("inflation_shock", "Inflation persistence shock", "adverse", 9.0),
        ("growth_shock", "Growth slowdown shock", "adverse", 11.0),
        ("policy_error", "Policy error shock", "severe", 17.0),
    ],
}


def build_scenario_matrix(
    base_risk_index: float | None,
    channels: list[RiskTransmissionChannel],
    *,
    scenario_set: str = "base_adverse_severe",
) -> list[RiskScenarioResult]:
    channel_pressure = sum(channel.risk_delta for channel in channels[:5]) / max(len(channels[:5]), 1) if channels else 0.0
    top_channels = [channel.channel for channel in sorted(channels, key=lambda item: item.risk_delta, reverse=True)[:4]]
    rows: list[RiskScenarioResult] = []
    for scenario_id, label, severity, base_delta in SCENARIO_PRESETS.get(scenario_set, SCENARIO_PRESETS["base_adverse_severe"]):
        delta = round(base_delta + channel_pressure * (0.20 if severity == "base" else 0.35 if severity == "adverse" else 0.55), 2)
        rows.append(
            RiskScenarioResult(
                scenario_id=scenario_id,
                label=label,
                severity=severity,  # type: ignore[arg-type]
                risk_index_delta=delta,
                projected_risk_index=None if base_risk_index is None else clamp_score(base_risk_index + delta),
                top_damage_channels=top_channels,
                notes=["Deterministic stress matrix; not a forecast or recommendation."],
            )
        )
    return rows

