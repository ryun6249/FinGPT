from __future__ import annotations

from typing import Any

from core.schemas.forecast import ForecastDatasetConfig, ForecastJobSubmitRequest, ForecastRunRequest, ForecastSourceContext, ForecastUniverseRunRequest
from core.schemas.quant import QuantModelProfile
from pipelines.forecast import jobs as forecast_jobs
from pipelines.forecast import service as forecast_service
from pipelines.forecast.common import now_iso, stable_hash
from pipelines.model_profiles.storage import validate_model_profile
from pipelines.strategies.storage import validate_strategy


SYNC_UNIVERSE_ASSET_LIMIT = 12
CROSS_SECTIONAL_RANK_SCHEMA_VERSION = "quant_model_lab_cross_sectional_rank_v1"


def profile_hash(profile: QuantModelProfile) -> str:
    return stable_hash(profile.model_dump(mode="json"), length=20)


def strategy_hash(strategy: dict[str, Any] | None) -> str:
    return stable_hash(strategy or {}, length=20)


def compile_forecast_request(
    profile: QuantModelProfile | dict[str, Any],
    *,
    strategy: dict[str, Any] | None = None,
    ticker: str | None = None,
) -> ForecastRunRequest:
    normalized = validate_model_profile(profile, touch=False)
    clean_strategy = validate_strategy(strategy) if strategy else {}
    selected_ticker = str(ticker or (normalized.tickers[0] if normalized.tickers else "SPY")).strip().upper() or "SPY"
    model_config = normalized.model_candidates[0]
    dataset_config = ForecastDatasetConfig(
        ticker=selected_ticker,
        universe_id=normalized.universe_id,
        benchmark=normalized.benchmark,
        start_date=normalized.start_date,
        end_date=normalized.end_date,
        frequency="1d",
        include_macro=normalized.include_macro,
        include_cross_asset=normalized.include_cross_asset,
        include_technical=True,
        data_source="data_mart:prices_daily",
        adjusted_price=True,
    )
    target_config = normalized.target_config.model_copy(update={"benchmark": normalized.benchmark})
    backtest_config = normalized.backtest_config.model_copy(update={"benchmark": normalized.benchmark})
    return ForecastRunRequest(
        dataset_config=dataset_config,
        feature_config=normalized.feature_config,
        target_config=target_config,
        validation_config=normalized.validation_config,
        model_config=model_config,
        signal_config=normalized.signal_config,
        backtest_config=backtest_config,
        source_context=ForecastSourceContext(
            source="quant_model_lab",
            strategy_id=str(clean_strategy.get("strategy_id") or normalized.strategy_id or ""),
            profile_id=normalized.profile_id,
            strategy_hash=strategy_hash(clean_strategy),
            profile_hash=profile_hash(normalized),
        ),
    )


def compile_universe_request(
    profile: QuantModelProfile | dict[str, Any],
    *,
    strategy: dict[str, Any] | None = None,
) -> ForecastUniverseRunRequest:
    normalized = validate_model_profile(profile, touch=False)
    tickers = normalized.tickers if normalized.universe_id == "custom" else []
    return ForecastUniverseRunRequest(
        universe_id=normalized.universe_id,
        tickers=tickers,
        request=compile_forecast_request(normalized, strategy=strategy),
        max_assets=normalized.max_assets,
        ranking_metric=normalized.ranking_metric,
        notes=f"quant_model_lab profile_id={normalized.profile_id} strategy_id={normalized.strategy_id}",
    )


def dry_run_model_profile(profile: QuantModelProfile | dict[str, Any], *, strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        normalized = validate_model_profile(profile, touch=False)
    except ValueError as exc:
        return {"status": "failed", "valid": False, "warnings": [str(exc)], "errors": [str(exc)]}

    clean_strategy: dict[str, Any] = {}
    if strategy:
        try:
            clean_strategy = validate_strategy(strategy)
        except ValueError as exc:
            errors.append(str(exc))
    elif normalized.strategy_id:
        warnings.append("strategy_definition_not_embedded")

    request = compile_forecast_request(normalized, strategy=clean_strategy or None)
    universe_request = compile_universe_request(normalized, strategy=clean_strategy or None)
    universe = forecast_service.resolve_universe(universe_request)
    if not universe.get("selected"):
        errors.append("model_profile_universe_empty")
    if normalized.run_mode in {"universe_per_asset", "cross_sectional_rank"} and int(universe.get("selected_count") or 0) > SYNC_UNIVERSE_ASSET_LIMIT:
        warnings.append(f"large_universe_requires_job:{universe.get('selected_count')}>{SYNC_UNIVERSE_ASSET_LIMIT}")

    valid = not errors
    return {
        "status": "success" if valid else "failed",
        "valid": valid,
        "profile": normalized.model_dump(mode="json"),
        "diagnostics": {
            "run_mode": normalized.run_mode,
            "profile_hash": profile_hash(normalized),
            "strategy_hash": strategy_hash(clean_strategy),
            "source_context": request.source_context.model_dump(mode="json"),
            "universe": universe,
            "selected_model": request.ml_model_config.model_dump(mode="json"),
            "target": request.target_config.model_dump(mode="json"),
            "validation": request.validation_config.model_dump(mode="json"),
            "execution_delay_bars": request.backtest_config.execution_delay_bars,
            "panel_ranker": _panel_ranker_diagnostics(normalized, universe) if normalized.run_mode == "cross_sectional_rank" else {},
        },
        "warnings": warnings,
        "errors": errors,
        "generated_at": now_iso(),
    }


def run_model_lab(profile: QuantModelProfile | dict[str, Any], *, strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = validate_model_profile(profile, touch=False)
    clean_strategy = validate_strategy(strategy) if strategy else {}
    if normalized.run_mode == "cross_sectional_rank":
        universe_request = compile_universe_request(normalized, strategy=clean_strategy or None)
        universe = forecast_service.resolve_universe(universe_request)
        if int(universe.get("selected_count") or 0) > SYNC_UNIVERSE_ASSET_LIMIT:
            return {
                "status": "failed",
                "errors": [f"model_lab_large_panel_requires_job:{universe.get('selected_count')}"],
                "warnings": [f"use /api/v1/quant/model-lab/job for more than {SYNC_UNIVERSE_ASSET_LIMIT} assets"],
                "universe": universe,
                "model_lab": _metadata(normalized, clean_strategy, mode="cross_sectional_rank"),
                "panel_ranker": _panel_ranker_diagnostics(normalized, universe),
                "generated_at": now_iso(),
            }
        payload = forecast_service.universe_run(universe_request)
        return _attach_cross_sectional_rank_metadata(payload, normalized, clean_strategy)
    if normalized.run_mode == "single_asset":
        payload = forecast_service.train(compile_forecast_request(normalized, strategy=clean_strategy or None))
        return _attach_model_lab_metadata(payload, normalized, clean_strategy, mode="single_asset")

    universe_request = compile_universe_request(normalized, strategy=clean_strategy or None)
    universe = forecast_service.resolve_universe(universe_request)
    if int(universe.get("selected_count") or 0) > SYNC_UNIVERSE_ASSET_LIMIT:
        return {
            "status": "failed",
            "errors": [f"model_lab_large_universe_requires_job:{universe.get('selected_count')}"],
            "warnings": [f"use /api/v1/quant/model-lab/job for more than {SYNC_UNIVERSE_ASSET_LIMIT} assets"],
            "universe": universe,
            "model_lab": _metadata(normalized, clean_strategy, mode="universe_per_asset"),
            "generated_at": now_iso(),
        }
    payload = forecast_service.universe_run(universe_request)
    return _attach_model_lab_metadata(payload, normalized, clean_strategy, mode="universe_per_asset")


def queue_model_lab_jobs(profile: QuantModelProfile | dict[str, Any], *, strategy: dict[str, Any] | None = None, runtime_budget_s: int = 900) -> dict[str, Any]:
    normalized = validate_model_profile(profile, touch=False)
    clean_strategy = validate_strategy(strategy) if strategy else {}
    if normalized.run_mode == "single_asset":
        request = compile_forecast_request(normalized, strategy=clean_strategy or None)
        job = forecast_jobs.submit_forecast_job(
            ForecastJobSubmitRequest(request=request, runtime_budget_s=runtime_budget_s, notes=_job_notes(normalized, clean_strategy, "single_asset"))
        )
        return {
            "status": "success",
            "job_mode": "single_asset",
            "jobs": [job],
            "count": 1,
            "model_lab": _metadata(normalized, clean_strategy, mode="single_asset"),
            "generated_at": now_iso(),
        }

    job_mode = "cross_sectional_rank" if normalized.run_mode == "cross_sectional_rank" else "universe_per_asset"
    universe_request = compile_universe_request(normalized, strategy=clean_strategy or None)
    universe = forecast_service.resolve_universe(universe_request)
    jobs: list[dict[str, Any]] = []
    for ticker in universe.get("selected") or []:
        request = compile_forecast_request(normalized, strategy=clean_strategy or None, ticker=str(ticker))
        jobs.append(
            forecast_jobs.submit_forecast_job(
                ForecastJobSubmitRequest(request=request, runtime_budget_s=runtime_budget_s, notes=_job_notes(normalized, clean_strategy, job_mode))
            )
        )
    payload = {
        "status": "success" if jobs else "failed",
        "job_mode": job_mode,
        "universe": universe,
        "jobs": jobs,
        "count": len(jobs),
        "model_lab": _metadata(normalized, clean_strategy, mode=job_mode),
        "errors": [] if jobs else ["model_lab_universe_empty"],
        "generated_at": now_iso(),
    }
    if job_mode == "cross_sectional_rank":
        payload["panel_ranker"] = {
            **_panel_ranker_diagnostics(normalized, universe),
            "status": "queued",
            "job_count": len(jobs),
            "aggregation": "rank jobs after all ticker forecasts finish; synchronous /run returns immediate panel ranking for smaller universes",
        }
        payload["warnings"] = ["panel_ranker_final_ranks_available_after_jobs_complete"] if jobs else []
    return payload


def _attach_model_lab_metadata(payload: dict[str, Any], profile: QuantModelProfile, strategy: dict[str, Any], *, mode: str) -> dict[str, Any]:
    payload = dict(payload or {})
    payload["model_lab"] = _metadata(profile, strategy, mode=mode)
    return payload


def _attach_cross_sectional_rank_metadata(payload: dict[str, Any], profile: QuantModelProfile, strategy: dict[str, Any]) -> dict[str, Any]:
    payload = _attach_model_lab_metadata(payload, profile, strategy, mode="cross_sectional_rank")
    panel_ranker = _panel_ranker_payload(payload, profile)
    payload["panel_ranker"] = panel_ranker
    summary = dict(payload.get("summary") or {})
    summary["panel_ranker_schema_version"] = CROSS_SECTIONAL_RANK_SCHEMA_VERSION
    summary["top_candidate"] = panel_ranker.get("top_candidate") or {}
    summary["rank_spread_to_second"] = (panel_ranker.get("score_distribution") or {}).get("spread_to_second")
    payload["summary"] = summary
    warnings = list(payload.get("warnings") or [])
    if panel_ranker.get("status") != "ready" and "panel_ranker_has_no_scored_candidates" not in warnings:
        warnings.append("panel_ranker_has_no_scored_candidates")
    payload["warnings"] = warnings
    return payload


def _metadata(profile: QuantModelProfile, strategy: dict[str, Any], *, mode: str) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "strategy_id": strategy.get("strategy_id") or profile.strategy_id,
        "profile_hash": profile_hash(profile),
        "strategy_hash": strategy_hash(strategy),
        "run_mode": mode,
        "advisory_only": True,
    }


def _panel_ranker_diagnostics(profile: QuantModelProfile, universe: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CROSS_SECTIONAL_RANK_SCHEMA_VERSION,
        "status": "configured" if universe.get("selected") else "blocked",
        "ranking_metric": profile.ranking_metric,
        "selected_count": int(universe.get("selected_count") or 0),
        "max_assets": profile.max_assets,
        "benchmark": profile.benchmark,
        "target": {
            "target_type": profile.target_config.target_type,
            "horizon": profile.target_config.horizon,
        },
        "validation": {
            "method": profile.validation_config.validation_method,
            "execution_delay_bars": profile.backtest_config.execution_delay_bars,
            "advisory_only": True,
            "requires_followup": ["single_asset_detail", "forecast_visualization", "portfolio_risk_budget"],
        },
    }


def _panel_ranker_payload(payload: dict[str, Any], profile: QuantModelProfile) -> dict[str, Any]:
    items = [dict(item) for item in payload.get("items") or [] if isinstance(item, dict)]
    scored = [
        item
        for item in items
        if item.get("status") == "success" and _as_float(item.get("rank_score")) is not None
    ]
    scored.sort(key=lambda item: (_as_float(item.get("rank_score")) or float("-inf")), reverse=True)
    for idx, item in enumerate(scored, start=1):
        item["rank"] = idx
    scores = [_as_float(item.get("rank_score")) for item in scored]
    scores = [score for score in scores if score is not None]
    top = scored[0] if scored else {}
    second = scored[1] if len(scored) > 1 else {}
    top_score = _as_float(top.get("rank_score"))
    second_score = _as_float(second.get("rank_score"))
    spread_to_second = top_score - second_score if top_score is not None and second_score is not None else None
    distribution = {
        "best": max(scores) if scores else None,
        "median": _median(scores),
        "worst": min(scores) if scores else None,
        "spread_to_second": spread_to_second,
    }
    top_candidate = _rank_candidate_summary(top) if top else {}
    status = "ready" if top_candidate else "blocked"
    headline = (
        f"{top_candidate.get('ticker')}가 {profile.ranking_metric} 기준 1위입니다."
        if top_candidate
        else "점수화된 후보가 없어 패널 랭킹을 확정할 수 없습니다."
    )
    return {
        "schema_version": CROSS_SECTIONAL_RANK_SCHEMA_VERSION,
        "status": status,
        "ranking_metric": profile.ranking_metric,
        "ranked_count": len(scored),
        "candidate_count": len(items),
        "blocked_count": max(0, len(items) - len(scored)),
        "top_candidate": top_candidate,
        "score_distribution": distribution,
        "ranked_tickers": [_rank_candidate_summary(item) for item in scored[:10]],
        "decision_template": {
            "headline": headline,
            "decision_use": "상위 후보를 매수 신호가 아니라 검증 우선순위로 사용하세요. 단일 Forecast 상세, 시각화, 포트폴리오 위험예산을 통과해야 의사결정 지원에 쓸 수 있습니다.",
            "why_not_obvious": [
                "동일 타깃, 동일 검증 설정, 동일 랭킹 기준으로 종목별 예측을 비교합니다.",
                "실패한 종목과 데이터 품질 상태를 랭킹에서 숨기지 않습니다.",
                "rank_score 격차와 신뢰도, 확률, 변동성을 같이 보존해 단순 수익률 정렬보다 감사 가능합니다.",
            ],
            "validation_required": [
                "상위 1-3개 후보의 단일 Forecast 결과와 leakage 상태 확인",
                "Forecast Visualization에서 실제값 대비 예측 산포와 시간별 안정성 확인",
                "Quant 백테스트와 포트폴리오 최적화에서 비용, 낙폭, 집중도 재검증",
            ],
        },
        "guardrails": {
            "advisory_only": True,
            "no_trade_execution": True,
            "ranking_source": "forecast_universe_run",
            "requires_oos_validation": True,
        },
    }


def _rank_candidate_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": item.get("rank"),
        "ticker": item.get("ticker"),
        "rank_score": item.get("rank_score"),
        "signal": item.get("signal"),
        "expected_return": item.get("expected_return"),
        "probability_up": item.get("probability_up"),
        "confidence": item.get("confidence"),
        "forecast_volatility": item.get("forecast_volatility"),
        "data_quality_status": item.get("data_quality_status"),
        "leakage_status": item.get("leakage_status"),
    }


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    clean = sorted(values)
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2


def _job_notes(profile: QuantModelProfile, strategy: dict[str, Any], mode: str) -> str:
    return (
        f"quant_model_lab mode={mode} profile_id={profile.profile_id} "
        f"strategy_id={strategy.get('strategy_id') or profile.strategy_id} profile_hash={profile_hash(profile)}"
    )
