from __future__ import annotations

from pipelines.backtest.engine import BacktestConfig, run_backtest, run_momentum_ranking_backtest, run_multi_asset_backtest


def _rows(prices: list[float], prefix: str = "2026-01") -> list[dict[str, object]]:
    return [
        {"date": f"{prefix}-{idx + 1:02d}", "adjusted_close": price, "close": price}
        for idx, price in enumerate(prices)
    ]


def test_buy_and_hold_metrics_include_cost_assumptions() -> None:
    result = run_backtest(
        _rows([100, 110, 121]),
        BacktestConfig(strategy="buy_and_hold", transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["equity_curve"][-1]["equity"] == 1.21
    assert result["assumptions"]["lookahead_policy"]
    assert result["metrics"]["total_return"] == 0.21
    assert result["metrics"]["max_drawdown"] == 0.0
    assert result["metrics"]["turnover"] == 1.0


def test_moving_average_signal_is_applied_one_bar_later() -> None:
    result = run_backtest(
        _rows([100, 90, 110]),
        BacktestConfig(strategy="moving_average", short_window=1, long_window=2, transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["equity_curve"][-1]["equity"] == 1.0
    assert result["trades"] == []


def test_momentum_ranking_uses_prior_history_and_records_turnover() -> None:
    result = run_momentum_ranking_backtest(
        {
            "AAA": _rows([100, 101, 103, 108, 112, 118]),
            "BBB": _rows([100, 99, 98, 98, 97, 96]),
        },
        lookback=2,
        top_n=1,
        rebalance_every=1,
        config=BacktestConfig(transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["selected_history"]
    assert result["selected_history"][0]["selected"] == ["AAA"]
    assert result["metrics"]["trade_count"] >= 1
    assert result["assumptions"]["lookahead_policy"]
    first_trade = result["trades"][0]
    assert first_trade["signal_date"] < first_trade["execution_date"]
    assert first_trade["ticker"] in {"AAA", "BBB"}
    assert "target_weight" in first_trade
    assert result["rebalance_snapshots"][0]["selected"] == ["AAA"]
    assert result["rebalance_snapshots"][0]["rejected"] == ["BBB"]


def test_risk_adjusted_momentum_ranking_records_score_mode() -> None:
    result = run_momentum_ranking_backtest(
        {
            "SMOOTH": _rows([100 + idx for idx in range(30)]),
            "CHOPPY": _rows([100 + idx * 2 + (18 if idx % 2 else -18) for idx in range(30)]),
        },
        lookback=5,
        top_n=1,
        rebalance_every=1,
        score_mode="risk_adjusted_momentum",
        config=BacktestConfig(transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["strategy"] == "risk_adjusted_momentum"
    assert result["assumptions"]["score_mode"] == "risk_adjusted_momentum"
    assert result["rebalance_snapshots"][0]["selected"] == ["SMOOTH"]
    assert result["rebalance_snapshots"][0]["scores"]["SMOOTH"] > result["rebalance_snapshots"][0]["scores"]["CHOPPY"]


def test_multi_asset_buy_and_hold_builds_single_portfolio_curve() -> None:
    result = run_multi_asset_backtest(
        {
            "AAA": _rows([100, 110, 121]),
            "BBB": _rows([100, 100, 100]),
        },
        BacktestConfig(strategy="buy_and_hold", transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["equity_curve"][-1]["equity"] == 1.1025
    assert result["weights_history"][0]["weights"] == {"AAA": 0.5, "BBB": 0.5}
    assert result["metrics"]["total_return"] == 0.1025
    assert result["metrics"]["turnover"] == 1.0
    assert {trade["ticker"] for trade in result["trades"]} == {"AAA", "BBB"}
    assert all(trade["signal_date"] < trade["execution_date"] for trade in result["trades"])


def test_multi_asset_moving_average_keeps_no_lookahead_cash_for_inactive_signals() -> None:
    result = run_multi_asset_backtest(
        {
            "AAA": _rows([100, 90, 110]),
            "BBB": _rows([100, 100, 100]),
        },
        BacktestConfig(strategy="moving_average", short_window=1, long_window=2, transaction_cost_bps=0, slippage_bps=0),
    )

    assert result["status"] == "success"
    assert result["equity_curve"][-1]["equity"] == 1.0
    assert result["trades"] == []
