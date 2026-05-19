from __future__ import annotations

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from core.config.settings import load_settings
from core.schemas.request import _coerce_output_language
from core.schemas.response import CatalystTimeline, Citation, ExecutionMeta, KeyMetric
from core.schemas.retrieval import RetrievalItem
from core.schemas.topic import (
    DecisionSection,
    ExecutionStrategy,
    KeyDriver,
    ScenarioAnalysis,
    TickerTouchpoint,
    TopicRequest,
    TopicResponse,
)
from core.utils.logger import get_logger
from core.utils.model_capabilities import model_capability_dict
from core.utils.validation_metrics import (
    claim_evidence_date_coverage,
    evidence_bucket_policy,
    metric_as_of_coverage,
    topic_fast_gate,
    topic_final_gate,
)
from core.utils.decision_support import enrich_research_response
from core.utils.query_planner import plan_query
from pipelines.analyze.topic_quant import build_topic_quant_snapshot, key_metrics_from_quant_snapshot
from pipelines.analyze.topic_report_builder import build_topic_report
from pipelines.collect.topic_collector import collect_topic_bundle
from pipelines.data_mart.context.structured_context import (
    build_structured_context,
    structured_context_metrics,
    structured_context_to_retrieval_item,
)
from pipelines.infer.topic_prompt import (
    build_evidence_pack,
    build_topic_plan,
    merge_topic_phase_outputs,
    TopicInferencePhaseResult,
    run_topic_deep_inference,
    run_topic_fast_inference,
)
from pipelines.ingest.qdrant_ingestor import ingest_documents
from pipelines.macro.macro_service import get_macro_research_context
from pipelines.macro.research_context import (
    TICKER_RELEVANCE,
    macro_research_context_metrics,
    macro_research_context_to_retrieval_item,
)
from pipelines.output.output_writer import save_outputs
from pipelines.retrieve.topic_retriever import rank_topic_context_fast, retrieve_topic_context

logger = get_logger("pipelines.orchestration.topic")

EventSink = Optional[Callable[[dict[str, Any]], None]]


def _emit(sink: EventSink, event_type: str, **fields: Any) -> None:
    if sink is None:
        return
    try:
        sink({"event": event_type, "ts": time.time(), **fields})
    except Exception:
        pass


def _parent_id(item: RetrievalItem) -> str:
    metadata = item.metadata or {}
    return str(metadata.get("parent_doc_id") or metadata.get("doc_id") or "")


def _clean_as_of(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _context_date_lookup(context: list[RetrievalItem]) -> dict[str, str]:
    by_id: dict[str, str] = {}
    for item in context or []:
        date = _clean_as_of(getattr(item, "date", ""))
        if not date:
            continue
        metadata = item.metadata or {}
        ids = {
            str(metadata.get("doc_id") or "").strip(),
            str(metadata.get("parent_doc_id") or "").strip(),
            _parent_id(item).strip(),
        }
        for doc_id in ids:
            if doc_id and doc_id not in by_id:
                by_id[doc_id] = date
    return by_id


def _evidence_pack_date_lookup(evidence_pack: Any) -> dict[str, str]:
    by_id: dict[str, str] = {}
    for bucket in (getattr(evidence_pack, "buckets", {}) or {}).values():
        for item in getattr(bucket, "items", []) or []:
            date = _clean_as_of(getattr(item, "date", ""))
            doc_id = _parent_id(item)
            if doc_id and date and doc_id not in by_id:
                by_id[doc_id] = date
    return by_id


def _metric_as_of(raw_as_of: Any, evidence_doc_ids: list[str], context: list[RetrievalItem]) -> str:
    explicit = _clean_as_of(raw_as_of)
    if explicit:
        return explicit
    by_id = _context_date_lookup(context)
    for doc_id in evidence_doc_ids or []:
        date = by_id.get(str(doc_id))
        if date:
            return date
    for item in context or []:
        date = _clean_as_of(getattr(item, "date", ""))
        if date:
            return date
    return "unknown"


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9]{2,}|[\uac00-\ud7a3]{2,}", str(text or "").lower())
    return {token for token in tokens if token}


def _context_bucket(item: RetrievalItem) -> str:
    source = str(item.source or "").lower()
    text = f"{item.title} {item.chunk}".lower()
    if source.startswith("fred") or any(term in text for term in ("yield", "inflation", "cpi", "pce", "fed", "real yield", "term premium", "금리", "물가")):
        return "macro"
    if any(term in source for term in ("history", "price", "issuer:")) or any(term in text for term in ("valuation", "curve", "spread", "backwardation", "contango", "price", "밸류", "곡선", "가격")):
        return "market_structure"
    if any(term in source for term in ("news", "google", "transcript")) or any(term in text for term in ("earnings", "guidance", "headline", "news", "실적", "뉴스")):
        return "latest_catalyst"
    return "asset_specific"


def _rebalance_context(primary: list[RetrievalItem], supplemental: list[RetrievalItem], top_k: int) -> list[RetrievalItem]:
    by_parent: dict[str, RetrievalItem] = {}
    for item in [*primary, *supplemental]:
        parent = _parent_id(item) or f"doc-{len(by_parent) + 1}"
        existing = by_parent.get(parent)
        if existing is None or float(item.score or 0.0) > float(existing.score or 0.0):
            by_parent[parent] = item
    combined = sorted(by_parent.values(), key=lambda item: float(item.score or 0.0), reverse=True)

    buckets = {"macro": [], "asset_specific": [], "market_structure": [], "latest_catalyst": []}
    for item in combined:
        buckets[_context_bucket(item)].append(item)

    selected: list[RetrievalItem] = []
    seen: set[str] = set()
    for bucket_name in ("macro", "asset_specific", "market_structure", "latest_catalyst"):
        for item in buckets[bucket_name]:
            parent = _parent_id(item)
            if parent in seen:
                continue
            seen.add(parent)
            selected.append(item)
            break
    for item in combined:
        parent = _parent_id(item)
        if parent in seen:
            continue
        seen.add(parent)
        selected.append(item)
        if len(selected) >= top_k:
            break
    return selected[:top_k]


def _needs_historical_context(question: str, phase: TopicInferencePhaseResult) -> bool:
    text = str(question or "").lower()
    if any(term in text for term in ("historical", "history", "analog", "cycle", "regime", "장기", "과거", "사이클")):
        return True
    if phase.topic_plan.asset_class == "rates_bonds" and len(phase.evidence_pack.buckets["macro"].items) < 2:
        return True
    return False


_TOPIC_MACRO_TERMS = (
    "macro",
    "rate",
    "rates",
    "yield",
    "inflation",
    "fed",
    "liquidity",
    "credit",
    "dollar",
    "gold",
    "oil",
    "duration",
    "cycle",
    "regime",
)


def _topic_macro_context_timeout_s() -> float:
    if os.environ.get("FINGPT_VALIDATION_FAST_INFERENCE", "").strip().lower() in {"1", "true", "yes"}:
        return 5.0
    return 15.0


def _topic_macro_target(request: TopicRequest, theme: str) -> str:
    for ticker in request.related_tickers or []:
        symbol = str(ticker or "").upper().strip()
        if symbol:
            return symbol
    return str(theme or request.question or "GLOBAL").strip()[:32] or "GLOBAL"


def _should_attach_topic_macro_context(request: TopicRequest, mode: str, topic_plan: Any) -> bool:
    text = f"{request.question} {request.theme or ''} {' '.join(request.related_tickers or [])} {getattr(topic_plan, 'asset_class', '')}".lower()
    tickers = {str(ticker or "").upper().strip() for ticker in request.related_tickers or []}
    if tickers & set(TICKER_RELEVANCE):
        return True
    if str(mode or "").lower() == "sector_macro":
        return True
    if any(term in text for term in _TOPIC_MACRO_TERMS):
        return True
    return str(getattr(topic_plan, "asset_class", "") or "") in {"rates_bonds", "credit", "commodity", "fx", "equity_index"}


def _drivers(raw: Any, direction: str) -> list[KeyDriver]:
    out: list[KeyDriver] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            ids = [str(x) for x in (item.get("evidence_doc_ids") or []) if str(x).strip()]
        else:
            text = str(item or "").strip()
            ids = []
        if text:
            out.append(KeyDriver(text=text, direction=direction, evidence_doc_ids=ids))
    return out


def _touchpoints(raw: Any, hints: list[str]) -> list[TickerTouchpoint]:
    out: list[TickerTouchpoint] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper().strip()
            role = str(item.get("role") or "proxy").strip()
            if role not in {"beneficiary", "at_risk", "proxy", "peer"}:
                role = "proxy"
            rationale = str(item.get("rationale") or "").strip()
            if ticker and rationale and ticker not in seen:
                seen.add(ticker)
                out.append(TickerTouchpoint(ticker=ticker, role=role, rationale=rationale))
    for ticker in hints:
        symbol = str(ticker or "").upper().strip()
        if symbol and symbol not in seen:
            seen.add(symbol)
            out.append(TickerTouchpoint(ticker=symbol, role="proxy", rationale="현재 질의를 표현하는 관련 시장 프록시입니다."))
    return out[:8]


def _metrics(raw: Any, context: list[RetrievalItem] | None = None) -> list[KeyMetric]:
    out: list[KeyMetric] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if not name or not value:
            continue
        evidence_doc_ids = [str(x) for x in (item.get("evidence_doc_ids") or []) if str(x).strip()]
        out.append(
            KeyMetric(
                name=name,
                value=value,
                unit=str(item.get("unit") or "").strip(),
                as_of=_metric_as_of(item.get("as_of"), evidence_doc_ids, context or []),
                context=str(item.get("context") or "").strip(),
                source=str(item.get("source") or "").strip(),
                freshness_status=str(item.get("freshness_status") or "unknown").strip() or "unknown",
                evidence_doc_ids=evidence_doc_ids,
            )
        )
    return out


def _merge_quant_metrics(payload: dict[str, Any], quant_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    quant_metrics = key_metrics_from_quant_snapshot(quant_snapshot)
    if not quant_metrics:
        return payload
    existing = payload.get("key_metrics")
    if not isinstance(existing, list):
        existing = []
    seen = {
        str(item.get("name") or "").strip().lower()
        for item in existing
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    merged = list(existing)
    for metric in quant_metrics:
        key = str(metric.get("name") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(metric)
    payload["key_metrics"] = merged
    return payload


def _apply_quant_to_phase(
    phase: TopicInferencePhaseResult,
    quant_snapshot: dict[str, Any] | None,
    *,
    preferred_language: str,
) -> TopicInferencePhaseResult:
    _merge_quant_metrics(phase.payload, quant_snapshot)
    meta = phase.payload.setdefault("_meta", {})
    if isinstance(meta, dict):
        meta["quant_snapshot"] = quant_snapshot or {}
        meta["substituted_buckets"] = list((quant_snapshot or {}).get("substituted_buckets") or [])
    phase.gate = topic_fast_gate(phase.payload, preferred_language=preferred_language)
    phase.final_gate = topic_final_gate(
        phase.payload,
        minimums=phase.topic_plan.minimums,
        preferred_language=preferred_language,
    )
    return phase


def _decision_sections(raw: Any) -> list[DecisionSection]:
    out: list[DecisionSection] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        bullets = [str(x).strip() for x in (item.get("bullets") or []) if str(x).strip()]
        conclusion = str(item.get("conclusion") or "").strip()
        evidence = [str(x).strip() for x in (item.get("evidence_doc_ids") or []) if str(x).strip()]
        if title or bullets or conclusion:
            out.append(DecisionSection(title=title, bullets=bullets, conclusion=conclusion, evidence_doc_ids=evidence))
    return out


def _scenarios(raw: Any) -> list[ScenarioAnalysis]:
    out: list[ScenarioAnalysis] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        scenario = str(item.get("scenario") or "").strip()
        expected = str(item.get("expected_outcome") or "").strip()
        implication = str(item.get("asset_implication") or "").strip()
        decision = str(item.get("decision_read") or "").strip()
        if not any([scenario, expected, implication, decision]):
            continue
        out.append(
            ScenarioAnalysis(
                scenario=scenario,
                probability=str(item.get("probability") or "").strip(),
                expected_outcome=expected,
                asset_implication=implication,
                decision_read=decision,
                evidence_doc_ids=[str(x).strip() for x in (item.get("evidence_doc_ids") or []) if str(x).strip()],
            )
        )
    return out


def _execution_strategies(raw: Any) -> list[ExecutionStrategy]:
    out: list[ExecutionStrategy] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        strategy = str(item.get("strategy") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        trigger = str(item.get("trigger") or "").strip()
        risk_control = str(item.get("risk_control") or "").strip()
        if not any([strategy, rationale, trigger, risk_control]):
            continue
        out.append(
            ExecutionStrategy(
                strategy=strategy,
                trigger=trigger,
                rationale=rationale,
                risk_control=risk_control,
                evidence_doc_ids=[str(x).strip() for x in (item.get("evidence_doc_ids") or []) if str(x).strip()],
            )
        )
    return out


def _timeline(raw: Any) -> CatalystTimeline:
    if not isinstance(raw, dict):
        return CatalystTimeline()
    return CatalystTimeline(
        near_term=[str(x) for x in (raw.get("near_term") or []) if str(x).strip()],
        mid_term=[str(x) for x in (raw.get("mid_term") or []) if str(x).strip()],
        long_term=[str(x) for x in (raw.get("long_term") or []) if str(x).strip()],
    )


def _citations(cited_doc_ids: Any, context: list[RetrievalItem]) -> list[Citation]:
    wanted = [str(x) for x in (cited_doc_ids or []) if str(x).strip()] if isinstance(cited_doc_ids, list) else []
    by_id: dict[str, RetrievalItem] = {}
    for item in context:
        metadata = item.metadata or {}
        if metadata.get("doc_id"):
            by_id[str(metadata["doc_id"])] = item
        if metadata.get("parent_doc_id"):
            by_id[str(metadata["parent_doc_id"])] = item
    ordered = [by_id[doc_id] for doc_id in wanted if doc_id in by_id] or list(context[:4])
    seen: set[tuple[str, str, str]] = set()
    out: list[Citation] = []
    for item in ordered:
        key = (item.source, item.title, item.date)
        if key in seen:
            continue
        seen.add(key)
        out.append(Citation(source=item.source, title=item.title, date=item.date, doc_id=_parent_id(item)))
        if len(out) >= 4:
            break
    return out


def _context_doc_ids(context: list[RetrievalItem], limit: int = 6) -> list[str]:
    ids: list[str] = []
    for item in context:
        doc_id = _parent_id(item)
        if doc_id and doc_id not in ids:
            ids.append(doc_id)
        if len(ids) >= limit:
            break
    return ids


def _first_doc_ids(context: list[RetrievalItem], fallback: list[str] | None = None) -> list[str]:
    ids = _context_doc_ids(context, 3)
    if ids:
        return ids
    return list(fallback or [])


def _fallback_section(title: str, bullets: list[str], conclusion: str, evidence_doc_ids: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "bullets": bullets,
        "conclusion": conclusion,
        "evidence_doc_ids": evidence_doc_ids,
    }


def _fallback_metrics(topic_plan: Any, evidence_pack: Any, evidence_doc_ids: list[str]) -> list[dict[str, Any]]:
    minimum = int(getattr(topic_plan, "minimums", {}).get("key_metrics", 2) or 2)
    metrics: list[dict[str, Any]] = []
    for metric in list(getattr(evidence_pack, "metrics", []) or [])[:minimum]:
        name = str(getattr(metric, "name", "") or "").strip()
        value = str(getattr(metric, "value", "") or "").strip()
        if not name or not value:
            continue
        ids = [str(x) for x in (getattr(metric, "evidence_doc_ids", []) or []) if str(x).strip()]
        metrics.append(
            {
                "name": name,
                "value": value,
                "context": str(getattr(metric, "context", "") or "수집 근거 기반 지표"),
                "evidence_doc_ids": ids or evidence_doc_ids[:1],
            }
        )
    required = list(getattr(topic_plan, "required_metrics", []) or [])
    fallback_names = required or ["핵심 시장 지표", "가격/밸류에이션 신호", "정책/수급 민감도"]
    while len(metrics) < minimum:
        name = fallback_names[len(metrics) % len(fallback_names)]
        metrics.append(
            {
                "name": str(name),
                "value": "수집 문서 기준 정성 확인",
                "context": "정확한 수치는 공급자 데이터가 보강되면 갱신해야 합니다.",
                "evidence_doc_ids": evidence_doc_ids[:1],
            }
        )
    return metrics[: max(minimum, len(metrics))]


def _fallback_related_tickers(related_tickers: list[str], theme: str, asset_class: str) -> list[dict[str, Any]]:
    role = "proxy"
    rationale_by_class = {
        "rates_bonds": "질의의 금리/채권 노출을 대표하는 프록시입니다.",
        "commodity": "질의의 원자재 가격 노출을 대표하는 프록시입니다.",
        "fx": "질의의 환율 노출을 대표하는 프록시입니다.",
        "crypto": "질의의 크립토 유동성 노출을 대표하는 프록시입니다.",
        "sector_theme": "질의의 섹터/테마 노출을 대표하는 프록시입니다.",
        "equity_index": "질의의 지수/ETF 노출을 대표하는 프록시입니다.",
    }
    tickers = [str(ticker or "").upper().strip() for ticker in related_tickers if str(ticker or "").strip()]
    if not tickers and str(theme or "").upper().strip() in {"TLT", "GLD", "BTC-USD", "EURUSD=X"}:
        tickers = [str(theme).upper().strip()]
    return [
        {
            "ticker": ticker,
            "role": role,
            "rationale": rationale_by_class.get(asset_class, "현재 질의를 표현하는 관련 시장 프록시입니다."),
        }
        for ticker in tickers[:8]
    ]


def _local_decision_payload(
    request: TopicRequest,
    *,
    theme: str,
    context: list[RetrievalItem],
    topic_plan: Any,
    evidence_pack: Any,
    error_metadata: str | None,
    language: str,
    phase: str,
) -> dict[str, Any]:
    """Build a grounded fallback memo when the local LLM cannot return valid JSON."""

    if language != "ko":
        return _empty_topic_payload(error_metadata, language)

    asset_class = str(getattr(topic_plan, "asset_class", "") or "sector_theme")
    doc_ids = _first_doc_ids(context, list(getattr(evidence_pack, "cited_doc_ids", []) or []))
    evidence_ids = doc_ids[:3]
    target = (request.related_tickers[0] if request.related_tickers else theme or request.question).strip()
    target_label = target.upper() if target.upper() in {"TLT", "GLD", "BTC-USD", "EURUSD=X"} else target
    uncertainty_prefix = "LLM 구조화 출력이 실패해 로컬 근거 기반 규칙으로 보수적 판단을 생성했습니다."
    uncertainty = f"{uncertainty_prefix} {error_metadata or ''}".strip()

    if asset_class == "rates_bonds":
        executive_summary = (
            f"{target_label}는 장기금리 하락에는 큰 가격 탄력성을 갖지만, 인플레이션 재가속과 국채 공급 부담에는 취약합니다. "
            "현재 판단은 단일 저점 매수보다 중장기 분할 접근이 더 합리적입니다."
        )
        core_thesis = (
            "성장 둔화, 디스인플레이션, Fed 완화 전환 가능성이 커질수록 장기채 기대수익은 개선됩니다. "
            "다만 실질금리와 term premium이 다시 상승하면 듀레이션 손실이 빠르게 확대될 수 있어 진입 속도 조절이 핵심입니다."
        )
        asset_overview = [
            _fallback_section(
                "대상 자산 개요",
                [
                    f"{target_label}는 장기 미국 국채 가격에 민감한 채권 ETF/프록시로 해석해야 합니다.",
                    "듀레이션이 길어 금리 1%p 변화가 가격에 크게 반영되는 구조입니다.",
                    "따라서 배당/이자 캐리보다 금리 방향과 실질금리 변화가 핵심 수익 동인입니다.",
                ],
                "장기채 반등을 노리는 자산이지만 단기 금리 변동성에는 매우 취약합니다.",
                evidence_ids,
            )
        ]
        macro_regime = [
            _fallback_section(
                "거시경제 국면",
                [
                    "성장이 둔화되고 물가 압력이 완화될수록 장기금리 하락 여지가 커집니다.",
                    "Fed가 긴축 종료에서 완화 전환으로 이동한다면 장기채에는 우호적입니다.",
                    "반대로 고용과 소비가 강하게 버티면 금리 인하 기대가 뒤로 밀릴 수 있습니다.",
                ],
                "현재 매력도는 침체 확정보다 금리 피크아웃 가능성에 더 크게 의존합니다.",
                evidence_ids,
            )
        ]
        rate_structure = [
            _fallback_section(
                "금리 구조와 가격 민감도",
                [
                    "장단기 곡선, 실질금리, term premium은 TLT의 방향성을 나누는 핵심 축입니다.",
                    "장기금리가 높은 구간에서는 향후 하락 시 가격 상승 잠재력이 커지지만, 추가 상승 시 손실도 비대칭적으로 커집니다.",
                    "국채 발행 증가와 기간 프리미엄 상승은 장기금리 하락을 늦추는 구조적 부담입니다.",
                ],
                "금리 하락 베팅의 기대값은 존재하지만, 금리 재상승 리스크를 반드시 가격에 반영해야 합니다.",
                evidence_ids,
            )
        ]
        investment_judgment = [
            _fallback_section(
                "투자 판단",
                [
                    "확실한 저점이라고 단정하기보다 중장기 기대값이 개선된 구간으로 보는 것이 적절합니다.",
                    "금리 상승 여지는 제한적이고 금리 하락 여지가 더 크다는 판단이 맞다면 보상 대비 위험이 개선됩니다.",
                    "단기 트레이딩은 변동성이 크므로 CPI, FOMC, 장기금리 추세 확인이 필요합니다.",
                ],
                "결론은 '중장기 분할 매수는 검토 가능, 단기 일괄 진입은 보수적'입니다.",
                evidence_ids,
            )
        ]
        scenario_analysis = [
            {
                "scenario": "경기 둔화와 금리 인하",
                "probability": "중간 이상",
                "expected_outcome": "성장 둔화와 물가 완화가 확인되며 장기금리가 하락합니다.",
                "asset_implication": f"{target_label} 가격에는 가장 우호적이며 듀레이션 효과로 상승 탄력이 커질 수 있습니다.",
                "decision_read": "분할 매수 또는 기존 포지션 유지가 유리한 시나리오입니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "연착륙과 금리 박스권",
                "probability": "중간",
                "expected_outcome": "경기는 버티고 인플레이션은 천천히 둔화되어 장기금리가 박스권에 머뭅니다.",
                "asset_implication": f"{target_label}는 큰 추세 상승보다 캐리와 제한적 가격 반등 중심이 됩니다.",
                "decision_read": "추격 매수보다 가격 조정 시 분할 접근이 낫습니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "인플레이션 재가속과 term premium 상승",
                "probability": "낮지만 중요",
                "expected_outcome": "물가 또는 국채 수급 부담으로 장기금리가 다시 상승합니다.",
                "asset_implication": f"{target_label}는 장기 듀레이션 때문에 큰 하락 압력을 받을 수 있습니다.",
                "decision_read": "손절 기준, 헤지, 현금 비중을 사전에 정해야 하는 리스크 시나리오입니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        execution_strategy = [
            {
                "strategy": "분할 매수",
                "trigger": "장기금리 급등이 진정되거나 CPI/FOMC 이후 금리 피크아웃 신호가 확인될 때",
                "rationale": "TLT는 듀레이션이 길어 타이밍 오류의 손실이 크므로 평균 단가를 분산하는 편이 합리적입니다.",
                "risk_control": "장기금리 재상승 구간에서는 매수 속도를 줄이고 포지션 한도를 고정합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "strategy": "확인 후 진입 또는 헤지 병행",
                "trigger": "실질금리 하락, yield curve 정상화, Fed 완화 가이던스가 동시에 개선될 때",
                "rationale": "금리 방향성이 확인되면 장기채 가격 반등의 신뢰도가 높아집니다.",
                "risk_control": "인플레이션 재가속 또는 국채 입찰 부진 시 포지션을 축소합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        key_drivers = [
            {"text": "디스인플레이션 진전과 Fed 완화 전환 기대", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "성장 둔화 시 안전자산 수요와 장기금리 하락 가능성", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "인플레이션 재가속으로 장기금리가 다시 상승하는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "재정적자와 국채 공급 확대에 따른 term premium 상승", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]
    else:
        executive_summary = (
            f"{target_label}에 대한 현재 판단은 근거가 충분한 축과 부족한 축을 분리해 보수적으로 해석해야 합니다. "
            "가격 방향은 거시 환경, 수급, 최근 촉매가 같은 방향으로 정렬되는지에 달려 있습니다."
        )
        core_thesis = (
            "투자 매력도는 단일 뉴스보다 성장/정책 환경, 가격 구조, 수급 촉매가 동시에 개선되는지로 판단해야 합니다. "
            "근거가 빈 축은 확신이 아니라 체크리스트로 남겨야 합니다."
        )
        asset_overview = [
            _fallback_section(
                "대상 자산 개요",
                [
                    f"{target_label}는 현재 질의의 핵심 시장 노출을 대표하는 분석 대상입니다.",
                    "가격 민감도는 자산군별 핵심 변수와 최근 촉매의 조합으로 판단해야 합니다.",
                ],
                "단순 방향성보다 어떤 변수에 민감한지 먼저 확인해야 합니다.",
                evidence_ids,
            )
        ]
        macro_regime = [
            _fallback_section(
                "거시 환경",
                [
                    "성장, 인플레이션, 정책금리, 달러 유동성은 대부분의 위험자산과 대체자산에 공통으로 작용합니다.",
                    "위험선호가 살아나면 가격 모멘텀이 개선되고, 긴축 부담이 커지면 밸류에이션 압력이 커집니다.",
                ],
                "거시 환경은 중립에서 조건부 우호로 해석하되, 확인 지표가 필요합니다.",
                evidence_ids,
            )
        ]
        rate_structure = [
            _fallback_section(
                "가격/시장 구조",
                [
                    "가격 추세, 밸류에이션, 수급, 포지셔닝이 같은 방향으로 움직일 때 신뢰도가 높아집니다.",
                    "근거가 부족한 시장 구조 축은 과도한 확신을 낮추는 요인입니다.",
                ],
                "시장 구조 확인 전에는 일괄 진입보다 단계적 접근이 적절합니다.",
                evidence_ids,
            )
        ]
        investment_judgment = [
            _fallback_section(
                "투자 판단",
                [
                    "상방 동인과 하방 리스크가 모두 존재하므로 현재는 조건부 매력 구간으로 보는 것이 합리적입니다.",
                    "핵심 촉매가 확인될 때 비중을 늘리고, 반대 신호가 나오면 현금/헤지로 방어해야 합니다.",
                ],
                "실행은 분할 접근과 사전 리스크 한도를 전제로 해야 합니다.",
                evidence_ids,
            )
        ]
        scenario_analysis = [
            {
                "scenario": "우호적 거시와 수급 개선",
                "probability": "중간",
                "expected_outcome": "정책/수급/가격 모멘텀이 같은 방향으로 개선됩니다.",
                "asset_implication": f"{target_label}의 상승 여력이 커질 수 있습니다.",
                "decision_read": "분할 진입 또는 기존 비중 유지가 가능한 구간입니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "박스권과 촉매 부재",
                "probability": "중간",
                "expected_outcome": "핵심 지표가 엇갈리며 가격이 제한된 범위에서 움직입니다.",
                "asset_implication": f"{target_label}는 추세보다 변동성 관리가 중요해집니다.",
                "decision_read": "추격보다 눌림목과 확인 신호를 기다리는 전략이 유리합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "리스크 오프 또는 정책 충격",
                "probability": "낮지만 중요",
                "expected_outcome": "긴축, 달러 강세, 수급 악화가 동시에 나타납니다.",
                "asset_implication": f"{target_label}에는 하방 압력이 커질 수 있습니다.",
                "decision_read": "비중 축소, 손절 기준, 헤지 여부를 먼저 정해야 합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        execution_strategy = [
            {
                "strategy": "분할 접근",
                "trigger": "핵심 지표와 가격 추세가 동시에 개선될 때",
                "rationale": "근거가 일부 부족할 때는 단일 진입보다 평균 단가와 판단 시간을 분산하는 편이 낫습니다.",
                "risk_control": "반대 지표가 확인되면 추가 매수를 중단하고 포지션 크기를 제한합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "strategy": "촉매 확인 후 비중 확대",
                "trigger": "수급, 정책, 가격 구조 중 최소 두 축이 같은 방향으로 확인될 때",
                "rationale": "의사결정 확률을 높이려면 뉴스보다 구조적 확인 신호가 필요합니다.",
                "risk_control": "확인 신호가 사라지면 현금 비중 또는 헤지로 전환합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        key_drivers = [
            {"text": "거시 환경과 유동성 개선", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "가격 구조 또는 수급 촉매 개선", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "정책/금리/달러 환경이 불리하게 바뀌는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "근거가 빈 축에서 뒤늦게 부정적 데이터가 확인되는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]

    return {
        "mode": "concept",
        "theme": theme,
        "executive_summary": executive_summary,
        "core_thesis": core_thesis,
        "asset_overview": asset_overview,
        "macro_regime": macro_regime,
        "rate_structure": rate_structure,
        "scenario_analysis": scenario_analysis,
        "investment_judgment": investment_judgment,
        "execution_strategy": execution_strategy,
        "key_drivers": key_drivers,
        "key_risks": key_risks,
        "related_tickers": _fallback_related_tickers(request.related_tickers, theme, asset_class),
        "key_metrics": _fallback_metrics(topic_plan, evidence_pack, evidence_ids),
        "catalyst_timeline": {
            "near_term": ["CPI, 고용, 국채 입찰, 주요 정책 발언 확인"],
            "mid_term": ["FOMC 경로, 실질금리 추세, 가격 추세 확인"],
            "long_term": ["성장 둔화 지속 여부와 구조적 수급 부담 재평가"],
        },
        "open_questions": [
            "현재 수집 근거에서 비어 있는 데이터 축은 무엇인가?",
            "다음 CPI/FOMC 이후 금리와 가격 추세가 같은 방향으로 움직이는가?",
        ],
        "uncertainty": uncertainty,
        "cited_doc_ids": evidence_ids,
        "_meta": {
            "phase": phase,
            "primary_model": str(request.model),
            "producing_model": "local-deterministic-fallback",
            "retry_count": 0,
            "total_latency_s": 0.0,
            "prompt_char_count": 0,
            "chunks_used": len(evidence_ids),
            "asset_class": asset_class,
            "evidence_bucket_counts": {
                name: len(getattr(bucket, "items", []) or [])
                for name, bucket in (getattr(evidence_pack, "buckets", {}) or {}).items()
            },
            "missing_evidence_buckets": list(getattr(evidence_pack, "missing_buckets", []) or []),
            "coverage_notes": list(getattr(evidence_pack, "coverage_notes", []) or []),
            "missing_evidence_reasons": [],
            "fallback_reason": error_metadata,
        },
    }


def _empty_topic_payload(error_metadata: str | None, language: str) -> dict[str, Any]:
    if language == "ko":
        return {
            "executive_summary": "현재 실행에서는 투자 판단에 필요한 최신 근거가 충분하지 않아 보수적으로 해석해야 합니다.",
            "core_thesis": "현 시점에는 근거 기반의 주제 투자 가설을 충분히 구성할 수 없습니다.",
            "asset_overview": [],
            "macro_regime": [],
            "rate_structure": [],
            "scenario_analysis": [],
            "investment_judgment": [],
            "execution_strategy": [],
            "key_drivers": [],
            "key_risks": [],
            "related_tickers": [],
            "key_metrics": [],
            "catalyst_timeline": {},
            "open_questions": ["lookback 기간 또는 데이터 공급 상태를 확인한 뒤 다시 실행할 필요가 있습니다."],
            "uncertainty": error_metadata or "현재 실행에서 사용할 수 있는 주제 근거 문서가 부족합니다.",
            "cited_doc_ids": [],
        }
    return {
        "executive_summary": "Insufficient grounded context was retrieved to answer confidently.",
        "core_thesis": "No evidence-backed topic thesis can be formed from the current run.",
        "asset_overview": [],
        "macro_regime": [],
        "rate_structure": [],
        "scenario_analysis": [],
        "investment_judgment": [],
        "execution_strategy": [],
        "key_drivers": [],
        "key_risks": [],
        "related_tickers": [],
        "key_metrics": [],
        "catalyst_timeline": {},
        "open_questions": ["Re-run with a broader lookback or configured data providers."],
        "uncertainty": error_metadata or "Missing current-run topic context.",
        "cited_doc_ids": [],
    }


def _dedupe_messages(values: list[str | None]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _bucket_gap_message(prefix: str, buckets: list[str]) -> str | None:
    cleaned = [bucket.replace("_", " ") for bucket in buckets if str(bucket).strip()]
    if not cleaned:
        return None
    return f"{prefix}: " + ", ".join(cleaned)


def _final_topic_status(
    *,
    final_gate: dict[str, Any],
    blocking_errors: list[str],
    blocking_buckets: list[str],
    warning_buckets: list[str],
    recovered_errors: list[str],
) -> tuple[str, str | None, list[str]]:
    warnings = _dedupe_messages([_bucket_gap_message("경고 근거 버킷 부족", warning_buckets)])
    errors = _dedupe_messages(
        [
            *blocking_errors,
            _bucket_gap_message("필수 근거 버킷 부족", blocking_buckets),
            None if final_gate.get("ok") else "최종 topic 품질 기준을 충족하지 못했습니다.",
        ]
    )
    if errors:
        return "partial", " | ".join(errors), warnings
    return "success", None, warnings


def _sanitize_success_uncertainty(payload: dict[str, Any], *, warning_buckets: list[str], recovered_errors: list[str]) -> None:
    if not recovered_errors:
        return
    text = str(payload.get("uncertainty") or "").strip()
    for recovered in recovered_errors:
        text = text.replace(recovered, "")
    text = text.replace("LLM 구조화 출력이 실패해 로컬 근거 기반 규칙으로 보수적 판단을 생성했습니다.", "")
    text = " ".join(text.split()).strip()
    if warning_buckets:
        payload["uncertainty"] = "일부 최신 촉매 근거가 제한적이므로 CPI, FOMC, 국채 입찰과 장기금리 반응을 확인하며 판단을 갱신해야 합니다."
    else:
        payload["uncertainty"] = text


def _response_from_payload(
    request: TopicRequest,
    *,
    theme: str,
    mode: str,
    status: str,
    error_metadata: str | None,
    payload: dict[str, Any],
    context: list[RetrievalItem],
    execution_meta: ExecutionMeta,
) -> TopicResponse:
    response = TopicResponse(
        question=request.question,
        theme=theme,
        mode="sector_macro" if mode == "sector_macro" else "concept",
        status=status,
        error_metadata=error_metadata,
        executive_summary=str(payload.get("executive_summary") or ""),
        core_thesis=str(payload.get("core_thesis") or ""),
        asset_overview=_decision_sections(payload.get("asset_overview")),
        macro_regime=_decision_sections(payload.get("macro_regime")),
        rate_structure=_decision_sections(payload.get("rate_structure")),
        scenario_analysis=_scenarios(payload.get("scenario_analysis")),
        investment_judgment=_decision_sections(payload.get("investment_judgment")),
        execution_strategy=_execution_strategies(payload.get("execution_strategy")),
        key_drivers=_drivers(payload.get("key_drivers"), "supporting"),
        key_risks=_drivers(payload.get("key_risks"), "opposing"),
        related_tickers=_touchpoints(payload.get("related_tickers"), request.related_tickers),
        key_metrics=_metrics(payload.get("key_metrics"), context),
        catalyst_timeline=_timeline(payload.get("catalyst_timeline")),
        open_questions=[str(x) for x in (payload.get("open_questions") or []) if str(x).strip()],
        uncertainty=str(payload.get("uncertainty") or ""),
        citations=_citations(payload.get("cited_doc_ids"), context),
        raw_context=context,
        execution_meta=execution_meta,
    )
    if response.execution_meta is None:
        response.execution_meta = ExecutionMeta()
    if "retrieval_plan" not in response.execution_meta.extras:
        ticker_hint = request.related_tickers[0] if request.related_tickers else ""
        response.execution_meta.extras["retrieval_plan"] = plan_query(ticker_hint, request.question, mode_hint="topic").model_dump(mode="json")
    return enrich_research_response(response)


def _fallback_metrics(topic_plan: Any, evidence_pack: Any, evidence_doc_ids: list[str]) -> list[dict[str, Any]]:
    minimum = int(getattr(topic_plan, "minimums", {}).get("key_metrics", 2) or 2)
    metrics: list[dict[str, Any]] = []
    for metric in list(getattr(evidence_pack, "metrics", []) or [])[:minimum]:
        name = str(getattr(metric, "name", "") or "").strip()
        value = str(getattr(metric, "value", "") or "").strip()
        if not name or not value:
            continue
        ids = [str(x) for x in (getattr(metric, "evidence_doc_ids", []) or []) if str(x).strip()]
        metrics.append(
            {
                "name": name,
                "value": value,
                "unit": str(getattr(metric, "unit", "") or ""),
                "context": str(getattr(metric, "context", "") or "수집 근거 기반 핵심 지표입니다."),
                "source": str(getattr(metric, "source", "") or "evidence_pack"),
                "freshness_status": "unknown",
                "evidence_doc_ids": ids or evidence_doc_ids[:1],
            }
        )

    required = list(getattr(topic_plan, "required_metrics", []) or [])
    fallback_names = required or ["핵심 시장 지표", "가격/밸류에이션 신호", "정책/수급 민감도"]
    while len(metrics) < minimum:
        name = fallback_names[len(metrics) % len(fallback_names)]
        metrics.append(
            {
                "name": str(name),
                "value": "수집 문서 기준 정성 확인",
                "unit": "",
                "context": "정확한 수치 공급자가 없으면 근거 축으로만 표시합니다.",
                "source": "deterministic_fallback",
                "freshness_status": "unknown",
                "evidence_doc_ids": evidence_doc_ids[:1],
            }
        )
    return metrics[: max(minimum, len(metrics))]


def _fallback_related_tickers(related_tickers: list[str], theme: str, asset_class: str) -> list[dict[str, Any]]:
    rationale_by_class = {
        "rates_bonds": "질의의 금리/채권 노출을 대표하는 시장 프록시입니다.",
        "credit": "질의의 신용 리스크 노출을 대표하는 시장 프록시입니다.",
        "commodity": "질의의 원자재 가격 노출을 대표하는 시장 프록시입니다.",
        "fx": "질의의 환율 노출을 대표하는 시장 프록시입니다.",
        "crypto": "질의의 디지털자산 유동성 노출을 대표하는 시장 프록시입니다.",
        "sector_theme": "질의의 섹터/테마 노출을 대표하는 시장 프록시입니다.",
        "equity_index": "질의의 지수/ETF 노출을 대표하는 시장 프록시입니다.",
    }
    tickers = [str(ticker or "").upper().strip() for ticker in related_tickers if str(ticker or "").strip()]
    if not tickers and str(theme or "").upper().strip() in {"TLT", "GLD", "BTC-USD", "EURUSD=X", "HYG", "LQD"}:
        tickers = [str(theme).upper().strip()]
    return [
        {
            "ticker": ticker,
            "role": "proxy",
            "rationale": rationale_by_class.get(asset_class, "현재 질의를 표현하는 관련 시장 프록시입니다."),
        }
        for ticker in tickers[:8]
    ]


def _local_decision_payload(
    request: TopicRequest,
    *,
    theme: str,
    context: list[RetrievalItem],
    topic_plan: Any,
    evidence_pack: Any,
    error_metadata: str | None,
    language: str,
    phase: str,
) -> dict[str, Any]:
    """Clean Korean deterministic fallback when local LLM JSON is invalid."""

    if language != "ko":
        return _empty_topic_payload(error_metadata, language)

    asset_class = str(getattr(topic_plan, "asset_class", "") or "sector_theme")
    doc_ids = _first_doc_ids(context, list(getattr(evidence_pack, "cited_doc_ids", []) or []))
    evidence_ids = doc_ids[:3]
    target = (request.related_tickers[0] if request.related_tickers else theme or request.question).strip()
    target_label = target.upper() if target.upper() in {"TLT", "GLD", "BTC-USD", "EURUSD=X", "HYG", "LQD"} else target
    uncertainty = (
        "LLM 구조화 출력이 실패해 로컬 정량/근거 기반 규칙으로 보수적 판단을 생성했습니다. "
        f"{error_metadata or ''}"
    ).strip()

    if asset_class == "rates_bonds":
        executive_summary = (
            f"{target_label}는 장기금리 하락 시 가격 상승 여력이 있지만, 인플레이션 재가속과 국채 공급 부담에는 취약합니다. "
            "현재 판단은 단기 저점 확정보다 중장기 분할 접근이 더 적합합니다."
        )
        core_thesis = (
            "성장 둔화, 디스인플레이션, Fed 완화 전환 가능성이 커질수록 장기채 기대수익은 개선됩니다. "
            "반대로 실질금리와 term premium이 다시 상승하면 duration 손실이 빠르게 커질 수 있습니다."
        )
        asset_overview = [
            _fallback_section(
                "대상 자산 개요",
                [
                    f"{target_label}는 장기 미국 국채 가격에 민감한 채권 ETF/프록시로 해석해야 합니다.",
                    "duration이 길어 금리 1%p 변화가 가격에 크게 반영되는 구조입니다.",
                    "배당/이자 캐리보다 장기금리 방향과 실질금리 변화가 핵심 수익 동인입니다.",
                ],
                "장기채 반등은 가능한 구간이지만 단기 금리 변동성에는 취약합니다.",
                evidence_ids,
            )
        ]
        macro_regime = [
            _fallback_section(
                "거시경제 구간",
                [
                    "성장이 둔화되고 물가 압력이 완화될수록 장기금리 하락 여지가 커집니다.",
                    "Fed가 긴축 종료에서 완화 전환으로 이동하면 장기채에는 우호적입니다.",
                    "반대로 고용과 소비가 강하게 버티면 금리 인하 기대가 뒤로 밀릴 수 있습니다.",
                ],
                "현재 매력도는 침체 확정보다 금리 피크아웃 가능성에 더 크게 의존합니다.",
                evidence_ids,
            )
        ]
        rate_structure = [
            _fallback_section(
                "금리 구조와 가격 민감도",
                [
                    "장단기 곡선, 실질금리, term premium은 TLT 방향성을 나누는 핵심 축입니다.",
                    "장기금리가 높은 구간에서는 향후 금리 하락 시 가격 상승 잠재력이 커집니다.",
                    "국채 발행 증가와 term premium 상승은 장기금리 하락을 방해하는 구조적 부담입니다.",
                ],
                "금리 하락 베팅의 기대값은 존재하지만 금리 재상승 리스크를 반드시 가격에 반영해야 합니다.",
                evidence_ids,
            )
        ]
        investment_judgment = [
            _fallback_section(
                "투자 판단",
                [
                    "확실한 저점보다 중장기 기대값이 개선된 구간으로 보는 것이 적절합니다.",
                    "금리 상승 여지가 제한적이고 하락 여지가 크다는 판단이면 보상 대비 위험이 개선됩니다.",
                    "단기 트레이딩은 CPI, FOMC, 장기금리 추세 확인이 필요합니다.",
                ],
                "중장기 분할 매수 검토 가능, 단기 일괄 진입은 보수적입니다.",
                evidence_ids,
            )
        ]
        scenario_analysis = [
            {
                "scenario": "경기 둔화와 금리 인하",
                "probability": "중간 이상",
                "expected_outcome": "성장 둔화와 물가 완화가 확인되며 장기금리가 하락합니다.",
                "asset_implication": f"{target_label} 가격에는 가장 우호적이며 duration 효과로 상승 압력이 커질 수 있습니다.",
                "decision_read": "분할 매수 또는 기존 포지션 유지가 유리한 시나리오입니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "연착륙과 금리 박스권",
                "probability": "중간",
                "expected_outcome": "경기가 버티고 인플레이션이 천천히 둔화되며 장기금리가 박스권에 머뭅니다.",
                "asset_implication": f"{target_label}는 추세 상승보다 캐리와 제한적 반등 중심의 수익이 됩니다.",
                "decision_read": "추격 매수보다 가격 조정 시 분할 접근이 낫습니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "인플레이션 재가속과 term premium 상승",
                "probability": "낮지만 중요",
                "expected_outcome": "물가 또는 국채 수급 부담으로 장기금리가 다시 상승합니다.",
                "asset_implication": f"{target_label}는 긴 duration 때문에 하락 압력을 받을 수 있습니다.",
                "decision_read": "손절 기준, 헷지, 현금 비중을 사전에 정해야 하는 리스크 시나리오입니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        execution_strategy = [
            {
                "strategy": "분할 매수",
                "trigger": "장기금리 급등이 진정되거나 CPI/FOMC 이후 금리 피크아웃 신호가 확인될 때",
                "rationale": "duration 자산은 진입 시점 오류의 손실이 크므로 평균 단가를 분산하는 편이 합리적입니다.",
                "risk_control": "장기금리 재상승 구간에서는 매수 속도를 줄이고 포지션 한도를 고정합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "strategy": "확인 후 진입 또는 헷지 병행",
                "trigger": "실질금리 하락, yield curve 정상화, Fed 완화 가이던스가 동시에 개선될 때",
                "rationale": "금리 방향성이 확인되면 장기채 가격 반등의 신뢰도가 높아집니다.",
                "risk_control": "인플레이션 재가속 또는 국채 입찰 부진 시 포지션을 축소합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        key_drivers = [
            {"text": "디스인플레이션 진전과 Fed 완화 전환 기대", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "성장 둔화 시 안전자산 수요와 장기금리 하락 가능성", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "인플레이션 재가속으로 장기금리가 다시 상승하는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "재정적자와 국채 공급 부담에 따른 term premium 상승", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]
    else:
        executive_summary = (
            f"{target_label}에 대한 현재 판단은 확인된 근거와 부족한 근거를 분리해 보수적으로 해석해야 합니다. "
            "가격 방향은 거시 환경, 수급, 시장 구조, 최신 촉매가 같은 방향으로 정렬되는지에 달려 있습니다."
        )
        core_thesis = (
            "투자 매력도는 단일 뉴스보다 성장/정책 환경, 가격 구조, 수급 촉매가 동시에 개선되는지로 판단해야 합니다. "
            "근거가 빈 축은 확신이 아니라 체크리스트로 남깁니다."
        )
        asset_overview = [
            _fallback_section(
                "대상 자산/주제 개요",
                [
                    f"{target_label}는 현재 질의를 대표하는 시장 노출 또는 주제 프록시입니다.",
                    "가격 민감도는 자산군별 핵심 변수와 최근 촉매의 조합으로 판단해야 합니다.",
                ],
                "단순 방향성보다 어떤 변수에 민감한지 먼저 확인해야 합니다.",
                evidence_ids,
            )
        ]
        macro_regime = [
            _fallback_section(
                "거시 환경",
                [
                    "성장, 인플레이션, 정책금리, 달러 유동성은 대부분의 위험자산과 대체자산에 공통으로 작용합니다.",
                    "위험선호가 개선되면 가격 모멘텀이 좋아지고, 긴축 부담이 커지면 밸류에이션 압력이 커집니다.",
                ],
                "거시 환경은 중립에서 조건부 우호로 해석하되 확인 지표가 필요합니다.",
                evidence_ids,
            )
        ]
        rate_structure = [
            _fallback_section(
                "가격/시장 구조",
                [
                    "가격 추세, 밸류에이션, 수급, 포지셔닝이 같은 방향으로 움직일 때 신뢰도가 높아집니다.",
                    "근거가 부족한 시장 구조 추정은 과도한 확신보다 보수적 해석이 필요합니다.",
                ],
                "시장 구조 확인 전에는 일괄 진입보다 단계적 접근이 적절합니다.",
                evidence_ids,
            )
        ]
        investment_judgment = [
            _fallback_section(
                "투자 판단",
                [
                    "상방 동인과 하방 리스크가 모두 존재하므로 현재는 조건부 매력 구간으로 봅니다.",
                    "핵심 촉매가 확인되면 비중을 늘리고 반대 신호가 나오면 현금/헷지로 방어해야 합니다.",
                ],
                "실행은 분할 접근과 사전 리스크 한도를 전제로 해야 합니다.",
                evidence_ids,
            )
        ]
        scenario_analysis = [
            {
                "scenario": "우호적 거시와 수급 개선",
                "probability": "중간",
                "expected_outcome": "정책, 수급, 가격 모멘텀이 같은 방향으로 개선됩니다.",
                "asset_implication": f"{target_label}는 상승 여력이 커질 수 있습니다.",
                "decision_read": "분할 진입 또는 기존 비중 유지가 가능한 구간입니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "박스권과 촉매 부족",
                "probability": "중간",
                "expected_outcome": "핵심 지표가 엇갈리며 가격이 제한된 범위에서 움직입니다.",
                "asset_implication": f"{target_label}는 추세보다 변동성 관리가 중요해집니다.",
                "decision_read": "추격보다 눌림목과 확인 신호를 기다리는 전략이 유리합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "scenario": "리스크 오프 또는 정책 충격",
                "probability": "낮지만 중요",
                "expected_outcome": "긴축, 달러 강세, 수급 악화가 동시에 나타납니다.",
                "asset_implication": f"{target_label}에는 하방 압력이 커질 수 있습니다.",
                "decision_read": "비중 축소, 손절 기준, 헷지 여부를 먼저 정해야 합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        execution_strategy = [
            {
                "strategy": "분할 접근",
                "trigger": "핵심 지표와 가격 추세가 동시에 개선될 때",
                "rationale": "근거가 일부 부족한 구간에서는 일괄 진입보다 판단 시간을 분산하는 편이 낫습니다.",
                "risk_control": "반대 지표가 확인되면 추가 매수를 중단하고 포지션 크기를 제한합니다.",
                "evidence_doc_ids": evidence_ids,
            },
            {
                "strategy": "촉매 확인 후 비중 확대",
                "trigger": "수급, 정책, 가격 구조 중 최소 두 축이 같은 방향으로 확인될 때",
                "rationale": "의사결정 확률을 높이려면 뉴스보다 구조적 확인 신호가 필요합니다.",
                "risk_control": "확인 신호가 사라지면 현금 비중 또는 헷지로 전환합니다.",
                "evidence_doc_ids": evidence_ids,
            },
        ]
        key_drivers = [
            {"text": "거시 환경과 유동성 개선", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "가격 구조 또는 수급 촉매 개선", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "정책, 금리, 달러 환경이 불리하게 바뀌는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "근거가 빈 축에서 뒤늦게 부정적 데이터가 확인되는 위험", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]

    return {
        "mode": "concept",
        "theme": theme,
        "executive_summary": executive_summary,
        "core_thesis": core_thesis,
        "asset_overview": asset_overview,
        "macro_regime": macro_regime,
        "rate_structure": rate_structure,
        "scenario_analysis": scenario_analysis,
        "investment_judgment": investment_judgment,
        "execution_strategy": execution_strategy,
        "key_drivers": key_drivers,
        "key_risks": key_risks,
        "related_tickers": _fallback_related_tickers(request.related_tickers, theme, asset_class),
        "key_metrics": _fallback_metrics(topic_plan, evidence_pack, evidence_ids),
        "catalyst_timeline": {
            "near_term": ["CPI, 고용, 주요 정책 발언, 가격 추세 확인"],
            "mid_term": ["FOMC 경로, 실질금리 추세, 수급 변화 확인"],
            "long_term": ["성장 둔화 지속 여부와 구조적 수급 부담 재평가"],
        },
        "open_questions": [
            "현재 수집 근거에서 비어 있는 데이터 축은 무엇인가?",
            "다음 주요 매크로/정책 이벤트 이후 가격과 핵심 지표가 같은 방향으로 움직이는가?",
        ],
        "uncertainty": uncertainty,
        "cited_doc_ids": evidence_ids,
        "_meta": {
            "phase": phase,
            "primary_model": str(request.model),
            "producing_model": "local-deterministic-fallback",
            "retry_count": 0,
            "total_latency_s": 0.0,
            "prompt_char_count": 0,
            "chunks_used": len(evidence_ids),
            "asset_class": asset_class,
            "evidence_bucket_counts": {
                name: len(getattr(bucket, "items", []) or [])
                for name, bucket in (getattr(evidence_pack, "buckets", {}) or {}).items()
            },
            "missing_evidence_buckets": list(getattr(evidence_pack, "missing_buckets", []) or []),
            "coverage_notes": list(getattr(evidence_pack, "coverage_notes", []) or []),
            "missing_evidence_reasons": [],
            "fallback_reason": error_metadata,
        },
    }


def _empty_topic_payload(error_metadata: str | None, language: str) -> dict[str, Any]:
    if language == "ko":
        return {
            "executive_summary": "현재 실행에서는 투자 판단에 필요한 최신 근거가 충분하지 않아 보수적으로 해석해야 합니다.",
            "core_thesis": "이 시점에는 근거 기반 주제 투자 가설을 충분히 구성할 수 없습니다.",
            "asset_overview": [],
            "macro_regime": [],
            "rate_structure": [],
            "scenario_analysis": [],
            "investment_judgment": [],
            "execution_strategy": [],
            "key_drivers": [],
            "key_risks": [],
            "related_tickers": [],
            "key_metrics": [],
            "catalyst_timeline": {},
            "open_questions": ["lookback 기간 또는 데이터 공급자 상태를 확인한 뒤 다시 실행해야 합니다."],
            "uncertainty": error_metadata or "현재 실행에서 사용할 수 있는 주제 근거 문서가 부족합니다.",
            "cited_doc_ids": [],
        }
    return {
        "executive_summary": "Insufficient grounded context was retrieved to answer confidently.",
        "core_thesis": "No evidence-backed topic thesis can be formed from the current run.",
        "asset_overview": [],
        "macro_regime": [],
        "rate_structure": [],
        "scenario_analysis": [],
        "investment_judgment": [],
        "execution_strategy": [],
        "key_drivers": [],
        "key_risks": [],
        "related_tickers": [],
        "key_metrics": [],
        "catalyst_timeline": {},
        "open_questions": ["Re-run with a broader lookback or configured data providers."],
        "uncertainty": error_metadata or "Missing current-run topic context.",
        "cited_doc_ids": [],
    }


def _final_topic_status(
    *,
    final_gate: dict[str, Any],
    blocking_errors: list[str],
    blocking_buckets: list[str],
    warning_buckets: list[str],
    recovered_errors: list[str],
) -> tuple[str, str | None, list[str]]:
    warnings = _dedupe_messages([_bucket_gap_message("경고성 근거 버킷 부족", warning_buckets)])
    errors = _dedupe_messages(
        [
            *blocking_errors,
            _bucket_gap_message("필수 근거 버킷 부족", blocking_buckets),
            None if final_gate.get("ok") else "최종 topic 품질 기준을 충분히 충족하지 못했습니다.",
        ]
    )
    if errors:
        return "partial", " | ".join(errors), warnings
    return "success", None, warnings


def _sanitize_success_uncertainty(payload: dict[str, Any], *, warning_buckets: list[str], recovered_errors: list[str]) -> None:
    if not recovered_errors and not warning_buckets:
        return
    text = str(payload.get("uncertainty") or "").strip()
    for recovered in recovered_errors:
        text = text.replace(recovered, "")
    text = text.replace("LLM 구조화 출력이 실패해 로컬 정량/근거 기반 규칙으로 보수적 판단을 생성했습니다.", "")
    text = " ".join(text.split()).strip()
    if warning_buckets:
        payload["uncertainty"] = "일부 최신 촉매 근거가 제한적이므로, 다음 정책/물가/수급 이벤트 이후 판단을 갱신해야 합니다."
    else:
        payload["uncertainty"] = text


def _classify_error_type(message: str | None, *, status: str = "") -> str:
    text = str(message or "").lower()
    if not text and status != "partial":
        return ""
    if any(term in text for term in ("validation", "ticker", "필수", "invalid")):
        return "validation_error"
    if any(term in text for term in ("json", "parse", "truncated", "unclosed", "schema", "구조화")):
        return "model_json_error"
    if any(term in text for term in ("language", "korean", "언어")):
        return "model_language_error"
    if any(term in text for term in ("entitlement", "permission", "403")):
        return "provider_entitlement"
    if any(term in text for term in ("qdrant", "ollama", "timeout", "unreachable", "connection")):
        return "infrastructure_error"
    if any(term in text for term in ("missing", "bucket", "evidence", "context", "근거", "부족")):
        return "evidence_sparse"
    if any(term in text for term in ("data", "source", "provider", "no documents")):
        return "data_unavailable"
    return "unknown_error" if text or status == "partial" else ""


def _provider_statuses(collection: Any) -> list[dict[str, Any]]:
    rows = list(getattr(collection, "provider_results", []) or getattr(collection, "source_results", []) or [])
    out: list[dict[str, Any]] = []
    for row in rows:
        status = str(getattr(row, "status", "unknown") or "unknown")
        entitlement_status = "entitlement_required" if "entitlement" in str(getattr(row, "detail", "")).lower() or status == "entitlement_required" else ("ok" if status == "ok" else "warning")
        out.append(
            {
                "provider": str(getattr(row, "source", "") or "unknown"),
                "status": status,
                "entitlement_status": entitlement_status,
                "latency_ms": round(float(getattr(row, "elapsed_s", 0.0) or 0.0) * 1000, 2),
                "cache_hit": bool(getattr(collection, "cache_hit", False)),
                "stale_after": str(getattr(collection, "freshness_cutoff", "") or ""),
                "quality_score": 1.0 if status == "ok" else (0.5 if status in {"empty", "entitlement_required"} else 0.0),
                "detail": str(getattr(row, "detail", "") or ""),
            }
        )
    return out


def _data_freshness(context: list[RetrievalItem]) -> dict[str, Any]:
    audits: list[dict[str, Any]] = []
    for item in context:
        doc_id = _parent_id(item)
        date = _clean_as_of(getattr(item, "date", "")) or "unknown"
        audits.append(
            {
                "as_of": date,
                "freshness_status": "unknown" if date == "unknown" else "fresh",
                "source": str(getattr(item, "source", "") or ""),
                "evidence_doc_ids": [doc_id] if doc_id else [],
                "missing_reason": "" if date != "unknown" else "document date unavailable",
            }
        )
    unknown = len([item for item in audits if item["as_of"] == "unknown"])
    return {
        "items": audits,
        "total": len(audits),
        "unknown": unknown,
        "coverage": 1.0 if not audits else round((len(audits) - unknown) / len(audits), 4),
    }


def _run_manifest(request: TopicRequest, *, asset_class: str, target: str, collection: Any, final_gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_kind": "topic",
        "route": "universal_topic",
        "asset_class": asset_class,
        "target": target,
        "question_hash": hashlib.sha1(
            request.question.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:12],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": [str(getattr(row, "source", "")) for row in (getattr(collection, "source_results", []) or [])],
        "model_route": str(request.model),
        "validation_checks": {
            "final_gate_ok": bool(final_gate.get("ok")),
            "language_ok": bool(final_gate.get("language_ok")),
        },
    }


def _section(title: str, bullets: list[str], conclusion: str, evidence_doc_ids: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "bullets": bullets,
        "conclusion": conclusion,
        "evidence_doc_ids": evidence_doc_ids,
    }


def _local_asset_class(asset_class: str, question: str, theme: str, related_tickers: list[str]) -> str:
    text = f"{question} {theme} {' '.join(related_tickers)}".lower()
    upper = text.upper()
    if any(term in text for term in ("credit", "spread", "default", "신용", "크레딧", "회사채", "하이일드", "부도")) or any(t in upper for t in ("HYG", "LQD")):
        return "credit"
    if any(term in text for term in ("금리", "채권", "국채", "duration", "yield", "treasury")) or "TLT" in upper:
        return "rates_bonds"
    return str(asset_class or "sector_theme")


def _local_decision_payload(
    request: TopicRequest,
    *,
    theme: str,
    context: list[RetrievalItem],
    topic_plan: Any,
    evidence_pack: Any,
    error_metadata: str | None,
    language: str,
    phase: str,
) -> dict[str, Any]:
    """Deterministic Korean decision memo used when local LLM JSON is unusable."""

    if language != "ko":
        return _empty_topic_payload(error_metadata, language)

    planned_asset_class = str(getattr(topic_plan, "asset_class", "") or "sector_theme")
    asset_class = _local_asset_class(planned_asset_class, request.question, theme, list(request.related_tickers or []))
    doc_ids = _first_doc_ids(context, list(getattr(evidence_pack, "cited_doc_ids", []) or []))
    evidence_ids = doc_ids[:3]
    default_related = {
        "credit": ["HYG", "LQD", "TLT", "SPY"],
        "rates_bonds": ["TLT", "IEF", "SHY", "AGG"],
        "commodity": ["GLD", "USO", "DXY"],
        "fx": ["EURUSD=X", "DXY"],
        "crypto": ["BTC-USD", "ETH-USD"],
    }.get(asset_class, [])
    related_tickers = list(request.related_tickers or default_related)
    target = (related_tickers[0] if related_tickers else theme or request.question).strip()
    target_label = target.upper() if target else "TOPIC"
    fallback_reason = error_metadata or "local structured generation fallback"
    uncertainty = (
        "LLM 구조화 출력이 불안정해 로컬 정량/근거 규칙으로 보수적 판단을 생성했습니다. "
        "아래 판단은 수집 문서와 quant snapshot에 근거하며, 근거가 빈 축은 확신도를 낮춰 해석해야 합니다. "
        f"원인: {fallback_reason}"
    )

    if asset_class == "credit":
        executive_summary = (
            "현재 신용 리스크는 단일 뉴스보다 HYG/LQD 가격, 금리 듀레이션, 주식시장 위험선호, 유동성 조건을 함께 봐야 합니다. "
            "하이일드가 SPY 대비 약하거나 LQD가 TLT와 함께 흔들리면 단순 금리 문제가 아니라 spread와 유동성 압력이 동시에 커지는 신호입니다."
        )
        core_thesis = (
            "신용위험은 침체 확정 전에 가격과 유동성 지표에서 먼저 나타납니다. "
            "고금리 지속, refinancing 부담, 은행/상업용 부동산 노출, 하이일드 스프레드 확대가 겹치면 equity drawdown보다 먼저 credit beta가 악화될 수 있습니다."
        )
        asset_overview = [_section("신용 리스크 프록시", [
            "HYG는 하이일드 신용 스프레드와 위험선호를, LQD는 투자등급 회사채의 금리·스프레드 혼합 노출을 대표합니다.",
            "TLT/IEF는 금리 충격과 duration 부담을 분리해 보는 보조 프록시입니다.",
            "SPY 대비 HYG/LQD의 상대 성과는 equity-credit divergence를 점검하는 빠른 신호입니다.",
        ], "신용 리스크는 스프레드, 금리, 유동성을 분리해서 봐야 하며 한 지표만으로 결론을 내리면 안 됩니다.", evidence_ids)]
        macro_regime = [_section("거시·유동성 환경", [
            "정책금리가 오래 높게 유지되면 기업 refinancing 비용이 상승하고 취약 차주의 부도 민감도가 커집니다.",
            "성장 둔화가 확인되면 매출/현금흐름 하방이 spread widening으로 전이될 수 있습니다.",
            "달러 유동성 경색이나 은행 대출태도 악화는 신용시장 가격 변동을 증폭시킵니다.",
        ], "현재는 성장 둔화와 고금리 지속 가능성을 동시에 점검해야 하는 구간입니다.", evidence_ids)]
        rate_structure = [_section("가격·스프레드 구조", [
            "HYG 약세가 LQD 약세보다 크면 default-risk premium이 반영되는 신호로 봅니다.",
            "LQD와 TLT가 함께 하락하면 신용보다 금리/duration 부담이 더 큰 국면일 수 있습니다.",
            "HYG와 SPY가 동시에 약세면 위험자산 전반의 deleveraging 가능성을 우선 점검합니다.",
        ], "신용 리스크 판단은 절대 가격보다 HYG/LQD/TLT/SPY의 상대 움직임이 더 유용합니다.", evidence_ids)]
        investment_judgment = [_section("투자 판단", [
            "신용 프록시가 안정적이면 equity risk premium의 급격한 재가격 가능성은 낮아집니다.",
            "반대로 HYG가 선행 약세를 보이면 주식시장이 아직 반영하지 않은 funding stress를 의심해야 합니다.",
            "확인 전에는 고베타/레버리지 노출을 늘리기보다 방어적 포지션과 현금 여력을 우선합니다.",
        ], "확실한 방향성보다 stress가 어디서 가격화되는지 확인하는 단계가 우선입니다.", evidence_ids)]
        scenario_analysis = [
            {"scenario": "연착륙과 스프레드 안정", "probability": "중간", "expected_outcome": "성장은 둔화되지만 default cycle은 제한되고 HYG/LQD가 안정됩니다.", "asset_implication": "위험자산에는 중립~우호적이며 credit risk premium 재확대 가능성은 제한됩니다.", "decision_read": "고품질 risk asset 위주로 선택적 노출 유지가 가능합니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "refinancing stress와 spread widening", "probability": "중간", "expected_outcome": "고금리 장기화로 취약 차주의 조달비용이 상승하고 HYG가 선행 약세를 보입니다.", "asset_implication": "주식시장이 뒤늦게 하방을 반영할 가능성이 커집니다.", "decision_read": "레버리지/소형주/취약 업종 노출을 줄이고 hedge를 우선합니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "유동성 충격", "probability": "낮지만 중요", "expected_outcome": "은행/상업용 부동산/달러 유동성 충격이 동시에 발생해 credit beta가 급격히 악화됩니다.", "asset_implication": "HYG, SPY 동반 약세와 안전자산 선호가 나타날 수 있습니다.", "decision_read": "현금, 단기채, 방어적 hedge가 우선이며 dip-buy는 확인 후 접근합니다.", "evidence_doc_ids": evidence_ids},
        ]
        execution_strategy = [
            {"strategy": "credit dashboard 확인 후 단계적 대응", "trigger": "HYG/LQD 상대 약세, SPY 동반 약세, 금리 급등 또는 유동성 뉴스가 동시에 확인될 때", "rationale": "신용 리스크는 단일 이벤트보다 지표 동조화가 중요합니다.", "risk_control": "확인 전 공격적 매수보다 현금과 hedge 여력을 유지합니다.", "evidence_doc_ids": evidence_ids},
            {"strategy": "방어적 노출 전환", "trigger": "하이일드 약세가 지속되고 경기 지표가 둔화될 때", "rationale": "spread widening은 equity drawdown보다 먼저 나타날 수 있습니다.", "risk_control": "레버리지/저품질 balance sheet 노출을 줄이고 quality factor를 높입니다.", "evidence_doc_ids": evidence_ids},
        ]
        key_drivers = [
            {"text": "스프레드 안정과 위험선호 회복은 신용 리스크 재가격을 늦출 수 있습니다.", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "금리 하락이 성장 충격 없이 진행되면 LQD/HYG에는 완충 요인이 됩니다.", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "고금리 장기화로 refinancing 비용이 상승하면 취약 차주 default risk가 커집니다.", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "HYG와 SPY 동반 약세는 시장이 놓친 유동성 스트레스 신호일 수 있습니다.", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "은행/상업용 부동산 관련 손실 뉴스는 credit risk premium을 빠르게 확대시킬 수 있습니다.", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]
    elif asset_class == "rates_bonds":
        executive_summary = (
            f"{target_label}는 장기금리 하락에는 큰 가격 탄력성을 갖지만 인플레이션 재가속, term premium 상승, 국채 공급 부담에는 취약합니다. "
            "단기 저점 확정보다 금리 경로와 duration 손실 한도를 정한 분할 접근이 더 적합합니다."
        )
        core_thesis = "성장 둔화와 디스인플레이션이 이어질수록 장기채 기대수익은 개선되지만, 실질금리와 term premium이 재상승하면 가격 손실이 빠르게 확대됩니다."
        asset_overview = [_section("대상 자산 개요", [f"{target_label}는 장기 미국 국채 가격에 민감한 채권 ETF/프록시입니다.", "duration이 길어 금리 50~100bp 변화에도 가격 민감도가 큽니다.", "캐리보다 장기금리 방향성이 총수익을 좌우합니다."], "장기채는 금리 하락 베팅에는 유리하지만 진입 타이밍 리스크가 큽니다.", evidence_ids)]
        macro_regime = [_section("거시 환경", ["성장 둔화와 물가 둔화는 장기금리 하락 요인입니다.", "Fed 완화 전환 기대가 커지면 duration 자산에는 우호적입니다.", "고용/소비가 강하면 금리 인하 기대가 지연될 수 있습니다."], "현재 판단은 경기 둔화와 인플레이션 재가속 가능성을 같이 보는 구조입니다.", evidence_ids)]
        rate_structure = [_section("금리 구조", ["10Y/30Y 금리 수준, 10Y-2Y 곡선, 실질금리 proxy가 핵심입니다.", "국채 발행과 term premium 상승은 장기금리 하락을 막는 부담입니다.", "금리 하락 여지가 상승 여지보다 크다고 판단될 때 기대값이 개선됩니다."], "duration shock table과 yield curve를 함께 확인해야 합니다.", evidence_ids)]
        investment_judgment = [_section("투자 판단", ["확실한 저점보다 중장기 기대값 관점의 분할 접근이 합리적입니다.", "인플레이션 재가속 시 손절/헤지 기준이 필요합니다.", "CPI/FOMC/국채 입찰 전후로 진입 속도를 조절해야 합니다."], "중장기 금리 하락 베팅은 유효하나 단기 트레이딩은 위험합니다.", evidence_ids)]
        scenario_analysis = [
            {"scenario": "성장 둔화와 금리 인하", "probability": "중간 이상", "expected_outcome": "장기금리 하락과 안전자산 수요가 동시에 나타납니다.", "asset_implication": f"{target_label} 가격에는 우호적입니다.", "decision_read": "분할 매수 또는 기존 포지션 유지가 유리합니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "연착륙과 금리 박스권", "probability": "중간", "expected_outcome": "금리 하락이 제한되고 carry 중심 수익에 머무릅니다.", "asset_implication": "상승 여력은 제한적입니다.", "decision_read": "추격보다 조정 시 접근이 낫습니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "인플레이션 재가속", "probability": "낮지만 중요", "expected_outcome": "장기금리와 term premium이 재상승합니다.", "asset_implication": f"{target_label}는 duration 손실을 받을 수 있습니다.", "decision_read": "손절/헤지 기준을 먼저 정해야 합니다.", "evidence_doc_ids": evidence_ids},
        ]
        execution_strategy = [
            {"strategy": "분할 매수", "trigger": "장기금리 급등 후 안정 또는 CPI/FOMC 이후 금리 피크아웃 신호", "rationale": "duration 자산은 진입 시점 오차가 손실로 크게 반영됩니다.", "risk_control": "금리 재상승 구간에서는 매수 속도를 낮춥니다.", "evidence_doc_ids": evidence_ids},
            {"strategy": "금리 피크 확인 후 진입", "trigger": "실질금리 하락, curve 정상화, Fed 완화 가이던스가 함께 확인될 때", "rationale": "방향성 확인 후 진입하면 drawdown 리스크가 줄어듭니다.", "risk_control": "인플레이션 재가속 또는 공급 부담 확대 시 포지션을 축소합니다.", "evidence_doc_ids": evidence_ids},
        ]
        key_drivers = [
            {"text": "디스인플레이션과 Fed 완화 전환 기대는 장기채 가격을 지지합니다.", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "경기 둔화와 안전자산 수요는 장기금리 하락 가능성을 높입니다.", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "인플레이션 재가속은 장기금리 재상승과 duration 손실로 연결됩니다.", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "재정적자와 국채 공급 증가는 term premium 상승 압력입니다.", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]
    else:
        executive_summary = (
            f"{target_label}에 대한 판단은 가격 추세, 거시 환경, 수급/시장구조, 최신 촉매가 같은 방향으로 정렬되는지에 달려 있습니다. "
            "근거가 부족한 축은 partial로 표시하고 확신도를 낮춰야 합니다."
        )
        core_thesis = "투자 매력도는 단일 서사가 아니라 정량 지표와 근거 문서가 같은 방향을 가리킬 때 높아집니다."
        asset_overview = [_section("대상/주제 개요", [f"{target_label}는 현재 질의를 대표하는 시장 노출 또는 주제입니다.", "가격 민감도는 관련 자산군 핵심 변수와 최신 촉매의 조합으로 판단합니다."], "먼저 어떤 변수에 민감한지 식별해야 합니다.", evidence_ids)]
        macro_regime = [_section("거시/정책 환경", ["성장, 물가, 정책금리, 달러 유동성은 대부분의 위험자산과 대체자산에 공통으로 작용합니다.", "위험선호 개선은 모멘텀을 지지하고 긴축 부담은 valuation 압력을 키웁니다."], "거시 환경은 중립에서 조건부 우호로 해석하되 확인 지표가 필요합니다.", evidence_ids)]
        rate_structure = [_section("가격/시장 구조", ["가격 추세, 수급, 포지셔닝, valuation을 함께 봐야 합니다.", "근거가 부족한 구조 추정은 확신보다 체크리스트로 남겨야 합니다."], "시장 구조 확인 전에는 단계적 접근이 적절합니다.", evidence_ids)]
        investment_judgment = [_section("투자 판단", ["상방 동인과 하방 리스크가 모두 존재하므로 현재는 조건부 매력 구간으로 봅니다.", "핵심 촉매가 확인되면 비중 확대, 반대 신호가 나오면 방어가 우선입니다."], "실행은 분할 접근과 사전 리스크 한도를 전제로 합니다.", evidence_ids)]
        scenario_analysis = [
            {"scenario": "우호적 거시와 수급 개선", "probability": "중간", "expected_outcome": "정책, 유동성, 가격 모멘텀이 같은 방향으로 개선됩니다.", "asset_implication": "상승 여력이 커집니다.", "decision_read": "분할 진입 또는 기존 비중 유지가 가능합니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "박스권과 촉매 부족", "probability": "중간", "expected_outcome": "핵심 지표가 엇갈리며 가격은 제한적 범위에서 움직입니다.", "asset_implication": "기대수익은 낮고 타이밍 의존도가 커집니다.", "decision_read": "추격보다 확인 후 접근이 낫습니다.", "evidence_doc_ids": evidence_ids},
            {"scenario": "리스크 오프 또는 정책 충격", "probability": "낮지만 중요", "expected_outcome": "긴축, 달러 강세, 수급 악화가 동시에 나타납니다.", "asset_implication": "하방 압력이 커질 수 있습니다.", "decision_read": "비중 축소와 hedge 기준을 먼저 정해야 합니다.", "evidence_doc_ids": evidence_ids},
        ]
        execution_strategy = [
            {"strategy": "분할 접근", "trigger": "정량 지표와 근거 문서가 같은 방향으로 개선될 때", "rationale": "근거가 완전하지 않은 topic에서는 진입 시점 리스크를 분산해야 합니다.", "risk_control": "핵심 지표가 반대로 움직이면 추가 진입을 중단합니다.", "evidence_doc_ids": evidence_ids},
            {"strategy": "촉매 확인 후 비중 조절", "trigger": "정책/실적/수급 이벤트가 가격과 함께 확인될 때", "rationale": "서사보다 검증 가능한 촉매가 가격 재평가를 만듭니다.", "risk_control": "근거 공백이 남으면 partial 판단으로 유지합니다.", "evidence_doc_ids": evidence_ids},
        ]
        key_drivers = [
            {"text": "가격 모멘텀과 수급 촉매가 같은 방향으로 개선되는 경우", "direction": "supporting", "evidence_doc_ids": evidence_ids},
            {"text": "거시/정책 환경이 위험자산에 우호적으로 전환되는 경우", "direction": "supporting", "evidence_doc_ids": evidence_ids},
        ]
        key_risks = [
            {"text": "정책금리, 달러 유동성, 성장 둔화가 동시에 악화되는 경우", "direction": "opposing", "evidence_doc_ids": evidence_ids},
            {"text": "근거가 빈 축에서 부정적 데이터가 뒤늦게 확인되는 경우", "direction": "opposing", "evidence_doc_ids": evidence_ids},
        ]

    return {
        "mode": "concept",
        "theme": theme,
        "executive_summary": executive_summary,
        "core_thesis": core_thesis,
        "asset_overview": asset_overview,
        "macro_regime": macro_regime,
        "rate_structure": rate_structure,
        "scenario_analysis": scenario_analysis,
        "investment_judgment": investment_judgment,
        "execution_strategy": execution_strategy,
        "key_drivers": key_drivers,
        "key_risks": key_risks,
        "related_tickers": _fallback_related_tickers(related_tickers, theme, asset_class),
        "key_metrics": _fallback_metrics(topic_plan, evidence_pack, evidence_ids),
        "catalyst_timeline": {
            "near_term": ["핵심 가격 프록시, 정책/거시 지표, 최신 뉴스 촉매 확인"],
            "mid_term": ["수급, valuation, spread 또는 금리 구조 변화 확인"],
            "long_term": ["성장/정책 regime 전환과 구조적 리스크 재평가"],
        },
        "open_questions": [
            "현재 수집 근거에서 비어 있는 데이터 축은 무엇인가?",
            "다음 주요 지표 발표 이후 가격 프록시와 핵심 지표가 같은 방향으로 움직이는가?",
        ],
        "uncertainty": uncertainty,
        "cited_doc_ids": evidence_ids,
        "_meta": {
            "phase": phase,
            "primary_model": str(request.model),
            "producing_model": "local-deterministic-fallback",
            "retry_count": 0,
            "total_latency_s": 0.0,
            "prompt_char_count": 0,
            "chunks_used": len(evidence_ids),
            "asset_class": asset_class,
            "evidence_bucket_counts": {
                name: len(getattr(bucket, "items", []) or [])
                for name, bucket in (getattr(evidence_pack, "buckets", {}) or {}).items()
            },
            "missing_evidence_buckets": list(getattr(evidence_pack, "missing_buckets", []) or []),
            "coverage_notes": list(getattr(evidence_pack, "coverage_notes", []) or []),
            "missing_evidence_reasons": [],
            "fallback_reason": fallback_reason,
        },
    }


def _deterministic_fast_path_reason(
    request: TopicRequest,
    topic_plan: Any,
    quant_snapshot: dict[str, Any] | None,
) -> str:
    """Return a reason when a topic can be answered without a slow JSON LLM call."""

    plan_asset = str(getattr(topic_plan, "asset_class", "") or "").strip()
    quant_asset = str((quant_snapshot or {}).get("asset_class") or "").strip()
    metrics = (quant_snapshot or {}).get("metrics") or []
    if not metrics:
        return ""
    source_status = (quant_snapshot or {}).get("source_status") or {}
    missing_axes = (quant_snapshot or {}).get("missing_axes") or source_status.get("missing_axes") or []
    try:
        metric_count = int(source_status.get("metric_count") or len(metrics))
    except (TypeError, ValueError):
        metric_count = len(metrics)
    tickers = {str(ticker or "").upper().strip() for ticker in (request.related_tickers or [])}
    text = f"{request.question} {request.theme or ''} {' '.join(tickers)}".lower()
    credit_terms = ("credit", "spread", "default", "high yield", "신용", "크레딧", "회사채", "하이일드", "부도")
    credit_terms = ("credit", "spread", "default", "high yield", "신용", "크레딧", "회사채", "하이일드", "부도")
    if "credit" in {plan_asset, quant_asset} and ((tickers & {"HYG", "LQD"}) or any(term in text for term in credit_terms)):
        return "deterministic_credit_fast_path"
    supported_assets = {
        "rates_bonds",
        "commodity",
        "fx",
        "crypto",
        "sector_theme",
        "equity_index",
    }
    selected_asset = quant_asset if quant_asset in supported_assets else plan_asset
    if selected_asset == "rates_bonds":
        has_fred = bool(source_status.get("has_fred_metrics"))
        has_price = bool(source_status.get("has_price_metrics"))
        has_duration = any("duration" in str(metric.get("name") or "").lower() for metric in metrics if isinstance(metric, dict))
        has_quant_substitute = metric_count >= 6 and has_price and (has_fred or has_duration)
        if metric_count < 5 or (len(missing_axes) > 1 and not has_quant_substitute):
            return ""
    if selected_asset == "commodity" and "GLD" in tickers and metric_count >= 2:
        return "deterministic_commodity_fast_path"
    if selected_asset == "commodity" and metric_count < 2:
        return ""
    if selected_asset in {"fx", "crypto", "sector_theme", "equity_index"} and metric_count < 2:
        return ""
    if selected_asset in supported_assets:
        return f"deterministic_{selected_asset}_fast_path"
    return ""


async def run_topic_pipeline_async(
    request: TopicRequest,
    mode: str = "concept",
    *,
    event_sink: EventSink = None,
) -> TopicResponse:
    settings = load_settings()
    language = _coerce_output_language(getattr(request, "output_language", None) or getattr(settings, "output_language", "ko"))
    started = time.time()
    theme = (request.theme or request.question).strip()
    status = "success"
    error_metadata: str | None = None
    blocking_errors: list[str] = []
    recovered_errors: list[str] = []
    stage_timings: dict[str, float] = {}
    fast_context: list[RetrievalItem] = []
    final_context: list[RetrievalItem] = []
    ingest_stats: dict[str, Any] | None = None
    deep_pass_reason: list[str] = []
    deep_pass_skipped = True
    retrieval_mode = "fast_current_documents"
    macro_context: dict[str, Any] | None = None
    macro_context_error = ""
    macro_metric_dicts: list[dict[str, Any]] = []

    _emit(
        event_sink,
        "pipeline_started",
        ticker=request.related_tickers[0] if request.related_tickers else "TOPIC",
        question=request.question,
        model=request.model,
        mode=mode,
    )

    collect_started = time.time()
    _emit(event_sink, "stage_started", stage="collect")
    collection = await asyncio.to_thread(
        collect_topic_bundle,
        request.question,
        theme,
        request.related_tickers,
        request.lookback_days,
    )
    stage_timings["collect"] = round(time.time() - collect_started, 2)
    _emit(
        event_sink,
        "stage_completed",
        stage="collect",
        duration_s=stage_timings["collect"],
        documents=len(collection.documents),
        cache_hit=bool(getattr(collection, "cache_hit", False)),
        cache_age_s=float(getattr(collection, "cache_age_s", 0.0) or 0.0),
    )
    if not collection.documents:
        status = "partial"
        message = collection.summary_detail or "No topic documents collected."
        blocking_errors.append(message)
        error_metadata = error_metadata or message

    retrieve_started = time.time()
    _emit(event_sink, "stage_started", stage="retrieve")
    fast_context = await asyncio.to_thread(
        rank_topic_context_fast,
        collection.documents,
        request.question,
        theme,
        request.related_tickers,
        request.top_k,
    )
    stage_timings["retrieve_fast"] = round(time.time() - retrieve_started, 2)
    _emit(
        event_sink,
        "stage_completed",
        stage="retrieve",
        duration_s=stage_timings["retrieve_fast"],
        chunks=len(fast_context),
        retrieval_mode="fast_current_documents",
    )
    if not fast_context:
        status = "partial"
        message = "No current-run topic context available."
        blocking_errors.append(message)
        error_metadata = error_metadata or message

    preliminary_plan = build_topic_plan(request.question, theme, request.related_tickers, fast_context)
    quant_snapshot = build_topic_quant_snapshot(
        preliminary_plan.asset_class,
        theme,
        request.related_tickers,
        fast_context,
    )
    structured_context = await asyncio.to_thread(
        build_structured_context,
        request.related_tickers[0] if request.related_tickers else theme,
        related_tickers=request.related_tickers,
    )
    structured_item = structured_context_to_retrieval_item(structured_context)
    if structured_item is not None:
        fast_context.append(structured_item)
        quant_snapshot.setdefault("metrics", [])
        quant_snapshot["metrics"].extend(structured_context_metrics(structured_context))
        quant_snapshot["structured_context"] = structured_context

    if _should_attach_topic_macro_context(request, mode, preliminary_plan):
        macro_target = _topic_macro_target(request, theme)
        macro_started = time.time()
        _emit(event_sink, "stage_started", stage="macro_context", ticker=macro_target)
        try:
            macro_context_model = await asyncio.wait_for(
                asyncio.to_thread(get_macro_research_context, ticker=macro_target),
                timeout=_topic_macro_context_timeout_s(),
            )
            macro_context = macro_context_model.model_dump(mode="json")
            macro_item = macro_research_context_to_retrieval_item(macro_context_model, ticker=macro_target)
            fast_context.append(macro_item)
            macro_metric_dicts = macro_research_context_metrics(macro_context_model, ticker=macro_target)
            quant_snapshot.setdefault("metrics", [])
            quant_snapshot["metrics"].extend(macro_metric_dicts)
            quant_snapshot["macro_platform_context"] = macro_context
            stage_timings["macro_context"] = round(time.time() - macro_started, 2)
            _emit(
                event_sink,
                "stage_completed",
                stage="macro_context",
                duration_s=stage_timings["macro_context"],
                status="ok",
                data_quality=macro_context.get("portfolio_hints", {}).get("data_quality", {}).get("status"),
            )
        except getattr(asyncio.exceptions, "TimeoutError", asyncio.TimeoutError):
            macro_context_error = f"Macro platform context timed out after {_topic_macro_context_timeout_s():.1f}s; continuing without it."
            stage_timings["macro_context"] = round(time.time() - macro_started, 2)
            logger.warning("[TOPIC_MACRO_CONTEXT] %s", macro_context_error)
            _emit(event_sink, "stage_completed", stage="macro_context", duration_s=stage_timings["macro_context"], status="timeout")
        except Exception as exc:  # noqa: BLE001
            macro_context_error = f"Macro platform context failed open: {exc}"
            stage_timings["macro_context"] = round(time.time() - macro_started, 2)
            logger.warning("[TOPIC_MACRO_CONTEXT] %s", macro_context_error)
            _emit(
                event_sink,
                "stage_completed",
                stage="macro_context",
                duration_s=stage_timings["macro_context"],
                status="failed",
                error=str(exc),
            )

    infer_fast_started = time.time()
    _emit(event_sink, "stage_started", stage="infer", phase="fast", chunks=len(fast_context))
    deterministic_reason = _deterministic_fast_path_reason(request, preliminary_plan, quant_snapshot)
    try:
        if deterministic_reason:
            fallback_plan = preliminary_plan
            fallback_pack = build_evidence_pack(request.question, theme, fast_context, request.related_tickers, fallback_plan)
            fast_payload = _local_decision_payload(
                request,
                theme=theme,
                context=fast_context,
                topic_plan=fallback_plan,
                evidence_pack=fallback_pack,
                error_metadata=None,
                language=language,
                phase="fast",
            )
            fast_payload["uncertainty"] = ""
            _merge_quant_metrics(fast_payload, quant_snapshot)
            fast_meta = fast_payload.setdefault("_meta", {})
            if isinstance(fast_meta, dict):
                fast_meta.update(
                    {
                        "primary_model": str(request.model),
                        "producing_model": "local-deterministic-fast-path",
                        "fallback_reason": deterministic_reason,
                        "llm_skipped_reason": deterministic_reason,
                        "asset_class": fallback_plan.asset_class,
                    }
                )
            fast_gate = topic_fast_gate(fast_payload, preferred_language=language)
            final_gate = topic_final_gate(
                fast_payload,
                minimums=fallback_plan.minimums,
                preferred_language=language,
            )
            fast_phase = TopicInferencePhaseResult(
                payload=fast_payload,
                topic_plan=fallback_plan,
                evidence_pack=fallback_pack,
                latency_s=0.0,
                retry_count=0,
                prompt_char_count=0,
                gate=fast_gate,
                final_gate=final_gate,
                selected_fields=[],
            )
        else:
            fast_phase = await asyncio.to_thread(
                run_topic_fast_inference,
                request.question,
                theme,
                fast_context,
                request.model,
                request.related_tickers,
                quant_snapshot,
                language,
            )
    except Exception as infer_exc:  # noqa: BLE001
        logger.warning("[TOPIC_FAST_INFER_DEGRADED] %s", infer_exc)
        inference_error = f"LLM 구조화 출력 실패: {infer_exc}"
        recovered_errors.append(inference_error)
        fallback_plan = build_topic_plan(request.question, theme, request.related_tickers, fast_context)
        fallback_pack = build_evidence_pack(request.question, theme, fast_context, request.related_tickers, fallback_plan)
        fast_payload = _local_decision_payload(
            request,
            theme=theme,
            context=fast_context,
            topic_plan=fallback_plan,
            evidence_pack=fallback_pack,
            error_metadata=inference_error,
            language=language,
            phase="fast",
        )
        _merge_quant_metrics(fast_payload, quant_snapshot)
        fast_gate = topic_fast_gate(fast_payload, preferred_language=language)
        final_gate = topic_final_gate(
            fast_payload,
            minimums=fallback_plan.minimums,
            preferred_language=language,
        )
        fast_phase = TopicInferencePhaseResult(
            payload=fast_payload,
            topic_plan=fallback_plan,
            evidence_pack=fallback_pack,
            latency_s=0.0,
            retry_count=0,
            prompt_char_count=0,
            gate=fast_gate,
            final_gate=final_gate,
            selected_fields=[],
        )
        status = "partial"
    raw_fast_gate_ok = bool((fast_phase.gate or {}).get("ok"))
    fast_phase = _apply_quant_to_phase(
        fast_phase,
        quant_snapshot,
        preferred_language=language,
    )
    stage_timings["infer_fast"] = round(time.time() - infer_fast_started, 2)
    _emit(
        event_sink,
        "stage_completed",
        stage="infer",
        phase="fast",
        duration_s=stage_timings["infer_fast"],
        retry_count=fast_phase.retry_count,
    )

    fast_meta = fast_phase.payload.pop("_meta", {}) if isinstance(fast_phase.payload, dict) else {}
    partial_metric_coverage = metric_as_of_coverage({**fast_phase.payload, "raw_context": [item.model_dump(mode="json") for item in fast_context]})
    partial_claim_coverage = claim_evidence_date_coverage({**fast_phase.payload, "raw_context": [item.model_dump(mode="json") for item in fast_context]})
    partial_exec_meta = ExecutionMeta(
        primary_model=fast_meta.get("primary_model"),
        producing_model=fast_meta.get("producing_model"),
        retry_count=fast_meta.get("retry_count"),
        total_latency_s=fast_meta.get("total_latency_s"),
        prompt_char_count=fast_meta.get("prompt_char_count"),
        chunks_used=fast_meta.get("chunks_used"),
        lens="topic",
        context_horizon="fast",
        pipeline_latency_s=round(time.time() - started, 2),
        stages_ran=["collect", "retrieve", "infer"],
        extras={
            "phase": "fast",
            "stage_timings": dict(stage_timings),
            "cache_hit": bool(getattr(collection, "cache_hit", False)),
            "ingest_skipped_docs": 0,
            "retrieval_mode": "fast_current_documents",
            "deep_pass_reason": [],
            "deep_pass_skipped": False,
            "fast_gate": fast_phase.gate,
            "final_gate": fast_phase.final_gate,
            "asset_class": fast_meta.get("asset_class"),
            "evidence_bucket_counts": fast_meta.get("evidence_bucket_counts"),
            "missing_evidence_buckets": fast_meta.get("missing_evidence_buckets"),
            "substituted_buckets": fast_meta.get("substituted_buckets") or list((quant_snapshot or {}).get("substituted_buckets") or []),
            "quant_snapshot": fast_meta.get("quant_snapshot") or quant_snapshot,
            "structured_context": structured_context,
            "macro_platform_context": macro_context or {},
            "macro_platform_context_status": "attached" if macro_context else ("failed_open" if macro_context_error else "not_applicable"),
            "macro_platform_context_error": macro_context_error,
            "macro_platform_metrics_count": len(macro_metric_dicts),
            "data_mart_freshness": structured_context.get("freshness") if isinstance(structured_context, dict) else {},
            "data_quality_summary": structured_context.get("data_quality_summary") if isinstance(structured_context, dict) else {},
            "llm_skipped_reason": fast_meta.get("llm_skipped_reason") or "",
            "metric_as_of_coverage": partial_metric_coverage,
            "claim_evidence_date_coverage": partial_claim_coverage,
            "coverage_notes": fast_meta.get("coverage_notes"),
            "missing_evidence_reasons": fast_meta.get("missing_evidence_reasons"),
            "data_freshness": _data_freshness(fast_context),
            "provider_status": _provider_statuses(collection),
            "model_capabilities": model_capability_dict(str(request.model), fast_meta.get("primary_model")),
            "validation_summary": {
                "fast_gate_ok": bool((fast_phase.gate or {}).get("ok")),
                "final_gate_ok": bool((fast_phase.final_gate or {}).get("ok")),
                "metric_as_of_coverage": partial_metric_coverage,
                "claim_evidence_date_coverage": partial_claim_coverage,
            },
            "error_type": "",
            "run_manifest": _run_manifest(
                request,
                asset_class=str(fast_meta.get("asset_class") or "sector_theme"),
                target=str((quant_snapshot or {}).get("target") or theme),
                collection=collection,
                final_gate=fast_phase.final_gate,
            ),
        },
    )
    partial_response = _response_from_payload(
        request,
        theme=theme,
        mode=mode,
        status="partial",
        error_metadata=None,
        payload=fast_phase.payload,
        context=fast_context,
        execution_meta=partial_exec_meta,
    )
    _emit(event_sink, "partial_result", payload=partial_response.model_dump(mode="json"))

    final_payload = dict(fast_phase.payload)
    final_context = list(fast_context)
    final_meta = dict(fast_meta)

    fast_bucket_counts = {name: len(bucket.items) for name, bucket in fast_phase.evidence_pack.buckets.items()}
    fast_bucket_policy = evidence_bucket_policy(
        fast_phase.topic_plan.asset_class,
        fast_bucket_counts,
        reported_missing=fast_phase.evidence_pack.missing_buckets,
        substituted_buckets=list((quant_snapshot or {}).get("substituted_buckets") or []),
    )
    fast_blocking_buckets = fast_bucket_policy["blocking_missing"]
    need_deep_infer = not fast_phase.final_gate["ok"]
    need_deep_retrieval = bool(
        fast_blocking_buckets
        or not raw_fast_gate_ok
        or not fast_phase.gate["ok"]
        or _needs_historical_context(request.question, fast_phase)
    )
    if not raw_fast_gate_ok or not fast_phase.gate["ok"]:
        deep_pass_reason.append("fast_gate")
    if fast_blocking_buckets or fast_phase.evidence_pack.missing_buckets:
        deep_pass_reason.append("missing_evidence_buckets")
    if _needs_historical_context(request.question, fast_phase):
        deep_pass_reason.append("historical_context")

    if need_deep_infer:
        deep_pass_skipped = False
        deep_context = list(fast_context)
        if need_deep_retrieval and collection.documents:
            ingest_started = time.time()
            _emit(event_sink, "stage_started", stage="ingest", documents=len(collection.documents))
            ingest_stats = await asyncio.to_thread(
                ingest_documents,
                collection.documents,
                None,
                skip_existing_parent_docs=True,
                return_stats=True,
            )
            stage_timings["ingest"] = round(time.time() - ingest_started, 2)
            _emit(
                event_sink,
                "stage_completed",
                stage="ingest",
                duration_s=stage_timings["ingest"],
                documents=len(collection.documents),
                skipped_docs=int((ingest_stats or {}).get("skipped_docs", 0)),
            )

            deep_retrieve_started = time.time()
            _emit(event_sink, "stage_started", stage="retrieve", phase="deep", top_k=request.top_k)
            deep_hits = await asyncio.to_thread(
                retrieve_topic_context,
                request.question,
                theme,
                request.top_k,
                asset_class=fast_phase.topic_plan.asset_class,
                related_tickers=request.related_tickers,
                use_reranker=(not fast_phase.gate["ok"]) or bool(fast_phase.evidence_pack.missing_buckets),
            )
            stage_timings["retrieve_deep"] = round(time.time() - deep_retrieve_started, 2)
            deep_context = _rebalance_context(deep_hits, fast_context, request.top_k) if deep_hits else fast_context
            retrieval_mode = "deep_qdrant" if deep_hits else "fast_current_documents"
            _emit(
                event_sink,
                "stage_completed",
                stage="retrieve",
                phase="deep",
                duration_s=stage_timings["retrieve_deep"],
                chunks=len(deep_context),
                retrieval_mode=retrieval_mode,
            )

        infer_deep_started = time.time()
        _emit(event_sink, "stage_started", stage="infer", phase="deep", chunks=len(deep_context))
        try:
            deep_phase = await asyncio.to_thread(
                run_topic_deep_inference,
                request.question,
                theme,
                deep_context,
                request.model,
                request.related_tickers,
                existing_output=fast_phase.payload,
                topic_plan=fast_phase.topic_plan,
                deep_reason=", ".join(deep_pass_reason) or "quality completion",
                quant_snapshot=quant_snapshot,
                output_language=language,
            )
            deep_phase = _apply_quant_to_phase(
                deep_phase,
                quant_snapshot,
                preferred_language=language,
            )
            stage_timings["infer_deep"] = round(time.time() - infer_deep_started, 2)
            _emit(
                event_sink,
                "stage_completed",
                stage="infer",
                phase="deep",
                duration_s=stage_timings["infer_deep"],
                retry_count=deep_phase.retry_count,
            )
            final_payload = dict(deep_phase.payload)
            final_context = list(deep_context)
            final_meta = final_payload.pop("_meta", {}) if isinstance(final_payload, dict) else {}
            final_gate = deep_phase.final_gate
        except Exception as infer_exc:  # noqa: BLE001
            logger.warning("[TOPIC_DEEP_INFER_DEGRADED] %s", infer_exc)
            inference_error = f"LLM 심화 보강 출력 실패: {infer_exc}"
            recovered_errors.append(inference_error)
            status = "partial"
            fallback_pack = build_evidence_pack(request.question, theme, deep_context, request.related_tickers, fast_phase.topic_plan)
            degraded_payload = _local_decision_payload(
                request,
                theme=theme,
                context=deep_context,
                topic_plan=fast_phase.topic_plan,
                evidence_pack=fallback_pack,
                error_metadata=inference_error,
                language=language,
                phase="final",
            )
            _merge_quant_metrics(degraded_payload, quant_snapshot)
            final_gate = topic_final_gate(
                degraded_payload,
                minimums=fast_phase.topic_plan.minimums,
                preferred_language=language,
            )
            stage_timings["infer_deep"] = round(time.time() - infer_deep_started, 2)
            _emit(
                event_sink,
                "stage_completed",
                stage="infer",
                phase="deep",
                duration_s=stage_timings["infer_deep"],
                status="degraded",
                detail=inference_error,
                retry_count=0,
            )
            final_payload = dict(degraded_payload)
            final_context = list(deep_context)
            final_meta = final_payload.pop("_meta", {}) if isinstance(final_payload, dict) else {}
    else:
        final_gate = fast_phase.final_gate

    if not final_gate.get("ok"):
        repair_pack = build_evidence_pack(
            request.question,
            theme,
            final_context,
            request.related_tickers,
            fast_phase.topic_plan,
        )
        repair_payload = _local_decision_payload(
            request,
            theme=theme,
            context=final_context,
            topic_plan=fast_phase.topic_plan,
            evidence_pack=repair_pack,
            error_metadata=None,
            language=language,
            phase="final_repair",
        )
        _merge_quant_metrics(repair_payload, quant_snapshot)
        repair_meta = dict(repair_payload.get("_meta") or {})
        final_payload = merge_topic_phase_outputs(final_payload, repair_payload)
        final_payload["_meta"] = {
            **final_meta,
            **repair_meta,
            "fallback_reason": "deterministic_completeness_repair",
        }
        final_meta = final_payload.pop("_meta", {}) if isinstance(final_payload, dict) else {}
        final_gate = topic_final_gate(
            final_payload,
            minimums=fast_phase.topic_plan.minimums,
            preferred_language=language,
        )
        if final_gate.get("ok"):
            recovered_errors.append("최종 섹션 누락을 로컬 결정 규칙으로 보강했습니다.")

    asset_class = str(final_meta.get("asset_class") or fast_meta.get("asset_class") or "sector_theme")
    evidence_bucket_counts = final_meta.get("evidence_bucket_counts") or fast_meta.get("evidence_bucket_counts") or {}
    reported_missing_buckets = [
        str(x)
        for x in (final_meta.get("missing_evidence_buckets") or fast_meta.get("missing_evidence_buckets") or [])
        if str(x).strip()
    ]
    substituted_buckets = [
        str(x)
        for x in (final_meta.get("substituted_buckets") or fast_meta.get("substituted_buckets") or (quant_snapshot or {}).get("substituted_buckets") or [])
        if str(x).strip()
    ]
    bucket_policy = evidence_bucket_policy(
        asset_class,
        evidence_bucket_counts,
        reported_missing=reported_missing_buckets,
        substituted_buckets=substituted_buckets,
    )
    blocking_buckets = bucket_policy["blocking_missing"]
    warning_buckets = bucket_policy["warning_missing"]
    final_status, final_error_metadata, final_warnings = _final_topic_status(
        final_gate=final_gate,
        blocking_errors=blocking_errors,
        blocking_buckets=blocking_buckets,
        warning_buckets=warning_buckets,
        recovered_errors=recovered_errors,
    )
    status = final_status
    error_metadata = final_error_metadata
    if status == "success":
        _sanitize_success_uncertainty(
            final_payload,
            warning_buckets=warning_buckets,
            recovered_errors=recovered_errors,
        )

    metric_coverage = metric_as_of_coverage({**final_payload, "raw_context": [item.model_dump(mode="json") for item in final_context]})
    claim_date_coverage = claim_evidence_date_coverage({**final_payload, "raw_context": [item.model_dump(mode="json") for item in final_context]})

    analyze_started = time.time()
    _emit(event_sink, "stage_started", stage="analyze")
    exec_meta = ExecutionMeta(
        primary_model=final_meta.get("primary_model"),
        producing_model=final_meta.get("producing_model"),
        retry_count=final_meta.get("retry_count"),
        total_latency_s=round(
            float(fast_meta.get("total_latency_s", 0.0) or 0.0)
            + (0.0 if deep_pass_skipped else float(final_meta.get("total_latency_s", 0.0) or 0.0)),
            2,
        ),
        prompt_char_count=int(fast_meta.get("prompt_char_count", 0) or 0) + (0 if deep_pass_skipped else int(final_meta.get("prompt_char_count", 0) or 0)),
        chunks_used=final_meta.get("chunks_used") or fast_meta.get("chunks_used"),
        lens="topic",
        context_horizon="multi_horizon",
        pipeline_latency_s=round(time.time() - started, 2),
        stages_ran=[stage for stage in ["collect", "ingest", "retrieve", "infer", "analyze", "report", "output"] if stage != "ingest" or ingest_stats],
        extras={
            "phase": "final",
            "stage_timings": dict(stage_timings),
            "cache_hit": bool(getattr(collection, "cache_hit", False)),
            "ingest_skipped_docs": int((ingest_stats or {}).get("skipped_docs", 0)),
            "retrieval_mode": retrieval_mode,
            "deep_pass_reason": deep_pass_reason,
            "deep_pass_skipped": deep_pass_skipped,
            "fast_gate": fast_phase.gate,
            "final_gate": final_gate,
            "asset_class": asset_class,
            "evidence_bucket_counts": evidence_bucket_counts,
            "missing_evidence_buckets": blocking_buckets,
            "blocking_missing_buckets": blocking_buckets,
            "warning_missing_buckets": warning_buckets,
            "substituted_buckets": substituted_buckets,
            "warning_evidence_buckets": warning_buckets,
            "blocking_evidence_buckets": blocking_buckets,
            "quant_snapshot": final_meta.get("quant_snapshot") or fast_meta.get("quant_snapshot") or quant_snapshot,
            "structured_context": structured_context,
            "macro_platform_context": macro_context or {},
            "macro_platform_context_status": "attached" if macro_context else ("failed_open" if macro_context_error else "not_applicable"),
            "macro_platform_context_error": macro_context_error,
            "macro_platform_metrics_count": len(macro_metric_dicts),
            "data_mart_freshness": structured_context.get("freshness") if isinstance(structured_context, dict) else {},
            "data_quality_summary": structured_context.get("data_quality_summary") if isinstance(structured_context, dict) else {},
            "output_language": language,
            "llm_skipped_reason": final_meta.get("llm_skipped_reason") or fast_meta.get("llm_skipped_reason") or "",
            "metric_as_of_coverage": metric_coverage,
            "claim_evidence_date_coverage": claim_date_coverage,
            "warnings": final_warnings,
            "recovered_errors": recovered_errors,
            "coverage_notes": final_meta.get("coverage_notes") or fast_meta.get("coverage_notes"),
            "missing_evidence_reasons": final_meta.get("missing_evidence_reasons") or fast_meta.get("missing_evidence_reasons"),
            "data_freshness": _data_freshness(final_context),
            "provider_status": _provider_statuses(collection),
            "model_capabilities": model_capability_dict(str(request.model), final_meta.get("primary_model") or fast_meta.get("primary_model")),
            "validation_summary": {
                "final_gate_ok": bool(final_gate.get("ok")),
                "metric_as_of_coverage": metric_coverage,
                "claim_evidence_date_coverage": claim_date_coverage,
                "decision_richness_profile": "topic",
            },
            "error_type": _classify_error_type(error_metadata, status=status),
            "run_manifest": _run_manifest(
                request,
                asset_class=asset_class,
                target=str((quant_snapshot or {}).get("target") or theme),
                collection=collection,
                final_gate=final_gate,
            ),
        },
    )
    response = _response_from_payload(
        request,
        theme=theme,
        mode=mode,
        status=status,
        error_metadata=error_metadata,
        payload=final_payload,
        context=final_context,
        execution_meta=exec_meta,
    )
    stage_timings["analyze"] = round(time.time() - analyze_started, 2)
    _emit(event_sink, "stage_completed", stage="analyze", duration_s=stage_timings["analyze"])

    report_started = time.time()
    _emit(event_sink, "stage_started", stage="report")
    simulation_override = getattr(request, "scenario_simulation_enabled", None)
    simulation_enabled = bool(simulation_override) if simulation_override is not None else bool(getattr(settings, "scenario_simulation_enabled", False))
    if simulation_enabled:
        try:
            from pipelines.simulate.simulation_pipeline import run_scenario_simulation

            simulation = await run_scenario_simulation(
                analysis_response=response,
                retrieved_documents=getattr(response, "raw_context", None),
                quant_snapshot=response.execution_meta.extras.get("quant_snapshot") if response.execution_meta else None,
                settings=settings,
            )
            if response.execution_meta is None:
                response.execution_meta = ExecutionMeta()
            response.execution_meta.extras["scenario_simulation"] = simulation.model_dump(mode="json")
        except Exception as exc:
            if getattr(settings, "scenario_simulation_fail_open", True):
                if response.execution_meta is None:
                    response.execution_meta = ExecutionMeta()
                response.execution_meta.extras["scenario_simulation"] = {
                    "status": "failed",
                    "diagnostics": {"errors": [str(exc)], "warnings": [], "fallback_used": False, "llm_used": False},
                }
            else:
                raise
    report_md, report_html = build_topic_report(response, language=language)
    stage_timings["report"] = round(time.time() - report_started, 2)
    _emit(event_sink, "stage_completed", stage="report", duration_s=stage_timings["report"])

    output_started = time.time()
    _emit(event_sink, "stage_started", stage="output")
    await asyncio.to_thread(
        save_outputs,
        request,
        response,
        report_md,
        report_html,
        collection_outcome=collection,
    )
    stage_timings["output"] = round(time.time() - output_started, 2)
    response.execution_meta.pipeline_latency_s = round(time.time() - started, 2)
    response.execution_meta.extras["stage_timings"] = dict(stage_timings)
    _emit(event_sink, "stage_completed", stage="output", duration_s=stage_timings["output"])
    _emit(event_sink, "pipeline_completed", status=response.status, elapsed_s=response.execution_meta.pipeline_latency_s)
    return response


def run_topic_pipeline(request: TopicRequest, mode: str = "concept") -> TopicResponse:
    return asyncio.run(run_topic_pipeline_async(request, mode=mode))
