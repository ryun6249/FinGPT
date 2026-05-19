from core.schemas.request import AnalysisRequest, CompareRequest, UniversalRequest
from core.schemas.topic import TopicRequest


def test_request_models_normalize_output_language_aliases():
    assert AnalysisRequest(ticker="MSFT", question="test", output_language="english").output_language == "en"
    assert UniversalRequest(question="test", output_language="kr").output_language == "ko"
    assert CompareRequest(tickers=["MSFT", "AAPL"], question="test", output_language="EN").output_language == "en"
    assert TopicRequest(question="test", output_language="KOREAN").output_language == "ko"
