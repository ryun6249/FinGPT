from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from core.config.settings import load_settings


SYSTEM_PROMPT = """You are a quantamental research interpreter.

Use only the deterministic Quantamental Engine payload supplied by the system.
Do not create, modify, or override scores, factor values, risk flags, signal
labels, or signal confidence. Interpret the deterministic signal as a research
classification only. Do not issue direct buy, sell, short, or position-sizing
orders. Use the supplied data_snapshot/used_data fields for basis date, source,
analysis period, observation count, missing data, and AI snapshot time. If a
field is missing, write "확인 불가" for Korean or "Unavailable" for English.
Return JSON only.
"""

_DIRECT_ORDER_RE = re.compile(
    r"\b(buy now|sell now|must buy|must sell|go long|go short|short it|all in|liquidate)\b|"
    r"무조건\s*(매수|매도)|반드시\s*(매수|매도)|전량\s*(매수|매도)",
    re.IGNORECASE,
)


def build_context(analysis: dict[str, Any]) -> dict[str, Any]:
    company = analysis.get("company") or {}
    composite = analysis.get("composite") or {}
    signal = analysis.get("signal") or {}
    factors = analysis.get("factors") or {}
    risk = analysis.get("risk") or {}
    data_quality = analysis.get("data_quality") or {}
    fundamentals = analysis.get("fundamentals") or {}
    quant = analysis.get("quant") or {}
    quant_algorithm = ((quant.get("metrics") or {}).get("algorithm") or {}) if isinstance(quant, dict) else {}
    quant_algorithms = ((quant.get("metrics") or {}).get("algorithms") or {}) if isinstance(quant, dict) else {}
    if quant_algorithm and not quant_algorithms.get("quality_adjusted_momentum"):
        quant_algorithms = {**quant_algorithms, "quality_adjusted_momentum": quant_algorithm}
    sec_evidence = analysis.get("sec_evidence") or {}
    peer_relative = analysis.get("peer_relative") or {}
    used_data = _build_used_data_snapshot(
        analysis=analysis,
        company=company,
        fundamentals=fundamentals,
        quant=quant,
        data_quality=data_quality,
        sec_evidence=sec_evidence,
    )
    return {
        "ticker": analysis.get("ticker") or company.get("ticker"),
        "market": analysis.get("market") or company.get("market"),
        "output_language": analysis.get("output_language") or "ko",
        "used_data": used_data,
        "data_snapshot": used_data,
        "company": {
            "name": company.get("name"),
            "sector": company.get("sector"),
            "industry": company.get("industry"),
            "current_price": company.get("current_price"),
            "market_cap": company.get("market_cap"),
        },
        "deterministic_scores": {
            "final_score": composite.get("final_score"),
            "fundamental_score": composite.get("fundamental_score"),
            "quant_score": composite.get("quant_score"),
            "risk_score": composite.get("risk_score"),
            "factor_scores": composite.get("factor_scores") or {
                key: factors.get(key)
                for key in (
                    "value_score",
                    "quality_score",
                    "growth_score",
                    "momentum_score",
                    "low_volatility_score",
                    "liquidity_score",
                )
            },
            "conflict": composite.get("data_conflict_classification"),
        },
        "deterministic_signal": {
            "signal_label": signal.get("signal_label"),
            "signal_score": signal.get("signal_score"),
            "signal_confidence": signal.get("signal_confidence"),
            "rationale": signal.get("rationale") or [],
            "warnings": signal.get("warnings") or [],
            "not_investment_advice": signal.get("not_investment_advice", True),
        },
        "risk": {
            "risk_level": risk.get("risk_level"),
            "risk_flags": risk.get("risk_flags") or [],
            "risk_summary": risk.get("risk_summary"),
        },
        "peer_relative": {
            "status": peer_relative.get("status"),
            "scope": peer_relative.get("scope"),
            "group_key": peer_relative.get("group_key"),
            "peer_count": peer_relative.get("peer_count"),
            "relative_strength_score": peer_relative.get("relative_strength_score"),
            "rank": peer_relative.get("rank"),
        },
        "sec_evidence": {
            "status": sec_evidence.get("status"),
            "latest_filing_at": sec_evidence.get("latest_filing_at"),
            "filing_count": sec_evidence.get("filing_count"),
            "fact_count": sec_evidence.get("fact_count"),
            "risk_flags": sec_evidence.get("risk_flags") or [],
            "quality_flags": sec_evidence.get("quality_flags") or [],
            "concept_provenance": (sec_evidence.get("concept_provenance") or [])[:8],
            "filing_excerpts": (sec_evidence.get("filing_excerpts") or [])[:3],
            "warnings": sec_evidence.get("warnings") or [],
        },
        "data_quality": {
            "score": data_quality.get("data_quality_score"),
            "level": data_quality.get("quality_level"),
            "missing_sections": data_quality.get("missing_sections") or [],
            "warnings": data_quality.get("warnings") or [],
        },
        "fundamental_snapshot": {
            "category_scores": fundamentals.get("category_scores") or {},
            "missing_metrics": (fundamentals.get("missing_metrics") or [])[:20],
        },
        "quant_snapshot": {
            "component_scores": quant.get("component_scores") or {},
            "quality_adjusted_momentum": quant_algorithm,
            "volatility_adjusted_breakout": quant_algorithms.get("volatility_adjusted_breakout") or {},
            "drawdown_recovery_resilience": quant_algorithms.get("drawdown_recovery_resilience") or {},
            "liquidity_participation_stability": quant_algorithms.get("liquidity_participation_stability") or {},
            "trend_efficiency_stability": quant_algorithms.get("trend_efficiency_stability") or {},
            "algorithms": quant_algorithms,
            "missing_metrics": (quant.get("missing_metrics") or [])[:20],
        },
    }


def _first_available(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _source_from_payload(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("source_metadata") if isinstance(payload.get("source_metadata"), dict) else {}
    return _first_available(
        payload.get("provider"),
        payload.get("source"),
        payload.get("data_source"),
        metadata.get("provider"),
        metadata.get("source"),
        metadata.get("data_source"),
    )


def _observation_count(quant: dict[str, Any], analysis: dict[str, Any]) -> int | None:
    explicit = _first_available(
        quant.get("observation_count"),
        quant.get("price_count"),
        analysis.get("observation_count"),
    )
    if isinstance(explicit, (int, float)):
        return int(explicit)
    for key in ("prices", "price_rows", "returns", "rows", "series"):
        value = quant.get(key)
        if isinstance(value, list):
            return len(value)
    chart_data = quant.get("chart_data")
    if isinstance(chart_data, dict):
        lengths = [len(value) for value in chart_data.values() if isinstance(value, list)]
        if lengths:
            return max(lengths)
    return None


def _build_used_data_snapshot(
    *,
    analysis: dict[str, Any],
    company: dict[str, Any],
    fundamentals: dict[str, Any],
    quant: dict[str, Any],
    data_quality: dict[str, Any],
    sec_evidence: dict[str, Any],
) -> dict[str, Any]:
    freshness = data_quality.get("freshness") if isinstance(data_quality.get("freshness"), dict) else {}
    sources = [
        _source_from_payload(quant),
        _source_from_payload(fundamentals),
        _source_from_payload(company),
        _source_from_payload(sec_evidence),
        _source_from_payload(data_quality),
    ]
    source_text = ", ".join(dict.fromkeys(str(source) for source in sources if source)) or None
    missing_sections = data_quality.get("missing_sections") or []
    missing_metrics = [
        *(fundamentals.get("missing_metrics") or []),
        *(quant.get("missing_metrics") or []),
    ]
    missing_data = [*missing_sections, *missing_metrics[:20]]
    return {
        "data_basis_date": _first_available(
            freshness.get("as_of"),
            data_quality.get("as_of"),
            quant.get("latest_date"),
            quant.get("as_of"),
            company.get("latest_price_date"),
            fundamentals.get("latest_statement_date"),
            sec_evidence.get("latest_filing_at"),
            analysis.get("generated_at"),
        ),
        "analysis_period": _first_available(
            quant.get("analysis_period"),
            quant.get("lookback_days") and f"{quant.get('lookback_days')}d",
            analysis.get("lookback_days") and f"{analysis.get('lookback_days')}d",
            fundamentals.get("period") and f"{fundamentals.get('period')} {fundamentals.get('years') or ''}".strip(),
        ),
        "data_source": source_text,
        "observation_count": _observation_count(quant, analysis),
        "missing_data": missing_data,
        "cache_state": _first_available(freshness.get("cache_state"), data_quality.get("cache_state")),
        "ai_snapshot_at": _first_available(analysis.get("generated_at"), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    }


def generate_report(
    context: dict[str, Any],
    *,
    use_llm: bool = False,
    model: str | None = None,
    timeout_s: float = 30.0,
    language: str = "ko",
) -> dict[str, Any]:
    language = _normalize_language(language or context.get("output_language"))
    context = {**context, "model": model or context.get("model")}
    fallback = _fallback_report(context, language=language)
    if not use_llm:
        fallback["warnings"].append("llm_not_used_deterministic_interpreter_active")
        return fallback
    try:
        raw_text, provider, latency_s = _call_local_llm(context, model=model, timeout_s=timeout_s, language=language)
        parsed = _parse_report(raw_text, expected_signal=_signal_label(context))
        parsed = _enforce_report_guardrails(parsed, context, language=language)
        if _DIRECT_ORDER_RE.search(json.dumps(parsed, ensure_ascii=False)):
            raise ValueError("direct_order_language_detected")
        parsed.update(
            {
                "status": "success",
                "provider": provider,
                "latency_s": latency_s,
                "prompt_template": SYSTEM_PROMPT,
                "signal_label": _signal_label(context),
                "signal_preserved": True,
                "not_investment_advice": True,
                "output_language": language,
                "warnings": [
                    f"llm_latency_s={latency_s}",
                    "deterministic_signal_preserved",
                    "advisory_only_guard_passed",
                    "json_schema_guard_passed",
                ],
            }
        )
        return parsed
    except Exception as exc:  # noqa: BLE001
        fallback["warnings"] = [
            "llm_provider_failed_or_rejected_output",
            f"fallback_reason:{type(exc).__name__}:{exc}",
            "deterministic_interpreter_active",
        ]
        return fallback


def _unavailable(language: str) -> str:
    return "Unavailable" if language == "en" else "확인 불가"


def _report_used_data(context: dict[str, Any], *, language: str) -> dict[str, Any]:
    used_data = context.get("used_data") or context.get("data_snapshot") or {}
    missing = used_data.get("missing_data")
    if isinstance(missing, list):
        missing_text = ", ".join(str(item) for item in missing[:20]) if missing else ("None identified" if language == "en" else "없음")
    else:
        missing_text = missing or _unavailable(language)
    return {
        "data_basis_date": used_data.get("data_basis_date") or _unavailable(language),
        "analysis_period": used_data.get("analysis_period") or _unavailable(language),
        "data_source": used_data.get("data_source") or _unavailable(language),
        "observation_count": used_data.get("observation_count") if used_data.get("observation_count") is not None else _unavailable(language),
        "missing_data": missing_text,
        "model": context.get("model") or _unavailable(language),
        "ai_snapshot_at": used_data.get("ai_snapshot_at") or _unavailable(language),
        "cache_state": used_data.get("cache_state") or _unavailable(language),
    }


def _key_changes(context: dict[str, Any], *, language: str) -> dict[str, Any]:
    scores = context.get("deterministic_scores") or {}
    risk = context.get("risk") or {}
    unavailable = _unavailable(language)
    factor_scores = scores.get("factor_scores") or {}
    quant_algorithm = ((context.get("quant_snapshot") or {}).get("quality_adjusted_momentum") or {})
    algorithm_text = _algorithm_change_text(quant_algorithm, unavailable=unavailable, language=language)
    if language == "en":
        return {
            "price": "Use deterministic quant components only; raw price change is unavailable." if scores.get("quant_score") is None else f"Quant score: {scores.get('quant_score')}.",
            "volume": unavailable,
            "volatility": f"Risk level: {risk.get('risk_level') or unavailable}.",
            "trend": f"Momentum score: {factor_scores.get('momentum_score', unavailable)}.",
            "quant_algorithm": algorithm_text,
            "risk": risk.get("risk_summary") or f"Risk score: {scores.get('risk_score', unavailable)}.",
        }
    return {
        "가격": "원시 가격 변화는 확인 불가이며 deterministic quant component만 사용했습니다." if scores.get("quant_score") is None else f"퀀트 점수: {scores.get('quant_score')}.",
        "거래량": unavailable,
        "변동성": f"리스크 수준: {risk.get('risk_level') or unavailable}.",
        "추세": f"모멘텀 점수: {factor_scores.get('momentum_score', unavailable)}.",
        "리스크": risk.get("risk_summary") or f"리스크 점수: {scores.get('risk_score', unavailable)}.",
    }


def _algorithm_change_text(algorithm: dict[str, Any], *, unavailable: str, language: str) -> str:
    if not algorithm:
        return unavailable
    score_key = (
        "quality_adjusted_momentum_score"
        if "quality_adjusted_momentum_score" in algorithm
        else "volatility_adjusted_breakout_score"
        if "volatility_adjusted_breakout_score" in algorithm
        else "drawdown_recovery_resilience_score"
        if "drawdown_recovery_resilience_score" in algorithm
        else "liquidity_participation_stability_score"
        if "liquidity_participation_stability_score" in algorithm
        else "trend_efficiency_stability_score"
        if "trend_efficiency_stability_score" in algorithm
        else "score"
    )
    score = algorithm.get(score_key)
    classification = algorithm.get("classification") or unavailable
    algorithm_id = algorithm.get("algorithm_id") or "unknown_quant_algorithm"
    if score is None:
        return (
            f"{algorithm_id}: unavailable; classification={classification}."
            if language == "en"
            else f"{algorithm_id}: 확인 불가; classification={classification}."
        )
    return (
        f"{algorithm_id}: score={score}, classification={classification}; not used in the composite score."
        if language == "en"
        else f"{algorithm_id}: 점수={score}, classification={classification}; composite 점수에는 반영하지 않았습니다."
    )


def _interpretation(context: dict[str, Any], *, language: str) -> dict[str, Any]:
    signal = context.get("deterministic_signal") or {}
    quality = context.get("data_quality") or {}
    rationale = signal.get("rationale") or []
    missing = quality.get("missing_sections") or []
    if language == "en":
        return {
            "data_supported": rationale[:6] or ["Only the deterministic signal label is available."],
            "unavailable": missing[:10] or ["No additional unavailable sections were reported."],
            "cautions": [
                "This is a research classification, not investment advice.",
                "Predictions are not stated as facts.",
            ],
        }
    return {
        "데이터로 확인되는 내용": rationale[:6] or ["deterministic signal label만 확인되었습니다."],
        "확인 불가능한 내용": missing[:10] or ["추가 확인 불가 항목은 보고되지 않았습니다."],
        "주의할 점": [
            "이 결과는 리서치 분류이며 투자 조언이 아닙니다.",
            "예측은 확정 사실로 표현하지 않습니다.",
        ],
    }


def _scenario_section(context: dict[str, Any], *, language: str) -> dict[str, str]:
    signal = context.get("deterministic_signal") or {}
    signal_label = signal.get("signal_label") or _unavailable(language)
    if language == "en":
        return {
            "positive": f"Positive case requires deterministic score/risk evidence to improve while the signal remains {signal_label}.",
            "neutral": "Neutral case is continued mixed evidence or unchanged data quality.",
            "negative": "Negative case is weaker deterministic scores, new risk flags, or lower data quality.",
        }
    return {
        "긍정 시나리오": f"deterministic 점수와 리스크 근거가 개선되고 신호가 {signal_label} 범위에서 유지되는 경우입니다.",
        "중립 시나리오": "혼재된 근거 또는 데이터 품질이 크게 변하지 않는 경우입니다.",
        "부정 시나리오": "deterministic 점수 악화, 신규 리스크 플래그, 데이터 품질 저하가 나타나는 경우입니다.",
    }


def _user_actions(context: dict[str, Any], *, language: str) -> dict[str, str]:
    used_data = _report_used_data(context, language=language)
    if language == "en":
        return {
            "metrics_to_check": "Review deterministic score components, risk flags, and missing data.",
            "additional_period": f"Compare against the current analysis period: {used_data['analysis_period']}.",
            "risks_to_watch": "Check provider freshness, missing observations, and signal/risk conflicts.",
        }
    return {
        "확인할 지표": "deterministic 점수 구성, 리스크 플래그, 결측 데이터를 확인하세요.",
        "추가로 볼 기간": f"현재 분석 기간({used_data['analysis_period']})과 다른 기간을 비교하세요.",
        "주의할 리스크": "공급자 신선도, 결측 관측치, 신호와 리스크 간 충돌을 확인하세요.",
    }


def _enforce_report_guardrails(parsed: dict[str, Any], context: dict[str, Any], *, language: str) -> dict[str, Any]:
    report = parsed.setdefault("report", {})
    report.setdefault("used_data", _report_used_data(context, language=language))
    report.setdefault("key_changes", _key_changes(context, language=language))
    report.setdefault("interpretation", _interpretation(context, language=language))
    report.setdefault("scenarios", _scenario_section(context, language=language))
    report.setdefault("user_actions", _user_actions(context, language=language))
    parsed.setdefault("data_snapshot", context.get("used_data") or context.get("data_snapshot") or {})
    parsed.setdefault(
        "guardrails",
        [
            "deterministic_inputs_only",
            "unsupported_values_marked_unavailable",
            "advisory_only_no_direct_orders",
        ],
    )
    return parsed


def _fallback_report(context: dict[str, Any], *, language: str = "ko") -> dict[str, Any]:
    signal = context.get("deterministic_signal") or {}
    scores = context.get("deterministic_scores") or {}
    risk = context.get("risk") or {}
    quality = context.get("data_quality") or {}
    company = context.get("company") or {}
    signal_label = _signal_label(context)
    if language == "en":
        report = {
            "summary": (
                f"{context.get('ticker') or 'ticker'} is classified as {signal_label} by the "
                "deterministic Quantamental Signal Engine."
            ),
            "signal_interpretation": {
                "label": signal_label,
                "confidence": signal.get("signal_confidence"),
                "score": signal.get("signal_score"),
                "rationale": signal.get("rationale") or [],
            },
            "bull_case": _bull_case(scores, company, language=language),
            "bear_case": _bear_case(scores, risk, quality, language=language),
            "conflict_analysis": (
                f"Conflict classification: {scores.get('conflict') or 'mixed_or_insufficient_data'}."
            ),
            "missing_data_warning": _missing_data_warning(quality, language=language),
            "safety_note": (
                "This report interprets deterministic research classifications only. "
                "It is not investment advice and does not instruct buy or sell orders."
            ),
        }
    else:
        report = {
            "summary": (
                f"{context.get('ticker') or 'ticker'}는 deterministic Quantamental Signal Engine 기준 "
                f"{signal_label} 리서치 분류입니다."
            ),
            "signal_interpretation": {
                "label": signal_label,
                "confidence": signal.get("signal_confidence"),
                "score": signal.get("signal_score"),
                "rationale": signal.get("rationale") or [],
            },
            "bull_case": _bull_case(scores, company, language=language),
            "bear_case": _bear_case(scores, risk, quality, language=language),
            "conflict_analysis": (
                f"충돌 분류: {scores.get('conflict') or 'mixed_or_insufficient_data'}."
            ),
            "missing_data_warning": _missing_data_warning(quality, language=language),
            "safety_note": (
                "이 보고서는 deterministic 리서치 분류만 해석합니다. "
                "투자 자문이 아니며 매수/매도 지시를 제공하지 않습니다."
            ),
        }
    report.update(
        {
            "used_data": _report_used_data(context, language=language),
            "key_changes": _key_changes(context, language=language),
            "interpretation": _interpretation(context, language=language),
            "scenarios": _scenario_section(context, language=language),
            "user_actions": _user_actions(context, language=language),
        }
    )
    quant_algorithm = ((context.get("quant_snapshot") or {}).get("quality_adjusted_momentum") or {})
    if quant_algorithm:
        key_changes = dict(report.get("key_changes") or {})
        key_changes.setdefault(
            "quant_algorithm",
            _algorithm_change_text(quant_algorithm, unavailable=_unavailable(language), language=language),
        )
        report["key_changes"] = key_changes
    breakout_algorithm = ((context.get("quant_snapshot") or {}).get("volatility_adjusted_breakout") or {})
    if breakout_algorithm:
        key_changes = dict(report.get("key_changes") or {})
        key_changes.setdefault(
            "secondary_quant_algorithm",
            _algorithm_change_text(breakout_algorithm, unavailable=_unavailable(language), language=language),
        )
        report["key_changes"] = key_changes
    resilience_algorithm = ((context.get("quant_snapshot") or {}).get("drawdown_recovery_resilience") or {})
    if resilience_algorithm:
        key_changes = dict(report.get("key_changes") or {})
        key_changes.setdefault(
            "drawdown_recovery_algorithm",
            _algorithm_change_text(resilience_algorithm, unavailable=_unavailable(language), language=language),
        )
        report["key_changes"] = key_changes
    liquidity_stability_algorithm = ((context.get("quant_snapshot") or {}).get("liquidity_participation_stability") or {})
    if liquidity_stability_algorithm:
        key_changes = dict(report.get("key_changes") or {})
        key_changes.setdefault(
            "liquidity_stability_algorithm",
            _algorithm_change_text(liquidity_stability_algorithm, unavailable=_unavailable(language), language=language),
        )
        report["key_changes"] = key_changes
    trend_efficiency_algorithm = ((context.get("quant_snapshot") or {}).get("trend_efficiency_stability") or {})
    if trend_efficiency_algorithm:
        key_changes = dict(report.get("key_changes") or {})
        key_changes.setdefault(
            "trend_efficiency_algorithm",
            _algorithm_change_text(trend_efficiency_algorithm, unavailable=_unavailable(language), language=language),
        )
        report["key_changes"] = key_changes
    return {
        "status": "partial",
        "provider": "deterministic_interpreter",
        "prompt_template": SYSTEM_PROMPT,
        "signal_label": signal_label,
        "signal_preserved": True,
        "output_language": language,
        "report": report,
        "data_snapshot": context.get("used_data") or context.get("data_snapshot") or {},
        "guardrails": [
            "deterministic_inputs_only",
            "unsupported_values_marked_unavailable",
            "advisory_only_no_direct_orders",
        ],
        "warnings": [],
        "not_investment_advice": True,
        "source_policy": "ai_interprets_deterministic_engine_only",
    }


def _bull_case(scores: dict[str, Any], company: dict[str, Any], *, language: str = "ko") -> list[str]:
    out = []
    if scores.get("fundamental_score") is not None:
        out.append(
            f"Fundamental score: {scores.get('fundamental_score')}."
            if language == "en"
            else f"펀더멘털 점수: {scores.get('fundamental_score')}."
        )
    if scores.get("quant_score") is not None:
        out.append(
            f"Quant score: {scores.get('quant_score')}."
            if language == "en"
            else f"퀀트 점수: {scores.get('quant_score')}."
        )
    factor_scores = scores.get("factor_scores") or {}
    best = sorted(
        [(key, value) for key, value in factor_scores.items() if isinstance(value, (int, float))],
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    if best:
        prefix = "Stronger factors: " if language == "en" else "강한 팩터: "
        out.append(prefix + ", ".join(f"{key}={value}" for key, value in best) + ".")
    if company.get("sector"):
        out.append(
            f"Company context: {company.get('sector')} / {company.get('industry') or 'industry unavailable'}."
            if language == "en"
            else f"기업 맥락: {company.get('sector')} / {company.get('industry') or '산업 정보 없음'}."
        )
    return out or (["Bull case is limited by missing deterministic inputs."] if language == "en" else ["상승 근거는 누락된 deterministic 입력 때문에 제한적입니다."])


def _bear_case(scores: dict[str, Any], risk: dict[str, Any], quality: dict[str, Any], *, language: str = "ko") -> list[str]:
    out = []
    if scores.get("risk_score") is not None:
        out.append(
            f"Risk score: {scores.get('risk_score')} ({risk.get('risk_level') or 'unknown'})."
            if language == "en"
            else f"리스크 점수: {scores.get('risk_score')} ({risk.get('risk_level') or 'unknown'})."
        )
    if risk.get("risk_flags"):
        prefix = "Risk flags: " if language == "en" else "리스크 플래그: "
        out.append(prefix + ", ".join(str(item) for item in risk.get("risk_flags")[:6]) + ".")
    if quality.get("level") in {"poor", "limited"}:
        out.append(
            f"Data quality is {quality.get('level')} with score {quality.get('score')}."
            if language == "en"
            else f"데이터 품질은 {quality.get('level')}이며 점수는 {quality.get('score')}입니다."
        )
    return out or (["No major deterministic risk flags were available."] if language == "en" else ["주요 deterministic 리스크 플래그는 확인되지 않았습니다."])


def _missing_data_warning(quality: dict[str, Any], *, language: str = "ko") -> str:
    missing = quality.get("missing_sections") or []
    warnings = quality.get("warnings") or []
    if not missing and not warnings:
        return (
            "No major data-quality warning from available deterministic checks."
            if language == "en"
            else "현재 deterministic 점검에서 주요 데이터 품질 경고는 없습니다."
        )
    prefix = "Missing or limited data: " if language == "en" else "누락 또는 제한 데이터: "
    return prefix + ", ".join(str(item) for item in [*missing, *warnings][:10])


def _call_local_llm(context: dict[str, Any], *, model: str | None, timeout_s: float, language: str) -> tuple[str, str, float]:
    settings = load_settings()
    selected_model = model or str(settings.primary_model or "qwen2.5:7b")
    language_instruction = (
        "Write all human-readable report fields in Korean."
        if language == "ko"
        else "Write all human-readable report fields in English."
    )
    prompt = (
        SYSTEM_PROMPT
        + f"\n{language_instruction}\nReturn JSON with keys: report.summary, report.signal_interpretation, report.bull_case, "
        + "report.bear_case, report.conflict_analysis, report.missing_data_warning, report.safety_note, "
        + "report.used_data, report.key_changes, report.interpretation, report.scenarios, report.user_actions. "
        + "Use context.used_data exactly for basis date/source/period/observations; do not calculate unsupported values. "
        + "Preserve deterministic_signal.signal_label exactly.\n\nQUANTAMENTAL_CONTEXT_JSON:\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    )
    started = time.time()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": selected_model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1000},
            "keep_alive": "5m",
        },
        timeout=max(1.0, min(float(timeout_s or 30.0), 90.0)),
    )
    response.raise_for_status()
    body = response.json()
    text = str(body.get("response") or "").strip()
    if not text:
        raise ValueError("empty_llm_response")
    return text, f"ollama:{selected_model}", round(time.time() - started, 2)


def _parse_report(raw_text: str, *, expected_signal: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed_json:{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("json_root_not_object")
    report = parsed.get("report")
    if not isinstance(report, dict):
        raise ValueError("missing_report_object")
    required = [
        "summary",
        "signal_interpretation",
        "bull_case",
        "bear_case",
        "conflict_analysis",
        "missing_data_warning",
        "safety_note",
    ]
    missing = [key for key in required if key not in report]
    if missing:
        raise ValueError(f"missing_report_keys:{','.join(missing)}")
    signal_interpretation = report.get("signal_interpretation") or {}
    if isinstance(signal_interpretation, dict):
        output_signal = signal_interpretation.get("label") or parsed.get("signal_label")
        if expected_signal and output_signal and output_signal != expected_signal:
            raise ValueError("ai_signal_override_detected")
    return {"report": report}


def _signal_label(context: dict[str, Any]) -> str | None:
    signal = context.get("deterministic_signal") or {}
    return signal.get("signal_label")


def _normalize_language(value: Any) -> str:
    clean = str(value or "ko").strip().lower()
    return "en" if clean in {"en", "eng", "english"} else "ko"
