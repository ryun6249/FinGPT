from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api import server as api_server
from app.api.routers import research as research_router
from app.api.routers import system as system_router
from core.schemas.response import AnalysisResponse
from core.schemas.topic import TopicResponse


def _parse_sse(raw: str) -> list[dict]:
    frames = []
    for block in raw.strip().split("\n\n"):
        if not block or block.startswith(":"):
            continue
        event = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        try:
            data = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            data = "\n".join(data_lines)
        frames.append({"event": event, "data": data})
    return frames


class ApiRoutingContractTests(unittest.TestCase):
    def test_preflight_status_uses_cache_for_polling_tabs(self):
        client = TestClient(api_server.app)
        system_router._preflight_cache["ts"] = 0.0
        system_router._preflight_cache["report"] = None
        try:
            with patch.object(system_router, "_run_preflight_sync", return_value={"passed": True, "checks": []}) as run_preflight:
                first = client.get("/api/v1/preflight")
                second = client.get("/api/v1/preflight")

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertGreaterEqual(first.json()["ttl_seconds"], 120)
            self.assertEqual(run_preflight.call_count, 1)
        finally:
            system_router._preflight_cache["ts"] = 0.0
            system_router._preflight_cache["report"] = None

    def test_config_exposes_fingpt_integration_status(self):
        client = TestClient(api_server.app)
        resp = client.get("/api/v1/config")

        self.assertEqual(resp.status_code, 200)
        fingpt = resp.json().get("fingpt")
        self.assertIsInstance(fingpt, dict)
        self.assertIsInstance(fingpt.get("datasets_enabled"), bool)
        self.assertIsInstance(fingpt.get("task_model_enabled"), bool)
        self.assertIn("task_model", fingpt)
        self.assertEqual(
            fingpt.get("tasks"),
            ["sentiment", "headline", "ner", "relation", "fiqa_qa", "forecaster"],
        )
        self.assertEqual(fingpt.get("default_behavior"), "disabled_fail_open")

    def test_config_model_options_expose_runtime_checked_model_names(self):
        client = TestClient(api_server.app)
        resp = client.get("/api/v1/config")

        self.assertEqual(resp.status_code, 200)
        models = resp.json().get("models")
        self.assertIsInstance(models, list)
        self.assertTrue(models)
        qwen = next((item for item in models if item.get("id") == "qwen"), None)
        self.assertIsNotNone(qwen)
        self.assertEqual(qwen.get("availability"), "runtime_checked")
        self.assertTrue(qwen.get("model"))
        self.assertIn("availability_note", qwen)
        for item in models:
            if "gemma" in str(item.get("id", "")).lower():
                self.assertEqual(item.get("availability"), "runtime_checked")
                self.assertTrue(item.get("model"))

    def test_direct_analyze_rejects_missing_ticker_before_pipeline(self):
        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=AsyncMock()) as run_pipeline:
            resp = client.post(
                "/api/v1/research/analyze",
                json={"question": "금리와 장기채 매력도 분석", "model": "qwen"},
            )

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["code"], "ticker_required_for_single_ticker_endpoint")
        run_pipeline.assert_not_awaited()

    def test_legacy_research_endpoint_routes_to_single_ticker_pipeline(self):
        response = AnalysisResponse(
            ticker="MSFT",
            question="AI capex risk",
            status="success",
            summary="ok",
            sentiment="Neutral",
            conclusion="ok",
        )
        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=AsyncMock(return_value=response)) as run_pipeline:
            resp = client.post(
                "/api/v1/research",
                json={"ticker": "MSFT", "question": "AI capex risk", "model": "qwen"},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["ticker"], "MSFT")
        self.assertEqual(body["summary"], "ok")
        run_pipeline.assert_awaited_once()

    def test_direct_analyze_propagates_simulation_override(self):
        response = AnalysisResponse(
            ticker="MSFT",
            question="AI capex risk",
            status="success",
            summary="ok",
            sentiment="Neutral",
            conclusion="ok",
        )
        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=AsyncMock(return_value=response)) as run_pipeline:
            resp = client.post(
                "/api/v1/research/analyze",
                json={
                    "ticker": "MSFT",
                    "question": "AI capex risk",
                    "model": "qwen",
                    "scenario_simulation_enabled": True,
                },
            )

        self.assertEqual(resp.status_code, 200)
        request = run_pipeline.await_args.args[0]
        self.assertIs(request.scenario_simulation_enabled, True)

    def test_direct_stream_rejects_missing_ticker_before_pipeline(self):
        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=AsyncMock()) as run_pipeline:
            resp = client.post(
                "/api/v1/research/stream",
                json={"question": "금리와 장기채 매력도 분석", "model": "qwen"},
            )

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["code"], "ticker_required_for_single_ticker_endpoint")
        run_pipeline.assert_not_awaited()

    def test_direct_analyze_returns_guidance_for_non_company_proxy(self):
        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=AsyncMock()) as run_pipeline:
            resp = client.post(
                "/api/v1/research/analyze",
                json={
                    "ticker": "TLT",
                    "question": "금리와 채권 가격이 매력적인지 분석",
                    "model": "qwen",
                },
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["execution_meta"]["extras"]["route_hint"], "use_universal_topic")
        run_pipeline.assert_not_awaited()

    def test_universal_stream_rejects_ticker_mode_without_ticker(self):
        client = TestClient(api_server.app)
        with patch.object(research_router, "dispatch_async", new=AsyncMock()) as dispatch:
            resp = client.post(
                "/api/v1/research/universal/stream",
                json={"question": "MSFT 리스크 분석", "mode_hint": "ticker", "model": "qwen"},
            )

        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["code"], "ticker_required_for_ticker_mode")
        dispatch.assert_not_awaited()

    def test_universal_stream_with_equity_ticker_returns_single_ticker_result(self):
        response = AnalysisResponse(
            ticker="MSFT",
            question="AI capex 리스크 분석",
            status="success",
            summary="ok",
            sentiment="Neutral",
            conclusion="ok",
        )
        client = TestClient(api_server.app)
        with patch.object(research_router, "dispatch_async", new=AsyncMock(return_value=response)) as dispatch:
            with client.stream(
                "POST",
                "/api/v1/research/universal/stream",
                json={
                    "ticker": "MSFT",
                    "question": "AI capex 리스크 분석",
                    "mode_hint": "auto",
                    "model": "qwen",
                },
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                body_text = "".join(chunk for chunk in resp.iter_text())

        dispatch.assert_awaited_once()
        frames = _parse_sse(body_text)
        self.assertEqual(frames[-1]["event"], "result")
        self.assertEqual(frames[-1]["data"]["mode"], "single_ticker")
        self.assertEqual(frames[-1]["data"]["ticker"], "MSFT")

    def test_universal_stream_with_tlt_ticker_can_return_topic_result(self):
        response = TopicResponse(
            question="금리와 채권 가격이 매력적인지 분석",
            theme="TLT",
            mode="sector_macro",
            status="success",
            executive_summary="장기금리와 듀레이션이 핵심입니다.",
            core_thesis="TLT는 topic playbook으로 분석해야 합니다.",
        )
        client = TestClient(api_server.app)
        with patch.object(research_router, "dispatch_async", new=AsyncMock(return_value=response)) as dispatch:
            with client.stream(
                "POST",
                "/api/v1/research/universal/stream",
                json={
                    "ticker": "TLT",
                    "question": "금리와 채권 가격이 매력적인지 분석",
                    "mode_hint": "auto",
                    "model": "qwen",
                },
            ) as resp:
                self.assertEqual(resp.status_code, 200)
                body_text = "".join(chunk for chunk in resp.iter_text())

        dispatch.assert_awaited_once()
        frames = _parse_sse(body_text)
        self.assertEqual(frames[-1]["event"], "result")
        self.assertEqual(frames[-1]["data"]["mode"], "sector_macro")

    def test_universal_endpoint_propagates_simulation_override(self):
        response = AnalysisResponse(
            ticker="MSFT",
            question="AI capex risk",
            status="success",
            summary="ok",
            sentiment="Neutral",
            conclusion="ok",
        )
        client = TestClient(api_server.app)
        with patch.object(research_router, "dispatch_async", new=AsyncMock(return_value=response)) as dispatch:
            resp = client.post(
                "/api/v1/research/universal",
                json={
                    "ticker": "MSFT",
                    "question": "AI capex risk",
                    "mode_hint": "auto",
                    "model": "qwen",
                    "scenario_simulation_enabled": True,
                },
            )

        self.assertEqual(resp.status_code, 200)
        request = dispatch.await_args.args[0]
        self.assertIs(request.scenario_simulation_enabled, True)

    def test_compare_endpoint_propagates_simulation_override_to_subrequests(self):
        captured = []

        async def fake_run_pipeline(request):
            captured.append((request.ticker, request.scenario_simulation_enabled))
            return AnalysisResponse(
                ticker=request.ticker,
                question=request.question,
                status="success",
                summary="ok",
                sentiment="Neutral",
                conclusion="ok",
            )

        client = TestClient(api_server.app)
        with patch.object(research_router, "run_pipeline_async", new=fake_run_pipeline):
            resp = client.post(
                "/api/v1/research/compare",
                json={
                    "tickers": ["MSFT", "AAPL"],
                    "question": "Compare AI capex risk",
                    "model": "qwen",
                    "scenario_simulation_enabled": True,
                },
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(captured), {("MSFT", True), ("AAPL", True)})


if __name__ == "__main__":
    unittest.main()
