from pipelines.risk.data_quality import evaluate_risk_data_quality


def test_risk_data_quality_fails_closed_on_blocked_company_payload():
    quality = evaluate_risk_data_quality(
        {
            "INVALID_TEST_TICKER_123": {
                "status": "failed",
                "data_integrity": {"status": "blocked"},
                "data_quality": {"missing_sections": ["company", "fundamentals", "quant"]},
                "freshness": {"status": "partial", "missing_sections": ["company", "prices"]},
                "errors": ["invalid_ticker"],
            }
        },
        {"status": "ok", "coverage": {"enabled_series": 20}, "data_quality": {"status": "ok"}},
    )

    assert quality.decision_usable is False
    assert quality.penalty == 100.0
    assert "INVALID_TEST_TICKER_123:critical_company_data" in quality.missing_inputs


def test_risk_data_quality_allows_asset_proxy_when_prices_are_present():
    quality = evaluate_risk_data_quality(
        {
            "TLT": {
                "status": "failed",
                "ticker": "TLT",
                "company": {"ticker": "TLT", "quote_type": "ETF"},
                "quant": {"status": "ok", "price_history": [{"date": "2026-05-20", "close": 84.0}]},
                "data_integrity": {"status": "blocked"},
                "data_quality": {"missing_sections": ["fundamentals"]},
                "freshness": {
                    "status": "partial",
                    "missing_sections": ["sec"],
                    "unknown_sections": ["fundamentals"],
                    "sections": {"prices": {"status": "fresh"}},
                },
            }
        },
        {"status": "ok", "coverage": {"enabled_series": 20}, "data_quality": {"status": "ok"}},
    )

    assert quality.decision_usable is True
    assert quality.freshness == "partial"
    assert "TLT:asset_proxy_price_macro_scope" in quality.provider_warnings
    assert "TLT:fundamentals" in quality.missing_inputs
