from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipelines.strategies.storage import migrate_strategy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STRATEGY_PATH = PROJECT_ROOT / "config" / "quant_strategies" / "defaults.yaml"


FALLBACK_STRATEGIES: list[dict[str, Any]] = [
    {
        "strategy_id": "momentum_ranking_v1",
        "name": "Momentum Ranking",
        "universe": ["SPY", "QQQ", "TLT", "GLD"],
        "benchmark": "SPY",
        "frequency": "daily",
        "features": {
            "momentum_63d": {"id": "momentum_63d", "lookback": 63},
            "realized_vol_21d": {"id": "realized_vol_21d", "lookback": 21},
        },
        "signal": {"type": "rank_top_n", "top_n": 2},
        "portfolio": {"method": "equal_weight", "max_weight": 0.5},
        "execution": {"trade_at": "next_bar_close", "transaction_cost_bps": 5, "slippage_bps": 2},
        "diagnostics": {"require_fresh_prices": True, "require_no_lookahead": True},
    },
    {
        "strategy_id": "research_confirmed_momentum_v1",
        "name": "Research Confirmed Momentum",
        "universe": ["SPY", "QQQ", "TLT"],
        "benchmark": "SPY",
        "frequency": "daily",
        "features": {
            "momentum_63d": {"id": "momentum_63d", "lookback": 63},
            "realized_vol_21d": {"id": "realized_vol_21d", "lookback": 21},
            "research_score": {"id": "research_score", "max_age_days": 7},
        },
        "signal": {"type": "score_threshold", "long_threshold": 0.6, "exit_threshold": 0.3},
        "portfolio": {"method": "equal_weight", "max_weight": 0.35},
        "execution": {"trade_at": "next_bar_close", "transaction_cost_bps": 5, "slippage_bps": 2},
        "diagnostics": {"require_fresh_prices": True, "require_no_lookahead": True},
    },
    {
        "strategy_id": "risk_adjusted_momentum_v1",
        "name": "Risk-Adjusted Momentum",
        "universe": ["SPY", "QQQ", "TLT", "GLD"],
        "benchmark": "SPY",
        "frequency": "daily",
        "features": {
            "momentum_63d": {"id": "momentum_63d", "lookback": 63},
            "risk_adjusted_momentum_63_21": {"id": "risk_adjusted_momentum_63_21"},
            "realized_vol_21d": {"id": "realized_vol_21d", "lookback": 21},
        },
        "signal": {"type": "risk_adjusted_rank_top_n", "top_n": 2, "score_mode": "risk_adjusted_momentum"},
        "portfolio": {"method": "equal_weight", "max_weight": 0.5},
        "execution": {"trade_at": "next_bar_close", "transaction_cost_bps": 5, "slippage_bps": 2},
        "diagnostics": {"require_fresh_prices": True, "require_no_lookahead": True},
    },
]


def list_strategies(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or DEFAULT_STRATEGY_PATH
    if not source.exists():
        return [migrate_strategy(dict(item), source="default", touch=False) for item in FALLBACK_STRATEGIES]
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("strategy registry must contain a JSON/YAML list")
    return [migrate_strategy(dict(item), source="default", touch=False) for item in payload]


def get_strategy(strategy_id: str, path: Path | None = None) -> dict[str, Any] | None:
    clean = str(strategy_id or "").strip()
    for strategy in list_strategies(path):
        if strategy.get("strategy_id") == clean:
            return strategy
    return None
