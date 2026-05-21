from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RiskMode = Literal["company", "watchlist", "portfolio"]
RiskLevel = Literal["low", "moderate", "elevated", "high", "unknown"]
FreshnessState = Literal["fresh", "partial", "stale", "missing", "unknown"]
RiskCoverageScope = Literal["company_full", "asset_proxy", "blocked", "unknown"]
RiskVectorName = Literal[
    "company_solvency",
    "company_cash_flow_quality",
    "company_earnings_quality",
    "valuation_fragility",
    "market_behavior",
    "macro_policy_rates",
    "macro_growth_inflation",
    "credit_liquidity",
    "transmission_sensitivity",
    "portfolio_concentration",
    "data_integrity",
]
RiskCoverageDomain = Literal["input", "company", "macro", "scenario", "forecast", "service", "evidence"]


class RiskPosition(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    weight: float = Field(..., ge=0.0, le=1.0)
    market_value: float | None = Field(default=None, ge=0.0)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        cleaned = str(value or "").strip().upper()
        if not cleaned:
            raise ValueError("ticker is required")
        return cleaned


class RiskWorkbenchRequest(BaseModel):
    mode: RiskMode = "company"
    tickers: list[str] = Field(default_factory=list, max_length=25)
    positions: list[RiskPosition] | None = None
    market: str = "US"
    lookback_days: int = Field(default=756, ge=63, le=2520)
    scenario_set: Literal[
        "base_adverse_severe",
        "rates_credit_liquidity",
        "inflation_growth_policy",
    ] = "base_adverse_severe"
    include_sec: bool = True
    include_macro_scenarios: bool = True
    force_refresh: bool = False
    output_language: Literal["ko", "en"] = "ko"

    @field_validator("market")
    @classmethod
    def normalize_market(cls, value: str) -> str:
        return str(value or "US").strip().upper() or "US"

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "RiskWorkbenchRequest":
        normalized = [ticker.strip().upper() for ticker in self.tickers if ticker and ticker.strip()]
        self.tickers = list(dict.fromkeys(normalized))
        if self.mode == "company" and len(self.tickers) != 1:
            raise ValueError("company mode requires exactly one ticker")
        if self.mode == "watchlist" and not self.tickers:
            raise ValueError("watchlist mode requires at least one ticker")
        if self.mode == "portfolio":
            if not self.positions:
                raise ValueError("portfolio mode requires positions")
            seen: set[str] = set()
            duplicates: list[str] = []
            for position in self.positions:
                if position.ticker in seen:
                    duplicates.append(position.ticker)
                seen.add(position.ticker)
            if duplicates:
                raise ValueError(f"portfolio mode duplicate positions: {', '.join(sorted(set(duplicates)))}")
            if sum(position.weight for position in self.positions) <= 0:
                raise ValueError("portfolio mode requires positive total weight")
            self.tickers = [position.ticker for position in self.positions]
        return self


class RiskEvidenceItem(BaseModel):
    evidence_id: str
    source: str
    label: str
    value: str | float | int | None = None
    as_of: datetime | None = None
    freshness: FreshnessState = "unknown"
    url: str | None = None
    notes: list[str] = Field(default_factory=list)


class RiskVector(BaseModel):
    vector: RiskVectorName
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=100.0)
    direction: Literal["higher_is_riskier"] = "higher_is_riskier"
    top_drivers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    decision_usable: bool = True


class RiskDataQuality(BaseModel):
    decision_usable: bool = True
    freshness: FreshnessState = "unknown"
    missing_inputs: list[str] = Field(default_factory=list)
    stale_inputs: list[str] = Field(default_factory=list)
    provider_warnings: list[str] = Field(default_factory=list)
    penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    confidence_penalty: float = Field(default=0.0, ge=0.0, le=100.0)


class RiskCompanyProfile(BaseModel):
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    asset_class: str = "equity"
    coverage_scope: RiskCoverageScope = "unknown"
    coverage_notes: list[str] = Field(default_factory=list)
    risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    vectors: list[RiskVector] = Field(default_factory=list)
    primary_drivers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    decision_usable: bool = True


class RiskMacroBackdrop(BaseModel):
    regime: str = "unknown"
    risk_level: RiskLevel = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    vectors: list[RiskVector] = Field(default_factory=list)
    primary_pressures: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskTransmissionChannel(BaseModel):
    channel: str
    pressure: RiskLevel
    sensitivity: float = Field(..., ge=0.0, le=1.0)
    risk_delta: float = Field(..., ge=0.0, le=100.0)
    affected_subjects: list[str] = Field(default_factory=list)
    mechanism: str
    evidence_refs: list[str] = Field(default_factory=list)


class RiskScenarioResult(BaseModel):
    scenario_id: str
    label: str
    severity: Literal["base", "adverse", "severe"]
    risk_index_delta: float
    projected_risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    top_damage_channels: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RiskPortfolioOverlay(BaseModel):
    weighted_risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    concentration_penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    largest_contributors: list[str] = Field(default_factory=list)
    scenario_exposures: list[RiskScenarioResult] = Field(default_factory=list)


class RiskDriverContribution(BaseModel):
    driver: str
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    contribution: float | None = Field(default=None, ge=0.0, le=100.0)
    level: RiskLevel


class RiskInputPositionReceipt(BaseModel):
    ticker: str
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    coverage_scope: RiskCoverageScope = "unknown"
    decision_usable: bool = True


class RiskInputReceipt(BaseModel):
    mode: RiskMode = "company"
    subjects: list[str] = Field(default_factory=list)
    subject_count: int = Field(default=0, ge=0)
    market: str = "US"
    scenario_set: str = "base_adverse_severe"
    lookback_days: int = 756
    output_language: Literal["ko", "en"] = "ko"
    normalized_positions: list[RiskInputPositionReceipt] = Field(default_factory=list)
    weight_sum: float | None = Field(default=None, ge=0.0)
    status: Literal["ok", "review", "blocked"] = "review"
    compatibility_notes: list[str] = Field(default_factory=list)
    replay_notes: list[str] = Field(default_factory=list)


class RiskCalculationPolicy(BaseModel):
    score_direction: Literal["higher_is_riskier"] = "higher_is_riskier"
    version: str = "risk-workbench-v1"
    weights: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskDecisionBrief(BaseModel):
    summary: str = ""
    review_questions: list[str] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    deployment_notes: list[str] = Field(default_factory=list)


class RiskDecisionPath(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    headline: str = ""
    primary_action: str = ""
    primary_handoff_label: str = ""
    primary_handoff_href: str = "/ui/#risk"
    ml_validation_label: str | None = None
    ml_validation_href: str | None = None
    service_gate: Literal["ready", "review_required", "blocked"] = "review_required"
    evidence_refs: list[str] = Field(default_factory=list)


class RiskDecisionQuality(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    label: str = ""
    basis: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_best_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskDecisionCompassStep(BaseModel):
    step_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    instruction: str = ""
    target: str = ""
    href: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class RiskDecisionCompass(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    headline: str = ""
    primary_focus: str = ""
    next_step: str = ""
    service_hint: str = ""
    steps: list[RiskDecisionCompassStep] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskEvidenceCoverageItem(BaseModel):
    coverage_id: str
    domain: RiskCoverageDomain
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    subject: str = ""
    coverage_scope: str = ""
    evidence_count: int = Field(default=0, ge=0)
    freshness: FreshnessState = "unknown"
    impact: str = ""
    next_step: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskEvidenceCoverage(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    covered_domains: list[str] = Field(default_factory=list)
    review_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    items: list[RiskEvidenceCoverageItem] = Field(default_factory=list)


class RiskCompatibilityRow(BaseModel):
    subject: str
    coverage_scope: RiskCoverageScope = "unknown"
    status: Literal["ok", "review", "blocked"] = "review"
    supported_workflows: list[str] = Field(default_factory=list)
    blocked_workflows: list[str] = Field(default_factory=list)
    forecast_launch_href: str | None = None
    decision_note: str = ""
    next_step: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskCompatibilityMatrix(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    summary: str = ""
    rows: list[RiskCompatibilityRow] = Field(default_factory=list)
    service_note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskActionItem(BaseModel):
    action_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    rationale: str = ""
    next_step: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskMonitoringTrigger(BaseModel):
    trigger_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    current_state: str = ""
    trigger_condition: str = ""
    rationale: str = ""
    next_step: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskPriorityCell(BaseModel):
    rank: int = Field(..., ge=1)
    subject: str
    vector: str
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    level: RiskLevel = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    reason: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskConfidenceFactor(BaseModel):
    factor_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "ok"
    impact: float = Field(default=0.0, ge=0.0, le=100.0)
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskHandoffItem(BaseModel):
    handoff_id: str
    label: str
    target_tab: Literal["risk", "macro", "quantamental", "ml_forecast", "quant_lab", "ai_portfolio"]
    href: str
    status: Literal["ok", "review", "blocked"] = "review"
    priority: int = Field(default=3, ge=1, le=5)
    reason: str = ""
    next_step: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RiskMlForecastPrefill(BaseModel):
    ticker: str
    benchmark: str = "QQQ"
    horizon_days: int | None = Field(default=None, ge=1, le=756)
    validation_method: str = "walk_forward"
    target_type: str = "forward_return"
    include_macro: bool = False
    include_cross_asset: bool = False
    source_risk_input_hash: str | None = None


class RiskMlValidationTest(BaseModel):
    test_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    priority: int = Field(default=3, ge=1, le=5)
    test_type: Literal[
        "walk_forward",
        "leakage_check",
        "scenario_backtest",
        "asset_proxy_validation",
        "portfolio_overlay",
        "data_gate_recheck",
    ] = "walk_forward"
    target_tickers: list[str] = Field(default_factory=list)
    horizon_days: int | None = Field(default=None, ge=1, le=756)
    rationale: str = ""
    setup_notes: str = ""
    pass_criteria: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    forecast_prefill: RiskMlForecastPrefill | None = None
    launch_href: str | None = None


class RiskForecastValidationPlan(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    primary_test_id: str | None = None
    primary_label: str = ""
    primary_launch_href: str | None = None
    run_order: list[str] = Field(default_factory=list)
    readiness_note: str = ""
    experiment_controls: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskServiceReadiness(BaseModel):
    status: Literal["ready", "review_required", "blocked"] = "review_required"
    deployment_target: str = "api_service"
    checklist: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class RiskRunLineage(BaseModel):
    service_version: str = "risk-workbench-v1"
    scenario_set: str = "base_adverse_severe"
    lookback_days: int = 756
    subjects: list[str] = Field(default_factory=list)
    subject_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    freshness_counts: dict[str, int] = Field(default_factory=dict)
    adapter_statuses: dict[str, str] = Field(default_factory=dict)
    missing_input_count: int = Field(default=0, ge=0)
    stale_input_count: int = Field(default=0, ge=0)
    provider_warning_count: int = Field(default=0, ge=0)
    replay_fields: list[str] = Field(default_factory=list)


class RiskReleaseCheck(BaseModel):
    check_id: str
    label: str
    status: Literal["ok", "review", "blocked"] = "review"
    evidence_refs: list[str] = Field(default_factory=list)
    next_step: str = ""


class RiskReleasePacket(BaseModel):
    status: Literal["ready", "review_required", "blocked"] = "review_required"
    deployment_target: str = "local_api_service"
    contract_version: str = "risk-release-packet-v1"
    api_routes: list[str] = Field(default_factory=list)
    ui_routes: list[str] = Field(default_factory=list)
    required_audit_fields: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    deployment_checks: list[RiskReleaseCheck] = Field(default_factory=list)
    rollback_triggers: list[str] = Field(default_factory=list)
    data_dependencies: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RiskAiOutputControls(BaseModel):
    status: Literal["ok", "review", "blocked"] = "review"
    language: Literal["ko", "en"] = "ko"
    grounding_summary: str = ""
    required_evidence_refs: list[str] = Field(default_factory=list)
    allowed_claims: list[str] = Field(default_factory=list)
    blocked_claims: list[str] = Field(default_factory=list)
    citation_policy: list[str] = Field(default_factory=list)
    review_instructions: list[str] = Field(default_factory=list)
    prompt_context: list[str] = Field(default_factory=list)


class RiskWorkbenchResponse(BaseModel):
    risk_run_id: str
    input_hash: str
    mode: RiskMode
    risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=100.0)
    decision_usable: bool
    as_of: datetime
    primary_drivers: list[str] = Field(default_factory=list)
    driver_contributions: list[RiskDriverContribution] = Field(default_factory=list)
    risk_vectors: list[RiskVector] = Field(default_factory=list)
    company_profiles: list[RiskCompanyProfile] = Field(default_factory=list)
    macro_backdrop: RiskMacroBackdrop
    transmission_channels: list[RiskTransmissionChannel] = Field(default_factory=list)
    scenario_matrix: list[RiskScenarioResult] = Field(default_factory=list)
    portfolio_overlay: RiskPortfolioOverlay | None = None
    evidence: list[RiskEvidenceItem] = Field(default_factory=list)
    data_quality: RiskDataQuality
    input_receipt: RiskInputReceipt = Field(default_factory=RiskInputReceipt)
    calculation_policy: RiskCalculationPolicy
    decision_brief: RiskDecisionBrief = Field(default_factory=RiskDecisionBrief)
    decision_path: RiskDecisionPath = Field(default_factory=RiskDecisionPath)
    decision_quality: RiskDecisionQuality = Field(default_factory=RiskDecisionQuality)
    decision_compass: RiskDecisionCompass = Field(default_factory=RiskDecisionCompass)
    evidence_coverage: RiskEvidenceCoverage = Field(default_factory=RiskEvidenceCoverage)
    compatibility_matrix: RiskCompatibilityMatrix = Field(default_factory=RiskCompatibilityMatrix)
    action_checklist: list[RiskActionItem] = Field(default_factory=list)
    monitoring_triggers: list[RiskMonitoringTrigger] = Field(default_factory=list)
    priority_map: list[RiskPriorityCell] = Field(default_factory=list)
    confidence_factors: list[RiskConfidenceFactor] = Field(default_factory=list)
    handoff_queue: list[RiskHandoffItem] = Field(default_factory=list)
    ml_validation_tests: list[RiskMlValidationTest] = Field(default_factory=list)
    forecast_validation_plan: RiskForecastValidationPlan = Field(default_factory=RiskForecastValidationPlan)
    service_readiness: RiskServiceReadiness = Field(default_factory=RiskServiceReadiness)
    run_lineage: RiskRunLineage = Field(default_factory=RiskRunLineage)
    release_packet: RiskReleasePacket = Field(default_factory=RiskReleasePacket)
    ai_output_controls: RiskAiOutputControls = Field(default_factory=RiskAiOutputControls)
    not_investment_advice: bool = True
