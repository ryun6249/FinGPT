from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.schemas.request import SupportedInferenceRoute, SupportedOutputLanguage, _coerce_output_language
from core.schemas.response import (
    CatalystTimeline,
    Citation,
    ConfidenceRationale,
    DecisionView,
    EvidenceQuality,
    ExecutionMeta,
    KeyMetric,
    MonitoringPlan,
    QualityMetrics,
    RiskManagement,
)
from core.schemas.retrieval import RetrievalItem


class TopicRequest(BaseModel):
    question: str
    theme: Optional[str] = None
    related_tickers: list[str] = Field(default_factory=list, max_length=8)
    lookback_days: int = 60
    top_k: int = 12
    model: SupportedInferenceRoute = "qwen"
    output_dir: Optional[str] = None
    output_language: SupportedOutputLanguage = Field(
        default="ko",
        description="Per-request output language for topic analysis and reports.",
    )
    scenario_simulation_enabled: Optional[bool] = Field(
        default=None,
        description="Optional per-request override for the default-off scenario simulation layer.",
    )

    @field_validator("output_language", mode="before")
    @classmethod
    def _clean_output_language(cls, value) -> str:
        return _coerce_output_language(value)


class KeyDriver(BaseModel):
    text: str
    direction: Literal["supporting", "opposing"]
    evidence_doc_ids: list[str] = Field(default_factory=list)


class TickerTouchpoint(BaseModel):
    ticker: str
    role: Literal["beneficiary", "at_risk", "proxy", "peer"]
    rationale: str


class DecisionSection(BaseModel):
    title: str = Field(default="", description="Section title.")
    bullets: list[str] = Field(default_factory=list, description="Decision-useful bullets grounded in evidence.")
    conclusion: str = Field(default="", description="Short investment implication for this section.")
    evidence_doc_ids: list[str] = Field(default_factory=list)


class ScenarioAnalysis(BaseModel):
    scenario: str = Field(default="", description="Scenario name.")
    probability: str = Field(default="", description="Qualitative probability or likelihood band.")
    expected_outcome: str = Field(default="", description="Macro / rates outcome expected in this scenario.")
    asset_implication: str = Field(default="", description="Implication for the target asset or ETF.")
    decision_read: str = Field(default="", description="Investor action or interpretation under this scenario.")
    evidence_doc_ids: list[str] = Field(default_factory=list)


class ExecutionStrategy(BaseModel):
    strategy: str = Field(default="", description="Implementation approach.")
    trigger: str = Field(default="", description="Condition that makes the strategy appropriate.")
    rationale: str = Field(default="", description="Why this strategy fits the evidence.")
    risk_control: str = Field(default="", description="How to control downside or timing risk.")
    evidence_doc_ids: list[str] = Field(default_factory=list)


class TopicResponse(BaseModel):
    question: str
    theme: str
    mode: Literal["sector_macro", "concept"] = "concept"
    status: Literal["success", "partial", "failed"] = "success"
    error_metadata: Optional[str] = None
    executive_summary: str
    core_thesis: str
    asset_overview: list[DecisionSection] = Field(default_factory=list)
    macro_regime: list[DecisionSection] = Field(default_factory=list)
    rate_structure: list[DecisionSection] = Field(default_factory=list)
    scenario_analysis: list[ScenarioAnalysis] = Field(default_factory=list)
    investment_judgment: list[DecisionSection] = Field(default_factory=list)
    execution_strategy: list[ExecutionStrategy] = Field(default_factory=list)
    key_drivers: list[KeyDriver] = Field(default_factory=list)
    key_risks: list[KeyDriver] = Field(default_factory=list)
    related_tickers: list[TickerTouchpoint] = Field(default_factory=list)
    key_metrics: list[KeyMetric] = Field(default_factory=list)
    catalyst_timeline: CatalystTimeline = Field(default_factory=CatalystTimeline)
    open_questions: list[str] = Field(default_factory=list)
    uncertainty: str = ""
    citations: list[Citation] = Field(default_factory=list)
    raw_context: list[RetrievalItem] = Field(default_factory=list)
    execution_meta: Optional[ExecutionMeta] = None
    decision_view: DecisionView = Field(default_factory=DecisionView)
    monitoring_plan: MonitoringPlan = Field(default_factory=MonitoringPlan)
    risk_management: RiskManagement = Field(default_factory=RiskManagement)
    confidence_rationale: ConfidenceRationale = Field(default_factory=ConfidenceRationale)
    quality_metrics: QualityMetrics = Field(default_factory=QualityMetrics)
    evidence_quality: dict[str, EvidenceQuality] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
