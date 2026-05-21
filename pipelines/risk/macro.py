from __future__ import annotations

from typing import Any

from core.schemas.risk import RiskEvidenceItem, RiskMacroBackdrop, RiskVector
from pipelines.macro.dashboard import build_macro_dashboard
from pipelines.risk.aggregation import average_score, clamp_score, risk_level


def load_macro_payload() -> dict[str, Any]:
    return build_macro_dashboard(observation_limit=20).model_dump(mode="json")


def _score_from_macro_level(value: Any) -> float | None:
    clean = str(value or "").lower()
    if clean in {"high", "reduce", "risk_off", "stress"}:
        return 80.0
    if clean in {"elevated", "watch", "tight", "restrictive"}:
        return 65.0
    if clean in {"moderate", "neutral", "mixed"}:
        return 45.0
    if clean in {"low", "supportive", "risk_on"}:
        return 20.0
    return None


def _signal_score(signals: list[dict[str, Any]], *tokens: str) -> float | None:
    scores: list[float | None] = []
    for signal in signals:
        haystack = " ".join(
            str(signal.get(key) or "")
            for key in ("signal_id", "name", "title", "direction", "status", "summary")
        ).lower()
        if not any(token in haystack for token in tokens):
            continue
        if signal.get("score") is not None:
            scores.append(clamp_score(signal.get("score")))
        else:
            scores.append(_score_from_macro_level(signal.get("status") or signal.get("direction")))
    return average_score(scores)


def build_macro_backdrop(payload: dict[str, Any] | None) -> RiskMacroBackdrop:
    macro = payload or {}
    overview = macro.get("overview") if isinstance(macro.get("overview"), dict) else {}
    regime = overview.get("regime") if isinstance(overview.get("regime"), dict) else {}
    signals = [item for item in overview.get("signals") or [] if isinstance(item, dict)]
    quality = macro.get("data_quality") if isinstance(macro.get("data_quality"), dict) else {}
    coverage = macro.get("coverage") if isinstance(macro.get("coverage"), dict) else {}
    confidence = regime.get("confidence")
    if confidence is None:
        confidence = 75.0 if macro.get("status") == "ok" else 45.0
    else:
        confidence = float(confidence) * 100.0 if float(confidence) <= 1.0 else float(confidence)
    confidence = clamp_score(confidence, default=45.0) or 45.0

    regime_score = _score_from_macro_level(regime.get("risk_level")) or _signal_score(signals, "regime", "risk")
    rates_score = _signal_score(signals, "rate", "yield", "policy") or regime_score
    growth_score = _signal_score(signals, "growth", "labor", "inflation", "cpi", "pce") or regime_score
    credit_score = _signal_score(signals, "credit", "liquidity", "spread", "financial") or regime_score
    if str(quality.get("status") or macro.get("status") or "").lower() in {"partial", "stale", "unavailable"}:
        credit_score = max(credit_score or 50.0, 55.0)

    evidence_ref = "macro:dashboard"
    vectors = [
        RiskVector(
            vector="macro_policy_rates",
            score=clamp_score(rates_score),
            level=risk_level(clamp_score(rates_score)),
            confidence=confidence,
            top_drivers=["policy and rate-sensitive macro signals"],
            evidence_refs=[evidence_ref],
            decision_usable=rates_score is not None,
        ),
        RiskVector(
            vector="macro_growth_inflation",
            score=clamp_score(growth_score),
            level=risk_level(clamp_score(growth_score)),
            confidence=confidence,
            top_drivers=["growth, labor, and inflation pressure"],
            evidence_refs=[evidence_ref],
            decision_usable=growth_score is not None,
        ),
        RiskVector(
            vector="credit_liquidity",
            score=clamp_score(credit_score),
            level=risk_level(clamp_score(credit_score)),
            confidence=confidence,
            top_drivers=["credit, liquidity, and provider quality pressure"],
            evidence_refs=[evidence_ref],
            decision_usable=credit_score is not None,
        ),
    ]
    pressures = [
        str(item.get("name") or item.get("signal_id") or item.get("title"))
        for item in signals[:6]
        if item.get("name") or item.get("signal_id") or item.get("title")
    ]
    if coverage:
        pressures.append(f"macro coverage {coverage.get('enabled_series') or coverage.get('registry_series') or 0} series")
    return RiskMacroBackdrop(
        regime=str(regime.get("name") or regime.get("display_name") or "unknown"),
        risk_level=risk_level(average_score([vector.score for vector in vectors])),
        confidence=confidence,
        vectors=vectors,
        primary_pressures=pressures[:8],
        evidence_refs=[evidence_ref],
    )


def macro_evidence(payload: dict[str, Any] | None) -> list[RiskEvidenceItem]:
    macro = payload or {}
    quality = macro.get("data_quality") if isinstance(macro.get("data_quality"), dict) else {}
    coverage = macro.get("coverage") if isinstance(macro.get("coverage"), dict) else {}
    freshness = "fresh" if macro.get("status") == "ok" else "stale" if macro.get("status") == "stale" else "unknown"
    return [
        RiskEvidenceItem(
            evidence_id="macro:dashboard",
            source="pipelines.macro.dashboard",
            label="Macro dashboard quality and coverage",
            value=quality.get("status") or macro.get("status") or "unknown",
            freshness=freshness,  # type: ignore[arg-type]
            notes=[
                f"enabled_series={coverage.get('enabled_series', coverage.get('registry_series', 0))}",
                *[str(item) for item in macro.get("warnings") or []],
            ],
        )
    ]

