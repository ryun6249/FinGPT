from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from csv import DictWriter
from io import StringIO
from pathlib import Path
from typing import Any

from core.config.settings import load_settings
from pipelines.quantamental.providers import now_iso


def save_snapshot(payload: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
    clean_payload = dict(payload)
    clean_payload.pop("snapshot", None)
    snapshot_id = _snapshot_id(clean_payload)
    ticker = str(clean_payload.get("ticker") or "").upper()
    market = str(clean_payload.get("market") or "US").upper()
    composite = clean_payload.get("composite") or {}
    signal = clean_payload.get("signal") or {}
    quality = clean_payload.get("data_quality") or {}
    created_at = now_iso()
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO quantamental_snapshots(
                snapshot_id, ticker, market, style, generated_at, created_at,
                signal_label, final_score, quality_level, request_json, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                created_at=excluded.created_at,
                signal_label=excluded.signal_label,
                final_score=excluded.final_score,
                quality_level=excluded.quality_level,
                request_json=excluded.request_json,
                payload_json=excluded.payload_json
            """,
            (
                snapshot_id,
                ticker,
                market,
                str(clean_payload.get("style") or composite.get("style") or ""),
                str(clean_payload.get("generated_at") or created_at),
                created_at,
                str(signal.get("signal_label") or ""),
                composite.get("final_score"),
                str(quality.get("quality_level") or ""),
                json.dumps(request or {}, ensure_ascii=False, sort_keys=True),
                json.dumps(clean_payload, ensure_ascii=False, sort_keys=True),
            ),
        )
    return {
        "snapshot_id": snapshot_id,
        "status": "saved",
        "storage": "sqlite",
        "database": str(path),
        "created_at": created_at,
    }


def list_snapshots(ticker: str | None = None, *, limit: int = 20) -> dict[str, Any]:
    path = db_path()
    if not path.exists():
        return {"status": "ok", "items": [], "count": 0, "storage": "sqlite", "database": str(path)}
    clean = str(ticker or "").upper().strip()
    with _connect(path) as conn:
        _ensure_schema(conn)
        if clean:
            rows = conn.execute(
                """
                SELECT snapshot_id, ticker, market, style, generated_at, created_at,
                       signal_label, final_score, quality_level
                FROM quantamental_snapshots
                WHERE ticker=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (clean, max(1, min(int(limit or 20), 100))),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT snapshot_id, ticker, market, style, generated_at, created_at,
                       signal_label, final_score, quality_level
                FROM quantamental_snapshots
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit or 20), 100)),),
            ).fetchall()
    items = [dict(row) for row in rows]
    return {"status": "ok", "items": items, "count": len(items), "storage": "sqlite", "database": str(path)}


def get_snapshot(snapshot_id: str) -> dict[str, Any]:
    clean = str(snapshot_id or "").strip()
    if not clean:
        return {"status": "failed", "error": "snapshot_id_required"}
    path = db_path()
    if not path.exists():
        return {"status": "failed", "error": "snapshot_store_missing", "snapshot_id": clean}
    with _connect(path) as conn:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT snapshot_id, request_json, payload_json FROM quantamental_snapshots WHERE snapshot_id=?",
            (clean,),
        ).fetchone()
    if not row:
        return {"status": "failed", "error": "snapshot_not_found", "snapshot_id": clean}
    payload = json.loads(row["payload_json"])
    return {
        "status": "ok",
        "snapshot_id": row["snapshot_id"],
        "request": json.loads(row["request_json"] or "{}"),
        "payload": payload,
        "storage": "sqlite",
        "database": str(path),
    }


def export_snapshot(snapshot_id: str, *, fmt: str = "json") -> dict[str, Any]:
    snapshot = get_snapshot(snapshot_id)
    if snapshot.get("status") != "ok":
        return snapshot
    clean_format = str(fmt or "json").lower().strip()
    if clean_format == "json":
        return {
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "format": "json",
            "media_type": "application/json",
            "filename": f"quantamental_{snapshot.get('snapshot_id')}.json",
            "content": json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
        }
    if clean_format == "csv":
        row = _snapshot_csv_row(snapshot.get("payload") or {})
        row["snapshot_id"] = snapshot.get("snapshot_id") or ""
        out = StringIO()
        writer = DictWriter(out, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        return {
            "status": "ok",
            "snapshot_id": snapshot.get("snapshot_id"),
            "format": "csv",
            "media_type": "text/csv",
            "filename": f"quantamental_{snapshot.get('snapshot_id')}.csv",
            "content": out.getvalue(),
        }
    return {"status": "failed", "error": "unsupported_snapshot_export_format", "supported_formats": ["json", "csv"]}


def diff_snapshots(base_snapshot_id: str, target_snapshot_id: str) -> dict[str, Any]:
    base = get_snapshot(base_snapshot_id)
    target = get_snapshot(target_snapshot_id)
    if base.get("status") != "ok":
        return {"status": "failed", "error": "base_snapshot_unavailable", "base": base}
    if target.get("status") != "ok":
        return {"status": "failed", "error": "target_snapshot_unavailable", "target": target}
    base_payload = base.get("payload") or {}
    target_payload = target.get("payload") or {}
    paths = [
        "status",
        "ticker",
        "market",
        "style",
        "signal.signal_label",
        "signal.signal_score",
        "signal.signal_confidence",
        "composite.final_score",
        "composite.fundamental_score",
        "composite.quant_score",
        "composite.risk_score",
        "risk.risk_level",
        "data_quality.quality_level",
        "data_quality.data_quality_score",
        "factors.value_score",
        "factors.quality_score",
        "factors.growth_score",
        "factors.momentum_score",
        "factors.low_volatility_score",
        "factors.liquidity_score",
    ]
    differences = []
    for path in paths:
        before = _path_get(base_payload, path)
        after = _path_get(target_payload, path)
        if before != after:
            differences.append({"path": path, "before": before, "after": after})
    return {
        "status": "ok",
        "base_snapshot_id": base.get("snapshot_id"),
        "target_snapshot_id": target.get("snapshot_id"),
        "difference_count": len(differences),
        "differences": differences,
        "not_investment_advice": True,
    }


def prune_snapshots(ticker: str | None = None, *, keep_last: int = 20, dry_run: bool = True) -> dict[str, Any]:
    keep = max(1, min(500, int(keep_last or 20)))
    clean = str(ticker or "").upper().strip()
    path = db_path()
    if not path.exists():
        return {"status": "ok", "dry_run": dry_run, "keep_last": keep, "prune_count": 0, "items": [], "database": str(path)}
    with _connect(path) as conn:
        _ensure_schema(conn)
        if clean:
            rows = conn.execute(
                """
                SELECT snapshot_id, ticker, created_at, generated_at, signal_label, final_score
                FROM quantamental_snapshots
                WHERE ticker=?
                ORDER BY created_at DESC
                """,
                (clean,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT snapshot_id, ticker, created_at, generated_at, signal_label, final_score
                FROM quantamental_snapshots
                ORDER BY ticker ASC, created_at DESC
                """
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            item = dict(row)
            grouped.setdefault(str(item.get("ticker") or ""), []).append(item)
        candidates: list[dict[str, Any]] = []
        for items in grouped.values():
            candidates.extend(items[keep:])
        if candidates and not dry_run:
            conn.executemany(
                "DELETE FROM quantamental_snapshots WHERE snapshot_id=?",
                [(item["snapshot_id"],) for item in candidates],
            )
    return {
        "status": "ok",
        "dry_run": bool(dry_run),
        "ticker": clean or None,
        "keep_last": keep,
        "prune_count": len(candidates),
        "items": candidates,
        "database": str(path),
    }


def db_path() -> Path:
    override = os.getenv("QUANTAMENTAL_DATA_DIR", "").strip()
    root = Path(override) if override else load_settings().data_dir / "quantamental"
    return root / "quantamental.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quantamental_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL,
            style TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            signal_label TEXT,
            final_score REAL,
            quality_level TEXT,
            request_json TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quantamental_snapshots_ticker_created ON quantamental_snapshots(ticker, created_at DESC)")


def _snapshot_id(payload: dict[str, Any]) -> str:
    seed = json.dumps(
        {
            "ticker": payload.get("ticker"),
            "market": payload.get("market"),
            "style": payload.get("style"),
            "generated_at": payload.get("generated_at"),
            "signal": (payload.get("signal") or {}).get("signal_label"),
            "score": (payload.get("composite") or {}).get("final_score"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()[:20]


def _snapshot_csv_row(payload: dict[str, Any]) -> dict[str, Any]:
    composite = payload.get("composite") or {}
    signal = payload.get("signal") or {}
    quality = payload.get("data_quality") or {}
    risk = payload.get("risk") or {}
    factors = payload.get("factors") or {}
    snapshot = payload.get("snapshot") or {}
    return {
        "snapshot_id": snapshot.get("snapshot_id") or "",
        "ticker": payload.get("ticker") or "",
        "market": payload.get("market") or "",
        "style": payload.get("style") or composite.get("style") or "",
        "generated_at": payload.get("generated_at") or "",
        "status": payload.get("status") or "",
        "signal_label": signal.get("signal_label") or "",
        "signal_score": signal.get("signal_score"),
        "signal_confidence": signal.get("signal_confidence") or "",
        "final_score": composite.get("final_score"),
        "fundamental_score": composite.get("fundamental_score"),
        "quant_score": composite.get("quant_score"),
        "risk_score": composite.get("risk_score"),
        "risk_level": risk.get("risk_level") or "",
        "quality_level": quality.get("quality_level") or "",
        "data_quality_score": quality.get("data_quality_score"),
        "value_score": factors.get("value_score"),
        "quality_score": factors.get("quality_score"),
        "growth_score": factors.get("growth_score"),
        "momentum_score": factors.get("momentum_score"),
        "low_volatility_score": factors.get("low_volatility_score"),
        "liquidity_score": factors.get("liquidity_score"),
    }


def _path_get(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value
