from __future__ import annotations

from typing import Any

from core.schemas.forecast import (
    ForecastDatasetConfig,
    ForecastExperiment,
    ForecastResult,
    ForecastRunRequest,
    ForecastUniverseRunRequest,
    ModelEvaluation,
    ModelRegistryItem,
)
from core.utils.build_info import build_info
from pipelines.forecast.ai_interpretation import ai_provider_health, generate_ai_interpretation
from pipelines.forecast.backtester import run_forecast_backtest
from pipelines.forecast.common import now_iso, stable_hash
from pipelines.forecast.confidence import calculate_model_confidence
from pipelines.forecast.data_loader import data_quality, hydrate_dataset as _hydrate_dataset, load_benchmark_rows, load_price_rows, preview_dataset as _preview_dataset
from pipelines.forecast.data_snapshot import build_data_snapshot
from pipelines.forecast.diagnostics import build_forecast_context, drift_check_from_payload, model_comparison_rows
from pipelines.forecast.experiment_store import (
    list_experiments,
    list_registry_audit,
    list_registry,
    load_experiment,
    register_model,
    save_model_artifact,
    save_data_snapshot,
    save_experiment,
    update_model_status,
    verify_model_registry_artifact,
)
from pipelines.forecast.explainability import generate_explainability
from pipelines.forecast.feature_engineering import build_features
from pipelines.forecast.integrations.macro_context import build_macro_regime_artifact, get_macro_context
from pipelines.forecast.integrations.portfolio_signal import build_portfolio_advisory_signal
from pipelines.forecast.integrations.research_context import build_forecast_research_context
from pipelines.forecast.leakage import run_leakage_check
from pipelines.forecast.modeling import available_models, train_and_forecast
from pipelines.forecast.registry_policy import evaluate_promotion_policy
from pipelines.forecast.signal_evaluator import evaluate_signal_quality
from pipelines.forecast.signal_generator import generate_signal
from pipelines.forecast.target_builder import align_feature_target, build_target, latest_feature_row
from pipelines.forecast.visualization import build_visualization_payload


LAST_EXPERIMENT_BY_TICKER: dict[str, str] = {}


def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ml_forecast",
        "data_source": "data_mart:prices_daily",
        "execution_policy": "advisory_only_no_broker_execution",
        "validation_default": "walk_forward",
        "build": build_info(),
        "generated_at": now_iso(),
    }


def models() -> dict[str, Any]:
    payload = available_models()
    payload["generated_at"] = now_iso()
    return payload


def preview_dataset(config: ForecastDatasetConfig) -> dict[str, Any]:
    payload = _preview_dataset(config)
    prices = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    payload["data_snapshot"] = build_data_snapshot(dataset_config=config, price_rows=prices, benchmark_rows=benchmark)
    payload["generated_at"] = now_iso()
    return payload


def hydrate_dataset(request) -> dict[str, Any]:
    payload = _hydrate_dataset(
        request.dataset_config,
        include_benchmark=request.include_benchmark,
        include_macro=request.include_macro,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    payload["generated_at"] = now_iso()
    return payload


def build_feature_payload(dataset_config: ForecastDatasetConfig, feature_config) -> dict[str, Any]:
    prices = load_price_rows(dataset_config)
    benchmark = load_benchmark_rows(dataset_config)
    if dataset_config.include_macro and "macro" not in {group.lower() for group in feature_config.feature_groups}:
        feature_config = feature_config.model_copy(update={"feature_groups": [*feature_config.feature_groups, "macro"]})
    payload = build_features(prices, benchmark, feature_config)
    payload.update({"ticker": dataset_config.ticker, "benchmark": dataset_config.benchmark, "generated_at": now_iso()})
    return payload


def build_target_payload(dataset_config: ForecastDatasetConfig, target_config) -> dict[str, Any]:
    prices = load_price_rows(dataset_config)
    benchmark = load_benchmark_rows(dataset_config)
    payload = build_target(prices, benchmark, target_config)
    payload.update({"ticker": dataset_config.ticker, "benchmark": dataset_config.benchmark, "generated_at": now_iso()})
    return payload


def leakage_check_for_request(request: ForecastRunRequest) -> dict[str, Any]:
    prices = load_price_rows(request.dataset_config)
    benchmark = load_benchmark_rows(request.dataset_config)
    quality = data_quality(prices, benchmark_rows=benchmark, include_macro=request.dataset_config.include_macro)
    feature_config = request.feature_config
    if request.dataset_config.include_macro and "macro" not in {group.lower() for group in feature_config.feature_groups}:
        feature_config = feature_config.model_copy(update={"feature_groups": [*feature_config.feature_groups, "macro"]})
    feature_payload = build_features(prices, benchmark, feature_config)
    check = run_leakage_check(
        feature_config=feature_config,
        target_config=request.target_config,
        validation_config=request.validation_config,
        backtest_config=request.backtest_config,
        data_quality=quality,
        feature_names=feature_payload.get("feature_names") or [],
    )
    return {"status": check.status, "leakage_check": check.model_dump(mode="json"), "generated_at": now_iso()}


def run_experiment(request: ForecastRunRequest) -> dict[str, Any]:
    generated_at = now_iso()
    prices = load_price_rows(request.dataset_config)
    benchmark = load_benchmark_rows(request.dataset_config)
    quality = data_quality(prices, benchmark_rows=benchmark, include_macro=request.dataset_config.include_macro)
    feature_config = request.feature_config
    if request.dataset_config.include_macro and "macro" not in {group.lower() for group in feature_config.feature_groups}:
        feature_config = feature_config.model_copy(update={"feature_groups": [*feature_config.feature_groups, "macro"]})
    feature_payload = build_features(prices, benchmark, feature_config)
    data_snapshot = build_data_snapshot(
        dataset_config=request.dataset_config,
        price_rows=prices,
        benchmark_rows=benchmark,
        feature_payload=feature_payload,
    )
    data_snapshot_artifact = save_data_snapshot(data_snapshot)
    target_payload = build_target(prices, benchmark, request.target_config)
    aligned = align_feature_target(feature_payload, target_payload)
    leakage = run_leakage_check(
        feature_config=feature_config,
        target_config=request.target_config,
        validation_config=request.validation_config,
        backtest_config=request.backtest_config,
        data_quality=quality,
        feature_names=feature_payload.get("feature_names") or [],
    )
    experiment_id = f"exp_{stable_hash({'request': request.model_dump(mode='json'), 'generated_at': generated_at}, length=20)}"
    warnings = list(feature_payload.get("warnings") or []) + list(target_payload.get("warnings") or []) + quality.warnings
    if leakage.status == "fail":
        payload = _failed_payload(
            experiment_id=experiment_id,
            request=request,
            generated_at=generated_at,
            data_quality_result=quality,
            leakage=leakage,
            warnings=warnings + ["leakage_check_failed_training_blocked"],
            data_snapshot=data_snapshot,
            data_snapshot_artifact=data_snapshot_artifact,
        )
        save_experiment(experiment_id, payload)
        LAST_EXPERIMENT_BY_TICKER[request.dataset_config.ticker] = experiment_id
        return payload

    training = train_and_forecast(
        aligned,
        latest_feature_row(feature_payload),
        list(feature_payload.get("feature_names") or []),
        target_config=request.target_config,
        validation_config=request.validation_config,
        model_config=request.ml_model_config,
    )
    if training.get("status") != "success":
        payload = _failed_payload(
            experiment_id=experiment_id,
            request=request,
            generated_at=generated_at,
            data_quality_result=quality,
            leakage=leakage,
            warnings=warnings + list(training.get("warnings") or []),
            errors=list(training.get("errors") or ["model_training_failed"]),
            data_snapshot=data_snapshot,
            data_snapshot_artifact=data_snapshot_artifact,
        )
        save_experiment(experiment_id, payload)
        LAST_EXPERIMENT_BY_TICKER[request.dataset_config.ticker] = experiment_id
        return payload

    provisional_quality = evaluate_signal_quality(training.get("oos_predictions") or [], request.signal_config)
    confidence = calculate_model_confidence(
        aggregate_metrics=training.get("aggregate_metrics") or {},
        baseline_metrics=training.get("baseline_metrics") or {},
        stability_metrics=training.get("stability_metrics") or {},
        signal_quality=provisional_quality,
        leakage_check=leakage,
        data_quality=quality,
        overfitting=training.get("overfitting_check") or {},
    )
    forecast = ForecastResult(
        experiment_id=experiment_id,
        model_id=training["model_id"],
        ticker=request.dataset_config.ticker,
        as_of=str(prices[-1].get("date") if prices else ""),
        horizon=request.target_config.horizon,
        prediction_type=request.target_config.target_type,
        expected_return=training.get("expected_return"),
        median_return=training.get("median_return"),
        probability_up=training.get("probability_up"),
        probability_down=training.get("probability_down"),
        p10=training.get("p10"),
        p50=training.get("p50"),
        p90=training.get("p90"),
        forecast_volatility=training.get("forecast_volatility"),
        model_confidence=confidence,
        warnings=list(training.get("warnings") or []) + warnings,
        data_quality=quality,
    )
    macro_context = get_macro_context(request.dataset_config.ticker) if request.dataset_config.include_macro else {"status": "not_requested"}
    macro_regime = build_macro_regime_artifact(request.dataset_config.ticker, macro_context, feature_payload) if request.dataset_config.include_macro else {"status": "not_requested"}
    signal_context = build_forecast_context(forecast.model_dump(mode="json"), feature_payload, macro_context, macro_regime)
    signal = generate_signal(
        forecast,
        request.signal_config,
        leakage_check=leakage,
        data_quality=quality,
        context=signal_context,
    )
    forecast.signal = signal.signal
    forecast.signal_score = signal.signal_score
    signal_quality = evaluate_signal_quality(training.get("oos_predictions") or [], request.signal_config)
    backtest = run_forecast_backtest(
        prices,
        benchmark,
        training.get("oos_predictions") or [],
        signal_config=request.signal_config,
        backtest_config=request.backtest_config,
    )
    explainability = generate_explainability(training)
    visualization = build_visualization_payload(
        experiment_id=experiment_id,
        model_id=training["model_id"],
        ticker=request.dataset_config.ticker,
        price_rows=prices,
        training_result=training,
        backtest_result=backtest,
        feature_payload=feature_payload,
    )
    task = str(training.get("task") or "")
    evaluation = ModelEvaluation(
        regression_metrics={} if task == "classification" else (training.get("aggregate_metrics") or {}),
        classification_metrics=training.get("aggregate_metrics") or {} if task == "classification" else {},
        financial_metrics=backtest.get("metrics") or {},
        stability_metrics=training.get("stability_metrics") or {},
        signal_quality=signal_quality,
        overfitting_check=training.get("overfitting_check") or {},
        leakage_check=leakage,
        benchmark_comparison={"baseline_metrics": training.get("baseline_metrics") or {}, "benchmark_metrics": backtest.get("benchmark_metrics") or {}},
    )
    experiment = ForecastExperiment(
        experiment_id=experiment_id,
        created_at=generated_at,
        ticker=request.dataset_config.ticker,
        dataset_config=request.dataset_config,
        feature_config=feature_config,
        target_config=request.target_config,
        validation_config=request.validation_config,
        ml_model_config=request.ml_model_config,
        signal_config=request.signal_config,
        backtest_config=request.backtest_config,
        visualization_config=request.visualization_config,
        source_context=request.source_context,
        status="success",
        warnings=forecast.warnings,
        data_quality=quality,
        leakage_check=leakage,
        metrics=evaluation.model_dump(mode="json"),
        signal_metrics=signal_quality.model_dump(mode="json"),
    )
    ai_payload = {
        "dataset_summary": preview_dataset(request.dataset_config),
        "feature_summary": feature_payload.get("summary") or {},
        "data_snapshot": data_snapshot,
        "target_config": request.target_config.model_dump(mode="json"),
        "validation_result": {"folds": training.get("folds") or [], "aggregate_metrics": training.get("aggregate_metrics") or {}},
        "forecast_result": forecast.model_dump(mode="json"),
        "signal_result": signal.model_dump(mode="json"),
        "signal_quality": signal_quality.model_dump(mode="json"),
        "backtest_result": backtest,
        "model_evaluation": evaluation.model_dump(mode="json"),
        "explainability": explainability,
        "visualization_summary": visualization.get("metadata") or {},
        "macro_context": macro_context,
        "macro_regime": macro_regime,
        "leakage_check": leakage.model_dump(mode="json"),
    }
    ai = generate_ai_interpretation(ai_payload)
    payload = {
        "status": "success",
        "generated_at": generated_at,
        "experiment": experiment.model_dump(mode="json"),
        "dataset_preview": preview_dataset(request.dataset_config),
        "data_snapshot": data_snapshot,
        "feature_payload": feature_payload,
        "target_payload": target_payload,
        "leakage_check": leakage.model_dump(mode="json"),
        "training_result": _json_safe_training(training),
        "forecast_result": forecast.model_dump(mode="json"),
        "signal_result": signal.model_dump(mode="json"),
        "signal_quality": signal_quality.model_dump(mode="json"),
        "backtest_result": backtest,
        "model_evaluation": evaluation.model_dump(mode="json"),
        "visualization": visualization,
        "explainability": explainability,
        "ai_interpretation": ai,
        "macro_context": macro_context,
        "macro_regime": macro_regime,
        "signal_context": signal_context,
        "portfolio_advisory_signal": {},
        "research_context": {},
        "source_context": request.source_context.model_dump(mode="json"),
        "warnings": forecast.warnings,
        "errors": [],
    }
    payload["portfolio_advisory_signal"] = build_portfolio_advisory_signal(payload)
    payload["research_context"] = build_forecast_research_context(payload)
    model_artifact = save_model_artifact(
        experiment_id,
        training["model_id"],
        _build_model_artifact_payload(
            request=request,
            experiment_id=experiment_id,
            generated_at=generated_at,
            feature_payload=feature_payload,
            target_payload=target_payload,
            training=training,
            forecast=forecast,
            signal_quality=signal_quality.model_dump(mode="json"),
            evaluation=evaluation.model_dump(mode="json"),
            leakage=leakage.model_dump(mode="json"),
            data_quality_result=quality.model_dump(mode="json"),
            data_snapshot=data_snapshot,
            macro_regime=macro_regime,
        ),
    )
    payload["experiment"]["artifact_refs"]["data_snapshot_json"] = data_snapshot_artifact["artifact_path"]
    payload["experiment"]["artifact_refs"]["data_snapshot_id"] = data_snapshot["data_snapshot_id"]
    payload["experiment"]["artifact_refs"]["model_artifact_json"] = model_artifact["artifact_path"]
    payload["experiment"]["artifact_refs"]["model_artifact_integrity_json"] = model_artifact["integrity_path"]
    payload["experiment"]["artifact_refs"]["model_artifact_sha256"] = model_artifact["artifact_sha256"]
    artifact = save_experiment(experiment_id, payload)
    payload["experiment"]["artifact_refs"]["experiment_json"] = artifact["artifact_path"]
    save_experiment(experiment_id, payload)
    register_model(
        ModelRegistryItem(
            model_id=training["model_id"],
            experiment_id=experiment_id,
            ticker=request.dataset_config.ticker,
            target=request.target_config.target_type,
            horizon=request.target_config.horizon,
            model_type=training.get("task", request.ml_model_config.model_type),
            feature_set_hash=training.get("feature_set_hash", ""),
            training_period=training.get("training_period") or {},
            validation_method=request.validation_config.validation_method,
            metrics=training.get("aggregate_metrics") or {},
            signal_metrics=signal_quality.model_dump(mode="json"),
            artifact_path=model_artifact["artifact_path"],
            status="validated",
            created_at=generated_at,
            notes=f"data_snapshot_id={data_snapshot['data_snapshot_id']}",
        )
    )
    LAST_EXPERIMENT_BY_TICKER[request.dataset_config.ticker] = experiment_id
    return payload


def _build_model_artifact_payload(
    *,
    request: ForecastRunRequest,
    experiment_id: str,
    generated_at: str,
    feature_payload: dict[str, Any],
    target_payload: dict[str, Any],
    training: dict[str, Any],
    forecast: ForecastResult,
    signal_quality: dict[str, Any],
    evaluation: dict[str, Any],
    leakage: dict[str, Any],
    data_quality_result: dict[str, Any],
    data_snapshot: dict[str, Any],
    macro_regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "forecast_model_artifact_v1",
        "artifact_type": "signed_reproducible_metadata_no_pickle",
        "created_at": generated_at,
        "build": build_info(),
        "experiment_id": experiment_id,
        "model_id": training.get("model_id"),
        "ticker": request.dataset_config.ticker,
        "target": request.target_config.target_type,
        "horizon": request.target_config.horizon,
        "feature_schema": {
            "feature_names": feature_payload.get("feature_names") or [],
            "feature_count": len(feature_payload.get("feature_names") or []),
            "feature_set_hash": training.get("feature_set_hash"),
            "feature_groups": request.feature_config.feature_groups,
            "feature_shift": request.feature_config.feature_shift,
            "missing_value_policy": request.feature_config.missing_value_policy,
            "missing_by_feature": (feature_payload.get("summary") or {}).get("missing_by_feature") or {},
        },
        "configs": {
            "dataset_config": request.dataset_config.model_dump(mode="json"),
            "feature_config": request.feature_config.model_dump(mode="json"),
            "target_config": request.target_config.model_dump(mode="json"),
            "validation_config": request.validation_config.model_dump(mode="json"),
            "model_config": request.ml_model_config.model_dump(mode="json"),
            "signal_config": request.signal_config.model_dump(mode="json"),
            "backtest_config": request.backtest_config.model_dump(mode="json"),
        },
        "training_period": training.get("training_period") or {},
        "validation_summary": {
            "fold_count": len(training.get("folds") or []),
            "aggregate_metrics": training.get("aggregate_metrics") or {},
            "baseline_metrics": training.get("baseline_metrics") or {},
            "stability_metrics": training.get("stability_metrics") or {},
            "overfitting_check": training.get("overfitting_check") or {},
            "purged_combinatorial_cv": training.get("purged_combinatorial_cv") or {},
        },
        "forecast_summary": forecast.model_dump(mode="json"),
        "signal_quality": signal_quality,
        "model_evaluation": evaluation,
        "return_calibration": training.get("return_calibration") or {},
        "probability_calibration": training.get("probability_calibration") or {},
        "prediction_interval": {
            "method": training.get("prediction_interval_method") or "residual_quantile_interval",
            "p10": training.get("p10"),
            "p50": training.get("p50"),
            "p90": training.get("p90"),
            "conformal_interval": training.get("conformal_interval") or {},
        },
        "explainability": {
            "feature_importance": training.get("feature_importance") or [],
            "permutation_importance": training.get("permutation_importance") or [],
            "shap_importance": training.get("shap_importance") or [],
            "unavailable_explainers": training.get("unavailable_explainers") or [],
        },
        "target_summary": target_payload.get("summary") or {},
        "data_snapshot": data_snapshot,
        "data_quality": data_quality_result,
        "leakage_check": leakage,
        "macro_regime": macro_regime or {},
        "governance": {
            "advisory_only": True,
            "broker_execution": False,
            "random_split_default": False,
            "out_of_sample_required": True,
            "same_bar_execution_allowed": False,
            "binary_model_pickle_stored": False,
            "reproducible_retrain_manifest": True,
            "artifact_integrity_manifest_required": True,
        },
    }


def train(request: ForecastRunRequest) -> dict[str, Any]:
    return run_experiment(request)


def predict(request: ForecastRunRequest) -> dict[str, Any]:
    payload = run_experiment(request)
    return {
        "status": payload.get("status"),
        "experiment": payload.get("experiment"),
        "forecast_result": payload.get("forecast_result"),
        "signal_result": payload.get("signal_result"),
        "leakage_check": payload.get("leakage_check"),
        "data_quality": (payload.get("forecast_result") or {}).get("data_quality"),
        "source_context": payload.get("source_context"),
        "generated_at": payload.get("generated_at"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


def generate_signal_from_request(request) -> dict[str, Any]:
    signal = generate_signal(
        request.forecast_result,
        request.signal_config,
        leakage_check=request.leakage_check,
        data_quality=request.data_quality,
        context=request.context,
    )
    return {"status": "success", "signal_result": signal.model_dump(mode="json"), "generated_at": now_iso()}


def visualization(experiment_id: str) -> dict[str, Any]:
    payload = load_experiment(experiment_id)
    if not payload:
        return {"status": "failed", "errors": [f"experiment_not_found:{experiment_id}"], "visualization": {}}
    return {"status": "success", "visualization": payload.get("visualization") or {}, "generated_at": now_iso()}


def ai_interpretation(payload: dict[str, Any]) -> dict[str, Any]:
    return generate_ai_interpretation(payload, use_llm=bool(payload.get("use_llm")))


def ai_provider_status() -> dict[str, Any]:
    payload = ai_provider_health()
    payload["generated_at"] = now_iso()
    return payload


def experiments(limit: int = 50) -> dict[str, Any]:
    return list_experiments(limit=limit)


def experiment_detail(experiment_id: str) -> dict[str, Any]:
    payload = load_experiment(experiment_id)
    if not payload:
        return {"status": "failed", "errors": [f"experiment_not_found:{experiment_id}"]}
    return payload


def model_registry() -> dict[str, Any]:
    return list_registry()


def model_registry_audit(model_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    return list_registry_audit(model_id=model_id, limit=limit)


def verify_registry_artifact(model_id: str) -> dict[str, Any]:
    return verify_model_registry_artifact(model_id)


def promote_model(model_id: str, notes: str = "") -> dict[str, Any]:
    registry_items = list_registry().get("items") or []
    registry_item = next((item for item in registry_items if item.get("model_id") == model_id), None)
    if not registry_item:
        return {"status": "failed", "errors": [f"model_not_found:{model_id}"]}
    experiment_id = str(registry_item.get("experiment_id") or "")
    experiment_payload = load_experiment(experiment_id) if experiment_id else None
    artifact_integrity = verify_model_registry_artifact(model_id)
    drift_result = drift_check_from_payload(experiment_payload or {}, recent_window=63) if experiment_payload else {"status": "failed", "drift_status": "unavailable"}
    eligibility = evaluate_promotion_policy(
        registry_item=registry_item,
        experiment_payload=experiment_payload,
        artifact_integrity=artifact_integrity,
        drift_result=drift_result,
    )
    if not eligibility.get("eligible"):
        return {
            "status": "failed",
            "errors": ["promotion_policy_failed", *list(eligibility.get("hard_failures") or [])],
            "model_id": model_id,
            "promotion_eligibility": eligibility,
            "artifact_integrity": artifact_integrity,
            "drift_check": drift_result,
        }
    result = update_model_status(model_id, "promoted", notes)
    result["promotion_eligibility"] = eligibility
    result["artifact_integrity"] = artifact_integrity
    result["drift_check"] = drift_result
    return result


def deprecate_model(model_id: str, notes: str = "") -> dict[str, Any]:
    return update_model_status(model_id, "deprecated", notes)


def latest_payload_for_ticker(ticker: str) -> dict[str, Any] | None:
    experiment_id = LAST_EXPERIMENT_BY_TICKER.get(str(ticker or "").upper().strip())
    if experiment_id:
        return load_experiment(experiment_id)
    items = list_experiments(limit=100).get("items") or []
    for item in items:
        if str(item.get("ticker") or "").upper() == str(ticker or "").upper().strip():
            return load_experiment(str(item.get("experiment_id") or ""))
    return None


def research_context(ticker: str) -> dict[str, Any]:
    payload = latest_payload_for_ticker(ticker)
    if not payload:
        return {"status": "unavailable", "ticker": ticker, "reason": "forecast_experiment_not_found"}
    return build_forecast_research_context(payload)


def portfolio_signal(ticker: str) -> dict[str, Any]:
    payload = latest_payload_for_ticker(ticker)
    if not payload:
        return {"status": "unavailable", "ticker": ticker, "reason": "forecast_experiment_not_found"}
    return build_portfolio_advisory_signal(payload)


def batch_predict(request) -> dict[str, Any]:
    tickers = list(request.tickers or [])
    if not tickers:
        return {"status": "failed", "items": [], "count": 0, "errors": ["tickers_required"]}
    items: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            run_request = request.request.model_copy(update={"dataset_config": request.request.dataset_config.model_copy(update={"ticker": ticker})})
            item = predict(run_request)
            items.append({"ticker": ticker, **item})
        except Exception as exc:  # noqa: BLE001
            items.append({"ticker": ticker, "status": "failed", "errors": [f"batch_item_failed:{type(exc).__name__}:{exc}"]})
    status = "success" if all(item.get("status") == "success" for item in items) else "partial"
    return {"status": status, "items": items, "count": len(items), "generated_at": now_iso(), "errors": []}


def _forecast_float(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num == num and num not in (float("inf"), float("-inf")) else None


def _forecast_clean_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _resolve_forecast_universe(request: ForecastUniverseRunRequest) -> dict[str, Any]:
    universe_id = str(request.universe_id or "custom").strip() or "custom"
    warnings: list[str] = []
    source = "custom"
    label = "Custom"
    raw_tickers: list[str] = []
    if request.tickers:
        raw_tickers = list(request.tickers)
        source = "direct_input"
        label = "Custom"
    elif universe_id.lower() != "custom":
        try:
            from pipelines.ai_portfolio.engine import load_universe, universe_label

            assets, universe_warnings = load_universe(universe_id)
            raw_tickers = [asset.ticker for asset in assets]
            warnings.extend(universe_warnings or [])
            source = "preset"
            label = universe_label(universe_id)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"universe_resolve_failed:{type(exc).__name__}:{exc}")
            raw_tickers = []
    if not raw_tickers:
        fallback = _forecast_clean_ticker(request.request.dataset_config.ticker)
        if fallback:
            raw_tickers = [fallback]
            warnings.append("universe_empty_single_ticker_fallback")
    seen: set[str] = set()
    resolved: list[str] = []
    for ticker in raw_tickers:
        clean = _forecast_clean_ticker(ticker)
        if clean and clean not in seen:
            seen.add(clean)
            resolved.append(clean)
    selected = resolved[: request.max_assets]
    excluded = resolved[request.max_assets :]
    if excluded:
        warnings.append(f"universe_capped:{len(resolved)}->{len(selected)}")
    return {
        "universe_id": universe_id,
        "label": label,
        "source": source,
        "requested_count": len(raw_tickers),
        "resolved_count": len(resolved),
        "selected_count": len(selected),
        "selected": selected,
        "excluded": excluded,
        "warnings": warnings,
    }


def resolve_universe(request: ForecastUniverseRunRequest) -> dict[str, Any]:
    return _resolve_forecast_universe(request)


def _forecast_universe_row(ticker: str, item: dict[str, Any], ranking_metric: str) -> dict[str, Any]:
    forecast = item.get("forecast_result") or {}
    signal = item.get("signal_result") or {}
    confidence = forecast.get("model_confidence") or {}
    leakage = item.get("leakage_check") or {}
    data_quality = forecast.get("data_quality") or item.get("data_quality") or {}
    expected_return = _forecast_float(forecast.get("expected_return"))
    probability_up = _forecast_float(forecast.get("probability_up"))
    forecast_volatility = _forecast_float(forecast.get("forecast_volatility"))
    confidence_score = _forecast_float(confidence.get("score"))
    signal_score = _forecast_float(signal.get("signal_score"))
    if confidence_score is None:
        confidence_score = _forecast_float(signal.get("confidence"))
    rank_source = {
        "confidence": confidence_score,
        "expected_return": expected_return,
        "probability_up": probability_up,
        "signal_score": signal_score,
        "risk_adjusted": (
            expected_return / max(abs(forecast_volatility or 0.0), 1e-6)
            if expected_return is not None and forecast_volatility not in (None, 0)
            else None
        ),
    }
    raw_signal = str(signal.get("signal") or forecast.get("signal") or "unavailable")
    if item.get("status") != "success":
        bucket = "unavailable"
    elif "bullish" in raw_signal:
        bucket = "bullish"
    elif "bearish" in raw_signal:
        bucket = "bearish"
    elif expected_return is not None and expected_return > 0.01 and (probability_up or 0) >= 0.52:
        bucket = "bullish"
    elif expected_return is not None and expected_return < -0.01:
        bucket = "bearish"
    else:
        bucket = "neutral"
    return {
        "ticker": ticker,
        "status": item.get("status") or "unknown",
        "rank": None,
        "rank_score": rank_source.get(ranking_metric),
        "ranking_metric": ranking_metric,
        "decision_bucket": bucket,
        "signal": raw_signal,
        "expected_return": expected_return,
        "probability_up": probability_up,
        "forecast_volatility": forecast_volatility,
        "signal_score": signal_score,
        "confidence": confidence_score,
        "confidence_level": confidence.get("level") or "",
        "as_of": forecast.get("as_of") or signal.get("as_of") or "",
        "experiment_id": forecast.get("experiment_id") or "",
        "model_id": forecast.get("model_id") or "",
        "data_quality_status": data_quality.get("status") or "unknown",
        "leakage_status": leakage.get("status") or "unknown",
        "source_context": item.get("source_context") or {},
        "warnings": list(item.get("warnings") or []) + list(forecast.get("warnings") or []) + list(signal.get("warnings") or []),
        "errors": list(item.get("errors") or []),
    }


def _forecast_universe_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row.get("status") == "success"]
    failed = [row for row in rows if row.get("status") != "success"]

    def avg(key: str) -> float | None:
        values = [_forecast_float(row.get(key)) for row in successful]
        clean = [value for value in values if value is not None]
        return sum(clean) / len(clean) if clean else None

    return {
        "success_count": len(successful),
        "failed_count": len(failed),
        "average_confidence": avg("confidence"),
        "average_expected_return": avg("expected_return"),
        "average_probability_up": avg("probability_up"),
        "bullish_count": sum(1 for row in rows if row.get("decision_bucket") == "bullish"),
        "neutral_count": sum(1 for row in rows if row.get("decision_bucket") == "neutral"),
        "bearish_count": sum(1 for row in rows if row.get("decision_bucket") == "bearish"),
        "unavailable_count": sum(1 for row in rows if row.get("decision_bucket") == "unavailable"),
        "advisory_only": True,
    }


def universe_run(request: ForecastUniverseRunRequest) -> dict[str, Any]:
    universe = _resolve_forecast_universe(request)
    selected = list(universe.get("selected") or [])
    generated_at = now_iso()
    if not selected:
        return {
            "status": "failed",
            "universe": universe,
            "items": [],
            "summary": _forecast_universe_summary([]),
            "count": 0,
            "ranking_metric": request.ranking_metric,
            "generated_at": generated_at,
            "errors": ["forecast_universe_empty"],
            "warnings": universe.get("warnings", []),
        }
    rows: list[dict[str, Any]] = []
    for ticker in selected:
        try:
            dataset_config = request.request.dataset_config.model_copy(update={"ticker": ticker, "universe_id": universe.get("universe_id")})
            source_context = request.request.source_context
            if not source_context.source:
                source_context = source_context.model_copy(update={"source": "forecast_universe"})
            run_request = request.request.model_copy(update={"dataset_config": dataset_config, "source_context": source_context})
            item = predict(run_request)
            rows.append(_forecast_universe_row(ticker, item, request.ranking_metric))
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "ticker": ticker,
                    "status": "failed",
                    "rank": None,
                    "rank_score": None,
                    "ranking_metric": request.ranking_metric,
                    "decision_bucket": "unavailable",
                    "signal": "unavailable",
                    "expected_return": None,
                    "probability_up": None,
                    "forecast_volatility": None,
                    "signal_score": None,
                    "confidence": None,
                    "confidence_level": "",
                    "as_of": "",
                    "experiment_id": "",
                    "model_id": "",
                    "data_quality_status": "unknown",
                    "leakage_status": "unknown",
                    "warnings": [],
                    "errors": [f"forecast_universe_item_failed:{type(exc).__name__}:{exc}"],
                }
            )
    rows.sort(
        key=lambda row: (
            row.get("status") == "success",
            row.get("rank_score") is not None,
            row.get("rank_score") if row.get("rank_score") is not None else float("-inf"),
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx if row.get("status") == "success" else None
    summary = _forecast_universe_summary(rows)
    if summary["success_count"] == len(rows):
        status = "success"
    elif summary["success_count"]:
        status = "partial"
    else:
        status = "failed"
    errors = [error for row in rows for error in row.get("errors", [])]
    return {
        "status": status,
        "universe": universe,
        "items": rows,
        "summary": summary,
        "count": len(rows),
        "ranking_metric": request.ranking_metric,
        "request_summary": {
            "model": request.request.ml_model_config.model_name,
            "target": request.request.target_config.target_type,
            "horizon": request.request.target_config.horizon,
            "validation": request.request.validation_config.validation_method,
            "benchmark": request.request.dataset_config.benchmark,
        },
        "generated_at": generated_at,
        "errors": errors,
        "warnings": list(universe.get("warnings") or []),
    }


def drift_check(*, ticker: str | None = None, experiment_id: str | None = None, recent_window: int = 63) -> dict[str, Any]:
    payload = load_experiment(str(experiment_id)) if experiment_id else latest_payload_for_ticker(str(ticker or ""))
    if not payload:
        return {"status": "failed", "errors": ["forecast_experiment_not_found"], "generated_at": now_iso()}
    result = drift_check_from_payload(payload, recent_window=recent_window)
    result["experiment_id"] = (payload.get("experiment") or {}).get("experiment_id") or payload.get("experiment_id")
    result["ticker"] = (payload.get("forecast_result") or {}).get("ticker") or ticker
    result["generated_at"] = now_iso()
    return result


def model_comparison(limit: int = 50, ticker: str | None = None) -> dict[str, Any]:
    summaries = list_experiments(limit=limit).get("items") or []
    payloads: list[dict[str, Any]] = []
    for item in summaries:
        if ticker and str(item.get("ticker") or "").upper() != str(ticker).upper():
            continue
        payload = load_experiment(str(item.get("experiment_id") or ""))
        if payload:
            payloads.append(payload)
    rows = model_comparison_rows(payloads)
    return {"status": "success", "items": rows, "count": len(rows), "generated_at": now_iso()}


def _failed_payload(
    *,
    experiment_id: str,
    request: ForecastRunRequest,
    generated_at: str,
    data_quality_result,
    leakage,
    warnings: list[str],
    errors: list[str] | None = None,
    data_snapshot: dict[str, Any] | None = None,
    data_snapshot_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forecast = ForecastResult(
        experiment_id=experiment_id,
        ticker=request.dataset_config.ticker,
        as_of="",
        horizon=request.target_config.horizon,
        prediction_type=request.target_config.target_type,
        warnings=warnings,
        data_quality=data_quality_result,
    )
    return {
        "status": "failed",
        "generated_at": generated_at,
        "experiment_id": experiment_id,
        "forecast_result": forecast.model_dump(mode="json"),
        "data_snapshot": data_snapshot or {},
        "source_context": request.source_context.model_dump(mode="json"),
        "leakage_check": leakage.model_dump(mode="json"),
        "artifact_refs": {
            "data_snapshot_json": (data_snapshot_artifact or {}).get("artifact_path", ""),
            "data_snapshot_id": (data_snapshot or {}).get("data_snapshot_id", ""),
        },
        "warnings": warnings,
        "errors": errors or ["forecast_experiment_failed"],
    }


def _json_safe_training(training: dict[str, Any]) -> dict[str, Any]:
    hidden = {"estimator"}
    out = {}
    for key, value in training.items():
        if key in hidden:
            continue
        if key == "model":
            continue
        out[key] = value
    return out
