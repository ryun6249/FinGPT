from __future__ import annotations

import json
import re
from types import SimpleNamespace

from pipelines.strategies import generator


DISALLOWED_NARRATIVE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")


def _assert_korean_narrative(items: list[str]) -> None:
    assert items
    for item in items:
        assert re.search(r"[\uac00-\ud7a3]", item)
        assert not DISALLOWED_NARRATIVE_RE.search(item)


def test_deterministic_strategy_generation_returns_korean_review_text() -> None:
    result = generator.generate_strategy_from_prompt(
        "63일 모멘텀 상위 2개를 사고, 21일 변동성이 높은 종목은 비중을 낮춰주세요.",
        context={"top_n": 2, "lookback": 63, "transaction_cost_bps": 5, "slippage_bps": 2},
        use_local_llm=False,
    )

    assert result["status"] == "success"
    assert result["model_status"] == "deterministic_fallback"
    assert result["strategy"]["execution"]["trade_at"] == "next_bar_close"
    _assert_korean_narrative(result["advantages"])
    _assert_korean_narrative(result["disadvantages"])


def test_strategy_generation_parameter_tuning_applies_auditable_values() -> None:
    result = generator.generate_strategy_from_prompt(
        "Keep drawdown controlled and reduce turnover for a momentum strategy.",
        context={"top_n": 4, "asset_count": 3, "transaction_cost_bps": 5, "slippage_bps": 2},
        use_local_llm=False,
        parameter_tuning={
            "enabled": True,
            "objective": "drawdown_control",
            "search_space": {
                "lookback": [21, 63, 126],
                "vol_lookback": [14, 21, 42],
                "top_n": [1, 2, 4],
                "rebalance_every": [5, 21, 42],
                "portfolio_method": ["equal_weight", "risk_parity"],
            },
        },
    )

    tuning = result["parameter_tuning"]
    strategy = result["strategy"]
    assert result["model_status"] == "deterministic_fallback"
    assert result["llm_diagnostics"]["fallback_used"] is True
    assert result["progress"]["percent"] == 100
    assert tuning["enabled"] is True
    assert tuning["status"] == "applied"
    assert tuning["applied_values"]["lookback"] == 126
    assert tuning["applied_values"]["top_n"] == 3
    assert tuning["applied_values"]["portfolio_method"] == "risk_parity"
    assert strategy["features"]["momentum_63d"]["lookback"] == 126
    assert strategy["signal"]["top_n"] == 3
    assert strategy["diagnostics"]["parameter_tuning"]["source"] == "deterministic_rules"


def test_local_llm_chinese_review_text_is_repaired_to_korean(monkeypatch) -> None:
    def fake_call_local_llm(**_: object) -> str:
        return json.dumps(
            {
                "strategy": {
                    "name": "长期增长潜力",
                    "schema_version": "quant_strategy_v1",
                    "frequency": "daily",
                    "features": {"momentum_63d": {"id": "momentum_63d", "lookback": 63}},
                    "signal": {"type": "rank_top_n", "top_n": 2},
                    "portfolio": {"method": "equal_weight", "max_weight": 0.5},
                    "execution": {"trade_at": "next_bar_close"},
                },
                "advantages": ["长期增长潜力", "通过调整权重来降低风险"],
                "disadvantages": ["仅基于历史数据进行决策可能无法完全捕捉市场变化"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(generator, "_call_local_llm", fake_call_local_llm)
    monkeypatch.setattr(
        generator,
        "load_settings",
        lambda: SimpleNamespace(primary_model="qwen2.5:7b", ollama_base_url="http://localhost:11434"),
    )

    result = generator.generate_strategy_from_prompt(
        "63일 모멘텀 상위 2개를 사고, 21일 변동성이 높은 종목은 비중을 낮춰주세요.",
        context={"top_n": 2, "lookback": 63, "transaction_cost_bps": 5, "slippage_bps": 2},
        use_local_llm=True,
    )

    assert result["status"] == "success"
    assert result["model_status"] == "local_llm"
    assert "strategy_review_language_repaired_to_korean" in result["warnings"]
    assert not DISALLOWED_NARRATIVE_RE.search(result["strategy"]["name"])
    _assert_korean_narrative(result["advantages"])
    _assert_korean_narrative(result["disadvantages"])
