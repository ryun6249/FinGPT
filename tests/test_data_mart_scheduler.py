from __future__ import annotations

import asyncio
from types import SimpleNamespace

from pipelines.data_mart import scheduler as scheduler_mod


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        data_mart_auto_refresh_enabled=True,
        data_mart_auto_refresh_prices_enabled=True,
        data_mart_auto_refresh_sec_enabled=True,
        data_mart_auto_refresh_macro_enabled=True,
        data_mart_auto_refresh_quality_checks_enabled=True,
        data_mart_auto_refresh_interval_hours=24.0,
        data_mart_auto_refresh_initial_delay_s=120.0,
        data_mart_auto_refresh_universe_id="all_supported",
        data_mart_auto_refresh_max_assets=250,
        data_mart_auto_refresh_price_markets="us,kr",
        data_mart_auto_refresh_sec_lookback_days=365,
        data_mart_auto_refresh_macro_lookback_days=730,
    )


def test_data_mart_scheduler_status_exposes_all_auto_refresh_jobs(monkeypatch) -> None:
    monkeypatch.setenv("DATA_MART_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setattr(scheduler_mod, "load_settings", _settings)

    scheduler = scheduler_mod.DataMartRefreshScheduler()
    status = scheduler.status()

    assert status["enabled"] is True
    assert status["jobs"] == {
        "price_history": True,
        "sec_company_data": True,
        "macro_platform_data": True,
        "data_quality_checks": True,
    }
    assert status["price_markets"] == ["us", "kr"]


def test_data_mart_scheduler_run_once_refreshes_all_data_domains(monkeypatch) -> None:
    monkeypatch.setenv("DATA_MART_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setattr(scheduler_mod, "load_settings", _settings)
    monkeypatch.setattr(scheduler_mod, "_watchlist_tickers", lambda market: ["SPY"] if market == "us" else ["005930.KS"])

    from pipelines.ai_portfolio import service as ai_service
    from pipelines.data_mart.jobs import quality_checks as quality_mod
    from pipelines.data_mart.jobs import update_macro_daily as macro_mod
    from pipelines.data_mart.jobs import update_prices_daily as prices_mod
    from pipelines.macro import macro_service

    price_calls: list[tuple[tuple[str, ...], str]] = []

    def fake_update_prices_daily(tickers, *, market: str, **kwargs):
        price_calls.append((tuple(tickers), market))
        return SimpleNamespace(
            run_id=f"price-{market}",
            status="success",
            rows_inserted=10,
            rows_updated=2,
            error_message=None,
        )

    def fake_sec_refresh(request):
        return {
            "operation_id": "sec-1",
            "status": "success",
            "created_at": "2026-05-22T00:00:00Z",
            "ticker_count": request.max_assets,
            "sec_result": {"status": "success"},
        }

    def fake_macro_refresh(*, lookback_days: int):
        return SimpleNamespace(
            run_id="macro-1",
            status="success",
            rows_inserted=20,
            rows_updated=3,
            providers=[],
        )

    monkeypatch.setattr(prices_mod, "update_prices_daily", fake_update_prices_daily)
    monkeypatch.setattr(ai_service, "run_sec_data_refresh", fake_sec_refresh)
    monkeypatch.setattr(macro_mod, "update_macro_platform_data", fake_macro_refresh)
    monkeypatch.setattr(quality_mod, "run_data_quality_checks", lambda: [{"status": "pass"}])
    monkeypatch.setattr(macro_service, "clear_macro_caches", lambda: None)

    scheduler = scheduler_mod.DataMartRefreshScheduler()
    result = asyncio.run(scheduler.run_once())

    assert result["status"] == "success"
    assert price_calls == [(("SPY",), "us"), (("005930.KS",), "kr")]
    assert result["jobs"]["price_history"]["status"] == "success"
    assert result["jobs"]["sec_company_data"]["status"] == "success"
    assert result["jobs"]["macro_platform_data"]["status"] == "success"
    assert result["jobs"]["data_quality_checks"]["status"] == "success"


def test_data_mart_scheduler_continues_after_one_job_failure(monkeypatch) -> None:
    monkeypatch.setenv("DATA_MART_AUTO_REFRESH_ENABLED", "true")
    monkeypatch.setattr(scheduler_mod, "load_settings", _settings)
    monkeypatch.setattr(scheduler_mod, "_watchlist_tickers", lambda market: ["SPY"])

    from pipelines.ai_portfolio import service as ai_service
    from pipelines.data_mart.jobs import quality_checks as quality_mod
    from pipelines.data_mart.jobs import update_macro_daily as macro_mod
    from pipelines.data_mart.jobs import update_prices_daily as prices_mod
    from pipelines.macro import macro_service

    def fake_update_prices_daily(tickers, *, market: str, **kwargs):
        if market == "kr":
            raise RuntimeError("provider timeout")
        return SimpleNamespace(
            run_id="price-us",
            status="success",
            rows_inserted=5,
            rows_updated=1,
            error_message=None,
        )

    monkeypatch.setattr(prices_mod, "update_prices_daily", fake_update_prices_daily)
    monkeypatch.setattr(ai_service, "run_sec_data_refresh", lambda request: {"status": "success"})
    monkeypatch.setattr(
        macro_mod,
        "update_macro_platform_data",
        lambda *, lookback_days: SimpleNamespace(
            run_id="macro-1",
            status="success",
            rows_inserted=1,
            rows_updated=0,
            providers=[],
        ),
    )
    monkeypatch.setattr(quality_mod, "run_data_quality_checks", lambda: [{"status": "pass"}])
    monkeypatch.setattr(macro_service, "clear_macro_caches", lambda: None)

    scheduler = scheduler_mod.DataMartRefreshScheduler()
    result = asyncio.run(scheduler.run_once())

    assert result["status"] == "failed"
    assert result["jobs"]["price_history"]["status"] == "failed"
    assert result["jobs"]["macro_platform_data"]["status"] == "success"
    assert result["jobs"]["data_quality_checks"]["status"] == "success"
