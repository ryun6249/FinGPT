from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field as dataclass_field
from typing import Any

import httpx

from core.config.settings import load_settings
from core.schemas.request import _coerce_output_language
from core.schemas.retrieval import RetrievalItem
from core.utils.logger import get_logger
from core.utils.validation_metrics import topic_fast_gate, topic_final_gate
from pipelines.analyze.topic_quant import key_metrics_from_quant_snapshot
from pipelines.infer.runner_factory import resolve_model_name

logger = get_logger("pipelines.infer.topic")

DEFAULT_NUM_CTX = 6144
DEFAULT_NUM_PREDICT = 640
RETRY_NUM_PREDICT = 896
DEEP_NUM_CTX = 7168
DEEP_NUM_PREDICT = 896
DEEP_RETRY_NUM_PREDICT = 1152
RETRYABLE_OUTPUT_REASONS = {"empty", "malformed", "schema-invalid", "language"}
MAX_FAST_PROMPT_CHARS = 6000
MAX_DEEP_PROMPT_CHARS = 8000
MAX_DOC_CHARS_FAST = 500
MAX_DOC_CHARS_DEEP = 700
MAX_EXISTING_JSON_CHARS = 2400

_DECISION_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "conclusion": {"type": "string"},
        "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "bullets", "conclusion", "evidence_doc_ids"],
}

_SCENARIO_SCHEMA = {
    "type": "object",
    "properties": {
        "scenario": {"type": "string"},
        "probability": {"type": "string"},
        "expected_outcome": {"type": "string"},
        "asset_implication": {"type": "string"},
        "decision_read": {"type": "string"},
        "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["scenario", "probability", "expected_outcome", "asset_implication", "decision_read", "evidence_doc_ids"],
}

_EXECUTION_STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy": {"type": "string"},
        "trigger": {"type": "string"},
        "rationale": {"type": "string"},
        "risk_control": {"type": "string"},
        "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["strategy", "trigger", "rationale", "risk_control", "evidence_doc_ids"],
}

TOPIC_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "core_thesis": {"type": "string"},
        "asset_overview": {"type": "array", "items": _DECISION_SECTION_SCHEMA},
        "macro_regime": {"type": "array", "items": _DECISION_SECTION_SCHEMA},
        "rate_structure": {"type": "array", "items": _DECISION_SECTION_SCHEMA},
        "scenario_analysis": {"type": "array", "items": _SCENARIO_SCHEMA},
        "investment_judgment": {"type": "array", "items": _DECISION_SECTION_SCHEMA},
        "execution_strategy": {"type": "array", "items": _EXECUTION_STRATEGY_SCHEMA},
        "key_drivers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "direction": {"type": "string"},
                    "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "direction", "evidence_doc_ids"],
            },
        },
        "key_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "direction": {"type": "string"},
                    "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "direction", "evidence_doc_ids"],
            },
        },
        "related_tickers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "role": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["ticker", "role", "rationale"],
            },
        },
        "key_metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "as_of": {"type": "string"},
                    "context": {"type": "string"},
                    "evidence_doc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "value", "as_of", "context", "evidence_doc_ids"],
            },
        },
        "catalyst_timeline": {
            "type": "object",
            "properties": {
                "near_term": {"type": "array", "items": {"type": "string"}},
                "mid_term": {"type": "array", "items": {"type": "string"}},
                "long_term": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["near_term", "mid_term", "long_term"],
        },
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "uncertainty": {"type": "string"},
        "cited_doc_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "executive_summary",
        "core_thesis",
        "asset_overview",
        "macro_regime",
        "rate_structure",
        "scenario_analysis",
        "investment_judgment",
        "execution_strategy",
        "key_drivers",
        "key_risks",
        "related_tickers",
        "key_metrics",
        "catalyst_timeline",
        "open_questions",
        "uncertainty",
        "cited_doc_ids",
    ],
}

TOPIC_FAST_FIELDS = [
    "executive_summary",
    "core_thesis",
    "asset_overview",
    "macro_regime",
    "rate_structure",
    "scenario_analysis",
    "investment_judgment",
    "execution_strategy",
    "key_drivers",
    "key_risks",
    "uncertainty",
    "cited_doc_ids",
]
TOPIC_DEEP_REPAIR_FIELDS = [
    "executive_summary",
    "core_thesis",
    "rate_structure",
    "scenario_analysis",
    "investment_judgment",
    "execution_strategy",
    "uncertainty",
    "cited_doc_ids",
]

TOPIC_FOUNDATION_SCHEMA = {
    "type": "object",
    "properties": {k: TOPIC_OUTPUT_SCHEMA["properties"][k] for k in ("asset_overview", "macro_regime", "rate_structure", "cited_doc_ids")},
    "required": ["asset_overview", "macro_regime", "rate_structure", "cited_doc_ids"],
}
TOPIC_DECISION_SCHEMA = {
    "type": "object",
    "properties": {k: TOPIC_OUTPUT_SCHEMA["properties"][k] for k in ("scenario_analysis", "investment_judgment", "execution_strategy", "cited_doc_ids")},
    "required": ["scenario_analysis", "investment_judgment", "execution_strategy", "cited_doc_ids"],
}
TOPIC_SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {k: TOPIC_OUTPUT_SCHEMA["properties"][k] for k in ("key_drivers", "key_risks", "uncertainty", "cited_doc_ids")},
    "required": ["key_drivers", "key_risks", "uncertainty", "cited_doc_ids"],
}
TOPIC_SYNTHESIS_SCHEMA = {
    "type": "object",
    "properties": {k: TOPIC_OUTPUT_SCHEMA["properties"][k] for k in ("executive_summary", "core_thesis", "uncertainty", "cited_doc_ids")},
    "required": ["executive_summary", "core_thesis", "uncertainty", "cited_doc_ids"],
}

TOPIC_STAGE_ONE_SCHEMA = TOPIC_FOUNDATION_SCHEMA
TOPIC_STAGE_TWO_SCHEMA = TOPIC_DECISION_SCHEMA

DOMAIN_DECISION_PLAYBOOK = """
Domain-specific decision playbook:
- Single-name equities: business model, revenue/EPS trend, margin quality, guidance, valuation anchor, balance sheet, competitive position, catalyst timing.
- Rates / sovereign bonds / bond ETFs: duration, yield level, curve shape, real rates, Fed path, inflation, term premium, Treasury supply, convexity, downside trigger.
- Equity ETFs / sectors / themes: exposure composition, concentration, breadth, earnings backdrop, valuation, capex/demand cycle, competitive position, policy catalyst.
- Commodities / energy / metals: supply-demand balance, inventory, futures curve, marginal cost, weather/geopolitics, USD and real-rate sensitivity, roll yield.
- FX / dollar / global macro: interest-rate differential, growth differential, policy divergence, capital flows, dollar liquidity, positioning, intervention risk.
- Crypto / digital assets: liquidity cycle, ETF or regulatory flows, network or exchange activity, volatility and liquidation risk, correlation with risk assets.
- Healthcare / biotech: pipeline catalysts, approval risk, patent cliff, cash runway, reimbursement, binary event sizing.
- Real estate / REITs / infrastructure: cap rates, funding costs, occupancy, refinancing wall, dividend sustainability, long-end rate sensitivity.
- Consumer / retail: traffic, ticket, pricing power, wage/input cost, credit stress, promotional intensity.
- General rule: do not invent numbers, keep document ids intact, and turn missing evidence into explicit uncertainty.
""".strip()

STRUCTURED_NUMERIC_EVIDENCE_POLICY = """
Structured numeric evidence policy:
- If the prompt includes STRUCTURED DATA MART CONTEXT or quant_snapshot metrics, use those stored values as authoritative numeric evidence.
- Do not invent prices, returns, macro values, factor values, risk metrics, or portfolio weights.
- Use RAG documents for qualitative interpretation, source citations, and catalyst/risk explanations.
""".strip()

TOPIC_SYSTEM_PROMPT = (
    "You are a senior macro and cross-asset strategist. "
    "Return only valid JSON matching the provided structured format. "
    "Do not wrap JSON in markdown fences. "
    "When Korean is requested, every descriptive field must be Korean. "
    "Keep tickers, source titles, company names, and numeric values unchanged. "
    f"{STRUCTURED_NUMERIC_EVIDENCE_POLICY}"
)


@dataclass
class TopicPlan:
    asset_class: str
    label: str
    description: str
    required_sections: list[str]
    required_metrics: list[str]
    scenario_axes: list[str]
    execution_axes: list[str]
    minimums: dict[str, int]


@dataclass
class EvidenceBucket:
    name: str
    label: str
    items: list[RetrievalItem] = dataclass_field(default_factory=list)

    def add(self, item: RetrievalItem) -> None:
        doc_id = _parent_doc_id(item)
        if doc_id and any(_parent_doc_id(existing) == doc_id for existing in self.items):
            return
        self.items.append(item)


@dataclass
class EvidenceMetric:
    name: str
    value: str
    as_of: str
    context: str
    evidence_doc_ids: list[str]


@dataclass
class EvidencePack:
    asset_class: str
    buckets: dict[str, EvidenceBucket]
    metrics: list[EvidenceMetric]
    cited_doc_ids: list[str]
    missing_buckets: list[str]
    coverage_notes: list[str]


@dataclass
class TopicInferencePhaseResult:
    payload: dict[str, Any]
    topic_plan: TopicPlan
    evidence_pack: EvidencePack
    latency_s: float
    retry_count: int
    prompt_char_count: int
    gate: dict[str, Any]
    final_gate: dict[str, Any]
    selected_fields: list[str]


TOPIC_PLAYBOOKS: dict[str, TopicPlan] = {
    "rates_bonds": TopicPlan(
        asset_class="rates_bonds",
        label="Rates / Bonds",
        description="Analyze growth, inflation, Fed path, real rates, yield curve, term premium, Treasury supply, and duration sensitivity.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["yield level", "real yield", "curve / duration"],
        scenario_axes=["rate cuts and slowdown", "soft landing / range bound", "inflation re-acceleration"],
        execution_axes=["staged entry", "confirmation entry", "hedged expression"],
        minimums={"decision_sections": 3, "scenario_analysis": 3, "execution_strategy": 2, "key_drivers": 2, "key_risks": 2, "key_metrics": 3},
    ),
    "equity_index": TopicPlan(
        asset_class="equity_index",
        label="Equity ETF / Index",
        description="Analyze exposure composition, concentration, valuation, earnings backdrop, and macro beta.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["valuation", "earnings / breadth", "macro beta"],
        scenario_axes=["macro improves", "range-bound market", "valuation compression"],
        execution_axes=["staged allocation", "trend confirmation", "paired hedge"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
    "credit": TopicPlan(
        asset_class="credit",
        label="Credit / Funding Stress",
        description="Analyze credit spreads, refinancing stress, liquidity, default cycle, equity-credit divergence, and funding risk.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["spread / proxy", "liquidity", "equity-credit divergence"],
        scenario_axes=["soft landing and spread stability", "refinancing stress", "liquidity shock"],
        execution_axes=["credit dashboard confirmation", "defensive rotation", "hedge overlay"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
    "commodity": TopicPlan(
        asset_class="commodity",
        label="Commodity",
        description="Analyze supply-demand balance, inventory, futures curve, dollar, real rates, and event risk.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["inventory / supply", "curve shape", "USD / real-rate sensitivity"],
        scenario_axes=["tightening supply", "range-bound demand", "demand slowdown / dollar strength"],
        execution_axes=["staged entry", "curve confirmation", "options or hedge overlay"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
    "fx": TopicPlan(
        asset_class="fx",
        label="FX",
        description="Analyze rate differentials, growth differentials, policy divergence, dollar liquidity, and positioning.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["rate differential", "growth / policy gap", "dollar or positioning signal"],
        scenario_axes=["policy divergence widens", "range-bound regime", "policy reversal / dollar squeeze"],
        execution_axes=["staged entry", "policy confirmation", "volatility control"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
    "crypto": TopicPlan(
        asset_class="crypto",
        label="Crypto",
        description="Analyze liquidity, ETF flows, regulation, risk-on/off, network or exchange signals, and liquidation risk.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["flow / liquidity", "volatility", "regulatory / network signal"],
        scenario_axes=["liquidity improves", "range-bound churn", "risk-off or regulatory shock"],
        execution_axes=["staged entry", "flow confirmation", "strict sizing"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
    "sector_theme": TopicPlan(
        asset_class="sector_theme",
        label="Sector / Theme",
        description="Analyze demand cycle, capex, pricing power, competition, beneficiaries, at-risk names, and proxy vehicles.",
        required_sections=["asset_overview", "macro_regime", "rate_structure"],
        required_metrics=["demand / orders", "valuation", "margin / capex"],
        scenario_axes=["cycle improves", "range-bound demand", "demand slowdown / multiple compression"],
        execution_axes=["leader concentration", "buy on pullbacks", "hedged basket"],
        minimums={"decision_sections": 3, "scenario_analysis": 2, "execution_strategy": 1, "key_drivers": 2, "key_risks": 2, "key_metrics": 2},
    ),
}


class StructuredOutputError(ValueError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _parent_doc_id(item: RetrievalItem) -> str:
    metadata = item.metadata or {}
    return str(metadata.get("parent_doc_id") or metadata.get("doc_id") or "")


def _shorten(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9=\-./]{1,}|[\uac00-\ud7a3]{2,}", str(text or "").lower())
    return {token for token in tokens if token}


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_decision_sections(value: Any) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return sections
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        conclusion = str(item.get("conclusion") or "").strip()
        bullets = _coerce_string_list(item.get("bullets"))
        evidence = _coerce_string_list(item.get("evidence_doc_ids"))
        if title or conclusion or bullets:
            sections.append({"title": title, "bullets": bullets, "conclusion": conclusion, "evidence_doc_ids": evidence})
    return sections


def _coerce_scenarios(value: Any) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return scenarios
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {
            "scenario": str(item.get("scenario") or "").strip(),
            "probability": str(item.get("probability") or "").strip(),
            "expected_outcome": str(item.get("expected_outcome") or "").strip(),
            "asset_implication": str(item.get("asset_implication") or "").strip(),
            "decision_read": str(item.get("decision_read") or "").strip(),
            "evidence_doc_ids": _coerce_string_list(item.get("evidence_doc_ids")),
        }
        if any(normalized[key] for key in ("scenario", "expected_outcome", "asset_implication", "decision_read")):
            scenarios.append(normalized)
    return scenarios


def _coerce_execution_strategies(value: Any) -> list[dict[str, Any]]:
    strategies: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return strategies
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = {
            "strategy": str(item.get("strategy") or "").strip(),
            "trigger": str(item.get("trigger") or "").strip(),
            "rationale": str(item.get("rationale") or "").strip(),
            "risk_control": str(item.get("risk_control") or "").strip(),
            "evidence_doc_ids": _coerce_string_list(item.get("evidence_doc_ids")),
        }
        if any(normalized[key] for key in ("strategy", "trigger", "rationale", "risk_control")):
            strategies.append(normalized)
    return strategies


def _coerce_directional_points(value: Any, default_direction: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return points
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            direction = str(item.get("direction") or default_direction).strip() or default_direction
            evidence = _coerce_string_list(item.get("evidence_doc_ids"))
        else:
            text = str(item or "").strip()
            direction = default_direction
            evidence = []
        if text:
            points.append({"text": text, "direction": direction, "evidence_doc_ids": evidence})
    return points


def _coerce_related_tickers(value: Any) -> list[dict[str, Any]]:
    tickers: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return tickers
    for item in value:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        role = str(item.get("role") or "proxy").strip() or "proxy"
        if role not in {"beneficiary", "at_risk", "proxy", "peer"}:
            role = "proxy"
        rationale = str(item.get("rationale") or "").strip()
        if ticker and rationale:
            tickers.append({"ticker": ticker, "role": role, "rationale": rationale})
    return tickers


def _coerce_key_metrics(value: Any) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return metrics
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        raw_value = item.get("value")
        if raw_value is None:
            continue
        metric_value = str(raw_value).strip()
        if not name or not metric_value:
            continue
        metrics.append(
            {
                "name": name,
                "value": metric_value,
                "as_of": str(item.get("as_of") or "").strip(),
                "context": str(item.get("context") or "").strip(),
                "evidence_doc_ids": _coerce_string_list(item.get("evidence_doc_ids")),
            }
        )
    return metrics


def _coerce_timeline(value: Any) -> dict[str, list[str]]:
    timeline = {"near_term": [], "mid_term": [], "long_term": []}
    if not isinstance(value, dict):
        return timeline
    for bucket in timeline:
        timeline[bucket] = _coerce_string_list(value.get(bucket))
    return timeline


def _collect_cited_doc_ids(parsed: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def merge_ids(ids: list[str]) -> None:
        for doc_id in ids:
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                ordered.append(doc_id)

    merge_ids(_coerce_string_list(parsed.get("cited_doc_ids")))
    for field in ("asset_overview", "macro_regime", "rate_structure", "investment_judgment"):
        for item in parsed.get(field, []) or []:
            if isinstance(item, dict):
                merge_ids(_coerce_string_list(item.get("evidence_doc_ids")))
    for field in ("scenario_analysis", "execution_strategy", "key_drivers", "key_risks", "key_metrics"):
        for item in parsed.get(field, []) or []:
            if isinstance(item, dict):
                merge_ids(_coerce_string_list(item.get("evidence_doc_ids")))
    return ordered


def _normalize_topic_response(parsed: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "executive_summary": str(parsed.get("executive_summary") or "").strip(),
        "core_thesis": str(parsed.get("core_thesis") or "").strip(),
        "asset_overview": _coerce_decision_sections(parsed.get("asset_overview")),
        "macro_regime": _coerce_decision_sections(parsed.get("macro_regime")),
        "rate_structure": _coerce_decision_sections(parsed.get("rate_structure")),
        "scenario_analysis": _coerce_scenarios(parsed.get("scenario_analysis")),
        "investment_judgment": _coerce_decision_sections(parsed.get("investment_judgment")),
        "execution_strategy": _coerce_execution_strategies(parsed.get("execution_strategy")),
        "key_drivers": _coerce_directional_points(parsed.get("key_drivers"), "supporting"),
        "key_risks": _coerce_directional_points(parsed.get("key_risks"), "opposing"),
        "related_tickers": _coerce_related_tickers(parsed.get("related_tickers")),
        "key_metrics": _coerce_key_metrics(parsed.get("key_metrics")),
        "catalyst_timeline": _coerce_timeline(parsed.get("catalyst_timeline")),
        "open_questions": _coerce_string_list(parsed.get("open_questions")),
        "uncertainty": str(parsed.get("uncertainty") or "").strip(),
    }
    normalized["cited_doc_ids"] = _collect_cited_doc_ids({**parsed, **normalized})
    return normalized


def _clean_json_candidate(raw: str) -> str:
    text = str(raw or "").lstrip("\ufeff").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    return text


def _extract_json(raw: str) -> dict[str, Any]:
    text = _clean_json_candidate(raw)
    if not text:
        raise StructuredOutputError("empty", "[Topic] Empty output.")
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise StructuredOutputError("schema-invalid", "[Topic] JSON root must be an object.")
        return parsed
    except StructuredOutputError:
        raise
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise StructuredOutputError("malformed", "[Topic] No JSON payload found.")

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : idx + 1]
                try:
                    parsed = json.loads(candidate)
                    if not isinstance(parsed, dict):
                        raise StructuredOutputError("schema-invalid", "[Topic] JSON root must be an object.")
                    return parsed
                except StructuredOutputError:
                    raise
                except json.JSONDecodeError as exc:
                    raise StructuredOutputError("malformed", f"[Topic] JSON malformed: {exc}") from exc
    raise StructuredOutputError("truncated", "[Topic] JSON truncated or unclosed.")


def _natural_language_fragments(parsed: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in ("executive_summary", "core_thesis", "uncertainty"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            fragments.append(value)
    for field in ("key_drivers", "key_risks", "related_tickers", "key_metrics"):
        for item in parsed.get(field, []) or []:
            if not isinstance(item, dict):
                continue
            for key in ("text", "rationale", "name", "context"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value)
    for field in ("asset_overview", "macro_regime", "rate_structure", "investment_judgment"):
        for item in parsed.get(field, []) or []:
            if not isinstance(item, dict):
                continue
            for key in ("title", "conclusion"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value)
            fragments.extend(str(x) for x in (item.get("bullets") or []) if str(x).strip())
    for item in parsed.get("scenario_analysis", []) or []:
        if isinstance(item, dict):
            for key in ("scenario", "probability", "expected_outcome", "asset_implication", "decision_read"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value)
    for item in parsed.get("execution_strategy", []) or []:
        if isinstance(item, dict):
            for key in ("strategy", "trigger", "rationale", "risk_control"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value)
    fragments.extend(str(x) for x in (parsed.get("open_questions") or []) if str(x).strip())
    return fragments


def _language_warning(parsed: dict[str, Any], expected_language: str) -> str | None:
    if str(expected_language or "").strip().lower() != "ko":
        return None
    joined = " ".join(_natural_language_fragments(parsed))
    if not joined.strip():
        return None
    hangul_count = len(re.findall(r"[\uac00-\ud7a3]", joined))
    latin_words = len(re.findall(r"\b[A-Za-z][A-Za-z\-]{2,}\b", joined))
    if hangul_count < 10 and latin_words >= 8:
        return "Korean output requested, but topic descriptive fields are mostly English."
    return None


def _validate_response(
    parsed: dict[str, Any],
    *,
    expected_language: str,
    required_fields: list[str],
    enforce_language: bool,
) -> None:
    for field in required_fields:
        value = parsed.get(field)
        if field == "cited_doc_ids":
            if not isinstance(value, list):
                raise StructuredOutputError("schema-invalid", "[Topic] 'cited_doc_ids' must be an array.")
        elif field in {"asset_overview", "macro_regime", "rate_structure", "investment_judgment"}:
            if not isinstance(value, list):
                raise StructuredOutputError("schema-invalid", f"[Topic] '{field}' must be an array.")
        elif field in {"scenario_analysis", "execution_strategy", "key_drivers", "key_risks", "related_tickers", "key_metrics", "open_questions"}:
            if not isinstance(value, list):
                raise StructuredOutputError("schema-invalid", f"[Topic] '{field}' must be an array.")
        elif field == "catalyst_timeline":
            if not isinstance(value, dict):
                raise StructuredOutputError("schema-invalid", "[Topic] 'catalyst_timeline' must be an object.")
        elif not str(value or "").strip():
            raise StructuredOutputError("schema-invalid", f"[Topic] '{field}' is empty.")

    package_has_content = any(
        bool(parsed.get(field))
        for field in required_fields
        if field not in {"cited_doc_ids", "uncertainty", "open_questions"}
    )
    if not package_has_content:
        raise StructuredOutputError("schema-invalid", "[Topic] Package produced no decision-useful content.")

    if enforce_language:
        warning = _language_warning(parsed, expected_language)
        if warning:
            raise StructuredOutputError("language", warning)


def _build_retry_prompt(prompt: str, reason: str, expected_language: str) -> str:
    if str(expected_language or "").strip().lower() == "ko" and reason == "language":
        correction = (
            "The previous response used too much English. Rewrite every descriptive field in Korean. "
            "Keep tickers, source titles, document ids, and numbers unchanged."
        )
    else:
        correction = (
            "The previous response was incomplete or invalid. Return exactly one complete JSON object that matches the requested fields. "
            "Do not omit keys, do not leave arrays open, and do not add markdown fences."
        )
    return f"{prompt}\n\nRETRY CORRECTION: {correction}"


def _build_language_repair_prompt(parsed: dict[str, Any], expected_language: str, required_fields: list[str]) -> str:
    language_name = "Korean" if str(expected_language or "").strip().lower() == "ko" else "English"
    return (
        f"Rewrite the following JSON object so every descriptive natural-language field is in {language_name}. "
        "Do not change tickers, source titles, numeric values, document ids, evidence_doc_ids, or cited_doc_ids. "
        f"Keep the same fields: {', '.join(required_fields)}.\n\n"
        f"JSON:\n{json.dumps(parsed, ensure_ascii=False)}"
    )


def _build_json_repair_prompt(raw_text: str, expected_language: str, required_fields: list[str]) -> str:
    language_name = "Korean" if str(expected_language or "").strip().lower() == "ko" else "English"
    broken = _shorten(_clean_json_candidate(raw_text), 2500)
    return (
        "The following output was intended to be JSON but is syntactically invalid or truncated. "
        "Repair it into exactly one valid JSON object. "
        "Repair only syntax, missing brackets, and missing required keys; do not expand the memo. "
        "Preserve existing facts, numbers, tickers, source titles, and document ids. "
        f"All descriptive fields must be in {language_name}. "
        f"Keep only these fields: {', '.join(required_fields)}.\n\n"
        f"Broken output:\n{broken}"
    )


def _call_topic_model(
    base_url: str,
    model_name: str,
    prompt: str,
    *,
    schema: dict[str, Any],
    num_predict: int,
    num_ctx: int,
) -> dict[str, Any]:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model_name,
            "system": TOPIC_SYSTEM_PROMPT,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict},
            "keep_alive": "5m",
        },
        timeout=240.0,
    )
    response.raise_for_status()
    body = response.json()
    return {"response": body.get("response", ""), "done_reason": body.get("done_reason"), "done": body.get("done")}


def _parse_generation_result(
    result: dict[str, Any],
    *,
    expected_language: str,
    enforce_language: bool,
    required_fields: list[str],
) -> dict[str, Any]:
    raw_text = result.get("response", "")
    if not str(raw_text or "").strip():
        raise StructuredOutputError("empty", "[Topic] Empty output.")
    if result.get("done_reason") == "length":
        raise StructuredOutputError("truncated", "[Topic] JSON truncated or unclosed.")
    parsed = _normalize_topic_response(_extract_json(raw_text))
    _validate_response(parsed, expected_language=expected_language, required_fields=required_fields, enforce_language=enforce_language)
    if not enforce_language:
        warning = _language_warning(parsed, expected_language)
        if warning:
            parsed["_language_warning"] = warning
    return parsed


def _repair_language_if_needed(
    *,
    base_url: str,
    model_name: str,
    parsed: dict[str, Any],
    expected_language: str,
    required_fields: list[str],
    schema: dict[str, Any],
    num_ctx: int,
    retry_predict: int,
) -> tuple[dict[str, Any], float, int]:
    warning = parsed.get("_language_warning")
    if not warning or str(expected_language or "").strip().lower() != "ko":
        parsed.pop("_language_warning", None)
        return parsed, 0.0, 0

    started = time.time()
    repair_result = _call_topic_model(
        base_url,
        model_name,
        _build_language_repair_prompt(parsed, expected_language, required_fields),
        schema=schema,
        num_predict=retry_predict,
        num_ctx=num_ctx,
    )
    latency = time.time() - started
    try:
        repaired = _parse_generation_result(
            repair_result,
            expected_language=expected_language,
            enforce_language=True,
            required_fields=required_fields,
        )
        repaired.pop("_language_warning", None)
        return repaired, latency, 1
    except StructuredOutputError:
        parsed.pop("_language_warning", None)
        return parsed, latency, 1


def _run_generation_phase(
    *,
    base_url: str,
    model_name: str,
    prompt: str,
    expected_language: str,
    schema: dict[str, Any],
    required_fields: list[str],
    num_ctx: int,
    primary_predict: int,
    retry_predict: int,
) -> tuple[dict[str, Any], float, int]:
    latencies = 0.0
    retries_used = 0
    current_prompt = prompt
    last_result: dict[str, Any] | None = None

    for attempt, num_predict in enumerate((primary_predict, retry_predict)):
        started = time.time()
        result = _call_topic_model(
            base_url,
            model_name,
            current_prompt,
            schema=schema,
            num_predict=num_predict,
            num_ctx=num_ctx,
        )
        latencies += time.time() - started
        last_result = result
        try:
            parsed = _parse_generation_result(
                result,
                expected_language=expected_language,
                enforce_language=attempt == 0,
                required_fields=required_fields,
            )
            repaired, repair_latency, repair_retry = _repair_language_if_needed(
                base_url=base_url,
                model_name=model_name,
                parsed=parsed,
                expected_language=expected_language,
                required_fields=required_fields,
                schema=schema,
                num_ctx=num_ctx,
                retry_predict=retry_predict,
            )
            latencies += repair_latency
            retries_used += repair_retry
            return repaired, latencies, retries_used
        except StructuredOutputError as exc:
            if exc.reason == "truncated":
                if attempt == 0 and last_result is not None and str(last_result.get("response") or "").strip():
                    repair_started = time.time()
                    repair_result = _call_topic_model(
                        base_url,
                        model_name,
                        _build_json_repair_prompt(last_result.get("response", ""), expected_language, required_fields),
                        schema=schema,
                        num_predict=retry_predict,
                        num_ctx=num_ctx,
                    )
                    latencies += time.time() - repair_started
                    retries_used += 1
                    try:
                        parsed = _parse_generation_result(
                            repair_result,
                            expected_language=expected_language,
                            enforce_language=False,
                            required_fields=required_fields,
                        )
                        repaired, repair_latency, repair_retry = _repair_language_if_needed(
                            base_url=base_url,
                            model_name=model_name,
                            parsed=parsed,
                            expected_language=expected_language,
                            required_fields=required_fields,
                            schema=schema,
                            num_ctx=num_ctx,
                            retry_predict=retry_predict,
                        )
                        latencies += repair_latency
                        retries_used += repair_retry
                        return repaired, latencies, retries_used
                    except StructuredOutputError:
                        raise exc
                raise
            can_retry = attempt == 0 and exc.reason in RETRYABLE_OUTPUT_REASONS
            if can_retry:
                retries_used += 1
                current_prompt = _build_retry_prompt(prompt, exc.reason, expected_language)
                continue
            if exc.reason in {"malformed", "schema-invalid"} and last_result is not None:
                repair_started = time.time()
                repair_result = _call_topic_model(
                    base_url,
                    model_name,
                    _build_json_repair_prompt(last_result.get("response", ""), expected_language, required_fields),
                    schema=schema,
                    num_predict=retry_predict,
                    num_ctx=num_ctx,
                )
                latencies += time.time() - repair_started
                retries_used += 1
                parsed = _parse_generation_result(
                    repair_result,
                    expected_language=expected_language,
                    enforce_language=False,
                    required_fields=required_fields,
                )
                repaired, repair_latency, repair_retry = _repair_language_if_needed(
                    base_url=base_url,
                    model_name=model_name,
                    parsed=parsed,
                    expected_language=expected_language,
                    required_fields=required_fields,
                    schema=schema,
                    num_ctx=num_ctx,
                    retry_predict=retry_predict,
                )
                latencies += repair_latency
                retries_used += repair_retry
                return repaired, latencies, retries_used
            raise


def _has_gold_intent(text: str) -> bool:
    lower = (text or "").lower()
    if any(term in lower for term in ("gold", "gld", "금값", "금 가격", "금 현물", "금 투자")):
        return True
    return re.search(r"(?<![가-힣])금(?!리|[가-힣])", text or "") is not None


def _has_commodity_intent(text: str) -> bool:
    lower = (text or "").lower()
    return _has_gold_intent(text) or any(
        term in lower
        for term in ("commodity", "oil", "crude", "wti", "backwardation", "contango", "원자재", "원유", "유가")
    )


def _asset_class_from_text(question: str, theme: str, related_tickers: list[str], context: list[RetrievalItem]) -> str:
    merged = f"{question} {theme} {' '.join(related_tickers)}".lower()
    original = f"{question} {theme} {' '.join(related_tickers)}"
    tickers = {ticker.upper() for ticker in related_tickers}
    if tickers & {"HYG", "LQD"} or any(term in merged for term in ("credit", "spread", "default", "corporate bond", "high yield", "신용", "크레딧", "회사채", "하이일드", "부도")):
        return "credit"
    if tickers & {"GLD", "USO", "SLV", "CL=F"} or _has_commodity_intent(original):
        return "commodity"
    if tickers & {"TLT", "IEF", "SHY", "AGG"} or any(term in merged for term in ("bond", "treasury", "yield curve", "real yield", "term premium", "duration", "채권", "국채", "금리")):
        return "rates_bonds"
    if tickers & {"EURUSD=X", "DXY"} or any(term in merged for term in ("eurusd", "eur/usd", "fx", "dollar", "환율", "달러")):
        return "fx"
    if tickers & {"BTC-USD", "ETH-USD"} or any(term in merged for term in ("bitcoin", "btc", "ethereum", "eth", "crypto", "비트코인", "암호화폐")):
        return "crypto"
    if len(tickers) > 1 or any(term in merged for term in ("sector", "theme", "semiconductor", "ai", "cloud", "섹터", "테마", "반도체")):
        return "sector_theme"
    for item in context:
        source = str(item.source or "").lower()
        title = f"{item.title} {item.chunk}".lower()
        if source.startswith("fred") and any(term in title for term in ("yield", "treasury", "cpi", "pce", "fed")):
            return "rates_bonds"
    return "equity_index"


def build_topic_plan(question: str, theme: str, related_tickers: list[str], context: list[RetrievalItem]) -> TopicPlan:
    return TOPIC_PLAYBOOKS[_asset_class_from_text(question, theme, related_tickers, context)]


def _classify_bucket_names(
    item: RetrievalItem,
    topic_plan: TopicPlan,
    question: str,
    theme: str,
    related_tickers: list[str],
) -> list[str]:
    metadata_bucket = str((item.metadata or {}).get("bucket") or "").strip()
    if metadata_bucket in {"macro", "asset_specific", "market_structure", "latest_catalyst"}:
        return [metadata_bucket]
    source = str(item.source or "").lower()
    title = str(item.title or "")
    text = f"{title} {item.chunk}".lower()
    ticker_hints = {ticker.upper() for ticker in related_tickers}
    metadata_ticker = str((item.metadata or {}).get("ticker") or (item.metadata or {}).get("symbol") or "").upper()
    matches: list[str] = []
    if source.startswith("fred") or any(term in text for term in ("cpi", "pce", "inflation", "payroll", "gdp", "fed", "yield", "real yield", "term premium", "growth", "금리", "물가", "고용")):
        matches.append("macro")
    if any(term in source for term in ("news", "google", "transcript")) or any(term in text for term in ("earnings", "guidance", "catalyst", "launch", "approval", "headline", "뉴스", "실적", "촉매")):
        matches.append("latest_catalyst")
    if any(term in source for term in ("history", "price", "issuer:")) or any(term in text for term in ("valuation", "spread", "curve", "contango", "backwardation", "multiple", "price", "premium", "discount", "roll", "밸류", "가격", "곡선", "스프레드")):
        matches.append("market_structure")
    theme_tokens = _tokenize(f"{question} {theme}")
    doc_tokens = _tokenize(f"{title} {item.chunk}")
    ticker_token_match = any(ticker.lower() in doc_tokens for ticker in ticker_hints)
    if metadata_ticker in ticker_hints or ticker_token_match or len(theme_tokens & doc_tokens) >= 2:
        matches.append("asset_specific")
    if not matches:
        matches.append("asset_specific")
    ordered = []
    for name in ("macro", "asset_specific", "market_structure", "latest_catalyst"):
        if name in matches and name not in ordered:
            ordered.append(name)
    return ordered


_METRIC_VALUE_RE = re.compile(
    r"(?<!\w)(?:[+-]?\d+(?:\.\d+)?(?:%|bp|bps|x)|\$?\d+(?:\.\d+)?(?:[BMK]| trillion| billion| million)?)(?!\w)",
    re.IGNORECASE,
)


def _metric_context(topic_plan: TopicPlan, bucket_name: str) -> str:
    if bucket_name == "macro":
        return "거시 변수"
    if bucket_name == "market_structure":
        return "가격 / 시장 구조"
    if bucket_name == "latest_catalyst":
        return "최신 촉매"
    if topic_plan.asset_class == "rates_bonds":
        return "채권 매력도 판단"
    return "의사결정 핵심 지표"


def _extract_metric_candidates(topic_plan: TopicPlan, buckets: dict[str, EvidenceBucket]) -> list[EvidenceMetric]:
    metrics: list[EvidenceMetric] = []
    seen_names: set[str] = set()
    seen_docs: set[str] = set()
    for bucket_name in ("macro", "market_structure", "asset_specific", "latest_catalyst"):
        for item in buckets[bucket_name].items:
            doc_id = _parent_doc_id(item)
            if doc_id in seen_docs:
                continue
            values = _METRIC_VALUE_RE.findall(str(item.chunk or ""))
            if not values:
                continue
            name = _shorten(item.title or item.source or "Metric", 48)
            if name in seen_names:
                continue
            metrics.append(
                EvidenceMetric(
                    name=name,
                    value=", ".join(values[:2]),
                    as_of=str(item.date or "").strip(),
                    context=_metric_context(topic_plan, bucket_name),
                    evidence_doc_ids=[doc_id] if doc_id else [],
                )
            )
            seen_names.add(name)
            seen_docs.add(doc_id)
            if len(metrics) >= 8:
                return metrics
    return metrics


def build_evidence_pack(
    question: str,
    theme: str,
    context: list[RetrievalItem],
    related_tickers: list[str],
    topic_plan: TopicPlan,
) -> EvidencePack:
    buckets = {
        "macro": EvidenceBucket("macro", "Macro"),
        "asset_specific": EvidenceBucket("asset_specific", "Asset-specific"),
        "market_structure": EvidenceBucket("market_structure", "Market-structure / valuation"),
        "latest_catalyst": EvidenceBucket("latest_catalyst", "Latest catalyst / news"),
    }
    seen_doc_ids: set[str] = set()
    cited_doc_ids: list[str] = []
    for item in context:
        doc_id = _parent_doc_id(item)
        if doc_id and doc_id not in seen_doc_ids:
            seen_doc_ids.add(doc_id)
            cited_doc_ids.append(doc_id)
        for bucket_name in _classify_bucket_names(item, topic_plan, question, theme, related_tickers):
            buckets[bucket_name].add(item)
    missing_buckets = [name for name, bucket in buckets.items() if not bucket.items]
    coverage_notes = []
    if missing_buckets:
        coverage_notes.append("Missing evidence buckets: " + ", ".join(name.replace("_", " ") for name in missing_buckets))
    metrics = _extract_metric_candidates(topic_plan, buckets)
    if not metrics:
        coverage_notes.append("No structured metric candidates extracted from current evidence.")
    return EvidencePack(
        asset_class=topic_plan.asset_class,
        buckets=buckets,
        metrics=metrics,
        cited_doc_ids=cited_doc_ids,
        missing_buckets=missing_buckets,
        coverage_notes=coverage_notes,
    )


def _trim_existing_output(existing_output: dict[str, Any] | None, fields: list[str]) -> str:
    if not existing_output:
        return ""
    subset = {field: existing_output.get(field) for field in fields if field in existing_output}
    return _shorten(json.dumps(subset, ensure_ascii=False), MAX_EXISTING_JSON_CHARS)


def _selected_buckets(evidence_pack: EvidencePack, *, phase: str, focus_buckets: list[str] | None = None) -> list[EvidenceBucket]:
    names = focus_buckets or ["macro", "asset_specific", "market_structure", "latest_catalyst"]
    max_docs = 1 if phase == "fast" else 2
    selected: list[EvidenceBucket] = []
    for name in names:
        bucket = evidence_pack.buckets[name]
        selected.append(EvidenceBucket(bucket.name, bucket.label, list(bucket.items[:max_docs])))
    return selected


def build_topic_prompt(
    question: str,
    theme: str,
    context: list[RetrievalItem],
    related_tickers: list[str],
    language: str = "ko",
    schema: dict[str, Any] | None = None,
    extra_requirements: str = "",
    *,
    topic_plan: TopicPlan | None = None,
    evidence_pack: EvidencePack | None = None,
    package_name: str = "topic memo",
    existing_output: dict[str, Any] | None = None,
    phase: str = "fast",
    required_fields: list[str] | None = None,
    focus_buckets: list[str] | None = None,
    quant_snapshot: dict[str, Any] | None = None,
) -> tuple[str, int]:
    topic_plan = topic_plan or build_topic_plan(question, theme, related_tickers, context)
    evidence_pack = evidence_pack or build_evidence_pack(question, theme, context, related_tickers, topic_plan)
    fields = list(required_fields or TOPIC_FAST_FIELDS)
    lang = "KOREAN" if language == "ko" else "ENGLISH"
    lang_instruction = (
        "Write every natural-language JSON value in professional Korean using formal business style. "
        "Tickers, company names, source titles, and standard market abbreviations may remain in English."
        if language == "ko"
        else "Write every natural-language JSON value in professional English."
    )
    quant_metrics = key_metrics_from_quant_snapshot(quant_snapshot)
    metric_rows: list[dict[str, Any]] = [
        {
            "name": metric.name,
            "value": metric.value,
            "as_of": metric.as_of or "unknown",
            "context": metric.context,
            "evidence_doc_ids": list(metric.evidence_doc_ids),
        }
        for metric in evidence_pack.metrics
    ]
    metric_rows = quant_metrics + metric_rows
    metrics_preview = (
        "\n".join(
            f"- {metric['name']}: {metric['value']} (as_of={metric.get('as_of') or 'unknown'}; {metric.get('context') or ''}) "
            f"[doc_ids={', '.join(metric.get('evidence_doc_ids') or []) or 'none'}]"
            for metric in metric_rows[:6]
        )
        or "- none"
    )
    quant_block = ""
    if quant_snapshot:
        quant_block = _shorten(json.dumps(quant_snapshot, ensure_ascii=False), 2200)
    prompt_limit = MAX_FAST_PROMPT_CHARS if phase == "fast" else MAX_DEEP_PROMPT_CHARS
    doc_limit = MAX_DOC_CHARS_FAST if phase == "fast" else MAX_DOC_CHARS_DEEP
    existing_json = _trim_existing_output(existing_output, fields)

    prompt = (
        f"LANGUAGE: {lang}\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n"
        f"Question: {question}\n"
        f"Theme: {theme}\n"
        f"Related ticker hints: {', '.join(related_tickers) if related_tickers else 'none'}\n"
        f"Phase: {phase}\n"
        f"Package: {package_name}\n"
        f"Return fields: {', '.join(fields)}\n"
        f"Asset class: {topic_plan.label} ({topic_plan.asset_class})\n"
        f"Playbook focus: {topic_plan.description}\n"
        f"Required sections: {', '.join(topic_plan.required_sections)}\n"
        f"Required metrics: {', '.join(topic_plan.required_metrics)}\n"
        f"Scenario axes: {', '.join(topic_plan.scenario_axes)}\n"
        f"Execution axes: {', '.join(topic_plan.execution_axes)}\n"
        f"Minimums: {json.dumps(topic_plan.minimums, ensure_ascii=False)}\n\n"
        f"{DOMAIN_DECISION_PLAYBOOK}\n\n"
        "Prompt rules:\n"
        "- Use only the supplied evidence. Never invent exact macro or pricing values.\n"
        "- If a deterministic quant snapshot is supplied, treat it as authoritative and interpret it instead of recalculating it.\n"
        "- If any descriptive sentence includes a number or value, state its evidence DATE or make the date basis explicit.\n"
        "- Every bullet must help an investor decide whether the setup is attractive, conditional, or unattractive.\n"
        "- Cite document ids through evidence_doc_ids or cited_doc_ids.\n"
        "- Every key_metrics item must include as_of. Use the evidence DATE, or 'unknown' only when the source date is unavailable.\n"
        "- If evidence is missing, say so in uncertainty or open_questions instead of guessing.\n"
        f"{extra_requirements}\n\n"
        "Evidence metric candidates:\n"
        f"{metrics_preview}\n\n"
    )
    if quant_block:
        prompt += "Deterministic quant snapshot:\n"
        prompt += quant_block + "\n\n"
    if existing_json:
        prompt += "Existing output to keep consistent:\n"
        prompt += existing_json + "\n\n"
    prompt += "Evidence buckets:\n"

    blocks: list[str] = []
    used_doc_ids: set[str] = set()
    for bucket in _selected_buckets(evidence_pack, phase=phase, focus_buckets=focus_buckets):
        header = f"[{bucket.label}]\n"
        if not bucket.items:
            blocks.append(header + "- no evidence available in this bucket\n")
            continue
        bucket_lines = [header]
        for item in bucket.items:
            doc_id = _parent_doc_id(item) or f"doc-{len(used_doc_ids) + 1}"
            snippet = _shorten(item.chunk, doc_limit)
            used_doc_ids.add(doc_id)
            bucket_lines.append(
                f"- ID={doc_id} | SOURCE={item.source} | DATE={item.date} | TITLE={item.title}\n"
                f"  CONTENT={snippet}"
            )
        blocks.append("\n".join(bucket_lines) + "\n")

    prompt += "\n".join(blocks)
    prompt += "\nReturn only the JSON object."
    return prompt[:prompt_limit], len(used_doc_ids)


def _schema_for_fields(fields: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {field: TOPIC_OUTPUT_SCHEMA["properties"][field] for field in fields},
        "required": fields,
    }


def _merge_package_output(base: dict[str, Any], package: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    merged = dict(base)
    for field in fields:
        if field == "cited_doc_ids":
            merged[field] = _coerce_string_list(base.get(field)) + _coerce_string_list(package.get(field))
        else:
            merged[field] = package.get(field, base.get(field))
    return _normalize_topic_response(merged)


def merge_topic_phase_outputs(base: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    fields = [field for field in TOPIC_OUTPUT_SCHEMA["required"] if field in package or field in base]
    if "cited_doc_ids" not in fields:
        fields.append("cited_doc_ids")
    return _merge_package_output(base, package, fields)


def determine_deep_fields(
    payload: dict[str, Any],
    topic_plan: TopicPlan,
    missing_buckets: list[str] | None = None,
) -> list[str]:
    deep_gate = topic_final_gate(payload, minimums=topic_plan.minimums)
    counts = deep_gate["completeness"]["counts"]
    missing = deep_gate["completeness"]["missing"]
    fields: list[str] = []
    if len(payload.get("asset_overview") or []) < 1:
        fields.append("asset_overview")
    if counts["macro_regime"] + counts["rate_structure"] + counts["investment_judgment"] < 2:
        for field in ("macro_regime", "rate_structure", "investment_judgment"):
            if field not in fields:
                fields.append(field)
    if missing.get("scenario_analysis", 0) > 0 and "scenario_analysis" not in fields:
        fields.append("scenario_analysis")
    if missing.get("execution_strategy", 0) > 0 and "execution_strategy" not in fields:
        fields.append("execution_strategy")
    if not str(payload.get("executive_summary") or "").strip():
        fields.append("executive_summary")
    if not str(payload.get("core_thesis") or "").strip():
        fields.append("core_thesis")
    if missing_buckets or not str(payload.get("uncertainty") or "").strip():
        fields.append("uncertainty")
    if "cited_doc_ids" not in fields:
        fields.append("cited_doc_ids")
    return [field for field in TOPIC_DEEP_REPAIR_FIELDS if field in fields] + [field for field in fields if field not in TOPIC_DEEP_REPAIR_FIELDS]


def _local_related_tickers(related_tickers: list[str], evidence_pack: EvidencePack) -> list[dict[str, Any]]:
    ordered: list[str] = []
    seen: set[str] = set()
    for ticker in related_tickers:
        symbol = str(ticker or "").upper().strip()
        if symbol and symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    for bucket in evidence_pack.buckets.values():
        for item in bucket.items:
            symbol = str((item.metadata or {}).get("ticker") or (item.metadata or {}).get("symbol") or "").upper().strip()
            if symbol and symbol not in seen:
                seen.add(symbol)
                ordered.append(symbol)
    return [
        {"ticker": symbol, "role": "proxy", "rationale": "현재 질의를 표현하는 관련 시장 프록시입니다."}
        for symbol in ordered[:8]
    ]


def _local_key_metrics(evidence_pack: EvidencePack, minimum: int, quant_snapshot: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    metrics = []
    seen: set[str] = set()
    for metric in key_metrics_from_quant_snapshot(quant_snapshot):
        key = str(metric.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        metrics.append(metric)
    for metric in evidence_pack.metrics:
        key = str(metric.name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        metrics.append(
            {
                "name": metric.name,
                "value": metric.value,
                "as_of": metric.as_of or "unknown",
                "context": metric.context,
                "evidence_doc_ids": list(metric.evidence_doc_ids),
            }
        )
        if len(metrics) >= max(4, minimum):
            break
    return metrics


def _local_catalyst_timeline(evidence_pack: EvidencePack) -> dict[str, list[str]]:
    near_term = []
    for item in evidence_pack.buckets["latest_catalyst"].items[:3]:
        title = _shorten(item.title or item.chunk, 90)
        if title:
            near_term.append(title)
    return {"near_term": near_term, "mid_term": [], "long_term": []}


def _local_open_questions(topic_plan: TopicPlan, evidence_pack: EvidencePack, existing: list[str] | None = None) -> list[str]:
    questions = list(existing or [])
    if evidence_pack.missing_buckets:
        questions.append("어떤 증거 버킷이 비어 있는지와 추가로 필요한 데이터가 무엇인지 확인해야 합니다.")
    if not evidence_pack.metrics:
        questions.append("정량 지표가 부족해 실제 가격 민감도와 기대값을 더 확인해야 합니다.")
    if topic_plan.asset_class == "rates_bonds":
        questions.append("실질금리와 장단기 곡선 변화가 지속될지 추가 확인이 필요합니다.")
    seen: set[str] = set()
    deduped: list[str] = []
    for question in questions:
        value = str(question).strip()
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped[:4]


def _local_uncertainty(existing: str, evidence_pack: EvidencePack) -> str:
    parts = [str(existing or "").strip()] if str(existing or "").strip() else []
    if evidence_pack.missing_buckets:
        parts.append("일부 증거 버킷이 비어 있어 판단 확신도가 제한됩니다.")
    if not evidence_pack.metrics:
        parts.append("현재 문서에서 구조화 가능한 정량 지표가 충분하지 않습니다.")
    if not parts:
        parts.append("현재 문서 범위 안에서만 판단했기 때문에 추가 데이터에 따라 해석이 달라질 수 있습니다.")
    return " ".join(dict.fromkeys(parts))


def _apply_local_signals(
    payload: dict[str, Any],
    topic_plan: TopicPlan,
    evidence_pack: EvidencePack,
    related_tickers: list[str],
    *,
    minimum_metrics: int,
    quant_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _normalize_topic_response(payload)
    local_metrics = _local_key_metrics(evidence_pack, minimum_metrics, quant_snapshot)
    if local_metrics:
        seen = {str(metric.get("name") or "").strip().lower() for metric in payload["key_metrics"] if isinstance(metric, dict)}
        for metric in local_metrics:
            key = str(metric.get("name") or "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                payload["key_metrics"].append(metric)
    if len(payload["key_metrics"]) < minimum_metrics:
        payload["key_metrics"] = local_metrics
    if not payload["related_tickers"]:
        payload["related_tickers"] = _local_related_tickers(related_tickers, evidence_pack)
    if not any(payload["catalyst_timeline"].values()):
        payload["catalyst_timeline"] = _local_catalyst_timeline(evidence_pack)
    payload["open_questions"] = _local_open_questions(topic_plan, evidence_pack, payload.get("open_questions"))
    payload["uncertainty"] = _local_uncertainty(payload.get("uncertainty", ""), evidence_pack)
    payload["cited_doc_ids"] = _collect_cited_doc_ids(payload)
    return payload


def _backfill_evidence_ids(parsed: dict[str, Any], evidence_pack: EvidencePack) -> dict[str, list[str]]:
    reasons: dict[str, list[str]] = {}
    default_doc_ids = {
        "asset_overview": [_parent_doc_id(item) for item in evidence_pack.buckets["asset_specific"].items if _parent_doc_id(item)],
        "macro_regime": [_parent_doc_id(item) for item in evidence_pack.buckets["macro"].items if _parent_doc_id(item)],
        "rate_structure": [
            _parent_doc_id(item)
            for bucket_name in ("market_structure", "macro")
            for item in evidence_pack.buckets[bucket_name].items
            if _parent_doc_id(item)
        ],
        "investment_judgment": evidence_pack.cited_doc_ids[:2],
        "scenario_analysis": evidence_pack.cited_doc_ids[:2],
        "execution_strategy": evidence_pack.cited_doc_ids[:2],
        "key_drivers": evidence_pack.cited_doc_ids[:2],
        "key_risks": evidence_pack.cited_doc_ids[:2],
        "key_metrics": evidence_pack.cited_doc_ids[:2],
    }

    for field in ("asset_overview", "macro_regime", "rate_structure", "investment_judgment"):
        for index, item in enumerate(parsed.get(field, []) or []):
            if isinstance(item, dict) and not item.get("evidence_doc_ids"):
                item["evidence_doc_ids"] = default_doc_ids[field][:2]
                if not item["evidence_doc_ids"]:
                    reasons.setdefault(field, []).append(f"item {index}: no supporting document in evidence pack")
    for field in ("scenario_analysis", "execution_strategy", "key_drivers", "key_risks", "key_metrics"):
        for index, item in enumerate(parsed.get(field, []) or []):
            if isinstance(item, dict) and not item.get("evidence_doc_ids"):
                item["evidence_doc_ids"] = default_doc_ids[field][:2]
                if not item["evidence_doc_ids"]:
                    reasons.setdefault(field, []).append(f"item {index}: no supporting document in evidence pack")
    parsed["cited_doc_ids"] = _collect_cited_doc_ids(parsed)
    return reasons


def _needs_summary_rewrite(payload: dict[str, Any]) -> bool:
    return not str(payload.get("executive_summary") or "").strip() or not str(payload.get("core_thesis") or "").strip()


def _synthesis_fallback(parsed: dict[str, Any]) -> dict[str, Any]:
    if not parsed.get("executive_summary"):
        summary_parts = []
        if parsed.get("investment_judgment"):
            summary_parts.append(str(parsed["investment_judgment"][0].get("conclusion") or "").strip())
        if not summary_parts and parsed.get("key_drivers"):
            summary_parts.append(str(parsed["key_drivers"][0].get("text") or "").strip())
        parsed["executive_summary"] = " ".join(part for part in summary_parts if part).strip()
    if not parsed.get("core_thesis"):
        if parsed.get("investment_judgment"):
            parsed["core_thesis"] = str(parsed["investment_judgment"][0].get("conclusion") or "").strip()
        elif parsed.get("key_drivers"):
            parsed["core_thesis"] = str(parsed["key_drivers"][0].get("text") or "").strip()
    return parsed


def run_topic_fast_inference(
    question: str,
    theme: str,
    context: list[RetrievalItem],
    model_name: str,
    related_tickers: list[str] | None = None,
    quant_snapshot: dict[str, Any] | None = None,
    output_language: str | None = None,
) -> TopicInferencePhaseResult:
    settings = load_settings()
    resolved = resolve_model_name(model_name, settings)
    language = _coerce_output_language(output_language or getattr(settings, "output_language", "ko"))
    related = related_tickers or []
    topic_plan = build_topic_plan(question, theme, related, context)
    evidence_pack = build_evidence_pack(question, theme, context, related, topic_plan)
    prompt, _ = build_topic_prompt(
        question,
        theme,
        context,
        related,
        language=language,
        topic_plan=topic_plan,
        evidence_pack=evidence_pack,
        package_name="topic fast pass",
        phase="fast",
        required_fields=TOPIC_FAST_FIELDS,
        quant_snapshot=quant_snapshot,
        extra_requirements=(
            "- Aim for a fast but decision-useful first pass.\n"
            "- Prefer concise sections and at least 2 scenarios when evidence allows.\n"
            "- Keep execution_strategy brief but actionable.\n"
        ),
    )
    parsed, latency, retries = _run_generation_phase(
        base_url=settings.ollama_base_url,
        model_name=resolved,
        prompt=prompt,
        expected_language=language,
        schema=_schema_for_fields(TOPIC_FAST_FIELDS),
        required_fields=TOPIC_FAST_FIELDS,
        num_ctx=DEFAULT_NUM_CTX,
        primary_predict=DEFAULT_NUM_PREDICT,
        retry_predict=RETRY_NUM_PREDICT,
    )
    payload = _apply_local_signals(parsed, topic_plan, evidence_pack, related, minimum_metrics=2, quant_snapshot=quant_snapshot)
    missing_evidence_reasons = _backfill_evidence_ids(payload, evidence_pack)
    payload = _normalize_topic_response(payload)
    payload["_meta"] = {
        "phase": "fast",
        "primary_model": resolved,
        "producing_model": resolved,
        "retry_count": retries,
        "total_latency_s": round(latency, 2),
        "prompt_char_count": len(prompt),
        "chunks_used": len(evidence_pack.cited_doc_ids),
        "asset_class": topic_plan.asset_class,
        "evidence_bucket_counts": {name: len(bucket.items) for name, bucket in evidence_pack.buckets.items()},
        "missing_evidence_buckets": list(evidence_pack.missing_buckets),
        "coverage_notes": list(evidence_pack.coverage_notes),
        "missing_evidence_reasons": missing_evidence_reasons,
        "quant_snapshot": quant_snapshot or {},
        "substituted_buckets": list((quant_snapshot or {}).get("substituted_buckets") or []),
    }
    fast_gate = topic_fast_gate(payload, preferred_language=language)
    final_gate = topic_final_gate(payload, minimums=topic_plan.minimums, preferred_language=language)
    return TopicInferencePhaseResult(
        payload=payload,
        topic_plan=topic_plan,
        evidence_pack=evidence_pack,
        latency_s=latency,
        retry_count=retries,
        prompt_char_count=len(prompt),
        gate=fast_gate,
        final_gate=final_gate,
        selected_fields=list(TOPIC_FAST_FIELDS),
    )


def run_topic_deep_inference(
    question: str,
    theme: str,
    context: list[RetrievalItem],
    model_name: str,
    related_tickers: list[str] | None = None,
    *,
    existing_output: dict[str, Any],
    topic_plan: TopicPlan | None = None,
    deep_reason: str = "",
    quant_snapshot: dict[str, Any] | None = None,
    output_language: str | None = None,
) -> TopicInferencePhaseResult:
    settings = load_settings()
    resolved = resolve_model_name(model_name, settings)
    language = _coerce_output_language(output_language or getattr(settings, "output_language", "ko"))
    related = related_tickers or []
    topic_plan = topic_plan or build_topic_plan(question, theme, related, context)
    evidence_pack = build_evidence_pack(question, theme, context, related, topic_plan)
    fields = determine_deep_fields(existing_output, topic_plan, evidence_pack.missing_buckets)
    if not fields:
        payload = _apply_local_signals(
            existing_output,
            topic_plan,
            evidence_pack,
            related,
            minimum_metrics=topic_plan.minimums.get("key_metrics", 1),
            quant_snapshot=quant_snapshot,
        )
        payload["_meta"] = {
            "phase": "final",
            "primary_model": resolved,
            "producing_model": resolved,
            "retry_count": 0,
            "total_latency_s": 0.0,
            "prompt_char_count": 0,
            "chunks_used": len(evidence_pack.cited_doc_ids),
            "asset_class": topic_plan.asset_class,
            "evidence_bucket_counts": {name: len(bucket.items) for name, bucket in evidence_pack.buckets.items()},
            "missing_evidence_buckets": list(evidence_pack.missing_buckets),
            "coverage_notes": list(evidence_pack.coverage_notes),
            "quant_snapshot": quant_snapshot or {},
            "substituted_buckets": list((quant_snapshot or {}).get("substituted_buckets") or []),
        }
        fast_gate = topic_fast_gate(payload, preferred_language=language)
        final_gate = topic_final_gate(payload, minimums=topic_plan.minimums, preferred_language=language)
        return TopicInferencePhaseResult(
            payload=payload,
            topic_plan=topic_plan,
            evidence_pack=evidence_pack,
            latency_s=0.0,
            retry_count=0,
            prompt_char_count=0,
            gate=fast_gate,
            final_gate=final_gate,
            selected_fields=[],
        )

    focus_buckets = evidence_pack.missing_buckets or None
    prompt, _ = build_topic_prompt(
        question,
        theme,
        context,
        related,
        language=language,
        topic_plan=topic_plan,
        evidence_pack=evidence_pack,
        package_name="topic deep repair",
        existing_output=existing_output,
        phase="deep",
        required_fields=fields,
        focus_buckets=focus_buckets,
        quant_snapshot=quant_snapshot,
        extra_requirements=(
            "- Repair only the requested fields.\n"
            "- Expand missing scenarios or execution strategy only where evidence supports it.\n"
            f"- Deep reason: {deep_reason or 'final quality completion'}.\n"
        ),
    )
    parsed, latency, retries = _run_generation_phase(
        base_url=settings.ollama_base_url,
        model_name=resolved,
        prompt=prompt,
        expected_language=language,
        schema=_schema_for_fields(fields),
        required_fields=fields,
        num_ctx=DEEP_NUM_CTX,
        primary_predict=DEEP_NUM_PREDICT,
        retry_predict=DEEP_RETRY_NUM_PREDICT,
    )
    merged = merge_topic_phase_outputs(existing_output, parsed)
    merged = _apply_local_signals(
        merged,
        topic_plan,
        evidence_pack,
        related,
        minimum_metrics=topic_plan.minimums.get("key_metrics", 1),
        quant_snapshot=quant_snapshot,
    )
    if _needs_summary_rewrite(merged):
        merged = _synthesis_fallback(merged)
    missing_evidence_reasons = _backfill_evidence_ids(merged, evidence_pack)
    merged = _normalize_topic_response(merged)
    merged["_meta"] = {
        "phase": "final",
        "primary_model": resolved,
        "producing_model": resolved,
        "retry_count": retries,
        "total_latency_s": round(latency, 2),
        "prompt_char_count": len(prompt),
        "chunks_used": len(evidence_pack.cited_doc_ids),
        "asset_class": topic_plan.asset_class,
        "evidence_bucket_counts": {name: len(bucket.items) for name, bucket in evidence_pack.buckets.items()},
        "missing_evidence_buckets": list(evidence_pack.missing_buckets),
        "coverage_notes": list(evidence_pack.coverage_notes),
        "missing_evidence_reasons": missing_evidence_reasons,
        "quant_snapshot": quant_snapshot or {},
        "substituted_buckets": list((quant_snapshot or {}).get("substituted_buckets") or []),
    }
    fast_gate = topic_fast_gate(merged, preferred_language=language)
    final_gate = topic_final_gate(merged, minimums=topic_plan.minimums, preferred_language=language)
    return TopicInferencePhaseResult(
        payload=merged,
        topic_plan=topic_plan,
        evidence_pack=evidence_pack,
        latency_s=latency,
        retry_count=retries,
        prompt_char_count=len(prompt),
        gate=fast_gate,
        final_gate=final_gate,
        selected_fields=fields,
    )


def run_topic_inference(
    question: str,
    theme: str,
    context: list[RetrievalItem],
    model_name: str,
    related_tickers: list[str] | None = None,
) -> dict[str, Any]:
    fast = run_topic_fast_inference(question, theme, context, model_name, related_tickers)
    if fast.final_gate["ok"] and not fast.evidence_pack.missing_buckets:
        payload = dict(fast.payload)
        payload["_meta"] = {
            **payload.get("_meta", {}),
            "phase": "final",
            "fast_gate": fast.gate,
            "final_gate": fast.final_gate,
        }
        return payload

    deep = run_topic_deep_inference(
        question,
        theme,
        context,
        model_name,
        related_tickers,
        existing_output=fast.payload,
        topic_plan=fast.topic_plan,
        deep_reason="wrapper completion",
    )
    payload = dict(deep.payload)
    payload["_meta"] = {
        **payload.get("_meta", {}),
        "phase": "final",
        "fast_gate": fast.gate,
        "final_gate": deep.final_gate,
    }
    return payload
