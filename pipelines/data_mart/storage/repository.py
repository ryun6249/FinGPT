from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from core.schemas.fingpt import FinGPTAnnotation
from pipelines.data_mart.models import Filing, MacroObservation, NewsArticle, PriceBar, utc_now_iso
from pipelines.data_mart.storage.db import connect, init_db


def _conn(db_path: str | Path | None = None) -> sqlite3.Connection:
    init_db(db_path)
    return connect(db_path)


def _asset_id(ticker: str) -> str:
    return ticker.upper().strip()


def _decode_annotation_metadata(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw": raw}
    return parsed if isinstance(parsed, dict) else {"raw": raw}


def _bounded_annotation_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 100
    return min(1000, max(1, parsed))


def _annotation_row_to_dict(row: sqlite3.Row | tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip(columns, row))


def ensure_assets(
    tickers: Iterable[str],
    *,
    market: str = "",
    asset_class: str = "",
    source: str = "watchlist",
    db_path: str | Path | None = None,
) -> None:
    now = utc_now_iso()
    with _conn(db_path) as conn:
        for raw in tickers:
            ticker = str(raw or "").upper().strip()
            if not ticker:
                continue
            conn.execute(
                """
                INSERT INTO assets(asset_id, ticker, market, asset_class, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    market=COALESCE(NULLIF(excluded.market, ''), assets.market),
                    asset_class=COALESCE(NULLIF(excluded.asset_class, ''), assets.asset_class),
                    updated_at=excluded.updated_at
                """,
                (_asset_id(ticker), ticker, market, asset_class, source, now, now),
            )
        conn.commit()


def upsert_asset_metadata(
    metadata: Iterable[dict[str, Any]],
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Persist normalized asset metadata used by UI filters and policy checks."""

    inserted = 0
    updated = 0
    now = utc_now_iso()
    with _conn(db_path) as conn:
        for item in metadata:
            ticker = str(item.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            existing = conn.execute("SELECT 1 FROM asset_metadata WHERE ticker=?", (ticker,)).fetchone()
            conn.execute(
                """
                INSERT INTO asset_metadata(
                    ticker, name, asset_class, quote_type, market, currency, exchange,
                    sector, industry, country, active, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=COALESCE(NULLIF(excluded.name, ''), asset_metadata.name),
                    asset_class=COALESCE(NULLIF(excluded.asset_class, ''), asset_metadata.asset_class),
                    quote_type=COALESCE(NULLIF(excluded.quote_type, ''), asset_metadata.quote_type),
                    market=COALESCE(NULLIF(excluded.market, ''), asset_metadata.market),
                    currency=COALESCE(NULLIF(excluded.currency, ''), asset_metadata.currency),
                    exchange=COALESCE(NULLIF(excluded.exchange, ''), asset_metadata.exchange),
                    sector=COALESCE(NULLIF(excluded.sector, ''), asset_metadata.sector),
                    industry=COALESCE(NULLIF(excluded.industry, ''), asset_metadata.industry),
                    country=COALESCE(NULLIF(excluded.country, ''), asset_metadata.country),
                    active=excluded.active,
                    source=COALESCE(NULLIF(excluded.source, ''), asset_metadata.source),
                    updated_at=excluded.updated_at
                """,
                (
                    ticker,
                    item.get("name") or "",
                    item.get("asset_class") or "",
                    item.get("quote_type") or "",
                    item.get("market") or "",
                    item.get("currency") or "",
                    item.get("exchange") or "",
                    item.get("sector") or "",
                    item.get("industry") or "",
                    item.get("country") or "",
                    1 if item.get("active", True) else 0,
                    item.get("source") or "provider",
                    now,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def upsert_universe_metadata(
    metadata: Iterable[dict[str, Any]],
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    """Persist normalized universe metadata for AI Portfolio policy checks.

    This is intentionally provider-light: it stores deterministic metadata from
    the local universe registry, then richer provider fundamentals can overwrite
    missing fields later through upsert_fundamentals_card.
    """

    now = utc_now_iso()
    counts = {
        "assets": 0,
        "asset_metadata": 0,
        "asset_identity": 0,
        "asset_classification": 0,
        "etf_exposure": 0,
        "kr_equity_profile": 0,
        "crypto_profile": 0,
    }
    with _conn(db_path) as conn:
        for item in metadata:
            ticker = str(item.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            name = str(item.get("name") or ticker).strip()
            asset_class = str(item.get("asset_class") or "").lower().strip()
            quote_type = str(item.get("quote_type") or "").upper().strip()
            market = str(item.get("market") or item.get("exchange") or "").upper().strip()
            exchange = str(item.get("exchange") or market).upper().strip()
            country = str(item.get("country") or ("KR" if ticker.endswith((".KS", ".KQ")) or market == "KRX" else "US")).upper()
            currency = str(item.get("currency") or ("KRW" if country == "KR" else "USD")).upper()
            sector = str(item.get("sector") or "").strip()
            industry = str(item.get("industry") or "").strip()
            source = str(item.get("source") or "universe").strip() or "universe"
            active = 1 if item.get("active", True) else 0
            local_symbol = str(item.get("local_symbol") or ticker.split(".", 1)[0]).upper().strip()

            conn.execute(
                """
                INSERT INTO assets(asset_id, ticker, name, market, asset_class, currency, exchange, source, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=COALESCE(NULLIF(excluded.name, ''), assets.name),
                    market=COALESCE(NULLIF(excluded.market, ''), assets.market),
                    asset_class=COALESCE(NULLIF(excluded.asset_class, ''), assets.asset_class),
                    currency=COALESCE(NULLIF(excluded.currency, ''), assets.currency),
                    exchange=COALESCE(NULLIF(excluded.exchange, ''), assets.exchange),
                    source=excluded.source,
                    active=excluded.active,
                    updated_at=excluded.updated_at
                """,
                (_asset_id(ticker), ticker, name, market, asset_class, currency, exchange, source, active, now, now),
            )
            counts["assets"] += 1

            conn.execute(
                """
                INSERT INTO asset_metadata(
                    ticker, name, asset_class, quote_type, market, currency, exchange,
                    sector, industry, country, active, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=COALESCE(NULLIF(excluded.name, ''), asset_metadata.name),
                    asset_class=COALESCE(NULLIF(excluded.asset_class, ''), asset_metadata.asset_class),
                    quote_type=COALESCE(NULLIF(excluded.quote_type, ''), asset_metadata.quote_type),
                    market=COALESCE(NULLIF(excluded.market, ''), asset_metadata.market),
                    currency=COALESCE(NULLIF(excluded.currency, ''), asset_metadata.currency),
                    exchange=COALESCE(NULLIF(excluded.exchange, ''), asset_metadata.exchange),
                    sector=COALESCE(NULLIF(excluded.sector, ''), asset_metadata.sector),
                    industry=COALESCE(NULLIF(excluded.industry, ''), asset_metadata.industry),
                    country=COALESCE(NULLIF(excluded.country, ''), asset_metadata.country),
                    active=excluded.active,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (ticker, name, asset_class, quote_type, market, currency, exchange, sector, industry, country, active, source, now),
            )
            counts["asset_metadata"] += 1

            conn.execute(
                """
                INSERT INTO asset_identity(ticker, name, local_symbol, exchange, currency, country, active, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=COALESCE(NULLIF(excluded.name, ''), asset_identity.name),
                    local_symbol=COALESCE(NULLIF(excluded.local_symbol, ''), asset_identity.local_symbol),
                    exchange=COALESCE(NULLIF(excluded.exchange, ''), asset_identity.exchange),
                    currency=COALESCE(NULLIF(excluded.currency, ''), asset_identity.currency),
                    country=COALESCE(NULLIF(excluded.country, ''), asset_identity.country),
                    active=excluded.active,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (ticker, name, local_symbol, exchange, currency, country, active, source, now),
            )
            counts["asset_identity"] += 1

            conn.execute(
                """
                INSERT INTO asset_classification(ticker, asset_class, sector, industry, country, theme, etf_category, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    asset_class=COALESCE(NULLIF(excluded.asset_class, ''), asset_classification.asset_class),
                    sector=COALESCE(NULLIF(excluded.sector, ''), asset_classification.sector),
                    industry=COALESCE(NULLIF(excluded.industry, ''), asset_classification.industry),
                    country=COALESCE(NULLIF(excluded.country, ''), asset_classification.country),
                    theme=COALESCE(NULLIF(excluded.theme, ''), asset_classification.theme),
                    etf_category=COALESCE(NULLIF(excluded.etf_category, ''), asset_classification.etf_category),
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (
                    ticker,
                    asset_class,
                    sector,
                    industry,
                    country,
                    str(item.get("theme") or "").strip(),
                    str(item.get("etf_category") or sector or "").strip(),
                    source,
                    now,
                ),
            )
            counts["asset_classification"] += 1

            is_etf = asset_class == "etf" or quote_type == "ETF" or "ETF" in market
            if is_etf:
                category = str(item.get("etf_category") or sector or "ETF").strip() or "ETF"
                conn.execute(
                    """
                    INSERT INTO etf_exposure(ticker, exposure_type, exposure_name, exposure_weight, source, updated_at)
                    VALUES (?, 'category', ?, NULL, ?, ?)
                    ON CONFLICT(ticker, exposure_type, exposure_name, source) DO UPDATE SET
                        updated_at=excluded.updated_at
                    """,
                    (ticker, category, source, now),
                )
                counts["etf_exposure"] += 1

            if ticker.endswith((".KS", ".KQ")) or market == "KRX" or country == "KR":
                conn.execute(
                    """
                    INSERT INTO kr_equity_profile(ticker, korean_name, market, sector, industry, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        korean_name=COALESCE(NULLIF(excluded.korean_name, ''), kr_equity_profile.korean_name),
                        market=COALESCE(NULLIF(excluded.market, ''), kr_equity_profile.market),
                        sector=COALESCE(NULLIF(excluded.sector, ''), kr_equity_profile.sector),
                        industry=COALESCE(NULLIF(excluded.industry, ''), kr_equity_profile.industry),
                        source=excluded.source,
                        updated_at=excluded.updated_at
                    """,
                    (ticker, name, market or "KRX", sector, industry, source, now),
                )
                counts["kr_equity_profile"] += 1

            if asset_class == "crypto" or ticker.endswith("-USD"):
                conn.execute(
                    """
                    INSERT INTO crypto_profile(ticker, symbol, category, quote_currency, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        symbol=COALESCE(NULLIF(excluded.symbol, ''), crypto_profile.symbol),
                        category=COALESCE(NULLIF(excluded.category, ''), crypto_profile.category),
                        quote_currency=COALESCE(NULLIF(excluded.quote_currency, ''), crypto_profile.quote_currency),
                        source=excluded.source,
                        updated_at=excluded.updated_at
                    """,
                    (ticker, ticker.split("-", 1)[0], str(item.get("category") or "crypto").strip(), currency, source, now),
                )
                counts["crypto_profile"] += 1
        conn.commit()
    return counts


def upsert_sec_company_registry(
    companies: Iterable[dict[str, Any]],
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    now = utc_now_iso()
    with _conn(db_path) as conn:
        for item in companies:
            ticker = str(item.get("ticker") or "").upper().strip()
            cik = str(item.get("cik") or "").strip()
            if not ticker or not cik:
                continue
            existing = conn.execute("SELECT 1 FROM sec_company_registry WHERE ticker=?", (ticker,)).fetchone()
            conn.execute(
                """
                INSERT INTO sec_company_registry(ticker, cik, company_name, exchange, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    cik=excluded.cik,
                    company_name=COALESCE(NULLIF(excluded.company_name, ''), sec_company_registry.company_name),
                    exchange=COALESCE(NULLIF(excluded.exchange, ''), sec_company_registry.exchange),
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (
                    ticker,
                    cik,
                    item.get("company_name") or item.get("name") or "",
                    item.get("exchange") or "",
                    item.get("source") or "sec_company_tickers",
                    now,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def _sec_fact_id(item: dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(item.get("ticker") or "").upper().strip(),
            str(item.get("taxonomy") or ""),
            str(item.get("concept") or ""),
            str(item.get("unit") or ""),
            str(item.get("form_type") or ""),
            str(item.get("fiscal_year") or ""),
            str(item.get("fiscal_period") or ""),
            str(item.get("end_date") or ""),
            str(item.get("filed_at") or ""),
            str(item.get("accession_number") or ""),
            str(item.get("frame") or ""),
        ]
    )
    return hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:32]


def upsert_sec_financial_facts(
    facts: Iterable[dict[str, Any]],
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    collected_at = utc_now_iso()
    with _conn(db_path) as conn:
        for item in facts:
            ticker = str(item.get("ticker") or "").upper().strip()
            cik = str(item.get("cik") or "").strip()
            concept = str(item.get("concept") or "").strip()
            unit = str(item.get("unit") or "").strip()
            form_type = str(item.get("form_type") or "").upper().strip()
            if not ticker or not cik or not concept or not unit or not form_type:
                continue
            fact_id = str(item.get("fact_id") or _sec_fact_id(item))
            existing = conn.execute("SELECT 1 FROM sec_financial_facts WHERE fact_id=?", (fact_id,)).fetchone()
            raw_json = json.dumps(item.get("raw") or item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            conn.execute(
                """
                INSERT INTO sec_financial_facts(
                    fact_id, ticker, cik, taxonomy, concept, label, unit, form_type,
                    fiscal_year, fiscal_period, start_date, end_date, filed_at,
                    accession_number, frame, value, raw_value, source, collected_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fact_id) DO UPDATE SET
                    ticker=excluded.ticker,
                    cik=excluded.cik,
                    taxonomy=excluded.taxonomy,
                    concept=excluded.concept,
                    label=excluded.label,
                    unit=excluded.unit,
                    form_type=excluded.form_type,
                    fiscal_year=excluded.fiscal_year,
                    fiscal_period=excluded.fiscal_period,
                    start_date=excluded.start_date,
                    end_date=excluded.end_date,
                    filed_at=excluded.filed_at,
                    accession_number=excluded.accession_number,
                    frame=excluded.frame,
                    value=excluded.value,
                    raw_value=excluded.raw_value,
                    source=excluded.source,
                    collected_at=excluded.collected_at,
                    raw_json=excluded.raw_json
                """,
                (
                    fact_id,
                    ticker,
                    cik,
                    item.get("taxonomy") or "us-gaap",
                    concept,
                    item.get("label") or "",
                    unit,
                    form_type,
                    item.get("fiscal_year"),
                    item.get("fiscal_period") or "",
                    item.get("start_date") or "",
                    item.get("end_date") or "",
                    item.get("filed_at") or "",
                    item.get("accession_number") or "",
                    item.get("frame") or "",
                    item.get("value"),
                    str(item.get("raw_value") if item.get("raw_value") is not None else item.get("value") or ""),
                    item.get("source") or "sec_companyfacts",
                    collected_at,
                    raw_json,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def upsert_fundamentals_card(card: Any, *, db_path: str | Path | None = None) -> dict[str, int]:
    """Store a provider-backed fundamentals card in normalized data-mart tables.

    The card is a point-in-time provider snapshot, not a full audited financial
    statement. Keeping the tables normalized lets the UI and report layer use
    deterministic numeric evidence without asking the LLM to invent fields.
    """

    raw = card.model_dump(exclude_none=True) if hasattr(card, "model_dump") else dict(card or {})
    ticker = str(raw.get("ticker") or getattr(card, "ticker", "") or "").upper().strip()
    as_of = str(raw.get("as_of") or getattr(card, "as_of", "") or "").strip()
    source = str(raw.get("source") or getattr(card, "source", "") or "yfinance").strip() or "yfinance"
    if not ticker or not as_of:
        return {"inserted": 0, "updated": 0}
    collected_at = utc_now_iso()
    inserted = 0
    updated = 0
    with _conn(db_path) as conn:
        snapshot_exists = conn.execute(
            "SELECT 1 FROM fundamentals_snapshots WHERE ticker=? AND as_of=? AND source=?",
            (ticker, as_of, source),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO fundamentals_snapshots(
                ticker, as_of, source, asset_class, quote_type, currency, exchange_name,
                name, sector, industry, raw_json, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, as_of, source) DO UPDATE SET
                asset_class=excluded.asset_class,
                quote_type=excluded.quote_type,
                currency=excluded.currency,
                exchange_name=excluded.exchange_name,
                name=excluded.name,
                sector=excluded.sector,
                industry=excluded.industry,
                raw_json=excluded.raw_json,
                collected_at=excluded.collected_at
            """,
            (
                ticker,
                as_of,
                source,
                raw.get("asset_class") or "",
                raw.get("quote_type") or "",
                raw.get("currency") or "",
                raw.get("exchange") or "",
                raw.get("name") or "",
                raw.get("sector") or "",
                raw.get("industry") or "",
                json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                collected_at,
            ),
        )
        inserted += 0 if snapshot_exists else 1
        updated += 1 if snapshot_exists else 0

        conn.execute(
            """
            INSERT INTO valuation_metrics(
                ticker, as_of, source, price, market_cap, enterprise_value, week52_high,
                week52_low, trailing_pe, forward_pe, price_to_book, dividend_yield,
                yield_value, beta, analyst_rating_mean, analyst_target_mean,
                num_analysts, shares_outstanding, average_volume, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, as_of, source) DO UPDATE SET
                price=excluded.price,
                market_cap=excluded.market_cap,
                enterprise_value=excluded.enterprise_value,
                week52_high=excluded.week52_high,
                week52_low=excluded.week52_low,
                trailing_pe=excluded.trailing_pe,
                forward_pe=excluded.forward_pe,
                price_to_book=excluded.price_to_book,
                dividend_yield=excluded.dividend_yield,
                yield_value=excluded.yield_value,
                beta=excluded.beta,
                analyst_rating_mean=excluded.analyst_rating_mean,
                analyst_target_mean=excluded.analyst_target_mean,
                num_analysts=excluded.num_analysts,
                shares_outstanding=excluded.shares_outstanding,
                average_volume=excluded.average_volume,
                collected_at=excluded.collected_at
            """,
            (
                ticker,
                as_of,
                source,
                raw.get("price"),
                raw.get("market_cap"),
                raw.get("enterprise_value"),
                raw.get("week52_high"),
                raw.get("week52_low"),
                raw.get("trailing_pe"),
                raw.get("forward_pe"),
                raw.get("price_to_book"),
                raw.get("dividend_yield"),
                raw.get("yield_value"),
                raw.get("beta"),
                raw.get("analyst_rating_mean"),
                raw.get("analyst_target_mean"),
                raw.get("num_analysts"),
                raw.get("shares_outstanding"),
                raw.get("average_volume"),
                collected_at,
            ),
        )
        conn.execute(
            """
            INSERT INTO financial_statements(
                ticker, as_of, source, statement_type, total_revenue, revenue_per_share,
                trailing_eps, forward_eps, book_value, gross_margin, operating_margin,
                profit_margin, return_on_equity, revenue_growth, earnings_growth, ebitda,
                free_cashflow, total_cash, total_debt, debt_to_equity, total_assets,
                total_liabilities, stockholders_equity, gross_profit, operating_income, net_income,
                net_assets, nav_price, expense_ratio, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, as_of, source, statement_type) DO UPDATE SET
                total_revenue=excluded.total_revenue,
                revenue_per_share=excluded.revenue_per_share,
                trailing_eps=excluded.trailing_eps,
                forward_eps=excluded.forward_eps,
                book_value=excluded.book_value,
                gross_margin=excluded.gross_margin,
                operating_margin=excluded.operating_margin,
                profit_margin=excluded.profit_margin,
                return_on_equity=excluded.return_on_equity,
                revenue_growth=excluded.revenue_growth,
                earnings_growth=excluded.earnings_growth,
                ebitda=excluded.ebitda,
                free_cashflow=excluded.free_cashflow,
                total_cash=excluded.total_cash,
                total_debt=excluded.total_debt,
                debt_to_equity=excluded.debt_to_equity,
                total_assets=excluded.total_assets,
                total_liabilities=excluded.total_liabilities,
                stockholders_equity=excluded.stockholders_equity,
                gross_profit=excluded.gross_profit,
                operating_income=excluded.operating_income,
                net_income=excluded.net_income,
                net_assets=excluded.net_assets,
                nav_price=excluded.nav_price,
                expense_ratio=excluded.expense_ratio,
                collected_at=excluded.collected_at
            """,
            (
                ticker,
                as_of,
                source,
                raw.get("statement_type") or "provider_snapshot",
                raw.get("total_revenue"),
                raw.get("revenue_per_share"),
                raw.get("trailing_eps"),
                raw.get("forward_eps"),
                raw.get("book_value"),
                raw.get("gross_margin"),
                raw.get("operating_margin"),
                raw.get("profit_margin"),
                raw.get("return_on_equity"),
                raw.get("revenue_growth"),
                raw.get("earnings_growth"),
                raw.get("ebitda"),
                raw.get("free_cashflow"),
                raw.get("total_cash"),
                raw.get("total_debt"),
                raw.get("debt_to_equity"),
                raw.get("total_assets"),
                raw.get("total_liabilities"),
                raw.get("stockholders_equity"),
                raw.get("gross_profit"),
                raw.get("operating_income"),
                raw.get("net_income"),
                raw.get("net_assets"),
                raw.get("nav_price"),
                raw.get("expense_ratio"),
                collected_at,
            ),
        )
        conn.commit()
    upsert_asset_metadata(
        [
            {
                "ticker": ticker,
                "name": raw.get("name") or "",
                "asset_class": raw.get("asset_class") or "",
                "quote_type": raw.get("quote_type") or "",
                "currency": raw.get("currency") or "",
                "exchange": raw.get("exchange") or "",
                "sector": raw.get("sector") or "",
                "industry": raw.get("industry") or "",
                "source": source,
            }
        ],
        db_path=db_path,
    )
    return {"inserted": inserted, "updated": updated}


def upsert_prices(prices: Iterable[PriceBar], *, db_path: str | Path | None = None) -> dict[str, int]:
    inserted = 0
    updated = 0
    with _conn(db_path) as conn:
        for price in prices:
            ticker = price.ticker.upper().strip()
            if not ticker or not price.date:
                continue
            asset_id = price.asset_id or _asset_id(ticker)
            existing = conn.execute(
                "SELECT 1 FROM prices_daily WHERE ticker=? AND date=? AND source=?",
                (ticker, price.date, price.source),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO prices_daily(
                    asset_id, ticker, date, open, high, low, close, adjusted_close, volume, source, collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date, source) DO UPDATE SET
                    asset_id=excluded.asset_id,
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    adjusted_close=excluded.adjusted_close,
                    volume=excluded.volume,
                    collected_at=excluded.collected_at
                """,
                (
                    asset_id,
                    ticker,
                    price.date,
                    price.open,
                    price.high,
                    price.low,
                    price.close,
                    price.adjusted_close,
                    price.volume,
                    price.source,
                    price.collected_at,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def get_prices(
    ticker: str,
    *,
    limit: int = 252,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ticker, date, open, high, low, close, adjusted_close, volume, source, collected_at
            FROM prices_daily
            WHERE ticker=?
            ORDER BY date DESC
            LIMIT ?
            """,
            (ticker.upper().strip(), int(limit)),
        ).fetchall()
    return [dict(row) for row in rows][::-1]


def price_availability(
    tickers: Iterable[str],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    min_rows: int = 2,
    db_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    clean: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            clean.append(ticker)
            seen.add(ticker)
    if not clean:
        return {}

    placeholders = ",".join("?" for _ in clean)
    where = [f"ticker IN ({placeholders})"]
    params: list[Any] = list(clean)
    if start_date:
        where.append("date >= ?")
        params.append(str(start_date))
    if end_date:
        where.append("date <= ?")
        params.append(str(end_date))
    # WHERE fragments are fixed templates and values are parameterized.
    query = "\n".join(
        [
            """
            SELECT
                ticker,
                COUNT(DISTINCT date) AS row_count,
                MIN(date) AS first_date,
                MAX(date) AS latest_date,
                GROUP_CONCAT(DISTINCT source) AS sources
            FROM prices_daily
            WHERE """,
            " AND ".join(where),
            """
            GROUP BY ticker
            """,
        ]
    )

    with _conn(db_path) as conn:
        rows = {str(row["ticker"]).upper(): dict(row) for row in conn.execute(query, params).fetchall()}

    minimum = max(1, int(min_rows or 1))
    availability: dict[str, dict[str, Any]] = {}
    for ticker in clean:
        row = rows.get(ticker) or {}
        count = int(row.get("row_count") or 0)
        status = "available" if count >= minimum else ("insufficient_history" if count else "missing_asset")
        availability[ticker] = {
            "ticker": ticker,
            "status": status,
            "available": status == "available",
            "row_count": count,
            "first_date": row.get("first_date") or "",
            "latest_date": row.get("latest_date") or "",
            "sources": [source for source in str(row.get("sources") or "").split(",") if source],
        }
    return availability


def latest_price(ticker: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT ticker, date, close, adjusted_close, volume, source, collected_at
            FROM prices_daily
            WHERE ticker=?
            ORDER BY date DESC
            LIMIT 1
            """,
            (ticker.upper().strip(),),
        ).fetchone()
    return dict(row) if row else None


def upsert_macro_observations(
    observations: Iterable[MacroObservation],
    *,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    now = utc_now_iso()
    with _conn(db_path) as conn:
        for obs in observations:
            series_id = obs.series_id.upper().strip()
            if not series_id or not obs.date:
                continue
            conn.execute(
                """
                INSERT INTO macro_series(series_id, title, units, frequency, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_id) DO UPDATE SET
                    title=COALESCE(NULLIF(excluded.title, ''), macro_series.title),
                    units=COALESCE(NULLIF(excluded.units, ''), macro_series.units),
                    frequency=COALESCE(NULLIF(excluded.frequency, ''), macro_series.frequency),
                    updated_at=excluded.updated_at
                """,
                (series_id, obs.title, obs.units, obs.frequency, obs.source, now, now),
            )
            existing = conn.execute(
                "SELECT 1 FROM macro_observations WHERE series_id=? AND date=? AND source=?",
                (series_id, obs.date, obs.source),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO macro_observations(series_id, date, value, source, collected_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(series_id, date, source) DO UPDATE SET
                    value=excluded.value,
                    collected_at=excluded.collected_at
                """,
                (series_id, obs.date, obs.value, obs.source, obs.collected_at),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def latest_macro(series_id: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT o.series_id, o.date, o.value, o.source, o.collected_at, s.title, s.units, s.frequency
            FROM macro_observations o
            LEFT JOIN macro_series s ON s.series_id = o.series_id
            WHERE o.series_id=?
            ORDER BY o.date DESC
            LIMIT 1
            """,
            (series_id.upper().strip(),),
        ).fetchone()
    return dict(row) if row else None


def latest_macros(series_ids: Iterable[str], *, db_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    ids = sorted({str(series_id or "").upper().strip() for series_id in series_ids if str(series_id or "").strip()})
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    with _conn(db_path) as conn:
        rows = conn.execute(
            f"""
            WITH ranked AS (
                SELECT
                    o.series_id,
                    o.date,
                    o.value,
                    o.source,
                    o.collected_at,
                    s.title,
                    s.units,
                    s.frequency,
                    ROW_NUMBER() OVER (
                        PARTITION BY o.series_id
                        ORDER BY o.date DESC, o.collected_at DESC, o.source DESC
                    ) AS rn
                FROM macro_observations o
                LEFT JOIN macro_series s ON s.series_id = o.series_id
                WHERE o.series_id IN ({placeholders})
            )
            SELECT series_id, date, value, source, collected_at, title, units, frequency
            FROM ranked
            WHERE rn=1
            """,
            tuple(ids),
        ).fetchall()
    return {str(row["series_id"]).upper(): dict(row) for row in rows}


def get_macro_observations(
    series_id: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 5000,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT o.series_id, o.date, o.value, o.source, o.collected_at, s.title, s.units, s.frequency
        FROM macro_observations o
        LEFT JOIN macro_series s ON s.series_id = o.series_id
        WHERE o.series_id=?
    """
    params: list[Any] = [series_id.upper().strip()]
    if start_date:
        query += " AND o.date>=?"
        params.append(start_date)
    if end_date:
        query += " AND o.date<=?"
        params.append(end_date)
    query += " ORDER BY o.date ASC LIMIT ?"
    params.append(max(1, int(limit)))
    with _conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def recent_macro_observations(
    series_id: str,
    *,
    limit: int = 300,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    bounded_limit = min(5000, max(1, int(limit or 1)))
    with _conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT o.series_id, o.date, o.value, o.source, o.collected_at, s.title, s.units, s.frequency
            FROM macro_observations o
            LEFT JOIN macro_series s ON s.series_id = o.series_id
            WHERE o.series_id=?
            ORDER BY o.date DESC, o.collected_at DESC
            LIMIT ?
            """,
            (series_id.upper().strip(), bounded_limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def upsert_news_articles(articles: Iterable[NewsArticle], *, db_path: str | Path | None = None) -> dict[str, int]:
    inserted = 0
    updated = 0
    with _conn(db_path) as conn:
        for article in articles:
            ticker = article.ticker.upper().strip()
            if not ticker or not article.title:
                continue
            seed = "|".join([ticker, article.title, article.url, article.published_at])
            article_id = hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:20]
            existing = conn.execute("SELECT 1 FROM news_articles WHERE article_id=?", (article_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO news_articles(article_id, ticker, title, url, source, published_at, summary, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    collected_at=excluded.collected_at
                """,
                (
                    article_id,
                    ticker,
                    article.title,
                    article.url,
                    article.source,
                    article.published_at,
                    article.summary,
                    article.collected_at,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def upsert_fingpt_annotations(conn: sqlite3.Connection, annotations: list[FinGPTAnnotation]) -> int:
    """Persist FinGPT article annotations into the data mart."""

    count = 0
    for annotation in annotations:
        ticker = str(annotation.ticker or "").upper().strip()
        metadata_json = json.dumps(
            annotation.metadata or {},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        conn.execute(
            """
            INSERT INTO fingpt_article_annotations(
                article_id, ticker, task, label, confidence, source, model_id, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_id, task, source, model_id) DO UPDATE SET
                ticker=excluded.ticker,
                label=excluded.label,
                confidence=excluded.confidence,
                metadata_json=excluded.metadata_json,
                created_at=excluded.created_at
            """,
            (
                annotation.article_id,
                ticker,
                annotation.task,
                annotation.label,
                float(annotation.confidence),
                annotation.source or "fingpt",
                annotation.model_id or "",
                metadata_json,
                utc_now_iso(),
            ),
        )
        count += 1
    return count


def get_fingpt_annotations(
    conn: sqlite3.Connection,
    *,
    ticker: str | None = None,
    task: str | None = None,
    limit: int = 100,
) -> list[FinGPTAnnotation]:
    """Load FinGPT article annotations newest first with optional filters."""

    bounded_limit = _bounded_annotation_limit(limit)
    where: list[str] = []
    params: list[Any] = []
    clean_ticker = str(ticker or "").upper().strip()
    if clean_ticker:
        where.append("ticker=?")
        params.append(clean_ticker)
    clean_task = str(task or "").strip()
    if clean_task:
        where.append("task=?")
        params.append(clean_task)
    query = """
        SELECT article_id, ticker, task, label, confidence, source, model_id, metadata_json
        FROM fingpt_article_annotations
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(bounded_limit)

    cursor = conn.execute(query, params)
    columns = [description[0] for description in cursor.description]
    rows = [_annotation_row_to_dict(row, columns) for row in cursor.fetchall()]
    return [
        FinGPTAnnotation(
            article_id=row["article_id"],
            ticker=row["ticker"] or "",
            task=row["task"],
            label=row["label"],
            confidence=float(row["confidence"] or 0.0),
            source=row["source"] or "fingpt",
            model_id=row["model_id"] or "",
            metadata=_decode_annotation_metadata(row["metadata_json"]),
        )
        for row in rows
    ]


def upsert_filings(filings: Iterable[Filing], *, db_path: str | Path | None = None) -> dict[str, int]:
    inserted = 0
    updated = 0
    with _conn(db_path) as conn:
        for filing in filings:
            ticker = filing.ticker.upper().strip()
            form_type = filing.form_type.upper().strip()
            if not ticker or not form_type:
                continue
            seed = filing.filing_id or "|".join([ticker, form_type, filing.filed_at, filing.url])
            filing_id = hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:24]
            existing = conn.execute("SELECT 1 FROM filings WHERE filing_id=?", (filing_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO filings(
                    filing_id, ticker, cik, accession_number, form_type, filed_at, report_date,
                    fiscal_year, fiscal_period, primary_document, description, url, source,
                    raw_json, collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filing_id) DO UPDATE SET
                    ticker=excluded.ticker,
                    cik=COALESCE(NULLIF(excluded.cik, ''), filings.cik),
                    accession_number=COALESCE(NULLIF(excluded.accession_number, ''), filings.accession_number),
                    form_type=excluded.form_type,
                    filed_at=excluded.filed_at,
                    report_date=COALESCE(NULLIF(excluded.report_date, ''), filings.report_date),
                    fiscal_year=COALESCE(excluded.fiscal_year, filings.fiscal_year),
                    fiscal_period=COALESCE(NULLIF(excluded.fiscal_period, ''), filings.fiscal_period),
                    primary_document=COALESCE(NULLIF(excluded.primary_document, ''), filings.primary_document),
                    description=COALESCE(NULLIF(excluded.description, ''), filings.description),
                    url=excluded.url,
                    source=excluded.source,
                    raw_json=excluded.raw_json,
                    collected_at=excluded.collected_at
                """,
                (
                    filing_id,
                    ticker,
                    getattr(filing, "cik", "") or "",
                    getattr(filing, "accession_number", "") or "",
                    form_type,
                    filing.filed_at,
                    getattr(filing, "report_date", "") or "",
                    getattr(filing, "fiscal_year", None),
                    getattr(filing, "fiscal_period", "") or "",
                    getattr(filing, "primary_document", "") or "",
                    getattr(filing, "description", "") or "",
                    filing.url,
                    filing.source,
                    json.dumps(getattr(filing, "raw", {}) or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    filing.collected_at,
                ),
            )
            inserted += 0 if existing else 1
            updated += 1 if existing else 0
        conn.commit()
    return {"inserted": inserted, "updated": updated}


def latest_fundamentals(ticker: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    clean = str(ticker or "").upper().strip()
    if not clean:
        return None
    with _conn(db_path) as conn:
        snapshot = conn.execute(
            """
            SELECT *
            FROM fundamentals_snapshots
            WHERE ticker=?
            ORDER BY as_of DESC, collected_at DESC
            LIMIT 1
            """,
            (clean,),
        ).fetchone()
        if not snapshot:
            return None
        as_of = snapshot["as_of"]
        source = snapshot["source"]
        valuation = conn.execute(
            """
            SELECT *
            FROM valuation_metrics
            WHERE ticker=? AND as_of=? AND source=?
            LIMIT 1
            """,
            (clean, as_of, source),
        ).fetchone()
        financials = conn.execute(
            """
            SELECT *
            FROM financial_statements
            WHERE ticker=? AND as_of=? AND source=?
            ORDER BY statement_type
            LIMIT 1
            """,
            (clean, as_of, source),
        ).fetchone()
        metadata = conn.execute("SELECT * FROM asset_metadata WHERE ticker=? LIMIT 1", (clean,)).fetchone()
    raw_payload: dict[str, Any] = {}
    try:
        raw_payload = json.loads(snapshot["raw_json"] or "{}")
    except json.JSONDecodeError:
        raw_payload = {}
    return {
        "ticker": clean,
        "as_of": as_of,
        "source": source,
        "snapshot": dict(snapshot),
        "valuation": dict(valuation) if valuation else {},
        "financials": dict(financials) if financials else {},
        "metadata": dict(metadata) if metadata else {},
        "raw": raw_payload,
    }


def fundamentals_availability(
    tickers: Iterable[str],
    *,
    db_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    clean: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            clean.append(ticker)
    if not clean:
        return {}
    placeholders = ",".join("?" for _ in clean)
    with _conn(db_path) as conn:
        query = "\n".join(
            [
                """
                SELECT ticker, MAX(as_of) AS latest_as_of, COUNT(*) AS snapshot_count
                FROM fundamentals_snapshots
                WHERE ticker IN (""",
                placeholders,
                """)
                GROUP BY ticker
                """,
            ]
        )
        rows = conn.execute(query, clean).fetchall()
    by_ticker = {str(row["ticker"]).upper(): dict(row) for row in rows}
    out: dict[str, dict[str, Any]] = {}
    for ticker in clean:
        row = by_ticker.get(ticker) or {}
        count = int(row.get("snapshot_count") or 0)
        out[ticker] = {
            "ticker": ticker,
            "available": count > 0,
            "status": "available" if count > 0 else "missing",
            "latest_as_of": row.get("latest_as_of") or "",
            "snapshot_count": count,
        }
    return out


def latest_filings(
    ticker: str,
    *,
    forms: Iterable[str] | None = None,
    limit: int = 20,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clean = str(ticker or "").upper().strip()
    if not clean:
        return []
    allowed_forms = [str(form or "").upper().strip() for form in forms or [] if str(form or "").strip()]
    query = """
        SELECT *
        FROM filings
        WHERE ticker=?
    """
    params: list[Any] = [clean]
    if allowed_forms:
        placeholders = ",".join("?" for _ in allowed_forms)
        query += f" AND form_type IN ({placeholders})"
        params.extend(allowed_forms)
    query += " ORDER BY filed_at DESC, collected_at DESC LIMIT ?"
    params.append(max(1, min(500, int(limit or 20))))
    with _conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def latest_sec_financial_facts(
    ticker: str,
    *,
    concepts: Iterable[str] | None = None,
    limit: int = 200,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clean = str(ticker or "").upper().strip()
    if not clean:
        return []
    concept_list = [str(concept or "").strip() for concept in concepts or [] if str(concept or "").strip()]
    query = """
        SELECT *
        FROM sec_financial_facts
        WHERE ticker=?
    """
    params: list[Any] = [clean]
    if concept_list:
        placeholders = ",".join("?" for _ in concept_list)
        query += f" AND concept IN ({placeholders})"
        params.extend(concept_list)
    query += " ORDER BY filed_at DESC, end_date DESC, concept ASC LIMIT ?"
    params.append(max(1, min(2000, int(limit or 200))))
    with _conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def peer_universe_candidates(
    tickers: Iterable[str],
    *,
    market: str = "US",
    sector: str = "",
    industry: str = "",
    limit: int = 12,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    excluded: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            excluded.append(ticker)
    clean_sector = str(sector or "").strip()
    clean_industry = str(industry or "").strip()
    if not clean_sector and not clean_industry:
        return []

    where = ["active=1"]
    where_params: list[Any] = []
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        where.append(f"ticker NOT IN ({placeholders})")
        where_params.extend(excluded)
    if clean_industry and clean_sector:
        where.append("(industry=? OR sector=?)")
        where_params.extend([clean_industry, clean_sector])
    elif clean_industry:
        where.append("industry=?")
        where_params.append(clean_industry)
    else:
        where.append("sector=?")
        where_params.append(clean_sector)

    clean_market = str(market or "US").upper().strip()
    if clean_market == "US":
        where.append("(currency IN ('', 'USD') OR country IN ('', 'US'))")
        where.append("ticker NOT LIKE '%.KS' AND ticker NOT LIKE '%.KQ'")
    elif clean_market == "KR":
        where.append("(currency='KRW' OR country='KR' OR ticker LIKE '%.KS' OR ticker LIKE '%.KQ')")

    params = [
        clean_industry,
        clean_industry,
        clean_sector,
        clean_sector,
        *where_params,
        max(1, min(50, int(limit or 12))),
    ]
    query = "\n".join(
        [
            """
            SELECT ticker, name, sector, industry, market, currency, exchange, source, updated_at,
                   CASE
                     WHEN ? != '' AND industry = ? THEN 3
                     WHEN ? != '' AND sector = ? THEN 2
                     ELSE 1
                   END AS peer_match_score
            FROM asset_metadata
            WHERE """,
            " AND ".join(where),
            """
              AND (quote_type IN ('', 'EQUITY') OR asset_class LIKE '%equity%')
            ORDER BY peer_match_score DESC, updated_at DESC, ticker ASC
            LIMIT ?
            """,
        ]
    )
    with _conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def sec_data_availability(
    tickers: Iterable[str],
    *,
    db_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    clean: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            clean.append(ticker)
    if not clean:
        return {}
    placeholders = ",".join("?" for _ in clean)
    with _conn(db_path) as conn:
        filings_query = "\n".join(
            [
                """
                SELECT ticker, MAX(filed_at) AS latest_filing_at, COUNT(*) AS filing_count
                FROM filings
                WHERE ticker IN (""",
                placeholders,
                """) AND form_type IN ('10-K', '10-Q', '8-K')
                GROUP BY ticker
                """,
            ]
        )
        facts_query = "\n".join(
            [
                """
                SELECT ticker, MAX(filed_at) AS latest_fact_filed_at, COUNT(*) AS fact_count
                FROM sec_financial_facts
                WHERE ticker IN (""",
                placeholders,
                """)
                GROUP BY ticker
                """,
            ]
        )
        filings = conn.execute(filings_query, clean).fetchall()
        facts = conn.execute(facts_query, clean).fetchall()
    filing_by_ticker = {str(row["ticker"]).upper(): dict(row) for row in filings}
    fact_by_ticker = {str(row["ticker"]).upper(): dict(row) for row in facts}
    out: dict[str, dict[str, Any]] = {}
    for ticker in clean:
        filing_row = filing_by_ticker.get(ticker) or {}
        fact_row = fact_by_ticker.get(ticker) or {}
        filing_count = int(filing_row.get("filing_count") or 0)
        fact_count = int(fact_row.get("fact_count") or 0)
        out[ticker] = {
            "ticker": ticker,
            "available": filing_count > 0 or fact_count > 0,
            "status": "available" if filing_count or fact_count else "missing",
            "filing_count": filing_count,
            "fact_count": fact_count,
            "latest_filing_at": filing_row.get("latest_filing_at") or "",
            "latest_fact_filed_at": fact_row.get("latest_fact_filed_at") or "",
        }
    return out


def start_update_run(
    *,
    market: str = "",
    provider: str = "",
    run_id: str | None = None,
    db_path: str | Path | None = None,
) -> str:
    run_id = run_id or uuid.uuid4().hex
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO data_update_runs(run_id, started_at, status, market, provider)
            VALUES (?, ?, 'running', ?, ?)
            """,
            (run_id, utc_now_iso(), market, provider),
        )
        conn.commit()
    return run_id


def finish_update_run(
    run_id: str,
    *,
    status: str,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            UPDATE data_update_runs
            SET finished_at=?, status=?, rows_inserted=?, rows_updated=?, error_message=?
            WHERE run_id=?
            """,
            (utc_now_iso(), status, int(rows_inserted), int(rows_updated), error_message, run_id),
        )
        conn.commit()


def record_provider_status(
    run_id: str,
    *,
    provider: str,
    status: str,
    market: str = "",
    ticker: str | None = None,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    db_path: str | Path | None = None,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO provider_status(
                run_id, provider, status, market, ticker, rows_inserted, rows_updated,
                error_message, started_at, finished_at, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                provider,
                status,
                market,
                ticker,
                int(rows_inserted),
                int(rows_updated),
                error_message,
                started_at or utc_now_iso(),
                finished_at or utc_now_iso(),
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        conn.commit()


def record_quality_check(
    *,
    check_name: str,
    status: str,
    message: str,
    run_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    observed_value: float | None = None,
    threshold_value: float | None = None,
    db_path: str | Path | None = None,
) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO data_quality_checks(
                run_id, check_name, status, entity_type, entity_id, observed_value,
                threshold_value, message, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                check_name,
                status,
                entity_type,
                entity_id,
                observed_value,
                threshold_value,
                message,
                utc_now_iso(),
            ),
        )
        conn.commit()


def _parse_utc_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def upsert_dashboard_snapshot(
    snapshot_key: str,
    payload: dict[str, Any],
    *,
    source: str = "dashboard",
    ttl_seconds: int = 60,
    db_path: str | Path | None = None,
) -> dict[str, str]:
    key = str(snapshot_key or "").strip()
    if not key:
        raise ValueError("snapshot_key is required")
    ttl = max(1, int(ttl_seconds or 60))
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    expires_at = (now_dt + timedelta(seconds=ttl)).isoformat(timespec="seconds").replace("+00:00", "Z")
    generated_at = str(payload.get("generated_at") or now)
    encoded = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO dashboard_snapshots(snapshot_key, source, payload_json, generated_at, expires_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_key) DO UPDATE SET
                source=excluded.source,
                payload_json=excluded.payload_json,
                generated_at=excluded.generated_at,
                expires_at=excluded.expires_at,
                updated_at=excluded.updated_at
            """,
            (key, source or "dashboard", encoded, generated_at, expires_at, now),
        )
        conn.commit()
    return {"snapshot_key": key, "generated_at": generated_at, "expires_at": expires_at, "updated_at": now}


def get_dashboard_snapshot(
    snapshot_key: str,
    *,
    include_expired: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    key = str(snapshot_key or "").strip()
    if not key:
        return None
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT snapshot_key, source, payload_json, generated_at, expires_at, updated_at
            FROM dashboard_snapshots
            WHERE snapshot_key=?
            """,
            (key,),
        ).fetchone()
    if row is None:
        return None
    expires_at = _parse_utc_iso(str(row["expires_at"] or ""))
    is_expired = expires_at is not None and expires_at <= datetime.now(timezone.utc)
    if is_expired and not include_expired:
        return None
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return {
        "snapshot_key": row["snapshot_key"],
        "source": row["source"],
        "payload": payload,
        "generated_at": row["generated_at"],
        "expires_at": row["expires_at"],
        "updated_at": row["updated_at"],
        "is_expired": is_expired,
    }


def clear_dashboard_snapshot(
    snapshot_key: str | None = None,
    *,
    db_path: str | Path | None = None,
) -> int:
    with _conn(db_path) as conn:
        if snapshot_key:
            cursor = conn.execute("DELETE FROM dashboard_snapshots WHERE snapshot_key=?", (str(snapshot_key).strip(),))
        else:
            cursor = conn.execute("DELETE FROM dashboard_snapshots")
        conn.commit()
        return int(cursor.rowcount or 0)


def acquire_dashboard_refresh_lock(
    lock_key: str,
    *,
    owner_token: str | None = None,
    ttl_seconds: int = 30,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    key = str(lock_key or "").strip()
    if not key:
        raise ValueError("lock_key is required")
    token = str(owner_token or uuid.uuid4().hex)
    ttl = max(1, int(ttl_seconds or 30))
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat(timespec="seconds").replace("+00:00", "Z")
    expires_at = (now_dt + timedelta(seconds=ttl)).isoformat(timespec="seconds").replace("+00:00", "Z")
    with _conn(db_path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT owner_token, acquired_at, expires_at
                FROM dashboard_refresh_locks
                WHERE lock_key=?
                """,
                (key,),
            ).fetchone()
            if row is not None:
                current_expires = _parse_utc_iso(str(row["expires_at"] or ""))
                if current_expires is not None and current_expires > now_dt:
                    conn.execute("COMMIT")
                    return {
                        "acquired": False,
                        "lock_key": key,
                        "owner_token": token,
                        "current_owner_token": row["owner_token"],
                        "current_acquired_at": row["acquired_at"],
                        "current_expires_at": row["expires_at"],
                    }
            conn.execute(
                """
                INSERT INTO dashboard_refresh_locks(lock_key, owner_token, acquired_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(lock_key) DO UPDATE SET
                    owner_token=excluded.owner_token,
                    acquired_at=excluded.acquired_at,
                    expires_at=excluded.expires_at
                """,
                (key, token, now, expires_at),
            )
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return {
        "acquired": True,
        "lock_key": key,
        "owner_token": token,
        "acquired_at": now,
        "expires_at": expires_at,
    }


def release_dashboard_refresh_lock(
    lock_key: str,
    owner_token: str,
    *,
    db_path: str | Path | None = None,
) -> bool:
    key = str(lock_key or "").strip()
    token = str(owner_token or "").strip()
    if not key or not token:
        return False
    with _conn(db_path) as conn:
        cursor = conn.execute(
            """
            DELETE FROM dashboard_refresh_locks
            WHERE lock_key=? AND owner_token=?
            """,
            (key, token),
        )
        conn.commit()
        return int(cursor.rowcount or 0) > 0


def clear_dashboard_refresh_locks(
    lock_key: str | None = None,
    *,
    db_path: str | Path | None = None,
) -> int:
    with _conn(db_path) as conn:
        if lock_key:
            cursor = conn.execute("DELETE FROM dashboard_refresh_locks WHERE lock_key=?", (str(lock_key).strip(),))
        else:
            cursor = conn.execute("DELETE FROM dashboard_refresh_locks")
        conn.commit()
        return int(cursor.rowcount or 0)


def data_health(*, db_path: str | Path | None = None) -> dict[str, Any]:
    with _conn(db_path) as conn:
        table_counts: dict[str, int] = {}
        for name in (
            "assets",
            "asset_metadata",
            "asset_identity",
            "asset_classification",
            "etf_exposure",
            "kr_equity_profile",
            "crypto_profile",
            "prices_daily",
            "macro_observations",
            "news_articles",
            "filings",
            "sec_company_registry",
            "sec_financial_facts",
            "fundamentals_snapshots",
            "valuation_metrics",
            "financial_statements",
            "data_update_runs",
            "provider_status",
            "data_quality_checks",
            "dashboard_snapshots",
            "dashboard_refresh_locks",
        ):
            query = " ".join(["SELECT COUNT(*) AS c", "FROM", name])
            table_counts[name] = int(conn.execute(query).fetchone()["c"])
        latest_fundamental = conn.execute(
            """
            SELECT ticker, as_of, source, collected_at
            FROM fundamentals_snapshots
            ORDER BY collected_at DESC
            LIMIT 1
            """
        ).fetchone()
        latest_sec_filing = conn.execute(
            """
            SELECT ticker, cik, accession_number, form_type, filed_at, report_date, url, collected_at
            FROM filings
            WHERE source LIKE 'sec%'
            ORDER BY filed_at DESC, collected_at DESC
            LIMIT 1
            """
        ).fetchone()
        latest_sec_fact = conn.execute(
            """
            SELECT ticker, cik, concept, unit, form_type, fiscal_year, fiscal_period, end_date, filed_at, value, collected_at
            FROM sec_financial_facts
            ORDER BY filed_at DESC, collected_at DESC
            LIMIT 1
            """
        ).fetchone()
        latest_macro_observation = conn.execute(
            """
            SELECT series_id, date, value, source, collected_at
            FROM macro_observations
            ORDER BY date DESC, collected_at DESC
            LIMIT 1
            """
        ).fetchone()
        macro_series_with_observations = conn.execute(
            """
            SELECT COUNT(DISTINCT series_id) AS c
            FROM macro_observations
            """
        ).fetchone()
        latest_run = conn.execute(
            "SELECT * FROM data_update_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        provider_rows = conn.execute(
            """
            SELECT provider, status, market, ticker, error_message, finished_at, details_json
            FROM provider_status
            ORDER BY finished_at DESC
            LIMIT 20
            """
        ).fetchall()
        quality_rows = conn.execute(
            """
            SELECT check_name, status, entity_type, entity_id, message, checked_at
            FROM data_quality_checks
            ORDER BY checked_at DESC
            LIMIT 20
            """
        ).fetchall()
    return {
        "status": "ok",
        "database": str(Path(db_path) if db_path else "default"),
        "table_counts": table_counts,
        "latest_fundamental": dict(latest_fundamental) if latest_fundamental else None,
        "latest_sec_filing": dict(latest_sec_filing) if latest_sec_filing else None,
        "latest_sec_fact": dict(latest_sec_fact) if latest_sec_fact else None,
        "latest_macro_observation": dict(latest_macro_observation) if latest_macro_observation else None,
        "macro_series_with_observations": int(macro_series_with_observations["c"] if macro_series_with_observations else 0),
        "latest_run": dict(latest_run) if latest_run else None,
        "recent_provider_status": [dict(row) for row in provider_rows],
        "recent_quality_checks": [dict(row) for row in quality_rows],
    }
