from __future__ import annotations

import re
import math
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routers import quant_lab as quant_lab_router
from app.api.server import app
from pipelines.data_mart.models import PriceBar
from pipelines.data_mart.storage import repository
from pipelines.data_mart.storage.db import init_db
from pipelines.backtest import artifact_exports
from pipelines.backtest.validation import _current_expected_market_date
from pipelines.orchestration import quant_lab_pipeline


def _seed_prices(db_path) -> None:
    init_db(db_path)
    rows = []
    for idx in range(90):
        day = (date(2026, 1, 1) + timedelta(days=idx)).isoformat()
        rows.extend(
            [
                PriceBar(ticker="SPY", date=day, close=100 + idx, adjusted_close=100 + idx, source="test"),
                PriceBar(ticker="QQQ", date=day, close=100 + idx * 1.3, adjusted_close=100 + idx * 1.3, source="test"),
                PriceBar(ticker="TLT", date=day, close=100 - idx * 0.2, adjusted_close=100 - idx * 0.2, source="test"),
            ]
        )
    repository.upsert_prices(rows, db_path=db_path)


def test_quant_config_and_feature_preview_endpoint(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    client = TestClient(app)

    config = client.get("/api/v1/quant/config")
    preview = client.post("/api/v1/quant/features/preview", json={"tickers": ["SPY", "QQQ"], "benchmark": "SPY"})

    assert config.status_code == 200
    assert any(item["factor_id"] == "momentum_63d" for item in config.json()["factors"])
    assert any(item["factor_id"] == "risk_adjusted_momentum_63d" for item in config.json()["factors"])
    assert "risk_adjusted_momentum" in config.json()["signal_templates"]
    assert preview.status_code == 200
    assert preview.json()["status"] == "success"
    assert preview.json()["rows"][0]["features"]["risk_adjusted_momentum_63d"] is not None
    assert preview.json()["diagnostics"]["freshness_policy"]["policy_id"] == "daily_price_t_plus_3_market_days"


def test_quant_universe_resolve_filters_assets_without_price_history(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    client = TestClient(app)

    response = client.post("/api/v1/quant/universe/resolve", json={"tickers": ["SPY", "005930.KS"], "min_rows": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["available"] == ["SPY"]
    assert body["unavailable"] == ["005930.KS"]
    assert body["price_counts"]["SPY"] == 90
    assert body["price_counts"]["005930.KS"] == 0


def test_quant_universe_resolve_can_hydrate_missing_price_history(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))

    def fake_ensure_price_history(tickers, **kwargs):
        rows = []
        for idx in range(5):
            day = (date(2026, 4, 1) + timedelta(days=idx)).isoformat()
            rows.append(PriceBar(ticker="AVGO", date=day, close=900 + idx, adjusted_close=900 + idx, source="test"))
        repository.upsert_prices(rows, db_path=db_path)
        availability = repository.price_availability(tickers, min_rows=kwargs.get("min_rows", 2), db_path=db_path)
        return {
            "availability": availability,
            "hydration": {
                "enabled": True,
                "attempted": True,
                "hydrated": ["AVGO"],
                "hydrated_count": 1,
                "still_unavailable": [],
                "still_unavailable_count": 0,
                "rows_inserted": len(rows),
                "rows_updated": 0,
            },
        }

    monkeypatch.setattr(quant_lab_router, "ensure_price_history", fake_ensure_price_history)
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/universe/resolve",
        json={"tickers": ["SPY", "AVGO"], "min_rows": 2, "hydrate_missing": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["available"] == ["SPY", "AVGO"]
    assert body["unavailable"] == []
    assert body["hydration"]["hydrated"] == ["AVGO"]
    assert body["price_counts"]["AVGO"] == 5


def test_quant_universe_resolve_refreshes_stale_price_history(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    expected = _current_expected_market_date().isoformat()

    def fake_update_prices_daily(tickers, **kwargs):
        rows = [
            PriceBar(ticker=ticker, date=expected, close=200, adjusted_close=200, source="test")
            for ticker in tickers
        ]
        counts = repository.upsert_prices(rows, db_path=db_path)
        return SimpleNamespace(
            run_id="stale-refresh-run",
            status="success",
            rows_inserted=counts["inserted"],
            rows_updated=counts["updated"],
            error_message=None,
            providers=[SimpleNamespace(detail={"failed_tickers": {}})],
        )

    monkeypatch.setattr(quant_lab_router, "update_prices_daily", fake_update_prices_daily)
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/universe/resolve",
        json={
            "tickers": ["SPY", "QQQ"],
            "min_rows": 2,
            "freshness_profile": "decision_review",
            "refresh_stale": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["strict_freshness_violation"] is False
    assert body["stale_assets"] == []
    assert body["asset_freshness"]["SPY"]["freshness_status"] == "fresh"
    assert body["asset_freshness"]["QQQ"]["latest_price_date"] == expected
    assert body["hydration"]["stale_refresh_attempted"] is True
    assert body["hydration"]["stale_candidates"] == ["SPY", "QQQ"]
    assert body["hydration"]["stale_refreshed"] == ["SPY", "QQQ"]


def test_quant_backtest_excludes_unavailable_assets_without_missing_assets(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/backtest",
        json={"tickers": ["SPY", "QQQ", "005930.KS"], "benchmark": "SPY", "lookback": 21, "top_n": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["tickers"] == ["SPY", "QQQ"]
    assert body["diagnostics"]["missing_assets"] == []
    assert body["diagnostics"]["excluded_assets"] == ["005930.KS"]
    assert "excluded_unavailable_assets:005930.KS" in body["diagnostics"]["warnings"]


def test_qlib_status_is_disabled_by_default() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/quant/qlib/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["startup_required"] is False


def test_qlib_export_preview_is_disabled_by_default() -> None:
    client = TestClient(app)

    response = client.post("/api/v1/quant/qlib/export", json={"tickers": ["SPY"], "start_date": "2024-01-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["export_ready"] is False
    assert body["requested"]["tickers"] == ["SPY"]


def test_quant_backtest_endpoint_persists_manifest(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/backtest",
        json={"tickers": ["SPY", "QQQ", "TLT"], "benchmark": "SPY", "lookback": 21, "top_n": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["diagnostics"]["lookahead_safe"] is True
    assert "weights" in body
    runs = client.get("/api/v1/quant/backtests?limit=5")
    assert runs.status_code == 200
    assert any(item["run_id"] == body["run_id"] for item in runs.json()["items"])
    run_item = next(item for item in runs.json()["items"] if item["run_id"] == body["run_id"])
    assert run_item["config_hash"]
    assert run_item["data_snapshot"]["price_counts"]["SPY"] == 90
    bundle = client.get(f"/api/v1/quant/backtest/{body['run_id']}/bundle")
    assert bundle.status_code == 200
    assert bundle.json()["manifest"]["run_id"] == body["run_id"]
    assert bundle.json()["manifest"]["schema_version"] == "quant_lab_artifact_v1"
    assert bundle.json()["manifest"]["data_snapshot"]["price_counts"]["SPY"] == 90
    metrics = client.get(f"/api/v1/quant/backtest/{body['run_id']}/metrics")
    assert metrics.status_code == 200
    assert "sharpe" in metrics.json()
    diagnostics = client.get(f"/api/v1/quant/backtest/{body['run_id']}/diagnostics")
    assert diagnostics.status_code == 200
    assert diagnostics.json()["lookahead_safe"] is True
    equity_curve = client.get(f"/api/v1/quant/backtest/{body['run_id']}/equity-curve")
    assert equity_curve.status_code == 200
    assert equity_curve.json()
    bundle = client.get(f"/api/v1/quant/backtest/{body['run_id']}/bundle")
    assert bundle.status_code == 200
    assert bundle.json()["config"]["tickers"] == ["SPY", "QQQ", "TLT"]
    replay = client.post(f"/api/v1/quant/backtest/{body['run_id']}/replay")
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["status"] == "success"
    assert replay_body["config_hash_match"] is True
    assert replay_body["metric_deltas"]["total_return"] == 0
    assert replay_body["tolerance_passed"] is True
    assert replay_body["report_path"]
    assert replay_body["report_history"]["count"] == 1
    bundle_after_replay = client.get(f"/api/v1/quant/backtest/{body['run_id']}/bundle")
    assert bundle_after_replay.status_code == 200
    assert bundle_after_replay.json()["replay_report"]["schema_version"] == "quant_lab_replay_report_v1"
    assert bundle_after_replay.json()["replay_reports"]["count"] == 1
    replay_reports = client.get(f"/api/v1/quant/backtest/{body['run_id']}/replay-reports")
    assert replay_reports.status_code == 200
    assert replay_reports.json()["items"][0]["tolerance_passed"] is True
    jsonl_export = client.post(
        f"/api/v1/quant/backtest/{body['run_id']}/export",
        json={"format": "jsonl", "keep_last_exports": 2},
    )
    csv_export = client.post(f"/api/v1/quant/backtest/{body['run_id']}/export", json={"format": "csv"})
    parquet_export = client.post(f"/api/v1/quant/backtest/{body['run_id']}/export", json={"format": "parquet"})
    bad_export = client.post(f"/api/v1/quant/backtest/{body['run_id']}/export", json={"format": "xlsx"})
    assert jsonl_export.status_code == 200
    assert jsonl_export.json()["files"]["jsonl"].endswith("artifact_bundle.jsonl")
    assert len(jsonl_export.json()["integrity"]["files"]["jsonl"]["sha256"]) == 64
    assert jsonl_export.json()["retention"]["keep_last_exports"] == 2
    assert csv_export.status_code == 200
    assert "metrics" in csv_export.json()["files"]
    exports = client.get(f"/api/v1/quant/backtest/{body['run_id']}/exports")
    assert exports.status_code == 200
    assert exports.json()["count"] >= 2
    assert exports.json()["items"][0]["integrity_available"] is True
    verify_latest = client.post(f"/api/v1/quant/backtest/{body['run_id']}/export/verify", json={})
    assert verify_latest.status_code == 200
    assert verify_latest.json()["status"] == "success"
    assert verify_latest.json()["files_failed"] == 0
    jsonl_manifest = jsonl_export.json()["files"]["manifest"]
    verify_jsonl = client.post(
        f"/api/v1/quant/backtest/{body['run_id']}/export/verify",
        json={"export_manifest_path": jsonl_manifest},
    )
    assert verify_jsonl.status_code == 200
    assert verify_jsonl.json()["status"] == "success"
    Path(jsonl_export.json()["files"]["jsonl"]).write_text("tampered\n", encoding="utf-8")
    verify_tampered = client.post(
        f"/api/v1/quant/backtest/{body['run_id']}/export/verify",
        json={"export_manifest_path": jsonl_manifest},
    )
    assert verify_tampered.status_code == 200
    assert verify_tampered.json()["status"] == "partial"
    assert verify_tampered.json()["files_failed"] == 1
    assert parquet_export.status_code == 200
    assert parquet_export.json()["status"] in {"success", "dependency_missing"}
    if parquet_export.json()["status"] == "success":
        assert parquet_export.json()["files"]["metrics"].endswith(".parquet")
    else:
        assert parquet_export.json()["export_written"] is False
    assert bad_export.status_code == 400


def test_quant_backtests_compare_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")
    client = TestClient(app)

    primary = client.post(
        "/api/v1/quant/backtest",
        json={"tickers": ["SPY", "QQQ", "TLT"], "benchmark": "SPY", "lookback": 21, "top_n": 1},
    )
    comparison = client.post(
        "/api/v1/quant/backtest",
        json={"tickers": ["SPY", "QQQ", "TLT"], "benchmark": "SPY", "lookback": 21, "top_n": 2},
    )
    assert primary.status_code == 200
    assert comparison.status_code == 200
    before = sorted(path.name for path in (tmp_path / "artifacts").iterdir() if path.is_dir())

    response = client.post(
        "/api/v1/quant/backtests/compare",
        json={"run_ids": [primary.json()["run_id"], comparison.json()["run_id"]]},
    )
    after = sorted(path.name for path in (tmp_path / "artifacts").iterdir() if path.is_dir())

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "quant_lab_run_compare_v1"
    assert body["lineage"]["config_hash_match"] is False
    assert any(row["field"] == "top_n" for row in body["config_differences"])
    assert any(row["metric"] == "sharpe" for row in body["metrics"])
    assert body["diagnostics"]["lookahead_safe_all"] is True
    assert before == after


def test_export_cleanup_preview_and_apply_endpoint(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")
    client = TestClient(app)

    backtest = client.post(
        "/api/v1/quant/backtest",
        json={"tickers": ["SPY", "QQQ", "TLT"], "benchmark": "SPY", "lookback": 21, "top_n": 2},
    )
    assert backtest.status_code == 200
    run_id = backtest.json()["run_id"]
    for export_format in ["jsonl", "csv", "jsonl"]:
        response = client.post(f"/api/v1/quant/backtest/{run_id}/export", json={"format": export_format})
        assert response.status_code == 200

    preview = client.get(f"/api/v1/quant/backtest/{run_id}/exports/cleanup-preview?keep_last_exports=1")

    assert preview.status_code == 200
    preview_body = preview.json()
    assert preview_body["cleanup_applied"] is False
    assert preview_body["export_count"] == 3
    assert preview_body["prune_export_count"] == 2
    storage = client.get("/api/v1/quant/exports/storage?limit=5&stale_after_days=0")
    assert storage.status_code == 200
    storage_body = storage.json()
    assert storage_body["status"] == "success"
    assert storage_body["schema_version"] == "quant_lab_export_storage_report_v1"
    assert storage_body["runs_with_exports"] >= 1
    assert storage_body["export_directory_count"] == 3
    assert storage_body["total_bytes"] > 0
    cross_preview = client.get("/api/v1/quant/exports/cleanup-preview?keep_last_exports=1&stale_after_days=0&limit=10")
    assert cross_preview.status_code == 200
    cross_preview_body = cross_preview.json()
    assert cross_preview_body["schema_version"] == "quant_lab_cross_run_export_cleanup_v1"
    assert cross_preview_body["cleanup_applied"] is False
    assert cross_preview_body["candidate_count"] == 2
    bad_cross_cleanup = client.post(
        "/api/v1/quant/exports/cleanup",
        json={
            "preview_id": "stale-preview",
            "candidate_ids": cross_preview_body["candidate_ids"],
            "keep_last_exports": 1,
            "stale_after_days": 0,
            "limit": 10,
        },
    )
    assert bad_cross_cleanup.status_code == 400
    exports_before = client.get(f"/api/v1/quant/backtest/{run_id}/exports")
    assert exports_before.status_code == 200
    assert exports_before.json()["count"] == 3

    cleanup = client.post(
        "/api/v1/quant/exports/cleanup",
        json={
            "preview_id": cross_preview_body["preview_id"],
            "candidate_ids": cross_preview_body["candidate_ids"],
            "keep_last_exports": 1,
            "stale_after_days": 0,
            "limit": 10,
        },
    )

    assert cleanup.status_code == 200
    cleanup_body = cleanup.json()
    assert cleanup_body["cleanup_applied"] is True
    assert cleanup_body["pruned_export_count"] == 2
    exports_after = client.get(f"/api/v1/quant/backtest/{run_id}/exports")
    assert exports_after.status_code == 200
    assert exports_after.json()["count"] == 1


def test_export_retention_rejects_current_export_outside_exports_root(tmp_path) -> None:
    exports_root = tmp_path / "run" / "exports"
    exports_root.mkdir(parents=True)
    current_export = tmp_path / "outside" / "20260515T000000_jsonl"
    current_export.mkdir(parents=True)

    try:
        artifact_exports._apply_export_retention(
            exports_root=exports_root,
            current_export_dir=current_export,
            keep_last_exports=1,
        )
    except ValueError as exc:
        assert "current export directory must stay within its run exports directory" in str(exc)
    else:  # pragma: no cover - defensive assertion path
        raise AssertionError("retention should reject export directories outside exports_root")


def test_strategy_dry_run_validates_no_lookahead_policy() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/strategy/dry-run",
        json={
            "strategy_id": "bad_execution_v1",
            "features": {"momentum_63d": {"id": "momentum_63d"}},
            "execution": {"trade_at": "same_bar_close"},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["valid"] is False


def test_strategy_migration_endpoint_normalizes_legacy_payload() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/strategy/migrate",
        json={
            "strategy_id": "legacy_momentum",
            "schema_version": "quant_strategy_v0",
            "execution": {"trade_at": "next_bar_close"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["strategy"]["schema_version"] == "quant_strategy_v1"
    assert body["migrations"][0]["from_schema_version"] == "quant_strategy_v0"


def test_strategy_generate_endpoint_returns_code_only_strategy_without_llm() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/strategy/generate",
        json={
            "prompt": "63일 모멘텀 상위 2개, 21일 변동성 확인, 다음 봉 체결",
            "context": {"top_n": 2, "lookback": 63, "transaction_cost_bps": 5, "slippage_bps": 2},
            "use_local_llm": False,
            "parameter_tuning": {"enabled": True, "objective": "turnover_control"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["model_status"] == "deterministic_fallback"
    assert body["llm_diagnostics"]["status"] == "not_requested"
    assert body["progress"]["percent"] == 100
    assert body["parameter_tuning"]["enabled"] is True
    assert body["parameter_tuning"]["applied_values"]["rebalance_every"] >= 21
    assert "universe" not in body["strategy"]
    assert "benchmark" not in body["strategy"]
    assert body["strategy"]["execution"]["trade_at"] == "next_bar_close"
    assert body["advantages"]
    assert body["disadvantages"]
    cjk_or_japanese = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")
    for text in [*body["advantages"], *body["disadvantages"]]:
        assert re.search(r"[\uac00-\ud7a3]", text)
        assert not cjk_or_japanese.search(text)


def test_python_strategy_run_endpoint_returns_code_backtest_and_optimization(monkeypatch) -> None:
    rows = []
    prev_close = 100.0
    for idx in range(220):
        day = (date(2025, 1, 1) + timedelta(days=idx)).isoformat()
        close = 100.0 + math.sin(idx / 6.0) * 8.0 + idx * 0.02
        rows.append(
            {
                "ticker": "SPY",
                "date": day,
                "open": prev_close,
                "high": max(prev_close, close) * 1.02,
                "low": min(prev_close, close) * 0.98,
                "close": close,
                "adjusted_close": close,
                "source": "test",
            }
        )
        prev_close = close
    monkeypatch.setattr("pipelines.strategies.python_generator.get_prices", lambda ticker, limit=252: rows[-limit:])
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/python-strategy/run",
        json={
            "prompt": "Supertrend 전략을 Python으로 만들고 atr/factor/손절/익절을 Bayesian 최적화해줘.",
            "ticker": "SPY",
            "use_local_llm": False,
            "max_trials": 6,
            "parameter_overrides": {"atr_period": 7, "factor": 1.5, "enable_short": True, "use_sltp": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["language"] == "python"
    assert "def generate_signals" in body["code"]
    assert body["validation"]["valid"] is True
    assert body["backtest"]["status"] == "success"
    assert body["backtest"]["chart"]["markers"]
    assert body["optimization"]["status"] == "success"
    assert body["optimization"]["trial_count"] <= 6


def test_python_strategy_run_endpoint_supports_moving_average_family(monkeypatch) -> None:
    rows = []
    prev_close = 100.0
    for idx in range(220):
        day = (date(2025, 1, 1) + timedelta(days=idx)).isoformat()
        close = 100.0 + math.sin(idx / 7.0) * 10.0 + idx * 0.01
        rows.append(
            {
                "ticker": "SPY",
                "date": day,
                "open": prev_close,
                "high": max(prev_close, close) * 1.02,
                "low": min(prev_close, close) * 0.98,
                "close": close,
                "adjusted_close": close,
                "source": "test",
            }
        )
        prev_close = close
    monkeypatch.setattr("pipelines.strategies.python_generator.get_prices", lambda ticker, limit=252: rows[-limit:])
    client = TestClient(app)

    response = client.post(
        "/api/v1/quant/python-strategy/run",
        json={
            "prompt": "Create a moving average crossover Python strategy and optimize fast/slow windows.",
            "ticker": "SPY",
            "use_local_llm": False,
            "max_trials": 6,
            "parameter_overrides": {"fast_window": 5, "slow_window": 25, "enable_short": True},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["family"] == "moving_average_crossover"
    assert "def simple_moving_average" in body["code"]
    assert body["backtest"]["status"] == "success"
    assert body["backtest"]["chart"]["indicators"]["overlays"][0]["key"] == "fast_ma"
    assert body["optimization"]["status"] == "success"
    assert set(body["optimization"]["recommended_parameters"]) <= {item["name"] for item in body["parameter_manifest"]}


def test_model_profile_api_roundtrip_and_dry_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quant_lab_router, "ARTIFACT_ROOT", tmp_path / "backtests")
    client = TestClient(app)
    profile = {
        "profile_id": "api_model_profile_v1",
        "schema_version": "quant_model_profile_v1",
        "strategy_id": "momentum_ranking_v1",
        "universe_id": "custom",
        "tickers": ["MSFT", "NVDA"],
        "benchmark": "QQQ",
        "target_config": {"target_type": "forward_return", "horizon": 5, "benchmark": "QQQ"},
        "model_candidates": [{"model_name": "ridge_regression", "model_type": "regression"}],
        "backtest_config": {"execution_delay_bars": 1, "benchmark": "QQQ"},
        "ranking_metric": "expected_return",
        "max_assets": 2,
        "run_mode": "universe_per_asset",
    }
    strategy = {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}}

    dry_run = client.post("/api/v1/quant/model-profile/dry-run", json={"profile": profile, "strategy": strategy})
    saved = client.post("/api/v1/quant/model-profile/save", json=profile)
    listed = client.get("/api/v1/quant/model-profile/list")
    detail = client.get("/api/v1/quant/model-profile/api_model_profile_v1")
    deleted = client.delete("/api/v1/quant/model-profile/api_model_profile_v1")

    assert dry_run.status_code == 200
    assert dry_run.json()["valid"] is True
    assert dry_run.json()["diagnostics"]["source_context"]["source"] == "quant_model_lab"
    assert saved.status_code == 200
    assert saved.json()["profile"]["profile_id"] == "api_model_profile_v1"
    assert listed.status_code == 200
    assert any(item["profile_id"] == "api_model_profile_v1" for item in listed.json()["items"])
    assert detail.status_code == 200
    assert detail.json()["benchmark"] == "QQQ"
    assert deleted.status_code == 200


def test_model_lab_run_uses_forecast_universe_adapter(monkeypatch) -> None:
    client = TestClient(app)
    seen = {}

    def fake_universe_run(request):
        seen["request"] = request
        return {
            "status": "success",
            "items": [{"ticker": "NVDA", "status": "success", "rank": 1, "rank_score": 0.05, "ranking_metric": "expected_return"}],
            "summary": {"success_count": 1, "failed_count": 0},
            "universe": {"selected_count": 1, "resolved_count": 1, "selected": ["NVDA"]},
            "ranking_metric": "expected_return",
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr("pipelines.orchestration.quant_model_lab.forecast_service.universe_run", fake_universe_run)
    response = client.post(
        "/api/v1/quant/model-lab/run",
        json={
            "profile": {
                "profile_id": "run_profile_v1",
                "schema_version": "quant_model_profile_v1",
                "strategy_id": "momentum_ranking_v1",
                "universe_id": "custom",
                "tickers": ["NVDA"],
                "benchmark": "QQQ",
                "model_candidates": [{"model_name": "ridge_regression", "model_type": "regression"}],
                "backtest_config": {"execution_delay_bars": 1, "benchmark": "QQQ"},
                "ranking_metric": "expected_return",
                "max_assets": 1,
                "run_mode": "universe_per_asset",
            },
            "strategy": {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["model_lab"]["profile_id"] == "run_profile_v1"
    assert body["model_lab"]["strategy_id"] == "momentum_ranking_v1"
    assert body["model_lab"]["profile_hash"]
    assert seen["request"].request.source_context.source == "quant_model_lab"
    assert seen["request"].request.source_context.profile_id == "run_profile_v1"


def test_model_lab_cross_sectional_rank_returns_panel_ranker(monkeypatch) -> None:
    client = TestClient(app)
    seen = {}

    def fake_universe_run(request):
        seen["request"] = request
        return {
            "status": "success",
            "items": [
                {
                    "ticker": "NVDA",
                    "status": "success",
                    "rank": 1,
                    "rank_score": 0.074,
                    "ranking_metric": "expected_return",
                    "signal": "bullish",
                    "expected_return": 0.074,
                    "probability_up": 0.64,
                    "confidence": 0.71,
                    "forecast_volatility": 0.19,
                    "data_quality_status": "fresh",
                    "leakage_status": "passed",
                },
                {
                    "ticker": "MSFT",
                    "status": "success",
                    "rank": 2,
                    "rank_score": 0.031,
                    "ranking_metric": "expected_return",
                    "signal": "neutral",
                    "expected_return": 0.031,
                    "probability_up": 0.57,
                    "confidence": 0.62,
                    "forecast_volatility": 0.16,
                    "data_quality_status": "fresh",
                    "leakage_status": "passed",
                },
                {
                    "ticker": "AAPL",
                    "status": "failed",
                    "rank": None,
                    "rank_score": None,
                    "ranking_metric": "expected_return",
                    "errors": ["forecast_unavailable"],
                },
            ],
            "summary": {"success_count": 2, "failed_count": 1},
            "universe": {"selected_count": 3, "resolved_count": 3, "selected": ["NVDA", "MSFT", "AAPL"]},
            "ranking_metric": "expected_return",
            "warnings": [],
            "errors": ["forecast_unavailable"],
        }

    monkeypatch.setattr("pipelines.orchestration.quant_model_lab.forecast_service.universe_run", fake_universe_run)
    response = client.post(
        "/api/v1/quant/model-lab/run",
        json={
            "profile": {
                "profile_id": "cross_rank_profile_v1",
                "schema_version": "quant_model_profile_v1",
                "strategy_id": "momentum_ranking_v1",
                "universe_id": "custom",
                "tickers": ["NVDA", "MSFT", "AAPL"],
                "benchmark": "QQQ",
                "model_candidates": [{"model_name": "ridge_regression", "model_type": "regression"}],
                "backtest_config": {"execution_delay_bars": 1, "benchmark": "QQQ"},
                "ranking_metric": "expected_return",
                "max_assets": 3,
                "run_mode": "cross_sectional_rank",
            },
            "strategy": {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["model_lab"]["run_mode"] == "cross_sectional_rank"
    assert body["panel_ranker"]["schema_version"] == "quant_model_lab_cross_sectional_rank_v1"
    assert body["panel_ranker"]["status"] == "ready"
    assert body["panel_ranker"]["top_candidate"]["ticker"] == "NVDA"
    assert body["panel_ranker"]["ranked_count"] == 2
    assert body["panel_ranker"]["blocked_count"] == 1
    assert body["summary"]["rank_spread_to_second"] == 0.043
    assert "cross_sectional_rank_hidden_until_panel_ranker_validation" not in body.get("errors", [])
    assert seen["request"].ranking_metric == "expected_return"


def test_model_profile_dry_run_exposes_cross_sectional_rank_guardrails() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/quant/model-profile/dry-run",
        json={
            "profile": {
                "profile_id": "cross_rank_dry_run_v1",
                "schema_version": "quant_model_profile_v1",
                "strategy_id": "momentum_ranking_v1",
                "universe_id": "custom",
                "tickers": ["NVDA", "MSFT"],
                "benchmark": "QQQ",
                "model_candidates": [{"model_name": "ridge_regression", "model_type": "regression"}],
                "backtest_config": {"execution_delay_bars": 1, "benchmark": "QQQ"},
                "ranking_metric": "risk_adjusted",
                "max_assets": 2,
                "run_mode": "cross_sectional_rank",
            },
            "strategy": {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["diagnostics"]["run_mode"] == "cross_sectional_rank"
    assert body["diagnostics"]["panel_ranker"]["schema_version"] == "quant_model_lab_cross_sectional_rank_v1"
    assert body["diagnostics"]["panel_ranker"]["ranking_metric"] == "risk_adjusted"
    assert "cross_sectional_rank_hidden_until_panel_ranker_validation" not in body.get("warnings", [])


def test_model_lab_cross_sectional_rank_can_queue_per_asset_jobs(monkeypatch) -> None:
    client = TestClient(app)
    submitted = []

    def fake_submit(request, *, run_inline=False):
        ticker = request.request.dataset_config.ticker
        submitted.append((ticker, request.notes, run_inline))
        return {
            "job_id": f"job_{ticker}",
            "job_status": "queued",
            "ticker": ticker,
            "model_name": request.request.ml_model_config.model_name,
            "target": request.request.target_config.target_type,
        }

    monkeypatch.setattr("pipelines.orchestration.quant_model_lab.forecast_jobs.submit_forecast_job", fake_submit)
    response = client.post(
        "/api/v1/quant/model-lab/job",
        json={
            "profile": {
                "profile_id": "cross_rank_job_v1",
                "schema_version": "quant_model_profile_v1",
                "strategy_id": "momentum_ranking_v1",
                "universe_id": "custom",
                "tickers": ["NVDA", "MSFT"],
                "benchmark": "QQQ",
                "model_candidates": [{"model_name": "ridge_regression", "model_type": "regression"}],
                "backtest_config": {"execution_delay_bars": 1, "benchmark": "QQQ"},
                "ranking_metric": "confidence",
                "max_assets": 2,
                "run_mode": "cross_sectional_rank",
            },
            "strategy": {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}},
            "runtime_budget_s": 600,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["job_mode"] == "cross_sectional_rank"
    assert body["panel_ranker"]["status"] == "queued"
    assert body["panel_ranker"]["job_count"] == 2
    assert [ticker for ticker, _notes, _inline in submitted] == ["NVDA", "MSFT"]
    assert all("mode=cross_sectional_rank" in notes for _ticker, notes, _inline in submitted)
