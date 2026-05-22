from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.server import app
from pipelines.data_mart.models import PriceBar
from pipelines.data_mart.storage import repository
from pipelines.data_mart.storage.db import init_db
from pipelines.orchestration import quant_lab_pipeline, strategy_research


def _seed_prices(db_path) -> None:
    init_db(db_path)
    rows = []
    for idx in range(140):
        day = (date(2026, 1, 1) + timedelta(days=idx)).isoformat()
        rows.extend(
            [
                PriceBar(ticker="SPY", date=day, close=100 + idx, adjusted_close=100 + idx, source="test"),
                PriceBar(ticker="QQQ", date=day, close=100 + idx * 1.25, adjusted_close=100 + idx * 1.25, source="test"),
                PriceBar(ticker="TLT", date=day, close=100 - idx * 0.08, adjusted_close=100 - idx * 0.08, source="test"),
            ]
        )
    btc_close = 42_000.0
    base_stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for idx in range(220):
        stamp = (base_stamp + timedelta(hours=idx * 4)).isoformat().replace("+00:00", "Z")
        close = 42_000 + idx * 35 + ((idx % 17) - 8) * 120
        rows.append(
            PriceBar(
                ticker="BTCUSDT",
                date=stamp,
                open=btc_close,
                high=max(btc_close, close) * 1.01,
                low=min(btc_close, close) * 0.99,
                close=close,
                adjusted_close=close,
                volume=100_000 + idx,
                source="test_4h",
            )
        )
        btc_close = close
    repository.upsert_prices(rows, db_path=db_path)


def _client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "backtests")
    monkeypatch.setattr(strategy_research, "ARTIFACT_ROOT", tmp_path / "strategy_research")
    return TestClient(app)


def test_strategy_research_backend_status_and_seeded_strategies(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    status = client.get("/api/v1/quant/strategy-research/backend-status")
    strategies = client.get("/api/v1/quant/strategy-research/strategies")
    versions = client.get("/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/versions")

    assert status.status_code == 200
    assert status.json()["schema_version"] == "strategy_research_v1"
    assert status.json()["live_llm_required"] is False
    assert status.json()["optuna_available"] is (importlib.util.find_spec("optuna") is not None)
    assert status.json()["bayesian_backend"] in {"optuna_tpe", "deterministic_surrogate"}
    assert isinstance(status.json()["protected_runtime_details"], dict)
    assert "repo_local_deterministic_evidence_only" in status.json()["warnings"]
    assert strategies.status_code == 200
    ids = [item["strategy_id"] for item in strategies.json()["items"]]
    assert "risk_adjusted_momentum_v1" in ids
    assert "btcusdt_4h_supertrend_research_preset" in ids
    assert versions.status_code == 200
    assert versions.json()["items"][0]["status"] == "accepted"


def test_strategy_research_optimization_persists_trials_and_scores(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/optimize",
        json={
            "method": "bayesian",
            "max_trials": 7,
            "search_space": {
                "lookback": [21, 42, 63],
                "rebalance_every": [10, 21],
                "top_n": [1, 2],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["trial_count"] == 7
    assert body["best_parameters_json"]
    assert body["recommended_parameters_json"]
    assert body["notes_json"]["not_financial_advice"] is True
    assert body["notes_json"]["bayesian_backend"] == "optuna_tpe"
    assert "win_rate" not in body["objective_name"]
    assert body["artifacts"]["optimization_trials"].endswith("optimization-trials.json")

    trials = client.get(f"/api/v1/quant/strategy-research/optimizations/{body['optimization_id']}/trials")
    assert trials.status_code == 200
    assert trials.json()["count"] == 7
    first = trials.json()["items"][0]
    assert "sharpe" in first["metrics_json"]
    assert "profit_factor" in first["metrics_json"]
    assert isinstance(first["constraint_flags_json"]["low_trade_count"], bool)


def test_strategy_research_rejects_invalid_parameters(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/optimize",
        json={
            "method": "grid_search",
            "max_trials": 1,
            "search_space": {"lookback": [1], "rebalance_every": [21], "top_n": [2]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    trials = client.get(f"/api/v1/quant/strategy-research/optimizations/{body['optimization_id']}/trials").json()["items"]
    assert trials[0]["status"] == "failed"
    assert trials[0]["rejection_flags_json"]["invalid_parameters"] is True


def test_strategy_research_diagnostics_hypotheses_and_decisions(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    diagnostics = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/diagnose",
        json={},
    )
    hypotheses = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/hypotheses/generate",
        json={},
    )
    hypotheses_repeat = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/hypotheses/generate",
        json={},
    )

    assert diagnostics.status_code == 200
    diag_body = diagnostics.json()
    assert diag_body["summary"]
    assert diag_body["failure_distribution_json"]
    assert diag_body["cost_impact_analysis"]["cost_to_expectancy_ratio"] >= 0
    assert diag_body["recommended_experiments_json"]
    assert hypotheses.status_code == 200
    assert hypotheses_repeat.status_code == 200
    assert hypotheses.json()["count"] == hypotheses_repeat.json()["count"]
    hypothesis = hypotheses.json()["items"][0]
    assert hypothesis["status"] == "pending"
    assert hypothesis["risk"]
    assert "core_logic" not in hypothesis["proposed_change_json"].get("module", "")
    assert "out_of_sample" in hypothesis["validation_required_json"]

    accepted = client.post(
        f"/api/v1/quant/strategy-research/hypotheses/{hypothesis['hypothesis_id']}/accept",
        json={"decision_reason": "validated in test harness"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"


def test_strategy_research_validation_outputs_evidence_blocks(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    optimize = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/optimize",
        json={"method": "grid_search", "max_trials": 4},
    )
    assert optimize.status_code == 200

    response = client.post(
        "/api/v1/quant/strategy-research/strategies/risk_adjusted_momentum_v1/validate",
        json={"optimization_id": optimize.json()["optimization_id"], "walk_forward_splits": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["in_sample_metrics_json"]
    assert body["out_of_sample_metrics_json"]
    assert len(body["walk_forward_results_json"]) == 3
    assert "stability_score" in body["parameter_stability_json"]
    assert body["monte_carlo_results_json"]["status"] in {"succeeded", "insufficient_evidence"}
    assert len(body["cost_stress_json"]) == 3
    assert body["summary"]["decision"] in {"accepted", "rejected"}
    assert body["summary"]["evidence_notes"]


def test_strategy_research_btcusdt_supertrend_runs_deterministically(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    optimize = client.post(
        "/api/v1/quant/strategy-research/strategies/btcusdt_4h_supertrend_research_preset/optimize",
        json={
            "method": "grid_search",
            "max_trials": 3,
            "search_space": {
                "atr_length": [7, 10],
                "atr_multiplier": [2.0],
                "stop_atr_multiplier": [2.0],
                "take_profit_atr_multiplier": [4.0],
                "use_adx_filter": [False],
                "use_rsi_filter": [False],
                "fee_bps": [5.0],
                "slippage_bps": [5.0],
                "execution_model": ["close_confirmed"],
                "stop_trigger_model": ["close_confirmed", "intrabar"],
            },
            "base_config": {
                "strategy_id": "btcusdt_4h_supertrend_research_preset",
                "tickers": ["BTCUSDT"],
                "benchmark": "BTCUSDT",
                "template": "supertrend_research",
                "timeframe": "4h",
            },
        },
    )

    assert optimize.status_code == 200
    body = optimize.json()
    assert body["status"] == "succeeded"
    assert body["trial_count"] == 3
    assert body["search_space_json"]["stop_trigger_model"] == ["close_confirmed", "intrabar"]

    validate = client.post(
        "/api/v1/quant/strategy-research/strategies/btcusdt_4h_supertrend_research_preset/validate",
        json={
            "optimization_id": body["optimization_id"],
            "parameters": body["recommended_parameters_json"],
            "walk_forward_splits": 2,
            "base_config": {
                "strategy_id": "btcusdt_4h_supertrend_research_preset",
                "tickers": ["BTCUSDT"],
                "benchmark": "BTCUSDT",
                "template": "supertrend_research",
                "timeframe": "4h",
            },
        },
    )
    assert validate.status_code == 200
    assert validate.json()["status"] == "succeeded"
    assert validate.json()["summary"]["evidence_notes"]


def test_strategy_research_protected_runtime_status_is_explicit(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/v1/quant/strategy-research/protected-runtime/status")

    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == "runtime_detection_only"
    assert body["fail_closed"] is True
    assert "lean_cli_available" in body
    assert "live_broker_available" in body
