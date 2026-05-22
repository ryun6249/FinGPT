from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any, Iterable

import httpx

from pipelines.data_mart.models import Filing, ProviderFetchResult, utc_now_iso

TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
HTTP_TIMEOUT_S = 12.0
DEFAULT_FORMS = ("10-K", "10-Q", "8-K")
DEFAULT_CONCEPTS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "GrossProfit",
    "OperatingIncomeLoss",
    "NetIncomeLoss",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "CommonStocksIncludingAdditionalPaidInCapital",
    "CommonStocksSharesOutstanding",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "OperatingCashFlow",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
)


def _headers(sec_user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }


def _classify_response(response: httpx.Response) -> str:
    if response.status_code == 429:
        return "rate_limited"
    if response.status_code in (403, 451):
        return "provider_unavailable"
    if response.status_code >= 500:
        return "provider_unavailable"
    if response.status_code == 404:
        return "empty"
    if response.status_code != 200:
        return "provider_unavailable"
    return "ok"


def _fetch_json(url: str, sec_user_agent: str) -> tuple[str, Any]:
    try:
        response = httpx.get(url, headers=_headers(sec_user_agent), timeout=HTTP_TIMEOUT_S, follow_redirects=True)
    except httpx.TimeoutException:
        return "timeout", None
    except httpx.HTTPError as exc:
        return "provider_unavailable", str(exc)
    status = _classify_response(response)
    if status != "ok":
        return status, response.text
    try:
        return "ok", response.json()
    except ValueError:
        return "provider_unavailable", response.text


def fetch_ticker_map(sec_user_agent: str) -> tuple[str, Any]:
    return _fetch_json(TICKERS_URL, sec_user_agent)


def _ticker_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    fields = payload.get("fields")
    rows = payload.get("data")
    if isinstance(fields, list) and isinstance(rows, list):
        normalized: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            normalized.append({str(field): row[index] if index < len(row) else "" for index, field in enumerate(fields)})
        return normalized
    return [value for value in payload.values() if isinstance(value, dict)]


def lookup_company(payload: Any, symbol: str) -> dict[str, str] | None:
    symbol_upper = symbol.upper().strip()
    for row in _ticker_rows(payload):
        if str(row.get("ticker") or "").upper().strip() != symbol_upper:
            continue
        cik_raw = row.get("cik") or row.get("cik_str") or row.get("CIK")
        try:
            cik = f"{int(cik_raw):010d}"
        except (TypeError, ValueError):
            return None
        return {
            "ticker": symbol_upper,
            "cik": cik,
            "company_name": str(row.get("name") or row.get("title") or symbol_upper),
            "exchange": str(row.get("exchange") or ""),
            "source": str(row.get("source") or "sec_company_tickers"),
        }
    return None


def _safe_recent_value(recent: dict[str, Any], field: str, index: int) -> str:
    values = recent.get(field)
    if not isinstance(values, list) or index >= len(values):
        return ""
    value = values[index]
    return "" if value is None else str(value)


def _canonical_form(form: str) -> str:
    return str(form or "").upper().strip().split("/", 1)[0]


def _allowed_forms(forms: Iterable[str]) -> set[str]:
    return {_canonical_form(form) for form in forms if _canonical_form(form)}


def _date_cutoff(lookback_days: int | None) -> date | None:
    if not lookback_days or int(lookback_days) <= 0:
        return None
    return date.today() - timedelta(days=int(lookback_days))


def _date_in_lookback(value: str, cutoff: date | None) -> bool:
    if cutoff is None:
        return True
    try:
        parsed = date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return True
    return parsed >= cutoff


def _filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    accession_path = accession_number.replace("-", "")
    cik_path = str(int(cik))
    if not primary_document:
        return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}/{primary_document}"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _submission_filings(
    payload: Any,
    *,
    ticker: str,
    cik: str,
    forms: Iterable[str],
    lookback_days: int,
    limit: int,
) -> list[Filing]:
    if not isinstance(payload, dict):
        return []
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    accession_numbers = recent.get("accessionNumber")
    if not isinstance(accession_numbers, list):
        return []
    allowed = _allowed_forms(forms)
    cutoff = _date_cutoff(lookback_days)
    out: list[Filing] = []
    for index, accession in enumerate(accession_numbers):
        raw_form = _safe_recent_value(recent, "form", index)
        form_type = _canonical_form(raw_form)
        filing_date = _safe_recent_value(recent, "filingDate", index)
        if form_type not in allowed or not _date_in_lookback(filing_date, cutoff):
            continue
        primary_document = _safe_recent_value(recent, "primaryDocument", index)
        raw = {
            field: _safe_recent_value(recent, field, index)
            for field in (
                "accessionNumber",
                "filingDate",
                "reportDate",
                "acceptanceDateTime",
                "act",
                "form",
                "fileNumber",
                "filmNumber",
                "items",
                "size",
                "isXBRL",
                "isInlineXBRL",
                "primaryDocument",
                "primaryDocDescription",
            )
        }
        out.append(
            Filing(
                ticker=ticker,
                cik=cik,
                accession_number=str(accession or ""),
                form_type=form_type,
                filed_at=filing_date,
                report_date=_safe_recent_value(recent, "reportDate", index),
                fiscal_year=_int_or_none(_safe_recent_value(recent, "fy", index)),
                fiscal_period=_safe_recent_value(recent, "fp", index),
                primary_document=primary_document,
                description=_safe_recent_value(recent, "primaryDocDescription", index),
                url=_filing_url(cik, str(accession or ""), primary_document),
                source="sec_submissions",
                filing_id=f"{ticker}:{accession}",
                raw=raw,
            )
        )
        if len(out) >= limit:
            break
    return out


def _company_facts(
    payload: Any,
    *,
    ticker: str,
    cik: str,
    forms: Iterable[str],
    concepts: Iterable[str],
    lookback_days: int,
    max_facts: int,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    facts_root = payload.get("facts")
    if not isinstance(facts_root, dict):
        return []
    allowed = _allowed_forms(forms)
    requested = {str(concept or "").strip() for concept in concepts if str(concept or "").strip()}
    cutoff = _date_cutoff(lookback_days)
    out: list[dict[str, Any]] = []
    for taxonomy, taxonomy_facts in facts_root.items():
        if not isinstance(taxonomy_facts, dict):
            continue
        for concept, concept_payload in taxonomy_facts.items():
            if requested and concept not in requested:
                continue
            if not isinstance(concept_payload, dict):
                continue
            label = str(concept_payload.get("label") or "")
            units = concept_payload.get("units")
            if not isinstance(units, dict):
                continue
            for unit, records in units.items():
                if not isinstance(records, list):
                    continue
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    form_type = _canonical_form(str(record.get("form") or ""))
                    filed_at = str(record.get("filed") or "")
                    if form_type not in allowed or not _date_in_lookback(filed_at, cutoff):
                        continue
                    out.append(
                        {
                            "ticker": ticker,
                            "cik": cik,
                            "taxonomy": str(taxonomy),
                            "concept": str(concept),
                            "label": label,
                            "unit": str(unit),
                            "form_type": form_type,
                            "fiscal_year": _int_or_none(record.get("fy")),
                            "fiscal_period": str(record.get("fp") or ""),
                            "start_date": str(record.get("start") or ""),
                            "end_date": str(record.get("end") or ""),
                            "filed_at": filed_at,
                            "accession_number": str(record.get("accn") or ""),
                            "frame": str(record.get("frame") or ""),
                            "value": _float_or_none(record.get("val")),
                            "raw_value": record.get("val"),
                            "source": "sec_companyfacts",
                            "raw": record,
                        }
                    )
                    if len(out) >= max_facts:
                        return out
    out.sort(key=lambda item: (str(item.get("filed_at") or ""), str(item.get("end_date") or "")), reverse=True)
    return out[:max_facts]


def fetch_sec_company_data(
    ticker: str,
    *,
    sec_user_agent: str,
    ticker_payload: Any | None = None,
    forms: Iterable[str] = DEFAULT_FORMS,
    concepts: Iterable[str] = DEFAULT_CONCEPTS,
    lookback_days: int = 365 * 3,
    include_companyfacts: bool = True,
    filing_limit: int = 40,
    max_facts: int = 500,
    request_delay_s: float = 0.12,
) -> ProviderFetchResult:
    started = utc_now_iso()
    clean = str(ticker or "").upper().strip()
    if not clean:
        return ProviderFetchResult(provider="sec_edgar", status="empty", error="missing ticker", started_at=started, finished_at=utc_now_iso())
    if ticker_payload is None:
        ticker_status, ticker_payload = fetch_ticker_map(sec_user_agent)
        if ticker_status != "ok":
            return ProviderFetchResult(
                provider="sec_edgar",
                status=ticker_status,
                error=f"SEC ticker map returned status={ticker_status}.",
                detail={"ticker": clean},
                started_at=started,
                finished_at=utc_now_iso(),
            )
    company = lookup_company(ticker_payload, clean)
    if not company:
        return ProviderFetchResult(
            provider="sec_edgar",
            status="empty",
            error=None,
            detail={"ticker": clean, "reason": "ticker_not_found_in_sec_map"},
            started_at=started,
            finished_at=utc_now_iso(),
        )

    cik = company["cik"]
    submissions_status, submissions_payload = _fetch_json(SUBMISSIONS_URL.format(cik=cik), sec_user_agent)
    if request_delay_s > 0:
        time.sleep(float(request_delay_s))
    if submissions_status != "ok":
        return ProviderFetchResult(
            provider="sec_edgar",
            status=submissions_status,
            error=f"SEC submissions returned status={submissions_status}.",
            detail={"ticker": clean, "company": company},
            started_at=started,
            finished_at=utc_now_iso(),
        )

    filings = _submission_filings(
        submissions_payload,
        ticker=clean,
        cik=cik,
        forms=forms,
        lookback_days=lookback_days,
        limit=max(1, int(filing_limit or 1)),
    )
    facts: list[dict[str, Any]] = []
    facts_status = "skipped"
    facts_error = None
    if include_companyfacts:
        facts_status, facts_payload = _fetch_json(COMPANY_FACTS_URL.format(cik=cik), sec_user_agent)
        if request_delay_s > 0:
            time.sleep(float(request_delay_s))
        if facts_status == "ok":
            facts = _company_facts(
                facts_payload,
                ticker=clean,
                cik=cik,
                forms=forms,
                concepts=concepts,
                lookback_days=lookback_days,
                max_facts=max(1, int(max_facts or 1)),
            )
        else:
            facts_error = f"SEC companyfacts returned status={facts_status}."

    status = "ok" if filings or facts else "empty"
    if include_companyfacts and facts_status not in {"ok", "empty", "skipped"} and not facts and not filings:
        status = facts_status
    return ProviderFetchResult(
        provider="sec_edgar",
        status=status,
        rows=len(filings) + len(facts),
        records=filings,
        error=facts_error if status not in {"ok", "empty"} else None,
        detail={
            "ticker": clean,
            "company": company,
            "filing_count": len(filings),
            "fact_count": len(facts),
            "facts_status": facts_status,
            "facts": facts,
        },
        started_at=started,
        finished_at=utc_now_iso(),
    )
