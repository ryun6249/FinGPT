from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from core.config.settings import load_settings
from core.utils.build_info import build_info
from core.preflight import run_preflight
from core.schemas.request import (
    COMPARE_MAX_CONCURRENCY,
    COMPARE_MAX_TICKERS,
    DEFAULT_COLLECTION_SOURCES,
    DISABLED_COLLECTION_SOURCES,
    KNOWN_COLLECTION_SOURCES,
    PRIMARY_COLLECTION_SOURCES,
)
from core.utils.eval_dashboard import load_eval_dashboard
from core.utils.logger import get_logger
from core.utils.qdrant_admin import get_collection_info, purge_points
from pipelines.collect.cache import get_cache as get_collection_cache
from pipelines.output.exporters import response_to_csv, response_to_jsonl
from pipelines.output.run_history import (
    get_run as history_get_run,
    list_runs as history_list_runs,
    ticker_summary as history_ticker_summary,
)


router = APIRouter(prefix="/api/v1", tags=["system"])
logger = get_logger("api.system")
_settings = load_settings()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
API_VERSION = "1.1.0"

SUPPORTED_INFERENCE_ROUTES = (
    "qwen",
    "mistral",
    "ollama",
    "primary",
    "fingpt",
    "llama-2",
    "gemma4",
    "gemma",
    "gemma-experimental",
)

# Full preflight touches local services and provider probes. Keep the status
# pill responsive across multiple open UI tabs; manual force refresh still
# bypasses this cache.
_PREFLIGHT_CACHE_TTL_SEC = 300
_preflight_cache: dict[str, Any] = {"ts": 0.0, "report": None}
_preflight_lock = asyncio.Lock()


def _ui_model_options() -> list[dict[str, Any]]:
    primary_model = getattr(_settings, "primary_model", "qwen2.5:7b")
    options = [
        {
            "id": "qwen",
            "model": primary_model,
            "label": f"{primary_model} (Ollama · 기본)",
            "role": "primary",
            "enabled": True,
            "availability": "runtime_checked",
            "availability_note": "Configured route; Ollama model availability is verified when a request runs.",
        }
    ]
    gemma4_model = getattr(_settings, "gemma4_model", None) or getattr(_settings, "experimental_fallback_model", "gemma4:e4b")
    if gemma4_model:
        options.append(
            {
                "id": "gemma4",
                "model": gemma4_model,
                "label": f"{gemma4_model} (Gemma4 E4B experimental)",
                "role": "experimental",
                "enabled": True,
                "availability": "runtime_checked",
                "availability_note": "Displayed only as a configured route; local model availability is not claimed until runtime.",
            }
        )
    if bool(getattr(_settings, "enable_experimental_fallback", False)):
        options.append(
            {
                "id": "gemma-experimental",
                "model": getattr(_settings, "experimental_fallback_model", "gemma4:e4b"),
                "label": f"{getattr(_settings, 'experimental_fallback_model', 'gemma4:e4b')} (fallback)",
                "role": "fallback",
                "enabled": True,
                "availability": "runtime_checked",
                "availability_note": "Displayed only when experimental fallback is enabled; checked at runtime.",
            }
        )
    return options


def _ui_presets() -> list[dict[str, str]]:
    return [
        {"id": "risk", "label": "핵심 리스크", "question": "현재 가격과 재무 지표 기준으로 가장 중요한 하방 리스크와 확인해야 할 시나리오는 무엇인가요?"},
        {"id": "catalyst", "label": "상승 촉매", "question": "향후 6~12개월 동안 가격을 움직일 수 있는 검증 가능한 상승 촉매는 무엇인가요?"},
        {"id": "thesis", "label": "12개월 투자 가설", "question": "최신 가격, 재무 지표, 수집 근거를 기준으로 12개월 투자 가설을 정리해주세요."},
        {"id": "earnings", "label": "실적 신호", "question": "최근 실적과 가이던스에서 확인되는 매출, 마진, 비용 구조의 핵심 신호를 요약해주세요."},
        {"id": "competitive", "label": "경쟁 구도", "question": "경쟁 구도가 어떻게 변하고 있으며 가격 결정력과 점유율에는 어떤 영향을 주나요?"},
    ]


@router.get("/config")
async def get_config() -> dict[str, Any]:
    return {
        "models": _ui_model_options(),
        "default_model": "qwen",
        "output_language": getattr(_settings, "output_language", "ko"),
        "risk_engine": getattr(_settings, "risk_engine", "heuristic"),
        "sources": {
            "known": list(KNOWN_COLLECTION_SOURCES),
            "default": list(DEFAULT_COLLECTION_SOURCES),
            "primary": list(PRIMARY_COLLECTION_SOURCES),
            "disabled": list(DISABLED_COLLECTION_SOURCES),
        },
        "limits": {
            "lookback_days": {"min": 1, "max": 365, "default": 90},
            "top_k": {"min": 1, "max": 20, "default": 15},
            "compare": {
                "max_tickers": COMPARE_MAX_TICKERS,
                "max_concurrency": COMPARE_MAX_CONCURRENCY,
                "default_concurrency": 2,
            },
        },
        "topic_mode_enabled": bool(getattr(_settings, "topic_mode_enabled", True)),
        "presets": _ui_presets(),
        "dashboard": {
            "news_endpoint": "/api/v1/dashboard/news",
            "tradingview_enabled": True,
        },
        "fingpt": {
            "datasets_enabled": bool(getattr(_settings, "fingpt_datasets_enabled", False)),
            "task_model_enabled": bool(getattr(_settings, "fingpt_task_model_enabled", False)),
            "task_model": getattr(_settings, "fingpt_task_model_name", ""),
            "tasks": ["sentiment", "headline", "ner", "relation", "fiqa_qa", "forecaster"],
            "default_behavior": "disabled_fail_open",
        },
    }


@router.get("/config/legacy")
async def get_config_legacy() -> dict[str, Any]:
    return {
        "models": list(SUPPORTED_INFERENCE_ROUTES),
        "default_model": "qwen",
        "presets": _ui_presets(),
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Failed to read JSON at {path}: {exc}")
        return None


@router.get("/outputs/latest")
async def get_latest_outputs() -> JSONResponse:
    payload = {
        "response": _read_json(OUTPUTS_DIR / "latest_response.json"),
        "collection": _read_json(OUTPUTS_DIR / "latest_collection.json"),
        "request": _read_json(OUTPUTS_DIR / "latest_request.json"),
        "has_markdown": (OUTPUTS_DIR / "latest_report.md").exists(),
        "has_html": (OUTPUTS_DIR / "latest_report.html").exists(),
    }
    return JSONResponse(payload)


@router.get("/outputs/report.md", response_class=PlainTextResponse)
async def get_latest_markdown():
    path = OUTPUTS_DIR / "latest_report.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No markdown report available yet.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@router.get("/outputs/report.html")
async def get_latest_html():
    path = OUTPUTS_DIR / "latest_report.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No HTML report available yet.")
    return FileResponse(path, media_type="text/html")


def _load_response_payload(run_id: str | None) -> dict[str, Any]:
    if run_id:
        entry = history_get_run(outputs_dir=OUTPUTS_DIR, run_id=run_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"run '{run_id}' not found")
        response = entry.get("response") if isinstance(entry, dict) else None
        if not response:
            raise HTTPException(status_code=404, detail=f"run '{run_id}' has no response payload")
        return response
    latest = _read_json(OUTPUTS_DIR / "latest_response.json")
    if not latest:
        raise HTTPException(status_code=404, detail="No analysis response available yet.")
    return latest


def _export_filename(payload: dict[str, Any], run_id: str | None, ext: str) -> str:
    ticker = str(payload.get("ticker") or "analysis").strip().upper()
    stamp = run_id or time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    safe_stamp = stamp.replace(":", "").replace("/", "_")
    return f"fingpt_{ticker}_{safe_stamp}.{ext}"


@router.get("/outputs/export/csv", response_class=PlainTextResponse)
async def export_csv(run_id: str | None = None):
    payload = _load_response_payload(run_id)
    body = response_to_csv(payload)
    return PlainTextResponse(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(payload, run_id, "csv")}"'},
    )


@router.get("/outputs/export/jsonl", response_class=PlainTextResponse)
async def export_jsonl(run_id: str | None = None, include_raw_context: bool = True):
    payload = _load_response_payload(run_id)
    body = response_to_jsonl(payload, include_raw_context=include_raw_context)
    return PlainTextResponse(
        body,
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_filename(payload, run_id, "jsonl")}"'},
    )


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "version": API_VERSION, "build": build_info()}


@router.get("/runs")
async def list_runs(
    ticker: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="limit/offset must be integers")
    items = history_list_runs(outputs_dir=OUTPUTS_DIR, ticker=ticker, limit=limit, offset=offset)
    return {"count": len(items), "items": items}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    entry = history_get_run(outputs_dir=OUTPUTS_DIR, run_id=run_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"run '{run_id}' not found")
    return entry


_FAILURE_MODES_RUNBOOK = [
    {
        "code": "QDRANT_SERVICE",
        "label": "Qdrant vector DB unreachable",
        "symptom": "retrieval returns empty / pipeline fails before inference.",
        "remediation": [
            "`docker ps` to confirm the `fingpt-qdrant` container is running.",
            "`docker start fingpt-qdrant` or re-run `scripts/bootstrap_local.ps1`.",
            "Check QDRANT_URL in .env (default http://localhost:6333).",
        ],
        "docs": ["docs/quickstart.md", "docs/runbook.md"],
    },
    {
        "code": "QDRANT_QUERY_STACK",
        "label": "Embedding / query stack not ready",
        "symptom": "Qdrant is up but embedding/add/query smoke test fails.",
        "remediation": [
            "Ensure fastembed model files finished downloading.",
            "Delete the stale collection and let pipeline recreate it.",
            "Re-run preflight once the embedder finishes warming up.",
        ],
        "docs": ["docs/runbook.md"],
    },
    {
        "code": "OLLAMA_SERVICE",
        "label": "Ollama daemon unreachable",
        "symptom": "inference stage raises ConnectionError to 11434.",
        "remediation": [
            "Start the Ollama app / service (`ollama serve`).",
            "Verify `curl http://localhost:11434/api/tags` returns JSON.",
            "Check OLLAMA_BASE_URL in .env.",
        ],
        "docs": ["docs/quickstart.md"],
    },
    {
        "code": "OLLAMA_MODEL",
        "label": "Primary model missing",
        "symptom": "model '{primary_model}' not installed.",
        "remediation": [
            "`ollama pull qwen2.5:7b` for the production baseline.",
            "Optionally enable experimental fallback in .env.",
        ],
        "docs": ["docs/quickstart.md"],
    },
    {
        "code": "FMP_API_KEY",
        "label": "FMP API key missing",
        "symptom": "transcript + stock news sources silently return empty.",
        "remediation": [
            "Set FMP_API_KEY in .env.",
            "Disable news/transcript sources in the UI if you cannot provide a key.",
        ],
        "docs": ["docs/quickstart.md"],
    },
    {
        "code": "TRANSCRIPT_PROVIDER",
        "label": "Transcript endpoint rejected",
        "symptom": "402 entitlement required or 4xx from FMP.",
        "remediation": [
            "Confirm the FMP plan covers earning_call_transcript.",
            "Run without transcripts until entitlement is resolved.",
        ],
        "docs": ["docs/runbook.md"],
    },
    {
        "code": "SEC_FILINGS",
        "label": "SEC EDGAR rate-limited",
        "symptom": "429 from data.sec.gov.",
        "remediation": [
            "SEC requires a User-Agent header; ensure SEC_USER_AGENT is populated.",
            "Back off and re-run; EDGAR caps aggressive polling.",
        ],
        "docs": ["docs/runbook.md"],
    },
    {
        "code": "YFINANCE_FEED",
        "label": "Yahoo Finance feed offline",
        "symptom": "news source returns empty context.",
        "remediation": [
            "Retry; yfinance is unofficial and occasionally rate-limits.",
            "Check outbound network / corporate proxy settings.",
        ],
        "docs": ["docs/runbook.md"],
    },
    {
        "code": "HF_TOKEN",
        "label": "HF_TOKEN missing",
        "symptom": "some optional embeddings / models skip.",
        "remediation": [
            "Set HF_TOKEN in .env if gated models are required.",
            "Non-blocking when using default local embeddings.",
        ],
        "docs": ["docs/quickstart.md"],
    },
]


def _run_preflight_sync() -> dict[str, Any]:
    return run_preflight()


async def _get_preflight_report(force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force and _preflight_cache["report"] is not None and (now - _preflight_cache["ts"]) < _PREFLIGHT_CACHE_TTL_SEC:
        return _preflight_cache["report"]

    async with _preflight_lock:
        now = time.time()
        if not force and _preflight_cache["report"] is not None and (now - _preflight_cache["ts"]) < _PREFLIGHT_CACHE_TTL_SEC:
            return _preflight_cache["report"]
        loop = asyncio.get_running_loop()
        report = await loop.run_in_executor(None, _run_preflight_sync)
        report = dict(report)
        report["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["ttl_seconds"] = _PREFLIGHT_CACHE_TTL_SEC
        _preflight_cache["report"] = report
        _preflight_cache["ts"] = time.time()
        return report


@router.get("/preflight")
async def preflight_status(force: bool = False) -> dict[str, Any]:
    return await _get_preflight_report(force=force)


@router.get("/runbook/failure-modes")
async def runbook_failure_modes() -> dict[str, Any]:
    return {"version": 1, "modes": _FAILURE_MODES_RUNBOOK}


@router.get("/collection/cache")
async def collection_cache_stats() -> dict[str, Any]:
    return get_collection_cache(_settings).stats()


@router.post("/collection/cache/invalidate")
async def collection_cache_invalidate(ticker: str | None = None) -> dict[str, Any]:
    dropped = get_collection_cache(_settings).invalidate(ticker)
    return {"dropped": dropped, "ticker": ticker}


@router.get("/eval/dashboard")
async def eval_dashboard() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(load_eval_dashboard, PROJECT_ROOT)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[EVAL_DASHBOARD] failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/qdrant/collection")
async def qdrant_collection_info() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(get_collection_info)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[QDRANT_ADMIN] info failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/qdrant/purge")
async def qdrant_purge(
    older_than_days: int | None = None,
    ticker: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if older_than_days is None and not ticker:
        raise HTTPException(
            status_code=400,
            detail="Provide older_than_days and/or ticker; refusing to purge the entire collection.",
        )
    try:
        return await asyncio.to_thread(
            purge_points,
            older_than_days=older_than_days,
            ticker=ticker,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[QDRANT_ADMIN] purge failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/runs/summary/{ticker}")
async def run_summary_for_ticker(ticker: str, limit: int = 10) -> dict[str, Any]:
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="limit must be an integer")
    series = history_ticker_summary(outputs_dir=OUTPUTS_DIR, ticker=ticker, limit=limit)
    return {"ticker": ticker.upper(), "points": list(reversed(series))}
