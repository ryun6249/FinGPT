from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from core.schemas.forecast import (
    ForecastBatchPredictRequest,
    ForecastDatasetPreviewRequest,
    ForecastDriftCheckRequest,
    ForecastDatasetHydrateRequest,
    ForecastFeatureBuildRequest,
    ForecastJobCancelRequest,
    ForecastJobSubmitRequest,
    ForecastLeakageCheckRequest,
    ForecastRegistryActionRequest,
    ForecastRunRequest,
    ForecastSignalGenerateRequest,
    ForecastTargetBuildRequest,
    ForecastUniverseRunRequest,
)
from pipelines.forecast import jobs
from pipelines.forecast import service


router = APIRouter(tags=["forecast"])


@router.get("/health")
async def get_health() -> dict[str, Any]:
    return service.health()


@router.get("/models")
async def get_models() -> dict[str, Any]:
    return service.models()


@router.post("/dataset/preview")
async def post_dataset_preview(request: ForecastDatasetPreviewRequest) -> dict[str, Any]:
    return service.preview_dataset(request.dataset_config)


@router.post("/dataset/hydrate")
async def post_dataset_hydrate(request: ForecastDatasetHydrateRequest) -> dict[str, Any]:
    return service.hydrate_dataset(request)


@router.post("/features/build")
async def post_features_build(request: ForecastFeatureBuildRequest) -> dict[str, Any]:
    return service.build_feature_payload(request.dataset_config, request.feature_config)


@router.post("/target/build")
async def post_target_build(request: ForecastTargetBuildRequest) -> dict[str, Any]:
    return service.build_target_payload(request.dataset_config, request.target_config)


@router.post("/leakage/check")
async def post_leakage_check(request: ForecastLeakageCheckRequest) -> dict[str, Any]:
    return service.leakage_check_for_request(request)


@router.post("/train")
async def post_train(request: ForecastRunRequest) -> dict[str, Any]:
    return service.train(request)


@router.post("/predict")
async def post_predict(request: ForecastRunRequest) -> dict[str, Any]:
    return service.predict(request)


@router.post("/signals/generate")
async def post_signals_generate(request: ForecastSignalGenerateRequest) -> dict[str, Any]:
    return service.generate_signal_from_request(request)


@router.post("/signals/evaluate")
async def post_signals_evaluate(request: ForecastRunRequest) -> dict[str, Any]:
    payload = service.train(request)
    return {
        "status": payload.get("status"),
        "signal_quality": payload.get("signal_quality"),
        "leakage_check": payload.get("leakage_check"),
        "generated_at": payload.get("generated_at"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


@router.post("/backtest")
async def post_backtest(request: ForecastRunRequest) -> dict[str, Any]:
    payload = service.train(request)
    return {
        "status": payload.get("status"),
        "backtest_result": payload.get("backtest_result"),
        "model_evaluation": payload.get("model_evaluation"),
        "leakage_check": payload.get("leakage_check"),
        "generated_at": payload.get("generated_at"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


@router.post("/explain")
async def post_explain(request: ForecastRunRequest) -> dict[str, Any]:
    payload = service.train(request)
    return {
        "status": payload.get("status"),
        "explainability": payload.get("explainability"),
        "generated_at": payload.get("generated_at"),
        "warnings": payload.get("warnings", []),
        "errors": payload.get("errors", []),
    }


@router.get("/visualization/{experiment_id}")
async def get_visualization(experiment_id: str) -> dict[str, Any]:
    result = service.visualization(experiment_id)
    if result.get("status") == "failed":
        raise HTTPException(status_code=404, detail=result.get("errors", ["experiment_not_found"])[0])
    return result


@router.post("/ai-interpretation")
async def post_ai_interpretation(payload: dict[str, Any]) -> dict[str, Any]:
    return service.ai_interpretation(payload)


@router.get("/ai-provider/health")
async def get_ai_provider_health() -> dict[str, Any]:
    return service.ai_provider_status()


@router.get("/experiments")
async def get_experiments(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return service.experiments(limit=limit)


@router.post("/jobs")
async def post_forecast_job(request: ForecastJobSubmitRequest) -> dict[str, Any]:
    return jobs.submit_forecast_job(request)


@router.get("/jobs")
async def get_forecast_jobs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return jobs.list_forecast_jobs(limit=limit)


@router.get("/jobs/{job_id}")
async def get_forecast_job(job_id: str) -> dict[str, Any]:
    payload = jobs.get_forecast_job(job_id)
    if payload.get("status") == "failed":
        raise HTTPException(status_code=404, detail=payload.get("errors", ["forecast_job_not_found"])[0])
    return payload


@router.post("/jobs/{job_id}/cancel")
async def post_forecast_job_cancel(job_id: str, request: ForecastJobCancelRequest | None = None) -> dict[str, Any]:
    payload = jobs.cancel_forecast_job(job_id, reason=(request.reason if request else ""))
    if payload.get("status") == "failed":
        raise HTTPException(status_code=404, detail=payload.get("errors", ["forecast_job_not_found"])[0])
    return payload


@router.post("/jobs/{job_id}/retry")
async def post_forecast_job_retry(job_id: str) -> dict[str, Any]:
    payload = jobs.retry_forecast_job(job_id)
    if payload.get("status") == "failed":
        raise HTTPException(status_code=404, detail=payload.get("errors", ["forecast_job_not_found"])[0])
    return payload


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str) -> dict[str, Any]:
    payload = service.experiment_detail(experiment_id)
    if payload.get("status") == "failed":
        raise HTTPException(status_code=404, detail=payload.get("errors", ["experiment_not_found"])[0])
    return payload


@router.get("/model-registry")
async def get_model_registry() -> dict[str, Any]:
    return service.model_registry()


@router.get("/model-registry/audit")
async def get_model_registry_audit(
    model_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return service.model_registry_audit(model_id=model_id, limit=limit)


@router.post("/model-registry/verify-artifact")
async def post_model_artifact_verify(request: ForecastRegistryActionRequest) -> dict[str, Any]:
    result = service.verify_registry_artifact(request.model_id)
    if result.get("status") == "failed" and any(str(error).startswith("model_not_found") for error in result.get("errors", [])):
        raise HTTPException(status_code=404, detail=result.get("errors", ["model_not_found"])[0])
    return result


@router.post("/model-registry/promote")
async def post_model_promote(request: ForecastRegistryActionRequest) -> dict[str, Any]:
    result = service.promote_model(request.model_id, request.notes)
    if result.get("status") == "failed":
        errors = result.get("errors", ["model_not_found"])
        status_code = 404 if any(str(error).startswith("model_not_found") for error in errors) else 409
        raise HTTPException(status_code=status_code, detail=result)
    return result


@router.post("/model-registry/deprecate")
async def post_model_deprecate(request: ForecastRegistryActionRequest) -> dict[str, Any]:
    result = service.deprecate_model(request.model_id, request.notes)
    if result.get("status") == "failed":
        raise HTTPException(status_code=404, detail=result.get("errors", ["model_not_found"])[0])
    return result


@router.get("/research-context/{ticker}")
async def get_research_context(ticker: str) -> dict[str, Any]:
    return service.research_context(ticker)


@router.get("/portfolio-signal/{ticker}")
async def get_portfolio_signal(ticker: str) -> dict[str, Any]:
    return service.portfolio_signal(ticker)


@router.post("/batch-predict")
async def post_batch_predict(request: ForecastBatchPredictRequest) -> dict[str, Any]:
    return service.batch_predict(request)


@router.post("/universe/run")
async def post_universe_run(request: ForecastUniverseRunRequest) -> dict[str, Any]:
    return service.universe_run(request)


@router.post("/drift/check")
async def post_drift_check(request: ForecastDriftCheckRequest) -> dict[str, Any]:
    return service.drift_check(ticker=request.ticker, experiment_id=request.experiment_id, recent_window=request.recent_window)


@router.get("/drift/check")
async def get_drift_check(
    ticker: str | None = Query(default=None),
    experiment_id: str | None = Query(default=None),
    recent_window: int = Query(default=63, ge=20, le=252),
) -> dict[str, Any]:
    return service.drift_check(ticker=ticker, experiment_id=experiment_id, recent_window=recent_window)


@router.get("/model-comparison")
async def get_model_comparison(limit: int = Query(default=50, ge=1, le=200), ticker: str | None = Query(default=None)) -> dict[str, Any]:
    return service.model_comparison(limit=limit, ticker=ticker)
