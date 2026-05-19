from pathlib import Path
import importlib.util
import re
import unittest

from fastapi.testclient import TestClient

from app.api import server as api_server


APP_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[1] / "app" / "web" / "index.html"
STYLES_CSS = Path(__file__).resolve().parents[1] / "app" / "web" / "styles.css"
AI_PORTFOLIO_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "ai-portfolio-ui.js"
MARKET_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "market-ui.js"
MACRO_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "macro-ui.js"
FORECAST_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "forecast-ui.js"
QUANT_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "quant-ui.js"
QUANTAMENTAL_UI_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "quantamental-ui.js"
AI_PORTFOLIO_UI_SMOKE = Path(__file__).resolve().parents[1] / "scripts" / "ai_portfolio_ui_smoke.py"


class UiRoutingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = APP_JS.read_text(encoding="utf-8")

    def test_non_compare_runs_use_universal_stream(self):
        match = re.search(r"async function runAnalysis\(e\) \{(?P<body>.*?)\n\}\n\n// ---------- Compare mode", self.source, re.S)
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("runStreamAnalysis(API.universalStream, payload, payload)", body)
        self.assertNotIn("API.stream", body)
        self.assertNotIn("useUniversal", body)

    def test_fingpt_status_ui_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="fingptStatus"', html)
        self.assertIn("function renderFinGPTStatus", self.source)
        self.assertIn("renderFinGPTStatus(state.config)", self.source)
        self.assertIn("FinGPT \ubcf4\uc870 \uae30\ub2a5 \ube44\ud65c\uc131 \u00b7 \uae30\ubcf8 \ubd84\uc11d \uacbd\ub85c\uc5d0\ub294 \uc601\ud5a5 \uc5c6\uc74c", self.source)
        self.assertIn("FinGPT \ubcf4\uc870 \uae30\ub2a5 \ud65c\uc131:", self.source)
        self.assertIn("is-enabled", self.source)

    def test_intent_normalizer_preserves_tickerless_topic_path(self):
        self.assertIn("function normalizeResearchIntent", self.source)
        self.assertIn("auto_topic", self.source)
        self.assertIn("extracted_ticker", self.source)
        self.assertIn("ticker \uc5c6\uc774 \uc9c8\uc758 \uac00\ub2a5", self.source)

    def test_question_ticker_inference_supports_explicit_universe_fallback(self):
        self.assertIn("function matchExplicitTickerPrefix", self.source)
        self.assertIn("function isSupportedExplicitTickerToken", self.source)
        self.assertIn("UNREGISTERED_TICKER_STOPWORDS", self.source)
        self.assertIn('source: "explicit_prefix"', self.source)
        self.assertIn("classShare", self.source)
        self.assertIn("[A-Z]{3,5}", self.source)
        self.assertIn("\\d{6}\\.(?:KS|KQ)", self.source)

    def test_every_declared_progress_stage_exists_in_dom(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        stage_match = re.search(r"const STAGES = \[(?P<items>.*?)\];", self.source, re.S)
        self.assertIsNotNone(stage_match)
        stages = re.findall(r'"([^"]+)"', stage_match.group("items"))
        dom_stages = set(re.findall(r'data-stage="([^"]+)"', html))
        self.assertTrue(stages)
        self.assertEqual(set(stages), dom_stages)

    def test_ui_static_server_falls_back_for_client_routes_only(self):
        with TestClient(api_server.app) as client:
            quantamental_route = client.get("/ui/quantamental")
            missing_asset = client.get("/ui/not-found-bundle.js")
        self.assertEqual(200, quantamental_route.status_code)
        self.assertIn("FinGPT Local Research Assistant", quantamental_route.text)
        self.assertIn('id="quantamentalTab"', quantamental_route.text)
        self.assertEqual(404, missing_asset.status_code)

    def test_static_html_korean_copy_is_not_mojibake(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("로컬 리서치 어시스턴트", html)
        self.assertIn("수집 -> 적재 -> 검색 -> 추론 -> 분석 -> 보고", html)
        self.assertIn("펀더멘털 + 가격 + 리스크 + AI 해석", html)
        self.assertIn("Quantamental 분석은 리서치 전용이며 투자 자문이 아닙니다.", html)
        cjk_or_mojibake = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufffd]")
        self.assertIsNone(cjk_or_mojibake.search(html))
        self.assertNotIn("??", html)
        for bad in ["鍮", "怨", "諛", "吏", "由", "遺", "媛", "쨌", "濡"]:
            self.assertNotIn(bad, html)

    def test_progress_stage_helpers_are_null_safe(self):
        self.assertIn("function progressNode(stage)", self.source)
        self.assertIn("if (!node) return", self.source)

    def test_top_level_function_declarations_are_not_shadowed(self):
        names = re.findall(r"(?m)^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", self.source)
        duplicates = sorted({name for name in names if names.count(name) > 1})
        self.assertEqual([], duplicates)

    def test_background_polling_is_visibility_aware_and_deduplicated(self):
        self.assertIn("function shouldRunBackgroundPoll", self.source)
        self.assertIn("preflightRequest: null", self.source)
        self.assertIn("watchlistRequest: null", self.source)
        self.assertIn("if (state.preflightRequest) return state.preflightRequest", self.source)
        self.assertIn("if (state.watchlistRequest) return state.watchlistRequest", self.source)
        self.assertIn("renderWatchlist({ force: true })", self.source)
        self.assertIn("state.watchlistTimer = setInterval(() => renderWatchlist(), 30000)", self.source)
        self.assertIn("state.preflightTimer = setInterval(() => loadPreflight(false), 60000)", self.source)
        self.assertIn('document.addEventListener("visibilitychange"', self.source)

    def test_ai_portfolio_dashboard_is_loaded_once_per_refresh_path(self):
        self.assertIn("async function loadAiPortfolioOps", self.source)
        self.assertIn("const AI_PORTFOLIO_DASHBOARD_CACHE_TTL_MS = 15000", self.source)
        self.assertIn("function aiPortfolioDashboardCacheFresh", self.source)
        self.assertIn("function clearAiPortfolioDashboardCache", self.source)
        self.assertIn("async function fetchAiPortfolioDashboard", self.source)
        self.assertIn("if (state.aiPortfolioDashboardRequest && state.aiPortfolioDashboardRequestUrl === url)", self.source)
        self.assertIn("return state.aiPortfolioDashboardRequest", self.source)
        self.assertIn("Date.now() - state.aiPortfolioDashboardFetchedAt < AI_PORTFOLIO_DASHBOARD_CACHE_TTL_MS", self.source)
        self.assertIn("err.superseded = true", self.source)
        self.assertIn("if (err?.superseded) return", self.source)
        self.assertIn("const dashboard = await fetchAiPortfolioDashboard(force)", self.source)
        self.assertIn("clearAiPortfolioDashboardCache();", self.source)
        self.assertNotIn("loadAiPortfolioOperations", self.source)

    def test_ai_portfolio_ui_module_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        module_source = AI_PORTFOLIO_UI_JS.read_text(encoding="utf-8")
        self.assertIn('src="modules/market-ui.js?v=20260514-domain-modules"', html)
        self.assertIn('src="modules/macro-ui.js?v=20260514-domain-modules"', html)
        self.assertIn('src="modules/forecast-ui.js?v=20260514-domain-modules"', html)
        self.assertIn('src="modules/quant-ui.js?v=20260514-domain-modules"', html)
        self.assertIn('src="modules/ai-portfolio-ui.js?v=20260514-domain-modules"', html)
        self.assertIn('src="modules/quantamental-ui.js?v=20260519-quantamental-v12"', html)
        self.assertIn('href="styles.css?v=20260519-continuous-enhancement-v3"', html)
        self.assertIn('src="app.js?v=20260519-continuous-enhancement-v3"', html)
        self.assertIn('id="dashboardContextStrip"', html)
        self.assertIn("dashboardDecisionCards", self.source)
        self.assertIn("function loadDashboardDecisionCards", self.source)
        self.assertIn("global.FinGPTAiPortfolioUi", module_source)
        self.assertIn("dashboardMeta", module_source)
        self.assertIn("operationList", module_source)
        self.assertIn("ai-portfolio-dashboard-meta", module_source)
        self.assertIn("window.FinGPTAiPortfolioUi", self.source)
        self.assertIn("window.FinGPTMarketUi", self.source)
        self.assertIn("window.FinGPTMacroUi", self.source)
        self.assertIn("window.FinGPTForecastUi", self.source)
        self.assertIn("window.FinGPTQuantUi", self.source)
        self.assertIn("window.FinGPTQuantamentalUi", self.source)
        self.assertIn(".ai-dashboard-meta", css)
        self.assertIn(".ai-operation-item", css)

    def test_cross_dashboard_smoke_tracks_current_bundle_and_quantamental(self):
        smoke_source = AI_PORTFOLIO_UI_SMOKE.read_text(encoding="utf-8")
        self.assertIn('DOMAIN_BUNDLE_VERSION = "20260514-domain-modules"', smoke_source)
        self.assertIn('QUANTAMENTAL_BUNDLE_VERSION = "20260519-quantamental-v12"', smoke_source)
        self.assertIn('APP_BUNDLE_VERSION = "20260519-continuous-enhancement-v3"', smoke_source)
        self.assertIn("def _normalize_base_url", smoke_source)
        self.assertIn("modules/quantamental-ui.js", smoke_source)
        self.assertIn("FinGPTQuantamentalUi?.topSignals", smoke_source)
        self.assertIn("quantamental-score-screen-run", smoke_source)
        self.assertIn('"quantamental-tab"', smoke_source)
        self.assertIn('"#quantamental"', smoke_source)
        self.assertIn("quantamental-screen-run", smoke_source)
        self.assertIn('data-language="en"', smoke_source)
        self.assertIn('data-language="ko"', smoke_source)
        self.assertIn('env["PYTHONUTF8"] = "1"', smoke_source)
        self.assertIn("stdout=subprocess.DEVNULL", smoke_source)
        self.assertIn("stderr=subprocess.DEVNULL", smoke_source)

    def test_cross_dashboard_smoke_accepts_ui_base_url(self):
        spec = importlib.util.spec_from_file_location("ai_portfolio_ui_smoke", AI_PORTFOLIO_UI_SMOKE)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)

        self.assertEqual(module._normalize_base_url("http://127.0.0.1:8273/ui/"), "http://127.0.0.1:8273")
        self.assertEqual(module._normalize_base_url("http://127.0.0.1:8273"), "http://127.0.0.1:8273")

    def test_language_toggle_drives_request_output_language(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="languageToggle"', html)
        self.assertIn('data-language="ko"', html)
        self.assertIn('data-language="en"', html)
        self.assertIn("fingpt.outputLanguage.v1", self.source)
        self.assertIn("function applyUiLanguage", self.source)
        self.assertIn("function bindLanguageToggle", self.source)
        self.assertIn("output_language: selectedOutputLanguage()", self.source)
        self.assertIn("output_language: payload.output_language", self.source)
        self.assertIn("output_language: request.output_language", self.source)
        self.assertIn("applyQuantamentalUiLanguage", self.source)
        self.assertIn("Request language: English", self.source)
        self.assertIn("dashboardHero", self.source)
        self.assertIn("function updateDashboardHero", self.source)
        self.assertIn("function setLeadingText", self.source)
        self.assertIn('state.activeDashboardTab === "market"', self.source)
        self.assertIn('normalizeTvChartSettings(state.tvChartSettings).source === "tradingview"', self.source)

    def test_market_chart_defaults_to_internal_data_but_keeps_tradingview_option(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('const TV_CHART_DEFAULTS = { source: "internal"', self.source)
        self.assertIn('raw.source === "tradingview" ? "tradingview"', self.source)
        self.assertIn('<option value="internal">Internal data</option>', html)
        self.assertIn('<option value="tradingview">TradingView</option>', html)

    def test_quantamental_static_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        module_source = QUANTAMENTAL_UI_JS.read_text(encoding="utf-8")
        for marker in [
            'id="quantamentalTab"',
            'data-testid="quantamental-tab"',
            'id="quantamentalTicker"',
            'id="quantamentalTickerOpen"',
            'id="quantamentalMarket"',
            'id="quantamentalPeriod"',
            'id="quantamentalYears"',
            'id="quantamentalLookback"',
            'id="quantamentalStyle"',
            'id="quantamentalAnalyze"',
            'data-testid="quantamental-analyze"',
            'id="quantamentalSignalSurface"',
            'id="quantamentalScoreSurface"',
            'id="quantamentalFactorSurface"',
            'id="quantamentalMainSurface"',
            'id="quantamentalAiRefresh"',
            'id="quantamentalDataQualitySurface"',
            'id="quantamentalExpandPeers"',
            'id="quantamentalPeerLimit"',
            'id="quantamentalWatchlistName"',
            'id="quantamentalWatchlistSelect"',
            'data-testid="quantamental-watchlist-save"',
            'data-testid="quantamental-watchlist-load"',
            'data-testid="quantamental-compare-csv"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "quantamentalAnalysis",
            "quantamentalCompareWatchlists",
            "function loadQuantamental",
            "function runQuantamentalAnalysis",
            "function askQuantamentalQuestion",
            "function loadQuantamentalCompareWatchlists",
            "function saveQuantamentalCompareWatchlist",
            "function exportQuantamentalCompareCsv",
            "function exportQuantamentalSnapshot",
            'tab === "quantamental"',
            'window.location.hash === "#quantamental"',
        ]:
            self.assertIn(marker, self.source)
        self.assertIn("global.FinGPTQuantamentalUi", module_source)
        self.assertIn("signalCard", module_source)
        self.assertIn("mainPanel", module_source)
        self.assertIn("qaAnswer", module_source)
        self.assertIn("snapshotDiff", module_source)
        self.assertIn("snapshotRetention", module_source)
        self.assertIn(".quantamental-signal-card", css)
        self.assertIn(".quantamental-factor-grid", css)

    def test_domain_ui_modules_are_connected(self):
        modules = {
            "market": (MARKET_UI_JS, "global.FinGPTMarketUi", ["marketTape", "marketSignals"]),
            "macro": (MACRO_UI_JS, "global.FinGPTMacroUi", ["providerHealth"]),
            "forecast": (FORECAST_UI_JS, "global.FinGPTForecastUi", ["jobs"]),
            "quant": (QUANT_UI_JS, "global.FinGPTQuantUi", ["exportStorageReport"]),
        }
        for name, (path, global_marker, exported_markers) in modules.items():
            with self.subTest(name=name):
                source = path.read_text(encoding="utf-8")
                self.assertIn(global_marker, source)
                for marker in exported_markers:
                    self.assertIn(marker, source)

    def test_quant_backtest_workbench_uses_artifact_endpoint(self):
        match = re.search(r"async function runHomeBacktest\(\) \{(?P<body>.*?)\n\}\n\nasync function loadQuantRunHistory", self.source, re.S)
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("fetch(API.quantBacktest", body)
        self.assertIn("attachBenchmarkComparison(data", body)
        self.assertIn("renderQuantBacktestResult(enriched", body)
        self.assertIn("renderQuantDiagnosticsPanel(data)", self.source)
        self.assertIn("loadQuantRunHistory(true)", body)
        self.assertNotIn("fetch(API.backtestRun", body)

    def test_financial_curve_charts_have_axes_hover_tooltips_and_larger_canvas(self):
        css = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn("function renderChartYAxis", self.source)
        self.assertIn("function initChartTooltips", self.source)
        self.assertIn("data-chart-tooltip", self.source)
        self.assertIn("formatCurveReturn", self.source)
        self.assertIn("const width = 620;", self.source)
        self.assertIn("const height = 190;", self.source)
        self.assertIn("const width = 760;", self.source)
        self.assertIn("const height = 230;", self.source)
        self.assertIn(".chart-y-label", css)
        self.assertIn(".chart-tooltip", css)
        self.assertIn("height: 170px;", css)
        self.assertIn("height: 220px;", css)
        self.assertIn("height: 190px;", css)

    def test_asset_detail_supports_date_view_and_return_curve_controls(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        for marker in [
            'id="assetDetailRange"',
            'id="assetDetailStartDate"',
            'id="assetDetailEndDate"',
            'id="assetDetailView"',
            'id="assetDetailBenchmark"',
            'id="assetDetailBenchmarkCompare"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "function assetDetailOptionsFromControls",
            "function filterPriceRowsByAssetOptions",
            "function renderAssetReturnLineChart",
            "function renderAssetBenchmarkComparison",
            "function renderAssetDetailSections",
            'renderDecisionLineChart(curve, "return", "\uc218\uc775\ub960 \uace1\uc120"',
            "renderNormalizedComparisonChart",
        ]:
            self.assertIn(marker, self.source)
        self.assertIn(".asset-detail-form", css)
        self.assertIn(".asset-detail-chart-grid", css)
        self.assertIn('input[type="date"]::-webkit-calendar-picker-indicator', css)
        self.assertIn('input[type="date"]::-webkit-datetime-edit-year-field', css)
        self.assertIn("function bindDateInputs", self.source)
        self.assertIn("input.showPicker", self.source)
        self.assertIn('document.querySelectorAll(\'input[type="date"]\')', self.source)
        self.assertIn("function assetDetailPriceQueryOptions", self.source)
        self.assertIn("function assetDetailRefreshStart", self.source)
        self.assertIn("API.dataPrices(ticker, 5000, priceQuery)", self.source)
        self.assertIn("API.dataPrices(options.benchmark, 5000, priceQuery)", self.source)
        self.assertIn('params.set("refresh", "true")', self.source)

    def test_quant_run_history_can_reopen_artifacts(self):
        self.assertIn("API.quantBacktestBundle", self.source)
        self.assertIn("function loadQuantBacktestArtifact", self.source)
        self.assertIn("data-quant-run-id", self.source)

    def test_ml_forecast_registry_actions_preserve_action_name(self):
        self.assertIn("Data Snapshot", self.source)
        self.assertIn("source_coverage_hash", self.source)
        self.assertIn("Registry Audit", self.source)
        self.assertIn("API.forecastRegistryAudit", self.source)
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('value="walk_forward_plus_purged_cv"', html)
        self.assertIn("Purged CV folds", self.source)
        self.assertIn('target.dataset.action === "forecast-verify-artifact"', self.source)
        self.assertIn('target.dataset.action === "forecast-promote"', self.source)
        self.assertIn('target.dataset.action === "forecast-deprecate"', self.source)
        self.assertIn("updateForecastModelStatus(target.dataset.action, target.dataset.modelId)", self.source)
        self.assertIn('action === "forecast-promote" ? API.forecastPromoteModel : API.forecastDeprecateModel', self.source)
        self.assertIn("verifyForecastModelArtifact(target.dataset.modelId)", self.source)

    def test_market_heatmap_has_manual_refresh_and_display_limit(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="homeHeatmapRefresh"', html)
        self.assertIn("HEATMAP_DISPLAY_MAX", self.source)
        self.assertIn("loadDashboardEquityHeatmap(true)", self.source)
        self.assertIn("\ud45c\uc2dc ${escapeHtml(_fmtNumber(displayItems.length))}", self.source)
        self.assertIn(".home-stock-heatmap.finviz-treemap", STYLES_CSS.read_text(encoding="utf-8"))

    def test_market_dashboard_overview_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        for marker in [
            'id="marketOverviewMeta"',
            'id="marketTapeSurface"',
            'id="marketSignalSurface"',
            'id="crossAssetSymbols"',
            'id="crossAssetAnalysisSurface"',
            'data-testid="cross-asset-run"',
            'id="homeNewsFocusedList"',
            'data-testid="market-news-search-run"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "dashboardMarketOverview",
            "dashboardCrossAssetAnalyze",
            "function renderMarketTape",
            "function renderMarketSignals",
            "function renderCrossAssetAnalysis",
            "function loadFocusedDashboardNews",
            "function loadDashboardMarketOverview",
            "loadDashboardMarketOverview(force)",
        ]:
            self.assertIn(marker, self.source)

    def test_internal_market_chart_has_horizontal_scroll_contract(self):
        css = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn("internal-chart-scroll", self.source)
        self.assertIn("scrollInternalChartToLatest", self.source)
        self.assertIn("primaryRows.length * 8 + 150", self.source)
        self.assertIn(".internal-chart-scroll", css)

    def _symbol_list_count(self, const_name: str) -> int:
        match = re.search(rf"const {const_name} = symbolList\(`(?P<body>.*?)`\);", self.source, re.S)
        self.assertIsNotNone(match, const_name)
        return len([token for token in match.group("body").split() if token])

    def test_quant_symbol_catalog_expanded_universe_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertEqual(self._symbol_list_count("US_LARGE_CAP_SYMBOLS"), 200)
        self.assertEqual(self._symbol_list_count("ETF_CORE_SYMBOLS"), 100)
        self.assertEqual(self._symbol_list_count("KOSPI200_SYMBOLS"), 200)
        self.assertEqual(self._symbol_list_count("KOSDAQ100_SYMBOLS"), 100)
        self.assertIn('const CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD"];', self.source)
        self.assertIn("const GLOBAL_EQUITY_SYMBOLS = [", self.source)
        self.assertIn('id="symbolPickerSummary"', html)
        self.assertIn('id="symbolPickerAddFiltered"', html)
        self.assertIn('id="symbolPickerRemoveFiltered"', html)
        self.assertIn("data-symbol-select-all", self.source)
        self.assertIn("data-symbol-scope", self.source)
        self.assertIn('value="kr_kospi200"', html)
        self.assertIn('value="kr_kosdaq100"', html)
        self.assertIn('value="global_equity"', html)
        self.assertIn('maxlength="12000"', html)
        self.assertIn("\uc0bc\uc131\uc804\uc790 (005930 \u00b7 KOSPI 200)", self.source)
        self.assertIn("\uc5d0\ucf54\ud504\ub85c\ube44\uc5e0 (247540 \u00b7 KOSDAQ 100)", self.source)
        self.assertIn("Microsoft Corporation", self.source)
        self.assertIn("iShares MSCI ACWI ETF", self.source)
        self.assertIn("ASML Holding N.V. (Euronext Amsterdam)", self.source)
        self.assertIn("Siemens AG (Xetra)", self.source)
        self.assertIn("LVMH (Euronext Paris)", self.source)
        self.assertIn("Nintendo Co., Ltd. (Tokyo)", self.source)

    def test_symbol_picker_selection_does_not_filter_by_price_availability(self):
        match = re.search(
            r"async function addFilteredSymbolsToBacktestUniverse\(\) \{(?P<body>.*?)\n\}",
            self.source,
            re.S,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("setSymbolTargetSymbols(target, [...readSymbolTargetSymbols(target), ...symbols])", body)
        self.assertNotIn("resolveBacktestUniverseAvailability", body)
        self.assertIn("state.lastUniverseResolution = null", self.source)

    def test_symbol_picker_is_shared_across_ticker_inputs(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        for marker in [
            'id="tickerSearchOpen"',
            'id="assetDetailTickerOpen"',
            'id="assetDetailBenchmarkOpen"',
            'id="backtestBenchmarkOpen"',
            'id="portfolioUniverseOpen"',
            'id="portfolioUniverseChips"',
            'id="portfolioBenchmarkOpen"',
            'id="forecastTickerOpen"',
            'id="forecastBenchmarkOpen"',
            'id="quantamentalTickerOpen"',
            'id="aiPortfolioCustomUniverseOpen"',
            'id="aiPortfolioCustomUniverseChips"',
            'id="aiPortfolioBenchmarkOpen"',
            'id="symbolPickerDescription"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "const SYMBOL_PICKER_TARGETS",
            "function setSymbolTargetSymbols",
            "function renderSymbolTargetChips",
            'openSymbolPicker("research")',
            'openSymbolPicker("assetDetailTicker")',
            'openSymbolPicker("backtestBenchmark")',
            'openSymbolPicker("portfolio")',
            'openSymbolPicker("forecastTicker")',
            'openSymbolPicker("quantamentalTicker")',
            'openSymbolPicker("aiPortfolioCustomUniverse")',
            'renderSymbolTargetChips("portfolio")',
            'renderSymbolTargetChips("aiPortfolioCustomUniverse")',
        ]:
            self.assertIn(marker, self.source)

    def test_quant_universe_resolve_hydrates_missing_prices_before_execution(self):
        self.assertIn("hydrate_missing", self.source)
        self.assertIn("\uac00\uaca9 \uc774\ub825 ${_fmtNumber(hydratedCount)}\uac1c \uc790\ub3d9 \ubcf4\uac15", self.source)
        self.assertIn("\ub204\ub77d\ub41c \uac00\uaca9 \uc774\ub825\uc740 \uc790\ub3d9 \ubcf4\uac15\ud558\ub294 \uc911\uc785\ub2c8\ub2e4", self.source)
        self.assertIn("numberInputValue(els.backtestLongWindow", self.source)

    def test_strategy_editor_is_code_only_not_universe_editor(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("function strategyCodeOnlyPayload", self.source)
        self.assertIn("delete clean.universe", self.source)
        self.assertIn("delete clean.benchmark", self.source)
        self.assertNotIn("universe: request.tickers.length", self.source)
        self.assertIn("API.quantStrategyGenerate", self.source)
        self.assertIn("function runQuantStrategyGenerate", self.source)
        self.assertIn("function renderStrategyPromptReview", self.source)
        self.assertIn("API.quantUniverseResolve", self.source)
        self.assertIn("function resolveBacktestUniverseAvailability", self.source)
        self.assertIn('id="strategyPromptInput"', html)
        self.assertIn('id="quantStrategyGenerate"', html)
        self.assertIn('id="strategyPromptReviewSurface"', html)
        self.assertIn("Strategy definition JSON only", html)
        self.assertIn("Python \ucf54\ub4dc\uac00 \uc544\ub2c8\uba74", html)

    def test_dashboard_tab_switching_is_url_addressable_and_verified(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="homeDashboardTabs"', html)
        self.assertIn('data-dashboard-tab="quant"', html)
        self.assertIn('data-dashboard-tab="ai-portfolio"', html)
        self.assertIn('data-dashboard-tab="macro"', html)
        self.assertIn("function dashboardTabFromLocation", self.source)
        self.assertIn("hashchange", self.source)
        self.assertIn('"#macro"', self.source)
        self.assertIn('"#quant-lab"', self.source)
        self.assertIn('"#ai-portfolio"', self.source)
        self.assertIn("setDashboardTab(nextTab", self.source)
        self.assertIn("function loadMarketDashboard", self.source)
        self.assertIn("function loadActiveDashboardResources", self.source)

    def test_dashboard_initialization_does_not_eager_load_market_for_other_tabs(self):
        init_match = re.search(r"\(async function init\(\) \{(?P<body>.*?)\n\}\)\(\);", self.source, re.S)
        self.assertIsNotNone(init_match)
        init_body = init_match.group("body")
        self.assertIn("loadActiveDashboardResources(false)", init_body)
        for marker in [
            "initializeTradingViewDashboard(false);",
            "loadDashboardEquityHeatmap(false);",
            "loadDashboardMarket(false);",
            "loadDataHealth(false);",
            "loadDashboardNews(false);",
        ]:
            self.assertNotIn(marker, init_body)
        show_match = re.search(r"function showHome\(\) \{(?P<body>.*?)\n\}\n\nfunction showTvFallback", self.source, re.S)
        self.assertIsNotNone(show_match)
        self.assertIn("loadActiveDashboardResources(false)", show_match.group("body"))
        market_match = re.search(r"function loadMarketDashboard\(force = false\) \{(?P<body>.*?)\n\}", self.source, re.S)
        self.assertIsNotNone(market_match)
        market_body = market_match.group("body")
        self.assertIn("initializeTradingViewDashboard(force)", market_body)
        self.assertIn("loadDashboardEquityHeatmap(force)", market_body)
        self.assertIn("loadDashboardMarket(force)", market_body)
        self.assertIn("loadDashboardNews(force)", market_body)

    def test_tradingview_chart_controls_are_real_and_persistent(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        for marker in [
            'id="tvChartSource"',
            'id="tvChartSymbol"',
            'id="tvChartInterval"',
            'id="tvChartCompare"',
            'data-testid="tradingview-chart-apply"',
        ]:
            self.assertIn(marker, html)
        self.assertIn("fingpt.tvChart.v1", self.source)
        self.assertIn("function tradingViewOverviewConfig", self.source)
        self.assertIn("compareSymbols", self.source)
        self.assertIn("function renderInternalOhlcChart", self.source)
        self.assertIn("function mountInternalMarketChart", self.source)
        self.assertIn("function fetchInternalChartPayload", self.source)
        self.assertIn("function aggregateInternalOhlcRows", self.source)
        self.assertIn("TV_INTERNAL_INTRADAY_INTERVALS", self.source)
        self.assertIn("dashboardIntraday", self.source)
        self.assertIn("API.dataPrices", self.source)
        self.assertIn('data-testid="internal-market-chart"', self.source)
        self.assertIn("function applyTvChartSettings", self.source)
        self.assertIn("mountMarketOverviewChart", self.source)

    def test_macro_static_ui_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        for marker in [
            'id="macroDashboardTab"',
            'id="macroSurface"',
            'id="macroRefresh"',
            'data-testid="macro-refresh"',
            'id="macroBriefGenerate"',
            'data-testid="macro-brief-generate"',
            'id="macroReportExport"',
            'data-testid="macro-report-export"',
            'id="macroLoadStatus"',
            'id="macroOverviewSurface"',
            'id="macroCoverageSurface"',
            'id="macroProviderHealthSurface"',
            'id="macroProviderFilter"',
            'id="macroCategoryFilter"',
            'id="macroCompareSurface"',
            'id="macroIndicatorTable"',
            'id="macroChartSurface"',
            'id="macroInterestRatesSurface"',
            'id="macroInflationSurface"',
            'id="macroGrowthLaborSurface"',
            'id="macroHousingConsumerSurface"',
            'id="macroYieldCurveSurface"',
            'id="macroLiquidityCreditSurface"',
            'id="macroFinancialConditionsSurface"',
            'id="macroFxDollarSurface"',
            'id="macroCommoditiesSurface"',
            'id="macroRegimeSurface"',
            'id="macroAssetImpactSurface"',
            'id="macroScenarioSurface"',
            'data-action="macro-scenario"',
            'id="macroResearchPreviewSurface"',
            'id="macroResearchTicker"',
            'id="macroResearchPreviewRun"',
            'data-testid="macro-research-preview-run"',
            'id="macroResearchPreviewResult"',
            'id="macroPortfolioHintsSurface"',
            'id="macroBriefSurface"',
            'id="macroDataQualitySurface"',
            '<section class="home-card macro-card macro-hints-card macro-surface" data-panel-tier="operations">',
            '<section class="home-card macro-card macro-brief-card macro-surface" data-panel-tier="operations">',
            'id="dashboardViewControls"',
            'data-panel-view="overview"',
            'data-panel-view="details"',
            'data-panel-view="operations"',
            'data-panel-view="all"',
            'id="globalQualitySummary"',
            'id="dashboardRangeControls"',
            'id="dashboardRangeSelect"',
            'id="dashboardRangeStart"',
            'id="dashboardRangeEnd"',
            'id="quantamentalAiModel"',
            'id="quantamentalAiModelStatus"',
            'data-testid="quantamental-ai-model-control"',
            'data-summary-field="observations"',
            'data-summary-field="missing"',
            'data-summary-field="ai-snapshot"',
            'id="qualityContextSummary"',
            'data-quality-detail="source"',
            'data-quality-detail="cache"',
            'data-quality-detail="range-support"',
            '<option value="1D">1D</option>',
            '<option value="MAX">MAX</option>',
            '<button type="button" id="macroBriefGenerate"',
        ]:
            self.assertIn(marker, html)
        self.assertIn('.dashboard-surface-grid[data-panel-view="overview"]', css)
        self.assertIn('.dashboard-view-controls', css)
        self.assertIn(".global-quality-summary", css)
        self.assertIn(".quality-context-summary", css)
        self.assertIn(".dashboard-range-controls", css)
        self.assertIn(".quantamental-ai-control", css)
        self.assertIn('.dashboard-surface-grid[data-panel-view="all"] [data-panel-tier="primary"] .home-card-head::before', css)
        self.assertIn(".dashboard-range-controls.range-warning", css)
        self.assertIn("DEFAULT_DASHBOARD_PANEL_VIEWS", self.source)
        self.assertIn("dashboardPanelViewByTab: initDashboardPanelViews()", self.source)
        self.assertIn('market: "all"', self.source)
        self.assertIn('macro: "all"', self.source)
        self.assertIn("function setGlobalRange", self.source)
        self.assertIn("function normalizeCustomGlobalDateOrder", self.source)
        self.assertIn("function globalRangeValidationMessage", self.source)
        self.assertIn("function globalRangeSupportSummary", self.source)
        self.assertIn("function updateGlobalQualitySummary", self.source)
        self.assertIn("function markGlobalQualityRangePending", self.source)
        self.assertIn("function renderQuantamentalAiModelOptions", self.source)
        self.assertIn("function quantamentalAiRequestOptions", self.source)
        self.assertIn("model: aiOptions.model", self.source)
        self.assertIn("기간 변경 후 데이터 재계산 대기", self.source)
        self.assertIn("function renderGlobalQualityContextSummary", self.source)
        self.assertIn("function displayMissingSummary", self.source)
        self.assertIn("AI 기준:", self.source)
        self.assertIn("globalRangeLookbackDays", self.source)
        self.assertLess(
            html.index('class="home-card macro-card macro-hints-card macro-surface"'),
            html.index('class="home-card macro-card macro-brief-card macro-surface"'),
        )
        for marker in [
            "macroOverview:",
            "API.macroDashboard",
            "API.macroProviderHealth",
            "API.macroScenario",
            "API.macroResearchContext",
            "API.macroSeriesList",
            "API.macroHousingConsumer",
            "API.macroFinancialConditions",
            "API.macroRefreshRun",
            "API.macroRefreshStatus",
            "API.macroBrief",
            "API.macroReport",
            "function loadMacro",
            "function loadMacroProgressive",
            "function refreshMacroData",
            "function renderMacroOverview",
            "function renderMacroProviderHealth",
            "function runMacroScenario",
            "function runMacroResearchPreview",
            "function loadMacroDefaultSeriesDetail",
            "function macroFetchJsonWithTimeout",
            "function renderMacroLoadStatus",
            "function renderMacroPanelFailure",
            "function renderMacroActionPaneStarters",
            "\uae30\uc874 \ub300\uc2dc\ubcf4\ub4dc \ud654\uba74\uc744 \uc720\uc9c0",
            "return true;",
            "return false;",
            "renderMacroLoadStatus(\"\ub9e4\ud06c\ub85c \uacf5\uae09\uc790 \uac31\uc2e0 \uc2e4\ud328\"",
            "function renderMacroCoverage",
            "function renderMacroIndicatorTable",
            "function renderMacroSeriesChart",
            "function renderMacroEtfCandidates",
            "function macroFallbackEtfCandidates",
            "function generateMacroBrief",
            "function exportMacroReport",
            "function macroDataSurfaces",
            "state.macroOverview",
            "renderActionCompletion(\"\ub9e4\ud06c\ub85c \ub370\uc774\ud130 \uac31\uc2e0 \uc644\ub8cc\"",
        ]:
            self.assertIn(marker, self.source)
        self.assertIn(".macro-surface", css)
        self.assertIn(".macro-coverage-grid", css)
        self.assertIn(".macro-coverage-chip", css)
        self.assertIn(".macro-etf-grid", css)
        self.assertIn(".macro-etf-card", css)
        self.assertIn('.dashboard-surface-grid[data-dashboard-tab="macro"] .macro-hints-card', css)
        self.assertIn('[data-dashboard-tab="macro"]', css)
        self.assertIn(".decision-completion", css)

    def test_quant_action_controls_have_stable_automation_selectors(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        for marker in [
            'data-testid="quant-feature-run"',
            'data-testid="quant-signal-run"',
            'data-testid="quant-strategy-refresh"',
            'data-testid="quant-strategy-new-draft"',
            'data-testid="quant-strategy-generate"',
            'data-testid="quant-strategy-dry-run"',
            'data-testid="quant-strategy-save"',
            'data-testid="quant-strategy-delete"',
            'data-testid="quant-backtest-run"',
            'data-testid="quant-export-storage-report"',
            'data-testid="quant-cross-run-cleanup-preview"',
            'data-testid="quant-run-history-refresh"',
            'data-testid="portfolio-sync-backtest"',
            'data-testid="portfolio-optimize"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            'data-testid="quant-export-verify-latest"',
            'data-testid="quant-export-verify-row"',
            'data-testid="quant-run-open"',
            'data-testid="quant-strategy-row-load"',
            'data-action="enable-strict-freshness"',
            "renderActionCompletion(\"\ubc31\ud14c\uc2a4\ud2b8 \uc644\ub8cc\"",
            "renderActionCompletion(\"\ubc31\ud14c\uc2a4\ud2b8 \uc2e4\ud589 \ubcf4\ub958\"",
            "renderActionCompletion(\"\ubc31\ud14c\uc2a4\ud2b8 \uc2e4\ud328\"",
            "renderActionCompletion(\"\ud329\ud130 \ubbf8\ub9ac\ubcf4\uae30 \uc644\ub8cc\"",
            "renderActionCompletion(\"\ud3ec\ud2b8\ud3f4\ub9ac\uc624 \ucd5c\uc801\ud654 \uc644\ub8cc\"",
        ]:
            self.assertIn(marker, self.source)

    def test_ai_portfolio_static_ui_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        for marker in [
            'id="aiPortfolioTab"',
            'id="aiPortfolioSurface"',
            'id="aiPortfolioInvestmentTypes"',
            'id="aiPortfolioUniverse"',
            'id="aiPortfolioCustomUniverse"',
            'id="aiPortfolioUniverseStatus"',
            'id="aiPortfolioPolicyForm"',
            'id="aiPortfolioGenerate"',
            'id="aiPortfolioRecommendationSurface"',
            'id="aiPortfolioPerformanceSurface"',
            'id="aiPortfolioComplianceSurface"',
            'id="aiPortfolioRebalanceSurface"',
            'id="aiPortfolioReportsSurface"',
            'id="aiPortfolioHistorySurface"',
            'id="aiPortfolioApproveRebalance"',
            'id="aiPortfolioRejectRebalance"',
            'id="aiPortfolioDeferRebalance"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "API.aiPortfolioInvestmentTypes",
            "API.aiPortfolioUniverses",
            "API.aiPortfolioGenerate",
            "function syncAiPortfolioUniverseMode",
            "function loadAiPortfolio",
            "function runAiPortfolioGenerate",
            "function runAiPortfolioRebalanceCheck",
            "function generateAiPortfolioReport",
            "state.aiPortfolioPolicy",
        ]:
            self.assertIn(marker, self.source)
        self.assertIn(".ai-portfolio-surface", css)
        self.assertIn('[data-dashboard-tab="ai-portfolio"]', css)

    def test_quant_lab_visual_flow_keeps_history_after_portfolio(self):
        css = STYLES_CSS.read_text(encoding="utf-8")
        expected_orders = {
            "asset-detail-card": "1",
            "feature-card": "2",
            "signal-card": "3",
            "strategy-governance-card": "4",
            "backtest-card": "5",
            "portfolio-card": "6",
            "quant-run-history-card": "7",
        }
        for class_name, order in expected_orders.items():
            pattern = rf'\.dashboard-surface-grid\[data-dashboard-tab="quant"\] \.{class_name} \{{(?P<body>.*?)\}}'
            match = re.search(pattern, css, re.S)
            self.assertIsNotNone(match, class_name)
            self.assertIn(f"order: {order};", match.group("body"))

    def test_quantamental_static_ui_contract(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        css = STYLES_CSS.read_text(encoding="utf-8")
        module_source = (Path(__file__).resolve().parents[1] / "app" / "web" / "modules" / "quantamental-ui.js").read_text(encoding="utf-8")
        for marker in [
            'id="quantamentalTab"',
            'data-testid="quantamental-tab"',
            'data-dashboard-tab="quantamental"',
            'id="quantamentalSurface"',
            'id="quantamentalTicker"',
            'id="quantamentalTickerOpen"',
            'id="quantamentalMarket"',
            'id="quantamentalPeriod"',
            'id="quantamentalYears"',
            'id="quantamentalLookback"',
            'id="quantamentalStyle"',
            'id="quantamentalAnalyze"',
            'data-testid="quantamental-analyze"',
            'id="quantamentalSignalSurface"',
            'id="quantamentalScoreSurface"',
            'id="quantamentalFactorSurface"',
            'id="quantamentalMainSurface"',
            'id="quantamentalAiRefresh"',
            'data-testid="quantamental-ai-report"',
            'id="quantamentalDataQualitySurface"',
            'id="quantamentalCompareTickers"',
            'id="quantamentalCompareRun"',
            'data-testid="quantamental-compare-run"',
            'id="quantamentalCompareSurface"',
            'id="quantamentalScreenRun"',
            'data-testid="quantamental-screen-run"',
            'id="quantamentalScreenSurface"',
            'id="quantamentalScoreThreshold"',
            'id="quantamentalScoreMetric"',
            'id="quantamentalScoreScreenLimit"',
            'id="quantamentalScoreScreenRun"',
            'data-testid="quantamental-score-screen-run"',
            'id="quantamentalScoreScreenStatus"',
            'id="quantamentalScoreScreenSurface"',
            'src="modules/quantamental-ui.js?v=20260519-quantamental-v12"',
        ]:
            self.assertIn(marker, html)
        for marker in [
            "API.quantamentalAnalysis",
            "API.quantamentalAiReport",
            "API.quantamentalAiQa",
            "API.quantamentalCompare",
            "API.quantamentalTopSignals",
            "API.quantamentalScoreScreen",
            "score_key",
            "function loadQuantamental",
            "function runQuantamentalAnalysis",
            "function runQuantamentalCompare",
            "function loadQuantamentalScreen",
            "function runQuantamentalScoreScreen",
            "Force reloads bypass the UI cache; stale-aware server refresh keeps Top 5 fast.",
            "forceRefresh: false",
            "function refreshQuantamentalAiReport",
            "function askQuantamentalQuestion",
            'openSymbolPicker("quantamentalTicker")',
            '"#quantamental"',
            "state.quantamentalActiveTab",
            "window.FinGPTQuantamentalUi",
        ]:
            self.assertIn(marker, self.source)
        for marker in [
            "global.FinGPTQuantamentalUi",
            "companyHeader",
            "signalCard",
            "scoreDashboard",
            "factorGrid",
            "mainPanel",
            "qaAnswer",
            "comparisonTable",
            "topSignals",
            "scoreScreen",
            "quantamental-ai-used-data",
            "function aiReportSection",
            "Research classification only. Not investment advice.",
        ]:
            self.assertIn(marker, module_source)
        self.assertIn('[data-dashboard-tab="quantamental"]', css)
        self.assertIn(".quantamental-surface", css)
        self.assertIn(".quantamental-tabs", css)


if __name__ == "__main__":
    unittest.main()
