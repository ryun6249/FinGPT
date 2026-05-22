from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from core.schemas.risk import (
    RiskActionItem,
    RiskAiOutputControls,
    RiskCalculationPolicy,
    RiskConfidenceFactor,
    RiskCompatibilityMatrix,
    RiskCompatibilityRow,
    RiskDecisionBrief,
    RiskDecisionCompass,
    RiskDecisionCompassStep,
    RiskEvidenceCoverage,
    RiskEvidenceCoverageItem,
    RiskDecisionQuality,
    RiskDecisionPath,
    RiskHandoffItem,
    RiskInputPositionReceipt,
    RiskInputReceipt,
    RiskForecastValidationPlan,
    RiskMlForecastPrefill,
    RiskMlValidationTest,
    RiskMonitoringTrigger,
    RiskPortfolioOverlay,
    RiskPriorityCell,
    RiskReleaseCheck,
    RiskReleasePacket,
    RiskRunLineage,
    RiskServiceReadiness,
    RiskWorkbenchRequest,
    RiskWorkbenchResponse,
)
from pipelines.risk.aggregation import (
    BASE_RISK_WEIGHTS,
    PORTFOLIO_RISK_WEIGHTS,
    average_score,
    concentration_penalty,
    driver_contributions,
    risk_level,
    stable_input_hash,
    weighted_score,
)
from pipelines.risk.company import build_company_profile, company_evidence
from pipelines.risk.data_quality import evaluate_risk_data_quality
from pipelines.risk.macro import build_macro_backdrop, macro_evidence
from pipelines.risk.scenario import build_scenario_matrix
from pipelines.risk.transmission import build_transmission_channels


def _positions_by_ticker(request: RiskWorkbenchRequest) -> dict[str, float]:
    if request.positions:
        total = sum(position.weight for position in request.positions) or 1.0
        return {position.ticker: position.weight / total for position in request.positions}
    if not request.tickers:
        return {}
    weight = 1.0 / len(request.tickers)
    return {ticker: weight for ticker in request.tickers}


def _profile_vector_score(profile, vector_name: str) -> float | None:
    return average_score([vector.score for vector in profile.vectors if vector.vector == vector_name])


def _weighted_profile_score(company_profiles, weights: dict[str, float], vector_name: str | None = None) -> float | None:
    values: list[float] = []
    value_weights: list[float] = []
    for profile in company_profiles:
        score = _profile_vector_score(profile, vector_name) if vector_name else profile.risk_index
        if score is None:
            continue
        values.append(float(score))
        value_weights.append(float(weights.get(profile.ticker, 0.0)))
    total = sum(value_weights)
    if total <= 0:
        return average_score(values)
    return round(sum(value * weight for value, weight in zip(values, value_weights)) / total, 2)


def _macro_vector_score(macro_backdrop, vector_name: str) -> float | None:
    return average_score([vector.score for vector in macro_backdrop.vectors if vector.vector == vector_name])


def _portfolio_overlay(
    request: RiskWorkbenchRequest,
    company_profiles,
    scenario_matrix,
) -> RiskPortfolioOverlay | None:
    if request.mode != "portfolio" or not request.positions:
        return None
    weights = _positions_by_ticker(request)
    weighted_risk = _weighted_profile_score(company_profiles, weights)
    concentration = concentration_penalty([position.weight for position in request.positions])
    contributors = sorted(
        (
            (profile.ticker, float(weights.get(profile.ticker, 0.0)) * float(profile.risk_index or 0.0))
            for profile in company_profiles
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return RiskPortfolioOverlay(
        weighted_risk_index=weighted_risk,
        concentration_penalty=concentration,
        largest_contributors=[f"{ticker}:{round(value, 2)}" for ticker, value in contributors[:5]],
        scenario_exposures=scenario_matrix,
    )



def _risk_output_language(request: RiskWorkbenchRequest) -> str:
    return "en" if request.output_language == "en" else "ko"


def _risk_text(language: str, english: str, korean: str) -> str:
    return english if language == "en" else korean


def _risk_mode_label(mode: str, language: str) -> str:
    labels = {
        "company": ("single-company", "단일 종목"),
        "watchlist": ("watchlist", "관심종목"),
        "portfolio": ("portfolio", "포트폴리오"),
    }
    english, korean = labels.get(mode, (mode, mode))
    return _risk_text(language, english, korean)


def _risk_driver_label(driver: str, language: str) -> str:
    english = str(driver or "").replace("_", " ")
    korean_labels = {
        "company_fundamental_vulnerability": "기업 펀더멘털 취약성",
        "market_behavior_risk": "시장 행동 리스크",
        "macro_regime_risk": "매크로 레짐 리스크",
        "credit_liquidity_risk": "신용/유동성 리스크",
        "transmission_sensitivity": "전이 민감도",
        "weighted_company_risk": "가중 기업 리스크",
        "weighted_market_behavior_risk": "가중 시장 행동 리스크",
        "weighted_transmission_sensitivity": "가중 전이 민감도",
        "concentration_penalty": "집중도 패널티",
        "data_quality_penalty": "데이터 품질 패널티",
        "data_quality_gate_review": "데이터 품질 게이트 검토",
    }
    return english if language == "en" else korean_labels.get(driver, english)


def _risk_channel_label(channel: str, language: str) -> str:
    english = str(channel or "").replace("_", " ")
    korean_labels = {
        "rates_duration": "금리/듀레이션",
        "curve_credit": "수익률곡선/신용",
        "credit_liquidity": "신용/유동성",
        "growth_inflation": "성장/인플레이션",
        "valuation_multiple": "밸류에이션 멀티플",
        "liquidity_beta": "유동성 베타",
        "commodity_input": "원자재 투입비",
    }
    return english if language == "en" else korean_labels.get(channel, english)


def _risk_level_label(level: str, language: str) -> str:
    english = str(level or "unknown")
    korean_labels = {
        "low": "낮음",
        "moderate": "보통",
        "elevated": "상승",
        "high": "높음",
        "unknown": "확인 불가",
    }
    return english if language == "en" else korean_labels.get(english, english)


def _build_clean_decision_brief(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    risk_level_value: str,
    decision_usable: bool,
    data_quality,
    driver_rows,
    transmission_channels,
    scenario_matrix,
) -> RiskDecisionBrief:
    language = _risk_output_language(request)
    mode_label = _risk_mode_label(request.mode, language)
    display_level = _risk_level_label(risk_level_value, language)

    if risk_index is None:
        summary = _risk_text(
            language,
            f"{mode_label} risk run is blocked because required company or macro inputs are unavailable.",
            f"{mode_label} 리스크 실행은 필수 기업 또는 매크로 입력이 부족해 의사결정용으로 차단되었습니다.",
        )
    elif not decision_usable:
        summary = _risk_text(
            language,
            f"{mode_label} risk index is {round(float(risk_index), 1)}, but decision use is blocked by data quality or confidence limits.",
            f"{mode_label} 리스크 지수는 {round(float(risk_index), 1)}점이지만 데이터 품질 또는 신뢰도 기준 때문에 의사결정 사용이 차단되었습니다.",
        )
    else:
        limited_suffix = ""
        if data_quality.missing_inputs:
            limited_suffix = _risk_text(
                language,
                " Missing inputs remain visible, so interpret it as a limited proxy-scope run.",
                " 일부 입력은 누락 상태로 표시되므로 제한된 프록시 범위 결과로 해석해야 합니다.",
            )
        summary = _risk_text(
            language,
            f"{mode_label} risk run is {risk_level_value} at {round(float(risk_index), 1)} on a higher-is-riskier scale.{limited_suffix}",
            f"{mode_label} 리스크는 높을수록 위험한 기준 {round(float(risk_index), 1)}점, 등급은 {display_level}입니다.{limited_suffix}",
        )

    top_drivers = [
        _risk_driver_label(row.driver, language)
        for row in sorted(
            [row for row in driver_rows if row.contribution is not None],
            key=lambda item: float(item.contribution or 0.0),
            reverse=True,
        )[:3]
    ]
    top_channels = [
        _risk_channel_label(channel.channel, language)
        for channel in list(transmission_channels or [])[:3]
    ]
    severe_rows = [row for row in scenario_matrix if row.severity == "severe"]
    blocked = list(data_quality.missing_inputs[:8]) if not decision_usable else []
    if not decision_usable and not blocked:
        blocked.append(_risk_text(language, "confidence below decision-use threshold", "의사결정 사용 기준 신뢰도 미달"))

    review_questions = (
        [
            "Which top driver would change the risk conclusion if updated?",
            "Are macro pressure and company vulnerability pointing in the same direction?",
            "Does the severe scenario expose a channel that is missing from the current thesis?",
        ]
        if language == "en"
        else [
            "어떤 상위 동인이 업데이트되면 리스크 결론이 달라질 수 있나요?",
            "매크로 압력과 기업 취약성이 같은 방향으로 악화되고 있나요?",
            "심각 시나리오가 현재 투자 가정에서 빠진 손상 경로를 드러내나요?",
        ]
    )
    if request.mode == "portfolio":
        review_questions.append(
            _risk_text(
                language,
                "Are the largest weighted contributors consistent with the intended portfolio risk budget?",
                "가중 리스크 기여 상위 종목이 의도한 포트폴리오 리스크 예산과 일치하나요?",
            )
        )

    watch_items = top_drivers + top_channels
    if severe_rows:
        watch_items.append(
            _risk_text(
                language,
                f"severe scenario delta {round(float(severe_rows[0].risk_index_delta), 1)}",
                f"심각 시나리오 리스크 변화 {round(float(severe_rows[0].risk_index_delta), 1)}",
            )
        )
    if data_quality.stale_inputs:
        watch_items.append(_risk_text(language, "stale input refresh required", "오래된 입력 새로고침 필요"))
    if data_quality.missing_inputs and decision_usable:
        watch_items.append(
            _risk_text(
                language,
                "limited proxy scope: missing company fundamentals visible",
                "제한된 프록시 범위: 누락된 기업 재무 입력 표시",
            )
        )

    deployment_notes = (
        [
            "Use /api/v1/risk/workbench as the stable service contract.",
            "Persist risk_run_id and input_hash when storing or comparing runs.",
            "Treat decision_usable=false as a product-level stop state, not a warning badge.",
        ]
        if language == "en"
        else [
            "/api/v1/risk/workbench를 안정적인 서비스 계약으로 사용하세요.",
            "실행 저장 또는 비교 시 risk_run_id와 input_hash를 함께 보존하세요.",
            "decision_usable=false는 경고 배지가 아니라 제품 수준 중단 상태로 처리하세요.",
        ]
    )
    return RiskDecisionBrief(
        summary=summary,
        review_questions=list(dict.fromkeys(review_questions))[:5],
        watch_items=list(dict.fromkeys(watch_items))[:8],
        blocked_reasons=blocked,
        deployment_notes=deployment_notes,
    )


def _build_clean_service_readiness(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    confidence: float,
    decision_usable: bool,
    data_quality,
    company_profiles,
    macro_backdrop,
) -> RiskServiceReadiness:
    language = _risk_output_language(request)
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    blocked_profile_tickers = [
        profile.ticker
        for profile in company_profiles
        if not getattr(profile, "decision_usable", False)
    ]
    blockers: list[str] = []
    warnings: list[str] = []

    if not decision_usable:
        blockers.extend(list(data_quality.missing_inputs[:8]))
        if risk_index is None:
            blockers.append(_risk_text(language, "risk_index_unavailable", "리스크 지수 산출 불가"))
        if blocked_profile_tickers:
            blockers.append(
                _risk_text(
                    language,
                    f"blocked_profiles={','.join(blocked_profile_tickers)}",
                    f"차단된 종목={','.join(blocked_profile_tickers)}",
                )
            )
        if confidence < 35:
            blockers.append(
                _risk_text(
                    language,
                    f"confidence_below_gate={round(confidence, 1)}",
                    f"신뢰도 기준 미달={round(confidence, 1)}",
                )
            )

    if asset_proxy_tickers:
        warnings.append(
            _risk_text(
                language,
                f"limited_asset_proxy_scope={','.join(asset_proxy_tickers)}",
                f"제한된 자산 프록시 범위={','.join(asset_proxy_tickers)}",
            )
        )
    if data_quality.stale_inputs:
        warnings.append(
            _risk_text(
                language,
                f"stale_inputs={','.join(data_quality.stale_inputs[:5])}",
                f"오래된 입력={','.join(data_quality.stale_inputs[:5])}",
            )
        )
    if data_quality.provider_warnings:
        warnings.extend(list(data_quality.provider_warnings[:5]))
    if str(getattr(macro_backdrop, "risk_level", "unknown")) == "unknown":
        warnings.append(_risk_text(language, "macro_backdrop_unknown", "매크로 배경 확인 불가"))
    if confidence < 60 and decision_usable:
        warnings.append(
            _risk_text(
                language,
                f"confidence_review_required={round(confidence, 1)}",
                f"신뢰도 검토 필요={round(confidence, 1)}",
            )
        )

    if blockers:
        status = "blocked"
    elif warnings:
        status = "review_required"
    else:
        status = "ready"

    checklist = (
        [
            "Typed /api/v1/risk/workbench contract returned",
            "decision_usable gate evaluated before display",
            "risk_run_id and input_hash are present for audit",
            "Data freshness and provider warnings are visible",
            "Output is analysis support, not trade instruction",
        ]
        if language == "en"
        else [
            "타입화된 /api/v1/risk/workbench 계약 반환",
            "표시 전 decision_usable 게이트 평가",
            "감사용 risk_run_id 및 input_hash 포함",
            "데이터 신선도와 provider 경고 표시",
            "매매 지시가 아닌 분석 지원 출력",
        ]
    )
    if status == "blocked":
        next_steps = (
            [
                "Resolve blocked inputs, then rerun the same request.",
                "Keep this response out of production decision workflows.",
            ]
            if language == "en"
            else [
                "차단된 입력을 복구한 뒤 같은 요청을 다시 실행하세요.",
                "이 응답은 운영 의사결정 워크플로에 연결하지 마세요.",
            ]
        )
    elif status == "review_required":
        next_steps = (
            [
                "Review warnings before exposing this run to users.",
                "Persist the run id and input hash when saving or comparing outputs.",
                "Add service auth, rate limits, and retention policy before external deployment.",
            ]
            if language == "en"
            else [
                "사용자에게 노출하기 전에 경고 항목을 검토하세요.",
                "저장 또는 비교 시 실행 ID와 입력 해시를 함께 보존하세요.",
                "외부 배포 전 인증, rate limit, 보존 정책을 추가하세요.",
            ]
        )
    else:
        next_steps = (
            [
                "Ready for controlled service integration behind auth and monitoring.",
                "Persist run lineage and monitor provider health on every refresh.",
            ]
            if language == "en"
            else [
                "인증과 모니터링 뒤의 제한된 서비스 통합에 사용할 수 있습니다.",
                "매 새로고침마다 실행 계보와 provider 상태를 보존·감시하세요.",
            ]
        )

    return RiskServiceReadiness(
        status=status,
        deployment_target="local_api_service",
        checklist=list(dict.fromkeys(checklist)),
        blockers=list(dict.fromkeys(blockers))[:10],
        warnings=list(dict.fromkeys(warnings))[:12],
        next_steps=list(dict.fromkeys(next_steps))[:6],
    )


def _build_confidence_factors(
    *,
    request: RiskWorkbenchRequest,
    confidence: float,
    decision_usable: bool,
    data_quality,
    company_profiles,
    macro_backdrop,
    scenario_matrix,
    service_readiness: RiskServiceReadiness,
) -> list[RiskConfidenceFactor]:
    language = _risk_output_language(request)
    factors: list[RiskConfidenceFactor] = []

    def add(
        factor_id: str,
        label_en: str,
        label_ko: str,
        status: str,
        impact: float,
        rationale_en: str,
        rationale_ko: str,
        evidence_refs: list[str] | None = None,
    ) -> None:
        factors.append(
            RiskConfidenceFactor(
                factor_id=factor_id,
                label=_risk_text(language, label_en, label_ko),
                status=status,
                impact=round(max(0.0, min(100.0, float(impact or 0.0))), 2),
                rationale=_risk_text(language, rationale_en, rationale_ko),
                evidence_refs=evidence_refs or [],
            )
        )

    profile_confidence = average_score([float(getattr(profile, "confidence", 0.0) or 0.0) for profile in company_profiles])
    profile_confidence = 0.0 if profile_confidence is None else float(profile_confidence)
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    blocked_profiles = [
        profile.ticker
        for profile in company_profiles
        if not getattr(profile, "decision_usable", False)
    ]
    company_status = "blocked" if blocked_profiles and not any(getattr(p, "decision_usable", False) for p in company_profiles) else ("review" if asset_proxy_tickers or profile_confidence < 70 else "ok")
    add(
        "company_coverage",
        "Company coverage",
        "기업 커버리지",
        company_status,
        max(0.0, 100.0 - profile_confidence) + (8.0 if asset_proxy_tickers else 0.0),
        f"Average company confidence is {round(profile_confidence, 1)}; asset proxies={','.join(asset_proxy_tickers) or 'none'}.",
        f"평균 기업 신뢰도는 {round(profile_confidence, 1)}이고 자산 프록시는 {','.join(asset_proxy_tickers) or '없음'}입니다.",
        ["company_profiles"],
    )

    macro_confidence = float(getattr(macro_backdrop, "confidence", 0.0) or 0.0)
    macro_unknown = str(getattr(macro_backdrop, "risk_level", "unknown")) == "unknown"
    add(
        "macro_backdrop",
        "Macro backdrop",
        "매크로 배경",
        "review" if macro_unknown or macro_confidence < 70 else "ok",
        max(0.0, 100.0 - macro_confidence) + (15.0 if macro_unknown else 0.0),
        f"Macro confidence is {round(macro_confidence, 1)} and regime is {getattr(macro_backdrop, 'regime', 'unknown')}.",
        f"매크로 신뢰도는 {round(macro_confidence, 1)}이고 레짐은 {getattr(macro_backdrop, 'regime', 'unknown')}입니다.",
        ["macro_backdrop"],
    )

    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    provider_count = len(getattr(data_quality, "provider_warnings", []) or [])
    data_status = "blocked" if not bool(getattr(data_quality, "decision_usable", False)) else ("review" if missing_count or stale_count or provider_count else "ok")
    add(
        "data_quality",
        "Data quality gate",
        "데이터 품질 게이트",
        data_status,
        float(getattr(data_quality, "confidence_penalty", 0.0) or 0.0),
        f"Missing={missing_count}, stale={stale_count}, provider warnings={provider_count}.",
        f"누락={missing_count}, 오래됨={stale_count}, provider 경고={provider_count}입니다.",
        ["data_quality", "evidence"],
    )

    severe_rows = [row for row in scenario_matrix if row.severity == "severe"]
    if severe_rows:
        projected = max(float(row.projected_risk_index or 0.0) for row in severe_rows)
        delta = max(float(row.risk_index_delta or 0.0) for row in severe_rows)
        scenario_status = "review" if projected >= 75.0 or delta >= 15.0 else "ok"
        scenario_impact = max(0.0, delta)
        scenario_en = f"Severe scenario max projected risk is {round(projected, 1)} with delta {round(delta, 1)}."
        scenario_ko = f"심각 시나리오의 최대 예상 리스크는 {round(projected, 1)}이고 변화폭은 {round(delta, 1)}입니다."
    else:
        scenario_status = "review" if request.include_macro_scenarios else "ok"
        scenario_impact = 10.0 if request.include_macro_scenarios else 0.0
        scenario_en = "No severe scenario row was returned for this run."
        scenario_ko = "이 실행에는 심각 시나리오 행이 반환되지 않았습니다."
    add(
        "scenario_coverage",
        "Scenario coverage",
        "시나리오 커버리지",
        scenario_status,
        scenario_impact,
        scenario_en,
        scenario_ko,
        ["scenario_matrix"],
    )

    add(
        "service_controls",
        "Service controls",
        "서비스 통제",
        "blocked" if service_readiness.status == "blocked" else ("review" if service_readiness.status == "review_required" else "ok"),
        25.0 if service_readiness.status == "blocked" else (10.0 if service_readiness.status == "review_required" else 0.0),
        f"Service readiness is {service_readiness.status}; confidence gate output is {round(confidence, 1)}.",
        f"서비스 준비도는 {service_readiness.status}이고 신뢰도 게이트 출력은 {round(confidence, 1)}입니다.",
        ["service_readiness", "run_lineage"],
    )

    if not decision_usable and not any(item.status == "blocked" for item in factors):
        factors.append(
            RiskConfidenceFactor(
                factor_id="decision_gate",
                label=_risk_text(language, "Decision-use gate", "의사결정 사용 게이트"),
                status="blocked",
                impact=100.0,
                rationale=_risk_text(
                    language,
                    "The final decision_usable flag is false, so product flows should stop.",
                    "최종 decision_usable 값이 false이므로 제품 흐름은 중단되어야 합니다.",
                ),
                evidence_refs=["decision_usable"],
            )
        )

    return factors[:6]


def _build_clean_action_checklist(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    confidence: float,
    decision_usable: bool,
    data_quality,
    driver_rows,
    transmission_channels,
    scenario_matrix,
    service_readiness: RiskServiceReadiness,
    company_profiles,
) -> list[RiskActionItem]:
    language = _risk_output_language(request)
    sorted_drivers = sorted(
        [row for row in driver_rows if row.contribution is not None],
        key=lambda item: float(item.contribution or 0.0),
        reverse=True,
    )
    top_driver = sorted_drivers[0] if sorted_drivers else None
    severe_rows = sorted(
        [row for row in scenario_matrix if row.severity == "severe"],
        key=lambda item: float(item.projected_risk_index or item.risk_index_delta or 0.0),
        reverse=True,
    )
    severe_row = severe_rows[0] if severe_rows else None
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    provider_warnings = list(getattr(data_quality, "provider_warnings", []) or [])
    stale_inputs = list(getattr(data_quality, "stale_inputs", []) or [])
    missing_inputs = list(getattr(data_quality, "missing_inputs", []) or [])

    def action(
        action_id: str,
        label_en: str,
        label_ko: str,
        status: str,
        rationale_en: str,
        rationale_ko: str,
        next_en: str,
        next_ko: str,
        evidence_refs: list[str] | None = None,
    ) -> RiskActionItem:
        return RiskActionItem(
            action_id=action_id,
            label=_risk_text(language, label_en, label_ko),
            status=status,
            rationale=_risk_text(language, rationale_en, rationale_ko),
            next_step=_risk_text(language, next_en, next_ko),
            evidence_refs=evidence_refs or [],
        )

    if not decision_usable:
        data_status = "blocked"
        data_rationale_en = "Decision use is blocked by missing critical inputs or confidence limits."
        data_rationale_ko = "필수 입력 누락 또는 신뢰도 기준 때문에 의사결정 사용이 차단되었습니다."
        data_next_en = "Resolve blocked inputs, then rerun the same request before comparing outputs."
        data_next_ko = "차단 입력을 복구한 뒤 같은 요청을 다시 실행하고 결과를 비교하세요."
    elif missing_inputs or stale_inputs or provider_warnings:
        data_status = "review"
        data_rationale_en = "Some missing, stale, or provider-warning inputs remain visible."
        data_rationale_ko = "일부 누락, 오래된 입력 또는 공급자 경고가 남아 있습니다."
        data_next_en = "Review the evidence drawer and decide whether a refresh is required before sharing the run."
        data_next_ko = "공유 전에 근거 영역을 확인하고 새로고침 필요 여부를 판단하세요."
    else:
        data_status = "ok"
        data_rationale_en = "Required data-quality gates passed for this run."
        data_rationale_ko = "이번 실행은 필수 데이터 품질 게이트를 통과했습니다."
        data_next_en = "Save the run id and input hash if this output is used for comparison."
        data_next_ko = "비교 또는 저장에 사용할 경우 실행 ID와 입력 해시를 함께 보존하세요."

    actions: list[RiskActionItem] = [
        action(
            "data_quality_gate",
            "Confirm data-quality gate",
            "데이터 품질 게이트 확인",
            data_status,
            data_rationale_en,
            data_rationale_ko,
            data_next_en,
            data_next_ko,
            ["data_quality"],
        )
    ]

    driver_name = _risk_driver_label(str(getattr(top_driver, "driver", "") or "risk driver"), language)
    driver_contribution = float(getattr(top_driver, "contribution", 0.0) or 0.0)
    driver_status = "blocked" if risk_index is None else ("review" if (risk_index >= 50 or driver_contribution >= 8.0) else "ok")
    actions.append(
        action(
            "top_driver_review",
            "Review dominant risk driver",
            "우세 리스크 동인 검토",
            driver_status,
            f"Top contribution is {driver_name} at {round(driver_contribution, 1)} points.",
            f"상위 기여 동인은 {driver_name}, 기여도는 {round(driver_contribution, 1)}점입니다.",
            "Use the driver waterfall to verify whether the conclusion depends on stale or partial evidence.",
            "동인 워터폴에서 결론이 오래되었거나 부분적인 근거에 의존하는지 확인하세요.",
            ["driver_contributions"],
        )
    )

    if severe_row is None:
        scenario_status = "review"
        scenario_rationale_en = "No severe scenario row is available for this request."
        scenario_rationale_ko = "이 요청에는 심각 시나리오 행이 제공되지 않았습니다."
        scenario_next_en = "Enable macro scenarios or run a scenario preset before treating stress impact as reviewed."
        scenario_next_ko = "스트레스 영향을 검토 완료로 보기 전에 매크로 시나리오를 켜거나 시나리오 프리셋을 실행하세요."
    else:
        projected = float(severe_row.projected_risk_index or 0.0)
        delta = float(severe_row.risk_index_delta or 0.0)
        scenario_status = "review" if projected >= 75.0 or delta >= 15.0 else "ok"
        scenario_rationale_en = f"Severe scenario projects risk {round(projected, 1)} with delta {round(delta, 1)}."
        scenario_rationale_ko = f"심각 시나리오는 예상 리스크 {round(projected, 1)}점, 변화폭 {round(delta, 1)}점을 제시합니다."
        scenario_next_en = "Inspect top damage channels and decide whether the thesis needs a stress-case note."
        scenario_next_ko = "상위 손상 경로를 확인하고 투자 가정에 스트레스 케이스 메모가 필요한지 판단하세요."
    actions.append(
        action(
            "scenario_stress_review",
            "Check severe scenario path",
            "심각 시나리오 경로 확인",
            scenario_status,
            scenario_rationale_en,
            scenario_rationale_ko,
            scenario_next_en,
            scenario_next_ko,
            ["scenario_matrix"],
        )
    )

    if asset_proxy_tickers:
        actions.append(
            action(
                "asset_proxy_scope_review",
                "Confirm asset-proxy scope",
                "자산 프록시 범위 확인",
                "review",
                f"{', '.join(asset_proxy_tickers)} is represented with price and macro proxy evidence, not company fundamentals.",
                f"{', '.join(asset_proxy_tickers)}는 기업 재무가 아니라 가격 및 매크로 프록시 근거로 표현됩니다.",
                "Keep the proxy limitation visible when comparing this run with company-equity outputs.",
                "회사 주식 결과와 비교할 때 프록시 제약을 함께 표시하세요.",
                ["company_profiles", "data_quality"],
            )
        )

    if request.mode == "portfolio" and request.positions:
        max_weight = max((position.weight for position in request.positions), default=0.0)
        actions.append(
            action(
                "portfolio_concentration_review",
                "Review portfolio concentration",
                "포트폴리오 집중도 검토",
                "review" if max_weight >= 0.5 else "ok",
                f"Largest submitted position weight is {round(max_weight * 100, 1)}%.",
                f"제출된 최대 종목 비중은 {round(max_weight * 100, 1)}%입니다.",
                "Compare weighted contributors with the intended risk budget before using the overlay.",
                "오버레이를 사용하기 전에 가중 기여도와 의도한 리스크 예산을 비교하세요.",
                ["portfolio_overlay"],
            )
        )

    service_status = "blocked" if service_readiness.status == "blocked" else ("review" if service_readiness.status == "review_required" else "ok")
    actions.append(
        action(
            "service_release_gate",
            "Check service release gate",
            "서비스 배포 게이트 확인",
            service_status,
            f"Service readiness is {service_readiness.status}.",
            f"서비스 준비도 상태는 {service_readiness.status}입니다.",
            "Add authentication, rate limits, retention policy, and run-lineage storage before external deployment.",
            "외부 배포 전 인증, rate limit, 보존 정책, 실행 계보 저장을 추가하세요.",
            ["service_readiness"],
        )
    )

    return actions[:6]


def _build_clean_monitoring_triggers(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    confidence: float,
    decision_usable: bool,
    data_quality,
    driver_rows,
    transmission_channels,
    scenario_matrix,
    service_readiness: RiskServiceReadiness,
    company_profiles,
) -> list[RiskMonitoringTrigger]:
    language = _risk_output_language(request)
    sorted_drivers = sorted(
        [row for row in driver_rows if row.contribution is not None],
        key=lambda item: float(item.contribution or 0.0),
        reverse=True,
    )
    top_driver = sorted_drivers[0] if sorted_drivers else None
    severe_rows = sorted(
        [row for row in scenario_matrix if row.severity == "severe"],
        key=lambda item: float(item.projected_risk_index or item.risk_index_delta or 0.0),
        reverse=True,
    )
    severe_row = severe_rows[0] if severe_rows else None
    top_channel = sorted(
        list(transmission_channels or []),
        key=lambda item: float(getattr(item, "risk_delta", 0.0) or 0.0),
        reverse=True,
    )[0] if transmission_channels else None
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    provider_warnings = list(getattr(data_quality, "provider_warnings", []) or [])
    stale_inputs = list(getattr(data_quality, "stale_inputs", []) or [])
    missing_inputs = list(getattr(data_quality, "missing_inputs", []) or [])

    def trigger(
        trigger_id: str,
        label_en: str,
        label_ko: str,
        status: str,
        current_en: str,
        current_ko: str,
        condition_en: str,
        condition_ko: str,
        rationale_en: str,
        rationale_ko: str,
        next_en: str,
        next_ko: str,
        evidence_refs: list[str] | None = None,
    ) -> RiskMonitoringTrigger:
        return RiskMonitoringTrigger(
            trigger_id=trigger_id,
            label=_risk_text(language, label_en, label_ko),
            status=status,
            current_state=_risk_text(language, current_en, current_ko),
            trigger_condition=_risk_text(language, condition_en, condition_ko),
            rationale=_risk_text(language, rationale_en, rationale_ko),
            next_step=_risk_text(language, next_en, next_ko),
            evidence_refs=evidence_refs or [],
        )

    if not decision_usable:
        data_status = "blocked"
        data_current_en = f"decision_usable=false; confidence={round(confidence, 1)}"
        data_current_ko = f"decision_usable=false, 신뢰도={round(confidence, 1)}"
        data_next_en = "Resolve blocked inputs before using this run in a product workflow."
        data_next_ko = "차단 입력을 복구하기 전에는 이 실행을 제품 워크플로에 사용하지 마세요."
    elif missing_inputs or stale_inputs or provider_warnings:
        data_status = "review"
        data_current_en = f"visible gaps={len(missing_inputs)}, stale={len(stale_inputs)}, provider_warnings={len(provider_warnings)}"
        data_current_ko = f"표시된 공백={len(missing_inputs)}, 오래된 입력={len(stale_inputs)}, 공급자 경고={len(provider_warnings)}"
        data_next_en = "Open the evidence drawer and decide whether the run needs a refresh before sharing."
        data_next_ko = "공유 전에 근거 영역을 열어 새로고침 필요 여부를 판단하세요."
    else:
        data_status = "ok"
        data_current_en = "required quality gates passed"
        data_current_ko = "필수 품질 게이트 통과"
        data_next_en = "Store risk_run_id and input_hash if this output is reused."
        data_next_ko = "출력을 재사용한다면 risk_run_id와 input_hash를 저장하세요."

    triggers: list[RiskMonitoringTrigger] = [
        trigger(
            "data_quality_monitor",
            "Monitor data-quality gate",
            "데이터 품질 게이트 감시",
            data_status,
            data_current_en,
            data_current_ko,
            "Trigger when decision_usable=false, stale inputs appear, or provider warnings increase.",
            "decision_usable=false, 오래된 입력 발생, 공급자 경고 증가 시 트리거",
            "Risk output quality depends on visible freshness and provider coverage.",
            "리스크 출력 품질은 표시된 신선도와 공급자 커버리지에 의존합니다.",
            data_next_en,
            data_next_ko,
            ["data_quality", "evidence"],
        )
    ]

    driver_name = _risk_driver_label(str(getattr(top_driver, "driver", "") or "risk driver"), language)
    driver_contribution = float(getattr(top_driver, "contribution", 0.0) or 0.0)
    driver_score = getattr(top_driver, "score", None)
    driver_status = "blocked" if risk_index is None else ("review" if risk_index >= 50 or driver_contribution >= 8.0 else "ok")
    triggers.append(
        trigger(
            "dominant_driver_monitor",
            "Monitor dominant risk driver",
            "우세 리스크 동인 감시",
            driver_status,
            f"{driver_name}: contribution={round(driver_contribution, 1)}, score={driver_score if driver_score is not None else 'unknown'}",
            f"{driver_name}: 기여도={round(driver_contribution, 1)}, 점수={driver_score if driver_score is not None else 'unknown'}",
            "Trigger review when driver contribution is >= 8 points or total risk index is >= 50.",
            "동인 기여도가 8점 이상이거나 전체 리스크 지수가 50 이상이면 검토",
            "A concentrated driver can make the conclusion sensitive to one stale or fast-moving input.",
            "리스크가 한 동인에 집중되면 오래되었거나 빠르게 변하는 입력 하나에 결론이 민감해질 수 있습니다.",
            "Compare the driver waterfall with evidence freshness before reusing the conclusion.",
            "결론을 재사용하기 전에 동인 워터폴과 근거 신선도를 함께 비교하세요.",
            ["driver_contributions"],
        )
    )

    if top_channel is None:
        channel_status = "review"
        channel_current_en = "no transmission channel available"
        channel_current_ko = "전이 경로 없음"
        channel_condition_en = "Trigger when channel evidence is missing for a decision-usable run."
        channel_condition_ko = "의사결정 사용 가능 실행에서 전이 경로 근거가 없으면 트리거"
        channel_next_en = "Rerun after macro and company adapters return channel inputs."
        channel_next_ko = "매크로와 기업 어댑터가 경로 입력을 반환한 뒤 다시 실행하세요."
    else:
        channel_delta = float(getattr(top_channel, "risk_delta", 0.0) or 0.0)
        channel_pressure = str(getattr(top_channel, "pressure", "unknown") or "unknown")
        channel_status = "review" if channel_pressure in {"elevated", "high"} or channel_delta >= 20.0 else "ok"
        channel_current_en = f"{top_channel.channel}: pressure={channel_pressure}, delta={round(channel_delta, 1)}"
        channel_current_ko = f"{_risk_channel_label(top_channel.channel, language)}: 압력={_risk_level_label(channel_pressure, language)}, 변화={round(channel_delta, 1)}"
        channel_condition_en = "Trigger review when pressure is elevated/high or risk delta is >= 20."
        channel_condition_ko = "압력이 상승/높음이거나 리스크 변화가 20 이상이면 검토"
        channel_next_en = "Check affected subjects and mechanism before relying on the scenario result."
        channel_next_ko = "시나리오 결과를 신뢰하기 전에 영향 대상과 메커니즘을 확인하세요."
    triggers.append(
        trigger(
            "transmission_channel_monitor",
            "Monitor macro transmission channel",
            "매크로 전이 경로 감시",
            channel_status,
            channel_current_en,
            channel_current_ko,
            channel_condition_en,
            channel_condition_ko,
            "Macro pressure becomes more useful when the affected channel is explicit.",
            "매크로 압력은 영향을 받는 전이 경로가 명확할 때 의사결정에 더 유용합니다.",
            channel_next_en,
            channel_next_ko,
            ["transmission_channels"],
        )
    )

    if severe_row is None:
        scenario_status = "review"
        scenario_current_en = "severe scenario unavailable"
        scenario_current_ko = "심각 시나리오 없음"
        scenario_next_en = "Run with macro scenarios enabled before marking stress review complete."
        scenario_next_ko = "스트레스 검토 완료 전 매크로 시나리오를 켜고 실행하세요."
    else:
        projected = float(severe_row.projected_risk_index or 0.0)
        delta = float(severe_row.risk_index_delta or 0.0)
        scenario_status = "review" if projected >= 75.0 or delta >= 15.0 else "ok"
        scenario_current_en = f"{severe_row.scenario_id}: projected={round(projected, 1)}, delta={round(delta, 1)}"
        scenario_current_ko = f"{severe_row.scenario_id}: 예상={round(projected, 1)}, 변화={round(delta, 1)}"
        scenario_next_en = "Keep the severe path visible in user-facing review notes when it crosses the trigger."
        scenario_next_ko = "트리거를 넘으면 사용자 검토 메모에 severe 경로를 계속 표시하세요."
    triggers.append(
        trigger(
            "severe_scenario_monitor",
            "Monitor severe scenario path",
            "심각 시나리오 경로 감시",
            scenario_status,
            scenario_current_en,
            scenario_current_ko,
            "Trigger review when projected severe risk is >= 75 or risk delta is >= 15.",
            "예상 severe 리스크가 75 이상이거나 리스크 변화가 15 이상이면 검토",
            "Stress-path visibility prevents a clean headline from hiding tail damage.",
            "스트레스 경로를 보이면 깔끔한 헤드라인이 꼬리 손상을 가리는 일을 줄일 수 있습니다.",
            scenario_next_en,
            scenario_next_ko,
            ["scenario_matrix"],
        )
    )

    if asset_proxy_tickers:
        triggers.append(
            trigger(
                "asset_proxy_scope_monitor",
                "Monitor asset-proxy scope",
                "자산 프록시 범위 감시",
                "review",
                f"asset_proxy={','.join(asset_proxy_tickers)}",
                f"자산 프록시={','.join(asset_proxy_tickers)}",
                "Trigger whenever an ETF or macro proxy is compared with full company-equity output.",
                "ETF 또는 매크로 프록시를 전체 기업 주식 출력과 비교할 때마다 트리거",
                "Proxy-scope runs can be useful, but missing fundamentals must remain visible.",
                "프록시 범위 실행은 유용할 수 있지만 누락된 재무 근거는 계속 보여야 합니다.",
                "Label saved or shared outputs as asset-proxy scope.",
                "저장 또는 공유 출력에 자산 프록시 범위를 표시하세요.",
                ["company_profiles", "data_quality"],
            )
        )

    service_status = "blocked" if service_readiness.status == "blocked" else ("review" if service_readiness.status == "review_required" else "ok")
    triggers.append(
        trigger(
            "service_readiness_monitor",
            "Monitor service release readiness",
            "서비스 배포 준비도 감시",
            service_status,
            f"service_readiness={service_readiness.status}",
            f"서비스 준비도={service_readiness.status}",
            "Trigger before external deployment unless auth, rate limits, retention, and run lineage are configured.",
            "외부 배포 전 인증, rate limit, 보존 정책, 실행 계보 저장이 구성되지 않으면 트리거",
            "Risk output needs product controls before it becomes a service surface.",
            "리스크 출력은 서비스 표면이 되기 전에 제품 통제가 필요합니다.",
            "Use this trigger as a release checklist item, not as an investment conclusion.",
            "이 트리거는 투자 결론이 아니라 릴리스 체크리스트 항목으로 사용하세요.",
            ["service_readiness"],
        )
    )

    return triggers[:6]


def _risk_priority_level_rank(level: str) -> int:
    return {
        "high": 5,
        "elevated": 4,
        "unknown": 3,
        "moderate": 2,
        "low": 1,
    }.get(str(level or "unknown"), 0)


def _build_priority_map(
    *,
    company_profiles,
    macro_backdrop,
    data_quality,
) -> list[RiskPriorityCell]:
    candidates: list[tuple[int, float, float, RiskPriorityCell]] = []

    def add_cell(
        *,
        subject: str,
        vector: str,
        score: float | None,
        level: str,
        confidence: float,
        reason: str,
        evidence_refs: list[str] | None = None,
    ) -> None:
        score_value = None if score is None else round(float(score), 2)
        level_value = level if level in {"low", "moderate", "elevated", "high", "unknown"} else risk_level(score_value)
        confidence_value = max(0.0, min(100.0, float(confidence or 0.0)))
        cell = RiskPriorityCell(
            rank=1,
            subject=subject,
            vector=vector,
            score=score_value,
            level=level_value,
            confidence=round(confidence_value, 2),
            reason=reason,
            evidence_refs=evidence_refs or [],
        )
        score_sort = -1.0 if score_value is None else float(score_value)
        candidates.append((
            _risk_priority_level_rank(level_value),
            score_sort,
            100.0 - confidence_value,
            cell,
        ))

    for profile in company_profiles:
        for vector in getattr(profile, "vectors", []) or []:
            reason = (vector.top_drivers or [vector.vector])[0]
            add_cell(
                subject=getattr(profile, "ticker", "UNKNOWN") or "UNKNOWN",
                vector=str(vector.vector),
                score=vector.score,
                level=str(vector.level),
                confidence=float(vector.confidence or 0.0),
                reason=reason,
                evidence_refs=list(vector.evidence_refs or []),
            )

    for vector in getattr(macro_backdrop, "vectors", []) or []:
        reason = (vector.top_drivers or [vector.vector])[0]
        add_cell(
            subject="MACRO",
            vector=str(vector.vector),
            score=vector.score,
            level=str(vector.level),
            confidence=float(vector.confidence or 0.0),
            reason=reason,
            evidence_refs=list(vector.evidence_refs or []),
        )

    if (
        getattr(data_quality, "missing_inputs", None)
        or getattr(data_quality, "stale_inputs", None)
        or getattr(data_quality, "provider_warnings", None)
    ):
        add_cell(
            subject="DATA_QUALITY",
            vector="data_integrity",
            score=float(getattr(data_quality, "penalty", 0.0) or 0.0),
            level=risk_level(float(getattr(data_quality, "penalty", 0.0) or 0.0)),
            confidence=max(0.0, 100.0 - float(getattr(data_quality, "confidence_penalty", 0.0) or 0.0)),
            reason="data_quality_gate_review",
            evidence_refs=["data_quality"],
        )

    ranked = [
        cell
        for _, _, _, cell in sorted(
            candidates,
            key=lambda item: (item[0], item[1], item[2], item[3].subject),
            reverse=True,
        )
    ]
    for index, cell in enumerate(ranked[:8], start=1):
        cell.rank = index
    return ranked[:8]


def _build_handoff_queue(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    decision_usable: bool,
    data_quality,
    company_profiles,
    macro_backdrop,
    transmission_channels,
    scenario_matrix,
    priority_map: list[RiskPriorityCell],
    service_readiness: RiskServiceReadiness,
) -> list[RiskHandoffItem]:
    language = _risk_output_language(request)
    items: list[RiskHandoffItem] = []
    seen: set[str] = set()

    def add(
        *,
        handoff_id: str,
        label_en: str,
        label_ko: str,
        target_tab: str,
        href: str,
        status: str,
        priority: int,
        reason_en: str,
        reason_ko: str,
        next_en: str,
        next_ko: str,
        evidence_refs: list[str] | None = None,
    ) -> None:
        if handoff_id in seen:
            return
        seen.add(handoff_id)
        items.append(
            RiskHandoffItem(
                handoff_id=handoff_id,
                label=_risk_text(language, label_en, label_ko),
                target_tab=target_tab,
                href=href,
                status=status,
                priority=max(1, min(5, int(priority))),
                reason=_risk_text(language, reason_en, reason_ko),
                next_step=_risk_text(language, next_en, next_ko),
                evidence_refs=evidence_refs or [],
            )
        )

    subjects = ", ".join(request.tickers[:5]) or _risk_text(language, "current request", "현재 요청")
    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    warning_count = len(getattr(data_quality, "provider_warnings", []) or [])
    data_status = "blocked" if not decision_usable else ("review" if missing_count or stale_count or warning_count else "ok")
    if data_status != "ok":
        add(
            handoff_id="risk_data_quality_repair",
            label_en="Repair data-quality gate",
            label_ko="데이터 품질 게이트 보정",
            target_tab="risk",
            href="/ui/#risk",
            status=data_status,
            priority=1,
            reason_en=f"Missing={missing_count}, stale={stale_count}, provider warnings={warning_count}.",
            reason_ko=f"누락={missing_count}, 오래됨={stale_count}, 공급자 경고={warning_count}입니다.",
            next_en="Open Risk evidence first and rerun the same input before comparing downstream outputs.",
            next_ko="먼저 Risk 근거 영역을 확인하고 같은 입력으로 다시 실행한 뒤 하위 탭 결과와 비교하세요.",
            evidence_refs=["data_quality", "evidence"],
        )

    macro_unknown = str(getattr(macro_backdrop, "risk_level", "unknown")) == "unknown"
    macro_pressure = bool(getattr(macro_backdrop, "primary_pressures", []) or transmission_channels)
    if macro_unknown or macro_pressure:
        add(
            handoff_id="macro_pressure_review",
            label_en="Review macro pressure next",
            label_ko="매크로 압력 우선 검토",
            target_tab="macro",
            href="/ui/#macro",
            status="review" if macro_unknown else "ok",
            priority=2,
            reason_en=f"Macro regime={getattr(macro_backdrop, 'regime', 'unknown')} and transmission channels={len(transmission_channels)}.",
            reason_ko=f"매크로 레짐={getattr(macro_backdrop, 'regime', 'unknown')}, 전이 경로={len(transmission_channels)}개입니다.",
            next_en="Check Macro provider health, regime details, and the pressure series behind the transmission rows.",
            next_ko="Macro 탭에서 공급자 상태, 레짐 상세, 전이 행의 배경 압력 시계열을 확인하세요.",
            evidence_refs=["macro_backdrop", "transmission_channels"],
        )

    full_company_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "company_full"
    ]
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    if full_company_tickers:
        add(
            handoff_id="quantamental_company_drilldown",
            label_en="Open Quantamental drilldown",
            label_ko="Quantamental 상세 점검",
            target_tab="quantamental",
            href="/ui/#quantamental",
            status="ok",
            priority=3,
            reason_en=f"{', '.join(full_company_tickers[:5])} has full company coverage in this Risk run.",
            reason_ko=f"{', '.join(full_company_tickers[:5])}는 이번 Risk 실행에서 기업 전체 범위로 커버됩니다.",
            next_en="Use Quantamental to inspect fundamentals, factor scores, freshness, and AI interpretation from the same subject list.",
            next_ko="Quantamental에서 같은 대상의 펀더멘털, 팩터 점수, 신선도, AI 해석을 점검하세요.",
            evidence_refs=["company_profiles"],
        )
    if asset_proxy_tickers:
        add(
            handoff_id="asset_proxy_scope_handoff",
            label_en="Keep proxy scope visible",
            label_ko="프록시 범위 유지 표시",
            target_tab="risk",
            href="/ui/#risk",
            status="review",
            priority=2,
            reason_en=f"{', '.join(asset_proxy_tickers[:5])} is represented with price and macro evidence, not company fundamentals.",
            reason_ko=f"{', '.join(asset_proxy_tickers[:5])}는 기업 재무가 아닌 가격·매크로 근거로 표현됩니다.",
            next_en="Do not compare this output as if it had solvency, cash-flow, or SEC-company coverage.",
            next_ko="지급능력, 현금흐름, SEC 기업 커버리지가 있는 결과처럼 비교하지 마세요.",
            evidence_refs=["company_profiles", "data_quality"],
        )

    market_score = _weighted_profile_score(company_profiles, _positions_by_ticker(request), "market_behavior")
    severe_rows = [row for row in scenario_matrix if row.severity == "severe"]
    severe_delta = max([float(row.risk_index_delta or 0.0) for row in severe_rows], default=0.0)
    severe_projected = max([float(row.projected_risk_index or 0.0) for row in severe_rows], default=0.0)
    if decision_usable and ((market_score is not None and market_score >= 50.0) or severe_delta >= 10.0 or severe_projected >= 70.0):
        add(
            handoff_id="ml_forecast_validation_test",
            label_en="Run ML Forecast validation test",
            label_ko="ML Forecast 검증 테스트 실행",
            target_tab="ml_forecast",
            href="/ui/#ml-forecast",
            status="review",
            priority=3,
            reason_en=f"Market behavior risk={risk_score_text(market_score)} and severe scenario delta={round(severe_delta, 1)} for {subjects}.",
            reason_ko=f"{subjects}의 시장 행동 리스크={risk_score_text(market_score)}, 심각 시나리오 변화={round(severe_delta, 1)}입니다.",
            next_en="Run a walk-forward forecast with leakage checks before using forecast output beside this Risk run.",
            next_ko="이 Risk 결과 옆에 예측 결과를 붙이기 전 walk-forward 예측과 누수 검사를 실행하세요.",
            evidence_refs=["company_profiles", "scenario_matrix"],
        )

    if request.mode == "portfolio":
        add(
            handoff_id="ai_portfolio_overlay_review",
            label_en="Review AI Portfolio overlay",
            label_ko="AI Portfolio 오버레이 검토",
            target_tab="ai_portfolio",
            href="/ui/#ai-portfolio",
            status="review" if risk_index is None or float(risk_index or 0.0) >= 50.0 else "ok",
            priority=3,
            reason_en=f"Portfolio mode generated weighted Risk output for {subjects}.",
            reason_ko=f"포트폴리오 모드가 {subjects}에 대한 가중 Risk 출력을 생성했습니다.",
            next_en="Compare largest weighted contributors with the portfolio policy before approving any saved portfolio workflow.",
            next_ko="저장 포트폴리오 흐름을 승인하기 전 최대 가중 기여 항목을 포트폴리오 정책과 비교하세요.",
            evidence_refs=["portfolio_overlay", "priority_map"],
        )

    if priority_map:
        top_cell = priority_map[0]
        target_tab = "macro" if top_cell.subject == "MACRO" else ("risk" if top_cell.subject == "DATA_QUALITY" else "quantamental")
        href = {"macro": "/ui/#macro", "risk": "/ui/#risk", "quantamental": "/ui/#quantamental"}[target_tab]
        add(
            handoff_id="top_priority_cell_review",
            label_en="Open top priority cell",
            label_ko="최우선 위험 셀 열기",
            target_tab=target_tab,
            href=href,
            status="review" if top_cell.level in {"elevated", "high", "unknown"} else "ok",
            priority=2,
            reason_en=f"Top priority is {top_cell.subject} / {top_cell.vector} at level {top_cell.level}.",
            reason_ko=f"최우선 항목은 {top_cell.subject} / {top_cell.vector}, 등급 {top_cell.level}입니다.",
            next_en="Inspect the referenced evidence before moving to secondary panels.",
            next_ko="보조 패널로 이동하기 전에 참조 근거를 먼저 확인하세요.",
            evidence_refs=list(top_cell.evidence_refs or ["priority_map"]),
        )

    service_status = "blocked" if service_readiness.status == "blocked" else ("review" if service_readiness.status == "review_required" else "ok")
    add(
        handoff_id="service_wrapper_gate",
        label_en="Check service wrapper gate",
        label_ko="서비스 래퍼 게이트 확인",
        target_tab="risk",
        href="/ui/#risk",
        status=service_status,
        priority=4,
        reason_en=f"Service readiness is {service_readiness.status}.",
        reason_ko=f"서비스 준비도는 {service_readiness.status}입니다.",
        next_en="Add auth, rate limits, retention, and run-lineage storage before external deployment.",
        next_ko="외부 배포 전 인증, rate limit, 보존 정책, 실행 계보 저장을 추가하세요.",
        evidence_refs=["service_readiness", "run_lineage"],
    )

    status_rank = {"blocked": 0, "review": 1, "ok": 2}
    return sorted(
        items,
        key=lambda item: (item.priority, status_rank.get(item.status, 3), item.handoff_id),
    )[:7]


def risk_score_text(value: float | None) -> str:
    if value is None:
        return "unknown"
    return str(round(float(value), 1))


def _ml_forecast_validation_method(test_type: str) -> str:
    if test_type in {"leakage_check", "scenario_backtest"}:
        return "walk_forward_plus_purged_cv"
    if test_type == "portfolio_overlay":
        return "walk_forward"
    return "walk_forward"


def _ml_forecast_prefill_for_test(
    *,
    test_id: str,
    label: str,
    test_type: str,
    priority: int,
    target_tickers: list[str],
    horizon_days: int | None,
    input_hash: str,
) -> tuple[RiskMlForecastPrefill | None, str | None]:
    clean_tickers = [ticker.strip().upper() for ticker in target_tickers if ticker and ticker.strip()]
    if not clean_tickers or test_type == "data_gate_recheck":
        return None, None
    include_macro = test_type in {"leakage_check", "scenario_backtest", "asset_proxy_validation"}
    include_cross_asset = test_type in {"portfolio_overlay", "asset_proxy_validation"}
    prefill = RiskMlForecastPrefill(
        ticker=clean_tickers[0],
        benchmark="SPY" if test_type in {"asset_proxy_validation", "portfolio_overlay"} else "QQQ",
        horizon_days=horizon_days or 63,
        validation_method=_ml_forecast_validation_method(test_type),
        target_type="forward_return",
        include_macro=include_macro,
        include_cross_asset=include_cross_asset,
        source_risk_input_hash=input_hash,
    )
    params = urlencode(
        {
            "tab": "ml-forecast",
            "forecastTicker": prefill.ticker,
            "forecastBenchmark": prefill.benchmark,
            "forecastHorizon": str(prefill.horizon_days or 63),
            "forecastValidation": prefill.validation_method,
            "forecastTargetType": prefill.target_type,
            "forecastIncludeMacro": "1" if prefill.include_macro else "0",
            "forecastIncludeCrossAsset": "1" if prefill.include_cross_asset else "0",
            "riskValidation": test_id,
            "riskInputHash": input_hash,
            "riskTestType": test_type,
            "riskTestPriority": str(max(1, min(5, int(priority)))),
            "riskTestLabel": label,
        }
    )
    return prefill, f"/ui/?{params}#ml-forecast"


def _build_ml_validation_tests(
    *,
    request: RiskWorkbenchRequest,
    input_hash: str,
    risk_index: float | None,
    decision_usable: bool,
    data_quality,
    company_profiles,
    macro_backdrop,
    transmission_channels,
    scenario_matrix,
) -> list[RiskMlValidationTest]:
    language = _risk_output_language(request)
    items: list[RiskMlValidationTest] = []
    seen: set[str] = set()

    def add(
        *,
        test_id: str,
        label_en: str,
        label_ko: str,
        status: str,
        priority: int,
        test_type: str,
        target_tickers: list[str],
        horizon_days: int | None,
        rationale_en: str,
        rationale_ko: str,
        setup_en: str,
        setup_ko: str,
        pass_criteria_en: list[str],
        pass_criteria_ko: list[str],
        evidence_refs: list[str],
    ) -> None:
        if test_id in seen:
            return
        seen.add(test_id)
        clean_tickers = list(dict.fromkeys([ticker for ticker in target_tickers if ticker]))[:10]
        label = _risk_text(language, label_en, label_ko)
        forecast_prefill, launch_href = _ml_forecast_prefill_for_test(
            test_id=test_id,
            label=label,
            test_type=test_type,
            priority=priority,
            target_tickers=clean_tickers,
            horizon_days=horizon_days,
            input_hash=input_hash,
        )
        items.append(
            RiskMlValidationTest(
                test_id=test_id,
                label=label,
                status=status,
                priority=max(1, min(5, int(priority))),
                test_type=test_type,
                target_tickers=clean_tickers,
                horizon_days=horizon_days,
                rationale=_risk_text(language, rationale_en, rationale_ko),
                setup_notes=_risk_text(language, setup_en, setup_ko),
                pass_criteria=_risk_text(language, "||".join(pass_criteria_en), "||".join(pass_criteria_ko)).split("||"),
                evidence_refs=evidence_refs,
                forecast_prefill=forecast_prefill,
                launch_href=launch_href,
            )
        )

    subjects = list(request.tickers)
    subject_text = ", ".join(subjects[:5]) or _risk_text(language, "current request", "현재 요청")
    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    warning_count = len(getattr(data_quality, "provider_warnings", []) or [])
    market_score = _weighted_profile_score(company_profiles, _positions_by_ticker(request), "market_behavior")
    severe_rows = [row for row in scenario_matrix if row.severity == "severe"]
    severe_delta = max([float(row.risk_index_delta or 0.0) for row in severe_rows], default=0.0)
    severe_projected = max([float(row.projected_risk_index or 0.0) for row in severe_rows], default=0.0)
    macro_pressure_count = len(getattr(macro_backdrop, "primary_pressures", []) or []) + len(transmission_channels or [])
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    full_company_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "company_full"
    ]

    if not decision_usable:
        add(
            test_id="risk_data_gate_recheck",
            label_en="Recheck data gate before ML Forecast",
            label_ko="ML Forecast 전 데이터 게이트 재점검",
            status="blocked",
            priority=1,
            test_type="data_gate_recheck",
            target_tickers=subjects,
            horizon_days=None,
            rationale_en=f"Risk run is blocked; missing={missing_count}, stale={stale_count}, warnings={warning_count}.",
            rationale_ko=f"Risk 실행이 차단되었습니다. 누락={missing_count}, 오래됨={stale_count}, 경고={warning_count}입니다.",
            setup_en="Repair Risk evidence first, then rerun the same input before creating any forecast experiment.",
            setup_ko="먼저 Risk 근거를 보정한 뒤 같은 입력으로 재실행하고 예측 실험을 생성하세요.",
            pass_criteria_en=[
                "Risk decision_usable becomes true.",
                "No forecast result is shown as valid while the data gate is blocked.",
            ],
            pass_criteria_ko=[
                "Risk decision_usable이 true가 됩니다.",
                "데이터 게이트가 차단된 동안 예측 결과를 유효한 결과로 표시하지 않습니다.",
            ],
            evidence_refs=["data_quality", "evidence"],
        )
        return items

    baseline_targets = full_company_tickers or subjects
    add(
        test_id="walk_forward_baseline",
        label_en="Run walk-forward baseline",
        label_ko="워크포워드 기준선 실행",
        status="ok",
        priority=2,
        test_type="walk_forward",
        target_tickers=baseline_targets,
        horizon_days=63,
        rationale_en=f"Risk output is decision-usable for {subject_text}; baseline forecast validation gives a comparable out-of-sample reference.",
        rationale_ko=f"{subject_text}의 Risk 출력이 의사결정 지원에 사용 가능하므로 비교 가능한 표본외 기준선을 만듭니다.",
        setup_en="Use the same ticker list, 63-trading-day horizon, walk-forward split, and the current Risk run id as experiment context.",
        setup_ko="같은 종목 목록, 63거래일 horizon, walk-forward 분할, 현재 Risk run id를 실험 컨텍스트로 사용하세요.",
        pass_criteria_en=[
            "Out-of-sample metrics are present.",
            "Train/test date ranges do not overlap.",
            "Forecast report links back to this Risk input hash.",
        ],
        pass_criteria_ko=[
            "표본외 지표가 표시됩니다.",
            "학습/테스트 날짜 구간이 겹치지 않습니다.",
            "예측 리포트가 현재 Risk 입력 해시로 추적됩니다.",
        ],
        evidence_refs=["run_lineage", "company_profiles"],
    )

    if macro_pressure_count:
        add(
            test_id="macro_feature_leakage_check",
            label_en="Check macro-feature leakage",
            label_ko="매크로 피처 누수 점검",
            status="review",
            priority=1,
            test_type="leakage_check",
            target_tickers=baseline_targets,
            horizon_days=63,
            rationale_en=f"Macro pressure and {len(transmission_channels)} transmission channels are active in this Risk run.",
            rationale_ko=f"이번 Risk 실행에서 매크로 압력과 {len(transmission_channels)}개 전이 경로가 활성화되었습니다.",
            setup_en="Force each macro feature to use only values available at the forecast origin and compare with a price-only baseline.",
            setup_ko="각 매크로 피처가 예측 기준일에 사용 가능했던 값만 쓰도록 제한하고 가격 전용 기준선과 비교하세요.",
            pass_criteria_en=[
                "Feature as-of dates are not later than forecast origin.",
                "Macro-enabled model beats or explains parity with the price-only baseline.",
            ],
            pass_criteria_ko=[
                "피처 기준일이 예측 기준일보다 늦지 않습니다.",
                "매크로 포함 모델이 가격 전용 기준선 대비 개선되거나 동률 사유를 설명합니다.",
            ],
            evidence_refs=["macro_backdrop", "transmission_channels", "run_lineage"],
        )

    if (market_score is not None and market_score >= 50.0) or severe_delta >= 10.0 or severe_projected >= 70.0:
        add(
            test_id="severe_scenario_forecast_backtest",
            label_en="Backtest severe-risk forecast window",
            label_ko="심각 시나리오 예측 구간 백테스트",
            status="review",
            priority=1,
            test_type="scenario_backtest",
            target_tickers=subjects,
            horizon_days=21,
            rationale_en=f"Market behavior risk={risk_score_text(market_score)}, severe delta={round(severe_delta, 1)}, projected severe risk={round(severe_projected, 1)}.",
            rationale_ko=f"시장 행동 리스크={risk_score_text(market_score)}, 심각 시나리오 변화={round(severe_delta, 1)}, 예상 심각 리스크={round(severe_projected, 1)}입니다.",
            setup_en="Run a short-horizon backtest around high-volatility windows and compare downside error, hit rate, and calibration.",
            setup_ko="고변동 구간 중심의 단기 백테스트를 실행하고 하방 오차, 적중률, 보정 상태를 비교하세요.",
            pass_criteria_en=[
                "Downside error is reported separately.",
                "Calibration is shown for adverse or severe windows.",
                "No forecast is converted into buy/sell/hold language.",
            ],
            pass_criteria_ko=[
                "하방 오차가 별도로 표시됩니다.",
                "악화 또는 심각 구간의 보정 상태가 표시됩니다.",
                "예측 결과를 매수/매도/보유 언어로 바꾸지 않습니다.",
            ],
            evidence_refs=["scenario_matrix", "company_profiles"],
        )

    if asset_proxy_tickers:
        add(
            test_id="asset_proxy_validation",
            label_en="Validate asset-proxy forecast scope",
            label_ko="자산 프록시 예측 범위 검증",
            status="review",
            priority=2,
            test_type="asset_proxy_validation",
            target_tickers=asset_proxy_tickers,
            horizon_days=63,
            rationale_en=f"{', '.join(asset_proxy_tickers[:5])} uses price and macro evidence, not company fundamentals.",
            rationale_ko=f"{', '.join(asset_proxy_tickers[:5])}는 기업 재무가 아니라 가격과 매크로 근거로 표현됩니다.",
            setup_en="Use proxy-specific features such as duration, rates, credit, liquidity, and volatility; do not require SEC or statement features.",
            setup_ko="듀레이션, 금리, 신용, 유동성, 변동성 같은 프록시 전용 피처를 사용하고 SEC 또는 재무제표 피처를 요구하지 마세요.",
            pass_criteria_en=[
                "Model card states asset-proxy scope.",
                "Missing company fundamentals remain visible as non-applicable inputs.",
            ],
            pass_criteria_ko=[
                "모델 카드에 자산 프록시 범위가 표시됩니다.",
                "기업 재무 누락은 미적용 입력으로 계속 보입니다.",
            ],
            evidence_refs=["company_profiles", "data_quality"],
        )

    if request.mode == "portfolio":
        add(
            test_id="portfolio_component_oos_check",
            label_en="Validate portfolio component forecasts",
            label_ko="포트폴리오 구성 예측 검증",
            status="review",
            priority=2,
            test_type="portfolio_overlay",
            target_tickers=subjects,
            horizon_days=63,
            rationale_en="Portfolio Risk output should be checked at both component and weighted-overlay levels.",
            rationale_ko="포트폴리오 Risk 출력은 구성 종목과 가중 오버레이 수준을 함께 검증해야 합니다.",
            setup_en="Run component forecasts, then compare weighted forecast errors with largest Risk contributors.",
            setup_ko="구성 종목 예측을 실행한 뒤 가중 예측 오차를 최대 Risk 기여 종목과 비교하세요.",
            pass_criteria_en=[
                "Largest weighted contributors are visible.",
                "Portfolio forecast error is decomposed by ticker.",
            ],
            pass_criteria_ko=[
                "최대 가중 기여 종목이 표시됩니다.",
                "포트폴리오 예측 오차가 종목별로 분해됩니다.",
            ],
            evidence_refs=["portfolio_overlay", "priority_map"],
        )

    status_rank = {"blocked": 0, "review": 1, "ok": 2}
    return sorted(
        items,
        key=lambda item: (item.priority, status_rank.get(item.status, 3), item.test_id),
    )[:6]


def _build_forecast_validation_plan(
    *,
    request: RiskWorkbenchRequest,
    input_hash: str,
    decision_usable: bool,
    data_quality,
    ml_validation_tests: list[RiskMlValidationTest],
) -> RiskForecastValidationPlan:
    language = _risk_output_language(request)
    tests = list(ml_validation_tests or [])
    launchable_tests = [item for item in tests if getattr(item, "launch_href", None)]
    blocked_reasons: list[str] = []

    if not decision_usable:
        missing = list(getattr(data_quality, "missing_inputs", []) or [])
        stale = list(getattr(data_quality, "stale_inputs", []) or [])
        if missing:
            blocked_reasons.append(
                _risk_text(
                    language,
                    f"Risk data gate is blocked by missing inputs: {', '.join(missing[:4])}.",
                    f"Risk 데이터 게이트가 누락 입력으로 차단되었습니다: {', '.join(missing[:4])}.",
                )
            )
        if stale:
            blocked_reasons.append(
                _risk_text(
                    language,
                    f"Risk data gate includes stale inputs: {', '.join(stale[:4])}.",
                    f"Risk 데이터 게이트에 오래된 입력이 포함되어 있습니다: {', '.join(stale[:4])}.",
                )
            )
        if not blocked_reasons:
            blocked_reasons.append(
                _risk_text(
                    language,
                    "Risk data-quality gate is blocked; repair evidence before creating a Forecast experiment.",
                    "Risk 데이터 품질 게이트가 차단되었습니다. Forecast 실험 생성 전 근거를 보정하세요.",
                )
            )

    if not tests:
        blocked_reasons.append(
            _risk_text(
                language,
                "No ML Forecast validation test was generated for this Risk run.",
                "이 Risk 실행에서 ML Forecast 검증 테스트가 생성되지 않았습니다.",
            )
        )
    elif not launchable_tests:
        blocked_reasons.append(
            _risk_text(
                language,
                "No launchable ML Forecast test is available until the Risk data gate is repaired.",
                "Risk 데이터 게이트를 보정하기 전에는 실행 가능한 ML Forecast 테스트가 없습니다.",
            )
        )

    preferred_order = ["risk_data_gate_recheck"]
    if request.mode == "portfolio":
        preferred_order.extend(["portfolio_component_oos_check", "asset_proxy_validation"])
    else:
        preferred_order.extend(["asset_proxy_validation", "portfolio_component_oos_check"])
    preferred_order.extend(
        [
            "macro_feature_leakage_check",
            "severe_scenario_forecast_backtest",
            "walk_forward_baseline",
        ]
    )
    primary = next((item for test_id in preferred_order for item in tests if item.test_id == test_id), None)
    if primary is None and tests:
        primary = tests[0]

    if blocked_reasons:
        status = "blocked"
    elif any(item.status == "review" for item in tests) or any(not getattr(item, "launch_href", None) for item in tests):
        status = "review"
    else:
        status = "ok"

    run_order = [
        f"{item.priority}:{item.test_id}:{item.status}"
        for item in sorted(
            tests,
            key=lambda item: (
                preferred_order.index(item.test_id) if item.test_id in preferred_order else 99,
                item.priority,
            ),
        )
    ][:6]

    controls = [
        _risk_text(
            language,
            "Carry risk_run_id, riskInputHash, riskValidation, and source_context into every Forecast request.",
            "모든 Forecast 요청에 risk_run_id, riskInputHash, riskValidation, source_context를 전달하세요.",
        ),
        _risk_text(
            language,
            "Freeze feature as-of dates at the forecast origin to avoid macro or cross-asset leakage.",
            "매크로 또는 교차자산 누수를 피하기 위해 피처 기준일을 예측 시점으로 고정하세요.",
        ),
        _risk_text(
            language,
            "Compare macro or scenario-enabled runs against a price-only walk-forward baseline.",
            "매크로 또는 시나리오 포함 실행은 가격 전용 walk-forward 기준선과 비교하세요.",
        ),
        _risk_text(
            language,
            "Keep Forecast output in validation language; do not convert it into buy/sell/hold instructions.",
            "Forecast 출력은 검증 언어로 유지하고 매수/매도/보유 지시로 변환하지 마세요.",
        ),
    ]
    criteria = list(getattr(primary, "pass_criteria", []) or [])[:4] if primary else []
    criteria.extend(
        [
            _risk_text(
                language,
                "Forecast result links back to the Risk input hash.",
                "Forecast 결과가 Risk 입력 해시로 다시 추적됩니다.",
            ),
            _risk_text(
                language,
                "Train and test ranges are visible and non-overlapping.",
                "학습/테스트 구간이 표시되고 서로 겹치지 않습니다.",
            ),
            _risk_text(
                language,
                "Downside error, calibration, or leakage checks are reviewed before user-facing reuse.",
                "사용자-facing 재사용 전 하방 오차, 보정 상태 또는 누수 점검을 검토합니다.",
            ),
        ]
    )
    criteria = list(dict.fromkeys([item for item in criteria if item]))[:7]

    if status == "blocked":
        readiness_note = _risk_text(
            language,
            "Forecast validation is blocked by Risk evidence quality; rerun Risk after repairing the listed blockers.",
            "Forecast 검증은 Risk 근거 품질 때문에 차단되었습니다. 표시된 차단 사유를 보정한 뒤 Risk를 다시 실행하세요.",
        )
    elif status == "review":
        readiness_note = _risk_text(
            language,
            "Forecast validation is launchable, but review tests and service controls must be checked before reuse.",
            "Forecast 검증은 실행 가능하지만 재사용 전 검토 테스트와 서비스 통제를 확인해야 합니다.",
        )
    else:
        readiness_note = _risk_text(
            language,
            "Forecast validation is ready for controlled local execution with Risk provenance attached.",
            "Forecast 검증은 Risk 출처가 연결된 통제된 로컬 실행 준비가 되었습니다.",
        )

    return RiskForecastValidationPlan(
        status=status,
        primary_test_id=getattr(primary, "test_id", None),
        primary_label=getattr(primary, "label", "") or "",
        primary_launch_href=getattr(primary, "launch_href", None),
        run_order=run_order,
        readiness_note=readiness_note,
        experiment_controls=controls,
        acceptance_criteria=criteria,
        blocked_reasons=blocked_reasons,
        evidence_refs=[
            "ml_validation_tests",
            "source_context",
            "input_hash",
            "data_quality",
            "run_lineage",
        ],
    )


def _build_run_lineage(
    *,
    request: RiskWorkbenchRequest,
    company_profiles,
    macro_backdrop,
    scenario_matrix,
    evidence,
    data_quality,
    service_readiness: RiskServiceReadiness,
) -> RiskRunLineage:
    freshness_counts: dict[str, int] = {}
    for item in evidence:
        freshness = str(getattr(item, "freshness", "unknown") or "unknown")
        freshness_counts[freshness] = freshness_counts.get(freshness, 0) + 1

    any_profile_usable = any(bool(getattr(profile, "decision_usable", False)) for profile in company_profiles)
    any_profile_blocked = any(not bool(getattr(profile, "decision_usable", False)) for profile in company_profiles)
    company_status = "ok" if any_profile_usable and not any_profile_blocked else ("review" if any_profile_usable else "blocked")
    macro_status = "ok" if str(getattr(macro_backdrop, "risk_level", "unknown")) != "unknown" else "review"
    scenario_status = "ok" if scenario_matrix else ("disabled" if not request.include_macro_scenarios else "review")
    data_status = "ok" if bool(getattr(data_quality, "decision_usable", False)) else "blocked"

    return RiskRunLineage(
        service_version="risk-workbench-v1",
        scenario_set=request.scenario_set,
        lookback_days=request.lookback_days,
        subjects=list(request.tickers),
        subject_count=len(request.tickers),
        evidence_count=len(evidence),
        freshness_counts=freshness_counts,
        adapter_statuses={
            "company": company_status,
            "macro": macro_status,
            "scenario": scenario_status,
            "data_quality": data_status,
            "service_readiness": service_readiness.status,
        },
        missing_input_count=len(getattr(data_quality, "missing_inputs", []) or []),
        stale_input_count=len(getattr(data_quality, "stale_inputs", []) or []),
        provider_warning_count=len(getattr(data_quality, "provider_warnings", []) or []),
        replay_fields=[
            "mode",
            "tickers",
            "positions",
            "market",
            "lookback_days",
            "scenario_set",
            "include_sec",
            "include_macro_scenarios",
            "output_language",
        ],
    )


def _build_input_receipt(
    *,
    request: RiskWorkbenchRequest,
    data_quality,
    company_profiles,
) -> RiskInputReceipt:
    language = _risk_output_language(request)
    weights_by_ticker = _positions_by_ticker(request)
    normalized_positions = [
        RiskInputPositionReceipt(
            ticker=profile.ticker,
            weight=round(float(weights_by_ticker.get(profile.ticker, 0.0)), 6) if weights_by_ticker else None,
            coverage_scope=getattr(profile, "coverage_scope", "unknown") or "unknown",
            decision_usable=bool(getattr(profile, "decision_usable", False)),
        )
        for profile in company_profiles
    ]
    weight_sum = round(sum(float(position.weight or 0.0) for position in normalized_positions), 6) if normalized_positions else None
    asset_proxy_tickers = [
        position.ticker
        for position in normalized_positions
        if position.coverage_scope == "asset_proxy"
    ]
    blocked_tickers = [
        position.ticker
        for position in normalized_positions
        if not position.decision_usable
    ]
    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    warning_count = len(getattr(data_quality, "provider_warnings", []) or [])

    if blocked_tickers or not bool(getattr(data_quality, "decision_usable", False)):
        status = "blocked"
    elif asset_proxy_tickers or missing_count or stale_count or warning_count:
        status = "review"
    else:
        status = "ok"

    notes: list[str] = []
    if request.mode == "portfolio":
        notes.append(
            _risk_text(
                language,
                f"Portfolio weights normalized to {weight_sum if weight_sum is not None else 0.0:.4f}.",
                f"포트폴리오 비중은 합계 {weight_sum if weight_sum is not None else 0.0:.4f}로 정규화되었습니다.",
            )
        )
    elif request.mode == "watchlist":
        notes.append(
            _risk_text(
                language,
                "Watchlist subjects use equal analytical weight for aggregate risk.",
                "관심종목 대상은 집계 리스크에서 동일 분석 비중으로 처리됩니다.",
            )
        )
    else:
        notes.append(
            _risk_text(
                language,
                "Company mode uses the first normalized ticker as the analysis subject.",
                "기업 모드는 정규화된 첫 번째 티커를 분석 대상으로 사용합니다.",
            )
        )
    if asset_proxy_tickers:
        notes.append(
            _risk_text(
                language,
                f"Asset-proxy scope is explicit for {', '.join(asset_proxy_tickers[:5])}.",
                f"{', '.join(asset_proxy_tickers[:5])}는 자산 프록시 범위로 명시됩니다.",
            )
        )
    if blocked_tickers:
        notes.append(
            _risk_text(
                language,
                f"Blocked subjects require input repair: {', '.join(blocked_tickers[:5])}.",
                f"차단된 대상은 입력 복구가 필요합니다: {', '.join(blocked_tickers[:5])}.",
            )
        )
    if missing_count or stale_count or warning_count:
        notes.append(
            _risk_text(
                language,
                f"Data review counts: missing={missing_count}, stale={stale_count}, provider_warnings={warning_count}.",
                f"데이터 검토 수: 누락={missing_count}, 오래됨={stale_count}, 공급자 경고={warning_count}.",
            )
        )

    replay_notes = [
        f"mode={request.mode}",
        f"subjects={','.join(request.tickers)}",
        f"market={request.market}",
        f"scenario_set={request.scenario_set}",
        f"lookback_days={request.lookback_days}",
    ]
    if request.mode == "portfolio":
        replay_notes.append(
            "positions="
            + ",".join(
                f"{position.ticker}:{float(position.weight or 0.0):.6f}"
                for position in normalized_positions
            )
        )

    return RiskInputReceipt(
        mode=request.mode,
        subjects=list(request.tickers),
        subject_count=len(request.tickers),
        market=request.market,
        scenario_set=request.scenario_set,
        lookback_days=request.lookback_days,
        output_language=request.output_language,
        normalized_positions=normalized_positions,
        weight_sum=weight_sum,
        status=status,
        compatibility_notes=list(dict.fromkeys(notes))[:8],
        replay_notes=replay_notes,
    )


def _build_release_packet(
    *,
    request: RiskWorkbenchRequest,
    input_hash: str,
    decision_usable: bool,
    data_quality,
    company_profiles,
    macro_backdrop,
    service_readiness: RiskServiceReadiness,
    run_lineage: RiskRunLineage,
    ml_validation_tests: list[RiskMlValidationTest],
) -> RiskReleasePacket:
    language = _risk_output_language(request)
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    macro_unknown = str(getattr(macro_backdrop, "risk_level", "unknown") or "unknown") == "unknown"
    provider_warnings = list(getattr(data_quality, "provider_warnings", []) or [])
    has_forecast_launch = any(bool(getattr(item, "launch_href", None)) for item in ml_validation_tests)

    if service_readiness.status == "blocked" or not decision_usable:
        packet_status = "blocked"
    else:
        # Public service exposure still needs explicit platform controls even when the run is decision-usable.
        packet_status = "review_required"

    def check(
        check_id: str,
        label_en: str,
        label_ko: str,
        status: str,
        next_en: str,
        next_ko: str,
        evidence_refs: list[str],
    ) -> RiskReleaseCheck:
        return RiskReleaseCheck(
            check_id=check_id,
            label=_risk_text(language, label_en, label_ko),
            status=status if status in {"ok", "review", "blocked"} else "review",
            next_step=_risk_text(language, next_en, next_ko),
            evidence_refs=evidence_refs,
        )

    deployment_checks = [
        check(
            "api_contract",
            "Risk API contract returns typed response",
            "Risk API 계약이 타입화된 응답을 반환",
            "ok",
            "Keep /api/v1/risk/workbench stable for clients.",
            "/api/v1/risk/workbench를 클라이언트용 안정 계약으로 유지하세요.",
            ["service_readiness", "calculation_policy"],
        ),
        check(
            "decision_data_gate",
            "Decision data gate is usable",
            "의사결정 데이터 게이트 사용 가능",
            "ok" if decision_usable else "blocked",
            "Block release traffic when decision_usable=false.",
            "decision_usable=false일 때 릴리스 트래픽을 차단하세요.",
            ["data_quality", "service_readiness"],
        ),
        check(
            "run_lineage_replay",
            "Run lineage and replay fields are present",
            "실행 감사와 재현 필드가 존재",
            "ok" if input_hash and run_lineage.replay_fields else "review",
            "Persist risk_run_id, input_hash, and replay fields with saved outputs.",
            "저장 출력에는 risk_run_id, input_hash, 재현 필드를 함께 보존하세요.",
            ["run_lineage"],
        ),
        check(
            "provider_warning_gate",
            "Provider and macro warnings are gated",
            "공급자와 매크로 경고가 게이트 처리됨",
            "review" if provider_warnings or macro_unknown else "ok",
            "Review provider warnings before exposing this run externally.",
            "외부 노출 전 공급자 경고를 검토하세요.",
            ["data_quality", "macro_backdrop"],
        ),
        check(
            "asset_proxy_release_scope",
            "Asset-proxy scope is explicit",
            "자산 프록시 범위가 명시됨",
            "review" if asset_proxy_tickers else "ok",
            "Show proxy-scope wording for ETF or macro proxy subjects.",
            "ETF 또는 매크로 프록시 대상에는 프록시 범위 문구를 표시하세요.",
            ["company_profiles", "data_quality"],
        ),
        check(
            "forecast_source_context",
            "ML Forecast source context is preserved",
            "ML Forecast 출처 맥락이 보존됨",
            "ok" if has_forecast_launch else ("blocked" if not decision_usable else "review"),
            "Use the generated Forecast launch URL to retain Risk test metadata.",
            "생성된 Forecast 실행 URL로 Risk 테스트 메타데이터를 유지하세요.",
            ["ml_validation_tests", "run_lineage"],
        ),
        check(
            "ai_output_guardrails",
            "AI output guardrails are grounded in typed evidence",
            "AI output guardrails are grounded in typed evidence",
            "ok" if decision_usable else "blocked",
            "Require ai_output_controls before exposing model-written Risk narratives.",
            "Require ai_output_controls before exposing model-written Risk narratives.",
            ["ai_output_controls", "evidence_coverage", "decision_quality"],
        ),
        check(
            "external_service_controls",
            "External auth, rate limit, retention, and monitoring are defined",
            "외부 인증, 제한, 보존, 모니터링이 정의됨",
            "blocked" if packet_status == "blocked" else "review",
            "Add platform auth, rate limits, retention policy, and alerting before public deployment.",
            "공개 배포 전 플랫폼 인증, rate limit, 보존 정책, 알림을 추가하세요.",
            ["service_readiness"],
        ),
    ]

    return RiskReleasePacket(
        status=packet_status,
        deployment_target="controlled_api_service",
        api_routes=[
            "/api/v1/risk/health",
            "/api/v1/risk/workbench",
            "/api/v1/risk/company/{ticker}",
            "/api/v1/risk/macro",
            "/api/v1/risk/scenario",
        ],
        ui_routes=[
            "/ui/#risk",
            "/ui/?tab=ml-forecast#ml-forecast",
        ],
        required_audit_fields=[
            "risk_run_id",
            "input_hash",
            "as_of",
            "decision_usable",
            "service_readiness.status",
            "release_packet.status",
            "run_lineage.replay_fields",
            "data_quality.missing_inputs",
            "calculation_policy.version",
            "ai_output_controls.status",
        ],
        validation_commands=[
            "python -m py_compile core/schemas/risk.py app/api/routers/risk.py pipelines/risk/*.py",
            "python -m pytest tests/test_risk_workbench_api.py tests/test_ui_risk_contract.py -q",
            "node --check app/web/app.js",
            "python scripts/check_ui_contract.py",
            "browser smoke: /ui/#risk desktop and 390px mobile overflow",
        ],
        deployment_checks=deployment_checks,
        rollback_triggers=(
            [
                "decision_usable=false",
                "release_packet.status=blocked",
                "provider warnings prevent freshness review",
                "missing risk_run_id/input_hash/run_lineage",
                "browser smoke reports horizontal overflow or console errors",
            ]
            if language == "en"
            else [
                "decision_usable=false",
                "release_packet.status=blocked",
                "공급자 경고로 신선도 검토 불가",
                "risk_run_id/input_hash/run_lineage 누락",
                "브라우저 스모크에서 가로 overflow 또는 콘솔 오류 발생",
            ]
        ),
        data_dependencies=(
            [
                "Quantamental company and price-risk payloads",
                "Macro dashboard and provider-health payloads",
                "Risk data-quality policy",
                "Risk-to-Forecast source_context handoff",
            ]
            if language == "en"
            else [
                "Quantamental 기업 및 가격 리스크 payload",
                "Macro 대시보드 및 공급자 상태 payload",
                "Risk 데이터 품질 정책",
                "Risk-to-Forecast source_context 핸드오프",
            ]
        ),
        limitations=(
            [
                "Release packet is an operability contract, not an investment conclusion.",
                "Public deployment still requires platform auth, rate limiting, retention, and monitoring outside this response.",
                "Provider freshness and asset-proxy scope remain run-specific.",
            ]
            if language == "en"
            else [
                "릴리스 패킷은 운용 계약이며 투자 결론이 아닙니다.",
                "공개 배포에는 이 응답 외부의 플랫폼 인증, rate limit, 보존, 모니터링이 필요합니다.",
                "공급자 신선도와 자산 프록시 범위는 실행별로 달라집니다.",
            ]
        ),
    )


def _build_decision_path(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    decision_usable: bool,
    priority_map: list[RiskPriorityCell],
    action_checklist: list[RiskActionItem],
    handoff_queue: list[RiskHandoffItem],
    ml_validation_tests: list[RiskMlValidationTest],
    service_readiness: RiskServiceReadiness,
) -> RiskDecisionPath:
    language = _risk_output_language(request)
    service_status = str(getattr(service_readiness, "status", "review_required") or "review_required")
    if not decision_usable or service_status == "blocked":
        status = "blocked"
    elif service_status == "review_required" or any(item.status == "review" for item in action_checklist[:3]):
        status = "review"
    else:
        status = "ok"

    top_cell = priority_map[0] if priority_map else None
    if top_cell:
        top_focus = f"{top_cell.subject} / {top_cell.vector}"
        top_score = f"{round(float(top_cell.score), 1)}" if top_cell.score is not None else "unknown"
    else:
        top_focus = _risk_text(language, "no priority cell", "우선순위 셀 없음")
        top_score = "unknown"

    if status == "blocked":
        headline = _risk_text(
            language,
            "Repair the Risk data gate before using this run for a workflow.",
            "워크플로우에 사용하기 전에 Risk 데이터 게이트를 먼저 복구하세요.",
        )
    elif status == "review":
        headline = _risk_text(
            language,
            f"Review {top_focus} first, then open the linked workflow.",
            f"{top_focus}를 먼저 검토한 뒤 연결된 워크플로우를 여세요.",
        )
    else:
        headline = _risk_text(
            language,
            "Risk run is usable; validate forecasts and retain lineage before service use.",
            "Risk 실행은 사용 가능하므로 Forecast 검증과 실행 감사를 보존한 뒤 서비스에 연결하세요.",
        )

    action = next((item for item in action_checklist if item.status in {"blocked", "review"}), None)
    if action is None and action_checklist:
        action = action_checklist[0]
    if action is not None:
        primary_action = action.next_step or action.label or action.action_id
        evidence_refs = list(action.evidence_refs)
    else:
        primary_action = _risk_text(
            language,
            f"Confirm the top priority cell {top_focus} with score {top_score}.",
            f"최우선 셀 {top_focus}와 점수 {top_score}를 확인하세요.",
        )
        evidence_refs = ["priority_map"]

    handoff = next((item for item in handoff_queue if item.status != "blocked"), None)
    if handoff is None and handoff_queue:
        handoff = handoff_queue[0]
    if handoff is not None:
        primary_handoff_label = handoff.label or handoff.handoff_id
        primary_handoff_href = handoff.href or "/ui/#risk"
        evidence_refs.extend(handoff.evidence_refs)
    else:
        primary_handoff_label = _risk_text(language, "Stay in Risk", "Risk에서 계속 검토")
        primary_handoff_href = "/ui/#risk"

    ml_test = next((item for item in ml_validation_tests if item.launch_href), None)
    if ml_test is not None:
        ml_validation_label = ml_test.label or ml_test.test_id
        ml_validation_href = ml_test.launch_href
        evidence_refs.extend(ml_test.evidence_refs)
    else:
        ml_validation_label = None
        ml_validation_href = None

    evidence_refs.extend(["priority_map", "service_readiness", "run_lineage"])
    return RiskDecisionPath(
        status=status,
        headline=headline,
        primary_action=primary_action,
        primary_handoff_label=primary_handoff_label,
        primary_handoff_href=primary_handoff_href,
        ml_validation_label=ml_validation_label,
        ml_validation_href=ml_validation_href,
        service_gate=service_status if service_status in {"ready", "review_required", "blocked"} else "review_required",
        evidence_refs=list(dict.fromkeys(evidence_refs))[:8],
    )


def _coverage_status(value: str) -> str:
    clean = str(value or "").lower()
    if clean in {"blocked", "failed", "fail", "error"}:
        return "blocked"
    if clean in {"ok", "ready", "fresh", "success"}:
        return "ok"
    return "review"


def _coverage_score(status: str) -> float:
    if status == "ok":
        return 100.0
    if status == "blocked":
        return 0.0
    return 62.0


def _build_evidence_coverage(
    *,
    request: RiskWorkbenchRequest,
    decision_usable: bool,
    evidence,
    data_quality,
    company_profiles,
    macro_backdrop,
    scenario_matrix,
    service_readiness: RiskServiceReadiness,
    input_receipt: RiskInputReceipt,
    release_packet: RiskReleasePacket,
    ml_validation_tests: list[RiskMlValidationTest],
) -> RiskEvidenceCoverage:
    language = _risk_output_language(request)
    evidence_items = list(evidence or [])
    company_evidence_count = sum(
        1
        for item in evidence_items
        if str(getattr(item, "source", "") or "").startswith("quantamental")
        or any(str(getattr(item, "evidence_id", "") or "").startswith(f"{ticker}:") for ticker in request.tickers)
    )
    macro_evidence_count = sum(
        1
        for item in evidence_items
        if str(getattr(item, "source", "") or "").startswith("pipelines.macro")
        or str(getattr(item, "evidence_id", "") or "").startswith("macro:")
    )
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    provider_warning_count = len(getattr(data_quality, "provider_warnings", []) or [])
    asset_proxy_tickers = [
        profile.ticker
        for profile in company_profiles
        if getattr(profile, "coverage_scope", "") == "asset_proxy"
    ]
    blocked_tickers = [
        profile.ticker
        for profile in company_profiles
        if not getattr(profile, "decision_usable", False)
    ]
    company_scopes = sorted(
        {
            str(getattr(profile, "coverage_scope", "unknown") or "unknown")
            for profile in company_profiles
        }
    )
    company_status = "ok"
    if blocked_tickers and not decision_usable:
        company_status = "blocked"
    elif asset_proxy_tickers or blocked_tickers or company_evidence_count == 0:
        company_status = "review"

    macro_status = "ok"
    if str(getattr(macro_backdrop, "risk_level", "unknown") or "unknown") == "unknown":
        macro_status = "review" if decision_usable else "blocked"
    elif provider_warning_count:
        macro_status = "review"

    scenario_status = "ok" if scenario_matrix else ("review" if request.include_macro_scenarios else "ok")
    forecast_launch_count = sum(1 for item in ml_validation_tests if getattr(item, "launch_href", None))
    forecast_status = "ok" if forecast_launch_count else ("blocked" if not decision_usable else "review")
    service_status = "blocked" if release_packet.status == "blocked" else _coverage_status(service_readiness.status)
    evidence_status = "ok"
    if not evidence_items and not decision_usable:
        evidence_status = "blocked"
    elif missing_count or stale_count or provider_warning_count or not evidence_items:
        evidence_status = "review"

    def add(
        coverage_id: str,
        domain: str,
        label_en: str,
        label_ko: str,
        status: str,
        subject: str,
        coverage_scope: str,
        evidence_count: int,
        freshness: str,
        impact_en: str,
        impact_ko: str,
        next_step_en: str,
        next_step_ko: str,
        evidence_refs: list[str],
    ) -> RiskEvidenceCoverageItem:
        clean_status = status if status in {"ok", "review", "blocked"} else "review"
        clean_freshness = freshness if freshness in {"fresh", "partial", "stale", "missing", "unknown"} else "unknown"
        return RiskEvidenceCoverageItem(
            coverage_id=coverage_id,
            domain=domain,  # type: ignore[arg-type]
            label=_risk_text(language, label_en, label_ko),
            status=clean_status,
            subject=subject,
            coverage_scope=coverage_scope,
            evidence_count=max(0, int(evidence_count or 0)),
            freshness=clean_freshness,  # type: ignore[arg-type]
            impact=_risk_text(language, impact_en, impact_ko),
            next_step=_risk_text(language, next_step_en, next_step_ko),
            evidence_refs=evidence_refs,
        )

    items = [
        add(
            "input_normalization",
            "input",
            "Input normalization",
            "입력 정규화",
            _coverage_status(input_receipt.status),
            ",".join(input_receipt.subjects or request.tickers),
            request.mode,
            len(input_receipt.normalized_positions),
            "unknown",
            "Shows what the service actually analyzed and can replay.",
            "서비스가 실제로 분석한 대상과 재현 조건을 보여줍니다.",
            "Fix blocked compatibility notes before comparing outputs.",
            "차단된 호환성 메모를 먼저 보정한 뒤 결과를 비교하세요.",
            ["input_receipt", "run_lineage"],
        ),
        add(
            "company_profile_coverage",
            "company",
            "Company and asset profile coverage",
            "기업 및 자산 프로필 커버리지",
            company_status,
            ",".join(request.tickers),
            ",".join(company_scopes) or "unknown",
            company_evidence_count,
            str(getattr(data_quality, "freshness", "unknown") or "unknown"),
            "Separates full company coverage from ETF or macro-proxy scope.",
            "기업 전체 커버리지와 ETF/매크로 프록시 범위를 분리합니다.",
            "Repair blocked tickers or treat asset-proxy rows as limited scope.",
            "차단된 티커를 보정하거나 자산 프록시 행을 제한 범위로 해석하세요.",
            ["company_profiles", "data_quality"],
        ),
        add(
            "macro_backdrop_coverage",
            "macro",
            "Macro backdrop coverage",
            "매크로 배경 커버리지",
            macro_status,
            "MACRO",
            str(getattr(macro_backdrop, "regime", "unknown") or "unknown"),
            macro_evidence_count,
            "fresh" if macro_status == "ok" else "unknown",
            "Confirms rates, growth, inflation, credit, and liquidity context.",
            "금리, 성장, 인플레이션, 신용, 유동성 맥락을 확인합니다.",
            "Refresh or review macro provider warnings before service exposure.",
            "서비스 노출 전 매크로 공급자 경고를 갱신하거나 검토하세요.",
            ["macro_backdrop", "data_quality.provider_warnings"],
        ),
        add(
            "scenario_coverage",
            "scenario",
            "Scenario stress coverage",
            "시나리오 스트레스 커버리지",
            scenario_status,
            request.scenario_set,
            "base_adverse_severe" if scenario_matrix else "not_generated",
            len(scenario_matrix or []),
            "unknown",
            "Shows whether severe paths exist before users rely on the run.",
            "사용자가 결과를 활용하기 전 심각 경로가 있는지 보여줍니다.",
            "Enable macro scenarios or inspect missing transmission channels.",
            "매크로 시나리오를 켜거나 누락된 전이 경로를 확인하세요.",
            ["scenario_matrix", "transmission_channels"],
        ),
        add(
            "forecast_validation_coverage",
            "forecast",
            "ML Forecast validation coverage",
            "ML Forecast 검증 커버리지",
            forecast_status,
            ",".join(request.tickers),
            f"launches={forecast_launch_count}",
            len(ml_validation_tests),
            "unknown",
            "Connects this Risk run to leakage, walk-forward, and scenario tests.",
            "Risk 결과를 leakage, walk-forward, 시나리오 테스트로 연결합니다.",
            "Open the first launchable Forecast test or repair the data gate.",
            "첫 Forecast 검증 링크를 열거나 데이터 게이트를 보정하세요.",
            ["ml_validation_tests", "source_context"],
        ),
        add(
            "service_release_coverage",
            "service",
            "Service release coverage",
            "서비스 배포 커버리지",
            service_status,
            release_packet.deployment_target,
            release_packet.contract_version,
            len(release_packet.deployment_checks or []),
            "unknown",
            "Keeps auth, rate limit, retention, monitoring, and rollback visible.",
            "인증, 제한, 보존, 모니터링, 롤백 조건을 계속 보이게 합니다.",
            "Complete external platform controls before public deployment.",
            "공개 배포 전 외부 플랫폼 통제를 완료하세요.",
            ["service_readiness", "release_packet"],
        ),
        add(
            "evidence_inventory",
            "evidence",
            "Evidence inventory",
            "근거 인벤토리",
            evidence_status,
            ",".join(request.tickers),
            f"missing={missing_count}; stale={stale_count}; warnings={provider_warning_count}",
            len(evidence_items),
            str(getattr(data_quality, "freshness", "unknown") or "unknown"),
            "Summarizes whether source rows are enough for audit and comparison.",
            "감사와 비교에 필요한 원천 행이 충분한지 요약합니다.",
            "Resolve missing or stale evidence before treating the run as production-ready.",
            "운영 준비 상태로 보기 전 누락 또는 오래된 근거를 해결하세요.",
            ["evidence", "data_quality"],
        ),
    ]

    scores = [_coverage_score(item.status) for item in items]
    score = round(sum(scores) / max(1, len(scores)), 2)
    if any(item.status == "blocked" for item in items):
        status = "blocked"
    elif any(item.status == "review" for item in items):
        status = "review"
    else:
        status = "ok"
    return RiskEvidenceCoverage(
        status=status,
        score=score,
        covered_domains=[item.domain for item in items if item.status == "ok"],
        review_domains=[item.domain for item in items if item.status == "review"],
        blocked_domains=[item.domain for item in items if item.status == "blocked"],
        items=items,
    )


def _build_compatibility_matrix(
    *,
    request: RiskWorkbenchRequest,
    decision_usable: bool,
    company_profiles,
    input_receipt: RiskInputReceipt,
    evidence_coverage: RiskEvidenceCoverage,
    ml_validation_tests: list[RiskMlValidationTest],
    release_packet: RiskReleasePacket,
) -> RiskCompatibilityMatrix:
    language = _risk_output_language(request)
    launch_by_ticker: dict[str, str] = {}
    for item in ml_validation_tests:
        launch_href = getattr(item, "launch_href", None)
        if not launch_href:
            continue
        for ticker in getattr(item, "target_tickers", []) or []:
            clean = str(ticker or "").strip().upper()
            if clean and clean not in launch_by_ticker:
                launch_by_ticker[clean] = str(launch_href)

    receipt_status_by_ticker = {
        position.ticker: str(position.coverage_scope or "unknown")
        for position in input_receipt.normalized_positions
    }

    rows: list[RiskCompatibilityRow] = []
    for profile in company_profiles:
        ticker = str(getattr(profile, "ticker", "") or "").strip().upper()
        if not ticker:
            continue
        coverage_scope = str(getattr(profile, "coverage_scope", "unknown") or receipt_status_by_ticker.get(ticker, "unknown"))
        usable = bool(getattr(profile, "decision_usable", False))
        launch_href = launch_by_ticker.get(ticker)
        supported: list[str] = []
        blocked: list[str] = []
        evidence_refs = ["input_receipt", "company_profiles", "evidence_coverage"]

        if not usable:
            status = "blocked"
            blocked = [
                _risk_text(language, "Risk scoring", "Risk 점수 산출"),
                _risk_text(language, "Quantamental drilldown", "Quantamental 드릴다운"),
                _risk_text(language, "ML Forecast launch", "ML Forecast 실행"),
                _risk_text(language, "AI Portfolio overlay", "AI Portfolio 오버레이"),
            ]
            decision_note = _risk_text(
                language,
                f"{ticker} is blocked because required company or price evidence is missing.",
                f"{ticker}는 필수 기업 또는 가격 근거가 부족해 차단되었습니다.",
            )
            next_step = _risk_text(
                language,
                "Repair the data gate, then rerun the same Risk request before using downstream workflows.",
                "데이터 게이트를 복구한 뒤 같은 Risk 요청을 재실행하고 후속 워크플로우를 사용하세요.",
            )
            evidence_refs.extend(["data_quality", "ml_validation_tests"])
        elif coverage_scope == "asset_proxy":
            status = "review"
            supported = [
                _risk_text(language, "Risk asset-proxy review", "Risk 자산 프록시 검토"),
                _risk_text(language, "Macro transmission review", "매크로 전이 검토"),
                _risk_text(language, "Scenario stress review", "시나리오 스트레스 검토"),
            ]
            if launch_href:
                supported.append(_risk_text(language, "ML Forecast proxy validation", "ML Forecast 프록시 검증"))
                evidence_refs.append("ml_validation_tests")
            blocked = [
                _risk_text(language, "Company fundamental claims", "기업 펀더멘털 주장"),
                _risk_text(language, "SEC evidence claims", "SEC 근거 주장"),
            ]
            decision_note = _risk_text(
                language,
                f"{ticker} is usable as a limited asset-proxy subject, not as full company-fundamental coverage.",
                f"{ticker}는 전체 기업 펀더멘털 커버리지가 아니라 제한된 자산 프록시 대상으로 사용할 수 있습니다.",
            )
            next_step = _risk_text(
                language,
                "Use proxy-specific Forecast validation and keep missing fundamentals visible in any shared output.",
                "프록시 전용 Forecast 검증을 사용하고 공유 출력에는 누락된 펀더멘털을 계속 표시하세요.",
            )
        elif usable:
            status = "ok" if decision_usable and evidence_coverage.status != "blocked" else "review"
            supported = [
                _risk_text(language, "Risk company review", "Risk 기업 검토"),
                _risk_text(language, "Quantamental drilldown", "Quantamental 드릴다운"),
                _risk_text(language, "Macro transmission review", "매크로 전이 검토"),
                _risk_text(language, "Scenario stress review", "시나리오 스트레스 검토"),
            ]
            if launch_href:
                supported.append(_risk_text(language, "ML Forecast validation", "ML Forecast 검증"))
                evidence_refs.append("ml_validation_tests")
            if request.mode == "portfolio":
                supported.append(_risk_text(language, "AI Portfolio overlay", "AI Portfolio 오버레이"))
            decision_note = _risk_text(
                language,
                f"{ticker} has full company-scope Risk compatibility for this run.",
                f"{ticker}는 이번 실행에서 기업 범위 Risk 호환성이 확보되었습니다.",
            )
            next_step = _risk_text(
                language,
                "Start with the linked Forecast validation or Quantamental drilldown before sharing the run.",
                "실행을 공유하기 전에 연결된 Forecast 검증 또는 Quantamental 드릴다운부터 확인하세요.",
            )
        else:
            status = "review"
            blocked = [_risk_text(language, "Workflow compatibility unknown", "워크플로우 호환성 확인 불가")]
            decision_note = _risk_text(
                language,
                f"{ticker} compatibility is unknown for this run.",
                f"{ticker}의 이번 실행 호환성을 확인할 수 없습니다.",
            )
            next_step = _risk_text(
                language,
                "Rerun after data refresh and inspect the evidence drawer.",
                "데이터 갱신 후 재실행하고 근거 드로어를 확인하세요.",
            )

        rows.append(
            RiskCompatibilityRow(
                subject=ticker,
                coverage_scope=coverage_scope,  # type: ignore[arg-type]
                status=status,  # type: ignore[arg-type]
                supported_workflows=list(dict.fromkeys(supported))[:7],
                blocked_workflows=list(dict.fromkeys(blocked))[:7],
                forecast_launch_href=launch_href,
                decision_note=decision_note,
                next_step=next_step,
                evidence_refs=list(dict.fromkeys(evidence_refs))[:8],
            )
        )

    if not rows:
        return RiskCompatibilityMatrix(
            status="blocked",
            summary=_risk_text(
                language,
                "No compatible Risk subjects were produced.",
                "호환 가능한 Risk 대상이 생성되지 않았습니다.",
            ),
            rows=[],
            service_note=_risk_text(
                language,
                "Repair request inputs before exposing this response through a service workflow.",
                "서비스 워크플로우에 노출하기 전에 요청 입력을 보정하세요.",
            ),
            evidence_refs=["input_receipt", "data_quality"],
        )

    if any(row.status == "blocked" for row in rows):
        status = "blocked"
    elif any(row.status == "review" for row in rows) or release_packet.status != "ready":
        status = "review"
    else:
        status = "ok"

    counts = {
        "ok": sum(1 for row in rows if row.status == "ok"),
        "review": sum(1 for row in rows if row.status == "review"),
        "blocked": sum(1 for row in rows if row.status == "blocked"),
    }
    summary = _risk_text(
        language,
        f"Compatibility: ok={counts['ok']}, review={counts['review']}, blocked={counts['blocked']}.",
        f"호환성: 정상={counts['ok']}, 검토={counts['review']}, 차단={counts['blocked']}.",
    )
    service_note = _risk_text(
        language,
        "Use this matrix as the per-subject gate before routing users to Forecast, Quantamental, AI Portfolio, or external service workflows.",
        "사용자를 Forecast, Quantamental, AI Portfolio, 외부 서비스 워크플로우로 보내기 전에 이 매트릭스를 대상별 게이트로 사용하세요.",
    )
    return RiskCompatibilityMatrix(
        status=status,  # type: ignore[arg-type]
        summary=summary,
        rows=rows,
        service_note=service_note,
        evidence_refs=[
            "input_receipt",
            "evidence_coverage",
            "ml_validation_tests",
            "release_packet",
        ],
    )


def _build_decision_quality(
    *,
    request: RiskWorkbenchRequest,
    confidence: float,
    decision_usable: bool,
    data_quality,
    service_readiness: RiskServiceReadiness,
    release_packet: RiskReleasePacket,
    input_receipt: RiskInputReceipt,
    evidence_coverage: RiskEvidenceCoverage,
    action_checklist: list[RiskActionItem],
    ml_validation_tests: list[RiskMlValidationTest],
) -> RiskDecisionQuality:
    language = _risk_output_language(request)
    score = float(confidence or 0.0)
    basis: list[str] = []
    blockers: list[str] = []
    next_best_actions: list[str] = []
    evidence_refs: list[str] = ["data_quality", "service_readiness", "release_packet"]

    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    warning_count = len(getattr(data_quality, "provider_warnings", []) or [])
    if missing_count:
        score -= min(20.0, missing_count * 4.0)
        basis.append(
            _risk_text(
                language,
                f"{missing_count} required input group(s) are missing.",
                f"필수 입력 그룹 {missing_count}개가 누락되었습니다.",
            )
        )
        evidence_refs.append("data_quality.missing_inputs")
    if stale_count:
        score -= min(12.0, stale_count * 3.0)
        basis.append(
            _risk_text(
                language,
                f"{stale_count} input group(s) are stale.",
                f"입력 그룹 {stale_count}개가 오래되었습니다.",
            )
        )
        evidence_refs.append("data_quality.stale_inputs")
    if warning_count:
        score -= min(8.0, warning_count * 2.0)
        basis.append(
            _risk_text(
                language,
                f"{warning_count} provider warning(s) remain visible.",
                f"공급자 경고 {warning_count}개가 남아 있습니다.",
            )
        )
        evidence_refs.append("data_quality.provider_warnings")

    if not decision_usable:
        score = min(score, 25.0)
        blockers.append(
            _risk_text(
                language,
                "Risk data gate blocks decision use.",
                "Risk 데이터 게이트가 의사결정 사용을 차단합니다.",
            )
        )
        evidence_refs.append("decision_usable")
    else:
        basis.append(
            _risk_text(
                language,
                "Risk data gate allows advisory decision support.",
                "Risk 데이터 게이트가 분석 지원 사용을 허용합니다.",
            )
        )

    service_status = str(getattr(service_readiness, "status", "review_required") or "review_required")
    if service_status == "blocked":
        score -= 30.0
        blockers.extend(list(getattr(service_readiness, "blockers", []) or [])[:3])
    elif service_status == "review_required":
        score -= 10.0
        basis.append(
            _risk_text(
                language,
                "Service-readiness gate still requires operator review.",
                "서비스 준비도 게이트는 운영자 검토가 필요합니다.",
            )
        )
    else:
        basis.append(_risk_text(language, "Service-readiness gate is ready.", "서비스 준비도 게이트가 준비되었습니다."))

    release_status = str(getattr(release_packet, "status", "review_required") or "review_required")
    if release_status == "blocked":
        score -= 20.0
    elif release_status == "review_required":
        score -= 5.0
        basis.append(
            _risk_text(
                language,
                "Public release packet is not fully ready without external controls.",
                "외부 통제가 없으면 공개 배포 패킷은 완전 준비 상태가 아닙니다.",
            )
        )
    else:
        basis.append(_risk_text(language, "Release packet is ready for service wrapping.", "배포 패킷이 서비스 래핑에 준비되었습니다."))

    input_status = str(getattr(input_receipt, "status", "review") or "review")
    if input_status == "blocked":
        score -= 15.0
        blockers.extend(list(getattr(input_receipt, "compatibility_notes", []) or [])[:3])
    elif input_status == "review":
        score -= 4.0
        basis.append(
            _risk_text(
                language,
                "Input receipt has compatibility notes to review.",
                "입력 확인서에 검토할 호환성 메모가 있습니다.",
            )
        )
    else:
        basis.append(_risk_text(language, "Input receipt is normalized and replayable.", "입력 확인서가 정규화되어 재현 가능합니다."))

    coverage_status = str(getattr(evidence_coverage, "status", "review") or "review")
    if coverage_status == "blocked":
        score -= 18.0
        blockers.append(
            _risk_text(
                language,
                "Evidence coverage has a blocked domain.",
                "근거 커버리지에 차단된 영역이 있습니다.",
            )
        )
    elif coverage_status == "review":
        score -= 6.0
        coverage_score = round(float(getattr(evidence_coverage, "score", 0.0) or 0.0), 1)
        basis.append(
            _risk_text(
                language,
                f"Evidence coverage score is {coverage_score} with review domains.",
                f"근거 커버리지 점수는 {coverage_score}이며 검토 영역이 있습니다.",
            )
        )
    else:
        basis.append(
            _risk_text(
                language,
                "Evidence coverage is complete enough for advisory review.",
                "근거 커버리지가 분석 검토에 충분합니다.",
            )
        )
    evidence_refs.append("evidence_coverage")

    launchable_ml_tests = [item for item in ml_validation_tests if item.launch_href]
    if launchable_ml_tests:
        basis.append(
            _risk_text(
                language,
                f"{len(launchable_ml_tests)} ML Forecast validation launch link(s) are available.",
                f"ML Forecast 검증 실행 링크 {len(launchable_ml_tests)}개를 사용할 수 있습니다.",
            )
        )
        evidence_refs.append("ml_validation_tests")
    elif decision_usable:
        score -= 8.0
        basis.append(
            _risk_text(
                language,
                "No actionable ML Forecast validation launch is available.",
                "실행 가능한 ML Forecast 검증 링크가 없습니다.",
            )
        )

    review_actions = [item for item in action_checklist if item.status in {"review", "blocked"}]
    score -= min(10.0, len(review_actions) * 2.0)
    for item in review_actions[:4]:
        if item.status == "blocked":
            blockers.append(item.rationale or item.label or item.action_id)
        action_text = item.next_step or item.label or item.action_id
        if action_text:
            next_best_actions.append(action_text)
        evidence_refs.extend(item.evidence_refs)
    release_checks = list(getattr(release_packet, "deployment_checks", []) or [])
    release_checks = [item for item in release_checks if item.status in {"review", "blocked"}] + [
        item for item in release_checks if item.status not in {"review", "blocked"}
    ]
    for check in release_checks[:5]:
        if check.status in {"review", "blocked"} and check.next_step:
            next_best_actions.append(check.next_step)
            evidence_refs.extend(check.evidence_refs)
    if launchable_ml_tests:
        first_ml = launchable_ml_tests[0]
        next_best_actions.append(first_ml.setup_notes or first_ml.label or first_ml.test_id)

    score = round(max(0.0, min(100.0, score)), 2)
    if (
        not decision_usable
        or service_status == "blocked"
        or release_status == "blocked"
        or input_status == "blocked"
    ):
        status = "blocked"
        label = _risk_text(language, "Blocked by data or service gate", "데이터 또는 서비스 게이트로 차단")
    elif (
        score < 75.0
        or service_status != "ready"
        or release_status != "ready"
        or input_status != "ok"
        or review_actions
    ):
        status = "review"
        label = _risk_text(language, "Usable with review gates", "검토 게이트가 있는 사용 가능 상태")
    else:
        status = "ok"
        label = _risk_text(language, "Ready for advisory workflow", "분석 지원 워크플로우 준비")

    if not basis:
        basis.append(_risk_text(language, "No additional quality deductions detected.", "추가 품질 차감이 감지되지 않았습니다."))
    if not next_best_actions:
        next_best_actions.append(
            _risk_text(
                language,
                "Retain run lineage and rerun after any data refresh.",
                "실행 감사를 보존하고 데이터 갱신 후 다시 실행하세요.",
            )
        )

    return RiskDecisionQuality(
        status=status,
        score=score,
        label=label,
        basis=list(dict.fromkeys(basis))[:6],
        blockers=list(dict.fromkeys([item for item in blockers if item]))[:5],
        next_best_actions=list(dict.fromkeys([item for item in next_best_actions if item]))[:6],
        evidence_refs=list(dict.fromkeys([item for item in evidence_refs if item]))[:10],
    )


def _build_decision_compass(
    *,
    request: RiskWorkbenchRequest,
    risk_index: float | None,
    confidence: float,
    decision_usable: bool,
    decision_path: RiskDecisionPath,
    decision_quality: RiskDecisionQuality,
    evidence_coverage: RiskEvidenceCoverage,
    ai_output_controls: RiskAiOutputControls,
    release_packet: RiskReleasePacket,
    input_receipt: RiskInputReceipt,
    priority_map: list[RiskPriorityCell],
    handoff_queue: list[RiskHandoffItem],
    ml_validation_tests: list[RiskMlValidationTest],
) -> RiskDecisionCompass:
    language = _risk_output_language(request)

    def normalize_status(value: str | None) -> str:
        raw = str(value or "review")
        if raw in {"blocked", "fail"}:
            return "blocked"
        if raw in {"ok", "ready"}:
            return "ok"
        return "review"

    quality_status = normalize_status(decision_quality.status)
    coverage_status = normalize_status(evidence_coverage.status)
    ai_status = normalize_status(ai_output_controls.status)
    release_status = normalize_status(release_packet.status)
    receipt_status = normalize_status(input_receipt.status)

    if not decision_usable or "blocked" in {quality_status, coverage_status, ai_status, release_status, receipt_status}:
        status = "blocked"
    elif "review" in {quality_status, coverage_status, ai_status, release_status, receipt_status}:
        status = "review"
    else:
        status = "ok"

    top_cell = priority_map[0] if priority_map else None
    review_position = next(
        (
            position
            for position in input_receipt.normalized_positions
            if position.coverage_scope in {"asset_proxy", "blocked"} or not position.decision_usable
        ),
        None,
    )
    if review_position is not None:
        primary_focus = f"{review_position.ticker} / {review_position.coverage_scope} / {input_receipt.status}"
    elif top_cell is not None:
        primary_focus = f"{top_cell.subject} / {top_cell.vector} / {risk_score_text(top_cell.score)}"
    else:
        primary_focus = _risk_text(language, "No priority risk cell is available.", "우선순위 리스크 셀이 없습니다.")
    launchable_ml = next((item for item in ml_validation_tests if getattr(item, "launch_href", None)), None)
    next_handoff = next((item for item in handoff_queue if item.status != "blocked"), None)
    if next_handoff is None and handoff_queue:
        next_handoff = handoff_queue[0]

    quality_instruction = (
        (decision_quality.blockers or decision_quality.next_best_actions or decision_quality.basis or [])[:1]
        or [_risk_text(language, "Read the quality score before interpreting risk drivers.", "리스크 동인을 해석하기 전에 결정 품질 점수를 먼저 확인하세요.")]
    )[0]
    coverage_instruction = _risk_text(
        language,
        "Review blocked or review domains before sharing the run.",
        "공유 전에 blocked 또는 review 근거 도메인을 확인하세요.",
    )
    if coverage_status == "ok":
        coverage_instruction = _risk_text(
            language,
            "Coverage is usable; keep evidence refs with the saved run.",
            "근거 커버리지는 사용 가능하며 저장 시 근거 참조를 함께 보관하세요.",
        )
    ml_instruction = _risk_text(
        language,
        "Open the linked Forecast validation experiment before treating the run as model-supported.",
        "이 실행을 모델 검증 기반으로 다루기 전에 연결된 Forecast 검증 실험을 여세요.",
    ) if launchable_ml else _risk_text(
        language,
        "ML Forecast validation is blocked until data-quality gates are repaired.",
        "데이터 품질 게이트가 복구될 때까지 ML Forecast 검증은 차단됩니다.",
    )
    ai_instruction = (
        ai_output_controls.review_instructions[:1]
        or [_risk_text(language, "Use only grounded AI narrative claims.", "근거가 있는 AI 서술만 사용하세요.")]
    )[0]
    service_instruction = _risk_text(
        language,
        "Keep external deployment in review until auth, rate limits, retention, and monitoring are defined.",
        "인증, rate limit, 보존 정책, 모니터링이 정의될 때까지 외부 배포는 검토 상태로 두세요.",
    )
    if release_status == "blocked":
        service_instruction = _risk_text(
            language,
            "Do not expose this run through service workflows until blocked checks are fixed.",
            "차단된 체크가 해결될 때까지 이 실행을 서비스 워크플로우에 노출하지 마세요.",
        )

    if status == "blocked":
        headline = _risk_text(
            language,
            "Stop at data repair before interpreting the Risk run.",
            "Risk 실행 해석 전에 데이터 복구부터 진행하세요.",
        )
        next_step = (decision_quality.blockers or [quality_instruction])[0]
    elif launchable_ml is not None:
        headline = _risk_text(
            language,
            f"Use the Risk run as a review workflow, then validate {launchable_ml.label}.",
            f"Risk 실행은 검토 워크플로우로 사용하고 {launchable_ml.label}을 검증하세요.",
        )
        next_step = _risk_text(
            language,
            "Run the linked ML Forecast validation test and compare it with the Risk input hash.",
            "연결된 ML Forecast 검증 테스트를 실행하고 Risk input hash와 대조하세요.",
        )
    else:
        headline = _risk_text(
            language,
            "Risk run is usable for review; keep evidence and service gates attached.",
            "Risk 실행은 검토에 사용할 수 있으며 근거와 서비스 게이트를 함께 유지하세요.",
        )
        next_step = (decision_quality.next_best_actions or [service_instruction])[0]

    service_hint = _risk_text(
        language,
        f"decision={status}; risk_index={risk_score_text(risk_index)}; confidence={risk_score_text(confidence)}%; release={release_packet.status}",
        f"결정={status}; 리스크={risk_score_text(risk_index)}; 신뢰도={risk_score_text(confidence)}%; 배포={release_packet.status}",
    )

    steps = [
        RiskDecisionCompassStep(
            step_id="verify_input_and_quality",
            label=_risk_text(language, "Verify input and decision quality", "입력과 결정 품질 확인"),
            status=quality_status,  # type: ignore[arg-type]
            instruction=str(quality_instruction),
            target="decision_quality",
            href="/ui/#risk",
            evidence_refs=["input_receipt", "decision_quality"],
        ),
        RiskDecisionCompassStep(
            step_id="review_evidence_coverage",
            label=_risk_text(language, "Review evidence coverage", "근거 커버리지 검토"),
            status=coverage_status,  # type: ignore[arg-type]
            instruction=coverage_instruction,
            target="evidence_coverage",
            href="/ui/#risk",
            evidence_refs=["evidence_coverage", "data_quality"],
        ),
        RiskDecisionCompassStep(
            step_id="run_forecast_validation",
            label=_risk_text(language, "Run Forecast validation", "Forecast 검증 실행"),
            status=("review" if launchable_ml else ("blocked" if status == "blocked" else "review")),
            instruction=ml_instruction,
            target="ml_forecast",
            href=getattr(launchable_ml, "launch_href", None) if launchable_ml else None,
            evidence_refs=["ml_validation_tests", "source_context"],
        ),
        RiskDecisionCompassStep(
            step_id="control_ai_output",
            label=_risk_text(language, "Control AI narrative output", "AI 서술 출력 통제"),
            status=ai_status,  # type: ignore[arg-type]
            instruction=str(ai_instruction),
            target="ai_output_controls",
            href="/ui/#risk",
            evidence_refs=["ai_output_controls", "decision_quality", "evidence_coverage"],
        ),
        RiskDecisionCompassStep(
            step_id="review_service_gate",
            label=_risk_text(language, "Review service gate", "서비스 게이트 검토"),
            status=release_status,  # type: ignore[arg-type]
            instruction=service_instruction,
            target=getattr(next_handoff, "target_tab", "risk") if next_handoff else "risk",
            href=getattr(next_handoff, "href", "/ui/#risk") if next_handoff else "/ui/#risk",
            evidence_refs=["release_packet", "service_readiness", "run_lineage"],
        ),
    ]

    return RiskDecisionCompass(
        status=status,  # type: ignore[arg-type]
        headline=headline,
        primary_focus=primary_focus,
        next_step=str(next_step),
        service_hint=service_hint,
        steps=steps,
        evidence_refs=list(
            dict.fromkeys(
                [
                    "input_receipt",
                    "decision_quality",
                    "evidence_coverage",
                    "compatibility_matrix",
                    "ai_output_controls",
                    "ml_validation_tests",
                    "release_packet",
                    "run_lineage",
                    *(getattr(top_cell, "evidence_refs", []) or []),
                ]
            )
        )[:12],
    )


def _build_ai_output_controls(
    *,
    request: RiskWorkbenchRequest,
    risk_run_id: str,
    input_hash: str,
    risk_index: float | None,
    confidence: float,
    decision_usable: bool,
    decision_quality: RiskDecisionQuality,
    evidence_coverage: RiskEvidenceCoverage,
    release_packet: RiskReleasePacket,
    compatibility_matrix: RiskCompatibilityMatrix,
    data_quality,
    priority_map: list[RiskPriorityCell],
    ml_validation_tests: list[RiskMlValidationTest],
    run_lineage: RiskRunLineage,
) -> RiskAiOutputControls:
    language = _risk_output_language(request)
    quality_status = str(getattr(decision_quality, "status", "review") or "review")
    coverage_status = str(getattr(evidence_coverage, "status", "review") or "review")
    release_status = str(getattr(release_packet, "status", "review_required") or "review_required")
    compatibility_status = str(getattr(compatibility_matrix, "status", "review") or "review")
    missing_count = len(getattr(data_quality, "missing_inputs", []) or [])
    stale_count = len(getattr(data_quality, "stale_inputs", []) or [])
    provider_warning_count = len(getattr(data_quality, "provider_warnings", []) or [])
    launchable_ml_count = sum(1 for item in ml_validation_tests if getattr(item, "launch_href", None))

    if (
        not decision_usable
        or quality_status == "blocked"
        or coverage_status == "blocked"
        or release_status == "blocked"
        or compatibility_status == "blocked"
    ):
        status = "blocked"
    elif (
        quality_status == "review"
        or coverage_status == "review"
        or release_status == "review_required"
        or compatibility_status == "review"
        or missing_count
        or stale_count
        or provider_warning_count
    ):
        status = "review"
    else:
        status = "ok"

    subjects = ", ".join(run_lineage.subjects or request.tickers) or _risk_text(language, "current request", "현재 요청")
    top_cell = priority_map[0] if priority_map else None
    top_focus = (
        f"{top_cell.subject}/{top_cell.vector}:{risk_score_text(top_cell.score)}"
        if top_cell is not None
        else _risk_text(language, "no priority cell", "우선순위 셀 없음")
    )
    required_refs = [
        "risk_run_id",
        "input_hash",
        "decision_quality",
        "evidence_coverage",
        "compatibility_matrix",
        "data_quality",
        "release_packet",
        "run_lineage",
    ]
    if top_cell is not None:
        required_refs.extend(top_cell.evidence_refs or ["priority_map"])
    if launchable_ml_count:
        required_refs.append("ml_validation_tests")
    if missing_count:
        required_refs.append("data_quality.missing_inputs")
    if stale_count:
        required_refs.append("data_quality.stale_inputs")

    grounding_summary = _risk_text(
        language,
        (
            f"Ground model-written Risk narratives on run {risk_run_id}, input hash {input_hash}, "
            f"subjects {subjects}, risk index {risk_score_text(risk_index)}, confidence {risk_score_text(confidence)}%, "
            f"decision quality {quality_status}, evidence coverage {coverage_status}, compatibility {compatibility_status}, "
            f"and top focus {top_focus}."
        ),
        (
            f"모델이 작성하는 Risk 설명은 실행 {risk_run_id}, 입력 해시 {input_hash}, "
            f"대상 {subjects}, 리스크 지수 {risk_score_text(risk_index)}, 신뢰도 {risk_score_text(confidence)}%, "
            f"결정 품질 {quality_status}, 근거 커버리지 {coverage_status}, 호환성 {compatibility_status}, "
            f"우선 검토 {top_focus}에 근거해야 합니다."
        ),
    )

    return RiskAiOutputControls(
        status=status,
        language=language,  # type: ignore[arg-type]
        grounding_summary=grounding_summary,
        required_evidence_refs=list(dict.fromkeys(required_refs))[:12],
        allowed_claims=[
            _risk_text(
                language,
                "Explain risk_index, confidence, decision_quality, evidence_coverage, and service gate status exactly as returned.",
                "반환된 risk_index, confidence, decision_quality, evidence_coverage, service gate 상태만 정확히 설명하세요.",
            ),
            _risk_text(
                language,
                "Summarize top drivers, scenario stress rows, data-quality gates, and ML Forecast validation tests with their evidence refs.",
                "상위 동인, 시나리오 스트레스 행, 데이터 품질 게이트, ML Forecast 검증 테스트를 근거 참조와 함께 요약하세요.",
            ),
            _risk_text(
                language,
                "Describe next verification workflow steps without changing Risk or Forecast score math.",
                "Risk 또는 Forecast 점수 계산을 바꾸지 않고 다음 검증 워크플로우만 설명하세요.",
            ),
        ],
        blocked_claims=[
            _risk_text(
                language,
                "Do not invent missing metrics, provider freshness, SEC findings, model accuracy, or production controls.",
                "누락 지표, 공급자 최신성, SEC 근거, 모델 정확도, 운영 통제를 만들어내지 마세요.",
            ),
            _risk_text(
                language,
                "Do not issue trade action instructions, price targets, or portfolio rebalance orders.",
                "거래 행동 지시, 목표가, 포트폴리오 리밸런싱 명령을 내리지 마세요.",
            ),
            _risk_text(
                language,
                "Do not describe asset-proxy coverage as full company-fundamental coverage.",
                "자산 프록시 커버리지를 기업 재무 전체 커버리지처럼 설명하지 마세요.",
            ),
            _risk_text(
                language,
                "Do not claim service deployment is ready when release_packet.status is not ready.",
                "release_packet.status가 ready가 아니면 서비스 배포 준비 완료라고 말하지 마세요.",
            ),
        ],
        citation_policy=[
            _risk_text(
                language,
                "Cite risk_run_id and input_hash in saved or shared model output.",
                "저장 또는 공유되는 모델 출력에는 risk_run_id와 input_hash를 포함하세요.",
            ),
            _risk_text(
                language,
                "Every material claim must map to one of required_evidence_refs.",
                "중요한 주장은 required_evidence_refs 중 하나에 연결되어야 합니다.",
            ),
            _risk_text(
                language,
                "If a referenced domain is review or blocked, name that limit in the first paragraph.",
                "참조 영역이 review 또는 blocked이면 첫 문단에서 그 한계를 명시하세요.",
            ),
        ],
        review_instructions=[
            _risk_text(
                language,
                "Open with decision_quality.status and score before narrative interpretation.",
                "서술형 해석 전에 decision_quality.status와 score를 먼저 제시하세요.",
            ),
            _risk_text(
                language,
                "Use the requested output language and keep advisory-only wording.",
                "요청된 출력 언어를 사용하고 분석 지원 전용 표현을 유지하세요.",
            ),
            _risk_text(
                language,
                "When ML validation links exist, present them as experiments to run, not confirmed forecasts.",
                "ML 검증 링크가 있으면 확정 예측이 아니라 실행할 실험으로 제시하세요.",
            ),
        ],
        prompt_context=[
            f"risk_run_id={risk_run_id}",
            f"input_hash={input_hash}",
            f"mode={request.mode}",
            f"subjects={subjects}",
            f"decision_usable={decision_usable}",
            f"decision_quality={quality_status}:{risk_score_text(decision_quality.score)}",
            f"evidence_coverage={coverage_status}:{risk_score_text(evidence_coverage.score)}",
            f"compatibility_matrix={compatibility_status}:{len(getattr(compatibility_matrix, 'rows', []) or [])}",
            f"release_packet={release_status}",
            f"missing_inputs={missing_count}",
            f"stale_inputs={stale_count}",
            f"provider_warnings={provider_warning_count}",
            f"ml_validation_launches={launchable_ml_count}",
        ],
    )


def build_risk_workbench_response(
    *,
    request: RiskWorkbenchRequest,
    company_payloads: dict[str, dict[str, Any]],
    macro_payload: dict[str, Any] | None,
) -> RiskWorkbenchResponse:
    input_hash = stable_input_hash(request.model_dump(mode="json"))
    data_quality = evaluate_risk_data_quality(company_payloads, macro_payload, include_sec=request.include_sec)
    company_profiles = [
        build_company_profile(ticker, company_payloads.get(ticker))
        for ticker in request.tickers
    ]
    macro_backdrop = build_macro_backdrop(macro_payload)
    transmission_channels = build_transmission_channels(company_profiles, macro_backdrop)
    weights_by_ticker = _positions_by_ticker(request)

    company_score = _weighted_profile_score(company_profiles, weights_by_ticker)
    market_score = _weighted_profile_score(company_profiles, weights_by_ticker, "market_behavior")
    macro_score = average_score([
        _macro_vector_score(macro_backdrop, "macro_policy_rates"),
        _macro_vector_score(macro_backdrop, "macro_growth_inflation"),
    ])
    credit_score = _macro_vector_score(macro_backdrop, "credit_liquidity")
    transmission_score = average_score([channel.risk_delta * 2.0 for channel in transmission_channels])
    concentration = concentration_penalty([position.weight for position in request.positions or []])

    component_scores = {
        "company_fundamental_vulnerability": company_score,
        "market_behavior_risk": market_score,
        "macro_regime_risk": macro_score,
        "credit_liquidity_risk": credit_score,
        "transmission_sensitivity": transmission_score,
        "data_quality_penalty": data_quality.penalty,
    }
    weights = BASE_RISK_WEIGHTS
    if request.mode == "portfolio":
        component_scores = {
            "weighted_company_risk": company_score,
            "weighted_market_behavior_risk": market_score,
            "macro_regime_risk": macro_score,
            "credit_liquidity_risk": credit_score,
            "weighted_transmission_sensitivity": transmission_score,
            "concentration_penalty": concentration,
            "data_quality_penalty": data_quality.penalty,
        }
        weights = PORTFOLIO_RISK_WEIGHTS

    risk_index = weighted_score(component_scores, weights)
    if not any(profile.decision_usable for profile in company_profiles):
        risk_index = None
    scenario_matrix = build_scenario_matrix(
        risk_index,
        transmission_channels,
        scenario_set=request.scenario_set,
    ) if request.include_macro_scenarios else []
    evidence = [
        item
        for ticker in request.tickers
        for item in company_evidence(ticker, company_payloads.get(ticker))
    ]
    evidence.extend(macro_evidence(macro_payload))
    flat_drivers: list[str] = []
    for profile in company_profiles:
        flat_drivers.extend(profile.primary_drivers)
    flat_drivers.extend(macro_backdrop.primary_pressures[:3])
    if data_quality.missing_inputs:
        flat_drivers.append("data quality blocks decision use")

    confidence = max(
        0.0,
        min(
            100.0,
            average_score([profile.confidence for profile in company_profiles] + [macro_backdrop.confidence]) or 0.0,
        ) - data_quality.confidence_penalty * 0.35,
    )
    decision_usable = bool(data_quality.decision_usable and risk_index is not None and confidence >= 35.0)
    level = risk_level(risk_index)
    contribution_rows = driver_contributions(component_scores, weights)
    service_readiness = _build_clean_service_readiness(
        request=request,
        risk_index=risk_index,
        confidence=confidence,
        decision_usable=decision_usable,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
    )
    confidence_factors = _build_confidence_factors(
        request=request,
        confidence=confidence,
        decision_usable=decision_usable,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        scenario_matrix=scenario_matrix,
        service_readiness=service_readiness,
    )
    action_checklist = _build_clean_action_checklist(
        request=request,
        risk_index=risk_index,
        confidence=confidence,
        decision_usable=decision_usable,
        data_quality=data_quality,
        driver_rows=contribution_rows,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
        service_readiness=service_readiness,
        company_profiles=company_profiles,
    )
    monitoring_triggers = _build_clean_monitoring_triggers(
        request=request,
        risk_index=risk_index,
        confidence=confidence,
        decision_usable=decision_usable,
        data_quality=data_quality,
        driver_rows=contribution_rows,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
        service_readiness=service_readiness,
        company_profiles=company_profiles,
    )
    priority_map = _build_priority_map(
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        data_quality=data_quality,
    )
    run_lineage = _build_run_lineage(
        request=request,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        scenario_matrix=scenario_matrix,
        evidence=evidence,
        data_quality=data_quality,
        service_readiness=service_readiness,
    )
    input_receipt = _build_input_receipt(
        request=request,
        data_quality=data_quality,
        company_profiles=company_profiles,
    )
    handoff_queue = _build_handoff_queue(
        request=request,
        risk_index=risk_index,
        decision_usable=decision_usable,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
        priority_map=priority_map,
        service_readiness=service_readiness,
    )
    ml_validation_tests = _build_ml_validation_tests(
        request=request,
        input_hash=input_hash,
        risk_index=risk_index,
        decision_usable=decision_usable,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
    )
    forecast_validation_plan = _build_forecast_validation_plan(
        request=request,
        input_hash=input_hash,
        decision_usable=decision_usable,
        data_quality=data_quality,
        ml_validation_tests=ml_validation_tests,
    )
    decision_path = _build_decision_path(
        request=request,
        risk_index=risk_index,
        decision_usable=decision_usable,
        priority_map=priority_map,
        action_checklist=action_checklist,
        handoff_queue=handoff_queue,
        ml_validation_tests=ml_validation_tests,
        service_readiness=service_readiness,
    )
    release_packet = _build_release_packet(
        request=request,
        input_hash=input_hash,
        decision_usable=decision_usable,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        service_readiness=service_readiness,
        run_lineage=run_lineage,
        ml_validation_tests=ml_validation_tests,
    )
    evidence_coverage = _build_evidence_coverage(
        request=request,
        decision_usable=decision_usable,
        evidence=evidence,
        data_quality=data_quality,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        scenario_matrix=scenario_matrix,
        service_readiness=service_readiness,
        input_receipt=input_receipt,
        release_packet=release_packet,
        ml_validation_tests=ml_validation_tests,
    )
    compatibility_matrix = _build_compatibility_matrix(
        request=request,
        decision_usable=decision_usable,
        company_profiles=company_profiles,
        input_receipt=input_receipt,
        evidence_coverage=evidence_coverage,
        ml_validation_tests=ml_validation_tests,
        release_packet=release_packet,
    )
    decision_quality = _build_decision_quality(
        request=request,
        confidence=confidence,
        decision_usable=decision_usable,
        data_quality=data_quality,
        service_readiness=service_readiness,
        release_packet=release_packet,
        input_receipt=input_receipt,
        evidence_coverage=evidence_coverage,
        action_checklist=action_checklist,
        ml_validation_tests=ml_validation_tests,
    )
    risk_run_id = f"risk-{uuid4().hex[:12]}"
    ai_output_controls = _build_ai_output_controls(
        request=request,
        risk_run_id=risk_run_id,
        input_hash=input_hash,
        risk_index=risk_index,
        confidence=confidence,
        decision_usable=decision_usable,
        decision_quality=decision_quality,
        evidence_coverage=evidence_coverage,
        release_packet=release_packet,
        compatibility_matrix=compatibility_matrix,
        data_quality=data_quality,
        priority_map=priority_map,
        ml_validation_tests=ml_validation_tests,
        run_lineage=run_lineage,
    )
    decision_compass = _build_decision_compass(
        request=request,
        risk_index=risk_index,
        confidence=confidence,
        decision_usable=decision_usable,
        decision_path=decision_path,
        decision_quality=decision_quality,
        evidence_coverage=evidence_coverage,
        ai_output_controls=ai_output_controls,
        release_packet=release_packet,
        input_receipt=input_receipt,
        priority_map=priority_map,
        handoff_queue=handoff_queue,
        ml_validation_tests=ml_validation_tests,
    )
    return RiskWorkbenchResponse(
        risk_run_id=risk_run_id,
        input_hash=input_hash,
        mode=request.mode,
        risk_index=risk_index,
        risk_level=level,
        confidence=round(confidence, 2),
        decision_usable=decision_usable,
        as_of=datetime.now(timezone.utc),
        primary_drivers=list(dict.fromkeys(flat_drivers))[:6],
        driver_contributions=contribution_rows,
        risk_vectors=[vector for profile in company_profiles for vector in profile.vectors] + macro_backdrop.vectors,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
        portfolio_overlay=_portfolio_overlay(request, company_profiles, scenario_matrix),
        evidence=evidence,
        data_quality=data_quality,
        input_receipt=input_receipt,
        calculation_policy=RiskCalculationPolicy(
            weights=weights,
            notes=[
                "Higher risk_index is riskier.",
                "Quantamental scores with safer-is-higher direction are inverted at the adapter boundary.",
                "Risk output is advisory decision support, not a buy/sell/hold recommendation.",
            ],
        ),
        decision_brief=_build_clean_decision_brief(
            request=request,
            risk_index=risk_index,
            risk_level_value=level,
            decision_usable=decision_usable,
            data_quality=data_quality,
            driver_rows=contribution_rows,
            transmission_channels=transmission_channels,
            scenario_matrix=scenario_matrix,
        ),
        decision_path=decision_path,
        decision_quality=decision_quality,
        decision_compass=decision_compass,
        evidence_coverage=evidence_coverage,
        compatibility_matrix=compatibility_matrix,
        action_checklist=action_checklist,
        monitoring_triggers=monitoring_triggers,
        priority_map=priority_map,
        confidence_factors=confidence_factors,
        handoff_queue=handoff_queue,
        ml_validation_tests=ml_validation_tests,
        forecast_validation_plan=forecast_validation_plan,
        service_readiness=service_readiness,
        run_lineage=run_lineage,
        release_packet=release_packet,
        ai_output_controls=ai_output_controls,
    )
