from core.schemas.risk import RiskCompanyProfile, RiskMacroBackdrop, RiskVector
from pipelines.risk.transmission import build_transmission_channels


def test_transmission_channels_surface_sector_specific_paths():
    macro = RiskMacroBackdrop(
        regime="tight_policy",
        risk_level="elevated",
        confidence=80,
        vectors=[
            RiskVector(vector="macro_policy_rates", score=70, level="elevated", confidence=80),
            RiskVector(vector="credit_liquidity", score=65, level="elevated", confidence=80),
            RiskVector(vector="macro_growth_inflation", score=55, level="elevated", confidence=80),
        ],
    )
    profiles = [
        RiskCompanyProfile(ticker="JPM", sector="Financial Services", industry="Banks", risk_index=45, risk_level="moderate"),
        RiskCompanyProfile(ticker="TLT", sector="ETF", industry="Long Duration Treasury", risk_index=50, risk_level="elevated"),
    ]

    channels = build_transmission_channels(profiles, macro)
    names = {channel.channel for channel in channels}

    assert "curve_credit" in names
    assert "rates_duration" in names

