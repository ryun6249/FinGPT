from __future__ import annotations

import sqlite3

from pipelines.data_mart.models import Filing, MacroObservation, NewsArticle, PriceBar
from pipelines.data_mart.storage import repository


def test_price_upsert_is_idempotent_and_keeps_runs_db_separate(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"
    repository.ensure_assets(["AAPL"], market="us", db_path=db_path)

    first = repository.upsert_prices(
        [
            PriceBar(
                ticker="AAPL",
                date="2026-05-01",
                open=100,
                high=110,
                low=99,
                close=108,
                adjusted_close=107.5,
                volume=12345,
                source="test",
            )
        ],
        db_path=db_path,
    )
    second = repository.upsert_prices(
        [
            PriceBar(
                ticker="AAPL",
                date="2026-05-01",
                open=101,
                high=111,
                low=100,
                close=109,
                adjusted_close=108.5,
                volume=54321,
                source="test",
            )
        ],
        db_path=db_path,
    )

    assert first == {"inserted": 1, "updated": 0}
    assert second == {"inserted": 0, "updated": 1}
    rows = repository.get_prices("AAPL", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["close"] == 109
    assert not (tmp_path / "runs.db").exists()


def test_macro_and_news_upserts_have_stable_keys(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    macro_result = repository.upsert_macro_observations(
        [
            MacroObservation(
                series_id="DGS10",
                date="2026-05-01",
                value=4.25,
                title="10-Year Treasury Constant Maturity Rate",
                units="percent",
            )
        ],
        db_path=db_path,
    )
    news_first = repository.upsert_news_articles(
        [
            NewsArticle(
                ticker="TLT",
                title="Treasury yields fall",
                url="https://example.com/tlt",
                source="Example",
                published_at="2026-05-01T12:00:00Z",
                summary="Long-duration bonds rose as yields fell.",
            )
        ],
        db_path=db_path,
    )
    news_second = repository.upsert_news_articles(
        [
            NewsArticle(
                ticker="TLT",
                title="Treasury yields fall",
                url="https://example.com/tlt",
                source="Example",
                published_at="2026-05-01T12:00:00Z",
                summary="Updated summary",
            )
        ],
        db_path=db_path,
    )

    assert macro_result == {"inserted": 1, "updated": 0}
    assert repository.latest_macro("DGS10", db_path=db_path)["value"] == 4.25
    assert news_first == {"inserted": 1, "updated": 0}
    assert news_second == {"inserted": 0, "updated": 1}


def test_filing_upsert_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    first = repository.upsert_filings(
        [Filing(ticker="MSFT", form_type="10-Q", filed_at="2026-04-25", url="https://sec.example/msft-10q")],
        db_path=db_path,
    )
    second = repository.upsert_filings(
        [Filing(ticker="MSFT", form_type="10-Q", filed_at="2026-04-25", url="https://sec.example/msft-10q")],
        db_path=db_path,
    )
    health = repository.data_health(db_path=db_path)

    assert first == {"inserted": 1, "updated": 0}
    assert second == {"inserted": 0, "updated": 1}
    assert health["table_counts"]["filings"] == 1


def test_sec_company_registry_and_facts_are_queryable(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    company_counts = repository.upsert_sec_company_registry(
        [{"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc.", "exchange": "Nasdaq"}],
        db_path=db_path,
    )
    filing_counts = repository.upsert_filings(
        [
            Filing(
                ticker="AAPL",
                cik="0000320193",
                accession_number="0000320193-26-000001",
                form_type="10-K",
                filed_at="2026-01-31",
                report_date="2025-12-31",
                fiscal_year=2025,
                fiscal_period="FY",
                primary_document="aapl-20251231.htm",
                description="10-K filing",
                url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/aapl-20251231.htm",
                filing_id="AAPL:0000320193-26-000001",
            )
        ],
        db_path=db_path,
    )
    fact_counts = repository.upsert_sec_financial_facts(
        [
            {
                "ticker": "AAPL",
                "cik": "0000320193",
                "taxonomy": "us-gaap",
                "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "label": "Revenue",
                "unit": "USD",
                "form_type": "10-K",
                "fiscal_year": 2025,
                "fiscal_period": "FY",
                "end_date": "2025-12-31",
                "filed_at": "2026-01-31",
                "accession_number": "0000320193-26-000001",
                "value": 390000000000,
            }
        ],
        db_path=db_path,
    )
    availability = repository.sec_data_availability(["AAPL", "MSFT"], db_path=db_path)
    registry_rows = repository.get_sec_company_registry(["AAPL", "MSFT"], db_path=db_path)
    filings = repository.latest_filings("AAPL", forms=["10-K"], db_path=db_path)
    facts = repository.latest_sec_financial_facts("AAPL", concepts=["RevenueFromContractWithCustomerExcludingAssessedTax"], db_path=db_path)
    health = repository.data_health(db_path=db_path)

    assert company_counts == {"inserted": 1, "updated": 0}
    assert filing_counts == {"inserted": 1, "updated": 0}
    assert fact_counts == {"inserted": 1, "updated": 0}
    assert availability["AAPL"]["available"] is True
    assert availability["AAPL"]["filing_count"] == 1
    assert availability["AAPL"]["fact_count"] == 1
    assert availability["MSFT"]["status"] == "missing"
    assert registry_rows == [
        {
            "ticker": "AAPL",
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "exchange": "Nasdaq",
            "source": "sec_company_tickers",
            "updated_at": registry_rows[0]["updated_at"],
        }
    ]
    assert filings[0]["accession_number"] == "0000320193-26-000001"
    assert facts[0]["value"] == 390000000000
    assert health["table_counts"]["sec_company_registry"] == 1
    assert health["table_counts"]["sec_financial_facts"] == 1


def test_update_run_provider_status_and_health(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"
    run_id = repository.start_update_run(market="us", provider="yfinance", db_path=db_path)
    repository.record_provider_status(
        run_id,
        provider="yfinance",
        status="ok",
        market="us",
        ticker="AAPL",
        rows_inserted=2,
        details={"source": "unit-test"},
        db_path=db_path,
    )
    repository.record_quality_check(
        run_id=run_id,
        check_name="coverage",
        status="pass",
        entity_type="ticker",
        entity_id="AAPL",
        message="AAPL has fresh prices.",
        db_path=db_path,
    )
    repository.finish_update_run(run_id, status="success", rows_inserted=2, db_path=db_path)

    health = repository.data_health(db_path=db_path)

    assert health["latest_run"]["status"] == "success"
    assert health["table_counts"]["provider_status"] == 1
    assert health["recent_provider_status"][0]["provider"] == "yfinance"
    assert health["recent_quality_checks"][0]["check_name"] == "coverage"


def test_provider_status_finished_index_supports_health_latest_rows(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"
    repository.data_health(db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        indexes = {
            row[1]
            for row in conn.execute("PRAGMA index_list(provider_status)").fetchall()
        }

    assert "idx_provider_status_finished" in indexes
