from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

from core.schemas.quant import QuantBacktestRequest, QuantFeaturePreviewRequest, QuantSignalGenerateRequest
from pipelines.data_mart.models import PriceBar
from pipelines.data_mart.storage import repository
from pipelines.data_mart.storage.db import init_db
from pipelines.output.run_history import _connect
from pipelines.orchestration import quant_lab_pipeline
from pipelines.orchestration.quant_lab_pipeline import (
    cleanup_backtest_exports,
    cleanup_cross_run_exports,
    compare_backtest_replay,
    compare_backtest_runs,
    export_backtest_artifacts,
    export_storage_report,
    feature_preview,
    load_backtest_artifact,
    list_backtest_runs,
    list_replay_reports,
    preview_backtest_export_cleanup,
    preview_cross_run_export_cleanup,
    replay_backtest_from_manifest,
    run_quant_backtest,
    signal_preview,
)
from pipelines.backtest.artifact_exports import verify_export_package
from pipelines.backtest.validation import _current_expected_market_date


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_expected_market_date_uses_new_york_market_clock() -> None:
    assert _current_expected_market_date(datetime(2026, 5, 17, 15, tzinfo=timezone.utc)) == date(2026, 5, 15)
    assert _current_expected_market_date(datetime(2026, 5, 18, 12, tzinfo=timezone.utc)) == date(2026, 5, 15)
    assert _current_expected_market_date(datetime(2026, 5, 18, 14, tzinfo=timezone.utc)) == date(2026, 5, 18)


def _seed_prices(db_path) -> None:
    init_db(db_path)
    rows = []
    for idx in range(90):
        day = (date(2026, 1, 1) + timedelta(days=idx)).isoformat()
        rows.extend(
            [
                PriceBar(ticker="SPY", date=day, close=100 + idx, adjusted_close=100 + idx, source="test"),
                PriceBar(ticker="QQQ", date=day, close=100 + idx * 1.2, adjusted_close=100 + idx * 1.2, source="test"),
                PriceBar(ticker="TLT", date=day, close=100 - idx * 0.1, adjusted_close=100 - idx * 0.1, source="test"),
            ]
        )
    repository.upsert_prices(rows, db_path=db_path)


def _seed_latest_research_run(root: Path, outputs_dir: Path, response: dict) -> None:
    run_dir = outputs_dir / "runs" / "SPY" / "20260504T000000Z_abc123"
    run_dir.mkdir(parents=True)
    (run_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
    with _connect(root / "runs.db") as conn:
        conn.execute(
            """
            INSERT INTO runs
              (id, ticker, question, status, sentiment, confidence, model,
               lookback_days, top_k, sources, created_at, run_dir, error_metadata)
            VALUES
              ('abc123', 'SPY', 'q', 'success', 'bullish', 0.8, 'test-model',
               30, 5, '[]', '2026-05-04T00:00:00Z', 'outputs/runs/SPY/20260504T000000Z_abc123', NULL)
            """
        )
        conn.commit()


def _signal_preview_for_research_response(root: Path, monkeypatch, response: dict):
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    outputs_dir = root / "outputs"
    _seed_latest_research_run(root, outputs_dir, response)
    monkeypatch.setattr(quant_lab_pipeline, "load_settings", lambda: type("S", (), {"outputs_dir": outputs_dir})())
    return signal_preview(
        QuantSignalGenerateRequest(tickers=["SPY"], benchmark="SPY", use_research_score=True, research_max_age_days=30)
    )


def test_feature_and_signal_preview_use_data_mart(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))

    features = feature_preview(QuantFeaturePreviewRequest(tickers=["SPY", "QQQ"], benchmark="SPY"))
    signals = signal_preview(QuantSignalGenerateRequest(tickers=["SPY", "QQQ"], benchmark="SPY"))

    assert features.status == "success"
    assert features.rows[0].features["momentum_63d"] is not None
    assert features.rows[0].features["risk_adjusted_momentum_63d"] is not None
    assert features.diagnostics.freshness_policy["policy_id"] == "daily_price_t_plus_3_market_days"
    assert features.diagnostics.asset_freshness["SPY"]["latest_price_date"] == "2026-03-31"
    assert signals.rows[0].lookahead_policy == "close_signal_next_bar_execution"


def test_feature_preview_audits_benchmark_price_freshness(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    init_db(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    expected_latest = _current_expected_market_date()
    rows = []
    for idx in range(90):
        qqq_day = (expected_latest - timedelta(days=89 - idx)).isoformat()
        spy_day = (expected_latest - timedelta(days=180 - idx)).isoformat()
        rows.extend(
            [
                PriceBar(ticker="QQQ", date=qqq_day, close=100 + idx, adjusted_close=100 + idx, source="test"),
                PriceBar(ticker="SPY", date=spy_day, close=90 + idx, adjusted_close=90 + idx, source="test"),
            ]
        )
    repository.upsert_prices(rows, db_path=db_path)

    features = feature_preview(
        QuantFeaturePreviewRequest(tickers=["QQQ"], benchmark="SPY", freshness_profile="decision_review")
    )

    assert features.status == "partial"
    assert features.diagnostics.latest_price_dates["QQQ"] == expected_latest.isoformat()
    assert features.diagnostics.asset_freshness["SPY"]["freshness_status"] == "stale"
    assert "SPY" in features.diagnostics.stale_assets
    assert "strict_freshness_violation" in features.warnings


def test_strict_freshness_marks_stale_preview_partial_and_backtest_failed(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    features = feature_preview(
        QuantFeaturePreviewRequest(tickers=["SPY", "QQQ"], benchmark="SPY", require_fresh_prices=True)
    )
    result = run_quant_backtest(
        QuantBacktestRequest(tickers=["SPY", "QQQ"], benchmark="SPY", lookback=21, require_fresh_prices=True)
    )

    assert features.status == "partial"
    assert "strict_freshness_violation" in features.warnings
    assert result.status == "failed"
    assert result.diagnostics.freshness_policy["require_fresh_prices"] is True
    assert "strict_freshness_violation" in result.diagnostics.warnings


def test_decision_review_profile_resolves_to_strict_freshness(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))

    features = feature_preview(QuantFeaturePreviewRequest(tickers=["SPY"], freshness_profile="decision_review"))
    backtest = run_quant_backtest(QuantBacktestRequest(tickers=["SPY", "QQQ"], freshness_profile="decision_review"))

    assert features.status == "partial"
    assert features.diagnostics.freshness_policy["profile"] == "decision_review"
    assert features.diagnostics.freshness_policy["require_fresh_prices"] is True
    assert features.diagnostics.freshness_policy["max_market_calendar_lag_days"] == 1
    assert backtest.status == "failed"
    assert backtest.diagnostics.freshness_policy["profile"] == "decision_review"
    assert backtest.diagnostics.freshness_policy["require_fresh_prices"] is True
    assert backtest.diagnostics.freshness_policy["max_market_calendar_lag_days"] == 1


def test_quant_backtest_writes_artifacts_and_keeps_no_lookahead(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )

    assert result.status == "success"
    assert result.diagnostics.lookahead_safe is True
    assert result.diagnostics.signal_shift_bars == 1
    assert result.artifacts is not None
    assert (tmp_path / "artifacts" / result.run_id / "manifest.json").exists()
    manifest = load_backtest_artifact(result.run_id, "manifest")
    config = load_backtest_artifact(result.run_id, "config")
    replay = replay_backtest_from_manifest(result.run_id)
    compare = compare_backtest_replay(result.run_id)
    assert manifest["schema_version"] == "quant_lab_artifact_v1"
    assert manifest["config_hash"]
    assert "code_version" in manifest
    assert manifest["data_snapshot"]["price_counts"]["SPY"] == 90
    assert manifest["data_snapshot"]["freshness_policy"]["policy_id"] == "daily_price_t_plus_3_market_days"
    assert config["expanded_features"]
    assert config["validation"]["lookahead_safe"] is True
    assert config["universe_policy"] == "user_supplied_static_list"
    assert "point-in-time" in config["survivorship_bias_warning"]
    assert result.trades[0]["signal_date"] < result.trades[0]["execution_date"]
    assert replay.status == "success"
    assert replay.metrics["total_return"] == result.metrics["total_return"]
    assert compare["config_hash_match"] is True
    assert compare["metric_deltas"]["total_return"] == 0
    assert compare["tolerance_passed"] is True
    assert compare["tolerance_failures"] == []
    assert compare["report_path"]
    report = load_backtest_artifact(result.run_id, "replay_report")
    assert report["schema_version"] == "quant_lab_replay_report_v1"
    assert report["tolerance_passed"] is True
    history = list_replay_reports(result.run_id)
    assert history["count"] == 1
    assert history["latest"]["tolerance_passed"] is True
    assert history["items"][0]["report_path"].endswith(".json")
    jsonl_export = export_backtest_artifacts(result.run_id, "jsonl")
    csv_export = export_backtest_artifacts(result.run_id, "csv", keep_last_exports=1)
    assert jsonl_export["format"] == "jsonl"
    assert jsonl_export["row_counts"]["trades"] >= 1
    assert jsonl_export["files"]["jsonl"].endswith("artifact_bundle.jsonl")
    assert jsonl_export["integrity"]["algorithm"] == "sha256"
    assert len(jsonl_export["integrity"]["files"]["jsonl"]["sha256"]) == 64
    assert jsonl_export["manifest"]["integrity"]["files"]["jsonl"]["size_bytes"] > 0
    assert csv_export["format"] == "csv"
    assert "metrics" in csv_export["files"]
    assert csv_export["row_counts"]["total"] >= jsonl_export["row_counts"]["trades"]
    assert csv_export["retention"]["retention_applied"] is True
    assert csv_export["retention"]["keep_last_exports"] == 1
    assert csv_export["retention"]["pruned_export_count"] >= 1
    export_dirs = [path for path in (tmp_path / "artifacts" / result.run_id / "exports").iterdir() if path.is_dir()]
    assert len(export_dirs) == 1
    parquet_export = export_backtest_artifacts(result.run_id, "parquet")
    assert parquet_export["format"] == "parquet"
    assert parquet_export["status"] in {"success", "dependency_missing"}
    if parquet_export["status"] == "success":
        assert parquet_export["export_written"] is True
        assert parquet_export["files"]["metrics"].endswith(".parquet")
    else:
        assert parquet_export["export_written"] is False
        assert parquet_export["dependency"]["available"] is False
    assert compare["replay_run_id"]


def test_list_backtest_runs_reports_current_snapshot_freshness(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=1,
        )
    )

    runs = list_backtest_runs(limit=5)
    item = next(row for row in runs["items"] if row["run_id"] == result.run_id)

    assert item["snapshot_freshness"]["status"] == "stale"
    assert set(item["snapshot_freshness"]["stale_assets"]) == {"SPY", "QQQ"}
    assert item["snapshot_freshness"]["refresh_recommended"] is True
    assert item["data_snapshot"]["snapshot_freshness"]["current_expected_latest_date"] == _current_expected_market_date().isoformat()


def test_replay_report_flags_tolerance_failures(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )
    metrics_path = tmp_path / "artifacts" / result.run_id / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["total_return"] = float(metrics["total_return"]) + 0.01
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    compare = compare_backtest_replay(result.run_id, tolerances={"total_return": 1e-6})

    assert compare["status"] == "partial"
    assert compare["tolerance_passed"] is False
    assert compare["tolerance_failures"][0]["metric"] == "total_return"
    assert compare["report_path"]


def test_compare_backtest_runs_is_read_only_and_reports_lineage(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    primary = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=1,
        )
    )
    comparison = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )
    before_dirs = sorted(path.name for path in (tmp_path / "artifacts").iterdir() if path.is_dir())

    report = compare_backtest_runs([primary.run_id, comparison.run_id])
    after_dirs = sorted(path.name for path in (tmp_path / "artifacts").iterdir() if path.is_dir())

    assert report["schema_version"] == "quant_lab_run_compare_v1"
    assert report["primary_run_id"] == primary.run_id
    assert report["comparison_run_id"] == comparison.run_id
    assert report["lineage"]["config_hash_match"] is False
    assert any(row["metric"] == "sharpe" for row in report["metrics"])
    assert any(row["field"] == "top_n" for row in report["config_differences"])
    assert report["diagnostics"]["lookahead_safe_all"] is True
    assert {run["snapshot_freshness"]["status"] for run in report["runs"]} == {"stale"}
    assert all(run["snapshot_freshness"]["refresh_recommended"] is True for run in report["runs"])
    assert all(run["data_snapshot"]["snapshot_freshness"]["current_expected_latest_date"] for run in report["runs"])
    assert before_dirs == after_dirs


def test_export_cleanup_preview_is_non_destructive_and_apply_prunes(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )
    export_backtest_artifacts(result.run_id, "jsonl")
    export_backtest_artifacts(result.run_id, "csv")
    export_backtest_artifacts(result.run_id, "jsonl")
    exports_root = tmp_path / "artifacts" / result.run_id / "exports"
    before_dirs = {path.name for path in exports_root.iterdir() if path.is_dir()}

    preview = preview_backtest_export_cleanup(result.run_id, keep_last_exports=1)

    assert preview["status"] == "success"
    assert preview["cleanup_applied"] is False
    assert preview["export_count"] == 3
    assert preview["kept_export_count"] == 1
    assert preview["prune_export_count"] == 2
    assert preview["total_bytes_to_prune"] > 0
    assert {path.name for path in exports_root.iterdir() if path.is_dir()} == before_dirs

    cleanup = cleanup_backtest_exports(result.run_id, keep_last_exports=1)

    assert cleanup["cleanup_applied"] is True
    assert cleanup["prune_export_count"] == 2
    assert cleanup["total_bytes_pruned"] == preview["total_bytes_to_prune"]
    remaining_dirs = [path for path in exports_root.iterdir() if path.is_dir()]
    assert len(remaining_dirs) == 1
    after_preview = preview_backtest_export_cleanup(result.run_id, keep_last_exports=1)
    assert after_preview["prune_export_count"] == 0


def test_export_storage_report_summarizes_runs_without_mutation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    first = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )
    second = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ"],
            benchmark="SPY",
            template="moving_average_trend",
            lookback=10,
        )
    )
    export_backtest_artifacts(first.run_id, "jsonl")
    export_backtest_artifacts(first.run_id, "csv")
    export_backtest_artifacts(second.run_id, "jsonl")
    missing_manifest_dir = tmp_path / "artifacts" / second.run_id / "exports" / "19000101T000000000000Z_csv"
    missing_manifest_dir.mkdir(parents=True)

    before_dirs = sorted(path.name for path in (tmp_path / "artifacts" / first.run_id / "exports").iterdir())
    report = export_storage_report(limit=10, stale_after_days=0)
    after_dirs = sorted(path.name for path in (tmp_path / "artifacts" / first.run_id / "exports").iterdir())

    assert report["status"] == "success"
    assert report["schema_version"] == "quant_lab_export_storage_report_v1"
    assert report["run_count"] >= 2
    assert report["runs_with_exports"] >= 2
    assert report["export_directory_count"] >= 4
    assert report["total_bytes"] > 0
    assert report["format_counts"]["jsonl"] >= 2
    assert report["manifest_status_counts"]["missing_manifest"] == 1
    assert report["top_runs"][0]["total_bytes"] >= report["top_runs"][-1]["total_bytes"]
    assert before_dirs == after_dirs


def test_cross_run_export_cleanup_requires_exact_preview_candidates(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    first = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            lookback=21,
            top_n=2,
        )
    )
    second = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            lookback=21,
            top_n=1,
        )
    )
    for run_id in [first.run_id, second.run_id]:
        export_backtest_artifacts(run_id, "jsonl")
        export_backtest_artifacts(run_id, "csv")
        export_backtest_artifacts(run_id, "jsonl")

    preview = preview_cross_run_export_cleanup(keep_last_exports=1, stale_after_days=0, limit=20)

    assert preview["status"] == "success"
    assert preview["cleanup_applied"] is False
    assert preview["schema_version"] == "quant_lab_cross_run_export_cleanup_v1"
    assert preview["candidate_count"] == 4
    assert preview["eligible_export_count"] == 4
    assert preview["total_bytes_to_prune"] > 0
    assert len(preview["candidate_ids"]) == 4
    for run_id in [first.run_id, second.run_id]:
        exports_root = tmp_path / "artifacts" / run_id / "exports"
        assert len([path for path in exports_root.iterdir() if path.is_dir()]) == 3

    try:
        cleanup_cross_run_exports(
            preview_id="wrong-preview",
            candidate_ids=preview["candidate_ids"],
            keep_last_exports=1,
            stale_after_days=0,
            limit=20,
        )
        raise AssertionError("cross-run cleanup accepted a stale preview id")
    except ValueError as exc:
        assert "preview_id" in str(exc)

    try:
        cleanup_cross_run_exports(
            preview_id=preview["preview_id"],
            candidate_ids=preview["candidate_ids"][:-1],
            keep_last_exports=1,
            stale_after_days=0,
            limit=20,
        )
        raise AssertionError("cross-run cleanup accepted an incomplete candidate list")
    except ValueError as exc:
        assert "candidate_ids" in str(exc)

    cleanup = cleanup_cross_run_exports(
        preview_id=preview["preview_id"],
        candidate_ids=preview["candidate_ids"],
        keep_last_exports=1,
        stale_after_days=0,
        limit=20,
    )

    assert cleanup["cleanup_applied"] is True
    assert cleanup["pruned_export_count"] == 4
    assert cleanup["total_bytes_pruned"] == preview["total_bytes_to_prune"]
    for run_id in [first.run_id, second.run_id]:
        exports_root = tmp_path / "artifacts" / run_id / "exports"
        assert len([path for path in exports_root.iterdir() if path.is_dir()]) == 1


def test_export_package_manifest_verifies_after_copy_and_detects_tamper(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
        )
    )
    export = export_backtest_artifacts(result.run_id, "jsonl")
    export_root = Path(export["export_root"])
    package_manifest = export_root / "package_manifest.json"

    assert package_manifest.exists()
    assert export["manifest"]["package_manifest"]["schema_version"] == "quant_lab_export_package_v1"
    assert export["files"]["package_manifest"].endswith("package_manifest.json")

    original_report = verify_export_package(export_root)
    assert original_report["status"] == "success"
    assert original_report["manifest_kind"] == "package_manifest"
    assert original_report["files_failed"] == 0
    assert "export_manifest" in original_report["files"]

    copied_root = tmp_path / "copied_export"
    shutil.copytree(export_root, copied_root)
    copied_report = verify_export_package(copied_root)
    assert copied_report["status"] == "success"
    assert copied_report["files_failed"] == 0

    cli_report = subprocess.run(
        [sys.executable, "scripts/verify_quant_export.py", "--json", str(copied_root)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(cli_report.stdout)["status"] == "success"

    (copied_root / "artifact_bundle.jsonl").write_text("tampered\n", encoding="utf-8")
    tampered_report = verify_export_package(copied_root)
    assert tampered_report["status"] == "partial"
    assert tampered_report["files_failed"] == 1
    assert tampered_report["failures"][0]["file"] == "jsonl"

    cli_tampered = subprocess.run(
        [sys.executable, "scripts/verify_quant_export.py", "--json", str(copied_root)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert cli_tampered.returncode == 1
    assert json.loads(cli_tampered.stdout)["status"] == "partial"


def test_replay_preserves_resolved_freshness_profile_policy(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="momentum_ranking",
            lookback=21,
            top_n=2,
            freshness_profile="historical_lab",
        )
    )
    config = load_backtest_artifact(result.run_id, "config")
    compare = compare_backtest_replay(result.run_id)

    assert config["freshness_profile"] == "historical_lab"
    assert config["max_market_calendar_lag_days"] == 30
    assert compare["status"] == "success"
    assert compare["config_hash_match"] is True


def test_quant_backtest_maps_moving_average_template_to_existing_engine(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ"],
            benchmark="SPY",
            template="moving_average_trend",
            lookback=10,
        )
    )

    assert result.status == "success"
    assert result.template == "moving_average_trend"
    assert result.diagnostics.lookahead_safe is True


def test_quant_backtest_supports_risk_adjusted_momentum_template(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    _seed_prices(db_path)
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    monkeypatch.setattr(quant_lab_pipeline, "ARTIFACT_ROOT", tmp_path / "artifacts")

    signal = signal_preview(
        QuantSignalGenerateRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="risk_adjusted_momentum",
            lookback=21,
        )
    )
    result = run_quant_backtest(
        QuantBacktestRequest(
            tickers=["SPY", "QQQ", "TLT"],
            benchmark="SPY",
            template="risk_adjusted_momentum",
            lookback=21,
            top_n=2,
        )
    )

    assert signal.status == "success"
    assert signal.rows[0].factor_values["risk_adjusted_momentum_63d"] is not None
    assert result.status == "success"
    assert result.template == "risk_adjusted_momentum"
    assert result.diagnostics.lookahead_safe is True
    assert result.trades[0]["signal_date"] < result.trades[0]["execution_date"]


def test_signal_preview_reports_research_score_provenance(tmp_path, monkeypatch) -> None:
    base_response = {
        "sentiment": "bullish",
        "confidence": 0.8,
        "bull_evidence_ids": [["doc-spy-1"]],
        "bear_evidence_ids": [],
    }
    signals = _signal_preview_for_research_response(
        tmp_path / "annotated",
        monkeypatch,
        {
            **base_response,
            "execution_meta": {
                "extras": {
                    "fingpt_annotations": {
                        "annotations": [
                            {
                                "task": "sentiment",
                                "label": "positive",
                                "confidence": 0.9,
                                "article_id": "doc-spy-1",
                            },
                            {
                                "task": "headline",
                                "label": "price_up",
                                "confidence": 0.7,
                                "article_id": "doc-spy-2",
                            },
                        ]
                    }
                }
            },
        },
    )
    baseline = _signal_preview_for_research_response(tmp_path / "baseline", monkeypatch, base_response)

    assert signals.diagnostics.research_score_status in {"fresh", "sparse_evidence"}
    assert signals.diagnostics.research_score_provenance["SPY"]["run_id"] == "abc123"
    assert signals.diagnostics.fingpt_forecaster_signals["SPY"]["direction"] == "up"
    assert signals.diagnostics.fingpt_forecaster_signals["SPY"]["evidence_doc_ids"] == ["doc-spy-1", "doc-spy-2"]
    assert signals.rows[0].research_score == 0.8
    assert signals.rows[0].research_score == baseline.rows[0].research_score
    assert signals.rows[0].final_score == baseline.rows[0].final_score
    assert signals.rows[0].signal == baseline.rows[0].signal
    assert signals.rows[0].diagnostics == baseline.rows[0].diagnostics
    assert all("fingpt_forecaster_signal" not in item for item in signals.rows[0].diagnostics)


def test_signal_preview_ignores_malformed_forecaster_annotations(tmp_path, monkeypatch) -> None:
    signals = _signal_preview_for_research_response(
        tmp_path,
        monkeypatch,
        {
            "sentiment": "bullish",
            "confidence": 0.8,
            "bull_evidence_ids": [["doc-spy-1"]],
            "bear_evidence_ids": [],
            "execution_meta": {
                "extras": {
                    "fingpt_annotations": {
                        "annotations": 123,
                    }
                }
            },
        },
    )

    assert signals.rows[0].research_score == 0.8
    assert signals.diagnostics.fingpt_forecaster_signals == {}
