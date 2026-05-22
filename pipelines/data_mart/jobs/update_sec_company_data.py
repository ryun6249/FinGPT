from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Iterable

from core.config.settings import load_settings
from core.utils.symbol_registry import symbol_identities
from pipelines.data_mart.models import Filing, ProviderFetchResult, UpdateRunResult
from pipelines.data_mart.providers.sec_edgar_provider import (
    DEFAULT_CONCEPTS,
    DEFAULT_FORMS,
    fetch_sec_company_data,
    fetch_ticker_map,
)
from pipelines.data_mart.storage import repository

SecCompanyCollector = Callable[..., ProviderFetchResult]
_PLAIN_US_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")

SEC_FIELD_CONCEPTS: dict[str, tuple[str, ...]] = {
    "total_revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "trailing_eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic"),
    "total_assets": ("Assets",),
    "total_liabilities": ("Liabilities",),
    "stockholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "total_cash": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "total_debt": (
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtCurrent",
    ),
    "shares_outstanding": (
        "CommonStocksSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities", "OperatingCashFlow"),
    "capital_expenditures": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}


def _local_ticker_map_payload(tickers: list[str], *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    rows = repository.get_sec_company_registry(tickers, db_path=db_path)
    if not rows:
        return None
    return {
        "fields": ["ticker", "cik", "title", "exchange", "source"],
        "data": [
            [
                row.get("ticker") or "",
                row.get("cik") or "",
                row.get("company_name") or row.get("ticker") or "",
                row.get("exchange") or "",
                row.get("source") or "local_sec_company_registry",
            ]
            for row in rows
        ],
        "source": "local_sec_company_registry",
    }


def _clean_tickers(tickers: Iterable[str]) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            clean.append(ticker)
    return clean


def _is_sec_company_candidate(ticker: str) -> tuple[bool, str]:
    clean = str(ticker or "").upper().strip()
    if not clean or clean == "CASH":
        return False, "cash_or_empty"
    if clean.endswith((".KS", ".KQ")):
        return False, "non_us_exchange"
    if clean.endswith("-USD"):
        return False, "crypto_pair"
    identities = symbol_identities()
    identity = identities.get(clean)
    if identity is not None:
        market = str(getattr(identity, "market", "") or "").upper()
        asset_class = str(getattr(identity, "asset_class", "") or "").lower()
        if market == "US" and asset_class == "stock":
            return True, "us_stock_registry"
        return False, f"non_sec_company:{market or 'unknown'}:{asset_class or 'unknown'}"
    if _PLAIN_US_SYMBOL_RE.match(clean):
        return True, "plain_us_symbol"
    return False, "unsupported_symbol_shape"


def _latest_fact(facts: list[dict[str, Any]], concepts: Iterable[str]) -> dict[str, Any] | None:
    concept_set = set(concepts)
    candidates = [fact for fact in facts if str(fact.get("concept") or "") in concept_set and fact.get("value") is not None]
    candidates.sort(
        key=lambda item: (
            str(item.get("filed_at") or ""),
            str(item.get("end_date") or ""),
            1 if str(item.get("form_type") or "") == "10-Q" else 0,
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def _sec_snapshot_from_facts(ticker: str, company: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not facts:
        return None
    latest = sorted(facts, key=lambda item: (str(item.get("filed_at") or ""), str(item.get("end_date") or "")), reverse=True)[0]
    raw_latest: dict[str, Any] = {}
    for field, concepts in SEC_FIELD_CONCEPTS.items():
        fact = _latest_fact(facts, concepts)
        if fact:
            raw_latest[field] = fact
    values: dict[str, Any] = {
        "ticker": ticker,
        "as_of": latest.get("filed_at") or latest.get("end_date") or "",
        "source": "sec_companyfacts",
        "statement_type": f"sec_companyfacts:{latest.get('form_type') or 'unknown'}",
        "quote_type": "EQUITY",
        "name": company.get("company_name") or ticker,
        "exchange": company.get("exchange") or "",
        "raw_sec_latest_facts": raw_latest,
        "cik": company.get("cik") or "",
    }
    for field, fact in raw_latest.items():
        if field in {"operating_cash_flow", "capital_expenditures"}:
            continue
        values[field] = fact.get("value")
    operating_cash_flow = raw_latest.get("operating_cash_flow", {}).get("value")
    capital_expenditures = raw_latest.get("capital_expenditures", {}).get("value")
    if operating_cash_flow is not None and capital_expenditures is not None:
        try:
            values["free_cashflow"] = float(operating_cash_flow) - abs(float(capital_expenditures))
        except (TypeError, ValueError):
            pass
    return values


def update_sec_company_data(
    tickers: Iterable[str],
    *,
    forms: Iterable[str] = DEFAULT_FORMS,
    concepts: Iterable[str] = DEFAULT_CONCEPTS,
    lookback_days: int = 365 * 3,
    max_assets: int = 250,
    filing_limit_per_ticker: int = 40,
    max_facts_per_ticker: int = 500,
    hydrate_financials: bool = True,
    dry_run: bool = False,
    db_path: str | Path | None = None,
    collector: SecCompanyCollector = fetch_sec_company_data,
) -> UpdateRunResult:
    clean = _clean_tickers(tickers)[: max(1, int(max_assets or 1))]
    if dry_run:
        return UpdateRunResult(run_id="dry-run", status="dry_run", market="us", provider="sec_edgar")

    run_id = repository.start_update_run(market="us", provider="sec_edgar", db_path=db_path)
    settings = load_settings()
    sec_user_agent = getattr(settings, "sec_user_agent", "")
    request_delay_s = float(getattr(settings, "sec_request_delay_s", 0.12) or 0.12)
    ticker_map_status, ticker_payload = fetch_ticker_map(sec_user_agent)
    if ticker_map_status != "ok":
        fallback_payload = _local_ticker_map_payload(clean, db_path=db_path)
        if fallback_payload:
            ticker_payload = fallback_payload
            ticker_map_status = "ok"
        else:
            repository.record_provider_status(
                run_id,
                provider="sec_edgar",
                status=ticker_map_status,
                market="us",
                error_message=f"SEC ticker map returned status={ticker_map_status}.",
                details={"requested_tickers": clean},
                db_path=db_path,
            )
            repository.finish_update_run(
                run_id,
                status="failed",
                error_message=f"SEC ticker map returned status={ticker_map_status}.",
                db_path=db_path,
            )
            return UpdateRunResult(
                run_id=run_id,
                status="failed",
                market="us",
                provider="sec_edgar",
                error_message=f"SEC ticker map returned status={ticker_map_status}.",
            )

    if isinstance(ticker_payload, dict) and ticker_payload.get("source") == "local_sec_company_registry":
        repository.record_provider_status(
            run_id,
            provider="sec_edgar",
            status="partial",
            market="us",
            error_message=f"SEC ticker map unavailable; using local registry for {len(ticker_payload.get('data') or [])} ticker(s).",
            details={"requested_tickers": clean, "ticker_map_fallback": "local_sec_company_registry"},
            db_path=db_path,
        )

    companies: list[dict[str, Any]] = []
    filings: list[Filing] = []
    facts: list[dict[str, Any]] = []
    provider_results: list[ProviderFetchResult] = []
    skipped_count = 0

    for ticker in clean:
        eligible, reason = _is_sec_company_candidate(ticker)
        if not eligible:
            skipped_count += 1
            provider_results.append(
                ProviderFetchResult(
                    provider="sec_edgar",
                    status="skipped",
                    rows=0,
                    detail={"ticker": ticker, "reason": reason},
                )
            )
            continue
        try:
            result = collector(
                ticker,
                sec_user_agent=sec_user_agent,
                ticker_payload=ticker_payload,
                forms=forms,
                concepts=concepts,
                lookback_days=lookback_days,
                include_companyfacts=hydrate_financials,
                filing_limit=filing_limit_per_ticker,
                max_facts=max_facts_per_ticker,
                request_delay_s=request_delay_s,
            )
        except Exception as exc:  # noqa: BLE001
            result = ProviderFetchResult(
                provider="sec_edgar",
                status="failed",
                rows=0,
                error=str(exc),
                detail={"ticker": ticker},
            )
        provider_results.append(result)
        company = result.detail.get("company") if isinstance(result.detail, dict) else None
        ticker_facts = result.detail.get("facts") if isinstance(result.detail, dict) else None
        if isinstance(company, dict):
            companies.append(company)
        filings.extend([record for record in result.records if isinstance(record, Filing)])
        if isinstance(ticker_facts, list):
            facts.extend([fact for fact in ticker_facts if isinstance(fact, dict)])

    company_counts = repository.upsert_sec_company_registry(companies, db_path=db_path) if companies else {"inserted": 0, "updated": 0}
    filing_counts = repository.upsert_filings(filings, db_path=db_path) if filings else {"inserted": 0, "updated": 0}
    fact_counts = repository.upsert_sec_financial_facts(facts, db_path=db_path) if facts else {"inserted": 0, "updated": 0}
    snapshot_counts = {"inserted": 0, "updated": 0}
    if facts:
        facts_by_ticker: dict[str, list[dict[str, Any]]] = {}
        company_by_ticker = {str(company.get("ticker") or "").upper(): company for company in companies}
        for fact in facts:
            facts_by_ticker.setdefault(str(fact.get("ticker") or "").upper(), []).append(fact)
        for ticker, ticker_facts in facts_by_ticker.items():
            snapshot = _sec_snapshot_from_facts(ticker, company_by_ticker.get(ticker) or {}, ticker_facts)
            if not snapshot:
                continue
            counts = repository.upsert_fundamentals_card(snapshot, db_path=db_path)
            snapshot_counts["inserted"] += counts["inserted"]
            snapshot_counts["updated"] += counts["updated"]

    for result in provider_results:
        ticker = str(result.detail.get("ticker") or "") if isinstance(result.detail, dict) else ""
        repository.record_provider_status(
            run_id,
            provider=result.provider,
            status=result.status,
            market="us",
            ticker=ticker,
            rows_inserted=result.rows,
            error_message=result.error,
            details={
                **(result.detail if isinstance(result.detail, dict) else {}),
                "stored_company_counts": company_counts,
                "stored_filing_counts": filing_counts,
                "stored_fact_counts": fact_counts,
                "stored_snapshot_counts": snapshot_counts,
            },
            started_at=result.started_at,
            finished_at=result.finished_at,
            db_path=db_path,
        )

    failed = [result for result in provider_results if result.status in {"failed", "timeout", "rate_limited", "provider_unavailable"}]
    inserted = company_counts["inserted"] + filing_counts["inserted"] + fact_counts["inserted"] + snapshot_counts["inserted"]
    updated = company_counts["updated"] + filing_counts["updated"] + fact_counts["updated"] + snapshot_counts["updated"]
    if failed and not inserted and not updated:
        final_status = "failed"
    elif failed:
        final_status = "partial"
    else:
        final_status = "success"
    error = "; ".join(f"{result.detail.get('ticker')}: {result.error or result.status}" for result in failed[:20]) or None
    repository.finish_update_run(
        run_id,
        status=final_status,
        rows_inserted=inserted,
        rows_updated=updated,
        error_message=error,
        db_path=db_path,
    )
    return UpdateRunResult(
        run_id=run_id,
        status=final_status,
        market="us",
        provider="sec_edgar",
        rows_inserted=inserted,
        rows_updated=updated,
        error_message=error,
        providers=provider_results,
    )
