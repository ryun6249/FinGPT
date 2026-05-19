from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pipelines.signals.research_score import coerce_research_score
from pipelines.signals.rule_based import generate_latest_signals


def test_signal_generation_is_deterministic_and_next_bar_marked() -> None:
    rows = [
        {
            "ticker": "SPY",
            "as_of": "2026-01-10",
            "features": {"momentum_63d": 0.08, "realized_vol_21d": 0.12, "ma_ratio_20_50": 0.03},
            "diagnostics": [],
        },
        {
            "ticker": "TLT",
            "as_of": "2026-01-10",
            "features": {"momentum_63d": -0.02, "realized_vol_21d": 0.18, "ma_ratio_20_50": -0.01},
            "diagnostics": [],
        },
        {
            "ticker": "GLD",
            "as_of": "2026-01-10",
            "features": {"momentum_63d": -0.08, "realized_vol_21d": 0.28, "ma_ratio_20_50": -0.04},
            "diagnostics": [],
        },
    ]

    signals = generate_latest_signals(rows, template="momentum_ranking")

    assert signals[0]["lookahead_policy"] == "close_signal_next_bar_execution"
    assert "execution_date_requires_next_available_bar" in signals[0]["diagnostics"]
    assert signals[0]["signal"] == 1.0
    assert signals[2]["signal"] == 0.0


def test_stale_research_score_is_unavailable() -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()

    score, diagnostics = coerce_research_score({"score": 0.8, "as_of": old, "evidence_ids": ["doc1"]}, max_age_days=7)

    assert score is None
    assert diagnostics[0].startswith("research_score_stale")


def test_volatility_targeting_signal_reports_scaled_exposure() -> None:
    rows = [
        {
            "ticker": "SPY",
            "as_of": "2026-01-10",
            "features": {"realized_vol_21d": 0.24},
            "diagnostics": [],
        }
    ]

    signals = generate_latest_signals(rows, template="volatility_targeting")

    assert signals[0]["signal"] == 0.5
    assert signals[0]["lookahead_policy"] == "close_signal_next_bar_execution"


def test_risk_adjusted_momentum_prefers_stronger_return_per_volatility() -> None:
    rows = [
        {
            "ticker": "SMOOTH",
            "as_of": "2026-01-10",
            "features": {
                "momentum_63d": 0.08,
                "risk_adjusted_momentum_63_21": 1.6,
                "realized_vol_21d": 0.08,
            },
            "diagnostics": [],
        },
        {
            "ticker": "CHOPPY",
            "as_of": "2026-01-10",
            "features": {
                "momentum_63d": 0.12,
                "risk_adjusted_momentum_63_21": 0.4,
                "realized_vol_21d": 0.35,
            },
            "diagnostics": [],
        },
    ]

    signals = generate_latest_signals(rows, template="risk_adjusted_momentum")

    assert signals[0]["signal"] == 1.0
    assert signals[0]["final_score"] > signals[1]["final_score"]
    assert signals[0]["factor_values"]["risk_adjusted_momentum_63_21"] == 1.6
