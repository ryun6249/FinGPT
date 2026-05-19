from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

import httpx

from core.config.settings import load_settings
from pipelines.data_mart.jobs.update_sec_company_data import SEC_FIELD_CONCEPTS
from pipelines.data_mart.storage import repository
from pipelines.quantamental.fundamental_engine import safe_divide
from pipelines.quantamental.global_market import global_sec_lookup_candidates, known_global_sec_aliases


DEFAULT_FORMS = ("10-K", "10-Q", "8-K", "20-F", "6-K")
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
GLOBAL_SEC_TICKER_ALIASES = known_global_sec_aliases()


def build_sec_evidence(
    ticker: str,
    *,
    market: str = "US",
    db_path: str | None = None,
    include_filing_text: bool = False,
    filing_text_timeout_s: float = 5.0,
) -> dict[str, Any]:
    clean = str(ticker or "").upper().strip()
    market_clean = str(market or "US").upper()
    sec_tickers = _sec_lookup_tickers(clean, market_clean)
    if not sec_tickers:
        warning = "sec_evidence_us_only" if market_clean != "GLOBAL" else "sec_evidence_global_no_sec_alias"
        return _skipped_payload(clean, market_clean, [warning])
    try:
        sec_ticker, filings, facts = _load_sec_store(sec_tickers, db_path=db_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "unavailable",
            "ticker": clean,
            "market": market_clean,
            "source": "sec_edgar",
            "warnings": ["sec_evidence_store_unavailable"],
            "errors": [f"sec_evidence_store_error:{type(exc).__name__}:{exc}"],
            "risk_flags": [],
            "quality_flags": [],
        }
    global_fallback_warning = []
    if market_clean == "GLOBAL":
        if sec_ticker and sec_ticker != clean:
            global_fallback_warning.append(f"sec_evidence_global_adr_fallback:{sec_ticker}")
        if not filings and not facts:
            return {
                "status": "missing",
                "ticker": clean,
                "market": market_clean,
                "sec_ticker": sec_ticker,
                "source": "sec_edgar",
                "filing_count": 0,
                "fact_count": 0,
                "warnings": [*global_fallback_warning, "sec_evidence_global_adr_data_missing"],
                "risk_flags": [],
                "quality_flags": [],
                "filing_excerpts": [],
                "sample_filings": [],
                "concept_provenance": [],
            }

    metrics = _metrics_from_facts(facts)
    risk_flags: list[str] = []
    quality_flags: list[str] = []
    warnings: list[str] = [*global_fallback_warning]
    if not filings:
        warnings.append("sec_filings_missing")
    if not facts:
        warnings.append("sec_companyfacts_missing")
    latest_filing_at = str(filings[0].get("filed_at") or "") if filings else ""
    stale_days = _days_since(latest_filing_at)
    if stale_days is not None and stale_days > 455:
        risk_flags.append("sec_latest_filing_stale")
    leverage = safe_divide(metrics.get("total_liabilities"), metrics.get("total_assets"))
    if leverage is not None and leverage > 0.85:
        risk_flags.append("sec_high_liabilities_to_assets")
    ocf_to_income = safe_divide(metrics.get("operating_cash_flow"), metrics.get("net_income"))
    if metrics.get("operating_cash_flow") is not None and float(metrics.get("operating_cash_flow") or 0.0) < 0:
        risk_flags.append("sec_negative_operating_cash_flow")
    if ocf_to_income is not None and ocf_to_income < 0.5:
        quality_flags.append("sec_low_cash_conversion")
    if facts:
        quality_flags.append("sec_companyfacts_available")
    if filings:
        quality_flags.append("sec_recent_filings_available")

    status = "ok" if filings and facts else ("partial" if filings or facts else "missing")
    return {
        "status": status,
        "ticker": clean,
        "market": market_clean,
        "sec_ticker": sec_ticker,
        "source": "sec_edgar",
        "latest_filing_at": latest_filing_at,
        "latest_fact_filed_at": _latest_value(facts, "filed_at"),
        "filing_count": len(filings),
        "fact_count": len(facts),
        "forms": sorted({str(item.get("form_type") or "") for item in filings if item.get("form_type")}),
        "metrics": {
            **metrics,
            "liabilities_to_assets": leverage,
            "ocf_to_net_income": ocf_to_income,
        },
        "concept_provenance": _concept_provenance(facts),
        "risk_flags": risk_flags,
        "quality_flags": quality_flags,
        "warnings": warnings,
        "filing_excerpts": _filing_excerpts(
            filings,
            include_filing_text=include_filing_text,
            timeout_s=filing_text_timeout_s,
        ),
        "sample_filings": [
            {
                "form_type": item.get("form_type"),
                "filed_at": item.get("filed_at"),
                "report_date": item.get("report_date"),
                "description": item.get("description"),
                "primary_document": item.get("primary_document"),
                "url": item.get("url"),
            }
            for item in filings[:3]
        ],
    }


def _skipped_payload(ticker: str, market: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "status": "skipped",
        "ticker": ticker,
        "market": market,
        "source": "sec_edgar",
        "warnings": warnings,
        "risk_flags": [],
        "quality_flags": [],
        "filing_count": 0,
        "fact_count": 0,
    }


def _sec_lookup_tickers(ticker: str, market: str) -> list[str]:
    clean = str(ticker or "").upper().strip()
    if market == "US":
        return [clean]
    if market != "GLOBAL":
        return []
    return global_sec_lookup_candidates(clean)


def _load_sec_store(sec_tickers: list[str], *, db_path: str | None = None) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    selected = sec_tickers[0] if sec_tickers else ""
    selected_filings: list[dict[str, Any]] = []
    selected_facts: list[dict[str, Any]] = []
    for candidate in sec_tickers:
        filings = repository.latest_filings(candidate, forms=DEFAULT_FORMS, limit=6, db_path=db_path)
        facts = repository.latest_sec_financial_facts(candidate, concepts=_all_sec_concepts(), limit=120, db_path=db_path)
        if filings or facts:
            return candidate, filings, facts
    return selected, selected_filings, selected_facts


def apply_sec_evidence_to_risk(risk_payload: dict[str, Any], sec_evidence: dict[str, Any]) -> dict[str, Any]:
    payload = dict(risk_payload or {})
    existing_flags = [str(item) for item in payload.get("risk_flags") or []]
    sec_flags = [str(item) for item in sec_evidence.get("risk_flags") or []]
    merged_flags = []
    for item in [*existing_flags, *sec_flags]:
        if item and item not in merged_flags:
            merged_flags.append(item)
    score = payload.get("risk_score")
    if score is not None and sec_flags:
        penalty = min(15.0, 5.0 * len(sec_flags))
        try:
            payload["risk_score"] = round(max(0.0, float(score) - penalty), 2)
        except (TypeError, ValueError):
            pass
    payload["risk_flags"] = merged_flags
    payload["sec_evidence"] = sec_evidence
    if sec_flags:
        summary = payload.get("risk_summary") or ""
        payload["risk_summary"] = (summary + "; SEC evidence flags: " + ", ".join(sec_flags)).strip("; ")
    return payload


def _all_sec_concepts() -> list[str]:
    out: list[str] = []
    for concepts in SEC_FIELD_CONCEPTS.values():
        for concept in concepts:
            if concept not in out:
                out.append(concept)
    return out


def _metrics_from_facts(facts: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for field, concepts in SEC_FIELD_CONCEPTS.items():
        fact = _latest_fact(facts, concepts)
        if fact and fact.get("value") is not None:
            metrics[field] = fact.get("value")
    if metrics.get("operating_cash_flow") is not None and metrics.get("capital_expenditures") is not None:
        try:
            metrics["free_cash_flow"] = float(metrics["operating_cash_flow"]) - abs(float(metrics["capital_expenditures"]))
        except (TypeError, ValueError):
            pass
    return metrics


def _concept_provenance(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    for field, concepts in SEC_FIELD_CONCEPTS.items():
        fact = _latest_fact(facts, concepts)
        if not fact:
            continue
        provenance.append(
            {
                "field": field,
                "taxonomy": fact.get("taxonomy"),
                "concept": fact.get("concept"),
                "label": fact.get("label"),
                "unit": fact.get("unit"),
                "form_type": fact.get("form_type"),
                "fiscal_year": fact.get("fiscal_year"),
                "fiscal_period": fact.get("fiscal_period"),
                "end_date": fact.get("end_date"),
                "filed_at": fact.get("filed_at"),
                "accession_number": fact.get("accession_number"),
                "value": fact.get("value"),
                "source": fact.get("source") or "sec_companyfacts",
            }
        )
    return provenance


def _filing_excerpts(
    filings: list[dict[str, Any]],
    *,
    include_filing_text: bool = False,
    timeout_s: float = 5.0,
) -> list[dict[str, Any]]:
    excerpts: list[dict[str, Any]] = []
    for item in filings[:5]:
        form_type = str(item.get("form_type") or "").upper()
        description = str(item.get("description") or item.get("primary_document") or form_type or "SEC filing").strip()
        excerpt = _risk_excerpt_for_form(form_type, description)
        source = "filing_metadata_description"
        text_payload: dict[str, Any] = {}
        if include_filing_text:
            text_payload = _fetch_filing_text_excerpt(item, timeout_s=timeout_s)
            if text_payload.get("excerpt"):
                excerpt = str(text_payload.get("excerpt") or "")
                source = str(text_payload.get("source") or "sec_filing_text")
        excerpts.append(
            {
                "form_type": form_type,
                "filed_at": item.get("filed_at"),
                "report_date": item.get("report_date"),
                "description": description,
                "excerpt": excerpt,
                "source": source,
                "section": text_payload.get("section"),
                "text_warning": text_payload.get("warning"),
                "url": item.get("url"),
            }
        )
    return excerpts


def _risk_excerpt_for_form(form_type: str, description: str) -> str:
    if form_type == "10-K":
        return f"{description}: annual filing; review Item 1A risk factors and MD&A before relying on the score."
    if form_type == "10-Q":
        return f"{description}: quarterly filing; compare updated risk factors, liquidity, and interim trends."
    if form_type == "8-K":
        return f"{description}: current report; inspect event-specific disclosure for material changes."
    if form_type == "20-F":
        return f"{description}: annual foreign private issuer filing; review risk factors, operating review, and liquidity disclosures."
    if form_type == "6-K":
        return f"{description}: foreign issuer current report; inspect event-specific disclosure for material changes."
    return f"{description}: SEC filing metadata available; inspect source filing for full text."


def _fetch_filing_text_excerpt(item: dict[str, Any], *, timeout_s: float = 5.0) -> dict[str, Any]:
    url = _filing_text_url(item)
    if not url:
        return {"warning": "filing_text_url_missing"}
    try:
        settings = load_settings()
        response = httpx.get(
            url,
            headers={"User-Agent": getattr(settings, "sec_user_agent", "FinGPTLocalResearch/1.0 contact@example.com")},
            timeout=max(1.0, min(15.0, float(timeout_s or 5.0))),
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return {"warning": f"filing_text_fetch_failed:{type(exc).__name__}"}
    clean_text = _clean_filing_text(response.text or "")
    if not clean_text:
        return {"warning": "filing_text_empty"}
    section, excerpt = _extract_risk_section_excerpt(clean_text)
    return {
        "source": "sec_filing_text",
        "section": section,
        "excerpt": excerpt or clean_text[:800],
        "url": url,
    }


def _filing_text_url(item: dict[str, Any]) -> str:
    direct = str(item.get("url") or "").strip()
    if direct:
        return direct
    cik = re.sub(r"\D", "", str(item.get("cik") or "")).lstrip("0")
    accession = re.sub(r"[^0-9]", "", str(item.get("accession_number") or ""))
    document = str(item.get("primary_document") or "").strip()
    if not cik or not accession or not document:
        return ""
    return SEC_ARCHIVES_URL.format(cik=cik, accession=accession, document=document)


def _clean_filing_text(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw or "")
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_risk_section_excerpt(text: str) -> tuple[str, str]:
    patterns = [
        ("Item 1A Risk Factors", r"(?is)\bItem\s+1A\.?\s+Risk Factors\b(.{0,1800})"),
        ("Risk Factors", r"(?is)\bRisk Factors\b(.{0,1800})"),
        ("Forward-Looking Statements", r"(?is)\bForward[- ]Looking Statements\b(.{0,1800})"),
    ]
    for section, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            excerpt = re.sub(r"\s+", " ", match.group(0)).strip()
            return section, excerpt[:900]
    return "filing_text_excerpt", text[:800]


def _latest_fact(facts: list[dict[str, Any]], concepts: tuple[str, ...]) -> dict[str, Any] | None:
    concept_set = set(concepts)
    candidates = [fact for fact in facts if str(fact.get("concept") or "") in concept_set and fact.get("value") is not None]
    candidates.sort(key=lambda item: (str(item.get("filed_at") or ""), str(item.get("end_date") or "")), reverse=True)
    return candidates[0] if candidates else None


def _latest_value(rows: list[dict[str, Any]], key: str) -> str:
    values = sorted([str(row.get(key) or "") for row in rows if row.get(key)], reverse=True)
    return values[0] if values else ""


def _days_since(value: str) -> int | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return (date.today() - parsed).days
