from __future__ import annotations

from pipelines.factors.catalog import compute_factor_latest, list_factor_catalog
from pipelines.factors.core import moving_average_ratio, rsi, rolling_beta


def test_factor_catalog_exposes_ui_safe_ids() -> None:
    ids = {item["factor_id"] for item in list_factor_catalog()}

    assert "momentum_63d" in ids
    assert "realized_vol_21d" in ids
    assert "relative_strength_spy_63d" in ids
    assert "risk_adjusted_momentum_63_21" in ids


def test_new_factor_math_is_deterministic() -> None:
    prices = [100 + idx for idx in range(80)]

    assert moving_average_ratio(prices, short_window=5, long_window=20) > 0
    assert rsi(prices, lookback=14) == 100.0
    assert compute_factor_latest("momentum_63d", prices) is not None
    assert compute_factor_latest("risk_adjusted_momentum_63_21", prices) is not None


def test_benchmark_factors_require_benchmark_prices() -> None:
    prices = [100 + idx for idx in range(150)]
    benchmark = [100 + idx * 0.5 for idx in range(150)]

    assert compute_factor_latest("relative_strength_spy_63d", prices) is None
    assert compute_factor_latest("relative_strength_spy_63d", prices, benchmark_prices=benchmark) is not None
    assert rolling_beta([0.01, 0.02, 0.03, 0.01], [0.01, 0.01, 0.02, 0.01], lookback=4) is not None
