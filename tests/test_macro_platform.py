from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.server import app
from core.schemas.macro import MacroDataQuality, MacroObservation, MacroSeriesResponse
from pipelines.data_mart.jobs.update_macro_daily import update_macro_platform_data
from pipelines.data_mart.models import MacroObservation as StoredMacroObservation
from pipelines.data_mart.models import ProviderFetchResult
from pipelines.data_mart.storage import repository
from pipelines.macro import macro_service
from pipelines.macro.asset_impact import ASSET_CLASSES, get_asset_impacts
from pipelines.macro.portfolio_hints import get_portfolio_policy_hint
from pipelines.macro.providers.ecos import EcosProvider
from pipelines.macro.providers.oecd import OecdProvider
from pipelines.macro.providers.worldbank import WorldBankProvider
from pipelines.macro.providers.yahoo import YahooFinanceProvider
from pipelines.macro.regime_engine import classify_macro_regime
from pipelines.macro.research_context import macro_research_context_to_retrieval_item
from pipelines.macro.series_registry import get_series_definition, list_macro_series


def _contains_chinese_japanese_or_hanja(text: str) -> bool:
    return any(0x4E00 <= ord(ch) <= 0x9FFF or 0x3040 <= ord(ch) <= 0x30FF for ch in text)


def _reset_macro_runtime(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_MART_DB_PATH", str(tmp_path / "macro_test.db"))
    monkeypatch.setenv("FRED_API_KEY", "")
    macro_service.clear_macro_caches()


def _series(series_id: str, value: float, *, change_3: float = 0.0) -> MacroSeriesResponse:
    definition = get_series_definition(series_id)
    observation = MacroObservation(date="2026-04-30", value=value, raw_value=value, source="test")
    return MacroSeriesResponse(
        series_id=definition.series_id,
        display_name=definition.display_name,
        category=definition.category,
        unit=definition.unit,
        frequency=definition.frequency,
        provider="test",
        observations=[observation],
        latest=observation,
        changes={
            "latest_date": observation.date,
            "latest_value": value,
            "change_1_period": change_3,
            "change_3_period": change_3,
            "change_12_period": change_3,
        },
        data_quality=MacroDataQuality(status="ok", provider="test", last_updated=observation.date),
    )


def test_compact_macro_payload_trims_observations_without_mutation() -> None:
    series = _series("DGS10", 4.0)
    observations = [
        MacroObservation(date=f"2026-04-{day:02d}", value=float(day), raw_value=float(day), source="test")
        for day in range(1, 4)
    ]
    series.observations = observations
    series.latest = observations[-1]
    payload = {
        "status": "success",
        "items": [series.model_dump(mode="json")],
        "key_indicators": [series.model_dump(mode="json")],
    }

    compact = macro_service.compact_macro_payload(payload, observation_limit=1)
    empty = macro_service.compact_macro_payload(payload, observation_limit=0)

    assert [row["date"] for row in compact["items"][0]["observations"]] == ["2026-04-03"]
    assert [row["date"] for row in compact["key_indicators"][0]["observations"]] == ["2026-04-03"]
    assert empty["items"][0]["observations"] == []
    assert len(payload["items"][0]["observations"]) == 3


def test_macro_registry_loads_required_series() -> None:
    all_items = list_macro_series(include_disabled=True)
    enabled_items = list_macro_series()
    ids = {item.series_id for item in all_items}
    for required in [
        "FEDFUNDS",
        "SOFR",
        "DGS3MO",
        "DGS1",
        "DGS2",
        "DGS5",
        "DGS7",
        "DGS10",
        "DGS30",
        "T10Y2Y",
        "T10Y3M",
        "DFII10",
        "T5YIFR",
        "MORTGAGE30US",
        "CPIAUCSL",
        "CPILFESL",
        "PCEPI",
        "PCEPILFE",
        "PCETRIM12M159SFRBDAL",
        "MEDCPIM158SFRBCLE",
        "STICKCPIM157SFRBATL",
        "CPIENGSL",
        "CPIUFDSL",
        "GDPC1",
        "INDPRO",
        "IPMAN",
        "TCU",
        "BUSINV",
        "DGORDER",
        "RSAFS",
        "UMCSENT",
        "HOUST",
        "PERMIT",
        "CSUSHPISA",
        "MSPUS",
        "PCEC96",
        "DSPIC96",
        "PSAVERT",
        "TOTALSL",
        "UNRATE",
        "U6RATE",
        "CIVPART",
        "PAYEMS",
        "CES0500000003",
        "AWHMAN",
        "ICSA",
        "JTSJOL",
        "M2SL",
        "WALCL",
        "RRPONTSYD",
        "BAMLH0A0HYM2",
        "BAMLC0A0CM",
        "BAMLC0A4CBBB",
        "BAMLH0A3HYC",
        "NFCI",
        "STLFSI4",
        "DRTSCILM",
        "BUSLOANS",
        "DTWEXBGS",
        "DEXUSEU",
        "DEXJPUS",
        "DEXKOUS",
        "DCOILWTICO",
        "DHHNGSP",
        "DCOILBRENTEU",
        "VIXCLS",
    ]:
        assert required in ids
    for extension in ["ECOS_KR_POLICY_RATE", "OECD_CLI", "WORLD_BANK_GDP", "YAHOO_DXY_PROXY", "YAHOO_GLD", "YAHOO_USO"]:
        assert extension in ids
    assert len(enabled_items) >= 70
    assert {"housing_consumer", "financial_conditions", "fx_dollar", "commodities"}.issubset({item.category for item in enabled_items})
    assert get_series_definition("CSUSHPISA").stale_after_days >= 140
    busloans = get_series_definition("BUSLOANS")
    assert busloans.frequency == "monthly"
    assert busloans.stale_after_days >= 95


def test_macro_data_quality_covers_full_registry_freshness(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    definitions = [get_series_definition(series_id) for series_id in ["CSUSHPISA", "BUSLOANS", "DGS10"]]
    monkeypatch.setattr(macro_service, "_list_macro_series", lambda include_disabled=False: definitions)
    today = datetime.now(timezone.utc).date()
    repository.upsert_macro_observations(
        [
            StoredMacroObservation(
                series_id="CSUSHPISA",
                date=(today - timedelta(days=120)).isoformat(),
                value=330.0,
                source="fred",
            ),
            StoredMacroObservation(
                series_id="BUSLOANS",
                date=(today - timedelta(days=60)).isoformat(),
                value=2800.0,
                source="fred",
            ),
            StoredMacroObservation(
                series_id="DGS10",
                date=(today - timedelta(days=8)).isoformat(),
                value=4.4,
                source="fred",
            ),
        ],
        db_path=tmp_path / "macro_test.db",
    )

    payload = macro_service.get_data_quality()
    rows = {row["series_id"]: row for row in payload["series"]}

    assert payload["coverage"]["evaluated_series"] == 3
    assert rows["CSUSHPISA"]["status"] == "ok"
    assert rows["BUSLOANS"]["status"] == "ok"
    assert rows["DGS10"]["status"] == "stale"
    assert payload["data_quality"]["stale_series"] == ["DGS10"]


def test_provider_unavailable_returns_no_fake_observations(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    response = macro_service.get_macro_series("FEDFUNDS")
    assert response.observations == []
    assert response.latest is None
    assert response.data_quality.status == "unavailable"
    assert "FEDFUNDS" in response.data_quality.missing_series


def test_unknown_series_is_controlled_404(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.get("/api/v1/macro/series/NOT_A_SERIES")
    assert response.status_code == 404
    assert response.json()["detail"] == "macro_series_not_found:NOT_A_SERIES"


def test_macro_search_matches_human_alias_and_detail_components(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)

    search = client.get("/api/v1/macro/series/search", params={"q": "US 10Y", "limit": 5})
    assert search.status_code == 200
    body = search.json()
    assert body["items"]
    assert body["items"][0]["series_id"] == "DGS10"

    detail = client.get("/api/v1/macro/series/CPIAUCSL/detail", params={"observation_limit": 12})
    assert detail.status_code == 200
    payload = detail.json()
    component_ids = {item["series_id"] for item in payload["component_series"]}
    assert {"CPILFESL", "CPIENGSL", "CPIUFDSL"}.issubset(component_ids)
    assert payload["definition"]["series_id"] == "CPIAUCSL"
    assert "statistics" in payload
    assert "interpretation" in payload


def test_macro_overview_schema_and_unknown_regime_on_insufficient_data(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    overview = macro_service.get_macro_overview()
    assert overview.data_quality.status == "unavailable"
    assert overview.regime.name == "unknown"
    assert overview.regime.confidence <= 0.25
    assert overview.key_indicators
    assert all(item.data_quality for item in overview.key_indicators)


def test_api_responses_include_data_quality(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)
    for path in [
        "/api/v1/macro/overview",
        "/api/v1/macro/series",
        "/api/v1/macro/interest-rates",
        "/api/v1/macro/housing-consumer",
        "/api/v1/macro/financial-conditions",
        "/api/macro/data-quality",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert "data_quality" in body


def test_macro_dashboard_summary_endpoint_is_compact_and_operable(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.get("/api/v1/macro/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "partial", "stale", "unavailable"}
    assert "overview" in body
    assert "coverage" in body
    assert "data_quality" in body
    assert "quality_detail" in body
    assert "refresh" in body
    assert "generated_at" in body
    assert body["coverage"]["registry_series"] >= 70
    assert body["coverage"]["countries"]
    assert "US" in body["coverage"]["countries"]
    assert all(len(item["observations"]) <= 20 for item in body["overview"]["key_indicators"])


def test_macro_provider_health_endpoint_reports_scheduler_and_stale_causes(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)

    def fake_data_quality():
        return {
            "status": "partial",
            "data_quality": MacroDataQuality(
                status="partial",
                provider="test",
                stale_series=["STALE_TEST"],
                missing_series=["UNAVAILABLE_TEST"],
            ).model_dump(mode="json"),
            "series": [
                {
                    "series_id": "STALE_TEST",
                    "display_name": "Stale Test",
                    "status": "stale",
                    "latest_date": "2025-01-01",
                    "provider": "test",
                    "errors": [],
                    "notes": ["stale"],
                },
                {
                    "series_id": "UNAVAILABLE_TEST",
                    "display_name": "Unavailable Test",
                    "status": "unavailable",
                    "latest_date": None,
                    "provider": "test",
                    "errors": ["missing"],
                    "notes": [],
                },
                {
                    "series_id": "PARTIAL_TEST",
                    "display_name": "Partial Test",
                    "status": "partial",
                    "latest_date": "2026-01-01",
                    "provider": "test",
                    "errors": [],
                    "notes": ["partial"],
                },
            ],
    }

    monkeypatch.setattr("pipelines.macro.provider_health.macro_service.get_data_quality", fake_data_quality)

    class FakeScheduler:
        def status(self):
            return {
                "enabled": True,
                "jobs": {"macro_platform_data": True},
                "last_result": {
                    "jobs": {
                        "macro_platform_data": {
                            "providers": [
                                {
                                    "provider": "fred",
                                    "status": "failed",
                                    "rows": 0,
                                    "error": {"message": "boom"},
                                    "detail": {"stage": "test"},
                                }
                            ]
                        }
                    }
                },
            }

    monkeypatch.setattr("app.api.routers.macro.get_data_mart_scheduler", lambda: FakeScheduler())
    client = TestClient(app)

    response = client.get("/api/v1/macro/provider-health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "partial", "stale", "unavailable"}
    assert "providers" in body
    assert body["providers"]
    provider = body["providers"][0]
    assert {"provider", "enabled", "configured", "latest_status", "latest_rows", "latest_error"}.issubset(provider)
    assert "rows" not in provider
    assert "error" not in provider
    fred = next(item for item in body["providers"] if item["provider"] == "fred")
    assert fred["latest_status"] == "failed"
    assert fred["latest_rows"] == 0
    assert "boom" in fred["latest_error"]
    assert "scheduler" in body
    assert isinstance(body["stale_series"], list)
    stale_statuses = {item["status"] for item in body["stale_series"]}
    assert {"stale", "unavailable", "partial"}.issubset(stale_statuses)
    assert {item["series_id"] for item in body["stale_series"]} >= {"STALE_TEST", "UNAVAILABLE_TEST", "PARTIAL_TEST"}


def test_macro_scenario_endpoint_returns_advisory_asset_impacts(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/v1/macro/scenario",
        json={
            "name": "rates_up",
            "rate_shock_bp": 100,
            "inflation_shock_pct": 0.5,
            "credit_spread_shock_bp": 150,
            "oil_shock_pct": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["advisory_only"] is True
    assert body["scenario"]["name"] == "rates_up"
    assert body["scenario"]["rate_shock_bp"] == 100
    assert body["risk_level"] in {"watch", "reduce", "neutral"}
    assert body["explanation"]
    assert body["data_quality"]["status"] == "ok"
    assert len(body["asset_impacts"]) >= 4
    assert "orders" not in body
    assert "trades" not in body


def test_expanded_macro_category_surfaces_have_visible_items(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr("pipelines.macro.providers.yahoo.yf", None)
    housing = macro_service.get_housing_consumer()
    financial = macro_service.get_financial_conditions()
    yield_curve = macro_service.get_yield_curve()
    fx = macro_service.get_fx_dollar()
    commodities = macro_service.get_commodities()

    assert housing["count"] >= 8
    assert financial["count"] >= 4
    assert yield_curve["count"] >= 10
    assert fx["count"] >= 5
    assert commodities["count"] >= 5
    assert {"HOUST", "PCEC96"}.issubset({item["series_id"] for item in housing["items"]})
    assert {"NFCI", "BUSLOANS"}.issubset({item["series_id"] for item in financial["items"]})


def test_synthetic_goldilocks_regime_classification() -> None:
    series = {
        "GDPC1": _series("GDPC1", 3.0),
        "INDPRO": _series("INDPRO", 2.0),
        "RSAFS": _series("RSAFS", 4.0),
        "UMCSENT": _series("UMCSENT", 92.0),
        "CPIAUCSL": _series("CPIAUCSL", 2.2, change_3=-0.2),
        "CPILFESL": _series("CPILFESL", 2.4, change_3=-0.1),
        "PCEPI": _series("PCEPI", 2.2, change_3=-0.1),
        "PCEPILFE": _series("PCEPILFE", 2.3, change_3=-0.1),
        "FEDFUNDS": _series("FEDFUNDS", 4.0),
        "DGS2": _series("DGS2", 3.7),
        "DFII10": _series("DFII10", 1.2),
        "UNRATE": _series("UNRATE", 3.8),
        "PAYEMS": _series("PAYEMS", 1.8),
        "ICSA": _series("ICSA", 210000.0),
        "BAMLH0A0HYM2": _series("BAMLH0A0HYM2", 3.2),
        "BAMLC0A0CM": _series("BAMLC0A0CM", 1.1),
        "VIXCLS": _series("VIXCLS", 14.0),
    }
    regime, signals = classify_macro_regime(series)
    assert regime.name == "goldilocks"
    assert regime.confidence > 0.5
    assert {signal.name for signal in signals} >= {"growth_signal", "inflation_signal", "policy_signal"}


def test_asset_impact_mapping_returns_required_assets() -> None:
    regime, signals = classify_macro_regime({
        "GDPC1": _series("GDPC1", -1.0),
        "UNRATE": _series("UNRATE", 6.5),
        "ICSA": _series("ICSA", 350000.0),
        "BAMLH0A0HYM2": _series("BAMLH0A0HYM2", 7.5),
        "BAMLC0A0CM": _series("BAMLC0A0CM", 3.0),
        "VIXCLS": _series("VIXCLS", 35.0),
    })
    impacts = get_asset_impacts(regime, signals)
    assert {item.asset_class for item in impacts} == set(ASSET_CLASSES)
    assert all(item.confidence >= 0 for item in impacts)


def test_portfolio_policy_hint_is_advisory_only() -> None:
    overview_quality = MacroDataQuality(status="partial", provider="test", missing_series=["CPIAUCSL"])
    regime, _signals = classify_macro_regime({})
    hint = get_portfolio_policy_hint(regime, overview_quality)
    assert hint.advisory_only is True
    assert "no trade order" in " ".join(hint.warnings).lower()
    assert hint.data_quality.status == "partial"
    assert hint.etf_candidates
    tickers = {ticker for candidate in hint.etf_candidates for ticker in candidate.tickers}
    assert {"SPY", "BND", "SGOV", "GLD", "LQD"}.issubset(tickers)
    assert not {"AAPL", "MSFT", "NVDA"}.intersection(tickers)


def test_research_context_and_brief_fallback_do_not_fabricate(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    context = macro_service.get_macro_research_context(ticker="TLT")
    assert "TLT" in context.ticker_relevance
    assert context.regime.name == "unknown"
    brief = macro_service.generate_macro_brief(include_prompt=True)
    assert brief.is_fallback is False
    assert brief.provider == "structured_macro_rules"
    assert "No key indicators are available" not in brief.content
    assert "증거 부족" in brief.content or "관측치 없음" in brief.content
    assert "ETF 기반 포트폴리오 구성 메모" in brief.content
    assert "경제 지표값을 지어내지 말고" in (brief.prompt_template or "")
    assert "중국어" in (brief.prompt_template or "")


def test_macro_research_context_can_be_injected_as_retrieval_item(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    context = macro_service.get_macro_research_context(ticker="QQQ")
    item = macro_research_context_to_retrieval_item(context, ticker="QQQ")
    assert item.source == "macro:platform"
    assert item.metadata["doc_type"] == "macro_platform_context"
    assert item.metadata["advisory_only"] is True
    assert "STRUCTURED MACRO PLATFORM CONTEXT" in item.chunk
    assert "Do not invent economic indicator values" in item.chunk


def test_live_macro_brief_rejected_when_llm_invents_numbers(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)

    class Response:
        status_code = 200
        text = "{}"

        def json(self):
            return {"response": "1. 현재 매크로 레짐\n이 브리프는 가짜 지표 9999.12를 지어냅니다."}

    monkeypatch.setattr("pipelines.macro.ai_brief.httpx.post", lambda *_, **__: Response())
    brief = macro_service.generate_macro_brief(use_llm=True, model="qwen", timeout_s=1)
    assert brief.is_fallback is True
    assert brief.provider == "rule_based_fallback"
    assert any("grounding guard rejected" in warning.lower() for warning in brief.warnings)


def test_live_macro_brief_can_use_grounded_llm_response(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    original_overview = macro_service.get_macro_overview

    def fake_overview():
        overview = original_overview()
        observation = MacroObservation(date="2026-04-30", value=3.0, raw_value=3.0, source="test")
        overview.key_indicators[0].observations = [observation]
        overview.key_indicators[0].latest = observation
        overview.key_indicators[0].data_quality = MacroDataQuality(status="ok", provider="test")
        overview.data_quality = MacroDataQuality(status="ok", provider="test")
        return overview

    class Response:
        status_code = 200
        text = "{}"

        def json(self):
            return {"response": "1. 현재 매크로 레짐\n제공된 데이터는 3.0만 보여주며, 주문은 생성하지 않습니다."}

    monkeypatch.setattr(macro_service, "get_macro_overview", fake_overview)
    monkeypatch.setattr("pipelines.macro.ai_brief.httpx.post", lambda *_, **__: Response())
    brief = macro_service.generate_macro_brief(use_llm=True, model="qwen", timeout_s=1)
    assert brief.is_fallback is False
    assert brief.provider.startswith("ollama:")
    assert "3.0" in brief.content


def test_live_macro_brief_rejects_non_korean_llm_response(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    original_overview = macro_service.get_macro_overview

    def fake_overview():
        overview = original_overview()
        observation = MacroObservation(date="2026-04-30", value=3.0, raw_value=3.0, source="test")
        overview.key_indicators[0].observations = [observation]
        overview.key_indicators[0].latest = observation
        overview.key_indicators[0].data_quality = MacroDataQuality(status="ok", provider="test")
        overview.data_quality = MacroDataQuality(status="ok", provider="test")
        return overview

    class Response:
        status_code = 200
        text = "{}"

        def json(self):
            return {"response": "壤볟뎺若뤺쭆??쥊?양ㅊ罌욇빣葉녑츣竊뚪싪??뗥뒟?됮솏竊뚩탡雅㏝뀓營?틪岳앮똻瘟ⓩ뀕??.0"}

    monkeypatch.setattr(macro_service, "get_macro_overview", fake_overview)
    monkeypatch.setattr("pipelines.macro.ai_brief.httpx.post", lambda *_, **__: Response())
    brief = macro_service.generate_macro_brief(use_llm=True, model="qwen", timeout_s=1)
    assert brief.is_fallback is True
    assert any("language guard" in warning.lower() for warning in brief.warnings)


def test_macro_report_endpoint_returns_markdown(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.get("/api/v1/macro/report")
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "markdown"
    assert body["content"].startswith("# FinGPT 매크로 리포트")
    assert "## AI 매크로 브리프" in body["content"]
    assert not _contains_chinese_japanese_or_hanja(body["content"])
    assert not _contains_chinese_japanese_or_hanja(" ".join(body["warnings"]))
    assert body["data_quality"]["status"] in {"ok", "partial", "stale", "unavailable"}


def test_macro_refresh_job_stores_fred_and_yahoo_series(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "macro_refresh.db"
    monkeypatch.setenv("DATA_MART_DB_PATH", str(db_path))

    def fake_fred(series_ids, **kwargs):
        return ProviderFetchResult(
            provider="fred",
            status="ok",
            rows=1,
            records=[
                StoredMacroObservation(
                    series_id="FEDFUNDS",
                    date="2026-05-01",
                    value=4.5,
                    source="fred",
                )
            ],
            detail={"requested_series": list(series_ids)},
        )

    monkeypatch.setattr("pipelines.data_mart.jobs.update_macro_daily.fetch_macro_series", fake_fred)

    import pandas as pd

    frame = pd.DataFrame(
        {"Close": [100.0, 102.0], "Adj Close": [100.0, 102.0], "Volume": [10, 20]},
        index=pd.to_datetime(["2026-05-01", "2026-05-02"]),
    )
    monkeypatch.setattr("pipelines.macro.providers.yahoo.yf.download", lambda **_: frame)

    result = update_macro_platform_data(["FEDFUNDS", "YAHOO_GLD"], lookback_days=10, db_path=db_path)

    assert result.status == "success"
    assert repository.latest_macro("FEDFUNDS", db_path=db_path)["value"] == 4.5
    assert repository.latest_macro("YAHOO_GLD", db_path=db_path)["value"] == 102.0
    health = repository.data_health(db_path=db_path)
    assert health["macro_series_with_observations"] == 2


def test_macro_refresh_api_supports_dry_run(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.post("/api/v1/macro/refresh", json={"series_ids": ["FEDFUNDS"], "dry_run": True})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run"
    assert body["refresh"]["providers"][0]["status"] == "dry_run"
    assert "data_quality" in body


def test_factor_regime_classifier_uses_same_signal_contract() -> None:
    series = {
        "GDPC1": _series("GDPC1", -1.0),
        "INDPRO": _series("INDPRO", -2.0),
        "CPIAUCSL": _series("CPIAUCSL", 2.2, change_3=-0.2),
        "CPILFESL": _series("CPILFESL", 2.4, change_3=-0.1),
        "UNRATE": _series("UNRATE", 6.5),
        "ICSA": _series("ICSA", 350000.0),
        "BAMLH0A0HYM2": _series("BAMLH0A0HYM2", 7.5),
        "BAMLC0A0CM": _series("BAMLC0A0CM", 3.0),
        "VIXCLS": _series("VIXCLS", 35.0),
    }
    regime, signals = classify_macro_regime(series, engine="factor")
    assert regime.name in {"recession_risk", "disinflation", "unknown"}
    assert "factor_distance" in regime.scores or regime.name == "unknown"
    assert {signal.name for signal in signals} >= {"growth_signal", "credit_signal"}


def test_macro_regime_api_supports_factor_engine(monkeypatch, tmp_path) -> None:
    _reset_macro_runtime(monkeypatch, tmp_path)
    client = TestClient(app)
    response = client.get("/api/v1/macro/regime?engine=factor")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "factor"
    assert "data_quality" in body


def test_worldbank_provider_parses_indicator_payload(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{}, [{"date": "2024", "value": "2.8"}, {"date": "2023", "value": None}]]

    monkeypatch.setattr("pipelines.macro.providers.worldbank.httpx.get", lambda *_, **__: Response())
    result = WorldBankProvider().fetch_series(get_series_definition("WORLD_BANK_GDP"))
    assert result.data_quality.status == "ok"
    assert len(result.observations) == 1
    assert result.observations[0].date == "2024-01-01"
    assert result.observations[0].value == 2.8


def test_oecd_provider_parses_sdmx_json(monkeypatch) -> None:
    payload = {
        "dataSets": [{"observations": {"0:0": [99.1], "0:1": [100.2]}}],
        "structure": {
            "dimensions": {
                "observation": [
                    {"id": "LOCATION", "values": [{"id": "USA"}]},
                    {"id": "TIME_PERIOD", "values": [{"id": "2025-01"}, {"id": "2025-02"}]},
                ]
            }
        },
    }

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    monkeypatch.setattr("pipelines.macro.providers.oecd.httpx.get", lambda *_, **__: Response())
    result = OecdProvider().fetch_series(get_series_definition("OECD_CLI"))
    assert result.data_quality.status == "ok"
    assert [item.date for item in result.observations] == ["2025-01-01", "2025-02-01"]


def test_ecos_provider_requires_api_key_without_fake_data(monkeypatch) -> None:
    monkeypatch.delenv("ECOS_API_KEY", raising=False)
    result = EcosProvider(api_key="").fetch_series(get_series_definition("ECOS_KR_POLICY_RATE"))
    assert result.observations == []
    assert result.data_quality.status == "unavailable"
    assert "ECOS_API_KEY is missing." in result.data_quality.errors


def test_yahoo_provider_parses_price_proxy(monkeypatch) -> None:
    import pandas as pd

    frame = pd.DataFrame(
        {"Close": [100.0, 101.5], "Adj Close": [99.5, 101.0], "Volume": [10, 20]},
        index=pd.to_datetime(["2026-04-01", "2026-04-02"]),
    )
    monkeypatch.setattr("pipelines.macro.providers.yahoo.yf.download", lambda **_: frame)
    result = YahooFinanceProvider().fetch_series(get_series_definition("YAHOO_GLD"))
    assert result.data_quality.status == "ok"
    assert len(result.observations) == 2
    assert result.observations[-1].value == 101.0
    assert result.observations[-1].metadata["symbol"] == "GLD"


def test_fx_and_commodities_categories_use_enabled_market_proxies(monkeypatch, tmp_path) -> None:
    import pandas as pd

    _reset_macro_runtime(monkeypatch, tmp_path)
    frame = pd.DataFrame(
        {"Close": [100.0, 101.0], "Adj Close": [100.0, 101.0]},
        index=pd.to_datetime(["2026-04-01", "2026-04-02"]),
    )
    monkeypatch.setattr("pipelines.macro.providers.yahoo.yf.download", lambda **_: frame)
    fx = macro_service.get_fx_dollar()
    commodities = macro_service.get_commodities()
    fx_ids = {item["series_id"] for item in fx["items"]}
    commodity_ids = {item["series_id"] for item in commodities["items"]}
    assert fx["count"] >= 5
    assert commodities["count"] >= 5
    assert {"DTWEXBGS", "YAHOO_DXY_PROXY"}.issubset(fx_ids)
    assert {"DCOILWTICO", "DCOILBRENTEU", "YAHOO_GLD", "YAHOO_USO"}.issubset(commodity_ids)
    assert any(item["provider"] == "yahoo" and item["observations"] for item in fx["items"])
    assert any(item["provider"] == "yahoo" and item["observations"] for item in commodities["items"])
