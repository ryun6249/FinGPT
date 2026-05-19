from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from pipelines.backtest.validation import resolve_freshness_policy_request, validate_backtest_inputs
from pipelines.data_mart.scheduler import get_scheduler as get_data_mart_scheduler
from pipelines.data_mart.jobs.update_prices_daily import update_prices_daily
from pipelines.data_mart.storage.repository import data_health as data_mart_health
from pipelines.data_mart.storage.repository import get_prices as data_mart_get_prices
from pipelines.data_mart.storage.repository import latest_filings as data_mart_latest_filings
from pipelines.data_mart.storage.repository import latest_fundamentals as data_mart_latest_fundamentals
from pipelines.data_mart.storage.repository import latest_sec_financial_facts as data_mart_latest_sec_facts


router = APIRouter(prefix="/api/v1/data", tags=["data"])

_SEC_EMPTY_IS_COVERED_TICKERS = {
    "BTC-USD",
    "ETH-USD",
    "GLD",
    "HYG",
    "QQQ",
    "SPY",
    "TLT",
    "USO",
}


def _provider_empty_is_covered(row: dict[str, Any]) -> bool:
    """Return true for empty provider rows that are valid coverage, not failures."""

    status = str(row.get("status") or "").lower()
    if status != "empty" or row.get("error_message"):
        return False
    provider = str(row.get("provider") or "").lower()
    ticker = str(row.get("ticker") or "").upper()
    if provider == "sec_filings":
        return ticker in _SEC_EMPTY_IS_COVERED_TICKERS
    if provider == "google_news_rss":
        return True
    return False


def _normalize_provider_status(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if _provider_empty_is_covered(normalized):
        normalized["raw_status"] = normalized.get("status")
        normalized["status"] = "ok"
        normalized["coverage_status"] = "covered_empty"
        normalized["coverage_note"] = (
            "Provider returned no rows, but the asset is covered by price, macro, filing, or news evidence elsewhere."
        )
    return normalized


def _clean_optional_query(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _filter_rows_for_freshness(
    rows: list[dict[str, Any]],
    *,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    start = _clean_optional_query(start_date)
    end = _clean_optional_query(end_date)
    filtered = []
    for row in rows:
        row_date = str(row.get("date") or "")
        if start and row_date < start:
            continue
        if end and row_date > end:
            continue
        filtered.append(row)
    return filtered


@router.get("/health")
async def data_health() -> dict[str, Any]:
    """Structured data mart health, update history, provider status, and quality checks."""

    payload = await asyncio.to_thread(data_mart_health)
    raw_provider_rows = payload.get("recent_provider_status") or []
    provider_rows = [_normalize_provider_status(row) for row in raw_provider_rows]
    payload["recent_provider_status"] = provider_rows
    quality_rows = payload.get("recent_quality_checks") or []
    failed = [row for row in provider_rows if str(row.get("status") or "").lower() in {"failed", "error"}]
    stale = [row for row in quality_rows if str(row.get("status") or "").lower() in {"warn", "fail"}]
    covered_empty = [row for row in provider_rows if row.get("coverage_status") == "covered_empty"]
    counts = payload.get("table_counts") or {}
    fundamentals_rows = int(counts.get("fundamentals_snapshots") or 0)
    sec_fact_rows = int(counts.get("sec_financial_facts") or 0)
    sec_filing_rows = int(counts.get("filings") or 0)
    macro_observation_rows = int(counts.get("macro_observations") or 0)
    payload["summary"] = {
        "provider_rows": len(provider_rows),
        "failed_provider_rows": len(failed),
        "covered_empty_provider_rows": len(covered_empty),
        "quality_rows": len(quality_rows),
        "stale_or_failed_quality_rows": len(stale),
        "fundamentals_rows": fundamentals_rows,
        "fundamentals_available": fundamentals_rows > 0,
        "sec_filing_rows": sec_filing_rows,
        "sec_fact_rows": sec_fact_rows,
        "sec_data_available": sec_filing_rows > 0 or sec_fact_rows > 0,
        "macro_observation_rows": macro_observation_rows,
        "macro_series_with_observations": int(payload.get("macro_series_with_observations") or 0),
        "macro_data_available": macro_observation_rows > 0,
        "decision_status": "failed" if failed else ("partial" if stale else "ok"),
    }
    return payload


@router.get("/auto-refresh/status")
async def data_auto_refresh_status() -> dict[str, Any]:
    """Return in-process structured data auto-refresh scheduler status."""

    return {"status": "ok", "scheduler": get_data_mart_scheduler().status()}


@router.get("/prices/{ticker}")
async def data_prices(
    ticker: str,
    limit: int = 252,
    refresh: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    freshness_profile: str = "research_default",
    require_fresh_prices: bool | None = None,
    max_market_calendar_lag_days: int | None = None,
) -> dict[str, Any]:
    """Return normalized daily prices from the structured data mart."""

    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    limit = max(1, min(int(limit or 252), 5000))
    refresh_payload: dict[str, Any] = {"enabled": bool(refresh), "attempted": False}
    if refresh:
        clean_start = _clean_optional_query(start_date)
        clean_end = _clean_optional_query(end_date)
        try:
            result = await asyncio.to_thread(
                update_prices_daily,
                [clean_ticker],
                market="mixed",
                start_date=clean_start,
                end_date=clean_end,
            )
            refresh_payload = {
                "enabled": True,
                "attempted": True,
                "status": result.status,
                "run_id": result.run_id,
                "rows_inserted": int(result.rows_inserted or 0),
                "rows_updated": int(result.rows_updated or 0),
                "error": result.error_message,
                "start_date": clean_start,
                "end_date": clean_end,
            }
        except Exception as exc:  # noqa: BLE001
            refresh_payload = {
                "enabled": True,
                "attempted": True,
                "status": "failed",
                "error": str(exc),
                "start_date": clean_start,
                "end_date": clean_end,
            }
    rows = await asyncio.to_thread(data_mart_get_prices, clean_ticker, limit=limit)
    filtered_rows = _filter_rows_for_freshness(rows, start_date=start_date, end_date=end_date)
    freshness_request = {
        "freshness_profile": freshness_profile,
        "require_fresh_prices": require_fresh_prices,
        "max_market_calendar_lag_days": max_market_calendar_lag_days,
    }
    freshness_policy_request = resolve_freshness_policy_request(
        {key: value for key, value in freshness_request.items() if value is not None}
    )
    freshness_validation = validate_backtest_inputs(
        {clean_ticker: filtered_rows},
        **freshness_policy_request,
    )
    latest = rows[-1] if rows else None
    return {
        "status": "ok" if rows else "empty",
        "ticker": clean_ticker,
        "count": len(rows),
        "latest": latest,
        "items": rows,
        "refresh": refresh_payload,
        "freshness_policy": dict(freshness_validation.get("freshness_policy") or {}),
        "asset_freshness": dict(freshness_validation.get("asset_freshness") or {}).get(clean_ticker, {}),
        "stale": clean_ticker in set(freshness_validation.get("stale_assets") or []),
        "strict_freshness_violation": bool(freshness_validation.get("strict_freshness_violation")),
        "expected_latest_date": str(freshness_validation.get("expected_latest_date") or "unknown"),
        "market_calendar_lag_days": int((freshness_validation.get("market_calendar_lag_days") or {}).get(clean_ticker) or 0),
    }


@router.get("/fundamentals/{ticker}")
async def data_fundamentals(ticker: str) -> dict[str, Any]:
    """Return normalized fundamentals, valuation, and financial snapshot data."""

    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    item = await asyncio.to_thread(data_mart_latest_fundamentals, clean_ticker)
    if not item:
        return {
            "status": "empty",
            "ticker": clean_ticker,
            "message": "normalized fundamentals snapshot is not available yet",
        }
    return {"status": "ok", **item}


@router.get("/sec/{ticker}")
async def data_sec(ticker: str, limit: int = 50) -> dict[str, Any]:
    """Return SEC filings and companyfacts rows stored in the local data mart."""

    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise HTTPException(status_code=422, detail="ticker is required")
    bounded = max(1, min(int(limit or 50), 500))
    filings, facts = await asyncio.gather(
        asyncio.to_thread(data_mart_latest_filings, clean_ticker, forms=["10-K", "10-Q", "8-K"], limit=bounded),
        asyncio.to_thread(data_mart_latest_sec_facts, clean_ticker, limit=bounded),
    )
    return {
        "status": "ok" if filings or facts else "empty",
        "ticker": clean_ticker,
        "filing_count": len(filings),
        "fact_count": len(facts),
        "filings": filings,
        "facts": facts,
    }
