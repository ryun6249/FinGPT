from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.schemas.forecast import BacktestConfig, FeatureConfig, ForecastUniverseRankingMetric, ModelConfig, SignalConfig, TargetConfig, ValidationConfig


FreshnessStatus = Literal["fresh", "stale", "unknown"]
ProviderEntitlementStatus = Literal["ok", "warning", "entitlement_required", "unavailable", "unknown"]
QuantStatus = Literal["success", "partial", "failed", "empty"]
ResearchScoreStatus = Literal["disabled", "fresh", "expired", "sparse_evidence", "unavailable", "invalid"]
FreshnessProfile = Literal["research_default", "decision_review", "historical_lab"]
QuantModelRunMode = Literal["single_asset", "universe_per_asset", "cross_sectional_rank"]
StrategyResearchStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "pending",
    "accepted",
    "rejected",
    "archived",
]
StrategyOptimizationMethod = Literal["grid_search", "random_search", "bayesian"]


class ProviderStatus(BaseModel):
    provider: str
    status: str = "unknown"
    entitlement_status: ProviderEntitlementStatus = "unknown"
    latency_ms: Optional[float] = None
    cache_hit: Optional[bool] = None
    stale_after: Optional[str] = None
    quality_score: Optional[float] = None
    detail: str = ""


class DataFreshnessAudit(BaseModel):
    as_of: str = "unknown"
    freshness_status: FreshnessStatus = "unknown"
    source: str = ""
    evidence_doc_ids: list[str] = Field(default_factory=list)
    missing_reason: str = ""


class QuantMetric(BaseModel):
    name: str
    value: str
    unit: str = ""
    as_of: str = "unknown"
    context: str = ""
    source: str = "deterministic_quant"
    freshness_status: FreshnessStatus = "unknown"
    evidence_doc_ids: list[str] = Field(default_factory=list)


class QuantSnapshot(BaseModel):
    asset_class: str
    target: str
    generated_at: str
    metrics: list[QuantMetric] = Field(default_factory=list)
    duration_or_proxy: Optional[dict[str, Any]] = None
    rate_shock_scenarios: list[dict[str, Any]] = Field(default_factory=list)
    factor_exposures: dict[str, Any] = Field(default_factory=dict)
    stress_table: list[dict[str, Any]] = Field(default_factory=list)
    substituted_buckets: list[str] = Field(default_factory=list)
    missing_axes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ModelCapabilityProfile(BaseModel):
    route: str
    resolved_model: str
    json_reliability: Literal["high", "medium", "low"]
    korean_reliability: Literal["high", "medium", "low"]
    context_window: int
    structured_output_support: bool
    finance_reasoning: Literal["high", "medium", "low"]
    latency_profile: Literal["fast", "medium", "slow", "unknown"]
    gpu_required: bool = False
    recommended_tasks: list[str] = Field(default_factory=list)
    restricted_tasks: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    run_kind: str
    route: str
    asset_class: str = ""
    target: str = ""
    question_hash: str = ""
    generated_at: str = ""
    data_sources: list[str] = Field(default_factory=list)
    model_route: str = ""
    validation_checks: dict[str, Any] = Field(default_factory=dict)


def _clean_tickers(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value.replace(",", " ").split() if isinstance(value, str) else list(value)
    seen: set[str] = set()
    tickers: list[str] = []
    for item in raw:
        ticker = str(item or "").strip().upper()
        if ticker and ticker not in seen:
            tickers.append(ticker)
            seen.add(ticker)
    return tickers


class QuantRunDiagnostics(BaseModel):
    lookahead_safe: bool = True
    signal_shift_bars: int = 1
    execution_assumption: str = "next_bar_close"
    data_source: str = "data_mart:prices_daily"
    freshness_policy: dict[str, Any] = Field(default_factory=dict)
    missing_assets: list[str] = Field(default_factory=list)
    stale_assets: list[str] = Field(default_factory=list)
    excluded_assets: list[str] = Field(default_factory=list)
    price_counts: dict[str, int] = Field(default_factory=dict)
    latest_price_dates: dict[str, str] = Field(default_factory=dict)
    expected_latest_date: str = "unknown"
    market_calendar_lag_days: dict[str, int] = Field(default_factory=dict)
    asset_freshness: dict[str, dict[str, Any]] = Field(default_factory=dict)
    research_score_used: bool = False
    research_score_status: ResearchScoreStatus = "disabled"
    research_score_provenance: dict[str, dict[str, Any]] = Field(default_factory=dict)
    fingpt_forecaster_signals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class QuantTradeEvent(BaseModel):
    signal_date: str
    execution_date: str
    ticker: str
    previous_weight: float = 0.0
    target_weight: float = 0.0
    delta_weight: float = 0.0
    price: float | None = None
    cost: float = 0.0
    slippage_bps: float = 0.0
    transaction_cost_bps: float = 0.0
    reason: str = "rebalance"
    selected: bool | None = None
    score: float | None = None
    diagnostics: list[str] = Field(default_factory=list)


class QuantArtifactManifest(BaseModel):
    run_id: str
    root: str
    manifest: str
    config: str = ""
    metrics: str = ""
    diagnostics: str = ""
    equity_curve: str = ""
    drawdown_curve: str = ""
    trades: str = ""
    signals: str = ""
    weights: str = ""


class QuantFeatureSpec(BaseModel):
    id: str
    lookback: int | None = Field(default=None, ge=1, le=5000)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def _clean_id(cls, value: Any) -> str:
        return str(value or "").strip().lower()


class QuantFeaturePreviewRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    start_date: str | None = None
    end_date: str | None = None
    features: list[QuantFeatureSpec] = Field(default_factory=list)
    freshness_profile: FreshnessProfile = "research_default"
    require_fresh_prices: bool = False
    max_market_calendar_lag_days: int = Field(default=3, ge=0, le=30)

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_request_tickers(cls, value: Any) -> list[str]:
        return _clean_tickers(value)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_benchmark(cls, value: Any) -> str:
        return str(value or "SPY").strip().upper() or "SPY"

    @field_validator("freshness_profile", mode="before")
    @classmethod
    def _clean_freshness_profile(cls, value: Any) -> str:
        clean = str(value or "research_default").strip().lower()
        return clean if clean in {"research_default", "decision_review", "historical_lab"} else "research_default"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


class QuantFeatureRow(BaseModel):
    ticker: str
    as_of: str
    source: str = "data_mart:prices_daily"
    features: dict[str, float | None] = Field(default_factory=dict)
    freshness_status: FreshnessStatus = "unknown"
    diagnostics: list[str] = Field(default_factory=list)


class QuantFeaturePreviewResponse(BaseModel):
    status: QuantStatus = "empty"
    as_of: str = "unknown"
    rows: list[QuantFeatureRow] = Field(default_factory=list)
    diagnostics: QuantRunDiagnostics = Field(default_factory=QuantRunDiagnostics)
    warnings: list[str] = Field(default_factory=list)


class QuantSignalGenerateRequest(QuantFeaturePreviewRequest):
    template: str = "momentum_ranking"
    use_research_score: bool = False
    research_max_age_days: int = Field(default=7, ge=1, le=365)

    @field_validator("template", mode="before")
    @classmethod
    def _clean_template(cls, value: Any) -> str:
        return str(value or "momentum_ranking").strip().lower()


class QuantSignalRow(BaseModel):
    date: str
    ticker: str
    factor_values: dict[str, float | None] = Field(default_factory=dict)
    research_score: float | None = None
    final_score: float | None = None
    signal: float = 0.0
    execution_date: str | None = None
    lookahead_policy: str = "close_signal_next_bar_execution"
    diagnostics: list[str] = Field(default_factory=list)


class QuantSignalGenerateResponse(BaseModel):
    status: QuantStatus = "empty"
    as_of: str = "unknown"
    rows: list[QuantSignalRow] = Field(default_factory=list)
    diagnostics: QuantRunDiagnostics = Field(default_factory=QuantRunDiagnostics)
    warnings: list[str] = Field(default_factory=list)


class QuantBacktestRequest(BaseModel):
    strategy_id: str | None = None
    template: str = "momentum_ranking"
    tickers: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    start_date: str | None = None
    end_date: str | None = None
    freshness_profile: FreshnessProfile = "research_default"
    rebalance_every: int = Field(default=21, ge=1, le=252)
    lookback: int = Field(default=63, ge=2, le=5000)
    top_n: int = Field(default=2, ge=1, le=50)
    portfolio_method: str = "equal_weight"
    transaction_cost_bps: float = Field(default=5.0, ge=0, le=1000)
    slippage_bps: float = Field(default=2.0, ge=0, le=1000)
    use_research_score: bool = False
    research_max_age_days: int = Field(default=7, ge=1, le=365)
    require_fresh_prices: bool = False
    max_market_calendar_lag_days: int = Field(default=3, ge=0, le=30)

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_backtest_tickers(cls, value: Any) -> list[str]:
        return _clean_tickers(value)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_backtest_benchmark(cls, value: Any) -> str:
        return str(value or "SPY").strip().upper() or "SPY"

    @field_validator("freshness_profile", mode="before")
    @classmethod
    def _clean_backtest_freshness_profile(cls, value: Any) -> str:
        clean = str(value or "research_default").strip().lower()
        return clean if clean in {"research_default", "decision_review", "historical_lab"} else "research_default"

    @field_validator("template", mode="before")
    @classmethod
    def _clean_template(cls, value: Any) -> str:
        return str(value or "momentum_ranking").strip().lower() or "momentum_ranking"

    @field_validator("portfolio_method", mode="before")
    @classmethod
    def _clean_portfolio_method(cls, value: Any) -> str:
        return str(value or "equal_weight").strip().lower() or "equal_weight"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_backtest_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


def _clean_profile_id(value: Any, default: str = "") -> str:
    cleaned = str(value or default).strip()
    return cleaned or default


def _clean_profile_ticker(value: Any, default: str = "SPY") -> str:
    ticker = str(value or default).strip().upper()
    return ticker or default


def _clean_profile_tickers(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(",", " ").split()
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        ticker = _clean_profile_ticker(item, default="")
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


class QuantModelProfile(BaseModel):
    profile_id: str = "core_universe_forecast_v1"
    schema_version: str = "quant_model_profile_v1"
    strategy_id: str = "momentum_ranking_v1"
    universe_id: str = "custom"
    tickers: list[str] = Field(default_factory=lambda: ["MSFT", "NVDA", "AAPL", "AMZN", "META"])
    benchmark: str = "SPY"
    start_date: str | None = None
    end_date: str | None = None
    include_macro: bool = False
    include_cross_asset: bool = False
    target_config: TargetConfig = Field(default_factory=lambda: TargetConfig(target_type="forward_return", horizon=5, benchmark="SPY"))
    feature_config: FeatureConfig = Field(default_factory=FeatureConfig)
    validation_config: ValidationConfig = Field(default_factory=ValidationConfig)
    model_candidates: list[ModelConfig] = Field(default_factory=lambda: [ModelConfig(model_name="ridge_regression", model_type="regression")])
    signal_config: SignalConfig = Field(default_factory=SignalConfig)
    backtest_config: BacktestConfig = Field(default_factory=BacktestConfig)
    ranking_metric: ForecastUniverseRankingMetric = "confidence"
    max_assets: int = Field(default=6, ge=1, le=25)
    run_mode: QuantModelRunMode = "universe_per_asset"
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @field_validator("profile_id", "strategy_id", "universe_id", mode="before")
    @classmethod
    def _clean_ids(cls, value: Any) -> str:
        return _clean_profile_id(value)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_benchmark_symbol(cls, value: Any) -> str:
        return _clean_profile_ticker(value, default="SPY")

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_profile_tickers(cls, value: Any) -> list[str]:
        return _clean_profile_tickers(value)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_profile_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


class QuantBacktestResponse(BaseModel):
    run_id: str
    status: QuantStatus
    template: str
    tickers: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    date_range: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    drawdown_curve: list[dict[str, Any]] = Field(default_factory=list)
    trades: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[dict[str, Any]] = Field(default_factory=list)
    weights: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: QuantRunDiagnostics = Field(default_factory=QuantRunDiagnostics)
    artifacts: QuantArtifactManifest | None = None


class StrategyResearchConfig(BaseModel):
    strategy_id: str = "risk_adjusted_momentum_v1"
    version_id: str | None = None
    tickers: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "TLT"])
    benchmark: str = "SPY"
    template: str = "risk_adjusted_momentum"
    timeframe: str = "1d"
    start_date: str | None = None
    end_date: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    filter_config: dict[str, Any] = Field(default_factory=dict)
    risk_config: dict[str, Any] = Field(default_factory=dict)
    exit_config: dict[str, Any] = Field(default_factory=dict)
    position_sizing_config: dict[str, Any] = Field(default_factory=dict)
    evidence_class: str = "repo_local_deterministic"
    evidence_notes: list[str] = Field(default_factory=list)

    @field_validator("strategy_id", "version_id", mode="before")
    @classmethod
    def _clean_optional_ids(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value or "").strip()
        return cleaned or None

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_strategy_tickers(cls, value: Any) -> list[str]:
        return _clean_tickers(value)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_strategy_benchmark(cls, value: Any) -> str:
        return str(value or "SPY").strip().upper() or "SPY"

    @field_validator("template", "timeframe", mode="before")
    @classmethod
    def _clean_strategy_text(cls, value: Any) -> str:
        return str(value or "").strip().lower()

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_strategy_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


class StrategyResearchStrategy(BaseModel):
    strategy_id: str
    name: str
    description: str = ""
    asset: str = "multi_asset"
    timeframe: str = "1d"
    core_logic_json: dict[str, Any] = Field(default_factory=dict)
    default_config_json: dict[str, Any] = Field(default_factory=dict)
    status: StrategyResearchStatus = "pending"
    evidence_class: str = "repo_local_deterministic"
    evidence_notes: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class StrategyResearchVersion(BaseModel):
    version_id: str
    strategy_id: str
    version_name: str = "base"
    core_config_json: dict[str, Any] = Field(default_factory=dict)
    filter_config_json: dict[str, Any] = Field(default_factory=dict)
    risk_config_json: dict[str, Any] = Field(default_factory=dict)
    exit_config_json: dict[str, Any] = Field(default_factory=dict)
    position_sizing_config_json: dict[str, Any] = Field(default_factory=dict)
    complexity_score: float = Field(default=1.0, ge=0.0)
    parent_version_id: str | None = None
    source_experiment_id: str | None = None
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    decision_reason: str = ""
    status: StrategyResearchStatus = "pending"
    created_at: str = ""
    updated_at: str = ""


class StrategyResearchExperiment(BaseModel):
    experiment_id: str
    strategy_id: str
    version_id: str = ""
    source_backtest_id: str = ""
    experiment_type: str = "optimization"
    optimization_method: StrategyOptimizationMethod = "grid_search"
    test_period_start: str | None = None
    test_period_end: str | None = None
    in_sample_start: str | None = None
    in_sample_end: str | None = None
    out_of_sample_start: str | None = None
    out_of_sample_end: str | None = None
    market_regime_scope_json: dict[str, Any] = Field(default_factory=dict)
    request_json: dict[str, Any] = Field(default_factory=dict)
    status: StrategyResearchStatus = "queued"
    created_at: str = ""
    updated_at: str = ""


class StrategyOptimizationRequest(BaseModel):
    version_id: str | None = None
    method: StrategyOptimizationMethod = "grid_search"
    objective_name: str = "robust_composite"
    objective_config: dict[str, Any] = Field(default_factory=dict)
    search_space: dict[str, list[Any]] = Field(default_factory=dict)
    max_trials: int = Field(default=12, ge=1, le=120)
    random_seed: int = Field(default=42, ge=0, le=999_999)
    base_config: StrategyResearchConfig = Field(default_factory=StrategyResearchConfig)
    notes: str = ""

    @field_validator("version_id", mode="before")
    @classmethod
    def _clean_version_id(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


class StrategyOptimizationTrial(BaseModel):
    trial_id: str
    optimization_id: str
    trial_number: int
    parameters_json: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    metrics_json: dict[str, Any] = Field(default_factory=dict)
    constraint_flags_json: dict[str, Any] = Field(default_factory=dict)
    rejection_flags_json: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    status: StrategyResearchStatus = "succeeded"
    created_at: str = ""


class StrategyOptimizationRun(BaseModel):
    optimization_id: str
    strategy_id: str
    version_id: str = ""
    experiment_id: str = ""
    job_id: str = ""
    method: StrategyOptimizationMethod = "grid_search"
    objective_name: str = "robust_composite"
    objective_config_json: dict[str, Any] = Field(default_factory=dict)
    search_space_json: dict[str, Any] = Field(default_factory=dict)
    best_parameters_json: dict[str, Any] = Field(default_factory=dict)
    recommended_parameters_json: dict[str, Any] = Field(default_factory=dict)
    best_score: float = 0.0
    recommended_score: float = 0.0
    robustness_score: float = 0.0
    overfitting_score: float = 0.0
    trial_count: int = 0
    notes_json: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    status: StrategyResearchStatus = "queued"
    created_at: str = ""
    updated_at: str = ""


class StrategyDiagnosticsRequest(BaseModel):
    version_id: str | None = None
    source_backtest_id: str | None = None
    optimization_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    base_config: StrategyResearchConfig = Field(default_factory=StrategyResearchConfig)
    min_trade_count: int = Field(default=10, ge=1, le=5000)


class StrategyFailureTag(BaseModel):
    tag: str
    count: int = 0
    share_pct: float = 0.0
    severity: str = "medium"
    decision_use: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)


class StrategyDiagnosticsRun(BaseModel):
    diagnostics_id: str
    strategy_id: str
    version_id: str = ""
    experiment_id: str = ""
    source_backtest_id: str = ""
    summary: str = ""
    failure_distribution_json: list[StrategyFailureTag] = Field(default_factory=list)
    top_failure_causes: list[str] = Field(default_factory=list)
    drawdown_analysis_json: dict[str, Any] = Field(default_factory=dict)
    regime_analysis_json: dict[str, Any] = Field(default_factory=dict)
    trade_cluster_json: dict[str, Any] = Field(default_factory=dict)
    cost_impact_analysis: dict[str, Any] = Field(default_factory=dict)
    parameter_sensitivity_notes: list[str] = Field(default_factory=list)
    recommended_experiments_json: list[dict[str, Any]] = Field(default_factory=list)
    rejected_experiments_json: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    status: StrategyResearchStatus = "succeeded"
    created_at: str = ""


class StrategyHypothesis(BaseModel):
    hypothesis_id: str
    strategy_id: str
    version_id: str = ""
    source_experiment_id: str = ""
    source_diagnostics_id: str = ""
    problem: str
    hypothesis: str
    proposed_change_json: dict[str, Any] = Field(default_factory=dict)
    expected_effect: str
    risk: str
    validation_required_json: list[str] = Field(default_factory=list)
    decision: StrategyResearchStatus = "pending"
    decision_reason: str = ""
    status: StrategyResearchStatus = "pending"
    created_at: str = ""
    updated_at: str = ""


class StrategyHypothesisDecisionRequest(BaseModel):
    decision_reason: str = ""
    validation_id: str | None = None


class StrategyValidationRequest(BaseModel):
    version_id: str | None = None
    optimization_id: str | None = None
    hypothesis_id: str | None = None
    validation_type: str = "full_mvp"
    parameters: dict[str, Any] = Field(default_factory=dict)
    base_config: StrategyResearchConfig = Field(default_factory=StrategyResearchConfig)
    out_of_sample_ratio: float = Field(default=0.3, ge=0.1, le=0.8)
    walk_forward_splits: int = Field(default=3, ge=1, le=8)
    random_seed: int = Field(default=42, ge=0, le=999_999)


class StrategyValidationSummary(BaseModel):
    decision: StrategyResearchStatus = "pending"
    decision_reason: str = ""
    acceptance_flags: list[str] = Field(default_factory=list)
    rejection_flags: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class StrategyValidationResult(BaseModel):
    validation_id: str
    strategy_id: str
    version_id: str = ""
    experiment_id: str = ""
    hypothesis_id: str = ""
    validation_type: str = "full_mvp"
    in_sample_metrics_json: dict[str, Any] = Field(default_factory=dict)
    out_of_sample_metrics_json: dict[str, Any] = Field(default_factory=dict)
    walk_forward_results_json: list[dict[str, Any]] = Field(default_factory=list)
    monte_carlo_results_json: dict[str, Any] = Field(default_factory=dict)
    parameter_stability_json: dict[str, Any] = Field(default_factory=dict)
    cost_stress_json: list[dict[str, Any]] = Field(default_factory=list)
    summary: StrategyValidationSummary = Field(default_factory=StrategyValidationSummary)
    artifacts: dict[str, str] = Field(default_factory=dict)
    status: StrategyResearchStatus = "succeeded"
    created_at: str = ""


class StrategyResearchBackendStatus(BaseModel):
    status: str = "success"
    backend: str = "fingpt_quant_lab_strategy_research"
    schema_version: str = "strategy_research_v1"
    evidence_class: str = "repo_local_deterministic"
    deterministic_available: bool = True
    live_llm_required: bool = False
    optuna_available: bool = False
    bayesian_backend: str = "deterministic_surrogate"
    protected_runtime_available: bool = False
    live_broker_available: bool = False
    protected_runtime_details: dict[str, Any] = Field(default_factory=dict)
    artifact_root: str = ""
    supported_methods: list[StrategyOptimizationMethod] = Field(
        default_factory=lambda: ["grid_search", "random_search", "bayesian"]
    )
    warnings: list[str] = Field(default_factory=list)
