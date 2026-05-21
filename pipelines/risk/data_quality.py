from __future__ import annotations

from typing import Any

from core.schemas.risk import FreshnessState, RiskDataQuality
from core.utils.asset_classifier import classify
from pipelines.risk.aggregation import clamp_score


BLOCKING_COMPANY_SECTIONS = {"company", "fundamentals", "prices", "quant"}
ASSET_PROXY_OPTIONAL_SECTIONS = {"fundamentals", "sec"}


def _freshness_from_status(status: str) -> FreshnessState:
    clean = str(status or "").lower()
    if clean == "fresh":
        return "fresh"
    if clean == "partial":
        return "partial"
    if clean == "stale":
        return "stale"
    if clean in {"missing", "failed", "error", "unavailable"}:
        return "missing"
    return "unknown"


def _worst_freshness(values: list[FreshnessState]) -> FreshnessState:
    for candidate in ("missing", "stale", "partial", "unknown", "fresh"):
        if candidate in values:
            return candidate  # type: ignore[return-value]
    return "unknown"


def _company_freshness(payload: dict[str, Any]) -> FreshnessState:
    freshness = payload.get("freshness") if isinstance(payload, dict) else {}
    return _freshness_from_status(str((freshness or {}).get("status") or payload.get("status") or "unknown"))


def _has_price_payload(payload: dict[str, Any]) -> bool:
    quant = payload.get("quant") if isinstance(payload.get("quant"), dict) else {}
    metrics = quant.get("metrics") if isinstance(quant.get("metrics"), dict) else {}
    return (
        quant.get("status") == "ok"
        and (
            bool(quant.get("price_history"))
            or bool(metrics.get("volatility"))
            or bool(metrics.get("drawdown"))
        )
    )


def _is_asset_proxy_payload(ticker: str, payload: dict[str, Any]) -> bool:
    company = payload.get("company") if isinstance(payload.get("company"), dict) else {}
    asset_profile = classify(ticker)
    quote_type = str(company.get("quote_type") or "").upper()
    is_proxy = (
        asset_profile.is_etf
        or asset_profile.asset_class in {"bond_etf", "commodity_etf", "forex", "futures", "crypto"}
        or quote_type in {"ETF", "MUTUALFUND"}
    )
    return bool(is_proxy and _has_price_payload(payload))


def evaluate_risk_data_quality(
    company_payloads: dict[str, dict[str, Any]],
    macro_payload: dict[str, Any] | None,
    *,
    include_sec: bool = True,
) -> RiskDataQuality:
    missing: list[str] = []
    stale: list[str] = []
    warnings: list[str] = []
    penalty = 0.0
    confidence_penalty = 0.0
    freshness_values: list[FreshnessState] = []
    blocking_missing: set[str] = set()

    for ticker, payload in company_payloads.items():
        clean_ticker = str(ticker or payload.get("ticker") or "").upper()
        status = str(payload.get("status") or "unknown").lower()
        freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
        quality = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
        integrity = payload.get("data_integrity") if isinstance(payload.get("data_integrity"), dict) else {}
        sections = freshness.get("sections") if isinstance(freshness.get("sections"), dict) else {}
        asset_proxy = _is_asset_proxy_payload(clean_ticker, payload)

        if status in {"failed", "error"} or integrity.get("status") == "blocked":
            if asset_proxy:
                warnings.append(f"{clean_ticker}:asset_proxy_price_macro_scope")
                penalty += 8
                confidence_penalty += 8
            else:
                missing.append(f"{clean_ticker}:critical_company_data")
                blocking_missing.add(f"{clean_ticker}:critical_company_data")
                penalty += 45
                confidence_penalty += 45
        for section in set(quality.get("missing_sections") or []) | set(freshness.get("missing_sections") or []):
            section_name = str(section)
            missing.append(f"{clean_ticker}:{section_name}")
            if asset_proxy and section_name in ASSET_PROXY_OPTIONAL_SECTIONS:
                warnings.append(f"{clean_ticker}:{section_name}_not_available_for_asset_proxy")
                penalty += 8 if section_name == "fundamentals" else 0
                confidence_penalty += 8 if section_name == "fundamentals" else 0
            elif section_name in BLOCKING_COMPANY_SECTIONS:
                blocking_missing.add(f"{clean_ticker}:{section_name}")
                penalty += 20 if section_name == "fundamentals" else 25
                confidence_penalty += 25
        for section in freshness.get("stale_sections") or []:
            section_name = str(section)
            stale.append(f"{clean_ticker}:{section_name}")
            penalty += 15 if section_name in {"prices", "price"} else 12
            confidence_penalty += 15
        for name, item in sections.items():
            if not isinstance(item, dict):
                continue
            if item.get("status") == "stale" and name not in freshness.get("stale_sections", []):
                stale.append(f"{clean_ticker}:{name}")
        if include_sec:
            sec_payload = payload.get("sec_evidence") if isinstance(payload.get("sec_evidence"), dict) else {}
            sec_status = str(sec_payload.get("status") or "").lower()
            if sec_status in {"failed", "error", "missing", ""}:
                warnings.append(f"{clean_ticker}:sec_unavailable")
                confidence_penalty += 8
            elif sec_status == "stale":
                stale.append(f"{clean_ticker}:sec")
                penalty += 5
        for warning in payload.get("warnings") or []:
            warnings.append(f"{clean_ticker}:{warning}")
        freshness_values.append(_company_freshness(payload))

    macro = macro_payload or {}
    macro_status = str(macro.get("status") or (macro.get("data_quality") or {}).get("status") or "unknown").lower()
    if macro_status in {"unavailable", "failed", "error"}:
        missing.append("macro:regime")
        blocking_missing.add("macro:regime")
        penalty += 20
        confidence_penalty += 20
        freshness_values.append("missing")
    elif macro_status in {"partial", "stale"}:
        stale.append("macro:data_quality")
        penalty += 10
        confidence_penalty += 10
        freshness_values.append("stale")
    else:
        freshness_values.append("fresh")

    coverage = macro.get("coverage") if isinstance(macro.get("coverage"), dict) else {}
    if coverage and int(coverage.get("enabled_series") or coverage.get("registry_series") or 0) < 5:
        warnings.append("macro:coverage_low")
        penalty += 10

    for warning in macro.get("warnings") or []:
        warnings.append(f"macro:{warning}")

    penalty = clamp_score(penalty, default=0.0) or 0.0
    confidence_penalty = clamp_score(confidence_penalty, default=0.0) or 0.0
    return RiskDataQuality(
        decision_usable=not blocking_missing,
        freshness=_worst_freshness(freshness_values),
        missing_inputs=sorted(set(missing)),
        stale_inputs=sorted(set(stale)),
        provider_warnings=sorted(set(warnings))[:20],
        penalty=penalty,
        confidence_penalty=confidence_penalty,
    )
