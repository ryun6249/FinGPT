from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    try:
        num = float(numerator)
        den = float(denominator)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num) or not math.isfinite(den) or den == 0:
        return None
    return num / den


def clamp(value: float | int | None, low: float = 0.0, high: float = 100.0) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return max(low, min(high, parsed))


def calculate_fundamentals(payload: dict[str, Any], company: dict[str, Any] | None = None) -> dict[str, Any]:
    statements = list(payload.get("items") or [])
    info = dict(payload.get("info_metrics") or {})
    company = dict(company or {})
    latest = statements[0] if statements else {}
    previous = statements[1] if len(statements) > 1 else {}
    warnings = list(payload.get("warnings") or [])
    missing: list[str] = []

    growth = {
        "revenue_growth": _coalesce_none(_growth(latest.get("revenue"), previous.get("revenue")), info.get("revenue_growth")),
        "operating_income_growth": _growth(latest.get("operating_income"), previous.get("operating_income")),
        "net_income_growth": _coalesce_none(_growth(latest.get("net_income"), previous.get("net_income")), info.get("earnings_growth")),
        "eps_growth": info.get("earnings_growth"),
        "revenue_cagr_3y": _cagr(statements, "revenue", 3),
        "revenue_cagr_5y": _cagr(statements, "revenue", 5),
        "net_income_cagr_3y": _cagr(statements, "net_income", 3),
        "net_income_cagr_5y": _cagr(statements, "net_income", 5),
        "fcf_cagr_3y": _cagr(statements, "free_cash_flow", 3),
        "fcf_cagr_5y": _cagr(statements, "free_cash_flow", 5),
    }

    revenue = _coalesce_none(latest.get("revenue"), info.get("total_revenue"))
    gross_profit = latest.get("gross_profit")
    operating_income = latest.get("operating_income")
    net_income = latest.get("net_income")
    ebitda = _coalesce_none(latest.get("ebitda"), info.get("ebitda"))
    assets = latest.get("total_assets")
    equity = latest.get("total_equity")
    debt = _coalesce_none(latest.get("total_debt"), info.get("total_debt"))
    cash = _coalesce_none(latest.get("cash"), info.get("total_cash"))
    ocf = _coalesce_none(latest.get("operating_cash_flow"), info.get("operating_cashflow"))
    capex = latest.get("capital_expenditure")
    fcf = _coalesce_none(latest.get("free_cash_flow"), info.get("free_cashflow"))
    if fcf is None and ocf is not None and capex is not None:
        fcf = ocf + capex if float(capex) < 0 else ocf - capex

    profitability = {
        "gross_margin": _ratio_or_fallback(gross_profit, revenue, info.get("gross_margin")),
        "operating_margin": _ratio_or_fallback(operating_income, revenue, info.get("operating_margin")),
        "net_margin": _ratio_or_fallback(net_income, revenue, info.get("profit_margin")),
        "ebitda_margin": safe_divide(ebitda, revenue),
        "roe": _ratio_or_fallback(net_income, equity, info.get("return_on_equity")),
        "roa": _ratio_or_fallback(net_income, assets, info.get("return_on_assets")),
        "roic": safe_divide(operating_income, _invested_capital(latest, debt, cash)),
    }

    current_assets = latest.get("current_assets")
    current_liabilities = latest.get("current_liabilities")
    inventory = latest.get("inventory")
    quick_assets = None
    if current_assets is not None:
        quick_assets = float(current_assets) - float(inventory or 0.0)
    net_debt = None if debt is None and cash is None else float(debt or 0.0) - float(cash or 0.0)
    stability = {
        "debt_to_equity": _ratio_or_fallback(debt, equity, _percent_to_ratio(info.get("debt_to_equity"))),
        "debt_to_assets": safe_divide(debt, assets),
        "current_ratio": _ratio_or_fallback(current_assets, current_liabilities, info.get("current_ratio")),
        "quick_ratio": _ratio_or_fallback(quick_assets, current_liabilities, info.get("quick_ratio")),
        "interest_coverage": safe_divide(operating_income, latest.get("interest_expense")),
        "net_debt": net_debt,
        "net_debt_to_ebitda": safe_divide(net_debt, ebitda),
    }

    cash_flow = {
        "operating_cash_flow": ocf,
        "free_cash_flow": fcf,
        "fcf_margin": safe_divide(fcf, revenue),
        "fcf_conversion": safe_divide(fcf, net_income),
        "ocf_to_net_income": safe_divide(ocf, net_income),
        "capex_to_revenue": safe_divide(abs(float(capex)) if capex is not None else None, revenue),
    }

    market_cap = company.get("market_cap")
    enterprise_value = company.get("enterprise_value")
    price = company.get("current_price")
    shares = company.get("shares_outstanding")
    eps = info.get("trailing_eps")
    book_value = info.get("book_value")
    valuation = {
        "per": _coalesce_none(info.get("trailing_pe"), safe_divide(price, eps)),
        "pbr": _coalesce_none(info.get("price_to_book"), safe_divide(price, book_value)),
        "psr": _coalesce_none(info.get("price_to_sales_ttm"), safe_divide(market_cap, revenue)),
        "ev_to_ebitda": _coalesce_none(info.get("enterprise_to_ebitda"), safe_divide(enterprise_value, ebitda)),
        "ev_to_sales": _coalesce_none(info.get("enterprise_to_revenue"), safe_divide(enterprise_value, revenue)),
        "fcf_yield": safe_divide(fcf, market_cap),
        "earnings_yield": _coalesce_none(
            safe_divide(net_income, market_cap),
            safe_divide(eps, price),
        ),
        "peg": info.get("peg_ratio"),
        "price": price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "shares_outstanding": shares,
    }

    earnings_quality = {
        "accrual_ratio": safe_divide((net_income or 0.0) - (ocf or 0.0), assets),
        "ocf_to_net_income": cash_flow["ocf_to_net_income"],
        "fcf_to_net_income": safe_divide(fcf, net_income),
        "receivables_growth_vs_revenue_growth": _growth_spread(statements, "receivables", "revenue"),
        "inventory_growth_vs_revenue_growth": _growth_spread(statements, "inventory", "revenue"),
        "margin_stability": _margin_stability(statements),
    }

    accounting_risk = {
        "negative_equity": equity is not None and float(equity) < 0,
        "declining_margins": _declining_margins(statements),
        "earnings_cashflow_divergence": _earnings_cashflow_divergence(net_income, ocf),
        "excessive_leverage": _is_excessive_leverage(stability),
        "repeated_negative_fcf": _repeated_negative(statements, "free_cash_flow", count=2),
        "revenue_growth_without_cashflow_growth": _revenue_growth_without_cashflow(statements),
    }

    all_metrics = {
        "growth": growth,
        "profitability": profitability,
        "stability": stability,
        "cash_flow_quality": cash_flow,
        "valuation": valuation,
        "earnings_quality": earnings_quality,
        "accounting_risk": accounting_risk,
    }
    for category, values in all_metrics.items():
        for key, value in values.items():
            if value is None:
                missing.append(f"{category}.{key}")

    return {
        "status": "ok" if statements or info else "empty",
        "ticker": payload.get("ticker"),
        "market": payload.get("market"),
        "period": payload.get("period"),
        "years": payload.get("years"),
        "statements": statements,
        "latest_statement": latest,
        "metrics": all_metrics,
        "category_scores": _category_scores(all_metrics),
        "missing_metrics": missing,
        "warnings": warnings,
        "source_metadata": payload.get("source_metadata") or {},
    }


def _percent_to_ratio(value: Any) -> float | None:
    parsed = _finite(value)
    if parsed is None:
        return None
    return parsed / 100.0 if abs(parsed) > 10 else parsed


def _coalesce_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _ratio_or_fallback(numerator: Any, denominator: Any, fallback: Any) -> float | None:
    if numerator is None or denominator is None:
        return fallback
    return safe_divide(numerator, denominator)


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _growth(current: Any, previous: Any) -> float | None:
    cur = _finite(current)
    prev = _finite(previous)
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev)


def _cagr(rows: list[dict[str, Any]], key: str, years: int) -> float | None:
    if len(rows) < years:
        return None
    end = _finite(rows[0].get(key))
    start = _finite(rows[years - 1].get(key))
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / max(years - 1, 1)) - 1


def _invested_capital(latest: dict[str, Any], debt: Any, cash: Any) -> float | None:
    equity = _finite(latest.get("total_equity"))
    debt_val = _finite(debt) or 0.0
    cash_val = _finite(cash) or 0.0
    if equity is None:
        return None
    return equity + debt_val - cash_val


def _growth_spread(rows: list[dict[str, Any]], left_key: str, right_key: str) -> float | None:
    if len(rows) < 2:
        return None
    left = _growth(rows[0].get(left_key), rows[1].get(left_key))
    right = _growth(rows[0].get(right_key), rows[1].get(right_key))
    if left is None or right is None:
        return None
    return left - right


def _margin_stability(rows: list[dict[str, Any]]) -> float | None:
    margins = []
    for row in rows[:5]:
        margin = safe_divide(row.get("operating_income"), row.get("revenue"))
        if margin is not None:
            margins.append(margin)
    if len(margins) < 2:
        return None
    return 1.0 - min(pstdev(margins), 1.0)


def _declining_margins(rows: list[dict[str, Any]]) -> bool:
    margins = [safe_divide(row.get("operating_income"), row.get("revenue")) for row in rows[:3]]
    margins = [value for value in margins if value is not None]
    return len(margins) >= 3 and margins[0] < margins[1] < margins[2]


def _earnings_cashflow_divergence(net_income: Any, ocf: Any) -> bool:
    ratio = safe_divide(ocf, net_income)
    return ratio is not None and ratio < 0.5


def _is_excessive_leverage(stability: dict[str, Any]) -> bool:
    dte = _finite(stability.get("debt_to_equity"))
    net_debt_to_ebitda = _finite(stability.get("net_debt_to_ebitda"))
    return (dte is not None and dte > 3.0) or (net_debt_to_ebitda is not None and net_debt_to_ebitda > 4.0)


def _repeated_negative(rows: list[dict[str, Any]], key: str, count: int) -> bool:
    values = [_finite(row.get(key)) for row in rows[:count]]
    return len(values) >= count and all(value is not None and value < 0 for value in values)


def _revenue_growth_without_cashflow(rows: list[dict[str, Any]]) -> bool:
    if len(rows) < 2:
        return False
    revenue_growth = _growth(rows[0].get("revenue"), rows[1].get("revenue"))
    fcf_growth = _growth(rows[0].get("free_cash_flow"), rows[1].get("free_cash_flow"))
    return revenue_growth is not None and revenue_growth > 0.15 and (fcf_growth is None or fcf_growth < 0)


def _score_high(value: Any, bad: float, good: float) -> float | None:
    parsed = _finite(value)
    if parsed is None:
        return None
    if good == bad:
        return None
    return clamp(((parsed - bad) / (good - bad)) * 100)


def _score_low(value: Any, good: float, bad: float) -> float | None:
    parsed = _finite(value)
    if parsed is None:
        return None
    if good == bad:
        return None
    return clamp((1 - ((parsed - good) / (bad - good))) * 100)


def _avg(values: list[float | None], fallback: float | None = None) -> float | None:
    nums = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not nums:
        return fallback
    return clamp(mean(nums))


def _category_scores(metrics: dict[str, Any]) -> dict[str, float | None]:
    growth = metrics["growth"]
    profitability = metrics["profitability"]
    stability = metrics["stability"]
    cash_flow = metrics["cash_flow_quality"]
    valuation = metrics["valuation"]
    earnings_quality = metrics["earnings_quality"]
    accounting_risk = metrics["accounting_risk"]
    risk_penalty = 10.0 * sum(1 for value in accounting_risk.values() if value is True)
    return {
        "growth": _avg([
            _score_high(_coalesce_none(growth.get("revenue_cagr_3y"), growth.get("revenue_growth")), -0.05, 0.20),
            _score_high(_coalesce_none(growth.get("net_income_cagr_3y"), growth.get("net_income_growth")), -0.10, 0.20),
            _score_high(growth.get("fcf_cagr_3y"), -0.10, 0.20),
        ]),
        "profitability": _avg([
            _score_high(profitability.get("gross_margin"), 0.15, 0.65),
            _score_high(profitability.get("operating_margin"), 0.03, 0.30),
            _score_high(profitability.get("net_margin"), 0.02, 0.25),
            _score_high(profitability.get("roe"), 0.02, 0.25),
            _score_high(profitability.get("roic"), 0.02, 0.20),
        ]),
        "stability": _avg([
            _score_low(stability.get("debt_to_equity"), 0.2, 3.0),
            _score_low(stability.get("debt_to_assets"), 0.1, 0.8),
            _score_high(stability.get("current_ratio"), 0.7, 2.0),
            _score_low(stability.get("net_debt_to_ebitda"), 0.0, 5.0),
        ]),
        "cash_flow_quality": _avg([
            _score_high(cash_flow.get("fcf_margin"), -0.05, 0.20),
            _score_high(cash_flow.get("fcf_conversion"), 0.0, 1.2),
            _score_high(cash_flow.get("ocf_to_net_income"), 0.3, 1.3),
        ]),
        "valuation": _avg([
            _score_low(valuation.get("per"), 12.0, 45.0),
            _score_low(valuation.get("pbr"), 1.0, 12.0),
            _score_low(valuation.get("psr"), 1.0, 15.0),
            _score_low(valuation.get("ev_to_ebitda"), 8.0, 35.0),
            _score_high(valuation.get("fcf_yield"), 0.0, 0.08),
            _score_high(valuation.get("earnings_yield"), 0.0, 0.08),
        ]),
        "earnings_quality": max(0.0, (_avg([
            _score_low(abs(_finite(earnings_quality.get("accrual_ratio")) or 0.0), 0.0, 0.25),
            _score_high(earnings_quality.get("ocf_to_net_income"), 0.3, 1.3),
            _score_high(earnings_quality.get("fcf_to_net_income"), 0.0, 1.2),
            _score_high(earnings_quality.get("margin_stability"), 0.5, 1.0),
        ], fallback=50.0) or 50.0) - risk_penalty),
    }
