from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pipelines.factors.core import (
    bollinger_zscore,
    current_drawdown,
    momentum_return,
    moving_average_ratio,
    realized_volatility,
    relative_strength,
    risk_adjusted_momentum,
    rolling_beta,
    rolling_correlation,
    simple_returns,
    rsi,
)


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    label: str
    description: str
    default_params: dict[str, Any] = field(default_factory=dict)
    requires_benchmark: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_FACTOR_DEFINITIONS: dict[str, FactorDefinition] = {
    "return_1d": FactorDefinition("return_1d", "1D Return", "Latest one-day adjusted-close return.", {"lookback": 1}),
    "return_5d": FactorDefinition("return_5d", "5D Return", "Latest five-day adjusted-close return.", {"lookback": 5}),
    "momentum_21d": FactorDefinition("momentum_21d", "21D Momentum", "One-month price momentum.", {"lookback": 21}),
    "momentum_63d": FactorDefinition("momentum_63d", "63D Momentum", "Quarterly price momentum.", {"lookback": 63}),
    "momentum_126d": FactorDefinition("momentum_126d", "126D Momentum", "Half-year price momentum.", {"lookback": 126}),
    "risk_adjusted_momentum_63d": FactorDefinition(
        "risk_adjusted_momentum_63d",
        "Risk-Adjusted Momentum 63D",
        "Quarterly momentum divided by realized volatility with a current-drawdown penalty.",
        {"lookback": 63, "volatility_lookback": 21, "volatility_floor": 0.05},
    ),
    "realized_vol_21d": FactorDefinition("realized_vol_21d", "21D Realized Vol", "Annualized realized volatility.", {"lookback": 21}),
    "drawdown_current": FactorDefinition("drawdown_current", "Current Drawdown", "Drawdown from the trailing peak."),
    "ma_ratio_20_50": FactorDefinition("ma_ratio_20_50", "MA 20/50 Ratio", "20-day average versus 50-day average.", {"short_window": 20, "long_window": 50}),
    "ma_ratio_50_200": FactorDefinition("ma_ratio_50_200", "MA 50/200 Ratio", "50-day average versus 200-day average.", {"short_window": 50, "long_window": 200}),
    "rsi_14": FactorDefinition("rsi_14", "RSI 14", "Fourteen-day relative strength index.", {"lookback": 14}),
    "bollinger_z_20": FactorDefinition("bollinger_z_20", "Bollinger Z 20", "Latest close z-score versus a 20-day band.", {"lookback": 20}),
    "relative_strength_spy_63d": FactorDefinition(
        "relative_strength_spy_63d",
        "Relative Strength vs SPY",
        "Asset momentum less benchmark momentum.",
        {"lookback": 63},
        requires_benchmark=True,
    ),
    "beta_spy_126d": FactorDefinition(
        "beta_spy_126d",
        "Beta vs Benchmark",
        "Rolling beta to the selected benchmark.",
        {"lookback": 126},
        requires_benchmark=True,
    ),
    "rolling_corr_spy_126d": FactorDefinition(
        "rolling_corr_spy_126d",
        "Correlation vs Benchmark",
        "Rolling return correlation to benchmark.",
        {"lookback": 126},
        requires_benchmark=True,
    ),
}


def list_factor_catalog() -> list[dict[str, Any]]:
    return [definition.to_dict() for definition in _FACTOR_DEFINITIONS.values()]


def get_factor_definition(factor_id: str) -> FactorDefinition:
    clean = str(factor_id or "").strip().lower()
    if clean not in _FACTOR_DEFINITIONS:
        raise ValueError(f"unsupported factor_id: {factor_id}")
    return _FACTOR_DEFINITIONS[clean]


def compute_factor_latest(
    factor_id: str,
    prices: list[float],
    *,
    benchmark_prices: list[float] | None = None,
    params: dict[str, Any] | None = None,
) -> float | None:
    definition = get_factor_definition(factor_id)
    resolved = dict(definition.default_params)
    resolved.update(params or {})
    fid = definition.factor_id
    if fid.startswith("return_") or fid.startswith("momentum_"):
        return momentum_return(prices, lookback=int(resolved.get("lookback") or 1))
    if fid == "risk_adjusted_momentum_63d":
        return risk_adjusted_momentum(
            prices,
            lookback=int(resolved.get("lookback") or 63),
            volatility_lookback=int(resolved.get("volatility_lookback") or 21),
            volatility_floor=float(resolved.get("volatility_floor") or 0.05),
        )
    if fid == "realized_vol_21d":
        return realized_volatility(prices, lookback=int(resolved.get("lookback") or 21))
    if fid == "drawdown_current":
        return current_drawdown(prices)
    if fid.startswith("ma_ratio_"):
        return moving_average_ratio(
            prices,
            short_window=int(resolved.get("short_window") or 20),
            long_window=int(resolved.get("long_window") or 50),
        )
    if fid == "rsi_14":
        return rsi(prices, lookback=int(resolved.get("lookback") or 14))
    if fid == "bollinger_z_20":
        return bollinger_zscore(prices, lookback=int(resolved.get("lookback") or 20))
    if fid == "relative_strength_spy_63d":
        if not benchmark_prices:
            return None
        return relative_strength(prices, benchmark_prices, lookback=int(resolved.get("lookback") or 63))
    if fid == "beta_spy_126d":
        if not benchmark_prices:
            return None
        return rolling_beta(
            simple_returns(prices),
            simple_returns(benchmark_prices),
            lookback=int(resolved.get("lookback") or 126),
        )
    if fid == "rolling_corr_spy_126d":
        if not benchmark_prices:
            return None
        return rolling_correlation(
            simple_returns(prices),
            simple_returns(benchmark_prices),
            lookback=int(resolved.get("lookback") or 126),
        )
    raise ValueError(f"unsupported factor_id: {factor_id}")
