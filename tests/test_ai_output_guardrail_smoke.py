from __future__ import annotations

from scripts.ai_output_guardrail_smoke import REQUIRED_QUERY_SET, run_smoke


def test_ai_output_guardrail_smoke_covers_required_surfaces_and_queries() -> None:
    report = run_smoke()

    assert report["status"] == "passed"
    assert report["production_llm_calls"] == 0
    assert report["provider_mode"] == "deterministic_or_mocked_fast_path"

    expected_surfaces = {
        "quantamental",
        "ml_forecast",
        "macro_ai_brief",
        "ai_portfolio",
        "research_output",
    }
    assert set(report["coverage"]["surfaces"]) == expected_surfaces

    required_case_ids = {case["case_id"] for case in REQUIRED_QUERY_SET}
    for surface, case_ids in report["coverage"]["by_surface"].items():
        assert set(case_ids) == required_case_ids, surface

    assert not report["failures"]
