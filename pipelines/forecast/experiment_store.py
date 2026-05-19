from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from core.config.settings import load_settings
from core.schemas.forecast import ModelRegistryItem
from pipelines.forecast.common import now_iso

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def forecast_root() -> Path:
    settings = load_settings()
    root = settings.data_dir / "forecast_lab"
    root.mkdir(parents=True, exist_ok=True)
    (root / "experiments").mkdir(parents=True, exist_ok=True)
    (root / "model_artifacts").mkdir(parents=True, exist_ok=True)
    (root / "data_snapshots").mkdir(parents=True, exist_ok=True)
    return root


def save_experiment(experiment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _experiment_path(experiment_id)
    _write_json_atomic(path, payload)
    return {"experiment_id": experiment_id, "artifact_path": str(path), "saved_at": now_iso()}


def save_model_artifact(experiment_id: str, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _model_artifact_path(experiment_id, model_id)
    _write_json_atomic(path, payload)
    integrity = _write_artifact_integrity_manifest(path, experiment_id=experiment_id, model_id=model_id)
    return {
        "experiment_id": experiment_id,
        "model_id": model_id,
        "artifact_path": str(path),
        "integrity_path": integrity["integrity_path"],
        "artifact_sha256": integrity["artifact_sha256"],
        "signature": integrity["signature"],
        "signature_algorithm": integrity["signature_algorithm"],
        "saved_at": now_iso(),
    }


def save_data_snapshot(data_snapshot: dict[str, Any]) -> dict[str, Any]:
    snapshot_id = str(data_snapshot.get("data_snapshot_id") or "").strip()
    if not _SAFE_ID_RE.fullmatch(snapshot_id):
        raise ValueError("invalid_forecast_data_snapshot_id")
    snapshots_dir = (forecast_root() / "data_snapshots").resolve()
    path = (snapshots_dir / f"{snapshot_id}.json").resolve()
    if snapshots_dir not in path.parents:
        raise ValueError("invalid_forecast_data_snapshot_path")
    _write_json_atomic(path, data_snapshot)
    return {"data_snapshot_id": snapshot_id, "artifact_path": str(path), "saved_at": now_iso()}


def verify_model_artifact_integrity(artifact_path: str | Path) -> dict[str, Any]:
    path = Path(artifact_path).resolve()
    try:
        _assert_model_artifact_child(path)
    except ValueError as exc:
        return {"status": "failed", "errors": [str(exc)], "checked_at": now_iso()}
    manifest_path = _integrity_manifest_path(path)
    if not path.exists():
        return {"status": "failed", "errors": ["model_artifact_missing"], "artifact_path": str(path), "checked_at": now_iso()}
    if not manifest_path.exists():
        return {"status": "failed", "errors": ["model_artifact_integrity_manifest_missing"], "artifact_path": str(path), "checked_at": now_iso()}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "failed", "errors": ["model_artifact_integrity_manifest_invalid_json"], "artifact_path": str(path), "checked_at": now_iso()}
    secret = _load_signing_secret(create=False)
    if not secret:
        return {"status": "failed", "errors": ["model_artifact_signing_key_missing"], "artifact_path": str(path), "checked_at": now_iso()}
    actual_sha = _sha256_file(path)
    actual_size = path.stat().st_size
    expected_signature = _artifact_signature(
        secret,
        artifact_sha256=actual_sha,
        artifact_bytes=actual_size,
        experiment_id=str(manifest.get("experiment_id") or ""),
        model_id=str(manifest.get("model_id") or ""),
    )
    checks = {
        "sha256_matches": hmac.compare_digest(str(manifest.get("artifact_sha256") or ""), actual_sha),
        "bytes_match": int(manifest.get("artifact_bytes") or -1) == actual_size,
        "signature_matches": hmac.compare_digest(str(manifest.get("signature") or ""), expected_signature),
    }
    status = "success" if all(checks.values()) else "failed"
    errors = [] if status == "success" else [name for name, ok in checks.items() if not ok]
    return {
        "status": status,
        "artifact_path": str(path),
        "integrity_path": str(manifest_path),
        "artifact_sha256": actual_sha,
        "checks": checks,
        "errors": errors,
        "checked_at": now_iso(),
    }


def load_experiment(experiment_id: str) -> dict[str, Any] | None:
    try:
        path = _experiment_path(experiment_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_experiments(limit: int = 50) -> dict[str, Any]:
    items = []
    for path in sorted((forecast_root() / "experiments").glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items.append(
            {
                "experiment_id": payload.get("experiment", {}).get("experiment_id") or payload.get("experiment_id") or path.stem,
                "ticker": payload.get("forecast_result", {}).get("ticker") or payload.get("ticker", ""),
                "status": payload.get("status") or payload.get("experiment", {}).get("status", "partial"),
                "created_at": payload.get("experiment", {}).get("created_at") or payload.get("generated_at", ""),
                "model_id": payload.get("forecast_result", {}).get("model_id", ""),
                "data_snapshot_id": (payload.get("data_snapshot") or {}).get("data_snapshot_id") or (payload.get("experiment", {}).get("artifact_refs") or {}).get("data_snapshot_id", ""),
                "source_coverage_hash": (payload.get("data_snapshot") or {}).get("source_coverage_hash", ""),
                "artifact_path": str(path),
            }
        )
    return {"status": "success", "items": items, "count": len(items)}


def register_model(item: ModelRegistryItem) -> dict[str, Any]:
    payload = item.model_dump(mode="json")
    _upsert_registry_item(payload)
    return {"status": "success", "item": payload, "storage": "sqlite"}


def list_registry() -> dict[str, Any]:
    items = _read_registry()
    return {"status": "success", "items": items, "count": len(items), "storage": "sqlite"}


def update_model_status(model_id: str, status: str, notes: str = "") -> dict[str, Any]:
    items = _read_registry()
    found = False
    previous_status = ""
    updated_item: dict[str, Any] | None = None
    for item in items:
        if item.get("model_id") != model_id:
            continue
        found = True
        previous_status = str(item.get("status") or "")
        item["status"] = status
        if status == "promoted":
            item["promoted_at"] = now_iso()
        if status == "deprecated":
            item["deprecated_at"] = now_iso()
        if notes:
            item["notes"] = notes
        updated_item = item
    if not found:
        return {"status": "failed", "errors": [f"model_not_found:{model_id}"]}
    if updated_item is None:  # pragma: no cover - defensive guard for type narrowing.
        return {"status": "failed", "errors": [f"model_not_found:{model_id}"]}
    _upsert_registry_item(updated_item)
    _append_registry_audit(
        model_id=model_id,
        action="status_update",
        previous_status=previous_status,
        new_status=status,
        notes=notes,
        item=updated_item,
    )
    return {"status": "success", "model_id": model_id, "status_value": status, "previous_status": previous_status, "storage": "sqlite"}


def verify_model_registry_artifact(model_id: str) -> dict[str, Any]:
    item = _registry_item_by_model_id(model_id)
    if not item:
        return {"status": "failed", "errors": [f"model_not_found:{model_id}"], "checked_at": now_iso()}
    artifact_path = str(item.get("artifact_path") or "")
    if not artifact_path:
        return {"status": "failed", "errors": ["model_artifact_path_missing"], "model_id": model_id, "checked_at": now_iso()}
    result = verify_model_artifact_integrity(artifact_path)
    result["model_id"] = model_id
    return result


def list_registry_audit(model_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    _init_registry_db()
    params: list[Any] = []
    where = ""
    if model_id:
        where = "WHERE model_id = ?"
        params.append(model_id)
    params.append(max(1, min(int(limit), 500)))
    with _registry_connection() as conn:
        # Optional WHERE clause is selected from a fixed template.
        query = "\n".join(
            [
                """
                SELECT model_id, action, previous_status, new_status, notes, actor, created_at, item_json
                FROM registry_audit
                """,
                where,
                """
                ORDER BY id DESC
                LIMIT ?
                """,
            ]
        )
        rows = conn.execute(query, params).fetchall()
    items = []
    for row in rows:
        payload = {
            "model_id": row["model_id"],
            "action": row["action"],
            "previous_status": row["previous_status"],
            "new_status": row["new_status"],
            "notes": row["notes"],
            "actor": row["actor"],
            "created_at": row["created_at"],
        }
        try:
            payload["item"] = json.loads(row["item_json"]) if row["item_json"] else {}
        except json.JSONDecodeError:
            payload["item"] = {}
        items.append(payload)
    return {"status": "success", "items": items, "count": len(items), "storage": "sqlite"}


def _registry_path() -> Path:
    return forecast_root() / "model_registry.json"


def _registry_db_path() -> Path:
    return forecast_root() / "model_registry.sqlite3"


def _experiment_path(experiment_id: str) -> Path:
    clean = str(experiment_id or "").strip()
    if not _SAFE_ID_RE.fullmatch(clean):
        raise ValueError("invalid_forecast_experiment_id")
    experiments_dir = (forecast_root() / "experiments").resolve()
    path = (experiments_dir / f"{clean}.json").resolve()
    if experiments_dir not in path.parents:
        raise ValueError("invalid_forecast_experiment_path")
    return path


def _model_artifact_path(experiment_id: str, model_id: str) -> Path:
    clean_experiment = str(experiment_id or "").strip()
    clean_model = str(model_id or "").strip()
    if not _SAFE_ID_RE.fullmatch(clean_experiment) or not _SAFE_ID_RE.fullmatch(clean_model):
        raise ValueError("invalid_forecast_model_artifact_id")
    artifact_dir = (forecast_root() / "model_artifacts").resolve()
    path = (artifact_dir / f"{clean_model}__{clean_experiment}.json").resolve()
    if artifact_dir not in path.parents:
        raise ValueError("invalid_forecast_model_artifact_path")
    return path


def _assert_model_artifact_child(path: Path) -> None:
    artifact_dir = (forecast_root() / "model_artifacts").resolve()
    if artifact_dir not in path.parents:
        raise ValueError("invalid_forecast_model_artifact_path")


def _integrity_manifest_path(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(".integrity.json")


def _write_artifact_integrity_manifest(path: Path, *, experiment_id: str, model_id: str) -> dict[str, Any]:
    secret = _load_signing_secret(create=True)
    if not secret:  # pragma: no cover - create=True always returns a local or env-backed secret.
        raise RuntimeError("forecast_model_artifact_signing_key_unavailable")
    artifact_sha256 = _sha256_file(path)
    artifact_bytes = path.stat().st_size
    signature = _artifact_signature(
        secret,
        artifact_sha256=artifact_sha256,
        artifact_bytes=artifact_bytes,
        experiment_id=experiment_id,
        model_id=model_id,
    )
    manifest = {
        "schema_version": "forecast_model_artifact_integrity_v1",
        "artifact_path": str(path),
        "experiment_id": experiment_id,
        "model_id": model_id,
        "artifact_sha256": artifact_sha256,
        "artifact_bytes": artifact_bytes,
        "signature_algorithm": "hmac_sha256_local",
        "signature": signature,
        "key_id": _key_id(secret),
        "signature_scope": "local_artifact_integrity_not_remote_attestation",
        "signed_at": now_iso(),
    }
    manifest_path = _integrity_manifest_path(path)
    _write_json_atomic(manifest_path, manifest)
    return {
        "integrity_path": str(manifest_path),
        "artifact_sha256": artifact_sha256,
        "signature": signature,
        "signature_algorithm": manifest["signature_algorithm"],
    }


def _load_signing_secret(*, create: bool) -> str | None:
    env_secret = os.environ.get("FORECAST_ARTIFACT_SIGNING_KEY", "").strip()
    if env_secret:
        return env_secret
    key_path = forecast_root() / ".artifact_signing_key.json"
    if key_path.exists():
        try:
            payload = json.loads(key_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _create_local_signing_secret(key_path) if create else None
        secret = str(payload.get("secret") or "").strip()
        if secret:
            return secret
        return _create_local_signing_secret(key_path) if create else None
    if not create:
        return None
    return _create_local_signing_secret(key_path)


def _create_local_signing_secret(key_path: Path) -> str:
    secret = secrets.token_hex(32)
    _write_json_atomic(
        key_path,
        {
            "schema_version": "forecast_artifact_signing_key_v1",
            "key_id": _key_id(secret),
            "secret": secret,
            "source": "local_generated",
            "created_at": now_iso(),
        },
    )
    return secret


def _artifact_signature(
    secret: str,
    *,
    artifact_sha256: str,
    artifact_bytes: int,
    experiment_id: str,
    model_id: str,
) -> str:
    message = f"{artifact_sha256}:{artifact_bytes}:{experiment_id}:{model_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _key_id(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def _read_registry() -> list[dict[str, Any]]:
    _init_registry_db()
    with _registry_connection() as conn:
        rows = conn.execute(
            """
            SELECT item_json
            FROM model_registry
            ORDER BY datetime(COALESCE(updated_at, created_at, '1970-01-01T00:00:00Z')) DESC, model_id ASC
            """
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["item_json"])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _read_legacy_registry_json() -> list[dict[str, Any]]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _write_registry(items: list[dict[str, Any]]) -> None:
    _init_registry_db()
    for item in items:
        _upsert_registry_item(item)


def _registry_connection() -> sqlite3.Connection:
    path = _registry_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_registry_db() -> None:
    with _registry_connection() as conn:
        _ensure_registry_schema(conn)
        count = conn.execute("SELECT COUNT(*) FROM model_registry").fetchone()[0]
        if count == 0:
            for item in _read_legacy_registry_json():
                _upsert_registry_item(item, conn=conn, audit_action="legacy_json_migration")


def _ensure_registry_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_registry (
            model_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL DEFAULT '',
            ticker TEXT NOT NULL DEFAULT '',
            target TEXT NOT NULL DEFAULT '',
            horizon INTEGER NOT NULL DEFAULT 0,
            model_type TEXT NOT NULL DEFAULT '',
            feature_set_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            artifact_path TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            item_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registry_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id TEXT NOT NULL,
            action TEXT NOT NULL,
            previous_status TEXT NOT NULL DEFAULT '',
            new_status TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            actor TEXT NOT NULL DEFAULT 'system',
            created_at TEXT NOT NULL,
            item_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model_registry_ticker ON model_registry(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_model_registry_status ON model_registry(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_audit_model_id ON registry_audit(model_id)")


def _upsert_registry_item(
    item: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
    audit_action: str = "upsert",
) -> None:
    model_id = str(item.get("model_id") or "").strip()
    if not _SAFE_ID_RE.fullmatch(model_id):
        raise ValueError("invalid_forecast_model_registry_id")
    now = now_iso()
    created_at = str(item.get("created_at") or now)
    updated_at = now
    item = {**item, "created_at": created_at}
    owns_conn = conn is None
    connection = conn or _registry_connection()
    try:
        _ensure_registry_schema(connection)
        existing = connection.execute("SELECT status FROM model_registry WHERE model_id = ?", (model_id,)).fetchone()
        previous_status = str(existing["status"] or "") if existing else ""
        connection.execute(
            """
            INSERT INTO model_registry (
                model_id, experiment_id, ticker, target, horizon, model_type, feature_set_hash,
                status, artifact_path, created_at, updated_at, item_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_id) DO UPDATE SET
                experiment_id=excluded.experiment_id,
                ticker=excluded.ticker,
                target=excluded.target,
                horizon=excluded.horizon,
                model_type=excluded.model_type,
                feature_set_hash=excluded.feature_set_hash,
                status=excluded.status,
                artifact_path=excluded.artifact_path,
                updated_at=excluded.updated_at,
                item_json=excluded.item_json
            """,
            (
                model_id,
                str(item.get("experiment_id") or ""),
                str(item.get("ticker") or ""),
                str(item.get("target") or ""),
                int(item.get("horizon") or 0),
                str(item.get("model_type") or ""),
                str(item.get("feature_set_hash") or ""),
                str(item.get("status") or ""),
                str(item.get("artifact_path") or ""),
                created_at,
                updated_at,
                json.dumps(item, ensure_ascii=False, default=str),
            ),
        )
        _append_registry_audit(
            model_id=model_id,
            action=audit_action,
            previous_status=previous_status,
            new_status=str(item.get("status") or ""),
            notes=str(item.get("notes") or ""),
            item=item,
            conn=connection,
        )
        if owns_conn:
            connection.commit()
    finally:
        if owns_conn:
            connection.close()


def _registry_item_by_model_id(model_id: str) -> dict[str, Any] | None:
    clean = str(model_id or "").strip()
    if not _SAFE_ID_RE.fullmatch(clean):
        return None
    _init_registry_db()
    with _registry_connection() as conn:
        row = conn.execute("SELECT item_json FROM model_registry WHERE model_id = ?", (clean,)).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["item_json"])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _append_registry_audit(
    *,
    model_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    notes: str,
    item: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> None:
    owns_conn = conn is None
    connection = conn or _registry_connection()
    try:
        connection.execute(
            """
            INSERT INTO registry_audit (
                model_id, action, previous_status, new_status, notes, actor, created_at, item_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                action,
                previous_status,
                new_status,
                notes,
                "system",
                now_iso(),
                json.dumps(item, ensure_ascii=False, default=str),
            ),
        )
        if owns_conn:
            connection.commit()
    finally:
        if owns_conn:
            connection.close()


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{stable_suffix()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def stable_suffix() -> str:
    return now_iso().replace(":", "").replace("-", "").replace(".", "").replace("Z", "")
