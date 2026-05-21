from fastapi.testclient import TestClient

from app.api.server import app
from core.schemas.risk import RiskWorkbenchRequest
from pipelines.risk.service import build_risk_workbench_response


client = TestClient(app)


def _sample_company_payload(ticker: str = "NVDA") -> dict:
    return {
        "status": "ok",
        "ticker": ticker,
        "generated_at": "2026-05-21T00:00:00+00:00",
        "company": {"ticker": ticker, "name": f"{ticker} Corp", "sector": "Technology", "industry": "Semiconductors"},
        "risk": {
            "risk_score": 72,
            "balance_sheet_risk": {"score": 70},
            "valuation_risk": {"score": 45},
            "price_risk": {"score": 60},
            "volatility_risk": {"score": 55},
            "drawdown_risk": {"score": 65},
            "risk_flags": ["valuation_fragility"],
        },
        "factors": {"quality_score": 82, "growth_score": 78, "value_score": 45},
        "quant": {"status": "ok", "metrics": {"volatility": {"realized_volatility_60d": 0.32}, "drawdown": {"current_drawdown": -0.12}}},
        "freshness": {"status": "fresh", "freshness_score": 95, "missing_sections": [], "stale_sections": []},
        "data_quality": {"data_quality_score": 92, "missing_sections": [], "warnings": []},
        "data_integrity": {"status": "ok", "usable_for_signal": True},
        "sec_evidence": {"status": "ok"},
    }


def _sample_macro_payload() -> dict:
    return {
        "status": "ok",
        "coverage": {"enabled_series": 34},
        "data_quality": {"status": "ok"},
        "overview": {
            "regime": {"name": "tight_policy", "risk_level": "watch", "confidence": 0.82},
            "signals": [
                {"signal_id": "rates_pressure", "score": 68, "status": "watch"},
                {"signal_id": "credit_tone", "score": 55, "status": "neutral"},
                {"signal_id": "growth_inflation", "score": 58, "status": "watch"},
            ],
        },
    }


def _sample_asset_proxy_payload(ticker: str = "TLT") -> dict:
    return {
        "status": "failed",
        "ticker": ticker,
        "generated_at": "2026-05-21T00:00:00+00:00",
        "company": {
            "ticker": ticker,
            "name": "iShares 20+ Year Treasury Bond ETF",
            "quote_type": "ETF",
        },
        "risk": {
            "risk_score": 76,
            "price_risk": {"score": 45},
            "volatility_risk": {"score": 80},
            "drawdown_risk": {"score": 70},
            "valuation_risk": {"score": 100},
        },
        "factors": {"quality_score": None, "growth_score": None},
        "quant": {
            "status": "ok",
            "price_history": [{"date": "2026-05-20", "close": 84.0}],
            "metrics": {
                "volatility": {"realized_volatility_60d": 0.10},
                "drawdown": {"current_drawdown": -0.11},
            },
        },
        "freshness": {
            "status": "partial",
            "freshness_score": 85,
            "missing_sections": ["sec"],
            "unknown_sections": ["fundamentals"],
            "sections": {"prices": {"status": "fresh"}},
        },
        "data_quality": {
            "data_quality_score": 35,
            "missing_sections": ["fundamentals"],
            "warnings": ["financial_statement_history_missing"],
        },
        "data_integrity": {"status": "blocked", "blocking_sections": ["fundamentals"]},
        "sec_evidence": {"status": "missing"},
    }


def test_risk_workbench_request_accepts_company_mode():
    request = RiskWorkbenchRequest(mode="company", tickers=["NVDA"])
    assert request.mode == "company"
    assert request.tickers == ["NVDA"]
    assert request.lookback_days == 756


def test_risk_workbench_response_populates_deterministic_contract():
    request = RiskWorkbenchRequest(mode="company", tickers=["NVDA"])
    payload = build_risk_workbench_response(
        request=request,
        company_payloads={"NVDA": _sample_company_payload("NVDA")},
        macro_payload=_sample_macro_payload(),
    )

    assert payload.risk_index is not None
    assert payload.decision_usable is True
    assert payload.company_profiles[0].ticker == "NVDA"
    assert payload.transmission_channels
    assert payload.scenario_matrix
    assert payload.decision_brief.review_questions
    assert "리스크" in payload.decision_brief.summary
    assert payload.decision_path.status == "review"
    assert payload.decision_path.primary_action
    assert payload.decision_path.primary_handoff_href.startswith("/ui/#")
    assert payload.decision_path.ml_validation_href
    assert payload.decision_quality.status == "review"
    assert 0 <= payload.decision_quality.score <= 100
    assert payload.decision_quality.basis
    assert payload.decision_quality.next_best_actions
    assert "release_packet" in payload.decision_quality.evidence_refs
    assert payload.decision_compass.status == "review"
    assert payload.decision_compass.headline
    assert payload.decision_compass.primary_focus
    assert {item.step_id for item in payload.decision_compass.steps} >= {
        "verify_input_and_quality",
        "review_evidence_coverage",
        "run_forecast_validation",
        "control_ai_output",
        "review_service_gate",
    }
    assert "decision_quality" in payload.decision_compass.evidence_refs
    assert "ai_output_controls" in payload.decision_compass.evidence_refs
    assert payload.evidence_coverage.status in {"ok", "review"}
    assert 0 <= payload.evidence_coverage.score <= 100
    assert {item.domain for item in payload.evidence_coverage.items} >= {
        "input",
        "company",
        "macro",
        "scenario",
        "forecast",
        "service",
        "evidence",
    }
    assert any(item.coverage_id == "company_profile_coverage" for item in payload.evidence_coverage.items)
    assert "evidence_coverage" in payload.decision_quality.evidence_refs
    assert payload.compatibility_matrix.status in {"ok", "review"}
    assert payload.compatibility_matrix.rows
    assert payload.compatibility_matrix.rows[0].subject == "NVDA"
    assert payload.compatibility_matrix.rows[0].forecast_launch_href
    assert any("ML Forecast" in item for item in payload.compatibility_matrix.rows[0].supported_workflows)
    assert payload.action_checklist
    assert payload.monitoring_triggers
    assert payload.priority_map
    assert payload.confidence_factors
    assert payload.handoff_queue
    assert payload.ml_validation_tests
    assert payload.forecast_validation_plan.status == "review"
    assert payload.forecast_validation_plan.primary_test_id in {
        "macro_feature_leakage_check",
        "severe_scenario_forecast_backtest",
        "walk_forward_baseline",
    }
    assert payload.forecast_validation_plan.primary_launch_href
    assert payload.forecast_validation_plan.run_order
    assert payload.forecast_validation_plan.experiment_controls
    assert payload.forecast_validation_plan.acceptance_criteria
    assert "source_context" in payload.forecast_validation_plan.evidence_refs
    assert {item.handoff_id for item in payload.handoff_queue} >= {
        "macro_pressure_review",
        "quantamental_company_drilldown",
        "ml_forecast_validation_test",
        "service_wrapper_gate",
    }
    assert payload.priority_map[0].rank == 1
    assert payload.priority_map[0].subject in {"NVDA", "MACRO", "DATA_QUALITY"}
    assert {item.factor_id for item in payload.confidence_factors} >= {
        "company_coverage",
        "macro_backdrop",
        "data_quality",
        "scenario_coverage",
        "service_controls",
    }
    assert {item.test_id for item in payload.ml_validation_tests} >= {
        "walk_forward_baseline",
        "macro_feature_leakage_check",
        "severe_scenario_forecast_backtest",
    }
    assert payload.ai_output_controls.status == "review"
    assert payload.ai_output_controls.language == "ko"
    assert "risk_run_id" in payload.ai_output_controls.required_evidence_refs
    assert "input_hash" in payload.ai_output_controls.required_evidence_refs
    assert "compatibility_matrix" in payload.ai_output_controls.required_evidence_refs
    assert payload.ai_output_controls.blocked_claims
    assert any("risk_run_id=" in item for item in payload.ai_output_controls.prompt_context)
    assert payload.ml_validation_tests[0].target_tickers
    assert any(item.forecast_prefill and item.launch_href for item in payload.ml_validation_tests)
    baseline_test = next(item for item in payload.ml_validation_tests if item.test_id == "walk_forward_baseline")
    assert baseline_test.forecast_prefill is not None
    assert baseline_test.forecast_prefill.ticker == "NVDA"
    assert baseline_test.forecast_prefill.validation_method == "walk_forward"
    assert baseline_test.launch_href is not None
    assert "tab=ml-forecast" in baseline_test.launch_href
    assert "forecastTicker=NVDA" in baseline_test.launch_href
    assert "riskTestType=walk_forward" in baseline_test.launch_href
    assert "riskTestPriority=2" in baseline_test.launch_href
    assert "riskTestLabel=" in baseline_test.launch_href
    assert payload.run_lineage.service_version == "risk-workbench-v1"
    assert payload.run_lineage.subjects == ["NVDA"]
    assert payload.run_lineage.adapter_statuses["company"] == "ok"
    assert payload.run_lineage.evidence_count == len(payload.evidence)
    assert payload.input_receipt.status == "ok"
    assert payload.input_receipt.mode == "company"
    assert payload.input_receipt.subjects == ["NVDA"]
    assert payload.input_receipt.normalized_positions[0].ticker == "NVDA"
    assert payload.input_receipt.normalized_positions[0].weight == 1.0
    assert any("mode=company" in item for item in payload.input_receipt.replay_notes)
    assert {item.action_id for item in payload.action_checklist} >= {
        "data_quality_gate",
        "top_driver_review",
        "scenario_stress_review",
        "service_release_gate",
    }
    assert {item.trigger_id for item in payload.monitoring_triggers} >= {
        "data_quality_monitor",
        "dominant_driver_monitor",
        "transmission_channel_monitor",
        "severe_scenario_monitor",
        "service_readiness_monitor",
    }
    assert payload.action_checklist[0].status == "ok"
    assert payload.monitoring_triggers[0].status == "ok"
    assert payload.service_readiness.status == "ready"
    assert "risk_run_id" in " ".join(payload.service_readiness.checklist)
    assert payload.release_packet.status == "review_required"
    assert payload.release_packet.contract_version == "risk-release-packet-v1"
    assert "/api/v1/risk/workbench" in payload.release_packet.api_routes
    assert "risk_run_id" in payload.release_packet.required_audit_fields
    assert any("check_ui_contract.py" in command for command in payload.release_packet.validation_commands)
    assert {item.check_id for item in payload.release_packet.deployment_checks} >= {
        "api_contract",
        "decision_data_gate",
        "run_lineage_replay",
        "forecast_source_context",
        "ai_output_guardrails",
        "external_service_controls",
    }
    assert next(
        item for item in payload.release_packet.deployment_checks if item.check_id == "external_service_controls"
    ).status == "review"
    assert "단일 종목" in payload.decision_brief.summary
    serialized = payload.model_dump_json()
    assert not any(marker in serialized for marker in ["由", "李", "諛", "湲", "좊", "쒗", "�"])
    assert payload.not_investment_advice is True


def test_risk_workbench_response_honors_english_output_language():
    request = RiskWorkbenchRequest(mode="company", tickers=["NVDA"], output_language="en")
    payload = build_risk_workbench_response(
        request=request,
        company_payloads={"NVDA": _sample_company_payload("NVDA")},
        macro_payload=_sample_macro_payload(),
    )

    assert "risk run" in payload.decision_brief.summary
    assert payload.decision_brief.review_questions[0].startswith("Which top driver")
    assert any(item.label == "Check service release gate" for item in payload.action_checklist)
    assert any(item.label == "Monitor service release readiness" for item in payload.monitoring_triggers)
    assert any(item.label == "Run ML Forecast validation test" for item in payload.handoff_queue)
    assert any(item.target_tab == "ml_forecast" for item in payload.handoff_queue)
    assert any(item.label == "Run walk-forward baseline" for item in payload.ml_validation_tests)
    assert any(item.test_type == "leakage_check" for item in payload.ml_validation_tests)
    assert payload.forecast_validation_plan.status == "review"
    assert payload.forecast_validation_plan.primary_label
    assert any("source_context" in item for item in payload.forecast_validation_plan.experiment_controls)
    assert payload.priority_map
    assert any(item.factor_id == "service_controls" for item in payload.confidence_factors)
    assert payload.run_lineage.scenario_set == "base_adverse_severe"
    assert payload.service_readiness.status == "ready"
    assert payload.input_receipt.status == "ok"
    assert "Typed /api/v1/risk/workbench contract returned" in payload.service_readiness.checklist
    assert payload.release_packet.status == "review_required"
    assert any(
        item.label == "External auth, rate limit, retention, and monitoring are defined"
        for item in payload.release_packet.deployment_checks
    )
    assert payload.decision_path.status == "review"
    assert payload.decision_path.ml_validation_href
    assert payload.decision_quality.status == "review"
    assert "Service-readiness gate is ready." in payload.decision_quality.basis
    assert any("platform auth" in item for item in payload.decision_quality.next_best_actions)
    assert payload.decision_compass.status == "review"
    assert any(item.target == "ml_forecast" for item in payload.decision_compass.steps)
    assert any(item.href and "tab=ml-forecast" in item.href for item in payload.decision_compass.steps)
    assert any(item.label == "Evidence inventory" for item in payload.evidence_coverage.items)
    assert payload.compatibility_matrix.summary.startswith("Compatibility:")
    assert any("Risk company review" in row.supported_workflows for row in payload.compatibility_matrix.rows)
    assert payload.ai_output_controls.language == "en"
    assert payload.ai_output_controls.status == "review"
    assert "decision_quality" in payload.ai_output_controls.required_evidence_refs
    assert "model-written Risk narratives" in payload.ai_output_controls.grounding_summary


def test_risk_workbench_response_brief_surfaces_blocked_inputs():
    request = RiskWorkbenchRequest(mode="company", tickers=["INVALID_TEST_TICKER_123"])
    payload = build_risk_workbench_response(
        request=request,
        company_payloads={
            "INVALID_TEST_TICKER_123": {
                "status": "failed",
                "ticker": "INVALID_TEST_TICKER_123",
                "data_integrity": {"status": "blocked"},
                "data_quality": {"missing_sections": ["company", "fundamentals", "quant"]},
                "freshness": {"status": "partial", "missing_sections": ["company", "prices"]},
                "errors": ["invalid_ticker"],
            }
        },
        macro_payload=_sample_macro_payload(),
    )

    assert payload.risk_index is None
    assert payload.decision_usable is False
    assert payload.decision_brief.blocked_reasons
    assert "INVALID_TEST_TICKER_123:critical_company_data" in payload.decision_brief.blocked_reasons
    assert payload.action_checklist[0].action_id == "data_quality_gate"
    assert payload.action_checklist[0].status == "blocked"
    assert payload.monitoring_triggers[0].trigger_id == "data_quality_monitor"
    assert payload.monitoring_triggers[0].status == "blocked"
    assert payload.service_readiness.status == "blocked"
    assert payload.input_receipt.status == "blocked"
    assert "INVALID_TEST_TICKER_123" in " ".join(payload.input_receipt.compatibility_notes)
    assert payload.release_packet.status == "blocked"
    assert next(
        item for item in payload.release_packet.deployment_checks if item.check_id == "decision_data_gate"
    ).status == "blocked"
    assert payload.decision_path.status == "blocked"
    assert payload.decision_path.ml_validation_href is None
    assert payload.decision_quality.status == "blocked"
    assert payload.decision_quality.blockers
    assert payload.decision_quality.score <= 25
    assert payload.decision_compass.status == "blocked"
    assert any(item.step_id == "run_forecast_validation" and item.status == "blocked" for item in payload.decision_compass.steps)
    assert payload.evidence_coverage.status == "blocked"
    assert "company" in payload.evidence_coverage.blocked_domains
    assert "forecast" in payload.evidence_coverage.blocked_domains
    assert payload.compatibility_matrix.status == "blocked"
    assert payload.compatibility_matrix.rows[0].status == "blocked"
    assert payload.compatibility_matrix.rows[0].forecast_launch_href is None
    assert payload.compatibility_matrix.rows[0].blocked_workflows
    assert payload.service_readiness.blockers
    assert payload.run_lineage.adapter_statuses["data_quality"] == "blocked"
    assert any(item.subject == "DATA_QUALITY" for item in payload.priority_map)
    assert payload.handoff_queue[0].handoff_id == "risk_data_quality_repair"
    assert payload.handoff_queue[0].status == "blocked"
    assert payload.ml_validation_tests[0].test_id == "risk_data_gate_recheck"
    assert payload.ml_validation_tests[0].status == "blocked"
    assert payload.forecast_validation_plan.status == "blocked"
    assert payload.forecast_validation_plan.primary_test_id == "risk_data_gate_recheck"
    assert payload.forecast_validation_plan.primary_launch_href is None
    assert payload.forecast_validation_plan.blocked_reasons
    assert payload.ai_output_controls.status == "blocked"
    assert "data_quality.missing_inputs" in payload.ai_output_controls.required_evidence_refs


def test_risk_workbench_response_keeps_asset_proxy_decision_usable_without_fabricated_fundamentals():
    request = RiskWorkbenchRequest(mode="company", tickers=["TLT"])
    payload = build_risk_workbench_response(
        request=request,
        company_payloads={"TLT": _sample_asset_proxy_payload("TLT")},
        macro_payload=_sample_macro_payload(),
    )

    profile = payload.company_profiles[0]
    solvency = next(vector for vector in profile.vectors if vector.vector == "company_solvency")

    assert payload.risk_index is not None
    assert payload.decision_usable is True
    assert payload.data_quality.freshness == "partial"
    assert profile.coverage_scope == "asset_proxy"
    assert profile.asset_class == "bond_etf"
    assert solvency.score is None
    assert solvency.decision_usable is False
    assert "TLT:fundamentals" in payload.data_quality.missing_inputs
    assert payload.decision_brief.blocked_reasons == []
    assert any(
        item.action_id == "asset_proxy_scope_review" and item.status == "review"
        for item in payload.action_checklist
    )
    assert any(
        item.trigger_id == "asset_proxy_scope_monitor" and item.status == "review"
        for item in payload.monitoring_triggers
    )
    assert payload.service_readiness.status == "review_required"
    assert payload.input_receipt.status == "review"
    assert payload.input_receipt.normalized_positions[0].coverage_scope == "asset_proxy"
    assert any("TLT" in item for item in payload.input_receipt.compatibility_notes)
    assert payload.release_packet.status == "review_required"
    assert next(
        item for item in payload.release_packet.deployment_checks if item.check_id == "asset_proxy_release_scope"
    ).status == "review"
    assert payload.decision_path.status == "review"
    assert payload.decision_path.ml_validation_href
    assert payload.decision_quality.status == "review"
    assert payload.decision_quality.basis
    assert payload.decision_compass.status == "review"
    assert "TLT" in payload.decision_compass.primary_focus
    assert payload.evidence_coverage.status == "review"
    assert "company" in payload.evidence_coverage.review_domains
    assert payload.compatibility_matrix.status == "review"
    assert payload.compatibility_matrix.rows[0].coverage_scope == "asset_proxy"
    assert payload.compatibility_matrix.rows[0].forecast_launch_href
    assert any("펀더멘털" in item for item in payload.compatibility_matrix.rows[0].blocked_workflows)
    assert any(
        item.coverage_id == "company_profile_coverage" and item.coverage_scope == "asset_proxy"
        for item in payload.evidence_coverage.items
    )
    assert any("TLT" in item for item in payload.service_readiness.warnings)
    assert payload.run_lineage.adapter_statuses["service_readiness"] == "review_required"
    assert any(item.subject == "TLT" for item in payload.priority_map)
    assert any(item.handoff_id == "asset_proxy_scope_handoff" for item in payload.handoff_queue)
    asset_proxy_test = next(item for item in payload.ml_validation_tests if item.test_id == "asset_proxy_validation")
    assert asset_proxy_test.forecast_prefill is not None
    assert asset_proxy_test.forecast_prefill.include_macro is True
    assert asset_proxy_test.forecast_prefill.include_cross_asset is True
    assert asset_proxy_test.launch_href is not None
    assert "forecastBenchmark=SPY" in asset_proxy_test.launch_href
    assert any("TLT" in item.target_tickers for item in payload.ml_validation_tests)
    assert payload.forecast_validation_plan.status == "review"
    assert payload.forecast_validation_plan.primary_test_id == "asset_proxy_validation"
    assert payload.forecast_validation_plan.primary_launch_href == asset_proxy_test.launch_href
    assert payload.forecast_validation_plan.run_order[0].split(":")[1] == "asset_proxy_validation"
    assert payload.ai_output_controls.status == "review"
    assert "evidence_coverage" in payload.ai_output_controls.required_evidence_refs


def test_risk_workbench_portfolio_forecast_plan_prioritizes_portfolio_validation():
    request = RiskWorkbenchRequest(
        mode="portfolio",
        positions=[
            {"ticker": "NVDA", "weight": 0.4},
            {"ticker": "MSFT", "weight": 0.35},
            {"ticker": "TLT", "weight": 0.25},
        ],
    )
    payload = build_risk_workbench_response(
        request=request,
        company_payloads={
            "NVDA": _sample_company_payload("NVDA"),
            "MSFT": _sample_company_payload("MSFT"),
            "TLT": _sample_asset_proxy_payload("TLT"),
        },
        macro_payload=_sample_macro_payload(),
    )

    assert payload.decision_usable is True
    assert any(item.test_id == "portfolio_component_oos_check" for item in payload.ml_validation_tests)
    assert any(item.test_id == "asset_proxy_validation" for item in payload.ml_validation_tests)
    assert payload.forecast_validation_plan.status == "review"
    assert payload.forecast_validation_plan.primary_test_id == "portfolio_component_oos_check"
    assert payload.forecast_validation_plan.primary_launch_href
    assert payload.forecast_validation_plan.run_order[0].split(":")[1] == "portfolio_component_oos_check"


def test_risk_health_endpoint():
    response = client.get("/api/v1/risk/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "risk"


def test_risk_workbench_endpoint_uses_service_adapters(monkeypatch):
    from app.api.routers import risk as risk_router

    monkeypatch.setattr(risk_router, "load_company_payloads", lambda request: {"NVDA": _sample_company_payload("NVDA")})
    monkeypatch.setattr(risk_router, "load_macro_payload", _sample_macro_payload)

    response = client.post("/api/v1/risk/workbench", json={"mode": "company", "tickers": ["NVDA"]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "company"
    assert payload["risk_index"] is not None
    assert payload["decision_usable"] is True
    assert payload["action_checklist"]
    assert payload["decision_path"]["status"] in {"ok", "review", "blocked"}
    assert payload["decision_path"]["primary_action"]
    assert payload["decision_quality"]["status"] in {"ok", "review", "blocked"}
    assert payload["decision_quality"]["basis"]
    assert payload["decision_compass"]["steps"]
    assert payload["decision_compass"]["status"] in {"ok", "review", "blocked"}
    assert payload["evidence_coverage"]["items"]
    assert payload["evidence_coverage"]["status"] in {"ok", "review", "blocked"}
    assert payload["compatibility_matrix"]["rows"]
    assert payload["compatibility_matrix"]["status"] in {"ok", "review", "blocked"}
    assert payload["monitoring_triggers"]
    assert payload["priority_map"]
    assert payload["handoff_queue"]
    assert payload["ml_validation_tests"]
    assert payload["forecast_validation_plan"]["status"] in {"ok", "review", "blocked"}
    assert payload["forecast_validation_plan"]["evidence_refs"]
    assert payload["run_lineage"]["adapter_statuses"]["company"] == "ok"
    assert payload["release_packet"]["deployment_checks"]
    assert payload["release_packet"]["contract_version"] == "risk-release-packet-v1"
    assert payload["ai_output_controls"]["required_evidence_refs"]
    assert payload["ai_output_controls"]["blocked_claims"]
    assert payload["company_profiles"][0]["ticker"] == "NVDA"
