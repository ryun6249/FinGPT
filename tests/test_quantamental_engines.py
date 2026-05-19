from __future__ import annotations

import sys
from types import SimpleNamespace

from pipelines.quantamental import ai_service, qa_service
from pipelines.quantamental.ai_service import build_context, generate_report
from pipelines.quantamental.factor_engine import calculate_factors
from pipelines.quantamental.fundamental_engine import calculate_fundamentals, safe_divide
from pipelines.quantamental.global_market import global_sec_hydration_plan, resolve_global_symbol
from pipelines.quantamental.hybrid_score_engine import calculate_composite
from pipelines.quantamental.peer_engine import apply_peer_relative_scores, expand_peer_universe
from pipelines.quantamental.providers import (
    OpenDartQuantamentalProvider,
    YFinanceQuantamentalProvider,
    _dart_statement_row_v2,
    _naver_kr_price_rows,
    provider_for_market,
)
from pipelines.quantamental.qa_service import answer_question
from pipelines.quantamental.quant_engine import calculate_quant
from pipelines.quantamental.risk_engine import calculate_risk
from pipelines.quantamental.sec_evidence import build_sec_evidence
from pipelines.quantamental.service import data_quality
from pipelines.quantamental.signal_engine import classify_signal


def _company():
    return {
        "ticker": "TEST",
        "market": "US",
        "name": "Test Company",
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
    }


def _fundamental_payload():
    return {
        "status": "ok",
        "ticker": "TEST",
        "market": "US",
        "period": "annual",
        "years": 5,
        "items": [
            {
                "date": "2025-12-31",
                "revenue": 50_000_000_000.0,
                "gross_profit": 31_000_000_000.0,
                "operating_income": 15_000_000_000.0,
                "net_income": 11_000_000_000.0,
                "ebitda": 18_000_000_000.0,
                "total_assets": 100_000_000_000.0,
                "total_equity": 40_000_000_000.0,
                "total_liabilities": 60_000_000_000.0,
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
                "date": "2024-12-31",
                "revenue": 44_000_000_000.0,
                "gross_profit": 26_000_000_000.0,
                "operating_income": 12_000_000_000.0,
                "net_income": 9_500_000_000.0,
                "ebitda": 15_000_000_000.0,
                "total_assets": 90_000_000_000.0,
                "total_equity": 36_000_000_000.0,
                "total_liabilities": 54_000_000_000.0,
                "current_assets": 30_000_000_000.0,
                "current_liabilities": 19_000_000_000.0,
                "cash": 16_000_000_000.0,
                "inventory": 900_000_000.0,
                "receivables": 5_800_000_000.0,
                "total_debt": 9_000_000_000.0,
                "operating_cash_flow": 13_000_000_000.0,
                "capital_expenditure": -2_500_000_000.0,
                "free_cash_flow": 10_500_000_000.0,
            },
            {
                "date": "2023-12-31",
                "revenue": 39_000_000_000.0,
                "net_income": 8_000_000_000.0,
                "free_cash_flow": 9_000_000_000.0,
            },
        ],
        "info_metrics": _company()["raw_info_metrics"],
        "warnings": [],
    }


def _price_payload(count: int = 260):
    rows = []
    for idx in range(count):
        close = 100 + idx * 0.2
        rows.append(
            {
                "date": f"2025-01-{(idx % 28) + 1:02d}" if idx < 28 else f"2025-{(idx // 28) + 1:02d}-{(idx % 28) + 1:02d}",
                "open": close - 0.4,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "adjusted_close": close,
                "volume": 30_000_000 + idx * 1000,
            }
        )
    return {
        "status": "ok",
        "ticker": "TEST",
        "market": "US",
        "lookback_days": count,
        "items": rows,
        "benchmark_ticker": "SPY",
        "benchmark_items": rows,
        "warnings": [],
    }


def _engine_bundle():
    fundamentals = calculate_fundamentals(_fundamental_payload(), _company())
    quant = calculate_quant(_price_payload())
    factors = calculate_factors(fundamentals, quant, _company())
    quality = data_quality({"status": "ok", "company": _company()}, fundamentals, quant, factors)
    risk = calculate_risk(fundamentals, quant, factors, quality["data_quality_score"])
    composite = calculate_composite(fundamentals, quant, factors, risk, style="balanced")
    signal = classify_signal(composite, risk, quality)
    return fundamentals, quant, factors, quality, risk, composite, signal


def test_fundamental_engine_handles_division_by_zero_and_missing_data():
    assert safe_divide(1, 0) is None
    payload = _fundamental_payload()
    payload["items"][0]["revenue"] = 0
    payload["info_metrics"]["total_revenue"] = None
    payload["info_metrics"]["gross_margin"] = None
    result = calculate_fundamentals(payload, _company())

    assert result["status"] == "ok"
    assert "profitability.gross_margin" in result["missing_metrics"]
    assert result["metrics"]["profitability"]["gross_margin"] is None


def test_quant_engine_handles_insufficient_price_history_without_crash():
    result = calculate_quant(_price_payload(count=5))

    assert result["status"] == "ok"
    assert "insufficient_price_history_for_core_quant_metrics" in result["warnings"]
    assert result["metrics"]["return"]["return_252d"] is None
    assert result["metrics"]["algorithm"]["algorithm_id"] == "quality_adjusted_momentum_v1"
    assert result["metrics"]["algorithm"]["quality_adjusted_momentum_score"] is None
    assert result["metrics"]["algorithm"]["classification"] == "insufficient_data"
    assert result["metrics"]["algorithm"]["used_in_composite_score"] is False
    breakout = result["metrics"]["algorithms"]["volatility_adjusted_breakout"]
    assert breakout["algorithm_id"] == "volatility_adjusted_breakout_v1"
    assert breakout["volatility_adjusted_breakout_score"] is None
    assert breakout["classification"] == "insufficient_data"
    assert breakout["used_in_composite_score"] is False
    resilience = result["metrics"]["algorithms"]["drawdown_recovery_resilience"]
    assert resilience["algorithm_id"] == "drawdown_recovery_resilience_v1"
    assert resilience["drawdown_recovery_resilience_score"] is None
    assert resilience["classification"] == "insufficient_data"
    assert resilience["used_in_composite_score"] is False
    liquidity_stability = result["metrics"]["algorithms"]["liquidity_participation_stability"]
    assert liquidity_stability["algorithm_id"] == "liquidity_participation_stability_v1"
    assert liquidity_stability["liquidity_participation_stability_score"] is None
    assert liquidity_stability["classification"] == "insufficient_data"
    assert liquidity_stability["used_in_composite_score"] is False


def test_factor_risk_hybrid_and_signal_are_deterministic():
    fundamentals, quant, factors, quality, risk, composite, signal = _engine_bundle()

    assert fundamentals["category_scores"]["profitability"] is not None
    assert quant["component_scores"]["momentum"] is not None
    assert quant["component_scores"]["quality_adjusted_momentum"] is not None
    assert quant["component_scores"]["volatility_adjusted_breakout"] is not None
    assert quant["component_scores"]["drawdown_recovery_resilience"] is not None
    assert quant["component_scores"]["liquidity_participation_stability"] is not None
    assert quant["metrics"]["algorithm"]["algorithm_id"] == "quality_adjusted_momentum_v1"
    assert quant["metrics"]["algorithm"]["not_investment_advice"] is True
    assert quant["metrics"]["algorithm"]["used_in_composite_score"] is False
    breakout = quant["metrics"]["algorithms"]["volatility_adjusted_breakout"]
    assert breakout["algorithm_id"] == "volatility_adjusted_breakout_v1"
    assert breakout["not_investment_advice"] is True
    assert breakout["used_in_composite_score"] is False
    resilience = quant["metrics"]["algorithms"]["drawdown_recovery_resilience"]
    assert resilience["algorithm_id"] == "drawdown_recovery_resilience_v1"
    assert resilience["not_investment_advice"] is True
    assert resilience["used_in_composite_score"] is False
    liquidity_stability = quant["metrics"]["algorithms"]["liquidity_participation_stability"]
    assert liquidity_stability["algorithm_id"] == "liquidity_participation_stability_v1"
    assert liquidity_stability["not_investment_advice"] is True
    assert liquidity_stability["used_in_composite_score"] is False
    assert factors["score_method"] == "deterministic_rule_based_v1"
    assert risk["risk_level"] in {"low risk", "medium risk", "elevated risk", "high risk", "unknown"}
    assert composite["score_explanation"]["method"] == "deterministic_weighted_average_v1"
    assert signal["not_investment_advice"] is True
    assert signal["signal_label"] in {
        "Strong Buy Candidate",
        "Buy Candidate",
        "Accumulate Watch",
        "Neutral / Hold-Watch",
        "Avoid",
        "Sell Risk / Reduce Risk",
        "Insufficient Data",
    }


def test_peer_relative_scores_rank_requested_peer_group():
    analyses = []
    for ticker, score, value_score in [
        ("AAA", 80.0, 20.0),
        ("BBB", 65.0, 60.0),
        ("CCC", 50.0, 90.0),
    ]:
        analyses.append(
            {
                "status": "ok",
                "ticker": ticker,
                "market": "US",
                "company": {"ticker": ticker, "sector": "Technology", "industry": "Software"},
                "composite": {"final_score": score},
                "signal": {"signal_label": "Neutral / Hold-Watch"},
                "data_quality": {"data_quality_score": 90.0, "quality_level": "good"},
                "factors": {
                    "value_score": value_score,
                    "quality_score": score,
                    "growth_score": score,
                    "momentum_score": score,
                    "low_volatility_score": score,
                    "liquidity_score": score,
                },
            }
        )

    result = apply_peer_relative_scores(analyses)

    assert result["status"] == "ok"
    assert result["peer_groups"][0]["scope"] == "industry"
    assert analyses[0]["peer_relative"]["rank"] == 1
    assert analyses[2]["peer_relative"]["normalized_factor_scores"]["value_score"] == 100.0


def test_global_peer_universe_uses_static_fallback_when_metadata_is_empty(monkeypatch):
    monkeypatch.setattr(
        "pipelines.quantamental.peer_engine.repository.peer_universe_candidates",
        lambda *args, **kwargs: [],
    )
    result = expand_peer_universe(
        ["ASML.AS"],
        [
            {
                "ticker": "ASML.AS",
                "status": "ok",
                "company": {
                    "name": "ASML Holding N.V.",
                    "sector": "Technology",
                    "industry": "Semiconductor Equipment & Materials",
                },
            }
        ],
        market="GLOBAL",
        max_total=4,
    )

    assert result["status"] == "ok"
    assert result["method"] == "global_static_liquid_peer_seed_v1"
    assert "global_peer_universe_static_fallback" in result["warnings"]
    assert "TSM" in result["added_tickers"]


def test_dart_account_id_mapping_and_krx_price_parser(monkeypatch):
    row = _dart_statement_row_v2(
        [
            {"account_id": "ifrs-full_Revenue", "thstrm_amount": "1,000"},
            {"account_id": "dart_OperatingIncomeLoss", "thstrm_amount": "120"},
            {"account_id": "ifrs-full_ProfitLoss", "thstrm_amount": "90"},
            {"account_id": "ifrs-full_Assets", "thstrm_amount": "2,000"},
            {"account_id": "ifrs-full_Liabilities", "thstrm_amount": "800"},
            {"account_id": "ifrs-full_Equity", "thstrm_amount": "1,200"},
            {"account_id": "ifrs-full_CurrentAssets", "thstrm_amount": "500"},
            {"account_id": "ifrs-full_CurrentLiabilities", "thstrm_amount": "250"},
            {"account_id": "ifrs-full_Borrowings", "thstrm_amount": "300"},
            {"account_id": "ifrs-full_CashFlowsFromUsedInOperatingActivities", "thstrm_amount": "150"},
            {"account_id": "ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "thstrm_amount": "40"},
        ],
        2025,
    )

    assert row["revenue"] == 1000.0
    assert row["operating_income"] == 120.0
    assert row["net_income"] == 90.0
    assert row["total_assets"] == 2000.0
    assert row["total_liabilities"] == 800.0
    assert row["total_equity"] == 1200.0
    assert row["current_assets"] == 500.0
    assert row["current_liabilities"] == 250.0
    assert row["total_debt"] == 300.0
    assert row["free_cash_flow"] == 110.0

    dart_row = _dart_statement_row_v2(
        [
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_Assets", "account_nm": "자산총계", "thstrm_amount": "566,942"},
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_CurrentAssets", "account_nm": "유동자산", "thstrm_amount": "247,684"},
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_CurrentLiabilities", "account_nm": "유동부채", "thstrm_amount": "106,411"},
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_Liabilities", "account_nm": "부채총계", "thstrm_amount": "130,621"},
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_Equity", "account_nm": "자본총계", "thstrm_amount": "436,320"},
            {"sj_nm": "자본변동표", "account_id": "ifrs-full_Equity", "account_nm": "자본총계", "thstrm_amount": "897"},
            {"sj_nm": "현금흐름표", "account_id": "ifrs-full_IncreaseDecreaseInCashAndCashEquivalents", "account_nm": "현금의 증가", "thstrm_amount": "4,150"},
            {"sj_nm": "재무상태표", "account_id": "ifrs-full_CashAndCashEquivalents", "account_nm": "현금및현금성자산", "thstrm_amount": "57,856"},
            {"sj_nm": "손익계산서", "account_id": "ifrs-full_ProfitLoss", "account_nm": "당기순이익", "thstrm_amount": "45,206"},
            {"sj_nm": "현금흐름표", "account_id": "ifrs-full_ProfitLoss", "account_nm": "당기순이익", "thstrm_amount": "0"},
        ],
        2025,
    )

    assert dart_row["total_assets"] == 566942.0
    assert dart_row["current_assets"] == 247684.0
    assert dart_row["current_liabilities"] == 106411.0
    assert dart_row["total_liabilities"] == 130621.0
    assert dart_row["total_equity"] == 436320.0
    assert dart_row["cash"] == 57856.0
    assert dart_row["net_income"] == 45206.0

    class FakeResponse:
        text = """
        [['날짜', '시가', '고가', '저가', '종가', '거래량'],
        ["20250102", 52700, 53600, 52300, 53400, 16630538],
        ["20250103", 52800, 55100, 52800, 54400, 19318046]]
        """

        def raise_for_status(self):
            return None

    monkeypatch.setattr("pipelines.quantamental.providers.httpx.get", lambda *args, **kwargs: FakeResponse())
    rows = _naver_kr_price_rows("005930", days=1, timeout_s=1)

    assert rows == [
        {
            "date": "2025-01-03",
            "open": 52800.0,
            "high": 55100.0,
            "low": 52800.0,
            "close": 54400.0,
            "adjusted_close": 54400.0,
            "volume": 19318046.0,
        }
    ]


def test_kr_price_provider_falls_back_to_naver_when_yfinance_empty(monkeypatch):
    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, **kwargs):
            return SimpleNamespace(empty=True)

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))
    monkeypatch.setattr(
        "pipelines.quantamental.providers._naver_kr_price_rows",
        lambda stock_code, *, days, timeout_s: [
            {
                "date": "2026-05-14",
                "open": 50000.0,
                "high": 51000.0,
                "low": 49500.0,
                "close": 50500.0,
                "adjusted_close": 50500.0,
                "volume": 1000.0,
            }
        ],
    )

    result = OpenDartQuantamentalProvider().prices("005930", lookback=5)

    assert result["status"] == "ok"
    assert result["items"][0]["close"] == 50500.0
    assert result["source_metadata"]["provider"] == "naver_finance_krx"
    assert result["source_metadata"]["fallback_from"] == "yfinance_kr"


def test_global_market_routes_to_yfinance_provider():
    provider = provider_for_market("GLOBAL")

    assert isinstance(provider, YFinanceQuantamentalProvider)
    assert provider.market == "GLOBAL"


def test_global_symbol_resolver_maps_common_local_aliases():
    toyota = resolve_global_symbol("7203")
    asml = resolve_global_symbol("ASML.AS")

    assert toyota.provider_ticker == "7203.T"
    assert toyota.sec_ticker == "TM"
    assert "global_symbol_resolved_to_yfinance:7203.T" in toyota.warnings
    assert asml.provider_ticker == "ASML.AS"
    assert asml.sec_ticker == "ASML"


def test_yfinance_global_provider_uses_resolved_symbol(monkeypatch):
    captured: list[str] = []

    class FakeTicker:
        def __init__(self, symbol):
            captured.append(symbol)

        def history(self, **kwargs):
            return SimpleNamespace(empty=True)

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    result = YFinanceQuantamentalProvider(market="GLOBAL").prices("7203", lookback=20, benchmark="ACWI")

    assert captured[:2] == ["7203.T", "ACWI"]
    assert result["resolved_ticker"] == "7203.T"
    assert result["provider_ticker"] == "7203.T"
    assert "global_symbol_resolved_to_yfinance:7203.T" in result["warnings"]


def test_global_sec_hydration_plan_maps_known_aliases_and_skips_unknown():
    plan = global_sec_hydration_plan(["ASML.AS", "7203", "9999.T"])

    assert plan["status"] == "ok"
    assert plan["sec_tickers"] == ["ASML", "TM"]
    assert any(item["ticker"] == "9999.T" for item in plan["skipped"])


def test_sec_evidence_includes_provenance_and_filing_excerpts(monkeypatch):
    monkeypatch.setattr(
        "pipelines.quantamental.sec_evidence.repository.latest_filings",
        lambda *args, **kwargs: [
            {
                "form_type": "10-K",
                "filed_at": "2026-02-01",
                "report_date": "2025-12-31",
                "description": "Annual report",
                "primary_document": "aapl-20251231.htm",
                "url": "https://www.sec.gov/example",
            }
        ],
    )
    monkeypatch.setattr(
        "pipelines.quantamental.sec_evidence.repository.latest_sec_financial_facts",
        lambda *args, **kwargs: [
            {
                "taxonomy": "us-gaap",
                "concept": "Assets",
                "label": "Assets",
                "unit": "USD",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "end_date": "2025-12-31",
                "filed_at": "2026-02-01",
                "accession_number": "000000",
                "value": 1000.0,
                "source": "sec_companyfacts",
            }
        ],
    )

    result = build_sec_evidence("AAPL")

    assert result["status"] == "ok"
    assert result["concept_provenance"][0]["field"] == "total_assets"
    assert result["filing_excerpts"][0]["form_type"] == "10-K"
    assert "annual filing" in result["filing_excerpts"][0]["excerpt"]


def test_sec_evidence_can_include_full_filing_text_excerpt(monkeypatch):
    monkeypatch.setattr(
        "pipelines.quantamental.sec_evidence.repository.latest_filings",
        lambda *args, **kwargs: [
            {
                "form_type": "10-K",
                "filed_at": "2026-02-01",
                "report_date": "2025-12-31",
                "description": "Annual report",
                "url": "https://www.sec.gov/Archives/example/aapl.htm",
            }
        ],
    )
    monkeypatch.setattr(
        "pipelines.quantamental.sec_evidence.repository.latest_sec_financial_facts",
        lambda *args, **kwargs: [
            {
                "taxonomy": "us-gaap",
                "concept": "Assets",
                "label": "Assets",
                "unit": "USD",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "end_date": "2025-12-31",
                "filed_at": "2026-02-01",
                "accession_number": "000000",
                "value": 1000.0,
                "source": "sec_companyfacts",
            }
        ],
    )

    class FakeResponse:
        text = "<html><body>Item 1A. Risk Factors Our business faces supply and market risks. Item 1B.</body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("pipelines.quantamental.sec_evidence.httpx.get", lambda *args, **kwargs: FakeResponse())

    result = build_sec_evidence("AAPL", include_filing_text=True)

    excerpt = result["filing_excerpts"][0]
    assert excerpt["source"] == "sec_filing_text"
    assert excerpt["section"] == "Item 1A Risk Factors"
    assert "supply and market risks" in excerpt["excerpt"]


def test_global_sec_evidence_uses_adr_alias_for_dual_listed_symbols(monkeypatch):
    def fake_filings(ticker, **kwargs):
        if ticker != "ASML":
            return []
        return [
            {
                "form_type": "20-F",
                "filed_at": "2026-02-01",
                "report_date": "2025-12-31",
                "description": "ASML annual report",
                "primary_document": "asml-20251231.htm",
                "url": "https://www.sec.gov/example/asml",
            }
        ]

    def fake_facts(ticker, **kwargs):
        if ticker != "ASML":
            return []
        return [
            {
                "taxonomy": "us-gaap",
                "concept": "Assets",
                "label": "Assets",
                "unit": "USD",
                "form_type": "20-F",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "end_date": "2025-12-31",
                "filed_at": "2026-02-01",
                "accession_number": "000000",
                "value": 1000.0,
                "source": "sec_companyfacts",
            }
        ]

    monkeypatch.setattr("pipelines.quantamental.sec_evidence.repository.latest_filings", fake_filings)
    monkeypatch.setattr("pipelines.quantamental.sec_evidence.repository.latest_sec_financial_facts", fake_facts)

    result = build_sec_evidence("ASML.AS", market="GLOBAL")

    assert result["status"] == "ok"
    assert result["market"] == "GLOBAL"
    assert result["sec_ticker"] == "ASML"
    assert "sec_evidence_global_adr_fallback:ASML" in result["warnings"]
    assert result["filing_excerpts"][0]["form_type"] == "20-F"
    assert "foreign private issuer" in result["filing_excerpts"][0]["excerpt"]


def test_global_sec_evidence_skips_when_no_sec_alias():
    result = build_sec_evidence("9999.T", market="GLOBAL")

    assert result["status"] == "skipped"
    assert "sec_evidence_global_no_sec_alias" in result["warnings"]


def test_ai_and_qa_interpret_without_overriding_signal_or_giving_orders():
    fundamentals, quant, factors, quality, risk, composite, signal = _engine_bundle()
    analysis = {
        "ticker": "TEST",
        "market": "US",
        "company": _company(),
        "fundamentals": fundamentals,
        "quant": quant,
        "factors": factors,
        "risk": risk,
        "composite": composite,
        "signal": signal,
        "data_quality": quality,
    }
    context = build_context(analysis)
    assert context["quant_snapshot"]["quality_adjusted_momentum"]["algorithm_id"] == "quality_adjusted_momentum_v1"
    assert context["quant_snapshot"]["volatility_adjusted_breakout"]["algorithm_id"] == "volatility_adjusted_breakout_v1"
    assert context["quant_snapshot"]["drawdown_recovery_resilience"]["algorithm_id"] == "drawdown_recovery_resilience_v1"
    assert context["quant_snapshot"]["liquidity_participation_stability"]["algorithm_id"] == "liquidity_participation_stability_v1"
    report = generate_report(context, use_llm=False)
    answer = answer_question("why Buy Candidate?", context, use_llm=False)

    assert report["signal_label"] == signal["signal_label"]
    assert report["signal_preserved"] is True
    assert report["not_investment_advice"] is True
    assert "quality_adjusted_momentum_v1" in str(report["report"]["key_changes"])
    assert "volatility_adjusted_breakout_v1" in str(report["report"]["key_changes"])
    assert "drawdown_recovery_resilience_v1" in str(report["report"]["key_changes"])
    assert "liquidity_participation_stability_v1" in str(report["report"]["key_changes"])
    assert "buy now" not in str(report).lower()
    assert answer["not_investment_advice"] is True
    assert "must buy" not in answer["answer"].lower()


def test_ai_and_qa_llm_failure_or_malformed_json_falls_back(monkeypatch):
    fundamentals, quant, factors, quality, risk, composite, signal = _engine_bundle()
    context = build_context(
        {
            "ticker": "TEST",
            "market": "US",
            "company": _company(),
            "fundamentals": fundamentals,
            "quant": quant,
            "factors": factors,
            "risk": risk,
            "composite": composite,
            "signal": signal,
            "data_quality": quality,
        }
    )

    def broken_report_call(*args, **kwargs):
        raise RuntimeError("forced provider failure")

    monkeypatch.setattr(ai_service, "_call_local_llm", broken_report_call)
    report = ai_service.generate_report(context, use_llm=True, timeout_s=1)

    assert report["status"] == "partial"
    assert report["provider"] == "deterministic_interpreter"
    assert report["signal_label"] == signal["signal_label"]
    assert report["signal_preserved"] is True
    assert "llm_provider_failed_or_rejected_output" in report["warnings"]

    def malformed_qa_call(*args, **kwargs):
        return "{not-json", "fake-llm", 0.01

    monkeypatch.setattr(qa_service, "_call_local_llm", malformed_qa_call)
    answer = qa_service.answer_question("why Buy Candidate?", context, use_llm=True, timeout_s=1)

    assert answer["status"] == "partial"
    assert answer["provider"] == "deterministic_qa"
    assert answer["not_investment_advice"] is True
    assert "llm_provider_failed_or_rejected_output" in answer["warnings"]


def test_ai_and_qa_reject_direct_investment_orders(monkeypatch):
    fundamentals, quant, factors, quality, risk, composite, signal = _engine_bundle()
    context = build_context(
        {
            "ticker": "TEST",
            "market": "US",
            "company": _company(),
            "fundamentals": fundamentals,
            "quant": quant,
            "factors": factors,
            "risk": risk,
            "composite": composite,
            "signal": signal,
            "data_quality": quality,
        }
    )

    def direct_order_report(*args, **kwargs):
        return (
            '{"report":{"summary":"무조건 매수하세요","signal_interpretation":{"label":"'
            + signal["signal_label"]
            + '"},"bull_case":[],"bear_case":[],"conflict_analysis":"","missing_data_warning":"","safety_note":""}}',
            "fake-llm",
            0.01,
        )

    monkeypatch.setattr(ai_service, "_call_local_llm", direct_order_report)
    report = ai_service.generate_report(context, use_llm=True)
    assert report["provider"] == "deterministic_interpreter"
    assert "llm_provider_failed_or_rejected_output" in report["warnings"]
    assert report["signal_label"] == signal["signal_label"]

    def direct_order_answer(*args, **kwargs):
        return '{"answer":"buy now","evidence_metrics":[],"caveats":[]}', "fake-llm", 0.01

    monkeypatch.setattr(qa_service, "_call_local_llm", direct_order_answer)
    answer = qa_service.answer_question("should I buy?", context, use_llm=True)
    assert answer["provider"] == "deterministic_qa"
    assert "llm_provider_failed_or_rejected_output" in answer["warnings"]
    assert answer["not_investment_advice"] is True


def test_ai_report_and_qa_fall_back_on_provider_failure_or_malformed_json(monkeypatch):
    fundamentals, quant, factors, quality, risk, composite, signal = _engine_bundle()
    context = build_context(
        {
            "ticker": "TEST",
            "market": "US",
            "company": _company(),
            "fundamentals": fundamentals,
            "quant": quant,
            "factors": factors,
            "risk": risk,
            "composite": composite,
            "signal": signal,
            "data_quality": quality,
        }
    )

    monkeypatch.setattr(ai_service, "_call_local_llm", lambda *args, **kwargs: ("not-json", "fake", 0.1))
    report = ai_service.generate_report(context, use_llm=True)
    assert report["provider"] == "deterministic_interpreter"
    assert "llm_provider_failed_or_rejected_output" in report["warnings"]
    assert report["signal_label"] == signal["signal_label"]

    monkeypatch.setattr(qa_service, "_call_local_llm", lambda *args, **kwargs: (_raise_runtime()))
    answer = qa_service.answer_question("what is the sell risk?", context, use_llm=True)
    assert answer["provider"] == "deterministic_qa"
    assert "llm_provider_failed_or_rejected_output" in answer["warnings"]
    assert answer["not_investment_advice"] is True


def _raise_runtime():
    raise RuntimeError("provider_down")
