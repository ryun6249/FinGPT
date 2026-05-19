from __future__ import annotations

import asyncio
import time

from core.config.settings import load_settings
from core.schemas.request import (
    COMPARE_MAX_CONCURRENCY,
    AnalysisRequest,
    CompareRequest,
    UniversalRequest,
)
from core.schemas.response import AnalysisResponse, CompareResponse
from core.schemas.topic import TopicRequest, TopicResponse
from pipelines.orchestration.research_pipeline import EventSink, run_pipeline_async
from pipelines.orchestration.topic_pipeline import run_topic_pipeline_async
from pipelines.router.query_router import extract_explicit_tickers, route_query, should_route_hint_as_topic


def _safe_sources(value) -> list[str]:
    if value is None:
        return ["news", "transcript"]
    if isinstance(value, str):
        raw = value.replace(",", " ").split()
    else:
        try:
            raw = list(value)
        except TypeError:
            raw = ["news", "transcript"]
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        source = str(item or "").strip().lower()
        if source and source not in seen:
            seen.add(source)
            cleaned.append(source)
    return cleaned or ["news", "transcript"]


def _merge_ticker_hints(*groups) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if not group:
            continue
        if isinstance(group, str):
            values = [group]
        else:
            try:
                values = list(group)
            except TypeError:
                values = [group]
        for raw in values:
            ticker = str(raw or "").strip().upper()
            if ticker and ticker not in seen:
                seen.add(ticker)
                merged.append(ticker)
    return merged[: int(getattr(load_settings(), "topic_max_related_tickers", 8) or 8)]


async def _run_compare_async(request: CompareRequest) -> CompareResponse:
    started = time.time()
    seen: set[str] = set()
    tickers = []
    for raw in request.tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    concurrency = max(1, min(request.concurrency, COMPARE_MAX_CONCURRENCY, len(tickers)))
    sem = asyncio.Semaphore(concurrency)

    async def one(ticker: str):
        async with sem:
            try:
                resp = await run_pipeline_async(
                    AnalysisRequest(
                        ticker=ticker,
                        question=request.question,
                        sources=list(request.sources),
                        lookback_days=request.lookback_days,
                        top_k=request.top_k,
                        model=request.model,
                        output_language=request.output_language,
                        scenario_simulation_enabled=request.scenario_simulation_enabled,
                    )
                )
                return ticker, resp
            except Exception as exc:  # noqa: BLE001
                return ticker, AnalysisResponse(
                    ticker=ticker,
                    question=request.question,
                    status="failed",
                    error_metadata=str(exc),
                    summary=f"{ticker} failed: {exc}",
                    sentiment="Neutral",
                    conclusion="Pipeline exception during universal compare.",
                )

    pairs = await asyncio.gather(*(one(ticker) for ticker in tickers))
    return CompareResponse(
        question=request.question,
        tickers=tickers,
        results={ticker: resp for ticker, resp in pairs},
        elapsed_s=round(time.time() - started, 2),
        concurrency=concurrency,
    )


async def dispatch_async(
    universal: UniversalRequest,
    *,
    event_sink: EventSink = None,
) -> AnalysisResponse | CompareResponse | TopicResponse:
    settings = load_settings()
    hint = universal.ticker.strip().upper() if universal.ticker else None
    sources = _safe_sources(getattr(universal, "sources", None))
    if universal.mode_hint == "ticker" and not hint:
        return AnalysisResponse(
            ticker="TICKER_REQUIRED",
            question=universal.question,
            status="failed",
            error_metadata=(
                "종목 분석 모드에서는 ticker 입력이 필요합니다. "
                "ticker 없이 일반 질의를 하려면 mode_hint=auto 또는 topic을 사용하세요."
            ),
            summary="ticker가 없어 단일 종목 분석을 시작하지 않았습니다.",
            sentiment="Neutral",
            conclusion="ticker를 입력하거나 자동/주제 모드로 다시 실행하세요.",
        )
    if universal.mode_hint == "ticker" and hint:
        routed_mode = "single_ticker"
        tickers = [hint]
        theme = None
    elif (
        universal.mode_hint == "auto"
        and hint
        and not extract_explicit_tickers(universal.question)
        and not should_route_hint_as_topic(universal.question, hint)
    ):
        routed_mode = "single_ticker"
        tickers = [hint]
        theme = None
    elif universal.mode_hint == "topic":
        routed = route_query(universal.question, hint_ticker=hint)
        tickers = _merge_ticker_hints([hint] if hint else [], routed.tickers)
        routed_mode = "sector_macro" if routed.mode in {"sector_macro", "multi_ticker"} or tickers else "concept"
        theme = routed.theme or universal.question
    else:
        routed = route_query(universal.question, hint_ticker=hint)
        routed_mode = routed.mode
        tickers = routed.tickers
        theme = routed.theme

    if routed_mode == "single_ticker":
        ticker = tickers[0] if tickers else hint
        return await run_pipeline_async(
            AnalysisRequest(
                ticker=ticker,
                question=universal.question,
                sources=sources,
                lookback_days=universal.lookback_days,
                top_k=universal.top_k,
                model=universal.model,
                output_dir=universal.output_dir,
                output_language=universal.output_language,
                scenario_simulation_enabled=universal.scenario_simulation_enabled,
            ),
            event_sink=event_sink,
        )

    if routed_mode == "multi_ticker":
        return await _run_compare_async(
            CompareRequest(
                tickers=tickers[:5],
                question=universal.question,
                sources=sources,
                lookback_days=universal.lookback_days,
                top_k=universal.top_k,
                model=universal.model,
                output_language=universal.output_language,
                scenario_simulation_enabled=universal.scenario_simulation_enabled,
            )
        )

    if not bool(getattr(settings, "topic_mode_enabled", True)):
        return AnalysisResponse(
            ticker=hint or "TOPIC",
            question=universal.question,
            status="failed",
            error_metadata="Topic mode is disabled by TOPIC_MODE_ENABLED=false.",
            summary="Topic mode is disabled.",
            sentiment="Neutral",
            conclusion="Enable TOPIC_MODE_ENABLED to route tickerless questions.",
        )

    explicit_question_tickers = set(extract_explicit_tickers(universal.question))
    hint_is_user_topic_context = bool(hint and (universal.mode_hint == "topic" or hint in explicit_question_tickers))
    related = _merge_ticker_hints([hint] if hint_is_user_topic_context else [], tickers)
    return await run_topic_pipeline_async(
        TopicRequest(
            question=universal.question,
            theme=theme or universal.question,
            related_tickers=related,
            lookback_days=universal.lookback_days,
            top_k=universal.top_k or getattr(settings, "topic_retrieval_top_k", 12),
            model=universal.model,
            output_dir=universal.output_dir,
            output_language=universal.output_language,
            scenario_simulation_enabled=universal.scenario_simulation_enabled,
        ),
        mode="sector_macro" if routed_mode == "sector_macro" else "concept",
        event_sink=event_sink,
    )


def dispatch(universal: UniversalRequest) -> AnalysisResponse | CompareResponse | TopicResponse:
    return asyncio.run(dispatch_async(universal))
