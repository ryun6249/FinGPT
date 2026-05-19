from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import ValidationError

from core.schemas.quantamental import (
    QuantamentalAIReportRequest,
    QuantamentalAnalysisRequest,
    QuantamentalCompareRequest,
    QuantamentalQARequest,
    QuantamentalScoreScreenRequest,
    QuantamentalScreenRequest,
)
from pipelines.quantamental import service
from pipelines.quantamental import watchlist_store


router = APIRouter(tags=["quantamental"])


def _parse_compare_tickers(raw: str) -> list[str]:
    return [item.strip().upper() for item in re.split(r"[\s,]+", str(raw or "")) if item.strip()]


def _validation_http_error(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.errors(include_context=False))


@router.get("/health")
async def get_health() -> dict[str, Any]:
    return service.health()


@router.get("/compare")
async def get_compare(
    tickers: str = Query(..., description="Comma-separated ticker list"),
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
    include_ai: bool = Query(default=False),
    use_llm: bool = Query(default=False),
    expand_peer_universe: bool = Query(default=False),
    peer_limit: int = Query(default=8, ge=2, le=20),
    force_refresh: bool = Query(default=False),
    output_language: str = Query(default="ko"),
) -> dict[str, Any]:
    try:
        request = QuantamentalCompareRequest(
            tickers=_parse_compare_tickers(tickers),
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            include_ai=include_ai,
            use_llm=use_llm,
            expand_peer_universe=expand_peer_universe,
            peer_limit=peer_limit,
            force_refresh=force_refresh,
            output_language=output_language,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc
    return service.compare(request)


@router.post("/compare")
async def post_compare(request: QuantamentalCompareRequest) -> dict[str, Any]:
    return service.compare(request)


@router.get("/screen/top-signals")
async def get_top_signal_screen(
    tickers: str | None = Query(default=None, description="Optional comma or space separated ticker list"),
    universe: str = Query(default="default_us_large_cap"),
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
    limit: int = Query(default=5, ge=1, le=10),
    include_ai: bool = Query(default=False),
    use_llm: bool = Query(default=False),
    refresh_stale: bool = Query(default=True),
    force_refresh: bool = Query(default=False),
    output_language: str = Query(default="ko"),
) -> dict[str, Any]:
    try:
        request = QuantamentalScreenRequest(
            tickers=_parse_compare_tickers(tickers or ""),
            universe=universe,  # type: ignore[arg-type]
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            limit=limit,
            include_ai=include_ai,
            use_llm=use_llm,
            refresh_stale=refresh_stale,
            force_refresh=force_refresh,
            output_language=output_language,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc
    return service.screen_top_signals(request)


@router.post("/screen/top-signals")
async def post_top_signal_screen(request: QuantamentalScreenRequest) -> dict[str, Any]:
    return service.screen_top_signals(request)


@router.get("/screen/by-score")
async def get_score_screen(
    tickers: str | None = Query(default=None, description="Optional comma or space separated ticker list"),
    universe: str = Query(default="default_us_large_cap"),
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
    score_key: str = Query(default="composite"),
    min_score: float = Query(default=70.0, ge=0.0, le=100.0),
    limit: int = Query(default=20, ge=1, le=50),
    include_ai: bool = Query(default=False),
    use_llm: bool = Query(default=False),
    refresh_stale: bool = Query(default=True),
    force_refresh: bool = Query(default=False),
    output_language: str = Query(default="ko"),
) -> dict[str, Any]:
    try:
        request = QuantamentalScoreScreenRequest(
            tickers=_parse_compare_tickers(tickers or ""),
            universe=universe,  # type: ignore[arg-type]
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            score_key=score_key,  # type: ignore[arg-type]
            min_score=min_score,
            limit=limit,
            include_ai=include_ai,
            use_llm=use_llm,
            refresh_stale=refresh_stale,
            force_refresh=force_refresh,
            output_language=output_language,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc
    return service.screen_by_score(request)


@router.post("/screen/by-score")
async def post_score_screen(request: QuantamentalScoreScreenRequest) -> dict[str, Any]:
    return service.screen_by_score(request)


@router.get("/compare/watchlists")
async def get_compare_watchlists() -> dict[str, Any]:
    return watchlist_store.list_watchlists()


@router.post("/compare/watchlists")
async def post_compare_watchlist(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return watchlist_store.upsert_watchlist(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/compare/watchlists/{item_id}")
async def put_compare_watchlist(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return watchlist_store.upsert_watchlist(payload, item_id=item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="quantamental compare watchlist not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/compare/watchlists/{item_id}")
async def delete_compare_watchlist(item_id: str) -> dict[str, Any]:
    try:
        return watchlist_store.delete_watchlist(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="quantamental compare watchlist not found") from exc


@router.get("/snapshots")
async def get_snapshots(
    ticker: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    return service.snapshots(ticker, limit=limit)


@router.post("/snapshots/retention")
async def post_snapshot_retention(
    ticker: str | None = Query(default=None),
    keep_last: int = Query(default=20, ge=1, le=500),
    dry_run: bool = Query(default=True),
) -> dict[str, Any]:
    return service.snapshot_retention(ticker, keep_last=keep_last, dry_run=dry_run)


@router.get("/snapshots/diff")
async def get_snapshot_diff(
    base_snapshot_id: str = Query(...),
    target_snapshot_id: str = Query(...),
) -> dict[str, Any]:
    return service.snapshot_diff(base_snapshot_id, target_snapshot_id)


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str) -> dict[str, Any]:
    return service.snapshot(snapshot_id)


@router.get("/snapshots/{snapshot_id}/export", response_model=None)
async def get_snapshot_export(
    snapshot_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
) -> Any:
    payload = service.snapshot_export(snapshot_id, fmt=format)
    if payload.get("status") != "ok":
        return payload
    headers = {"Content-Disposition": f'attachment; filename="{payload.get("filename")}"'}
    return Response(content=str(payload.get("content") or ""), media_type=str(payload.get("media_type") or "text/plain"), headers=headers)


@router.get("/sec/{ticker}")
async def get_sec_evidence(
    ticker: str,
    market: str = Query(default="US"),
    include_filing_text: bool = Query(default=False),
    filing_text_timeout_s: float = Query(default=5.0, ge=1.0, le=15.0),
) -> dict[str, Any]:
    return service.sec(ticker, market=market, include_filing_text=include_filing_text, filing_text_timeout_s=filing_text_timeout_s)


@router.post("/sec/global/hydrate")
async def post_global_sec_hydration(
    payload: dict[str, Any],
    dry_run: bool = Query(default=True),
    lookback_days: int = Query(default=365 * 5, ge=30, le=365 * 10),
    max_assets: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    tickers = payload.get("tickers") if isinstance(payload, dict) else []
    if isinstance(tickers, str):
        parsed_tickers = _parse_compare_tickers(tickers)
    else:
        parsed_tickers = [str(item or "").upper().strip() for item in (tickers or []) if str(item or "").strip()]
    return service.global_sec_hydration(
        parsed_tickers,
        all_known=bool(payload.get("all_known")) if isinstance(payload, dict) else False,
        dry_run=dry_run,
        lookback_days=lookback_days,
        max_assets=max_assets,
    )


@router.get("/resolve/{ticker}")
async def get_resolved_ticker(
    ticker: str,
    market: str = Query(default="GLOBAL"),
) -> dict[str, Any]:
    return service.resolve_ticker(ticker, market=market)


@router.get("/company/{ticker}")
async def get_company(
    ticker: str,
    market: str = Query(default="US"),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    return service.company(ticker, market=market, force_refresh=force_refresh)


@router.get("/fundamentals/{ticker}")
async def get_fundamentals(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    return service.fundamentals(ticker, market=market, period=period, years=years, force_refresh=force_refresh)


@router.get("/quant/{ticker}")
async def get_quant(
    ticker: str,
    market: str = Query(default="US"),
    lookback: str = Query(default="252"),
    force_refresh: bool = Query(default=False),
) -> dict[str, Any]:
    return service.quant(ticker, market=market, lookback=lookback, force_refresh=force_refresh)


@router.get("/factors/{ticker}")
async def get_factors(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
) -> dict[str, Any]:
    return service.factors(ticker, market=market, period=period, years=years, lookback=lookback)


@router.get("/risk/{ticker}")
async def get_risk(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
) -> dict[str, Any]:
    return service.risk(ticker, market=market, period=period, years=years, lookback=lookback)


@router.get("/composite/{ticker}")
async def get_composite(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
) -> dict[str, Any]:
    try:
        return service.composite(ticker, market=market, period=period, years=years, lookback=lookback, style=style)
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc


@router.get("/signal/{ticker}")
async def get_signal(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
) -> dict[str, Any]:
    try:
        return service.signal(ticker, market=market, period=period, years=years, lookback=lookback, style=style)
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc


@router.get("/analysis/{ticker}")
async def get_analysis(
    ticker: str,
    market: str = Query(default="US"),
    period: str = Query(default="annual"),
    years: int = Query(default=5, ge=1, le=10),
    lookback: str = Query(default="252"),
    style: str = Query(default="balanced"),
    include_ai: bool = Query(default=True),
    include_sec: bool = Query(default=True),
    use_llm: bool = Query(default=False),
    force_refresh: bool = Query(default=False),
    output_language: str = Query(default="ko"),
) -> dict[str, Any]:
    try:
        request = QuantamentalAnalysisRequest(
            ticker=ticker,
            market=market,  # type: ignore[arg-type]
            period=period,  # type: ignore[arg-type]
            years=years,
            lookback=lookback,
            style=style,  # type: ignore[arg-type]
            include_ai=include_ai,
            include_sec=include_sec,
            use_llm=use_llm,
            force_refresh=force_refresh,
            output_language=output_language,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise _validation_http_error(exc) from exc
    return service.analysis(request)


@router.post("/analysis")
async def post_analysis(request: QuantamentalAnalysisRequest) -> dict[str, Any]:
    return service.analysis(request)


@router.post("/ai/report")
async def post_ai_report(request: QuantamentalAIReportRequest) -> dict[str, Any]:
    return service.ai_report(request)


@router.post("/ai/qa")
async def post_ai_qa(request: QuantamentalQARequest) -> dict[str, Any]:
    return service.qa(request)
