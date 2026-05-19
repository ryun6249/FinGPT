from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from core.schemas.quantamental import (
    QuantamentalAIReportRequest,
    QuantamentalAnalysisRequest,
    QuantamentalCompareRequest,
    QuantamentalQARequest,
    QuantamentalScoreScreenRequest,
    QuantamentalScreenRequest,
)
from pipelines.quantamental.ai_service import build_context, generate_report
from pipelines.quantamental.cache import quantamental_cache
from pipelines.quantamental.factor_engine import calculate_factors
from pipelines.quantamental.global_market import resolve_global_symbol
from pipelines.quantamental.fundamental_engine import calculate_fundamentals
from pipelines.quantamental.hybrid_score_engine import STYLE_WEIGHTS, calculate_composite
from pipelines.quantamental.providers import (
    UnsupportedMarketError,
    normalize_market,
    now_iso,
    provider_for_market,
    validate_ticker,
)
from pipelines.quantamental.peer_engine import apply_peer_relative_scores, expand_peer_universe
from pipelines.quantamental.qa_service import answer_question
from pipelines.quantamental.quant_engine import calculate_quant
from pipelines.quantamental.risk_engine import calculate_risk
from pipelines.quantamental.sec_evidence import apply_sec_evidence_to_risk, build_sec_evidence
from pipelines.quantamental.sec_hydration import hydrate_global_sec_aliases
from pipelines.quantamental.signal_engine import classify_signal
from pipelines.quantamental.snapshot_store import get_snapshot, list_snapshots, save_snapshot


DEFAULT_CACHE_TTL_S = 900
SCREEN_CACHE_TTL_S = 300
PRICE_FRESH_MAX_AGE_DAYS = 5
COMPANY_FETCH_MAX_AGE_DAYS = 1
ANNUAL_FUNDAMENTAL_MAX_AGE_DAYS = 455
QUARTERLY_FUNDAMENTAL_MAX_AGE_DAYS = 160
SEC_FILING_MAX_AGE_DAYS = 455
SCREEN_TOP_LIMIT = 5
DEFAULT_SCREEN_CANDIDATE_LIMIT = 6
FRESHNESS_RETRYABLE_STATUSES = {"stale", "missing", "failed", "unknown"}
STRICT_SIGNAL_FRESHNESS_SECTIONS = ("company", "fundamentals", "prices")
DEFAULT_SCREENING_UNIVERSES = {
    "default_us_large_cap": [
        "AAPL",
        "MSFT",
        "NVDA",
        "GOOGL",
        "AMZN",
        "META",
        "AVGO",
        "TSLA",
        "LLY",
        "JPM",
        "V",
        "MA",
        "UNH",
        "COST",
        "HD",
        "PG",
        "NFLX",
        "AMD",
        "CRM",
        "ORCL",
        "ADBE",
        "NOW",
        "INTC",
        "QCOM",
        "TXN",
        "INTU",
        "IBM",
        "PLTR",
        "PANW",
        "UBER",
        "GE",
        "XOM",
        "CVX",
        "COP",
        "WMT",
        "MCD",
        "KO",
        "PEP",
        "NKE",
        "DIS",
        "BAC",
        "WFC",
        "GS",
        "MS",
        "AXP",
        "JNJ",
        "MRK",
        "ABBV",
        "PFE",
        "TMO",
        "LIN",
        "CAT",
        "RTX",
        "LMT",
        "UPS",
        "NEE",
    ],
    "mega_cap_tech": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "AMD", "NFLX"],
}

SCORE_SCREEN_REGISTRY: dict[str, dict[str, str]] = {
    "composite": {"label": "Composite", "row_field": "final_score"},
    "value": {"label": "Value", "row_field": "value_score"},
    "quality": {"label": "Quality", "row_field": "quality_score"},
    "growth": {"label": "Growth", "row_field": "growth_score"},
    "momentum": {"label": "Momentum", "row_field": "momentum_score"},
    "low_volatility": {"label": "Low Volatility", "row_field": "low_volatility_score"},
    "liquidity": {"label": "Liquidity", "row_field": "liquidity_score"},
    "drawdown_resilience": {
        "label": "Drawdown Resilience",
        "row_field": "drawdown_resilience_score",
        "algorithm_key": "drawdown_recovery_resilience",
        "algorithm_score_field": "drawdown_recovery_resilience_score",
    },
    "liquidity_stability": {
        "label": "Liquidity Stability",
        "row_field": "liquidity_stability_score",
        "algorithm_key": "liquidity_participation_stability",
        "algorithm_score_field": "liquidity_participation_stability_score",
    },
    "trend_efficiency": {
        "label": "Trend Efficiency",
        "row_field": "trend_efficiency_score",
        "algorithm_key": "trend_efficiency_stability",
        "algorithm_score_field": "trend_efficiency_stability_score",
    },
    "market_resilience": {
        "label": "Market Resilience",
        "row_field": "market_resilience_score",
        "algorithm_key": "market_relative_resilience",
        "algorithm_score_field": "market_relative_resilience_score",
    },
}


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "engine": "quantamental",
        "supported_markets": ["US", "KR", "GLOBAL"],
        "unsupported_markets": [],
        "styles": sorted(STYLE_WEIGHTS),
        "execution_policy": "deterministic_scores_ai_interpretation_only",
        "not_investment_advice": True,
        "enhancements": [
            "peer_relative_comparison",
            "broader_peer_universe",
            "sec_evidence_overlay",
            "sec_global_adr_fallback",
            "global_symbol_resolver",
            "global_sec_hydration_script",
            "sec_filing_text_excerpt",
            "opendart_kr_provider",
            "global_yfinance_provider",
            "global_peer_universe_fallback",
            "krx_price_fallback",
            "sqlite_snapshots",
            "snapshot_export_diff_retention",
            "batch_compare",
            "comparison_watchlist_csv",
            "server_side_compare_watchlists",
            "freshness_audit_and_stale_refresh_retry",
            "strict_freshness_gate",
            "top_signal_screener",
            "score_threshold_screener",
            "fast_top_signal_screen_cache",
            "axis_annotated_overview_charts",
            "quality_adjusted_momentum_v1",
            "volatility_adjusted_breakout_v1",
            "drawdown_recovery_resilience_v1",
            "liquidity_participation_stability_v1",
            "trend_efficiency_stability_v1",
            "market_relative_resilience_v1",
        ],
        "score_screen_keys": [
            {
                "key": key,
                "label": meta["label"],
                "row_field": meta["row_field"],
                "algorithm_key": meta.get("algorithm_key"),
                "used_in_composite_score": key == "composite",
            }
            for key, meta in SCORE_SCREEN_REGISTRY.items()
        ],
    }


def company(ticker: str, *, market: str = "US", force_refresh: bool = False) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    cached = None if force_refresh else _cache_get("company", clean, market)
    if cached:
        return cached
    try:
        payload = provider_for_market(market).company(clean)
    except UnsupportedMarketError as exc:
        payload = _unsupported_payload("company", clean, market, exc)
    except Exception as exc:  # noqa: BLE001
        payload = _failed_payload("company", clean, market, f"provider_failure:{type(exc).__name__}:{exc}")
    _cache_set("company", clean, market, payload)
    return payload


def fundamentals(
    ticker: str,
    *,
    market: str = "US",
    period: str = "annual",
    years: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    period = "quarterly" if str(period).lower() == "quarterly" else "annual"
    years = max(1, min(int(years or 5), 10))
    cache_key = _key("fundamentals", clean, market, period, years)
    cached = None if force_refresh else quantamental_cache.get(cache_key)
    if cached:
        return cached
    company_payload = company(clean, market=market, force_refresh=force_refresh)
    try:
        raw = provider_for_market(market).fundamentals(clean, period=period, years=years)
        payload = calculate_fundamentals(raw, company_payload.get("company") or {})
        payload["provider_status"] = raw.get("status")
        payload["company_status"] = company_payload.get("status")
    except UnsupportedMarketError as exc:
        payload = _unsupported_payload("fundamentals", clean, market, exc)
    except Exception as exc:  # noqa: BLE001
        payload = _failed_payload("fundamentals", clean, market, f"fundamental_engine_failure:{type(exc).__name__}:{exc}")
    quantamental_cache.set(cache_key, payload, DEFAULT_CACHE_TTL_S)
    return payload


def quant(ticker: str, *, market: str = "US", lookback: int | str = 252, force_refresh: bool = False) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    cache_key = _key("quant", clean, market, lookback)
    cached = None if force_refresh else quantamental_cache.get(cache_key)
    if cached:
        return cached
    try:
        raw = provider_for_market(market).prices(clean, lookback=lookback, benchmark=_benchmark_for_market(market))
        payload = calculate_quant(raw)
        payload["provider_status"] = raw.get("status")
    except UnsupportedMarketError as exc:
        payload = _unsupported_payload("quant", clean, market, exc)
    except Exception as exc:  # noqa: BLE001
        payload = _failed_payload("quant", clean, market, f"quant_engine_failure:{type(exc).__name__}:{exc}")
    quantamental_cache.set(cache_key, payload, DEFAULT_CACHE_TTL_S)
    return payload


def factors(ticker: str, *, market: str = "US", period: str = "annual", years: int = 5, lookback: int | str = 252) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    f_payload = fundamentals(clean, market=market, period=period, years=years)
    q_payload = quant(clean, market=market, lookback=lookback)
    c_payload = company(clean, market=market)
    try:
        payload = calculate_factors(f_payload, q_payload, c_payload.get("company") or {})
        payload.update({"ticker": clean, "market": market})
    except Exception as exc:  # noqa: BLE001
        payload = _failed_payload("factors", clean, market, f"factor_engine_failure:{type(exc).__name__}:{exc}")
    return payload


def risk(
    ticker: str,
    *,
    market: str = "US",
    period: str = "annual",
    years: int = 5,
    lookback: int | str = 252,
) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    f_payload = fundamentals(clean, market=market, period=period, years=years)
    q_payload = quant(clean, market=market, lookback=lookback)
    factor_payload = calculate_factors(f_payload, q_payload, (company(clean, market=market).get("company") or {}))
    quality = data_quality(company(clean, market=market), f_payload, q_payload)
    try:
        payload = calculate_risk(f_payload, q_payload, factor_payload, quality.get("data_quality_score"))
        payload.update({"ticker": clean, "market": market})
    except Exception as exc:  # noqa: BLE001
        payload = _failed_payload("risk", clean, market, f"risk_engine_failure:{type(exc).__name__}:{exc}")
    return payload


def composite(
    ticker: str,
    *,
    market: str = "US",
    period: str = "annual",
    years: int = 5,
    lookback: int | str = 252,
    style: str = "balanced",
) -> dict[str, Any]:
    analysis_payload = analysis(
        QuantamentalAnalysisRequest(
            ticker=ticker,
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            include_ai=False,
            use_llm=False,
        )
    )
    return analysis_payload.get("composite") or {}


def signal(
    ticker: str,
    *,
    market: str = "US",
    period: str = "annual",
    years: int = 5,
    lookback: int | str = 252,
    style: str = "balanced",
) -> dict[str, Any]:
    analysis_payload = analysis(
        QuantamentalAnalysisRequest(
            ticker=ticker,
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            include_ai=False,
            use_llm=False,
        )
    )
    return analysis_payload.get("signal") or {}


def analysis(request: QuantamentalAnalysisRequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalAnalysisRequest) else QuantamentalAnalysisRequest.model_validate(request)
    payload = _build_analysis(req, force_refresh=req.force_refresh)
    freshness = payload.get("freshness") or {}
    refresh_sections = _freshness_refresh_sections(freshness)
    if not req.force_refresh and _freshness_refresh_recommended(freshness) and refresh_sections:
        refreshed = _build_analysis(req, force_refresh=True, refresh_reason=f"freshness_retry:{','.join(refresh_sections)}")
        refreshed_freshness = dict(refreshed.get("freshness") or {})
        refreshed_freshness["refresh_attempted"] = True
        refreshed_freshness["refresh_reason"] = f"freshness_retry:{','.join(refresh_sections)}"
        refreshed["freshness"] = refreshed_freshness
        refreshed["data_quality"] = {
            **dict(refreshed.get("data_quality") or {}),
            "freshness": refreshed_freshness,
        }
        refreshed["warnings"] = _unique(
            [*list(refreshed.get("warnings") or []), *list(refreshed_freshness.get("warnings") or [])]
        )
        return refreshed
    return payload


def _build_analysis(
    req: QuantamentalAnalysisRequest,
    *,
    force_refresh: bool = False,
    refresh_reason: str | None = None,
) -> dict[str, Any]:
    clean, market_result = _clean_inputs(req.ticker, req.market)
    market = str(req.market or "US").upper()
    if market_result:
        return _analysis_error(clean, market, market_result, include_ai=req.include_ai, output_language=req.output_language)

    company_payload = company(clean, market=market, force_refresh=force_refresh)
    company_data = company_payload.get("company") or {"ticker": clean, "market": market}
    f_payload = fundamentals(clean, market=market, period=req.period, years=req.years, force_refresh=force_refresh)
    q_payload = quant(clean, market=market, lookback=req.lookback, force_refresh=force_refresh)
    factor_payload = calculate_factors(f_payload, q_payload, company_data)
    quality = data_quality(company_payload, f_payload, q_payload, factor_payload)
    sec_payload = (
        build_sec_evidence(clean, market=market)
        if req.include_sec
        else _skipped_sec_overlay_payload(clean, market, reason="screening_fast_path_sec_overlay_skipped")
    )
    freshness = freshness_audit(
        company_payload,
        f_payload,
        q_payload,
        sec_payload,
        period=req.period,
        generated_at=now_iso(),
        force_refresh=force_refresh,
        refresh_reason=refresh_reason,
    )
    quality["evidence_sources"] = {
        "sec_edgar": {
            "status": sec_payload.get("status"),
            "filing_count": sec_payload.get("filing_count", 0),
            "fact_count": sec_payload.get("fact_count", 0),
        }
    }
    quality["freshness"] = freshness
    risk_payload = calculate_risk(f_payload, q_payload, factor_payload, quality.get("data_quality_score"))
    risk_payload = apply_sec_evidence_to_risk(risk_payload, sec_payload)
    composite_payload = calculate_composite(
        f_payload,
        q_payload,
        factor_payload,
        risk_payload,
        style=req.style,
    )
    signal_payload = classify_signal(composite_payload, risk_payload, quality)
    context_payload: dict[str, Any] = {}
    ai_payload: dict[str, Any] = {}
    assembled = {
        "status": _overall_status(company_payload, f_payload, q_payload, quality),
        "ticker": clean,
        "market": market,
        "period": req.period,
        "years": req.years,
        "lookback": req.lookback,
        "style": composite_payload.get("style"),
        "output_language": req.output_language,
        "generated_at": now_iso(),
        "company": company_data,
        "fundamentals": f_payload,
        "quant": q_payload,
        "factors": factor_payload,
        "risk": risk_payload,
        "sec_evidence": sec_payload,
        "freshness": freshness,
        "composite": composite_payload,
        "signal": signal_payload,
        "data_quality": quality,
        "warnings": _unique(
            [
                *list(company_payload.get("warnings") or []),
                *list(f_payload.get("warnings") or []),
                *list(q_payload.get("warnings") or []),
                *list(quality.get("warnings") or []),
                *list(freshness.get("warnings") or []),
                *list(signal_payload.get("warnings") or []),
            ]
        ),
        "errors": _unique(
            [
                *list(company_payload.get("errors") or []),
                *list(f_payload.get("errors") or []),
                *list(q_payload.get("errors") or []),
                *list(quality.get("errors") or []),
            ]
        ),
        "not_investment_advice": True,
        "execution_policy": "scores_and_signal_from_deterministic_engines_ai_interprets_only",
    }
    if not req.include_sec:
        assembled["screening_fast_path"] = True
    _apply_data_integrity_gate(assembled)
    context_payload = build_context(assembled)
    if req.include_ai:
        ai_payload = generate_report(context_payload, use_llm=req.use_llm, language=req.output_language)
    assembled["ai_context"] = context_payload
    assembled["ai_report"] = ai_payload
    try:
        request_payload = req.model_dump(mode="json")
        request_payload["force_refresh_effective"] = force_refresh
        assembled["snapshot"] = save_snapshot(assembled, request_payload)
    except Exception as exc:  # noqa: BLE001
        assembled["snapshot"] = {
            "status": "failed",
            "error": f"snapshot_save_failed:{type(exc).__name__}:{exc}",
        }
    return assembled


def ai_report(request: QuantamentalAIReportRequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalAIReportRequest) else QuantamentalAIReportRequest.model_validate(request)
    context = req.context or {}
    if "deterministic_signal" not in context and "signal" in context:
        context = build_context(context)
    return generate_report(context, use_llm=req.use_llm, model=req.model, timeout_s=req.timeout_s, language=req.output_language)


def qa(request: QuantamentalQARequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalQARequest) else QuantamentalQARequest.model_validate(request)
    context = req.context or {}
    if "deterministic_signal" not in context and "signal" in context:
        context = build_context(context)
    return answer_question(req.question, context, use_llm=req.use_llm, model=req.model, timeout_s=req.timeout_s, language=req.output_language)


def compare(request: QuantamentalCompareRequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalCompareRequest) else QuantamentalCompareRequest.model_validate(request)
    analyses: list[dict[str, Any]] = []
    for ticker in req.tickers:
        analyses.append(
            analysis(
                QuantamentalAnalysisRequest(
                    ticker=ticker,
                    market=req.market,
                    period=req.period,
                    years=req.years,
                    lookback=req.lookback,
                    style=req.style,
                    include_ai=req.include_ai,
                    use_llm=req.use_llm,
                    force_refresh=req.force_refresh,
                    output_language=req.output_language,
                )
            )
        )
    peer_universe = {
        "status": "skipped",
        "warnings": [] if not req.expand_peer_universe else ["peer_universe_not_evaluated"],
    }
    if req.expand_peer_universe:
        peer_universe = expand_peer_universe(req.tickers, analyses, market=req.market, max_total=req.peer_limit)
        for ticker in peer_universe.get("added_tickers") or []:
            analyses.append(
                analysis(
                    QuantamentalAnalysisRequest(
                        ticker=ticker,
                        market=req.market,
                        period=req.period,
                        years=req.years,
                        lookback=req.lookback,
                        style=req.style,
                        include_ai=False,
                        use_llm=False,
                        force_refresh=req.force_refresh,
                        output_language=req.output_language,
                    )
                )
            )
    peer_payload = apply_peer_relative_scores(analyses)
    rows = peer_payload.get("rows") or []
    rows.sort(key=lambda row: (float(row.get("final_score") or -1.0)), reverse=True)
    return {
        "status": "ok" if any(item.get("status") in {"ok", "partial"} for item in analyses) else "failed",
        "market": req.market,
        "period": req.period,
        "years": req.years,
        "lookback": req.lookback,
        "style": req.style,
        "generated_at": now_iso(),
        "count": len(analyses),
        "rows": rows,
        "analyses": analyses,
        "peer_groups": peer_payload.get("peer_groups") or [],
        "peer_universe": peer_universe,
        "warnings": _unique([*(peer_payload.get("warnings") or []), *(peer_universe.get("warnings") or [])]),
        "not_investment_advice": True,
        "execution_policy": "scores_and_signal_from_deterministic_engines_ai_interprets_only",
    }


def screen_top_signals(request: QuantamentalScreenRequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalScreenRequest) else QuantamentalScreenRequest.model_validate(request)
    universe_tickers = _screening_tickers(req)
    cache_key = _screen_cache_key(req, universe_tickers)
    cached = None if req.force_refresh else quantamental_cache.get(cache_key)
    if cached:
        cached["cache_hit"] = True
        return cached
    rows, ranked_rows, failures, freshness_summary = _run_screening(req, universe_tickers)
    top_limit = min(SCREEN_TOP_LIMIT, int(req.limit or SCREEN_TOP_LIMIT))
    top = [dict(row, rank=idx) for idx, row in enumerate(ranked_rows[:top_limit], start=1)]
    top_count = len(top)
    response_status = "ok" if top else "partial" if rows else "failed"
    response = {
        "status": response_status,
        "universe": req.universe,
        "market": req.market,
        "period": req.period,
        "years": req.years,
        "lookback": req.lookback,
        "style": req.style,
        "output_language": req.output_language,
        "generated_at": now_iso(),
        "requested_count": len(universe_tickers),
        "scored_count": len(ranked_rows),
        "eligible_count": len(ranked_rows),
        "limit": top_limit,
        "top_count": top_count,
        "top_signals": top,
        "top": top,
        "ranked_rows": ranked_rows,
        "screened_rows": rows,
        "rows": rows,
        "failures": failures,
        "cache_hit": False,
        "freshness_summary": freshness_summary,
        "freshness": freshness_summary,
        "summary": {
            "status": response_status,
            "requested_count": len(universe_tickers),
            "scored_count": len(ranked_rows),
            "top_count": top_count,
            "freshness_status": freshness_summary.get("status"),
            "policy": "rank_only_fresh_complete_core_data_after_retry_sec_overlay_skipped_for_speed",
        },
        "screening_policy": "rank_only_fresh_complete_core_data_after_retry_sec_overlay_skipped_for_speed",
        "warnings": _unique(
            [
                "screening_fast_path_sec_overlay_skipped",
                *list(freshness_summary.get("warnings") or []),
                *(["screening_less_than_limit_scored"] if len(top) < top_limit else []),
            ]
        ),
        "not_investment_advice": True,
        "execution_policy": "scores_and_signal_from_deterministic_engines_ai_interprets_only",
    }
    quantamental_cache.set(cache_key, response, SCREEN_CACHE_TTL_S)
    return response


def screen_by_score(request: QuantamentalScoreScreenRequest | dict[str, Any]) -> dict[str, Any]:
    req = request if isinstance(request, QuantamentalScoreScreenRequest) else QuantamentalScoreScreenRequest.model_validate(request)
    universe_tickers = _screening_tickers(req)
    cache_key = _score_screen_cache_key(req, universe_tickers)
    cached = None if req.force_refresh else quantamental_cache.get(cache_key)
    if cached:
        cached["cache_hit"] = True
        return cached
    rows, ranked_rows, failures, freshness_summary = _run_screening(req, universe_tickers)
    min_score = float(req.min_score)
    limit = int(req.limit or 20)
    score_key = str(req.score_key or "composite")
    matches = [
        dict(row)
        for row in ranked_rows
        if row.get("screen_score") is not None and float(row.get("screen_score") or 0.0) >= min_score
    ]
    limited_matches = matches[:limit]
    for idx, row in enumerate(limited_matches, start=1):
        row["threshold_rank"] = idx
    match_count = len(matches)
    response_status = "ok" if limited_matches else "partial" if rows else "failed"
    response = {
        "status": response_status,
        "universe": req.universe,
        "market": req.market,
        "period": req.period,
        "years": req.years,
        "lookback": req.lookback,
        "style": req.style,
        "score_key": score_key,
        "score_label": _score_screen_label(score_key),
        "output_language": req.output_language,
        "generated_at": now_iso(),
        "requested_count": len(universe_tickers),
        "scored_count": len(ranked_rows),
        "eligible_count": len(ranked_rows),
        "min_score": min_score,
        "limit": limit,
        "matched_count": match_count,
        "returned_count": len(limited_matches),
        "matches": limited_matches,
        "top": limited_matches,
        "ranked_rows": ranked_rows,
        "screened_rows": rows,
        "rows": rows,
        "failures": failures,
        "cache_hit": False,
        "freshness_summary": freshness_summary,
        "freshness": freshness_summary,
        "summary": {
            "status": response_status,
            "requested_count": len(universe_tickers),
            "scored_count": len(ranked_rows),
            "matched_count": match_count,
            "returned_count": len(limited_matches),
            "min_score": min_score,
            "score_key": score_key,
            "score_label": _score_screen_label(score_key),
            "freshness_status": freshness_summary.get("status"),
            "policy": "rank_fresh_complete_core_data_then_filter_min_score_sec_overlay_skipped_for_speed",
        },
        "screening_policy": "rank_fresh_complete_core_data_then_filter_min_score_sec_overlay_skipped_for_speed",
        "warnings": _unique(
            [
                "screening_fast_path_sec_overlay_skipped",
                *list(freshness_summary.get("warnings") or []),
                *(["score_screen_no_matches"] if not limited_matches else []),
                *(["score_screen_matches_limited"] if match_count > len(limited_matches) else []),
            ]
        ),
        "not_investment_advice": True,
        "execution_policy": "scores_and_signal_from_deterministic_engines_ai_interprets_only",
    }
    quantamental_cache.set(cache_key, response, SCREEN_CACHE_TTL_S)
    return response


def _run_screening(
    req: QuantamentalScreenRequest | QuantamentalScoreScreenRequest,
    universe_tickers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    score_key = _screening_score_key(req)
    analyses: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for ticker in universe_tickers:
        payload = analysis(
            QuantamentalAnalysisRequest(
                ticker=ticker,
                market=req.market,
                period=req.period,
                years=req.years,
                lookback=req.lookback,
                style=req.style,
                include_ai=req.include_ai,
                include_sec=False,
                use_llm=req.use_llm,
                force_refresh=req.force_refresh,
                output_language=req.output_language,
            )
        )
        if req.refresh_stale and not req.force_refresh and _screening_refresh_recommended(payload.get("freshness") or {}):
            payload = analysis(
                QuantamentalAnalysisRequest(
                    ticker=ticker,
                    market=req.market,
                    period=req.period,
                    years=req.years,
                    lookback=req.lookback,
                    style=req.style,
                    include_ai=req.include_ai,
                    include_sec=False,
                    use_llm=req.use_llm,
                    force_refresh=True,
                    output_language=req.output_language,
                )
            )
        analyses.append(payload)
        if payload.get("status") == "failed":
            failures.append(
                {
                    "ticker": ticker,
                    "status": payload.get("status"),
                    "errors": payload.get("errors") or [],
                    "warnings": payload.get("warnings") or [],
                }
            )

    rows = [_screening_row(item, score_key=score_key) for item in analyses]
    ranked = [
        row for row in rows
        if (
            row.get("screen_score") is not None
            and row.get("signal_label") != "Insufficient Data"
            and row.get("usable_for_signal") is True
        )
    ]
    ranked.sort(
        key=lambda row: (
            float(row.get("screen_score") or -1.0),
            float(row.get("final_score") or -1.0),
            float(row.get("data_quality_score") or -1.0),
            float(row.get("freshness_score") or -1.0),
        ),
        reverse=True,
    )
    ranked_rows = [dict(row, rank=idx) for idx, row in enumerate(ranked, start=1)]
    freshness_summary = _screening_freshness_summary(rows)
    return rows, ranked_rows, failures, freshness_summary


def snapshots(ticker: str | None = None, *, limit: int = 20) -> dict[str, Any]:
    return list_snapshots(ticker, limit=limit)


def snapshot(snapshot_id: str) -> dict[str, Any]:
    return get_snapshot(snapshot_id)


def snapshot_export(snapshot_id: str, *, fmt: str = "json") -> dict[str, Any]:
    from pipelines.quantamental.snapshot_store import export_snapshot

    return export_snapshot(snapshot_id, fmt=fmt)


def snapshot_diff(base_snapshot_id: str, target_snapshot_id: str) -> dict[str, Any]:
    from pipelines.quantamental.snapshot_store import diff_snapshots

    return diff_snapshots(base_snapshot_id, target_snapshot_id)


def snapshot_retention(ticker: str | None = None, *, keep_last: int = 20, dry_run: bool = True) -> dict[str, Any]:
    from pipelines.quantamental.snapshot_store import prune_snapshots

    return prune_snapshots(ticker, keep_last=keep_last, dry_run=dry_run)


def _skipped_sec_overlay_payload(ticker: str, market: str, *, reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "ticker": ticker,
        "market": str(market or "US").upper(),
        "source": "sec_edgar",
        "warnings": [reason],
        "risk_flags": [],
        "quality_flags": [],
        "filing_count": 0,
        "fact_count": 0,
        "filing_excerpts": [],
        "sample_filings": [],
        "concept_provenance": [],
    }


def sec(
    ticker: str,
    *,
    market: str = "US",
    include_filing_text: bool = False,
    filing_text_timeout_s: float = 5.0,
) -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    if market_result:
        return market_result
    return build_sec_evidence(
        clean,
        market=str(market or "US").upper(),
        include_filing_text=include_filing_text,
        filing_text_timeout_s=filing_text_timeout_s,
    )


def resolve_ticker(ticker: str, *, market: str = "GLOBAL") -> dict[str, Any]:
    clean, market_result = _clean_inputs(ticker, market)
    market_clean = str(market or "GLOBAL").upper()
    if market_result:
        return market_result
    if market_clean == "GLOBAL":
        resolved = resolve_global_symbol(clean)
        return {"status": "ok", **resolved.to_dict()}
    return {
        "status": "ok",
        "input_ticker": clean,
        "provider_ticker": clean,
        "yfinance_symbol": clean,
        "market": market_clean,
        "resolution_source": "input",
        "warnings": [],
    }


def global_sec_hydration(
    tickers: list[str],
    *,
    all_known: bool = False,
    dry_run: bool = True,
    lookback_days: int = 365 * 5,
    max_assets: int = 25,
) -> dict[str, Any]:
    return hydrate_global_sec_aliases(
        tickers,
        all_known=all_known,
        dry_run=dry_run,
        lookback_days=lookback_days,
        max_assets=max_assets,
    )


def data_quality(
    company_payload: dict[str, Any],
    fundamentals_payload: dict[str, Any],
    quant_payload: dict[str, Any],
    factors_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing_sections: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    company_data = company_payload.get("company") or {}
    if company_payload.get("status") not in {"ok", "success"} or not (
        company_data.get("name") or company_data.get("current_price") or company_data.get("market_cap")
    ):
        missing_sections.append("company")
    if fundamentals_payload.get("status") != "ok":
        missing_sections.append("fundamentals")
    if quant_payload.get("status") != "ok":
        missing_sections.append("quant")
    if factors_payload is not None and factors_payload.get("status") not in {"ok", "success"}:
        missing_sections.append("factors")
    for payload in (company_payload, fundamentals_payload, quant_payload, factors_payload or {}):
        warnings.extend(str(item) for item in payload.get("warnings") or [])
        if payload.get("error"):
            errors.append(str(payload.get("error")))
        errors.extend(str(item) for item in payload.get("errors") or [])
    fundamental_missing = len(fundamentals_payload.get("missing_metrics") or [])
    quant_missing = len(quant_payload.get("missing_metrics") or [])
    section_penalty = 25 * len(set(missing_sections))
    metric_penalty = min(30, int((fundamental_missing + quant_missing) * 0.5))
    warning_penalty = min(20, len(set(warnings)) * 3)
    score = max(0.0, min(100.0, 100.0 - section_penalty - metric_penalty - warning_penalty))
    return {
        "data_quality_score": round(score, 2),
        "quality_level": _quality_level(score),
        "missing_sections": sorted(set(missing_sections)),
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "fundamental_missing_metric_count": fundamental_missing,
        "quant_missing_metric_count": quant_missing,
        "source_policy": "fail_open_with_visible_warnings",
    }


def freshness_audit(
    company_payload: dict[str, Any],
    fundamentals_payload: dict[str, Any],
    quant_payload: dict[str, Any],
    sec_payload: dict[str, Any],
    *,
    period: str = "annual",
    generated_at: str | None = None,
    force_refresh: bool = False,
    refresh_reason: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or now_iso()
    sections = {
        "company": _company_freshness(company_payload),
        "fundamentals": _fundamentals_freshness(fundamentals_payload, period=period),
        "prices": _price_freshness(quant_payload),
        "sec": _sec_freshness(sec_payload),
    }
    stale_sections = [name for name, item in sections.items() if item.get("status") == "stale"]
    missing_sections = [name for name, item in sections.items() if item.get("status") in {"missing", "failed"}]
    unknown_sections = [name for name, item in sections.items() if item.get("status") == "unknown"]
    retryable_refreshable = [
        name for name, item in sections.items()
        if item.get("status") in FRESHNESS_RETRYABLE_STATUSES
        if sections.get(name, {}).get("refreshable") is True
    ]
    if stale_sections:
        overall = "stale"
    elif missing_sections:
        overall = "partial"
    elif any(item.get("status") == "unknown" for item in sections.values()):
        overall = "partial"
    else:
        overall = "fresh"
    freshness_score = max(0.0, 100.0 - 20.0 * len(stale_sections) - 15.0 * len(missing_sections))
    warnings = []
    if stale_sections:
        warnings.append(f"freshness_stale_sections:{','.join(stale_sections)}")
    if missing_sections:
        warnings.append(f"freshness_missing_sections:{','.join(missing_sections)}")
    if unknown_sections:
        warnings.append(f"freshness_unknown_sections:{','.join(unknown_sections)}")
    return {
        "status": overall,
        "freshness_score": round(freshness_score, 2),
        "generated_at": generated,
        "force_refresh": bool(force_refresh),
        "refresh_reason": refresh_reason or "",
        "refresh_recommended": bool(retryable_refreshable),
        "stale_sections": stale_sections,
        "stale_refreshable_sections": [
            name for name in stale_sections
            if sections.get(name, {}).get("refreshable") is True
        ],
        "retryable_sections": retryable_refreshable,
        "missing_sections": missing_sections,
        "unknown_sections": unknown_sections,
        "sections": sections,
        "thresholds": {
            "company_fetched_at_days": COMPANY_FETCH_MAX_AGE_DAYS,
            "price_as_of_days": PRICE_FRESH_MAX_AGE_DAYS,
            "fundamental_annual_days": ANNUAL_FUNDAMENTAL_MAX_AGE_DAYS,
            "fundamental_quarterly_days": QUARTERLY_FUNDAMENTAL_MAX_AGE_DAYS,
            "sec_filing_days": SEC_FILING_MAX_AGE_DAYS,
        },
        "warnings": warnings,
        "source_policy": "freshness_is_audited_per_section_and_stale_missing_or_unknown_core_data_is_refetched_once_then_failed_closed",
    }


def _company_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    company_data = payload.get("company") or {}
    meta = payload.get("source_metadata") or company_data.get("source_metadata") or {}
    fetched_at = str(meta.get("fetched_at") or company_data.get("last_updated") or "").strip()
    age_days = _days_since(fetched_at)
    if payload.get("status") in {"failed", "error"}:
        return _freshness_section("failed", "company profile provider failed", fetched_at, age_days, "source_fetched_at", refreshable=True)
    if not (company_data.get("name") or company_data.get("current_price") or company_data.get("market_cap")):
        return _freshness_section("missing", "company profile is empty", fetched_at, age_days, "source_fetched_at", refreshable=True)
    if age_days is None:
        return _freshness_section("unknown", "provider fetch timestamp is unavailable", fetched_at, age_days, "source_fetched_at", refreshable=True)
    if age_days > COMPANY_FETCH_MAX_AGE_DAYS:
        return _freshness_section("stale", "company profile fetch timestamp is stale", fetched_at, age_days, "source_fetched_at", refreshable=True)
    return _freshness_section("fresh", "company profile was fetched recently", fetched_at, age_days, "source_fetched_at", refreshable=True)


def _fundamentals_freshness(payload: dict[str, Any], *, period: str) -> dict[str, Any]:
    statements = list(payload.get("statements") or payload.get("items") or [])
    latest_date = _max_iso_date([row.get("date") for row in statements if isinstance(row, dict)])
    age_days = _days_since(latest_date)
    max_age = QUARTERLY_FUNDAMENTAL_MAX_AGE_DAYS if str(period).lower() == "quarterly" else ANNUAL_FUNDAMENTAL_MAX_AGE_DAYS
    if payload.get("status") in {"failed", "error"}:
        return _freshness_section("failed", "fundamental provider failed", latest_date, age_days, "latest_statement_date", refreshable=True)
    if not statements and not payload.get("metrics"):
        return _freshness_section("missing", "fundamental statement history is empty", latest_date, age_days, "latest_statement_date", refreshable=True)
    if age_days is None:
        return _freshness_section("unknown", "latest statement date is unavailable", latest_date, age_days, "latest_statement_date", refreshable=True)
    if age_days > max_age:
        return _freshness_section("stale", "latest statement is older than the configured reporting freshness window", latest_date, age_days, "latest_statement_date", refreshable=False)
    return _freshness_section("fresh", "latest statement is within the reporting freshness window", latest_date, age_days, "latest_statement_date", refreshable=True)


def _price_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("price_history") or payload.get("items") or [])
    latest_date = _max_iso_date([row.get("date") for row in rows if isinstance(row, dict)])
    age_days = _days_since(latest_date)
    if payload.get("status") in {"failed", "error"}:
        return _freshness_section("failed", "price provider failed", latest_date, age_days, "latest_price_date", refreshable=True)
    if not rows:
        return _freshness_section("missing", "price history is empty", latest_date, age_days, "latest_price_date", refreshable=True)
    if age_days is None:
        return _freshness_section("unknown", "latest price date is unavailable", latest_date, age_days, "latest_price_date", refreshable=True)
    if age_days > PRICE_FRESH_MAX_AGE_DAYS:
        return _freshness_section("stale", "latest price bar is older than the configured market-data freshness window", latest_date, age_days, "latest_price_date", refreshable=True)
    return _freshness_section("fresh", "latest price bar is within the market-data freshness window", latest_date, age_days, "latest_price_date", refreshable=True)


def _sec_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "").lower()
    latest_date = str(payload.get("latest_filing_at") or payload.get("latest_fact_filed_at") or "").strip()
    age_days = _days_since(latest_date)
    if status in {"skipped", "unsupported"}:
        return _freshness_section("skipped", "SEC evidence is not applicable for this resolved market or symbol", latest_date, age_days, "latest_sec_filing", refreshable=False)
    if status in {"failed", "error"}:
        return _freshness_section("failed", "SEC evidence lookup failed", latest_date, age_days, "latest_sec_filing", refreshable=True)
    if not latest_date:
        return _freshness_section("missing", "SEC filing metadata is unavailable", latest_date, age_days, "latest_sec_filing", refreshable=True)
    if age_days is not None and age_days > SEC_FILING_MAX_AGE_DAYS:
        return _freshness_section("stale", "latest SEC filing metadata is older than the annual filing window", latest_date, age_days, "latest_sec_filing", refreshable=False)
    return _freshness_section("fresh", "latest SEC filing metadata is within the annual filing window", latest_date, age_days, "latest_sec_filing", refreshable=True)


def _freshness_section(
    status: str,
    reason: str,
    as_of: str | None,
    age_days: int | None,
    basis: str,
    *,
    refreshable: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "as_of": as_of or "",
        "age_days": age_days,
        "basis": basis,
        "refreshable": refreshable,
    }


def _freshness_refresh_recommended(freshness: dict[str, Any]) -> bool:
    return bool(freshness.get("refresh_recommended") or freshness.get("retryable_sections") or freshness.get("stale_refreshable_sections"))


def _freshness_refresh_sections(freshness: dict[str, Any]) -> list[str]:
    sections = freshness.get("sections") or {}
    return [
        name for name, item in sections.items()
        if isinstance(item, dict)
        and item.get("status") in FRESHNESS_RETRYABLE_STATUSES
        and item.get("refreshable") is True
    ]


def _screening_refresh_recommended(freshness: dict[str, Any]) -> bool:
    if freshness.get("refresh_attempted") is True:
        return False
    sections = freshness.get("sections") or {}
    return any(
        isinstance(sections.get(name), dict)
        and sections[name].get("status") in FRESHNESS_RETRYABLE_STATUSES
        and sections[name].get("refreshable") is True
        for name in STRICT_SIGNAL_FRESHNESS_SECTIONS
    )


def _apply_data_integrity_gate(payload: dict[str, Any]) -> None:
    freshness = payload.get("freshness") or {}
    sections = freshness.get("sections") or {}
    blocking = [
        name for name in STRICT_SIGNAL_FRESHNESS_SECTIONS
        if (sections.get(name) or {}).get("status") in FRESHNESS_RETRYABLE_STATUSES
    ]
    optional_issues = [
        name for name, item in sections.items()
        if name not in STRICT_SIGNAL_FRESHNESS_SECTIONS
        and isinstance(item, dict)
        and item.get("status") in FRESHNESS_RETRYABLE_STATUSES
    ]
    integrity = {
        "status": "blocked" if blocking else "ok",
        "usable_for_signal": not blocking,
        "strict_policy": "company_fundamentals_and_prices_must_be_fresh_complete_and_traceable_after_retry",
        "critical_sections": list(STRICT_SIGNAL_FRESHNESS_SECTIONS),
        "blocking_sections": blocking,
        "optional_issue_sections": optional_issues,
        "no_silent_missing_data": True,
    }
    payload["data_integrity"] = integrity
    quality = dict(payload.get("data_quality") or {})
    quality["data_integrity"] = integrity
    if blocking:
        warnings = _unique([
            *list(payload.get("warnings") or []),
            f"strict_freshness_gate_blocked:{','.join(blocking)}",
        ])
        quality["warnings"] = _unique([
            *list(quality.get("warnings") or []),
            f"strict_freshness_gate_blocked:{','.join(blocking)}",
        ])
        missing_sections = set(quality.get("missing_sections") or [])
        missing_sections.update(blocking)
        quality["missing_sections"] = sorted(missing_sections)
        quality["quality_level"] = "poor"
        quality["data_quality_score"] = min(float(quality.get("data_quality_score") or 0.0), 35.0)
        payload["status"] = "failed"
        payload["signal"] = _strict_freshness_insufficient_signal(payload.get("composite") or {}, quality, blocking)
        payload["warnings"] = warnings
    payload["data_quality"] = quality


def _strict_freshness_insufficient_signal(
    composite: dict[str, Any],
    data_quality_payload: dict[str, Any],
    blocking_sections: list[str],
) -> dict[str, Any]:
    return {
        "signal_label": "Insufficient Data",
        "signal_score": None,
        "signal_confidence": "low",
        "time_horizon": "unavailable",
        "rationale": [
            "Strict freshness gate blocked the signal because required core data was stale, missing, failed, or not timestamped after refresh.",
            f"Blocking sections: {', '.join(blocking_sections)}.",
        ],
        "warnings": _unique([
            f"strict_freshness_gate_blocked:{','.join(blocking_sections)}",
            *list(data_quality_payload.get("warnings") or []),
        ]),
        "not_investment_advice": True,
        "inputs": {
            "final_composite_score": composite.get("final_score"),
            "fundamental_score": composite.get("fundamental_score"),
            "quant_score": composite.get("quant_score"),
            "risk_score": composite.get("risk_score"),
            "data_quality_score": data_quality_payload.get("data_quality_score"),
            "blocking_sections": blocking_sections,
        },
    }


def _screening_tickers(req: QuantamentalScreenRequest | QuantamentalScoreScreenRequest) -> list[str]:
    raw = req.tickers or DEFAULT_SCREENING_UNIVERSES.get(req.universe, DEFAULT_SCREENING_UNIVERSES["default_us_large_cap"])
    max_count = 50 if req.tickers else max(int(req.limit or SCREEN_TOP_LIMIT), DEFAULT_SCREEN_CANDIDATE_LIMIT)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        ticker = str(item or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append(ticker)
    return cleaned[:max_count]


def _screen_cache_key(req: QuantamentalScreenRequest, tickers: list[str]) -> str:
    return _key(
        "screen_top_signals",
        ",".join(tickers),
        req.universe,
        req.market,
        req.period,
        req.years,
        req.lookback,
        req.style,
        req.limit,
        req.include_ai,
        req.use_llm,
        req.refresh_stale,
        req.output_language,
    )


def _score_screen_cache_key(req: QuantamentalScoreScreenRequest, tickers: list[str]) -> str:
    return _key(
        "screen_by_score",
        ",".join(tickers),
        req.universe,
        req.market,
        req.period,
        req.years,
        req.lookback,
        req.style,
        req.score_key,
        req.min_score,
        req.limit,
        req.include_ai,
        req.use_llm,
        req.refresh_stale,
        req.output_language,
    )


def _screening_score_key(req: QuantamentalScreenRequest | QuantamentalScoreScreenRequest) -> str:
    return str(getattr(req, "score_key", "composite") or "composite")


def _score_screen_label(score_key: str) -> str:
    return SCORE_SCREEN_REGISTRY.get(str(score_key or "composite"), SCORE_SCREEN_REGISTRY["composite"])["label"]


def _screening_score_value(row: dict[str, Any], score_key: str) -> Any:
    meta = SCORE_SCREEN_REGISTRY.get(str(score_key or "composite"), SCORE_SCREEN_REGISTRY["composite"])
    return row.get(meta["row_field"], row.get("final_score"))


def _screening_row(payload: dict[str, Any], *, score_key: str = "composite") -> dict[str, Any]:
    company_data = payload.get("company") or {}
    composite = payload.get("composite") or {}
    factors = payload.get("factors") or {}
    signal_payload = payload.get("signal") or {}
    quality = payload.get("data_quality") or {}
    freshness = payload.get("freshness") or {}
    integrity = payload.get("data_integrity") or quality.get("data_integrity") or {}
    quant = payload.get("quant") or {}
    quant_algorithms = ((quant.get("metrics") or {}).get("algorithms") or {}) if isinstance(quant, dict) else {}
    row = {
        "ticker": payload.get("ticker"),
        "market": payload.get("market"),
        "name": company_data.get("name"),
        "sector": company_data.get("sector"),
        "industry": company_data.get("industry"),
        "signal_label": signal_payload.get("signal_label"),
        "signal_confidence": signal_payload.get("signal_confidence"),
        "final_score": composite.get("final_score"),
        "fundamental_score": composite.get("fundamental_score"),
        "quant_score": composite.get("quant_score"),
        "risk_score": composite.get("risk_score"),
        "value_score": factors.get("value_score"),
        "quality_score": factors.get("quality_score"),
        "growth_score": factors.get("growth_score"),
        "momentum_score": factors.get("momentum_score"),
        "low_volatility_score": factors.get("low_volatility_score"),
        "liquidity_score": factors.get("liquidity_score"),
        "data_quality_score": quality.get("data_quality_score"),
        "quality_level": quality.get("quality_level"),
        "freshness_status": freshness.get("status"),
        "freshness_score": freshness.get("freshness_score"),
        "usable_for_signal": bool(integrity.get("usable_for_signal")),
        "data_integrity_status": integrity.get("status") or "unknown",
        "blocking_sections": integrity.get("blocking_sections") or [],
        "stale_sections": freshness.get("stale_sections") or [],
        "missing_sections": quality.get("missing_sections") or [],
        "warnings": _unique([*list(payload.get("warnings") or []), *list(freshness.get("warnings") or [])])[:12],
        "not_investment_advice": True,
    }
    for meta in SCORE_SCREEN_REGISTRY.values():
        algorithm_key = meta.get("algorithm_key")
        score_field = meta.get("algorithm_score_field")
        if algorithm_key and score_field:
            row[meta["row_field"]] = (quant_algorithms.get(algorithm_key) or {}).get(score_field)
    row["screen_score_key"] = score_key
    row["screen_score_label"] = _score_screen_label(score_key)
    row["screen_score"] = _screening_score_value(row, score_key)
    return row


def _screening_freshness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    fresh = sum(1 for row in rows if row.get("freshness_status") == "fresh")
    stale = sum(1 for row in rows if row.get("freshness_status") == "stale")
    partial = sum(1 for row in rows if row.get("freshness_status") in {"partial", "missing", "failed", "unknown"})
    warnings = []
    if stale:
        warnings.append(f"screening_stale_rows:{stale}")
    if partial:
        warnings.append(f"screening_partial_freshness_rows:{partial}")
    return {
        "status": "fresh" if total and fresh == total else "stale" if stale else "partial" if partial else "empty",
        "total": total,
        "fresh": fresh,
        "stale": stale,
        "partial": partial,
        "warnings": warnings,
    }


def _max_iso_date(values: list[Any]) -> str:
    dates = [str(value or "").strip()[:10] for value in values if str(value or "").strip()]
    return max(dates) if dates else ""


def _days_since(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed_date = parsed.astimezone(timezone.utc).date() if parsed.tzinfo else parsed.date()
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError:
            return None
    return (datetime.now(timezone.utc).date() - parsed_date).days


def _clean_inputs(ticker: str, market: str) -> tuple[str, dict[str, Any] | None]:
    try:
        clean = validate_ticker(ticker)
    except ValueError as exc:
        return str(ticker or "").strip().upper(), {
            "status": "failed",
            "ticker": str(ticker or "").strip().upper(),
            "market": str(market or "US").upper(),
            "errors": [f"invalid_ticker:{exc}"],
            "warnings": ["ticker_validation_failed"],
        }
    try:
        normalize_market(market)
    except UnsupportedMarketError as exc:
        return clean, _unsupported_payload("input", clean, str(market or "US").upper(), exc)
    return clean, None


def _unsupported_payload(section: str, ticker: str, market: str, exc: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "section": section,
        "ticker": ticker,
        "market": str(market or "US").upper(),
        "errors": [str(exc)],
        "warnings": ["unsupported_market"],
        "data_quality": {"missing_sections": [section], "data_quality_score": 0.0},
    }


def _benchmark_for_market(market: str) -> str:
    cleaned = normalize_market(market)
    if cleaned == "GLOBAL":
        return "ACWI"
    if cleaned == "KR":
        return ""
    return "SPY"


def _failed_payload(section: str, ticker: str, market: str, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "section": section,
        "ticker": ticker,
        "market": str(market or "US").upper(),
        "errors": [error],
        "error": error,
        "warnings": [f"{section}_unavailable"],
    }


def _analysis_error(
    ticker: str,
    market: str,
    error_payload: dict[str, Any],
    *,
    include_ai: bool = False,
    output_language: str = "ko",
) -> dict[str, Any]:
    freshness = {
        "status": "failed",
        "freshness_score": 0.0,
        "generated_at": now_iso(),
        "force_refresh": False,
        "refresh_recommended": False,
        "stale_sections": [],
        "missing_sections": ["company", "fundamentals", "prices", "sec"],
        "sections": {
            "company": _freshness_section("failed", "analysis input validation failed", "", None, "input_validation", refreshable=False),
            "fundamentals": _freshness_section("failed", "analysis input validation failed", "", None, "input_validation", refreshable=False),
            "prices": _freshness_section("failed", "analysis input validation failed", "", None, "input_validation", refreshable=False),
            "sec": _freshness_section("failed", "analysis input validation failed", "", None, "input_validation", refreshable=False),
        },
        "warnings": ["freshness_failed_input_validation"],
    }
    quality = {
        "data_quality_score": 0.0,
        "quality_level": "poor",
        "missing_sections": ["company", "fundamentals", "quant", "factors"],
        "warnings": _unique([*list(error_payload.get("warnings") or []), *list(freshness.get("warnings") or [])]),
        "errors": list(error_payload.get("errors") or []),
    }
    quality["freshness"] = freshness
    signal_payload = classify_signal({}, {}, quality)
    context = build_context({
        "ticker": ticker,
        "market": market,
        "output_language": output_language,
        "signal": signal_payload,
        "data_quality": quality,
    })
    payload = {
        "status": "failed",
        "ticker": ticker,
        "market": market,
        "output_language": output_language,
        "generated_at": now_iso(),
        "company": {"ticker": ticker, "market": market},
        "fundamentals": {},
        "quant": {},
        "factors": {},
        "risk": {},
        "composite": {},
        "signal": signal_payload,
        "data_quality": quality,
        "freshness": freshness,
        "ai_context": context,
        "ai_report": generate_report(context, use_llm=False, language=output_language) if include_ai else {},
        "warnings": _unique([*list(error_payload.get("warnings") or []), *list(freshness.get("warnings") or [])]),
        "errors": list(error_payload.get("errors") or []),
        "not_investment_advice": True,
        "execution_policy": "scores_and_signal_from_deterministic_engines_ai_interprets_only",
    }
    try:
        payload["snapshot"] = save_snapshot(payload, {"ticker": ticker, "market": market, "include_ai": include_ai})
    except Exception as exc:  # noqa: BLE001
        payload["snapshot"] = {"status": "failed", "error": f"snapshot_save_failed:{type(exc).__name__}:{exc}"}
    return payload


def _overall_status(
    company_payload: dict[str, Any],
    fundamentals_payload: dict[str, Any],
    quant_payload: dict[str, Any],
    quality: dict[str, Any],
) -> str:
    if company_payload.get("status") == "failed" and fundamentals_payload.get("status") == "failed" and quant_payload.get("status") == "failed":
        return "failed"
    if quality.get("missing_sections") or quality.get("warnings") or quality.get("errors"):
        return "partial"
    return "ok"


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


def _key(kind: str, *parts: Any) -> str:
    return "quantamental:" + kind + ":" + ":".join(str(part) for part in parts)


def _cache_get(kind: str, ticker: str, market: str) -> dict[str, Any] | None:
    return quantamental_cache.get(_key(kind, ticker, market))


def _cache_set(kind: str, ticker: str, market: str, payload: dict[str, Any]) -> None:
    quantamental_cache.set(_key(kind, ticker, market), payload, DEFAULT_CACHE_TTL_S)


def _unique(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in out:
            out.append(text)
    return out
