from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.config.settings import load_settings


_FILENAME = "compare_watchlists.json"
_MAX_WATCHLISTS = 48
_MAX_TICKERS = 12
_lock = threading.RLock()


@dataclass
class QuantamentalCompareWatchlist:
    id: str
    name: str
    tickers: list[str]
    market: str = "US"
    style: str = "balanced"
    expand_peer_universe: bool = False
    peer_limit: int = 8
    created_at: str = ""
    updated_at: str = ""
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def list_watchlists() -> dict[str, Any]:
    with _lock:
        items = [item.to_dict() for item in _read_all()]
    return {"status": "ok", "items": items, "count": len(items), "storage": "json", "path": str(_watchlist_path())}


def upsert_watchlist(payload: dict[str, Any], *, item_id: str | None = None) -> dict[str, Any]:
    normalized = _normalize_payload(payload, item_id=item_id)
    with _lock:
        items = _read_all()
        now = _now_iso()
        if item_id:
            for idx, existing in enumerate(items):
                if existing.id == item_id:
                    updated = QuantamentalCompareWatchlist(
                        **{
                            **existing.to_dict(),
                            **normalized,
                            "id": existing.id,
                            "created_at": existing.created_at,
                            "updated_at": now,
                        }
                    )
                    items[idx] = updated
                    _write_all(items)
                    return {"status": "ok", "item": updated.to_dict(), "storage": "json", "path": str(_watchlist_path())}
            raise KeyError(f"quantamental compare watchlist not found: {item_id}")

        for idx, existing in enumerate(items):
            if existing.name.lower() == str(normalized["name"]).lower():
                updated = QuantamentalCompareWatchlist(
                    **{
                        **existing.to_dict(),
                        **normalized,
                        "id": existing.id,
                        "created_at": existing.created_at,
                        "updated_at": now,
                    }
                )
                items[idx] = updated
                _write_all(items)
                return {"status": "ok", "item": updated.to_dict(), "storage": "json", "path": str(_watchlist_path())}

        if len(items) >= _MAX_WATCHLISTS:
            raise ValueError(f"compare watchlist store is full (max {_MAX_WATCHLISTS})")
        created = QuantamentalCompareWatchlist(id=uuid.uuid4().hex, created_at=now, updated_at=now, **normalized)
        items.append(created)
        _write_all(items)
        return {"status": "ok", "item": created.to_dict(), "storage": "json", "path": str(_watchlist_path())}


def delete_watchlist(item_id: str) -> dict[str, Any]:
    clean = str(item_id or "").strip()
    with _lock:
        items = _read_all()
        kept = [item for item in items if item.id != clean]
        if len(kept) == len(items):
            raise KeyError(f"quantamental compare watchlist not found: {item_id}")
        _write_all(kept)
    return {"status": "ok", "deleted": True, "id": clean, "storage": "json", "path": str(_watchlist_path())}


def _normalize_payload(payload: dict[str, Any], *, item_id: str | None = None) -> dict[str, Any]:
    name = str(payload.get("name") or "Quantamental Set").strip()[:80]
    tickers = _clean_tickers(payload.get("tickers") or [])
    if not name:
        raise ValueError("name is required")
    if len(tickers) < 2:
        raise ValueError("at least two tickers are required")
    market = str(payload.get("market") or "US").upper().strip()
    if market not in {"US", "KR", "GLOBAL"}:
        raise ValueError("market must be one of US, KR, GLOBAL")
    style = str(payload.get("style") or "balanced").strip()
    if style not in {"balanced", "quality_growth", "value", "momentum", "defensive"}:
        raise ValueError("unsupported quantamental style")
    return {
        "name": name,
        "tickers": tickers,
        "market": market,
        "style": style,
        "expand_peer_universe": bool(payload.get("expand_peer_universe", False)),
        "peer_limit": max(2, min(20, int(payload.get("peer_limit") or 8))),
        "notes": payload.get("notes") or None,
        "metadata": dict(payload.get("metadata") or {}),
    }


def _clean_tickers(raw: Iterable[Any] | str) -> list[str]:
    values = str(raw).replace(",", " ").split() if isinstance(raw, str) else list(raw or [])
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        ticker = str(item or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append(ticker)
        if len(cleaned) >= _MAX_TICKERS:
            break
    return cleaned


def _read_all() -> list[QuantamentalCompareWatchlist]:
    path = _watchlist_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    items: list[QuantamentalCompareWatchlist] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            normalized = _normalize_payload(raw, item_id=str(raw.get("id") or ""))
            items.append(
                QuantamentalCompareWatchlist(
                    id=str(raw.get("id") or uuid.uuid4().hex),
                    created_at=str(raw.get("created_at") or _now_iso()),
                    updated_at=str(raw.get("updated_at") or raw.get("created_at") or _now_iso()),
                    **normalized,
                )
            )
        except (TypeError, ValueError):
            continue
    return items


def _write_all(items: Iterable[QuantamentalCompareWatchlist]) -> None:
    path = _watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "saved_at": _now_iso(), "items": [item.to_dict() for item in items]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _watchlist_path() -> Path:
    override = os.getenv("QUANTAMENTAL_DATA_DIR", "").strip()
    root = Path(override) if override else load_settings().data_dir / "quantamental"
    return root / _FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
