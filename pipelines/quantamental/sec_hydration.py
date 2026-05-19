from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pipelines.data_mart.jobs.update_sec_company_data import update_sec_company_data
from pipelines.quantamental.global_market import global_sec_hydration_plan
from pipelines.quantamental.sec_evidence import DEFAULT_FORMS


def plan_global_sec_hydration(
    tickers: Iterable[str] | None = None,
    *,
    all_known: bool = False,
) -> dict[str, Any]:
    return global_sec_hydration_plan(tickers, all_known=all_known)


def hydrate_global_sec_aliases(
    tickers: Iterable[str] | None = None,
    *,
    all_known: bool = False,
    forms: Iterable[str] = DEFAULT_FORMS,
    lookback_days: int = 365 * 5,
    max_assets: int = 25,
    filing_limit_per_ticker: int = 20,
    max_facts_per_ticker: int = 300,
    hydrate_financials: bool = True,
    dry_run: bool = True,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    plan = plan_global_sec_hydration(tickers, all_known=all_known)
    sec_tickers = [str(item) for item in plan.get("sec_tickers") or []]
    if dry_run or not sec_tickers:
        return {
            "status": "dry_run" if dry_run else "empty",
            "dry_run": bool(dry_run),
            "plan": plan,
            "sec_result": None,
        }
    result = update_sec_company_data(
        sec_tickers,
        forms=forms,
        lookback_days=max(30, int(lookback_days or 365 * 5)),
        max_assets=max(1, min(int(max_assets or 25), len(sec_tickers))),
        filing_limit_per_ticker=max(1, min(int(filing_limit_per_ticker or 20), 80)),
        max_facts_per_ticker=max(1, min(int(max_facts_per_ticker or 300), 1000)),
        hydrate_financials=bool(hydrate_financials),
        dry_run=False,
        db_path=db_path,
    )
    return {
        "status": result.status,
        "dry_run": False,
        "plan": plan,
        "sec_result": result.__dict__,
    }
