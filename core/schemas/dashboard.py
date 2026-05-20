from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketTapeItem(BaseModel):
    symbol: str
    label: str = ""
    asset_class: str = ""
    price: float | None = None
    return_1d: float | None = None
    return_1m: float | None = None
    as_of: str = ""
    source: str = "unknown"
    freshness_status: str = "unknown"
    is_decision_usable: bool = False


class MarketDashboardSignal(BaseModel):
    signal_id: str
    title: str
    status: str = "neutral"
    score: float | None = None
    direction: str = "neutral"
    confidence: str = "medium"
    horizon: str = "1D"
    impact: str = ""
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)
    components: list[dict[str, Any]] = Field(default_factory=list)
    watch_points: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    interpretation: str = ""
    is_decision_usable: bool = False


class MarketDashboardFreshnessSummary(BaseModel):
    status: str = "unavailable"
    item_count: int = 0
    decision_usable_count: int = 0
    freshness_counts: dict[str, int] = Field(default_factory=dict)
    warning: str = ""
    policy: str = ""


class MarketDashboardHeatmapSummary(BaseModel):
    status: str = "not_loaded"
    universe_version: str = ""
    universe_size: int = 0
    decision_usable_count: int = 0
    stale_or_unavailable_count: int = 0
    latest_as_of: str = ""
    provider: str = "unknown"
    interval: str = ""
    warning: str = ""
    cache_hit: bool = False


class MarketDashboardOverview(BaseModel):
    generated_at: str
    provider: str = "market_dashboard"
    advisory_only: bool = True
    market_tape: list[MarketTapeItem] = Field(default_factory=list)
    signals: list[MarketDashboardSignal] = Field(default_factory=list)
    freshness_summary: MarketDashboardFreshnessSummary
    heatmap_summary: MarketDashboardHeatmapSummary
    raw_market_meta: dict[str, Any] = Field(default_factory=dict)
