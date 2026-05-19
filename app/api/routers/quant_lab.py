from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.routers.market_utils import clean_ticker_list
from core.schemas.quant import (
    QuantBacktestRequest,
    QuantBacktestResponse,
    QuantFeaturePreviewRequest,
    QuantFeaturePreviewResponse,
    QuantSignalGenerateRequest,
    QuantSignalGenerateResponse,
)
from pipelines.orchestration.quant_lab_pipeline import (
    ARTIFACT_ROOT,
    cleanup_backtest_exports,
    cleanup_cross_run_exports,
    compare_backtest_replay,
    compare_backtest_runs,
    export_storage_report,
    export_backtest_artifacts,
    feature_preview,
    load_backtest_artifact,
    list_backtest_runs,
    list_backtest_exports,
    list_replay_reports,
    preview_backtest_export_cleanup,
    preview_cross_run_export_cleanup,
    quant_config,
    run_quant_backtest,
    signal_preview,
    verify_backtest_export,
)
from pipelines.adapters.qlib_adapter import qlib_export_preview, qlib_status
from pipelines.backtest.validation import validate_backtest_inputs
from pipelines.data_mart.jobs.ensure_price_history import ensure_price_history
from pipelines.data_mart.jobs.update_prices_daily import update_prices_daily
from pipelines.data_mart.storage.repository import get_prices, price_availability
from pipelines.strategies.generator import generate_strategy_from_prompt
from pipelines.strategies.registry import get_strategy, list_strategies
from pipelines.strategies.storage import delete_strategy, load_strategy, migrate_strategy, save_strategy, validate_strategy


router = APIRouter(prefix="/api/v1/quant", tags=["quant_lab"])


class QuantUniverseResolveRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    freshness_profile: str = "research_default"
    require_fresh_prices: bool = False
    max_market_calendar_lag_days: int = Field(default=3, ge=0, le=30)
    refresh_stale: bool = False
    min_rows: int = Field(default=2, ge=1, le=5000)
    hydrate_missing: bool = False
    max_hydrate_assets: int = Field(default=750, ge=0, le=1000)
    hydrate_batch_size: int = Field(default=40, ge=1, le=100)

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, value: Any) -> list[str]:
        return clean_ticker_list(value)

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


class QuantStrategyGenerateRequest(BaseModel):
    prompt: str = Field(default="", max_length=5000)
    context: dict[str, Any] = Field(default_factory=dict)
    use_local_llm: bool = True
    timeout_s: float = Field(default=45.0, ge=4.0, le=45.0)

    @field_validator("prompt", mode="before")
    @classmethod
    def _clean_prompt(cls, value: Any) -> str:
        return str(value or "").strip()


class QuantRunCompareRequest(BaseModel):
    run_ids: list[str] = Field(default_factory=list, min_length=2, max_length=2)

    @field_validator("run_ids", mode="before")
    @classmethod
    def _clean_run_ids(cls, value: Any) -> list[str]:
        raw = value.replace(",", " ").split() if isinstance(value, str) else list(value or [])
        return [str(item or "").strip() for item in raw if str(item or "").strip()]


@router.get("/config")
async def get_quant_config() -> dict[str, Any]:
    return quant_config()


@router.get("/qlib/status")
async def get_qlib_status() -> dict[str, Any]:
    return qlib_status()


@router.post("/qlib/export")
async def post_qlib_export_preview(payload: dict[str, Any]) -> dict[str, Any]:
    tickers = payload.get("tickers") or []
    if isinstance(tickers, str):
        tickers = tickers.replace(",", " ").split()
    return qlib_export_preview(
        tickers=list(tickers),
        start_date=payload.get("start_date"),
        end_date=payload.get("end_date"),
        provider_uri=payload.get("provider_uri"),
        dry_run=bool(payload.get("dry_run", True)),
    )


@router.post("/features/preview", response_model=QuantFeaturePreviewResponse)
async def post_feature_preview(request: QuantFeaturePreviewRequest) -> QuantFeaturePreviewResponse:
    return feature_preview(request)


@router.post("/signals/generate", response_model=QuantSignalGenerateResponse)
async def post_signal_generate(request: QuantSignalGenerateRequest) -> QuantSignalGenerateResponse:
    return signal_preview(request)


@router.post("/backtest", response_model=QuantBacktestResponse)
async def post_quant_backtest(request: QuantBacktestRequest) -> QuantBacktestResponse:
    return run_quant_backtest(request)


@router.post("/universe/resolve")
async def post_quant_universe_resolve(request: QuantUniverseResolveRequest) -> dict[str, Any]:
    freshness_policy_request = _resolve_universe_freshness_policy(request)
    hydration: dict[str, Any] = {
        "enabled": False,
        "attempted": False,
        "refresh_stale_enabled": bool(request.refresh_stale),
        "stale_refresh_attempted": False,
        "stale_candidates": [],
        "stale_refreshed": [],
        "stale_run_ids": [],
        "hydrated": [],
        "hydrated_count": 0,
        "still_unavailable": [],
        "still_unavailable_count": 0,
    }
    if request.hydrate_missing:
        resolved = ensure_price_history(
            request.tickers,
            start_date=request.start_date,
            end_date=request.end_date,
            min_rows=request.min_rows,
            hydrate_missing=True,
            max_hydrate_assets=request.max_hydrate_assets,
            batch_size=request.hydrate_batch_size,
        )
        availability = resolved["availability"]
        hydration = dict(resolved.get("hydration") or hydration)
        hydration.setdefault("refresh_stale_enabled", bool(request.refresh_stale))
        hydration.setdefault("stale_refresh_attempted", False)
        hydration.setdefault("stale_candidates", [])
        hydration.setdefault("stale_refreshed", [])
        hydration.setdefault("stale_run_ids", [])
    else:
        availability = price_availability(
            request.tickers,
            start_date=request.start_date,
            end_date=request.end_date,
            min_rows=request.min_rows,
        )
    freshness_validation = _validate_universe_freshness(request, freshness_policy_request)
    stale_assets = list(freshness_validation.get("stale_assets") or [])
    stale_refresh_result = _refresh_stale_universe_prices(
        request,
        stale_assets=stale_assets,
        freshness_validation=freshness_validation,
    )
    if stale_refresh_result.get("attempted"):
        hydration["refresh_stale_enabled"] = True
        hydration["stale_refresh_attempted"] = True
        hydration["stale_candidates"] = list(stale_refresh_result.get("candidates") or [])
        hydration["stale_run_ids"] = list(stale_refresh_result.get("run_ids") or [])
        hydration["rows_inserted"] = int(hydration.get("rows_inserted") or 0) + int(stale_refresh_result.get("rows_inserted") or 0)
        hydration["rows_updated"] = int(hydration.get("rows_updated") or 0) + int(stale_refresh_result.get("rows_updated") or 0)
        hydration["failed_tickers"] = {
            **(hydration.get("failed_tickers") if isinstance(hydration.get("failed_tickers"), dict) else {}),
            **(stale_refresh_result.get("failed_tickers") if isinstance(stale_refresh_result.get("failed_tickers"), dict) else {}),
        }
        availability = price_availability(
            request.tickers,
            start_date=request.start_date,
            end_date=request.end_date,
            min_rows=request.min_rows,
        )
        freshness_validation = _validate_universe_freshness(request, freshness_policy_request)
        refreshed_stale = [
            ticker
            for ticker in stale_assets
            if (freshness_validation.get("asset_freshness") or {}).get(ticker, {}).get("freshness_status") == "fresh"
        ]
        hydration["stale_refreshed"] = refreshed_stale
    items = [availability[ticker] for ticker in request.tickers if ticker in availability]
    available = [item["ticker"] for item in items if item.get("available")]
    unavailable = [item["ticker"] for item in items if not item.get("available")]
    strict_violation = bool(freshness_validation.get("strict_freshness_violation"))
    status = "success" if available and not unavailable and not strict_violation else ("partial" if available else "empty")
    return {
        "status": status,
        "requested_count": len(request.tickers),
        "available_count": len(available),
        "unavailable_count": len(unavailable),
        "available": available,
        "unavailable": unavailable,
        "items": items,
        "price_counts": {item["ticker"]: int(item.get("row_count") or 0) for item in items},
        "latest_price_dates": {item["ticker"]: item.get("latest_date") or "" for item in items if item.get("latest_date")},
        "date_range": {"start": request.start_date, "end": request.end_date},
        "min_rows": request.min_rows,
        "hydration": hydration,
        "freshness_policy": dict(freshness_validation.get("freshness_policy") or {}),
        "asset_freshness": dict(freshness_validation.get("asset_freshness") or {}),
        "stale_assets": list(freshness_validation.get("stale_assets") or []),
        "strict_freshness_violation": strict_violation,
        "expected_latest_date": str(freshness_validation.get("expected_latest_date") or "unknown"),
        "market_calendar_lag_days": dict(freshness_validation.get("market_calendar_lag_days") or {}),
    }


@router.get("/backtests")
async def get_quant_backtests(limit: int = 20) -> dict[str, Any]:
    return list_backtest_runs(limit=limit)


@router.post("/backtests/compare")
async def post_quant_backtests_compare(request: QuantRunCompareRequest) -> dict[str, Any]:
    try:
        return compare_backtest_runs(request.run_ids)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/exports/storage")
async def get_quant_export_storage(limit: int = 20, stale_after_days: int = 30) -> dict[str, Any]:
    return export_storage_report(limit=limit, stale_after_days=stale_after_days)


@router.get("/exports/cleanup-preview")
async def get_quant_cross_run_export_cleanup_preview(
    keep_last_exports: int = 5,
    stale_after_days: int = 30,
    limit: int = 100,
) -> dict[str, Any]:
    try:
        return preview_cross_run_export_cleanup(
            keep_last_exports=keep_last_exports,
            stale_after_days=stale_after_days,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/exports/cleanup")
async def post_quant_cross_run_export_cleanup(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = payload or {}
        candidate_ids = payload.get("candidate_ids")
        if candidate_ids is None:
            candidate_ids = payload.get("candidates")
        return cleanup_cross_run_exports(
            preview_id=str(payload.get("preview_id") or ""),
            candidate_ids=candidate_ids if isinstance(candidate_ids, list) else [],
            keep_last_exports=payload.get("keep_last_exports", 5),
            stale_after_days=payload.get("stale_after_days", 30),
            limit=payload.get("limit", 100),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/backtest/{run_id}")
async def get_quant_backtest(run_id: str) -> dict[str, Any]:
    return _load_or_404(run_id, "manifest")


@router.get("/backtest/{run_id}/bundle")
async def get_quant_backtest_bundle(run_id: str) -> dict[str, Any]:
    manifest = _load_or_404(run_id, "manifest")
    return {
        "status": "success",
        "run_id": manifest.get("run_id") or run_id,
        "manifest": manifest,
        "config": _load_or_empty(run_id, "config", default={}),
        "metrics": _load_or_empty(run_id, "metrics", default={}),
        "diagnostics": _load_or_empty(run_id, "diagnostics", default={}),
        "equity_curve": _load_or_empty(run_id, "equity_curve", default=[]),
        "drawdown_curve": _load_or_empty(run_id, "drawdown_curve", default=[]),
        "trades": _load_or_empty(run_id, "trades", default=[]),
        "signals": _load_or_empty(run_id, "signals", default=[]),
        "weights": _load_or_empty(run_id, "weights", default=[]),
        "replay_report": _load_or_empty(run_id, "replay_report", default={}),
        "replay_reports": _replay_reports_or_empty(run_id),
    }


@router.post("/backtest/{run_id}/replay")
async def post_quant_backtest_replay(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = payload or {}
        return compare_backtest_replay(
            run_id,
            tolerances=payload.get("tolerances") if isinstance(payload.get("tolerances"), dict) else None,
            persist_report=bool(payload.get("persist_report", True)),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest artifact not found: {run_id}")


@router.get("/backtest/{run_id}/replay-reports")
async def get_quant_backtest_replay_reports(run_id: str, limit: int = 20) -> dict[str, Any]:
    try:
        return list_replay_reports(run_id, limit=limit)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest artifact not found: {run_id}")


@router.post("/backtest/{run_id}/export")
async def post_quant_backtest_export(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = payload or {}
        return export_backtest_artifacts(
            run_id,
            export_format=str(payload.get("format") or "jsonl"),
            keep_last_exports=payload.get("keep_last_exports"),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest artifact not found: {run_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/backtest/{run_id}/exports")
async def get_quant_backtest_exports(run_id: str, limit: int = 20) -> dict[str, Any]:
    try:
        return list_backtest_exports(run_id, limit=limit)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest artifact not found: {run_id}")


@router.get("/backtest/{run_id}/exports/cleanup-preview")
async def get_quant_backtest_export_cleanup_preview(run_id: str, keep_last_exports: int = 5) -> dict[str, Any]:
    try:
        return preview_backtest_export_cleanup(run_id, keep_last_exports=keep_last_exports)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest export not found: {run_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backtest/{run_id}/exports/cleanup")
async def post_quant_backtest_export_cleanup(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = payload or {}
        return cleanup_backtest_exports(
            run_id,
            keep_last_exports=payload.get("keep_last_exports", 5),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest export not found: {run_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backtest/{run_id}/export/verify")
async def post_quant_backtest_export_verify(run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        payload = payload or {}
        return verify_backtest_export(
            run_id,
            export_manifest_path=payload.get("export_manifest_path") or payload.get("manifest_path"),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest export not found: {run_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/backtest/{run_id}/metrics")
async def get_quant_backtest_metrics(run_id: str) -> dict[str, Any]:
    return _load_or_404(run_id, "metrics")


@router.get("/backtest/{run_id}/diagnostics")
async def get_quant_backtest_diagnostics(run_id: str) -> dict[str, Any]:
    return _load_or_404(run_id, "diagnostics")


@router.get("/backtest/{run_id}/equity-curve")
async def get_quant_backtest_equity_curve(run_id: str) -> list[dict[str, Any]]:
    payload = _load_or_404(run_id, "equity_curve")
    return payload if isinstance(payload, list) else []


@router.get("/backtest/{run_id}/drawdown-curve")
async def get_quant_backtest_drawdown_curve(run_id: str) -> list[dict[str, Any]]:
    payload = _load_or_404(run_id, "drawdown_curve")
    return payload if isinstance(payload, list) else []


@router.get("/backtest/{run_id}/trades")
async def get_quant_backtest_trades(run_id: str) -> list[dict[str, Any]]:
    payload = _load_or_404(run_id, "trades")
    return payload if isinstance(payload, list) else []


@router.get("/backtest/{run_id}/signals")
async def get_quant_backtest_signals(run_id: str) -> list[dict[str, Any]]:
    payload = _load_or_404(run_id, "signals")
    return payload if isinstance(payload, list) else []


@router.get("/backtest/{run_id}/weights")
async def get_quant_backtest_weights(run_id: str) -> list[dict[str, Any]]:
    payload = _load_or_404(run_id, "weights")
    return payload if isinstance(payload, list) else []


@router.post("/strategy/save")
async def post_strategy_save(payload: dict[str, Any]) -> dict[str, Any]:
    path = save_strategy(payload, ARTIFACT_ROOT.parent / "strategies")
    strategy = load_strategy(path.stem, ARTIFACT_ROOT.parent / "strategies") or payload
    return {"status": "success", "path": str(path), "strategy": strategy}


@router.post("/strategy/dry-run")
async def post_strategy_dry_run(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        strategy = validate_strategy(payload)
    except ValueError as exc:
        return {"status": "failed", "valid": False, "warnings": [str(exc)]}
    features = strategy.get("features") if isinstance(strategy.get("features"), dict) else {}
    feature_ids = [
        str(spec.get("id") or feature_id).strip().lower()
        for feature_id, spec in features.items()
        if isinstance(spec, dict)
    ]
    supported = {item.get("factor_id") for item in quant_config()["factors"]}
    missing_features = [feature_id for feature_id in feature_ids if feature_id not in supported and feature_id != "research_score"]
    return {
        "status": "success" if not missing_features else "partial",
        "valid": not missing_features,
        "strategy": strategy,
        "diagnostics": {
            "feature_ids": feature_ids,
            "missing_features": missing_features,
            "execution_trade_at": (strategy.get("execution") or {}).get("trade_at"),
            "lookahead_safe": (strategy.get("execution") or {}).get("trade_at") == "next_bar_close",
            "schema_version": strategy.get("schema_version"),
            "strategy_version": strategy.get("strategy_version"),
            "migration_history": strategy.get("migration_history") or [],
        },
    }


@router.post("/strategy/generate")
async def post_strategy_generate(request: QuantStrategyGenerateRequest) -> dict[str, Any]:
    return generate_strategy_from_prompt(
        request.prompt,
        context=request.context,
        use_local_llm=request.use_local_llm,
        timeout_s=request.timeout_s,
    )


@router.post("/strategy/migrate")
async def post_strategy_migrate(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        strategy = migrate_strategy(payload, touch=False)
    except ValueError as exc:
        return {"status": "failed", "valid": False, "warnings": [str(exc)]}
    return {
        "status": "success",
        "valid": True,
        "strategy": strategy,
        "migrations": strategy.get("migration_history") or [],
    }


@router.get("/strategy/list")
async def get_strategy_list() -> dict[str, Any]:
    user_root = ARTIFACT_ROOT.parent / "strategies"
    defaults = list_strategies()
    user_items = []
    if user_root.exists():
        for path in sorted(user_root.glob("*.json")):
            item = load_strategy(path.stem, user_root)
            if item:
                user_items.append(item)
    return {"status": "success", "items": defaults + user_items}


@router.get("/strategy/{strategy_id}")
async def get_strategy_detail(strategy_id: str) -> dict[str, Any]:
    user_strategy = load_strategy(strategy_id, ARTIFACT_ROOT.parent / "strategies")
    strategy = user_strategy or get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"strategy not found: {strategy_id}")
    return strategy


@router.delete("/strategy/{strategy_id}")
async def delete_strategy_detail(strategy_id: str) -> dict[str, Any]:
    deleted = delete_strategy(strategy_id, ARTIFACT_ROOT.parent / "strategies")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"strategy not found: {strategy_id}")
    return {"status": "success", "deleted": True, "strategy_id": strategy_id}


def _load_or_404(run_id: str, name: str) -> Any:
    try:
        return load_backtest_artifact(run_id, name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"quant backtest artifact not found: {run_id}/{name}")


def _load_or_empty(run_id: str, name: str, *, default: Any) -> Any:
    try:
        return load_backtest_artifact(run_id, name)
    except FileNotFoundError:
        return default


def _replay_reports_or_empty(run_id: str) -> dict[str, Any]:
    try:
        return list_replay_reports(run_id, limit=10)
    except FileNotFoundError:
        return {"status": "success", "run_id": run_id, "count": 0, "latest": {}, "items": []}


def _resolve_universe_freshness_policy(request: QuantUniverseResolveRequest) -> dict[str, Any]:
    profiles = quant_config().get("freshness_profiles") or {}
    profile = request.freshness_profile if request.freshness_profile in profiles else "research_default"
    defaults = profiles.get(profile) or {}
    fields_set = set(getattr(request, "model_fields_set", set()))
    require_fresh_prices = bool(defaults.get("require_fresh_prices", False))
    max_lag = int(defaults.get("max_market_calendar_lag_days", request.max_market_calendar_lag_days))
    if "require_fresh_prices" in fields_set:
        require_fresh_prices = bool(request.require_fresh_prices)
    if "max_market_calendar_lag_days" in fields_set:
        max_lag = int(request.max_market_calendar_lag_days)
    return {
        "freshness_profile": profile,
        "require_fresh_prices": require_fresh_prices,
        "max_market_calendar_lag_days": max_lag,
    }


def _validate_universe_freshness(
    request: QuantUniverseResolveRequest,
    freshness_policy_request: dict[str, Any],
) -> dict[str, Any]:
    prices_by_asset = {
        ticker: _filter_price_rows(get_prices(ticker, limit=5000), start_date=request.start_date, end_date=request.end_date)
        for ticker in request.tickers
    }
    return validate_backtest_inputs(prices_by_asset, **freshness_policy_request)


def _filter_price_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str | None,
    end_date: str | None,
) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        row_date = str(row.get("date") or "")
        if start_date and row_date < start_date:
            continue
        if end_date and row_date > end_date:
            continue
        filtered.append(row)
    return filtered


def _refresh_stale_universe_prices(
    request: QuantUniverseResolveRequest,
    *,
    stale_assets: list[str],
    freshness_validation: dict[str, Any],
) -> dict[str, Any]:
    if not request.refresh_stale or not stale_assets:
        return {"attempted": False}
    policy = freshness_validation.get("freshness_policy") or {}
    expected_latest_date = str(policy.get("expected_latest_date") or "")
    if request.end_date and expected_latest_date and str(request.end_date) < expected_latest_date:
        return {"attempted": False, "skipped_reason": "historical_end_date"}
    latest_dates = dict(freshness_validation.get("latest_dates") or {})
    fetch_start = _stale_refresh_start_date([latest_dates.get(ticker) for ticker in stale_assets], request.start_date)
    result = update_prices_daily(
        stale_assets,
        market="mixed",
        start_date=fetch_start,
        end_date=request.end_date,
    )
    failed_tickers: dict[str, str] = {}
    for provider in result.providers:
        failed = provider.detail.get("failed_tickers") if isinstance(provider.detail, dict) else None
        if isinstance(failed, dict):
            failed_tickers.update({str(key).upper(): str(value) for key, value in failed.items()})
    return {
        "attempted": True,
        "candidates": stale_assets,
        "run_ids": [result.run_id],
        "rows_inserted": int(result.rows_inserted or 0),
        "rows_updated": int(result.rows_updated or 0),
        "failed_tickers": failed_tickers,
        "status": result.status,
        "error": result.error_message,
        "start_date": fetch_start,
        "end_date": request.end_date,
    }


def _stale_refresh_start_date(values: list[Any], request_start_date: str | None) -> str | None:
    parsed: list[date] = []
    for value in values:
        try:
            parsed.append(date.fromisoformat(str(value or "")[:10]))
        except ValueError:
            continue
    if parsed:
        return (min(parsed) - timedelta(days=7)).isoformat()
    return request_start_date
