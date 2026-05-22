from __future__ import annotations

import asyncio
from copy import deepcopy
import math
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.api.heatmap_universe import HEATMAP_UNIVERSE_VERSION, US_EQUITY_HEATMAP_UNIVERSE
from core.utils.logger import get_logger
from pipelines.collect.google_news_rss import collect_news_from_google_rss
from pipelines.dashboard.market_service import (
    MARKET_SNAPSHOT_CACHE_KEY,
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
_CROSS_ASSET_ALIASES = {
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "TNX": "^TNX",
}
_CROSS_ASSET_LABELS = {
    "SPY": ("S&P 500", "equity"),
    "QQQ": ("Nasdaq 100", "equity"),
    "TLT": ("Long Treasury", "rates"),
    "IEF": ("Intermediate Treasury", "rates"),
    "SHY": ("Short Treasury", "rates"),
    "HYG": ("High Yield Credit", "credit"),
    "LQD": ("IG Credit", "credit"),
    "GLD": ("Gold", "commodity"),
    "USO": ("Oil ETF", "commodity"),
    "BTC-USD": ("Bitcoin", "crypto"),
    "ETH-USD": ("Ethereum", "crypto"),
    "DXY": ("Dollar Index", "fx"),
    "DX-Y.NYB": ("Dollar Index", "fx"),
    "US10Y": ("US 10Y Yield", "rates"),
    "^TNX": ("US 10Y Yield", "rates"),
}

_DECISION_CARD_CONTRACTS: list[dict[str, Any]] = [
    {
        "tab": "market",
        "title": "Market Dashboard",
        "decision_question": "Is the current tape risk-on, risk-off, or mixed?",
        "primary_output": "Market tape plus cross-asset signal checks before chart/news inspection.",
        "next_action": "Review market tape and cross-asset signals, then refresh intraday data if stale.",
        "source_endpoints": [
            "/api/v1/dashboard/market/overview",
            "/api/v1/dashboard/market",
            "/api/v1/dashboard/equity-heatmap",
        ],
        "guardrails": ["advisory_only", "freshness_required", "no_price_target"],
        "chips": [
            {"label": "Decision", "value": "risk regime", "status": "ok", "detail": "Tape and cross-asset pressure"},
            {"label": "Evidence", "value": "market data", "status": "warn", "detail": "Loads from local snapshot or provider"},
            {"label": "Guard", "value": "freshness", "status": "warn", "detail": "Exclude stale symbols from decision surface"},
            {"label": "Action", "value": "refresh", "status": "ok", "detail": "Refresh before relying on intraday moves"},
        ],
    },
    {
        "tab": "macro",
        "title": "Macro",
        "decision_question": "Which macro regime and data-quality constraints should frame the research?",
        "primary_output": "Regime, data quality, coverage, and series explorer separated from AI narrative.",
        "next_action": "Check regime and data quality before using scenario or policy hints.",
        "source_endpoints": [
            "/api/v1/macro/dashboard",
            "/api/v1/macro/data-quality",
            "/api/v1/macro/provider-health",
        ],
        "guardrails": ["observed_data_first", "advisory_hints_only", "provider_status_visible"],
        "chips": [
            {"label": "Decision", "value": "regime frame", "status": "ok", "detail": "Rules engine before interpretation"},
            {"label": "Evidence", "value": "macro series", "status": "ok", "detail": "FRED/Yahoo/data mart surfaces"},
            {"label": "Guard", "value": "quality", "status": "warn", "detail": "Use quality panel before policy hints"},
            {"label": "Action", "value": "refresh/status", "status": "ok", "detail": "Refresh job status is explicit"},
        ],
    },
    {
        "tab": "risk",
        "title": "Risk",
        "decision_question": "Which company, macro, transmission, scenario, and data-quality risks can damage the subject?",
        "primary_output": "Enterprise risk workbench with company vectors, macro pressure, transmission channels, scenario matrix, and evidence review.",
        "next_action": "Run the risk workbench, inspect decision usability, then review evidence before acting elsewhere.",
        "source_endpoints": [
            "/api/v1/risk/health",
            "/api/v1/risk/workbench",
            "/api/v1/risk/company/{ticker}",
            "/api/v1/risk/macro",
        ],
        "guardrails": ["no_buy_sell_hold", "deterministic_scores_only", "freshness_visible", "ai_no_score_generation"],
        "chips": [
            {"label": "Decision", "value": "risk control", "status": "ok", "detail": "Company, macro, and portfolio risk context"},
            {"label": "Evidence", "value": "risk vectors", "status": "warn", "detail": "Uses Quantamental and Macro adapters"},
            {"label": "Guard", "value": "decision usable", "status": "warn", "detail": "Missing or stale inputs stay visible"},
            {"label": "Action", "value": "run risk", "status": "ok", "detail": "Review scenario damage paths and evidence"},
        ],
    },
    {
        "tab": "quant",
        "title": "Quant Lab",
        "decision_question": "Did the strategy survive reproducible backtest and portfolio checks?",
        "primary_output": "Backtest artifacts, portfolio optimizer output, replay, exports, and model lab evidence.",
        "next_action": "Run or inspect backtest artifacts before using portfolio allocation output.",
        "source_endpoints": [
            "/api/v1/quant/backtest",
            "/api/v1/quant/backtests",
            "/api/v1/portfolio/optimize",
        ],
        "guardrails": ["artifact_backed", "no_lookahead", "replay_required"],
        "chips": [
            {"label": "Decision", "value": "strategy viability", "status": "ok", "detail": "Backtest plus portfolio workflow"},
            {"label": "Evidence", "value": "artifacts", "status": "ok", "detail": "Manifest, metrics, trades, exports"},
            {"label": "Guard", "value": "no-lookahead", "status": "warn", "detail": "Feature/signal diagnostics stay visible"},
            {"label": "Action", "value": "run/replay", "status": "ok", "detail": "Use replay before comparing runs"},
        ],
    },
    {
        "tab": "auto-trading",
        "title": "Auto Trading",
        "decision_question": "Which strategy version is ready to move from research evidence toward the paper/live seam?",
        "primary_output": "Strategy governance, local LLM drafts, optimization, diagnostics, hypotheses, validation, and version decisions.",
        "next_action": "Edit or generate a strategy, run dry-run validation, then use Strategy Research evidence before any promotion.",
        "source_endpoints": [
            "/api/v1/quant/strategies",
            "/api/v1/quant/strategy-research/backend-status",
            "/api/v1/quant/strategy-research/strategies",
            "/api/v1/quant/strategy-research/protected-runtime/status",
        ],
        "guardrails": ["validation_gated", "core_logic_protected", "paper_live_seam_fail_closed", "no_financial_advice"],
        "chips": [
            {"label": "Decision", "value": "version readiness", "status": "ok", "detail": "Strategy definition and validation evidence"},
            {"label": "Evidence", "value": "research artifacts", "status": "ok", "detail": "Optimization, diagnostics, validation"},
            {"label": "Guard", "value": "protected seam", "status": "warn", "detail": "No live execution claim without protected runtime"},
            {"label": "Action", "value": "draft/validate", "status": "ok", "detail": "Keep AI hypotheses pending until validated"},
        ],
    },
    {
        "tab": "quantamental",
        "title": "Quantamental",
        "decision_question": "Is the deterministic company/factor signal supported by coverage and audit evidence?",
        "primary_output": "Company setup, deterministic signal, composite score, then factor/detail drilldown.",
        "next_action": "Run analysis, inspect data quality, and use peer comparison only as operations detail.",
        "source_endpoints": [
            "/api/v1/quantamental/health",
            "/api/v1/quantamental/analysis/{ticker}",
            "/api/v1/quantamental/snapshots",
        ],
        "guardrails": ["deterministic_scores_only", "ai_interpretation_only", "snapshot_audit"],
        "chips": [
            {"label": "Decision", "value": "research candidate", "status": "ok", "detail": "Signal and composite score"},
            {"label": "Evidence", "value": "fundamental+quant", "status": "ok", "detail": "Provider coverage stays explicit"},
            {"label": "Guard", "value": "AI no scoring", "status": "warn", "detail": "AI interprets engine output only"},
            {"label": "Action", "value": "analyze", "status": "ok", "detail": "Persist snapshot for audit trail"},
        ],
    },
    {
        "tab": "forecast",
        "title": "ML Forecast",
        "decision_question": "Is the forecast experiment valid enough to produce an advisory signal?",
        "primary_output": "Dataset quality, leakage check, forecast result, and validation diagnostics.",
        "next_action": "Preview dataset and leakage before training or interpreting forecast output.",
        "source_endpoints": [
            "/api/v1/forecast/health",
            "/api/v1/forecast/preview",
            "/api/v1/forecast/jobs",
            "/api/v1/forecast/model-registry",
        ],
        "guardrails": ["walk_forward", "purge_embargo", "advisory_only"],
        "chips": [
            {"label": "Decision", "value": "signal validity", "status": "ok", "detail": "Validation before forecast interpretation"},
            {"label": "Evidence", "value": "dataset+leakage", "status": "ok", "detail": "Core keeps data quality visible"},
            {"label": "Guard", "value": "walk-forward", "status": "warn", "detail": "No synchronous hidden training claim"},
            {"label": "Action", "value": "preview/train", "status": "ok", "detail": "Jobs and registry remain operations"},
        ],
    },
    {
        "tab": "ai-portfolio",
        "title": "AI Portfolio",
        "decision_question": "Does the policy-constrained portfolio recommendation need user-approved action?",
        "primary_output": "Policy overview, recommendation, create form, compliance, rebalance, and audit history.",
        "next_action": "Inspect recommendation and compliance before creating or approving changes.",
        "source_endpoints": [
            "/api/v1/ai-portfolio/dashboard",
            "/api/v1/ai-portfolio/recommendation",
            "/api/v1/ai-portfolio/operations",
        ],
        "guardrails": ["policy_first", "user_approved_rebalance", "hash_audit"],
        "chips": [
            {"label": "Decision", "value": "approve or hold", "status": "ok", "detail": "Recommendation before create form"},
            {"label": "Evidence", "value": "policy+engine", "status": "ok", "detail": "Quant engine separate from AI explanation"},
            {"label": "Guard", "value": "approval", "status": "warn", "detail": "No automatic rebalance execution"},
            {"label": "Action", "value": "review", "status": "ok", "detail": "Operations history keeps audit trail"},
        ],
    },
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


def _decision_card_contracts_by_tab() -> dict[str, dict[str, Any]]:
    return {str(item["tab"]): deepcopy(item) for item in _DECISION_CARD_CONTRACTS}


def _market_decision_card_evidence() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "snapshot_status": "unloaded",
        "snapshot_updated_at": None,
        "snapshot_expired": None,
        "decision_usable_count": None,
        "market_item_count": None,
        "heatmap_status": "unloaded",
        "heatmap_decision_usable_count": None,
        "heatmap_universe_size": None,
    }
    try:
        snapshot = get_dashboard_snapshot(MARKET_SNAPSHOT_CACHE_KEY, include_expired=True)
    except Exception as exc:  # noqa: BLE001
        evidence["snapshot_status"] = "error"
        evidence["error"] = str(exc)
        snapshot = None
    if snapshot:
        payload = snapshot.get("payload") if isinstance(snapshot, dict) else None
        payload = payload if isinstance(payload, dict) else {}
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        evidence.update({
            "snapshot_status": "stale" if snapshot.get("is_expired") else "cached",
            "snapshot_updated_at": snapshot.get("updated_at"),
            "snapshot_expired": bool(snapshot.get("is_expired")),
            "decision_usable_count": payload.get("decision_usable_count"),
            "market_item_count": len(items),
            "provider": payload.get("provider"),
        })
    heatmap = _dashboard_equity_heatmap_cache.get("payload")
    if isinstance(heatmap, dict):
        evidence.update({
            "heatmap_status": "cached",
            "heatmap_decision_usable_count": heatmap.get("decision_usable_count"),
            "heatmap_universe_size": heatmap.get("universe_size"),
            "heatmap_latest_as_of": heatmap.get("latest_as_of"),
        })
    return evidence


def _apply_market_decision_evidence(card: dict[str, Any]) -> dict[str, Any]:
    evidence = _market_decision_card_evidence()
    card["evidence"] = evidence
    status = "ok" if evidence.get("snapshot_status") in {"cached", "stale"} else "warn"
    source_count = evidence.get("decision_usable_count")
    source_text = (
        f"{source_count} usable"
        if source_count is not None
        else ("snapshot needed" if evidence.get("snapshot_status") == "unloaded" else str(evidence.get("snapshot_status")))
    )
    chips = list(card.get("chips") or [])
    if len(chips) >= 2:
        chips[1] = {
            **chips[1],
            "value": source_text,
            "status": status,
            "detail": f"snapshot={evidence.get('snapshot_status')}, heatmap={evidence.get('heatmap_status')}",
        }
    if len(chips) >= 3:
        chips[2] = {
            **chips[2],
            "status": "warn" if evidence.get("snapshot_status") in {"stale", "unloaded", "error"} else "ok",
            "detail": "Use refresh if snapshot is stale or absent",
        }
    card["chips"] = chips
    card["status"] = status
    return card


def _build_decision_card_payload(tab: str | None = None) -> dict[str, Any]:
    contracts = _decision_card_contracts_by_tab()
    if "market" in contracts:
        contracts["market"] = _apply_market_decision_evidence(contracts["market"])
    requested = str(tab or "").strip().lower()
    items = [contracts[requested]] if requested and requested in contracts else [contracts[item["tab"]] for item in _DECISION_CARD_CONTRACTS]
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract_version": "dashboard_decision_cards_v1",
        "scope": "backend-backed dashboard decision-support metadata; no synthetic scores or buy/sell recommendations",
        "items": items,
    }


@router.get("/decision-cards")
async def dashboard_decision_cards(tab: str | None = None) -> dict[str, Any]:
    """Common decision-support cards for dashboard tabs.

    The contract is intentionally metadata-only except for lightweight cached
    market freshness evidence. It must not fabricate tab-specific scores.
    """

    return _build_decision_card_payload(tab=tab)


def _bounded_text(value: str | None, max_len: int = 120) -> str:
    return str(value or "").strip()[:max_len]


def _split_symbols(raw: str | None, default: list[str] | None = None, limit: int = 12) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").replace(";", ",").split(","):
        for piece in token.split():
            clean = piece.strip().strip("$").upper()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            tokens.append(clean)
            if len(tokens) >= limit:
                return tokens
    fallback = default if default is not None else ["SPY", "QQQ", "TLT", "HYG", "LQD", "GLD", "BTC-USD", "DXY", "US10Y"]
    return fallback[:limit] if not tokens else tokens


def _cross_asset_data_symbol(symbol: str) -> str:
    clean = str(symbol or "").strip().upper()
    return _CROSS_ASSET_ALIASES.get(clean, clean)


def _cross_asset_profile(symbol: str) -> tuple[str, str]:
    clean = str(symbol or "").strip().upper()
    data_symbol = _cross_asset_data_symbol(clean)
    label, role = _CROSS_ASSET_LABELS.get(clean) or _CROSS_ASSET_LABELS.get(data_symbol) or (clean, "custom")
    if role == "custom":
        if clean.endswith("-USD"):
            role = "crypto"
        elif clean.endswith("=X"):
            role = "fx"
    return label, role


def _pct_change_from_close(close_values: Any, periods: int) -> float | None:
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


def _history_close_series(data_symbol: str, *, period: str = "6mo") -> Any:
    import yfinance as yf

    history = yf.Ticker(data_symbol).history(period=period, interval="1d", auto_adjust=False)
    if history is None or history.empty or "Close" not in history:
        raise RuntimeError("no close data")
    close = history["Close"].dropna()
    if close.empty:
        raise RuntimeError("empty close series")
    return close


def _date_label(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _collect_cross_asset_item(symbol: str) -> dict[str, Any]:
    display_symbol = str(symbol or "").strip().upper()
    data_symbol = _cross_asset_data_symbol(display_symbol)
    label, role = _cross_asset_profile(display_symbol)
    try:
        close = _history_close_series(data_symbol)
        latest_idx = close.index[-1]
        last_price = round(float(close.iloc[-1]), 4)
        returns = {
            "1d": _pct_change_from_close(close, 1),
            "5d": _pct_change_from_close(close, 5),
            "1m": _pct_change_from_close(close, 21),
            "3m": _pct_change_from_close(close, 63),
        }
        momentum = returns.get("1m")
        trend_score = 0.0 if momentum is None else max(-1.0, min(1.0, float(momentum) / 10.0))
        return {
            "symbol": display_symbol,
            "data_symbol": data_symbol,
            "label": label,
            "role": role,
            "price": last_price,
            "as_of": _date_label(latest_idx),
            "status": "ok",
            "is_decision_usable": True,
            "returns": returns,
            "trend_score": round(trend_score, 3),
            "source": "yfinance_daily_6mo",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_CROSS_ASSET] %s failed: %s", display_symbol, exc)
        return {
            "symbol": display_symbol,
            "data_symbol": data_symbol,
            "label": label,
            "role": role,
            "price": None,
            "as_of": "",
            "status": "unavailable",
            "is_decision_usable": False,
            "returns": {"1d": None, "5d": None, "1m": None, "3m": None},
            "trend_score": None,
            "source": "yfinance_daily_6mo",
            "error": str(exc),
        }


def _horizon_periods(horizon: str) -> int:
    return {"1d": 1, "5d": 5, "1m": 21, "3m": 63}.get(str(horizon or "").lower(), 21)


def _pair_ratio_points(close_a: Any, close_b: Any, *, limit: int = 90) -> list[dict[str, Any]]:
    import pandas as pd

    aligned = pd.concat([close_a.rename("a"), close_b.rename("b")], axis=1).dropna()
    if aligned.empty:
        return []
    if len(aligned) > limit:
        aligned = aligned.iloc[-limit:]
    base_a = float(aligned["a"].iloc[0])
    base_b = float(aligned["b"].iloc[0])
    points: list[dict[str, Any]] = []
    for idx, row in aligned.iterrows():
        a_value = float(row["a"])
        b_value = float(row["b"])
        ratio = None if b_value == 0 else a_value / b_value
        points.append({
            "date": _date_label(idx),
            "asset_a": round(a_value, 4),
            "asset_b": round(b_value, 4),
            "asset_a_index": round(a_value / base_a * 100.0, 4) if base_a else None,
            "asset_b_index": round(b_value / base_b * 100.0, 4) if base_b else None,
            "ratio": round(ratio, 6) if ratio is not None else None,
        })
    return points


def _pair_ratio_return(points: list[dict[str, Any]], periods: int) -> float | None:
    try:
        valid = [point for point in points if point.get("ratio") is not None]
        if len(valid) <= periods:
            return None
        current = float(valid[-1]["ratio"])
        previous = float(valid[-1 - periods]["ratio"])
        if previous == 0:
            return None
        return round((current / previous - 1.0) * 100.0, 2)
    except Exception:
        return None


def _finite_float(value: Any) -> float | None:
    try:
        n = float(value)
    except Exception:
        return None
    if not math.isfinite(n):
        return None
    return n


def _round_or_none(value: Any, digits: int = 4) -> float | None:
    n = _finite_float(value)
    return round(n, digits) if n is not None else None


def _pair_engineering_status(z_score: float | None, spread_return: float | None) -> str:
    z = _finite_float(z_score)
    spread = _finite_float(spread_return)
    if z is None and spread is None:
        return "insufficient_history"
    if z is not None and z >= 1.5:
        return "asset_a_rich"
    if z is not None and z <= -1.5:
        return "asset_a_cheap"
    if spread is not None and spread >= 1.0:
        return "asset_a_beta_leading"
    if spread is not None and spread <= -1.0:
        return "asset_b_beta_leading"
    return "balanced_spread"


def _pair_diagnostic_confidence(sample_count: int, correlation: float | None, tracking_error: float | None) -> str:
    corr = abs(_finite_float(correlation) or 0.0)
    te = _finite_float(tracking_error)
    if sample_count >= 60 and corr >= 0.5 and (te is None or te <= 35.0):
        return "high"
    if sample_count >= 30:
        return "medium"
    return "low"


def _pair_half_life_days(values: list[float]) -> float | None:
    if len(values) < 20:
        return None
    lag = values[:-1]
    delta = [values[idx + 1] - values[idx] for idx in range(len(values) - 1)]
    mean_lag = sum(lag) / len(lag)
    mean_delta = sum(delta) / len(delta)
    denominator = sum((value - mean_lag) ** 2 for value in lag)
    if denominator <= 0:
        return None
    slope = sum((lag[idx] - mean_lag) * (delta[idx] - mean_delta) for idx in range(len(delta))) / denominator
    if slope >= 0:
        return None
    half_life = -math.log(2) / slope
    if not math.isfinite(half_life) or half_life <= 0 or half_life > 252:
        return None
    return round(half_life, 1)


def _pair_financial_engineering(
    close_a: Any,
    close_b: Any,
    points: list[dict[str, Any]],
    *,
    horizon: str,
    symbol_a: str,
    symbol_b: str,
) -> dict[str, Any]:
    import pandas as pd

    periods = _horizon_periods(horizon)
    aligned = pd.concat([close_a.rename("a"), close_b.rename("b")], axis=1).dropna()
    if aligned.empty or len(aligned) < 3:
        return {
            "status": "insufficient_history",
            "sample_count": int(len(aligned)),
            "window_days": 0,
            "diagnostic_confidence": "low",
            "metrics": {},
            "levels": {},
            "scenarios": [],
            "risk_controls": ["겹치는 일별 가격 이력이 부족해 금융공학 진단을 보류합니다."],
        }

    window_days = min(126, int(len(aligned)))
    recent = aligned.tail(window_days).copy()
    returns = recent.pct_change().dropna()
    sample_count = int(len(returns))
    ret_a = returns["a"]
    ret_b = returns["b"]
    correlation = _round_or_none(ret_a.corr(ret_b), 4) if sample_count >= 2 else None
    variance_b = _finite_float(ret_b.var())
    covariance_ab = _finite_float(ret_a.cov(ret_b)) if sample_count >= 2 else None
    hedge_ratio = _round_or_none(covariance_ab / variance_b, 4) if variance_b and covariance_ab is not None else None

    beta_spread = None
    beta_spread_return_pct = None
    tracking_error = None
    horizon_noise_pct = None
    signal_to_noise = None
    if hedge_ratio is not None and sample_count >= 2:
        beta_spread = ret_a - (float(hedge_ratio) * ret_b)
        horizon_slice = beta_spread.tail(max(1, min(periods, len(beta_spread))))
        beta_spread_return_pct = _round_or_none(float(horizon_slice.sum()) * 100.0, 2)
        tracking_error = _round_or_none(float(beta_spread.std()) * math.sqrt(252.0) * 100.0, 2)
        if tracking_error is not None:
            horizon_noise_pct = _round_or_none(float(tracking_error) * math.sqrt(max(1, periods) / 252.0), 2)
        if beta_spread_return_pct is not None and horizon_noise_pct not in (None, 0):
            signal_to_noise = _round_or_none(float(beta_spread_return_pct) / float(horizon_noise_pct), 2)

    log_ratios: list[float] = []
    for _, row in recent.iterrows():
        a_value = _finite_float(row.get("a"))
        b_value = _finite_float(row.get("b"))
        if a_value is not None and b_value is not None and a_value > 0 and b_value > 0:
            log_ratios.append(math.log(a_value / b_value))
    ratio_window = log_ratios[-min(63, len(log_ratios)) :]
    ratio_zscore = None
    ratio_percentile = None
    if len(ratio_window) >= 3:
        mean_ratio = sum(ratio_window) / len(ratio_window)
        variance = sum((value - mean_ratio) ** 2 for value in ratio_window) / max(len(ratio_window) - 1, 1)
        std_ratio = math.sqrt(variance)
        if std_ratio > 0:
            ratio_zscore = _round_or_none((ratio_window[-1] - mean_ratio) / std_ratio, 2)
        ranked = sum(1 for value in ratio_window if value <= ratio_window[-1])
        ratio_percentile = round(ranked / len(ratio_window) * 100.0, 1)

    latest_ratio = _finite_float(points[-1].get("ratio")) if points else None
    recent_ratios = [_finite_float(point.get("ratio")) for point in points[-min(63, len(points)) :]]
    clean_ratios = [value for value in recent_ratios if value is not None]
    ratio_low = min(clean_ratios) if clean_ratios else None
    ratio_high = max(clean_ratios) if clean_ratios else None
    ratio_mid = (ratio_low + ratio_high) / 2.0 if ratio_low is not None and ratio_high is not None else None
    half_life = _pair_half_life_days(log_ratios)
    status = _pair_engineering_status(ratio_zscore, beta_spread_return_pct)
    confidence = _pair_diagnostic_confidence(sample_count, correlation, tracking_error)
    z_text = "중립권" if ratio_zscore is None else f"z={ratio_zscore:+.2f}"
    beta_text = "-" if hedge_ratio is None else f"{hedge_ratio:.2f}"
    spread_text = "-" if beta_spread_return_pct is None else f"{beta_spread_return_pct:+.2f}%"
    te_text = "-" if tracking_error is None else f"{tracking_error:.2f}%"
    return {
        "status": status,
        "sample_count": sample_count,
        "window_days": window_days,
        "diagnostic_confidence": confidence,
        "metrics": {
            "correlation": correlation,
            "hedge_ratio": hedge_ratio,
            "beta_adjusted_spread_return_pct": beta_spread_return_pct,
            "tracking_error_annualized_pct": tracking_error,
            "horizon_noise_pct": horizon_noise_pct,
            "signal_to_noise": signal_to_noise,
            "ratio_zscore": ratio_zscore,
            "ratio_percentile": ratio_percentile,
            "half_life_days": half_life,
        },
        "levels": {
            "latest_ratio": _round_or_none(latest_ratio, 6),
            "ratio_low_63d": _round_or_none(ratio_low, 6),
            "ratio_mid_63d": _round_or_none(ratio_mid, 6),
            "ratio_high_63d": _round_or_none(ratio_high, 6),
        },
        "beta_neutral_expression": f"{symbol_a} - {beta_text} x {symbol_b}",
        "engineering_read": (
            f"{symbol_a}/{symbol_b}는 최근 {sample_count}개 수익률 표본 기준 상관 {correlation if correlation is not None else '-'}, "
            f"헤지 베타 {beta_text}, 베타조정 스프레드 {spread_text}, 연율 추적오차 {te_text}, 비율 {z_text}입니다."
        ),
        "scenarios": [
            {
                "name": "Continuation",
                "trigger": f"{symbol_a}가 베타조정 스프레드 플러스와 63D 상단 돌파를 동시에 유지",
                "implication": f"{symbol_a} 상대 우위가 단순 방향성보다 강한 페어 모멘텀으로 해석됩니다.",
            },
            {
                "name": "Mean reversion",
                "trigger": "비율 z-score가 절대 1.5 이상에서 되돌림을 시작",
                "implication": "상대가격이 평균회귀 구간으로 들어가며 추격보다 리밸런싱 감시가 우선입니다.",
            },
            {
                "name": "Breakdown",
                "trigger": f"{symbol_b}가 방어/헤지 역할을 강화하고 베타조정 스프레드가 음수로 전환",
                "implication": f"{symbol_a} 우위 논리가 훼손되어 페어 목적 적합성을 다시 확인해야 합니다.",
            },
        ],
        "risk_controls": [
            "베타 헤지는 과거 일별 수익률 기반이며 구조 변화가 생기면 즉시 재추정해야 합니다.",
            "z-score는 평균회귀 진단이지 매수·매도 신호가 아닙니다.",
            "상관이 낮거나 추적오차가 크면 페어보다 독립 자산 두 개로 해석하는 편이 안전합니다.",
        ],
    }


def _gate(status: str, name: str, evidence: str, implication: str) -> dict[str, str]:
    return {
        "status": status,
        "name": name,
        "evidence": evidence,
        "implication": implication,
    }


def _pair_decision_memo(
    symbol_a: str,
    symbol_b: str,
    ratio_return: float | None,
    horizon: str,
    engineering: dict[str, Any],
    topic: str,
) -> dict[str, Any]:
    metrics = engineering.get("metrics") if isinstance(engineering.get("metrics"), dict) else {}
    sample_count = int(engineering.get("sample_count") or 0)
    confidence = str(engineering.get("diagnostic_confidence") or "low")
    corr = _finite_float(metrics.get("correlation"))
    hedge = _finite_float(metrics.get("hedge_ratio"))
    spread = _finite_float(metrics.get("beta_adjusted_spread_return_pct"))
    z_score = _finite_float(metrics.get("ratio_zscore"))
    signal_to_noise = _finite_float(metrics.get("signal_to_noise"))
    horizon_noise = _finite_float(metrics.get("horizon_noise_pct"))
    tracking_error = _finite_float(metrics.get("tracking_error_annualized_pct"))
    half_life = _finite_float(metrics.get("half_life_days"))
    abs_z = abs(z_score) if z_score is not None else 0.0
    abs_stn = abs(signal_to_noise) if signal_to_noise is not None else 0.0

    if sample_count < 30:
        grade = "data_insufficient"
        bias = "data_first"
    elif abs_z >= 1.5 and abs_stn >= 1.0:
        grade = "high_attention"
        bias = "extended_trend_with_reversion_risk" if spread and spread > 0 else "downside_spread_with_reversion_watch"
    elif abs_z >= 1.0 or abs_stn >= 0.75:
        grade = "monitor"
        bias = "conditional_follow_through"
    else:
        grade = "low_conviction"
        bias = "range_or_noise"

    corr_status = "ok" if corr is not None and abs(corr) >= 0.5 else ("warn" if corr is not None and abs(corr) >= 0.25 else "fail")
    spread_status = "ok" if signal_to_noise is not None and abs(signal_to_noise) >= 1.0 else ("warn" if signal_to_noise is not None and abs(signal_to_noise) >= 0.5 else "fail")
    z_status = "warn" if z_score is not None and abs_z >= 1.5 else ("ok" if z_score is not None else "fail")
    hedge_status = "ok" if hedge is not None and tracking_error is not None and tracking_error <= 25 else ("warn" if hedge is not None else "fail")
    mean_reversion_status = "ok" if half_life is not None and 3 <= half_life <= 60 else ("warn" if half_life is not None else "fail")
    ratio_text = "-" if ratio_return is None else f"{ratio_return:+.2f}%"
    stn_text = "-" if signal_to_noise is None else f"{signal_to_noise:+.2f}x"
    z_text = "-" if z_score is None else f"{z_score:+.2f}"
    corr_text = "-" if corr is None else f"{corr:.2f}"
    hedge_text = "-" if hedge is None else f"{hedge:.2f}"
    noise_text = "-" if horizon_noise is None else f"{horizon_noise:.2f}%"

    if grade == "high_attention":
        executive = (
            f"{symbol_a}/{symbol_b}는 {horizon.upper()} 상대수익률 {ratio_text}, 베타조정 신호대잡음 {stn_text}, "
            f"비율 z-score {z_text}로 통계적으로 눈에 띄는 구간입니다. 추세 추종과 평균회귀 리스크를 동시에 관리해야 합니다."
        )
    elif grade == "monitor":
        executive = (
            f"{symbol_a}/{symbol_b}는 방향 신호가 일부 있지만 확증은 부족합니다. {symbol_a} 우위가 이어지려면 "
            "베타조정 스프레드와 비율 레벨이 같은 방향으로 재확인되어야 합니다."
        )
    elif grade == "low_conviction":
        executive = (
            f"{symbol_a}/{symbol_b}는 현재 표본에서 유의한 페어 엣지가 약합니다. 단기 변동보다 레벨 돌파와 "
            "상관 회복 여부를 먼저 확인하는 편이 낫습니다."
        )
    else:
        executive = "겹치는 표본이 부족해 의사결정용 페어 판단을 보류합니다. 데이터 품질과 가격 이력을 먼저 확보해야 합니다."

    gates = [
        _gate(
            corr_status,
            "공동 움직임",
            f"상관 {corr_text}, 표본 {sample_count}개",
            "상관이 낮으면 페어 트레이드보다 독립 자산 두 개로 해석합니다.",
        ),
        _gate(
            hedge_status,
            "헤지 적합도",
            f"베타 {hedge_text}, 연율 추적오차 {tracking_error if tracking_error is not None else '-'}%",
            "추적오차가 높으면 베타 중립식의 방어력이 낮습니다.",
        ),
        _gate(
            spread_status,
            "스프레드 신호",
            f"베타조정 스프레드 {spread if spread is not None else '-'}%, 예상 노이즈 {noise_text}, S/N {stn_text}",
            "신호대잡음이 1배 미만이면 확증보다 감시 대상입니다.",
        ),
        _gate(
            z_status,
            "비율 위치",
            f"z-score {z_text}, percentile {metrics.get('ratio_percentile') if metrics.get('ratio_percentile') is not None else '-'}",
            "절대 z-score가 높으면 우위 신호와 과열 리스크를 같이 봅니다.",
        ),
        _gate(
            mean_reversion_status,
            "평균회귀성",
            f"반감기 {half_life if half_life is not None else '-'}일",
            "반감기가 추정되면 되돌림 감시선과 보유 기간을 분리합니다.",
        ),
    ]

    data_diagnosis = [
        f"분석 창: 최근 {engineering.get('window_days') or 0}거래일, 수익률 표본 {sample_count}개",
        f"상대수익률: {horizon.upper()} {ratio_text}, 베타조정 스프레드 {spread if spread is not None else '-'}%",
        f"분포 위치: z-score {z_text}, 신호대잡음 {stn_text}",
    ]
    if topic:
        data_diagnosis.insert(0, f"사용자 주제 반영: {topic}")

    next_tests = [
        f"{symbol_a}/{symbol_b} 비율이 63D 상단을 유지하는지 확인",
        "베타조정 스프레드가 0 아래로 꺾이는지 확인",
        "z-score가 +1.0 아래로 되돌아오면 평균회귀 모드로 전환",
        "상관이 0.25 아래로 내려가면 페어 해석 중단",
    ]
    invalidation = [
        "가격 데이터 최신성이 깨지거나 표본 수가 30개 미만이면 판단 보류",
        "상관 붕괴와 추적오차 확대가 동시에 나오면 헤지비율 재추정",
        "비율 돌파는 유지되지만 스프레드가 음수면 단순 방향성 착시 가능성 점검",
    ]
    return {
        "grade": grade,
        "bias": bias,
        "confidence": confidence,
        "executive_summary": executive,
        "data_diagnosis": data_diagnosis,
        "decision_gates": gates,
        "next_tests": next_tests,
        "invalidation": invalidation,
        "actionability": "advisory_monitor" if grade in {"high_attention", "monitor"} else "research_only",
        "method": "beta_adjusted_pair_decision_memo_v1",
    }


def _cross_asset_pair_briefing(
    symbol_a: str,
    symbol_b: str,
    item_a: dict[str, Any],
    item_b: dict[str, Any],
    ratio_return: float | None,
    horizon: str,
    topic: str,
    engineering: dict[str, Any] | None = None,
) -> dict[str, Any]:
    engineering = engineering or {}
    label_a, role_a = item_a.get("label") or symbol_a, item_a.get("role") or "custom"
    label_b, role_b = item_b.get("label") or symbol_b, item_b.get("role") or "custom"
    role_a_label = {"equity": "위험자산", "credit": "신용", "rates": "금리/채권", "commodity": "원자재", "crypto": "크립토", "fx": "FX"}.get(role_a, "사용자 자산")
    role_b_label = {"equity": "위험자산", "credit": "신용", "rates": "금리/채권", "commodity": "원자재", "crypto": "크립토", "fx": "FX"}.get(role_b, "사용자 자산")
    pair = f"{symbol_a}/{symbol_b}"
    horizon_label = horizon.upper()
    if ratio_return is None:
        stance = "unavailable"
        title = f"{pair} 상대 추세 데이터 부족"
        current = "두 자산의 겹치는 종가가 부족해 상대 차트를 의사결정에 쓰기 어렵습니다."
        forward = "데이터 공급자 응답과 심볼 매핑을 확인한 뒤 다시 실행해야 합니다."
    elif ratio_return >= 1.0:
        stance = "asset_a_leading"
        title = f"{symbol_a}가 {symbol_b} 대비 우위"
        current = f"{horizon_label} 기준 {pair} 비율이 {ratio_return:+.2f}% 상승해 {label_a}가 {label_b}보다 강합니다."
        forward = f"이 흐름이 유지되려면 {symbol_a} 가격 자체의 상승 또는 {symbol_b} 방어 수요 둔화가 이어져야 합니다."
    elif ratio_return <= -1.0:
        stance = "asset_b_leading"
        title = f"{symbol_b}가 {symbol_a} 대비 우위"
        current = f"{horizon_label} 기준 {pair} 비율이 {ratio_return:+.2f}% 하락해 {label_b}가 {label_a}보다 강합니다."
        forward = f"반전 확인 전까지는 {symbol_a}보다 {symbol_b} 쪽 상대 강도가 우세하다는 해석이 더 보수적입니다."
    else:
        stance = "range_bound"
        title = f"{pair} 상대 강도는 박스권"
        current = f"{horizon_label} 기준 {pair} 비율 변화가 {ratio_return:+.2f}%로 뚜렷한 상대 우위를 만들지 못했습니다."
        forward = "향후 방향은 최근 고점/저점 돌파와 두 자산의 동시 변동성 확대 여부를 확인해야 합니다."

    purpose_fit = (
        f"{pair}는 {role_a_label}과 {role_b_label}의 상대 선호를 직접 보는 용도입니다. "
        "절대 매수·매도 신호가 아니라 포트폴리오 기울기, 헤지 강도, 리스크 선호 변화 점검에 맞습니다."
    )
    watch_points = [
        f"{symbol_a} 단독 추세와 거래량이 비율 방향을 확인하는지",
        f"{symbol_b}가 방어/헤지 역할을 강화하거나 약화하는지",
        f"{pair} 비율의 최근 고점·저점 돌파 여부",
    ]
    if topic:
        watch_points.insert(0, f"사용자 주제와 연결: {topic}")
    decision_memo = _pair_decision_memo(symbol_a, symbol_b, ratio_return, horizon, engineering, topic)
    return {
        "status": stance,
        "title": title,
        "current_interpretation": current,
        "forward_direction": forward,
        "purpose_fit": purpose_fit,
        "watch_points": watch_points,
        "decision_memo": decision_memo,
        "engineering_interpretation": engineering.get("engineering_read") or "상관·베타·z-score 진단은 겹치는 가격 이력이 충분할 때 표시됩니다.",
        "risk_controls": engineering.get("risk_controls") or [
            "페어 비율은 상대 강도 감시용이며 단독 매수·매도 신호가 아닙니다.",
        ],
        "model": "deterministic_cross_asset_pair_brief_v3",
        "mode": "deterministic_guardrail",
        "advisory_only": True,
    }


def _collect_cross_asset_pair_analysis(
    clean_symbols: list[str],
    items: list[dict[str, Any]],
    horizon: str,
    topic: str,
) -> dict[str, Any] | None:
    if len(clean_symbols) < 2:
        return None
    symbol_a, symbol_b = clean_symbols[0], clean_symbols[1]
    item_a = next((item for item in items if item.get("symbol") == symbol_a), {})
    item_b = next((item for item in items if item.get("symbol") == symbol_b), {})
    try:
        close_a = _history_close_series(_cross_asset_data_symbol(symbol_a))
        close_b = _history_close_series(_cross_asset_data_symbol(symbol_b))
        points = _pair_ratio_points(close_a, close_b)
        if not points:
            raise RuntimeError("no overlapping close data")
        horizon_return = _pair_ratio_return(points, _horizon_periods(horizon))
        latest = points[-1]
        engineering = _pair_financial_engineering(
            close_a,
            close_b,
            points,
            horizon=horizon,
            symbol_a=symbol_a,
            symbol_b=symbol_b,
        )
        briefing = _cross_asset_pair_briefing(
            symbol_a,
            symbol_b,
            item_a,
            item_b,
            horizon_return,
            horizon,
            topic,
            engineering,
        )
        return {
            "status": "ok",
            "pair": f"{symbol_a}/{symbol_b}",
            "asset_a": {"symbol": symbol_a, "label": item_a.get("label") or symbol_a, "role": item_a.get("role") or "custom"},
            "asset_b": {"symbol": symbol_b, "label": item_b.get("label") or symbol_b, "role": item_b.get("role") or "custom"},
            "horizon": horizon,
            "horizon_return_pct": horizon_return,
            "latest_ratio": latest.get("ratio"),
            "as_of": latest.get("date") or "",
            "points": points,
            "financial_engineering": engineering,
            "ai_briefing": briefing,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DASHBOARD_CROSS_ASSET_PAIR] %s/%s failed: %s", symbol_a, symbol_b, exc)
        return {
            "status": "unavailable",
            "pair": f"{symbol_a}/{symbol_b}",
            "asset_a": {"symbol": symbol_a, "label": item_a.get("label") or symbol_a, "role": item_a.get("role") or "custom"},
            "asset_b": {"symbol": symbol_b, "label": item_b.get("label") or symbol_b, "role": item_b.get("role") or "custom"},
            "horizon": horizon,
            "horizon_return_pct": None,
            "latest_ratio": None,
            "as_of": "",
            "points": [],
            "financial_engineering": {
                "status": "insufficient_history",
                "sample_count": 0,
                "window_days": 0,
                "diagnostic_confidence": "low",
                "metrics": {},
                "levels": {},
                "scenarios": [],
                "risk_controls": ["페어 분석용 겹치는 가격 이력을 확보하지 못했습니다."],
            },
            "ai_briefing": _cross_asset_pair_briefing(symbol_a, symbol_b, item_a, item_b, None, horizon, topic),
            "error": str(exc),
        }


def _avg_return(items: list[dict[str, Any]], roles: set[str], horizon: str) -> float | None:
    values = [
        float(item["returns"][horizon])
        for item in items
        if item.get("role") in roles and isinstance(item.get("returns"), dict) and item["returns"].get(horizon) is not None
    ]
    return round(sum(values) / len(values), 2) if values else None


def _cross_asset_summary(items: list[dict[str, Any]], horizon: str, topic: str) -> dict[str, Any]:
    usable = [item for item in items if item.get("is_decision_usable")]
    equity = _avg_return(usable, {"equity"}, horizon)
    credit = _avg_return(usable, {"credit"}, horizon)
    rates = _avg_return(usable, {"rates"}, horizon)
    defensive = _avg_return(usable, {"rates", "commodity", "fx"}, horizon)
    crypto = _avg_return(usable, {"crypto"}, horizon)

    risk_score = 0.0
    contributors: list[str] = []
    if equity is not None:
        risk_score += equity * 0.6
        contributors.append(f"equity {equity:+.2f}%")
    if credit is not None:
        risk_score += credit * 0.35
        contributors.append(f"credit {credit:+.2f}%")
    if crypto is not None:
        risk_score += crypto * 0.15
        contributors.append(f"crypto {crypto:+.2f}%")
    if defensive is not None:
        risk_score -= defensive * 0.25
        contributors.append(f"defensive {defensive:+.2f}%")
    if rates is not None and rates > 2.0:
        risk_score -= rates * 0.2

    if not usable:
        state = "unavailable"
        title = "데이터 부족"
        current = "의사결정에 사용할 수 있는 교차자산 가격 데이터가 없습니다."
        forward = "공급자 응답을 새로고침한 뒤 다시 확인해야 합니다."
    elif risk_score >= 1.2:
        state = "risk_on"
        title = "위험선호 우위"
        current = "주식/신용/성장자산 쪽 모멘텀이 방어자산 압력보다 강합니다."
        forward = "금리와 달러가 안정되면 위험자산 추세가 유지될 가능성이 높지만, 신용 스프레드 악화는 빠르게 확인해야 합니다."
    elif risk_score <= -1.2:
        state = "risk_off"
        title = "방어적 압력 우위"
        current = "방어자산 또는 금리/달러 압력이 위험자산 흐름을 누르고 있습니다."
        forward = "단기 반등이 나오더라도 신용과 지수 breadth가 회복되기 전까지는 보수적 해석이 필요합니다."
    else:
        state = "mixed"
        title = "혼재 국면"
        current = "교차자산 흐름이 한 방향으로 정렬되지 않았습니다."
        forward = "다음 방향성은 금리, 달러, 신용 ETF, 주도 섹터가 같은 방향으로 재정렬되는지에 달려 있습니다."

    watch = ["금리와 장기채 반응", "HYG/LQD 신용 ETF", "달러 지수", "원자재와 성장자산 괴리"]
    if topic:
        watch.insert(0, f"사용자 주제: {topic}")
    return {
        "state": state,
        "title": title,
        "risk_score": round(risk_score, 2),
        "current_state": current,
        "forward_bias": forward,
        "contributors": contributors,
        "watch_points": watch,
        "role_returns": {
            "equity": equity,
            "credit": credit,
            "rates": rates,
            "defensive": defensive,
            "crypto": crypto,
        },
    }


@router.get("/cross-asset/analyze")
async def dashboard_cross_asset_analyze(
    symbols: str | None = None,
    topic: str | None = None,
    horizon: str = "1m",
) -> dict[str, Any]:
    """User-controlled cross-asset decision-support surface for the dashboard."""

    clean_horizon = str(horizon or "1m").strip().lower()
    if clean_horizon not in {"1d", "5d", "1m", "3m"}:
        clean_horizon = "1m"
    clean_topic = _bounded_text(topic, 160)
    clean_symbols = _split_symbols(symbols)
    items = await asyncio.gather(*(asyncio.to_thread(_collect_cross_asset_item, symbol) for symbol in clean_symbols))
    usable_count = sum(1 for item in items if item.get("is_decision_usable"))
    summary = _cross_asset_summary(list(items), clean_horizon, clean_topic)
    pair_analysis = await asyncio.to_thread(
        _collect_cross_asset_pair_analysis,
        clean_symbols,
        list(items),
        clean_horizon,
        clean_topic,
    )
    return {
        "status": "ok" if usable_count else "unavailable",
        "symbols": clean_symbols,
        "topic": clean_topic,
        "horizon": clean_horizon,
        "items": items,
        "pair_analysis": pair_analysis,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "yfinance",
        "analysis_engine": "deterministic_cross_asset_v4",
        "advisory_only": True,
        "decision_usable_count": usable_count,
        "guardrails": [
            "no_buy_sell_recommendation",
            "freshness_visible",
            "deterministic_price_inputs",
            "pair_ratio_not_absolute_signal",
            "beta_hedge_is_diagnostic_only",
            "zscore_is_not_trade_signal",
            "decision_memo_requires_gate_confirmation",
        ],
    }


@router.get("/news")
async def dashboard_news(
    limit: int = 20,
    query: str | None = None,
    ticker: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
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
    clean_query = _bounded_text(query, 180)
    clean_topic = _bounded_text(topic, 120)
    clean_ticker = _split_symbols(ticker, default=[], limit=1)
    focused_entries: list[dict[str, Any]] = []
    if clean_ticker:
        symbol = clean_ticker[0]
        focused_entries.append({
            "symbol": symbol,
            "query": clean_query or f'("{symbol}" OR "{symbol} stock" OR "{symbol} earnings" OR "{symbol} company") (Reuters OR CNBC OR Bloomberg OR "Wall Street Journal" OR "Financial Times" OR "Yahoo Finance")',
            "category": "company_news",
            "lookback": 14,
        })
    if clean_topic:
        topic_query = clean_query or f'("{clean_topic}") (Reuters OR CNBC OR Bloomberg OR "Wall Street Journal" OR "Financial Times" OR "Yahoo Finance")'
        focused_entries.append({
            "symbol": "TOPIC",
            "query": topic_query,
            "category": "topic_news",
            "lookback": 14,
        })
    elif clean_query and not focused_entries:
        focused_entries.append({
            "symbol": "QUERY",
            "query": clean_query,
            "category": "topic_news",
            "lookback": 14,
        })
    if focused_entries:
        watchlist = focused_entries + watchlist
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
        "company_news": tuple(filter(None, [clean_ticker[0].lower() if clean_ticker else "", "earnings", "guidance", "revenue", "stock", "shares", "company"])),
        "topic_news": tuple(word.lower() for word in clean_topic.split() if word) or ("market", "stock", "policy", "earnings"),
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
        "selection_policy": "focused_query_plus_market_coverage" if focused_entries else "major_source_priority_issue_coverage",
        "query": clean_query,
        "ticker": clean_ticker[0] if clean_ticker else "",
        "topic": clean_topic,
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
        if not force:
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
