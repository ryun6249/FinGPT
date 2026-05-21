from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "app" / "web" / "index.html"
APP_JS = ROOT / "app" / "web" / "app.js"
STYLES_CSS = ROOT / "app" / "web" / "styles.css"


def test_risk_static_ui_contract_markers():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    for marker in [
        'id="riskDashboardTab"',
        'data-testid="risk-dashboard-tab"',
        'data-dashboard-tab="risk"',
        'id="riskWorkbenchPanel"',
        'id="riskExecutiveStrip"',
        'id="riskDecisionBrief"',
        'id="riskDriverWaterfall"',
        'id="riskCompanyTable"',
        'id="riskMacroPressurePanel"',
        'id="riskTransmissionMatrix"',
        'id="riskScenarioMatrix"',
        'id="riskEvidenceDrawer"',
        'id="forecastRiskPrefillNotice"',
        'data-testid="risk-run"',
    ]:
        assert marker in html

    for marker in [
        "risk: {",
        "function loadRiskWorkbench",
        "function renderRiskWorkbench",
        "function renderRiskDecisionBrief",
        "function riskActionStatusClass",
        "function riskReadinessStatusClass",
        "decision_path",
        "risk-decision-path",
        "decision_compass",
        "risk-decision-compass",
        "risk-compass-step",
        "decision_quality",
        "risk-decision-quality",
        "evidence_coverage",
        "risk-evidence-coverage",
        "risk-evidence-coverage-detail",
        "compatibility_matrix",
        "risk-compatibility-matrix",
        "risk-compatibility-detail",
        "ai_output_controls",
        "risk-ai-output-controls",
        "risk-ai-output-detail",
        "function renderRiskTransmissionMatrix",
        "function riskPortfolioPositions",
        "function riskRequestPayload",
        "action_checklist",
        "risk-action-checklist",
        "monitoring_triggers",
        "risk-monitoring-triggers",
        "priority_map",
        "risk-priority-map",
        "confidence_factors",
        "risk-confidence-ladder",
        "handoff_queue",
        "risk-handoff-queue",
        "ml_validation_tests",
        "risk-ml-validation-tests",
        "forecast_prefill",
        "launch_href",
        "risk-ml-validation-link",
        "forecast_validation_plan",
        "risk-forecast-validation-plan",
        "risk-forecast-validation-detail",
        "function applyForecastPrefillFromLocation",
        "forecastRiskHandoff",
        "function renderForecastRiskHandoffNotice",
        "source_context",
        "riskTestType",
        "riskTestPriority",
        "riskTestLabel",
        "risk-forecast-prefill-card",
        "run_lineage",
        "risk-run-lineage",
        "service_readiness",
        "risk-service-readiness",
        "release_packet",
        "risk-release-packet",
        "deployment_checks",
        "input_receipt",
        "risk-input-receipt",
        "normalized_positions",
        "coverage_scope",
        "asset_proxy_price_macro_scope",
        '"#risk"',
        "state.risk",
    ]:
        assert marker in source

    assert '[data-dashboard-tab="risk"]' in css
    assert ".risk-surface" in css
    assert ".risk-command-bar" in css
    assert ".risk-decision-brief" in css
    assert ".risk-decision-compass" in css
    assert ".risk-decision-quality" in css
    assert ".risk-evidence-coverage" in css
    assert ".risk-compatibility-matrix" in css
    assert ".risk-forecast-validation-plan" in css
    assert ".risk-forecast-validation-detail" in css
    assert ".risk-ai-output-controls" in css
