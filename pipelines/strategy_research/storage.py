from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from core.schemas.quant import (
    StrategyDiagnosticsRun,
    StrategyHypothesis,
    StrategyOptimizationRun,
    StrategyOptimizationTrial,
    StrategyResearchExperiment,
    StrategyResearchStrategy,
    StrategyResearchVersion,
    StrategyValidationResult,
)


ModelT = TypeVar("ModelT", bound=BaseModel)

INDEX_MODEL: dict[str, tuple[str, type[BaseModel]]] = {
    "strategies": ("strategy_id", StrategyResearchStrategy),
    "versions": ("version_id", StrategyResearchVersion),
    "experiments": ("experiment_id", StrategyResearchExperiment),
    "optimizations": ("optimization_id", StrategyOptimizationRun),
    "optimization_trials": ("trial_id", StrategyOptimizationTrial),
    "diagnostics": ("diagnostics_id", StrategyDiagnosticsRun),
    "hypotheses": ("hypothesis_id", StrategyHypothesis),
    "validations": ("validation_id", StrategyValidationResult),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_id(value: str, *, allow_empty: bool = False) -> str:
    clean = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch in {"_", "-"})
    if allow_empty and not clean:
        return ""
    if not clean:
        raise ValueError("id is required")
    if clean != str(value or "").strip():
        raise ValueError("id may only contain letters, numbers, underscore, and dash")
    return clean


def ensure_layout(root: Path) -> None:
    for name in ["strategies", "versions", "experiments", "index"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    for index_name in INDEX_MODEL:
        path = root / "index" / f"{index_name}.json"
        if not path.exists():
            write_json(path, [])


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def list_index(root: Path, index_name: str) -> list[dict[str, Any]]:
    ensure_layout(root)
    raw = read_json(root / "index" / f"{index_name}.json", default=[])
    return list(raw) if isinstance(raw, list) else []


def replace_index(root: Path, index_name: str, items: list[dict[str, Any]]) -> None:
    ensure_layout(root)
    write_json(root / "index" / f"{index_name}.json", items)


def upsert_index_item(root: Path, index_name: str, item: BaseModel | dict[str, Any]) -> dict[str, Any]:
    id_field, _model = INDEX_MODEL[index_name]
    payload = item.model_dump(mode="json") if isinstance(item, BaseModel) else dict(item)
    item_id = safe_id(str(payload.get(id_field) or ""))
    payload[id_field] = item_id
    items = [existing for existing in list_index(root, index_name) if existing.get(id_field) != item_id]
    items.append(payload)
    items.sort(key=lambda row: str(row.get("created_at") or row.get(id_field) or ""))
    replace_index(root, index_name, items)
    return payload


def load_index_item(root: Path, index_name: str, item_id: str) -> dict[str, Any] | None:
    id_field, _model = INDEX_MODEL[index_name]
    clean = safe_id(item_id, allow_empty=True)
    if not clean:
        return None
    for item in list_index(root, index_name):
        if item.get(id_field) == clean:
            return item
    return None


def model_items(root: Path, index_name: str, model: type[ModelT]) -> list[ModelT]:
    return [model.model_validate(item) for item in list_index(root, index_name)]


def model_item(root: Path, index_name: str, item_id: str, model: type[ModelT]) -> ModelT | None:
    item = load_index_item(root, index_name, item_id)
    return model.model_validate(item) if item else None


def save_strategy(root: Path, strategy: StrategyResearchStrategy) -> StrategyResearchStrategy:
    payload = upsert_index_item(root, "strategies", strategy)
    path = root / "strategies" / f"{payload['strategy_id']}.json"
    write_json(path, payload)
    return StrategyResearchStrategy.model_validate(payload)


def save_version(root: Path, version: StrategyResearchVersion) -> StrategyResearchVersion:
    payload = upsert_index_item(root, "versions", version)
    path = root / "versions" / f"{payload['version_id']}.json"
    write_json(path, payload)
    return StrategyResearchVersion.model_validate(payload)


def save_experiment(root: Path, experiment: StrategyResearchExperiment) -> StrategyResearchExperiment:
    payload = upsert_index_item(root, "experiments", experiment)
    write_experiment_artifact(root, payload["experiment_id"], "request.json", payload)
    return StrategyResearchExperiment.model_validate(payload)


def save_optimization(root: Path, run: StrategyOptimizationRun) -> StrategyOptimizationRun:
    payload = upsert_index_item(root, "optimizations", run)
    if payload.get("experiment_id"):
        write_experiment_artifact(root, payload["experiment_id"], "optimization-summary.json", payload)
    return StrategyOptimizationRun.model_validate(payload)


def save_trials(root: Path, experiment_id: str, trials: list[StrategyOptimizationTrial]) -> list[StrategyOptimizationTrial]:
    saved: list[StrategyOptimizationTrial] = []
    for trial in trials:
        payload = upsert_index_item(root, "optimization_trials", trial)
        saved.append(StrategyOptimizationTrial.model_validate(payload))
    write_experiment_artifact(root, experiment_id, "optimization-trials.json", [item.model_dump(mode="json") for item in saved])
    return saved


def save_diagnostics(root: Path, run: StrategyDiagnosticsRun) -> StrategyDiagnosticsRun:
    payload = upsert_index_item(root, "diagnostics", run)
    if payload.get("experiment_id"):
        write_experiment_artifact(root, payload["experiment_id"], "diagnostics-summary.json", payload)
    return StrategyDiagnosticsRun.model_validate(payload)


def save_hypothesis(root: Path, hypothesis: StrategyHypothesis) -> StrategyHypothesis:
    payload = upsert_index_item(root, "hypotheses", hypothesis)
    if payload.get("source_experiment_id"):
        hypotheses = [item for item in list_index(root, "hypotheses") if item.get("source_experiment_id") == payload["source_experiment_id"]]
        write_experiment_artifact(root, payload["source_experiment_id"], "hypotheses.json", hypotheses)
    return StrategyHypothesis.model_validate(payload)


def save_validation(root: Path, result: StrategyValidationResult) -> StrategyValidationResult:
    payload = upsert_index_item(root, "validations", result)
    if payload.get("experiment_id"):
        write_experiment_artifact(root, payload["experiment_id"], "validation-result.json", payload)
    return StrategyValidationResult.model_validate(payload)


def write_experiment_artifact(root: Path, experiment_id: str, filename: str, payload: Any) -> str:
    clean = safe_id(experiment_id)
    path = root / "experiments" / clean / filename
    write_json(path, payload)
    return str(path)


def experiment_artifact_path(root: Path, experiment_id: str, filename: str) -> str:
    return str(root / "experiments" / safe_id(experiment_id) / filename)
