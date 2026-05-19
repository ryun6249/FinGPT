"""
Answer-quality evaluation suite for the local FinGPT stack.

The suite now supports:
  - ``analysis``: single-ticker equity cases
  - ``topic``: cross-asset / topic / universal routing cases
  - ``all``: both suites

Artifacts are written to ``reports/quality_review_results.json`` and mirrored
to the legacy ``quality_review_results.json`` path for compatibility.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from core.preflight import run_preflight
from core.schemas.request import AnalysisRequest, UniversalRequest
from core.schemas.response import CompareResponse
from core.schemas.topic import TopicRequest
from core.utils.validation_metrics import (
    as_payload_dict,
    claim_evidence_date_coverage,
    citation_count,
    decision_quality_metrics,
    decision_richness,
    detect_mode,
    duplicate_paragraph_ratio,
    evidence_count,
    has_warning_only_partial,
    language_ok,
    metric_as_of_coverage,
    partial_reason_is_actionable,
    quant_snapshot_present,
    topic_bucket_coverage,
    topic_final_gate,
)
from pipelines.orchestration.dispatch import dispatch_async
from pipelines.orchestration.research_pipeline import _detect_lens, run_pipeline_async
from pipelines.orchestration.topic_pipeline import run_topic_pipeline_async


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "quality_review_results.json"
LEGACY_OUTPUT_PATH = PROJECT_ROOT / "quality_review_results.json"


ANALYSIS_CASES = [
    {
        "suite": "analysis",
        "category": "A. Catalyst",
        "desc": "MSFT AI cloud catalyst drivers",
        "ticker": "MSFT",
        "question": "마이크로소프트의 Azure와 AI 관련 향후 30일 핵심 상승 촉매를 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "A. Catalyst",
        "desc": "AAPL product cycle catalyst",
        "ticker": "AAPL",
        "question": "애플의 단기 제품 사이클과 실적 관련 촉매를 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "A. Catalyst",
        "desc": "META ad revenue and AI monetization",
        "ticker": "META",
        "question": "META의 다음 분기 상승 요인이 될 수 있는 실적과 AI 수익화 촉매를 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "B. Risk",
        "desc": "NVDA geopolitical and valuation risks",
        "ticker": "NVDA",
        "question": "엔비디아의 단기 하방 리스크를 지정학과 밸류에이션 중심으로 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "B. Risk",
        "desc": "TSLA execution and demand risks",
        "ticker": "TSLA",
        "question": "테슬라의 향후 60일 수요와 실행 리스크를 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "B. Risk",
        "desc": "AMZN AWS competition and retail margin risks",
        "ticker": "AMZN",
        "question": "아마존의 AWS 경쟁과 리테일 마진 측면 리스크를 정리해줘.",
        "lookback_days": 30,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "C. Near-Term",
        "desc": "GOOGL antitrust and AI search developments",
        "ticker": "GOOGL",
        "question": "알파벳의 단기 규제 이슈와 AI 검색 관련 핵심 변수를 정리해줘.",
        "lookback_days": 21,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "C. Near-Term",
        "desc": "JPM macro and earnings developments",
        "ticker": "JPM",
        "question": "지금 JPM에 중요한 거시 변수와 회사별 이슈를 정리해줘.",
        "lookback_days": 21,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "D. Sparse",
        "desc": "UONE thin coverage debt and revenue focus",
        "ticker": "UONE",
        "question": "Urban One의 현재 재무 상태와 단기 전망을 정리해줘.",
        "lookback_days": 30,
        "allow_sparse": True,
        "min_citations": 0,
    },
    {
        "suite": "analysis",
        "category": "D. Sparse",
        "desc": "SIGA small-cap biopharma coverage",
        "ticker": "SIGA",
        "question": "SIGA 주주에게 중요한 최근 뉴스와 개발 상황을 정리해줘.",
        "lookback_days": 30,
        "allow_sparse": True,
        "min_citations": 0,
    },
    {
        "suite": "analysis",
        "category": "E. Ambiguous",
        "desc": "MSFT broad investment question",
        "ticker": "MSFT",
        "question": "마이크로소프트가 지금 투자 매력이 있는지 근거 중심으로 정리해줘.",
        "lookback_days": 14,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "E. Ambiguous",
        "desc": "SPY ETF near-term factors",
        "ticker": "SPY",
        "question": "S&P500의 단기 강세 요인과 약세 요인을 정리해줘.",
        "lookback_days": 14,
        "min_citations": 1,
    },
    {
        "suite": "analysis",
        "category": "E. Ambiguous",
        "desc": "NVDA one-year thesis from recent context",
        "ticker": "NVDA",
        "question": "엔비디아의 12개월 투자 가설을 최근 공개 정보 기준으로 정리해줘.",
        "lookback_days": 7,
        "min_citations": 1,
    },
]


TOPIC_CASES = [
    {
        "suite": "topic",
        "category": "Rates / Bonds",
        "desc": "TLT rate attractiveness",
        "runner": "topic",
        "theme": "미국 장기채 금리와 TLT 매력도",
        "question": "거시경제와 금리 구조를 감안할 때 지금 TLT가 중장기 관점에서 매력적인지 분석해줘.",
        "related_tickers": ["TLT"],
        "lookback_days": 60,
        "top_k": 10,
        "min_citations": 1,
    },
    {
        "suite": "topic",
        "category": "Commodities",
        "desc": "GLD real-rate sensitivity",
        "runner": "universal",
        "question": "실질금리와 달러 흐름을 기준으로 지금 GLD가 매력적인지 분석해줘.",
        "ticker": "GLD",
        "mode_hint": "topic",
        "lookback_days": 60,
        "top_k": 10,
        "min_citations": 1,
    },
    {
        "suite": "topic",
        "category": "FX",
        "desc": "EURUSD macro decision memo",
        "runner": "universal",
        "question": "성장, 인플레이션, 중앙은행 경로를 감안할 때 EURUSD 방향성을 의사결정용으로 정리해줘.",
        "ticker": "EURUSD=X",
        "mode_hint": "topic",
        "lookback_days": 60,
        "top_k": 10,
        "min_citations": 1,
    },
    {
        "suite": "topic",
        "category": "Crypto",
        "desc": "BTC macro and flow regime",
        "runner": "universal",
        "question": "유동성, 달러, 위험선호, 온체인 심리를 감안할 때 지금 BTC-USD가 매력적인지 분석해줘.",
        "ticker": "BTC-USD",
        "mode_hint": "topic",
        "lookback_days": 60,
        "top_k": 10,
        "min_citations": 1,
    },
    {
        "suite": "topic",
        "category": "Sector / Theme",
        "desc": "AI semiconductors topic mode",
        "runner": "topic",
        "theme": "AI semiconductors",
        "question": "AI 반도체 섹터의 단기 리스크, 촉매, 실행 전략을 의사결정용으로 정리해줘.",
        "related_tickers": ["NVDA", "AMD", "AVGO", "TSM", "SOXX"],
        "lookback_days": 60,
        "top_k": 12,
        "min_citations": 1,
    },
    {
        "suite": "topic",
        "category": "Macro",
        "desc": "Tickerless macro routing",
        "runner": "universal",
        "question": "미국 금리 경로가 성장주와 장기채에 어떤 영향을 주는지 지금 시점 기준으로 정리해줘.",
        "mode_hint": "auto",
        "lookback_days": 60,
        "top_k": 12,
        "min_citations": 1,
    },
]


def _output_paths(explicit: str | None) -> tuple[Path, Path]:
    primary = Path(explicit) if explicit else DEFAULT_OUTPUT_PATH
    if explicit:
        legacy = primary
    else:
        legacy = LEGACY_OUTPUT_PATH if primary.resolve() != LEGACY_OUTPUT_PATH.resolve() else primary
    return primary, legacy


def _model_used(payload: dict[str, Any], fallback: str = "unknown") -> str:
    execution_meta = payload.get("execution_meta") or {}
    if isinstance(execution_meta, dict):
        for field in ("producing_model", "primary_model"):
            value = str(execution_meta.get(field) or "").strip()
            if value:
                return value
    return fallback


def _sparse_warning(payload: dict[str, Any]) -> bool:
    return has_warning_only_partial(payload) or bool(str(payload.get("uncertainty") or "").strip())


def _topic_minimums(case: dict[str, Any]) -> dict[str, int]:
    return {
        "scenario_analysis": int(case.get("min_scenarios", 2)),
        "execution_strategy": int(case.get("min_execution", 1)),
        "key_drivers": int(case.get("min_drivers", 2)),
        "key_risks": int(case.get("min_risks", 2)),
        "key_metrics": int(case.get("min_metrics", 1)),
        "decision_sections": int(case.get("min_sections", 3)),
    }


def _capture_stream_events() -> tuple[list[dict[str, Any]], Any]:
    started = time.time()
    events: list[dict[str, Any]] = []

    def sink(event: dict[str, Any]) -> None:
        events.append(
            {
                "event": str(event.get("event") or ""),
                "stage": event.get("stage"),
                "phase": event.get("phase"),
                "elapsed_s": round(time.time() - started, 2),
                "payload": event.get("payload"),
            }
        )

    return events, sink


def _topic_latency_snapshot(payload: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    execution_meta = payload.get("execution_meta") or {}
    extras = execution_meta.get("extras") or {}
    partial_event = next((item for item in events if item.get("event") == "partial_result"), None)
    completed_event = next((item for item in events if item.get("event") == "pipeline_completed"), None)
    return {
        "partial_result_s": partial_event.get("elapsed_s") if partial_event else None,
        "final_result_s": completed_event.get("elapsed_s") if completed_event else execution_meta.get("pipeline_latency_s"),
        "stage_timings": extras.get("stage_timings") or {},
        "cache_hit": extras.get("cache_hit"),
        "ingest_skipped_docs": extras.get("ingest_skipped_docs"),
        "retrieval_mode": extras.get("retrieval_mode"),
        "deep_pass_reason": extras.get("deep_pass_reason") or [],
        "deep_pass_skipped": extras.get("deep_pass_skipped"),
        "fast_gate": extras.get("fast_gate"),
        "final_gate": extras.get("final_gate"),
        "evidence_bucket_counts": extras.get("evidence_bucket_counts") or {},
        "missing_evidence_buckets": extras.get("missing_evidence_buckets") or [],
        "substituted_buckets": extras.get("substituted_buckets") or [],
        "metric_as_of_coverage": extras.get("metric_as_of_coverage"),
        "claim_evidence_date_coverage": extras.get("claim_evidence_date_coverage"),
        "quant_snapshot_present": bool(extras.get("quant_snapshot")),
        "event_sequence": [item.get("event") for item in events],
    }


def _analysis_gate(case: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    if str(payload.get("status") or "").lower() == "failed":
        return False, "status=failed"
    if not language_ok(payload):
        return False, "language violation"
    duplicate_ratio = duplicate_paragraph_ratio(payload)
    if duplicate_ratio["total"] >= 4 and not duplicate_ratio["ok"]:
        return False, f"duplicate paragraph ratio too high: {duplicate_ratio['ratio']}"
    metric_coverage = metric_as_of_coverage(payload)
    if metric_coverage["total"] and not metric_coverage["ok"]:
        return False, "metric as_of coverage below 100%"

    richness = decision_richness(payload)
    if case.get("allow_sparse"):
        summary_ok = richness["checks"].get("summary") is True
        conclusion_ok = richness["checks"].get("conclusion") is True
        if not (summary_ok and conclusion_ok):
            return False, "sparse case still needs summary and conclusion"
        if citation_count(payload) < int(case.get("min_citations", 0)) and not _sparse_warning(payload):
            return False, "sparse case missing warning or citation"
        return True, "ok"

    if not richness["ok"]:
        return False, "decision richness below threshold"
    if citation_count(payload) < int(case.get("min_citations", 1)) and not _sparse_warning(payload):
        return False, "missing citation coverage"
    if str(payload.get("status") or "").lower() == "partial" and not has_warning_only_partial(payload):
        return False, "partial response without explicit warning"
    return True, "ok"


def _topic_gate(case: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    if str(payload.get("status") or "").lower() == "failed":
        return False, "status=failed"
    final_gate = topic_final_gate(payload, minimums=_topic_minimums(case))
    if not final_gate["language_ok"]:
        return False, "language violation"
    duplicate_ratio = duplicate_paragraph_ratio(payload)
    if duplicate_ratio["total"] >= 4 and not duplicate_ratio["ok"]:
        return False, f"duplicate paragraph ratio too high: {duplicate_ratio['ratio']}"
    metric_coverage = metric_as_of_coverage(payload)
    if metric_coverage["total"] and not metric_coverage["ok"]:
        return False, "metric as_of coverage below 100%"
    if not claim_evidence_date_coverage(payload)["ok"]:
        return False, "claim evidence date coverage below 100%"
    is_tlt_golden = "rates" in str(case.get("category") or "").lower() or "tlt rate" in str(case.get("desc") or "").lower()
    if is_tlt_golden and not quant_snapshot_present(payload):
        return False, "TLT quant snapshot missing"
    if not partial_reason_is_actionable(payload):
        return False, "partial reason is not actionable"
    if not decision_richness(payload)["ok"]:
        return False, "decision richness below threshold"
    if not final_gate["ok"]:
        return False, f"topic completeness below threshold: {final_gate['completeness']['missing']}"
    if citation_count(payload) < int(case.get("min_citations", 1)) and not _sparse_warning(payload):
        return False, "missing citation coverage"
    if str(payload.get("status") or "").lower() == "partial" and not has_warning_only_partial(payload):
        return False, "partial response without explicit warning"
    return True, "ok"

async def _run_analysis_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    request = AnalysisRequest(
        ticker=case["ticker"],
        question=case["question"],
        lookback_days=case.get("lookback_days", 30),
        top_k=case.get("top_k", 5),
    )
    task_type, horizon = _detect_lens(case["question"])

    try:
        response = await run_pipeline_async(request)
        payload = as_payload_dict(response)
        gate_pass, gate_reason = _analysis_gate(case, payload)
        return {
            "suite": case["suite"],
            "category": case["category"],
            "desc": case["desc"],
            "ticker": case["ticker"],
            "question": case["question"],
            "request_kind": "analysis",
            "mode": detect_mode(payload),
            "status": payload.get("status"),
            "error": payload.get("error_metadata"),
            "summary": payload.get("summary") or "",
            "conclusion": payload.get("conclusion") or "",
            "bull_points": payload.get("bull_points") or [],
            "bear_points": payload.get("bear_points") or [],
            "sentiment": payload.get("sentiment"),
            "confidence": payload.get("confidence"),
            "context_chunks": len(payload.get("raw_context") or []),
            "citation_count": citation_count(payload),
            "evidence_count": evidence_count(payload),
            "language_ok": language_ok(payload),
            "metric_as_of_coverage": metric_as_of_coverage(payload),
            "claim_evidence_date_coverage": claim_evidence_date_coverage(payload),
            "quant_snapshot_present": quant_snapshot_present(payload),
            "decision_richness": decision_richness(payload),
            "quality_metrics": decision_quality_metrics(payload),
            "duplicate_paragraph_ratio": duplicate_paragraph_ratio(payload),
            "purity_ratio": None,
            "raw_context": payload.get("raw_context") or [],
            "elapsed_s": round(time.time() - started, 2),
            "inferred_lens": task_type,
            "inferred_horizon": horizon,
            "model_used": _model_used(payload),
            "gate_pass": gate_pass,
            "gate_reason": gate_reason,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "suite": case["suite"],
            "category": case["category"],
            "desc": case["desc"],
            "ticker": case["ticker"],
            "question": case["question"],
            "request_kind": "analysis",
            "mode": "single_ticker",
            "status": "failed",
            "error": str(exc),
            "summary": "",
            "conclusion": "",
            "bull_points": [],
            "bear_points": [],
            "sentiment": "",
            "confidence": None,
            "context_chunks": 0,
            "citation_count": 0,
            "evidence_count": 0,
            "language_ok": False,
            "metric_as_of_coverage": {"ok": False, "total": 0, "covered": 0, "coverage": 0.0, "missing": []},
            "claim_evidence_date_coverage": {"ok": False, "total": 0, "covered": 0, "coverage": 0.0, "missing": []},
            "quant_snapshot_present": False,
            "decision_richness": {"profile": "analysis", "ok": False, "checks": {}},
            "quality_metrics": {
                "claim_support_rate": 0.0,
                "numeric_grounding_rate": 0.0,
                "evidence_quality_average": 0.0,
                "freshness_coverage": 0.0,
                "stale_context_rate": 0.0,
                "source_diversity": 0,
                "required_bucket_coverage": 0.0,
            },
            "duplicate_paragraph_ratio": {"ok": False, "total": 0, "duplicates": 0, "ratio": 0.0, "examples": []},
            "purity_ratio": None,
            "raw_context": [],
            "elapsed_s": round(time.time() - started, 2),
            "inferred_lens": task_type,
            "inferred_horizon": horizon,
            "model_used": "unknown",
            "gate_pass": False,
            "gate_reason": f"exception: {exc}",
        }


async def _run_topic_case(case: dict[str, Any], *, measure_latency: bool = False) -> dict[str, Any]:
    started = time.time()
    runner = case["runner"]
    events: list[dict[str, Any]] = []
    event_sink = None
    if measure_latency:
        events, event_sink = _capture_stream_events()

    try:
        if runner == "topic":
            response = await run_topic_pipeline_async(
                TopicRequest(
                    question=case["question"],
                    theme=case.get("theme"),
                    related_tickers=list(case.get("related_tickers") or []),
                    lookback_days=case.get("lookback_days", 60),
                    top_k=case.get("top_k", 12),
                ),
                mode=case.get("expected_mode", "sector_macro"),
                event_sink=event_sink,
            )
        elif runner == "universal":
            response = await dispatch_async(
                UniversalRequest(
                    question=case["question"],
                    ticker=case.get("ticker"),
                    mode_hint=case.get("mode_hint", "auto"),
                    lookback_days=case.get("lookback_days", 60),
                    top_k=case.get("top_k", 12),
                ),
                event_sink=event_sink,
            )
        else:
            raise ValueError(f"Unsupported topic runner: {runner}")

        if isinstance(response, CompareResponse):
            raise ValueError("quality review topic suite does not support compare responses")

        payload = as_payload_dict(response)
        gate_pass, gate_reason = _topic_gate(case, payload)
        latency = _topic_latency_snapshot(payload, events) if measure_latency else None
        execution_extras = ((payload.get("execution_meta") or {}).get("extras") or {})
        return {
            "suite": case["suite"],
            "category": case["category"],
            "desc": case["desc"],
            "ticker": case.get("ticker"),
            "question": case["question"],
            "request_kind": runner,
            "mode": detect_mode(payload),
            "status": payload.get("status"),
            "error": payload.get("error_metadata"),
            "warnings": execution_extras.get("warnings") or [],
            "blocking_evidence_buckets": execution_extras.get("blocking_evidence_buckets") or [],
            "warning_evidence_buckets": execution_extras.get("warning_evidence_buckets") or [],
            "recovered_errors": execution_extras.get("recovered_errors") or [],
            "summary": payload.get("executive_summary") or payload.get("summary") or "",
            "conclusion": payload.get("core_thesis") or payload.get("conclusion") or "",
            "sentiment": payload.get("sentiment", "Neutral"),
            "confidence": payload.get("confidence"),
            "context_chunks": len(payload.get("raw_context") or []),
            "citation_count": citation_count(payload),
            "evidence_count": evidence_count(payload),
            "language_ok": language_ok(payload),
            "metric_as_of_coverage": metric_as_of_coverage(payload),
            "claim_evidence_date_coverage": claim_evidence_date_coverage(payload),
            "quant_snapshot_present": quant_snapshot_present(payload),
            "topic_bucket_coverage": topic_bucket_coverage(payload),
            "partial_reason_is_actionable": partial_reason_is_actionable(payload),
            "decision_richness": decision_richness(payload),
            "quality_metrics": decision_quality_metrics(payload),
            "duplicate_paragraph_ratio": duplicate_paragraph_ratio(payload),
            "theme": payload.get("theme") or case.get("theme") or "",
            "raw_context": payload.get("raw_context") or [],
            "elapsed_s": round(time.time() - started, 2),
            "inferred_lens": "topic",
            "inferred_horizon": "multi_horizon",
            "model_used": _model_used(payload),
            "latency": latency,
            "gate_pass": gate_pass,
            "gate_reason": gate_reason,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "suite": case["suite"],
            "category": case["category"],
            "desc": case["desc"],
            "ticker": case.get("ticker"),
            "question": case["question"],
            "request_kind": runner,
            "mode": "concept",
            "status": "failed",
            "error": str(exc),
            "summary": "",
            "conclusion": "",
            "sentiment": "",
            "confidence": None,
            "context_chunks": 0,
            "citation_count": 0,
            "evidence_count": 0,
            "language_ok": False,
            "metric_as_of_coverage": {"ok": False, "total": 0, "covered": 0, "coverage": 0.0, "missing": []},
            "claim_evidence_date_coverage": {"ok": False, "total": 0, "covered": 0, "coverage": 0.0, "missing": []},
            "quant_snapshot_present": False,
            "topic_bucket_coverage": {"counts": {}, "present": [], "substituted": [], "blocking_missing": [], "warning_missing": []},
            "partial_reason_is_actionable": False,
            "decision_richness": {"profile": "topic", "ok": False, "checks": {}},
            "quality_metrics": {
                "claim_support_rate": 0.0,
                "numeric_grounding_rate": 0.0,
                "evidence_quality_average": 0.0,
                "freshness_coverage": 0.0,
                "stale_context_rate": 0.0,
                "source_diversity": 0,
                "required_bucket_coverage": 0.0,
            },
            "duplicate_paragraph_ratio": {"ok": False, "total": 0, "duplicates": 0, "ratio": 0.0, "examples": []},
            "theme": case.get("theme") or "",
            "raw_context": [],
            "elapsed_s": round(time.time() - started, 2),
            "inferred_lens": "topic",
            "inferred_horizon": "multi_horizon",
            "model_used": "unknown",
            "latency": _topic_latency_snapshot({}, events) if measure_latency else None,
            "gate_pass": False,
            "gate_reason": f"exception: {exc}",
        }


def _select_cases(suite: str) -> list[dict[str, Any]]:
    if suite == "analysis":
        return list(ANALYSIS_CASES)
    if suite == "topic":
        return list(TOPIC_CASES)
    return list(ANALYSIS_CASES) + list(TOPIC_CASES)


def _case_key(case: dict[str, Any]) -> str:
    return "::".join(
        [
            str(case.get("suite") or ""),
            str(case.get("category") or ""),
            str(case.get("desc") or ""),
            str(case.get("ticker") or case.get("theme") or ""),
            str(case.get("question") or ""),
        ]
    )


def _case_window(cases: list[dict[str, Any]], *, case_offset: int = 0, case_limit: int | None = None) -> list[dict[str, Any]]:
    offset = max(0, int(case_offset or 0))
    selected = cases[offset:]
    if case_limit is None:
        return selected
    return selected[: max(0, int(case_limit))]


def _load_resume_results(resume_from: str | None) -> list[dict[str, Any]]:
    if not resume_from:
        return []
    path = Path(resume_from)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    cases = payload.get("cases") if isinstance(payload, dict) else None
    return [dict(item) for item in cases if isinstance(item, dict)] if isinstance(cases, list) else []


def _result_key(result: dict[str, Any]) -> str:
    return "::".join(
        [
            str(result.get("suite") or ""),
            str(result.get("category") or ""),
            str(result.get("desc") or ""),
            str(result.get("ticker") or result.get("theme") or ""),
            str(result.get("question") or ""),
        ]
    )


def _write_report(report: dict[str, Any], output_path: str | None) -> None:
    primary_output, legacy_output = _output_paths(output_path)
    primary_output.parent.mkdir(parents=True, exist_ok=True)
    primary_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if legacy_output.resolve() != primary_output.resolve():
        legacy_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_report(
    *,
    suite: str,
    measure_latency: bool,
    preflight: dict[str, Any],
    results: list[dict[str, Any]],
    selected_case_count: int,
    skipped_resume: int,
    partial: bool = False,
) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    suite_counts: dict[str, int] = {}
    gate_failures = 0
    for item in results:
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        key = str(item.get("suite") or "unknown")
        suite_counts[key] = suite_counts.get(key, 0) + 1
        if not item.get("gate_pass"):
            gate_failures += 1

    latency_summary = None
    if measure_latency:
        topic_cases = [item for item in results if item.get("suite") == "topic" and isinstance(item.get("latency"), dict)]
        partial_samples = [float(item["latency"]["partial_result_s"]) for item in topic_cases if item["latency"].get("partial_result_s") is not None]
        final_samples = [float(item["latency"]["final_result_s"]) for item in topic_cases if item["latency"].get("final_result_s") is not None]
        deep_skipped = sum(1 for item in topic_cases if item["latency"].get("deep_pass_skipped"))
        latency_summary = {
            "topic_cases": len(topic_cases),
            "partial_result_samples_s": partial_samples,
            "final_result_samples_s": final_samples,
            "deep_pass_skip_ratio": round(deep_skipped / len(topic_cases), 4) if topic_cases else None,
            "cache_hits": sum(1 for item in topic_cases if item["latency"].get("cache_hit")),
            "retrieval_modes": [item["latency"].get("retrieval_mode") for item in topic_cases],
            "evidence_bucket_coverage": {
                item["desc"]: item["latency"].get("evidence_bucket_counts") or {}
                for item in topic_cases
            },
        }

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "suite": suite,
        "measure_latency": measure_latency,
        "partial": partial,
        "preflight": preflight,
        "summary": {
            "total": len(results),
            "selected_case_count": selected_case_count,
            "skipped_resume": skipped_resume,
            "status_counts": status_counts,
            "suite_counts": suite_counts,
            "gate_failures": gate_failures,
            "gate_passed": gate_failures == 0 and bool(preflight.get("passed")) and not partial,
            "latency": latency_summary,
        },
        "cases": results,
    }


async def run_quality_review(
    suite: str = "all",
    output_path: str | None = None,
    *,
    measure_latency: bool = False,
    case_limit: int | None = None,
    case_offset: int = 0,
    resume_from: str | None = None,
) -> dict[str, Any]:
    suite = (suite or "all").strip().lower()
    if suite not in {"analysis", "topic", "all"}:
        raise ValueError("suite must be one of: analysis, topic, all")

    preflight = run_preflight()
    cases = _case_window(_select_cases(suite), case_offset=case_offset, case_limit=case_limit)
    resume_results = _load_resume_results(resume_from)
    completed_keys = {_result_key(item) for item in resume_results}
    results: list[dict[str, Any]] = list(resume_results)
    skipped_resume = 0

    for case in cases:
        if _case_key(case) in completed_keys:
            skipped_resume += 1
            continue
        print(f"[{case['suite']}] {case['category']} :: {case['desc']}", flush=True)
        if case["suite"] == "analysis":
            result = await _run_analysis_case(case)
        else:
            result = await _run_topic_case(case, measure_latency=measure_latency)
        results.append(result)
        completed_keys.add(_result_key(result))
        tag = str(result["status"]).upper().ljust(7)
        print(
            f"  -> {tag} mode={result['mode']} model={result['model_used']} "
            f"lang={result['language_ok']} gate={result['gate_pass']} elapsed={result['elapsed_s']}s",
            flush=True,
        )
        partial_report = _build_report(
            suite=suite,
            measure_latency=measure_latency,
            preflight=preflight,
            results=results,
            selected_case_count=len(cases),
            skipped_resume=skipped_resume,
            partial=True,
        )
        _write_report(partial_report, output_path)

    report = _build_report(
        suite=suite,
        measure_latency=measure_latency,
        preflight=preflight,
        results=results,
        selected_case_count=len(cases),
        skipped_resume=skipped_resume,
        partial=False,
    )
    _write_report(report, output_path)

    print("\n============================================================", flush=True)
    print("QUALITY REVIEW SUMMARY", flush=True)
    print("============================================================", flush=True)
    print(f"suite: {suite}", flush=True)
    print(f"preflight passed: {preflight['passed']}", flush=True)
    print(f"status counts: {report['summary']['status_counts']}", flush=True)
    print(f"gate failures: {report['summary']['gate_failures']}", flush=True)
    print(f"selected cases: {len(cases)} skipped by resume: {skipped_resume}", flush=True)
    print(f"results: {_output_paths(output_path)[0]}", flush=True)
    print("============================================================", flush=True)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the FinGPT answer-quality review suite.")
    parser.add_argument(
        "--suite",
        default="all",
        choices=["analysis", "topic", "all"],
        help="Which quality suite to run.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Where to save the structured quality review JSON.",
    )
    parser.add_argument(
        "--measure-latency",
        action="store_true",
        help="Capture partial/final stage latency diagnostics for topic cases.",
    )
    parser.add_argument(
        "--case-limit",
        type=int,
        default=None,
        help="Run at most this many selected cases for bounded automation shards.",
    )
    parser.add_argument(
        "--case-offset",
        type=int,
        default=0,
        help="Skip this many selected cases before running the shard.",
    )
    parser.add_argument(
        "--resume-from",
        default=None,
        help="Reuse completed cases from an existing quality review JSON and skip matching cases.",
    )
    return parser.parse_args()


def main() -> int:
    os.environ.setdefault("FINGPT_VALIDATION_FAST_INFERENCE", "1")
    os.environ.setdefault("FINGPT_VALIDATION_INFERENCE_TIMEOUT_S", "30")
    args = _parse_args()
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        report = loop.run_until_complete(
            run_quality_review(
                suite=args.suite,
                output_path=args.output,
                measure_latency=bool(args.measure_latency),
                case_limit=args.case_limit,
                case_offset=args.case_offset,
                resume_from=args.resume_from,
            )
        )
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return 0 if report["summary"]["gate_passed"] else 1


if __name__ == "__main__":
    exit_code = main()
    if os.environ.get("FINGPT_QUALITY_FORCE_EXIT", "1").strip().lower() in {"1", "true", "yes"}:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)
    raise SystemExit(exit_code)
