import json
import tempfile
import unittest
from pathlib import Path

from core.schemas.request import AnalysisRequest
from core.schemas.response import AnalysisResponse
from pipelines.collect.models import CollectionOutcome, SourceCollectionResult
from pipelines.output.output_writer import save_outputs
from pipelines.output.run_history import list_runs


class CollectionSidecarOutputTests(unittest.TestCase):
    def test_save_outputs_writes_latest_collection_sidecar(self):
        request = AnalysisRequest(
            ticker="MSFT",
            question="Test",
            output_dir="",
        )
        response = AnalysisResponse(
            ticker="MSFT",
            question="Test",
            status="success",
            summary="Summary",
            sentiment="Neutral",
            conclusion="Conclusion",
        )
        outcome = CollectionOutcome(
            documents=[],
            source_results=[SourceCollectionResult("news", "ok", 1, 0.1, "news ok")],
            provider_results=[SourceCollectionResult("news:yfinance", "ok", 1, 0.1, "provider ok")],
            current_doc_ids=["doc-1"],
            run_started_at="2026-04-21T00:00:00",
            freshness_cutoff="2026-04-14T00:00:00",
            retrieval_policy="current_run_only",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            request.output_dir = tmp_dir
            save_outputs(request, response, "md", "html", collection_outcome=outcome)

            sidecar_path = Path(tmp_dir) / "latest_collection.json"
            with sidecar_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)

        self.assertEqual(data["ticker"], "MSFT")
        self.assertEqual(data["current_doc_ids"], ["doc-1"])
        self.assertEqual(data["retrieval_policy"], "current_run_only")
        self.assertEqual(data["source_results"][0]["source"], "news")
        self.assertEqual(data["provider_results"][0]["source"], "news:yfinance")

    def test_run_history_list_includes_run_id_alias(self):
        request = AnalysisRequest(ticker="MSFT", question="Test", output_dir="")
        response = AnalysisResponse(
            ticker="MSFT",
            question="Test",
            status="success",
            summary="Summary",
            sentiment="Neutral",
            conclusion="Conclusion",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            request.output_dir = tmp_dir
            save_outputs(request, response, "md", "html")
            items = list_runs(outputs_dir=Path(tmp_dir), limit=1)

        self.assertTrue(items)
        self.assertEqual(items[0]["run_id"], items[0]["id"])


if __name__ == "__main__":
    unittest.main()
