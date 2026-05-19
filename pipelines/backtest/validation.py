from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo


_US_MARKET_TZ = ZoneInfo("America/New_York")
_US_MARKET_OPEN = time(9, 30)


FRESHNESS_PROFILES: dict[str, dict[str, Any]] = {
    "research_default": {
        "require_fresh_prices": False,
        "max_market_calendar_lag_days": 3,
    },
    "decision_review": {
        "require_fresh_prices": True,
        "max_market_calendar_lag_days": 1,
    },
    "historical_lab": {
        "require_fresh_prices": False,
        "max_market_calendar_lag_days": 30,
    },
}


def resolve_freshness_policy_request(request: Any) -> dict[str, Any]:
    """Resolve a request object or dict into explicit validation kwargs."""

    def _value(key: str, default: Any = None) -> Any:
        if isinstance(request, dict):
            return request.get(key, default)
        return getattr(request, key, default)

    profile = str(_value("freshness_profile", "research_default") or "research_default").strip().lower()
    if profile not in FRESHNESS_PROFILES:
        profile = "research_default"
    fields_set = set(request.keys()) if isinstance(request, dict) else set(getattr(request, "model_fields_set", set()))
    profile_defaults = FRESHNESS_PROFILES[profile]
    require_fresh_prices = bool(profile_defaults["require_fresh_prices"])
    max_lag = int(profile_defaults["max_market_calendar_lag_days"])
    if "require_fresh_prices" in fields_set and _value("require_fresh_prices") is not None:
        require_fresh_prices = bool(_value("require_fresh_prices"))
    if "max_market_calendar_lag_days" in fields_set and _value("max_market_calendar_lag_days") is not None:
        max_lag = int(_value("max_market_calendar_lag_days"))
    return {
        "freshness_profile": profile,
        "require_fresh_prices": require_fresh_prices,
        "max_market_calendar_lag_days": max_lag,
    }


def validate_backtest_inputs(
    prices_by_asset: dict[str, list[dict[str, Any]]],
    *,
    signal_shift_bars: int = 1,
    transaction_cost_bps: float = 5.0,
    slippage_bps: float = 2.0,
    freshness_profile: str = "research_default",
    require_fresh_prices: bool = False,
    max_market_calendar_lag_days: int = 3,
) -> dict[str, Any]:
    price_counts = {asset: len(rows) for asset, rows in prices_by_asset.items()}
    missing_assets = [asset for asset, rows in prices_by_asset.items() if not rows]
    insufficient_assets = [asset for asset, rows in prices_by_asset.items() if 0 < len(rows) < 2]
    latest_dates = {
        asset: str(rows[-1].get("date") or "")
        for asset, rows in prices_by_asset.items()
        if rows
    }
    freshness_policy = _freshness_policy(
        freshness_profile=freshness_profile,
        require_fresh_prices=require_fresh_prices,
        max_market_calendar_lag_days=max_market_calendar_lag_days,
    )
    asset_freshness = {
        asset: _asset_freshness(rows, policy=freshness_policy)
        for asset, rows in prices_by_asset.items()
    }
    stale_assets = [
        asset
        for asset, audit in asset_freshness.items()
        if audit.get("freshness_status") == "stale"
    ]
    return {
        "lookahead_safe": signal_shift_bars >= 1,
        "signal_shift_bars": signal_shift_bars,
        "execution_assumption": "next_bar_close",
        "adjusted_price_used": True,
        "missing_price_rows": sum(1 for rows in prices_by_asset.values() if not rows),
        "missing_assets": missing_assets,
        "excluded_assets": insufficient_assets,
        "price_counts": price_counts,
        "latest_dates": latest_dates,
        "expected_latest_date": freshness_policy["expected_latest_date"],
        "market_calendar_lag_days": {
            asset: int(audit.get("market_calendar_lag_days") or 0)
            for asset, audit in asset_freshness.items()
        },
        "stale_assets": stale_assets,
        "strict_freshness_violation": bool(require_fresh_prices and (stale_assets or missing_assets or insufficient_assets)),
        "asset_freshness": asset_freshness,
        "freshness_policy": freshness_policy,
        "cost_model": {
            "transaction_cost_bps": float(transaction_cost_bps),
            "slippage_bps": float(slippage_bps),
        },
    }


def _freshness_policy(
    *,
    freshness_profile: str = "research_default",
    require_fresh_prices: bool = False,
    max_market_calendar_lag_days: int = 3,
) -> dict[str, Any]:
    expected = _current_expected_market_date()
    max_lag = max(0, int(max_market_calendar_lag_days))
    return {
        "policy_id": f"daily_price_t_plus_{max_lag}_market_days",
        "profile": freshness_profile,
        "source": "data_mart:prices_daily",
        "expected_latest_date": expected.isoformat(),
        "max_market_calendar_lag_days": max_lag,
        "require_fresh_prices": bool(require_fresh_prices),
        "missing_states": [
            "missing_asset",
            "insufficient_history",
            "stale_price",
            "provider_empty",
            "provider_failed",
        ],
    }


def _asset_freshness(rows: list[dict[str, Any]], *, policy: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return {
            "freshness_status": "unknown",
            "latest_price_date": "unknown",
            "expected_latest_date": policy["expected_latest_date"],
            "market_calendar_lag_days": 0,
            "missing_reason": "missing_asset",
        }
    latest = str(rows[-1].get("date") or "")[:10]
    try:
        observed = date.fromisoformat(latest)
        expected = date.fromisoformat(str(policy["expected_latest_date"]))
    except ValueError:
        return {
            "freshness_status": "unknown",
            "latest_price_date": latest or "unknown",
            "expected_latest_date": policy["expected_latest_date"],
            "market_calendar_lag_days": 0,
            "missing_reason": "unparseable_price_date",
        }
    lag_days = _market_day_lag(observed, expected)
    status = "fresh" if lag_days <= int(policy["max_market_calendar_lag_days"]) else "stale"
    return {
        "freshness_status": status,
        "latest_price_date": observed.isoformat(),
        "expected_latest_date": expected.isoformat(),
        "market_calendar_lag_days": lag_days,
        "missing_reason": "" if status == "fresh" else "stale_price",
    }


def _expected_market_date(today: date) -> date:
    expected = today
    while expected.weekday() >= 5:
        expected = date.fromordinal(expected.toordinal() - 1)
    return expected


def _current_expected_market_date(now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    now_ny = current.astimezone(_US_MARKET_TZ)
    candidate = now_ny.date()
    if candidate.weekday() >= 5 or now_ny.time() < _US_MARKET_OPEN:
        return _previous_market_date(candidate)
    return candidate


def _previous_market_date(day: date) -> date:
    expected = date.fromordinal(day.toordinal() - 1)
    while expected.weekday() >= 5:
        expected = date.fromordinal(expected.toordinal() - 1)
    return expected


def _market_day_lag(observed: date, expected: date) -> int:
    if observed >= expected:
        return 0
    lag = 0
    cursor = observed
    while cursor < expected:
        cursor = date.fromordinal(cursor.toordinal() + 1)
        if cursor.weekday() < 5:
            lag += 1
    return lag
