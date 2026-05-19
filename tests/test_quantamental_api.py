from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.api import server as api_server
from pipelines.quantamental import service
from pipelines.quantamental.cache import quantamental_cache
from pipelines.quantamental import snapshot_store


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


class FakeQuantamentalProvider:
    def company(self, ticker: str):
        return {
            "status": "ok",
            "company": {
                "ticker": ticker,
                "market": "US",
                "name": f"{ticker} Corp",
                "sector": "Technology",
                "industry": "Software",
                "current_price": 120.0,
                "market_cap": 120_000_000_000.0,
                "enterprise_value": 118_000_000_000.0,
                "shares_outstanding": 1_000_000_000.0,
                "average_volume": 30_000_000.0,
                "raw_info_metrics": {
                    "trailing_pe": 24.0,
                    "price_to_book": 6.0,
                    "price_to_sales_ttm": 8.0,
                    "enterprise_to_ebitda": 18.0,
                    "profit_margin": 0.22,
                    "gross_margin": 0.62,
                    "operating_margin": 0.30,
                    "return_on_equity": 0.28,
                    "return_on_assets": 0.15,
                    "revenue_growth": 0.12,
                    "earnings_growth": 0.14,
                    "total_revenue": 50_000_000_000.0,
                    "ebitda": 18_000_000_000.0,
                    "free_cashflow": 12_000_000_000.0,
                    "operating_cashflow": 15_000_000_000.0,
                    "total_cash": 20_000_000_000.0,
                    "total_debt": 8_000_000_000.0,
                    "debt_to_equity": 20.0,
                    "current_ratio": 1.8,
                    "quick_ratio": 1.5,
                    "trailing_eps": 5.0,
                    "book_value": 20.0,
                },
                "last_updated": service.now_iso(),
                "source_metadata": {"provider": "fake", "fetched_at": service.now_iso()},
            },
            "source_metadata": {"provider": "fake", "fetched_at": service.now_iso()},
            "warnings": [],
        }

    def fundamentals(self, ticker: str, *, period: str = "annual", years: int = 5):
        return {
            "status": "ok",
            "ticker": ticker,
            "market": "US",
            "period": period,
            "years": years,
            "items": [
                {
                    "date": _days_ago(90),
                    "revenue": 50_000_000_000.0,
                    "gross_profit": 31_000_000_000.0,
                    "operating_income": 15_000_000_000.0,
                    "net_income": 11_000_000_000.0,
                    "ebitda": 18_000_000_000.0,
                    "total_assets": 100_000_000_000.0,
                    "total_equity": 40_000_000_000.0,
                    "current_assets": 35_000_000_000.0,
                    "current_liabilities": 20_000_000_000.0,
                    "cash": 20_000_000_000.0,
                    "inventory": 1_000_000_000.0,
                    "receivables": 6_000_000_000.0,
                    "total_debt": 8_000_000_000.0,
                    "operating_cash_flow": 15_000_000_000.0,
                    "capital_expenditure": -3_000_000_000.0,
                    "free_cash_flow": 12_000_000_000.0,
                },
                {
                    "date": _days_ago(455),
                    "revenue": 44_000_000_000.0,
                    "operating_income": 12_000_000_000.0,
                    "net_income": 9_500_000_000.0,
                    "free_cash_flow": 10_500_000_000.0,
                },
            ],
            "info_metrics": self.company(ticker)["company"]["raw_info_metrics"],
            "warnings": [],
        }

    def prices(self, ticker: str, *, lookback=252, benchmark: str = "SPY"):
        rows = []
        for idx in range(260):
            close = 100 + idx * 0.2
            rows.append(
                {
                    "date": _days_ago(259 - idx),
                    "open": close - 0.3,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "adjusted_close": close,
                    "volume": 30_000_000 + idx * 1000,
                }
            )
        return {
            "status": "ok",
            "ticker": ticker,
            "market": "US",
            "lookback_days": 252,
            "items": rows,
            "benchmark_ticker": benchmark,
            "benchmark_items": rows,
            "source_metadata": {"provider": "fake", "fetched_at": service.now_iso()},
            "warnings": [],
        }


class StalePriceProvider(FakeQuantamentalProvider):
    def prices(self, ticker: str, *, lookback=252, benchmark: str = "SPY"):
        payload = super().prices(ticker, lookback=lookback, benchmark=benchmark)
        stale_rows = []
        for idx, row in enumerate(payload["items"]):
            stale_rows.append({**row, "date": _days_ago(700 - idx)})
        payload["items"] = stale_rows
        payload["benchmark_items"] = stale_rows
        return payload


def test_quantamental_analysis_endpoint_shape(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/analysis/AAPL?style=quality_growth&period=annual&years=5&lookback=252")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "AAPL"
    assert body["composite"]["style"] == "quality_growth"
    assert body["signal"]["not_investment_advice"] is True
    assert body["ai_report"]["signal_preserved"] is True
    assert "data_snapshot" in body["ai_report"]
    assert "used_data" in body["ai_report"]["report"]
    assert body["ai_report"]["report"]["used_data"]["analysis_period"] != ""
    assert body["ai_report"]["report"]["used_data"]["data_source"] != ""
    assert body["quant"]["metrics"]["algorithms"]["volatility_adjusted_breakout"]["algorithm_id"] == "volatility_adjusted_breakout_v1"
    assert body["quant"]["metrics"]["algorithms"]["volatility_adjusted_breakout"]["used_in_composite_score"] is False
    assert body["quant"]["metrics"]["algorithms"]["drawdown_recovery_resilience"]["algorithm_id"] == "drawdown_recovery_resilience_v1"
    assert body["quant"]["metrics"]["algorithms"]["drawdown_recovery_resilience"]["used_in_composite_score"] is False
    assert body["quant"]["metrics"]["algorithms"]["liquidity_participation_stability"]["algorithm_id"] == "liquidity_participation_stability_v1"
    assert body["quant"]["metrics"]["algorithms"]["liquidity_participation_stability"]["used_in_composite_score"] is False
    assert body["execution_policy"] == "scores_and_signal_from_deterministic_engines_ai_interprets_only"


def test_quantamental_analysis_includes_freshness_audit_and_refresh_attempt(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: StalePriceProvider())
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/analysis/AAPL?include_ai=false")

    assert resp.status_code == 200
    body = resp.json()
    freshness = body["freshness"]
    assert freshness["sections"]["company"]["status"] in {"fresh", "unknown"}
    assert freshness["sections"]["fundamentals"]["basis"] == "latest_statement_date"
    assert freshness["sections"]["prices"]["basis"] == "latest_price_date"
    assert body["data_quality"]["freshness"]["status"] == freshness["status"]
    assert freshness.get("refresh_attempted") is True
    assert "prices" in freshness["stale_sections"]
    assert body["data_integrity"]["status"] == "blocked"
    assert body["data_integrity"]["usable_for_signal"] is False
    assert body["signal"]["signal_label"] == "Insufficient Data"


def test_quantamental_top_signal_screen_returns_ranked_top_five(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    monkeypatch.setattr(
        service,
        "build_sec_evidence",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Top signal screen should not block on SEC overlay")),
    )
    client = TestClient(api_server.app)

    resp = client.get(
        "/api/v1/quantamental/screen/top-signals"
        "?tickers=AAPL%20MSFT%20NVDA%20TSLA%20AMD%20CRM&limit=5&include_ai=false"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["requested_count"] == 6
    assert body["scored_count"] == 6
    assert body["eligible_count"] == 6
    assert body["top_count"] == 5
    assert len(body["top_signals"]) == 5
    assert body["top"] == body["top_signals"]
    assert body["top_signals"] == body["ranked_rows"][:5]
    assert body["screened_rows"] == body["rows"]
    assert [row["rank"] for row in body["top_signals"]] == [1, 2, 3, 4, 5]
    assert [row["rank"] for row in body["ranked_rows"]] == [1, 2, 3, 4, 5, 6]
    assert body["ranked_rows"][0]["final_score"] >= body["ranked_rows"][-1]["final_score"]
    assert all(row["final_score"] is not None for row in body["top_signals"])
    assert all(row["usable_for_signal"] is True for row in body["top_signals"])
    assert all("freshness_status" in row for row in body["top_signals"])
    assert body["freshness_summary"]["total"] == 6
    assert body["freshness"] == body["freshness_summary"]
    assert body["summary"]["top_count"] == 5
    assert body["screening_policy"] == "rank_only_fresh_complete_core_data_after_retry_sec_overlay_skipped_for_speed"
    assert "screening_fast_path_sec_overlay_skipped" in body["warnings"]


def test_quantamental_score_screen_filters_by_min_score(monkeypatch):
    quantamental_cache.clear()

    composite_scores = {"AAA": 81.0, "BBB": 92.0, "CCC": 74.0}
    quality_scores = {"AAA": 81.0, "BBB": 66.0, "CCC": 74.0}

    def fake_analysis(request):
        ticker = request.ticker
        score = composite_scores[ticker]
        quality_score = quality_scores[ticker]
        return {
            "status": "ok",
            "ticker": ticker,
            "market": request.market,
            "company": {"ticker": ticker, "name": f"{ticker} Corp", "sector": "Technology", "industry": "Software"},
            "composite": {
                "final_score": score,
                "fundamental_score": score - 3,
                "quant_score": score + 2,
                "risk_score": score - 5,
            },
            "factors": {
                "value_score": score - 10,
                "quality_score": quality_score,
                "growth_score": 55.0,
                "momentum_score": 60.0,
                "low_volatility_score": 65.0,
                "liquidity_score": 70.0,
            },
            "signal": {
                "signal_label": "Buy Candidate" if score >= 75 else "Accumulate Watch",
                "signal_confidence": "medium",
            },
            "data_quality": {"data_quality_score": 0.92, "quality_level": "good", "missing_sections": []},
            "freshness": {"status": "fresh", "freshness_score": 1.0, "stale_sections": [], "warnings": []},
            "data_integrity": {"status": "usable", "usable_for_signal": True, "blocking_sections": []},
            "warnings": [],
        }

    monkeypatch.setattr(service, "analysis", fake_analysis)
    client = TestClient(api_server.app)

    resp = client.get(
        "/api/v1/quantamental/screen/by-score"
        "?tickers=AAA%20BBB%20CCC&score_key=quality&min_score=70&limit=10&include_ai=false"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["score_key"] == "quality"
    assert body["score_label"] == "Quality"
    assert body["min_score"] == 70.0
    assert body["requested_count"] == 3
    assert body["scored_count"] == 3
    assert body["matched_count"] == 2
    assert [row["ticker"] for row in body["matches"]] == ["AAA", "CCC"]
    assert all(row["screen_score"] >= 70 for row in body["matches"])
    assert all(row["screen_score_key"] == "quality" for row in body["matches"])
    assert body["matches"][0]["quality_score"] >= body["matches"][1]["quality_score"]
    assert "BBB" not in [row["ticker"] for row in body["matches"]]
    assert body["screening_policy"] == "rank_fresh_complete_core_data_then_filter_min_score_sec_overlay_skipped_for_speed"
    assert "screening_fast_path_sec_overlay_skipped" in body["warnings"]


def test_quantamental_score_screen_supports_drawdown_resilience_score(monkeypatch):
    quantamental_cache.clear()
    resilience_scores = {"AAA": 82.0, "BBB": 57.0, "CCC": 74.0}

    def fake_analysis(request):
        score = resilience_scores[request.ticker]
        return {
            "status": "ok",
            "ticker": request.ticker,
            "market": request.market,
            "company": {"ticker": request.ticker, "name": f"{request.ticker} Corp"},
            "composite": {"final_score": score - 2, "fundamental_score": score - 4, "quant_score": score, "risk_score": score - 6},
            "factors": {
                "value_score": 55.0,
                "quality_score": 60.0,
                "growth_score": 58.0,
                "momentum_score": 62.0,
                "low_volatility_score": 66.0,
                "liquidity_score": 72.0,
            },
            "quant": {
                "metrics": {
                    "algorithms": {
                        "drawdown_recovery_resilience": {
                            "algorithm_id": "drawdown_recovery_resilience_v1",
                            "drawdown_recovery_resilience_score": score,
                            "classification": "constructive_drawdown_recovery",
                            "used_in_composite_score": False,
                        }
                    }
                }
            },
            "signal": {"signal_label": "Accumulate Watch", "signal_confidence": "medium"},
            "data_quality": {"data_quality_score": 0.92, "quality_level": "good", "missing_sections": []},
            "freshness": {"status": "fresh", "freshness_score": 1.0, "stale_sections": [], "warnings": []},
            "data_integrity": {"status": "usable", "usable_for_signal": True, "blocking_sections": []},
            "warnings": [],
        }

    monkeypatch.setattr(service, "analysis", fake_analysis)
    client = TestClient(api_server.app)

    resp = client.get(
        "/api/v1/quantamental/screen/by-score"
        "?tickers=AAA%20BBB%20CCC&score_key=drawdown_resilience&min_score=70&limit=10&include_ai=false"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["score_key"] == "drawdown_resilience"
    assert body["score_label"] == "Drawdown Resilience"
    assert [row["ticker"] for row in body["matches"]] == ["AAA", "CCC"]
    assert all(row["screen_score_key"] == "drawdown_resilience" for row in body["matches"])
    assert all(row["drawdown_resilience_score"] >= 70 for row in body["matches"])


def test_quantamental_score_screen_supports_liquidity_stability_score(monkeypatch):
    quantamental_cache.clear()
    liquidity_scores = {"AAA": 83.0, "BBB": 54.0, "CCC": 77.0}

    def fake_analysis(request):
        score = liquidity_scores[request.ticker]
        return {
            "status": "ok",
            "ticker": request.ticker,
            "market": request.market,
            "company": {"ticker": request.ticker, "name": f"{request.ticker} Corp"},
            "composite": {"final_score": score - 2, "fundamental_score": score - 4, "quant_score": score, "risk_score": score - 6},
            "factors": {
                "value_score": 55.0,
                "quality_score": 60.0,
                "growth_score": 58.0,
                "momentum_score": 62.0,
                "low_volatility_score": 66.0,
                "liquidity_score": 72.0,
            },
            "quant": {
                "metrics": {
                    "algorithms": {
                        "liquidity_participation_stability": {
                            "algorithm_id": "liquidity_participation_stability_v1",
                            "liquidity_participation_stability_score": score,
                            "classification": "constructive_liquidity_participation",
                            "used_in_composite_score": False,
                        }
                    }
                }
            },
            "signal": {"signal_label": "Accumulate Watch", "signal_confidence": "medium"},
            "data_quality": {"data_quality_score": 0.92, "quality_level": "good", "missing_sections": []},
            "freshness": {"status": "fresh", "freshness_score": 1.0, "stale_sections": [], "warnings": []},
            "data_integrity": {"status": "usable", "usable_for_signal": True, "blocking_sections": []},
            "warnings": [],
        }

    monkeypatch.setattr(service, "analysis", fake_analysis)
    client = TestClient(api_server.app)

    resp = client.get(
        "/api/v1/quantamental/screen/by-score"
        "?tickers=AAA%20BBB%20CCC&score_key=liquidity_stability&min_score=70&limit=10&include_ai=false"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["score_key"] == "liquidity_stability"
    assert body["score_label"] == "Liquidity Stability"
    assert [row["ticker"] for row in body["matches"]] == ["AAA", "CCC"]
    assert all(row["screen_score_key"] == "liquidity_stability" for row in body["matches"])
    assert all(row["liquidity_stability_score"] >= 70 for row in body["matches"])


def test_quantamental_score_screen_default_universe_respects_limit(monkeypatch):
    quantamental_cache.clear()
    tickers = [f"T{i:02d}" for i in range(12)]
    monkeypatch.setitem(service.DEFAULT_SCREENING_UNIVERSES, "default_us_large_cap", tickers)

    def fake_analysis(request):
        index = tickers.index(request.ticker)
        score = 100.0 - index
        return {
            "status": "ok",
            "ticker": request.ticker,
            "market": request.market,
            "company": {"ticker": request.ticker, "name": f"{request.ticker} Corp", "sector": "Technology", "industry": "Software"},
            "composite": {
                "final_score": score,
                "fundamental_score": score - 3,
                "quant_score": score + 2,
                "risk_score": score - 5,
            },
            "factors": {
                "value_score": score - 10,
                "quality_score": score - 8,
                "growth_score": score - 6,
                "momentum_score": score,
                "low_volatility_score": score - 4,
                "liquidity_score": score - 2,
            },
            "signal": {"signal_label": "Buy Candidate", "signal_confidence": "medium"},
            "data_quality": {"data_quality_score": 0.92, "quality_level": "good", "missing_sections": []},
            "freshness": {"status": "fresh", "freshness_score": 1.0, "stale_sections": [], "warnings": []},
            "data_integrity": {"status": "usable", "usable_for_signal": True, "blocking_sections": []},
            "warnings": [],
        }

    monkeypatch.setattr(service, "analysis", fake_analysis)
    client = TestClient(api_server.app)

    resp = client.get(
        "/api/v1/quantamental/screen/by-score"
        "?score_key=momentum&min_score=0&limit=10&include_ai=false"
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["requested_count"] == 10
    assert body["matched_count"] == 10
    assert body["returned_count"] == 10
    assert len(body["matches"]) == 10
    assert [row["ticker"] for row in body["matches"]] == tickers[:10]
    assert all(row["screen_score_key"] == "momentum" for row in body["matches"])


def test_quantamental_health_lists_global_as_supported_and_quant_uses_global_benchmark(monkeypatch):
    quantamental_cache.clear()
    captured: dict[str, str] = {}

    class CaptureProvider(FakeQuantamentalProvider):
        def __init__(self, market: str):
            self.market = market

        def prices(self, ticker: str, *, lookback=252, benchmark: str = "SPY"):
            captured["benchmark"] = benchmark
            payload = super().prices(ticker, lookback=lookback, benchmark=benchmark)
            payload["market"] = self.market
            return payload

    monkeypatch.setattr(service, "provider_for_market", lambda market: CaptureProvider(market))
    client = TestClient(api_server.app)

    health = client.get("/api/v1/quantamental/health").json()
    quant = service.quant("ASML.AS", market="GLOBAL", lookback=252)

    assert "GLOBAL" in health["supported_markets"]
    assert "GLOBAL" not in health["unsupported_markets"]
    assert "global_yfinance_provider" in health["enhancements"]
    assert captured["benchmark"] == "ACWI"
    assert quant["market"] == "GLOBAL"
    assert quant["benchmark_ticker"] == "ACWI"


def test_quantamental_resolve_endpoint_and_global_sec_hydration_dry_run():
    client = TestClient(api_server.app)

    resolved = client.get("/api/v1/quantamental/resolve/7203?market=GLOBAL")
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["provider_ticker"] == "7203.T"
    assert body["sec_ticker"] == "TM"
    assert "global_symbol_resolved_to_yfinance:7203.T" in body["warnings"]

    hydration = client.post(
        "/api/v1/quantamental/sec/global/hydrate?dry_run=true",
        json={"tickers": ["ASML.AS", "7203", "9999.T"]},
    )
    assert hydration.status_code == 200
    plan = hydration.json()["plan"]
    assert hydration.json()["status"] == "dry_run"
    assert plan["sec_tickers"] == ["ASML", "TM"]
    assert any(item["ticker"] == "9999.T" for item in plan["skipped"])


def test_quantamental_legacy_prefix_and_section_endpoints(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    for path in [
        "/api/quantamental/company/MSFT",
        "/api/quantamental/fundamentals/MSFT",
        "/api/quantamental/quant/MSFT",
        "/api/quantamental/factors/MSFT",
        "/api/quantamental/risk/MSFT",
        "/api/quantamental/composite/MSFT",
        "/api/quantamental/signal/MSFT",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert resp.json()


def test_quantamental_ai_report_and_qa_do_not_override_signal(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)
    analysis = client.get("/api/v1/quantamental/analysis/NVDA").json()

    report = client.post("/api/v1/quantamental/ai/report", json={"context": analysis, "use_llm": False, "output_language": "en"}).json()
    answer = client.post(
        "/api/v1/quantamental/ai/qa",
        json={"context": analysis, "question": "what is the sell risk?", "use_llm": False, "output_language": "en"},
    ).json()

    assert report["signal_label"] == analysis["signal"]["signal_label"]
    assert report["not_investment_advice"] is True
    assert report["output_language"] == "en"
    assert report["report"]["used_data"]["data_basis_date"] != ""
    assert report["report"]["used_data"]["analysis_period"] != ""
    assert "key_changes" in report["report"]
    assert "interpretation" in report["report"]
    assert "user_actions" in report["report"]
    assert "advisory_only_no_direct_orders" in report["guardrails"]
    assert answer["not_investment_advice"] is True
    assert answer["output_language"] == "en"
    assert "instruction to sell" in answer["answer"].lower()


def test_quantamental_ai_report_and_qa_support_korean_output(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)
    analysis = client.get("/api/v1/quantamental/analysis/NVDA?include_ai=true&output_language=ko").json()

    answer = client.post(
        "/api/v1/quantamental/ai/qa",
        json={"context": analysis, "question": "리스크를 설명해주세요", "use_llm": False, "output_language": "ko"},
    ).json()

    assert analysis["output_language"] == "ko"
    assert analysis["ai_report"]["output_language"] == "ko"
    assert "투자 자문" in analysis["ai_report"]["report"]["safety_note"]
    assert "used_data" in analysis["ai_report"]["report"]
    assert "확인 불가" not in str(analysis["ai_report"]["report"]["used_data"]["analysis_period"])
    assert answer["output_language"] == "ko"
    assert "매도 지시가 아닙니다" in answer["answer"]


def test_quantamental_invalid_ticker_returns_structured_insufficient_data():
    quantamental_cache.clear()
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/analysis/INVALID_TEST_TICKER_123")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["signal"]["signal_label"] == "Insufficient Data"
    assert body["ai_report"]["signal_label"] == "Insufficient Data"
    assert body["ai_report"]["provider"] == "deterministic_interpreter"
    assert "ticker_validation_failed" in body["warnings"]
    assert body["data_quality"]["quality_level"] == "poor"


def test_quantamental_compare_adds_peer_relative_scores_and_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTAMENTAL_DATA_DIR", str(tmp_path / "quantamental"))
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    resp = client.post(
        "/api/v1/quantamental/compare",
        json={"tickers": ["AAPL", "MSFT", "NVDA"], "style": "balanced", "include_ai": False},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["count"] == 3
    assert body["peer_groups"]
    assert all("peer_relative" in row for row in body["rows"])
    assert any(row["peer_relative"]["peer_count"] >= 2 for row in body["rows"])
    snapshot_id = body["analyses"][0]["snapshot"]["snapshot_id"]
    history = client.get("/api/v1/quantamental/snapshots?ticker=AAPL").json()
    replay = client.get(f"/api/v1/quantamental/snapshots/{snapshot_id}").json()
    assert history["count"] >= 1
    assert replay["status"] == "ok"
    assert replay["payload"]["ticker"] == "AAPL"
    export_resp = client.get(f"/api/v1/quantamental/snapshots/{snapshot_id}/export?format=csv")
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    assert "signal_label" in export_resp.text


def test_quantamental_snapshot_diff_and_retention_preview(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTAMENTAL_DATA_DIR", str(tmp_path / "quantamental"))
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    first = client.get("/api/v1/quantamental/analysis/AAPL?style=balanced&include_ai=false").json()
    second = client.get("/api/v1/quantamental/analysis/AAPL?style=value&include_ai=false").json()
    first_id = first["snapshot"]["snapshot_id"]
    second_id = second["snapshot"]["snapshot_id"]

    diff = client.get(f"/api/v1/quantamental/snapshots/diff?base_snapshot_id={first_id}&target_snapshot_id={second_id}").json()
    retention = client.post("/api/v1/quantamental/snapshots/retention?ticker=AAPL&keep_last=1&dry_run=true").json()

    assert diff["status"] == "ok"
    assert any(item["path"] == "style" for item in diff["differences"])
    assert retention["status"] == "ok"
    assert retention["dry_run"] is True
    assert retention["prune_count"] >= 1


def test_quantamental_snapshot_retention_delete_uses_temp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTAMENTAL_DATA_DIR", str(tmp_path))
    for idx in range(3):
        snapshot = snapshot_store.save_snapshot(
            {
                "status": "ok",
                "ticker": "AAPL",
                "market": "US",
                "style": "balanced",
                "generated_at": f"2026-05-15T00:00:0{idx}+00:00",
                "signal": {"signal_label": "Accumulate Watch"},
                "composite": {"final_score": 60 + idx},
                "data_quality": {"quality_level": "good"},
            }
        )
        with sqlite3.connect(snapshot_store.db_path()) as conn:
            conn.execute(
                "UPDATE quantamental_snapshots SET created_at=? WHERE snapshot_id=?",
                (f"2026-05-15T00:00:0{idx}+00:00", snapshot["snapshot_id"]),
            )

    preview = snapshot_store.prune_snapshots("AAPL", keep_last=1, dry_run=True)
    deleted = snapshot_store.prune_snapshots("AAPL", keep_last=1, dry_run=False)
    remaining = snapshot_store.list_snapshots("AAPL", limit=10)

    assert preview["prune_count"] == 2
    assert deleted["dry_run"] is False
    assert deleted["prune_count"] == 2
    assert remaining["count"] == 1
    assert remaining["items"][0]["final_score"] == 62


def test_quantamental_compare_can_expand_peer_universe(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    monkeypatch.setattr(
        service,
        "expand_peer_universe",
        lambda tickers, analyses, market="US", max_total=8: {
            "status": "ok",
            "method": "fixture",
            "requested_tickers": tickers,
            "added_tickers": ["ADBE"],
            "candidates": [{"ticker": "ADBE", "sector": "Technology", "industry": "Software"}],
            "warnings": [],
        },
    )
    client = TestClient(api_server.app)

    resp = client.post(
        "/api/v1/quantamental/compare",
        json={"tickers": ["AAPL", "MSFT"], "expand_peer_universe": True, "peer_limit": 3},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["peer_universe"]["added_tickers"] == ["ADBE"]
    assert body["count"] == 3
    assert any(row["ticker"] == "ADBE" for row in body["rows"])


def test_quantamental_compare_watchlists_persist_server_side(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTAMENTAL_DATA_DIR", str(tmp_path))
    client = TestClient(api_server.app)

    created = client.post(
        "/api/v1/quantamental/compare/watchlists",
        json={
            "name": "Core Tech",
            "tickers": ["aapl", "msft", "aapl"],
            "market": "US",
            "style": "quality_growth",
            "expand_peer_universe": True,
            "peer_limit": 6,
        },
    )
    assert created.status_code == 200
    item = created.json()["item"]
    assert item["tickers"] == ["AAPL", "MSFT"]
    assert item["style"] == "quality_growth"
    assert item["expand_peer_universe"] is True

    listed = client.get("/api/v1/quantamental/compare/watchlists")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    updated = client.put(
        f"/api/v1/quantamental/compare/watchlists/{item['id']}",
        json={"name": "Core Tech", "tickers": ["NVDA", "TSLA"], "peer_limit": 4},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["tickers"] == ["NVDA", "TSLA"]

    deleted = client.delete(f"/api/v1/quantamental/compare/watchlists/{item['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/v1/quantamental/compare/watchlists").json()["count"] == 0


def test_quantamental_compare_get_accepts_space_separated_tickers(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/compare?tickers=AAPL%20MSFT&include_ai=false")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert [row["ticker"] for row in body["rows"]] == ["AAPL", "MSFT"]


def test_quantamental_get_validation_errors_return_400(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/analysis/AAPL?style=quality")

    assert resp.status_code == 400
    assert resp.json()["detail"][0]["loc"][-1] == "style"


def test_quantamental_sec_evidence_is_attached_to_risk(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setattr(service, "provider_for_market", lambda market: FakeQuantamentalProvider())
    monkeypatch.setattr(
        service,
        "build_sec_evidence",
        lambda ticker, market="US": {
            "status": "ok",
            "ticker": ticker,
            "market": market,
            "filing_count": 2,
            "fact_count": 12,
            "risk_flags": ["sec_low_cash_conversion"],
            "quality_flags": ["sec_companyfacts_available"],
            "warnings": [],
        },
    )
    client = TestClient(api_server.app)

    body = client.get("/api/v1/quantamental/analysis/AAPL?include_ai=false").json()

    assert body["sec_evidence"]["status"] == "ok"
    assert "sec_low_cash_conversion" in body["risk"]["risk_flags"]
    assert body["data_quality"]["evidence_sources"]["sec_edgar"]["fact_count"] == 12


def test_quantamental_kr_dart_provider_fails_closed_without_key(monkeypatch):
    quantamental_cache.clear()
    monkeypatch.setenv("DART_API_KEY", "")
    client = TestClient(api_server.app)

    resp = client.get("/api/v1/quantamental/company/005930?market=KR")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "dart_api_key_missing" in body["warnings"]
