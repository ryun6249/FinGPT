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
    assert result["optimization"]["status"] == "success"
    assert result["optimization"]["trial_count"] <= 8
    assert result["optimization"]["recommended_parameters"]


def test_python_strategy_validation_rejects_missing_interface() -> None:
    manifest = [{"name": "atr_period", "default": 10}]
    result = python_generator.validate_python_strategy_code("def nope():\n    return 1\n", manifest)

    assert result["valid"] is False
    assert result["syntax_valid"] is True
    assert result["warnings"][0].startswith("missing_interface")
