from __future__ import annotations

from core.schemas.risk import RiskCompanyProfile, RiskMacroBackdrop, RiskTransmissionChannel
from pipelines.risk.aggregation import average_score, clamp_score, risk_level


def _macro_score(backdrop: RiskMacroBackdrop, vector_name: str) -> float:
    matches = [vector.score for vector in backdrop.vectors if vector.vector == vector_name]
    return average_score(matches) or 50.0


def _sector_sensitivity(profile: RiskCompanyProfile, channel: str) -> float:
    ticker = profile.ticker.upper()
    sector = f"{profile.sector} {profile.industry}".lower()
    if ticker in {"TLT", "IEF", "SHY"} and channel == "rates_duration":
        return 0.95
    if any(token in sector for token in ("bank", "financial", "capital markets")) and channel in {"curve_credit", "credit_liquidity"}:
        return 0.85
    if any(token in sector for token in ("semiconductor", "technology", "software", "internet")) and channel in {"valuation_multiple", "liquidity_beta"}:
        return 0.80
    if any(token in sector for token in ("energy", "materials", "industrial")) and channel == "commodity_input":
        return 0.70
    if channel in {"rates_duration", "credit_liquidity"}:
        return 0.55
    return 0.45


def build_transmission_channels(
    company_profiles: list[RiskCompanyProfile],
    macro_backdrop: RiskMacroBackdrop,
) -> list[RiskTransmissionChannel]:
    channels: list[RiskTransmissionChannel] = []
    if not company_profiles:
        return channels

    channel_specs = [
        ("rates_duration", "macro_policy_rates", "Higher real or nominal rates pressure duration, leverage, and discount-rate-sensitive assets."),
        ("curve_credit", "credit_liquidity", "Curve shape and credit spreads transmit through bank margins, funding cost, and default risk."),
        ("credit_liquidity", "credit_liquidity", "Liquidity tightening can amplify refinancing and market-depth risk."),
        ("growth_inflation", "macro_growth_inflation", "Growth and inflation shocks transmit through revenue durability and margin pressure."),
        ("valuation_multiple", "macro_policy_rates", "Discount-rate shifts can compress valuation multiples for long-duration equities."),
        ("liquidity_beta", "credit_liquidity", "Funding stress and risk-off beta can raise equity and factor drawdown risk."),
        ("commodity_input", "macro_growth_inflation", "Commodity and input-cost pressure can damage margins where exposure is material."),
    ]
    for channel, macro_vector, mechanism in channel_specs:
        sensitivities = [_sector_sensitivity(profile, channel) for profile in company_profiles]
        sensitivity = round(sum(sensitivities) / len(sensitivities), 2)
        pressure_score = _macro_score(macro_backdrop, macro_vector)
        risk_delta = clamp_score(pressure_score * sensitivity * 0.45, default=0.0) or 0.0
        if risk_delta < 8 and channel not in {"rates_duration", "credit_liquidity", "growth_inflation"}:
            continue
        channels.append(
            RiskTransmissionChannel(
                channel=channel,
                pressure=risk_level(pressure_score),
                sensitivity=sensitivity,
                risk_delta=round(risk_delta, 2),
                affected_subjects=[profile.ticker for profile in company_profiles if _sector_sensitivity(profile, channel) >= 0.55],
                mechanism=mechanism,
                evidence_refs=["macro:dashboard", *[ref for profile in company_profiles for ref in profile.evidence_refs[:1]]],
            )
        )
    return channels

