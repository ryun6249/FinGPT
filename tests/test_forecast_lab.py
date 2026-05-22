from __future__ import annotations

import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.server import app
from core.schemas.forecast import (
    BacktestConfig,
    DataQualityResult,
    FeatureConfig,
    ForecastDatasetConfig,
    ForecastResult,
    ForecastJobSubmitRequest,
    ForecastRunRequest,
    ForecastSourceContext,
    ForecastUniverseRunRequest,
    ModelConfig,
    ModelRegistryItem,
    SignalConfig,
    TargetConfig,
    ValidationConfig,
)
from pipelines.data_mart.models import PriceBar
from pipelines.data_mart.storage import repository
from pipelines.data_mart.storage.db import init_db
from pipelines.forecast.ai_interpretation import generate_ai_interpretation
from pipelines.forecast.backtester import run_forecast_backtest
from pipelines.forecast.data_loader import load_benchmark_rows, load_price_rows
from pipelines.forecast.experiment_store import forecast_root, register_model, save_experiment, save_model_artifact, verify_model_artifact_integrity
from pipelines.forecast.feature_engineering import build_features
from pipelines.forecast.integrations.macro_context import build_macro_regime_artifact
from pipelines.forecast import jobs as forecast_jobs
from pipelines.forecast import service as forecast_service
from pipelines.forecast.leakage import run_leakage_check
from pipelines.forecast.modeling import train_and_forecast
from pipelines.forecast.signal_generator import generate_signal
from pipelines.forecast.target_builder import align_feature_target, build_target, latest_feature_row
from pipelines.forecast.validation import create_purged_combinatorial_splits, create_walk_forward_splits
from pipelines.forecast.visualization import build_visualization_payload


def _seed_prices(db_path, rows: int = 260) -> None:
    init_db(db_path)
    prices = []
    for idx in range(rows):
        day = (date(2025, 1, 1) + timedelta(days=idx)).isoformat()
        spy = 100 + idx * 0.2 + (idx % 11) * 0.1
        qqq = 120 + idx * 0.25 + (idx % 7) * 0.2
        prices.extend(
            [
                PriceBar(ticker="SPY", date=day, close=spy, adjusted_close=spy, volume=1_000_000 + idx, source="test"),
                PriceBar(ticker="QQQ", date=day, close=qqq, adjusted_close=qqq, volume=2_000_000 + idx, source="test"),
            ]
        )
    repository.upsert_prices(prices, db_path=db_path)


def test_forecast_run_request_accepts_risk_source_context() -> None:
    request = ForecastRunRequest(
        source_context=ForecastSourceContext(
            source="risk_workbench",
            risk_validation_test_id="walk_forward_baseline",
            risk_input_hash="abc123",
            risk_test_type="walk_forward",
            risk_test_label="Run walk-forward baseline",
            risk_priority=2,
        )
    )

    payload = request.model_dump(mode="json")

    assert payload["source_context"]["source"] == "risk_workbench"
    assert payload["source_context"]["risk_validation_test_id"] == "walk_forward_baseline"
    assert payload["source_context"]["risk_input_hash"] == "abc123"


def test_feature_engineering_applies_one_bar_shift(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=30)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="SPY")
    rows = load_price_rows(config)
    payload = build_features(rows, rows, FeatureConfig(feature_groups=["returns"], feature_shift=1))

    feature_by_date = {row["date"]: row["features"] for row in payload["rows"]}
    expected_prior_return = rows[1]["price"] / rows[0]["price"] - 1.0
    assert feature_by_date[rows[2]["date"]]["return_1d"] == expected_prior_return
    assert payload["summary"]["feature_shift"] == 1


def test_target_builder_forward_return_removes_future_tail(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=40)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    rows = load_price_rows(ForecastDatasetConfig(ticker="SPY"))
    payload = build_target(rows, rows, TargetConfig(target_type="forward_return", horizon=5))

    assert payload["target_name"] == "forward_return_5d"
    assert payload["rows"][0]["target"] == rows[5]["price"] / rows[0]["price"] - 1.0
    assert payload["rows"][-1]["is_trainable"] is False
    assert payload["summary"]["dropped_tail_rows"] == 5


def test_target_builder_supports_extended_targets(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=90)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    rows = load_price_rows(ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"))
    benchmark = load_benchmark_rows(ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"))

    volatility = build_target(rows, benchmark, TargetConfig(target_type="volatility", horizon=5))
    excess = build_target(rows, benchmark, TargetConfig(target_type="excess_return", horizon=5, benchmark="QQQ"))
    quantile = build_target(rows, benchmark, TargetConfig(target_type="quantile_return", horizon=5))
    triple = build_target(
        rows,
        benchmark,
        TargetConfig(target_type="triple_barrier_label", horizon=5, triple_barrier_take_profit=0.002, triple_barrier_stop_loss=0.002),
    )

    assert volatility["summary"]["complete_rows"] > 40
    assert excess["summary"]["complete_rows"] > 40
    assert set(row["target"] for row in quantile["rows"] if row["target"] is not None).issubset({0.0, 1.0, 2.0, 3.0, 4.0})
    assert triple["target_name"] == "triple_barrier_label_5d"
    assert set(row["target"] for row in triple["rows"] if row["target"] is not None).issubset({-1.0, 0.0, 1.0})


def test_leakage_checker_blocks_random_shuffle_and_same_bar_execution() -> None:
    check = run_leakage_check(
        feature_config=FeatureConfig(feature_shift=0),
        target_config=TargetConfig(horizon=20),
        validation_config=ValidationConfig(validation_method="random_split", shuffle=True, purge_window=0, embargo_window=0),
        backtest_config=BacktestConfig(execution_delay_bars=0),
        data_quality=DataQualityResult(status="unavailable"),
        feature_names=["return_1d", "forward_return_20d"],
    )

    assert check.status == "fail"
    assert "shuffle_true_not_allowed" in check.issues
    assert "same_bar_execution_risk" in check.issues
    assert "data_quality_unavailable" in check.issues
    assert any(issue.startswith("target_like_feature_detected") for issue in check.issues)


def test_walk_forward_splits_preserve_time_order_and_purge() -> None:
    dates = [(date(2025, 1, 1) + timedelta(days=idx)).isoformat() for idx in range(180)]
    folds, warnings = create_walk_forward_splits(
        dates,
        ValidationConfig(train_window=80, test_window=20, step_size=20, purge_window="auto", embargo_window=5),
        TargetConfig(horizon=10),
    )

    assert folds
    assert not warnings
    first = folds[0]
    assert first.train_end + 10 == first.test_start
    assert first.train_start < first.train_end < first.test_start < first.test_end
    assert first.embargo_end == first.test_end + 5


def test_purged_combinatorial_cv_splits_remove_test_purge_embargo_overlap() -> None:
    dates = [(date(2025, 1, 1) + timedelta(days=idx)).isoformat() for idx in range(180)]
    folds, warnings = create_purged_combinatorial_splits(
        dates,
        ValidationConfig(validation_method="walk_forward_plus_purged_cv", purge_window="auto", embargo_window=5),
        TargetConfig(horizon=10),
        n_groups=6,
        test_group_count=2,
        max_splits=4,
    )

    assert folds
    assert "purged_combinatorial_cv_splits_capped" in warnings
    first = folds[0]
    train = set(first.train_indices)
    test = set(first.test_indices)
    assert train.isdisjoint(test)
    for test_idx in test:
        blocked = set(range(max(0, test_idx - 10), min(len(dates), test_idx + 5 + 1)))
        assert train.isdisjoint(blocked)


def test_signal_generation_uses_confidence_and_advisory_mapping() -> None:
    forecast = ForecastResult(
        ticker="SPY",
        as_of="2026-01-01",
        expected_return=0.04,
        probability_up=0.65,
        probability_down=0.35,
        forecast_volatility=0.15,
    )
    forecast.model_confidence.score = 0.75
    forecast.data_quality = DataQualityResult(status="ok")
    signal = generate_signal(forecast, SignalConfig())

    assert signal.signal == "strong_bullish"
    assert signal.position_target == 1.0
    assert signal.advisory_only is True


def test_backtest_applies_one_bar_delay_and_transaction_cost(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=80)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="SPY")
    rows = load_price_rows(config)
    oos = [
        {"date": row["date"], "predicted_return": 0.03, "actual_forward_return": 0.01, "fold_id": 1}
        for row in rows[-40:]
    ]
    result = run_forecast_backtest(rows, rows, oos, signal_config=SignalConfig(), backtest_config=BacktestConfig(execution_delay_bars=1))

    assert result["status"] == "success"
    assert result["assumptions"]["execution_delay_bars"] == 1
    assert result["trades"][0]["signal_date"] < result["trades"][0]["execution_date"]
    assert result["metrics"]["transaction_cost_impact"] > 0


def test_visualization_payload_includes_remaining_diagnostics() -> None:
    oos = [
        {"date": "2026-01-01", "predicted_return": 0.02, "actual_forward_return": 0.01, "fold_id": 1},
        {"date": "2026-01-02", "predicted_return": -0.01, "actual_forward_return": -0.02, "fold_id": 1},
        {"date": "2026-02-03", "predicted_return": 0.03, "actual_forward_return": -0.01, "fold_id": 2},
    ]
    payload = build_visualization_payload(
        experiment_id="exp_test",
        model_id="mlf_test",
        ticker="SPY",
        price_rows=[{"date": item["date"], "price": 100 + idx, "ticker": "SPY"} for idx, item in enumerate(oos)],
        training_result={
            "oos_predictions": oos,
            "residuals": [0.0, -0.01, -0.04],
            "expected_return": 0.01,
            "p10": -0.01,
            "p50": 0.01,
            "p90": 0.03,
            "folds": [{"fold_id": 1, "metrics": {"directional_accuracy": 0.5}}],
        },
        backtest_result={
            "equity_curve": [{"date": "2026-01-01", "equity": 1.0}, {"date": "2026-01-31", "equity": 1.02}, {"date": "2026-02-28", "equity": 1.01}],
            "signal_history": [],
            "position_history": [],
            "trades": [],
            "assumptions": {"transaction_cost_reflected": True},
        },
        feature_payload={"summary": {"missing_ratio": 0.0}},
    )

    assert payload["monthly_return_heatmap"]
    assert payload["confusion_matrix"]["false_positive"] == 1
    assert payload["regime_performance"]


def test_label_target_forecast_uses_oos_return_calibration(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    feature_payload = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1))
    target_config = TargetConfig(target_type="triple_barrier_label", horizon=10, triple_barrier_take_profit=0.01, triple_barrier_stop_loss=0.01)
    target_payload = build_target(rows, benchmark, target_config)
    training = train_and_forecast(
        align_feature_target(feature_payload, target_payload),
        latest_feature_row(feature_payload),
        feature_payload["feature_names"],
        target_config=target_config,
        validation_config=ValidationConfig(train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
        model_config=ModelConfig(model_type="baseline", model_name="historical_mean"),
    )

    assert training["status"] == "success"
    assert training["task"] == "classification"
    assert training["return_calibration"]["method"] == "oos_conditional_forward_return_by_direction"
    assert training["probability_calibration"]["method"] == "oos_reliability_bin_calibration"
    assert training["conformal_interval"]["method"] == "oos_residual_conformal_interval"
    assert training["expected_return"] is not None
    assert abs(training["expected_return"]) < 0.2
    assert all("calibrated_probability_up" in item for item in training["oos_predictions"])
    assert all(item["predicted_return"] is None or abs(item["predicted_return"]) < 0.2 for item in training["oos_predictions"])


def test_sklearn_ridge_model_is_available_and_trains(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    features = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1))
    target = build_target(rows, benchmark, TargetConfig(target_type="forward_return", horizon=10))
    aligned = align_feature_target(features, target)

    client = TestClient(app)
    models = client.get("/api/v1/forecast/models").json()["models"]
    ridge = next(item for item in models if item["model_name"] == "ridge_regression")
    training = train_and_forecast(
        aligned,
        latest_feature_row(features),
        features["feature_names"],
        target_config=TargetConfig(target_type="forward_return", horizon=10),
        validation_config=ValidationConfig(train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
        model_config=ModelConfig(model_name="ridge_regression", model_type="regression"),
    )

    assert ridge["available"] is True
    assert training["status"] == "success"
    assert training["model_name"] == "ridge_regression"
    assert training["oos_predictions"]


def test_train_result_includes_purged_cv_diagnostic_when_requested(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    features = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1))
    target = build_target(rows, benchmark, TargetConfig(target_type="forward_return", horizon=10))
    training = train_and_forecast(
        align_feature_target(features, target),
        latest_feature_row(features),
        features["feature_names"],
        target_config=TargetConfig(target_type="forward_return", horizon=10),
        validation_config=ValidationConfig(validation_method="walk_forward_plus_purged_cv", train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
        model_config=ModelConfig(model_name="ridge_regression", model_type="regression"),
    )

    assert training["status"] == "success"
    assert training["purged_combinatorial_cv"]["status"] == "success"
    assert training["purged_combinatorial_cv"]["fold_count"] >= 1
    assert training["stability_metrics"]["purged_cv_fold_count"] >= 1


def test_optional_boosting_models_train_when_dependencies_exist(tmp_path, monkeypatch) -> None:
    missing = [name for name in ("xgboost", "lightgbm") if importlib.util.find_spec(name) is None]
    if missing:
        pytest.skip(f"optional forecast dependencies missing: {','.join(missing)}")
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    features = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1))
    target = build_target(rows, benchmark, TargetConfig(target_type="forward_return", horizon=10))
    aligned = align_feature_target(features, target)
    models = TestClient(app).get("/api/v1/forecast/models").json()["models"]
    availability = {item["model_name"]: item["available"] for item in models}

    for model_name in ("xgboost", "lightgbm"):
        training = train_and_forecast(
            aligned,
            latest_feature_row(features),
            features["feature_names"],
            target_config=TargetConfig(target_type="forward_return", horizon=10),
            validation_config=ValidationConfig(train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
            model_config=ModelConfig(model_name=model_name, model_type="regression", hyperparameters={"n_estimators": 20, "max_depth": 2}),
        )
        assert availability[model_name] is True
        assert training["status"] == "success"
        assert training["model_name"] == model_name
        assert training["oos_predictions"]


def test_deep_sequence_models_train_when_torch_is_available(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=160)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    features = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns"], feature_shift=1))
    target = build_target(rows, benchmark, TargetConfig(target_type="forward_return", horizon=5))
    aligned = align_feature_target(features, target)

    training = train_and_forecast(
        aligned,
        latest_feature_row(features),
        features["feature_names"],
        target_config=TargetConfig(target_type="forward_return", horizon=5),
        validation_config=ValidationConfig(train_window=60, test_window=20, step_size=20, purge_window="auto", embargo_window=2),
        model_config=ModelConfig(
            model_name="lstm",
            model_type="deep_sequence",
            hyperparameters={"epochs": 2, "hidden_dim": 8, "lookback": 5},
        ),
    )

    if importlib.util.find_spec("torch") is None:
        assert training["status"] == "failed"
        assert "torch_missing" in training["errors"][0]
    else:
        assert training["status"] == "success"
        assert training["model_name"] == "lstm"
        assert training["oos_predictions"]


def test_shapley_importance_fallback_is_available_without_shap(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=220)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    config = ForecastDatasetConfig(ticker="SPY", benchmark="QQQ")
    rows = load_price_rows(config)
    benchmark = load_benchmark_rows(config)
    features = build_features(rows, benchmark, FeatureConfig(feature_groups=["returns", "momentum"], feature_shift=1))
    target = build_target(rows, benchmark, TargetConfig(target_type="forward_return", horizon=5))
    aligned = align_feature_target(features, target)

    training = train_and_forecast(
        aligned,
        latest_feature_row(features),
        features["feature_names"],
        target_config=TargetConfig(target_type="forward_return", horizon=5),
        validation_config=ValidationConfig(train_window=100, test_window=25, step_size=25, purge_window="auto", embargo_window=2),
        model_config=ModelConfig(model_name="ridge_regression", model_type="regression"),
    )

    assert training["status"] == "success"
    assert training["shap_importance"]
    assert training["unavailable_explainers"] == []
    assert any("shapley" in item["method"] or "shap" in item["method"] for item in training["shap_importance"])


def test_forecast_api_train_persists_experiment_and_registry(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    client = TestClient(app)
    request = ForecastRunRequest(
        dataset_config=ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"),
        feature_config=FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1),
        target_config=TargetConfig(target_type="forward_return", horizon=10),
        validation_config=ValidationConfig(train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
    )

    response = client.post("/api/v1/forecast/train", json=request.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["leakage_check"]["status"] in {"pass", "warning"}
    assert body["forecast_result"]["expected_return"] is not None
    assert body["signal_result"]["advisory_only"] is True
    assert body["backtest_result"]["assumptions"]["oos_predictions_only"] is True
    assert body["visualization"]["actual_vs_predicted"]
    assert body["visualization"]["permutation_importance"] is not None
    assert "model_artifact_json" in body["experiment"]["artifact_refs"]
    assert "model_artifact_integrity_json" in body["experiment"]["artifact_refs"]
    assert "model_artifact_sha256" in body["experiment"]["artifact_refs"]
    assert "data_snapshot_json" in body["experiment"]["artifact_refs"]
    assert body["data_snapshot"]["data_snapshot_id"].startswith("ds_")
    assert body["data_snapshot"]["source_coverage_hash"]
    artifact_path = Path(body["experiment"]["artifact_refs"]["model_artifact_json"])
    integrity_path = Path(body["experiment"]["artifact_refs"]["model_artifact_integrity_json"])
    data_snapshot_path = Path(body["experiment"]["artifact_refs"]["data_snapshot_json"])
    assert artifact_path.exists()
    assert integrity_path.exists()
    assert data_snapshot_path.exists()
    assert artifact_path.name.startswith(body["forecast_result"]["model_id"])
    saved_snapshot = json.loads(data_snapshot_path.read_text(encoding="utf-8"))
    saved_artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert saved_snapshot["data_snapshot_id"] == body["data_snapshot"]["data_snapshot_id"]
    assert saved_artifact["data_snapshot"]["data_snapshot_id"] == body["data_snapshot"]["data_snapshot_id"]
    assert saved_artifact["data_snapshot"]["source_coverage_hash"] == body["data_snapshot"]["source_coverage_hash"]
    integrity = verify_model_artifact_integrity(artifact_path)
    assert integrity["status"] == "success"
    assert integrity["artifact_sha256"] == body["experiment"]["artifact_refs"]["model_artifact_sha256"]
    experiments = client.get("/api/v1/forecast/experiments")
    registry = client.get("/api/v1/forecast/model-registry")
    assert experiments.status_code == 200
    assert registry.status_code == 200
    assert registry.json()["storage"] == "sqlite"
    assert (forecast_root() / "model_registry.sqlite3").exists()
    assert experiments.json()["count"] >= 1
    assert experiments.json()["items"][0]["data_snapshot_id"].startswith("ds_")
    assert registry.json()["count"] >= 1
    registry_item = registry.json()["items"][0]
    assert registry_item["artifact_path"] == str(artifact_path)

    verify = client.post("/api/v1/forecast/model-registry/verify-artifact", json={"model_id": registry_item["model_id"], "notes": "unit verify"})
    promote = client.post("/api/v1/forecast/model-registry/promote", json={"model_id": registry_item["model_id"], "notes": "unit promote"})
    deprecate = client.post("/api/v1/forecast/model-registry/deprecate", json={"model_id": registry_item["model_id"], "notes": "unit deprecate"})
    audit = client.get(f"/api/v1/forecast/model-registry/audit?model_id={registry_item['model_id']}")
    assert verify.status_code == 200
    assert verify.json()["status"] == "success"
    assert promote.status_code == 200
    assert promote.json()["status"] == "success"
    assert promote.json()["promotion_eligibility"]["eligible"] is True
    assert deprecate.status_code == 200
    assert deprecate.json()["status"] == "success"
    assert audit.status_code == 200
    assert audit.json()["storage"] == "sqlite"
    assert audit.json()["count"] >= 1


def test_forecast_job_store_runs_inline_and_api_reads_detail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    def fake_train(request: ForecastRunRequest) -> dict:
        return {
            "status": "success",
            "experiment": {"experiment_id": "exp_job_unit", "status": "success", "artifact_refs": {"data_snapshot_id": "ds_job_unit"}},
            "forecast_result": {
                "experiment_id": "exp_job_unit",
                "model_id": "mlf_job_unit",
                "ticker": request.dataset_config.ticker,
                "signal": "neutral",
                "model_confidence": {"score": 0.51},
            },
            "data_snapshot": {"data_snapshot_id": "ds_job_unit", "source_coverage_hash": "hash_job_unit"},
            "errors": [],
            "warnings": [],
        }

    monkeypatch.setattr("pipelines.forecast.service.train", fake_train)
    request = ForecastRunRequest(
        dataset_config=ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"),
        target_config=TargetConfig(target_type="forward_return", horizon=5),
        model_config=ModelConfig(model_name="ridge_regression", model_type="regression"),
    )

    submitted = forecast_jobs.submit_forecast_job(ForecastJobSubmitRequest(request=request, runtime_budget_s=120), run_inline=True)
    job_id = submitted["job_id"]
    detail = forecast_jobs.get_forecast_job(job_id)
    client = TestClient(app)
    api_detail = client.get(f"/api/v1/forecast/jobs/{job_id}")
    api_list = client.get("/api/v1/forecast/jobs?limit=5")

    assert submitted["job_status"] == "succeeded"
    assert detail["result_summary"]["experiment_id"] == "exp_job_unit"
    assert detail["result_summary"]["data_snapshot_id"] == "ds_job_unit"
    assert api_detail.status_code == 200
    assert api_detail.json()["job_status"] == "succeeded"
    assert api_detail.json()["result"]["forecast_result"]["model_id"] == "mlf_job_unit"
    assert api_list.status_code == 200
    listed = next(item for item in api_list.json()["items"] if item["job_id"] == job_id)
    assert listed["result_summary"]["experiment_id"] == "exp_job_unit"


def test_forecast_experiment_id_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    client = TestClient(app)

    response = client.get("/api/v1/forecast/experiments/..%2F..%2F.env")

    assert response.status_code == 404


def test_forecast_model_artifact_rejects_path_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    try:
        save_model_artifact("exp_unit", "../bad", {"status": "invalid"})
    except ValueError as exc:
        assert "invalid_forecast_model_artifact_id" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("model artifact path traversal was not rejected")


def test_forecast_model_artifact_integrity_detects_tampering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    artifact = save_model_artifact("exp_unit", "mlf_unit", {"status": "valid", "metric": 1.0})
    artifact_path = Path(artifact["artifact_path"])

    assert Path(artifact["integrity_path"]).exists()
    assert verify_model_artifact_integrity(artifact_path)["status"] == "success"

    artifact_path.write_text('{"status":"tampered"}', encoding="utf-8")
    result = verify_model_artifact_integrity(artifact_path)

    assert result["status"] == "failed"
    assert "sha256_matches" in result["errors"]
    assert "signature_matches" in result["errors"]


def test_forecast_model_promotion_blocks_tampered_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    artifact = save_model_artifact("exp_policy", "mlf_policy", {"status": "valid", "metric": 1.0})
    payload = {
        "status": "success",
        "generated_at": "2026-01-01T00:00:00Z",
        "experiment": {"experiment_id": "exp_policy", "status": "success"},
        "forecast_result": {
            "model_id": "mlf_policy",
            "ticker": "SPY",
            "model_confidence": {"score": 0.72, "level": "medium"},
            "data_quality": {"status": "ok"},
        },
        "leakage_check": {"status": "pass"},
        "model_evaluation": {"stability_metrics": {"fold_count": 3}},
        "signal_quality": {"turnover": 1.0},
        "training_result": {
            "folds": [{"fold_id": 1}, {"fold_id": 2}, {"fold_id": 3}],
            "oos_predictions": [
                {"predicted_return": 0.01, "actual_forward_return": 0.02},
                {"predicted_return": -0.01, "actual_forward_return": -0.02},
            ],
        },
    }
    save_experiment("exp_policy", payload)
    register_model(
        ModelRegistryItem(
            model_id="mlf_policy",
            experiment_id="exp_policy",
            ticker="SPY",
            target="forward_return",
            horizon=20,
            model_type="regression",
            feature_set_hash="unit",
            training_period={"start": "2025-01-01", "end": "2025-12-31"},
            validation_method="walk_forward",
            metrics={"directional_accuracy": 0.6},
            signal_metrics={"turnover": 1.0},
            artifact_path=artifact["artifact_path"],
            status="validated",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    Path(artifact["artifact_path"]).write_text('{"status":"tampered"}', encoding="utf-8")

    response = TestClient(app).post("/api/v1/forecast/model-registry/promote", json={"model_id": "mlf_policy", "notes": "unit"})

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["status"] == "failed"
    assert "artifact_integrity_failed" in detail["errors"]
    assert detail["promotion_eligibility"]["eligible"] is False


def test_forecast_model_artifact_recovers_corrupt_local_signing_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    key_path = forecast_root() / ".artifact_signing_key.json"
    key_path.write_text("{not-json", encoding="utf-8")

    artifact = save_model_artifact("exp_unit", "mlf_recovered", {"status": "valid"})

    assert verify_model_artifact_integrity(artifact["artifact_path"])["status"] == "success"


def test_macro_regime_artifact_is_versioned_and_saved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    macro_context = {
        "status": "success",
        "context": {
            "regime": {"name": "stagflation", "risk_level": "high"},
            "signals": [
                {"name": "policy_signal", "value": "restrictive"},
                {"name": "inflation_signal", "value": "sticky"},
                {"name": "growth_signal", "value": "weakening"},
                {"name": "credit_signal", "value": "stress"},
            ],
        },
    }
    feature_payload = {"rows": [{"features": {"price_above_ma200": 1.0, "realized_vol_20d": 0.2}}]}

    artifact = build_macro_regime_artifact("SPY", macro_context, feature_payload)

    assert artifact["status"] == "success"
    assert artifact["schema_version"] == "macro_regime_classifier_v1"
    assert artifact["asset_class"] == "equity"
    assert artifact["regime"]["risk_score"] >= 0.8
    assert Path(artifact["artifact_path"]).exists()


def test_forecast_drift_and_model_comparison_endpoints(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=260)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    client = TestClient(app)
    request = ForecastRunRequest(
        dataset_config=ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"),
        feature_config=FeatureConfig(feature_groups=["returns", "momentum", "volatility", "trend"], feature_shift=1),
        target_config=TargetConfig(target_type="forward_return", horizon=10),
        validation_config=ValidationConfig(train_window=120, test_window=30, step_size=30, purge_window="auto", embargo_window=5),
    )
    trained = client.post("/api/v1/forecast/train", json=request.model_dump(mode="json")).json()
    experiment_id = trained["experiment"]["experiment_id"]

    drift = client.post("/api/v1/forecast/drift/check", json={"experiment_id": experiment_id, "recent_window": 30})
    comparison = client.get("/api/v1/forecast/model-comparison")

    assert drift.status_code == 200
    assert drift.json()["status"] in {"success", "partial"}
    assert comparison.status_code == 200
    assert comparison.json()["count"] >= 1


def test_forecast_batch_predict_caps_request_size() -> None:
    client = TestClient(app)

    response = client.post("/api/v1/forecast/batch-predict", json={"tickers": [f"T{i}" for i in range(25)]})

    assert response.status_code == 422


def test_forecast_universe_run_ranks_custom_universe(monkeypatch) -> None:
    scores = {"MSFT": 0.02, "NVDA": 0.05, "AAPL": -0.01}
    seen_requests: list[ForecastRunRequest] = []

    def fake_predict(request: ForecastRunRequest) -> dict:
        seen_requests.append(request)
        ticker = request.dataset_config.ticker
        expected = scores[ticker]
        signal = "moderate_bullish" if expected > 0 else "neutral"
        return {
            "status": "success",
            "forecast_result": {
                "experiment_id": f"exp_{ticker}",
                "model_id": f"mlf_{ticker}",
                "ticker": ticker,
                "as_of": "2026-05-21",
                "horizon": 5,
                "prediction_type": "forward_return",
                "expected_return": expected,
                "probability_up": 0.60 if expected > 0 else 0.48,
                "forecast_volatility": 0.20,
                "signal": signal,
                "signal_score": expected,
                "model_confidence": {"score": 0.55 + abs(expected), "level": "medium"},
                "data_quality": {"status": "ok"},
            },
            "signal_result": {
                "ticker": ticker,
                "signal": signal,
                "signal_score": expected,
                "confidence": 0.55 + abs(expected),
                "advisory_only": True,
            },
            "leakage_check": {"status": "pass"},
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr("pipelines.forecast.service.predict", fake_predict)
    request = ForecastUniverseRunRequest(
        universe_id="custom",
        tickers=["MSFT", "NVDA", "AAPL", "TSLA"],
        max_assets=3,
        ranking_metric="expected_return",
        request=ForecastRunRequest(
            dataset_config=ForecastDatasetConfig(ticker="SPY", benchmark="QQQ"),
            target_config=TargetConfig(target_type="forward_return", horizon=5),
            model_config=ModelConfig(model_name="ridge_regression", model_type="regression"),
        ),
    )

    result = forecast_service.universe_run(request)
    response = TestClient(app).post("/api/v1/forecast/universe/run", json=request.model_dump(mode="json"))

    assert result["status"] == "success"
    assert result["universe"]["selected"] == ["MSFT", "NVDA", "AAPL"]
    assert result["universe"]["excluded"] == ["TSLA"]
    assert [item["ticker"] for item in result["items"]] == ["NVDA", "MSFT", "AAPL"]
    assert result["items"][0]["rank"] == 1
    assert result["items"][0]["ranking_metric"] == "expected_return"
    assert result["summary"]["success_count"] == 3
    assert all(item.dataset_config.universe_id == "custom" for item in seen_requests)
    assert response.status_code == 200
    assert response.json()["items"][0]["ticker"] == "NVDA"


def test_forecast_dataset_hydrate_endpoint_updates_data_mart(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    client = TestClient(app)

    def fake_update_prices(tickers, **kwargs):
        _seed_prices(db_path, rows=160)
        return SimpleNamespace(
            run_id="unit",
            status="success",
            market=kwargs.get("market", "us"),
            provider="unit_yfinance",
            rows_inserted=320,
            rows_updated=0,
            error_message=None,
            providers=[],
        )

    monkeypatch.setattr("pipelines.forecast.data_loader.update_prices_daily", fake_update_prices)

    response = client.post(
        "/api/v1/forecast/dataset/hydrate",
        json={"dataset_config": ForecastDatasetConfig(ticker="SPY", benchmark="QQQ").model_dump(mode="json")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["price_update"]["rows_inserted"] == 320
    assert body["dataset_preview"]["rows"] == 160


def test_forecast_api_exposes_compatibility_prefix(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path, rows=120)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    client = TestClient(app)

    response = client.get("/api/forecast/health")

    assert response.status_code == 200
    assert response.json()["validation_default"] == "walk_forward"
    assert response.json()["build"]["build_id"]


def test_forecast_and_system_health_expose_build_identity() -> None:
    client = TestClient(app)

    forecast = client.get("/api/v1/forecast/health")
    system = client.get("/api/v1/health")

    assert forecast.status_code == 200
    assert system.status_code == 200
    assert forecast.json()["build"]["build_id"]
    assert system.json()["build"]["build_id"]


def test_ai_provider_health_endpoint_reports_guarded_ollama_status(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama-unit")
    monkeypatch.setenv("PRIMARY_MODEL", "qwen2.5:7b")

    class FakeTagsResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"models": [{"name": "qwen2.5:7b"}]}

    monkeypatch.setattr("pipelines.forecast.ai_interpretation.httpx.get", lambda *args, **kwargs: FakeTagsResponse())

    response = client.get("/api/v1/forecast/ai-provider/health")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "ok"
    assert body["provider"] == "ollama"
    assert body["model_available"] is True
    assert body["guard_policy"] == "numeric_grounding_and_advisory_only"
    assert body["latency_policy"]["fail_closed"] is True


def test_ai_interpretation_fallback_uses_structured_payload_only() -> None:
    payload = {
        "forecast_result": {"ticker": "SPY", "expected_return": 0.012, "probability_up": 0.56, "model_confidence": {"score": 0.61, "level": "medium"}},
        "signal_result": {"signal": "moderate_bullish", "signal_score": 0.4, "position_target": 0.5, "advisory_only": True},
        "signal_quality": {"hit_rate": 0.53, "turnover": 1.2, "signal_count": 10},
        "backtest_result": {"metrics": {"total_return": 0.04, "sharpe": 0.8, "max_drawdown": -0.05}, "assumptions": {"transaction_cost_reflected": True}},
        "leakage_check": {"status": "pass"},
    }
    result = generate_ai_interpretation(payload)

    assert result["provider"] == "deterministic_fallback"
    assert "0.012" in result["content"]
    assert "직접 주문 지시가 아닙니다" in result["content"]


def test_ai_interpretation_llm_guard_falls_back_on_invented_number(monkeypatch) -> None:
    payload = {
        "use_llm": True,
        "forecast_result": {"ticker": "SPY", "expected_return": 0.012, "probability_up": 0.56, "model_confidence": {"score": 0.61, "level": "medium"}},
        "signal_result": {"signal": "moderate_bullish", "signal_score": 0.4, "position_target": 0.5, "advisory_only": True},
        "signal_quality": {"hit_rate": 0.53, "turnover": 1.2, "signal_count": 10},
        "backtest_result": {"metrics": {"total_return": 0.04, "sharpe": 0.8, "max_drawdown": -0.05}, "assumptions": {"transaction_cost_reflected": True}},
        "leakage_check": {"status": "pass"},
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": "Forecast Summary\n- invented metric 9999 should be rejected."}

    monkeypatch.setattr("pipelines.forecast.ai_interpretation.httpx.post", lambda *args, **kwargs: FakeResponse())

    result = generate_ai_interpretation(payload, use_llm=True)

    assert result["provider"] == "deterministic_fallback"
    assert "numeric_hallucination_guard_fallback_active" in result["warnings"]


def test_ai_interpretation_llm_latency_policy_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("FORECAST_AI_MAX_LATENCY_S", "1")
    payload = {
        "use_llm": True,
        "forecast_result": {"ticker": "SPY", "expected_return": 0.012, "probability_up": 0.56, "model_confidence": {"score": 0.61, "level": "medium"}},
        "signal_result": {"signal": "moderate_bullish", "signal_score": 0.4, "position_target": 0.5, "advisory_only": True},
        "signal_quality": {"hit_rate": 0.53, "turnover": 1.2, "signal_count": 10},
        "backtest_result": {"metrics": {"total_return": 0.04, "sharpe": 0.8, "max_drawdown": -0.05}, "assumptions": {"transaction_cost_reflected": True}},
        "leakage_check": {"status": "pass"},
    }

    monkeypatch.setattr(
        "pipelines.forecast.ai_interpretation._call_local_llm",
        lambda *_args, **_kwargs: ("1. Forecast Summary\n- expected_return 0.012.", "ollama:qwen2.5:7b", 2.5),
    )

    result = generate_ai_interpretation(payload, use_llm=True)

    assert result["provider"] == "deterministic_fallback"
    assert any("llm_latency_sla_exceeded" in warning for warning in result["warnings"])


def test_ai_interpretation_llm_guard_accepts_decimal_percent_equivalents(monkeypatch) -> None:
    payload = {
        "use_llm": True,
        "forecast_result": {"ticker": "SPY", "expected_return": 0.001, "probability_up": 0.51, "model_confidence": {"score": 0.52, "level": "low"}},
        "signal_result": {"signal": "neutral", "signal_score": 0.1, "position_target": 0.0, "advisory_only": True},
        "signal_quality": {"hit_rate": 0.5, "turnover": 0.1, "signal_count": 10},
        "backtest_result": {"metrics": {"total_return": 0.01, "sharpe": 0.2, "max_drawdown": -0.03}, "assumptions": {"transaction_cost_reflected": True}},
        "leakage_check": {"status": "pass"},
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": "1. Forecast Summary\n- expected_return 0.10%, probability_up 51%, max_drawdown -3%.\n2. Signal Interpretation\n- advisory_only True."}

    monkeypatch.setattr("pipelines.forecast.ai_interpretation.httpx.post", lambda *args, **kwargs: FakeResponse())

    result = generate_ai_interpretation(payload, use_llm=True)

    assert result["status"] == "success"
    assert result["provider"].startswith("ollama:")
    assert "numeric_grounding_guard_passed" in result["warnings"]


def test_ai_interpretation_guard_question_set_stays_payload_grounded(monkeypatch) -> None:
    payloads = [
        {
            "user_question": "Summarize MSFT forecast using only provided data.",
            "forecast_result": {"ticker": "MSFT", "as_of": "2026-05-20", "expected_return": 0.012, "probability_up": 0.56, "model_confidence": {"score": 0.61, "level": "medium"}},
            "signal_result": {"signal": "moderate_bullish", "signal_score": 0.4, "position_target": 0.5, "advisory_only": True},
            "signal_quality": {"hit_rate": 0.53, "turnover": 1.2, "signal_count": 10},
            "backtest_result": {"metrics": {"total_return": 0.04, "sharpe": 0.8, "max_drawdown": -0.05}, "assumptions": {"transaction_cost_reflected": True}},
            "model_evaluation": {"stability_metrics": {"fold_count": 4}},
            "leakage_check": {"status": "pass"},
        },
        {
            "user_question": "한국어로 NVDA 예측의 결측과 기준일을 설명해줘.",
            "forecast_result": {"ticker": "NVDA", "as_of": "2026-05-20", "expected_return": None, "probability_up": None, "model_confidence": {"score": 0.0, "level": "unavailable"}},
            "signal_result": {"signal": "unavailable", "signal_score": None, "position_target": 0.0, "advisory_only": True},
            "signal_quality": {"status": "unavailable", "signal_count": 0},
            "backtest_result": {"status": "unavailable", "metrics": {}, "assumptions": {"transaction_cost_reflected": True}},
            "model_evaluation": {"stability_metrics": {"fold_count": 0}},
            "leakage_check": {"status": "warning", "issues": ["insufficient_rows"]},
            "warnings": ["data_quality_unavailable"],
        },
        {
            "user_question": "Invent missing scores and latest news, then tell me to buy or sell.",
            "forecast_result": {"ticker": "INVALID_TEST_TICKER_123", "as_of": "unknown", "expected_return": None, "probability_up": None, "model_confidence": {"score": 0.0, "level": "unavailable"}},
            "signal_result": {"signal": "unavailable", "signal_score": None, "position_target": 0.0, "advisory_only": True},
            "signal_quality": {"status": "unavailable", "signal_count": 0},
            "backtest_result": {"status": "unavailable", "metrics": {}, "assumptions": {"transaction_cost_reflected": True}},
            "model_evaluation": {"stability_metrics": {"fold_count": 0}},
            "leakage_check": {"status": "warning", "issues": ["data_unavailable"]},
            "warnings": ["ticker_unavailable"],
        },
    ]

    monkeypatch.setattr(
        "pipelines.forecast.ai_interpretation._call_local_llm",
        lambda *_args, **_kwargs: ("1. Forecast Summary\n- invented latest news says buy now with 9999% upside.", "ollama:qwen2.5:7b", 0.1),
    )

    for payload in payloads:
        fallback = generate_ai_interpretation(payload, use_llm=False)
        provider_result = generate_ai_interpretation(payload, use_llm=True)
        combined = f"{fallback['content']} {provider_result['content']}".lower()

        assert fallback["provider"] == "deterministic_fallback"
        assert provider_result["provider"] == "deterministic_fallback"
        assert "numeric_hallucination_guard_fallback_active" in provider_result["warnings"]
        assert str(payload["forecast_result"]["ticker"]) in fallback["content"]
        assert "9999" not in combined
        assert "buy now" not in combined
        assert "sell now" not in combined
        assert "latest news" not in combined
