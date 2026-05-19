from __future__ import annotations

import math
from statistics import mean
from typing import Any

from pipelines.data_mart.storage import repository
from pipelines.quantamental.fundamental_engine import clamp


FACTOR_KEYS = (
    "value_score",
    "quality_score",
    "growth_score",
    "momentum_score",
    "low_volatility_score",
    "liquidity_score",
)

GLOBAL_PEER_FALLBACKS = {
    "semiconductor": [
        ("ASML.AS", "ASML Holding N.V.", "Technology", "Semiconductor Equipment & Materials"),
        ("TSM", "Taiwan Semiconductor Manufacturing Company", "Technology", "Semiconductors"),
        ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
        ("AVGO", "Broadcom Inc.", "Technology", "Semiconductors"),
        ("AMAT", "Applied Materials, Inc.", "Technology", "Semiconductor Equipment & Materials"),
        ("LRCX", "Lam Research Corporation", "Technology", "Semiconductor Equipment & Materials"),
    ],
    "technology": [
        ("MSFT", "Microsoft Corporation", "Technology", "Software"),
        ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics"),
        ("NVDA", "NVIDIA Corporation", "Technology", "Semiconductors"),
        ("ASML.AS", "ASML Holding N.V.", "Technology", "Semiconductor Equipment & Materials"),
        ("TSM", "Taiwan Semiconductor Manufacturing Company", "Technology", "Semiconductors"),
    ],
    "healthcare": [
        ("NVO", "Novo Nordisk A/S", "Healthcare", "Biotechnology"),
        ("AZN", "AstraZeneca PLC", "Healthcare", "Drug Manufacturers"),
        ("NVS", "Novartis AG", "Healthcare", "Drug Manufacturers"),
        ("LLY", "Eli Lilly and Company", "Healthcare", "Drug Manufacturers"),
    ],
    "financial": [
        ("HSBC", "HSBC Holdings plc", "Financial Services", "Banks"),
        ("JPM", "JPMorgan Chase & Co.", "Financial Services", "Banks"),
        ("RY", "Royal Bank of Canada", "Financial Services", "Banks"),
        ("UBS", "UBS Group AG", "Financial Services", "Capital Markets"),
    ],
    "energy": [
        ("SHEL", "Shell plc", "Energy", "Oil & Gas Integrated"),
        ("BP", "BP p.l.c.", "Energy", "Oil & Gas Integrated"),
        ("TTE", "TotalEnergies SE", "Energy", "Oil & Gas Integrated"),
        ("XOM", "Exxon Mobil Corporation", "Energy", "Oil & Gas Integrated"),
    ],
}


def apply_peer_relative_scores(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [_summary_row(item) for item in analyses if isinstance(item, dict)]
    valid_rows = [row for row in rows if row["status"] not in {"failed"}]
    for row in rows:
        row["peer_relative"] = _empty_peer(row, "not_enough_peer_data")
    if len(valid_rows) < 2:
        return {
            "status": "partial",
            "method": "peer_relative_percentile_v1",
            "factor_keys": list(FACTOR_KEYS),
            "rows": rows,
            "peer_groups": [],
            "warnings": ["peer_relative_requires_at_least_two_valid_tickers"],
        }

    groups = _choose_groups(valid_rows)
    peer_groups: list[dict[str, Any]] = []
    for group_key, group_rows in groups:
        factor_percentiles = _factor_percentiles(group_rows)
        peer_groups.append(
            {
                "group_key": group_key,
                "peer_count": len(group_rows),
                "tickers": [row["ticker"] for row in group_rows],
                "scope": group_rows[0].get("peer_scope") or "overall",
            }
        )
        for row in group_rows:
            normalized = {key: factor_percentiles.get(key, {}).get(row["ticker"]) for key in FACTOR_KEYS}
            nums = [float(value) for value in normalized.values() if _finite(value) is not None]
            row["peer_relative"] = {
                "status": "ok" if nums else "empty",
                "method": "peer_relative_percentile_v1",
                "group_key": group_key,
                "scope": row.get("peer_scope") or "overall",
                "peer_count": len(group_rows),
                "normalized_factor_scores": normalized,
                "relative_strength_score": round(mean(nums), 2) if nums else None,
                "rank": _rank_for(row, group_rows),
                "warnings": [] if nums else ["peer_factor_values_missing"],
            }

    by_ticker = {row["ticker"]: row for row in rows}
    for analysis in analyses:
        ticker = str(analysis.get("ticker") or "").upper()
        if ticker in by_ticker:
            analysis["peer_relative"] = by_ticker[ticker]["peer_relative"]
    return {
        "status": "ok",
        "method": "peer_relative_percentile_v1",
        "factor_keys": list(FACTOR_KEYS),
        "rows": rows,
        "peer_groups": peer_groups,
        "warnings": [],
    }


def expand_peer_universe(
    requested_tickers: list[str],
    analyses: list[dict[str, Any]],
    *,
    market: str = "US",
    max_total: int = 8,
) -> dict[str, Any]:
    existing: list[str] = []
    seen: set[str] = set()
    for ticker in [*requested_tickers, *[str(item.get("ticker") or "") for item in analyses]]:
        clean = str(ticker or "").upper().strip()
        if clean and clean not in seen:
            seen.add(clean)
            existing.append(clean)
    max_total = max(len(existing), min(20, max(2, int(max_total or 8))))
    added: list[str] = []
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    seed_rows = [_summary_row(item) for item in analyses if isinstance(item, dict)]
    for row in seed_rows:
        if len(existing) + len(added) >= max_total:
            break
        try:
            peer_rows = repository.peer_universe_candidates(
                [*existing, *added],
                market=market,
                sector=str(row.get("sector") or ""),
                industry=str(row.get("industry") or ""),
                limit=max_total - len(existing) - len(added),
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"peer_universe_lookup_failed:{type(exc).__name__}:{exc}")
            break
        for candidate in peer_rows:
            ticker = str(candidate.get("ticker") or "").upper().strip()
            if not ticker or ticker in seen or ticker in added:
                continue
            added.append(ticker)
            candidates.append(candidate)
            if len(existing) + len(added) >= max_total:
                break
    if not added and str(market or "").upper() == "GLOBAL":
        fallback = _global_peer_fallback(existing, seed_rows, max_total=max_total)
        for candidate in fallback:
            ticker = str(candidate.get("ticker") or "").upper().strip()
            if not ticker or ticker in seen or ticker in added:
                continue
            added.append(ticker)
            candidates.append(candidate)
        if added:
            warnings.append("global_peer_universe_static_fallback")
    return {
        "status": "ok" if added else "empty",
        "method": "data_mart_asset_metadata_sector_industry_v1" if "global_peer_universe_static_fallback" not in warnings else "global_static_liquid_peer_seed_v1",
        "requested_tickers": existing,
        "added_tickers": added,
        "max_total": max_total,
        "candidates": candidates,
        "warnings": warnings or ([] if added else ["peer_universe_candidates_not_found"]),
    }


def _global_peer_fallback(existing: list[str], seed_rows: list[dict[str, Any]], *, max_total: int) -> list[dict[str, Any]]:
    slots = max(0, int(max_total or len(existing)) - len(existing))
    if slots <= 0:
        return []
    text = " ".join(
        str(value or "").lower()
        for row in seed_rows
        for value in (row.get("sector"), row.get("industry"), row.get("company_name"), row.get("ticker"))
    )
    key = "technology"
    for candidate_key in GLOBAL_PEER_FALLBACKS:
        if candidate_key in text:
            key = candidate_key
            break
    existing_set = {str(item or "").upper().strip() for item in existing}
    rows: list[dict[str, Any]] = []
    for ticker, name, sector, industry in GLOBAL_PEER_FALLBACKS.get(key, []):
        if ticker in existing_set:
            continue
        rows.append(
            {
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "industry": industry,
                "market": "GLOBAL",
                "currency": "",
                "exchange": "",
                "source": "static_global_liquid_peer_seed_v1",
                "updated_at": "",
            }
        )
        if len(rows) >= slots:
            break
    return rows


def _summary_row(item: dict[str, Any]) -> dict[str, Any]:
    company = item.get("company") or {}
    composite = item.get("composite") or {}
    signal = item.get("signal") or {}
    factors = item.get("factors") or {}
    quality = item.get("data_quality") or {}
    return {
        "ticker": str(item.get("ticker") or company.get("ticker") or "").upper(),
        "market": item.get("market") or company.get("market"),
        "status": item.get("status") or "unknown",
        "company_name": company.get("name"),
        "sector": company.get("sector") or "Unknown Sector",
        "industry": company.get("industry") or "Unknown Industry",
        "final_score": composite.get("final_score"),
        "signal_label": signal.get("signal_label"),
        "data_quality_score": quality.get("data_quality_score"),
        "quality_level": quality.get("quality_level"),
        "factors": {key: factors.get(key) for key in FACTOR_KEYS},
    }


def _choose_groups(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    industry_groups = _group_by(rows, "industry")
    selected: list[tuple[str, list[dict[str, Any]]]] = []
    consumed: set[str] = set()
    for key, group in industry_groups.items():
        if len(group) >= 2 and key != "Unknown Industry":
            for row in group:
                row["peer_scope"] = "industry"
                consumed.add(row["ticker"])
            selected.append((f"industry:{key}", group))
    remaining = [row for row in rows if row["ticker"] not in consumed]
    for key, group in _group_by(remaining, "sector").items():
        if len(group) >= 2 and key != "Unknown Sector":
            for row in group:
                row["peer_scope"] = "sector"
                consumed.add(row["ticker"])
            selected.append((f"sector:{key}", group))
    leftover = [row for row in rows if row["ticker"] not in consumed]
    if len(leftover) >= 2:
        for row in leftover:
            row["peer_scope"] = "overall"
        selected.append(("overall:request", leftover))
    elif leftover and selected:
        group_key, group = selected[0]
        leftover[0]["peer_scope"] = "overall_fallback"
        group.append(leftover[0])
        consumed.add(leftover[0]["ticker"])
        selected[0] = (group_key, group)
    elif leftover:
        leftover[0]["peer_scope"] = "single"
    return selected


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or f"Unknown {key.title()}"), []).append(row)
    return grouped


def _factor_percentiles(rows: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = {}
    for key in FACTOR_KEYS:
        values = [(row["ticker"], _finite((row.get("factors") or {}).get(key))) for row in rows]
        values = [(ticker, value) for ticker, value in values if value is not None]
        if len(values) < 2:
            out[key] = {row["ticker"]: None for row in rows}
            continue
        sorted_values = sorted(values, key=lambda item: item[1])
        percentiles: dict[str, float | None] = {row["ticker"]: None for row in rows}
        for idx, (ticker, _value) in enumerate(sorted_values):
            percentiles[ticker] = round(float(clamp((idx / max(len(sorted_values) - 1, 1)) * 100.0) or 0.0), 2)
        out[key] = percentiles
    return out


def _rank_for(row: dict[str, Any], rows: list[dict[str, Any]]) -> int | None:
    scored = [(item["ticker"], _finite(item.get("final_score"))) for item in rows]
    scored = [(ticker, value) for ticker, value in scored if value is not None]
    if not scored:
        return None
    scored.sort(key=lambda item: item[1], reverse=True)
    for idx, (ticker, _value) in enumerate(scored, start=1):
        if ticker == row["ticker"]:
            return idx
    return None


def _empty_peer(row: dict[str, Any], warning: str) -> dict[str, Any]:
    return {
        "status": "empty",
        "method": "peer_relative_percentile_v1",
        "group_key": None,
        "scope": None,
        "peer_count": 0,
        "normalized_factor_scores": {key: None for key in FACTOR_KEYS},
        "relative_strength_score": None,
        "rank": None,
        "warnings": [warning],
    }


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
