from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.api.heatmap_universe import HEATMAP_UNIVERSE_VERSION, US_EQUITY_HEATMAP_UNIVERSE
from core.utils.logger import get_logger
from pipelines.collect.google_news_rss import collect_news_from_google_rss
from pipelines.dashboard.market_service import (
    build_market_dashboard_overview,
    get_market_snapshot,
    market_freshness_is_decision_usable as _dashboard_freshness_is_decision_usable,
    us_market_freshness as _us_market_freshness,
)
from pipelines.data_mart.storage.repository import get_dashboard_snapshot, upsert_dashboard_snapshot


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = get_logger("api.dashboard")

_DASHBOARD_EQUITY_HEATMAP_CACHE_TTL_SEC = 60
_dashboard_equity_heatmap_cache: dict[str, Any] = {"ts": 0.0, "payload": None}
_EQUITY_HEATMAP_UNIVERSE = US_EQUITY_HEATMAP_UNIVERSE
_EQUITY_HEATMAP_BATCH_SIZE = 60
_INTRADAY_INTERVALS = {"5": "5m", "5m": "5m", "15": "15m", "15m": "15m", "60": "60m", "60m": "60m", "1h": "60m"}
_INTRADAY_PERIOD_BY_INTERVAL = {"5m": "5d", "15m": "30d", "60m": "60d"}
_INTRADAY_CACHE_TTL_SEC = 90
_DASHBOARD_DECISION_CARD_VERSION = "dashboard_decision_cards.v1"


def _decision_card(
    *,
    tab: str,
    title: str,
    purpose: str,
    primary_output: str,
    chips: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "tab": tab,
        "title": title,
        "status": "ok",
        "purpose": purpose,
        "primary_output": primary_output,
        "advisory_only": True,
        "contract_version": _DASHBOARD_DECISION_CARD_VERSION,
        "chips": chips,
    }


def _dashboard_decision_cards() -> list[dict[str, Any]]:
    return [
        _decision_card(
            tab="market",
            title="Market Dashboard",
            purpose="시장 테이프, 교차자산 신호, 데이터 신선도를 빠르게 점검합니다.",
            primary_output="시장 상태 요약과 다음 확인 대상",
            chips=[
                {"label": "데이터", "value": "Yahoo + local cache", "status": "ok", "detail": "가격·뉴스·히트맵 입력"},
                {"label": "범위", "value": "시장 스냅샷", "status": "ok", "detail": "시장 테이프와 교차자산 신호"},
                {"label": "최신성", "value": "가능 시 장중 데이터", "status": "warn", "detail": "freshness 확인 필요"},
                {"label": "작업", "value": "새로고침과 점검", "status": "ok", "detail": "로컬 데이터 갱신"},
            ],
        ),
        _decision_card(
            tab="macro",
            title="Macro",
            purpose="FRED, Yahoo, data mart 기반 거시 관측치와 레짐 해석을 확인합니다.",
            primary_output="거시 레짐, 정책 힌트, 데이터 품질",
            chips=[
                {"label": "데이터", "value": "FRED / Yahoo / data mart", "status": "ok", "detail": "매크로 관측 데이터"},
                {"label": "경계", "value": "관측 데이터 우선", "status": "ok", "detail": "AI 해석 전 데이터 확인"},
                {"label": "레짐", "value": "신호와 AI 해석 분리", "status": "warn", "detail": "레짐 엔진 결과 우선"},
                {"label": "출력", "value": "정책 힌트 전용", "status": "ok", "detail": "자문용 맥락"},
            ],
        ),
        _decision_card(
            tab="quant",
            title="Quant Lab",
            purpose="저장 가격 이력으로 백테스트, 전략 검증, 아티팩트를 재현합니다.",
            primary_output="백테스트 결과, 리플레이, 검증 아티팩트",
            chips=[
                {"label": "데이터", "value": "저장 가격 이력", "status": "ok", "detail": "data mart 가격"},
                {"label": "경계", "value": "No-lookahead 검사", "status": "warn", "detail": "미래 데이터 누수 방지"},
                {"label": "체결", "value": "다음 봉 기준", "status": "ok", "detail": "체결 가정 명시"},
                {"label": "출력", "value": "아티팩트와 리플레이", "status": "ok", "detail": "재현 가능한 결과"},
            ],
        ),
        _decision_card(
            tab="quantamental",
            title="Quantamental",
            purpose="가격, 재무, 피어, 리스크 엔진 산출값을 AI 해석과 분리해 점검합니다.",
            primary_output="classification, score, audit, AI interpretation",
            chips=[
                {"label": "데이터", "value": "yfinance + SEC/DART", "status": "ok", "detail": "시장별 provider coverage"},
                {"label": "계산", "value": "deterministic + peer", "status": "ok", "detail": "엔진 산출값 우선"},
                {"label": "AI", "value": "해석만 수행", "status": "warn", "detail": "AI는 점수 생성 금지"},
                {"label": "출력", "value": "classification + audit", "status": "ok", "detail": "스냅샷 감사"},
            ],
        ),
        _decision_card(
            tab="forecast",
            title="ML Forecast",
            purpose="가격 기반 예측 피처, 검증, 드리프트, 모델 레지스트리를 점검합니다.",
            primary_output="예측 실험과 자문용 신호",
            chips=[
                {"label": "데이터", "value": "data_mart 가격", "status": "ok", "detail": "예측 피처 입력"},
                {"label": "검증", "value": "Walk-forward 기본", "status": "ok", "detail": "시계열 검증"},
                {"label": "가드", "value": "Leakage / embargo", "status": "warn", "detail": "누수 검사 우선"},
                {"label": "출력", "value": "자문용 신호만", "status": "ok", "detail": "매매 지시 아님"},
            ],
        ),
        _decision_card(
            tab="ai-portfolio",
            title="AI Portfolio",
            purpose="정책 제약, 리밸런싱 후보, 보고서와 감사 이력을 운영 관점에서 확인합니다.",
            primary_output="정책 기반 추천과 승인 필요 작업",
            chips=[
                {"label": "저장소", "value": "Local SQLite", "status": "ok", "detail": "로컬 포트폴리오 상태"},
                {"label": "정책", "value": "제약조건 우선", "status": "ok", "detail": "정책 기반 엔진"},
                {"label": "승인", "value": "사용자 확인 작업", "status": "warn", "detail": "자동 리밸런싱 금지"},
                {"label": "감사", "value": "Hash와 이력", "status": "ok", "detail": "요청/정책 해시"},
            ],
        ),
    ]


def _clean_intraday_interval(value: Any) -> str:
    key = str(value or "5m").strip().lower()
    if key not in _INTRADAY_INTERVALS:
        raise ValueError("interval must be one of 5m, 15m, 60m")
    return _INTRADAY_INTERVALS[key]


def _frame_value(row: Any, name: str, fallback: float | None = None) -> float | int | None:
    try:
        value = row.get(name)
    except Exception:
        value = None
    if value is None:
        return fallback
    try:
        if value != value:
            return fallback
    except Exception:
        pass
    try:
        if name == "Volume":
            return int(value)
        return round(float(value), 6)
    except Exception:
        return fallback


def _intraday_rows_from_frame(frame: Any, *, limit: int) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", False):
        return []
    rows: list[dict[str, Any]] = []
    tail = frame.tail(max(1, int(limit or 500)))
    for idx, row in tail.iterrows():
        close = _frame_value(row, "Close")
        if close is None:
            continue
        open_price = _frame_value(row, "Open", close)
        high = _frame_value(row, "High", max(float(open_price or close), float(close)))
        low = _frame_value(row, "Low", min(float(open_price or close), float(close)))
        rows.append({
            "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "adjusted_close": close,
            "volume": _frame_value(row, "Volume"),
            "source": "yfinance_intraday",
        })
    return rows


def _intraday_snapshot_key(ticker: str, interval: str, period: str, limit: int) -> str:
    safe_ticker = str(ticker or "").strip().upper().replace("/", "_")
    return f"market_dashboard_intraday_v1:{safe_ticker}:{interval}:{period}:{int(limit)}"


def _intraday_cache_response(
    payload: dict[str, Any],
    *,
    cache_hit: bool,
    cache_layer: str,
    cache_stale: bool = False,
) -> dict[str, Any]:
    response = dict(payload)
    response["cache_hit"] = cache_hit
    response["cache_layer"] = cache_layer
    response["cache_ttl_seconds"] = _INTRADAY_CACHE_TTL_SEC
    if cache_stale:
        response["cache_stale"] = True
    return response


def _load_intraday_snapshot(
    snapshot_key: str,
    *,
    include_expired: bool = False,
) -> dict[str, Any] | None:
    try:
        snapshot = get_dashboard_snapshot(snapshot_key, include_expired=include_expired)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_INTRADAY] persisted snapshot load failed: %s", exc)
        return None
    if not snapshot:
        return None
    payload = snapshot.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return None
    layer = "persisted_stale" if snapshot.get("is_expired") else "persisted"
    response = _intraday_cache_response(
        payload,
        cache_hit=True,
        cache_layer=layer,
        cache_stale=bool(snapshot.get("is_expired")),
    )
    response["persisted_at"] = snapshot.get("updated_at")
    response["expires_at"] = snapshot.get("expires_at")
    return response


def _persist_intraday_snapshot(snapshot_key: str, payload: dict[str, Any]) -> None:
    try:
        upsert_dashboard_snapshot(
            snapshot_key,
            payload,
            source="dashboard_intraday",
            ttl_seconds=_INTRADAY_CACHE_TTL_SEC,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_INTRADAY] persisted snapshot write failed: %s", exc)


@router.get("/news")
async def dashboard_news(limit: int = 20) -> dict[str, Any]:
    """News cards for the UI home dashboard."""

    watchlist: list[dict[str, Any]] = [
        {
            "symbol": "MARKET",
            "query": '("Wall Street" OR "S&P 500" OR "stock market") (Reuters OR CNBC OR Bloomberg OR "Wall Street Journal" OR "Financial Times")',
            "category": "equity_index",
            "lookback": 7,
        },
        {"symbol": "SPY", "query": None, "category": "equity_index", "lookback": 7},
        {"symbol": "QQQ", "query": None, "category": "equity_index", "lookback": 7},
        {
            "symbol": "MACRO",
            "query": '("Federal Reserve" OR inflation OR CPI OR "Treasury yields" OR "rate cuts") (Reuters OR CNBC OR Bloomberg OR "New York Times" OR "Financial Times")',
            "category": "macro_policy",
            "lookback": 10,
        },
        {"symbol": "RATES", "query": 'site:cnbc.com "Treasury yields" when:10d', "category": "rates_credit", "lookback": 10},
        {
            "symbol": "BOND_MARKET",
            "query": 'site:bloomberg.com ("Treasury yields" OR "Bond Traders" OR "bond market") when:10d',
            "category": "rates_credit",
            "lookback": 10,
        },
        {"symbol": "TLT", "query": '"Treasury yields" OR "long bond ETF" OR TLT', "category": "rates_credit", "lookback": 10},
        {
            "symbol": "CREDIT",
            "query": 'site:bloomberg.com ("credit markets" OR "credit spreads" OR "high yield bonds") when:14d',
            "category": "rates_credit",
            "lookback": 14,
        },
        {
            "symbol": "CREDIT_REUTERS",
            "query": 'site:reuters.com ("credit spreads" OR "corporate debt" OR "high yield bonds") when:14d',
            "category": "rates_credit",
            "lookback": 14,
        },
        {"symbol": "HYG", "query": '"credit spreads" OR "high yield bonds" OR HYG', "category": "rates_credit", "lookback": 14},
        {
            "symbol": "AI_SEMIS",
            "query": '("AI chips" OR semiconductors OR Nvidia OR "AI capex") (Reuters OR CNBC OR Bloomberg OR "Financial Times")',
            "category": "ai_semis",
            "lookback": 10,
        },
        {
            "symbol": "EARNINGS",
            "query": '("earnings season" OR "earnings outlook" OR margins OR guidance) (Reuters OR CNBC OR Bloomberg OR "Wall Street Journal")',
            "category": "earnings",
            "lookback": 10,
        },
        {"symbol": "GLD", "query": '"gold price" OR "gold futures" OR "real yields gold" OR GLD', "category": "commodity", "lookback": 14},
        {"symbol": "OIL", "query": '"oil prices" OR "crude oil" OR OPEC OR "energy market"', "category": "commodity", "lookback": 14},
        {"symbol": "BTC-USD", "query": '"Bitcoin price" OR "Bitcoin ETF" OR cryptocurrency OR "crypto market"', "category": "crypto", "lookback": 14},
    ]
    max_items = max(6, min(int(limit or 20), 30))

    major_sources = (
        "reuters",
        "bloomberg",
        "cnbc",
        "wall street journal",
        "wsj",
        "financial times",
        "new york times",
        "nytimes",
        "associated press",
        "ap news",
        "barron's",
        "barrons",
    )
    market_sources = ("marketwatch", "yahoo finance", "axios", "fortune", "the economist", "seeking alpha")
    low_priority_sources = ("invesco", "etf database", "tipranks", "motley fool", "moomoo", "minichart", "investing.com")
    topic_keywords = {
        "equity_index": ("stock", "s&p", "nasdaq", "wall street", "equity", "market"),
        "macro_policy": ("inflation", "fed", "federal reserve", "consumer", "sentiment", "jobs", "cpi", "rates", "gdp"),
        "rates_credit": ("treasury", "yield", "bond", "credit", "spread", "debt", "fed", "rate", "default", "loan"),
        "ai_semis": ("ai", "chip", "semiconductor", "nvidia", "intel", "huawei", "capex"),
        "earnings": ("earnings", "profit", "margin", "guidance", "revenue", "quarter"),
        "commodity": ("oil", "crude", "gold", "opec", "commodity", "energy"),
        "crypto": ("bitcoin", "crypto", "cryptocurrency", "etf", "ethereum", "wallet"),
    }

    def _published_ts(value: str | None) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    def _repair_feed_text(value: Any) -> str:
        text = str(value or "")
        if not text or not any(marker in text for marker in ("창", "횄", "횂")):
            return text
        try:
            repaired = text.encode("latin1").decode("utf-8")
            return repaired if repaired else text
        except Exception:
            return text

    def _source_score(item: dict[str, Any]) -> int:
        haystack = " ".join([str(item.get("source") or ""), str(item.get("title") or ""), str(item.get("url") or "")]).lower()
        if any(token in haystack for token in major_sources):
            return 0
        if any(token in haystack for token in market_sources):
            return 1
        if any(token in haystack for token in low_priority_sources):
            return 3
        return 2

    def _topic_score(entry: dict[str, Any], item: dict[str, Any]) -> int:
        category = str(entry.get("category") or "market")
        title = str(item.get("title") or "").lower()
        return 0 if any(keyword in title for keyword in topic_keywords.get(category, ())) else 1

    def collect_one(entry: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            _, docs = collect_news_from_google_rss(
                str(entry["symbol"]),
                int(entry.get("lookback") or 10),
                limit=8,
                query_override=entry.get("query"),
                strict_purity=entry.get("query") is None,
            )
            return docs
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DASHBOARD_NEWS] %s failed: %s", entry.get("symbol"), exc)
            return []

    groups = await asyncio.gather(*(asyncio.to_thread(collect_one, entry) for entry in watchlist))
    seen: set[str] = set()

    def make_item(entry: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any] | None:
        symbol = str(entry["symbol"])
        title = _repair_feed_text(doc.get("title")).strip()
        url = str(doc.get("url") or "").strip()
        key = url or title.lower()
        if not title or key in seen:
            return None
        seen.add(key)
        published_at = doc.get("published_at") or doc.get("date") or ""
        item = {
            "symbol": symbol,
            "title": title,
            "source": _repair_feed_text(doc.get("source") or "Google News"),
            "url": url,
            "category": entry.get("category") or "market",
            "published_at": published_at,
            "collected_at": doc.get("collected_at") or datetime.now(timezone.utc).isoformat(),
            "summary": _repair_feed_text(doc.get("text") or doc.get("chunk") or ""),
        }
        item["source_tier"] = _source_score(item)
        item["topic_tier"] = _topic_score(entry, item)
        item["sort_ts"] = _published_ts(str(published_at))
        return item

    candidates_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for entry, docs in zip(watchlist, groups):
        symbol = str(entry["symbol"])
        candidates_by_symbol[symbol] = []
        for doc in docs:
            item = make_item(entry, doc)
            if item:
                candidates_by_symbol[symbol].append(item)
        candidates_by_symbol[symbol].sort(
            key=lambda row: (int(row.get("source_tier", 2)), int(row.get("topic_tier", 1)), -float(row.get("sort_ts", 0.0)))
        )

    items: list[dict[str, Any]] = []
    used_categories: set[str] = set()
    for entry in watchlist:
        symbol = str(entry["symbol"])
        category = str(entry.get("category") or "market")
        if category in used_categories:
            continue
        if candidates_by_symbol.get(symbol):
            items.append(candidates_by_symbol[symbol][0])
            used_categories.add(category)
            if len(items) >= max_items:
                break
    if len(items) < max_items:
        category_counts: dict[str, int] = {}
        for item in items:
            category = str(item.get("category") or "market")
            category_counts[category] = category_counts.get(category, 0) + 1
        leftovers = [item for rows in candidates_by_symbol.values() for item in rows if item not in items]
        leftovers.sort(
            key=lambda row: (int(row.get("source_tier", 2)), int(row.get("topic_tier", 1)), -float(row.get("sort_ts", 0.0)))
        )
        deferred: list[dict[str, Any]] = []
        for item in leftovers:
            if len(items) >= max_items:
                break
            category = str(item.get("category") or "market")
            if category_counts.get(category, 0) >= 4:
                deferred.append(item)
                continue
            items.append(item)
            category_counts[category] = category_counts.get(category, 0) + 1
        if len(items) < max_items:
            items.extend(deferred[: max_items - len(items)])

    for item in items:
        item.pop("sort_ts", None)
        item.pop("topic_tier", None)

    return {
        "items": items[:max_items],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "google_news_rss",
        "selection_policy": "major_source_priority_issue_coverage",
    }


@router.get("/decision-cards")
async def dashboard_decision_cards() -> dict[str, Any]:
    """Return tab-level decision context for the static dashboard strip."""

    items = _dashboard_decision_cards()
    return {
        "status": "ok",
        "contract_version": _DASHBOARD_DECISION_CARD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "advisory_only": True,
        "items": items,
    }


@router.get("/market")
async def dashboard_market(force: bool = False) -> dict[str, Any]:
    """Local market snapshot for the UI dashboard."""

    return await get_market_snapshot(force=force)


@router.get("/market/overview")
async def dashboard_market_overview(force: bool = False) -> dict[str, Any]:
    """Decision-support overview assembled from local market dashboard data."""

    market = await get_market_snapshot(force=force)
    overview = build_market_dashboard_overview(market, _dashboard_equity_heatmap_cache.get("payload"))
    return overview.model_dump(mode="json")


@router.get("/market/intraday/{ticker}")
async def dashboard_market_intraday(
    ticker: str,
    interval: str = "5m",
    period: str | None = None,
    limit: int = 500,
    force: bool = False,
) -> dict[str, Any]:
    """Return internal intraday OHLC rows for the market chart."""

    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        return {
            "status": "empty",
            "ticker": "",
            "items": [],
            "count": 0,
            "message": "ticker is required",
        }
    try:
        clean_interval = _clean_intraday_interval(interval)
    except ValueError as exc:
        return {
            "status": "error",
            "ticker": clean_ticker,
            "items": [],
            "count": 0,
            "message": str(exc),
        }
    clean_period = str(period or _INTRADAY_PERIOD_BY_INTERVAL[clean_interval]).strip()
    bounded_limit = max(1, min(int(limit or 500), 1000))
    snapshot_key = _intraday_snapshot_key(clean_ticker, clean_interval, clean_period, bounded_limit)
    if not force:
        cached = _load_intraday_snapshot(snapshot_key)
        if cached:
            return cached

    def collect() -> dict[str, Any]:
        import yfinance as yf

        frame = yf.Ticker(clean_ticker).history(
            period=clean_period,
            interval=clean_interval,
            auto_adjust=False,
            prepost=False,
        )
        rows = _intraday_rows_from_frame(frame, limit=bounded_limit)
        latest = rows[-1] if rows else None
        return {
            "status": "ok" if rows else "empty",
            "ticker": clean_ticker,
            "interval": clean_interval,
            "period": clean_period,
            "count": len(rows),
            "latest": latest,
            "items": rows,
            "provider": "yfinance",
            "source": f"yfinance_intraday_{clean_interval}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        payload = await asyncio.to_thread(collect)
        if payload.get("items"):
            _persist_intraday_snapshot(snapshot_key, payload)
        elif not force:
            stale = _load_intraday_snapshot(snapshot_key, include_expired=True)
            if stale:
                stale["provider_error"] = "empty intraday response"
                return stale
        return _intraday_cache_response(payload, cache_hit=False, cache_layer="provider")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_INTRADAY] %s %s failed: %s", clean_ticker, clean_interval, exc)
        stale = _load_intraday_snapshot(snapshot_key, include_expired=True)
        if stale:
            stale["provider_error"] = str(exc)
            return stale
        return {
            "status": "error",
            "ticker": clean_ticker,
            "interval": clean_interval,
            "period": clean_period,
            "count": 0,
            "latest": None,
            "items": [],
            "provider": "yfinance",
            "source": f"yfinance_intraday_{clean_interval}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "message": str(exc),
            "cache_hit": False,
            "cache_layer": "provider",
            "cache_ttl_seconds": _INTRADAY_CACHE_TTL_SEC,
        }


def _tile_span(weight: float) -> dict[str, int]:
    if weight >= 8:
        return {"col": 4, "row": 4}
    if weight >= 4:
        return {"col": 3, "row": 3}
    if weight >= 2:
        return {"col": 2, "row": 2}
    return {"col": 1, "row": 1}


def _batched_symbols(symbols: list[str], batch_size: int) -> list[list[str]]:
    size = max(1, int(batch_size or 1))
    return [symbols[idx:idx + size] for idx in range(0, len(symbols), size)]


def _extract_yfinance_symbol_frame(raw: Any, pd: Any, symbol: str) -> Any:
    if raw is None or getattr(raw, "empty", False):
        raise RuntimeError("empty intraday download")
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = list(raw.columns.get_level_values(0))
        if symbol in level0:
            return raw[symbol]
        return raw.xs(symbol, axis=1, level=0)
    return raw


def _download_equity_heatmap_frames(yf: Any, pd: Any, symbols: list[str]) -> tuple[dict[str, Any], dict[str, str]]:
    frames: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for batch in _batched_symbols(symbols, _EQUITY_HEATMAP_BATCH_SIZE):
        try:
            raw = yf.download(
                tickers=batch,
                period="5d",
                interval="5m",
                auto_adjust=False,
                prepost=False,
                group_by="ticker",
                threads=True,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            for symbol in batch:
                errors[symbol] = f"batch download failed: {exc}"
            continue
        for symbol in batch:
            try:
                frames[symbol] = _extract_yfinance_symbol_frame(raw, pd, symbol)
            except Exception as exc:  # noqa: BLE001
                errors[symbol] = str(exc)
    return frames, errors


def _collect_equity_heatmap_snapshot() -> dict[str, Any]:
    import pandas as pd
    import yfinance as yf

    symbols = [item["symbol"] for item in _EQUITY_HEATMAP_UNIVERSE]
    frames_by_symbol, download_errors = _download_equity_heatmap_frames(yf, pd, symbols)
    now_utc = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []

    for meta in _EQUITY_HEATMAP_UNIVERSE:
        symbol = str(meta["symbol"])
        try:
            if symbol in download_errors:
                raise RuntimeError(download_errors[symbol])
            frame = frames_by_symbol.get(symbol)
            if frame is None or frame.empty or "Close" not in frame:
                raise RuntimeError("no intraday close data")
            close = frame["Close"].dropna()
            if close.empty:
                raise RuntimeError("empty intraday close series")
            daily_last = close.groupby(close.index.date).last().dropna()
            if len(daily_last) < 2:
                raise RuntimeError("not enough intraday days for previous-close comparison")
            latest_idx = close.index[-1]
            latest_price = float(close.iloc[-1])
            previous_close = float(daily_last.iloc[-2])
            if previous_close == 0:
                raise RuntimeError("previous close is zero")
            change_pct = round((latest_price / previous_close - 1.0) * 100.0, 2)
            as_of = latest_idx.isoformat() if hasattr(latest_idx, "isoformat") else str(latest_idx)
            freshness = _us_market_freshness(as_of)
            usable = _dashboard_freshness_is_decision_usable(freshness["freshness_status"])
            items.append({
                **meta,
                "price": round(latest_price, 4),
                "previous_close": round(previous_close, 4),
                "change_pct": change_pct,
                "as_of": as_of,
                "source": "yfinance_intraday_5m",
                "status": "ok" if usable else "stale",
                "is_decision_usable": usable,
                "freshness_status": freshness["freshness_status"],
                "age_minutes": freshness["age_minutes"],
                "is_intraday": freshness["is_intraday"],
                "tile_span": _tile_span(float(meta["weight"])),
            })
        except Exception as exc:  # noqa: BLE001
            items.append({
                **meta,
                "price": None,
                "previous_close": None,
                "change_pct": None,
                "as_of": "",
                "source": "yfinance_intraday_5m",
                "status": "unavailable",
                "is_decision_usable": False,
                "freshness_status": "unknown",
                "age_minutes": None,
                "is_intraday": False,
                "tile_span": _tile_span(float(meta["weight"])),
                "error": str(exc),
            })

    usable_items = [item for item in items if item.get("status") == "ok" and item.get("is_decision_usable")]
    freshness_counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("freshness_status") or "unknown")
        freshness_counts[key] = freshness_counts.get(key, 0) + 1
    latest_as_of = max((str(item.get("as_of")) for item in usable_items if item.get("as_of")), default="")
    stale_count = sum(1 for item in items if not item.get("is_decision_usable"))
    return {
        "items": items,
        "generated_at": now_utc.isoformat(),
        "provider": "yfinance",
        "interval": "5m",
        "universe_version": HEATMAP_UNIVERSE_VERSION,
        "universe_size": len(_EQUITY_HEATMAP_UNIVERSE),
        "batch_size": _EQUITY_HEATMAP_BATCH_SIZE,
        "ok_count": len(usable_items),
        "decision_usable_count": len(usable_items),
        "stale_or_unavailable_count": stale_count,
        "latest_as_of": latest_as_of,
        "freshness_counts": freshness_counts,
        "freshness_policy": "US market hours require fresh or delayed 5-minute intraday data; prior-close/stale symbols are excluded from the rendered heatmap.",
        "warning": (
            f"{stale_count} symbols are excluded from the decision surface because fresh or delayed intraday data was unavailable."
            if stale_count else ""
        ),
    }


@router.get("/equity-heatmap")
async def dashboard_equity_heatmap(force: bool = False) -> dict[str, Any]:
    now = time.time()
    cached = _dashboard_equity_heatmap_cache.get("payload")
    if cached and not force and now - float(_dashboard_equity_heatmap_cache.get("ts") or 0) < _DASHBOARD_EQUITY_HEATMAP_CACHE_TTL_SEC:
        payload = dict(cached)
        payload["cache_hit"] = True
        return payload

    payload = await asyncio.to_thread(_collect_equity_heatmap_snapshot)
    payload["cache_hit"] = False
    _dashboard_equity_heatmap_cache["ts"] = now
    _dashboard_equity_heatmap_cache["payload"] = dict(payload)
    return payload
