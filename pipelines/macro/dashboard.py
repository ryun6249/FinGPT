from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from core.schemas.macro import MacroDashboardCoverage, MacroDashboardResponse
from pipelines.macro import macro_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coverage(registry_payload: dict[str, Any], quality: dict[str, Any], quality_coverage: dict[str, Any] | None = None) -> MacroDashboardCoverage:
    items = [dict(item or {}) for item in registry_payload.get("items", [])]
    category_counts = Counter(str(item.get("category") or "unknown") for item in items)
    provider_counts = Counter(str(item.get("provider") or "unknown") for item in items)
    country_counts = Counter(str(item.get("country") or "unknown") for item in items)
    missing_series = quality.get("missing_series") or []
    stale_series = quality.get("stale_series") or []
    status_counts = dict((quality_coverage or {}).get("status_counts") or {})
    return MacroDashboardCoverage(
        registry_series=int(registry_payload.get("count") or len(items)),
        enabled_series=len(items),
        categories=dict(sorted(category_counts.items())),
        providers=dict(sorted(provider_counts.items())),
        countries=dict(sorted(country_counts.items())),
        missing_series_count=len(missing_series),
        stale_series_count=len(stale_series),
        unavailable_series_count=int(status_counts.get("unavailable", len(missing_series))),
    )


def _warnings(quality: dict[str, Any], coverage: MacroDashboardCoverage) -> list[str]:
    status = str(quality.get("status") or "unavailable")
    warnings: list[str] = []
    if status != "ok":
        warnings.append(
            "Macro data quality is "
            f"{status}; missing={coverage.missing_series_count}, "
            f"stale={coverage.stale_series_count}, unavailable={coverage.unavailable_series_count}."
        )
    for error in quality.get("errors") or []:
        warnings.append(str(error))
    return warnings


def build_macro_dashboard(
    *,
    refresh_status: dict[str, Any] | None = None,
    engine: str = "rules",
    observation_limit: int = 20,
) -> MacroDashboardResponse:
    limit = min(120, max(0, int(observation_limit or 0)))
    registry = macro_service.list_macro_series(include_disabled=False)
    overview_model = macro_service.get_macro_overview(regime_engine=engine)
    overview = macro_service.compact_macro_payload(
        overview_model,
        observation_limit=limit,
    )
    quality_payload = macro_service.get_data_quality()
    quality = dict(quality_payload.get("data_quality") or overview_model.data_quality.model_dump(mode="json"))
    coverage = _coverage(registry, quality, quality_payload.get("coverage") if isinstance(quality_payload, dict) else None)
    return MacroDashboardResponse(
        status=quality.get("status") or "unavailable",
        generated_at=_now_iso(),
        overview=overview,
        coverage=coverage,
        data_quality=quality,
        quality_detail=quality_payload,
        refresh=refresh_status or {"enabled": False},
        warnings=_warnings(quality, coverage),
    )
