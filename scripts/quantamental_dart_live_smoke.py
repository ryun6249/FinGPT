from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.quantamental import service
from pipelines.quantamental.cache import quantamental_cache
from pipelines.quantamental.providers import OpenDartQuantamentalProvider


def _ok_status(payload: dict[str, Any]) -> bool:
    return str(payload.get("status") or "").lower() in {"ok", "success", "partial"}


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": payload.get("status"),
        "warnings": payload.get("warnings") or [],
        "errors": payload.get("errors") or [],
        "provider_status": payload.get("provider_status"),
    }
    if payload.get("company"):
        company = payload.get("company") or {}
        out["company"] = {
            "ticker": company.get("ticker"),
            "name": company.get("name"),
            "market": company.get("market"),
            "currency": company.get("currency"),
            "exchange": company.get("exchange"),
            "data_source": company.get("data_source"),
            "corp_code_present": bool(company.get("corp_code")),
            "stock_code": company.get("stock_code"),
        }
    if payload.get("items") is not None:
        out["item_count"] = len(payload.get("items") or [])
    if payload.get("metrics") is not None:
        metrics = payload.get("metrics") or {}
        flattened = _flatten_metrics(metrics)
        out["metric_count"] = sum(1 for value in flattened.values() if value is not None)
        out["sample_metrics"] = {
            key: flattened.get(key)
            for key in (
                "profitability.net_margin",
                "profitability.roe",
                "stability.debt_to_equity",
                "cash_flow_quality.free_cash_flow",
            )
            if key in flattened
        }
    if payload.get("latest_statement") is not None:
        latest = payload.get("latest_statement") or {}
        out["latest_statement"] = {
            key: latest.get(key)
            for key in (
                "date",
                "revenue",
                "net_income",
                "total_assets",
                "total_equity",
                "total_liabilities",
                "current_assets",
                "current_liabilities",
                "cash",
                "total_debt",
                "operating_cash_flow",
                "capital_expenditure",
                "free_cash_flow",
            )
            if key in latest
        }
    if payload.get("data_quality"):
        quality = payload.get("data_quality") or {}
        out["data_quality"] = {
            "score": quality.get("data_quality_score"),
            "level": quality.get("quality_level"),
            "missing_sections": quality.get("missing_sections") or [],
            "warnings": quality.get("warnings") or [],
        }
    if payload.get("signal"):
        signal = payload.get("signal") or {}
        out["signal"] = {
            "label": signal.get("signal_label") or signal.get("label"),
            "score": signal.get("signal_score") or signal.get("score"),
            "confidence": signal.get("signal_confidence") or signal.get("confidence"),
            "source": "deterministic_signal_engine",
        }
    if payload.get("quant"):
        quant = payload.get("quant") or {}
        out["quant"] = {
            "status": quant.get("status"),
            "provider_status": quant.get("provider_status"),
            "lookback_days": quant.get("lookback_days"),
            "missing_metrics": quant.get("missing_metrics") or [],
        }
    return out


def _flatten_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for category, values in metrics.items():
        if isinstance(values, dict):
            for key, value in values.items():
                flattened[f"{category}.{key}"] = value
        else:
            flattened[str(category)] = values
    return flattened


def _http_get(base_url: str, path: str) -> dict[str, Any]:
    with httpx.Client(timeout=60.0) as client:
        response = client.get(f"{base_url.rstrip('/')}{path}")
        return {"status_code": response.status_code, "json": response.json()}


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    if not os.getenv("DART_API_KEY"):
        raise RuntimeError("DART_API_KEY is required for credentialed DART live smoke.")
    quantamental_cache.clear()
    provider = OpenDartQuantamentalProvider()
    ticker = str(args.ticker or "005930").strip()
    period = str(args.period or "annual").strip().lower()
    years = int(args.years or 5)
    lookback = str(args.lookback or "252")

    company_raw = provider.company(ticker)
    fundamentals_raw = provider.fundamentals(ticker, period=period, years=years)
    company_payload = service.company(ticker, market="KR")
    fundamentals_payload = service.fundamentals(ticker, market="KR", period=period, years=years)
    quant_payload = service.quant(ticker, market="KR", lookback=lookback)
    analysis_payload = service.analysis(
        {
            "ticker": ticker,
            "market": "KR",
            "period": period,
            "years": years,
            "lookback": lookback,
            "style": args.style,
            "include_ai": True,
            "use_llm": False,
        }
    )

    report: dict[str, Any] = {
        "status": "passed",
        "ticker": ticker,
        "market": "KR",
        "period": period,
        "years": years,
        "lookback": lookback,
        "dart_api_key_present": True,
        "provider_company": _compact(company_raw),
        "provider_fundamentals": _compact(fundamentals_raw),
        "service_company": _compact(company_payload),
        "service_fundamentals": _compact(fundamentals_payload),
        "service_quant": _compact(quant_payload),
        "analysis": _compact(analysis_payload),
        "not_investment_advice": bool(analysis_payload.get("not_investment_advice")),
        "execution_policy": analysis_payload.get("execution_policy"),
    }

    failures: list[str] = []
    if not _ok_status(company_raw):
        failures.append("provider_company_not_ok")
    if not _ok_status(fundamentals_raw) or not fundamentals_raw.get("items"):
        failures.append("provider_fundamentals_missing")
    if not _ok_status(company_payload):
        failures.append("service_company_not_ok")
    if not _ok_status(fundamentals_payload):
        failures.append("service_fundamentals_not_ok")
    if analysis_payload.get("status") not in {"ok", "partial"}:
        failures.append("analysis_not_ok_or_partial")
    if "dart_api_key_missing" in json.dumps(report, ensure_ascii=False):
        failures.append("unexpected_missing_key_warning")
    if not report["not_investment_advice"]:
        failures.append("missing_investment_advice_disclaimer")

    if args.base_url:
        http_company = _http_get(args.base_url, f"/api/v1/quantamental/company/{ticker}?market=KR")
        http_fundamentals = _http_get(
            args.base_url,
            f"/api/v1/quantamental/fundamentals/{ticker}?market=KR&period={period}&years={years}",
        )
        http_analysis = _http_get(
            args.base_url,
            f"/api/v1/quantamental/analysis/{ticker}?market=KR&period={period}&years={years}&lookback={lookback}&include_ai=true&use_llm=false",
        )
        report["http"] = {
            "base_url": args.base_url,
            "company": _compact(http_company.get("json") or {}),
            "fundamentals": _compact(http_fundamentals.get("json") or {}),
            "analysis": _compact(http_analysis.get("json") or {}),
            "status_codes": {
                "company": http_company.get("status_code"),
                "fundamentals": http_fundamentals.get("status_code"),
                "analysis": http_analysis.get("status_code"),
            },
        }
        if any(code != 200 for code in report["http"]["status_codes"].values()):
            failures.append("http_status_not_200")
        if not _ok_status(http_company.get("json") or {}):
            failures.append("http_company_not_ok")
        if not _ok_status(http_fundamentals.get("json") or {}):
            failures.append("http_fundamentals_not_ok")

    if failures:
        report["status"] = "failed"
        report["failures"] = failures
    else:
        report["failures"] = []
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Credentialed live OpenDART smoke for Quantamental KR provider.")
    parser.add_argument("--ticker", default="005930")
    parser.add_argument("--period", default="annual", choices=["annual", "quarterly"])
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--lookback", default="252")
    parser.add_argument("--style", default="balanced")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--output", default="reports/quantamental_dart_live_latest.json")
    args = parser.parse_args()

    try:
        report = run_smoke(args)
    except Exception as exc:  # noqa: BLE001
        report = {
            "status": "failed",
            "error": f"{type(exc).__name__}:{exc}",
            "dart_api_key_present": bool(os.getenv("DART_API_KEY")),
        }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
