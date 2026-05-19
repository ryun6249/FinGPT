from __future__ import annotations

import re
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
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["model_status"] == "deterministic_fallback"
    assert "universe" not in body["strategy"]
    assert "benchmark" not in body["strategy"]
    assert body["strategy"]["execution"]["trade_at"] == "next_bar_close"
    assert body["advantages"]
    assert body["disadvantages"]
    cjk_or_japanese = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")
    for text in [*body["advantages"], *body["disadvantages"]]:
        assert re.search(r"[\uac00-\ud7a3]", text)
        assert not cjk_or_japanese.search(text)
