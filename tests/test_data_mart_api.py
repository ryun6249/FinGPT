from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.api.routers import data as data_router
from app.api.server import app
from pipelines.backtest.validation import _current_expected_market_date
from pipelines.data_mart.models import Filing, PriceBar, UpdateRunResult
from pipelines.data_mart.storage import repository
from pipelines.data_mart.storage.db import init_db


def test_data_health_and_prices_endpoint_use_structured_store(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.ensure_assets(["SPY"], market="us", db_path=db_path)
    repository.upsert_prices(
        [
            PriceBar(ticker="SPY", date="2026-01-02", close=100, adjusted_close=100, source="test"),
            PriceBar(ticker="SPY", date="2026-01-03", close=101, adjusted_close=101, source="test"),
        ],
        db_path=db_path,
    )
    run_id = repository.start_update_run(market="us", provider="test", db_path=db_path)
    repository.finish_update_run(run_id, status="success", rows_inserted=2, db_path=db_path)

    client = TestClient(app)
    health = client.get("/api/v1/data/health")
    prices = client.get("/api/v1/data/prices/SPY?limit=10")

    assert health.status_code == 200
    assert health.json()["table_counts"]["prices_daily"] == 2
    assert health.json()["summary"]["decision_status"] == "ok"
    assert prices.status_code == 200
    assert prices.json()["status"] == "ok"
    assert prices.json()["latest"]["date"] == "2026-01-03"


def test_data_prices_refreshes_before_returning_rows(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.ensure_assets(["SPY"], market="us", db_path=db_path)
    repository.upsert_prices(
        [
            PriceBar(ticker="SPY", date="2026-05-07", close=731.58, adjusted_close=731.58, source="test"),
        ],
        db_path=db_path,
    )

    def fake_update_prices_daily(tickers, **kwargs):
        assert tickers == ["SPY"]
        assert kwargs["market"] == "mixed"
        assert kwargs["start_date"] == "2025-05-09"
        assert kwargs["end_date"] is None
        repository.upsert_prices(
            [
                PriceBar(ticker="SPY", date="2026-05-08", close=737.62, adjusted_close=737.62, source="test"),
            ],
            db_path=db_path,
        )
        return UpdateRunResult(
            run_id="refresh-test",
            status="success",
            market="mixed",
            provider="test",
            rows_inserted=1,
            rows_updated=0,
        )

    monkeypatch.setattr(data_router, "update_prices_daily", fake_update_prices_daily)
    client = TestClient(app)

    response = client.get("/api/v1/data/prices/SPY?limit=10&refresh=true&start_date=2025-05-09")

    assert response.status_code == 200
    body = response.json()
    assert body["latest"]["date"] == "2026-05-08"
    assert body["refresh"]["attempted"] is True
    assert body["refresh"]["status"] == "success"
    assert body["refresh"]["rows_inserted"] == 1


def test_data_prices_returns_quant_freshness_audit(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.upsert_prices(
        [
            PriceBar(ticker="SPY", date="2026-01-02", close=100, adjusted_close=100, source="test"),
            PriceBar(ticker="SPY", date="2026-01-03", close=101, adjusted_close=101, source="test"),
        ],
        db_path=db_path,
    )

    client = TestClient(app)
    response = client.get("/api/v1/data/prices/SPY?limit=10&freshness_profile=decision_review")

    assert response.status_code == 200
    body = response.json()
    assert body["freshness_policy"]["profile"] == "decision_review"
    assert body["freshness_policy"]["require_fresh_prices"] is True
    assert body["asset_freshness"]["freshness_status"] == "stale"
    assert body["strict_freshness_violation"] is True


def test_data_health_marks_optional_empty_provider_rows_as_covered(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    run_id = repository.start_update_run(market="us", provider="sec_filings", db_path=db_path)
    repository.record_provider_status(
        run_id,
        provider="sec_filings",
        status="empty",
        market="us",
        ticker="SPY",
        db_path=db_path,
    )
    repository.record_provider_status(
        run_id,
        provider="sec_filings",
        status="ok",
        market="us",
        ticker="MSFT",
        rows_inserted=1,
        db_path=db_path,
    )
    repository.finish_update_run(run_id, status="success", rows_inserted=1, db_path=db_path)

    client = TestClient(app)
    health = client.get("/api/v1/data/health")

    assert health.status_code == 200
    body = health.json()
    spy_row = next(row for row in body["recent_provider_status"] if row["ticker"] == "SPY")
    assert spy_row["status"] == "ok"
    assert spy_row["raw_status"] == "empty"
    assert spy_row["coverage_status"] == "covered_empty"
    assert body["summary"]["covered_empty_provider_rows"] == 1
    assert body["summary"]["decision_status"] == "ok"


def test_data_sec_endpoint_returns_local_filings_and_facts(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.upsert_filings(
        [
            Filing(
                ticker="MSFT",
                cik="0000789019",
                accession_number="0000789019-26-000001",
                form_type="10-Q",
                filed_at="2026-04-25",
                url="https://sec.example/msft-10q",
                filing_id="MSFT:0000789019-26-000001",
            )
        ],
        db_path=db_path,
    )
    repository.upsert_sec_financial_facts(
        [
            {
                "ticker": "MSFT",
                "cik": "0000789019",
                "taxonomy": "us-gaap",
                "concept": "Assets",
                "unit": "USD",
                "form_type": "10-Q",
                "fiscal_year": 2026,
                "fiscal_period": "Q3",
                "end_date": "2026-03-31",
                "filed_at": "2026-04-25",
                "accession_number": "0000789019-26-000001",
                "value": 1000,
            }
        ],
        db_path=db_path,
    )

    client = TestClient(app)
    response = client.get("/api/v1/data/sec/MSFT")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["filing_count"] == 1
    assert body["fact_count"] == 1
    assert body["filings"][0]["form_type"] == "10-Q"
    assert body["facts"][0]["concept"] == "Assets"


def test_backtest_endpoint_accepts_request_price_rows() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/backtest/run",
        json={
            "ticker": "SPY",
            "strategy": "buy_and_hold",
            "transaction_cost_bps": 0,
            "slippage_bps": 0,
            "price_rows": [
                {"date": "2026-01-02", "adjusted_close": 100},
                {"date": "2026-01-03", "adjusted_close": 110},
                {"date": "2026-01-04", "adjusted_close": 121},
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data_status"] == "request_rows"
    assert body["equity_curve"][-1]["equity"] == 1.21


def test_backtest_endpoint_serializes_single_ticker_data_mart_result(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.upsert_prices(
        [
            PriceBar(ticker="SPY", date="2026-01-02", close=100, adjusted_close=100, source="test"),
            PriceBar(ticker="SPY", date="2026-01-03", close=110, adjusted_close=110, source="test"),
            PriceBar(ticker="SPY", date="2026-01-04", close=121, adjusted_close=121, source="test"),
        ],
        db_path=db_path,
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/backtest/run",
        json={
            "ticker": "SPY",
            "strategy": "buy_and_hold",
            "start_date": "2026-01-02",
            "end_date": "2026-01-04",
            "transaction_cost_bps": 0,
            "slippage_bps": 0,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data_status"] == "data_mart"
    assert body["asset_results"]["SPY"]["status"] == "success"
    assert body["equity_curve"][-1]["equity"] == 1.21


def test_backtest_endpoint_accepts_multiple_tickers_with_request_range(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    repository.upsert_prices(
        [
            PriceBar(ticker="SPY", date="2026-01-02", close=100, adjusted_close=100, source="test"),
            PriceBar(ticker="SPY", date="2026-01-03", close=110, adjusted_close=110, source="test"),
            PriceBar(ticker="TLT", date="2026-01-02", close=50, adjusted_close=50, source="test"),
            PriceBar(ticker="TLT", date="2026-01-03", close=49, adjusted_close=49, source="test"),
        ],
        db_path=db_path,
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/backtest/run",
        json={
            "tickers": ["SPY", "TLT"],
            "strategy": "buy_and_hold",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "transaction_cost_bps": 0,
            "slippage_bps": 0,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert set(body["asset_results"]) == {"SPY", "TLT"}
    assert body["summary_policy"] == "reported metrics come from one aligned multi-asset portfolio equity curve"
    assert body["equity_curve"]
    assert body["requested_range"]["start"] == "2026-01-02"
    assert body["price_counts"] == {"SPY": 2, "TLT": 2}


def test_portfolio_optimize_endpoint_accepts_request_returns() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/portfolio/optimize",
        json={
            "method": "inverse_volatility",
            "returns_by_asset": {
                "LOW": [0.001, 0.002, 0.001, 0.002],
                "HIGH": [0.05, -0.04, 0.03, -0.02],
            },
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data_status"] == "request_returns"
    assert body["weights"]["LOW"] > body["weights"]["HIGH"]


def test_portfolio_optimize_endpoint_supports_advanced_methods() -> None:
    client = TestClient(app)
    resp = client.post(
        "/api/v1/portfolio/optimize",
        json={
            "method": "momentum_tilt",
            "max_weight": 0.8,
            "returns_by_asset": {
                "UP": [0.01, 0.02, 0.01],
                "FLAT": [0.0, 0.0, 0.0],
            },
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["weights"]["UP"] > body["weights"]["FLAT"]


def test_portfolio_optimize_endpoint_fails_closed_on_strict_stale_prices(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))
    init_db(db_path)
    rows = []
    for idx in range(5):
        day = (date(2026, 1, 2) + timedelta(days=idx)).isoformat()
        rows.extend(
            [
                PriceBar(ticker="SPY", date=day, close=100 + idx, adjusted_close=100 + idx, source="test"),
                PriceBar(ticker="TLT", date=day, close=90 + idx, adjusted_close=90 + idx, source="test"),
            ]
        )
    repository.upsert_prices(rows, db_path=db_path)

    client = TestClient(app)
    response = client.post(
        "/api/v1/portfolio/optimize",
        json={
            "tickers": ["SPY", "TLT"],
            "benchmark": "SPY",
            "lookback_days": 5,
            "freshness_profile": "decision_review",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["data_status"] == "freshness_failed"
    assert body["strict_freshness_violation"] is True
    assert set(body["stale_assets"]) == {"SPY", "TLT"}
    assert body["freshness_policy"]["expected_latest_date"] == _current_expected_market_date().isoformat()
