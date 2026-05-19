from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
from typing import Any

import httpx
from defusedxml import ElementTree

from core.config.settings import load_settings
from core.utils.logger import get_logger
from pipelines.quantamental.global_market import ResolvedGlobalSymbol, resolve_global_symbol


logger = get_logger("pipelines.quantamental.providers")

SUPPORTED_MARKETS = {"US", "KR", "GLOBAL"}
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,23}$")
DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_FINANCIALS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
DART_REPORT_CODES = {"annual": "11011", "quarterly": "11014"}
NAVER_KRX_DAILY_URL = "https://api.finance.naver.com/siseJson.naver"


class QuantamentalProviderError(RuntimeError):
    pass


class UnsupportedMarketError(QuantamentalProviderError):
    pass


class ProviderCredentialsMissing(QuantamentalProviderError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def validate_ticker(ticker: str) -> str:
    cleaned = str(ticker or "").strip().upper()
    if not cleaned:
        raise ValueError("ticker_required")
    if not TICKER_RE.match(cleaned):
        raise ValueError("invalid_ticker_format")
    return cleaned


def normalize_market(market: str) -> str:
    cleaned = str(market or "US").strip().upper()
    if cleaned not in {"US", "KR", "GLOBAL"}:
        raise UnsupportedMarketError(f"unsupported_market:{cleaned}")
    return cleaned


def lookback_to_period(lookback: int | str) -> tuple[str, int]:
    raw = str(lookback or "252").strip().upper()
    labels = {
        "3M": ("6mo", 63),
        "6M": ("1y", 126),
        "1Y": ("2y", 252),
        "3Y": ("5y", 756),
        "5Y": ("5y", 1260),
    }
    if raw in labels:
        return labels[raw]
    try:
        days = max(20, min(int(float(raw)), 1260))
    except (TypeError, ValueError):
        days = 252
    if days <= 63:
        return "6mo", days
    if days <= 126:
        return "1y", days
    if days <= 252:
        return "2y", days
    if days <= 756:
        return "5y", days
    return "5y", days


def _clean_scalar(value: Any) -> Any | None:
    if value is None:
        return None
    try:
        # pandas and numpy scalars both pass through this path.
        if hasattr(value, "item"):
            value = value.item()
    except Exception:  # noqa: BLE001
        pass
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return float(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        return text or None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _float_or_none(value: Any) -> float | None:
    cleaned = _clean_scalar(value)
    if cleaned is None:
        return None
    try:
        parsed = float(cleaned)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _str_or_none(value: Any) -> str | None:
    cleaned = _clean_scalar(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip()
    return text or None


def _date_key(value: Any) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def _frame_value(frame: Any, column: Any, candidates: list[str]) -> float | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    for row in candidates:
        try:
            if row in frame.index:
                return _float_or_none(frame.loc[row, column])
        except Exception:  # noqa: BLE001
            continue
    return None


def _kr_stock_code(ticker: str) -> str:
    clean = validate_ticker(ticker)
    if clean.endswith(".KS") or clean.endswith(".KQ"):
        clean = clean.rsplit(".", 1)[0]
    return clean.zfill(6) if clean.isdigit() and len(clean) <= 6 else clean


@dataclass(frozen=True)
class YFinanceQuantamentalProvider:
    market: str = "US"

    def _resolve(self, ticker: str) -> ResolvedGlobalSymbol:
        if self.market not in SUPPORTED_MARKETS:
            raise UnsupportedMarketError(f"unsupported_market:{self.market}:Unsupported market")
        clean_ticker = validate_ticker(ticker)
        if self.market == "GLOBAL":
            return resolve_global_symbol(clean_ticker)
        return ResolvedGlobalSymbol(
            input_ticker=clean_ticker,
            provider_ticker=clean_ticker,
            yfinance_symbol=clean_ticker,
            market=self.market,
            resolution_source="input",
        )

    def _ticker(self, ticker: str) -> Any:
        resolution = self._resolve(ticker)
        import yfinance as yf

        return yf.Ticker(resolution.yfinance_symbol)

    def company(self, ticker: str) -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        resolution = self._resolve(clean_ticker)
        cache_meta = {
            "provider": "yfinance",
            "market": self.market,
            "input_ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "resolution": resolution.to_dict(),
            "fetched_at": now_iso(),
        }
        try:
            import yfinance as yf

            yf_ticker = yf.Ticker(resolution.yfinance_symbol)
            info = yf_ticker.info or {}
            if not isinstance(info, dict):
                info = {}
        except UnsupportedMarketError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] company provider failed ticker=%s: %s", clean_ticker, exc)
            return {
                "status": "failed",
                "ticker": clean_ticker,
                "market": self.market,
                "error": f"provider_failure:{type(exc).__name__}:{exc}",
                "source_metadata": cache_meta,
                "warnings": list(resolution.warnings),
            }

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
            or info.get("navPrice")
        )
        company = {
            "ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "provider_ticker": resolution.yfinance_symbol,
            "market": self.market,
            "name": _str_or_none(info.get("longName") or info.get("shortName")),
            "sector": _str_or_none(info.get("sector")),
            "industry": _str_or_none(info.get("industry")),
            "currency": _str_or_none(info.get("currency") or info.get("financialCurrency")),
            "exchange": _str_or_none(info.get("exchange") or info.get("fullExchangeName")),
            "quote_type": _str_or_none(info.get("quoteType")),
            "current_price": _float_or_none(price),
            "market_cap": _float_or_none(info.get("marketCap")),
            "enterprise_value": _float_or_none(info.get("enterpriseValue")),
            "shares_outstanding": _float_or_none(info.get("sharesOutstanding")),
            "average_volume": _float_or_none(info.get("averageVolume") or info.get("averageVolume10days")),
            "beta": _float_or_none(info.get("beta")),
            "website": _str_or_none(info.get("website")),
            "last_updated": now_iso(),
            "data_source": "yfinance",
            "source_metadata": cache_meta,
            "raw_info_metrics": {
                "trailing_pe": _float_or_none(info.get("trailingPE")),
                "forward_pe": _float_or_none(info.get("forwardPE")),
                "price_to_book": _float_or_none(info.get("priceToBook")),
                "price_to_sales_ttm": _float_or_none(info.get("priceToSalesTrailing12Months")),
                "enterprise_to_revenue": _float_or_none(info.get("enterpriseToRevenue")),
                "enterprise_to_ebitda": _float_or_none(info.get("enterpriseToEbitda")),
                "peg_ratio": _float_or_none(info.get("pegRatio")),
                "profit_margin": _float_or_none(info.get("profitMargins")),
                "gross_margin": _float_or_none(info.get("grossMargins")),
                "operating_margin": _float_or_none(info.get("operatingMargins")),
                "return_on_equity": _float_or_none(info.get("returnOnEquity")),
                "return_on_assets": _float_or_none(info.get("returnOnAssets")),
                "revenue_growth": _float_or_none(info.get("revenueGrowth")),
                "earnings_growth": _float_or_none(info.get("earningsGrowth")),
                "total_revenue": _float_or_none(info.get("totalRevenue")),
                "ebitda": _float_or_none(info.get("ebitda")),
                "free_cashflow": _float_or_none(info.get("freeCashflow")),
                "operating_cashflow": _float_or_none(info.get("operatingCashflow")),
                "total_cash": _float_or_none(info.get("totalCash")),
                "total_debt": _float_or_none(info.get("totalDebt")),
                "debt_to_equity": _float_or_none(info.get("debtToEquity")),
                "current_ratio": _float_or_none(info.get("currentRatio")),
                "quick_ratio": _float_or_none(info.get("quickRatio")),
                "trailing_eps": _float_or_none(info.get("trailingEps")),
                "forward_eps": _float_or_none(info.get("forwardEps")),
                "book_value": _float_or_none(info.get("bookValue")),
            },
        }
        status = "ok" if company["name"] or company["current_price"] or company["market_cap"] else "empty"
        warnings = list(resolution.warnings)
        if status == "empty":
            warnings.append("company_profile_empty")
        return {"status": status, "company": company, "source_metadata": cache_meta, "warnings": warnings}

    def fundamentals(self, ticker: str, *, period: str = "annual", years: int = 5) -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        resolution = self._resolve(clean_ticker)
        period = "quarterly" if str(period).lower() == "quarterly" else "annual"
        years = max(1, min(int(years or 5), 10))
        cache_meta = {
            "provider": "yfinance",
            "market": self.market,
            "period": period,
            "input_ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "resolution": resolution.to_dict(),
            "fetched_at": now_iso(),
        }
        try:
            import yfinance as yf

            yf_ticker = yf.Ticker(resolution.yfinance_symbol)
            income = yf_ticker.quarterly_financials if period == "quarterly" else yf_ticker.financials
            balance = yf_ticker.quarterly_balance_sheet if period == "quarterly" else yf_ticker.balance_sheet
            cashflow = yf_ticker.quarterly_cashflow if period == "quarterly" else yf_ticker.cashflow
        except UnsupportedMarketError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] fundamentals provider failed ticker=%s: %s", clean_ticker, exc)
            return {
                "status": "failed",
                "ticker": clean_ticker,
                "market": self.market,
                "period": period,
                "items": [],
                "error": f"provider_failure:{type(exc).__name__}:{exc}",
                "source_metadata": cache_meta,
                "warnings": list(resolution.warnings),
            }

        dates = set()
        for frame in (income, balance, cashflow):
            if frame is not None and not getattr(frame, "empty", True):
                dates.update(list(frame.columns))
        rows = []
        for column in sorted(dates, key=lambda value: _date_key(value), reverse=True)[:years]:
            revenue = _frame_value(income, column, ["Total Revenue", "Operating Revenue", "Revenue"])
            gross_profit = _frame_value(income, column, ["Gross Profit"])
            operating_income = _frame_value(income, column, ["Operating Income", "EBIT"])
            net_income = _frame_value(income, column, ["Net Income", "Net Income Common Stockholders"])
            ebitda = _frame_value(income, column, ["EBITDA", "Normalized EBITDA"])
            total_assets = _frame_value(balance, column, ["Total Assets"])
            total_equity = _frame_value(
                balance,
                column,
                ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity"],
            )
            total_liabilities = _frame_value(
                balance,
                column,
                ["Total Liabilities Net Minority Interest", "Total Liabilities"],
            )
            current_assets = _frame_value(balance, column, ["Current Assets", "Total Current Assets"])
            current_liabilities = _frame_value(balance, column, ["Current Liabilities", "Total Current Liabilities"])
            cash = _frame_value(balance, column, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
            inventory = _frame_value(balance, column, ["Inventory"])
            receivables = _frame_value(balance, column, ["Accounts Receivable", "Receivables"])
            total_debt = _frame_value(balance, column, ["Total Debt", "Long Term Debt", "Short Long Term Debt Total"])
            operating_cash_flow = _frame_value(
                cashflow,
                column,
                ["Operating Cash Flow", "Total Cash From Operating Activities"],
            )
            capex = _frame_value(cashflow, column, ["Capital Expenditure", "Capital Expenditures"])
            free_cash_flow = _frame_value(cashflow, column, ["Free Cash Flow"])
            if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
                free_cash_flow = operating_cash_flow + capex if capex < 0 else operating_cash_flow - capex
            rows.append(
                {
                    "date": _date_key(column),
                    "revenue": revenue,
                    "gross_profit": gross_profit,
                    "operating_income": operating_income,
                    "net_income": net_income,
                    "ebitda": ebitda,
                    "total_assets": total_assets,
                    "total_equity": total_equity,
                    "total_liabilities": total_liabilities,
                    "current_assets": current_assets,
                    "current_liabilities": current_liabilities,
                    "cash": cash,
                    "inventory": inventory,
                    "receivables": receivables,
                    "total_debt": total_debt,
                    "operating_cash_flow": operating_cash_flow,
                    "capital_expenditure": capex,
                    "free_cash_flow": free_cash_flow,
                }
            )

        info_metrics = self.company(clean_ticker).get("company", {}).get("raw_info_metrics", {})
        return {
            "status": "ok" if rows or info_metrics else "empty",
            "ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "provider_ticker": resolution.yfinance_symbol,
            "market": self.market,
            "period": period,
            "years": years,
            "items": rows,
            "info_metrics": info_metrics,
            "source_metadata": cache_meta,
            "warnings": list(resolution.warnings) if rows else [*list(resolution.warnings), "financial_statement_history_missing"],
        }

    def prices(self, ticker: str, *, lookback: int | str = 252, benchmark: str = "SPY") -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        resolution = self._resolve(clean_ticker)
        yf_period, days = lookback_to_period(lookback)
        cache_meta = {
            "provider": "yfinance",
            "market": self.market,
            "input_ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "resolution": resolution.to_dict(),
            "period": yf_period,
            "lookback_days": days,
            "fetched_at": now_iso(),
        }
        try:
            import yfinance as yf

            yf_ticker = yf.Ticker(resolution.yfinance_symbol)
            history = yf_ticker.history(period=yf_period, auto_adjust=False)
            benchmark_history = None
            if benchmark:
                benchmark_history = yf.Ticker(validate_ticker(benchmark)).history(period=yf_period, auto_adjust=False)
        except UnsupportedMarketError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] price provider failed ticker=%s: %s", clean_ticker, exc)
            return {
                "status": "failed",
                "ticker": clean_ticker,
                "market": self.market,
                "items": [],
                "benchmark_items": [],
                "error": f"provider_failure:{type(exc).__name__}:{exc}",
                "source_metadata": cache_meta,
                "warnings": list(resolution.warnings),
            }

        rows = _history_rows(history)[-days:]
        benchmark_rows = _history_rows(benchmark_history)[-days:] if benchmark_history is not None else []
        return {
            "status": "ok" if rows else "empty",
            "ticker": clean_ticker,
            "resolved_ticker": resolution.provider_ticker,
            "provider_ticker": resolution.yfinance_symbol,
            "market": self.market,
            "lookback_days": days,
            "items": rows,
            "benchmark_ticker": benchmark,
            "benchmark_items": benchmark_rows,
            "source_metadata": cache_meta,
            "warnings": list(resolution.warnings) if rows else [*list(resolution.warnings), "price_history_missing"],
        }


@dataclass(frozen=True)
class OpenDartQuantamentalProvider:
    market: str = "KR"

    def _credentials(self) -> tuple[str, float]:
        settings = load_settings()
        api_key = str(getattr(settings, "dart_api_key", "") or "").strip()
        timeout_s = float(getattr(settings, "dart_request_timeout_s", 12.0) or 12.0)
        return api_key, timeout_s

    def company(self, ticker: str) -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        stock_code = _kr_stock_code(clean_ticker)
        api_key, timeout_s = self._credentials()
        cache_meta = {"provider": "opendart", "market": self.market, "fetched_at": now_iso()}
        if not api_key:
            return _dart_failed(clean_ticker, self.market, "company", "dart_api_key_missing", cache_meta)
        try:
            corp = _dart_lookup_company(api_key, stock_code, timeout_s)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] DART company provider failed ticker=%s: %s", clean_ticker, exc)
            return _dart_failed(clean_ticker, self.market, "company", f"dart_company_failure:{type(exc).__name__}:{exc}", cache_meta)
        if not corp:
            return _dart_failed(clean_ticker, self.market, "company", "dart_company_not_found", cache_meta, warning="dart_company_not_found")
        company = {
            "ticker": clean_ticker,
            "market": self.market,
            "name": corp.get("corp_name") or clean_ticker,
            "sector": "Korea Equity",
            "industry": None,
            "currency": "KRW",
            "exchange": "KRX",
            "quote_type": "EQUITY",
            "current_price": None,
            "market_cap": None,
            "enterprise_value": None,
            "shares_outstanding": None,
            "average_volume": None,
            "beta": None,
            "website": None,
            "last_updated": now_iso(),
            "data_source": "opendart",
            "corp_code": corp.get("corp_code"),
            "stock_code": corp.get("stock_code"),
            "source_metadata": cache_meta,
            "raw_info_metrics": {},
        }
        return {"status": "ok", "company": company, "source_metadata": cache_meta, "warnings": []}

    def fundamentals(self, ticker: str, *, period: str = "annual", years: int = 5) -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        stock_code = _kr_stock_code(clean_ticker)
        period = "quarterly" if str(period).lower() == "quarterly" else "annual"
        years = max(1, min(int(years or 5), 10))
        api_key, timeout_s = self._credentials()
        cache_meta = {"provider": "opendart", "market": self.market, "period": period, "fetched_at": now_iso()}
        if not api_key:
            return _dart_failed(clean_ticker, self.market, "fundamentals", "dart_api_key_missing", cache_meta)
        try:
            corp = _dart_lookup_company(api_key, stock_code, timeout_s)
            if not corp:
                return _dart_failed(clean_ticker, self.market, "fundamentals", "dart_company_not_found", cache_meta, warning="dart_company_not_found")
            rows = _dart_financial_rows(api_key, str(corp.get("corp_code") or ""), period=period, years=years, timeout_s=timeout_s)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] DART fundamentals provider failed ticker=%s: %s", clean_ticker, exc)
            return _dart_failed(clean_ticker, self.market, "fundamentals", f"dart_fundamentals_failure:{type(exc).__name__}:{exc}", cache_meta)
        return {
            "status": "ok" if rows else "empty",
            "ticker": clean_ticker,
            "market": self.market,
            "period": period,
            "years": years,
            "items": rows,
            "info_metrics": {},
            "source_metadata": cache_meta,
            "warnings": [] if rows else ["dart_financial_statement_history_missing"],
        }

    def prices(self, ticker: str, *, lookback: int | str = 252, benchmark: str = "SPY") -> dict[str, Any]:
        clean_ticker = validate_ticker(ticker)
        stock_code = _kr_stock_code(clean_ticker)
        yf_symbol = clean_ticker if clean_ticker.endswith((".KS", ".KQ")) else f"{stock_code}.KS"
        yf_period, days = lookback_to_period(lookback)
        cache_meta = {
            "provider": "yfinance_kr",
            "market": self.market,
            "symbol": yf_symbol,
            "period": yf_period,
            "lookback_days": days,
            "fetched_at": now_iso(),
        }
        warnings: list[str] = []
        rows: list[dict[str, Any]] = []
        try:
            import yfinance as yf

            history = yf.Ticker(yf_symbol).history(period=yf_period, auto_adjust=False)
            rows = _history_rows(history)[-days:]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[QUANTAMENTAL] KR price provider failed ticker=%s: %s", clean_ticker, exc)
            warnings.append(f"yfinance_kr_price_failure:{type(exc).__name__}")
        if not rows:
            api_key, timeout_s = self._credentials()
            try:
                rows = _naver_kr_price_rows(stock_code, days=days, timeout_s=timeout_s)
                if rows:
                    cache_meta["provider"] = "naver_finance_krx"
                    cache_meta["fallback_from"] = "yfinance_kr"
                else:
                    warnings.append("naver_krx_price_history_missing")
            except Exception as exc:  # noqa: BLE001
                logger.warning("[QUANTAMENTAL] Naver KRX price provider failed ticker=%s: %s", clean_ticker, exc)
                warnings.append(f"naver_krx_price_failure:{type(exc).__name__}")
        if not rows and warnings:
            return {
                "status": "failed",
                "ticker": clean_ticker,
                "market": self.market,
                "items": [],
                "benchmark_items": [],
                "error": "kr_price_history_unavailable",
                "source_metadata": cache_meta,
                "warnings": [*warnings, "kr_price_history_unavailable"],
            }
        return {
            "status": "ok" if rows else "empty",
            "ticker": clean_ticker,
            "market": self.market,
            "lookback_days": days,
            "items": rows,
            "benchmark_ticker": "",
            "benchmark_items": [],
            "source_metadata": cache_meta,
            "warnings": warnings if rows else [*warnings, "kr_price_history_missing"],
        }


def _history_rows(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    rows: list[dict[str, Any]] = []
    try:
        iterable = frame.sort_index().iterrows()
    except Exception:  # noqa: BLE001
        return []
    for idx, row in iterable:
        rows.append(
            {
                "date": _date_key(idx),
                "open": _float_or_none(row.get("Open")),
                "high": _float_or_none(row.get("High")),
                "low": _float_or_none(row.get("Low")),
                "close": _float_or_none(row.get("Close")),
                "adjusted_close": _float_or_none(row.get("Adj Close")) or _float_or_none(row.get("Close")),
                "volume": _float_or_none(row.get("Volume")),
            }
        )
    return [row for row in rows if row.get("adjusted_close") is not None]


def _naver_kr_price_rows(stock_code: str, *, days: int, timeout_s: float) -> list[dict[str, Any]]:
    clean = _kr_stock_code(stock_code)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=max(365, int(days or 252) * 2 + 30))
    response = httpx.get(
        NAVER_KRX_DAILY_URL,
        params={
            "symbol": clean,
            "requestType": "1",
            "startTime": start_date.strftime("%Y%m%d"),
            "endTime": end_date.strftime("%Y%m%d"),
            "timeframe": "day",
        },
        headers={"User-Agent": "FinGPTLocalResearch/1.0"},
        timeout=timeout_s,
    )
    response.raise_for_status()
    rows: list[dict[str, Any]] = []
    pattern = re.compile(
        r'\["(?P<date>\d{8})",\s*(?P<open>-?\d+(?:\.\d+)?),\s*(?P<high>-?\d+(?:\.\d+)?),\s*'
        r'(?P<low>-?\d+(?:\.\d+)?),\s*(?P<close>-?\d+(?:\.\d+)?),\s*(?P<volume>-?\d+(?:\.\d+)?)'
    )
    for match in pattern.finditer(response.text or ""):
        raw_date = match.group("date")
        close = _float_or_none(match.group("close"))
        if close is None:
            continue
        rows.append(
            {
                "date": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
                "open": _float_or_none(match.group("open")),
                "high": _float_or_none(match.group("high")),
                "low": _float_or_none(match.group("low")),
                "close": close,
                "adjusted_close": close,
                "volume": _float_or_none(match.group("volume")),
            }
        )
    rows.sort(key=lambda row: str(row.get("date") or ""))
    return rows[-max(1, int(days or 252)) :]


def provider_for_market(market: str) -> YFinanceQuantamentalProvider | OpenDartQuantamentalProvider:
    cleaned = normalize_market(market)
    if cleaned in {"US", "GLOBAL"}:
        return YFinanceQuantamentalProvider(market=cleaned)
    if cleaned == "KR":
        return OpenDartQuantamentalProvider(market=cleaned)
    raise UnsupportedMarketError(f"unsupported_market:{cleaned}")


def _dart_failed(
    ticker: str,
    market: str,
    section: str,
    error: str,
    source_metadata: dict[str, Any],
    *,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "section": section,
        "ticker": ticker,
        "market": market,
        "items": [],
        "error": error,
        "errors": [error],
        "warnings": [warning or error],
        "source_metadata": source_metadata,
    }


@lru_cache(maxsize=4)
def _dart_corp_rows(api_key: str, timeout_s: float) -> tuple[dict[str, str], ...]:
    response = httpx.get(DART_CORP_CODE_URL, params={"crtfc_key": api_key}, timeout=timeout_s)
    response.raise_for_status()
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        if not names:
            return tuple()
        xml_bytes = archive.read(names[0])
    root = ElementTree.fromstring(xml_bytes)
    rows: list[dict[str, str]] = []
    for item in root.findall(".//list"):
        row = {child.tag: str(child.text or "").strip() for child in list(item)}
        if row.get("corp_code"):
            rows.append(row)
    return tuple(rows)


def _dart_lookup_company(api_key: str, stock_code: str, timeout_s: float) -> dict[str, str] | None:
    clean = str(stock_code or "").upper().strip()
    for row in _dart_corp_rows(api_key, timeout_s):
        if str(row.get("stock_code") or "").upper().strip() == clean:
            return dict(row)
    return None


def _dart_financial_rows(api_key: str, corp_code: str, *, period: str, years: int, timeout_s: float) -> list[dict[str, Any]]:
    current_year = datetime.now(timezone.utc).year
    report_code = DART_REPORT_CODES.get(period, DART_REPORT_CODES["annual"])
    rows: list[dict[str, Any]] = []
    for year in range(current_year, current_year - years - 1, -1):
        response = httpx.get(
            DART_FINANCIALS_URL,
            params={
                "crtfc_key": api_key,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": report_code,
                "fs_div": "CFS",
            },
            timeout=timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status") or "") not in {"000", "013"}:
            raise QuantamentalProviderError(f"dart_financials_status:{payload.get('status')}:{payload.get('message')}")
        items = payload.get("list") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            continue
        row = _dart_statement_row_v2(items, year)
        if any(value is not None for key, value in row.items() if key != "date"):
            rows.append(row)
    return rows[:years]


def _dart_statement_row(items: list[dict[str, Any]], year: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "date": f"{year}-12-31",
        "revenue": None,
        "gross_profit": None,
        "operating_income": None,
        "net_income": None,
        "ebitda": None,
        "total_assets": None,
        "total_equity": None,
        "total_liabilities": None,
        "current_assets": None,
        "current_liabilities": None,
        "cash": None,
        "inventory": None,
        "receivables": None,
        "total_debt": None,
        "operating_cash_flow": None,
        "capital_expenditure": None,
        "free_cash_flow": None,
    }
    debt_total = 0.0
    debt_seen = False
    for item in items:
        account = str(item.get("account_nm") or "")
        amount = _parse_dart_amount(item.get("thstrm_amount"))
        if amount is None:
            continue
        if "매출액" in account or "영업수익" in account:
            row["revenue"] = row["revenue"] if row["revenue"] is not None else amount
        elif "매출총이익" in account:
            row["gross_profit"] = amount
        elif "영업이익" in account:
            row["operating_income"] = amount
        elif "당기순이익" in account and "지배" not in account and "비지배" not in account:
            row["net_income"] = amount
        elif "자산총계" in account:
            row["total_assets"] = amount
        elif "부채총계" in account:
            row["total_liabilities"] = amount
        elif "자본총계" in account:
            row["total_equity"] = amount
        elif "유동자산" == account:
            row["current_assets"] = amount
        elif "유동부채" == account:
            row["current_liabilities"] = amount
        elif "현금및현금성자산" in account:
            row["cash"] = amount
        elif "재고자산" in account:
            row["inventory"] = amount
        elif "매출채권" in account or "수취채권" in account:
            row["receivables"] = amount
        elif "차입금" in account or "사채" in account:
            debt_total += abs(amount)
            debt_seen = True
        elif "영업활동" in account and "현금흐름" in account:
            row["operating_cash_flow"] = amount
        elif "유형자산" in account and ("취득" in account or "증가" in account):
            row["capital_expenditure"] = -abs(amount)
    if debt_seen:
        row["total_debt"] = debt_total
    if row["operating_cash_flow"] is not None and row["capital_expenditure"] is not None:
        row["free_cash_flow"] = float(row["operating_cash_flow"]) + float(row["capital_expenditure"])
    return row


def _parse_dart_amount(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return -parsed if negative else parsed


def _dart_statement_row_v2(items: list[dict[str, Any]], year: int) -> dict[str, Any]:
    row: dict[str, Any] = {
        "date": f"{year}-12-31",
        "revenue": None,
        "gross_profit": None,
        "operating_income": None,
        "net_income": None,
        "ebitda": None,
        "total_assets": None,
        "total_equity": None,
        "total_liabilities": None,
        "current_assets": None,
        "current_liabilities": None,
        "cash": None,
        "inventory": None,
        "receivables": None,
        "total_debt": None,
        "operating_cash_flow": None,
        "capital_expenditure": None,
        "free_cash_flow": None,
    }
    debt_total = 0.0
    debt_seen = False
    for item in items:
        account_id = _compact_account_id(item.get("account_id"))
        statement_kind = _dart_statement_kind(item)
        amount = _parse_dart_amount(item.get("thstrm_amount"))
        if amount is None:
            continue
        if _statement_allowed(statement_kind, "income_statement") and _account_id_is(
            account_id,
            (
                "ifrsfullrevenue",
                "ifrsfullrevenuefromcontractswithcustomers",
                "ifrsfullsalesrevenue",
                "dartoperatingrevenue",
            ),
        ):
            row["revenue"] = row["revenue"] if row["revenue"] is not None else amount
        elif _statement_allowed(statement_kind, "income_statement") and _account_id_is(account_id, ("ifrsfullgrossprofit",)):
            row["gross_profit"] = amount
        elif _statement_allowed(statement_kind, "income_statement") and _account_id_is(
            account_id,
            ("dartoperatingincomeloss", "ifrsfullprofitlossfromoperatingactivities", "ifrsfulloperatingincomeloss"),
        ):
            row["operating_income"] = amount
        elif _statement_allowed(statement_kind, "income_statement") and account_id == "ifrsfullprofitlossattributabletoownersofparent":
            row["net_income"] = amount
        elif _statement_allowed(statement_kind, "income_statement") and account_id == "ifrsfullprofitloss" and row["net_income"] is None:
            row["net_income"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and account_id == "ifrsfullassets":
            row["total_assets"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and account_id == "ifrsfullliabilities":
            row["total_liabilities"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and account_id == "ifrsfullequity":
            row["total_equity"] = amount
        elif (
            _statement_allowed(statement_kind, "balance_sheet")
            and account_id == "ifrsfullequityattributabletoownersofparent"
            and row["total_equity"] is None
        ):
            row["total_equity"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and account_id == "ifrsfullcurrentassets":
            row["current_assets"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and account_id == "ifrsfullcurrentliabilities":
            row["current_liabilities"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and _account_id_is(
            account_id,
            ("ifrsfullcashandcashequivalents", "dartcashcashequivalentsandshorttermdeposits"),
        ):
            row["cash"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and _account_id_is(account_id, ("ifrsfullinventories", "ifrsfullinventory")):
            row["inventory"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and _account_id_is(
            account_id,
            (
                "ifrsfullcurrenttradereceivables",
                "ifrsfulltradeandothercurrentreceivables",
                "dartshorttermotherreceivablesnet",
            ),
        ):
            row["receivables"] = amount
        elif _statement_allowed(statement_kind, "balance_sheet") and _is_debt_account_id(account_id):
            debt_total += abs(amount)
            debt_seen = True
        elif _statement_allowed(statement_kind, "cash_flow") and account_id in {
            "ifrsfullcashflowsfromusedinoperatingactivities",
            "ifrsfullnetcashflowsfromusedinoperatingactivities",
        }:
            row["operating_cash_flow"] = amount
        elif _statement_allowed(statement_kind, "cash_flow") and (
            "purchaseofpropertyplantandequipment" in account_id or account_id == "capitalexpenditure"
        ):
            row["capital_expenditure"] = -abs(amount)
    if debt_seen:
        row["total_debt"] = debt_total
    if row["operating_cash_flow"] is not None and row["capital_expenditure"] is not None:
        row["free_cash_flow"] = float(row["operating_cash_flow"]) + float(row["capital_expenditure"])
    return row


def _compact_account_id(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _account_id_is(account_id: str, accepted: tuple[str, ...]) -> bool:
    return account_id in {_compact_account_id(item) for item in accepted}


def _dart_statement_kind(item: dict[str, Any]) -> str:
    statement = str(item.get("sj_nm") or item.get("statement") or "").lower()
    if not statement:
        return "unknown"
    if "현금흐름" in statement or "cash flow" in statement:
        return "cash_flow"
    if "재무상태" in statement or "financial position" in statement or "balance sheet" in statement:
        return "balance_sheet"
    if "손익" in statement and "포괄" not in statement:
        return "income_statement"
    if "income statement" in statement and "comprehensive" not in statement:
        return "income_statement"
    if "포괄손익" in statement or "comprehensive income" in statement:
        return "comprehensive_income"
    return "other"


def _statement_allowed(statement_kind: str, *allowed: str) -> bool:
    return statement_kind == "unknown" or statement_kind in set(allowed)


def _is_debt_account_id(account_id: str) -> bool:
    return any(
        token in account_id
        for token in (
            "borrowings",
            "bondsissued",
            "debentures",
            "leaseliabilities",
            "loansreceived",
        )
    )
