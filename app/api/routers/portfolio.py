from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.routers.market_utils import clean_ticker_list, filter_price_rows, returns_from_price_rows
from pipelines.backtest.validation import resolve_freshness_policy_request, validate_backtest_inputs
from pipelines.data_mart.storage.repository import get_prices as data_mart_get_prices
from pipelines.portfolio.optimizer import optimize_portfolio


router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


class PortfolioOptimizeRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    method: str = Field(default="equal_weight")
    benchmark: str = Field(default="SPY")
    lookback_days: int = Field(default=252, ge=2, le=5000)
    start_date: str | None = Field(default=None)
    end_date: str | None = Field(default=None)
    max_weight: float = Field(default=1.0, gt=0, le=1.0)
    covariance_method: str = Field(default="sample")
    shrinkage_alpha: float = Field(default=0.1, ge=0.0, le=1.0)
    freshness_profile: str = "research_default"
    require_fresh_prices: bool = False
    max_market_calendar_lag_days: int = Field(default=3, ge=0, le=30)
    returns_by_asset: dict[str, list[float]] | None = None

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, value: Any) -> list[str]:
        return clean_ticker_list(value)

    @field_validator("method", mode="before")
    @classmethod
    def _clean_method(cls, value: Any) -> str:
        return str(value or "equal_weight").strip().lower()

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_benchmark(cls, value: Any) -> str:
        return str(value or "SPY").strip().upper() or "SPY"

    @field_validator("covariance_method", mode="before")
    @classmethod
    def _clean_covariance_method(cls, value: Any) -> str:
        return str(value or "sample").strip().lower() or "sample"

    @field_validator("freshness_profile", mode="before")
    @classmethod
    def _clean_freshness_profile(cls, value: Any) -> str:
        clean = str(value or "research_default").strip().lower()
        return clean if clean in {"research_default", "decision_review", "historical_lab"} else "research_default"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


@router.post("/optimize")
async def portfolio_optimize(request: PortfolioOptimizeRequest) -> dict[str, Any]:
    """Optimize portfolio weights from supplied returns or data-mart daily prices."""

    returns_by_asset = dict(request.returns_by_asset or {})
    benchmark_returns: list[float] | None = None
    prices_by_asset: dict[str, list[dict[str, Any]]] = {}
    missing: list[str] = []
    if not returns_by_asset:
        if not request.tickers:
            raise HTTPException(status_code=422, detail="tickers or returns_by_asset is required")
        for ticker in request.tickers:
            rows = await asyncio.to_thread(data_mart_get_prices, ticker, limit=request.lookback_days)
            rows = filter_price_rows(rows, start_date=request.start_date, end_date=request.end_date)
            prices_by_asset[ticker] = rows
            returns = returns_from_price_rows(rows)
            if returns:
                returns_by_asset[ticker] = returns
            else:
                missing.append(ticker)
        if request.benchmark:
            benchmark_rows = prices_by_asset.get(request.benchmark)
            if benchmark_rows is None:
                benchmark_rows = await asyncio.to_thread(data_mart_get_prices, request.benchmark, limit=request.lookback_days)
                benchmark_rows = filter_price_rows(benchmark_rows, start_date=request.start_date, end_date=request.end_date)
                prices_by_asset[request.benchmark] = benchmark_rows
            if request.benchmark not in returns_by_asset:
                benchmark_returns = returns_from_price_rows(benchmark_rows) or None
        freshness_policy_request = resolve_freshness_policy_request(request)
        freshness_validation = validate_backtest_inputs(
            prices_by_asset,
            **freshness_policy_request,
        )
        if freshness_validation.get("strict_freshness_violation"):
            warnings = _freshness_warnings(freshness_validation)
            return {
                "status": "failed",
                "weights": {},
                "method": request.method,
                "warnings": warnings,
                "missing_assets": missing,
                "data_status": "freshness_failed",
                "tickers": request.tickers,
                "benchmark": request.benchmark,
                "date_range": {"start": request.start_date, "end": request.end_date, "lookback_days": request.lookback_days},
                "return_counts": {ticker: len(returns) for ticker, returns in returns_by_asset.items()},
                **_freshness_payload(freshness_validation),
            }
    else:
        freshness_validation = {}
    try:
        result = await asyncio.to_thread(
            optimize_portfolio,
            returns_by_asset,
            method=request.method,
            max_weight=request.max_weight,
            covariance_method=request.covariance_method,
            shrinkage_alpha=request.shrinkage_alpha,
            benchmark=request.benchmark,
            benchmark_returns=benchmark_returns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result["missing_assets"] = missing
    result["data_status"] = "request_returns" if request.returns_by_asset else ("partial" if missing else "data_mart")
    result["tickers"] = request.tickers
    result["benchmark"] = request.benchmark
    result["date_range"] = {"start": request.start_date, "end": request.end_date, "lookback_days": request.lookback_days}
    result["return_counts"] = {ticker: len(returns) for ticker, returns in returns_by_asset.items()}
    if freshness_validation:
        result.update(_freshness_payload(freshness_validation))
        result["warnings"] = list(result.get("warnings") or []) + _freshness_warnings(freshness_validation, strict_only=False)
    return result


def _freshness_payload(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "freshness_policy": dict(validation.get("freshness_policy") or {}),
        "asset_freshness": dict(validation.get("asset_freshness") or {}),
        "stale_assets": list(validation.get("stale_assets") or []),
        "freshness_missing_assets": list(validation.get("missing_assets") or []),
        "freshness_excluded_assets": list(validation.get("excluded_assets") or []),
        "strict_freshness_violation": bool(validation.get("strict_freshness_violation")),
        "latest_price_dates": dict(validation.get("latest_dates") or {}),
        "expected_latest_date": str(validation.get("expected_latest_date") or "unknown"),
        "market_calendar_lag_days": dict(validation.get("market_calendar_lag_days") or {}),
        "price_counts": dict(validation.get("price_counts") or {}),
    }


def _freshness_warnings(validation: dict[str, Any], *, strict_only: bool = True) -> list[str]:
    warnings: list[str] = []
    if validation.get("strict_freshness_violation"):
        warnings.append("strict_freshness_violation")
    if not strict_only or validation.get("strict_freshness_violation"):
        stale = list(validation.get("stale_assets") or [])
        missing = list(validation.get("missing_assets") or [])
        excluded = list(validation.get("excluded_assets") or [])
        if stale:
            warnings.append(f"stale_assets:{','.join(stale)}")
        if missing:
            warnings.append(f"missing_assets:{','.join(missing)}")
        if excluded:
            warnings.append(f"insufficient_assets:{','.join(excluded)}")
    return warnings
