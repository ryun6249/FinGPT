from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.schemas.quantamental import QuantamentalAnalysisRequest
from core.schemas.risk import RiskCompanyProfile, RiskEvidenceItem, RiskVector
from core.utils.asset_classifier import classify
from pipelines.quantamental import service as quantamental_service
from pipelines.risk.aggregation import average_score, clamp_score, inverse_score, risk_level, weighted_score


COMPANY_VECTOR_WEIGHTS = {
    "company_solvency": 0.25,
    "company_cash_flow_quality": 0.15,
    "company_earnings_quality": 0.15,
    "valuation_fragility": 0.20,
    "market_behavior": 0.25,
}

ASSET_PROXY_VECTOR_WEIGHTS = {
    "valuation_fragility": 0.10,
    "market_behavior": 0.65,
    "data_integrity": 0.25,
}


def load_company_payloads(request) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for ticker in request.tickers:
        q_request = QuantamentalAnalysisRequest(
            ticker=ticker,
            market=request.market,  # type: ignore[arg-type]
            period="annual",
            years=5,
            lookback=request.lookback_days,
            style="balanced",
            include_ai=False,
            include_sec=request.include_sec,
            use_llm=False,
            force_refresh=request.force_refresh,
            output_language=request.output_language,
        )
        payloads[ticker] = quantamental_service.analysis(q_request)
    return payloads


def _vector(
    name: str,
    score: float | None,
    *,
    confidence: float,
    drivers: list[str],
    evidence_refs: list[str],
    usable: bool,
) -> RiskVector:
    return RiskVector(
        vector=name,  # type: ignore[arg-type]
        score=score,
        level=risk_level(score),
        confidence=confidence,
        top_drivers=drivers[:4],
        evidence_refs=evidence_refs,
        decision_usable=usable and score is not None,
    )


def _has_price_payload(payload: dict[str, Any]) -> bool:
    quant = payload.get("quant") if isinstance(payload.get("quant"), dict) else {}
    metrics = quant.get("metrics") if isinstance(quant.get("metrics"), dict) else {}
    return (
        quant.get("status") == "ok"
        and (
            bool(quant.get("price_history"))
            or bool(metrics.get("volatility"))
            or bool(metrics.get("drawdown"))
        )
    )


def _is_asset_proxy_payload(ticker: str, payload: dict[str, Any]) -> bool:
    company = payload.get("company") if isinstance(payload.get("company"), dict) else {}
    asset_profile = classify(ticker)
    quote_type = str(company.get("quote_type") or "").upper()
    is_proxy = (
        asset_profile.is_etf
        or asset_profile.asset_class in {"bond_etf", "commodity_etf", "forex", "futures", "crypto"}
        or quote_type in {"ETF", "MUTUALFUND"}
    )
    return bool(is_proxy and _has_price_payload(payload))


def _payload_confidence(payload: dict[str, Any], *, asset_proxy: bool = False) -> float:
    quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    score = clamp_score(quality.get("data_quality_score"), default=50.0) or 50.0
    freshness_score = clamp_score(freshness.get("freshness_score"), default=score) or score
    integrity = payload.get("data_integrity") if isinstance(payload.get("data_integrity"), dict) else {}
    if integrity.get("status") == "blocked":
        if asset_proxy:
            return round((max(score, 50.0) + freshness_score) / 2.0, 2)
        return min(score, 25.0)
    return round((score + freshness_score) / 2.0, 2)


def build_company_profile(ticker: str, payload: dict[str, Any] | None) -> RiskCompanyProfile:
    clean_ticker = str(ticker or "").strip().upper()
    asset_profile = classify(clean_ticker)
    if not payload:
        vector = _vector(
            "data_integrity",
            100.0,
            confidence=0.0,
            drivers=["company payload unavailable"],
            evidence_refs=[],
            usable=False,
        )
        return RiskCompanyProfile(
            ticker=clean_ticker,
            asset_class=asset_profile.asset_class,
            coverage_scope="blocked",
            coverage_notes=["risk_profile_blocked_by_missing_company_or_price_data"],
            risk_index=None,
            risk_level="unknown",
            confidence=0.0,
            vectors=[vector],
            primary_drivers=["company payload unavailable"],
            decision_usable=False,
        )

    company = payload.get("company") if isinstance(payload.get("company"), dict) else {}
    risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    quant = payload.get("quant") if isinstance(payload.get("quant"), dict) else {}
    quant_metrics = quant.get("metrics") if isinstance(quant.get("metrics"), dict) else {}
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    asset_proxy = _is_asset_proxy_payload(clean_ticker, payload)
    confidence = _payload_confidence(payload, asset_proxy=asset_proxy)
    usable = (
        payload.get("status") not in {"failed", "error"}
        and (payload.get("data_integrity") or {}).get("status") != "blocked"
    ) or asset_proxy

    evidence_refs = [f"{clean_ticker}:freshness", f"{clean_ticker}:risk"]
    solvency = None if asset_proxy else inverse_score((risk.get("balance_sheet_risk") or {}).get("score"))
    cash_flow = None if asset_proxy else inverse_score(factors.get("quality_score"))
    earnings = None if asset_proxy else inverse_score(average_score([factors.get("growth_score"), factors.get("quality_score")]))
    valuation = (
        inverse_score((risk.get("valuation_risk") or {}).get("score"))
        if not asset_proxy or asset_profile.asset_class == "equity"
        else None
    )
    market_behavior = average_score([
        inverse_score((risk.get("price_risk") or {}).get("score")),
        inverse_score((risk.get("volatility_risk") or {}).get("score")),
        inverse_score((risk.get("drawdown_risk") or {}).get("score")),
    ])
    data_integrity = inverse_score(quality.get("data_quality_score"))

    drivers = list(risk.get("risk_flags") or [])
    coverage_notes = ["company_fundamentals_full_scope"]
    if asset_proxy:
        coverage_notes = ["asset_proxy_price_macro_scope", "fundamentals_not_applicable_for_etf"]
        drivers.extend(coverage_notes)
    if freshness.get("status") in {"stale", "partial"}:
        drivers.append(f"freshness_{freshness.get('status')}")
    if quality.get("missing_sections"):
        drivers.append("missing_" + ",".join(quality.get("missing_sections")[:3]))
    if not drivers:
        drivers.append("deterministic quantamental risk inputs")

    vectors = [
        _vector("company_solvency", solvency, confidence=confidence, drivers=drivers, evidence_refs=evidence_refs, usable=usable),
        _vector("company_cash_flow_quality", cash_flow, confidence=confidence, drivers=drivers, evidence_refs=evidence_refs, usable=usable),
        _vector("company_earnings_quality", earnings, confidence=confidence, drivers=drivers, evidence_refs=evidence_refs, usable=usable),
        _vector("valuation_fragility", valuation, confidence=confidence, drivers=drivers, evidence_refs=evidence_refs, usable=usable),
        _vector(
            "market_behavior",
            market_behavior,
            confidence=confidence,
            drivers=[
                f"realized volatility {(quant_metrics.get('volatility') or {}).get('realized_volatility_60d', 'unknown')}",
                f"drawdown {(quant_metrics.get('drawdown') or {}).get('current_drawdown', 'unknown')}",
            ],
            evidence_refs=evidence_refs,
            usable=usable,
        ),
        _vector(
            "data_integrity",
            data_integrity,
            confidence=confidence,
            drivers=list(quality.get("missing_sections") or quality.get("warnings") or ["data quality checked"]),
            evidence_refs=[f"{clean_ticker}:freshness"],
            usable=usable,
        ),
    ]
    score_by_vector = {vector.vector: vector.score for vector in vectors}
    risk_index = weighted_score(
        score_by_vector,
        ASSET_PROXY_VECTOR_WEIGHTS if asset_proxy else COMPANY_VECTOR_WEIGHTS,
    ) if usable else None
    return RiskCompanyProfile(
        ticker=clean_ticker,
        name=str(company.get("name") or ""),
        sector=str(company.get("sector") or ("ETF" if asset_profile.is_etf else "")),
        industry=str(company.get("industry") or asset_profile.display_name or ""),
        asset_class=asset_profile.asset_class,
        coverage_scope="asset_proxy" if asset_proxy else "company_full" if usable else "blocked",
        coverage_notes=coverage_notes,
        risk_index=risk_index,
        risk_level=risk_level(risk_index),
        confidence=confidence if usable else min(confidence, 25.0),
        vectors=vectors,
        primary_drivers=drivers[:5],
        evidence_refs=evidence_refs,
        decision_usable=usable and risk_index is not None,
    )


def company_evidence(ticker: str, payload: dict[str, Any] | None) -> list[RiskEvidenceItem]:
    clean_ticker = str(ticker or "").strip().upper()
    if not payload:
        return [
            RiskEvidenceItem(
                evidence_id=f"{clean_ticker}:missing",
                source="quantamental",
                label=f"{clean_ticker} company payload",
                value="missing",
                freshness="missing",
                notes=["No Quantamental payload was available for this risk run."],
            )
        ]
    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
    sec = payload.get("sec_evidence") if isinstance(payload.get("sec_evidence"), dict) else {}
    generated = str(payload.get("generated_at") or "")
    as_of = None
    if generated:
        try:
            as_of = datetime.fromisoformat(generated.replace("Z", "+00:00"))
        except ValueError:
            as_of = datetime.now(timezone.utc)
    items = [
        RiskEvidenceItem(
            evidence_id=f"{clean_ticker}:freshness",
            source="quantamental.freshness",
            label=f"{clean_ticker} freshness",
            value=freshness.get("status") or "unknown",
            as_of=as_of,
            freshness="stale" if freshness.get("status") == "stale" else "fresh" if freshness.get("status") == "fresh" else "unknown",
            notes=list(freshness.get("warnings") or []),
        ),
        RiskEvidenceItem(
            evidence_id=f"{clean_ticker}:risk",
            source="quantamental.risk_engine",
            label=f"{clean_ticker} deterministic risk score",
            value=(payload.get("risk") or {}).get("risk_score"),
            as_of=as_of,
            freshness="unknown",
            notes=list((payload.get("risk") or {}).get("risk_flags") or []),
        ),
        RiskEvidenceItem(
            evidence_id=f"{clean_ticker}:data_quality",
            source="quantamental.data_quality",
            label=f"{clean_ticker} data quality",
            value=quality.get("data_quality_score"),
            as_of=as_of,
            freshness="unknown",
            notes=list(quality.get("warnings") or []),
        ),
    ]
    if sec:
        items.append(
            RiskEvidenceItem(
                evidence_id=f"{clean_ticker}:sec",
                source="quantamental.sec_evidence",
                label=f"{clean_ticker} SEC evidence",
                value=sec.get("status") or "unknown",
                as_of=as_of,
                freshness="unknown",
                notes=list(sec.get("warnings") or []),
            )
        )
    return items
