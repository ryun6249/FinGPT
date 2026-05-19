from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from core.schemas.macro import MacroSeriesDefinition


def _definition(
    series_id: str,
    display_name: str,
    category: str,
    *,
    subcategory: str = "",
    provider: str = "fred",
    provider_series_id: str | None = None,
    country: str = "US",
    region: str = "US",
    frequency: str = "daily",
    unit: str = "level",
    transform: str = "level",
    stale_after_days: int = 30,
    importance: str = "medium",
    description: str = "",
    interpretation_hint: str = "",
    enabled: bool = True,
    tags: Iterable[str] = (),
) -> MacroSeriesDefinition:
    return MacroSeriesDefinition(
        series_id=series_id.upper(),
        display_name=display_name,
        category=normalize_category(category),
        subcategory=subcategory,
        provider=provider,
        provider_series_id=(provider_series_id or series_id).upper(),
        country=country,
        region=region,
        frequency=frequency,
        unit=unit,
        transform=transform,
        stale_after_days=stale_after_days,
        importance=importance,
        description=description,
        interpretation_hint=interpretation_hint,
        enabled=enabled,
        tags=list(tags),
    )


def normalize_category(category: str) -> str:
    return str(category or "").strip().lower().replace("&", "and").replace("-", "_").replace(" ", "_")


_SERIES: "OrderedDict[str, MacroSeriesDefinition]" = OrderedDict()


def _add(definition: MacroSeriesDefinition) -> None:
    _SERIES[definition.series_id] = definition


# Interest rates and yield curve
for item in [
    ("FEDFUNDS", "Effective Federal Funds Rate", "policy", "monthly", "percent", 95, "Policy rate level."),
    ("SOFR", "Secured Overnight Financing Rate", "policy", "daily", "percent", 7, "Overnight funding-rate anchor."),
    ("DGS3MO", "3-Month Treasury Yield", "treasury", "daily", "percent", 7, "Front-end Treasury yield."),
    ("DGS1", "1-Year Treasury Yield", "treasury", "daily", "percent", 7, "Short-end Treasury yield."),
    ("DGS2", "2-Year Treasury Yield", "treasury", "daily", "percent", 7, "Policy-sensitive Treasury yield."),
    ("DGS5", "5-Year Treasury Yield", "treasury", "daily", "percent", 7, "Intermediate Treasury yield."),
    ("DGS7", "7-Year Treasury Yield", "treasury", "daily", "percent", 7, "Intermediate-duration Treasury yield."),
    ("DGS10", "10-Year Treasury Yield", "treasury", "daily", "percent", 7, "Long-duration discount-rate anchor."),
    ("DGS30", "30-Year Treasury Yield", "treasury", "daily", "percent", 7, "Long-end Treasury yield."),
    ("T10Y2Y", "10Y-2Y Treasury Spread", "yield_curve", "daily", "percentage points", 7, "Curve inversion and recession-risk proxy."),
    ("T10Y3M", "10Y-3M Treasury Spread", "yield_curve", "daily", "percentage points", 7, "Curve inversion and policy-restriction proxy."),
    ("DFII10", "10-Year Real Yield", "real_rates", "daily", "percent", 7, "Real-rate pressure on growth assets and gold."),
    ("T5YIFR", "5Y5Y Forward Inflation Expectation", "inflation_expectations", "daily", "percent", 7, "Forward inflation expectation watched by rates markets."),
    ("MORTGAGE30US", "30-Year Fixed Mortgage Rate", "mortgage", "weekly", "percent", 21, "Housing affordability and credit channel pressure."),
]:
    _add(_definition(item[0], item[1], "interest_rates", subcategory=item[2], frequency=item[3], unit=item[4], stale_after_days=item[5], interpretation_hint=item[6], importance="high"))


# Inflation
for item in [
    ("CPIAUCSL", "CPI", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Headline inflation pressure."),
    ("CPILFESL", "Core CPI", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Core inflation persistence."),
    ("PCEPI", "PCE Price Index", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Fed-preferred inflation proxy."),
    ("PCEPILFE", "Core PCE", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Fed-preferred core inflation proxy."),
    ("PCETRIM12M159SFRBDAL", "Trimmed Mean PCE", "consumer_prices", "monthly", "percent", "level", 95, "Dallas Fed trimmed-mean inflation persistence."),
    ("MEDCPIM158SFRBCLE", "Median CPI", "consumer_prices", "monthly", "percent", "level", 95, "Median CPI inflation breadth."),
    ("STICKCPIM157SFRBATL", "Sticky CPI", "consumer_prices", "monthly", "percent", "level", 95, "Sticky-price inflation persistence."),
    ("CPIENGSL", "CPI Energy", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Energy-price inflation impulse."),
    ("CPIUFDSL", "CPI Food", "consumer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Food-price inflation impulse."),
    ("T5YIE", "5-Year Breakeven Inflation", "inflation_expectations", "daily", "percent", "level", 7, "Market-implied medium-term inflation expectation."),
    ("T10YIE", "10-Year Breakeven Inflation", "inflation_expectations", "daily", "percent", "level", 7, "Market-implied long-term inflation expectation."),
    ("PPIACO", "Producer Price Index", "producer_prices", "monthly", "y/y percent", "yoy_percent", 95, "Input-price pressure."),
]:
    _add(_definition(item[0], item[1], "inflation", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="high"))


# Growth
for item in [
    ("GDPC1", "Real GDP", "growth", "quarterly", "y/y percent", "yoy_percent", 140, "Real growth trend."),
    ("INDPRO", "Industrial Production", "growth", "monthly", "y/y percent", "yoy_percent", 95, "Industrial cycle momentum."),
    ("IPMAN", "Manufacturing Industrial Production", "growth", "monthly", "y/y percent", "yoy_percent", 95, "Manufacturing-cycle momentum."),
    ("TCU", "Capacity Utilization", "growth", "monthly", "percent", "level", 95, "Slack and overheating proxy."),
    ("BUSINV", "Total Business Inventories", "growth", "monthly", "y/y percent", "yoy_percent", 95, "Inventory cycle and demand-balance proxy."),
    ("DGORDER", "Durable Goods Orders", "growth", "monthly", "y/y percent", "yoy_percent", 95, "Business spending and capex demand proxy."),
    ("RSAFS", "Retail Sales", "growth", "monthly", "y/y percent", "yoy_percent", 95, "Consumer demand momentum."),
    ("UMCSENT", "University of Michigan Sentiment", "growth", "monthly", "index", "level", 95, "Consumer confidence and demand risk."),
]:
    _add(_definition(item[0], item[1], "growth", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="high"))


# Housing, household demand, and consumer balance-sheet channels
for item in [
    ("HOUST", "Housing Starts", "housing", "monthly", "y/y percent", "yoy_percent", 95, "Residential construction cycle."),
    ("PERMIT", "Building Permits", "housing", "monthly", "y/y percent", "yoy_percent", 95, "Forward-looking housing construction signal."),
    ("CSUSHPISA", "Case-Shiller Home Price Index", "housing", "monthly", "y/y percent", "yoy_percent", 140, "Home-price inflation and household wealth."),
    ("MSPUS", "Median Sales Price of Houses Sold", "housing", "quarterly", "USD", "level", 140, "Housing price level and affordability pressure."),
    ("PCEC96", "Real Personal Consumption Expenditures", "consumer", "monthly", "y/y percent", "yoy_percent", 95, "Real household consumption trend."),
    ("DSPIC96", "Real Disposable Personal Income", "consumer", "monthly", "y/y percent", "yoy_percent", 95, "Real income support for consumption."),
    ("PSAVERT", "Personal Saving Rate", "consumer", "monthly", "percent", "level", 95, "Household savings buffer."),
    ("TOTALSL", "Consumer Credit Outstanding", "consumer", "monthly", "y/y percent", "yoy_percent", 95, "Consumer credit growth and leverage."),
]:
    _add(_definition(item[0], item[1], "housing_consumer", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="medium"))


# Labor
for item in [
    ("UNRATE", "Unemployment Rate", "labor", "monthly", "percent", "level", 95, "Labor-market slack."),
    ("U6RATE", "U-6 Unemployment Rate", "labor", "monthly", "percent", "level", 95, "Broad labor underutilization."),
    ("CIVPART", "Labor Force Participation Rate", "labor", "monthly", "percent", "level", 95, "Participation and labor-supply trend."),
    ("PAYEMS", "Nonfarm Payrolls", "labor", "monthly", "y/y percent", "yoy_percent", 95, "Payroll growth trend."),
    ("CES0500000003", "Average Hourly Earnings", "labor", "monthly", "y/y percent", "yoy_percent", 95, "Wage inflation pressure."),
    ("AWHMAN", "Manufacturing Weekly Hours", "labor", "monthly", "hours", "level", 95, "Cyclical labor-hours signal."),
    ("ICSA", "Initial Jobless Claims", "labor", "weekly", "level", "level", 21, "High-frequency labor stress."),
    ("JTSJOL", "Job Openings", "labor", "monthly", "level", "level", 95, "Labor demand."),
]:
    _add(_definition(item[0], item[1], "labor", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="high"))


# Liquidity, credit, and market stress
for item in [
    ("M2SL", "M2 Money Stock", "liquidity", "monthly", "y/y percent", "yoy_percent", 95, "Broad money growth."),
    ("WALCL", "Fed Balance Sheet", "liquidity", "weekly", "y/y percent", "yoy_percent", 21, "Central-bank liquidity impulse."),
    ("RRPONTSYD", "Overnight Reverse Repo", "liquidity", "daily", "USD billions", "level", 7, "Reserve-drain and liquidity proxy."),
    ("BAMLH0A0HYM2", "High Yield Credit Spread", "credit", "daily", "percentage points", "level", 7, "Credit stress proxy."),
    ("BAMLC0A0CM", "Investment Grade Credit Spread", "credit", "daily", "percentage points", "level", 7, "Investment-grade credit stress proxy."),
    ("BAMLC0A4CBBB", "BBB Corporate Credit Spread", "credit", "daily", "percentage points", "level", 7, "Lower investment-grade credit stress proxy."),
    ("BAMLH0A3HYC", "CCC High Yield Credit Spread", "credit", "daily", "percentage points", "level", 7, "Distressed high-yield credit stress proxy."),
]:
    _add(_definition(item[0], item[1], "liquidity_credit", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="high"))

_add(_definition("VIXCLS", "CBOE VIX", "market", subcategory="risk", frequency="daily", unit="index", stale_after_days=7, interpretation_hint="Equity volatility and risk appetite.", importance="medium"))

for item in [
    ("NFCI", "Chicago Fed National Financial Conditions Index", "financial_conditions", "weekly", "index", "level", 21, "Broad financial conditions stress."),
    ("STLFSI4", "St. Louis Fed Financial Stress Index", "financial_conditions", "weekly", "index", "level", 21, "Market-based financial stress."),
    ("DRTSCILM", "C&I Loan Standards Tightening", "bank_lending", "quarterly", "net percent", "level", 140, "Bank-lending standards for medium and large firms."),
    ("BUSLOANS", "Commercial and Industrial Loans", "bank_lending", "monthly", "y/y percent", "yoy_percent", 95, "Bank credit growth to businesses."),
]:
    _add(_definition(item[0], item[1], "financial_conditions", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="medium"))

for item in [
    ("DTWEXBGS", "Trade Weighted U.S. Dollar Index", "dollar", "daily", "index", "level", 7, "Broad dollar strength."),
    ("DEXUSEU", "USD/EUR Exchange Rate", "fx", "daily", "USD per EUR", "level", 7, "Euro-dollar exchange-rate pressure."),
    ("DEXJPUS", "JPY/USD Exchange Rate", "fx", "daily", "JPY per USD", "level", 7, "Yen-dollar exchange-rate pressure."),
    ("DEXKOUS", "KRW/USD Exchange Rate", "fx", "daily", "KRW per USD", "level", 7, "Korea won-dollar exchange-rate pressure."),
]:
    _add(_definition(item[0], item[1], "fx_dollar", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="medium"))

for item in [
    ("DCOILWTICO", "WTI Crude Oil", "energy", "daily", "USD per barrel", "level", 14, "Oil-price inflation and growth shock proxy."),
    ("DHHNGSP", "Henry Hub Natural Gas", "energy", "daily", "USD per MMBtu", "level", 14, "Natural-gas energy cost pressure."),
    ("DCOILBRENTEU", "Brent Crude Oil", "energy", "daily", "USD per barrel", "level", 14, "Global oil-price inflation and growth shock proxy."),
]:
    _add(_definition(item[0], item[1], "commodities", subcategory=item[2], frequency=item[3], unit=item[4], transform=item[5], stale_after_days=item[6], interpretation_hint=item[7], importance="medium"))


# Cross-provider extension entries. ECOS/OECD/World Bank remain disabled in
# default dashboards to avoid surprise key/network dependencies, but direct
# series fetches can use their adapters. Yahoo market proxies are enabled
# category surfaces because yfinance is already part of the local stack.
for item in [
    (
        "ECOS_KR_POLICY_RATE",
        "Korea Policy Rate",
        "interest_rates",
        "ecos",
        "722Y001/M/0101000",
        "KR",
        "monthly",
        "percent",
        65,
        "Bank of Korea policy-rate extension; requires ECOS_API_KEY.",
    ),
    (
        "ECOS_KR_CPI",
        "Korea CPI",
        "inflation",
        "ecos",
        "901Y009/M/0",
        "KR",
        "monthly",
        "index",
        65,
        "Korea CPI extension; requires ECOS_API_KEY and verified ECOS item code.",
    ),
    (
        "ECOS_USDKRW",
        "USD/KRW",
        "fx_dollar",
        "ecos",
        "731Y001/D/0000001",
        "KR",
        "daily",
        "KRW per USD",
        7,
        "USD/KRW extension; requires ECOS_API_KEY and verified ECOS item code.",
    ),
    (
        "OECD_CLI",
        "OECD US Composite Leading Indicator",
        "growth",
        "oecd",
        "DP_LIVE/USA.CLI.AMPLITUD.LTRENDIDX.M",
        "US",
        "monthly",
        "index",
        65,
        "OECD leading-indicator extension via SDMX.",
    ),
    (
        "WORLD_BANK_GDP",
        "World Bank US GDP Growth",
        "growth",
        "worldbank",
        "NY.GDP.MKTP.KD.ZG",
        "US",
        "annual",
        "annual percent",
        500,
        "World Bank annual real GDP growth extension.",
    ),
]:
    _add(
        _definition(
            item[0],
            item[1],
            item[2],
            provider=item[3],
            provider_series_id=item[4],
            country=item[5],
            region=item[5],
            frequency=item[6],
            unit=item[7],
            stale_after_days=item[8],
            description="Cross-provider macro extension entry.",
            interpretation_hint=item[9],
            enabled=False,
            tags=["extension"],
        )
    )

for item in [
    ("YAHOO_DXY_PROXY", "Dollar Index Proxy", "fx_dollar", "DX-Y.NYB", "index", "Dollar strength proxy."),
    ("YAHOO_GLD", "GLD Gold Proxy", "commodities", "GLD", "price", "Gold price proxy."),
    ("YAHOO_USO", "USO Oil Proxy", "commodities", "USO", "price", "Oil price proxy."),
    ("YAHOO_TLT", "TLT Duration Proxy", "market", "TLT", "price", "Long-duration Treasury ETF proxy."),
    ("YAHOO_SPY", "SPY Equity Proxy", "market", "SPY", "price", "US equity beta proxy."),
]:
    _add(
        _definition(
            item[0],
            item[1],
            item[2],
            provider="yahoo",
            provider_series_id=item[3],
            country="US",
            region="US",
            frequency="daily",
            unit=item[4],
            stale_after_days=7,
            importance="medium",
            description="Yahoo Finance market proxy; values are price/index levels, not economic releases.",
            interpretation_hint=item[5],
            enabled=True,
            tags=["market_proxy", "extension"],
        )
    )


def list_macro_series(*, include_disabled: bool = False) -> list[MacroSeriesDefinition]:
    return [definition for definition in _SERIES.values() if include_disabled or definition.enabled]


def get_series_definition(series_id: str) -> MacroSeriesDefinition:
    key = str(series_id or "").upper().strip()
    if key not in _SERIES:
        raise KeyError(key)
    return _SERIES[key]


def series_by_category(category: str, *, include_disabled: bool = False) -> list[MacroSeriesDefinition]:
    slug = normalize_category(category)
    return [item for item in list_macro_series(include_disabled=include_disabled) if item.category == slug]


def category_names() -> list[str]:
    return sorted({item.category for item in list_macro_series(include_disabled=False)})


def provider_names(*, include_disabled: bool = True) -> list[str]:
    return sorted({item.provider for item in list_macro_series(include_disabled=include_disabled)})


def country_names(*, include_disabled: bool = True) -> list[str]:
    return sorted({item.country for item in list_macro_series(include_disabled=include_disabled)})
