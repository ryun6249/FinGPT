from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from core.config.settings import load_settings
from core.schemas.macro import (
    MacroBriefResponse,
    MacroDataQuality,
    MacroObservation,
    MacroOverview,
    MacroReportResponse,
    MacroSeriesDetailResponse,
    MacroSeriesResponse,
    MacroSeriesSearchItem,
    MacroSeriesSearchResponse,
)
from pipelines.data_mart.storage import repository
from pipelines.macro.ai_brief import generate_brief
from pipelines.macro.asset_impact import get_asset_impacts
from pipelines.macro.data_quality import aggregate_quality, evaluate_series_quality
from pipelines.macro.portfolio_hints import get_portfolio_policy_hint
from pipelines.macro.providers.ecos import EcosProvider
from pipelines.macro.providers.fred import FredProvider
from pipelines.macro.providers.oecd import OecdProvider
from pipelines.macro.providers.storage import DataMartMacroProvider
from pipelines.macro.providers.unavailable import UnavailableProvider
from pipelines.macro.providers.worldbank import WorldBankProvider
from pipelines.macro.providers.yahoo import YahooFinanceProvider
from pipelines.macro.regime_engine import classify_macro_regime
from pipelines.macro.research_context import get_research_context
from pipelines.macro.series_registry import (
    category_names,
    country_names,
    get_series_definition,
    list_macro_series as _list_macro_series,
    normalize_category,
    provider_names,
    series_by_category,
)
from pipelines.macro.transforms import apply_transform, compute_changes


KEY_INDICATOR_IDS = [
    "FEDFUNDS",
    "DGS3MO",
    "DGS2",
    "DGS10",
    "DGS30",
    "T10Y2Y",
    "T10Y3M",
    "DFII10",
    "T5YIFR",
    "MORTGAGE30US",
    "CPIAUCSL",
    "CPILFESL",
    "PCEPI",
    "PCEPILFE",
    "MEDCPIM158SFRBCLE",
    "STICKCPIM157SFRBATL",
    "UNRATE",
    "U6RATE",
    "GDPC1",
    "TCU",
    "PCEC96",
    "HOUST",
    "NFCI",
    "DTWEXBGS",
    "DCOILWTICO",
    "VIXCLS",
]

REGIME_INPUT_IDS = [
    "FEDFUNDS",
    "SOFR",
    "DGS2",
    "DFII10",
    "CPIAUCSL",
    "CPILFESL",
    "PCEPI",
    "PCEPILFE",
    "T5YIE",
    "T10YIE",
    "T5YIFR",
    "PPIACO",
    "GDPC1",
    "INDPRO",
    "RSAFS",
    "UMCSENT",
    "UNRATE",
    "PAYEMS",
    "ICSA",
    "JTSJOL",
    "M2SL",
    "WALCL",
    "RRPONTSYD",
    "BAMLH0A0HYM2",
    "BAMLC0A0CM",
    "VIXCLS",
]

_SERIES_CACHE_TTL_S = 300.0
_OVERVIEW_CACHE_TTL_S = 120.0
_SERIES_CACHE: dict[tuple[str, str, str | None, str | None], tuple[float, MacroSeriesResponse]] = {}
_OVERVIEW_CACHE: dict[str, tuple[float, MacroOverview]] = {}


def clear_macro_caches() -> None:
    _SERIES_CACHE.clear()
    _OVERVIEW_CACHE.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_observation_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _cache_time() -> float:
    return datetime.now(timezone.utc).timestamp()


def _cache_key() -> str:
    settings = load_settings()
    provider_state = ";".join(f"{name}:{int(provider.is_available())}" for name, provider in _live_providers().items())
    return f"{settings.data_mart_db_path}|{provider_state}"


def _live_providers():
    return {
        "fred": FredProvider(),
        "ecos": EcosProvider(),
        "oecd": OecdProvider(),
        "worldbank": WorldBankProvider(),
        "yahoo": YahooFinanceProvider(),
    }


def _fetch_raw_series(definition, *, start_date: str | None = None, end_date: str | None = None):
    storage = DataMartMacroProvider()
    storage_result = storage.fetch_series(definition, start_date=start_date, end_date=end_date)
    if storage_result.observations:
        return storage_result
    provider = _live_providers().get(str(definition.provider or "").lower())
    if provider is not None and provider.supports(definition):
        return provider.fetch_series(definition, start_date=start_date, end_date=end_date)
    return UnavailableProvider("No cached data and live provider is not configured.").fetch_series(
        definition,
        start_date=start_date,
        end_date=end_date,
    )


def list_macro_series(*, include_disabled: bool = False) -> dict[str, Any]:
    items = _list_macro_series(include_disabled=include_disabled)
    return {
        "status": "success",
        "count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
        "data_quality": MacroDataQuality(status="ok", provider="registry", notes=["Registry metadata only."]).model_dump(mode="json"),
    }


_SEARCH_ALIAS_OVERRIDES: dict[str, list[str]] = {
    "CPIAUCSL": ["cpi", "headline cpi", "consumer price index", "us cpi", "inflation headline"],
    "CPILFESL": ["core cpi", "cpi ex food energy", "underlying cpi", "core inflation"],
    "CPIENGSL": ["cpi energy", "energy cpi", "energy inflation"],
    "CPIUFDSL": ["cpi food", "food cpi", "food inflation"],
    "PCEPI": ["pce", "pce inflation", "personal consumption expenditure prices"],
    "PCEPILFE": ["core pce", "fed preferred inflation", "pce ex food energy"],
    "FEDFUNDS": ["fed funds", "policy rate", "fed rate", "federal funds"],
    "SOFR": ["overnight rate", "funding rate", "secured overnight financing rate"],
    "UNRATE": ["unemployment", "jobless rate", "labor slack"],
    "PAYEMS": ["payrolls", "nonfarm payrolls", "jobs"],
    "ICSA": ["jobless claims", "initial claims", "claims"],
    "GDPC1": ["real gdp", "gdp growth", "economic growth"],
    "INDPRO": ["industrial production", "production"],
    "RSAFS": ["retail sales", "consumer sales"],
    "DCOILWTICO": ["wti", "oil", "crude oil"],
    "DCOILBRENTEU": ["brent", "brent oil"],
    "DTWEXBGS": ["dxy", "dollar", "usd index", "trade weighted dollar"],
    "VIXCLS": ["vix", "volatility", "equity volatility"],
}

_COMPONENT_SERIES: dict[str, list[str]] = {
    "CPIAUCSL": ["CPILFESL", "CPIENGSL", "CPIUFDSL", "MEDCPIM158SFRBCLE", "STICKCPIM157SFRBATL", "PCEPI", "PCEPILFE"],
    "CPILFESL": ["CPIAUCSL", "MEDCPIM158SFRBCLE", "STICKCPIM157SFRBATL", "PCEPILFE", "PCETRIM12M159SFRBDAL"],
    "PCEPI": ["PCEPILFE", "PCETRIM12M159SFRBDAL", "CPIAUCSL", "CPILFESL", "T5YIE", "T10YIE"],
    "PCEPILFE": ["PCEPI", "PCETRIM12M159SFRBDAL", "CPILFESL", "MEDCPIM158SFRBCLE"],
    "DGS10": ["DGS2", "DGS30", "T10Y2Y", "T10Y3M", "DFII10", "T10YIE", "T5YIFR", "YAHOO_TLT"],
    "DGS2": ["FEDFUNDS", "SOFR", "DGS3MO", "DGS10", "T10Y2Y"],
    "T10Y2Y": ["DGS2", "DGS10", "T10Y3M", "FEDFUNDS", "UNRATE"],
    "T10Y3M": ["DGS3MO", "DGS10", "T10Y2Y", "FEDFUNDS", "UNRATE"],
    "UNRATE": ["U6RATE", "PAYEMS", "ICSA", "JTSJOL", "CIVPART", "CES0500000003"],
    "GDPC1": ["INDPRO", "RSAFS", "TCU", "UMCSENT", "PCEC96", "DSPIC96"],
    "M2SL": ["WALCL", "RRPONTSYD", "BAMLH0A0HYM2", "BAMLC0A0CM"],
    "BAMLH0A0HYM2": ["BAMLC0A0CM", "BAMLC0A4CBBB", "BAMLH0A3HYC", "VIXCLS", "NFCI"],
    "DCOILWTICO": ["DCOILBRENTEU", "DHHNGSP", "CPIENGSL", "PPIACO", "YAHOO_USO"],
}

_IMPORTANCE_BONUS = {"high": 8.0, "medium": 4.0, "low": 1.0}


def _normalize_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _query_tokens(query: str) -> list[str]:
    return [token for token in _normalize_search_text(query).split() if token]


def _field_contains_token(field: str, token: str) -> bool:
    words = set(str(field or "").split())
    if len(token) <= 2:
        return token in words
    return token in field


def _series_aliases(definition) -> list[str]:
    aliases = set(_SEARCH_ALIAS_OVERRIDES.get(definition.series_id, []))
    aliases.update(str(tag) for tag in definition.tags)
    aliases.add(definition.series_id.lower())
    aliases.add(definition.display_name.lower())
    aliases.add(definition.provider_series_id.lower())
    if definition.series_id.startswith("DGS"):
        tenor = definition.series_id.removeprefix("DGS").lower()
        tenor = tenor.replace("mo", "m")
        aliases.update(
            {
                f"us {tenor}",
                f"{tenor} treasury",
                f"us treasury {tenor}",
                f"{tenor} yield",
                f"treasury {tenor} yield",
            }
        )
        if tenor.isdigit():
            aliases.update({f"{tenor}y", f"us {tenor}y", f"{tenor} year treasury", f"treasury {tenor} year"})
    if definition.series_id.startswith("T10Y"):
        aliases.update({"yield curve", "curve spread", "inversion", "10y spread"})
    if definition.category == "inflation":
        aliases.update({"inflation", "prices", "price pressure"})
    if definition.category in {"growth", "labor"}:
        aliases.update({"cycle", "macro activity"})
    return sorted(alias for alias in aliases if alias)


def _score_definition(definition, query: str, tokens: list[str]) -> tuple[float, list[str]]:
    aliases = _series_aliases(definition)
    fields = [
        definition.series_id,
        definition.display_name,
        definition.category,
        definition.subcategory,
        definition.provider,
        definition.country,
        definition.region,
        definition.unit,
        definition.description,
        definition.interpretation_hint,
        *aliases,
    ]
    normalized_fields = [_normalize_search_text(item) for item in fields if item]
    haystack = " ".join(normalized_fields)
    normalized_query = _normalize_search_text(query)
    if not tokens:
        return _IMPORTANCE_BONUS.get(definition.importance, 1.0), []

    score = _IMPORTANCE_BONUS.get(definition.importance, 1.0)
    matched: list[str] = []
    if normalized_query and normalized_query == _normalize_search_text(definition.series_id):
        score += 120
        matched.append(definition.series_id)
    if normalized_query and normalized_query in normalized_fields:
        score += 90
        matched.append(normalized_query)
    elif normalized_query and normalized_query in haystack:
        score += 45
        matched.append(normalized_query)
    for token in tokens:
        normalized_id = _normalize_search_text(definition.series_id)
        if (len(token) > 2 and token in normalized_id) or token == normalized_id:
            score += 30
            matched.append(token)
        elif any(_field_contains_token(field, token) for field in normalized_fields):
            score += 12
            matched.append(token)
    if tokens and all(any(_field_contains_token(field, token) for field in normalized_fields) for token in tokens):
        score += 25
    return score, sorted(set(matched))


def _search_item_from_definition(
    definition,
    *,
    score: float = 0.0,
    matched_terms: list[str] | None = None,
    response: MacroSeriesResponse | None = None,
) -> MacroSeriesSearchItem:
    quality = response.data_quality if response else MacroDataQuality(status="ok", provider="registry", notes=["Registry metadata only."])
    return MacroSeriesSearchItem(
        series_id=definition.series_id,
        display_name=definition.display_name,
        category=definition.category,
        subcategory=definition.subcategory,
        provider=response.provider if response else definition.provider,
        country=definition.country,
        frequency=definition.frequency,
        unit=definition.unit,
        importance=definition.importance,
        description=definition.description,
        interpretation_hint=definition.interpretation_hint,
        aliases=_series_aliases(definition)[:12],
        matched_terms=matched_terms or [],
        score=round(float(score), 3),
        latest=response.latest if response else None,
        changes=response.changes if response else {},
        data_quality=quality,
    )


def search_macro_series(
    query: str = "",
    *,
    limit: int = 12,
    include_disabled: bool = False,
) -> MacroSeriesSearchResponse:
    tokens = _query_tokens(query)
    scored: list[tuple[float, list[str], Any]] = []
    for definition in _list_macro_series(include_disabled=include_disabled):
        score, matched = _score_definition(definition, query, tokens)
        if tokens and score <= _IMPORTANCE_BONUS.get(definition.importance, 1.0):
            continue
        if len(tokens) > 1 and not all(token in matched for token in tokens) and score < 45:
            continue
        scored.append((score, matched, definition))
    scored.sort(key=lambda row: (-row[0], row[2].category, row[2].display_name))
    selected = scored[: max(1, int(limit or 12))]

    items: list[MacroSeriesSearchItem] = []
    qualities: list[MacroDataQuality] = []
    for score, matched, definition in selected:
        response: MacroSeriesResponse | None = None
        try:
            response = get_macro_series(definition.series_id)
            qualities.append(response.data_quality)
        except Exception:  # noqa: BLE001
            response = None
        items.append(_search_item_from_definition(definition, score=score, matched_terms=matched, response=response))
    quality = aggregate_quality(qualities, provider="macro_search") if qualities else MacroDataQuality(status="ok", provider="registry")
    return MacroSeriesSearchResponse(
        status="success",
        query=str(query or ""),
        count=len(items),
        items=items,
        data_quality=quality,
    )


def _series_statistics(series: MacroSeriesResponse) -> dict[str, Any]:
    observations = [item for item in series.observations if item.value is not None]
    values = [float(item.value) for item in observations]
    if not observations or not values:
        return {
            "observation_count": 0,
            "start_date": None,
            "end_date": None,
            "min": None,
            "max": None,
            "average": None,
            "latest_value": None,
            "latest_date": None,
        }
    return {
        "observation_count": len(observations),
        "start_date": observations[0].date,
        "end_date": observations[-1].date,
        "min": min(values),
        "max": max(values),
        "average": sum(values) / len(values),
        "latest_value": observations[-1].value,
        "latest_date": observations[-1].date,
        "change_1_period": series.changes.get("change_1_period"),
        "change_3_period": series.changes.get("change_3_period"),
        "change_12_period": series.changes.get("change_12_period"),
        "percent_change_1_period": series.changes.get("percent_change_1_period"),
    }


def _series_interpretation(definition, series: MacroSeriesResponse, statistics: dict[str, Any]) -> dict[str, Any]:
    latest = series.latest
    change_1 = series.changes.get("change_1_period")
    change_3 = series.changes.get("change_3_period")
    direction = "flat"
    if isinstance(change_3, (int, float)) and abs(float(change_3)) > 1e-9:
        direction = "rising" if float(change_3) > 0 else "falling"
    elif isinstance(change_1, (int, float)) and abs(float(change_1)) > 1e-9:
        direction = "rising" if float(change_1) > 0 else "falling"
    if latest and latest.value is not None:
        latest_text = f"{definition.display_name} latest is {latest.value:.3f} {definition.unit} as of {latest.date}."
    else:
        latest_text = f"{definition.display_name} has no usable latest observation in the current data mart/provider path."
    trend_text = {
        "rising": "최근 관측치 기준으로 상승 방향입니다.",
        "falling": "최근 관측치 기준으로 하락 방향입니다.",
        "flat": "최근 관측치 변화가 제한적이거나 계산할 관측치가 부족합니다.",
    }[direction]
    return {
        "latest_summary": latest_text,
        "trend": direction,
        "trend_summary": trend_text,
        "macro_use": definition.interpretation_hint or definition.description,
        "data_caveat": (
            "데이터 품질이 ok가 아니므로 레짐/포트폴리오 해석에서는 신호 강도를 낮춰야 합니다."
            if series.data_quality.status != "ok"
            else "데이터 품질은 현재 ok입니다."
        ),
        "observed_range": (
            f"{statistics.get('start_date')} to {statistics.get('end_date')}"
            if statistics.get("start_date") and statistics.get("end_date")
            else "not available"
        ),
    }


def _component_ids_for(definition) -> list[str]:
    if definition.series_id in _COMPONENT_SERIES:
        return _COMPONENT_SERIES[definition.series_id]
    if definition.category == "inflation":
        return [item.series_id for item in series_by_category("inflation") if item.series_id != definition.series_id][:8]
    if definition.category == "interest_rates":
        return ["FEDFUNDS", "DGS2", "DGS10", "DGS30", "T10Y2Y", "DFII10"]
    if definition.category == "labor":
        return ["UNRATE", "U6RATE", "PAYEMS", "ICSA", "JTSJOL", "CES0500000003"]
    if definition.category == "growth":
        return ["GDPC1", "INDPRO", "RSAFS", "UMCSENT", "TCU", "DGORDER"]
    return []


def _related_search_items(definition, *, exclude: set[str], limit: int = 8) -> list[MacroSeriesSearchItem]:
    candidates = [
        item
        for item in _list_macro_series()
        if item.series_id not in exclude and (item.category == definition.category or item.subcategory == definition.subcategory)
    ]
    candidates.sort(key=lambda item: (_IMPORTANCE_BONUS.get(item.importance, 0.0) * -1, item.display_name))
    out: list[MacroSeriesSearchItem] = []
    for candidate in candidates[:limit]:
        try:
            response = get_macro_series(candidate.series_id)
        except Exception:  # noqa: BLE001
            response = None
        out.append(_search_item_from_definition(candidate, score=0.0, matched_terms=["related"], response=response))
    return out


def get_macro_series_detail(series_id: str, *, observation_limit: int = 240) -> MacroSeriesDetailResponse:
    definition = get_series_definition(series_id)
    series = get_macro_series(definition.series_id)
    statistics = _series_statistics(series)
    limit = max(0, int(observation_limit or 0))
    limited_series = series.model_copy(
        deep=True,
        update={"observations": series.observations[-limit:] if limit else []},
    )
    component_items: list[MacroSeriesSearchItem] = []
    exclude = {definition.series_id}
    for component_id in _component_ids_for(definition):
        try:
            component_def = get_series_definition(component_id)
        except KeyError:
            continue
        exclude.add(component_def.series_id)
        try:
            component_response = get_macro_series(component_def.series_id)
        except Exception:  # noqa: BLE001
            component_response = None
        component_items.append(
            _search_item_from_definition(
                component_def,
                score=0.0,
                matched_terms=["component"],
                response=component_response,
            )
        )
    related_items = _related_search_items(definition, exclude=exclude, limit=8)
    return MacroSeriesDetailResponse(
        status="success",
        definition=definition,
        series=limited_series,
        statistics=statistics,
        interpretation=_series_interpretation(definition, series, statistics),
        component_series=component_items,
        related_series=related_items,
        data_quality=series.data_quality,
    )


def _compact_series_payload(item: Any, *, observation_limit: int = 0) -> dict[str, Any]:
    payload = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {})
    observations = payload.get("observations")
    if isinstance(observations, list):
        if observation_limit <= 0:
            payload["observations"] = []
        else:
            payload["observations"] = observations[-observation_limit:]
    return payload


def compact_macro_payload(payload: Any, *, observation_limit: int = 0) -> dict[str, Any]:
    out = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else dict(payload or {})
    limit = max(0, int(observation_limit or 0))
    for key in ("key_indicators", "items"):
        rows = out.get(key)
        if isinstance(rows, list):
            out[key] = [_compact_series_payload(item, observation_limit=limit) for item in rows]
    return out


def get_macro_series(series_id: str, *, start_date: str | None = None, end_date: str | None = None) -> MacroSeriesResponse:
    definition = get_series_definition(series_id)
    cache_key = (_cache_key(), definition.series_id, start_date, end_date)
    cached = _SERIES_CACHE.get(cache_key)
    now = _cache_time()
    if cached and now - cached[0] <= _SERIES_CACHE_TTL_S:
        return cached[1].model_copy(deep=True)
    raw_result = _fetch_raw_series(definition, start_date=start_date, end_date=end_date)
    observations, transform_errors = apply_transform(definition, raw_result.observations)
    quality = evaluate_series_quality(definition, observations, raw_result.data_quality, transform_errors=transform_errors)
    latest = observations[-1] if observations else None
    response = MacroSeriesResponse(
        series_id=definition.series_id,
        display_name=definition.display_name,
        category=definition.category,
        unit=definition.unit,
        frequency=definition.frequency,
        provider=raw_result.provider,
        observations=observations,
        latest=latest,
        changes=compute_changes(observations),
        data_quality=quality,
    )
    _SERIES_CACHE[cache_key] = (now, response.model_copy(deep=True))
    return response


def _series_map(series_ids: list[str] | None = None) -> dict[str, MacroSeriesResponse]:
    ids = series_ids or [item.series_id for item in _list_macro_series()]
    out: dict[str, MacroSeriesResponse] = {}
    for series_id in ids:
        try:
            out[series_id] = get_macro_series(series_id)
        except KeyError:
            continue
    return out


def _summary_raw_limit(definition, observation_limit: int = 0) -> int:
    requested = max(0, int(observation_limit or 0))
    if str(definition.transform or "").lower() == "yoy_percent":
        freq = str(definition.frequency or "").lower()
        period = 4 if "quarter" in freq else (52 if "week" in freq else (252 if "daily" in freq else 12))
        return max(period + requested + 12, 36)
    return max(requested + 12, 30)


def _summary_series_response(definition, *, observation_limit: int = 0) -> MacroSeriesResponse:
    rows = repository.recent_macro_observations(definition.series_id, limit=_summary_raw_limit(definition, observation_limit))
    provider = str(rows[-1].get("source") or "data_mart") if rows else "data_mart"
    raw_observations = [
        MacroObservation(
            date=str(row.get("date") or ""),
            value=row.get("value"),
            raw_value=row.get("value"),
            source=str(row.get("source") or provider),
            metadata={"collected_at": row.get("collected_at")},
        )
        for row in rows
    ]
    provider_quality = MacroDataQuality(
        status="ok" if raw_observations else "unavailable",
        provider=provider,
        last_updated=str(rows[-1].get("collected_at") or rows[-1].get("date") or "") if rows else None,
        missing_series=[] if raw_observations else [definition.series_id],
    )
    observations, transform_errors = apply_transform(definition, raw_observations)
    quality = evaluate_series_quality(definition, observations, provider_quality, transform_errors=transform_errors)
    latest = observations[-1] if observations else None
    limit = max(0, int(observation_limit or 0))
    return MacroSeriesResponse(
        series_id=definition.series_id,
        display_name=definition.display_name,
        category=definition.category,
        unit=definition.unit,
        frequency=definition.frequency,
        provider=provider,
        observations=observations[-limit:] if limit else [],
        latest=latest,
        changes=compute_changes(observations),
        data_quality=quality,
    )


def _series_group_summary(category: str, definitions, *, observation_limit: int = 0) -> dict[str, Any]:
    items = [_summary_series_response(definition, observation_limit=observation_limit) for definition in definitions]
    return {
        "status": "success",
        "category": category,
        "count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
        "data_quality": aggregate_quality(items, provider="macro_category").model_dump(mode="json"),
    }


def get_macro_category_summary(category: str, *, observation_limit: int = 0) -> dict[str, Any]:
    slug = normalize_category(category)
    definitions = series_by_category(slug)
    if not definitions:
        raise KeyError(slug)
    return _series_group_summary(slug, definitions, observation_limit=observation_limit)


def get_growth_labor_summary(*, observation_limit: int = 0) -> dict[str, Any]:
    definitions = [*series_by_category("growth"), *series_by_category("labor")]
    return _series_group_summary("growth_labor", definitions, observation_limit=observation_limit)


def get_yield_curve_summary(*, observation_limit: int = 0) -> dict[str, Any]:
    ids = ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS7", "DGS10", "DGS30", "T10Y2Y", "T10Y3M", "DFII10"]
    definitions = [get_series_definition(series_id) for series_id in ids]
    return _series_group_summary("yield_curve", definitions, observation_limit=observation_limit)


def get_macro_category(category: str) -> dict[str, Any]:
    slug = normalize_category(category)
    definitions = series_by_category(slug)
    if not definitions:
        raise KeyError(slug)
    items = [get_macro_series(item.series_id) for item in definitions]
    return {
        "status": "success",
        "category": slug,
        "count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
        "data_quality": aggregate_quality(items, provider="macro_category").model_dump(mode="json"),
    }


def get_interest_rates() -> dict[str, Any]:
    return get_macro_category("interest_rates")


def get_inflation() -> dict[str, Any]:
    return get_macro_category("inflation")


def get_growth_labor() -> dict[str, Any]:
    items = [get_macro_series(item.series_id) for item in [*series_by_category("growth"), *series_by_category("labor")]]
    return {
        "status": "success",
        "category": "growth_labor",
        "count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
        "data_quality": aggregate_quality(items, provider="macro_category").model_dump(mode="json"),
    }


def get_yield_curve() -> dict[str, Any]:
    ids = ["DGS3MO", "DGS1", "DGS2", "DGS5", "DGS7", "DGS10", "DGS30", "T10Y2Y", "T10Y3M", "DFII10"]
    items = [get_macro_series(item) for item in ids]
    return {
        "status": "success",
        "category": "yield_curve",
        "count": len(items),
        "items": [item.model_dump(mode="json") for item in items],
        "data_quality": aggregate_quality(items, provider="macro_category").model_dump(mode="json"),
    }


def _empty_category(category: str, missing_series: list[str], note: str) -> dict[str, Any]:
    return {
        "status": "success",
        "category": category,
        "count": 0,
        "items": [],
        "data_quality": MacroDataQuality(
            status="unavailable",
            provider="registry",
            missing_series=missing_series,
            notes=[note],
        ).model_dump(mode="json"),
    }


def get_fx_dollar() -> dict[str, Any]:
    try:
        return get_macro_category("fx_dollar")
    except KeyError:
        return _empty_category("fx_dollar", ["DTWEXBGS", "DEXUSEU", "DEXJPUS", "DEXKOUS", "ECOS_USDKRW", "YAHOO_DXY_PROXY"], "FX/dollar provider entries are not enabled; no fake data returned.")


def get_commodities() -> dict[str, Any]:
    try:
        return get_macro_category("commodities")
    except KeyError:
        return _empty_category("commodities", ["DCOILWTICO", "DHHNGSP", "DCOILBRENTEU", "YAHOO_GLD", "YAHOO_USO"], "Commodity provider entries are not enabled; no fake data returned.")


def get_housing_consumer() -> dict[str, Any]:
    return get_macro_category("housing_consumer")


def get_financial_conditions() -> dict[str, Any]:
    return get_macro_category("financial_conditions")


def get_macro_overview(*, regime_engine: str = "rules") -> MacroOverview:
    engine = str(regime_engine or "rules").strip().lower()
    cache_key = f"{_cache_key()}|engine:{engine}"
    now = _cache_time()
    cached = _OVERVIEW_CACHE.get(cache_key)
    if cached and now - cached[0] <= _OVERVIEW_CACHE_TTL_S:
        return cached[1].model_copy(deep=True)
    needed = sorted(set([*KEY_INDICATOR_IDS, *REGIME_INPUT_IDS]))
    series = _series_map(needed)
    regime, signals = classify_macro_regime(series, engine=engine)
    key_indicators = [series[item] for item in KEY_INDICATOR_IDS if item in series]
    quality = aggregate_quality(list(series.values()), provider="macro_overview")
    overview = MacroOverview(
        as_of=_now_iso(),
        key_indicators=key_indicators,
        signals=signals,
        regime=regime,
        asset_impact_summary=get_asset_impacts(regime, signals),
        data_quality=quality,
    )
    _OVERVIEW_CACHE[cache_key] = (now, overview.model_copy(deep=True))
    return overview


def get_macro_regime(*, engine: str = "rules") -> dict[str, Any]:
    selected_engine = str(engine or "rules").strip().lower()
    if selected_engine not in {"rules", "factor"}:
        selected_engine = "rules"
    overview = get_macro_overview(regime_engine=selected_engine)
    return {
        "status": "success",
        "engine": selected_engine,
        "regime": overview.regime.model_dump(mode="json"),
        "signals": [item.model_dump(mode="json") for item in overview.signals],
        "data_quality": overview.data_quality.model_dump(mode="json"),
    }


def get_asset_impact() -> dict[str, Any]:
    overview = get_macro_overview()
    impacts = get_asset_impacts(overview.regime, overview.signals)
    return {
        "status": "success",
        "items": [item.model_dump(mode="json") for item in impacts],
        "count": len(impacts),
        "data_quality": overview.data_quality.model_dump(mode="json"),
    }


def get_portfolio_policy_hints():
    overview = get_macro_overview()
    return get_portfolio_policy_hint(overview.regime, overview.data_quality)


def get_macro_research_context(ticker: str | None = None):
    return get_research_context(get_macro_overview(), ticker=ticker)


def generate_macro_brief(
    *,
    include_prompt: bool = False,
    use_llm: bool = False,
    model: str | None = None,
    timeout_s: float = 45.0,
) -> MacroBriefResponse:
    return generate_brief(
        get_macro_overview(),
        include_prompt=include_prompt,
        use_llm=use_llm,
        model=model,
        timeout_s=timeout_s,
    )


def _generate_macro_report_legacy() -> MacroReportResponse:
    overview = get_macro_overview()
    impacts = get_asset_impacts(overview.regime, overview.signals)
    hint = get_portfolio_policy_hint(overview.regime, overview.data_quality)
    context = get_research_context(overview)
    brief = generate_brief(overview, include_prompt=False, use_llm=False)
    generated_at = _now_iso()
    warnings = [
        "리포트는 구조화된 Macro payload와 규칙 기반 폴백 브리프에서 생성됩니다.",
        "포트폴리오 정책 힌트는 자문 전용이며 주문을 생성하지 않습니다.",
    ]
    if overview.data_quality.status != "ok":
        warnings.append(f"매크로 데이터 품질은 {overview.data_quality.status}이며 누락/지연 데이터는 불확실성으로 남습니다.")
    content = "\n".join(
        [
            "# FinGPT 매크로 리포트",
            "",
            f"- 생성 시각: {generated_at}",
            f"- 데이터 품질: {overview.data_quality.status}",
            f"- 레짐: {overview.regime.display_name} ({overview.regime.name})",
            f"- 신뢰도: {overview.regime.confidence:.2f}",
            f"- 위험 수준: {overview.regime.risk_level}",
            "",
            "## 핵심 지표",
            "",
            "| 시계열 | 최근값 | 날짜 | 품질 | 공급자 |",
            "|---|---:|---|---|---|",
            *[
                (
                    f"| {item.series_id} - {item.display_name} | "
                    f"{item.latest.value if item.latest and item.latest.value is not None else '사용 불가'} {item.unit} | "
                    f"{item.latest.date if item.latest else '사용 불가'} | "
                    f"{item.data_quality.status} | {item.provider} |"
                )
                for item in overview.key_indicators
            ],
            "",
            "## 신호",
            "",
            "| 신호 | 값 | 점수 | 신뢰도 | 증거 |",
            "|---|---|---:|---:|---|",
            *[
                f"| {item.name} | {item.value} | {item.score:.1f} | {item.confidence:.2f} | {'; '.join(item.evidence[:3]) or '데이터 부족'} |"
                for item in overview.signals
            ],
            "",
            "## 레짐 해석",
            "",
            overview.regime.interpretation or "입력이 부족해 레짐 해석을 보류합니다.",
            "",
            "## 자산군 영향",
            "",
            "| 자산군 | 영향 | 신뢰도 | 근거 | 핵심 리스크 |",
            "|---|---|---:|---|---|",
            *[
                f"| {item.asset_class} | {item.impact} | {item.confidence:.2f} | {item.reason} | {'; '.join(item.key_risks) or '-'} |"
                for item in impacts
            ],
            "",
            "## 포트폴리오 정책 힌트",
            "",
            f"- 자문 전용: {hint.advisory_only}",
            f"- 주식 편향: {hint.equity_bias}",
            f"- 채권 편향: {hint.bond_bias}",
            f"- 현금 편향: {hint.cash_bias}",
            f"- 듀레이션 편향: {hint.duration_bias}",
            f"- 신용 편향: {hint.credit_bias}",
            f"- 위험 수준: {hint.risk_level}",
            f"- 리밸런싱 주의: {hint.rebalance_attention}",
            f"- 설명: {hint.explanation}",
            "",
            "## 리서치 맥락",
            "",
            f"- 티커 관련 항목: {', '.join(sorted(context.ticker_relevance.keys()))}",
            f"- 데이터 품질 경고: {', '.join(context.data_quality_warnings[:20]) or '없음'}",
            "",
            "## AI 매크로 브리프",
            "",
            brief.content,
            "",
            "## 데이터 품질",
            "",
            f"- 누락 시계열: {', '.join(overview.data_quality.missing_series) or '없음'}",
            f"- 지연 시계열: {', '.join(overview.data_quality.stale_series) or '없음'}",
            f"- 오류: {', '.join(overview.data_quality.errors) or '없음'}",
            f"- 메모: {', '.join(overview.data_quality.notes[:20]) or '없음'}",
        ]
    )
    return MacroReportResponse(
        status="success",
        generated_at=generated_at,
        filename=f"fingpt_macro_report_{generated_at.replace(':', '').replace('-', '')}.md",
        content=content,
        data_quality=overview.data_quality,
        warnings=warnings,
    )


def generate_macro_report() -> MacroReportResponse:
    overview = get_macro_overview()
    impacts = get_asset_impacts(overview.regime, overview.signals)
    hint = get_portfolio_policy_hint(overview.regime, overview.data_quality)
    context = get_research_context(overview)
    brief = generate_brief(overview, include_prompt=False, use_llm=False)
    generated_at = _now_iso()
    warnings = [
        "이 리포트는 구조화된 Macro payload와 규칙 기반 브리프에서 생성되었습니다.",
        "포트폴리오 힌트는 자문용이며 주문을 생성하지 않습니다.",
    ]
    if overview.data_quality.status != "ok":
        warnings.append(f"매크로 데이터 품질은 {overview.data_quality.status}입니다. 누락 또는 지연 데이터는 불확실성으로 처리해야 합니다.")
    content = "\n".join(
        [
            "# FinGPT 매크로 리포트",
            "",
            f"- 생성 시각: {generated_at}",
            f"- 데이터 품질: {overview.data_quality.status}",
            f"- 레짐: {overview.regime.display_name} ({overview.regime.name})",
            f"- 신뢰도: {overview.regime.confidence:.2f}",
            f"- 위험 수준: {overview.regime.risk_level}",
            "",
            "## 핵심 지표",
            "",
            "| 시계열 | 최근값 | 날짜 | 품질 | 공급자 |",
            "|---|---:|---|---|---|",
            *[
                (
                    f"| {item.series_id} - {item.display_name} | "
                    f"{item.latest.value if item.latest and item.latest.value is not None else '사용 불가'} {item.unit} | "
                    f"{item.latest.date if item.latest else '사용 불가'} | "
                    f"{item.data_quality.status} | {item.provider} |"
                )
                for item in overview.key_indicators
            ],
            "",
            "## 신호",
            "",
            "| 신호 | 값 | 점수 | 신뢰도 | 근거 |",
            "|---|---|---:|---:|---|",
            *[
                f"| {item.name} | {item.value} | {item.score:.1f} | {item.confidence:.2f} | {'; '.join(item.evidence[:3]) or '데이터 부족'} |"
                for item in overview.signals
            ],
            "",
            "## 레짐 해석",
            "",
            overview.regime.interpretation or "입력이 부족해 레짐 해석을 보류합니다.",
            "",
            "## 자산군 영향",
            "",
            "| 자산군 | 영향 | 신뢰도 | 근거 | 핵심 리스크 |",
            "|---|---|---:|---|---|",
            *[
                f"| {item.asset_class} | {item.impact} | {item.confidence:.2f} | {item.reason} | {'; '.join(item.key_risks) or '-'} |"
                for item in impacts
            ],
            "",
            "## 포트폴리오 정책 힌트",
            "",
            f"- 자문 전용: {hint.advisory_only}",
            f"- 주식 성향: {hint.equity_bias}",
            f"- 채권 성향: {hint.bond_bias}",
            f"- 현금 성향: {hint.cash_bias}",
            f"- 듀레이션 성향: {hint.duration_bias}",
            f"- 신용 성향: {hint.credit_bias}",
            f"- 위험 수준: {hint.risk_level}",
            f"- 리밸런싱 주의: {hint.rebalance_attention}",
            f"- 설명: {hint.explanation}",
            "",
            "## 리서치 맥락",
            "",
            f"- 티커 관련 항목: {', '.join(sorted(context.ticker_relevance.keys()))}",
            f"- 데이터 품질 경고: {', '.join(context.data_quality_warnings[:20]) or '없음'}",
            "",
            "## AI 매크로 브리프",
            "",
            brief.content,
            "",
            "## 데이터 품질",
            "",
            f"- 누락 시계열: {', '.join(overview.data_quality.missing_series) or '없음'}",
            f"- 지연 시계열: {', '.join(overview.data_quality.stale_series) or '없음'}",
            f"- 오류: {', '.join(overview.data_quality.errors) or '없음'}",
            f"- 메모: {', '.join(overview.data_quality.notes[:20]) or '없음'}",
        ]
    )
    return MacroReportResponse(
        status="success",
        generated_at=generated_at,
        filename=f"fingpt_macro_report_{generated_at.replace(':', '').replace('-', '')}.md",
        content=content,
        data_quality=overview.data_quality,
        warnings=warnings,
    )


def _series_freshness_quality(definition, row: dict[str, Any] | None, *, now: datetime) -> MacroDataQuality:
    provider = str(row.get("source") or "data_mart") if row else "data_mart"
    if not row:
        return MacroDataQuality(
            status="unavailable",
            provider=provider,
            missing_series=[definition.series_id],
            notes=["No cached macro observation is available."],
        )
    latest_date = str(row.get("date") or "")
    latest_dt = _parse_observation_date(latest_date)
    errors: list[str] = []
    notes: list[str] = []
    stale_series: list[str] = []
    status = "ok"
    if latest_dt is None:
        status = "partial"
        errors.append(f"invalid latest date for {definition.series_id}: {latest_date}")
    else:
        age_days = (now - latest_dt).days
        if age_days > definition.stale_after_days:
            status = "stale"
            stale_series.append(definition.series_id)
            notes.append(
                f"{definition.series_id} latest observation is {age_days} days old "
                f"(threshold {definition.stale_after_days} days)."
            )
    return MacroDataQuality(
        status=status,
        provider=provider,
        last_updated=str(row.get("collected_at") or latest_date or ""),
        stale_series=stale_series,
        errors=errors,
        notes=notes,
    )


def _data_quality_row(definition, row: dict[str, Any] | None, quality: MacroDataQuality) -> dict[str, Any]:
    return {
        "series_id": definition.series_id,
        "display_name": definition.display_name,
        "category": definition.category,
        "subcategory": definition.subcategory,
        "status": quality.status,
        "latest_date": row.get("date") if row else None,
        "last_updated": quality.last_updated,
        "provider": quality.provider,
        "source": row.get("source") if row else None,
        "frequency": definition.frequency,
        "stale_after_days": definition.stale_after_days,
        "errors": quality.errors,
        "notes": quality.notes,
    }


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for row in rows if row.get("status") == status) for status in ["ok", "partial", "stale", "unavailable"]}


def get_data_quality(*, include_disabled: bool = False, scope: str = "all") -> dict[str, Any]:
    selected_scope = str(scope or "all").strip().lower()
    if selected_scope == "overview":
        overview = get_macro_overview()
        rows = [
            {
                "series_id": item.series_id,
                "display_name": item.display_name,
                "category": item.category,
                "status": item.data_quality.status,
                "latest_date": item.latest.date if item.latest else None,
                "last_updated": item.data_quality.last_updated,
                "provider": item.provider,
                "errors": item.data_quality.errors,
                "notes": item.data_quality.notes,
            }
            for item in overview.key_indicators
        ]
        return {
            "status": overview.data_quality.status,
            "scope": "overview",
            "data_quality": overview.data_quality.model_dump(mode="json"),
            "coverage": {
                "registry_series": len(_list_macro_series(include_disabled=include_disabled)),
                "evaluated_series": len(rows),
                "status_counts": _status_counts(rows),
            },
            "series": rows,
        }

    definitions = _list_macro_series(include_disabled=include_disabled)
    latest_by_id = repository.latest_macros([definition.series_id for definition in definitions])
    now = datetime.now(timezone.utc)
    qualities: list[MacroDataQuality] = []
    rows: list[dict[str, Any]] = []
    for definition in definitions:
        row = latest_by_id.get(definition.series_id)
        quality = _series_freshness_quality(definition, row, now=now)
        qualities.append(quality)
        rows.append(_data_quality_row(definition, row, quality))
    aggregate = aggregate_quality(qualities, provider="macro_registry")
    counts = _status_counts(rows)
    return {
        "status": aggregate.status,
        "scope": "all",
        "data_quality": aggregate.model_dump(mode="json"),
        "coverage": {
            "registry_series": len(definitions),
            "evaluated_series": len(rows),
            "status_counts": counts,
            "ok_series": counts.get("ok", 0),
            "stale_series": counts.get("stale", 0),
            "partial_series": counts.get("partial", 0),
            "unavailable_series": counts.get("unavailable", 0),
        },
        "series": rows,
    }


def get_provider_metadata() -> dict[str, Any]:
    storage = DataMartMacroProvider()
    live = _live_providers()
    return {
        "status": "success",
        "providers": [
            storage.health_check(),
            *[provider.health_check() for provider in live.values()],
            UnavailableProvider("fallback").health_check(),
        ],
        "registry_providers": provider_names(include_disabled=True),
        "data_quality": MacroDataQuality(status="ok", provider="registry", notes=["Provider metadata only."]).model_dump(mode="json"),
    }


def get_country_metadata() -> dict[str, Any]:
    return {
        "status": "success",
        "countries": country_names(include_disabled=True),
        "data_quality": MacroDataQuality(status="ok", provider="registry", notes=["Country metadata only."]).model_dump(mode="json"),
    }


def get_health() -> dict[str, Any]:
    storage = DataMartMacroProvider()
    live = _live_providers()
    return {
        "status": "ok",
        "registry_series": len(_list_macro_series()),
        "categories": category_names(),
        "data_mart_available": storage.is_available(),
        "providers": {name: provider.is_available() for name, provider in live.items()},
        "data_quality": MacroDataQuality(status="ok", provider="macro_health").model_dump(mode="json"),
    }
