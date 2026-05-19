"""
Persistent run history for FinGPT analyses.

Every analysis run is archived in ``data/outputs/runs/{TICKER}/{TIMESTAMP}/``
alongside the overwrite-based ``latest_*`` mirror. A tiny SQLite index
(``data/runs.db``) keeps querying fast for the UI history panel and any
downstream comparison tooling.

This module is intentionally dependency-free and synchronous: the research
pipeline offloads the ``save_outputs`` call to ``asyncio.to_thread`` already.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.utils.logger import get_logger

logger = get_logger("pipelines.output.history")

DB_FILENAME = "runs.db"
RUNS_SUBDIR = "runs"

_INVALID_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_segment(value: str) -> str:
    cleaned = _INVALID_SEGMENT.sub("_", (value or "").strip())
    return cleaned or "UNKNOWN"


def _db_path(outputs_dir: Path) -> Path:
    return outputs_dir.parent / DB_FILENAME


def _runs_dir(outputs_dir: Path) -> Path:
    return outputs_dir / RUNS_SUBDIR


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            question TEXT NOT NULL,
            status TEXT NOT NULL,
            sentiment TEXT,
            confidence REAL,
            model TEXT,
            lookback_days INTEGER,
            top_k INTEGER,
            sources TEXT,
            created_at TEXT NOT NULL,
            run_dir TEXT NOT NULL,
            error_metadata TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_ticker_created "
        "ON runs(ticker, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_created "
        "ON runs(created_at DESC)"
    )
    conn.commit()
    return conn


def archive_run(
    *,
    outputs_dir: Path,
    request_json: str,
    response_json: str,
    report_md: str,
    report_html: str,
    collection_sidecar: Optional[Dict[str, Any]],
    ticker: str,
    question: str,
    status: str,
    sentiment: Optional[str],
    confidence: Optional[float],
    model: Optional[str],
    lookback_days: Optional[int],
    top_k: Optional[int],
    sources: Optional[List[str]],
    error_metadata: Optional[str],
) -> Dict[str, Any]:
    """
    Persist the current run into ``runs/{TICKER}/{TIMESTAMP}/`` and index it.
    Returns a metadata dict describing the archived run. Failures here must not
    break the caller; archival is best-effort.
    """
    try:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        run_id = uuid.uuid4().hex[:12]
        timestamp = now.strftime("%Y%m%dT%H%M%SZ") + f"_{run_id}"
        ticker_seg = _safe_segment(ticker.upper())
        run_dir = _runs_dir(outputs_dir) / ticker_seg / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        (run_dir / "request.json").write_text(request_json, encoding="utf-8")
        (run_dir / "response.json").write_text(response_json, encoding="utf-8")
        (run_dir / "report.md").write_text(report_md, encoding="utf-8")
        (run_dir / "report.html").write_text(report_html, encoding="utf-8")
        if collection_sidecar is not None:
            (run_dir / "collection.json").write_text(
                json.dumps(collection_sidecar, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        index_entry = {
            "id": run_id,
            "ticker": ticker_seg,
            "question": question or "",
            "status": status or "unknown",
            "sentiment": sentiment,
            "confidence": float(confidence) if confidence is not None else None,
            "model": model,
            "lookback_days": lookback_days,
            "top_k": top_k,
            "sources": json.dumps(sources or [], ensure_ascii=False),
            "created_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "run_dir": str(run_dir.relative_to(outputs_dir.parent)).replace("\\", "/"),
            "error_metadata": error_metadata,
        }

        db_path = _db_path(outputs_dir)
        with _connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs
                  (id, ticker, question, status, sentiment, confidence, model,
                   lookback_days, top_k, sources, created_at, run_dir, error_metadata)
                VALUES
                  (:id, :ticker, :question, :status, :sentiment, :confidence, :model,
                   :lookback_days, :top_k, :sources, :created_at, :run_dir, :error_metadata)
                """,
                index_entry,
            )
            conn.commit()

        logger.info(f"[HISTORY_ARCHIVED] run_id={run_id} dir={run_dir}")
        return index_entry
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[HISTORY_ARCHIVE_FAILED] {exc}")
        return {}


def list_runs(
    *,
    outputs_dir: Path,
    ticker: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    db_path = _db_path(outputs_dir)
    if not db_path.exists():
        return []
    with _connect(db_path) as conn:
        params: List[Any] = []
        where = ""
        if ticker:
            where = "WHERE ticker = ?"
            params.append(_safe_segment(ticker.upper()))
        # Optional WHERE clause is selected from a fixed template.
        sql = " ".join(
            [
                "SELECT id, ticker, question, status, sentiment, confidence, model,",
                "lookback_days, top_k, sources, created_at, run_dir, error_metadata",
                "FROM runs",
                where,
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            ]
        )
        params.extend([int(limit), int(offset)])
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_run(
    *,
    outputs_dir: Path,
    run_id: str,
) -> Optional[Dict[str, Any]]:
    db_path = _db_path(outputs_dir)
    if not db_path.exists():
        return None
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, ticker, question, status, sentiment, confidence, model, "
            "lookback_days, top_k, sources, created_at, run_dir, error_metadata "
            "FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    meta = _row_to_dict(row)
    run_abs = outputs_dir.parent / meta["run_dir"]
    meta["artifacts"] = _read_artifacts(run_abs)
    return meta


def ticker_summary(
    *,
    outputs_dir: Path,
    ticker: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Lightweight per-ticker time series for UI mini-charts."""
    return [
        {
            "id": entry["id"],
            "created_at": entry["created_at"],
            "status": entry["status"],
            "sentiment": entry["sentiment"],
            "confidence": entry["confidence"],
        }
        for entry in list_runs(outputs_dir=outputs_dir, ticker=ticker, limit=limit)
    ]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    if data.get("id") and not data.get("run_id"):
        data["run_id"] = data["id"]
    try:
        data["sources"] = json.loads(data.get("sources") or "[]")
    except Exception:
        data["sources"] = []
    return data


def _read_artifacts(run_dir: Path) -> Dict[str, Any]:
    artifacts: Dict[str, Any] = {
        "request": None,
        "response": None,
        "collection": None,
        "report_md": None,
        "has_html": False,
    }
    if not run_dir.exists():
        return artifacts
    try:
        artifacts["request"] = _load_json(run_dir / "request.json")
        artifacts["response"] = _load_json(run_dir / "response.json")
        artifacts["collection"] = _load_json(run_dir / "collection.json")
        md_path = run_dir / "report.md"
        if md_path.exists():
            artifacts["report_md"] = md_path.read_text(encoding="utf-8")
        artifacts["has_html"] = (run_dir / "report.html").exists()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"[HISTORY_READ_FAILED] dir={run_dir} error={exc}")
    return artifacts


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
