from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.schemas.macro import MacroBriefRequest, MacroRefreshRequest, MacroScenarioRequest
from pipelines.data_mart.jobs.update_macro_daily import update_macro_platform_data
from pipelines.data_mart.scheduler import get_scheduler as get_data_mart_scheduler
from pipelines.macro import macro_service as service
from pipelines.macro.dashboard import build_macro_dashboard
from pipelines.macro.provider_health import build_macro_provider_health
from pipelines.macro.scenario import run_macro_scenario


router = APIRouter(tags=["macro"])


def _not_found(entity: str, key: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{entity}_not_found:{key}")


def _update_result_payload(result) -> dict[str, Any]:
    return {
        "status": result.status,
        "run_id": result.run_id,
        "market": result.market,
        "provider": result.provider,
        "rows_inserted": result.rows_inserted,
        "rows_updated": result.rows_updated,
        "error_message": result.error_message,
        "providers": [
            {
                "provider": item.provider,
                "status": item.status,
                "rows": item.rows,
                "error": item.error,
                "detail": item.detail,
            }
            for item in result.providers
        ],
    }


def _scheduler_status() -> dict[str, Any]:
    try:
        return get_data_mart_scheduler().status()
    except Exception as exc:  # noqa: BLE001
        return {"enabled": False, "error": str(exc)}


async def _run_blocking(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/series")
async def list_series(include_disabled: bool = False) -> dict[str, Any]:
    return await _run_blocking(service.list_macro_series, include_disabled=include_disabled)


@router.get("/series/search")
async def search_series(
    q: str = Query(default=""),
    limit: int = Query(default=12, ge=1, le=50),
    include_disabled: bool = False,
) -> dict[str, Any]:
    result = await _run_blocking(service.search_macro_series, q, limit=limit, include_disabled=include_disabled)
    return result.model_dump(mode="json")


@router.get("/series/{series_id}")
async def get_series(series_id: str, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    try:
        result = await _run_blocking(service.get_macro_series, series_id, start_date=start_date, end_date=end_date)
        return result.model_dump(mode="json")
    except KeyError:
        raise _not_found("macro_series", series_id)


@router.get("/series/{series_id}/detail")
async def get_series_detail(
    series_id: str,
    observation_limit: int = Query(default=240, ge=0, le=5000),
) -> dict[str, Any]:
    try:
        result = await _run_blocking(service.get_macro_series_detail, series_id, observation_limit=observation_limit)
        return result.model_dump(mode="json")
    except KeyError:
        raise _not_found("macro_series", series_id)


@router.get("/overview")
async def get_overview(
    engine: str = Query(default="rules", pattern="^(rules|factor)$"),
    compact: bool = False,
    observation_limit: int = Query(default=120, ge=0, le=1000),
) -> dict[str, Any]:
    overview = await _run_blocking(service.get_macro_overview, regime_engine=engine)
    if compact:
        return await _run_blocking(service.compact_macro_payload, overview, observation_limit=observation_limit)
    return overview.model_dump(mode="json")


@router.get("/dashboard")
async def get_dashboard(
    engine: str = Query(default="rules", pattern="^(rules|factor)$"),
    observation_limit: int = Query(default=20, ge=0, le=120),
) -> dict[str, Any]:
    refresh_status = await _run_blocking(_scheduler_status)
    result = await _run_blocking(
        build_macro_dashboard,
        refresh_status=refresh_status,
        engine=engine,
        observation_limit=observation_limit,
    )
    return result.model_dump(mode="json")


@router.get("/category/{category}")
async def get_category(
    category: str,
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    try:
        if compact:
            return await _run_blocking(service.get_macro_category_summary, category, observation_limit=observation_limit)
        payload = await _run_blocking(service.get_macro_category, category)
        return payload
    except KeyError:
        raise _not_found("macro_category", category)


@router.get("/interest-rates")
async def get_interest_rates(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "interest_rates", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_interest_rates)
    return payload


@router.get("/inflation")
async def get_inflation(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "inflation", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_inflation)
    return payload


@router.get("/growth-labor")
async def get_growth_labor(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_growth_labor_summary, observation_limit=observation_limit)
    payload = await _run_blocking(service.get_growth_labor)
    return payload


@router.get("/housing-consumer")
async def get_housing_consumer(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "housing_consumer", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_housing_consumer)
    return payload


@router.get("/yield-curve")
async def get_yield_curve(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_yield_curve_summary, observation_limit=observation_limit)
    payload = await _run_blocking(service.get_yield_curve)
    return payload


@router.get("/liquidity-credit")
async def get_liquidity_credit(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "liquidity_credit", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_macro_category, "liquidity_credit")
    return payload


@router.get("/financial-conditions")
async def get_financial_conditions(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "financial_conditions", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_financial_conditions)
    return payload


@router.get("/fx-dollar")
async def get_fx_dollar(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "fx_dollar", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_fx_dollar)
    return payload


@router.get("/commodities")
async def get_commodities(
    compact: bool = False,
    observation_limit: int = Query(default=0, ge=0, le=1000),
) -> dict[str, Any]:
    if compact:
        return await _run_blocking(service.get_macro_category_summary, "commodities", observation_limit=observation_limit)
    payload = await _run_blocking(service.get_commodities)
    return payload


@router.get("/regime")
async def get_regime(engine: str = Query(default="rules", pattern="^(rules|factor)$")) -> dict[str, Any]:
    return await _run_blocking(service.get_macro_regime, engine=engine)


@router.get("/asset-impact")
async def get_asset_impact() -> dict[str, Any]:
    return await _run_blocking(service.get_asset_impact)


@router.get("/portfolio-policy-hints")
async def get_portfolio_policy_hints() -> dict[str, Any]:
    result = await _run_blocking(service.get_portfolio_policy_hints)
    return result.model_dump(mode="json")


@router.get("/research-context")
async def get_research_context(ticker: str | None = Query(default=None)) -> dict[str, Any]:
    result = await _run_blocking(service.get_macro_research_context, ticker=ticker)
    return result.model_dump(mode="json")


@router.post("/brief")
async def post_brief(request: MacroBriefRequest | None = None) -> dict[str, Any]:
    request = request or MacroBriefRequest()
    result = await _run_blocking(
        service.generate_macro_brief,
        include_prompt=request.include_prompt,
        use_llm=request.use_llm,
        model=request.model,
        timeout_s=request.timeout_s,
    )
    return result.model_dump(mode="json")


@router.get("/report")
async def get_report() -> dict[str, Any]:
    result = await _run_blocking(service.generate_macro_report)
    return result.model_dump(mode="json")


@router.get("/data-quality")
async def get_data_quality(
    scope: str = Query(default="all", pattern="^(all|overview)$"),
    include_disabled: bool = False,
) -> dict[str, Any]:
    return await _run_blocking(service.get_data_quality, scope=scope, include_disabled=include_disabled)


@router.get("/providers")
async def get_providers() -> dict[str, Any]:
    return await _run_blocking(service.get_provider_metadata)


@router.get("/countries")
async def get_countries() -> dict[str, Any]:
    return await _run_blocking(service.get_country_metadata)


@router.get("/health")
async def get_health() -> dict[str, Any]:
    return await _run_blocking(service.get_health)


@router.get("/provider-health")
async def get_provider_health() -> dict[str, Any]:
    scheduler_status = await _run_blocking(_scheduler_status)
    result = await _run_blocking(build_macro_provider_health, scheduler_status=scheduler_status)
    return result.model_dump(mode="json")


@router.post("/scenario")
async def post_scenario(request: MacroScenarioRequest | None = None) -> dict[str, Any]:
    result = await _run_blocking(run_macro_scenario, request or MacroScenarioRequest())
    return result.model_dump(mode="json")


@router.post("/refresh")
async def post_refresh(request: MacroRefreshRequest | None = None) -> dict[str, Any]:
    request = request or MacroRefreshRequest()
    try:
        result = await asyncio.to_thread(
            update_macro_platform_data,
            request.series_ids or None,
            providers=request.providers or None,
            include_disabled=request.include_disabled,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_days=request.lookback_days,
            dry_run=request.dry_run,
        )
    except KeyError as exc:
        raise _not_found("macro_series", str(exc).strip("'"))
    service.clear_macro_caches()
    data_quality = await _run_blocking(service.get_data_quality)
    return {
        "status": result.status,
        "refresh": _update_result_payload(result),
        "data_quality": data_quality.get("data_quality"),
    }


@router.get("/refresh/status")
async def get_refresh_status() -> dict[str, Any]:
    data_quality = await _run_blocking(service.get_data_quality)
    return {
        "status": "ok",
        "scheduler": await _run_blocking(_scheduler_status),
        "data_quality": data_quality.get("data_quality"),
    }
