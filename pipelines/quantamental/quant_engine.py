from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from pipelines.quantamental.fundamental_engine import clamp, safe_divide


TRADING_DAYS = 252


def calculate_quant(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _normalize_prices(payload.get("items") or [])
    benchmark_rows = _normalize_prices(payload.get("benchmark_items") or [])
    closes = [_price(row) for row in rows]
    volumes = [_finite(row.get("volume")) for row in rows]
    returns = daily_returns(rows)
    benchmark_returns = _aligned_benchmark_returns(rows, benchmark_rows)
    warnings = list(payload.get("warnings") or [])
    if len(rows) < 20:
        warnings.append("insufficient_price_history_for_core_quant_metrics")

    return_metrics = {
        "return_1d": _window_return(closes, 1),
        "return_5d": _window_return(closes, 5),
        "return_20d": _window_return(closes, 20),
        "return_60d": _window_return(closes, 60),
        "return_120d": _window_return(closes, 120),
        "return_252d": _window_return(closes, 252),
        "cagr": _cagr(closes, len(rows)),
    }
    momentum = {
        "momentum_1m": return_metrics["return_20d"],
        "momentum_3m": return_metrics["return_60d"],
        "momentum_6m": return_metrics["return_120d"],
        "momentum_12m": return_metrics["return_252d"],
        "momentum_12m_minus_1m": _momentum_12m_minus_1m(closes),
        "relative_strength_vs_benchmark": _relative_strength(closes, benchmark_rows),
    }
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    sma100 = _sma(closes, 100)
    sma200 = _sma(closes, 200)
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    latest_close = closes[-1] if closes else None
    trend = {
        "sma_20": sma20,
        "sma_50": sma50,
        "sma_100": sma100,
        "sma_200": sma200,
        "ema_20": ema20,
        "ema_50": ema50,
        "price_above_sma_50": _above(latest_close, sma50),
        "price_above_sma_200": _above(latest_close, sma200),
        "golden_cross": _cross(closes, 50, 200, direction="golden"),
        "death_cross": _cross(closes, 50, 200, direction="death"),
        "trend_regime": _trend_regime(latest_close, sma50, sma200),
    }
    volatility = {
        "realized_volatility_20d": realized_volatility(returns, 20),
        "realized_volatility_60d": realized_volatility(returns, 60),
        "realized_volatility_252d": realized_volatility(returns, 252),
        "downside_volatility": downside_volatility(returns),
        "volatility_percentile": _volatility_percentile(returns),
    }
    drawdown_series = _drawdown_series(closes)
    drawdown = {
        "max_drawdown": min(drawdown_series) if drawdown_series else None,
        "current_drawdown": drawdown_series[-1] if drawdown_series else None,
        "drawdown_duration": _drawdown_duration(closes),
    }
    risk_adjusted = {
        "sharpe_ratio": _sharpe_ratio(returns),
        "sortino_ratio": _sortino_ratio(returns),
        "calmar_ratio": safe_divide(return_metrics["cagr"], abs(drawdown["max_drawdown"]) if drawdown["max_drawdown"] else None),
    }
    risk = {
        "var_95": _percentile(returns, 5),
        "cvar_95": _cvar(returns, 5),
        "beta_vs_benchmark": _beta(returns, benchmark_returns),
        "correlation_vs_benchmark": _correlation(returns, benchmark_returns),
    }
    avg_volume = _mean_tail(volumes, 60)
    avg_dollar_volume = _average_dollar_volume(rows, 60)
    volume_trend = _volume_trend(volumes)
    volume_spike = safe_divide(volumes[-1], _mean_tail(volumes, 20)) if volumes else None
    liquidity = {
        "average_volume": avg_volume,
        "average_dollar_volume": avg_dollar_volume,
        "volume_trend": volume_trend,
        "volume_spike": volume_spike,
        "liquidity_risk": _liquidity_risk(avg_dollar_volume),
    }
    algorithm = _quality_adjusted_momentum_algorithm(
        rows=rows,
        returns=returns,
        momentum=momentum,
        trend=trend,
        volatility=volatility,
        drawdown=drawdown,
        risk_adjusted=risk_adjusted,
        liquidity=liquidity,
    )
    breakout_algorithm = _volatility_adjusted_breakout_algorithm(
        rows=rows,
        returns=returns,
        trend=trend,
        volatility=volatility,
        drawdown=drawdown,
        liquidity=liquidity,
    )
    chart_data = {
        "price": _price_chart(rows),
        "cumulative_return": _cumulative_return_chart(rows),
        "rolling_volatility": _rolling_vol_chart(rows, returns),
        "drawdown": [{"date": row["date"], "drawdown": value} for row, value in zip(rows, drawdown_series)],
        "volume": [{"date": row["date"], "volume": row.get("volume")} for row in rows],
    }
    metrics = {
        "return": return_metrics,
        "momentum": momentum,
        "trend": trend,
        "volatility": volatility,
        "risk_adjusted_return": risk_adjusted,
        "drawdown": drawdown,
        "risk": risk,
        "liquidity": liquidity,
        "algorithm": algorithm,
        "algorithms": {
            "quality_adjusted_momentum": algorithm,
            "volatility_adjusted_breakout": breakout_algorithm,
        },
    }
    return {
        "status": "ok" if rows else "empty",
        "ticker": payload.get("ticker"),
        "market": payload.get("market"),
        "lookback_days": payload.get("lookback_days"),
        "price_history": rows,
        "benchmark_ticker": payload.get("benchmark_ticker"),
        "metrics": metrics,
        "component_scores": _component_scores(metrics),
        "chart_data": chart_data,
        "missing_metrics": _missing_metrics(metrics),
        "warnings": warnings,
        "source_metadata": payload.get("source_metadata") or {},
    }


def daily_returns(rows: list[dict[str, Any]]) -> list[float]:
    closes = [_price(row) for row in _normalize_prices(rows)]
    out: list[float] = []
    for prev, cur in zip(closes, closes[1:]):
        value = safe_divide(cur - prev, prev) if prev is not None and cur is not None else None
        if value is not None and math.isfinite(value):
            out.append(value)
    return out


def realized_volatility(returns: list[float], window: int) -> float | None:
    nums = [value for value in returns[-window:] if math.isfinite(value)]
    if len(nums) < max(2, min(window, 20)):
        return None
    return pstdev(nums) * math.sqrt(TRADING_DAYS)


def downside_volatility(returns: list[float]) -> float | None:
    negatives = [value for value in returns if value < 0]
    if len(negatives) < 2:
        return None
    return pstdev(negatives) * math.sqrt(TRADING_DAYS)


def max_drawdown(rows: list[dict[str, Any]]) -> float | None:
    closes = [_price(row) for row in _normalize_prices(rows)]
    series = _drawdown_series(closes)
    return min(series) if series else None


def _normalize_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        date = str(row.get("date") or "").strip()
        price = _price(row)
        if not date or price is None:
            continue
        normalized.append(
            {
                "date": date,
                "open": _finite(row.get("open")),
                "high": _finite(row.get("high")),
                "low": _finite(row.get("low")),
                "close": _finite(row.get("close")),
                "adjusted_close": price,
                "volume": _finite(row.get("volume")),
            }
        )
    return sorted(normalized, key=lambda item: item["date"])


def _price(row: dict[str, Any]) -> float | None:
    return _finite(row.get("adjusted_close")) or _finite(row.get("close"))


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _window_return(closes: list[float | None], days: int) -> float | None:
    if len(closes) <= days:
        return None
    start = closes[-days - 1]
    end = closes[-1]
    if start is None or end is None:
        return None
    return safe_divide(end - start, start)


def _cagr(closes: list[float | None], observations: int) -> float | None:
    if len(closes) < 2:
        return None
    start = closes[0]
    end = closes[-1]
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    years = max((observations - 1) / TRADING_DAYS, 1 / TRADING_DAYS)
    return (end / start) ** (1 / years) - 1


def _momentum_12m_minus_1m(closes: list[float | None]) -> float | None:
    if len(closes) <= 252:
        return None
    start = closes[-253]
    end = closes[-21] if len(closes) > 21 else None
    if start is None or end is None:
        return None
    return safe_divide(end - start, start)


def _relative_strength(closes: list[float | None], benchmark_rows: list[dict[str, Any]]) -> float | None:
    benchmark_closes = [_price(row) for row in benchmark_rows]
    own = _window_return(closes, min(252, len(closes) - 1)) if len(closes) > 2 else None
    bench = _window_return(benchmark_closes, min(252, len(benchmark_closes) - 1)) if len(benchmark_closes) > 2 else None
    if own is None or bench is None:
        return None
    return own - bench


def _sma(values: list[float | None], window: int) -> float | None:
    nums = [value for value in values[-window:] if value is not None]
    if len(nums) < window:
        return None
    return mean(nums)


def _ema(values: list[float | None], window: int) -> float | None:
    nums = [value for value in values if value is not None]
    if len(nums) < window:
        return None
    k = 2 / (window + 1)
    ema = mean(nums[:window])
    for value in nums[window:]:
        ema = value * k + ema * (1 - k)
    return ema


def _above(value: float | None, reference: float | None) -> bool | None:
    if value is None or reference is None:
        return None
    return value > reference


def _cross(closes: list[float | None], short: int, long: int, *, direction: str) -> bool | None:
    if len(closes) < long + 2:
        return None
    current_short = _sma(closes, short)
    current_long = _sma(closes, long)
    previous_short = _sma(closes[:-1], short)
    previous_long = _sma(closes[:-1], long)
    if None in {current_short, current_long, previous_short, previous_long}:
        return None
    if direction == "golden":
        return bool(current_short > current_long and previous_short <= previous_long)
    return bool(current_short < current_long and previous_short >= previous_long)


def _trend_regime(latest: float | None, sma50: float | None, sma200: float | None) -> str:
    if latest is None or sma50 is None or sma200 is None:
        return "insufficient_data"
    if latest > sma50 > sma200:
        return "uptrend"
    if latest < sma50 < sma200:
        return "downtrend"
    if latest > sma200:
        return "mixed_positive"
    return "mixed_negative"


def _volatility_percentile(returns: list[float]) -> float | None:
    if len(returns) < 60:
        return None
    windows = []
    for i in range(20, len(returns) + 1):
        vol = realized_volatility(returns[:i], 20)
        if vol is not None:
            windows.append(vol)
    if len(windows) < 5:
        return None
    current = windows[-1]
    return sum(1 for value in windows if value <= current) / len(windows)


def _drawdown_series(closes: list[float | None]) -> list[float]:
    peak = None
    out = []
    for value in closes:
        if value is None:
            continue
        peak = value if peak is None else max(peak, value)
        out.append((value / peak) - 1 if peak else 0.0)
    return out


def _drawdown_duration(closes: list[float | None]) -> int | None:
    if not closes:
        return None
    peak = -math.inf
    duration = 0
    for value in closes:
        if value is None:
            continue
        if value >= peak:
            peak = value
            duration = 0
        else:
            duration += 1
    return duration


def _sharpe_ratio(returns: list[float]) -> float | None:
    nums = [value for value in returns if math.isfinite(value)]
    if len(nums) < 2:
        return None
    vol = pstdev(nums)
    if vol == 0:
        return None
    return mean(nums) / vol * math.sqrt(TRADING_DAYS)


def _sortino_ratio(returns: list[float]) -> float | None:
    nums = [value for value in returns if math.isfinite(value)]
    neg = [value for value in nums if value < 0]
    if len(nums) < 2 or len(neg) < 2:
        return None
    vol = pstdev(neg)
    if vol == 0:
        return None
    return mean(nums) / vol * math.sqrt(TRADING_DAYS)


def _percentile(values: list[float], percentile: float) -> float | None:
    nums = sorted(value for value in values if math.isfinite(value))
    if not nums:
        return None
    idx = max(0, min(len(nums) - 1, int((percentile / 100) * (len(nums) - 1))))
    return nums[idx]


def _cvar(values: list[float], percentile: float) -> float | None:
    var = _percentile(values, percentile)
    if var is None:
        return None
    tail = [value for value in values if value <= var]
    return mean(tail) if tail else None


def _aligned_benchmark_returns(rows: list[dict[str, Any]], benchmark_rows: list[dict[str, Any]]) -> list[float]:
    benchmark_by_date = {row["date"]: row for row in benchmark_rows}
    aligned = []
    for row in rows:
        b_row = benchmark_by_date.get(row["date"])
        if b_row:
            aligned.append(b_row)
    return daily_returns(aligned)


def _beta(returns: list[float], benchmark_returns: list[float]) -> float | None:
    pairs = _aligned_return_pairs(returns, benchmark_returns)
    if len(pairs) < 20:
        return None
    xs = [pair[1] for pair in pairs]
    ys = [pair[0] for pair in pairs]
    x_mean = mean(xs)
    y_mean = mean(ys)
    variance = sum((x - x_mean) ** 2 for x in xs)
    if variance == 0:
        return None
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return covariance / variance


def _correlation(returns: list[float], benchmark_returns: list[float]) -> float | None:
    pairs = _aligned_return_pairs(returns, benchmark_returns)
    if len(pairs) < 20:
        return None
    xs = [pair[1] for pair in pairs]
    ys = [pair[0] for pair in pairs]
    sx = pstdev(xs)
    sy = pstdev(ys)
    if sx == 0 or sy == 0:
        return None
    return sum((x - mean(xs)) * (y - mean(ys)) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)


def _aligned_return_pairs(returns: list[float], benchmark_returns: list[float]) -> list[tuple[float, float]]:
    n = min(len(returns), len(benchmark_returns))
    if n <= 0:
        return []
    return list(zip(returns[-n:], benchmark_returns[-n:]))


def _mean_tail(values: list[float | None], window: int) -> float | None:
    nums = [value for value in values[-window:] if value is not None]
    return mean(nums) if nums else None


def _average_dollar_volume(rows: list[dict[str, Any]], window: int) -> float | None:
    values = []
    for row in rows[-window:]:
        price = _price(row)
        volume = _finite(row.get("volume"))
        if price is not None and volume is not None:
            values.append(price * volume)
    return mean(values) if values else None


def _volume_trend(volumes: list[float | None]) -> float | None:
    recent = _mean_tail(volumes, 20)
    prior_values = [value for value in volumes[-80:-20] if value is not None]
    prior = mean(prior_values) if prior_values else None
    return safe_divide((recent or 0.0) - prior, prior) if recent is not None and prior is not None else None


def _liquidity_risk(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "unknown"
    if avg_dollar_volume >= 100_000_000:
        return "low"
    if avg_dollar_volume >= 10_000_000:
        return "medium"
    return "high"


def _quality_adjusted_momentum_algorithm(
    *,
    rows: list[dict[str, Any]],
    returns: list[float],
    momentum: dict[str, Any],
    trend: dict[str, Any],
    volatility: dict[str, Any],
    drawdown: dict[str, Any],
    risk_adjusted: dict[str, Any],
    liquidity: dict[str, Any],
) -> dict[str, Any]:
    available_observations = len(rows)
    required_observations = 60
    warnings: list[str] = []
    if available_observations < required_observations:
        warnings.append("insufficient_price_history_for_quality_adjusted_momentum")

    base_momentum = _first_numeric(
        momentum.get("momentum_12m_minus_1m"),
        momentum.get("momentum_12m"),
        momentum.get("momentum_6m"),
        momentum.get("momentum_3m"),
    )
    trend_score = _avg([
        100.0 if trend.get("price_above_sma_50") is True else 30.0 if trend.get("price_above_sma_50") is False else None,
        100.0 if trend.get("price_above_sma_200") is True else 30.0 if trend.get("price_above_sma_200") is False else None,
        _trend_regime_score(trend.get("trend_regime")),
    ])
    volatility_score = _score_low(volatility.get("realized_volatility_60d"), 0.15, 0.80)
    drawdown_score = _score_low(
        abs(drawdown.get("max_drawdown")) if drawdown.get("max_drawdown") is not None else None,
        0.05,
        0.60,
    )
    consistency = _positive_return_share(returns, 60)
    liquidity_score = _score_high(
        math.log10(liquidity.get("average_dollar_volume")) if liquidity.get("average_dollar_volume") else None,
        6.0,
        9.0,
    )
    momentum_score = _score_high(base_momentum, -0.20, 0.40)
    risk_adjusted_score = _score_high(risk_adjusted.get("sharpe_ratio"), -0.5, 2.0)
    consistency_score = _score_high(consistency, 0.42, 0.62)
    score = _weighted_score(
        [
            (momentum_score, 0.30),
            (trend_score, 0.18),
            (volatility_score, 0.14),
            (drawdown_score, 0.14),
            (risk_adjusted_score, 0.10),
            (consistency_score, 0.09),
            (liquidity_score, 0.05),
        ],
        min_components=4,
    )
    if available_observations < required_observations:
        score = None

    return {
        "algorithm_id": "quality_adjusted_momentum_v1",
        "quality_adjusted_momentum_score": score,
        "classification": _quality_adjusted_momentum_classification(score),
        "score_direction": "higher means stronger momentum after volatility, drawdown, consistency, and liquidity checks",
        "required_observations": required_observations,
        "available_observations": available_observations,
        "base_momentum": base_momentum,
        "positive_return_share_60d": consistency,
        "component_scores": {
            "momentum": momentum_score,
            "trend": trend_score,
            "volatility": volatility_score,
            "drawdown": drawdown_score,
            "risk_adjusted": risk_adjusted_score,
            "consistency": consistency_score,
            "liquidity": liquidity_score,
        },
        "inputs": {
            "momentum_source": _momentum_source(momentum),
            "volatility_window": "60d",
            "consistency_window": "60d",
            "liquidity_basis": "average_dollar_volume_60d",
        },
        "warnings": warnings,
        "not_investment_advice": True,
        "used_in_composite_score": False,
    }


def _volatility_adjusted_breakout_algorithm(
    *,
    rows: list[dict[str, Any]],
    returns: list[float],
    trend: dict[str, Any],
    volatility: dict[str, Any],
    drawdown: dict[str, Any],
    liquidity: dict[str, Any],
) -> dict[str, Any]:
    closes = [_price(row) for row in rows]
    available_observations = len(rows)
    required_observations = 90
    warnings: list[str] = []
    if available_observations < required_observations:
        warnings.append("insufficient_price_history_for_volatility_adjusted_breakout")

    latest_close = closes[-1] if closes else None
    prior_high_63d = _rolling_prior_high(closes, 63)
    breakout_strength = safe_divide((latest_close or 0.0) - prior_high_63d, prior_high_63d) if latest_close is not None and prior_high_63d is not None else None
    trend_return_20d = _window_return(closes, 20)
    positive_share_20d = _positive_return_share(returns, 20)
    volume_confirmation = liquidity.get("volume_spike")
    current_drawdown_abs = abs(drawdown.get("current_drawdown")) if drawdown.get("current_drawdown") is not None else None

    breakout_score = _score_high(breakout_strength, -0.05, 0.08)
    trend_score = _avg([
        _score_high(trend_return_20d, -0.06, 0.12),
        _trend_regime_score(trend.get("trend_regime")),
        100.0 if trend.get("price_above_sma_50") is True else 30.0 if trend.get("price_above_sma_50") is False else None,
    ])
    volatility_score = _score_low(volatility.get("realized_volatility_20d"), 0.12, 0.70)
    drawdown_score = _score_low(current_drawdown_abs, 0.00, 0.25)
    consistency_score = _score_high(positive_share_20d, 0.42, 0.68)
    volume_score = _score_high(volume_confirmation, 0.7, 1.8)
    score = _weighted_score(
        [
            (breakout_score, 0.30),
            (trend_score, 0.20),
            (volatility_score, 0.16),
            (drawdown_score, 0.14),
            (consistency_score, 0.12),
            (volume_score, 0.08),
        ],
        min_components=4,
    )
    if available_observations < required_observations:
        score = None

    return {
        "algorithm_id": "volatility_adjusted_breakout_v1",
        "volatility_adjusted_breakout_score": score,
        "classification": _volatility_adjusted_breakout_classification(score, breakout_strength),
        "score_direction": "higher means a breakout is better supported by trend, volatility, drawdown, consistency, and volume",
        "required_observations": required_observations,
        "available_observations": available_observations,
        "prior_high_window": "63d",
        "prior_high": prior_high_63d,
        "latest_close": latest_close,
        "breakout_strength": breakout_strength,
        "trend_return_20d": trend_return_20d,
        "positive_return_share_20d": positive_share_20d,
        "component_scores": {
            "breakout": breakout_score,
            "trend": trend_score,
            "volatility": volatility_score,
            "drawdown": drawdown_score,
            "consistency": consistency_score,
            "volume": volume_score,
        },
        "inputs": {
            "breakout_basis": "latest_close_vs_prior_63d_high",
            "trend_window": "20d",
            "volatility_window": "20d",
            "volume_basis": "latest_volume_vs_average_volume_20d",
        },
        "warnings": warnings,
        "not_investment_advice": True,
        "used_in_composite_score": False,
    }


def _rolling_prior_high(closes: list[float | None], window: int) -> float | None:
    if len(closes) <= window:
        return None
    nums = [value for value in closes[-window - 1 : -1] if value is not None]
    return max(nums) if nums else None


def _volatility_adjusted_breakout_classification(score: float | None, breakout_strength: float | None) -> str:
    if score is None:
        return "insufficient_data"
    if breakout_strength is not None and breakout_strength <= 0 and score < 65:
        return "no_confirmed_breakout"
    if score >= 75:
        return "confirmed_volatility_adjusted_breakout"
    if score >= 60:
        return "constructive_breakout_setup"
    if score >= 45:
        return "mixed_breakout_setup"
    return "weak_breakout_setup"


def _first_numeric(*values: Any) -> float | None:
    for value in values:
        parsed = _finite(value)
        if parsed is not None:
            return parsed
    return None


def _trend_regime_score(regime: Any) -> float | None:
    return {
        "uptrend": 100.0,
        "mixed_positive": 65.0,
        "mixed_negative": 40.0,
        "downtrend": 20.0,
    }.get(str(regime or ""), None)


def _positive_return_share(returns: list[float], window: int) -> float | None:
    nums = [value for value in returns[-window:] if math.isfinite(value)]
    if len(nums) < 20:
        return None
    return sum(1 for value in nums if value > 0) / len(nums)


def _weighted_score(values: list[tuple[float | None, float]], *, min_components: int = 1) -> float | None:
    available = [(float(value), weight) for value, weight in values if value is not None]
    if len(available) < min_components:
        return None
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        return None
    return round(float(clamp(sum(value * weight for value, weight in available) / total_weight) or 0.0), 2)


def _quality_adjusted_momentum_classification(score: float | None) -> str:
    if score is None:
        return "insufficient_data"
    if score >= 75:
        return "strong_quality_adjusted_momentum"
    if score >= 60:
        return "constructive_quality_adjusted_momentum"
    if score >= 45:
        return "mixed_quality_adjusted_momentum"
    return "weak_quality_adjusted_momentum"


def _momentum_source(momentum: dict[str, Any]) -> str:
    for key in ("momentum_12m_minus_1m", "momentum_12m", "momentum_6m", "momentum_3m"):
        if _finite(momentum.get(key)) is not None:
            return key
    return "unavailable"


def _price_chart(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closes = [_price(row) for row in rows]
    out = []
    for idx, row in enumerate(rows):
        out.append(
            {
                "date": row["date"],
                "close": _price(row),
                "sma_50": _sma(closes[: idx + 1], 50),
                "sma_200": _sma(closes[: idx + 1], 200),
                "volume": row.get("volume"),
            }
        )
    return out


def _cumulative_return_chart(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closes = [_price(row) for row in rows]
    first = closes[0] if closes else None
    return [{"date": row["date"], "cumulative_return": safe_divide((_price(row) or 0.0) - first, first)} for row in rows] if first else []


def _rolling_vol_chart(rows: list[dict[str, Any]], returns: list[float]) -> list[dict[str, Any]]:
    out = []
    for idx, row in enumerate(rows[1:], start=1):
        vol = realized_volatility(returns[:idx], 20)
        out.append({"date": row["date"], "rolling_volatility_20d": vol})
    return out


def _score_high(value: Any, bad: float, good: float) -> float | None:
    parsed = _finite(value)
    if parsed is None or good == bad:
        return None
    return clamp(((parsed - bad) / (good - bad)) * 100)


def _score_low(value: Any, good: float, bad: float) -> float | None:
    parsed = _finite(value)
    if parsed is None or good == bad:
        return None
    return clamp((1 - ((parsed - good) / (bad - good))) * 100)


def _avg(values: list[float | None], fallback: float | None = None) -> float | None:
    nums = [value for value in values if value is not None]
    if not nums:
        return fallback
    return clamp(mean(nums))


def _component_scores(metrics: dict[str, Any]) -> dict[str, float | None]:
    momentum = metrics["momentum"]
    trend = metrics["trend"]
    volatility = metrics["volatility"]
    risk_adjusted = metrics["risk_adjusted_return"]
    drawdown = metrics["drawdown"]
    liquidity = metrics["liquidity"]
    algorithm = metrics.get("algorithm") or {}
    algorithms = metrics.get("algorithms") or {}
    breakout_algorithm = algorithms.get("volatility_adjusted_breakout") or {}
    return {
        "momentum": _avg([
            _score_high(momentum.get("momentum_3m"), -0.10, 0.20),
            _score_high(momentum.get("momentum_6m"), -0.15, 0.35),
            _score_high(momentum.get("momentum_12m"), -0.20, 0.50),
            _score_high(momentum.get("momentum_12m_minus_1m"), -0.20, 0.40),
            _score_high(momentum.get("relative_strength_vs_benchmark"), -0.15, 0.20),
        ]),
        "trend": _avg([
            100.0 if trend.get("price_above_sma_50") is True else 30.0 if trend.get("price_above_sma_50") is False else None,
            100.0 if trend.get("price_above_sma_200") is True else 30.0 if trend.get("price_above_sma_200") is False else None,
            90.0 if trend.get("trend_regime") == "uptrend" else 20.0 if trend.get("trend_regime") == "downtrend" else 55.0,
        ]),
        "volatility_quality": _avg([
            _score_low(volatility.get("realized_volatility_60d"), 0.15, 0.80),
            _score_low(volatility.get("downside_volatility"), 0.10, 0.70),
            _score_low(abs(drawdown.get("max_drawdown")) if drawdown.get("max_drawdown") is not None else None, 0.05, 0.60),
        ]),
        "risk_adjusted_return": _avg([
            _score_high(risk_adjusted.get("sharpe_ratio"), -0.5, 2.0),
            _score_high(risk_adjusted.get("sortino_ratio"), -0.5, 3.0),
            _score_high(risk_adjusted.get("calmar_ratio"), -0.5, 2.0),
        ]),
        "liquidity": _avg([
            _score_high(math.log10(liquidity.get("average_dollar_volume")) if liquidity.get("average_dollar_volume") else None, 6.0, 9.0),
            _score_high(liquidity.get("volume_trend"), -0.5, 0.5),
        ]),
        "quality_adjusted_momentum": _finite(algorithm.get("quality_adjusted_momentum_score")),
        "volatility_adjusted_breakout": _finite(breakout_algorithm.get("volatility_adjusted_breakout_score")),
    }


def _missing_metrics(metrics: dict[str, Any]) -> list[str]:
    missing = []
    for category, values in metrics.items():
        for key, value in values.items():
            if value is None:
                missing.append(f"{category}.{key}")
    return missing
