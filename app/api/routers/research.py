from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.config.settings import load_settings
from core.schemas.portfolio import PortfolioRiskRequest, PortfolioRiskResponse
from core.schemas.request import (
    COMPARE_MAX_CONCURRENCY,
    COMPARE_MAX_TICKERS,
    AnalysisRequest,
    CompareRequest,
    UniversalRequest,
)
from core.schemas.response import AnalysisResponse, CompareResponse, ExecutionMeta
from core.schemas.topic import TopicResponse
from core.utils.asset_classifier import classify
from core.utils.logger import get_logger
from pipelines.analyze.portfolio_quant import analyze_portfolio_risk
from pipelines.orchestration.dispatch import dispatch_async
from pipelines.orchestration.research_pipeline import run_pipeline_async


router = APIRouter(prefix="/api/v1/research", tags=["research"])
logger = get_logger("api.research")

_NON_COMPANY_DIRECT_ASSET_CLASSES = {"bond_etf", "commodity_etf", "forex", "futures", "crypto"}


def _validation_422(message: str, code: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": message})


def _validate_question_present(question: str | None) -> None:
    if not str(question or "").strip():
        raise _validation_422("질문을 입력해야 합니다.", "question_required")


def _validate_direct_ticker_request(request: AnalysisRequest) -> None:
    _validate_question_present(request.question)
    if not request.ticker:
        raise _validation_422(
            "단일 종목 endpoint는 ticker가 필요합니다. ticker 없는 일반 질문은 /api/v1/research/universal/stream을 사용하세요.",
            "ticker_required_for_single_ticker_endpoint",
        )


def _validate_universal_request(request: UniversalRequest) -> None:
    _validate_question_present(request.question)
    if request.mode_hint == "ticker" and not request.ticker:
        raise _validation_422(
            "종목 모드에서는 ticker가 필요합니다. ticker 없이 질문하려면 자동 또는 주제 모드를 사용하세요.",
            "ticker_required_for_ticker_mode",
        )


def _direct_non_company_response(request: AnalysisRequest) -> AnalysisResponse | None:
    if not request.ticker:
        return None
    profile = classify(request.ticker)
    if profile.asset_class not in _NON_COMPANY_DIRECT_ASSET_CLASSES:
        return None
    return AnalysisResponse(
        ticker=profile.ticker,
        question=request.question,
        status="failed",
        error_metadata=(
            f"{profile.ticker}는 {profile.asset_class} 유형입니다. 단일 기업 endpoint가 아니라 "
            "/api/v1/research/universal/stream topic 경로로 분석해야 합니다."
        ),
        summary="요청한 ticker는 개별 기업 종목이 아니므로 topic/universal 분석 경로가 필요합니다.",
        sentiment="Neutral",
        confidence=0.0,
        conclusion="UI에서 자동 또는 주제 모드로 실행하면 거시/시장구조 playbook으로 처리합니다.",
        execution_meta=ExecutionMeta(
            extras={
                "route_hint": "use_universal_topic",
                "asset_class": profile.asset_class,
                "direct_endpoint_guard": True,
                "error_type": "validation_error",
            }
        ),
    )


@router.post("", response_model=AnalysisResponse)
async def analyze_research_legacy(request: AnalysisRequest):
    return await analyze_research(request)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_research(request: AnalysisRequest):
    logger.info(f"Received API request for ticker: {request.ticker}")
    _validate_direct_ticker_request(request)
    guarded = _direct_non_company_response(request)
    if guarded is not None:
        return guarded
    try:
        response = await run_pipeline_async(request)
        if response.status == "failed":
            logger.error(f"Request finalized with failed state: {response.error_metadata}")
        return response
    except Exception as exc:
        logger.error(f"Unhandled exception during async API execution: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/universal")
async def universal_research(request: UniversalRequest) -> dict[str, Any]:
    logger.info("[UNIVERSAL] Received request ticker=%s mode_hint=%s", request.ticker, request.mode_hint)
    _validate_universal_request(request)
    try:
        result = await dispatch_async(request)
        payload = result.model_dump(mode="json")
        if isinstance(result, TopicResponse):
            payload["mode"] = result.mode
        elif isinstance(result, CompareResponse):
            payload["mode"] = "multi_ticker"
        else:
            payload["mode"] = "single_ticker"
        return payload
    except Exception as exc:
        logger.error(f"Unhandled exception during universal API execution: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/compare", response_model=CompareResponse)
async def compare_research(request: CompareRequest) -> CompareResponse:
    """Run the same question across multiple tickers and return a consolidated bundle."""

    started = time.time()
    seen: set[str] = set()
    tickers: list[str] = []
    for raw in request.tickers:
        ticker = (raw or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="At least 2 distinct tickers are required.")
    if len(tickers) > COMPARE_MAX_TICKERS:
        raise HTTPException(status_code=400, detail=f"Up to {COMPARE_MAX_TICKERS} tickers per compare request.")

    concurrency = max(1, min(request.concurrency, COMPARE_MAX_CONCURRENCY, len(tickers)))
    settings = load_settings()
    model_name = str(request.model or settings.primary_model or "").lower()
    is_local_ollama = "localhost" in settings.ollama_base_url or "127.0.0.1" in settings.ollama_base_url
    if is_local_ollama and any(marker in model_name for marker in ("qwen", "mistral", "fingpt")):
        concurrency = 1
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(ticker: str) -> tuple[str, AnalysisResponse]:
        async with semaphore:
            try:
                sub_request = AnalysisRequest(
                    ticker=ticker,
                    question=request.question,
                    sources=list(request.sources),
                    lookback_days=request.lookback_days,
                    top_k=request.top_k,
                    model=request.model,
                    output_language=request.output_language,
                    scenario_simulation_enabled=request.scenario_simulation_enabled,
                )
                return ticker, await run_pipeline_async(sub_request)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"[COMPARE] {ticker} failed: {exc}")
                return ticker, AnalysisResponse(
                    ticker=ticker,
                    question=request.question,
                    status="failed",
                    error_metadata=str(exc),
                    summary=f"{ticker} failed: {exc}" if request.output_language == "en" else f"{ticker} 실행 실패: {exc}",
                    sentiment="Neutral",
                    conclusion=(
                        "Pipeline exception during compare analysis."
                        if request.output_language == "en"
                        else "비교 분석 중 파이프라인 예외가 발생했습니다."
                    ),
                )

    pairs = await asyncio.gather(*(run_one(ticker) for ticker in tickers))
    return CompareResponse(
        question=request.question,
        tickers=tickers,
        results={ticker: response for ticker, response in pairs},
        elapsed_s=round(time.time() - started, 2),
        concurrency=concurrency,
    )


@router.post("/portfolio/risk", response_model=PortfolioRiskResponse)
async def portfolio_risk(request: PortfolioRiskRequest) -> PortfolioRiskResponse:
    """Deterministic portfolio concentration, factor exposure, and stress analysis."""

    return await asyncio.to_thread(analyze_portfolio_risk, request)


def _sse_pack(event: str, data: Any) -> bytes:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


async def _stream_with_runner(http_request: Request, runner):
    import queue as threadqueue

    q: threadqueue.Queue = threadqueue.Queue(maxsize=512)
    sentinel = object()

    def sink(event: dict[str, Any]) -> None:
        try:
            q.put_nowait(event)
        except threadqueue.Full:
            pass

    async def run_and_enqueue():
        try:
            response = await runner(sink)
            payload = response.model_dump(mode="json")
            if isinstance(response, TopicResponse):
                payload["mode"] = response.mode
            elif isinstance(response, CompareResponse):
                payload["mode"] = "multi_ticker"
            else:
                payload["mode"] = "single_ticker"
            q.put_nowait({"event": "result", "payload": payload})
        except Exception as exc:
            logger.error(f"[SSE] pipeline failed: {exc}")
            q.put_nowait({"event": "pipeline_failed", "reason": str(exc)})
        finally:
            q.put_nowait(sentinel)

    async def event_generator():
        task = asyncio.create_task(run_and_enqueue())
        try:
            yield _sse_pack("stream_open", {"ts": time.time()})
            request_stage_started = time.time()
            yield _sse_pack("stage_started", {"stage": "request"})
            yield _sse_pack(
                "stage_completed",
                {"stage": "request", "duration_s": round(time.time() - request_stage_started, 3)},
            )

            while True:
                try:
                    item = await asyncio.to_thread(q.get, True, 15.0)
                except threadqueue.Empty:
                    if await http_request.is_disconnected():
                        break
                    yield b": heartbeat\n\n"
                    continue

                if item is sentinel:
                    break

                event_name = item.get("event", "message")
                yield _sse_pack(event_name, item.get("payload", item))

                if await http_request.is_disconnected():
                    break
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/stream")
async def research_stream(request: AnalysisRequest, http_request: Request):
    logger.info(f"[SSE] Stream request for ticker: {request.ticker}")
    _validate_direct_ticker_request(request)
    guarded = _direct_non_company_response(request)
    if guarded is not None:
        async def immediate(_sink):
            return guarded

        return await _stream_with_runner(http_request, immediate)
    return await _stream_with_runner(
        http_request,
        lambda sink: run_pipeline_async(request, event_sink=sink),
    )


@router.post("/universal/stream")
async def universal_research_stream(request: UniversalRequest, http_request: Request):
    logger.info("[UNIVERSAL_SSE] Received request ticker=%s mode_hint=%s", request.ticker, request.mode_hint)
    _validate_universal_request(request)
    return await _stream_with_runner(
        http_request,
        lambda sink: dispatch_async(request, event_sink=sink),
    )
