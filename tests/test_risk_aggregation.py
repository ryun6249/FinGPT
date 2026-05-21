from pipelines.risk.aggregation import (
    BASE_RISK_WEIGHTS,
    concentration_penalty,
    risk_level,
    weighted_score,
)


def test_base_risk_weighted_score_uses_available_components():
    score = weighted_score(
        {
            "company_fundamental_vulnerability": 60,
            "market_behavior_risk": 50,
            "macro_regime_risk": 40,
            "credit_liquidity_risk": 30,
            "transmission_sensitivity": 20,
            "data_quality_penalty": 10,
        },
        BASE_RISK_WEIGHTS,
    )
    assert score == 40.5
    assert risk_level(score) == "moderate"


def test_concentration_penalty_increases_for_single_name_portfolio():
    assert concentration_penalty([1.0]) > concentration_penalty([0.25, 0.25, 0.25, 0.25])

