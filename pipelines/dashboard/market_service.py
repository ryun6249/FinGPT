from __future__ import annotations

import asyncio
import copy
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.schemas.dashboard import (
    MarketDashboardFreshnessSummary,
    MarketDashboardHeatmapSummary,
    MarketDashboardOverview,
    MarketDashboardSignal,
    MarketTapeItem,
)
from core.utils.logger import get_logger
from pipelines.data_mart.storage.repository import (
    acquire_dashboard_refresh_lock,
    get_dashboard_snapshot,
    release_dashboard_refresh_lock,
    upsert_dashboard_snapshot,
)


logger = get_logger("pipelines.dashboard.market")

MARKET_SNAPSHOT_CACHE_TTL_SEC = 45
MARKET_SNAPSHOT_CACHE_KEY = "market_dashboard_market_snapshot_v1"
MARKET_SNAPSHOT_REFRESH_LOCK_KEY = "market_dashboard_market_snapshot_refresh_v1"
MARKET_SNAPSHOT_REFRESH_LOCK_TTL_SEC = 30
MARKET_SNAPSHOT_REFRESH_WAIT_SEC = 8.0
MARKET_SNAPSHOT_SYMBOLS: list[dict[str, str]] = [
    {"symbol": "SPY", "label": "S&P 500", "asset_class": "equity_index"},
    {"symbol": "QQQ", "label": "Nasdaq 100", "asset_class": "equity_index"},
    {"symbol": "TLT", "label": "Long Treasury", "asset_class": "rates_bonds"},
    {"symbol": "HYG", "label": "High Yield Credit", "asset_class": "credit"},
    {"symbol": "LQD", "label": "IG Credit", "asset_class": "credit"},
    {"symbol": "GLD", "label": "Gold", "asset_class": "commodity"},
    {"symbol": "BTC-USD", "label": "Bitcoin", "asset_class": "crypto"},
    {"symbol": "DX-Y.NYB", "label": "DXY", "asset_class": "fx"},
    {"symbol": "^TNX", "label": "US 10Y Yield", "asset_class": "rates"},
]

_market_snapshot_cache: dict[str, Any] = {"ts": 0.0, "payload": None}


def clear_market_snapshot_cache() -> None:
    _market_snapshot_cache["ts"] = 0.0
    _market_snapshot_cache["payload"] = None


def market_freshness_is_decision_usable(status: Any) -> bool:
    return str(status or "").lower() in {"fresh", "delayed", "closed"}


def _previous_business_day(value: Any) -> Any:
    day = value
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _expected_latest_us_market_date(now_ny: datetime) -> Any:
    today = now_ny.date()
    if now_ny.weekday() >= 5:
        return _previous_business_day(today - timedelta(days=1))
    if now_ny.time() < dt_time(9, 30):
        return _previous_business_day(today - timedelta(days=1))
    return today


def us_market_freshness(as_of: str) -> dict[str, Any]:
    try:
        latest = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
    except Exception:
        return {"freshness_status": "unknown", "age_minutes": None, "is_intraday": False}

    ny_tz = ZoneInfo("America/New_York")
    latest_ny = latest.astimezone(ny_tz) if latest.tzinfo else latest.replace(tzinfo=ny_tz)
    now_ny = datetime.now(ny_tz)
    age_minutes = max(0.0, round((now_ny - latest_ny).total_seconds() / 60.0, 1))
    expected_date = _expected_latest_us_market_date(now_ny)
    market_open = now_ny.weekday() < 5 and dt_time(9, 30) <= now_ny.time() <= dt_time(16, 15)
    is_intraday = latest_ny.date() == expected_date
    if latest_ny.date() < expected_date:
        status = "stale_prior_close"
    elif market_open and age_minutes <= 25:
        status = "fresh"
    elif market_open and age_minutes <= 90:
        status = "delayed"
    elif market_open:
        status = "stale"
    else:
        status = "closed"
    return {
        "freshness_status": status,
        "age_minutes": age_minutes,
        "is_intraday": is_intraday,
        "market_clock": now_ny.isoformat(),
        "expected_market_date": expected_date.isoformat(),
    }


def _pct_change(close_values: Any, periods: int) -> float | None:
    try:
        if len(close_values) <= periods:
            return None
        current = float(close_values.iloc[-1])
        previous = float(close_values.iloc[-1 - periods])
        if previous == 0:
            return None
        return round((current / previous - 1.0) * 100.0, 2)
    except Exception:
        return None


def _as_iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _close_series(frame: Any) -> Any:
    if frame is None or frame.empty or "Close" not in frame:
        raise RuntimeError("no close data")
    close = frame["Close"].dropna()
    if close.empty:
        raise RuntimeError("empty close series")
    return close


def _collect_one_market_item(item: dict[str, str]) -> dict[str, Any]:
    intraday_error = ""
    try:
        import yfinance as yf

        ticker = yf.Ticker(item["symbol"])
        intraday = ticker.history(period="5d", interval="5m", auto_adjust=False, prepost=False)
        close = _close_series(intraday)
        daily_last = close.groupby(close.index.date).last().dropna()
        if len(daily_last) < 2:
            raise RuntimeError("not enough intraday days for 1d return")
        last_idx = close.index[-1]
        as_of = _as_iso(last_idx)
        freshness = us_market_freshness(as_of)
        usable = market_freshness_is_decision_usable(freshness.get("freshness_status"))
        daily_history = ticker.history(period="6mo", interval="1d", auto_adjust=False)
        daily_close = _close_series(daily_history)
        return {
            **item,
            "price": round(float(close.iloc[-1]), 4),
            "as_of": as_of,
            "source": "yfinance_intraday_5m",
            "status": "ok" if usable else "stale",
            "is_decision_usable": usable,
            "freshness_status": freshness.get("freshness_status", "unknown"),
            "age_minutes": freshness.get("age_minutes"),
            "market_clock": freshness.get("market_clock"),
            "returns": {
                "1d": round((float(daily_last.iloc[-1]) / float(daily_last.iloc[-2]) - 1.0) * 100.0, 2),
                "5d": _pct_change(daily_close, 5),
                "1m": _pct_change(daily_close, 21),
                "3m": _pct_change(daily_close, 63),
            },
        }
    except Exception as exc:  # noqa: BLE001
        intraday_error = str(exc)
        try:
            import yfinance as yf

            history = yf.Ticker(item["symbol"]).history(period="6mo", interval="1d", auto_adjust=False)
            close = _close_series(history)
            last_idx = close.index[-1]
            as_of = last_idx.date().isoformat() if hasattr(last_idx, "date") else str(last_idx)
            freshness = us_market_freshness(as_of)
            usable = market_freshness_is_decision_usable(freshness.get("freshness_status"))
            return {
                **item,
                "price": round(float(close.iloc[-1]), 4),
                "as_of": as_of,
                "source": "yfinance_daily_fallback",
                "status": "ok" if usable else "stale",
                "is_decision_usable": usable,
                "freshness_status": freshness.get("freshness_status", "unknown"),
                "age_minutes": freshness.get("age_minutes"),
                "market_clock": freshness.get("market_clock"),
                "intraday_error": intraday_error,
                "returns": {
                    "1d": _pct_change(close, 1),
                    "5d": _pct_change(close, 5),
                    "1m": _pct_change(close, 21),
                    "3m": _pct_change(close, 63),
                },
            }
        except Exception as fallback_exc:  # noqa: BLE001
            logger.warning("[DASHBOARD_MARKET] %s failed: %s", item["symbol"], fallback_exc)
            return {
                **item,
                "price": None,
                "as_of": "",
                "source": "yfinance",
                "status": "unavailable",
                "is_decision_usable": False,
                "freshness_status": "unknown",
                "age_minutes": None,
                "error": str(fallback_exc),
                "intraday_error": intraday_error,
                "returns": {"1d": None, "5d": None, "1m": None, "3m": None},
            }


async def _collect_market_snapshot() -> dict[str, Any]:
    items = await asyncio.gather(*(asyncio.to_thread(_collect_one_market_item, item) for item in MARKET_SNAPSHOT_SYMBOLS))
    ok_count = sum(1 for item in items if item.get("status") == "ok")
    decision_usable_count = sum(1 for item in items if item.get("is_decision_usable"))
    freshness_counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("freshness_status") or "unknown")
        freshness_counts[key] = freshness_counts.get(key, 0) + 1
    return {
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "yfinance",
        "ok_count": ok_count,
        "decision_usable_count": decision_usable_count,
        "freshness_counts": freshness_counts,
        "freshness_policy": "US market hours require fresh or delayed intraday data; stale prior-close data is labelled and excluded from decision-usable counts.",
        "warning": "" if decision_usable_count else "No fresh or delayed intraday market snapshot could be loaded from yfinance.",
    }


def _canonical_market_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(payload or {})
    for key in ("cache_hit", "cache_layer", "cache_ttl_seconds", "persisted_at", "expires_at", "refresh_lock"):
        clean.pop(key, None)
    return clean


def _market_snapshot_response(
    payload: dict[str, Any],
    *,
    cache_hit: bool,
    cache_layer: str,
    refresh_lock: str | None = None,
) -> dict[str, Any]:
    response = copy.deepcopy(payload)
    response["cache_hit"] = cache_hit
    response["cache_layer"] = cache_layer
    response["cache_ttl_seconds"] = MARKET_SNAPSHOT_CACHE_TTL_SEC
    if refresh_lock:
        response["refresh_lock"] = refresh_lock
    return response


def _store_memory_snapshot(payload: dict[str, Any], ts: float | None = None) -> None:
    _market_snapshot_cache["ts"] = ts if ts is not None else time.time()
    _market_snapshot_cache["payload"] = _canonical_market_snapshot(payload)


def _load_persisted_market_snapshot(db_path: str | Path | None = None) -> dict[str, Any] | None:
    try:
        snapshot = get_dashboard_snapshot(MARKET_SNAPSHOT_CACHE_KEY, db_path=db_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_MARKET] persisted snapshot load failed: %s", exc)
        return None
    if not snapshot:
        return None
    payload = snapshot.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return None
    response = _market_snapshot_response(_canonical_market_snapshot(payload), cache_hit=True, cache_layer="persisted")
    response["persisted_at"] = snapshot.get("updated_at")
    response["expires_at"] = snapshot.get("expires_at")
    return response


def _persist_market_snapshot(payload: dict[str, Any], db_path: str | Path | None = None) -> None:
    try:
        upsert_dashboard_snapshot(
            MARKET_SNAPSHOT_CACHE_KEY,
            _canonical_market_snapshot(payload),
            source="dashboard_market",
            ttl_seconds=MARKET_SNAPSHOT_CACHE_TTL_SEC,
            db_path=db_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_MARKET] persisted snapshot write failed: %s", exc)


def _acquire_market_refresh_lock(db_path: str | Path | None = None) -> dict[str, Any] | None:
    try:
        return acquire_dashboard_refresh_lock(
            MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
            ttl_seconds=MARKET_SNAPSHOT_REFRESH_LOCK_TTL_SEC,
            db_path=db_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_MARKET] refresh lock acquire failed: %s", exc)
        return None


def _release_market_refresh_lock(lock: dict[str, Any] | None, db_path: str | Path | None = None) -> None:
    if not lock or not lock.get("acquired") or not lock.get("owner_token"):
        return
    try:
        release_dashboard_refresh_lock(
            MARKET_SNAPSHOT_REFRESH_LOCK_KEY,
            str(lock["owner_token"]),
            db_path=db_path,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_MARKET] refresh lock release failed: %s", exc)


async def _wait_for_locked_market_snapshot(db_path: str | Path | None = None) -> dict[str, Any] | None:
    deadline = time.monotonic() + MARKET_SNAPSHOT_REFRESH_WAIT_SEC
    while time.monotonic() < deadline:
        await asyncio.sleep(0.25)
        persisted = _load_persisted_market_snapshot(db_path)
        if persisted:
            persisted["refresh_lock"] = "waited"
            _store_memory_snapshot(persisted)
            return persisted
    return None


async def get_market_snapshot(*, force: bool = False, db_path: str | Path | None = None) -> dict[str, Any]:
    now = time.time()
    cached = _market_snapshot_cache.get("payload")
    if cached and not force and now - float(_market_snapshot_cache.get("ts") or 0) < MARKET_SNAPSHOT_CACHE_TTL_SEC:
        return _market_snapshot_response(cached, cache_hit=True, cache_layer="memory")
    if not force:
        persisted = _load_persisted_market_snapshot(db_path)
        if persisted:
            _store_memory_snapshot(persisted, ts=now)
            return persisted
    lock = _acquire_market_refresh_lock(db_path)
    if lock and not lock.get("acquired"):
        waited = await _wait_for_locked_market_snapshot(db_path)
        if waited:
            return waited
    try:
        payload = await _collect_market_snapshot()
        _store_memory_snapshot(payload)
        _persist_market_snapshot(payload, db_path)
        refresh_lock = "acquired" if lock and lock.get("acquired") else ("unavailable" if lock is None else "timeout")
        return _market_snapshot_response(payload, cache_hit=False, cache_layer="provider", refresh_lock=refresh_lock)
    finally:
        _release_market_refresh_lock(lock, db_path)


def _dashboard_safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 4)
    except Exception:
        return None


def _dashboard_return(item: dict[str, Any] | None, key: str = "1d") -> float | None:
    if not item:
        return None
    returns = item.get("returns") if isinstance(item.get("returns"), dict) else {}
    return _dashboard_safe_float(returns.get(key))


def _dashboard_item_by_symbol(items: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    target = symbol.upper()
    for item in items:
        if str(item.get("symbol") or "").upper() == target:
            return item
    return None


def _dashboard_fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _dashboard_avg_return(items: list[dict[str, Any] | None], key: str = "1d") -> float | None:
    values = [_dashboard_return(item, key) for item in items]
    numeric = [value for value in values if value is not None]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def _dashboard_signal_component(label: str, value: float | None, *, status: str = "neutral", detail: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "value": _dashboard_fmt_pct(value),
        "raw_value": value,
        "status": status,
        "detail": detail,
    }


def _dashboard_signal_confidence(
    usable_items: list[dict[str, Any] | None],
    score: float | None,
    *,
    high_threshold: float = 1.0,
    medium_threshold: float = 0.35,
) -> str:
    if not usable_items or not all(bool(item and item.get("is_decision_usable")) for item in usable_items):
        return "low"
    if score is None:
        return "low"
    magnitude = abs(float(score))
    if magnitude >= high_threshold:
        return "high"
    if magnitude >= medium_threshold:
        return "medium"
    return "low"


def _dashboard_market_tape(items: list[dict[str, Any]]) -> list[MarketTapeItem]:
    tape: list[MarketTapeItem] = []
    for item in items:
        tape.append(
            MarketTapeItem(
                symbol=str(item.get("symbol") or ""),
                label=str(item.get("label") or ""),
                asset_class=str(item.get("asset_class") or ""),
                price=_dashboard_safe_float(item.get("price")),
                return_1d=_dashboard_return(item, "1d"),
                return_1m=_dashboard_return(item, "1m"),
                as_of=str(item.get("as_of") or ""),
                source=str(item.get("source") or "unknown"),
                freshness_status=str(item.get("freshness_status") or "unknown"),
                is_decision_usable=bool(item.get("is_decision_usable")),
            )
        )
    return tape


def _dashboard_signal(
    *,
    signal_id: str,
    title: str,
    status: str,
    score: float | None,
    summary: str,
    evidence: list[str],
    interpretation: str,
    usable_items: list[dict[str, Any] | None],
    direction: str = "neutral",
    confidence: str = "medium",
    horizon: str = "1D",
    impact: str = "",
    components: list[dict[str, Any]] | None = None,
    watch_points: list[str] | None = None,
    next_actions: list[str] | None = None,
    invalidation: list[str] | None = None,
) -> MarketDashboardSignal:
    return MarketDashboardSignal(
        signal_id=signal_id,
        title=title,
        status=status,
        score=round(score, 4) if score is not None else None,
        direction=direction,
        confidence=confidence,
        horizon=horizon,
        impact=impact,
        summary=summary,
        evidence=evidence,
        components=components or [],
        watch_points=watch_points or [],
        next_actions=next_actions or [],
        invalidation=invalidation or [],
        interpretation=interpretation,
        is_decision_usable=all(bool(item and item.get("is_decision_usable")) for item in usable_items),
    )


def _build_market_dashboard_signals(items: list[dict[str, Any]]) -> list[MarketDashboardSignal]:
    spy = _dashboard_item_by_symbol(items, "SPY")
    qqq = _dashboard_item_by_symbol(items, "QQQ")
    tlt = _dashboard_item_by_symbol(items, "TLT")
    hyg = _dashboard_item_by_symbol(items, "HYG")
    lqd = _dashboard_item_by_symbol(items, "LQD")
    gld = _dashboard_item_by_symbol(items, "GLD")
    btc = _dashboard_item_by_symbol(items, "BTC-USD")
    dxy = _dashboard_item_by_symbol(items, "DX-Y.NYB")
    tnx = _dashboard_item_by_symbol(items, "^TNX")

    signals: list[MarketDashboardSignal] = []
    equity_score = _dashboard_avg_return([spy, qqq], "1d")
    equity_trend = _dashboard_avg_return([spy, qqq], "1m")
    if equity_score is None:
        equity_status = "unavailable"
        equity_summary = "SPY/QQQ 1D 데이터가 부족합니다."
    elif equity_score >= 0.5 and (equity_trend is None or equity_trend >= 0):
        equity_status = "risk_on"
        equity_summary = f"SPY/QQQ 평균 1D 수익률이 {_dashboard_fmt_pct(equity_score)}, 1M 추세가 {_dashboard_fmt_pct(equity_trend)}로 위험자산 선호 쪽입니다."
    elif equity_score <= -0.5 and (equity_trend is None or equity_trend <= 0):
        equity_status = "risk_off"
        equity_summary = f"SPY/QQQ 평균 1D 수익률이 {_dashboard_fmt_pct(equity_score)}, 1M 추세가 {_dashboard_fmt_pct(equity_trend)}로 위험회피 쪽입니다."
    elif abs(equity_score) >= 0.5:
        equity_status = "mixed"
        equity_summary = f"SPY/QQQ 1D {_dashboard_fmt_pct(equity_score)}와 1M {_dashboard_fmt_pct(equity_trend)}가 엇갈려 추세 확인이 필요합니다."
    else:
        equity_status = "neutral"
        equity_summary = f"SPY/QQQ 평균 1D 수익률은 {_dashboard_fmt_pct(equity_score)}로 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="equity_momentum",
            title="Equity Momentum",
            status=equity_status,
            score=equity_score,
            direction=equity_status,
            confidence=_dashboard_signal_confidence([spy, qqq], equity_score),
            horizon="1D tape + 1M confirmation",
            impact="Risk appetite",
            summary=equity_summary,
            evidence=[
                f"SPY 1D {_dashboard_fmt_pct(_dashboard_return(spy))}",
                f"QQQ 1D {_dashboard_fmt_pct(_dashboard_return(qqq))}",
                f"SPY/QQQ 1M avg {_dashboard_fmt_pct(equity_trend)}",
            ],
            components=[
                _dashboard_signal_component("SPY 1D", _dashboard_return(spy), status="risk_on" if (_dashboard_return(spy) or 0) > 0 else "risk_off"),
                _dashboard_signal_component("QQQ 1D", _dashboard_return(qqq), status="risk_on" if (_dashboard_return(qqq) or 0) > 0 else "risk_off"),
                _dashboard_signal_component("Equity 1M", equity_trend, status="risk_on" if (equity_trend or 0) > 0 else "risk_off"),
            ],
            watch_points=["SPY와 QQQ가 같은 방향인지", "1D 반등이 1M 추세와 맞는지", "성장주 주도력이 크레딧과 동행하는지"],
            next_actions=["주식 강세가 HYG/LQD와 동행하면 위험선호 신뢰도를 높입니다.", "QQQ만 강하고 SPY가 약하면 섹터 편중 리스크를 확인합니다."],
            invalidation=["SPY/QQQ가 동시에 -0.5% 이하로 전환", "QQQ 강세에도 HYG가 약세로 이탈"],
            interpretation="주식 베타 방향을 판단하는 1차 테이프입니다.",
            usable_items=[spy, qqq],
        )
    )

    tnx_score = _dashboard_return(tnx)
    tlt_return = _dashboard_return(tlt)
    if tnx_score is None:
        rates_status = "unavailable"
        rates_summary = "10Y yield proxy 데이터가 부족합니다."
    elif tnx_score >= 1.0 and (tlt_return is None or tlt_return <= 0):
        rates_status = "watch"
        rates_summary = f"10Y yield proxy가 1D {_dashboard_fmt_pct(tnx_score)} 상승하고 TLT가 {_dashboard_fmt_pct(tlt_return)}라 duration 부담을 점검해야 합니다."
    elif tnx_score <= -1.0 or (tlt_return is not None and tlt_return >= 0.75):
        rates_status = "easing"
        rates_summary = f"10Y yield proxy 1D {_dashboard_fmt_pct(tnx_score)}, TLT {_dashboard_fmt_pct(tlt_return)}로 금리 압력은 완화 쪽입니다."
    else:
        rates_status = "neutral"
        rates_summary = f"10Y yield proxy 1D 변화는 {_dashboard_fmt_pct(tnx_score)}로 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="rates_pressure",
            title="Rates Pressure",
            status=rates_status,
            score=tnx_score,
            direction="risk_off" if rates_status == "watch" else ("risk_on" if rates_status == "easing" else "neutral"),
            confidence=_dashboard_signal_confidence([tnx, tlt], tnx_score),
            horizon="1D yield shock",
            impact="Duration and valuation pressure",
            summary=rates_summary,
            evidence=[f"^TNX 1D {_dashboard_fmt_pct(tnx_score)}", f"TLT 1D {_dashboard_fmt_pct(tlt_return)}"],
            components=[
                _dashboard_signal_component("^TNX 1D", tnx_score, status="risk_off" if (tnx_score or 0) > 0 else "risk_on"),
                _dashboard_signal_component("TLT 1D", tlt_return, status="risk_on" if (tlt_return or 0) > 0 else "risk_off"),
            ],
            watch_points=["금리 상승과 주식 강세가 공존하는지", "TLT가 금리 신호를 확인하는지", "DXY 강세가 금리 부담을 증폭하는지"],
            next_actions=["금리 상승이 1%p 이상 지속되면 성장주 밸류에이션 민감도를 낮춰 봅니다.", "TLT 반등이 동반되면 금리 부담 완화로 해석합니다."],
            invalidation=["^TNX가 하락 전환하고 TLT가 반등", "주식/크레딧이 금리 상승을 흡수"],
            interpretation="금리와 장기채 가격을 함께 보며 duration 리스크를 확인합니다.",
            usable_items=[tnx, tlt],
        )
    )

    hyg_return = _dashboard_return(hyg)
    lqd_return = _dashboard_return(lqd)
    credit_score = _dashboard_avg_return([hyg, lqd], "1d")
    credit_spread_proxy = None if hyg_return is None or lqd_return is None else round(hyg_return - lqd_return, 4)
    if credit_score is None:
        credit_status = "unavailable"
        credit_summary = "HYG/LQD 데이터가 부족합니다."
    elif hyg_return is not None and hyg_return <= -0.5 and (credit_spread_proxy is None or credit_spread_proxy < -0.2):
        credit_status = "risk_off"
        credit_summary = f"HYG가 1D {_dashboard_fmt_pct(hyg_return)}로 IG 대비 약해 신용 리스크 확인이 필요합니다."
    elif credit_score >= 0.35 and (credit_spread_proxy is None or credit_spread_proxy >= -0.2):
        credit_status = "ok"
        credit_summary = f"HYG/LQD 평균 1D 수익률은 {_dashboard_fmt_pct(credit_score)}로 신용 테이프가 양호합니다."
    else:
        credit_status = "neutral"
        credit_summary = f"HYG/LQD 평균 1D 수익률은 {_dashboard_fmt_pct(credit_score)}로 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="credit_tone",
            title="Credit Tone",
            status=credit_status,
            score=credit_score,
            direction="risk_off" if credit_status == "risk_off" else ("risk_on" if credit_status == "ok" else "neutral"),
            confidence=_dashboard_signal_confidence([hyg, lqd], credit_score, high_threshold=0.75),
            horizon="1D credit tape",
            impact="Funding and spread tone",
            summary=credit_summary,
            evidence=[
                f"HYG 1D {_dashboard_fmt_pct(hyg_return)}",
                f"LQD 1D {_dashboard_fmt_pct(lqd_return)}",
                f"HYG-LQD proxy {_dashboard_fmt_pct(credit_spread_proxy)}",
            ],
            components=[
                _dashboard_signal_component("HYG 1D", hyg_return, status="risk_on" if (hyg_return or 0) > 0 else "risk_off"),
                _dashboard_signal_component("LQD 1D", lqd_return, status="risk_on" if (lqd_return or 0) > 0 else "risk_off"),
                _dashboard_signal_component("HY minus IG", credit_spread_proxy, status="risk_on" if (credit_spread_proxy or 0) >= 0 else "risk_off"),
            ],
            watch_points=["HYG가 LQD보다 강한지", "신용 ETF가 주식 랠리를 확인하는지", "금리 상승에도 크레딧이 버티는지"],
            next_actions=["HYG가 LQD를 계속 앞서면 위험선호 확인 신호로 봅니다.", "HYG 약세가 주식보다 먼저 나타나면 리스크 축소 후보를 점검합니다."],
            invalidation=["HYG가 -0.5% 이하로 하락하고 LQD 대비 언더퍼폼", "신용 강세 없이 주식만 상승"],
            interpretation="하이일드와 투자등급 크레딧의 동조화를 확인합니다.",
            usable_items=[hyg, lqd],
        )
    )

    dxy_return = _dashboard_return(dxy)
    dxy_trend = _dashboard_return(dxy, "1m")
    if dxy_return is None:
        dxy_status = "unavailable"
        dxy_summary = "DXY 데이터가 부족합니다."
    elif dxy_return >= 0.5:
        dxy_status = "risk_off"
        dxy_summary = f"DXY 1D {_dashboard_fmt_pct(dxy_return)} 상승은 글로벌 유동성/위험자산에 부담입니다."
    elif dxy_return <= -0.5:
        dxy_status = "risk_on"
        dxy_summary = f"DXY 1D {_dashboard_fmt_pct(dxy_return)} 하락은 달러 압력 완화 신호입니다."
    else:
        dxy_status = "neutral"
        dxy_summary = f"DXY 1D 변화는 {_dashboard_fmt_pct(dxy_return)}로 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="dollar_liquidity",
            title="Dollar Liquidity",
            status=dxy_status,
            score=dxy_return,
            direction=dxy_status,
            confidence=_dashboard_signal_confidence([dxy], dxy_return, high_threshold=0.75),
            horizon="1D with 1M context",
            impact="Dollar pressure",
            summary=dxy_summary,
            evidence=[f"DXY 1D {_dashboard_fmt_pct(dxy_return)}", f"DXY 1M {_dashboard_fmt_pct(dxy_trend)}"],
            components=[
                _dashboard_signal_component("DXY 1D", dxy_return, status="risk_off" if (dxy_return or 0) > 0 else "risk_on"),
                _dashboard_signal_component("DXY 1M", dxy_trend, status="risk_off" if (dxy_trend or 0) > 0 else "risk_on"),
            ],
            watch_points=["달러 강세가 원자재/크립토와 충돌하는지", "DXY 1M 추세가 1D 움직임을 확인하는지"],
            next_actions=["DXY 강세와 금리 상승이 겹치면 위험자산 민감도를 낮춰 해석합니다.", "DXY 약세가 이어지면 원자재와 글로벌 베타 회복을 확인합니다."],
            invalidation=["DXY가 1D/1M 모두 하락 전환", "달러 강세에도 크레딧과 주식이 동반 상승"],
            interpretation="달러 방향은 글로벌 유동성, 원자재, 비달러 위험자산의 공통 압력으로 봅니다.",
            usable_items=[dxy],
        )
    )

    gld_return = _dashboard_return(gld)
    defensive_score = _dashboard_avg_return([tlt, gld], "1d")
    if defensive_score is None:
        defensive_status = "unavailable"
        defensive_summary = "TLT/GLD 방어자산 데이터가 부족합니다."
    elif defensive_score >= 0.5 and (equity_score is None or equity_score <= 0.5):
        defensive_status = "hedge_bid"
        defensive_summary = f"TLT/GLD 평균 1D {_dashboard_fmt_pct(defensive_score)}로 헤지 수요가 관측됩니다."
    elif defensive_score <= -0.5 and (equity_score is not None and equity_score >= 0.5):
        defensive_status = "risk_on"
        defensive_summary = f"TLT/GLD 평균 1D {_dashboard_fmt_pct(defensive_score)} 약세는 방어 수요 둔화 신호입니다."
    else:
        defensive_status = "neutral"
        defensive_summary = f"TLT/GLD 평균 1D {_dashboard_fmt_pct(defensive_score)}로 방어 수요는 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="defensive_hedge_bid",
            title="Defensive Hedge Bid",
            status=defensive_status,
            score=defensive_score,
            direction="risk_off" if defensive_status == "hedge_bid" else ("risk_on" if defensive_status == "risk_on" else "neutral"),
            confidence=_dashboard_signal_confidence([tlt, gld], defensive_score, high_threshold=0.9),
            horizon="1D hedge demand",
            impact="Portfolio hedge pressure",
            summary=defensive_summary,
            evidence=[f"TLT 1D {_dashboard_fmt_pct(tlt_return)}", f"GLD 1D {_dashboard_fmt_pct(gld_return)}"],
            components=[
                _dashboard_signal_component("TLT 1D", tlt_return, status="risk_off" if (tlt_return or 0) > 0 else "risk_on"),
                _dashboard_signal_component("GLD 1D", gld_return, status="risk_off" if (gld_return or 0) > 0 else "risk_on"),
                _dashboard_signal_component("Defensive avg", defensive_score, status="risk_off" if (defensive_score or 0) > 0 else "risk_on"),
            ],
            watch_points=["GLD와 TLT가 동시에 강한지", "방어자산 강세가 주식 약세와 동행하는지", "SPY/GLD 상대비율이 방어 수요를 반박하는지"],
            next_actions=["방어자산 강세가 크레딧 약세와 겹치면 리스크 관리 우선입니다.", "SPY/GLD가 상승하면 방어 강세를 단기 헤지성으로 낮춰 봅니다."],
            invalidation=["GLD/TLT가 동반 약세 전환", "SPY와 HYG가 동시에 강세 유지"],
            interpretation="금과 장기채가 포트폴리오 헤지 수요를 확인하는지 봅니다.",
            usable_items=[tlt, gld],
        )
    )

    btc_return = _dashboard_return(btc)
    btc_trend = _dashboard_return(btc, "1m")
    if btc_return is None:
        crypto_status = "unavailable"
        crypto_summary = "BTC 데이터가 부족합니다."
    elif btc_return >= 1.0 and (equity_score is None or equity_score >= 0):
        crypto_status = "risk_on"
        crypto_summary = f"BTC 1D {_dashboard_fmt_pct(btc_return)}로 고베타 위험선호가 보강됩니다."
    elif btc_return <= -1.0:
        crypto_status = "risk_off"
        crypto_summary = f"BTC 1D {_dashboard_fmt_pct(btc_return)} 약세는 고베타 리스크 축소 신호입니다."
    elif equity_score is not None and abs(btc_return - equity_score) >= 1.5:
        crypto_status = "mixed"
        crypto_summary = f"BTC 1D {_dashboard_fmt_pct(btc_return)}와 주식 {_dashboard_fmt_pct(equity_score)}가 엇갈립니다."
    elif equity_score is not None and equity_score >= 0.5:
        crypto_status = "neutral"
        crypto_summary = f"BTC 1D {_dashboard_fmt_pct(btc_return)}는 주식 신호를 강하게 증폭하지는 않습니다."
    else:
        crypto_status = "neutral"
        crypto_summary = f"BTC 1D {_dashboard_fmt_pct(btc_return)}는 중립권입니다."
    signals.append(
        _dashboard_signal(
            signal_id="crypto_beta",
            title="Crypto Beta",
            status=crypto_status,
            score=btc_return,
            direction=crypto_status,
            confidence=_dashboard_signal_confidence([btc], btc_return, high_threshold=1.5),
            horizon="1D high beta + 1M context",
            impact="Speculative beta",
            summary=crypto_summary,
            evidence=[f"BTC-USD 1D {_dashboard_fmt_pct(btc_return)}", f"BTC-USD 1M {_dashboard_fmt_pct(btc_trend)}"],
            components=[
                _dashboard_signal_component("BTC 1D", btc_return, status="risk_on" if (btc_return or 0) > 0 else "risk_off"),
                _dashboard_signal_component("BTC 1M", btc_trend, status="risk_on" if (btc_trend or 0) > 0 else "risk_off"),
                _dashboard_signal_component("Equity avg 1D", equity_score, status="risk_on" if (equity_score or 0) > 0 else "risk_off"),
            ],
            watch_points=["BTC가 주식보다 먼저 꺾이는지", "고베타 강세가 QQQ와 동행하는지", "달러 강세와 BTC 강세가 충돌하는지"],
            next_actions=["BTC와 QQQ가 동시에 강하면 투기적 베타 확인입니다.", "BTC만 급락하면 리스크 선호 약화의 선행 경고로 둡니다."],
            invalidation=["BTC가 -1% 이하로 전환", "DXY 급등과 BTC 약세 동시 발생"],
            interpretation="크립토는 고베타 위험선호의 보조 확인 신호입니다.",
            usable_items=[btc],
        )
    )

    cross_values = {
        "SPY": _dashboard_return(spy),
        "TLT": _dashboard_return(tlt),
        "HYG": _dashboard_return(hyg),
        "GLD": _dashboard_return(gld),
        "BTC-USD": _dashboard_return(btc),
        "DXY": _dashboard_return(dxy),
    }
    risk_asset_avg = _dashboard_avg_return([spy, hyg, btc], "1d")
    defensive_avg = _dashboard_avg_return([tlt, gld, dxy], "1d")
    cross_score = None if risk_asset_avg is None or defensive_avg is None else round(risk_asset_avg - defensive_avg, 4)
    negative_risk_assets = sum(1 for key in ("SPY", "HYG", "BTC-USD") if (cross_values.get(key) or 0) <= -0.5)
    defensive_bid = sum(1 for key in ("TLT", "GLD", "DXY") if (cross_values.get(key) or 0) >= 0.5)
    if cross_score is None:
        cross_status = "unavailable"
        cross_summary = "교차자산 확인에 필요한 가격 데이터가 부족합니다."
    elif negative_risk_assets >= 2 and defensive_bid >= 1:
        cross_status = "risk_off"
        cross_summary = "위험자산 약세와 방어자산 강세가 동시에 관측됩니다."
    elif negative_risk_assets == 0 and risk_asset_avg is not None and risk_asset_avg >= 0.35 and (defensive_avg is None or defensive_avg < risk_asset_avg):
        cross_status = "risk_on"
        cross_summary = f"위험자산 평균 {_dashboard_fmt_pct(risk_asset_avg)}가 방어 평균 {_dashboard_fmt_pct(defensive_avg)}보다 강해 위험선호 조합입니다."
    elif defensive_bid >= 2 and (risk_asset_avg is None or risk_asset_avg <= 0.35):
        cross_status = "risk_off"
        cross_summary = "방어자산 강세가 넓게 관측되어 리스크 관리 우선입니다."
    else:
        cross_status = "mixed"
        cross_summary = "교차자산 신호가 한 방향으로 충분히 모이지 않았습니다."
    signals.append(
        _dashboard_signal(
            signal_id="cross_asset_confirmation",
            title="Cross-Asset Confirmation",
            status=cross_status,
            score=cross_score,
            direction=cross_status,
            confidence=_dashboard_signal_confidence([spy, tlt, hyg, gld, btc, dxy], cross_score),
            horizon="1D cross-asset map",
            impact="Composite regime check",
            summary=cross_summary,
            evidence=[f"{key} 1D {_dashboard_fmt_pct(value)}" for key, value in cross_values.items()],
            components=[
                _dashboard_signal_component("Risk avg", risk_asset_avg, status="risk_on" if (risk_asset_avg or 0) > 0 else "risk_off"),
                _dashboard_signal_component("Defensive avg", defensive_avg, status="risk_off" if (defensive_avg or 0) > 0 else "risk_on"),
                _dashboard_signal_component("Risk minus defense", cross_score, status="risk_on" if (cross_score or 0) > 0 else "risk_off"),
            ],
            watch_points=["주식·크레딧·BTC가 같은 방향인지", "TLT·GLD·DXY가 방어 수요를 확인하는지", "위험자산 평균이 방어 평균을 계속 앞서는지"],
            next_actions=["교차자산 합치가 강하면 페어 브리핑의 상대차트와 같이 확인합니다.", "혼재일 때는 단일 카드보다 충돌 신호를 우선 점검합니다."],
            invalidation=["위험자산 2개 이상 약세 전환", "방어자산 2개 이상 강세 전환", "크레딧이 주식 신호를 반박"],
            interpretation="주식, 채권, 크레딧, 원자재, 달러, 크립토가 같은 방향인지 점검합니다.",
            usable_items=[spy, tlt, hyg, gld, btc, dxy],
        )
    )
    return signals


def _market_freshness_summary(market: dict[str, Any]) -> MarketDashboardFreshnessSummary:
    item_count = len(market.get("items") or [])
    usable_count = int(market.get("decision_usable_count") or 0)
    if item_count and usable_count == item_count:
        status = "ok"
    elif usable_count:
        status = "partial"
    else:
        status = "unavailable"
    return MarketDashboardFreshnessSummary(
        status=status,
        item_count=item_count,
        decision_usable_count=usable_count,
        freshness_counts=dict(market.get("freshness_counts") or {}),
        warning=str(market.get("warning") or ""),
        policy=str(market.get("freshness_policy") or ""),
    )


def heatmap_cache_summary(cached: Any) -> MarketDashboardHeatmapSummary:
    payload = dict(cached or {})
    if not payload:
        return MarketDashboardHeatmapSummary(
            status="not_loaded",
            warning="Heatmap snapshot has not been loaded in this API process yet.",
        )
    usable = int(payload.get("decision_usable_count") or payload.get("ok_count") or 0)
    stale = int(payload.get("stale_or_unavailable_count") or 0)
    status = "ok" if usable and not stale else ("partial" if usable else "unavailable")
    return MarketDashboardHeatmapSummary(
        status=status,
        universe_version=str(payload.get("universe_version") or ""),
        universe_size=int(payload.get("universe_size") or 0),
        decision_usable_count=usable,
        stale_or_unavailable_count=stale,
        latest_as_of=str(payload.get("latest_as_of") or ""),
        provider=str(payload.get("provider") or "unknown"),
        interval=str(payload.get("interval") or ""),
        warning=str(payload.get("warning") or ""),
        cache_hit=True,
    )


def build_market_dashboard_overview(market: dict[str, Any], heatmap_payload: Any) -> MarketDashboardOverview:
    items = list(market.get("items") or [])
    return MarketDashboardOverview(
        generated_at=datetime.now(timezone.utc).isoformat(),
        market_tape=_dashboard_market_tape(items),
        signals=_build_market_dashboard_signals(items),
        freshness_summary=_market_freshness_summary(market),
        heatmap_summary=heatmap_cache_summary(heatmap_payload),
        raw_market_meta={
            "generated_at": market.get("generated_at"),
            "provider": market.get("provider"),
            "ok_count": market.get("ok_count"),
            "cache_hit": market.get("cache_hit"),
        },
    )
