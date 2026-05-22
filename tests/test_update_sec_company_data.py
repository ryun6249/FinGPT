from __future__ import annotations

from types import SimpleNamespace

from pipelines.data_mart.jobs import update_sec_company_data as sec_job
from pipelines.data_mart.models import ProviderFetchResult
from pipelines.data_mart.storage import repository


def test_sec_update_uses_local_registry_when_sec_ticker_map_is_unavailable(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "research_mart.db"
    repository.upsert_sec_company_registry(
        [{"ticker": "AAPL", "cik": "0000320193", "company_name": "Apple Inc.", "exchange": "Nasdaq"}],
        db_path=db_path,
    )
    monkeypatch.setattr(sec_job, "fetch_ticker_map", lambda sec_user_agent: ("provider_unavailable", None))
    monkeypatch.setattr(
        sec_job,
        "load_settings",
        lambda: SimpleNamespace(sec_user_agent="test@example.com", sec_request_delay_s=0),
    )

    captured_sources: list[str] = []

    def fake_collector(ticker: str, **kwargs):
        payload = kwargs["ticker_payload"]
        captured_sources.append(str(payload.get("source") or ""))
        return ProviderFetchResult(
            provider="sec_edgar",
            status="ok",
            rows=1,
            detail={
                "ticker": ticker,
                "company": {
                    "ticker": ticker,
                    "cik": "0000320193",
                    "company_name": "Apple Inc.",
                    "exchange": "Nasdaq",
                    "source": "local_sec_company_registry",
                },
            },
        )

    result = sec_job.update_sec_company_data(
        ["AAPL"],
        db_path=db_path,
        collector=fake_collector,
    )
    health = repository.data_health(db_path=db_path)

    assert result.status == "success"
    assert captured_sources == ["local_sec_company_registry"]
    rows = health["recent_provider_status"]
    assert any(row["status"] == "ok" and row["ticker"] == "AAPL" for row in rows)
    fallback_rows = [row for row in rows if "ticker_map_fallback" in str(row.get("details_json") or "")]
    assert fallback_rows
    assert fallback_rows[0]["status"] == "partial"
