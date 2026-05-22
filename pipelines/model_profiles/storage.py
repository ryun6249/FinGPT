from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schemas.quant import QuantModelProfile


CURRENT_MODEL_PROFILE_SCHEMA_VERSION = "quant_model_profile_v1"
SUPPORTED_MODEL_PROFILE_SCHEMA_VERSIONS = {"", CURRENT_MODEL_PROFILE_SCHEMA_VERSION}


def default_model_profile() -> QuantModelProfile:
    return validate_model_profile(QuantModelProfile(), touch=False)


def list_model_profiles(root: Path) -> list[QuantModelProfile]:
    default = default_model_profile()
    profiles_by_id: dict[str, QuantModelProfile] = {}
    if not root.exists():
        return [default]
    for path in sorted(root.glob("*.json")):
        loaded = load_model_profile(path.stem, root)
        if loaded:
            profiles_by_id[loaded.profile_id] = loaded
    return [profiles_by_id.pop(default.profile_id, default), *profiles_by_id.values()]


def save_model_profile(profile: QuantModelProfile | dict[str, Any], root: Path) -> Path:
    normalized = validate_model_profile(profile, touch=True)
    safe_id = _safe_profile_id(normalized.profile_id)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{safe_id}.json"
    payload = normalized.model_dump(mode="json")
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if isinstance(existing, dict) and existing.get("created_at"):
            payload["created_at"] = existing["created_at"]
    _write_json(path, payload)
    return path


def load_model_profile(profile_id: str, root: Path) -> QuantModelProfile | None:
    safe_id = _safe_profile_id(profile_id, allow_empty=True)
    if not safe_id:
        return None
    path = root / f"{safe_id}.json"
    if not path.exists():
        default = default_model_profile()
        return default if default.profile_id == safe_id else None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_model_profile(payload, touch=False)


def delete_model_profile(profile_id: str, root: Path) -> bool:
    safe_id = _safe_profile_id(profile_id, allow_empty=True)
    if not safe_id:
        return False
    path = root / f"{safe_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True


def validate_model_profile(profile: QuantModelProfile | dict[str, Any], *, touch: bool = True) -> QuantModelProfile:
    migrated = migrate_model_profile(profile, touch=touch)
    if not migrated.profile_id:
        raise ValueError("profile_id is required")
    _safe_profile_id(migrated.profile_id)
    if not migrated.model_candidates:
        raise ValueError("model_candidates must contain at least one model")
    if migrated.run_mode in {"universe_per_asset", "cross_sectional_rank"} and not migrated.tickers and migrated.universe_id == "custom":
        raise ValueError(f"custom {migrated.run_mode} profile requires tickers")
    if migrated.run_mode == "single_asset" and not migrated.tickers:
        raise ValueError("single_asset profile requires at least one ticker")
    if int(migrated.backtest_config.execution_delay_bars or 0) < 1:
        raise ValueError("backtest_config.execution_delay_bars must be at least 1")
    return migrated


def migrate_model_profile(profile: QuantModelProfile | dict[str, Any], *, touch: bool = False) -> QuantModelProfile:
    payload = profile.model_dump(mode="json") if isinstance(profile, QuantModelProfile) else dict(profile or {})
    schema_version = str(payload.get("schema_version") or "").strip()
    if schema_version not in SUPPORTED_MODEL_PROFILE_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported model profile schema_version: {schema_version}")
    if schema_version != CURRENT_MODEL_PROFILE_SCHEMA_VERSION:
        payload["schema_version"] = CURRENT_MODEL_PROFILE_SCHEMA_VERSION
    now = datetime.now(timezone.utc).isoformat()
    if not payload.get("created_at"):
        payload["created_at"] = now
    if touch or not payload.get("updated_at"):
        payload["updated_at"] = now
    return QuantModelProfile.model_validate(payload)


def _safe_profile_id(profile_id: str, *, allow_empty: bool = False) -> str:
    safe_id = "".join(ch for ch in str(profile_id or "") if ch.isalnum() or ch in {"_", "-"})
    if not safe_id and allow_empty:
        return ""
    if not safe_id:
        raise ValueError("profile_id is required")
    if safe_id != profile_id:
        raise ValueError("profile_id may only contain letters, numbers, underscore, and dash")
    return safe_id


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
