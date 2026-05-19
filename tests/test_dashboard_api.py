from __future__ import annotations

import asyncio
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi.testclient import TestClient

from app.api import server as api_server
from app.api.routers import dashboard as dashboard_router
from pipelines.dashboard.market_service import (
    MARKET_SNAPSHOT_CACHE_KEY,
    MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
    clear_market_snapshot_cache,
    get_market_snapshot,
)
from pipelines.data_mart.storage.repository import (
    acquire_dashboard_refresh_lock,
    clear_dashboard_refresh_locks,
    clear_dashboard_snapshot,
    release_dashboard_refresh_lock,
    upsert_dashboard_snapshot,
)


class _FakeTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period: str, interval: str, auto_adjust: bool = False, **kwargs):
        if interval in {"5m", "15m", "60m"}:
            ny_tz = ZoneInfo("America/New_York")
            now_ny = datetime.now(ny_tz)
            latest = now_ny.replace(second=0, microsecond=0)
            previous_day = latest - timedelta(days=1)
            idx = pd.DatetimeIndex([
                previous_day.replace(hour=15, minute=55),
                latest - timedelta(minutes=5),
                latest,
            ])
            base = 100 + (sum(ord(ch) for ch in self.symbol) % 17)
            closes = [base, base + 0.25, base + 0.5]
            return pd.DataFrame(
                {
                    "Open": [close - 0.1 for close in closes],
                    "High": [close + 0.2 for close in closes],
                    "Low": [close - 0.3 for close in closes],
                    "Close": closes,
                    "Volume": [1000, 1500, 2000],
                },
                index=idx,
            )
        idx = pd.date_range("2026-01-01", periods=90, freq="B")
        base = 100 + (sum(ord(ch) for ch in self.symbol) % 17)
        closes = [base + i * 0.25 for i in range(len(idx))]
        return pd.DataFrame({"Close": closes}, index=idx)


def _fake_intraday_download(tickers, *args, **kwargs):
    symbols = list(tickers)
    ny_tz = ZoneInfo("America/New_York")
    now_ny = datetime.now(ny_tz).replace(second=0, microsecond=0)
    previous_day = now_ny - timedelta(days=1)
    idx = pd.DatetimeIndex([
        previous_day.replace(hour=15, minute=55),
        now_ny - timedelta(minutes=5),
        now_ny,
    ])
    data = {}
    for pos, symbol in enumerate(symbols):
        base = 100 + pos
        data[(symbol, "Close")] = [base, base + 1, base + 2]
        data[(symbol, "Volume")] = [1000, 1500, 2000]
    return pd.DataFrame(data, index=idx)


def _fake_stale_intraday_download(tickers, *args, **kwargs):
    symbols = list(tickers)
    idx = pd.to_datetime([
        "2026-01-05 15:50:00-05:00",
        "2026-01-06 15:55:00-05:00",
    ])
    data = {}
    for pos, symbol in enumerate(symbols):
        base = 100 + pos
        data[(symbol, "Close")] = [base, base + 1]
        data[(symbol, "Volume")] = [1000, 2000]
    return pd.DataFrame(data, index=idx)


class DashboardApiTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_market_snapshot_cache()
        clear_dashboard_snapshot(MARKET_SNAPSHOT_CACHE_KEY)
        clear_dashboard_refresh_locks(MARKET_SNAPSHOT_REFRESH_LOCK_KEY)

    def tearDown(self) -> None:
        clear_market_snapshot_cache()
        clear_dashboard_snapshot(MARKET_SNAPSHOT_CACHE_KEY)
        clear_dashboard_refresh_locks(MARKET_SNAPSHOT_REFRESH_LOCK_KEY)

    def test_dashboard_news_includes_category(self):
        docs = [
            {
                "title": "Rates and credit risk update",
                "source": "Example",
                "url": "https://example.com/rates",
                "published_at": "2026-04-24T00:00:00+00:00",
                "text": "summary",
            }
        ]
        client = TestClient(api_server.app)

        def fake_collect(symbol: str, *args, **kwargs):
            return symbol, docs if symbol == "TLT" else []

        with patch.object(dashboard_router, "collect_news_from_google_rss", side_effect=fake_collect):
            resp = client.get("/api/v1/dashboard/news?limit=3")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["items"][0]["category"], "rates_credit")
        self.assertEqual(body["items"][0]["symbol"], "TLT")

    def test_dashboard_news_supports_company_and_topic_query(self):
        client = TestClient(api_server.app)

        def fake_collect(symbol: str, *args, **kwargs):
            if symbol == "NVDA":
                return symbol, [{
                    "title": "Nvidia earnings guidance update",
                    "source": "Example",
                    "url": "https://example.com/nvda",
                    "published_at": "2026-04-24T00:00:00+00:00",
                    "text": "company summary",
                }]
            if symbol == "TOPIC":
                return symbol, [{
                    "title": "AI chip export controls move semiconductor shares",
                    "source": "Example",
                    "url": "https://example.com/topic",
                    "published_at": "2026-04-24T00:00:00+00:00",
                    "text": "topic summary",
                }]
            return symbol, []

        with patch.object(dashboard_router, "collect_news_from_google_rss", side_effect=fake_collect):
            resp = client.get("/api/v1/dashboard/news?limit=6&ticker=NVDA&topic=AI%20chips")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["selection_policy"], "focused_query_plus_market_coverage")
        categories = {item["category"] for item in body["items"]}
        self.assertIn("company_news", categories)
        self.assertIn("topic_news", categories)
        self.assertEqual(body["ticker"], "NVDA")
        self.assertEqual(body["topic"], "AI chips")

    def test_dashboard_cross_asset_analyze_returns_user_controlled_summary(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/cross-asset/analyze?symbols=SPY,TLT,HYG&horizon=1m&topic=rates")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["provider"], "yfinance")
        self.assertEqual(body["analysis_engine"], "deterministic_cross_asset_v1")
        self.assertTrue(body["advisory_only"])
        self.assertEqual(body["horizon"], "1m")
        self.assertEqual(body["topic"], "rates")
        self.assertEqual(len(body["items"]), 3)
        self.assertGreaterEqual(body["decision_usable_count"], 3)
        self.assertIn(body["summary"]["state"], {"risk_on", "risk_off", "mixed"})
        self.assertIn("current_state", body["summary"])
        self.assertIn("forward_bias", body["summary"])

    def test_dashboard_market_returns_as_of_quant_snapshot(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/market?force=true")
            cached_resp = client.get("/api/v1/dashboard/market")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["cache_hit"])
        self.assertTrue(cached_resp.json()["cache_hit"])
        self.assertEqual(body["provider"], "yfinance")
        self.assertGreaterEqual(body["ok_count"], 6)
        self.assertGreaterEqual(body["decision_usable_count"], 6)
        first = body["items"][0]
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["is_decision_usable"])
        self.assertEqual(first["source"], "yfinance_intraday_5m")
        self.assertIn("T", first["as_of"])
        self.assertIn(first["freshness_status"], {"fresh", "delayed", "closed"})
        self.assertIn("1d", first["returns"])
        self.assertIsInstance(first["returns"]["1d"], float)

    def test_dashboard_market_intraday_returns_ohlc_rows(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/market/intraday/SPY?interval=15m&limit=2&force=true")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["ticker"], "SPY")
        self.assertEqual(body["interval"], "15m")
        self.assertEqual(body["period"], "30d")
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["provider"], "yfinance")
        self.assertEqual(body["source"], "yfinance_intraday_15m")
        self.assertEqual(body["cache_layer"], "provider")
        self.assertFalse(body["cache_hit"])
        self.assertEqual(len(body["items"]), 2)
        first = body["items"][0]
        for key in ["date", "open", "high", "low", "close", "adjusted_close", "volume", "source"]:
            self.assertIn(key, first)
        self.assertGreaterEqual(first["high"], first["close"])
        self.assertLessEqual(first["low"], first["close"])

    def test_dashboard_market_intraday_reuses_persisted_snapshot(self):
        stored: dict[str, dict] = {}

        def fake_get(snapshot_key: str, *args, **kwargs):
            payload = stored.get(snapshot_key)
            if not payload:
                return None
            return {
                "payload": payload,
                "updated_at": "2026-05-12T00:00:00Z",
                "expires_at": "2026-05-12T00:01:30Z",
                "is_expired": bool(kwargs.get("include_expired")),
            }

        def fake_upsert(snapshot_key: str, payload: dict, **kwargs):
            stored[snapshot_key] = payload
            return {"snapshot_key": snapshot_key}

        client = TestClient(api_server.app)
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))

        with patch.dict(sys.modules, {"yfinance": fake_yf}), patch.object(dashboard_router, "get_dashboard_snapshot", side_effect=fake_get), patch.object(dashboard_router, "upsert_dashboard_snapshot", side_effect=fake_upsert):
            first = client.get("/api/v1/dashboard/market/intraday/SPY?interval=5m&limit=2&force=true")
            second = client.get("/api/v1/dashboard/market/intraday/SPY?interval=5m&limit=2")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["cache_layer"], "provider")
        body = second.json()
        self.assertEqual(body["cache_layer"], "persisted")
        self.assertTrue(body["cache_hit"])
        self.assertEqual(body["count"], 2)

    def test_dashboard_market_intraday_rejects_unknown_interval(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/market/intraday/SPY?interval=2m")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["ticker"], "SPY")
        self.assertEqual(body["count"], 0)
        self.assertIn("interval must be one of", body["message"])

    def test_dashboard_market_overview_returns_tape_signals_and_heatmap_summary(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))
        client = TestClient(api_server.app)
        old_cache = dict(dashboard_router._dashboard_equity_heatmap_cache)
        dashboard_router._dashboard_equity_heatmap_cache["payload"] = {
            "provider": "yfinance",
            "interval": "5m",
            "universe_version": "test_universe",
            "universe_size": 237,
            "decision_usable_count": 236,
            "stale_or_unavailable_count": 1,
            "latest_as_of": "2026-05-08T19:55:00+00:00",
            "warning": "1 symbols excluded",
        }

        try:
            with patch.dict(sys.modules, {"yfinance": fake_yf}):
                resp = client.get("/api/v1/dashboard/market/overview?force=true")
        finally:
            dashboard_router._dashboard_equity_heatmap_cache.clear()
            dashboard_router._dashboard_equity_heatmap_cache.update(old_cache)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["advisory_only"])
        self.assertEqual(body["freshness_summary"]["status"], "ok")
        self.assertEqual(body["heatmap_summary"]["status"], "partial")
        self.assertEqual(body["heatmap_summary"]["universe_version"], "test_universe")
        symbols = {item["symbol"] for item in body["market_tape"]}
        self.assertIn("SPY", symbols)
        signal_ids = {item["signal_id"] for item in body["signals"]}
        self.assertIn("equity_momentum", signal_ids)
        self.assertIn("rates_pressure", signal_ids)
        self.assertIn("credit_tone", signal_ids)
        self.assertIn("cross_asset_confirmation", signal_ids)

    def test_dashboard_decision_cards_returns_common_contract(self):
        client = TestClient(api_server.app)

        resp = client.get("/api/v1/dashboard/decision-cards")
        forecast_resp = client.get("/api/v1/dashboard/decision-cards?tab=forecast")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["contract_version"], "dashboard_decision_cards_v1")
        self.assertIn("no synthetic scores", body["scope"])
        items = body["items"]
        tabs = {item["tab"] for item in items}
        self.assertEqual(tabs, {"market", "macro", "quant", "quantamental", "forecast", "ai-portfolio"})
        for item in items:
            self.assertIn("decision_question", item)
            self.assertIn("primary_output", item)
            self.assertIn("next_action", item)
            self.assertGreaterEqual(len(item.get("chips") or []), 4)
            self.assertTrue(item.get("source_endpoints"))
            self.assertTrue(item.get("guardrails"))
        market = next(item for item in items if item["tab"] == "market")
        self.assertIn("evidence", market)
        self.assertIn("snapshot_status", market["evidence"])
        self.assertEqual(forecast_resp.status_code, 200)
        forecast_items = forecast_resp.json()["items"]
        self.assertEqual(len(forecast_items), 1)
        self.assertEqual(forecast_items[0]["tab"], "forecast")

    def test_dashboard_market_reuses_persisted_snapshot_after_memory_clear(self):
        fake_yf = types.SimpleNamespace(Ticker=lambda symbol: _FakeTicker(symbol))

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "research_mart.db"
            with patch.dict(sys.modules, {"yfinance": fake_yf}):
                first = asyncio.run(get_market_snapshot(force=True, db_path=db_path))

            clear_market_snapshot_cache()

            def fail_ticker(symbol: str):
                raise AssertionError(f"provider should not be called for {symbol}")

            with patch.dict(sys.modules, {"yfinance": types.SimpleNamespace(Ticker=fail_ticker)}):
                cached = asyncio.run(get_market_snapshot(db_path=db_path))

        self.assertFalse(first["cache_hit"])
        self.assertEqual(first["cache_layer"], "provider")
        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["cache_layer"], "persisted")
        self.assertEqual(cached["provider"], "yfinance")
        self.assertGreaterEqual(len(cached["items"]), 6)

    def test_dashboard_market_waits_for_refresh_lock_owner_snapshot(self):
        payload = {
            "items": [
                {
                    "symbol": "SPY",
                    "label": "S&P 500",
                    "asset_class": "equity_index",
                    "price": 101.5,
                    "as_of": "2026-05-11T13:35:00+00:00",
                    "source": "test",
                    "status": "ok",
                    "is_decision_usable": True,
                    "freshness_status": "fresh",
                    "returns": {"1d": 1.0, "5d": 2.0, "1m": 3.0, "3m": 4.0},
                }
            ],
            "generated_at": "2026-05-11T13:35:00Z",
            "provider": "test-provider",
            "ok_count": 1,
            "decision_usable_count": 1,
            "freshness_counts": {"fresh": 1},
            "freshness_policy": "test",
            "warning": "",
        }

        async def write_snapshot_after_delay(db_path: Path) -> None:
            await asyncio.sleep(0.5)
            upsert_dashboard_snapshot(
                MARKET_SNAPSHOT_CACHE_KEY,
                payload,
                source="dashboard_market",
                ttl_seconds=45,
                db_path=db_path,
            )

        async def run_waiter(db_path: Path) -> dict:
            writer = asyncio.create_task(write_snapshot_after_delay(db_path))
            try:
                return await get_market_snapshot(db_path=db_path)
            finally:
                await writer

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "research_mart.db"
            lock = acquire_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                owner_token="other-worker",
                ttl_seconds=5,
                db_path=db_path,
            )
            self.assertTrue(lock["acquired"])

            def fail_ticker(symbol: str):
                raise AssertionError(f"provider should not be called for {symbol}")

            try:
                with patch.dict(sys.modules, {"yfinance": types.SimpleNamespace(Ticker=fail_ticker)}):
                    cached = asyncio.run(run_waiter(db_path))
            finally:
                release_dashboard_refresh_lock(MARKET_SNAPSHOT_REFRESH_LOCK_KEY, "other-worker", db_path=db_path)

        self.assertTrue(cached["cache_hit"])
        self.assertEqual(cached["cache_layer"], "persisted")
        self.assertEqual(cached["refresh_lock"], "waited")
        self.assertEqual(cached["provider"], "test-provider")
        self.assertEqual(cached["items"][0]["symbol"], "SPY")

    def test_dashboard_refresh_lock_is_exclusive_and_releasable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "research_mart.db"
            first = acquire_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                owner_token="worker-a",
                ttl_seconds=30,
                db_path=db_path,
            )
            second = acquire_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                owner_token="worker-b",
                ttl_seconds=30,
                db_path=db_path,
            )
            wrong_release = release_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                "worker-b",
                db_path=db_path,
            )
            right_release = release_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                "worker-a",
                db_path=db_path,
            )
            third = acquire_dashboard_refresh_lock(
                MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
                owner_token="worker-c",
                ttl_seconds=30,
                db_path=db_path,
            )

        self.assertTrue(first["acquired"])
        self.assertFalse(second["acquired"])
        self.assertFalse(wrong_release)
        self.assertTrue(right_release)
        self.assertTrue(third["acquired"])

    def test_dashboard_equity_heatmap_returns_intraday_as_of_and_freshness(self):
        fake_yf = types.SimpleNamespace(download=_fake_intraday_download)
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/equity-heatmap?force=true")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["provider"], "yfinance")
        self.assertEqual(body["interval"], "5m")
        self.assertGreaterEqual(body["universe_size"], 200)
        self.assertEqual(body["universe_size"], len(body["items"]))
        self.assertGreater(body["ok_count"], 100)
        sectors = {item["sector"] for item in body["items"]}
        self.assertGreaterEqual(len(sectors), 10)
        self.assertIn("REAL ESTATE", sectors)
        self.assertIn("BASIC MATERIALS", sectors)
        first = body["items"][0]
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["is_decision_usable"])
        self.assertEqual(first["source"], "yfinance_intraday_5m")
        self.assertIn("industry", first)
        self.assertIn("T", first["as_of"])
        self.assertIn("change_pct", first)
        self.assertIn(first["freshness_status"], {"fresh", "delayed", "closed"})
        self.assertIn("tile_span", first)

    def test_dashboard_equity_heatmap_marks_old_prior_close_as_not_decision_usable(self):
        fake_yf = types.SimpleNamespace(download=_fake_stale_intraday_download)
        client = TestClient(api_server.app)

        with patch.dict(sys.modules, {"yfinance": fake_yf}):
            resp = client.get("/api/v1/dashboard/equity-heatmap?force=true")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["ok_count"], 0)
        self.assertGreater(body["stale_or_unavailable_count"], 0)
        first = body["items"][0]
        self.assertEqual(first["status"], "stale")
        self.assertFalse(first["is_decision_usable"])
        self.assertEqual(first["freshness_status"], "stale_prior_close")


if __name__ == "__main__":
    unittest.main()
