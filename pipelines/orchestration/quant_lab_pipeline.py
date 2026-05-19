from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from core.config.settings import load_settings
from core.schemas.quant import (
    QuantArtifactManifest,
    QuantBacktestRequest,
    QuantBacktestResponse,
    QuantFeaturePreviewRequest,
    QuantFeaturePreviewResponse,
    QuantFeatureRow,
    QuantRunDiagnostics,
    QuantSignalGenerateRequest,
    QuantSignalGenerateResponse,
)
from pipelines.backtest.artifacts import build_run_id, write_backtest_artifacts
from pipelines.backtest.engine import (
    BacktestConfig,
    run_momentum_ranking_backtest,
    run_multi_asset_backtest,
    run_risk_adjusted_momentum_backtest,
)
from pipelines.backtest.artifact_exports import (
    cleanup_backtest_artifact_exports,
    cleanup_cross_run_artifact_exports,
    export_backtest_artifact_bundle,
    list_backtest_artifact_exports,
    preview_backtest_artifact_export_cleanup,
    preview_cross_run_artifact_export_cleanup,
    summarize_backtest_artifact_export_storage,
    verify_backtest_artifact_export,
)
from pipelines.backtest.validation import (
    FRESHNESS_PROFILES,
    resolve_freshness_policy_request,
    validate_backtest_inputs,
)
from pipelines.data_mart.storage.repository import get_prices
from pipelines.factors.catalog import compute_factor_latest, list_factor_catalog
from pipelines.factors.core import drawdown_series
from pipelines.output.run_history import get_run, list_runs
from pipelines.signals.research_score import evaluate_research_score
from pipelines.signals.rule_based import generate_latest_signals


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = PROJECT_ROOT / "data" / "quant_lab" / "backtests"
DEFAULT_FEATURES = [
    {"id": "momentum_63d"},
    {"id": "risk_adjusted_momentum_63d"},
    {"id": "realized_vol_21d"},
    {"id": "drawdown_current"},
    {"id": "ma_ratio_20_50"},
    {"id": "relative_strength_spy_63d"},
]
DEFAULT_REPLAY_TOLERANCES = {
    "default_abs": 1e-8,
    "metrics": {
        "total_return": 1e-8,
        "cagr": 1e-8,
        "annualized_volatility": 1e-8,
        "sharpe": 1e-8,
        "sortino": 1e-8,
        "max_drawdown": 1e-8,
        "turnover": 1e-8,
        "exposure": 1e-8,
    },
}
def quant_config() -> dict[str, Any]:
    return {
        "status": "success",
        "data_source": "data_mart:prices_daily",
        "factors": list_factor_catalog(),
        "signal_templates": [
            "buy_and_hold",
            "moving_average_trend",
            "volatility_targeting",
            "momentum_ranking",
            "risk_adjusted_momentum",
            "research_confirmed_momentum",
        ],
        "execution_assumptions": {
            "close_based_signals": "next_bar_close",
            "minimum_signal_shift_bars": 1,
        },
        "freshness_profiles": {
            key: {
                **value,
                "description": {
                    "research_default": "Warning-first local research profile.",
                    "decision_review": "Fail-closed review profile for current decision work.",
                    "historical_lab": "Historical experiments where old end dates are expected.",
                }[key],
            }
            for key, value in FRESHNESS_PROFILES.items()
        },
    }


def feature_preview(request: QuantFeaturePreviewRequest) -> QuantFeaturePreviewResponse:
    features = request.features or [dict(item) for item in DEFAULT_FEATURES]
    tickers = request.tickers
    if not tickers:
        return QuantFeaturePreviewResponse(
            status="empty",
            diagnostics=QuantRunDiagnostics(warnings=["ticker_universe_empty"]),
            warnings=["ticker_universe_empty"],
        )
    validation_tickers = _unique_strings(list(tickers) + [request.benchmark])
    prices_for_validation = _load_prices(
        validation_tickers,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    prices_by_asset = {ticker: list(prices_for_validation.get(ticker, [])) for ticker in tickers}
    freshness_policy = _resolve_freshness_policy_request(request)
    freshness_validation = validate_backtest_inputs(
        prices_for_validation,
        **freshness_policy,
    )
    asset_freshness = dict(freshness_validation.get("asset_freshness") or {})
    benchmark_rows = prices_for_validation.get(request.benchmark, [])
    benchmark_prices = _prices(benchmark_rows)
    rows: list[QuantFeatureRow] = []
    missing_assets: list[str] = []
    stale_assets: list[str] = []
    price_counts: dict[str, int] = {}
    latest_as_of = "unknown"
    warnings: list[str] = []
    for ticker in tickers:
        asset_rows = prices_by_asset.get(ticker, [])
        price_counts[ticker] = len(asset_rows)
        if not asset_rows:
            missing_assets.append(ticker)
            rows.append(
                QuantFeatureRow(
                    ticker=ticker,
                    as_of="unknown",
                    freshness_status="unknown",
                    diagnostics=["missing_price_history"],
                )
            )
            continue
        latest_as_of = max(latest_as_of, str(asset_rows[-1].get("date") or "unknown"))
        freshness = str((asset_freshness.get(ticker) or {}).get("freshness_status") or _freshness_status(asset_rows[-1]))
        if freshness == "stale":
            stale_assets.append(ticker)
        row_features: dict[str, float | None] = {}
        diagnostics: list[str] = []
        asset_prices = _prices(asset_rows)
        for spec in features:
            spec_dict = spec.model_dump() if hasattr(spec, "model_dump") else dict(spec)
            factor_id = str(spec_dict.get("id") or "").strip().lower()
            params = dict(spec_dict.get("params") or {})
            if spec_dict.get("lookback"):
                params["lookback"] = spec_dict.get("lookback")
            try:
                value = compute_factor_latest(
                    factor_id,
                    asset_prices,
                    benchmark_prices=benchmark_prices,
                    params=params,
                )
                row_features[factor_id] = round(value, 8) if value is not None else None
                if value is None:
                    diagnostics.append(f"{factor_id}:insufficient_data")
            except ValueError as exc:
                row_features[factor_id] = None
                diagnostics.append(str(exc))
        rows.append(
            QuantFeatureRow(
                ticker=ticker,
                as_of=str(asset_rows[-1].get("date") or "unknown"),
                features=row_features,
                freshness_status=freshness,
                diagnostics=diagnostics,
            )
        )
    strict_violation = bool(freshness_validation.get("strict_freshness_violation"))
    status = "success" if rows and not missing_assets else ("partial" if rows else "empty")
    if strict_violation and rows:
        status = "partial"
    missing_assets = _unique_strings(list(missing_assets) + list(freshness_validation.get("missing_assets") or []))
    stale_assets = _unique_strings(list(stale_assets) + list(freshness_validation.get("stale_assets") or []))
    price_counts = dict(freshness_validation.get("price_counts") or price_counts)
    if missing_assets:
        warnings.append(f"missing_assets:{','.join(missing_assets)}")
    if stale_assets:
        warnings.append(f"stale_assets:{','.join(stale_assets)}")
    if strict_violation:
        warnings.append("strict_freshness_violation")
    return QuantFeaturePreviewResponse(
        status=status,
        as_of=latest_as_of,
        rows=rows,
        diagnostics=QuantRunDiagnostics(
            missing_assets=missing_assets,
            stale_assets=stale_assets,
            price_counts=price_counts,
            latest_price_dates=dict(freshness_validation.get("latest_dates") or {}),
            expected_latest_date=str(freshness_validation.get("expected_latest_date") or "unknown"),
            market_calendar_lag_days=dict(freshness_validation.get("market_calendar_lag_days") or {}),
            asset_freshness=asset_freshness,
            freshness_policy=dict(freshness_validation.get("freshness_policy") or {}),
            warnings=warnings,
        ),
        warnings=warnings,
    )


def signal_preview(request: QuantSignalGenerateRequest) -> QuantSignalGenerateResponse:
    feature_response = feature_preview(request)
    feature_rows = [row.model_dump() for row in feature_response.rows]
    research = _resolve_research_scores(
        request.tickers,
        use_research_score=request.use_research_score,
        max_age_days=request.research_max_age_days,
    )
    rows = generate_latest_signals(feature_rows, template=request.template, research_scores=research["scores"])
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        provenance = research["provenance"].get(ticker)
        if not provenance:
            continue
        diagnostics = list(row.get("diagnostics") or [])
        diagnostics.append(f"research_score_status:{provenance.get('status')}")
        row["diagnostics"] = diagnostics
    return QuantSignalGenerateResponse(
        status=feature_response.status,
        as_of=feature_response.as_of,
        rows=rows,
        diagnostics=feature_response.diagnostics.model_copy(
            update={
                "research_score_used": bool(request.use_research_score),
                "research_score_status": research["status"],
                "research_score_provenance": research["provenance"],
                "fingpt_forecaster_signals": research["forecaster_signals"],
            }
        ),
        warnings=feature_response.warnings + list(research["warnings"]),
    )


def run_quant_backtest(request: QuantBacktestRequest) -> QuantBacktestResponse:
    tickers = request.tickers
    if not tickers:
        run_id = build_run_id(request.template, request.model_dump())
        return QuantBacktestResponse(
            run_id=run_id,
            status="empty",
            template=request.template,
            benchmark=request.benchmark,
            diagnostics=QuantRunDiagnostics(warnings=["ticker_universe_empty"]),
        )
    prices_by_asset = _load_prices(
        tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        limit=max(5000, request.lookback + 252),
    )
    freshness_policy = _resolve_freshness_policy_request(request)
    validation = validate_backtest_inputs(
        prices_by_asset,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
        **freshness_policy,
    )
    if validation.get("strict_freshness_violation"):
        run_id = build_run_id(request.template, request.model_dump())
        diagnostics = QuantRunDiagnostics(
            lookahead_safe=bool(validation.get("lookahead_safe")),
            signal_shift_bars=int(validation.get("signal_shift_bars") or 1),
            execution_assumption=str(validation.get("execution_assumption") or "next_bar_close"),
            data_source="data_mart:prices_daily",
            freshness_policy=dict(validation.get("freshness_policy") or {}),
            missing_assets=list(validation.get("missing_assets") or []),
            stale_assets=list(validation.get("stale_assets") or []),
            excluded_assets=list(validation.get("excluded_assets") or []),
            price_counts=dict(validation.get("price_counts") or {}),
            latest_price_dates=dict(validation.get("latest_dates") or {}),
            expected_latest_date=str(validation.get("expected_latest_date") or "unknown"),
            market_calendar_lag_days=dict(validation.get("market_calendar_lag_days") or {}),
            asset_freshness=dict(validation.get("asset_freshness") or {}),
            warnings=["strict_freshness_violation"],
        )
        return QuantBacktestResponse(
            run_id=run_id,
            status="failed",
            template=request.template,
            tickers=tickers,
            benchmark=request.benchmark,
            diagnostics=diagnostics,
        )
    unavailable_assets = _unique_strings(
        list(validation.get("missing_assets") or []) + list(validation.get("excluded_assets") or [])
    )
    if unavailable_assets:
        runnable_tickers = [ticker for ticker in tickers if ticker not in set(unavailable_assets)]
        if not runnable_tickers:
            run_id = build_run_id(request.template, request.model_dump())
            diagnostics = QuantRunDiagnostics(
                lookahead_safe=bool(validation.get("lookahead_safe")),
                signal_shift_bars=int(validation.get("signal_shift_bars") or 1),
                execution_assumption=str(validation.get("execution_assumption") or "next_bar_close"),
                data_source="data_mart:prices_daily",
                freshness_policy=dict(validation.get("freshness_policy") or {}),
                missing_assets=[],
                stale_assets=list(validation.get("stale_assets") or []),
                excluded_assets=unavailable_assets,
                price_counts=dict(validation.get("price_counts") or {}),
                latest_price_dates=dict(validation.get("latest_dates") or {}),
                expected_latest_date=str(validation.get("expected_latest_date") or "unknown"),
                market_calendar_lag_days=dict(validation.get("market_calendar_lag_days") or {}),
                asset_freshness=dict(validation.get("asset_freshness") or {}),
                warnings=["executable_price_universe_empty", f"excluded_assets:{','.join(unavailable_assets)}"],
            )
            return QuantBacktestResponse(
                run_id=run_id,
                status="failed",
                template=request.template,
                tickers=[],
                benchmark=request.benchmark,
                diagnostics=diagnostics,
            )
        tickers = runnable_tickers
        request = request.model_copy(update={"tickers": tickers})
        prices_by_asset = {ticker: prices_by_asset.get(ticker, []) for ticker in tickers}
        validation = validate_backtest_inputs(
            prices_by_asset,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            **freshness_policy,
        )
        validation["excluded_assets"] = _unique_strings(list(validation.get("excluded_assets") or []) + unavailable_assets)
        validation["warnings"] = [f"excluded_unavailable_assets:{','.join(unavailable_assets)}"]
    engine_strategy = _engine_strategy_for_template(request.template)
    if not engine_strategy:
        run_id = build_run_id(request.template, request.model_dump())
        return QuantBacktestResponse(
            run_id=run_id,
            status="failed",
            template=request.template,
            tickers=tickers,
            benchmark=request.benchmark,
            diagnostics=QuantRunDiagnostics(warnings=[f"unsupported_template:{request.template}"]),
        )
    config = BacktestConfig(
        strategy=engine_strategy,
        short_window=request.lookback,
        long_window=max(request.lookback * 2, request.lookback + 1),
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
        initial_capital=1.0,
    )
    try:
        if request.template == "risk_adjusted_momentum" and len(tickers) > 1:
            result = run_risk_adjusted_momentum_backtest(
                prices_by_asset,
                lookback=request.lookback,
                top_n=min(request.top_n, len(tickers)),
                rebalance_every=request.rebalance_every,
                config=config,
            )
        elif request.template == "momentum_ranking" and len(tickers) > 1:
            result = run_momentum_ranking_backtest(
                prices_by_asset,
                lookback=request.lookback,
                top_n=min(request.top_n, len(tickers)),
                rebalance_every=request.rebalance_every,
                config=config,
            )
        else:
            result = run_multi_asset_backtest(prices_by_asset, config)
    except ValueError as exc:
        run_id = build_run_id(request.template, request.model_dump())
        return QuantBacktestResponse(
            run_id=run_id,
            status="failed",
            template=request.template,
            tickers=tickers,
            benchmark=request.benchmark,
            diagnostics=QuantRunDiagnostics(warnings=[str(exc)]),
        )
    equity_curve = list(result.get("equity_curve") or [])
    drawdown_curve = _drawdown_curve(equity_curve)
    signal_response = signal_preview(
        QuantSignalGenerateRequest(
            tickers=tickers,
            benchmark=request.benchmark,
            start_date=request.start_date,
            end_date=request.end_date,
            template=request.template,
            features=[dict(item) for item in DEFAULT_FEATURES],
            freshness_profile=freshness_policy["freshness_profile"],
            require_fresh_prices=freshness_policy["require_fresh_prices"],
            max_market_calendar_lag_days=freshness_policy["max_market_calendar_lag_days"],
            use_research_score=request.use_research_score,
            research_max_age_days=request.research_max_age_days,
        )
    )
    signals = signal_response.model_dump(mode="json")["rows"]
    run_id = build_run_id(request.template, request.model_dump())
    diagnostics = QuantRunDiagnostics(
        lookahead_safe=bool(validation.get("lookahead_safe")),
        signal_shift_bars=int(validation.get("signal_shift_bars") or 1),
        execution_assumption=str(validation.get("execution_assumption") or "next_bar_close"),
        data_source="data_mart:prices_daily",
        freshness_policy=dict(validation.get("freshness_policy") or {}),
        missing_assets=list(validation.get("missing_assets") or []),
        stale_assets=list(validation.get("stale_assets") or []),
        excluded_assets=list(validation.get("excluded_assets") or []),
        price_counts=dict(validation.get("price_counts") or {}),
        latest_price_dates=dict(validation.get("latest_dates") or {}),
        expected_latest_date=str(validation.get("expected_latest_date") or "unknown"),
        market_calendar_lag_days=dict(validation.get("market_calendar_lag_days") or {}),
        asset_freshness=dict(validation.get("asset_freshness") or {}),
        research_score_used=bool(request.use_research_score),
        research_score_status=signal_response.diagnostics.research_score_status,
        research_score_provenance=signal_response.diagnostics.research_score_provenance,
        warnings=list(validation.get("warnings") or []) + list(result.get("warnings") or []) + list(signal_response.warnings or []),
    )
    artifact_config = _artifact_config(request, config=config, validation=validation)
    weights_payload = list(result.get("weights_history") or result.get("rebalance_snapshots") or result.get("selected_history") or [])
    artifact_paths = write_backtest_artifacts(
        run_id=run_id,
        root=ARTIFACT_ROOT,
        config=artifact_config,
        metrics=dict(result.get("metrics") or {}),
        diagnostics=diagnostics.model_dump(mode="json"),
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        trades=list(result.get("trades") or []),
        signals=signals,
        weights=weights_payload,
        data_snapshot=_data_snapshot(request, validation=validation),
    )
    return QuantBacktestResponse(
        run_id=run_id,
        status=str(result.get("status") or "failed"),
        template=request.template,
        tickers=tickers,
        benchmark=request.benchmark,
        date_range=dict(result.get("date_range") or {}),
        metrics=dict(result.get("metrics") or {}),
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        trades=list(result.get("trades") or []),
        signals=signals,
        weights=weights_payload,
        diagnostics=diagnostics,
        artifacts=QuantArtifactManifest(**artifact_paths),
    )


def load_backtest_artifact(run_id: str, name: str = "manifest") -> dict[str, Any]:
    clean = "".join(ch for ch in str(run_id or "") if ch.isalnum() or ch in {"_", "-"})
    if not clean:
        raise FileNotFoundError("run_id is required")
    path = ARTIFACT_ROOT / clean / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def replay_backtest_from_manifest(run_id: str) -> QuantBacktestResponse:
    config = load_backtest_artifact(run_id, "config")
    request_fields = set(QuantBacktestRequest.model_fields)
    request_payload = {key: value for key, value in config.items() if key in request_fields}
    return run_quant_backtest(QuantBacktestRequest(**request_payload))


def compare_backtest_replay(
    run_id: str,
    *,
    tolerances: dict[str, Any] | None = None,
    persist_report: bool = True,
) -> dict[str, Any]:
    original_manifest = load_backtest_artifact(run_id, "manifest")
    original_metrics = load_backtest_artifact(run_id, "metrics")
    replay = replay_backtest_from_manifest(run_id)
    replay_manifest = load_backtest_artifact(replay.run_id, "manifest") if replay.artifacts else {}
    replay_metrics = dict(replay.metrics or {})
    metric_deltas = _metric_deltas(original_metrics, replay_metrics)
    tolerance_policy = _resolve_replay_tolerances(tolerances)
    tolerance_failures = _replay_tolerance_failures(metric_deltas, tolerance_policy)
    config_hash_match = original_manifest.get("config_hash") == replay_manifest.get("config_hash")
    status = "success" if replay.status == "success" and config_hash_match and not tolerance_failures else "partial"
    report = {
        "schema_version": "quant_lab_replay_report_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "run_id": run_id,
        "replay_run_id": replay.run_id,
        "config_hash_match": config_hash_match,
        "original_config_hash": original_manifest.get("config_hash"),
        "replay_config_hash": replay_manifest.get("config_hash"),
        "original_code_version": original_manifest.get("code_version") or {},
        "current_code_version": replay_manifest.get("code_version") or {},
        "original_generated_at": original_manifest.get("generated_at") or "",
        "replay_generated_at": replay_manifest.get("generated_at") or "",
        "original_metrics": original_metrics,
        "replay_metrics": replay_metrics,
        "metric_deltas": metric_deltas,
        "tolerance_policy": tolerance_policy,
        "tolerance_passed": not tolerance_failures,
        "tolerance_failures": tolerance_failures,
        "diagnostics": {
            "replay_status": replay.status,
            "lookahead_safe": replay.diagnostics.lookahead_safe,
            "signal_shift_bars": replay.diagnostics.signal_shift_bars,
            "warnings": replay.diagnostics.warnings,
        },
    }
    if persist_report:
        report["report_path"] = _write_replay_report(run_id, report)
    report["report_history"] = list_replay_reports(run_id, limit=5)
    return report


def compare_backtest_runs(run_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    clean_ids = _clean_compare_run_ids(run_ids)
    primary = _run_compare_snapshot(clean_ids[0])
    comparison = _run_compare_snapshot(clean_ids[1])
    metrics = _compare_metric_payload(primary["metrics"], comparison["metrics"])
    config_differences = _config_differences(primary["config"], comparison["config"])
    diagnostics = {
        "lookahead_safe_all": bool(primary["diagnostics"].get("lookahead_safe"))
        and bool(comparison["diagnostics"].get("lookahead_safe")),
        "signal_shift_bars": {
            primary["run_id"]: primary["diagnostics"].get("signal_shift_bars"),
            comparison["run_id"]: comparison["diagnostics"].get("signal_shift_bars"),
        },
        "stale_assets": sorted(
            set(primary["diagnostics"].get("stale_assets") or [])
            | set(comparison["diagnostics"].get("stale_assets") or [])
        ),
        "missing_assets": sorted(
            set(primary["diagnostics"].get("missing_assets") or [])
            | set(comparison["diagnostics"].get("missing_assets") or [])
        ),
        "warning_count": len(primary["diagnostics"].get("warnings") or [])
        + len(comparison["diagnostics"].get("warnings") or []),
    }
    lineage = {
        "config_hash_match": primary["config_hash"] == comparison["config_hash"],
        "primary_config_hash": primary["config_hash"],
        "comparison_config_hash": comparison["config_hash"],
        "code_commit_match": _code_commit(primary["code_version"]) == _code_commit(comparison["code_version"]),
        "primary_code_version": primary["code_version"],
        "comparison_code_version": comparison["code_version"],
        "data_snapshot_match": _stable_compare_json(primary["data_snapshot"])
        == _stable_compare_json(comparison["data_snapshot"]),
    }
    return {
        "schema_version": "quant_lab_run_compare_v1",
        "status": "success",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_run_id": primary["run_id"],
        "comparison_run_id": comparison["run_id"],
        "runs": [primary, comparison],
        "metrics": metrics,
        "config_differences": config_differences,
        "diagnostics": diagnostics,
        "lineage": lineage,
    }


def export_backtest_artifacts(
    run_id: str,
    export_format: str = "jsonl",
    keep_last_exports: int | None = None,
) -> dict[str, Any]:
    return export_backtest_artifact_bundle(
        run_id=run_id,
        artifact_root=ARTIFACT_ROOT,
        export_format=export_format,
        keep_last_exports=keep_last_exports,
    )


def list_backtest_exports(run_id: str, limit: int = 20) -> dict[str, Any]:
    return list_backtest_artifact_exports(
        run_id=run_id,
        artifact_root=ARTIFACT_ROOT,
        limit=limit,
    )


def verify_backtest_export(
    run_id: str,
    export_manifest_path: str | None = None,
) -> dict[str, Any]:
    return verify_backtest_artifact_export(
        run_id=run_id,
        artifact_root=ARTIFACT_ROOT,
        export_manifest_path=export_manifest_path,
    )


def preview_backtest_export_cleanup(run_id: str, keep_last_exports: int | None = 5) -> dict[str, Any]:
    return preview_backtest_artifact_export_cleanup(
        run_id=run_id,
        artifact_root=ARTIFACT_ROOT,
        keep_last_exports=keep_last_exports,
    )


def cleanup_backtest_exports(run_id: str, keep_last_exports: int | None = 5) -> dict[str, Any]:
    return cleanup_backtest_artifact_exports(
        run_id=run_id,
        artifact_root=ARTIFACT_ROOT,
        keep_last_exports=keep_last_exports,
    )


def export_storage_report(limit: int = 20, stale_after_days: int | None = 30) -> dict[str, Any]:
    return summarize_backtest_artifact_export_storage(
        artifact_root=ARTIFACT_ROOT,
        limit=limit,
        stale_after_days=stale_after_days,
    )


def preview_cross_run_export_cleanup(
    keep_last_exports: int | None = 5,
    stale_after_days: int | None = 30,
    limit: int = 100,
) -> dict[str, Any]:
    return preview_cross_run_artifact_export_cleanup(
        artifact_root=ARTIFACT_ROOT,
        keep_last_exports=keep_last_exports,
        stale_after_days=stale_after_days,
        limit=limit,
    )


def cleanup_cross_run_exports(
    *,
    preview_id: str,
    candidate_ids: list[Any],
    keep_last_exports: int | None = 5,
    stale_after_days: int | None = 30,
    limit: int = 100,
) -> dict[str, Any]:
    return cleanup_cross_run_artifact_exports(
        artifact_root=ARTIFACT_ROOT,
        preview_id=preview_id,
        candidate_ids=candidate_ids,
        keep_last_exports=keep_last_exports,
        stale_after_days=stale_after_days,
        limit=limit,
    )


def list_replay_reports(run_id: str, limit: int = 20) -> dict[str, Any]:
    clean = "".join(ch for ch in str(run_id or "") if ch.isalnum() or ch in {"_", "-"})
    if not clean:
        raise FileNotFoundError("run_id is required")
    run_dir = ARTIFACT_ROOT / clean
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))
    limit = max(1, min(int(limit or 20), 100))
    reports_dir = run_dir / "replay_reports"
    items: list[dict[str, Any]] = []
    if reports_dir.exists():
        for path in sorted(reports_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            payload = _read_artifact_json(path, default={})
            if not isinstance(payload, dict):
                continue
            items.append(_replay_report_summary(payload, path))
            if len(items) >= limit:
                break
    latest = _read_artifact_json(run_dir / "replay_report.json", default={})
    latest_payload = latest if isinstance(latest, dict) else {}
    return {
        "status": "success",
        "run_id": clean,
        "count": len(items),
        "latest": _replay_report_summary(latest_payload, run_dir / "replay_report.json") if latest_payload else {},
        "items": items,
    }


def list_backtest_runs(limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    items: list[dict[str, Any]] = []
    if ARTIFACT_ROOT.exists():
        for run_dir in sorted(ARTIFACT_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not run_dir.is_dir():
                continue
            manifest_path = run_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            metrics = _read_artifact_json(run_dir / "metrics.json", default={})
            diagnostics = _read_artifact_json(run_dir / "diagnostics.json", default={})
            config = _read_artifact_json(run_dir / "config.json", default={})
            data_snapshot = dict(manifest.get("data_snapshot") or {})
            snapshot_freshness = _current_snapshot_freshness(data_snapshot, config=config, diagnostics=diagnostics)
            items.append(
                {
                    "run_id": manifest.get("run_id") or run_dir.name,
                    "generated_at": manifest.get("generated_at") or "",
                    "config_hash": manifest.get("config_hash") or "",
                    "code_version": manifest.get("code_version") or {},
                    "data_snapshot": {
                        "price_counts": data_snapshot.get("price_counts") or {},
                        "latest_price_dates": data_snapshot.get("latest_price_dates") or data_snapshot.get("latest_dates") or {},
                        "latest_as_of": data_snapshot.get("latest_as_of") or "unknown",
                        "expected_latest_date": data_snapshot.get("expected_latest_date") or "unknown",
                        "market_calendar_lag_days": data_snapshot.get("market_calendar_lag_days") or {},
                        "asset_freshness": data_snapshot.get("asset_freshness") or {},
                        "freshness_policy": data_snapshot.get("freshness_policy") or {},
                        "snapshot_freshness": snapshot_freshness,
                    },
                    "snapshot_freshness": snapshot_freshness,
                    "template": config.get("template") or "unknown",
                    "tickers": config.get("tickers") or [],
                    "benchmark": config.get("benchmark") or "",
                    "strategy_id": config.get("strategy_id") or "",
                    "freshness_policy": diagnostics.get("freshness_policy") or data_snapshot.get("freshness_policy") or {},
                    "costs": {
                        "transaction_cost_bps": config.get("transaction_cost_bps"),
                        "slippage_bps": config.get("slippage_bps"),
                    },
                    "status": "success" if metrics else "partial",
                    "metrics": {
                        "total_return": metrics.get("total_return"),
                        "cagr": metrics.get("cagr"),
                        "sharpe": metrics.get("sharpe"),
                        "max_drawdown": metrics.get("max_drawdown"),
                    },
                    "diagnostics": {
                        "lookahead_safe": diagnostics.get("lookahead_safe"),
                        "signal_shift_bars": diagnostics.get("signal_shift_bars"),
                        "missing_assets": diagnostics.get("missing_assets") or [],
                        "stale_assets": diagnostics.get("stale_assets") or [],
                    },
                    "replay_reports": list_replay_reports(manifest.get("run_id") or run_dir.name, limit=3)
                    if (run_dir / "replay_report.json").exists() or (run_dir / "replay_reports").exists()
                    else {"status": "success", "run_id": manifest.get("run_id") or run_dir.name, "count": 0, "latest": {}, "items": []},
                    "manifest": str(manifest_path),
                }
            )
            if len(items) >= limit:
                break
    return {"status": "success", "count": len(items), "items": items}


def _current_snapshot_freshness(
    data_snapshot: dict[str, Any],
    *,
    config: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_dates = dict(data_snapshot.get("latest_price_dates") or data_snapshot.get("latest_dates") or {})
    tickers = _unique_strings(
        list(config.get("tickers") or [])
        + ([config.get("benchmark")] if config.get("benchmark") else [])
        + list(latest_dates)
    )
    policy = dict((diagnostics or {}).get("freshness_policy") or data_snapshot.get("freshness_policy") or {})
    policy_request = resolve_freshness_policy_request(
        {
            "freshness_profile": policy.get("profile") or config.get("freshness_profile") or "research_default",
            "require_fresh_prices": True,
            "max_market_calendar_lag_days": policy.get("max_market_calendar_lag_days")
            if policy.get("max_market_calendar_lag_days") is not None
            else config.get("max_market_calendar_lag_days", 3),
        }
    )
    historical_end_date = str(config.get("end_date") or "").strip()
    current_expected = validate_backtest_inputs({}, **policy_request).get("expected_latest_date") or "unknown"
    if historical_end_date and current_expected != "unknown" and historical_end_date < str(current_expected):
        return {
            "status": "historical",
            "refresh_recommended": False,
            "historical_end_date": historical_end_date,
            "current_expected_latest_date": str(current_expected),
            "stale_assets": [],
            "missing_assets": [],
            "asset_freshness": {},
            "market_calendar_lag_days": {},
            "policy": policy_request,
            "detail": "snapshot_has_explicit_historical_end_date",
        }
    prices_by_asset: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        latest = str(latest_dates.get(ticker) or "").strip()
        prices_by_asset[ticker] = [{"date": latest}, {"date": latest}] if latest and latest != "unknown" else []
    validation = validate_backtest_inputs(prices_by_asset, **policy_request)
    stale_assets = list(validation.get("stale_assets") or [])
    missing_assets = list(validation.get("missing_assets") or [])
    excluded_assets = list(validation.get("excluded_assets") or [])
    status = "fresh"
    if not tickers:
        status = "unknown"
    elif missing_assets or excluded_assets:
        status = "partial"
    elif stale_assets:
        status = "stale"
    return {
        "status": status,
        "refresh_recommended": status in {"stale", "partial", "unknown"},
        "current_expected_latest_date": str(validation.get("expected_latest_date") or "unknown"),
        "latest_price_dates": dict(validation.get("latest_dates") or {}),
        "stale_assets": stale_assets,
        "missing_assets": missing_assets,
        "excluded_assets": excluded_assets,
        "asset_freshness": dict(validation.get("asset_freshness") or {}),
        "market_calendar_lag_days": dict(validation.get("market_calendar_lag_days") or {}),
        "policy": dict(validation.get("freshness_policy") or {}),
        "detail": "current_snapshot_audit",
    }


def _clean_compare_run_ids(run_ids: list[str] | tuple[str, ...]) -> list[str]:
    if not isinstance(run_ids, (list, tuple)):
        raise ValueError("run_ids must contain exactly two saved Quant Lab run ids")
    clean: list[str] = []
    for raw in run_ids:
        value = "".join(ch for ch in str(raw or "") if ch.isalnum() or ch in {"_", "-"})
        if value and value not in clean:
            clean.append(value)
    if len(clean) != 2:
        raise ValueError("run_ids must contain exactly two distinct saved Quant Lab run ids")
    return clean


def _run_compare_snapshot(run_id: str) -> dict[str, Any]:
    manifest = load_backtest_artifact(run_id, "manifest")
    config = load_backtest_artifact(run_id, "config")
    metrics = load_backtest_artifact(run_id, "metrics")
    diagnostics = load_backtest_artifact(run_id, "diagnostics")
    data_snapshot = dict(manifest.get("data_snapshot") or {})
    snapshot_freshness = _current_snapshot_freshness(data_snapshot, config=config, diagnostics=diagnostics)
    return {
        "run_id": manifest.get("run_id") or run_id,
        "generated_at": manifest.get("generated_at") or "",
        "template": config.get("template") or "unknown",
        "tickers": config.get("tickers") or [],
        "benchmark": config.get("benchmark") or "",
        "strategy_id": config.get("strategy_id") or "",
        "status": "success" if metrics else "partial",
        "metrics": metrics,
        "diagnostics": diagnostics,
        "config": _compare_config_summary(config),
        "config_hash": manifest.get("config_hash") or "",
        "code_version": manifest.get("code_version") or {},
        "data_snapshot": {
            "price_counts": data_snapshot.get("price_counts") or {},
            "latest_price_dates": data_snapshot.get("latest_price_dates") or data_snapshot.get("latest_dates") or {},
            "latest_as_of": data_snapshot.get("latest_as_of") or "unknown",
            "expected_latest_date": data_snapshot.get("expected_latest_date") or "unknown",
            "market_calendar_lag_days": data_snapshot.get("market_calendar_lag_days") or {},
            "asset_freshness": data_snapshot.get("asset_freshness") or {},
            "freshness_policy": data_snapshot.get("freshness_policy") or {},
            "snapshot_freshness": snapshot_freshness,
        },
        "snapshot_freshness": snapshot_freshness,
    }


def _compare_config_summary(config: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "strategy_id",
        "template",
        "tickers",
        "benchmark",
        "start_date",
        "end_date",
        "freshness_profile",
        "lookback",
        "top_n",
        "rebalance_every",
        "transaction_cost_bps",
        "slippage_bps",
        "use_research_score",
        "require_fresh_prices",
        "max_market_calendar_lag_days",
        "universe_policy",
        "survivorship_bias_warning",
    ]
    return {key: config.get(key) for key in keys if key in config}


def _compare_metric_payload(primary: dict[str, Any], comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = sorted(set(primary) | set(comparison))
    for key in keys:
        primary_value = _number_or_none(primary.get(key))
        comparison_value = _number_or_none(comparison.get(key))
        if primary_value is None and comparison_value is None:
            continue
        delta = None if primary_value is None or comparison_value is None else comparison_value - primary_value
        relative_delta = None
        if delta is not None and primary_value not in (None, 0):
            relative_delta = delta / abs(primary_value)
        rows.append(
            {
                "metric": key,
                "primary": primary_value,
                "comparison": comparison_value,
                "delta": delta,
                "relative_delta": relative_delta,
            }
        )
    return rows


def _config_differences(primary: dict[str, Any], comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(set(primary) | set(comparison)):
        left = primary.get(key)
        right = comparison.get(key)
        if _stable_compare_json(left) != _stable_compare_json(right):
            rows.append({"field": key, "primary": left, "comparison": right})
    return rows


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stable_compare_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def _code_commit(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("git_commit") or "")


def _read_artifact_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _metric_deltas(original: dict[str, Any], replay: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key in sorted(set(original) | set(replay)):
        try:
            old = float(original.get(key))
            new = float(replay.get(key))
        except (TypeError, ValueError):
            continue
        deltas[key] = round(new - old, 10)
    return deltas


def _resolve_replay_tolerances(tolerances: dict[str, Any] | None) -> dict[str, Any]:
    policy = {
        "default_abs": float(DEFAULT_REPLAY_TOLERANCES["default_abs"]),
        "metrics": dict(DEFAULT_REPLAY_TOLERANCES["metrics"]),
    }
    if not isinstance(tolerances, dict):
        return policy
    if "default_abs" in tolerances:
        try:
            policy["default_abs"] = max(0.0, float(tolerances["default_abs"]))
        except (TypeError, ValueError):
            pass
    metric_overrides = tolerances.get("metrics") if isinstance(tolerances.get("metrics"), dict) else tolerances
    for key, value in metric_overrides.items():
        if key == "default_abs" or key == "metrics":
            continue
        try:
            policy["metrics"][str(key)] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue
    return policy


def _replay_tolerance_failures(metric_deltas: dict[str, float], tolerance_policy: dict[str, Any]) -> list[dict[str, Any]]:
    default_abs = float(tolerance_policy.get("default_abs") or 0.0)
    metric_policy = tolerance_policy.get("metrics") if isinstance(tolerance_policy.get("metrics"), dict) else {}
    failures: list[dict[str, Any]] = []
    for metric, delta in sorted(metric_deltas.items()):
        tolerance = float(metric_policy.get(metric, default_abs))
        if abs(float(delta)) > tolerance:
            failures.append(
                {
                    "metric": metric,
                    "delta": delta,
                    "abs_delta": round(abs(float(delta)), 10),
                    "tolerance_abs": tolerance,
                }
            )
    return failures


def _write_replay_report(run_id: str, report: dict[str, Any]) -> str:
    clean = "".join(ch for ch in str(run_id or "") if ch.isalnum() or ch in {"_", "-"})
    if not clean:
        raise FileNotFoundError("run_id is required")
    run_dir = ARTIFACT_ROOT / clean
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = run_dir / "replay_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    status = "".join(ch for ch in str(report.get("status") or "unknown") if ch.isalnum() or ch in {"_", "-"})
    history_path = reports_dir / f"{stamp}_{status or 'unknown'}.json"
    latest_path = run_dir / "replay_report.json"
    report["report_path"] = str(history_path)
    report["latest_report_path"] = str(latest_path)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    history_path.write_text(encoded, encoding="utf-8")
    latest_path.write_text(encoded, encoding="utf-8")
    return str(history_path)


def _replay_report_summary(report: dict[str, Any], path: Path) -> dict[str, Any]:
    failures = report.get("tolerance_failures") if isinstance(report.get("tolerance_failures"), list) else []
    metric_deltas = report.get("metric_deltas") if isinstance(report.get("metric_deltas"), dict) else {}
    return {
        "generated_at": report.get("generated_at") or "",
        "status": report.get("status") or "unknown",
        "run_id": report.get("run_id") or "",
        "replay_run_id": report.get("replay_run_id") or "",
        "config_hash_match": bool(report.get("config_hash_match")),
        "tolerance_passed": bool(report.get("tolerance_passed")),
        "tolerance_failure_count": len(failures),
        "metric_deltas": metric_deltas,
        "report_path": str(path),
    }


def _resolve_freshness_policy_request(request: QuantFeaturePreviewRequest | QuantBacktestRequest) -> dict[str, Any]:
    return resolve_freshness_policy_request(request)


def _artifact_config(
    request: QuantBacktestRequest,
    *,
    config: BacktestConfig,
    validation: dict[str, Any],
) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    universe_policy = _infer_universe_policy(request)
    freshness_policy = dict(validation.get("freshness_policy") or {})
    if freshness_policy:
        payload["freshness_profile"] = freshness_policy.get("profile") or payload.get("freshness_profile")
        payload["require_fresh_prices"] = bool(freshness_policy.get("require_fresh_prices"))
        payload["max_market_calendar_lag_days"] = int(
            freshness_policy.get("max_market_calendar_lag_days")
            if freshness_policy.get("max_market_calendar_lag_days") is not None
            else payload.get("max_market_calendar_lag_days", 3)
        )
    payload.update(
        {
            "schema_version": "quant_lab_config_v1",
            "universe_policy": universe_policy,
            "survivorship_bias_warning": _survivorship_bias_warning(universe_policy),
            "expanded_features": [dict(item) for item in DEFAULT_FEATURES],
            "engine_config": {
                "strategy": config.strategy,
                "short_window": config.short_window,
                "long_window": config.long_window,
                "transaction_cost_bps": config.transaction_cost_bps,
                "slippage_bps": config.slippage_bps,
                "initial_capital": config.initial_capital,
            },
            "validation": validation,
        }
    )
    return payload


def _infer_universe_policy(request: QuantBacktestRequest) -> str:
    if len(request.tickers or []) <= 1:
        return "single_asset"
    return "user_supplied_static_list"


def _survivorship_bias_warning(universe_policy: str) -> str:
    if universe_policy == "point_in_time_verified":
        return ""
    return (
        "Universe membership is not verified as point-in-time. Treat results as exploratory "
        "unless delisted coverage and historical constituent membership are independently verified."
    )


def _data_snapshot(request: QuantBacktestRequest, *, validation: dict[str, Any]) -> dict[str, Any]:
    latest_dates = dict(validation.get("latest_dates") or {})
    return {
        "source": "data_mart:prices_daily",
        "tickers": list(request.tickers),
        "benchmark": request.benchmark,
        "requested_start_date": request.start_date,
        "requested_end_date": request.end_date,
        "price_counts": dict(validation.get("price_counts") or {}),
        "latest_dates": latest_dates,
        "latest_as_of": max(latest_dates.values()) if latest_dates else "unknown",
        "expected_latest_date": validation.get("expected_latest_date") or "unknown",
        "market_calendar_lag_days": dict(validation.get("market_calendar_lag_days") or {}),
        "asset_freshness": dict(validation.get("asset_freshness") or {}),
        "freshness_policy": dict(validation.get("freshness_policy") or {}),
        "missing_assets": list(validation.get("missing_assets") or []),
        "stale_assets": list(validation.get("stale_assets") or []),
        "excluded_assets": list(validation.get("excluded_assets") or []),
        "cost_model": dict(validation.get("cost_model") or {}),
    }


def _unique_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip().upper()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _engine_strategy_for_template(template: str) -> str | None:
    clean = str(template or "").strip().lower()
    return {
        "buy_and_hold": "buy_and_hold",
        "moving_average_trend": "moving_average",
        "volatility_targeting": "volatility_targeting",
        "momentum_ranking": "momentum_ranking",
        "risk_adjusted_momentum": "risk_adjusted_momentum",
        "research_confirmed_momentum": "moving_average",
    }.get(clean)


def _load_prices(
    tickers: list[str],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 5000,
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker in tickers:
        rows = get_prices(ticker, limit=limit)
        out[ticker] = _filter_rows(rows, start_date=start_date, end_date=end_date)
    return out


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
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


def _prices(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get("adjusted_close")
        if value is None:
            value = row.get("close")
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _freshness_status(row: dict[str, Any]) -> str:
    raw = str(row.get("date") or "")
    try:
        observed = date.fromisoformat(raw[:10])
    except ValueError:
        return "unknown"
    age_days = (datetime.now(timezone.utc).date() - observed).days
    return "fresh" if age_days <= 7 else "stale"


def _drawdown_curve(equity_curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[float] = []
    dates: list[str] = []
    for row in equity_curve:
        try:
            values.append(float(row.get("equity")))
            dates.append(str(row.get("date") or ""))
        except (TypeError, ValueError):
            continue
    return [
        {"date": row_date, "drawdown": round(drawdown, 8)}
        for row_date, drawdown in zip(dates, drawdown_series(values))
    ]


def _resolve_research_scores(
    tickers: list[str],
    *,
    use_research_score: bool,
    max_age_days: int,
) -> dict[str, Any]:
    if not use_research_score:
        return {"scores": {}, "provenance": {}, "forecaster_signals": {}, "status": "disabled", "warnings": []}
    settings = load_settings()
    scores: dict[str, float | None] = {}
    provenance: dict[str, dict[str, Any]] = {}
    forecaster_signals: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for ticker in tickers:
        payload = _latest_research_score_payload(settings.outputs_dir, ticker)
        evaluation = evaluate_research_score(payload, max_age_days=max_age_days)
        ticker_key = ticker.upper()
        provenance[ticker_key] = evaluation
        scores[ticker_key] = evaluation["score"]
        forecaster_signal = _build_forecaster_signal_payload(ticker_key, payload)
        if forecaster_signal:
            forecaster_signals[ticker_key] = forecaster_signal
        if evaluation["status"] != "fresh":
            warnings.append(f"{ticker_key}:research_score_{evaluation['status']}")
    return {
        "scores": scores,
        "provenance": provenance,
        "forecaster_signals": forecaster_signals,
        "status": _aggregate_research_status([item["status"] for item in provenance.values()]),
        "warnings": warnings,
    }


def _latest_research_score_payload(outputs_dir: Path, ticker: str) -> dict[str, Any] | None:
    runs = list_runs(outputs_dir=outputs_dir, ticker=ticker, limit=1)
    if not runs:
        return None
    latest = runs[0]
    run = get_run(outputs_dir=outputs_dir, run_id=str(latest.get("id") or latest.get("run_id") or ""))
    response = ((run or {}).get("artifacts") or {}).get("response") or {}
    response = response if isinstance(response, dict) else {}
    execution_meta = response.get("execution_meta") if isinstance(response.get("execution_meta"), dict) else {}
    extras = execution_meta.get("extras") if isinstance(execution_meta.get("extras"), dict) else {}
    fingpt_annotations = extras.get("fingpt_annotations") if isinstance(extras.get("fingpt_annotations"), dict) else {}
    annotations = fingpt_annotations.get("annotations")
    sentiment = str(latest.get("sentiment") or response.get("sentiment") or "").lower()
    confidence = latest.get("confidence")
    if confidence is None:
        confidence = response.get("confidence")
    score = _sentiment_to_score(sentiment, confidence)
    return {
        "score": score,
        "as_of": latest.get("created_at") or "",
        "run_id": latest.get("id") or latest.get("run_id") or "",
        "model": latest.get("model") or "",
        "prompt_version": response.get("prompt_version") or response.get("schema_version") or "unknown",
        "evidence_ids": _flatten_evidence_ids(
            list(response.get("bull_evidence_ids") or []) + list(response.get("bear_evidence_ids") or [])
        ),
        "annotations": annotations if isinstance(annotations, list) else [],
        "structured_metrics": _structured_metrics_payload(response, extras),
    }


def _build_forecaster_signal_payload(ticker: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    annotations = payload.get("annotations") if isinstance(payload.get("annotations"), list) else []
    if not annotations:
        return None
    structured_metrics = payload.get("structured_metrics") if isinstance(payload.get("structured_metrics"), dict) else {}
    try:
        from pipelines.fingpt.forecaster_features import build_forecaster_signal

        signal = build_forecaster_signal(
            ticker=ticker,
            annotations=annotations,
            structured_metrics=structured_metrics,
        )
        return signal.model_dump(mode="json")
    except Exception:
        return None


def _structured_metrics_payload(response: dict[str, Any], extras: dict[str, Any]) -> dict[str, Any]:
    for payload in (
        response.get("structured_metrics"),
        extras.get("structured_metrics"),
        extras.get("metrics"),
    ):
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _sentiment_to_score(sentiment: str, confidence: Any) -> float | None:
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.5
    conf = max(0.0, min(1.0, conf))
    if sentiment in {"bullish", "positive", "constructive"}:
        return conf
    if sentiment in {"bearish", "negative", "cautious"}:
        return -conf
    if sentiment in {"neutral", "mixed"}:
        return 0.0
    return None


def _flatten_evidence_ids(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        if isinstance(item, list):
            out.extend(_flatten_evidence_ids(item))
            continue
        clean = str(item or "").strip()
        if clean and clean not in out:
            out.append(clean)
    return out


def _aggregate_research_status(statuses: list[str]) -> str:
    if not statuses:
        return "unavailable"
    if any(status == "fresh" for status in statuses):
        return "fresh"
    for status in ["sparse_evidence", "expired", "invalid", "unavailable"]:
        if any(item == status for item in statuses):
            return status
    return "unavailable"
