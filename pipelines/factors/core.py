from __future__ import annotations

import math
from typing import Iterable


def _clean(values: Iterable[float | int | None]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(val):
            out.append(val)
    return out


def simple_returns(prices: Iterable[float | int | None]) -> list[float]:
    values = _clean(prices)
    returns: list[float] = []
    for idx in range(1, len(values)):
        prev = values[idx - 1]
        if prev == 0:
            continue
        returns.append(values[idx] / prev - 1.0)
    return returns


def momentum_return(prices: Iterable[float | int | None], lookback: int = 21) -> float | None:
    values = _clean(prices)
    if len(values) <= lookback:
        return None
    previous = values[-lookback - 1]
    if previous == 0:
        return None
    return values[-1] / previous - 1.0


def realized_volatility(prices: Iterable[float | int | None], lookback: int = 20, annualization: int = 252) -> float | None:
    returns = simple_returns(_clean(prices)[-(lookback + 1):])
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(annualization)


def moving_average(prices: Iterable[float | int | None], window: int = 20) -> float | None:
    values = _clean(prices)
    window = int(window or 0)
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def moving_average_ratio(
    prices: Iterable[float | int | None],
    short_window: int = 20,
    long_window: int = 50,
) -> float | None:
    short = moving_average(prices, short_window)
    long = moving_average(prices, long_window)
    if short is None or long in (None, 0):
        return None
    return short / long - 1.0


def rsi(prices: Iterable[float | int | None], lookback: int = 14) -> float | None:
    values = _clean(prices)
    lookback = int(lookback or 0)
    if lookback <= 0 or len(values) < lookback + 1:
        return None
    changes = [values[idx] - values[idx - 1] for idx in range(len(values) - lookback, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]
    avg_gain = sum(gains) / lookback
    avg_loss = sum(losses) / lookback
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_histogram(
    prices: Iterable[float | int | None],
    fast_window: int = 12,
    slow_window: int = 26,
    signal_window: int = 9,
) -> float | None:
    values = _clean(prices)
    fast_window = int(fast_window or 0)
    slow_window = int(slow_window or 0)
    signal_window = int(signal_window or 0)
    if min(fast_window, slow_window, signal_window) <= 0 or len(values) < slow_window + signal_window:
        return None
    fast = _ema_series(values, fast_window)
    slow = _ema_series(values, slow_window)
    macd = [f - s for f, s in zip(fast[-len(slow):], slow)]
    signal = _ema_series(macd, signal_window)
    if not signal:
        return None
    return macd[-1] - signal[-1]


def bollinger_zscore(prices: Iterable[float | int | None], lookback: int = 20) -> float | None:
    values = _clean(prices)
    lookback = int(lookback or 0)
    if lookback <= 1 or len(values) < lookback:
        return None
    window = values[-lookback:]
    mean = sum(window) / len(window)
    stdev = math.sqrt(sum((value - mean) ** 2 for value in window) / (len(window) - 1))
    if stdev == 0:
        return 0.0
    return (window[-1] - mean) / stdev


def current_drawdown(prices: Iterable[float | int | None]) -> float | None:
    values = drawdown_series(prices)
    return values[-1] if values else None


def drawdown_series(prices: Iterable[float | int | None]) -> list[float]:
    values = _clean(prices)
    peak: float | None = None
    out: list[float] = []
    for value in values:
        peak = value if peak is None else max(peak, value)
        out.append(value / peak - 1.0 if peak else 0.0)
    return out


def correlation_matrix(returns_by_asset: dict[str, Iterable[float | int | None]]) -> dict[str, dict[str, float]]:
    cleaned = {asset: _clean(values) for asset, values in returns_by_asset.items()}
    assets = list(cleaned)
    matrix: dict[str, dict[str, float]] = {asset: {} for asset in assets}
    for left in assets:
        for right in assets:
            matrix[left][right] = _correlation(cleaned[left], cleaned[right])
    return matrix


def rate_sensitivity(asset_returns: Iterable[float | int | None], rate_changes: Iterable[float | int | None]) -> float | None:
    returns = _clean(asset_returns)
    rates = _clean(rate_changes)
    n = min(len(returns), len(rates))
    if n < 3:
        return None
    x = rates[-n:]
    y = returns[-n:]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    var_x = sum((value - mean_x) ** 2 for value in x)
    if var_x == 0:
        return None
    cov = sum((xv - mean_x) * (yv - mean_y) for xv, yv in zip(x, y))
    return cov / var_x


def rolling_beta(
    asset_returns: Iterable[float | int | None],
    benchmark_returns: Iterable[float | int | None],
    lookback: int = 126,
) -> float | None:
    asset = _clean(asset_returns)
    benchmark = _clean(benchmark_returns)
    n = min(len(asset), len(benchmark), int(lookback or 0))
    if n < 3:
        return None
    asset = asset[-n:]
    benchmark = benchmark[-n:]
    mean_asset = sum(asset) / n
    mean_benchmark = sum(benchmark) / n
    var_benchmark = sum((value - mean_benchmark) ** 2 for value in benchmark)
    if var_benchmark == 0:
        return None
    cov = sum((a - mean_asset) * (b - mean_benchmark) for a, b in zip(asset, benchmark))
    return cov / var_benchmark


def rolling_correlation(
    left_returns: Iterable[float | int | None],
    right_returns: Iterable[float | int | None],
    lookback: int = 126,
) -> float | None:
    left = _clean(left_returns)
    right = _clean(right_returns)
    n = min(len(left), len(right), int(lookback or 0))
    if n < 2:
        return None
    return _correlation(left[-n:], right[-n:])


def relative_strength(
    asset_prices: Iterable[float | int | None],
    benchmark_prices: Iterable[float | int | None],
    lookback: int = 63,
) -> float | None:
    asset = momentum_return(asset_prices, lookback=lookback)
    benchmark = momentum_return(benchmark_prices, lookback=lookback)
    if asset is None or benchmark is None:
        return None
    return asset - benchmark


def risk_adjusted_momentum(
    prices: Iterable[float | int | None],
    lookback: int = 63,
    volatility_lookback: int = 21,
    volatility_floor: float = 0.05,
) -> float | None:
    momentum = momentum_return(prices, lookback=lookback)
    vol = realized_volatility(prices, lookback=volatility_lookback)
    drawdown = current_drawdown(prices)
    if momentum is None or vol is None:
        return None
    denominator = max(abs(float(vol)), float(volatility_floor or 0.05))
    drawdown_penalty = max(0.0, 1.0 + float(drawdown or 0.0))
    return (float(momentum) / denominator) * drawdown_penalty


def _correlation(left: list[float], right: list[float]) -> float:
    n = min(len(left), len(right))
    if n < 2:
        return 0.0
    a = left[-n:]
    b = right[-n:]
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    var_a = sum((value - mean_a) ** 2 for value in a)
    var_b = sum((value - mean_b) ** 2 for value in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    cov = sum((av - mean_a) * (bv - mean_b) for av, bv in zip(a, b))
    return cov / math.sqrt(var_a * var_b)


def _ema_series(values: list[float], window: int) -> list[float]:
    if window <= 0 or not values:
        return []
    alpha = 2.0 / (window + 1.0)
    ema: list[float] = []
    current = values[0]
    for value in values:
        current = alpha * value + (1.0 - alpha) * current
        ema.append(current)
    return ema
