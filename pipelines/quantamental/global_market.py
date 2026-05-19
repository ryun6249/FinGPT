from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


SEC_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
KNOWN_EXCHANGE_SUFFIXES = (
    ".AS",
    ".AX",
    ".CO",
    ".DE",
    ".HK",
    ".L",
    ".PA",
    ".SS",
    ".SZ",
    ".SW",
    ".T",
    ".TO",
    ".TW",
)


@dataclass(frozen=True)
class GlobalSymbolProfile:
    symbol: str
    name: str
    country: str
    exchange: str
    yfinance_symbol: str
    sec_ticker: str | None = None
    aliases: tuple[str, ...] = ()
    sector: str = "global_equity"


@dataclass(frozen=True)
class ResolvedGlobalSymbol:
    input_ticker: str
    provider_ticker: str
    yfinance_symbol: str
    market: str = "GLOBAL"
    sec_ticker: str | None = None
    name: str | None = None
    country: str | None = None
    exchange: str | None = None
    sector: str | None = None
    resolution_source: str = "input"
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


GLOBAL_SYMBOL_PROFILES: tuple[GlobalSymbolProfile, ...] = (
    GlobalSymbolProfile("ASML.AS", "ASML Holding N.V.", "NL", "Euronext Amsterdam", "ASML.AS", "ASML", ("ASML",)),
    GlobalSymbolProfile("SHEL.L", "Shell plc", "GB", "London Stock Exchange", "SHEL.L", "SHEL", ("SHEL",)),
    GlobalSymbolProfile("ULVR.L", "Unilever PLC", "GB", "London Stock Exchange", "ULVR.L", "UL", ("UL",)),
    GlobalSymbolProfile("AZN.L", "AstraZeneca PLC", "GB", "London Stock Exchange", "AZN.L", "AZN", ("AZN",)),
    GlobalSymbolProfile("HSBA.L", "HSBC Holdings plc", "GB", "London Stock Exchange", "HSBA.L", "HSBC", ("HSBC",)),
    GlobalSymbolProfile("BP.L", "BP p.l.c.", "GB", "London Stock Exchange", "BP.L", "BP", ("BP",)),
    GlobalSymbolProfile("RIO.L", "Rio Tinto Group", "GB", "London Stock Exchange", "RIO.L", "RIO", ("RIO",)),
    GlobalSymbolProfile("BHP.AX", "BHP Group Limited", "AU", "ASX", "BHP.AX", "BHP", ("BHP",)),
    GlobalSymbolProfile("7203.T", "Toyota Motor Corporation", "JP", "Tokyo Stock Exchange", "7203.T", "TM", ("7203", "TM")),
    GlobalSymbolProfile("6758.T", "Sony Group Corporation", "JP", "Tokyo Stock Exchange", "6758.T", "SONY", ("6758", "SONY")),
    GlobalSymbolProfile("7267.T", "Honda Motor Co., Ltd.", "JP", "Tokyo Stock Exchange", "7267.T", "HMC", ("7267", "HMC")),
    GlobalSymbolProfile("7974.T", "Nintendo Co., Ltd.", "JP", "Tokyo Stock Exchange", "7974.T", "NTDOY", ("7974", "NTDOY")),
    GlobalSymbolProfile("9984.T", "SoftBank Group Corp.", "JP", "Tokyo Stock Exchange", "9984.T", "SFTBY", ("9984", "SFTBY")),
    GlobalSymbolProfile("0700.HK", "Tencent Holdings Limited", "HK", "Hong Kong Stock Exchange", "0700.HK", "TCEHY", ("0700", "TCEHY")),
    GlobalSymbolProfile("9988.HK", "Alibaba Group Holding Limited", "HK", "Hong Kong Stock Exchange", "9988.HK", "BABA", ("9988", "BABA")),
    GlobalSymbolProfile("TSM", "Taiwan Semiconductor Manufacturing Company Limited ADR", "TW", "NYSE", "TSM", "TSM", ("2330.TW",)),
    GlobalSymbolProfile("NVO", "Novo Nordisk A/S ADR", "DK", "NYSE", "NVO", "NVO", ("NVO.CO",)),
    GlobalSymbolProfile("SAP", "SAP SE ADR", "DE", "NYSE", "SAP", "SAP", ("SAP.DE",)),
    GlobalSymbolProfile("SIE.DE", "Siemens AG", "DE", "Xetra", "SIE.DE", "SIEGY", ("SIEGY",)),
    GlobalSymbolProfile("BAS.DE", "BASF SE", "DE", "Xetra", "BAS.DE", "BASFY", ("BASFY",)),
    GlobalSymbolProfile("SHOP.TO", "Shopify Inc.", "CA", "Toronto Stock Exchange", "SHOP.TO", "SHOP", ("SHOP",)),
    GlobalSymbolProfile("UBSG.SW", "UBS Group AG", "CH", "SIX Swiss Exchange", "UBSG.SW", "UBS", ("UBS",)),
    GlobalSymbolProfile("NESN.SW", "Nestle S.A.", "CH", "SIX Swiss Exchange", "NESN.SW", "NSRGY", ("NSRGY",)),
    GlobalSymbolProfile("NOVN.SW", "Novartis AG", "CH", "SIX Swiss Exchange", "NOVN.SW", "NVS", ("NVS",)),
    GlobalSymbolProfile("MC.PA", "LVMH Moet Hennessy Louis Vuitton SE", "FR", "Euronext Paris", "MC.PA", "LVMUY", ("LVMUY",)),
    GlobalSymbolProfile("OR.PA", "L'Oreal S.A.", "FR", "Euronext Paris", "OR.PA", "LRLCY", ("LRLCY",)),
    GlobalSymbolProfile("AIR.PA", "Airbus SE", "FR", "Euronext Paris", "AIR.PA", "EADSY", ("EADSY",)),
)


def clean_global_symbol(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def known_global_profiles() -> tuple[GlobalSymbolProfile, ...]:
    return GLOBAL_SYMBOL_PROFILES


def known_global_sec_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for profile in GLOBAL_SYMBOL_PROFILES:
        if not profile.sec_ticker:
            continue
        aliases[profile.symbol] = profile.sec_ticker
        aliases[profile.yfinance_symbol] = profile.sec_ticker
        for alias in profile.aliases:
            aliases[clean_global_symbol(alias)] = profile.sec_ticker
    return aliases


def resolve_global_symbol(ticker: str) -> ResolvedGlobalSymbol:
    clean = clean_global_symbol(ticker)
    profile = _PROFILE_BY_TOKEN.get(clean)
    if profile:
        warnings: list[str] = []
        source = "curated_global_symbol"
        provider_ticker = profile.yfinance_symbol
        if clean != provider_ticker:
            source = "curated_global_alias"
            if "." not in clean and not SEC_TICKER_RE.match(clean):
                warnings.append(f"global_symbol_resolved_to_yfinance:{provider_ticker}")
            elif clean.isdigit():
                warnings.append(f"global_symbol_resolved_to_yfinance:{provider_ticker}")
        return ResolvedGlobalSymbol(
            input_ticker=clean,
            provider_ticker=provider_ticker,
            yfinance_symbol=provider_ticker,
            sec_ticker=profile.sec_ticker,
            name=profile.name,
            country=profile.country,
            exchange=profile.exchange,
            sector=profile.sector,
            resolution_source=source,
            warnings=tuple(warnings),
        )

    warnings = []
    source = "input"
    if "." not in clean and clean:
        source = "unmapped_plain_symbol"
        warnings.append("global_symbol_without_exchange_suffix")
    elif any(clean.endswith(suffix) for suffix in KNOWN_EXCHANGE_SUFFIXES):
        source = "exchange_suffix_input"

    return ResolvedGlobalSymbol(
        input_ticker=clean,
        provider_ticker=clean,
        yfinance_symbol=clean,
        sec_ticker=None,
        resolution_source=source,
        warnings=tuple(warnings),
    )


def global_sec_lookup_candidates(ticker: str, *, include_input_candidates: bool = True) -> list[str]:
    clean = clean_global_symbol(ticker)
    resolved = resolve_global_symbol(clean)
    candidates: list[str] = []
    if resolved.sec_ticker:
        candidates.append(resolved.sec_ticker)
    if include_input_candidates:
        if SEC_TICKER_RE.match(clean):
            candidates.append(clean)
        if "." in clean:
            base = clean.split(".", 1)[0]
            if SEC_TICKER_RE.match(base):
                candidates.append(base)
    return _unique(candidates)


def global_sec_hydration_plan(
    tickers: Iterable[str] | None = None,
    *,
    all_known: bool = False,
) -> dict[str, object]:
    requested = [clean_global_symbol(item) for item in (tickers or []) if clean_global_symbol(item)]
    profiles = list(GLOBAL_SYMBOL_PROFILES if all_known else [])
    if requested:
        seen_profile_symbols = {profile.symbol for profile in profiles}
        for ticker in requested:
            profile = _PROFILE_BY_TOKEN.get(ticker)
            if profile and profile.symbol not in seen_profile_symbols:
                profiles.append(profile)
                seen_profile_symbols.add(profile.symbol)
    aliases: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    sec_tickers: list[str] = []
    for ticker in requested:
        profile = _PROFILE_BY_TOKEN.get(ticker)
        if not profile:
            skipped.append({"ticker": ticker, "reason": "global_symbol_not_in_curated_alias_map"})
        elif not profile.sec_ticker:
            skipped.append({"ticker": ticker, "reason": "sec_alias_missing"})
    for profile in profiles:
        if not profile.sec_ticker:
            continue
        sec_tickers.append(profile.sec_ticker)
        aliases.append(
            {
                "symbol": profile.symbol,
                "yfinance_symbol": profile.yfinance_symbol,
                "sec_ticker": profile.sec_ticker,
                "name": profile.name,
                "country": profile.country,
                "exchange": profile.exchange,
            }
        )
    return {
        "status": "ok" if sec_tickers else "empty",
        "requested_tickers": requested,
        "all_known": bool(all_known),
        "sec_tickers": _unique(sec_tickers),
        "aliases": aliases,
        "skipped": skipped,
    }


def _unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        clean = clean_global_symbol(value)
        if clean and clean not in out:
            out.append(clean)
    return out


def _build_profile_index() -> dict[str, GlobalSymbolProfile]:
    by_token: dict[str, GlobalSymbolProfile] = {}
    for profile in GLOBAL_SYMBOL_PROFILES:
        for token in (profile.symbol, profile.yfinance_symbol, *(profile.aliases or ())):
            clean = clean_global_symbol(token)
            if clean and clean not in by_token:
                by_token[clean] = profile
    return by_token


_PROFILE_BY_TOKEN = _build_profile_index()
