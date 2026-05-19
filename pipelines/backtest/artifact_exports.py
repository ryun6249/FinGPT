from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_SECTIONS = [
    "manifest",
    "config",
    "metrics",
    "diagnostics",
    "equity_curve",
    "drawdown_curve",
    "trades",
    "signals",
    "weights",
    "replay_report",
]
SUPPORTED_EXPORT_FORMATS = {"csv", "jsonl", "parquet"}
PARQUET_ENGINES = ("pyarrow", "fastparquet")


def export_backtest_artifact_bundle(
    *,
    run_id: str,
    artifact_root: Path,
    export_format: str,
    keep_last_exports: int | None = None,
) -> dict[str, Any]:
    clean_run_id = _clean_run_id(run_id)
    run_dir = artifact_root / clean_run_id
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))

    fmt = str(export_format or "").strip().lower()
    if fmt not in SUPPORTED_EXPORT_FORMATS:
        raise ValueError("export_format must be one of: csv, jsonl, parquet")

    artifacts = _load_artifacts(run_dir)
    dependency: dict[str, Any] | None = None
    if fmt == "parquet":
        dependency = _parquet_dependency_status()
        if not dependency["available"]:
            return {
                "status": "dependency_missing",
                "run_id": clean_run_id,
                "format": fmt,
                "export_written": False,
                "export_root": None,
                "files": {},
                "row_counts": _section_row_counts(artifacts),
                "dependency": dependency,
                "supported_formats": sorted(SUPPORTED_EXPORT_FORMATS),
                "integrity": _empty_integrity(),
                "retention": _retention_result(keep_last_exports, applied=False),
                "manifest": {},
            }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    export_dir = run_dir / "exports" / f"{stamp}_{fmt}"
    export_dir.mkdir(parents=True, exist_ok=True)
    package_manifest_path = export_dir / "package_manifest.json"

    if fmt == "jsonl":
        files, row_counts = _write_jsonl_export(export_dir, artifacts)
    elif fmt == "csv":
        files, row_counts = _write_csv_export(export_dir, artifacts)
    else:
        files, row_counts = _write_parquet_export(export_dir, artifacts, engine=str(dependency["engine"]))

    manifest_path = export_dir / "export_manifest.json"
    files["manifest"] = str(manifest_path)
    files["package_manifest"] = str(package_manifest_path)
    data_files = {name: path for name, path in files.items() if name not in {"manifest", "package_manifest"}}
    integrity = _build_integrity(data_files)
    retention = _apply_export_retention(
        exports_root=run_dir / "exports",
        current_export_dir=export_dir,
        keep_last_exports=keep_last_exports,
    )
    manifest = {
        "schema_version": "quant_lab_artifact_export_v1",
        "run_id": clean_run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "format": fmt,
        "status": "success",
        "export_written": True,
        "source_artifacts": sorted(artifacts),
        "row_counts": row_counts,
        "files": files,
        "dependency": dependency or {},
        "supported_formats": sorted(SUPPORTED_EXPORT_FORMATS),
        "integrity": integrity,
        "retention": retention,
        "package_manifest": {
            "schema_version": "quant_lab_export_package_v1",
            "path": str(package_manifest_path),
            "portable": True,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    package_manifest = _build_package_manifest(
        run_id=clean_run_id,
        run_dir=run_dir,
        export_dir=export_dir,
        export_format=fmt,
        export_manifest_path=manifest_path,
        files=data_files,
        row_counts=row_counts,
        dependency=dependency or {},
        retention=retention,
    )
    package_manifest_path.write_text(
        json.dumps(package_manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    response_integrity = _build_integrity(files)
    return {
        "status": "success",
        "run_id": clean_run_id,
        "format": fmt,
        "export_written": True,
        "export_root": str(export_dir),
        "files": files,
        "row_counts": row_counts,
        "dependency": dependency or {},
        "supported_formats": sorted(SUPPORTED_EXPORT_FORMATS),
        "integrity": response_integrity,
        "retention": retention,
        "manifest": manifest,
    }


def list_backtest_artifact_exports(
    *,
    run_id: str,
    artifact_root: Path,
    limit: int = 20,
) -> dict[str, Any]:
    clean_run_id = _clean_run_id(run_id)
    run_dir = artifact_root / clean_run_id
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))

    limit = max(1, min(int(limit or 20), 100))
    exports_root = run_dir / "exports"
    items: list[dict[str, Any]] = []
    if exports_root.exists():
        for export_dir in sorted(
            [path for path in exports_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            items.append(_export_manifest_summary(export_dir / "export_manifest.json", export_dir))
            if len(items) >= limit:
                break

    return {
        "status": "success",
        "run_id": clean_run_id,
        "count": len(items),
        "items": items,
    }


def verify_backtest_artifact_export(
    *,
    run_id: str,
    artifact_root: Path,
    export_manifest_path: str | None = None,
) -> dict[str, Any]:
    clean_run_id = _clean_run_id(run_id)
    run_dir = artifact_root / clean_run_id
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))

    manifest_path = _resolve_export_manifest_path(run_dir, export_manifest_path)
    if not manifest_path.exists():
        raise FileNotFoundError(str(manifest_path))

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "failed",
            "run_id": clean_run_id,
            "manifest_path": str(manifest_path),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "files_checked": 0,
            "files_passed": 0,
            "files_failed": 0,
            "failures": [{"file": "manifest", "reason": f"decode_error:{exc}"}],
            "files": {},
        }

    integrity_files = ((manifest.get("integrity") or {}).get("files") or {})
    if not isinstance(integrity_files, dict) or not integrity_files:
        return {
            "status": "partial",
            "run_id": clean_run_id,
            "manifest_path": str(manifest_path),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "files_checked": 0,
            "files_passed": 0,
            "files_failed": 0,
            "failures": [{"file": "integrity", "reason": "missing_integrity_files"}],
            "files": {},
        }

    export_dir = manifest_path.parent
    file_results: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for name, expected in sorted(integrity_files.items()):
        if not isinstance(expected, dict):
            failures.append({"file": name, "reason": "invalid_integrity_entry"})
            file_results[name] = {"status": "failed", "reason": "invalid_integrity_entry"}
            continue
        expected_path = str(expected.get("path") or "")
        try:
            file_path = _resolve_export_file_path(export_dir, expected_path)
        except ValueError as exc:
            failures.append({"file": name, "reason": str(exc), "expected_path": expected_path})
            file_results[name] = {"status": "failed", "reason": str(exc), "expected_path": expected_path}
            continue
        if not file_path.exists() or not file_path.is_file():
            failures.append({"file": name, "reason": "missing_file", "path": str(file_path)})
            file_results[name] = {"status": "failed", "reason": "missing_file", "path": str(file_path)}
            continue
        actual = _file_integrity(file_path)
        sha_match = actual["sha256"] == expected.get("sha256")
        size_match = actual["size_bytes"] == expected.get("size_bytes")
        status = "passed" if sha_match and size_match else "failed"
        file_results[name] = {
            "status": status,
            "path": str(file_path),
            "expected_sha256": expected.get("sha256"),
            "actual_sha256": actual["sha256"],
            "expected_size_bytes": expected.get("size_bytes"),
            "actual_size_bytes": actual["size_bytes"],
        }
        if status != "passed":
            failures.append(
                {
                    "file": name,
                    "reason": "integrity_mismatch",
                    "sha256_match": sha_match,
                    "size_match": size_match,
                }
            )

    files_checked = len(file_results)
    files_failed = len([item for item in file_results.values() if item.get("status") != "passed"])
    return {
        "status": "success" if files_checked and files_failed == 0 else "partial",
        "run_id": clean_run_id,
        "manifest_path": str(manifest_path),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "format": manifest.get("format") or "unknown",
        "generated_at": manifest.get("generated_at") or "",
        "files_checked": files_checked,
        "files_passed": files_checked - files_failed,
        "files_failed": files_failed,
        "failures": failures,
        "files": file_results,
    }


def preview_backtest_artifact_export_cleanup(
    *,
    run_id: str,
    artifact_root: Path,
    keep_last_exports: int | None = 5,
) -> dict[str, Any]:
    return _export_cleanup_plan(
        run_id=run_id,
        artifact_root=artifact_root,
        keep_last_exports=keep_last_exports,
        apply_cleanup=False,
    )


def cleanup_backtest_artifact_exports(
    *,
    run_id: str,
    artifact_root: Path,
    keep_last_exports: int | None = 5,
) -> dict[str, Any]:
    return _export_cleanup_plan(
        run_id=run_id,
        artifact_root=artifact_root,
        keep_last_exports=keep_last_exports,
        apply_cleanup=True,
    )


def preview_cross_run_artifact_export_cleanup(
    *,
    artifact_root: Path,
    keep_last_exports: int | None = 5,
    stale_after_days: int | None = 30,
    limit: int = 100,
) -> dict[str, Any]:
    return _cross_run_export_cleanup_plan(
        artifact_root=artifact_root,
        keep_last_exports=keep_last_exports,
        stale_after_days=stale_after_days,
        limit=limit,
        apply_cleanup=False,
        preview_id=None,
        candidate_ids=None,
    )


def cleanup_cross_run_artifact_exports(
    *,
    artifact_root: Path,
    preview_id: str,
    candidate_ids: list[Any],
    keep_last_exports: int | None = 5,
    stale_after_days: int | None = 30,
    limit: int = 100,
) -> dict[str, Any]:
    return _cross_run_export_cleanup_plan(
        artifact_root=artifact_root,
        keep_last_exports=keep_last_exports,
        stale_after_days=stale_after_days,
        limit=limit,
        apply_cleanup=True,
        preview_id=preview_id,
        candidate_ids=candidate_ids,
    )


def summarize_backtest_artifact_export_storage(
    *,
    artifact_root: Path,
    limit: int = 20,
    stale_after_days: int | None = 30,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    stale_days = _coerce_stale_after_days(stale_after_days)
    generated_at = datetime.now(timezone.utc)
    run_summaries: list[dict[str, Any]] = []
    stale_candidates: list[dict[str, Any]] = []
    format_counts: dict[str, int] = {}
    manifest_status_counts: dict[str, int] = {}
    total_export_dirs = 0
    total_bytes = 0
    total_rows = 0
    oldest_export_at = ""
    newest_export_at = ""

    run_dirs = []
    if artifact_root.exists():
        run_dirs = sorted(
            [path for path in artifact_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    for run_dir in run_dirs:
        run_id = run_dir.name
        export_dirs = _sorted_export_dirs(run_dir / "exports")
        export_items = [_export_cleanup_summary(path) for path in export_dirs]
        run_bytes = sum(int(item.get("total_bytes") or 0) for item in export_items)
        run_rows = sum(int(item.get("total_rows") or 0) for item in export_items)
        run_formats: dict[str, int] = {}
        run_manifest_statuses: dict[str, int] = {}
        run_oldest = ""
        run_newest = ""
        run_stale_count = 0

        for item in export_items:
            fmt = str(item.get("format") or "unknown")
            status = str(item.get("status") or "unknown")
            run_formats[fmt] = run_formats.get(fmt, 0) + 1
            format_counts[fmt] = format_counts.get(fmt, 0) + 1
            run_manifest_statuses[status] = run_manifest_statuses.get(status, 0) + 1
            manifest_status_counts[status] = manifest_status_counts.get(status, 0) + 1
            item_time = _export_generated_at(item)
            if item_time:
                run_oldest = _min_iso_datetime(run_oldest, item_time)
                run_newest = _max_iso_datetime(run_newest, item_time)
                oldest_export_at = _min_iso_datetime(oldest_export_at, item_time)
                newest_export_at = _max_iso_datetime(newest_export_at, item_time)
                if stale_days > 0 and _age_days(item_time, generated_at) >= stale_days:
                    run_stale_count += 1
                    stale_candidates.append(_storage_export_candidate(run_id, item, generated_at))

        source_manifest = _read_json(run_dir / "manifest.json", default={})
        run_summaries.append(
            {
                "run_id": run_id,
                "run_generated_at": source_manifest.get("generated_at") if isinstance(source_manifest, dict) else "",
                "export_count": len(export_items),
                "total_bytes": run_bytes,
                "total_rows": run_rows,
                "formats": run_formats,
                "manifest_statuses": run_manifest_statuses,
                "oldest_export_generated_at": run_oldest,
                "newest_export_generated_at": run_newest,
                "stale_export_count": run_stale_count,
                "latest_export_root": str(export_dirs[0]) if export_dirs else "",
                "run_root": str(run_dir),
            }
        )
        total_export_dirs += len(export_items)
        total_bytes += run_bytes
        total_rows += run_rows

    top_runs = sorted(run_summaries, key=lambda item: int(item.get("total_bytes") or 0), reverse=True)[:limit]
    stale_exports = sorted(stale_candidates, key=lambda item: str(item.get("generated_at") or ""))[:limit]
    return {
        "status": "success",
        "schema_version": "quant_lab_export_storage_report_v1",
        "generated_at": generated_at.isoformat(),
        "artifact_root": str(artifact_root),
        "run_count": len(run_summaries),
        "runs_with_exports": len([item for item in run_summaries if int(item.get("export_count") or 0) > 0]),
        "export_directory_count": total_export_dirs,
        "total_bytes": total_bytes,
        "total_rows": total_rows,
        "format_counts": dict(sorted(format_counts.items())),
        "manifest_status_counts": dict(sorted(manifest_status_counts.items())),
        "oldest_export_generated_at": oldest_export_at,
        "newest_export_generated_at": newest_export_at,
        "stale_after_days": stale_days,
        "stale_export_count": len(stale_candidates),
        "top_runs": top_runs,
        "stale_exports": stale_exports,
    }


def _load_artifacts(run_dir: Path) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for section in ARTIFACT_SECTIONS:
        path = run_dir / f"{section}.json"
        if not path.exists():
            continue
        try:
            artifacts[section] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            artifacts[section] = {"decode_error": str(path)}
    return artifacts


def _write_jsonl_export(export_dir: Path, artifacts: dict[str, Any]) -> tuple[dict[str, str], dict[str, int]]:
    path = export_dir / "artifact_bundle.jsonl"
    row_counts: dict[str, int] = {}
    total = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for section, payload in artifacts.items():
            rows = _section_rows(payload)
            row_counts[section] = len(rows)
            for idx, row in enumerate(rows):
                fh.write(
                    json.dumps(
                        {"section": section, "index": idx, "payload": row},
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
                total += 1
    row_counts["total"] = total
    return {"jsonl": str(path)}, row_counts


def _write_csv_export(export_dir: Path, artifacts: dict[str, Any]) -> tuple[dict[str, str], dict[str, int]]:
    files: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    for section, payload in artifacts.items():
        rows = [_flatten_row(row) for row in _section_rows(payload)]
        row_counts[section] = len(rows)
        if not rows:
            continue
        fieldnames = sorted({key for row in rows for key in row})
        path = export_dir / f"{section}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        files[section] = str(path)
    row_counts["total"] = sum(value for key, value in row_counts.items() if key != "total")
    return files, row_counts


def _write_parquet_export(
    export_dir: Path,
    artifacts: dict[str, Any],
    *,
    engine: str,
) -> tuple[dict[str, str], dict[str, int]]:
    import pandas as pd

    files: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    for section, payload in artifacts.items():
        rows = [_flatten_row(row) for row in _section_rows(payload)]
        row_counts[section] = len(rows)
        if not rows:
            continue
        normalized_rows = [row if row else {"_empty": True} for row in rows]
        path = export_dir / f"{section}.parquet"
        pd.DataFrame(normalized_rows).to_parquet(path, index=False, engine=engine)
        files[section] = str(path)
    row_counts["total"] = sum(value for key, value in row_counts.items() if key != "total")
    return files, row_counts


def _section_row_counts(artifacts: dict[str, Any]) -> dict[str, int]:
    row_counts = {section: len(_section_rows(payload)) for section, payload in artifacts.items()}
    row_counts["total"] = sum(row_counts.values())
    return row_counts


def _parquet_dependency_status() -> dict[str, Any]:
    pandas_available = importlib.util.find_spec("pandas") is not None
    engines = {engine: importlib.util.find_spec(engine) is not None for engine in PARQUET_ENGINES}
    selected_engine = next((engine for engine in PARQUET_ENGINES if engines[engine]), None)
    available = bool(pandas_available and selected_engine)
    return {
        "available": available,
        "pandas": pandas_available,
        "engines": engines,
        "engine": selected_engine,
        "message": "parquet export available"
        if available
        else "Parquet export requires pandas plus pyarrow or fastparquet.",
    }


def _build_package_manifest(
    *,
    run_id: str,
    run_dir: Path,
    export_dir: Path,
    export_format: str,
    export_manifest_path: Path,
    files: dict[str, str],
    row_counts: dict[str, int],
    dependency: dict[str, Any],
    retention: dict[str, Any],
) -> dict[str, Any]:
    source_manifest_path = run_dir / "manifest.json"
    source_manifest = _read_json(source_manifest_path, default={})
    source_integrity = _file_integrity(source_manifest_path) if source_manifest_path.exists() else {}
    package_files = {
        name: _portable_file_entry(export_dir, Path(path))
        for name, path in sorted(files.items())
        if path
    }
    return {
        "schema_version": "quant_lab_export_package_v1",
        "source_run_id": run_id,
        "package_created_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "pipelines.backtest.artifact_exports.export_backtest_artifact_bundle",
        "format": export_format,
        "portable": True,
        "source": {
            "artifact_manifest_sha256": source_integrity.get("sha256"),
            "artifact_manifest_size_bytes": source_integrity.get("size_bytes"),
            "config_hash": source_manifest.get("config_hash") if isinstance(source_manifest, dict) else None,
            "code_version": source_manifest.get("code_version") if isinstance(source_manifest, dict) else {},
            "source_artifact_schema_version": source_manifest.get("schema_version") if isinstance(source_manifest, dict) else "",
        },
        "export_manifest": _portable_file_entry(export_dir, export_manifest_path),
        "files": package_files,
        "row_counts": row_counts,
        "dependency": dependency,
        "retention": retention,
    }


def _portable_file_entry(export_dir: Path, path: Path) -> dict[str, Any]:
    integrity = _file_integrity(path)
    try:
        relative_path = path.resolve().relative_to(export_dir.resolve()).as_posix()
    except ValueError:
        relative_path = path.name
    return {
        "relative_path": relative_path,
        "sha256": integrity["sha256"],
        "size_bytes": integrity["size_bytes"],
    }


def _build_integrity(files: dict[str, str]) -> dict[str, Any]:
    return {
        "algorithm": "sha256",
        "files": {name: _file_integrity(Path(path)) for name, path in sorted(files.items()) if path},
    }


def _empty_integrity() -> dict[str, Any]:
    return {"algorithm": "sha256", "files": {}}


def _file_integrity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _export_manifest_summary(manifest_path: Path, export_dir: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "status": "missing_manifest",
            "format": _format_from_export_dir(export_dir),
            "generated_at": "",
            "export_root": str(export_dir),
            "manifest_path": str(manifest_path),
            "row_counts": {},
            "total_rows": 0,
            "total_bytes": 0,
            "integrity_available": False,
            "files": {},
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "decode_failed",
            "format": _format_from_export_dir(export_dir),
            "generated_at": "",
            "export_root": str(export_dir),
            "manifest_path": str(manifest_path),
            "row_counts": {},
            "total_rows": 0,
            "total_bytes": 0,
            "integrity_available": False,
            "files": {},
            "error": str(exc),
        }

    integrity_files = ((manifest.get("integrity") or {}).get("files") or {})
    total_bytes = 0
    if isinstance(integrity_files, dict):
        total_bytes = sum(
            int(item.get("size_bytes") or 0)
            for item in integrity_files.values()
            if isinstance(item, dict)
        )
    row_counts = manifest.get("row_counts") if isinstance(manifest.get("row_counts"), dict) else {}
    return {
        "status": manifest.get("status") or "unknown",
        "format": manifest.get("format") or _format_from_export_dir(export_dir),
        "generated_at": manifest.get("generated_at") or "",
        "export_root": manifest.get("export_root") or str(export_dir),
        "manifest_path": str(manifest_path),
        "row_counts": row_counts,
        "total_rows": int(row_counts.get("total") or 0),
        "total_bytes": total_bytes,
        "integrity_available": bool(integrity_files),
        "files": manifest.get("files") if isinstance(manifest.get("files"), dict) else {},
        "retention": manifest.get("retention") if isinstance(manifest.get("retention"), dict) else {},
        "package_manifest": manifest.get("package_manifest") if isinstance(manifest.get("package_manifest"), dict) else {},
    }


def verify_export_package(package_path: str | Path) -> dict[str, Any]:
    target = Path(package_path)
    manifest_path, manifest_kind = _resolve_package_verification_manifest(target)
    package_root = manifest_path.parent
    verified_at = datetime.now(timezone.utc).isoformat()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "failed",
            "schema_version": "quant_lab_export_package_verification_v1",
            "verified_at": verified_at,
            "package_root": str(package_root),
            "manifest_path": str(manifest_path),
            "manifest_kind": manifest_kind,
            "files_checked": 0,
            "files_passed": 0,
            "files_failed": 0,
            "failures": [{"file": manifest_path.name, "reason": f"decode_error:{exc}"}],
            "files": {},
            "warnings": [],
        }

    if manifest_kind == "package_manifest":
        entries = _package_manifest_file_entries(manifest)
        warnings: list[str] = []
    else:
        entries = _legacy_export_manifest_file_entries(manifest)
        warnings = ["package_manifest_missing:verified_from_export_manifest"]

    if not entries:
        return {
            "status": "partial",
            "schema_version": "quant_lab_export_package_verification_v1",
            "verified_at": verified_at,
            "package_root": str(package_root),
            "manifest_path": str(manifest_path),
            "manifest_kind": manifest_kind,
            "source_run_id": manifest.get("source_run_id") or manifest.get("run_id") or "",
            "format": manifest.get("format") or manifest.get("export_format") or "unknown",
            "files_checked": 0,
            "files_passed": 0,
            "files_failed": 0,
            "failures": [{"file": "integrity", "reason": "missing_integrity_files"}],
            "files": {},
            "warnings": warnings,
        }

    file_results: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for name, expected in sorted(entries.items()):
        result = _verify_package_file_entry(
            package_root=package_root,
            name=name,
            expected=expected,
            legacy_manifest=manifest_kind == "export_manifest",
        )
        file_results[name] = result
        if result.get("status") != "passed":
            failures.append(
                {
                    "file": name,
                    "reason": result.get("reason") or "integrity_mismatch",
                    "sha256_match": result.get("sha256_match"),
                    "size_match": result.get("size_match"),
                    "path": result.get("path") or result.get("expected_path") or "",
                }
            )

    files_checked = len(file_results)
    files_failed = len([item for item in file_results.values() if item.get("status") != "passed"])
    return {
        "status": "success" if files_checked and files_failed == 0 else "partial",
        "schema_version": "quant_lab_export_package_verification_v1",
        "verified_at": verified_at,
        "package_root": str(package_root),
        "manifest_path": str(manifest_path),
        "manifest_kind": manifest_kind,
        "source_run_id": manifest.get("source_run_id") or manifest.get("run_id") or "",
        "format": manifest.get("format") or manifest.get("export_format") or "unknown",
        "files_checked": files_checked,
        "files_passed": files_checked - files_failed,
        "files_failed": files_failed,
        "failures": failures,
        "files": file_results,
        "warnings": warnings,
    }


def _resolve_export_manifest_path(run_dir: Path, export_manifest_path: str | None) -> Path:
    exports_root = run_dir / "exports"
    if not export_manifest_path:
        candidates = [
            path / "export_manifest.json"
            for path in exports_root.iterdir()
            if path.is_dir()
        ] if exports_root.exists() else []
        if not candidates:
            raise FileNotFoundError(str(exports_root))
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    raw_path = Path(str(export_manifest_path))
    candidate = raw_path if raw_path.is_absolute() else run_dir / raw_path
    resolved_exports_root = exports_root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_exports_root)
    except ValueError as exc:
        raise ValueError("export_manifest_path must stay within this run's exports directory") from exc
    if resolved_candidate.name != "export_manifest.json":
        raise ValueError("export_manifest_path must point to export_manifest.json")
    return resolved_candidate


def _resolve_export_file_path(export_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path) if raw_path else export_dir
    file_path = candidate if candidate.is_absolute() else export_dir / candidate
    resolved_export_dir = export_dir.resolve()
    resolved_file = file_path.resolve()
    try:
        resolved_file.relative_to(resolved_export_dir)
    except ValueError as exc:
        raise ValueError("export file path escapes export directory") from exc
    return resolved_file


def _resolve_package_verification_manifest(target: Path) -> tuple[Path, str]:
    if target.is_dir():
        package_manifest = target / "package_manifest.json"
        if package_manifest.exists():
            return package_manifest, "package_manifest"
        export_manifest = target / "export_manifest.json"
        if export_manifest.exists():
            return export_manifest, "export_manifest"
        raise FileNotFoundError(str(target / "package_manifest.json"))
    if target.name == "package_manifest.json":
        return target, "package_manifest"
    if target.name == "export_manifest.json":
        return target, "export_manifest"
    raise ValueError("package_path must be an export directory, package_manifest.json, or export_manifest.json")


def _package_manifest_file_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    export_manifest = manifest.get("export_manifest") if isinstance(manifest.get("export_manifest"), dict) else {}
    if export_manifest:
        entries["export_manifest"] = export_manifest
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    for name, item in files.items():
        if isinstance(item, dict):
            entries[str(name)] = item
    return entries


def _legacy_export_manifest_file_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    integrity_files = ((manifest.get("integrity") or {}).get("files") or {})
    if not isinstance(integrity_files, dict):
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for name, item in integrity_files.items():
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path") or "")
        entries[str(name)] = {
            "relative_path": Path(raw_path).name if raw_path else str(name),
            "path": raw_path,
            "sha256": item.get("sha256"),
            "size_bytes": item.get("size_bytes"),
        }
    return entries


def _verify_package_file_entry(
    *,
    package_root: Path,
    name: str,
    expected: dict[str, Any],
    legacy_manifest: bool,
) -> dict[str, Any]:
    expected_path = str(expected.get("relative_path") or expected.get("path") or "").strip()
    try:
        file_path = _resolve_package_file_path(package_root, expected_path, legacy_manifest=legacy_manifest)
    except ValueError as exc:
        return {
            "status": "failed",
            "reason": str(exc),
            "expected_path": expected_path,
        }
    if not file_path.exists() or not file_path.is_file():
        return {
            "status": "failed",
            "reason": "missing_file",
            "path": str(file_path),
            "expected_path": expected_path,
        }
    actual = _file_integrity(file_path)
    expected_sha = expected.get("sha256")
    expected_size = expected.get("size_bytes")
    sha_match = actual["sha256"] == expected_sha
    size_match = actual["size_bytes"] == expected_size
    return {
        "status": "passed" if sha_match and size_match else "failed",
        "reason": "" if sha_match and size_match else "integrity_mismatch",
        "path": str(file_path),
        "relative_path": _safe_relative_path(package_root, file_path),
        "expected_sha256": expected_sha,
        "actual_sha256": actual["sha256"],
        "expected_size_bytes": expected_size,
        "actual_size_bytes": actual["size_bytes"],
        "sha256_match": sha_match,
        "size_match": size_match,
        "file_key": name,
    }


def _resolve_package_file_path(package_root: Path, raw_path: str, *, legacy_manifest: bool) -> Path:
    if not raw_path:
        raise ValueError("package file path is required")
    raw = Path(raw_path)
    candidate = package_root / raw.name if raw.is_absolute() and legacy_manifest else package_root / raw
    resolved_root = package_root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("package file path escapes export directory") from exc
    return resolved_candidate


def _safe_relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _format_from_export_dir(export_dir: Path) -> str:
    name = export_dir.name
    return name.rsplit("_", 1)[-1] if "_" in name else "unknown"


def _apply_export_retention(
    *,
    exports_root: Path,
    current_export_dir: Path,
    keep_last_exports: int | None,
) -> dict[str, Any]:
    keep_last = _coerce_keep_last_exports(keep_last_exports)
    if keep_last <= 0:
        return _retention_result(keep_last_exports, applied=False)
    exports_root.mkdir(parents=True, exist_ok=True)
    resolved_exports_root = exports_root.resolve()
    current_resolved = current_export_dir.resolve()
    _validate_direct_export_dir(current_resolved, exports_root=resolved_exports_root, label="current export directory")
    export_dirs = [
        path
        for path in exports_root.iterdir()
        if path.is_dir() and path.resolve() != current_resolved
    ]
    export_dirs = sorted(export_dirs, key=lambda path: path.stat().st_mtime, reverse=True)
    keep_older = max(0, keep_last - 1)
    prune_dirs = export_dirs[keep_older:]
    pruned: list[str] = []
    for path in prune_dirs:
        target = _validate_direct_export_dir(path, exports_root=resolved_exports_root, label="export retention target")
        shutil.rmtree(target)
        pruned.append(str(path))
    return {
        "policy": "keep_last_exports",
        "keep_last_exports": keep_last,
        "retention_applied": True,
        "pruned_export_count": len(pruned),
        "pruned_exports": pruned,
    }


def _export_cleanup_plan(
    *,
    run_id: str,
    artifact_root: Path,
    keep_last_exports: int | None,
    apply_cleanup: bool,
) -> dict[str, Any]:
    clean_run_id = _clean_run_id(run_id)
    run_dir = artifact_root / clean_run_id
    if not run_dir.exists():
        raise FileNotFoundError(str(run_dir))

    keep_last = _coerce_keep_last_exports(keep_last_exports)
    exports_root = run_dir / "exports"
    export_dirs = _sorted_export_dirs(exports_root)
    if keep_last <= 0:
        return {
            "status": "disabled",
            "run_id": clean_run_id,
            "policy": "disabled",
            "keep_last_exports": 0,
            "cleanup_applied": False,
            "export_count": len(export_dirs),
            "kept_export_count": len(export_dirs),
            "prune_export_count": 0,
            "kept_exports": [_export_cleanup_summary(path) for path in export_dirs],
            "prune_exports": [],
            "pruned_exports": [],
            "total_bytes_to_prune": 0,
            "total_bytes_pruned": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    kept_dirs = export_dirs[:keep_last]
    prune_dirs = export_dirs[keep_last:]
    prune_summaries = [_export_cleanup_summary(path) for path in prune_dirs]
    bytes_to_prune = sum(int(item.get("total_bytes") or 0) for item in prune_summaries)
    pruned: list[str] = []
    if apply_cleanup:
        resolved_exports_root = exports_root.resolve()
        for path in prune_dirs:
            target = _validate_direct_export_dir(path, exports_root=resolved_exports_root, label="export cleanup target")
            shutil.rmtree(target)
            pruned.append(str(path))

    return {
        "status": "success",
        "run_id": clean_run_id,
        "policy": "keep_last_exports",
        "keep_last_exports": keep_last,
        "cleanup_applied": bool(apply_cleanup and prune_dirs),
        "export_count": len(export_dirs),
        "kept_export_count": len(kept_dirs),
        "prune_export_count": len(prune_dirs),
        "kept_exports": [_export_cleanup_summary(path) for path in kept_dirs],
        "prune_exports": prune_summaries,
        "pruned_exports": pruned,
        "total_bytes_to_prune": bytes_to_prune,
        "total_bytes_pruned": bytes_to_prune if pruned else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _cross_run_export_cleanup_plan(
    *,
    artifact_root: Path,
    keep_last_exports: int | None,
    stale_after_days: int | None,
    limit: int,
    apply_cleanup: bool,
    preview_id: str | None,
    candidate_ids: list[Any] | None,
) -> dict[str, Any]:
    keep_last = _coerce_cross_run_keep_last_exports(keep_last_exports)
    stale_days = _coerce_stale_after_days(stale_after_days)
    item_limit = max(1, min(int(limit or 100), 500))
    generated_at = datetime.now(timezone.utc)
    all_candidates: list[dict[str, Any]] = []
    run_count = 0
    runs_with_exports = 0
    export_directory_count = 0

    run_dirs = []
    if artifact_root.exists():
        run_dirs = sorted(
            [path for path in artifact_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    for run_dir in run_dirs:
        run_count += 1
        run_id = run_dir.name
        export_dirs = _sorted_export_dirs(run_dir / "exports")
        if not export_dirs:
            continue
        runs_with_exports += 1
        export_directory_count += len(export_dirs)
        for export_dir in export_dirs[keep_last:]:
            summary = _export_cleanup_summary(export_dir)
            export_time = _export_generated_at(summary)
            age_days = _age_days(export_time, generated_at) if export_time else None
            if stale_days > 0 and (age_days is None or age_days < stale_days):
                continue
            all_candidates.append(
                _cross_run_cleanup_candidate(
                    run_id=run_id,
                    export_dir=export_dir,
                    summary=summary,
                    age_days=age_days,
                    keep_last_exports=keep_last,
                    stale_after_days=stale_days,
                )
            )

    all_candidates = sorted(
        all_candidates,
        key=lambda item: (str(item.get("run_id") or ""), str(item.get("generated_at") or ""), str(item.get("export_root") or "")),
    )
    candidates = all_candidates[:item_limit]
    current_preview_id = _cross_run_cleanup_preview_id(
        artifact_root=artifact_root,
        keep_last_exports=keep_last,
        stale_after_days=stale_days,
        candidates=candidates,
    )

    pruned_exports: list[dict[str, Any]] = []
    if apply_cleanup:
        supplied_preview_id = str(preview_id or "").strip()
        if not supplied_preview_id:
            raise ValueError("cross-run cleanup requires preview_id from a fresh cleanup preview")
        if supplied_preview_id != current_preview_id:
            raise ValueError("cross-run cleanup preview_id does not match current cleanup candidates")
        supplied_candidate_ids = _normalize_cleanup_candidate_ids(candidate_ids)
        current_candidate_ids = sorted(str(item.get("candidate_id") or "") for item in candidates)
        if supplied_candidate_ids != current_candidate_ids:
            raise ValueError("cross-run cleanup requires the exact current candidate_ids from cleanup preview")
        for candidate in candidates:
            target = _validate_cross_run_cleanup_target(
                Path(str(candidate.get("export_root") or "")),
                artifact_root=artifact_root,
                run_id=str(candidate.get("run_id") or ""),
            )
            shutil.rmtree(target)
            pruned = dict(candidate)
            pruned["pruned"] = True
            pruned_exports.append(pruned)

    candidate_bytes = sum(int(item.get("total_bytes") or 0) for item in candidates)
    return {
        "status": "success",
        "schema_version": "quant_lab_cross_run_export_cleanup_v1",
        "generated_at": generated_at.isoformat(),
        "artifact_root": str(artifact_root),
        "policy": "keep_last_exports_and_stale_after_days",
        "keep_last_exports": keep_last,
        "stale_after_days": stale_days,
        "limit": item_limit,
        "preview_id": current_preview_id,
        "cleanup_applied": bool(apply_cleanup and pruned_exports),
        "run_count": run_count,
        "runs_with_exports": runs_with_exports,
        "export_directory_count": export_directory_count,
        "eligible_export_count": len(all_candidates),
        "candidate_count": len(candidates),
        "limited": len(all_candidates) > len(candidates),
        "candidate_ids": [str(item.get("candidate_id") or "") for item in candidates],
        "candidates": candidates,
        "pruned_export_count": len(pruned_exports),
        "pruned_exports": pruned_exports,
        "total_bytes_to_prune": candidate_bytes,
        "total_bytes_pruned": candidate_bytes if pruned_exports else 0,
    }


def _cross_run_cleanup_candidate(
    *,
    run_id: str,
    export_dir: Path,
    summary: dict[str, Any],
    age_days: int | None,
    keep_last_exports: int,
    stale_after_days: int,
) -> dict[str, Any]:
    candidate = {
        "run_id": run_id,
        "export_dir_name": export_dir.name,
        "export_root": str(export_dir),
        "manifest_path": summary.get("manifest_path") or str(export_dir / "export_manifest.json"),
        "status": summary.get("status") or "unknown",
        "format": summary.get("format") or "unknown",
        "generated_at": _export_generated_at(summary),
        "age_days": age_days,
        "total_bytes": int(summary.get("total_bytes") or 0),
        "total_rows": int(summary.get("total_rows") or 0),
        "integrity_available": bool(summary.get("integrity_available")),
        "reason": "older_than_keep_last_and_stale",
        "keep_last_exports": keep_last_exports,
        "stale_after_days": stale_after_days,
    }
    candidate["candidate_id"] = _cross_run_cleanup_candidate_id(candidate)
    return candidate


def _cross_run_cleanup_candidate_id(candidate: dict[str, Any]) -> str:
    payload = {
        "run_id": candidate.get("run_id") or "",
        "export_dir_name": candidate.get("export_dir_name") or "",
        "export_root": candidate.get("export_root") or "",
        "manifest_path": candidate.get("manifest_path") or "",
        "generated_at": candidate.get("generated_at") or "",
        "total_bytes": int(candidate.get("total_bytes") or 0),
        "total_rows": int(candidate.get("total_rows") or 0),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cross_run_cleanup_preview_id(
    *,
    artifact_root: Path,
    keep_last_exports: int,
    stale_after_days: int,
    candidates: list[dict[str, Any]],
) -> str:
    try:
        root = str(artifact_root.resolve())
    except FileNotFoundError:
        root = str(artifact_root)
    payload = {
        "schema_version": "quant_lab_cross_run_export_cleanup_v1",
        "artifact_root": root,
        "keep_last_exports": keep_last_exports,
        "stale_after_days": stale_after_days,
        "candidate_ids": sorted(str(item.get("candidate_id") or "") for item in candidates),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_cleanup_candidate_ids(candidate_ids: list[Any] | None) -> list[str]:
    if not isinstance(candidate_ids, list):
        raise ValueError("cross-run cleanup requires candidate_ids from cleanup preview")
    normalized: list[str] = []
    for item in candidate_ids:
        if isinstance(item, dict):
            value = item.get("candidate_id")
        else:
            value = item
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("cross-run cleanup candidate_ids cannot include empty values")
        normalized.append(clean)
    return sorted(normalized)


def _validate_cross_run_cleanup_target(path: Path, *, artifact_root: Path, run_id: str) -> Path:
    clean_run_id = _clean_run_id(run_id)
    exports_root = (artifact_root / clean_run_id / "exports").resolve()
    resolved_path = path.resolve()
    return _validate_direct_export_dir(resolved_path, exports_root=exports_root, label="cross-run cleanup target")


def _validate_direct_export_dir(path: Path, *, exports_root: Path, label: str) -> Path:
    resolved_exports_root = exports_root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_exports_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within its run exports directory") from exc
    if resolved_path.parent != resolved_exports_root:
        raise ValueError(f"{label} must be a direct generated export directory")
    if not resolved_path.exists() or not resolved_path.is_dir():
        raise FileNotFoundError(str(resolved_path))
    return resolved_path


def _coerce_cross_run_keep_last_exports(value: int | None) -> int:
    keep_last = _coerce_keep_last_exports(value)
    if keep_last <= 0:
        raise ValueError("cross-run cleanup requires keep_last_exports >= 1")
    return keep_last


def _sorted_export_dirs(exports_root: Path) -> list[Path]:
    if not exports_root.exists():
        return []
    return sorted(
        [path for path in exports_root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _export_cleanup_summary(export_dir: Path) -> dict[str, Any]:
    summary = _export_manifest_summary(export_dir / "export_manifest.json", export_dir)
    summary["directory"] = str(export_dir)
    summary["directory_size_bytes"] = _directory_size(export_dir)
    summary["total_bytes"] = int(summary.get("total_bytes") or 0) or int(summary["directory_size_bytes"])
    return summary


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _retention_result(keep_last_exports: int | None, *, applied: bool) -> dict[str, Any]:
    keep_last = _coerce_keep_last_exports(keep_last_exports)
    return {
        "policy": "keep_last_exports" if keep_last > 0 else "disabled",
        "keep_last_exports": keep_last,
        "retention_applied": applied,
        "pruned_export_count": 0,
        "pruned_exports": [],
    }


def _coerce_keep_last_exports(value: int | None) -> int:
    if value is None:
        return 0
    try:
        return max(0, min(int(value), 100))
    except (TypeError, ValueError):
        return 0


def _coerce_stale_after_days(value: int | None) -> int:
    if value is None:
        return 30
    try:
        return max(0, min(int(value), 3650))
    except (TypeError, ValueError):
        return 30


def _export_generated_at(item: dict[str, Any]) -> str:
    generated = str(item.get("generated_at") or "")
    if generated:
        return generated
    directory = item.get("directory") or item.get("export_root")
    if not directory:
        return ""
    try:
        return datetime.fromtimestamp(Path(str(directory)).stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return ""


def _storage_export_candidate(run_id: str, item: dict[str, Any], now: datetime) -> dict[str, Any]:
    generated_at = _export_generated_at(item)
    return {
        "run_id": run_id,
        "status": item.get("status") or "unknown",
        "format": item.get("format") or "unknown",
        "generated_at": generated_at,
        "age_days": _age_days(generated_at, now) if generated_at else None,
        "total_bytes": int(item.get("total_bytes") or 0),
        "total_rows": int(item.get("total_rows") or 0),
        "export_root": item.get("directory") or item.get("export_root") or "",
        "manifest_path": item.get("manifest_path") or "",
        "integrity_available": bool(item.get("integrity_available")),
    }


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(value: str, now: datetime) -> int:
    parsed = _parse_iso_datetime(value)
    if not parsed:
        return 0
    return max(0, int((now - parsed).total_seconds() // 86400))


def _min_iso_datetime(current: str, candidate: str) -> str:
    if not current:
        return candidate
    current_dt = _parse_iso_datetime(current)
    candidate_dt = _parse_iso_datetime(candidate)
    if not current_dt or not candidate_dt:
        return current
    return candidate if candidate_dt < current_dt else current


def _max_iso_datetime(current: str, candidate: str) -> str:
    if not current:
        return candidate
    current_dt = _parse_iso_datetime(current)
    candidate_dt = _parse_iso_datetime(candidate)
    if not current_dt or not candidate_dt:
        return current
    return candidate if candidate_dt > current_dt else current


def _section_rows(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if payload is None:
        return []
    return [payload]


def _flatten_row(row: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(row, dict):
        return {prefix.rstrip(".") or "value": row}
    flattened: dict[str, Any] = {}
    for key, value in row.items():
        flat_key = f"{prefix}{key}"
        if isinstance(value, dict):
            nested = _flatten_row(value, prefix=f"{flat_key}.")
            flattened.update(nested)
        elif isinstance(value, list):
            flattened[flat_key] = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        else:
            flattened[flat_key] = value
    return flattened


def _clean_run_id(run_id: str) -> str:
    clean = "".join(ch for ch in str(run_id or "") if ch.isalnum() or ch in {"_", "-"})
    if not clean:
        raise FileNotFoundError("run_id is required")
    return clean
