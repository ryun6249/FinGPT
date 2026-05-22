from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ForecastStatus = Literal["success", "partial", "failed", "empty"]
ForecastJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
DataQualityStatus = Literal["ok", "partial", "stale", "unavailable", "insufficient"]
LeakageStatus = Literal["pass", "warning", "fail"]
SignalValue = Literal[
    "strong_bullish",
    "moderate_bullish",
    "neutral",
    "moderate_bearish",
    "strong_bearish",
    "unavailable",
]
ModelStatus = Literal["draft", "trained", "validated", "promoted", "deprecated", "failed"]
ForecastUniverseRankingMetric = Literal["confidence", "expected_return", "probability_up", "signal_score", "risk_adjusted"]


class ForecastSourceContext(BaseModel):
    source: str = ""
    strategy_id: str = ""
    profile_id: str = ""
    strategy_hash: str = ""
    profile_hash: str = ""
    risk_validation_test_id: str = ""
    risk_input_hash: str = ""
    risk_test_type: str = ""
    risk_test_label: str = ""
    risk_priority: int | None = Field(default=None, ge=1, le=5)


def _clean_ticker(value: Any, default: str = "SPY") -> str:
    ticker = str(value or default).strip().upper()
    return ticker or default


def _clean_ticker_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(",", " ").split()
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        ticker = _clean_ticker(item, default="").strip()
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


class ForecastDatasetConfig(BaseModel):
    ticker: str = "SPY"
    universe_id: str | None = None
    benchmark: str = "SPY"
    start_date: str | None = None
    end_date: str | None = None
    frequency: str = "1d"
    include_macro: bool = False
    include_cross_asset: bool = False
    include_technical: bool = True
    data_source: str = "data_mart:prices_daily"
    adjusted_price: bool = True
    max_rows: int = Field(default=5000, ge=100, le=20000)

    @field_validator("ticker", "benchmark", mode="before")
    @classmethod
    def _clean_symbols(cls, value: Any) -> str:
        return _clean_ticker(value)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _clean_date(cls, value: Any) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned or None


class FeatureConfig(BaseModel):
    feature_groups: list[str] = Field(default_factory=lambda: ["returns", "momentum", "volatility", "trend"])
    selected_features: list[str] = Field(default_factory=list)
    lag_config: dict[str, int] = Field(default_factory=dict)
    rolling_windows: list[int] = Field(default_factory=lambda: [5, 20, 60, 200])
    scaling_method: str = "standard"
    feature_shift: int = Field(default=1, ge=0, le=10)
    missing_value_policy: str = "drop"


class TargetConfig(BaseModel):
    target_type: str = "forward_return"
    horizon: int = Field(default=20, ge=1, le=252)
    threshold: float = 0.0
    benchmark: str = "SPY"
    triple_barrier_take_profit: float | None = None
    triple_barrier_stop_loss: float | None = None
    triple_barrier_max_holding: int | None = None
    volatility_window: int = Field(default=20, ge=2, le=252)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_benchmark(cls, value: Any) -> str:
        return _clean_ticker(value)


class ValidationConfig(BaseModel):
    validation_method: str = "walk_forward"
    train_window: str | int = "3y"
    validation_window: str | int = "6m"
    test_window: str | int = "6m"
    step_size: str | int = "1m"
    purge_window: str | int = "auto"
    embargo_window: int = Field(default=5, ge=0, le=252)
    expanding: bool = True
    shuffle: bool = False
    random_state: int = 42


class ModelConfig(BaseModel):
    model_type: str = "regression"
    model_name: str = "ridge_regression"
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    scaling: bool = True
    feature_selection: str = "none"
    hyperparameter_search: bool = False
    seed: int = 42


class SignalConfig(BaseModel):
    signal_method: str = "threshold_confidence"
    bullish_threshold: float = 0.01
    bearish_threshold: float = -0.01
    strong_bullish_threshold: float = 0.03
    strong_bearish_threshold: float = -0.03
    probability_threshold: float = 0.55
    confidence_threshold: float = 0.55
    volatility_filter_enabled: bool = True
    max_forecast_volatility: float = 0.40
    volatility_max: float | None = None
    trend_filter_enabled: bool = True
    regime_filter_enabled: bool = True
    smoothing_window: int = Field(default=1, ge=1, le=63)
    cooldown_period: int = Field(default=0, ge=0, le=63)
    max_position_size: float = Field(default=1.0, ge=0.0, le=2.0)
    long_only: bool = True
    allow_short: bool = False


class BacktestConfig(BaseModel):
    strategy_type: str = "long_cash"
    signal_threshold: float = 0.0
    long_only: bool = True
    allow_short: bool = False
    max_position_size: float = Field(default=1.0, ge=0.0, le=2.0)
    rebalance_frequency: str = "daily"
    commission_bps: float = Field(default=5.0, ge=0.0, le=1000.0)
    slippage_bps: float = Field(default=2.0, ge=0.0, le=1000.0)
    spread_bps: float = Field(default=0.0, ge=0.0, le=1000.0)
    benchmark: str = "SPY"
    initial_capital: float = Field(default=1.0, gt=0)
    execution_delay_bars: int = Field(default=1, ge=0, le=10)

    @field_validator("benchmark", mode="before")
    @classmethod
    def _clean_benchmark(cls, value: Any) -> str:
        return _clean_ticker(value)


class VisualizationConfig(BaseModel):
    show_forecast_cone: bool = True
    show_signal_overlay: bool = True
    show_actual_vs_predicted: bool = True
    show_residuals: bool = True
    show_feature_importance: bool = True
    show_equity_curve: bool = True
    show_drawdown: bool = True
    show_rolling_sharpe: bool = True
    show_signal_history: bool = True
    show_position_exposure: bool = True
    show_model_comparison: bool = True


class DataQualityResult(BaseModel):
    status: DataQualityStatus = "unavailable"
    rows: int = 0
    start_date: str = ""
    end_date: str = ""
    missing_values: int = 0
    missing_ratio: float = 0.0
    adjusted_price_status: str = "unknown"
    benchmark_availability: str = "unknown"
    macro_availability: str = "unavailable"
    warnings: list[str] = Field(default_factory=list)


class LeakageCheckResult(BaseModel):
    status: LeakageStatus = "warning"
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    checked_at: str = ""


class ConfidenceResult(BaseModel):
    score: float = 0.0
    level: str = "very_low"
    components: dict[str, float] = Field(default_factory=dict)
    penalties: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class ForecastResult(BaseModel):
    experiment_id: str = ""
    model_id: str = ""
    ticker: str = ""
    as_of: str = ""
    horizon: int = 20
    prediction_type: str = "forward_return"
    expected_return: float | None = None
    median_return: float | None = None
    probability_up: float | None = None
    probability_down: float | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    forecast_volatility: float | None = None
    signal: SignalValue = "unavailable"
    signal_score: float = 0.0
    model_confidence: ConfidenceResult = Field(default_factory=ConfidenceResult)
    warnings: list[str] = Field(default_factory=list)
    data_quality: DataQualityResult = Field(default_factory=DataQualityResult)


class SignalResult(BaseModel):
    ticker: str = ""
    as_of: str = ""
    horizon: int = 20
    raw_forecast: dict[str, Any] = Field(default_factory=dict)
    signal: SignalValue = "unavailable"
    signal_score: float = 0.0
    confidence: float = 0.0
    position_target: float = 0.0
    filters_applied: list[str] = Field(default_factory=list)
    filter_results: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    advisory_only: bool = True
    warnings: list[str] = Field(default_factory=list)


class SignalQuality(BaseModel):
    signal_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    hit_rate: float | None = None
    average_forward_return_after_bullish: float | None = None
    average_forward_return_after_bearish: float | None = None
    precision_bullish: float | None = None
    precision_bearish: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    average_holding_period: float | None = None
    turnover: float = 0.0
    signal_stability: float = 0.0
    recent_signal_performance: float | None = None
    signal_decay_by_horizon: dict[str, float] = Field(default_factory=dict)


class ModelEvaluation(BaseModel):
    regression_metrics: dict[str, float] = Field(default_factory=dict)
    classification_metrics: dict[str, Any] = Field(default_factory=dict)
    financial_metrics: dict[str, float] = Field(default_factory=dict)
    stability_metrics: dict[str, float] = Field(default_factory=dict)
    signal_quality: SignalQuality = Field(default_factory=SignalQuality)
    overfitting_check: dict[str, Any] = Field(default_factory=dict)
    leakage_check: LeakageCheckResult = Field(default_factory=LeakageCheckResult)
    benchmark_comparison: dict[str, Any] = Field(default_factory=dict)


class ForecastExperiment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    experiment_id: str
    created_at: str
    ticker: str
    dataset_config: ForecastDatasetConfig
    feature_config: FeatureConfig
    target_config: TargetConfig
    validation_config: ValidationConfig
    ml_model_config: ModelConfig = Field(alias="model_config", serialization_alias="model_config")
    signal_config: SignalConfig
    backtest_config: BacktestConfig
    visualization_config: VisualizationConfig
    source_context: ForecastSourceContext = Field(default_factory=ForecastSourceContext)
    status: ForecastStatus = "partial"
    warnings: list[str] = Field(default_factory=list)
    data_quality: DataQualityResult = Field(default_factory=DataQualityResult)
    leakage_check: LeakageCheckResult = Field(default_factory=LeakageCheckResult)
    metrics: dict[str, Any] = Field(default_factory=dict)
    signal_metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: dict[str, str] = Field(default_factory=dict)


class ForecastRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dataset_config: ForecastDatasetConfig = Field(default_factory=ForecastDatasetConfig)
    feature_config: FeatureConfig = Field(default_factory=FeatureConfig)
    target_config: TargetConfig = Field(default_factory=TargetConfig)
    validation_config: ValidationConfig = Field(default_factory=ValidationConfig)
    ml_model_config: ModelConfig = Field(default_factory=ModelConfig, alias="model_config", serialization_alias="model_config")
    signal_config: SignalConfig = Field(default_factory=SignalConfig)
    backtest_config: BacktestConfig = Field(default_factory=BacktestConfig)
    visualization_config: VisualizationConfig = Field(default_factory=VisualizationConfig)
    source_context: ForecastSourceContext = Field(default_factory=ForecastSourceContext)


class ForecastJobSubmitRequest(BaseModel):
    request: ForecastRunRequest = Field(default_factory=ForecastRunRequest)
    runtime_budget_s: int = Field(default=900, ge=30, le=7200)
    notes: str = ""


class ForecastJobCancelRequest(BaseModel):
    reason: str = ""


class ForecastDatasetPreviewRequest(BaseModel):
    dataset_config: ForecastDatasetConfig = Field(default_factory=ForecastDatasetConfig)


class ForecastDatasetHydrateRequest(BaseModel):
    dataset_config: ForecastDatasetConfig = Field(default_factory=ForecastDatasetConfig)
    include_benchmark: bool = True
    include_macro: bool | None = None
    start_date: str | None = None
    end_date: str | None = None


class ForecastFeatureBuildRequest(BaseModel):
    dataset_config: ForecastDatasetConfig = Field(default_factory=ForecastDatasetConfig)
    feature_config: FeatureConfig = Field(default_factory=FeatureConfig)


class ForecastTargetBuildRequest(BaseModel):
    dataset_config: ForecastDatasetConfig = Field(default_factory=ForecastDatasetConfig)
    target_config: TargetConfig = Field(default_factory=TargetConfig)


class ForecastLeakageCheckRequest(ForecastRunRequest):
    pass


class ForecastSignalGenerateRequest(BaseModel):
    forecast_result: ForecastResult
    signal_config: SignalConfig = Field(default_factory=SignalConfig)
    leakage_check: LeakageCheckResult | None = None
    data_quality: DataQualityResult | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ForecastExperimentIdRequest(BaseModel):
    experiment_id: str


class ForecastBatchPredictRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list, max_length=20)
    request: ForecastRunRequest = Field(default_factory=ForecastRunRequest)

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, value: Any) -> list[str]:
        return _clean_ticker_list(value)


class ForecastUniverseRunRequest(BaseModel):
    universe_id: str = "custom"
    tickers: list[str] = Field(default_factory=list, max_length=50)
    request: ForecastRunRequest = Field(default_factory=ForecastRunRequest)
    max_assets: int = Field(default=8, ge=1, le=25)
    ranking_metric: ForecastUniverseRankingMetric = "confidence"
    notes: str = ""

    @field_validator("universe_id", mode="before")
    @classmethod
    def _clean_universe_id(cls, value: Any) -> str:
        cleaned = str(value or "custom").strip()
        return cleaned or "custom"

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, value: Any) -> list[str]:
        return _clean_ticker_list(value)


class ForecastDriftCheckRequest(BaseModel):
    ticker: str | None = None
    experiment_id: str | None = None
    recent_window: int = Field(default=63, ge=20, le=252)


class ForecastRegistryActionRequest(BaseModel):
    model_id: str
    notes: str = ""


class ModelRegistryItem(BaseModel):
    model_id: str
    experiment_id: str
    ticker: str
    target: str
    horizon: int
    model_type: str
    feature_set_hash: str
    training_period: dict[str, str] = Field(default_factory=dict)
    validation_method: str = "walk_forward"
    metrics: dict[str, Any] = Field(default_factory=dict)
    signal_metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_path: str = ""
    status: ModelStatus = "trained"
    created_at: str = ""
    promoted_at: str | None = None
    deprecated_at: str | None = None
    notes: str = ""
