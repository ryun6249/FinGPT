from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from core.schemas.forecast import ForecastJobSubmitRequest, ForecastRunRequest
from pipelines.forecast.common import now_iso
from pipelines.forecast.experiment_store import forecast_root

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
_LOCK = threading.Lock()
_FUTURES: dict[str, Future] = {}


def _worker_count() -> int:
    raw = os.environ.get("FORECAST_JOB_WORKERS", "1").strip()
    try:
        return max(1, min(int(raw), 4))
    except ValueError:
        return 1


_EXECUTOR = ThreadPoolExecutor(max_workers=_worker_count(), thread_name_prefix="forecast-job")


def submit_forecast_job(request: ForecastJobSubmitRequest, *, run_inline: bool = False) -> dict[str, Any]:
    _init_job_db()
    job_id = f"fj_{uuid.uuid4().hex[:20]}"
    created_at = now_iso()
    forecast_request = request.request
    summary = _request_summary(forecast_request)
    _insert_job(
        {
            "job_id": job_id,
            "status": "queued",
            "request_json": _json_dumps(forecast_request.model_dump(mode="json", by_alias=True)),
            "runtime_budget_s": request.runtime_budget_s,
            "notes": request.notes,
            "progress_stage": "queued",
            "progress_message": "Forecast job queued.",
            "cancel_requested": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "ticker": summary["ticker"],
            "model_name": summary["model_name"],
            "target": summary["target"],
            "horizon": summary["horizon"],
        }
    )
    if run_inline:
        _run_job(job_id)
    else:
        future = _EXECUTOR.submit(_run_job, job_id)
        with _LOCK:
            _FUTURES[job_id] = future
    return get_forecast_job(job_id, include_result=False)


def get_forecast_job(job_id: str, *, include_result: bool = True) -> dict[str, Any]:
    row = _read_job(job_id)
    if row is None:
        return {"status": "failed", "errors": [f"forecast_job_not_found:{job_id}"]}
    return _row_to_payload(row, include_result=include_result)


def list_forecast_jobs(limit: int = 50) -> dict[str, Any]:
    _init_job_db()
    limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM forecast_jobs
            ORDER BY datetime(COALESCE(updated_at, created_at, '1970-01-01T00:00:00Z')) DESC, job_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    items = [_row_to_payload(row, include_result=False) for row in rows]
    return {"status": "success", "items": items, "count": len(items), "storage": "sqlite"}


def cancel_forecast_job(job_id: str, reason: str = "") -> dict[str, Any]:
    row = _read_job(job_id)
    if row is None:
        return {"status": "failed", "errors": [f"forecast_job_not_found:{job_id}"]}
    current_status = str(row["status"] or "")
    if current_status in _TERMINAL_STATUSES:
        return _row_to_payload(row, include_result=False)

    cancelled_before_start = False
    with _LOCK:
        future = _FUTURES.get(job_id)
        if future is not None and future.cancel():
            cancelled_before_start = True
            _FUTURES.pop(job_id, None)
    if cancelled_before_start or current_status == "queued":
        _update_job(
            job_id,
            status="cancelled",
            cancel_requested=1,
            finished_at=now_iso(),
            progress_stage="cancelled",
            progress_message=reason or "Forecast job cancelled before execution.",
            error_json=_json_dumps({"errors": ["forecast_job_cancelled"], "reason": reason}),
        )
    else:
        _update_job(
            job_id,
            cancel_requested=1,
            progress_stage="cancel_requested",
            progress_message=reason or "Cancellation requested; current model run will finish before the worker stops.",
        )
    return get_forecast_job(job_id, include_result=False)


def retry_forecast_job(job_id: str) -> dict[str, Any]:
    row = _read_job(job_id)
    if row is None:
        return {"status": "failed", "errors": [f"forecast_job_not_found:{job_id}"]}
    payload = _json_loads(row["request_json"])
    request = ForecastRunRequest.model_validate(payload)
    return submit_forecast_job(
        ForecastJobSubmitRequest(
            request=request,
            runtime_budget_s=int(row["runtime_budget_s"] or 900),
            notes=f"retry_of={job_id}",
        )
    )


def _run_job(job_id: str) -> None:
    row = _read_job(job_id)
    if row is None:
        return
    if int(row["cancel_requested"] or 0):
        _update_job(job_id, status="cancelled", finished_at=now_iso(), progress_stage="cancelled", progress_message="Forecast job cancelled before start.")
        return
    _update_job(job_id, status="running", started_at=now_iso(), progress_stage="train_forecast", progress_message="Running train/forecast pipeline.")
    try:
        request = ForecastRunRequest.model_validate(_json_loads(row["request_json"]))
        from pipelines.forecast import service

        result = service.train(request)
        if _is_cancel_requested(job_id):
            _update_job(
                job_id,
                status="cancelled",
                result_json=_json_dumps(result),
                finished_at=now_iso(),
                progress_stage="cancelled",
                progress_message="Cancellation was requested while the model was running; result retained for audit.",
            )
            return
        result_status = str(result.get("status") or "")
        _update_job(
            job_id,
            status="failed" if result_status == "failed" else "succeeded",
            result_json=_json_dumps(result),
            finished_at=now_iso(),
            progress_stage="finished",
            progress_message="Forecast job finished." if result_status != "failed" else "Forecast job finished with failed pipeline status.",
        )
    except Exception as exc:  # pragma: no cover - defensive boundary for background worker failures.
        _update_job(
            job_id,
            status="failed",
            error_json=_json_dumps({"errors": [type(exc).__name__, str(exc)]}),
            finished_at=now_iso(),
            progress_stage="failed",
            progress_message=f"Forecast job failed: {type(exc).__name__}",
        )
    finally:
        with _LOCK:
            _FUTURES.pop(job_id, None)


def _request_summary(request: ForecastRunRequest) -> dict[str, Any]:
    return {
        "ticker": request.dataset_config.ticker,
        "model_name": request.ml_model_config.model_name,
        "target": request.target_config.target_type,
        "horizon": request.target_config.horizon,
    }


def _row_to_payload(row: sqlite3.Row, *, include_result: bool) -> dict[str, Any]:
    stored_result = _json_loads(row["result_json"])
    result = stored_result if include_result else {}
    error = _json_loads(row["error_json"])
    experiment = stored_result.get("experiment") or {}
    forecast_result = stored_result.get("forecast_result") or {}
    return {
        "status": "success",
        "job_id": row["job_id"],
        "job_status": row["status"],
        "ticker": row["ticker"],
        "model_name": row["model_name"],
        "target": row["target"],
        "horizon": row["horizon"],
        "runtime_budget_s": row["runtime_budget_s"],
        "progress_stage": row["progress_stage"],
        "progress_message": row["progress_message"],
        "cancel_requested": bool(row["cancel_requested"]),
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "updated_at": row["updated_at"],
        "notes": row["notes"],
        "errors": error.get("errors", []),
        "result_summary": {
            "status": stored_result.get("status", ""),
            "experiment_id": experiment.get("experiment_id") or forecast_result.get("experiment_id", ""),
            "model_id": forecast_result.get("model_id", ""),
            "signal": forecast_result.get("signal", ""),
            "confidence": (forecast_result.get("model_confidence") or {}).get("score"),
            "data_snapshot_id": (stored_result.get("data_snapshot") or {}).get("data_snapshot_id") or (experiment.get("artifact_refs") or {}).get("data_snapshot_id", ""),
        },
        "result": result if include_result else {},
        "can_cancel": row["status"] not in _TERMINAL_STATUSES,
        "can_retry": row["status"] in {"failed", "cancelled"},
        "storage": "sqlite",
    }


def _insert_job(values: dict[str, Any]) -> None:
    _init_job_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO forecast_jobs (
              job_id, status, request_json, result_json, error_json, runtime_budget_s, notes,
              progress_stage, progress_message, cancel_requested, created_at, started_at,
              finished_at, updated_at, ticker, model_name, target, horizon
            )
            VALUES (
              :job_id, :status, :request_json, '', '', :runtime_budget_s, :notes,
              :progress_stage, :progress_message, :cancel_requested, :created_at, '',
              '', :updated_at, :ticker, :model_name, :target, :horizon
            )
            """,
            values,
        )


def _read_job(job_id: str) -> sqlite3.Row | None:
    _init_job_db()
    if not _SAFE_ID_RE.fullmatch(str(job_id or "")):
        return None
    with _connect() as conn:
        return conn.execute("SELECT * FROM forecast_jobs WHERE job_id = ?", (job_id,)).fetchone()


def _update_job(job_id: str, **values: Any) -> None:
    if not values:
        return
    values["updated_at"] = now_iso()
    allowed = {
        "status",
        "result_json",
        "error_json",
        "progress_stage",
        "progress_message",
        "cancel_requested",
        "started_at",
        "finished_at",
        "updated_at",
    }
    assignments = [f"{key} = :{key}" for key in values if key in allowed]
    if not assignments:
        return
    values["job_id"] = job_id
    with _connect() as conn:
        # Assignment identifiers are filtered through the local allowlist.
        query = " ".join(["UPDATE forecast_jobs SET", ", ".join(assignments), "WHERE job_id = :job_id"])
        conn.execute(query, values)


def _is_cancel_requested(job_id: str) -> bool:
    row = _read_job(job_id)
    return bool(row and int(row["cancel_requested"] or 0))


def _init_job_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_jobs (
              job_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              request_json TEXT NOT NULL,
              result_json TEXT NOT NULL DEFAULT '',
              error_json TEXT NOT NULL DEFAULT '',
              runtime_budget_s INTEGER NOT NULL DEFAULT 900,
              notes TEXT NOT NULL DEFAULT '',
              progress_stage TEXT NOT NULL DEFAULT '',
              progress_message TEXT NOT NULL DEFAULT '',
              cancel_requested INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              started_at TEXT NOT NULL DEFAULT '',
              finished_at TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL,
              ticker TEXT NOT NULL DEFAULT '',
              model_name TEXT NOT NULL DEFAULT '',
              target TEXT NOT NULL DEFAULT '',
              horizon INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_jobs_status_updated ON forecast_jobs(status, updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_jobs_ticker_updated ON forecast_jobs(ticker, updated_at)")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(forecast_root() / "jobs.sqlite3", timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(payload: Any) -> dict[str, Any]:
    if not payload:
        return {}
    if isinstance(payload, dict):
        return payload
    try:
        data = json.loads(str(payload))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
