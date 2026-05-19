from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.schemas.request import _coerce_output_language


QuantamentalMarket = Literal["US", "KR", "GLOBAL"]
QuantamentalPeriod = Literal["annual", "quarterly"]
QuantamentalStyle = Literal["balanced", "quality_growth", "value", "momentum", "defensive"]
QuantamentalOutputLanguage = Literal["ko", "en"]
QuantamentalScoreKey = Literal[
    "composite",
    "value",
    "quality",
    "growth",
    "momentum",
    "low_volatility",
    "liquidity",
    "drawdown_resilience",
    "liquidity_stability",
    "trend_efficiency",
]


class QuantamentalFlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class QuantamentalCompanyOverview(QuantamentalFlexibleModel):
    ticker: str
    market: QuantamentalMarket = "US"
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    exchange: str | None = None
    current_price: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    data_source: str | None = None


class QuantamentalFundamentalStatement(QuantamentalFlexibleModel):
    date: str
    revenue: float | None = None
    gross_profit: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    total_debt: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None


class QuantamentalPriceBar(QuantamentalFlexibleModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adjusted_close: float | None = None
    volume: float | None = None


class QuantamentalFundamentalMetrics(QuantamentalFlexibleModel):
    status: str = "unknown"
    metrics: dict[str, Any] = Field(default_factory=dict)
    category_scores: dict[str, float | None] = Field(default_factory=dict)
    missing_metrics: list[str] = Field(default_factory=list)


class QuantamentalQuantMetrics(QuantamentalFlexibleModel):
    status: str = "unknown"
    metrics: dict[str, Any] = Field(default_factory=dict)
    component_scores: dict[str, float | None] = Field(default_factory=dict)
    chart_data: dict[str, Any] = Field(default_factory=dict)
    missing_metrics: list[str] = Field(default_factory=list)


class QuantamentalFactorScores(QuantamentalFlexibleModel):
    status: str = "unknown"
    value_score: float | None = None
    quality_score: float | None = None
    growth_score: float | None = None
    momentum_score: float | None = None
    low_volatility_score: float | None = None
    liquidity_score: float | None = None
    confidence: dict[str, float] = Field(default_factory=dict)


class QuantamentalRiskMetrics(QuantamentalFlexibleModel):
    risk_score: float | None = None
    risk_level: str = "unknown"
    risk_flags: list[str] = Field(default_factory=list)
    risk_summary: str = ""


class QuantamentalCompositeScore(QuantamentalFlexibleModel):
    style: QuantamentalStyle = "balanced"
    final_score: float | None = None
    fundamental_score: float | None = None
    quant_score: float | None = None
    risk_score: float | None = None
    data_conflict_classification: str = "mixed_or_insufficient_data"


class QuantamentalSignal(QuantamentalFlexibleModel):
    signal_label: str = "Insufficient Data"
    signal_score: float | None = None
    signal_confidence: str = "low"
    time_horizon: str = "medium_to_long_term"
    rationale: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


class QuantamentalAIReportResponse(QuantamentalFlexibleModel):
    status: str = "partial"
    provider: str = "deterministic_interpreter"
    signal_label: str | None = None
    signal_preserved: bool = True
    report: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


class QuantamentalQAResponse(QuantamentalFlexibleModel):
    status: str = "partial"
    provider: str = "deterministic_interpreter"
    question: str
    answer: str
    evidence_metrics: list[dict[str, Any]] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    not_investment_advice: bool = True


class QuantamentalDataQuality(QuantamentalFlexibleModel):
    data_quality_score: float = 0.0
    quality_level: str = "poor"
    missing_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class QuantamentalError(QuantamentalFlexibleModel):
    code: str
    message: str
    recoverable: bool = True


class QuantamentalAnalysisResponse(QuantamentalFlexibleModel):
    status: str
    ticker: str
    market: QuantamentalMarket = "US"
    company: dict[str, Any] = Field(default_factory=dict)
    fundamentals: dict[str, Any] = Field(default_factory=dict)
    quant: dict[str, Any] = Field(default_factory=dict)
    factors: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    composite: dict[str, Any] = Field(default_factory=dict)
    signal: dict[str, Any] = Field(default_factory=dict)
    ai_report: dict[str, Any] = Field(default_factory=dict)
    data_quality: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class QuantamentalAIReportRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    use_llm: bool = False
    model: str | None = None
    timeout_s: float = Field(default=30.0, ge=1.0, le=90.0)
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class QuantamentalQARequest(BaseModel):
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    use_llm: bool = False
    model: str | None = None
    timeout_s: float = Field(default=30.0, ge=1.0, le=90.0)
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("question is required")
        return cleaned

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class QuantamentalAnalysisRequest(BaseModel):
    ticker: str
    market: QuantamentalMarket = "US"
    period: QuantamentalPeriod = "annual"
    years: int = Field(default=5, ge=1, le=10)
    lookback: int | str = 252
    style: QuantamentalStyle = "balanced"
    include_ai: bool = True
    include_sec: bool = True
    use_llm: bool = False
    force_refresh: bool = False
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        cleaned = str(value or "").strip().upper()
        if not cleaned:
            raise ValueError("ticker is required")
        return cleaned

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class QuantamentalCompareRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    market: QuantamentalMarket = "US"
    period: QuantamentalPeriod = "annual"
    years: int = Field(default=5, ge=1, le=10)
    lookback: int | str = 252
    style: QuantamentalStyle = "balanced"
    include_ai: bool = False
    use_llm: bool = False
    expand_peer_universe: bool = False
    peer_limit: int = Field(default=8, ge=2, le=20)
    force_refresh: bool = False
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            ticker = str(item or "").strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            cleaned.append(ticker)
        if len(cleaned) < 2:
            raise ValueError("at least two tickers are required")
        if len(cleaned) > 12:
            raise ValueError("at most twelve tickers are supported")
        return cleaned

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class QuantamentalScreenRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    universe: Literal["default_us_large_cap", "mega_cap_tech", "custom"] = "default_us_large_cap"
    market: QuantamentalMarket = "US"
    period: QuantamentalPeriod = "annual"
    years: int = Field(default=5, ge=1, le=10)
    lookback: int | str = 252
    style: QuantamentalStyle = "balanced"
    limit: int = Field(default=5, ge=1, le=10)
    include_ai: bool = False
    use_llm: bool = False
    refresh_stale: bool = True
    force_refresh: bool = False
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("tickers")
    @classmethod
    def validate_screen_tickers(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            ticker = str(item or "").strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            cleaned.append(ticker)
        if len(cleaned) > 50:
            raise ValueError("at most fifty tickers are supported")
        return cleaned

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class QuantamentalScoreScreenRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    universe: Literal["default_us_large_cap", "mega_cap_tech", "custom"] = "default_us_large_cap"
    market: QuantamentalMarket = "US"
    period: QuantamentalPeriod = "annual"
    years: int = Field(default=5, ge=1, le=10)
    lookback: int | str = 252
    style: QuantamentalStyle = "balanced"
    score_key: QuantamentalScoreKey = "composite"
    min_score: float = Field(default=70.0, ge=0.0, le=100.0)
    limit: int = Field(default=20, ge=1, le=50)
    include_ai: bool = False
    use_llm: bool = False
    refresh_stale: bool = True
    force_refresh: bool = False
    output_language: QuantamentalOutputLanguage = "ko"

    @field_validator("tickers")
    @classmethod
    def validate_screen_tickers(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            ticker = str(item or "").strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            cleaned.append(ticker)
        if len(cleaned) > 50:
            raise ValueError("at most fifty tickers are supported")
        return cleaned

    @field_validator("output_language", mode="before")
    @classmethod
    def validate_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)
