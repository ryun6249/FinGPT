from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipelines.factors.core import momentum_return, risk_adjusted_momentum
from pipelines.backtest.metrics import performance_metrics


@dataclass(frozen=True)
class BacktestConfig:
    strategy: str = "buy_and_hold"
    short_window: int = 20
    long_window: int = 50
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 2.0
    initial_capital: float = 1.0


def run_backtest(price_rows: list[dict[str, Any]], config: BacktestConfig | None = None) -> dict[str, Any]:
    config = config or BacktestConfig()
    rows = [row for row in price_rows if _price(row) is not None]
    rows.sort(key=lambda row: str(row.get("date") or ""))
    if len(rows) < 2:
        return {
            "status": "partial",
            "reason": "not_enough_price_history",
            "strategy": config.strategy,
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    prices = [_price(row) for row in rows]
    dates = [str(row.get("date") or "") for row in rows]
    signals = _signals(prices, config)
    cost = (float(config.transaction_cost_bps) + float(config.slippage_bps)) / 10000.0
    equity = [float(config.initial_capital)]
    trades: list[dict[str, Any]] = []
    prev_position = 0.0
    for idx in range(1, len(prices)):
        position = signals[idx - 1]  # previous close signal prevents lookahead
        daily_return = prices[idx] / prices[idx - 1] - 1.0 if prices[idx - 1] else 0.0
        turnover = abs(position - prev_position)
        if turnover > 0:
            trades.append(
                _trade_event(
                    signal_date=dates[idx - 1],
                    execution_date=dates[idx],
                    ticker="PORTFOLIO",
                    previous_weight=prev_position,
                    target_weight=position,
                    price=prices[idx],
                    cost_rate=cost,
                    transaction_cost_bps=config.transaction_cost_bps,
                    slippage_bps=config.slippage_bps,
                    reason=f"{config.strategy}_signal_change",
                )
            )
        equity.append(equity[-1] * (1.0 + position * daily_return - turnover * cost))
        prev_position = position

    metrics = performance_metrics(equity)
    metrics.update(
        {
            "turnover": round(sum(trade["turnover"] for trade in trades), 6),
            "exposure": round(sum(abs(signal) for signal in signals[:-1]) / max(len(signals) - 1, 1), 6),
            "trade_count": len(trades),
        }
    )
    return {
        "status": "success",
        "strategy": config.strategy,
        "assumptions": {
            "transaction_cost_bps": config.transaction_cost_bps,
            "slippage_bps": config.slippage_bps,
            "lookahead_policy": "signals are applied one bar after calculation",
        },
        "date_range": {"start": dates[0], "end": dates[-1]},
        "equity_curve": [{"date": date, "equity": round(value, 8)} for date, value in zip(dates, equity)],
        "trades": trades,
        "metrics": metrics,
    }


def _price(row: dict[str, Any]) -> float | None:
    value = row.get("adjusted_close")
    if value is None:
        value = row.get("close")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _signals(prices: list[float], config: BacktestConfig) -> list[float]:
    strategy = str(config.strategy or "buy_and_hold").lower()
    if strategy == "buy_and_hold":
        return [1.0 for _ in prices]
    if strategy == "moving_average":
        out: list[float] = []
        for idx in range(len(prices)):
            if idx + 1 < config.long_window:
                out.append(0.0)
                continue
            short_avg = sum(prices[idx + 1 - config.short_window: idx + 1]) / config.short_window
            long_avg = sum(prices[idx + 1 - config.long_window: idx + 1]) / config.long_window
            out.append(1.0 if short_avg > long_avg else 0.0)
        return out
    if strategy == "volatility_targeting":
        out = []
        target_vol = 0.12
        for idx in range(len(prices)):
            if idx < 21:
                out.append(0.0)
                continue
            window = prices[idx - 21: idx + 1]
            returns = [window[i] / window[i - 1] - 1.0 for i in range(1, len(window)) if window[i - 1]]
            vol = _stdev(returns) * (252 ** 0.5)
            out.append(max(0.0, min(1.5, target_vol / vol)) if vol else 0.0)
        return out
    raise ValueError(f"unsupported strategy: {config.strategy}")


def run_momentum_ranking_backtest(
    prices_by_asset: dict[str, list[dict[str, Any]]],
    *,
    lookback: int = 21,
    top_n: int = 1,
    rebalance_every: int = 21,
    config: BacktestConfig | None = None,
) -> dict[str, Any]:
    config = config or BacktestConfig(strategy="momentum_ranking")
    series = {
        asset.upper().strip(): sorted([row for row in rows if _price(row) is not None], key=lambda row: str(row.get("date") or ""))
        for asset, rows in prices_by_asset.items()
        if str(asset).strip()
    }
    series = {asset: rows for asset, rows in series.items() if len(rows) >= lookback + 2}
    if not series:
        return {
            "status": "partial",
            "reason": "not_enough_price_history",
            "strategy": "momentum_ranking",
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    common_dates = sorted(set.intersection(*(set(str(row.get("date") or "") for row in rows) for rows in series.values())))
    if len(common_dates) < lookback + 2:
        return {
            "status": "partial",
            "reason": "not_enough_common_history",
            "strategy": "momentum_ranking",
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    prices = {
        asset: {str(row.get("date") or ""): _price(row) for row in rows}
        for asset, rows in series.items()
    }
    top_n = max(1, min(int(top_n), len(prices)))
    rebalance_every = max(1, int(rebalance_every))
    cost = (float(config.transaction_cost_bps) + float(config.slippage_bps)) / 10000.0
    equity = [float(config.initial_capital)]
    weights = {asset: 0.0 for asset in prices}
    trades: list[dict[str, Any]] = []
    selected_history: list[dict[str, Any]] = []
    rebalance_snapshots: list[dict[str, Any]] = []
    exposure_history: list[float] = []

    for idx in range(1, len(common_dates)):
        date = common_dates[idx]
        prev_date = common_dates[idx - 1]
        rebalance_turnover = 0.0
        if idx > lookback and (idx - lookback - 1) % rebalance_every == 0:
            scores: list[tuple[str, float]] = []
            for asset in prices:
                history = [prices[asset][d] for d in common_dates[:idx] if prices[asset].get(d) is not None]
                score = momentum_return(history, lookback=lookback)
                if score is not None:
                    scores.append((asset, score))
            ranked = sorted(scores, key=lambda item: item[1], reverse=True)
            selected = [asset for asset, _ in ranked[:top_n]]
            score_map = {asset: score for asset, score in ranked}
            next_weights = {asset: (1.0 / len(selected) if asset in selected and selected else 0.0) for asset in prices}
            turnover = sum(abs(next_weights[asset] - weights.get(asset, 0.0)) for asset in prices)
            if turnover:
                for asset in prices:
                    previous_weight = weights.get(asset, 0.0)
                    target_weight = next_weights[asset]
                    if abs(target_weight - previous_weight) <= 1e-12:
                        continue
                    trades.append(
                        _trade_event(
                            signal_date=prev_date,
                            execution_date=date,
                            ticker=asset,
                            previous_weight=previous_weight,
                            target_weight=target_weight,
                            price=prices[asset].get(date),
                            cost_rate=cost,
                            transaction_cost_bps=config.transaction_cost_bps,
                            slippage_bps=config.slippage_bps,
                            reason="momentum_ranking_rebalance",
                            selected=asset in selected,
                            score=score_map.get(asset),
                        )
                    )
                rebalance_turnover = turnover
            weights = next_weights
            selected_history.append({"date": date, "selected": selected})
            rebalance_snapshots.append(
                {
                    "signal_date": prev_date,
                    "execution_date": date,
                    "selected": selected,
                    "rejected": [asset for asset, _ in ranked[top_n:]],
                    "scores": {asset: round(score, 8) for asset, score in ranked},
                    "target_weights": {asset: round(weight, 8) for asset, weight in weights.items()},
                    "turnover": round(turnover, 8),
                }
            )
        exposure_history.append(sum(abs(weight) for weight in weights.values()))
        daily_return = 0.0
        for asset, weight in weights.items():
            prev_price = prices[asset].get(prev_date)
            current_price = prices[asset].get(date)
            if not prev_price or current_price is None:
                continue
            daily_return += weight * (current_price / prev_price - 1.0)
        turnover_cost = rebalance_turnover * cost
        equity.append(equity[-1] * (1.0 + daily_return - turnover_cost))

    metrics = performance_metrics(equity)
    metrics.update(
        {
            "turnover": round(sum(trade["turnover"] for trade in trades), 6),
            "exposure": round(sum(exposure_history) / max(len(exposure_history), 1), 6),
            "trade_count": len(trades),
        }
    )
    return {
        "status": "success",
        "strategy": "momentum_ranking",
        "assumptions": {
            "lookback": lookback,
            "top_n": top_n,
            "rebalance_every": rebalance_every,
            "transaction_cost_bps": config.transaction_cost_bps,
            "slippage_bps": config.slippage_bps,
            "lookahead_policy": "ranking uses history through the previous close before applying weights",
        },
        "date_range": {"start": common_dates[0], "end": common_dates[-1]},
        "equity_curve": [{"date": date, "equity": round(value, 8)} for date, value in zip(common_dates, equity)],
        "trades": trades,
        "selected_history": selected_history,
        "rebalance_snapshots": rebalance_snapshots,
        "metrics": metrics,
    }


def run_risk_adjusted_momentum_backtest(
    prices_by_asset: dict[str, list[dict[str, Any]]],
    *,
    lookback: int = 63,
    top_n: int = 1,
    rebalance_every: int = 21,
    config: BacktestConfig | None = None,
) -> dict[str, Any]:
    config = config or BacktestConfig(strategy="risk_adjusted_momentum")
    return _run_ranked_backtest(
        prices_by_asset,
        strategy_name="risk_adjusted_momentum",
        score_reason="risk_adjusted_momentum_rebalance",
        score_fn=lambda history: risk_adjusted_momentum(history, lookback=lookback, volatility_lookback=min(21, max(2, lookback // 3))),
        lookback=lookback,
        top_n=top_n,
        rebalance_every=rebalance_every,
        config=config,
    )


def _run_ranked_backtest(
    prices_by_asset: dict[str, list[dict[str, Any]]],
    *,
    strategy_name: str,
    score_reason: str,
    score_fn,
    lookback: int,
    top_n: int,
    rebalance_every: int,
    config: BacktestConfig,
) -> dict[str, Any]:
    series = {
        asset.upper().strip(): sorted([row for row in rows if _price(row) is not None], key=lambda row: str(row.get("date") or ""))
        for asset, rows in prices_by_asset.items()
        if str(asset).strip()
    }
    series = {asset: rows for asset, rows in series.items() if len(rows) >= lookback + 2}
    if not series:
        return {
            "status": "partial",
            "reason": "not_enough_price_history",
            "strategy": strategy_name,
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    common_dates = sorted(set.intersection(*(set(str(row.get("date") or "") for row in rows) for rows in series.values())))
    if len(common_dates) < lookback + 2:
        return {
            "status": "partial",
            "reason": "not_enough_common_history",
            "strategy": strategy_name,
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    prices = {
        asset: {str(row.get("date") or ""): _price(row) for row in rows}
        for asset, rows in series.items()
    }
    top_n = max(1, min(int(top_n), len(prices)))
    rebalance_every = max(1, int(rebalance_every))
    cost = (float(config.transaction_cost_bps) + float(config.slippage_bps)) / 10000.0
    equity = [float(config.initial_capital)]
    weights = {asset: 0.0 for asset in prices}
    trades: list[dict[str, Any]] = []
    selected_history: list[dict[str, Any]] = []
    rebalance_snapshots: list[dict[str, Any]] = []
    exposure_history: list[float] = []

    for idx in range(1, len(common_dates)):
        date = common_dates[idx]
        prev_date = common_dates[idx - 1]
        rebalance_turnover = 0.0
        if idx > lookback and (idx - lookback - 1) % rebalance_every == 0:
            scores: list[tuple[str, float]] = []
            for asset in prices:
                history = [prices[asset][d] for d in common_dates[:idx] if prices[asset].get(d) is not None]
                score = score_fn(history)
                if score is not None:
                    scores.append((asset, float(score)))
            ranked = sorted(scores, key=lambda item: item[1], reverse=True)
            selected = [asset for asset, _ in ranked[:top_n]]
            score_map = {asset: score for asset, score in ranked}
            next_weights = {asset: (1.0 / len(selected) if asset in selected and selected else 0.0) for asset in prices}
            turnover = sum(abs(next_weights[asset] - weights.get(asset, 0.0)) for asset in prices)
            if turnover:
                for asset in prices:
                    previous_weight = weights.get(asset, 0.0)
                    target_weight = next_weights[asset]
                    if abs(target_weight - previous_weight) <= 1e-12:
                        continue
                    trades.append(
                        _trade_event(
                            signal_date=prev_date,
                            execution_date=date,
                            ticker=asset,
                            previous_weight=previous_weight,
                            target_weight=target_weight,
                            price=prices[asset].get(date),
                            cost_rate=cost,
                            transaction_cost_bps=config.transaction_cost_bps,
                            slippage_bps=config.slippage_bps,
                            reason=score_reason,
                            selected=asset in selected,
                            score=score_map.get(asset),
                        )
                    )
                rebalance_turnover = turnover
            weights = next_weights
            selected_history.append({"date": date, "selected": selected})
            rebalance_snapshots.append(
                {
                    "signal_date": prev_date,
                    "execution_date": date,
                    "selected": selected,
                    "rejected": [asset for asset, _ in ranked[top_n:]],
                    "scores": {asset: round(score, 8) for asset, score in ranked},
                    "target_weights": {asset: round(weight, 8) for asset, weight in weights.items()},
                    "turnover": round(turnover, 8),
                }
            )
        exposure_history.append(sum(abs(weight) for weight in weights.values()))
        daily_return = 0.0
        for asset, weight in weights.items():
            prev_price = prices[asset].get(prev_date)
            current_price = prices[asset].get(date)
            if not prev_price or current_price is None:
                continue
            daily_return += weight * (current_price / prev_price - 1.0)
        equity.append(equity[-1] * (1.0 + daily_return - rebalance_turnover * cost))

    metrics = performance_metrics(equity)
    metrics.update(
        {
            "turnover": round(sum(trade["turnover"] for trade in trades), 6),
            "exposure": round(sum(exposure_history) / max(len(exposure_history), 1), 6),
            "trade_count": len(trades),
        }
    )
    return {
        "status": "success",
        "strategy": strategy_name,
        "assumptions": {
            "lookback": lookback,
            "top_n": top_n,
            "rebalance_every": rebalance_every,
            "transaction_cost_bps": config.transaction_cost_bps,
            "slippage_bps": config.slippage_bps,
            "lookahead_policy": "ranking uses history through the previous close before applying weights",
            "ranking_score": strategy_name,
        },
        "date_range": {"start": common_dates[0], "end": common_dates[-1]},
        "equity_curve": [{"date": date, "equity": round(value, 8)} for date, value in zip(common_dates, equity)],
        "trades": trades,
        "selected_history": selected_history,
        "rebalance_snapshots": rebalance_snapshots,
        "metrics": metrics,
    }


def run_multi_asset_backtest(
    prices_by_asset: dict[str, list[dict[str, Any]]],
    config: BacktestConfig | None = None,
) -> dict[str, Any]:
    """Run a single portfolio equity curve across multiple aligned assets.

    Signals are still calculated per asset, then applied one bar later as
    capital weights. This keeps the no-lookahead policy explicit while avoiding
    the previous average-of-single-asset-results summary.
    """

    config = config or BacktestConfig()
    series = {
        asset.upper().strip(): sorted([row for row in rows if _price(row) is not None], key=lambda row: str(row.get("date") or ""))
        for asset, rows in prices_by_asset.items()
        if str(asset).strip()
    }
    series = {asset: rows for asset, rows in series.items() if len(rows) >= 2}
    if not series:
        return {
            "status": "partial",
            "reason": "not_enough_price_history",
            "strategy": config.strategy,
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    common_dates = sorted(set.intersection(*(set(str(row.get("date") or "") for row in rows) for rows in series.values())))
    if len(common_dates) < 2:
        return {
            "status": "partial",
            "reason": "not_enough_common_history",
            "strategy": config.strategy,
            "equity_curve": [],
            "trades": [],
            "metrics": performance_metrics([]),
        }

    prices = {
        asset: {str(row.get("date") or ""): _price(row) for row in rows}
        for asset, rows in series.items()
    }
    signals = {}
    for asset in prices:
        asset_prices = [prices[asset][date] for date in common_dates]
        signals[asset] = _signals(asset_prices, config)

    cost = (float(config.transaction_cost_bps) + float(config.slippage_bps)) / 10000.0
    equity = [float(config.initial_capital)]
    trades: list[dict[str, Any]] = []
    weights = {asset: 0.0 for asset in prices}
    weights_history: list[dict[str, Any]] = []
    exposure_history: list[float] = []

    for idx in range(1, len(common_dates)):
        date = common_dates[idx]
        prev_date = common_dates[idx - 1]
        next_weights = _portfolio_weights_from_signals({asset: signals[asset][idx - 1] for asset in prices})
        turnover = sum(abs(next_weights[asset] - weights.get(asset, 0.0)) for asset in prices)
        if turnover > 0:
            for asset in prices:
                previous_weight = weights.get(asset, 0.0)
                target_weight = next_weights[asset]
                if abs(target_weight - previous_weight) <= 1e-12:
                    continue
                trades.append(
                    _trade_event(
                        signal_date=prev_date,
                        execution_date=date,
                        ticker=asset,
                        previous_weight=previous_weight,
                        target_weight=target_weight,
                        price=prices[asset].get(date),
                        cost_rate=cost,
                        transaction_cost_bps=config.transaction_cost_bps,
                        slippage_bps=config.slippage_bps,
                        reason=f"{config.strategy}_portfolio_signal",
                        selected=target_weight > 0,
                    )
                )
        weights = next_weights
        weights_history.append({"date": date, "weights": {k: round(v, 8) for k, v in weights.items()}})
        exposure_history.append(sum(abs(weight) for weight in weights.values()))
        daily_return = 0.0
        for asset, weight in weights.items():
            prev_price = prices[asset].get(prev_date)
            current_price = prices[asset].get(date)
            if not prev_price or current_price is None:
                continue
            daily_return += weight * (current_price / prev_price - 1.0)
        equity.append(equity[-1] * (1.0 + daily_return - turnover * cost))

    metrics = performance_metrics(equity)
    metrics.update(
        {
            "turnover": round(sum(trade["turnover"] for trade in trades), 6),
            "exposure": round(sum(exposure_history) / max(len(exposure_history), 1), 6),
            "trade_count": len(trades),
        }
    )
    return {
        "status": "success",
        "strategy": config.strategy,
        "assumptions": {
            "transaction_cost_bps": config.transaction_cost_bps,
            "slippage_bps": config.slippage_bps,
            "lookahead_policy": "asset signals are applied one bar after calculation",
            "allocation_policy": "equal capital budget per asset signal; inactive signals remain in cash",
        },
        "date_range": {"start": common_dates[0], "end": common_dates[-1]},
        "equity_curve": [{"date": date, "equity": round(value, 8)} for date, value in zip(common_dates, equity)],
        "trades": trades,
        "weights_history": weights_history,
        "metrics": metrics,
    }


def _portfolio_weights_from_signals(signals: dict[str, float]) -> dict[str, float]:
    if not signals:
        return {}
    n_assets = len(signals)
    weights: dict[str, float] = {}
    for asset, signal in signals.items():
        try:
            value = float(signal)
        except (TypeError, ValueError):
            value = 0.0
        weights[asset] = max(value, 0.0) / n_assets
    return weights


def _trade_event(
    *,
    signal_date: str,
    execution_date: str,
    ticker: str,
    previous_weight: float,
    target_weight: float,
    price: float | None,
    cost_rate: float,
    transaction_cost_bps: float,
    slippage_bps: float,
    reason: str,
    selected: bool | None = None,
    score: float | None = None,
) -> dict[str, Any]:
    delta = float(target_weight) - float(previous_weight)
    turnover = abs(delta)
    action = "increase" if delta > 0 else "decrease"
    if previous_weight <= 0 and target_weight > 0:
        action = "enter"
    elif previous_weight > 0 and target_weight <= 0:
        action = "exit"
    return {
        "date": execution_date,
        "signal_date": signal_date,
        "execution_date": execution_date,
        "ticker": ticker,
        "action": action,
        "previous_weight": round(float(previous_weight), 8),
        "target_weight": round(float(target_weight), 8),
        "weight": round(float(target_weight), 8),
        "delta_weight": round(delta, 8),
        "turnover": round(turnover, 8),
        "price": round(float(price), 8) if price is not None else None,
        "cost": round(turnover * cost_rate, 10),
        "transaction_cost_bps": float(transaction_cost_bps),
        "slippage_bps": float(slippage_bps),
        "reason": reason,
        "selected": selected,
        "score": round(float(score), 8) if score is not None else None,
        "diagnostics": ["signal_uses_prior_close", "execution_next_bar_close"],
    }


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5
