from __future__ import annotations

import math
from datetime import date, timedelta

from pipelines.strategies import python_generator
from pipelines.strategies.python_generator import PythonStrategyRunRequest, run_python_strategy_lab


def _cycle_rows(count: int = 260) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    start = date(2025, 1, 1)
    prev_close = 100.0
    for idx in range(count):
        close = 100.0 + math.sin(idx / 7.0) * 9.0 + math.sin(idx / 23.0) * 4.0 + idx * 0.015
        high = max(prev_close, close) * 1.018
        low = min(prev_close, close) * 0.982
        rows.append(
            {
                "ticker": "SPY",
                "date": (start + timedelta(days=idx)).isoformat(),
                "open": prev_close,
                "high": high,
                "low": low,
                "close": close,
                "adjusted_close": close,
                "volume": 1_000_000 + idx,
                "source": "test",
            }
        )
        prev_close = close
    return rows


def test_python_strategy_lab_generates_valid_code_backtest_and_optimization(monkeypatch) -> None:
    monkeypatch.setattr(python_generator, "get_prices", lambda ticker, limit=252: _cycle_rows(limit))

    result = run_python_strategy_lab(
        PythonStrategyRunRequest(
            prompt="빠른 Supertrend 전략을 long/short 양방향으로 만들고 손절 익절까지 최적화해줘.",
            ticker="SPY",
            use_local_llm=False,
            optimize=True,
            max_trials=8,
            parameter_overrides={"atr_period": 7, "factor": 1.5, "enable_short": True, "use_sltp": True},
        )
    )

    assert result["status"] == "success"
    assert result["language"] == "python"
    assert result["family"] == "supertrend"
    assert "def generate_signals" in result["code"]
    assert result["validation"]["valid"] is True
    assert {item["name"] for item in result["parameter_manifest"]} >= {"atr_period", "factor", "stop_loss_pct", "take_profit_pct"}
    assert result["backtest"]["status"] == "success"
    assert result["backtest"]["chart"]["rows"]
    assert result["backtest"]["chart"]["markers"]
    assert result["backtest"]["chart"]["trade_paths"]
    assert result["backtest"]["chart"]["trade_paths"][0]["entry_date"]
    assert result["backtest"]["chart"]["trade_paths"][0]["exit_date"]
    assert result["backtest"]["chart"]["trade_paths"][0]["result"] in {"win", "loss"}
    assert result["optimization"]["status"] == "success"
    assert result["optimization"]["trial_count"] <= 8
    assert result["optimization"]["recommended_parameters"]
    assert result["robustness_validation"]["status"] == "success"
    assert result["robustness_validation"]["split_validation"]["oos_metrics"]
    assert result["robustness_validation"]["walk_forward"]["segment_count"] >= 1
    assert result["robustness_validation"]["cost_stress"]["scenarios"]
    assert result["robustness_validation"]["monte_carlo"]["status"] in {"success", "insufficient_trades"}
    assert result["explanation"]["source"] == "verified_backtest_and_optimizer"
    assert result["explanation"]["summary"]
    assert result["explanation"]["parameter_insights"]
    assert {item["name"] for item in result["explanation"]["robustness_checks"]} >= {
        "Python interface validation",
        "Freshness gate",
        "Trade sample",
        "Drawdown guard",
        "Bayesian search",
        "Out-of-sample split",
        "Walk-forward consistency",
        "3x cost stress",
        "Monte Carlo resampling",
    }


def test_python_strategy_lab_generates_moving_average_strategy(monkeypatch) -> None:
    monkeypatch.setattr(python_generator, "get_prices", lambda ticker, limit=252: _cycle_rows(limit))

    result = run_python_strategy_lab(
        PythonStrategyRunRequest(
            prompt="Create a moving average crossover Python strategy with fast and slow SMA parameters.",
            ticker="SPY",
            use_local_llm=False,
            optimize=True,
            max_trials=6,
            parameter_overrides={"fast_window": 5, "slow_window": 25, "enable_short": True},
        )
    )

    assert result["status"] == "success"
    assert result["family"] == "moving_average_crossover"
    assert "def simple_moving_average" in result["code"]
    manifest_names = {item["name"] for item in result["parameter_manifest"]}
    assert manifest_names >= {"fast_window", "slow_window", "enable_short"}
    assert result["validation"]["valid"] is True
    assert result["backtest"]["status"] == "success"
    assert result["backtest"]["chart"]["indicators"]["overlays"][0]["key"] == "fast_ma"
    assert result["backtest"]["chart"]["trade_paths"]
    assert any("fast_ma" in row and "slow_ma" in row for row in result["backtest"]["chart"]["rows"])
    assert result["optimization"]["status"] == "success"
    assert set(result["optimization"]["recommended_parameters"]) <= manifest_names
    assert result["optimization"]["parameter_sensitivity"]
    assert any(item["name"] in {"fast_window", "slow_window"} for item in result["explanation"]["parameter_insights"])
    assert result["robustness_validation"]["split_validation"]["train_parameters"]
    assert result["robustness_validation"]["walk_forward"]["segments"]


def test_python_strategy_lab_generates_rsi_reversion_strategy(monkeypatch) -> None:
    monkeypatch.setattr(python_generator, "get_prices", lambda ticker, limit=252: _cycle_rows(limit))

    result = run_python_strategy_lab(
        PythonStrategyRunRequest(
            prompt="Build an RSI mean reversion Python strategy using oversold and overbought entries.",
            ticker="SPY",
            use_local_llm=False,
            optimize=True,
            max_trials=6,
            parameter_overrides={"rsi_period": 7, "oversold": 35, "overbought": 65, "exit_rsi": 50},
        )
    )

    assert result["status"] == "success"
    assert result["family"] == "rsi_reversion"
    assert "def compute_rsi" in result["code"]
    manifest_names = {item["name"] for item in result["parameter_manifest"]}
    assert manifest_names >= {"rsi_period", "oversold", "overbought", "exit_rsi"}
    assert result["validation"]["valid"] is True
    assert result["backtest"]["status"] == "success"
    assert result["backtest"]["chart"]["indicators"]["panels"][0]["key"] == "rsi"
    assert result["backtest"]["chart"]["trade_paths"]
    assert any("rsi" in row for row in result["backtest"]["chart"]["rows"])
    assert result["optimization"]["status"] == "success"
    assert set(result["optimization"]["recommended_parameters"]) <= manifest_names
    assert result["optimization"]["parameter_sensitivity"]
    assert any(item["name"] == "rsi_period" for item in result["explanation"]["parameter_insights"])
    assert result["robustness_validation"]["cost_stress"]["scenarios"][-1]["multiplier"] == 3.0


def test_python_strategy_validation_rejects_missing_interface() -> None:
    manifest = [{"name": "atr_period", "default": 10}]
    result = python_generator.validate_python_strategy_code("def nope():\n    return 1\n", manifest)

    assert result["valid"] is False
    assert result["syntax_valid"] is True
    assert result["warnings"][0].startswith("missing_interface")
