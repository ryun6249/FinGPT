from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from core.schemas.risk import RiskWorkbenchRequest, RiskWorkbenchResponse
from pipelines.risk.company import load_company_payloads
from pipelines.risk.macro import load_macro_payload
from pipelines.risk.service import build_risk_workbench_response


router = APIRouter(tags=["risk"])


async def _run_blocking(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/health")
async def risk_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "risk",
        "contract": "risk-workbench-v1",
        "not_investment_advice": True,
    }


@router.post("/workbench", response_model=RiskWorkbenchResponse)
async def risk_workbench(request: RiskWorkbenchRequest) -> RiskWorkbenchResponse:
    company_payloads, macro_payload = await asyncio.gather(
        _run_blocking(load_company_payloads, request),
        _run_blocking(load_macro_payload),
    )
    return build_risk_workbench_response(
        request=request,
        company_payloads=company_payloads,
        macro_payload=macro_payload,
    )


@router.get("/company/{ticker}", response_model=RiskWorkbenchResponse)
async def risk_company(ticker: str, market: str = "US", lookback_days: int = 756) -> RiskWorkbenchResponse:
    request = RiskWorkbenchRequest(mode="company", tickers=[ticker], market=market, lookback_days=lookback_days)
    return await risk_workbench(request)


@router.get("/macro")
async def risk_macro() -> dict[str, Any]:
    macro_payload = await _run_blocking(load_macro_payload)
    return {
        "status": "ok",
        "service": "risk",
        "macro_backdrop": build_risk_workbench_response(
            request=RiskWorkbenchRequest(mode="company", tickers=["SPY"]),
            company_payloads={},
            macro_payload=macro_payload,
        ).macro_backdrop.model_dump(mode="json"),
    }


@router.post("/scenario", response_model=RiskWorkbenchResponse)
async def risk_scenario(request: RiskWorkbenchRequest) -> RiskWorkbenchResponse:
    return await risk_workbench(request)

