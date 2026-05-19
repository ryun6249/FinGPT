/* =============================================================
   FinGPT Local Research Assistant — UI Controller
   ============================================================= */

const API = {
  config: "/api/v1/config",
  analyze: "/api/v1/research/analyze",
  stream: "/api/v1/research/stream",
  universal: "/api/v1/research/universal",
  universalStream: "/api/v1/research/universal/stream",
  compare: "/api/v1/research/compare",
  watchlist: "/api/v1/watchlist",
  latest: "/api/v1/outputs/latest",
  reportMd: "/api/v1/outputs/report.md",
  reportHtml: "/api/v1/outputs/report.html",
  health: "/api/v1/health",
  runs: "/api/v1/runs",
  run: (id) => `/api/v1/runs/${encodeURIComponent(id)}`,
  runSummary: (ticker) => `/api/v1/runs/summary/${encodeURIComponent(ticker)}`,
  preflight: "/api/v1/preflight",
  preflightForce: "/api/v1/preflight?force=true",
  runbookFailureModes: "/api/v1/runbook/failure-modes",
  qdrantInfo: "/api/v1/qdrant/collection",
  qdrantPurge: "/api/v1/qdrant/purge",
  evalDashboard: "/api/v1/eval/dashboard",
  dashboardNews: (options = {}) => {
    const params = new URLSearchParams({ limit: String(options.limit || 20) });
    if (options.query) params.set("query", options.query);
    if (options.ticker) params.set("ticker", options.ticker);
    if (options.topic) params.set("topic", options.topic);
    return `/api/v1/dashboard/news?${params.toString()}`;
  },
  dashboardMarket: "/api/v1/dashboard/market",
  dashboardMarketOverview: "/api/v1/dashboard/market/overview",
  dashboardDecisionCards: "/api/v1/dashboard/decision-cards",
  dashboardCrossAssetAnalyze: (options = {}) => {
    const params = new URLSearchParams();
    if (options.symbols) params.set("symbols", options.symbols);
    if (options.topic) params.set("topic", options.topic);
    if (options.horizon) params.set("horizon", options.horizon);
    return `/api/v1/dashboard/cross-asset/analyze?${params.toString()}`;
  },
  dashboardIntraday: (ticker, interval = "5m", limit = 500) => {
    const params = new URLSearchParams({ interval: String(interval), limit: String(limit) });
    return `/api/v1/dashboard/market/intraday/${encodeURIComponent(ticker)}?${params.toString()}`;
  },
  dashboardEquityHeatmap: "/api/v1/dashboard/equity-heatmap",
  macroSeriesList: "/api/v1/macro/series",
  macroSeriesSearch: (query, limit = 12) => `/api/v1/macro/series/search?q=${encodeURIComponent(query || "")}&limit=${encodeURIComponent(limit)}`,
  macroSeriesDetail: (seriesId, observationLimit = 240) => `/api/v1/macro/series/${encodeURIComponent(seriesId || "")}/detail?observation_limit=${encodeURIComponent(observationLimit)}`,
  macroDashboard: "/api/v1/macro/dashboard?observation_limit=20",
  macroProviderHealth: "/api/v1/macro/provider-health",
  macroScenario: "/api/v1/macro/scenario",
  macroResearchContext: (ticker) => `/api/v1/macro/research-context?ticker=${encodeURIComponent(ticker || "")}`,
  macroOverview: "/api/v1/macro/overview?compact=true&observation_limit=120",
  macroInterestRates: "/api/v1/macro/interest-rates?compact=true&observation_limit=0",
  macroInflation: "/api/v1/macro/inflation?compact=true&observation_limit=0",
  macroGrowthLabor: "/api/v1/macro/growth-labor?compact=true&observation_limit=0",
  macroHousingConsumer: "/api/v1/macro/housing-consumer?compact=true&observation_limit=0",
  macroYieldCurve: "/api/v1/macro/yield-curve?compact=true&observation_limit=0",
  macroLiquidityCredit: "/api/v1/macro/liquidity-credit?compact=true&observation_limit=0",
  macroFinancialConditions: "/api/v1/macro/financial-conditions?compact=true&observation_limit=0",
  macroFxDollar: "/api/v1/macro/fx-dollar?compact=true&observation_limit=0",
  macroCommodities: "/api/v1/macro/commodities?compact=true&observation_limit=0",
  macroPortfolioHints: "/api/v1/macro/portfolio-policy-hints",
  macroBrief: "/api/v1/macro/brief",
  macroReport: "/api/v1/macro/report",
  macroDataQuality: "/api/v1/macro/data-quality",
  macroRefreshRun: "/api/v1/macro/refresh",
  macroRefreshStatus: "/api/v1/macro/refresh/status",
  dataHealth: "/api/v1/data/health",
  dataPrices: (ticker, limit = 252, options = {}) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (options.refresh) params.set("refresh", "true");
    if (options.startDate) params.set("start_date", options.startDate);
    if (options.endDate) params.set("end_date", options.endDate);
    if (options.freshnessProfile) params.set("freshness_profile", options.freshnessProfile);
    if (options.requireFreshPrices) params.set("require_fresh_prices", "true");
    if (options.maxMarketCalendarLagDays !== undefined && options.maxMarketCalendarLagDays !== null) {
      params.set("max_market_calendar_lag_days", String(options.maxMarketCalendarLagDays));
    }
    return `/api/v1/data/prices/${encodeURIComponent(ticker)}?${params.toString()}`;
  },
  dataFundamentals: (ticker) => `/api/v1/data/fundamentals/${encodeURIComponent(ticker)}`,
  backtestRun: "/api/v1/backtest/run",
  quantFeatures: "/api/v1/quant/features/preview",
  quantSignals: "/api/v1/quant/signals/generate",
  quantBacktest: "/api/v1/quant/backtest",
  quantBacktests: "/api/v1/quant/backtests",
  quantBacktestsCompare: "/api/v1/quant/backtests/compare",
  quantBacktestBundle: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/bundle`,
  quantBacktestReplay: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/replay`,
  quantBacktestReplayReports: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/replay-reports`,
  quantBacktestExport: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/export`,
  quantBacktestExports: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/exports`,
  quantBacktestExportCleanupPreview: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/exports/cleanup-preview`,
  quantBacktestExportCleanup: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/exports/cleanup`,
  quantBacktestExportVerify: (runId) => `/api/v1/quant/backtest/${encodeURIComponent(runId)}/export/verify`,
  quantExportStorage: "/api/v1/quant/exports/storage",
  quantExportCleanupPreview: "/api/v1/quant/exports/cleanup-preview",
  quantExportCleanup: "/api/v1/quant/exports/cleanup",
  quantStrategies: "/api/v1/quant/strategy/list",
  quantStrategy: (strategyId) => `/api/v1/quant/strategy/${encodeURIComponent(strategyId)}`,
  quantStrategyDryRun: "/api/v1/quant/strategy/dry-run",
  quantStrategyGenerate: "/api/v1/quant/strategy/generate",
  quantStrategySave: "/api/v1/quant/strategy/save",
  quantUniverseResolve: "/api/v1/quant/universe/resolve",
  forecastHealth: "/api/v1/forecast/health",
  forecastModels: "/api/v1/forecast/models",
  forecastDatasetPreview: "/api/v1/forecast/dataset/preview",
  forecastDatasetHydrate: "/api/v1/forecast/dataset/hydrate",
  forecastFeaturesBuild: "/api/v1/forecast/features/build",
  forecastLeakageCheck: "/api/v1/forecast/leakage/check",
  forecastTrain: "/api/v1/forecast/train",
  forecastJobs: "/api/v1/forecast/jobs",
  forecastJob: (jobId) => `/api/v1/forecast/jobs/${encodeURIComponent(jobId)}`,
  forecastJobCancel: (jobId) => `/api/v1/forecast/jobs/${encodeURIComponent(jobId)}/cancel`,
  forecastJobRetry: (jobId) => `/api/v1/forecast/jobs/${encodeURIComponent(jobId)}/retry`,
  forecastAiInterpretation: "/api/v1/forecast/ai-interpretation",
  forecastAiProviderHealth: "/api/v1/forecast/ai-provider/health",
  forecastVisualization: (experimentId) => `/api/v1/forecast/visualization/${encodeURIComponent(experimentId)}`,
  forecastExperiments: "/api/v1/forecast/experiments",
  forecastExperiment: (experimentId) => `/api/v1/forecast/experiments/${encodeURIComponent(experimentId)}`,
  forecastRegistry: "/api/v1/forecast/model-registry",
  forecastRegistryAudit: "/api/v1/forecast/model-registry/audit",
  forecastVerifyArtifact: "/api/v1/forecast/model-registry/verify-artifact",
  forecastPromoteModel: "/api/v1/forecast/model-registry/promote",
  forecastDeprecateModel: "/api/v1/forecast/model-registry/deprecate",
  forecastDriftCheck: "/api/v1/forecast/drift/check",
  forecastModelComparison: "/api/v1/forecast/model-comparison",
  portfolioOptimize: "/api/v1/portfolio/optimize",
  aiPortfolioInvestmentTypes: "/api/v1/ai-portfolio/investment-types",
  aiPortfolioUniverses: "/api/v1/ai-portfolio/universes",
  aiPortfolioStoreStatus: "/api/v1/ai-portfolio/store/status",
  aiPortfolioDashboard: "/api/v1/ai-portfolio/dashboard",
  aiPortfolioOperations: "/api/v1/ai-portfolio/operations",
  aiPortfolioHydrate: "/api/v1/ai-portfolio/operations/hydrate",
  aiPortfolioSnapshotJob: "/api/v1/ai-portfolio/operations/snapshots",
  aiPortfolioSecRefresh: "/api/v1/ai-portfolio/operations/sec-refresh",
  aiPortfolioPolicies: "/api/v1/ai-portfolio/policies",
  aiPortfolioPolicy: (policyId) => `/api/v1/ai-portfolio/policies/${encodeURIComponent(policyId)}`,
  aiPortfolioActivate: (policyId) => `/api/v1/ai-portfolio/policies/${encodeURIComponent(policyId)}/activate`,
  aiPortfolioDeactivate: (policyId) => `/api/v1/ai-portfolio/policies/${encodeURIComponent(policyId)}/deactivate`,
  aiPortfolioGenerate: "/api/v1/ai-portfolio/generate",
  aiPortfolioRecommendations: (policyId) => `/api/v1/ai-portfolio/recommendations?policy_id=${encodeURIComponent(policyId)}`,
  aiPortfolioRecommendationDiff: (policyId) => `/api/v1/ai-portfolio/recommendations/${encodeURIComponent(policyId)}/diff`,
  aiPortfolioRebalanceCheck: "/api/v1/ai-portfolio/rebalance/check",
  aiPortfolioRebalanceSignals: (policyId) => `/api/v1/ai-portfolio/rebalance/signals?policy_id=${encodeURIComponent(policyId)}`,
  aiPortfolioRebalanceAction: (signalId, action) => `/api/v1/ai-portfolio/rebalance/signals/${encodeURIComponent(signalId)}/${encodeURIComponent(action)}`,
  aiPortfolioReportsGenerate: "/api/v1/ai-portfolio/reports",
  aiPortfolioReports: (policyId) => `/api/v1/ai-portfolio/reports?policy_id=${encodeURIComponent(policyId)}`,
  aiPortfolioHistory: (policyId) => `/api/v1/ai-portfolio/history?policy_id=${encodeURIComponent(policyId)}`,
  quantamentalAnalysis: (ticker, options = {}) => {
    const params = new URLSearchParams({
      market: String(options.market || "US"),
      period: String(options.period || "annual"),
      years: String(options.years || 5),
      lookback: String(options.lookback || 252),
      style: String(options.style || "balanced"),
      include_ai: String(options.includeAi ?? true),
      use_llm: String(options.useLlm ?? false),
      force_refresh: String(options.forceRefresh ?? false),
      output_language: String(options.outputLanguage || selectedOutputLanguage()),
    });
    return `/api/v1/quantamental/analysis/${encodeURIComponent(ticker)}?${params.toString()}`;
  },
  quantamentalAiReport: "/api/v1/quantamental/ai/report",
  quantamentalAiQa: "/api/v1/quantamental/ai/qa",
  quantamentalCompare: "/api/v1/quantamental/compare",
  quantamentalTopSignals: (options = {}) => {
    const params = new URLSearchParams({
      universe: String(options.universe || "default_us_large_cap"),
      market: String(options.market || "US"),
      period: String(options.period || "annual"),
      years: String(options.years || 5),
      lookback: String(options.lookback || 252),
      style: String(options.style || "balanced"),
      limit: String(options.limit || 5),
      refresh_stale: String(options.refreshStale ?? true),
      force_refresh: String(options.forceRefresh ?? false),
      output_language: String(options.outputLanguage || selectedOutputLanguage()),
    });
    if (options.tickers) params.set("tickers", String(options.tickers));
    return `/api/v1/quantamental/screen/top-signals?${params.toString()}`;
  },
  quantamentalScoreScreen: (options = {}) => {
    const params = new URLSearchParams({
      universe: String(options.universe || "default_us_large_cap"),
      market: String(options.market || "US"),
      period: String(options.period || "annual"),
      years: String(options.years || 5),
      lookback: String(options.lookback || 252),
      style: String(options.style || "balanced"),
      score_key: String(options.scoreKey || "composite"),
      min_score: String(options.minScore ?? 70),
      limit: String(options.limit || 20),
      refresh_stale: String(options.refreshStale ?? true),
      force_refresh: String(options.forceRefresh ?? false),
      output_language: String(options.outputLanguage || selectedOutputLanguage()),
    });
    if (options.tickers) params.set("tickers", String(options.tickers));
    return `/api/v1/quantamental/screen/by-score?${params.toString()}`;
  },
  quantamentalCompareWatchlists: "/api/v1/quantamental/compare/watchlists",
  quantamentalCompareWatchlist: (id) => `/api/v1/quantamental/compare/watchlists/${encodeURIComponent(id || "")}`,
  quantamentalSnapshotExport: (snapshotId, format = "json") => `/api/v1/quantamental/snapshots/${encodeURIComponent(snapshotId || "")}/export?format=${encodeURIComponent(format)}`,
  quantamentalSnapshotDiff: (baseSnapshotId, targetSnapshotId) => `/api/v1/quantamental/snapshots/diff?base_snapshot_id=${encodeURIComponent(baseSnapshotId || "")}&target_snapshot_id=${encodeURIComponent(targetSnapshotId || "")}`,
  quantamentalSnapshotRetention: (options = {}) => {
    const params = new URLSearchParams({
      keep_last: String(options.keepLast || 20),
      dry_run: String(options.dryRun ?? true),
    });
    if (options.ticker) params.set("ticker", String(options.ticker));
    return `/api/v1/quantamental/snapshots/retention?${params.toString()}`;
  },
};

const STORAGE = {
  history: "fingpt.history.v1",
  form: "fingpt.form.v1",
  controlPanel: "fingpt.controlPanel.v1",
  dashboardLayout: "fingpt.dashboardLayout.v1",
  dashboardLayoutVersion: "fingpt.dashboardLayout.version",
  dashboardRange: "fingpt.dashboardRange.v1",
  tvChart: "fingpt.tvChart.v1",
  theme: "fingpt.theme.v1",
  outputLanguage: "fingpt.outputLanguage.v1",
  quantamentalCompareWatchlists: "fingpt.quantamental.compareWatchlists.v1",
};

const STAGES = ["collect", "ingest", "retrieve", "infer", "analyze", "report", "output"];
const DASHBOARD_PANEL_LAYOUT_VERSION = "20260519-all-default";
const DEFAULT_DASHBOARD_PANEL_VIEWS = {
  market: "all",
  macro: "all",
  quant: "all",
  quantamental: "all",
  forecast: "all",
  "ai-portfolio": "all",
};
const DEFAULT_GLOBAL_RANGE = { range: "1Y", startDate: "", endDate: "" };
const DASHBOARD_RANGE_OPTIONS = new Set(["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX", "custom"]);
const DASHBOARD_RANGE_LOOKBACK_DAYS = {
  "1D": 1,
  "1W": 5,
  "1M": 21,
  "3M": 63,
  "6M": 126,
  "1Y": 252,
  "3Y": 756,
  "5Y": 1260,
  MAX: 5000,
};

const TV_ADVANCED_CHART_SCRIPT = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
const TV_CHART_DEFAULTS = { source: "internal", symbolKey: "SPY", interval: "D", compareKey: "" };
const TV_CHART_SYMBOLS = {
  SPY: { label: "SPY · S&P 500", symbol: "AMEX:SPY", dataTicker: "SPY" },
  QQQ: { label: "QQQ · Nasdaq 100", symbol: "NASDAQ:QQQ", dataTicker: "QQQ" },
  TLT: { label: "TLT · 20Y Treasury", symbol: "NASDAQ:TLT", dataTicker: "TLT" },
  HYG: { label: "HYG · High Yield", symbol: "AMEX:HYG", dataTicker: "HYG" },
  LQD: { label: "LQD · IG Credit", symbol: "AMEX:LQD", dataTicker: "LQD" },
  GLD: { label: "GLD · Gold", symbol: "AMEX:GLD", dataTicker: "GLD" },
  "BTC-USD": { label: "BTC-USD · Bitcoin", symbol: "COINBASE:BTCUSD", dataTicker: "BTC-USD" },
  DXY: { label: "DXY · Dollar Index", symbol: "TVC:DXY", dataTicker: "DX-Y.NYB" },
  US10Y: { label: "US10Y · 10Y Yield", symbol: "TVC:US10Y", dataTicker: "^TNX" },
};
const TV_CHART_INTERVALS = {
  5: "5m",
  15: "15m",
  60: "1h",
  D: "Daily",
  W: "Weekly",
  M: "Monthly",
};
const TV_INTERNAL_INTRADAY_INTERVALS = new Set(["5", "15", "60"]);
const AI_PORTFOLIO_DASHBOARD_CACHE_TTL_MS = 15000;

function safeReadStoredJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return { ...fallback, ...JSON.parse(raw) };
  } catch (_) {
    return fallback;
  }
}

function safeWriteStoredJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {}
}

function safeReadStoredValue(key, fallback = "") {
  try {
    return localStorage.getItem(key) || fallback;
  } catch (_) {
    return fallback;
  }
}

function safeWriteStoredValue(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (_) {}
}

function initDashboardPanelViews() {
  const savedVersion = safeReadStoredValue(STORAGE.dashboardLayoutVersion, "");
  if (savedVersion !== DASHBOARD_PANEL_LAYOUT_VERSION) {
    safeWriteStoredJson(STORAGE.dashboardLayout, DEFAULT_DASHBOARD_PANEL_VIEWS);
    safeWriteStoredValue(STORAGE.dashboardLayoutVersion, DASHBOARD_PANEL_LAYOUT_VERSION);
    return { ...DEFAULT_DASHBOARD_PANEL_VIEWS };
  }
  return safeReadStoredJson(STORAGE.dashboardLayout, DEFAULT_DASHBOARD_PANEL_VIEWS);
}

function normalizeGlobalRange(value) {
  const raw = String(value || "").trim();
  const normalized = raw.toLowerCase() === "custom" ? "custom" : raw.toUpperCase();
  return DASHBOARD_RANGE_OPTIONS.has(normalized) ? normalized : "1Y";
}

function initGlobalRangeFromLocation() {
  const saved = safeReadStoredJson(STORAGE.dashboardRange, DEFAULT_GLOBAL_RANGE);
  const params = new URLSearchParams(window.location.search || "");
  const urlRange = params.get("range");
  const range = normalizeGlobalRange(urlRange || saved.range || DEFAULT_GLOBAL_RANGE.range);
  const ordered = normalizeCustomGlobalDateOrder(params.get("start") || saved.startDate, params.get("end") || saved.endDate);
  return {
    range,
    startDate: ordered.startDate,
    endDate: ordered.endDate,
  };
}

const els = {
  homeBtn: document.getElementById("homeBtn"),
  controlPanel: document.querySelector(".control-panel"),
  commandPanelToggle: document.getElementById("commandPanelToggle"),
  form: document.getElementById("analysisForm"),
  ticker: document.getElementById("ticker"),
  tickerSearchOpen: document.getElementById("tickerSearchOpen"),
  researchModeInputs: () => document.querySelectorAll('input[name="researchMode"]'),
  tickerChips: document.getElementById("tickerChips"),
  question: document.getElementById("question"),
  presetChips: document.getElementById("presetChips"),
  sourceInputs: () => document.querySelectorAll('input[name="source"]'),
  lookback: document.getElementById("lookback"),
  lookbackValue: document.getElementById("lookbackValue"),
  topk: document.getElementById("topk"),
  topkValue: document.getElementById("topkValue"),
  model: document.getElementById("model"),
  fingptStatus: document.getElementById("fingptStatus"),
  runBtn: document.getElementById("runBtn"),
  loadLatestBtn: document.getElementById("loadLatestBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  historyToggleBtn: document.getElementById("historyToggleBtn"),
  historySummary: document.getElementById("historySummary"),
  historyList: document.getElementById("historyList"),
  healthPill: document.getElementById("healthPill"),

  preflightPill: document.getElementById("preflightPill"),
  preflightDot: document.getElementById("preflightDot"),
  preflightLabel: document.getElementById("preflightLabel"),
  preflightPanel: document.getElementById("preflightPanel"),
  preflightSubtitle: document.getElementById("preflightSubtitle"),
  preflightChecks: document.getElementById("preflightChecks"),
  preflightRunbook: document.getElementById("preflightRunbook"),
  preflightRefresh: document.getElementById("preflightRefresh"),
  preflightClose: document.getElementById("preflightClose"),

  qdrantAdminBtn: document.getElementById("qdrantAdminBtn"),
  qdrantPanel: document.getElementById("qdrantPanel"),
  qdrantSubtitle: document.getElementById("qdrantSubtitle"),
  qdrantStats: document.getElementById("qdrantStats"),
  qdrantBreakdownList: document.getElementById("qdrantBreakdownList"),
  qdrantBreakdownNote: document.getElementById("qdrantBreakdownNote"),
  qdrantRefresh: document.getElementById("qdrantRefresh"),
  qdrantClose: document.getElementById("qdrantClose"),
  qdrantPurgeDays: document.getElementById("qdrantPurgeDays"),
  qdrantPurgeTicker: document.getElementById("qdrantPurgeTicker"),
  qdrantPurgeDryRun: document.getElementById("qdrantPurgeDryRun"),
  qdrantPurgeRun: document.getElementById("qdrantPurgeRun"),
  qdrantPurgeResult: document.getElementById("qdrantPurgeResult"),

  qualityDashBtn: document.getElementById("qualityDashBtn"),
  globalQualitySummary: document.getElementById("globalQualitySummary"),
  themeToggleBtn: document.getElementById("themeToggleBtn"),
  languageToggle: document.getElementById("languageToggle"),
  qualityPanel: document.getElementById("qualityPanel"),
  qualitySubtitle: document.getElementById("qualitySubtitle"),
  qualitySummary: document.getElementById("qualitySummary"),
  qualityContextSummary: document.getElementById("qualityContextSummary"),
  qualityDataHealth: document.getElementById("qualityDataHealth"),
  qualityMacroData: document.getElementById("qualityMacroData"),
  qualityCategories: document.getElementById("qualityCategories"),
  qualityCases: document.getElementById("qualityCases"),
  qualityCasesNote: document.getElementById("qualityCasesNote"),
  qualityReport: document.getElementById("qualityReport"),
  qualityRefresh: document.getElementById("qualityRefresh"),
  qualityClose: document.getElementById("qualityClose"),

  tickerSummary: document.getElementById("tickerSummary"),
  sparkline: document.getElementById("sparkline"),
  sparklineLabel: document.getElementById("sparklineLabel"),

  emptyState: document.getElementById("emptyState"),
  loadingState: document.getElementById("loadingState"),
  loadingTicker: document.getElementById("loadingTicker"),
  loadingSub: document.getElementById("loadingSub"),
  loadingTimer: document.getElementById("loadingTimer"),
  progressStages: document.getElementById("progressStages"),

  resultView: document.getElementById("resultView"),
  resTicker: document.getElementById("resTicker"),
  resStatus: document.getElementById("resStatus"),
  resCacheBadge: document.getElementById("resCacheBadge"),
  compareMode: document.getElementById("compareMode"),
  tickerHint: document.getElementById("tickerHint"),
  compareView: document.getElementById("compareView"),
  compareMeta: document.getElementById("compareMeta"),
  compareTable: document.getElementById("compareTable"),
  compareSummaries: document.getElementById("compareSummaries"),
  watchlistList: document.getElementById("watchlistList"),
  watchlistAddBtn: document.getElementById("watchlistAddBtn"),
  watchlistSchedStatus: document.getElementById("watchlistSchedStatus"),
  resQuestion: document.getElementById("resQuestion"),
  errorBanner: document.getElementById("errorBanner"),
  resSentiment: document.getElementById("resSentiment"),
  resConfidence: document.getElementById("resConfidence"),
  confidenceFill: document.getElementById("confidenceFill"),
  resCitationCount: document.getElementById("resCitationCount"),
  resChunkCount: document.getElementById("resChunkCount"),

  tabs: document.querySelectorAll(".tab"),
  tabPanels: document.querySelectorAll(".tab-panel"),

  resSummary: document.getElementById("resSummary"),
  resConclusion: document.getElementById("resConclusion"),
  metricsTable: document.getElementById("metricsTable"),
  quantSnapshot: document.getElementById("quantSnapshot"),
  riskPanel: document.getElementById("riskPanel"),
  scenarioPanel: document.getElementById("scenarioPanel"),
  bullList: document.getElementById("bullList"),
  bearList: document.getElementById("bearList"),
  evidenceList: document.getElementById("evidenceList"),
  evidenceSearch: document.getElementById("evidenceSearch"),
  citationsList: document.getElementById("citationsList"),
  diagRequest: document.getElementById("diagRequest"),
  diagInference: document.getElementById("diagInference"),
  stageTimeline: document.getElementById("stageTimeline"),
  sourceResultsBody: document.getElementById("sourceResultsBody"),
  providerResultsBody: document.getElementById("providerResultsBody"),
  diagRetrieval: document.getElementById("diagRetrieval"),
  reportMd: document.getElementById("reportMd"),
  rawJson: document.getElementById("rawJson"),

  downloadMdBtn: document.getElementById("downloadMdBtn"),
  downloadJsonBtn: document.getElementById("downloadJsonBtn"),
  openHtmlBtn: document.getElementById("openHtmlBtn"),
  formNotice: document.getElementById("formNotice"),
  homeNewsList: document.getElementById("homeNewsList"),
  homeNewsCategories: document.getElementById("homeNewsCategories"),
  homeNewsRefresh: document.getElementById("homeNewsRefresh"),
  homeNewsTicker: document.getElementById("homeNewsTicker"),
  homeNewsTickerOpen: document.getElementById("homeNewsTickerOpen"),
  homeNewsTopic: document.getElementById("homeNewsTopic"),
  homeNewsSearchRun: document.getElementById("homeNewsSearchRun"),
  homeNewsSearchStatus: document.getElementById("homeNewsSearchStatus"),
  homeNewsFocusedList: document.getElementById("homeNewsFocusedList"),
  homeDashboardTabs: document.getElementById("homeDashboardTabs"),
  dashboardContextStrip: document.getElementById("dashboardContextStrip"),
  dashboardRangeControls: document.getElementById("dashboardRangeControls"),
  dashboardRangeSelect: document.getElementById("dashboardRangeSelect"),
  dashboardRangeStart: document.getElementById("dashboardRangeStart"),
  dashboardRangeEnd: document.getElementById("dashboardRangeEnd"),
  dashboardRangeSupport: document.getElementById("dashboardRangeSupport"),
  dashboardViewControls: document.getElementById("dashboardViewControls"),
  homeSurfaceGrid: document.getElementById("homeSurfaceGrid"),
  marketDashboardTab: document.getElementById("marketDashboardTab"),
  macroDashboardTab: document.getElementById("macroDashboardTab"),
  quantLabTab: document.getElementById("quantLabTab"),
  quantamentalTab: document.getElementById("quantamentalTab"),
  mlForecastTab: document.getElementById("mlForecastTab"),
  aiPortfolioTab: document.getElementById("aiPortfolioTab"),
  homeHeatmap: document.getElementById("homeHeatmap"),
  homeHeatmapMeta: document.getElementById("homeHeatmapMeta"),
  homeHeatmapRefresh: document.getElementById("homeHeatmapRefresh"),
  marketOverviewMeta: document.getElementById("marketOverviewMeta"),
  marketTapeSurface: document.getElementById("marketTapeSurface"),
  marketSignalSurface: document.getElementById("marketSignalSurface"),
  crossAssetSymbols: document.getElementById("crossAssetSymbols"),
  crossAssetSymbolOpen: document.getElementById("crossAssetSymbolOpen"),
  crossAssetHorizon: document.getElementById("crossAssetHorizon"),
  crossAssetTopic: document.getElementById("crossAssetTopic"),
  crossAssetRun: document.getElementById("crossAssetRun"),
  crossAssetStatus: document.getElementById("crossAssetStatus"),
  crossAssetAnalysisSurface: document.getElementById("crossAssetAnalysisSurface"),
  homeMarketList: document.getElementById("homeMarketList"),
  dataHealthRefresh: document.getElementById("dataHealthRefresh"),
  homeDataHealth: document.getElementById("homeDataHealth"),
  macroRefresh: document.getElementById("macroRefresh"),
  macroBriefGenerate: document.getElementById("macroBriefGenerate"),
  macroReportExport: document.getElementById("macroReportExport"),
  macroLoadStatus: document.getElementById("macroLoadStatus"),
  macroOverviewSurface: document.getElementById("macroOverviewSurface"),
  macroCoverageSurface: document.getElementById("macroCoverageSurface"),
  macroProviderHealthSurface: document.getElementById("macroProviderHealthSurface"),
  macroIndicatorTable: document.getElementById("macroIndicatorTable"),
  macroChartSurface: document.getElementById("macroChartSurface"),
  macroInterestRatesSurface: document.getElementById("macroInterestRatesSurface"),
  macroInflationSurface: document.getElementById("macroInflationSurface"),
  macroGrowthLaborSurface: document.getElementById("macroGrowthLaborSurface"),
  macroHousingConsumerSurface: document.getElementById("macroHousingConsumerSurface"),
  macroYieldCurveSurface: document.getElementById("macroYieldCurveSurface"),
  macroLiquidityCreditSurface: document.getElementById("macroLiquidityCreditSurface"),
  macroFinancialConditionsSurface: document.getElementById("macroFinancialConditionsSurface"),
  macroFxDollarSurface: document.getElementById("macroFxDollarSurface"),
  macroCommoditiesSurface: document.getElementById("macroCommoditiesSurface"),
  macroRegimeSurface: document.getElementById("macroRegimeSurface"),
  macroAssetImpactSurface: document.getElementById("macroAssetImpactSurface"),
  macroPortfolioHintsSurface: document.getElementById("macroPortfolioHintsSurface"),
  macroBriefSurface: document.getElementById("macroBriefSurface"),
  macroDataQualitySurface: document.getElementById("macroDataQualitySurface"),
  macroSeriesSearchInput: document.getElementById("macroSeriesSearchInput"),
  macroSeriesSearchRun: document.getElementById("macroSeriesSearchRun"),
  macroSeriesSearchResults: document.getElementById("macroSeriesSearchResults"),
  macroSeriesDetailSurface: document.getElementById("macroSeriesDetailSurface"),
  macroProviderFilter: document.getElementById("macroProviderFilter"),
  macroCategoryFilter: document.getElementById("macroCategoryFilter"),
  macroCompareSurface: document.getElementById("macroCompareSurface"),
  macroScenarioSurface: document.getElementById("macroScenarioSurface"),
  macroScenarioResult: document.getElementById("macroScenarioResult"),
  macroResearchPreviewSurface: document.getElementById("macroResearchPreviewSurface"),
  macroResearchTicker: document.getElementById("macroResearchTicker"),
  macroResearchPreviewRun: document.getElementById("macroResearchPreviewRun"),
  macroResearchPreviewResult: document.getElementById("macroResearchPreviewResult"),
  assetDetailTicker: document.getElementById("assetDetailTicker"),
  assetDetailTickerOpen: document.getElementById("assetDetailTickerOpen"),
  assetDetailRange: document.getElementById("assetDetailRange"),
  assetDetailStartDate: document.getElementById("assetDetailStartDate"),
  assetDetailEndDate: document.getElementById("assetDetailEndDate"),
  assetDetailView: document.getElementById("assetDetailView"),
  assetDetailBenchmark: document.getElementById("assetDetailBenchmark"),
  assetDetailBenchmarkOpen: document.getElementById("assetDetailBenchmarkOpen"),
  assetDetailBenchmarkCompare: document.getElementById("assetDetailBenchmarkCompare"),
  assetDetailLoad: document.getElementById("assetDetailLoad"),
  assetDetailSurface: document.getElementById("assetDetailSurface"),
  backtestTicker: document.getElementById("backtestTicker"),
  backtestUniverseOpen: document.getElementById("backtestUniverseOpen"),
  backtestUniverseChips: document.getElementById("backtestUniverseChips"),
  backtestStrategy: document.getElementById("backtestStrategy"),
  backtestStrategyRegistry: document.getElementById("backtestStrategyRegistry"),
  backtestBenchmark: document.getElementById("backtestBenchmark"),
  backtestBenchmarkOpen: document.getElementById("backtestBenchmarkOpen"),
  backtestBenchmarkCompare: document.getElementById("backtestBenchmarkCompare"),
  backtestStartDate: document.getElementById("backtestStartDate"),
  backtestEndDate: document.getElementById("backtestEndDate"),
  backtestLookbackDays: document.getElementById("backtestLookbackDays"),
  backtestShortWindow: document.getElementById("backtestShortWindow"),
  backtestLongWindow: document.getElementById("backtestLongWindow"),
  backtestTopN: document.getElementById("backtestTopN"),
  backtestRebalanceEvery: document.getElementById("backtestRebalanceEvery"),
  backtestFreshnessProfile: document.getElementById("backtestFreshnessProfile"),
  backtestRequireFresh: document.getElementById("backtestRequireFresh"),
  backtestUseResearchScore: document.getElementById("backtestUseResearchScore"),
  backtestCostBps: document.getElementById("backtestCostBps"),
  backtestSlippageBps: document.getElementById("backtestSlippageBps"),
  backtestRun: document.getElementById("backtestRun"),
  backtestSurface: document.getElementById("backtestSurface"),
  quantFeatureRun: document.getElementById("quantFeatureRun"),
  quantFeatureSurface: document.getElementById("quantFeatureSurface"),
  quantSignalRun: document.getElementById("quantSignalRun"),
  quantSignalSurface: document.getElementById("quantSignalSurface"),
  quantStrategyRefresh: document.getElementById("quantStrategyRefresh"),
  quantStrategyNewDraft: document.getElementById("quantStrategyNewDraft"),
  quantStrategyGenerate: document.getElementById("quantStrategyGenerate"),
  quantStrategyDryRun: document.getElementById("quantStrategyDryRun"),
  quantStrategySave: document.getElementById("quantStrategySave"),
  quantStrategyDelete: document.getElementById("quantStrategyDelete"),
  strategyPromptInput: document.getElementById("strategyPromptInput"),
  strategyDefinitionJson: document.getElementById("strategyDefinitionJson"),
  strategyPromptReviewSurface: document.getElementById("strategyPromptReviewSurface"),
  quantStrategySurface: document.getElementById("quantStrategySurface"),
  quantStrategyResultSurface: document.getElementById("quantStrategyResultSurface"),
  quantRunHistoryRefresh: document.getElementById("quantRunHistoryRefresh"),
  quantExportStorageReport: document.getElementById("quantExportStorageReport"),
  quantCrossRunCleanupPreview: document.getElementById("quantCrossRunCleanupPreview"),
  quantRunHistorySurface: document.getElementById("quantRunHistorySurface"),
  forecastTicker: document.getElementById("forecastTicker"),
  forecastTickerOpen: document.getElementById("forecastTickerOpen"),
  forecastBenchmark: document.getElementById("forecastBenchmark"),
  forecastBenchmarkOpen: document.getElementById("forecastBenchmarkOpen"),
  forecastStartDate: document.getElementById("forecastStartDate"),
  forecastEndDate: document.getElementById("forecastEndDate"),
  forecastHorizon: document.getElementById("forecastHorizon"),
  forecastTargetType: document.getElementById("forecastTargetType"),
  forecastModel: document.getElementById("forecastModel"),
  forecastValidation: document.getElementById("forecastValidation"),
  forecastIncludeMacro: document.getElementById("forecastIncludeMacro"),
  forecastIncludeCrossAsset: document.getElementById("forecastIncludeCrossAsset"),
  forecastPreviewDataset: document.getElementById("forecastPreviewDataset"),
  forecastHydrateDataset: document.getElementById("forecastHydrateDataset"),
  forecastBuildFeatures: document.getElementById("forecastBuildFeatures"),
  forecastRunTrain: document.getElementById("forecastRunTrain"),
  forecastQueueJob: document.getElementById("forecastQueueJob"),
  forecastGenerateAi: document.getElementById("forecastGenerateAi"),
  forecastGenerateProviderAi: document.getElementById("forecastGenerateProviderAi"),
  forecastDatasetSurface: document.getElementById("forecastDatasetSurface"),
  forecastFeatureSurface: document.getElementById("forecastFeatureSurface"),
  forecastLeakageSurface: document.getElementById("forecastLeakageSurface"),
  forecastResultSurface: document.getElementById("forecastResultSurface"),
  forecastSignalSurface: document.getElementById("forecastSignalSurface"),
  forecastSignalQualitySurface: document.getElementById("forecastSignalQualitySurface"),
  forecastVizSurface: document.getElementById("forecastVizSurface"),
  forecastBacktestSurface: document.getElementById("forecastBacktestSurface"),
  forecastEvaluationSurface: document.getElementById("forecastEvaluationSurface"),
  forecastExplainSurface: document.getElementById("forecastExplainSurface"),
  forecastAiSurface: document.getElementById("forecastAiSurface"),
  forecastAiProviderCheck: document.getElementById("forecastAiProviderCheck"),
  forecastAiProviderSurface: document.getElementById("forecastAiProviderSurface"),
  forecastDriftRefresh: document.getElementById("forecastDriftRefresh"),
  forecastDriftSurface: document.getElementById("forecastDriftSurface"),
  forecastModelComparisonRefresh: document.getElementById("forecastModelComparisonRefresh"),
  forecastModelComparisonSurface: document.getElementById("forecastModelComparisonSurface"),
  forecastJobsRefresh: document.getElementById("forecastJobsRefresh"),
  forecastJobsSurface: document.getElementById("forecastJobsSurface"),
  forecastHistoryRefresh: document.getElementById("forecastHistoryRefresh"),
  forecastHistorySurface: document.getElementById("forecastHistorySurface"),
  forecastRegistryRefresh: document.getElementById("forecastRegistryRefresh"),
  forecastRegistrySurface: document.getElementById("forecastRegistrySurface"),
  forecastDetailModal: document.getElementById("forecastDetailModal"),
  forecastDetailClose: document.getElementById("forecastDetailClose"),
  forecastDetailTitle: document.getElementById("forecastDetailTitle"),
  forecastDetailBody: document.getElementById("forecastDetailBody"),
  portfolioTickers: document.getElementById("portfolioTickers"),
  portfolioUniverseOpen: document.getElementById("portfolioUniverseOpen"),
  portfolioUniverseChips: document.getElementById("portfolioUniverseChips"),
  portfolioMethod: document.getElementById("portfolioMethod"),
  portfolioBenchmark: document.getElementById("portfolioBenchmark"),
  portfolioBenchmarkOpen: document.getElementById("portfolioBenchmarkOpen"),
  portfolioCovarianceMethod: document.getElementById("portfolioCovarianceMethod"),
  portfolioShrinkageAlpha: document.getElementById("portfolioShrinkageAlpha"),
  portfolioStartDate: document.getElementById("portfolioStartDate"),
  portfolioEndDate: document.getElementById("portfolioEndDate"),
  portfolioLookbackDays: document.getElementById("portfolioLookbackDays"),
  portfolioMaxWeight: document.getElementById("portfolioMaxWeight"),
  portfolioSyncBacktest: document.getElementById("portfolioSyncBacktest"),
  portfolioOptimize: document.getElementById("portfolioOptimize"),
  portfolioSurface: document.getElementById("portfolioSurface"),
  aiPortfolioOverviewSurface: document.getElementById("aiPortfolioOverviewSurface"),
  aiPortfolioOpsRefresh: document.getElementById("aiPortfolioOpsRefresh"),
  aiPortfolioOpsSurface: document.getElementById("aiPortfolioOpsSurface"),
  aiPortfolioCoverageSurface: document.getElementById("aiPortfolioCoverageSurface"),
  aiPortfolioSnapshotTimelineSurface: document.getElementById("aiPortfolioSnapshotTimelineSurface"),
  aiPortfolioRefreshPolicies: document.getElementById("aiPortfolioRefreshPolicies"),
  aiPortfolioHydrateData: document.getElementById("aiPortfolioHydrateData"),
  aiPortfolioRetryMissing: document.getElementById("aiPortfolioRetryMissing"),
  aiPortfolioSnapshotJob: document.getElementById("aiPortfolioSnapshotJob"),
  aiPortfolioSecRefresh: document.getElementById("aiPortfolioSecRefresh"),
  aiPortfolioPolicyListSurface: document.getElementById("aiPortfolioPolicyListSurface"),
  aiPortfolioRecommendationDiffSurface: document.getElementById("aiPortfolioRecommendationDiffSurface"),
  aiPortfolioOperationsSurface: document.getElementById("aiPortfolioOperationsSurface"),
  aiPortfolioInvestmentTypes: document.getElementById("aiPortfolioInvestmentTypes"),
  aiPortfolioName: document.getElementById("aiPortfolioName"),
  aiPortfolioUniverse: document.getElementById("aiPortfolioUniverse"),
  aiPortfolioCustomUniverseWrap: document.getElementById("aiPortfolioCustomUniverseWrap"),
  aiPortfolioCustomUniverse: document.getElementById("aiPortfolioCustomUniverse"),
  aiPortfolioCustomUniverseOpen: document.getElementById("aiPortfolioCustomUniverseOpen"),
  aiPortfolioCustomUniverseChips: document.getElementById("aiPortfolioCustomUniverseChips"),
  aiPortfolioUniverseStatus: document.getElementById("aiPortfolioUniverseStatus"),
  aiPortfolioInitialCapital: document.getElementById("aiPortfolioInitialCapital"),
  aiPortfolioMonthlyContribution: document.getElementById("aiPortfolioMonthlyContribution"),
  aiPortfolioTargetReturn: document.getElementById("aiPortfolioTargetReturn"),
  aiPortfolioBenchmark: document.getElementById("aiPortfolioBenchmark"),
  aiPortfolioBenchmarkOpen: document.getElementById("aiPortfolioBenchmarkOpen"),
  aiPortfolioAutomation: document.getElementById("aiPortfolioAutomation"),
  aiPortfolioAdvancedToggle: document.getElementById("aiPortfolioAdvancedToggle"),
  aiPortfolioPolicyForm: document.getElementById("aiPortfolioPolicyForm"),
  aiPortfolioTargetVolatility: document.getElementById("aiPortfolioTargetVolatility"),
  aiPortfolioMaxDrawdown: document.getElementById("aiPortfolioMaxDrawdown"),
  aiPortfolioMinCash: document.getElementById("aiPortfolioMinCash"),
  aiPortfolioMaxSingle: document.getElementById("aiPortfolioMaxSingle"),
  aiPortfolioMaxSector: document.getElementById("aiPortfolioMaxSector"),
  aiPortfolioRebalanceFrequency: document.getElementById("aiPortfolioRebalanceFrequency"),
  aiPortfolioDriftThreshold: document.getElementById("aiPortfolioDriftThreshold"),
  aiPortfolioMaxTurnover: document.getElementById("aiPortfolioMaxTurnover"),
  aiPortfolioOptimization: document.getElementById("aiPortfolioOptimization"),
  aiPortfolioLookbackMonths: document.getElementById("aiPortfolioLookbackMonths"),
  aiPortfolioRiskModel: document.getElementById("aiPortfolioRiskModel"),
  aiPortfolioExpectedReturn: document.getElementById("aiPortfolioExpectedReturn"),
  aiPortfolioEquityRange: document.getElementById("aiPortfolioEquityRange"),
  aiPortfolioBondRange: document.getElementById("aiPortfolioBondRange"),
  aiPortfolioCashRange: document.getElementById("aiPortfolioCashRange"),
  aiPortfolioAlternativeRange: document.getElementById("aiPortfolioAlternativeRange"),
  aiPortfolioGenerate: document.getElementById("aiPortfolioGenerate"),
  aiPortfolioGenerateQuick: document.getElementById("aiPortfolioGenerateQuick"),
  aiPortfolioCheckRebalanceQuick: document.getElementById("aiPortfolioCheckRebalanceQuick"),
  aiPortfolioReportQuick: document.getElementById("aiPortfolioReportQuick"),
  aiPortfolioRecommendationSurface: document.getElementById("aiPortfolioRecommendationSurface"),
  aiPortfolioPerformanceSurface: document.getElementById("aiPortfolioPerformanceSurface"),
  aiPortfolioComplianceSurface: document.getElementById("aiPortfolioComplianceSurface"),
  aiPortfolioCurrentWeights: document.getElementById("aiPortfolioCurrentWeights"),
  aiPortfolioCheckRebalance: document.getElementById("aiPortfolioCheckRebalance"),
  aiPortfolioApproveRebalance: document.getElementById("aiPortfolioApproveRebalance"),
  aiPortfolioRejectRebalance: document.getElementById("aiPortfolioRejectRebalance"),
  aiPortfolioDeferRebalance: document.getElementById("aiPortfolioDeferRebalance"),
  aiPortfolioRebalanceSurface: document.getElementById("aiPortfolioRebalanceSurface"),
  aiPortfolioReportWeekly: document.getElementById("aiPortfolioReportWeekly"),
  aiPortfolioReportMonthly: document.getElementById("aiPortfolioReportMonthly"),
  aiPortfolioReportRebalance: document.getElementById("aiPortfolioReportRebalance"),
  aiPortfolioReportsSurface: document.getElementById("aiPortfolioReportsSurface"),
  aiPortfolioHistorySurface: document.getElementById("aiPortfolioHistorySurface"),
  quantamentalTicker: document.getElementById("quantamentalTicker"),
  quantamentalTickerOpen: document.getElementById("quantamentalTickerOpen"),
  quantamentalMarket: document.getElementById("quantamentalMarket"),
  quantamentalPeriod: document.getElementById("quantamentalPeriod"),
  quantamentalYears: document.getElementById("quantamentalYears"),
  quantamentalLookback: document.getElementById("quantamentalLookback"),
  quantamentalStyle: document.getElementById("quantamentalStyle"),
  quantamentalAiModel: document.getElementById("quantamentalAiModel"),
  quantamentalAiModelStatus: document.getElementById("quantamentalAiModelStatus"),
  quantamentalAnalyze: document.getElementById("quantamentalAnalyze"),
  quantamentalStatus: document.getElementById("quantamentalStatus"),
  quantamentalCompanySurface: document.getElementById("quantamentalCompanySurface"),
  quantamentalSignalSurface: document.getElementById("quantamentalSignalSurface"),
  quantamentalScoreSurface: document.getElementById("quantamentalScoreSurface"),
  quantamentalFactorSurface: document.getElementById("quantamentalFactorSurface"),
  quantamentalMainSurface: document.getElementById("quantamentalMainSurface"),
  quantamentalAiRefresh: document.getElementById("quantamentalAiRefresh"),
  quantamentalDataQualitySurface: document.getElementById("quantamentalDataQualitySurface"),
  quantamentalCompareTickers: document.getElementById("quantamentalCompareTickers"),
  quantamentalCompareRun: document.getElementById("quantamentalCompareRun"),
  quantamentalCompareSurface: document.getElementById("quantamentalCompareSurface"),
  quantamentalExpandPeers: document.getElementById("quantamentalExpandPeers"),
  quantamentalPeerLimit: document.getElementById("quantamentalPeerLimit"),
  quantamentalWatchlistName: document.getElementById("quantamentalWatchlistName"),
  quantamentalWatchlistSelect: document.getElementById("quantamentalWatchlistSelect"),
  quantamentalWatchlistSave: document.getElementById("quantamentalWatchlistSave"),
  quantamentalWatchlistLoad: document.getElementById("quantamentalWatchlistLoad"),
  quantamentalCompareCsv: document.getElementById("quantamentalCompareCsv"),
  quantamentalScreenRun: document.getElementById("quantamentalScreenRun"),
  quantamentalScreenSurface: document.getElementById("quantamentalScreenSurface"),
  quantamentalScreenStatus: document.getElementById("quantamentalScreenStatus"),
  quantamentalScoreThreshold: document.getElementById("quantamentalScoreThreshold"),
  quantamentalScoreMetric: document.getElementById("quantamentalScoreMetric"),
  quantamentalScoreScreenLimit: document.getElementById("quantamentalScoreScreenLimit"),
  quantamentalScoreScreenRun: document.getElementById("quantamentalScoreScreenRun"),
  quantamentalScoreScreenSurface: document.getElementById("quantamentalScoreScreenSurface"),
  quantamentalScoreScreenStatus: document.getElementById("quantamentalScoreScreenStatus"),
  tvOverviewMeta: document.getElementById("tvOverviewMeta"),
  tvOverviewWidget: document.getElementById("tvOverviewWidget"),
  tvOverviewFallback: document.getElementById("tvOverviewFallback"),
  tvChartSource: document.getElementById("tvChartSource"),
  tvChartSymbol: document.getElementById("tvChartSymbol"),
  tvChartInterval: document.getElementById("tvChartInterval"),
  tvChartCompare: document.getElementById("tvChartCompare"),
  tvChartApply: document.getElementById("tvChartApply"),
  tvHeatmapWidget: document.getElementById("tvHeatmapWidget"),
  tvHeatmapFallback: document.getElementById("tvHeatmapFallback"),
  symbolPickerModal: document.getElementById("symbolPickerModal"),
  symbolPickerTitle: document.getElementById("symbolPickerTitle"),
  symbolPickerDescription: document.getElementById("symbolPickerDescription"),
  symbolPickerClose: document.getElementById("symbolPickerClose"),
  symbolPickerSearch: document.getElementById("symbolPickerSearch"),
  symbolPickerTabs: document.getElementById("symbolPickerTabs"),
  symbolPickerCountry: document.getElementById("symbolPickerCountry"),
  symbolPickerSector: document.getElementById("symbolPickerSector"),
  symbolPickerSummary: document.getElementById("symbolPickerSummary"),
  symbolPickerSelected: document.getElementById("symbolPickerSelected"),
  symbolPickerList: document.getElementById("symbolPickerList"),
  symbolPickerAddFiltered: document.getElementById("symbolPickerAddFiltered"),
  symbolPickerRemoveFiltered: document.getElementById("symbolPickerRemoveFiltered"),
  symbolPickerClear: document.getElementById("symbolPickerClear"),
  symbolPickerApply: document.getElementById("symbolPickerApply"),
};

// Shared state
const state = {
  config: null,
  lastResponse: null,
  lastCollection: null,
  lastRequest: null,
  activeRequest: null,
  evidenceRaw: [],
  preflight: null,
  preflightTimer: null,
  preflightRequest: null,
  watchlistTimer: null,
  watchlistRequest: null,
  watchlistItems: [],
  pendingTimer: null,
  stageTimer: null,
  stageIndex: 0,
  startedAt: null,
  streamStartedAt: null,
  streamHasPartial: false,
  historyExpanded: false,
  dashboardLoaded: false,
  marketOverviewLoaded: false,
  marketLoaded: false,
  dataHealthLoaded: false,
  dashboardHeatmapLoaded: false,
  tradingViewInitialized: false,
  dashboardNewsItems: [],
  focusedNewsItems: [],
  dashboardNewsCategory: "all",
  crossAssetAnalysis: null,
  marketOverview: null,
  dashboardMarketItems: [],
  dashboardDecisionCardsByTab: {},
  dashboardDecisionCardsLoaded: false,
  dashboardDecisionCardsRequest: null,
  activeDashboardTab: "market",
  outputLanguage: safeReadStoredValue(STORAGE.outputLanguage, "ko"),
  tvChartSettings: safeReadStoredJson(STORAGE.tvChart, TV_CHART_DEFAULTS),
  dashboardPanelViewByTab: initDashboardPanelViews(),
  globalRange: initGlobalRangeFromLocation(),
  globalRangeNotice: "",
  globalQuality: null,
  macroLoaded: false,
  macroLoading: false,
  macroOverview: null,
  macroDashboard: null,
  macroProviderHealth: null,
  macroScenario: null,
  macroResearchContext: null,
  macroPortfolioHint: null,
  macroDataQuality: null,
  macroRefreshStatus: null,
  macroBrief: null,
  macroSeriesList: null,
  macroSeriesSearch: null,
  macroSeriesDetail: null,
  lastBacktestRequest: null,
  lastQuantBacktestRequest: null,
  lastBacktestResult: null,
  lastFeatureResult: null,
  lastSignalResult: null,
  lastUniverseResolution: null,
  lastStrategyGeneration: null,
  quantStrategiesLoaded: false,
  quantStrategyItems: [],
  activeStrategyId: "",
  symbolPickerType: "all",
  symbolPickerTarget: null,
  symbolPickerFilteredSymbols: [],
  quantRunHistoryLoaded: false,
  quantRunCompareSelection: [],
  lastCrossRunExportCleanupPreview: null,
  forecastLoaded: false,
  forecastModelsLoaded: false,
  forecastModels: [],
  lastForecastPayload: null,
  forecastJobPollTimer: null,
  chartTooltipBound: false,
  aiPortfolioLoaded: false,
  aiPortfolioOpsLoaded: false,
  aiPortfolioDashboard: null,
  aiPortfolioDashboardFetchedAt: 0,
  aiPortfolioDashboardUrl: "",
  aiPortfolioDashboardRequest: null,
  aiPortfolioDashboardRequestUrl: "",
  aiPortfolioDashboardCacheVersion: 0,
  aiPortfolioInvestmentTypes: [],
  aiPortfolioUniverses: [],
  aiPortfolioPolicies: [],
  aiPortfolioOperations: [],
  aiPortfolioSelectedType: "balanced_growth",
  aiPortfolioPolicy: null,
  aiPortfolioRecommendation: null,
  aiPortfolioSignal: null,
  quantamentalLoaded: false,
  quantamentalLoading: false,
  quantamentalAnalysis: null,
  quantamentalComparison: null,
  quantamentalCompareWatchlists: [],
  quantamentalAiModels: [],
  quantamentalLastSnapshotId: "",
  quantamentalActiveTab: "overview",
  quantamentalScreen: null,
  quantamentalScreenLoaded: false,
  quantamentalScreenLoading: false,
  quantamentalScoreScreen: null,
  quantamentalScoreScreenLoading: false,
};

function symbolList(text) {
  return String(text || "").trim().split(/\s+/).filter(Boolean);
}

function symbolNameList(text) {
  return String(text || "")
    .trim()
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [symbol, ...nameParts] = line.split("|");
      return [normalizeTickerToken(symbol), nameParts.join("|").trim()];
    })
    .filter(([symbol, name]) => symbol && name);
}

const US_LARGE_CAP_SYMBOLS = symbolList(`
  MSFT AAPL NVDA AVGO ORCL CRM AMD CSCO ACN IBM INTU NOW PANW PLTR SNPS CRWD FTNT ADBE ADP ROP
  CDNS PTC FICO TXN QCOM MU ADI AMAT LRCX KLAC INTC MCHP NXPI ANET DELL WDC STX GOOGL META NFLX DIS
  TMUS VZ T CMCSA EA TTWO LYV WBD CHTR AMZN TSLA HD MCD LOW SBUX BKNG RCL CCL ABNB MAR HLT TJX ROST
  LULU NKE ORLY AZO GM F CMG YUM DRI EBAY DASH WMT COST PG KO PEP PM MO CL KMB MDLZ MNST KDP EL TGT
  DG KR ADM GIS HSY SYY KHC STZ BRK-B JPM V MA BAC WFC C AXP GS MS BLK SCHW SPGI ICE CME COF USB PNC
  TFC CB PGR TRV AON AFL WELL AJG ALL KKR BX LLY JNJ UNH ABBV MRK TMO ABT ISRG DHR PFE AMGN MDT BSX
  SYK CVS CI HUM BMY GILD REGN VRTX MCK COR HCA ELV BDX EW IQV ZTS GE RTX CAT DE BA LMT HON UPS ETN
  PH MMM UNP CSX NSC WM RSG ITW EMR PCAR CMI FDX JCI TT AXON GEV CARR XOM CVX COP EOG SLB OXY MPC
  PSX VLO KMI WMB HAL BKR FANG OKE DVN CTRA NEE SO
`);

const US_SYMBOL_NAMES = Object.fromEntries(symbolNameList(`
AAPL|Apple Inc.
ABBV|AbbVie Inc.
ABNB|Airbnb, Inc.
ABT|Abbott Laboratories
ACN|Accenture plc
ADBE|Adobe Inc.
ADI|Analog Devices, Inc.
ADM|Archer-Daniels-Midland Company
ADP|Automatic Data Processing, Inc.
AFL|Aflac Incorporated
AJG|Arthur J. Gallagher & Co.
ALL|The Allstate Corporation
AMAT|Applied Materials, Inc.
AMD|Advanced Micro Devices, Inc.
AMGN|Amgen Inc.
AMZN|Amazon.com, Inc.
ANET|Arista Networks, Inc.
AON|Aon plc
AVGO|Broadcom Inc.
AXON|Axon Enterprise, Inc.
AXP|American Express Company
AZO|AutoZone, Inc.
BA|The Boeing Company
BAC|Bank of America Corporation
BDX|Becton, Dickinson and Company
BKNG|Booking Holdings Inc.
BKR|Baker Hughes Company
BLK|BlackRock, Inc.
BMY|Bristol-Myers Squibb Company
BRK-B|Berkshire Hathaway Inc. Class B
BSX|Boston Scientific Corporation
BX|Blackstone Inc.
C|Citigroup Inc.
CARR|Carrier Global Corporation
CAT|Caterpillar Inc.
CB|Chubb Limited
CCL|Carnival Corporation & plc
CDNS|Cadence Design Systems, Inc.
CHTR|Charter Communications, Inc.
CI|The Cigna Group
CL|Colgate-Palmolive Company
CMCSA|Comcast Corporation
CME|CME Group Inc.
CMG|Chipotle Mexican Grill, Inc.
CMI|Cummins Inc.
COF|Capital One Financial Corporation
COP|ConocoPhillips
COR|Cencora, Inc.
COST|Costco Wholesale Corporation
CRM|Salesforce, Inc.
CRWD|CrowdStrike Holdings, Inc.
CSCO|Cisco Systems, Inc.
CSX|CSX Corporation
CTRA|Coterra Energy Inc.
CVS|CVS Health Corporation
CVX|Chevron Corporation
DASH|DoorDash, Inc.
DE|Deere & Company
DELL|Dell Technologies Inc.
DG|Dollar General Corporation
DHR|Danaher Corporation
DIS|The Walt Disney Company
DRI|Darden Restaurants, Inc.
DVN|Devon Energy Corporation
EA|Electronic Arts Inc.
EBAY|eBay Inc.
EL|The Estée Lauder Companies Inc.
ELV|Elevance Health, Inc.
EMR|Emerson Electric Co.
EOG|EOG Resources, Inc.
ETN|Eaton Corporation plc
EW|Edwards Lifesciences Corporation
F|Ford Motor Company
FANG|Diamondback Energy, Inc.
FDX|FedEx Corporation
FICO|Fair Isaac Corporation
FTNT|Fortinet, Inc.
GE|GE Aerospace
GEV|GE Vernova Inc.
GILD|Gilead Sciences, Inc.
GIS|General Mills, Inc.
GM|General Motors Company
GOOGL|Alphabet Inc.
GS|The Goldman Sachs Group, Inc.
HAL|Halliburton Company
HCA|HCA Healthcare, Inc.
HD|The Home Depot, Inc.
HLT|Hilton Worldwide Holdings Inc.
HON|Honeywell International Inc.
HSY|The Hershey Company
HUM|Humana Inc.
IBM|International Business Machines Corporation
ICE|Intercontinental Exchange, Inc.
INTC|Intel Corporation
INTU|Intuit Inc.
IQV|IQVIA Holdings Inc.
ISRG|Intuitive Surgical, Inc.
ITW|Illinois Tool Works Inc.
JCI|Johnson Controls International plc
JNJ|Johnson & Johnson
JPM|JPMorgan Chase & Co.
KDP|Keurig Dr Pepper Inc.
KHC|The Kraft Heinz Company
KKR|KKR & Co. Inc.
KLAC|KLA Corporation
KMB|Kimberly-Clark Corporation
KMI|Kinder Morgan, Inc.
KO|The Coca-Cola Company
KR|The Kroger Co.
LLY|Eli Lilly and Company
LMT|Lockheed Martin Corporation
LOW|Lowe's Companies, Inc.
LRCX|Lam Research Corporation
LULU|lululemon athletica inc.
LYV|Live Nation Entertainment, Inc.
MA|Mastercard Incorporated
MAR|Marriott International, Inc.
MCD|McDonald's Corporation
MCHP|Microchip Technology Incorporated
MCK|McKesson Corporation
MDLZ|Mondelez International, Inc.
MDT|Medtronic plc
META|Meta Platforms, Inc.
WELL|Welltower Inc.
MMM|3M Company
MNST|Monster Beverage Corporation
MO|Altria Group, Inc.
MPC|Marathon Petroleum Corporation
MRK|Merck & Co., Inc.
MS|Morgan Stanley
MSFT|Microsoft Corporation
MU|Micron Technology, Inc.
NEE|NextEra Energy, Inc.
NFLX|Netflix, Inc.
NKE|NIKE, Inc.
NOW|ServiceNow, Inc.
NSC|Norfolk Southern Corporation
NVDA|NVIDIA Corporation
NXPI|NXP Semiconductors N.V.
OKE|ONEOK, Inc.
ORCL|Oracle Corporation
ORLY|O'Reilly Automotive, Inc.
OXY|Occidental Petroleum Corporation
PANW|Palo Alto Networks, Inc.
PCAR|PACCAR Inc
PEP|PepsiCo, Inc.
PFE|Pfizer Inc.
PG|The Procter & Gamble Company
PGR|The Progressive Corporation
PH|Parker-Hannifin Corporation
PLTR|Palantir Technologies Inc.
PM|Philip Morris International Inc.
PNC|The PNC Financial Services Group, Inc.
PSX|Phillips 66
PTC|PTC Inc.
QCOM|QUALCOMM Incorporated
RCL|Royal Caribbean Cruises Ltd.
REGN|Regeneron Pharmaceuticals, Inc.
ROP|Roper Technologies, Inc.
ROST|Ross Stores, Inc.
RSG|Republic Services, Inc.
RTX|RTX Corporation
SBUX|Starbucks Corporation
SCHW|The Charles Schwab Corporation
SLB|SLB N.V.
SNPS|Synopsys, Inc.
SO|The Southern Company
SPGI|S&P Global Inc.
STX|Seagate Technology Holdings plc
STZ|Constellation Brands, Inc.
SYK|Stryker Corporation
SYY|Sysco Corporation
T|AT&T Inc.
TFC|Truist Financial Corporation
TGT|Target Corporation
TJX|The TJX Companies, Inc.
TMO|Thermo Fisher Scientific Inc.
TMUS|T-Mobile US, Inc.
TRV|The Travelers Companies, Inc.
TSLA|Tesla, Inc.
TT|Trane Technologies plc
TTWO|Take-Two Interactive Software, Inc.
TXN|Texas Instruments Incorporated
UNH|UnitedHealth Group Incorporated
UNP|Union Pacific Corporation
UPS|United Parcel Service, Inc.
USB|U.S. Bancorp
V|Visa Inc.
VLO|Valero Energy Corporation
VRTX|Vertex Pharmaceuticals Incorporated
VZ|Verizon Communications Inc.
WBD|Warner Bros. Discovery, Inc.
WDC|Western Digital Corporation
WFC|Wells Fargo & Company
WM|Waste Management, Inc.
WMB|The Williams Companies, Inc.
WMT|Walmart Inc.
XOM|Exxon Mobil Corporation
YUM|Yum! Brands, Inc.
ZTS|Zoetis Inc.
`));

const ETF_CORE_SYMBOLS = symbolList(`
  SPY IVV VOO SPLG RSP QQQ QQQM DIA IWM IJR IJH VTI ITOT SCHB VT ACWI VXUS IXUS VEA IEFA VWO IEMG
  EFA EEM EWJ EWU EWG EWC EWA EWH EWT EWY MCHI FXI INDA EWW EWZ XLK XLF XLV XLY XLP XLE XLI XLU XLB
  XLRE XLC VGT VFH VHT VCR VDC VDE VIS VPU VAW VNQ IYR SMH SOXX XBI IBB KRE XRT ITB TAN ICLN URA
  XOP AGG BND BSV BIV BLV IEF SHY TLT GOVT TIP VTIP LQD HYG JNK MUB EMB BIL SGOV SHV ICSH MBB GLD
  IAU SLV USO UNG DBA DBC CPER UUP
`);

const ETF_SYMBOL_NAMES = Object.fromEntries(symbolNameList(`
SPY|State Street SPDR S&P 500 ETF Trust
IVV|iShares Core S&P 500 ETF
VOO|Vanguard S&P 500 ETF
SPLG|State Street SPDR Portfolio S&P 500 ETF
RSP|Invesco S&P 500 Equal Weight ETF
QQQ|Invesco QQQ Trust
QQQM|Invesco NASDAQ 100 ETF
DIA|State Street SPDR Dow Jones Industrial Average ETF Trust
IWM|iShares Russell 2000 ETF
IJR|iShares Core S&P Small-Cap ETF
IJH|iShares Core S&P Mid-Cap ETF
VTI|Vanguard Total Stock Market ETF
ITOT|iShares Core S&P Total U.S. Stock Market ETF
SCHB|Schwab U.S. Broad Market ETF
VT|Vanguard Total World Stock ETF
ACWI|iShares MSCI ACWI ETF
VXUS|Vanguard Total International Stock ETF
IXUS|iShares Core MSCI Total International Stock ETF
VEA|Vanguard FTSE Developed Markets ETF
IEFA|iShares Core MSCI EAFE ETF
VWO|Vanguard Emerging Markets Stock ETF
IEMG|iShares Core MSCI Emerging Markets ETF
EFA|iShares MSCI EAFE ETF
EEM|iShares MSCI Emerging Markets ETF
EWJ|iShares MSCI Japan ETF
EWU|iShares MSCI United Kingdom ETF
EWG|iShares MSCI Germany ETF
EWC|iShares MSCI Canada ETF
EWA|iShares MSCI Australia ETF
EWH|iShares MSCI Hong Kong ETF
EWT|iShares MSCI Taiwan ETF
EWY|iShares MSCI South Korea ETF
MCHI|iShares MSCI China ETF
FXI|iShares China Large-Cap ETF
INDA|iShares MSCI India ETF
EWW|iShares MSCI Mexico ETF
EWZ|iShares MSCI Brazil ETF
XLK|Technology Select Sector SPDR ETF
XLF|Financial Select Sector SPDR ETF
XLV|Health Care Select Sector SPDR ETF
XLY|Consumer Discretionary Select Sector SPDR ETF
XLP|Consumer Staples Select Sector SPDR ETF
XLE|Energy Select Sector SPDR ETF
XLI|Industrial Select Sector SPDR ETF
XLU|Utilities Select Sector SPDR ETF
XLB|Materials Select Sector SPDR ETF
XLRE|Real Estate Select Sector SPDR ETF
XLC|Communication Services Select Sector SPDR ETF
VGT|Vanguard Information Technology ETF
VFH|Vanguard Financials ETF
VHT|Vanguard Health Care ETF
VCR|Vanguard Consumer Discretionary ETF
VDC|Vanguard Consumer Staples ETF
VDE|Vanguard Energy ETF
VIS|Vanguard Industrials ETF
VPU|Vanguard Utilities ETF
VAW|Vanguard Materials ETF
VNQ|Vanguard Real Estate ETF
IYR|iShares U.S. Real Estate ETF
SMH|VanEck Semiconductor ETF
SOXX|iShares Semiconductor ETF
XBI|SPDR S&P Biotech ETF
IBB|iShares Biotechnology ETF
KRE|SPDR S&P Regional Banking ETF
XRT|SPDR S&P Retail ETF
ITB|iShares U.S. Home Construction ETF
TAN|Invesco Solar ETF
ICLN|iShares Global Clean Energy ETF
URA|Global X Uranium ETF
XOP|SPDR S&P Oil & Gas Exploration & Production ETF
AGG|iShares Core U.S. Aggregate Bond ETF
BND|Vanguard Total Bond Market ETF
BSV|Vanguard Short-Term Bond ETF
BIV|Vanguard Intermediate-Term Bond ETF
BLV|Vanguard Long-Term Bond ETF
IEF|iShares 7-10 Year Treasury Bond ETF
SHY|iShares 1-3 Year Treasury Bond ETF
TLT|iShares 20+ Year Treasury Bond ETF
GOVT|iShares U.S. Treasury Bond ETF
TIP|iShares TIPS Bond ETF
VTIP|Vanguard Short-Term Inflation-Protected Securities ETF
LQD|iShares iBoxx Investment Grade Corporate Bond ETF
HYG|iShares iBoxx High Yield Corporate Bond ETF
JNK|SPDR Bloomberg High Yield Bond ETF
MUB|iShares National Muni Bond ETF
EMB|iShares J.P. Morgan USD Emerging Markets Bond ETF
BIL|SPDR Bloomberg 1-3 Month T-Bill ETF
SGOV|iShares 0-3 Month Treasury Bond ETF
SHV|iShares Short Treasury Bond ETF
ICSH|iShares Ultra Short Duration Bond ETF
MBB|iShares MBS ETF
GLD|SPDR Gold Shares
IAU|iShares Gold Trust
SLV|iShares Silver Trust
USO|United States Oil Fund
UNG|United States Natural Gas Fund
DBA|Invesco DB Agriculture Fund
DBC|Invesco DB Commodity Index Tracking Fund
CPER|United States Copper Index Fund
UUP|Invesco DB US Dollar Index Bullish Fund
`));

const KOSPI200_SYMBOLS = symbolList(`
  000080 000087 000100 000120 000150 000210 000240 000270 000660 000670 000720 000810 000880 000990
  001040 001120 001230 001430 001440 001450 001530 001680 001740 001800 002380 002710 002790 002840
  003000 003030 003090 003230 003240 267250 003490 003520 003530 003550 003670 003850 004000 004020
  004170 004370 004490 004690 004700 004800 004990 005070 005180 005250 005300 005380 005420 005440
  005490 005830 005850 005930 005940 006040 006110 006120 006260 006280 006360 006400 006650 006800
  007070 007310 007340 007570 271560 008730 008770 008930 009150 009240 009420 009540 009830 009970
  010060 010120 010130 010140 272210 010690 010780 010950 011070 011170 011200 011210 011780 011790
  012330 012450 012510 012750 013890 014680 014820 014830 015760 016360 017670 017800 018260 018670
  018880 019170 020000 020150 021240 023530 023590 024110 025540 025860 026960 027410 028050 028260
  029780 030000 030200 032350 032640 032830 033780 034020 034220 034730 035250 035420 035720 036460
  036570 036580 039490 042660 047040 047050 047810 282330 051600 051900 051910 052690 055550 057050
  058650 064350 064960 066570 068270 069260 069620 069960 071050 071320 071840 073240 078930 079550
  081660 084010 086280 086790 088350 089590 090430 093050 093370 096770 097950 103140 103590 105560
  108670 111770 112610 114090 117580 120110 128940 137310 138040 138930 139130 139480 145720 161390
  161890 170900 175330 180640
`);

const KOSDAQ100_SYMBOLS = symbolList(`
  000250 017000 019550 025900 028300 032190 032500 033640 035760 035900 036200 036540 036810 036830
  039030 039200 039440 041510 042000 277810 048410 048530 049070 050890 053030 053610 053800 058470
  058610 058970 060250 060720 061970 064240 064260 064290 064550 064760 067160 067310 067900 068760
  069080 073570 078130 078340 078600 078890 079370 082270 084370 085660 086520 086900 088800 089030
  089790 089980 357780 092040 095340 095610 095660 095700 096530 099190 101490 108320 112040 121600
  122640 122870 131970 137400 140410 145020 178320 183300 196170 200130 214150 214370 214450 215200
  220260 222800 225570 226950 237690 240810 241710 247540 253450 263750 290650 293490 299030 299900
  376300 950220
`);

const KOREAN_SYMBOL_NAMES = Object.fromEntries(symbolNameList(`
000080|하이트진로
000087|하이트진로2우B
000100|유한양행
000120|CJ대한통운
000150|두산
000210|DL
000240|한국앤컴퍼니
000250|삼천당제약
000270|기아
000660|SK하이닉스
000670|영풍
000720|현대건설
000810|삼성화재
000880|한화
000990|DB하이텍
001040|CJ
001120|LX인터내셔널
001230|동국홀딩스
001430|세아베스틸지주
001440|대한전선
001450|현대해상
001530|DI동일
001680|대상
001740|SK네트웍스
001800|오리온홀딩스
002380|KCC
002710|TCC스틸
002790|아모레퍼시픽홀딩스
002840|미원상사
003000|부광약품
003030|세아제강지주
003090|대웅
003230|삼양식품
003240|태광산업
267250|HD현대
003490|대한항공
003520|영진약품
003530|한화투자증권
003550|LG
003670|포스코퓨처엠
003850|보령
004000|롯데정밀화학
004020|현대제철
004170|신세계
004370|농심
004490|세방전지
004690|삼천리
004700|조광피혁
004800|효성
004990|롯데지주
005070|코스모신소재
005180|빙그레
005250|녹십자홀딩스
005300|롯데칠성
005380|현대차
005420|코스모화학
005440|현대지에프홀딩스
005490|POSCO홀딩스
005830|DB손해보험
005850|에스엘
005930|삼성전자
005940|NH투자증권
006040|동원산업
006110|삼아알미늄
006120|SK디스커버리
006260|LS
006280|녹십자
006360|GS건설
006400|삼성SDI
006650|대한유화
006800|미래에셋증권
007070|GS리테일
007310|오뚜기
007340|DN오토모티브
007570|일양약품
271560|오리온
008730|율촌화학
008770|호텔신라
008930|한미사이언스
009150|삼성전기
009240|한샘
009420|한올바이오파마
009540|HD한국조선해양
009830|한화솔루션
009970|영원무역홀딩스
010060|OCI홀딩스
010120|LS ELECTRIC
010130|고려아연
010140|삼성중공업
272210|한화시스템
010690|화신
010780|아이에스동서
010950|S-Oil
011070|LG이노텍
011170|롯데케미칼
011200|HMM
011210|현대위아
011780|금호석유화학
011790|SKC
012330|현대모비스
012450|한화에어로스페이스
012510|더존비즈온
012750|에스원
013890|지누스
014680|한솔케미칼
014820|동원시스템즈
014830|유니드
015760|한국전력
016360|삼성증권
017000|신원종합개발
017670|SK텔레콤
017800|현대엘리베이터
018260|삼성에스디에스
018670|SK가스
018880|한온시스템
019170|신풍제약
019550|SBI인베스트먼트
020000|한섬
020150|롯데에너지머티리얼즈
021240|코웨이
023530|롯데쇼핑
023590|다우기술
024110|기업은행
025540|한국단자
025860|남해화학
025900|동화기업
026960|동서
027410|BGF
028050|삼성E&A
028260|삼성물산
028300|HLB
029780|삼성카드
030000|제일기획
030200|KT
032190|다우데이타
032350|롯데관광개발
032500|케이엠더블유
032640|LG유플러스
032830|삼성생명
033640|네패스
033780|KT&G
034020|두산에너빌리티
034220|LG디스플레이
034730|SK
035250|강원랜드
035420|NAVER
035720|카카오
035760|CJ ENM
035900|JYP Ent.
036200|유니셈
036460|한국가스공사
036540|SFA반도체
036570|NC
036580|팜스코
036810|에프에스티
036830|솔브레인홀딩스
039030|이오테크닉스
039200|오스코텍
039440|에스티아이
039490|키움증권
041510|에스엠
042000|카페24
042660|한화오션
047040|대우건설
047050|포스코인터내셔널
047810|한국항공우주
277810|레인보우로보틱스
048410|현대바이오
048530|인트론바이오
049070|인탑스
282330|BGF리테일
050890|쏠리드
051600|한전KPS
051900|LG생활건강
051910|LG화학
052690|한전기술
053030|바이넥스
053610|프로텍
053800|안랩
055550|신한지주
057050|현대홈쇼핑
058470|리노공업
058610|에스피지
058650|세아홀딩스
058970|엠로
060250|NHN KCP
060720|KH바텍
061970|LB세미콘
064240|홈캐스트
064260|다날
064290|인텍플러스
064350|현대로템
064550|바이오니아
064760|티씨케이
064960|SNT모티브
066570|LG전자
067160|SOOP
067310|하나마이크론
067900|와이엔텍
068270|셀트리온
068760|셀트리온제약
069080|웹젠
069260|TKG휴켐스
069620|대웅제약
069960|현대백화점
071050|한국금융지주
071320|지역난방공사
071840|롯데하이마트
073240|금호타이어
073570|리튬포어스
078130|국일제지
078340|컴투스
078600|대주전자재료
078890|가온그룹
078930|GS
079370|제우스
079550|LIG디펜스앤에어로스페이스
081660|미스토홀딩스
082270|젬백스
084010|대한제강
084370|유진테크
085660|차바이오텍
086280|현대글로비스
086520|에코프로
086790|하나금융지주
086900|메디톡스
088350|한화생명
088800|에이스테크
089030|테크윙
089590|제주항공
089790|제이티
089980|상아프론테크
090430|아모레퍼시픽
357780|솔브레인
092040|아미코젠
093050|LF
093370|후성
095340|ISC
095610|테스
095660|네오위즈
095700|제넥신
096530|씨젠
096770|SK이노베이션
097950|CJ제일제당
099190|아이센스
101490|에스앤에스텍
103140|풍산
103590|일진전기
105560|KB금융
108320|LX세미콘
108670|LX하우시스
111770|영원무역
112040|위메이드
112610|씨에스윈드
114090|GKL
117580|대성에너지
120110|코오롱인더
121600|나노신소재
122640|예스티
122870|와이지엔터테인먼트
128940|한미약품
131970|두산테스나
137310|에스디바이오센서
137400|피엔티
138040|메리츠금융지주
138930|BNK금융지주
139130|iM금융지주
139480|이마트
140410|메지온
145020|휴젤
145720|덴티움
161390|한국타이어앤테크놀로지
161890|한국콜마
170900|동아에스티
175330|JB금융지주
178320|서진시스템
180640|한진칼
183300|코미코
196170|알테오젠
200130|콜마비앤에이치
214150|클래시스
214370|케어젠
214450|파마리서치
215200|메가스터디교육
220260|켐트로스
222800|심텍
225570|넥슨게임즈
226950|올릭스
237690|에스티팜
240810|원익IPS
241710|코스메카코리아
247540|에코프로비엠
253450|스튜디오드래곤
263750|펄어비스
290650|엘앤씨바이오
293490|카카오게임즈
299030|하나기술
299900|위지윅스튜디오
376300|디어유
950220|네오이뮨텍
`));

const KOREAN_ETF_SYMBOLS = symbolList(`
114800
252670
251340
`);

const KOREAN_ETF_NAMES = Object.fromEntries(symbolNameList(`
114800|KODEX 인버스
252670|KODEX 200선물인버스2X
251340|KODEX 코스닥150선물인버스
`));

const CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD"];

const GLOBAL_EQUITY_SYMBOLS = [
  "ASML.AS", "SHEL.L", "AZN.L", "BP.L", "RIO.L", "BHP.AX",
  "ULVR.L", "HSBA.L", "7203.T", "6758.T", "7267.T", "7974.T", "9984.T",
  "0700.HK", "9988.HK", "TSM", "NVO", "SAP", "SIE.DE", "BAS.DE", "SHOP.TO",
  "UBSG.SW", "NESN.SW", "NOVN.SW", "MC.PA", "OR.PA", "AIR.PA",
];

const SYMBOL_NAME_OVERRIDES = {
  AAPL: "Apple Inc.",
  MSFT: "Microsoft Corporation",
  NVDA: "NVIDIA Corporation",
  GOOGL: "Alphabet Inc.",
  AMZN: "Amazon.com, Inc.",
  META: "Meta Platforms, Inc.",
  TSLA: "Tesla, Inc.",
  JPM: "JPMorgan Chase & Co.",
  "BRK-B": "Berkshire Hathaway Inc. Class B",
  SPY: "SPDR S&P 500 ETF Trust",
  QQQ: "Invesco QQQ Trust",
  TLT: "iShares 20+ Year Treasury Bond ETF",
  GLD: "SPDR Gold Shares",
  "005930.KS": "삼성전자 (005930 · KOSPI 200)",
  "000660.KS": "SK하이닉스 (000660 · KOSPI 200)",
  "035420.KS": "NAVER (035420 · KOSPI 200)",
  "035720.KS": "카카오 (035720 · KOSPI 200)",
  "357780.KQ": "솔브레인 (357780 · KOSDAQ 100)",
  "247540.KQ": "에코프로비엠 (247540 · KOSDAQ 100)",
  "ASML.AS": "ASML Holding N.V. (Euronext Amsterdam)",
  "SHEL.L": "Shell plc (London)",
  "ULVR.L": "Unilever PLC (London)",
  "AZN.L": "AstraZeneca PLC (London)",
  "HSBA.L": "HSBC Holdings plc (London)",
  "BP.L": "BP p.l.c. (London)",
  "RIO.L": "Rio Tinto Group (London)",
  "BHP.AX": "BHP Group (Australia)",
  "7203.T": "Toyota Motor Corporation (Tokyo)",
  "6758.T": "Sony Group Corporation (Tokyo)",
  "7267.T": "Honda Motor Co., Ltd. (Tokyo)",
  "7974.T": "Nintendo Co., Ltd. (Tokyo)",
  "9984.T": "SoftBank Group Corp. (Tokyo)",
  "0700.HK": "Tencent Holdings (Hong Kong)",
  "9988.HK": "Alibaba Group (Hong Kong)",
  TSM: "Taiwan Semiconductor Manufacturing Company ADR",
  NVO: "Novo Nordisk A/S ADR",
  SAP: "SAP SE ADR",
  "SIE.DE": "Siemens AG (Xetra)",
  "BAS.DE": "BASF SE (Xetra)",
  "SHOP.TO": "Shopify Inc. (Toronto)",
  "UBSG.SW": "UBS Group AG (SIX)",
  "NESN.SW": "Nestle S.A. (SIX)",
  "NOVN.SW": "Novartis AG (SIX)",
  "MC.PA": "LVMH (Euronext Paris)",
  "OR.PA": "L'Oreal S.A. (Euronext Paris)",
  "AIR.PA": "Airbus SE (Euronext Paris)",
  "BTC-USD": "Bitcoin USD",
  "ETH-USD": "Ethereum USD",
};

const ETF_GROUPS = {
  etf_bond: new Set(symbolList("AGG BND BSV BIV BLV IEF SHY TLT GOVT TIP VTIP LQD HYG JNK MUB EMB BIL SGOV SHV ICSH MBB")),
  etf_commodity: new Set(symbolList("GLD IAU SLV USO UNG DBA DBC CPER UUP")),
  etf_sector: new Set(symbolList("XLK XLF XLV XLY XLP XLE XLI XLU XLB XLRE XLC VGT VFH VHT VCR VDC VDE VIS VPU VAW VNQ IYR SMH SOXX XBI IBB KRE XRT ITB TAN ICLN URA XOP")),
};

function etfScope(symbol) {
  if (ETF_GROUPS.etf_bond.has(symbol)) return "etf_bond";
  if (ETF_GROUPS.etf_commodity.has(symbol)) return "etf_commodity";
  if (ETF_GROUPS.etf_sector.has(symbol)) return "etf_sector";
  return "etf_index";
}

function pushCatalogItem(rows, seen, item) {
  const symbol = normalizeTickerToken(item.symbol);
  if (!symbol || seen.has(symbol)) return;
  seen.add(symbol);
  rows.push({
    symbol,
    name: item.name || SYMBOL_NAME_OVERRIDES[symbol] || symbol,
    type: item.type,
    country: item.country,
    sector: item.sector || item.universe || "general",
    exchange: item.exchange || "",
    universe: item.universe || "custom",
    rank: item.rank || rows.length + 1,
  });
}

function buildSymbolCatalog() {
  const rows = [];
  const seen = new Set();
  US_LARGE_CAP_SYMBOLS.forEach((symbol, idx) => pushCatalogItem(rows, seen, {
    symbol,
    name: SYMBOL_NAME_OVERRIDES[symbol] || US_SYMBOL_NAMES[symbol] || `${symbol} · S&P 500 상위 200`,
    type: "stock",
    country: "US",
    sector: "us_large_cap",
    exchange: "US",
    universe: "us_large_cap",
    rank: idx + 1,
  }));
  ETF_CORE_SYMBOLS.forEach((symbol, idx) => {
    const scope = etfScope(symbol);
    pushCatalogItem(rows, seen, {
      symbol,
      name: SYMBOL_NAME_OVERRIDES[symbol] || ETF_SYMBOL_NAMES[symbol] || `${symbol} · 주요 ETF 100`,
      type: "etf",
      country: "US",
      sector: scope,
      exchange: "US ETF",
      universe: "etf_core",
      rank: idx + 1,
    });
  });
  KOSPI200_SYMBOLS.forEach((code, idx) => {
    const symbol = `${code}.KS`;
    const companyName = KOREAN_SYMBOL_NAMES[code] || code;
    pushCatalogItem(rows, seen, {
      symbol,
      name: SYMBOL_NAME_OVERRIDES[symbol] || `${companyName} (${code} · KOSPI 200)`,
      type: "stock",
      country: "KR",
      sector: "kr_kospi200",
      exchange: "KRX",
      universe: "kr_kospi200",
      rank: idx + 1,
    });
  });
  KOSDAQ100_SYMBOLS.forEach((code, idx) => {
    const symbol = `${code}.KQ`;
    const companyName = KOREAN_SYMBOL_NAMES[code] || code;
    pushCatalogItem(rows, seen, {
      symbol,
      name: SYMBOL_NAME_OVERRIDES[symbol] || `${companyName} (${code} · KOSDAQ 100)`,
      type: "stock",
      country: "KR",
      sector: "kr_kosdaq100",
      exchange: "KRX",
      universe: "kr_kosdaq100",
      rank: idx + 1,
    });
  });
  KOREAN_ETF_SYMBOLS.forEach((code, idx) => {
    const symbol = `${code}.KS`;
    const name = KOREAN_ETF_NAMES[code] || code;
    pushCatalogItem(rows, seen, {
      symbol,
      name: `${name} (${code} · KRX ETF)`,
      type: "etf",
      country: "KR",
      sector: "kr_inverse_etf",
      exchange: "KRX",
      universe: "kr_inverse_etf",
      rank: idx + 1,
    });
  });
  CRYPTO_SYMBOLS.forEach((symbol, idx) => pushCatalogItem(rows, seen, {
    symbol,
    name: SYMBOL_NAME_OVERRIDES[symbol] || symbol,
    type: "crypto",
    country: "GLOBAL",
    sector: "crypto",
    exchange: "Crypto",
    universe: "crypto_major",
    rank: idx + 1,
  }));
  GLOBAL_EQUITY_SYMBOLS.forEach((symbol, idx) => pushCatalogItem(rows, seen, {
    symbol,
    name: SYMBOL_NAME_OVERRIDES[symbol] || `${symbol} · Global equity`,
    type: "stock",
    country: "GLOBAL",
    sector: "global_equity",
    exchange: "Global",
    universe: "global_equity",
    rank: idx + 1,
  }));
  return rows;
}

const SYMBOL_CATALOG = buildSymbolCatalog();

// ---------- Utilities ----------
const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString();
};

const escapeHtml = (s) => String(s ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#39;");

const statusClass = (s) => ({ success: "success", partial: "partial", failed: "failed" }[s] || "muted");

const sourceStatusClass = (s) => {
  const key = (s || "").toLowerCase();
  if (["ok", "success"].includes(key)) return "ok";
  if (["failed", "error", "timeout"].includes(key)) return "fail";
  if (["empty", "entitlement_required", "credentials_missing", "rate_limited", "no_data_in_window", "provider_unavailable", "partial"].includes(key)) return "warn";
  return "muted";
};

function qualityStatusClass(status) {
  const key = String(status || "").toLowerCase();
  if (["ok", "success", "good", "normal", "fresh", "healthy"].includes(key)) return "ok";
  if (["failed", "fail", "error", "poor", "danger", "critical"].includes(key)) return "fail";
  if (["partial", "warn", "warning", "stale", "limited", "empty", "delayed"].includes(key)) return "warn";
  return "unknown";
}

function qualityStatusLabel(status) {
  const cls = qualityStatusClass(status);
  if (cls === "ok") return "정상";
  if (cls === "warn") return "주의";
  if (cls === "fail") return "위험";
  return "확인 불가";
}

function displayQualityValue(value, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.length ? value.join(", ") : "없음";
  return String(value);
}

function displayQualityCount(value, fallback = "확인 불가") {
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.length ? _fmtNumber(value.length) : "0";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return _fmtNumber(numeric);
  return displayQualityValue(value, fallback);
}

function displayMissingSummary(value, fallback = "확인 불가") {
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.length ? `${_fmtNumber(value.length)}개` : "없음";
  if (typeof value === "boolean") return value ? "있음" : "없음";
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric > 0 ? `${_fmtNumber(numeric)}개` : "없음";
  const text = displayQualityValue(value, fallback);
  return ["none", "no", "false", "0", "없음"].includes(text.toLowerCase()) ? "없음" : text;
}

function displayCompactQualityTime(value, fallback = "확인 불가") {
  const text = displayQualityValue(value, fallback);
  if (text === fallback || text === "-") return text;
  const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}:\d{2}))?/);
  if (match) return match[2] ? `${match[1]} ${match[2]}` : match[1];
  return text.length > 24 ? `${text.slice(0, 21)}...` : text;
}

function selectedRangeLabel() {
  const range = state.globalRange || DEFAULT_GLOBAL_RANGE;
  if (range.range === "custom") {
    const bounds = globalRangeDateBounds(range.range, range.startDate, range.endDate);
    const start = bounds.startDate || "시작일 미지정";
    const end = bounds.endDate || range.endDate || "종료일 미지정";
    return `${start}~${end}`;
  }
  return range.range || DEFAULT_GLOBAL_RANGE.range;
}

function renderGlobalQualitySummary() {
  if (!els.globalQualitySummary) return;
  const detail = globalQualityContextModel();
  const status = detail.status;
  const statusClassName = qualityStatusClass(status);
  const label = [
    `품질 ${detail.statusLabel}`,
    `기준일 ${detail.asOf}`,
    `업데이트 ${detail.updatedAt}`,
    `기간 ${detail.range}`,
    `관측치 ${detail.observations}`,
    `결측 ${detail.missing}`,
    `AI 기준 ${detail.aiSnapshot}`,
  ].join(", ");
  els.globalQualitySummary.className = `global-quality-summary ${statusClassName}`;
  els.globalQualitySummary.setAttribute("aria-label", label);
  els.globalQualitySummary.title = [
    `데이터 소스: ${detail.source}`,
    `분석 기간: ${detail.range}`,
    `관측치 수: ${detail.observations}`,
    `결측치: ${detail.missing}`,
    `캐시: ${detail.cache}`,
    `AI 분석 기준: ${detail.aiSnapshot}`,
  ].join("\n");
  els.globalQualitySummary.innerHTML = `
    <span class="quality-status">품질: ${escapeHtml(detail.statusLabel)}</span>
    <span class="quality-meta">기준일: ${escapeHtml(detail.asOf)}</span>
    <span class="quality-meta">업데이트: ${escapeHtml(detail.updatedAt)}</span>
    <span class="quality-meta quality-range">기간: ${escapeHtml(detail.range)}</span>
    <span class="quality-meta quality-observations" data-summary-field="observations">관측치: ${escapeHtml(detail.observations)}</span>
    <span class="quality-meta quality-missing" data-summary-field="missing">결측: ${escapeHtml(detail.missing)}</span>
    <span class="quality-meta quality-ai" data-summary-field="ai-snapshot">AI 기준: ${escapeHtml(detail.aiSnapshot)}</span>
  `;
  renderGlobalQualityContextSummary();
}

function updateGlobalQualitySummary(next = {}) {
  state.globalQuality = {
    ...(state.globalQuality || {}),
    ...next,
  };
  renderGlobalQualitySummary();
}

function markGlobalQualityRangePending() {
  const isEnglish = selectedOutputLanguage() === "en";
  state.globalQuality = {
    status: "unknown",
    asOf: "",
    updatedAt: isEnglish ? "refreshing" : "갱신 중",
    source: isEnglish ? "range changed; waiting for refreshed data" : "기간 변경 후 데이터 재계산 대기",
    observations: "",
    missing: isEnglish ? "checking" : "확인 중",
    cache: isEnglish ? "refreshing" : "재조회 중",
    aiSnapshotAt: isEnglish ? "pending recalculation" : "재계산 대기",
  };
  renderGlobalQualitySummary();
}

function globalQualityContextModel() {
  const quality = state.globalQuality || {};
  const status = quality.status || "unknown";
  const cacheValue = quality.cache ?? quality.cacheStatus ?? quality.cacheLayer
    ?? (quality.cache_hit === true ? "사용" : (quality.cache_hit === false ? "미사용" : undefined));
  const rangeSupport = globalRangeSupportSummary();
  return {
    status,
    statusLabel: qualityStatusLabel(status),
    asOf: displayQualityValue(quality.asOf || quality.dataBasisDate),
    updatedAt: displayCompactQualityTime(quality.updatedAt || quality.lastUpdated, "-"),
    range: selectedRangeLabel(),
    observations: displayQualityCount(quality.observations, "확인 불가"),
    missing: displayMissingSummary(quality.missing, "확인 불가"),
    source: displayQualityValue(quality.source, "확인 불가"),
    cache: displayQualityValue(cacheValue, "확인 불가"),
    aiSnapshot: displayCompactQualityTime(quality.aiSnapshotAt, "확인 불가"),
    rangeSupport: rangeSupport.detail,
  };
}

function qualityContextItem(label, value, field) {
  return `<span class="quality-context-item" data-quality-detail="${escapeHtml(field)}"><strong>${escapeHtml(label)}</strong><em>${escapeHtml(value)}</em></span>`;
}

function renderGlobalQualityContextSummary() {
  if (!els.qualityContextSummary) return;
  const detail = globalQualityContextModel();
  const statusClassName = qualityStatusClass(detail.status);
  els.qualityContextSummary.className = `quality-context-summary ${statusClassName}`;
  els.qualityContextSummary.innerHTML = `
    <div class="quality-context-head">
      <strong>현재 분석 신뢰도: ${escapeHtml(detail.statusLabel)}</strong>
      <span>상단 품질 배지와 같은 기준입니다. 확인 불가 값은 아직 출처나 기준일이 확보되지 않은 항목입니다.</span>
    </div>
    <div class="quality-context-grid">
      ${qualityContextItem("데이터 소스", detail.source, "source")}
      ${qualityContextItem("분석 기간", detail.range, "range")}
      ${qualityContextItem("기준일", detail.asOf, "basis-date")}
      ${qualityContextItem("마지막 업데이트", detail.updatedAt, "updated-at")}
      ${qualityContextItem("관측치", detail.observations, "observations")}
      ${qualityContextItem("결측치", detail.missing, "missing")}
      ${qualityContextItem("캐시", detail.cache, "cache")}
      ${qualityContextItem("AI 분석 기준", detail.aiSnapshot, "ai-snapshot")}
      ${qualityContextItem("기간 적용 방식", detail.rangeSupport, "range-support")}
    </div>
  `;
}

const KNOWN_TICKERS = SYMBOL_CATALOG
  .map((item) => normalizeTickerToken(item.symbol))
  .filter(Boolean)
  .sort((a, b) => b.length - a.length || a.localeCompare(b));
const UNREGISTERED_TICKER_STOPWORDS = new Set([
  "AI", "API", "APP", "CEO", "CFO", "CPU", "CPI", "ETF", "EPS", "FED", "FOMC",
  "GDP", "GPU", "IPO", "KRX", "LLM", "MDD", "NAV", "NYSE", "PBR", "PER", "ROA",
  "ROE", "SEC", "USD",
]);

function normalizeTickerToken(value) {
  const clean = String(value || "")
    .trim()
    .replace(/^\$/, "")
    .toUpperCase();
  const classShare = clean.match(/^([A-Z]{1,5})\.([A-Z])$/);
  if (classShare) return `${classShare[1]}-${classShare[2]}`;
  return clean;
}

function parseTickerInput(raw) {
  const seen = new Set();
  return String(raw || "")
    .split(/[\s,]+/)
    .map(normalizeTickerToken)
    .filter((ticker) => {
      if (!ticker || seen.has(ticker)) return false;
      seen.add(ticker);
      return true;
    });
}

function isSupportedExplicitTickerToken(ticker, { marked = false } = {}) {
  const clean = normalizeTickerToken(ticker);
  if (!clean) return false;
  if (KNOWN_TICKERS.includes(clean)) return true;
  if (!marked && UNREGISTERED_TICKER_STOPWORDS.has(clean)) return false;
  if (/^(?:[A-Z]{3,5}(?:[.-][A-Z0-9]{1,4})?|[A-Z]{2,8}-USD|[A-Z]{6}=X|[A-Z]{1,3}=F|\d{6}\.(?:KS|KQ))$/.test(clean)) {
    return true;
  }
  return marked && /^[A-Z]{1,2}(?:[.-][A-Z0-9]{1,4})?$/.test(clean);
}

const SYMBOL_PICKER_TARGETS = {
  research: {
    inputKey: "ticker",
    mode: () => (els.compareMode?.checked ? "multi" : "single"),
    title: "리서치 티커 선택",
    description: "종목 분석은 단일 선택, 비교 모드에서는 여러 심볼을 선택합니다.",
    emptyLabel: "리서치에 사용할 심볼을 선택하세요.",
    applyLabel: "티커 적용",
  },
  crossAssetSymbols: {
    inputKey: "crossAssetSymbols",
    mode: "multi",
    title: "교차자산 심볼 선택",
    description: "대시보드 교차자산 분석에 사용할 지수, ETF, 암호화폐, 글로벌 심볼을 선택합니다.",
    emptyLabel: "교차자산 분석에 사용할 심볼을 선택하세요.",
    applyLabel: "자산 적용",
  },
  homeNewsTicker: {
    inputKey: "homeNewsTicker",
    mode: "single",
    title: "뉴스 티커 선택",
    description: "회사 자체 뉴스를 조회할 단일 티커를 선택합니다.",
    emptyLabel: "뉴스를 조회할 티커를 선택하세요.",
    applyLabel: "티커 적용",
  },
  assetDetailTicker: {
    inputKey: "assetDetailTicker",
    mode: "single",
    title: "자산 상세 종목 선택",
    description: "가격, 수익률, 리스크를 조회할 단일 종목을 선택합니다.",
    emptyLabel: "자산 상세에 사용할 심볼을 선택하세요.",
    applyLabel: "종목 적용",
  },
  assetDetailBenchmark: {
    inputKey: "assetDetailBenchmark",
    mode: "single",
    title: "자산 상세 벤치마크 선택",
    description: "자산 상세 비교에 사용할 벤치마크 심볼을 선택합니다.",
    emptyLabel: "비교 기준 심볼을 선택하세요.",
    applyLabel: "벤치마크 적용",
  },
  backtest: {
    inputKey: "backtestTicker",
    chipsKey: "backtestUniverseChips",
    mode: "multi",
    title: "백테스트 유니버스 선택",
    description: "검색하거나 필터를 조합해 백테스트에 사용할 종목 유니버스를 선택합니다.",
    emptyLabel: "백테스트에 사용할 심볼을 선택하세요.",
    applyLabel: "유니버스 적용",
  },
  backtestBenchmark: {
    inputKey: "backtestBenchmark",
    mode: "single",
    title: "백테스트 벤치마크 선택",
    description: "성과 비교에 사용할 벤치마크 심볼을 선택합니다.",
    emptyLabel: "백테스트 벤치마크를 선택하세요.",
    applyLabel: "벤치마크 적용",
  },
  portfolio: {
    inputKey: "portfolioTickers",
    chipsKey: "portfolioUniverseChips",
    mode: "multi",
    title: "포트폴리오 유니버스 선택",
    description: "포트폴리오 최적화에 사용할 종목군을 검색하고 선택합니다.",
    emptyLabel: "포트폴리오에 사용할 심볼을 선택하세요.",
    applyLabel: "유니버스 적용",
  },
  portfolioBenchmark: {
    inputKey: "portfolioBenchmark",
    mode: "single",
    title: "포트폴리오 벤치마크 선택",
    description: "포트폴리오 성과 비교 기준을 선택합니다.",
    emptyLabel: "포트폴리오 벤치마크를 선택하세요.",
    applyLabel: "벤치마크 적용",
  },
  forecastTicker: {
    inputKey: "forecastTicker",
    mode: "single",
    title: "ML Forecast 티커 선택",
    description: "예측 실험 대상 단일 종목을 선택합니다.",
    emptyLabel: "예측 대상 심볼을 선택하세요.",
    applyLabel: "티커 적용",
  },
  forecastBenchmark: {
    inputKey: "forecastBenchmark",
    mode: "single",
    title: "ML Forecast 벤치마크 선택",
    description: "excess return과 비교 평가에 사용할 벤치마크를 선택합니다.",
    emptyLabel: "예측 벤치마크를 선택하세요.",
    applyLabel: "벤치마크 적용",
  },
  quantamentalTicker: {
    inputKey: "quantamentalTicker",
    mode: "single",
    title: "Quantamental 티커 선택",
    description: "재무제표, 가격, 팩터, 리스크를 분석할 단일 종목을 선택합니다.",
    emptyLabel: "Quantamental 분석 대상 심볼을 선택하세요.",
    applyLabel: "티커 적용",
  },
  aiPortfolioCustomUniverse: {
    inputKey: "aiPortfolioCustomUniverse",
    chipsKey: "aiPortfolioCustomUniverseChips",
    mode: "multi",
    title: "AI Portfolio 직접 유니버스 선택",
    description: "직접 입력 모드에서 사용할 종목 목록을 검색하고 선택합니다.",
    emptyLabel: "직접 유니버스에 사용할 심볼을 선택하세요.",
    applyLabel: "유니버스 적용",
  },
  aiPortfolioBenchmark: {
    inputKey: "aiPortfolioBenchmark",
    mode: "single",
    title: "AI Portfolio 벤치마크 선택",
    description: "AI Portfolio 성과 비교에 사용할 벤치마크를 선택합니다.",
    emptyLabel: "AI Portfolio 벤치마크를 선택하세요.",
    applyLabel: "벤치마크 적용",
  },
};

function symbolPickerTarget(targetKey = "backtest") {
  const key = SYMBOL_PICKER_TARGETS[targetKey] ? targetKey : "backtest";
  return { key, ...SYMBOL_PICKER_TARGETS[key] };
}

function symbolPickerMode(target = null) {
  const mode = target?.mode;
  return typeof mode === "function" ? mode() : (mode || "multi");
}

function normalizeSymbolSelection(tickers, mode = "multi") {
  const clean = [];
  const seen = new Set();
  (tickers || []).map(normalizeTickerToken).forEach((ticker) => {
    if (!ticker || seen.has(ticker)) return;
    seen.add(ticker);
    clean.push(ticker);
  });
  return mode === "single" ? clean.slice(-1) : clean;
}

function symbolTargetInput(target) {
  return target?.inputKey ? els[target.inputKey] : null;
}

function readSymbolTargetSymbols(targetKeyOrTarget = "backtest") {
  const target = typeof targetKeyOrTarget === "string" ? symbolPickerTarget(targetKeyOrTarget) : targetKeyOrTarget;
  const input = symbolTargetInput(target);
  return normalizeSymbolSelection(parseTickerInput(input?.value || ""), symbolPickerMode(target));
}

function setSymbolTargetSymbols(targetKeyOrTarget, tickers, options = {}) {
  const target = typeof targetKeyOrTarget === "string" ? symbolPickerTarget(targetKeyOrTarget) : targetKeyOrTarget;
  const input = symbolTargetInput(target);
  if (!input) return;
  const mode = symbolPickerMode(target);
  const clean = normalizeSymbolSelection(tickers, mode);
  input.value = mode === "single" ? (clean[0] || "") : clean.join(",");
  if (target.key === "backtest") state.lastUniverseResolution = null;
  renderSymbolTargetChips(target);
  if (options.dispatch !== false) input.dispatchEvent(new Event("input", { bubbles: true }));
}

function renderSymbolTargetChips(targetKeyOrTarget = "backtest") {
  const target = typeof targetKeyOrTarget === "string" ? symbolPickerTarget(targetKeyOrTarget) : targetKeyOrTarget;
  const chips = target?.chipsKey ? els[target.chipsKey] : null;
  if (!chips) return;
  const tickers = readSymbolTargetSymbols(target);
  const visibleTickers = tickers.slice(0, 48);
  const hiddenCount = Math.max(0, tickers.length - visibleTickers.length);
  chips.innerHTML = tickers.length
    ? `
        <span class="selected-symbol-count">선택 ${escapeHtml(_fmtNumber(tickers.length))}개</span>
        ${visibleTickers.map((ticker) => `
          <button type="button" data-symbol-chip-remove="${escapeHtml(ticker)}" title="${escapeHtml(ticker)} 제거">${escapeHtml(ticker)}</button>
        `).join("")}
        ${hiddenCount ? `<span class="selected-symbol-more">+${escapeHtml(_fmtNumber(hiddenCount))}개 더 있음</span>` : ""}
      `
    : '<span>선택된 심볼 없음</span>';
  chips.querySelectorAll("[data-symbol-chip-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      setSymbolTargetSymbols(target, tickers.filter((ticker) => ticker !== button.dataset.symbolChipRemove));
      if (!els.symbolPickerModal?.classList.contains("hidden")) renderSymbolPicker();
    });
  });
}

function setBacktestUniverse(tickers) {
  setSymbolTargetSymbols("backtest", tickers, { dispatch: false });
}

function selectedBacktestUniverse() {
  return parseTickerInput(els.backtestTicker?.value || "");
}

function renderUniverseResolutionNotice(data) {
  if (!data || typeof data !== "object") return "";
  const available = Array.isArray(data.available) ? data.available : [];
  const unavailable = Array.isArray(data.unavailable) ? data.unavailable : [];
  const staleAssets = Array.isArray(data.stale_assets) ? data.stale_assets : [];
  const hydration = data.hydration || {};
  const hydratedCount = Number(hydration.hydrated_count || (Array.isArray(hydration.hydrated) ? hydration.hydrated.length : 0));
  const staleRefreshed = Array.isArray(hydration.stale_refreshed) ? hydration.stale_refreshed : [];
  const staleRefreshAttempted = !!hydration.stale_refresh_attempted;
  const strictViolation = !!data.strict_freshness_violation;
  const status = unavailable.length || strictViolation || staleAssets.length ? "warn" : "ok";
  const hidden = Math.max(0, unavailable.length - 12);
  const hiddenStale = Math.max(0, staleAssets.length - 12);
  let summary = unavailable.length
    ? `실행 가능 ${_fmtNumber(available.length)}개 · 보강 후에도 가격 이력이 부족한 종목 ${_fmtNumber(unavailable.length)}개가 남았습니다.`
    : `실행 가능 ${_fmtNumber(available.length)}개 · 선택 종목의 저장 가격을 확인했습니다.`;
  if (hydratedCount > 0) {
    summary = unavailable.length
      ? `가격 이력 ${_fmtNumber(hydratedCount)}개 자동 보강 · 실행 가능 ${_fmtNumber(available.length)}개 · 추가 확인 필요 ${_fmtNumber(unavailable.length)}개`
      : `가격 이력 ${_fmtNumber(hydratedCount)}개 자동 보강 완료 · 실행 가능 ${_fmtNumber(available.length)}개`;
  }
  if (staleRefreshAttempted && staleRefreshed.length > 0) {
    summary += ` · stale 가격 ${_fmtNumber(staleRefreshed.length)}개 최신 보강`;
  }
  return `
    <div class="decision-summary ${escapeHtml(decisionStatusClass(status))}">
      ${escapeHtml(summary)}
      ${data.expected_latest_date ? `<br><span class="muted small">기대 최신일: ${escapeHtml(data.expected_latest_date)}</span>` : ""}
      ${unavailable.length ? `<br><span class="muted small">확인 필요: ${escapeHtml(unavailable.slice(0, 12).join(", "))}${hidden ? ` 외 ${escapeHtml(_fmtNumber(hidden))}개` : ""}</span>` : ""}
      ${staleAssets.length ? `<br><span class="muted small">stale: ${escapeHtml(staleAssets.slice(0, 12).join(", "))}${hiddenStale ? ` 외 ${escapeHtml(_fmtNumber(hiddenStale))}개` : ""}</span>` : ""}
      ${(unavailable.length || strictViolation || staleAssets.length) ? `<div class="freshness-cta"><button type="button" class="linkish decision-inline-action" data-action="enable-strict-freshness">공급자 갱신 후 엄격 검증</button></div>` : ""}
    </div>
  `;
  updateGlobalQualitySummary({
    status: quality.status || (statusCounts.stale || statusCounts.partial || statusCounts.unavailable ? "warn" : "ok"),
    asOf: quality.as_of || quality.latest_date || quality.last_updated || "",
    updatedAt: quality.last_updated || macroJob.finished_at || lastResult.finished_at || "",
    source: `macro · ${quality.provider || "mixed"}`,
    observations: coverage.evaluated_series || rows.length || "",
    missing: (quality.missing_series || []).length ? `${(quality.missing_series || []).length} series` : "없음",
  });
}

async function resolveQuantUniverseForTickers(tickers, options = {}) {
  const clean = Array.isArray(tickers) ? tickers.map(normalizeTickerToken).filter(Boolean) : [];
  if (!clean.length) return null;
  const extra = Array.isArray(options.extraTickers) ? options.extraTickers.map(normalizeTickerToken).filter(Boolean) : [];
  const requested = normalizeSymbolSelection([...clean, ...extra], "multi");
  const res = await fetch(API.quantUniverseResolve, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tickers: requested,
      start_date: options.startDate || null,
      end_date: options.endDate || null,
      freshness_profile: options.freshnessProfile || els.backtestFreshnessProfile?.value || "research_default",
      require_fresh_prices: options.requireFreshPrices ? true : undefined,
      max_market_calendar_lag_days: options.maxMarketCalendarLagDays || undefined,
      refresh_stale: options.refreshStale !== false,
      min_rows: options.minRows || 2,
      hydrate_missing: options.hydrateMissing !== false,
      max_hydrate_assets: options.maxHydrateAssets || 750,
      hydrate_batch_size: options.hydrateBatchSize || 40,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  state.lastUniverseResolution = data;
  return data;
}

function scopeUniverseResolution(data, tickers) {
  if (!data || !Array.isArray(tickers)) return data;
  const selected = new Set(tickers.map(normalizeTickerToken).filter(Boolean));
  const items = (Array.isArray(data.items) ? data.items : []).filter((item) => selected.has(normalizeTickerToken(item.ticker || "")));
  const available = (Array.isArray(data.available) ? data.available : []).filter((ticker) => selected.has(normalizeTickerToken(ticker)));
  const unavailable = (Array.isArray(data.unavailable) ? data.unavailable : []).filter((ticker) => selected.has(normalizeTickerToken(ticker)));
  const scopedCounts = {};
  const scopedLatest = {};
  Object.entries(data.price_counts || {}).forEach(([ticker, value]) => {
    if (selected.has(normalizeTickerToken(ticker))) scopedCounts[ticker] = value;
  });
  Object.entries(data.latest_price_dates || {}).forEach(([ticker, value]) => {
    if (selected.has(normalizeTickerToken(ticker))) scopedLatest[ticker] = value;
  });
  return {
    ...data,
    requested_count: selected.size,
    available_count: available.length,
    unavailable_count: unavailable.length,
    available,
    unavailable,
    items,
    price_counts: scopedCounts,
    latest_price_dates: scopedLatest,
    stale_assets: (Array.isArray(data.stale_assets) ? data.stale_assets : []).filter((ticker) => selected.has(normalizeTickerToken(ticker))),
  };
}

function selectedQuantFreshnessOptions() {
  return {
    freshnessProfile: els.backtestFreshnessProfile?.value || "research_default",
    requireFreshPrices: !!els.backtestRequireFresh?.checked,
    refreshStale: true,
  };
}

async function resolveBacktestUniverseAvailability(surface = null, options = {}) {
  const tickers = selectedBacktestUniverse();
  if (!tickers.length) return { ok: false, tickers: [], data: null };
  if (surface && !options.silent) {
    surface.innerHTML = decisionEmpty(`${tickers.length}개 종목의 저장 가격을 확인하고, 누락된 가격 이력은 자동 보강하는 중입니다.`);
  }
  try {
    const requiredRows = Math.max(
      2,
      numberInputValue(els.backtestShortWindow, 20, { min: 1, max: 5000 }) + 2,
      numberInputValue(els.backtestLongWindow, 50, { min: 2, max: 5000 }) + 2,
      options.minRows || 2,
    );
    const benchmark = normalizeTickerToken(els.backtestBenchmark?.value || "SPY") || "SPY";
    const data = await resolveQuantUniverseForTickers(tickers, {
      startDate: textInputValue(els.backtestStartDate),
      endDate: textInputValue(els.backtestEndDate),
      extraTickers: benchmark && !tickers.includes(benchmark) ? [benchmark] : [],
      minRows: requiredRows,
      hydrateMissing: options.hydrateMissing !== false,
      ...selectedQuantFreshnessOptions(),
    });
    const scopedData = scopeUniverseResolution(data, tickers);
    const available = Array.isArray(scopedData?.available) ? scopedData.available : [];
    const unavailable = Array.isArray(scopedData?.unavailable) ? scopedData.unavailable : [];
    if (available.length && unavailable.length) {
      setBacktestUniverse(available);
      if (els.portfolioTickers) {
        els.portfolioTickers.value = available.join(",");
        renderSymbolTargetChips("portfolio");
      }
      renderSymbolPicker();
    }
    if (!available.length) {
      if (surface) {
        surface.innerHTML = decisionEmpty("선택한 종목 중 저장 가격이 있는 종목이 없습니다. 데이터 마트 업데이트 후 다시 실행하세요.");
      }
      return { ok: false, tickers: [], data: scopedData };
    }
    return { ok: true, tickers: available, data: scopedData };
  } catch (err) {
    if (surface) surface.innerHTML = decisionEmpty(`종목 데이터 확인 실패: ${err.message || err}`);
    return { ok: false, tickers: [], data: null, error: err };
  }
}

async function resolvePortfolioUniverseAvailability(surface = null) {
  const tickers = parseTickerInput(els.portfolioTickers?.value || "");
  if (!tickers.length) return { ok: false, tickers: [], data: null };
  if (surface) surface.innerHTML = decisionEmpty(`${tickers.length}개 종목의 포트폴리오 가격 이력을 확인하고 자동 보강하는 중입니다.`);
  try {
    const requiredRows = Math.max(2, Math.min(52, numberInputValue(els.portfolioLookbackDays, 756, { min: 2, max: 5000 })));
    const benchmark = normalizeTickerToken(els.portfolioBenchmark?.value || "SPY") || "SPY";
    const data = await resolveQuantUniverseForTickers(tickers, {
      startDate: textInputValue(els.portfolioStartDate),
      endDate: textInputValue(els.portfolioEndDate),
      extraTickers: benchmark && !tickers.includes(benchmark) ? [benchmark] : [],
      minRows: requiredRows,
      hydrateMissing: true,
      ...selectedQuantFreshnessOptions(),
    });
    const scopedData = scopeUniverseResolution(data, tickers);
    const available = Array.isArray(scopedData?.available) ? scopedData.available : [];
    const unavailable = Array.isArray(scopedData?.unavailable) ? scopedData.unavailable : [];
    if (available.length && unavailable.length && els.portfolioTickers) {
      els.portfolioTickers.value = available.join(",");
      renderSymbolTargetChips("portfolio");
    }
    if (!available.length) {
      if (surface) surface.innerHTML = decisionEmpty("포트폴리오 최적화에 사용할 가격 이력이 있는 종목이 없습니다.");
      return { ok: false, tickers: [], data: scopedData };
    }
    return { ok: true, tickers: available, data: scopedData };
  } catch (err) {
    if (surface) surface.innerHTML = decisionEmpty(`포트폴리오 종목 확인 실패: ${err.message || err}`);
    return { ok: false, tickers: [], data: null, error: err };
  }
}

function renderBacktestUniverseChips() {
  renderSymbolTargetChips("backtest");
}

function symbolPickerMatches(item, query, selectedType, country, sector) {
  if (!item) return false;
  if (selectedType !== "all" && item.type !== selectedType) return false;
  if (country !== "all" && item.country !== country) return false;
  if (sector !== "all" && item.sector !== sector && item.universe !== sector) return false;
  if (!query) return true;
  const haystack = `${item.symbol} ${item.name} ${item.exchange} ${item.type} ${item.country} ${item.sector} ${item.universe}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function currentSymbolPickerItems() {
  const query = els.symbolPickerSearch?.value.trim() || "";
  const type = state.symbolPickerType || "all";
  const country = els.symbolPickerCountry?.value || "all";
  const sector = els.symbolPickerSector?.value || "all";
  return SYMBOL_CATALOG.filter((item) => symbolPickerMatches(item, query, type, country, sector));
}

function symbolPickerScopeCount(scope) {
  if (scope === "kr_equity") return SYMBOL_CATALOG.filter((item) => item.country === "KR").length;
  return SYMBOL_CATALOG.filter((item) => item.universe === scope).length;
}

function renderSymbolPickerSummary(filteredCount, selectedCount) {
  if (!els.symbolPickerSummary) return;
  const summaryItems = [
    ["미국 대형주", symbolPickerScopeCount("us_large_cap"), "us_large_cap"],
    ["ETF", symbolPickerScopeCount("etf_core"), "etf_core"],
    ["한국", symbolPickerScopeCount("kr_equity"), "kr_equity"],
    ["글로벌 주식", symbolPickerScopeCount("global_equity"), "global_equity"],
    ["암호화폐", symbolPickerScopeCount("crypto_major"), "crypto_major"],
  ];
  els.symbolPickerSummary.innerHTML = `
    ${summaryItems.map(([label, count, scope]) => `
      <button type="button" data-symbol-scope="${escapeHtml(scope)}">${escapeHtml(label)} <strong>${escapeHtml(_fmtNumber(count))}</strong></button>
    `).join("")}
    <span>현재 필터 <strong>${escapeHtml(_fmtNumber(filteredCount))}</strong></span>
    <span>선택 <strong>${escapeHtml(_fmtNumber(selectedCount))}</strong></span>
  `;
}

function setSymbolPickerType(type) {
  state.symbolPickerType = type || "all";
  els.symbolPickerTabs?.querySelectorAll("[data-symbol-type]").forEach((button) => {
    button.classList.toggle("active", button.dataset.symbolType === state.symbolPickerType);
  });
}

function applySymbolPickerScope(scope) {
  const presets = {
    us_large_cap: { type: "stock", country: "US", sector: "us_large_cap" },
    etf_core: { type: "etf", country: "all", sector: "all" },
    kr_equity: { type: "stock", country: "KR", sector: "all" },
    global_equity: { type: "stock", country: "GLOBAL", sector: "global_equity" },
    crypto_major: { type: "crypto", country: "GLOBAL", sector: "crypto" },
  };
  const preset = presets[scope];
  if (!preset) return;
  setSymbolPickerType(preset.type);
  if (els.symbolPickerCountry) els.symbolPickerCountry.value = preset.country;
  if (els.symbolPickerSector) els.symbolPickerSector.value = preset.sector;
  if (els.symbolPickerSearch) els.symbolPickerSearch.value = "";
  renderSymbolPicker();
}

function renderSymbolPicker() {
  if (!els.symbolPickerList) return;
  const target = state.symbolPickerTarget || symbolPickerTarget("backtest");
  const mode = symbolPickerMode(target);
  const bulkEnabled = mode !== "single";
  const selected = new Set(readSymbolTargetSymbols(target));
  const items = currentSymbolPickerItems()
    .sort((a, b) => Number(selected.has(b.symbol)) - Number(selected.has(a.symbol)) || a.symbol.localeCompare(b.symbol));
  state.symbolPickerFilteredSymbols = items.map((item) => item.symbol);
  renderSymbolPickerSummary(items.length, selected.size);
  els.symbolPickerAddFiltered?.classList.toggle("hidden", !bulkEnabled);
  els.symbolPickerRemoveFiltered?.classList.toggle("hidden", !bulkEnabled);

  if (els.symbolPickerSelected) {
    const selectedItems = Array.from(selected);
    const visibleSelected = selectedItems.slice(0, 36);
    const hiddenSelected = Math.max(0, selectedItems.length - visibleSelected.length);
    els.symbolPickerSelected.innerHTML = selected.size
      ? `
          <span class="symbol-picker-count">선택 ${escapeHtml(_fmtNumber(selected.size))}개</span>
          ${visibleSelected.map((ticker) => `<span>${escapeHtml(ticker)}</span>`).join("")}
          ${hiddenSelected ? `<span>+${escapeHtml(_fmtNumber(hiddenSelected))}개</span>` : ""}
          ${bulkEnabled ? '<button type="button" class="symbol-picker-inline-action" data-symbol-select-all>전체 선택</button>' : ""}
          <button type="button" class="symbol-picker-inline-action muted" data-symbol-clear-selected>선택 해제</button>
        `
      : `
          <span>${escapeHtml(target.emptyLabel || "심볼을 선택하세요.")}</span>
          ${bulkEnabled ? '<button type="button" class="symbol-picker-inline-action" data-symbol-select-all>전체 선택</button>' : ""}
        `;
  }
  els.symbolPickerList.innerHTML = items.length
    ? items.map((item) => {
        const isSelected = selected.has(item.symbol);
        return `
          <button type="button" class="symbol-picker-row${isSelected ? " selected" : ""}" data-symbol-toggle="${escapeHtml(item.symbol)}">
            <span class="symbol-picker-symbol">${escapeHtml(item.symbol)}</span>
            <span class="symbol-picker-name">${escapeHtml(item.name)}</span>
            <span class="symbol-picker-meta">${escapeHtml(item.type)} · ${escapeHtml(item.exchange)}</span>
          </button>
        `;
      }).join("")
    : '<div class="symbol-picker-empty">검색 조건과 일치하는 심볼이 없습니다.</div>';
}

function openSymbolPicker(targetKey = "backtest") {
  if (!els.symbolPickerModal) return;
  state.symbolPickerTarget = symbolPickerTarget(targetKey);
  setSymbolPickerType("all");
  if (els.symbolPickerSearch) els.symbolPickerSearch.value = "";
  if (els.symbolPickerCountry) els.symbolPickerCountry.value = "all";
  if (els.symbolPickerSector) els.symbolPickerSector.value = "all";
  if (els.symbolPickerTitle) els.symbolPickerTitle.textContent = state.symbolPickerTarget.title || "심볼 찾기";
  if (els.symbolPickerDescription) {
    els.symbolPickerDescription.textContent = state.symbolPickerTarget.description || "검색하거나 필터를 조합해 심볼을 선택합니다.";
  }
  if (els.symbolPickerApply) els.symbolPickerApply.textContent = state.symbolPickerTarget.applyLabel || "적용";
  els.symbolPickerModal.classList.remove("hidden");
  renderSymbolPicker();
  window.setTimeout(() => els.symbolPickerSearch?.focus(), 0);
}

function closeSymbolPicker() {
  els.symbolPickerModal?.classList.add("hidden");
}

function toggleSymbolPickerItem(symbol) {
  const ticker = normalizeTickerToken(symbol);
  if (!ticker) return;
  const target = state.symbolPickerTarget || symbolPickerTarget("backtest");
  const selected = readSymbolTargetSymbols(target);
  if (symbolPickerMode(target) === "single") {
    setSymbolTargetSymbols(target, selected.includes(ticker) ? [] : [ticker]);
  } else if (selected.includes(ticker)) {
    setSymbolTargetSymbols(target, selected.filter((item) => item !== ticker));
  } else {
    setSymbolTargetSymbols(target, [...selected, ticker]);
  }
  renderSymbolPicker();
}

async function addFilteredSymbolsToBacktestUniverse() {
  const symbols = currentSymbolPickerItems().map((item) => item.symbol);
  if (!symbols.length) return;
  const target = state.symbolPickerTarget || symbolPickerTarget("backtest");
  if (symbolPickerMode(target) === "single") {
    setSymbolTargetSymbols(target, symbols.slice(0, 1));
  } else {
    setSymbolTargetSymbols(target, [...readSymbolTargetSymbols(target), ...symbols]);
  }
  renderSymbolPicker();
}

function removeFilteredSymbolsFromBacktestUniverse() {
  const filtered = new Set(currentSymbolPickerItems().map((item) => item.symbol));
  if (!filtered.size) return;
  const target = state.symbolPickerTarget || symbolPickerTarget("backtest");
  setSymbolTargetSymbols(target, readSymbolTargetSymbols(target).filter((ticker) => !filtered.has(ticker)));
  renderSymbolPicker();
}

function inferTickerFromQuestion(question) {
  const text = String(question || "").trimStart();
  if (!text) return null;

  // Marker-based extraction is intentionally permissive so users can type
  // "$BRK.B" or "BRK.B: ..." even when the symbol is not in the chip list.
  const marked = text.match(/^\$([A-Za-z][A-Za-z0-9]{0,9}(?:[.\-=][A-Za-z0-9]{1,8})?)(?=$|[^A-Za-z0-9])/);
  if (marked) return { ticker: normalizeTickerToken(marked[1]), source: "question_marker" };

  const colon = text.match(/^([A-Za-z][A-Za-z0-9]{0,9}(?:[.\-=][A-Za-z0-9]{1,8})?)\s*[:：]/);
  if (colon) {
    const ticker = normalizeTickerToken(colon[1]);
    if (isSupportedExplicitTickerToken(ticker)) return { ticker, source: "question_prefix" };
  }

  // Plain leading words are restricted to known symbols to avoid treating
  // "What" or "AI" as a ticker.
  const known = matchKnownTickerPrefix(text);
  if (known) return { ticker: known, source: "known_prefix" };
  const explicit = matchExplicitTickerPrefix(text);
  if (explicit) return { ticker: explicit, source: "explicit_prefix" };
  return null;
}

function matchKnownTickerPrefix(text) {
  const raw = String(text || "").trimStart();
  const upper = raw.toUpperCase();
  for (const ticker of KNOWN_TICKERS) {
    if (!upper.startsWith(ticker)) continue;
    const next = raw.charAt(ticker.length);
    if (next && /[A-Za-z0-9]/.test(next)) continue;
    const original = raw.slice(0, ticker.length);
    if (/^[A-Z]{1,3}$/.test(ticker) && original !== ticker) continue;
    return ticker;
  }
  return "";
}

function matchExplicitTickerPrefix(text) {
  const raw = String(text || "").trimStart();
  const match = raw.match(/^([A-Z][A-Z0-9]{0,9}(?:[.\-=][A-Z0-9]{1,8})?|\d{6}\.(?:KS|KQ))(?=$|[^A-Za-z0-9])/);
  if (!match) return "";
  const ticker = normalizeTickerToken(match[1]);
  return isSupportedExplicitTickerToken(ticker) ? ticker : "";
}

const MARKET_TOPIC_RULES = [
  {
    id: "kr_inverse_etf",
    label: "Korea inverse ETF topic",
    marketTerms: ["코스피", "kospi", "코스닥", "kosdaq", "krx", "한국 증시", "국내 증시", "한국 시장"],
    intentTerms: ["인버스", "inverse", "곱버스", "선물인버스", "하락 베팅", "short kospi", "short korea"],
    tickers: ["114800.KS", "252670.KS", "251340.KS", "EWY"],
  },
  {
    id: "credit_risk",
    label: "Credit risk topic",
    marketTerms: ["credit", "bond", "bonds", "회사채", "신용", "하이일드", "투자등급"],
    intentTerms: ["spread", "spreads", "widening", "risk", "default", "스프레드", "위험", "리스크", "부도"],
    tickers: ["HYG", "LQD", "TLT"],
  },
  {
    id: "rates_bonds",
    label: "Rates and bonds topic",
    marketTerms: ["rate", "rates", "yield", "treasury", "bond", "bonds", "금리", "채권", "국채"],
    intentTerms: ["curve", "duration", "attractive", "path", "level", "커브", "듀레이션", "매력", "경로", "수준"],
    tickers: ["TLT", "IEF", "SHY"],
  },
  {
    id: "commodities",
    label: "Commodity topic",
    marketTerms: ["gold", "oil", "crude", "commodity", "gld", "uso", "금", "유가", "원유", "원자재"],
    intentTerms: ["price", "attractive", "backwardation", "inventory", "가격", "매력", "백워데이션", "재고"],
    tickers: ["GLD", "USO"],
  },
  {
    id: "fx_dollar",
    label: "FX and dollar topic",
    marketTerms: ["fx", "forex", "dollar", "usd", "eurusd", "환율", "달러", "유로"],
    intentTerms: ["rate differential", "policy divergence", "strong", "weak", "강세", "약세", "금리차", "정책 차이"],
    tickers: ["EURUSD=X", "DXY"],
  },
  {
    id: "crypto",
    label: "Crypto topic",
    marketTerms: ["bitcoin", "btc", "ethereum", "eth", "crypto", "비트코인", "이더리움", "암호화폐"],
    intentTerms: ["volatility", "etf flow", "flow", "risk", "변동성", "etf", "자금", "리스크"],
    tickers: ["BTC-USD", "ETH-USD"],
  },
];

function textContainsAny(text, terms) {
  return terms.some((term) => text.includes(String(term || "").toLowerCase()));
}

function inferMarketTopicFromQuestion(question) {
  const text = String(question || "");
  const lower = text.toLowerCase();
  for (const rule of MARKET_TOPIC_RULES) {
    if (textContainsAny(lower, rule.marketTerms) && textContainsAny(lower, rule.intentTerms)) {
      return rule;
    }
  }
  return null;
}

function questionMentionsTicker(question, ticker) {
  const clean = normalizeTickerToken(ticker);
  if (!clean) return false;
  const upper = String(question || "").toUpperCase();
  if (upper.includes(clean)) return true;
  if (clean.endsWith(".KS") || clean.endsWith(".KQ")) {
    return upper.includes(clean.split(".", 1)[0]);
  }
  return false;
}

function shouldSuppressTypedTickersForTopic({ mode, compare, question, typedTickers }) {
  if (compare || mode === "ticker" || !typedTickers.length) return { suppress: false, topic: null };
  const topic = inferMarketTopicFromQuestion(question);
  if (!topic) return { suppress: false, topic: null };
  const explicitlyMentioned = typedTickers.some((ticker) => questionMentionsTicker(question, ticker));
  return { suppress: !explicitlyMentioned, topic };
}

function normalizeResearchIntent({ tickerRaw, question, modeHint, compare }) {
  const cleanQuestion = String(question || "").trim();
  const mode = ["auto", "ticker", "topic"].includes(modeHint) ? modeHint : "auto";
  const typedTickers = parseTickerInput(tickerRaw);
  const topicGuard = shouldSuppressTypedTickersForTopic({
    mode,
    compare,
    question: cleanQuestion,
    typedTickers,
  });
  const effectiveTypedTickers = topicGuard.suppress ? [] : typedTickers;
  const inferred = (!effectiveTypedTickers.length && !compare && !topicGuard.topic) ? inferTickerFromQuestion(cleanQuestion) : null;
  const tickers = effectiveTypedTickers.length ? effectiveTypedTickers : (inferred ? [inferred.ticker] : []);
  const ticker = tickers[0] || "";
  const intentKind = compare
    ? "compare"
    : mode === "ticker"
      ? "single_ticker_required"
      : mode === "topic"
        ? "topic"
        : ticker
          ? "auto_with_ticker_hint"
          : "auto_topic";

  return {
    ticker,
    tickers,
    compare: !!compare,
    mode_hint: mode,
    question: cleanQuestion,
    intent_kind: intentKind,
    extracted_ticker: inferred?.ticker || "",
    topic_hint: topicGuard.topic?.id || "",
    topic_related_tickers: topicGuard.topic?.tickers || [],
    stale_ticker_ignored: topicGuard.suppress ? typedTickers.join(",") : "",
    route_hint: compare ? "compare" : "universal",
  };
}

// ---------- Health ----------
async function checkHealth() {
  try {
    const res = await fetch(API.health);
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    els.healthPill.textContent = `api · v${data.version || ""}`;
    els.healthPill.classList.add("ok");
    els.healthPill.classList.remove("err");
  } catch (e) {
    els.healthPill.textContent = "api offline";
    els.healthPill.classList.add("err");
    els.healthPill.classList.remove("ok");
  }
}

// ---------- Preflight ----------
function shouldRunBackgroundPoll(force = false) {
  return !!force || !document.hidden;
}

const PREFLIGHT_WARNING_ONLY = new Set([
  "HF_TOKEN", "FMP_API_KEY", "FMP_STOCK_NEWS",
  "SEC_FILINGS", "FRED_MACRO", "TRANSCRIPT_PROVIDER", "ALPHA_VANTAGE_NEWS",
  "QDRANT_COLLECTION_SCHEMA", "OPENBB_NEWS_RUNTIME", "OPENBB_AGENT_CONTRACT",
]);

function classifyCheck(check) {
  if (check.ok) return "ok";
  return PREFLIGHT_WARNING_ONLY.has(check.name) ? "warn" : "err";
}

function preflightStateLabel(level) {
  if (level === "ok") return "정상";
  if (level === "warn") return "경고";
  if (level === "err") return "치명";
  return "확인";
}

function summarizePreflight(report) {
  const checks = (report && report.checks) || [];
  let critical = 0;
  let warning = 0;
  for (const c of checks) {
    const state = classifyCheck(c);
    if (state === "err") critical += 1;
    else if (state === "warn") warning += 1;
  }
  if (!checks.length) return { level: "muted", label: "사전 점검: 알 수 없음" };
  if (critical > 0) return { level: "err", label: `사전 점검: 치명 ${critical}개` };
  if (warning > 0) return { level: "warn", label: `사전 점검: 경고 ${warning}개` };
  return { level: "ok", label: "사전 점검: 정상" };
}

function renderPreflightPill(report) {
  const s = summarizePreflight(report);
  const pill = els.preflightPill;
  pill.classList.remove("ok", "warn", "err");
  if (s.level !== "muted") pill.classList.add(s.level);
  els.preflightLabel.textContent = s.label;
}

function renderPreflightPanel(report) {
  const checks = (report && report.checks) || [];
  els.preflightChecks.innerHTML = "";
  checks.forEach((c) => {
    const level = classifyCheck(c);
    const li = document.createElement("li");
    li.className = level;
    li.innerHTML = `
      <span class="status-dot"></span>
      <div>
        <div class="check-name">${escapeHtml(c.name)}</div>
        <div class="check-detail">${escapeHtml(c.detail || "")}</div>
      </div>
      <span class="check-state">${preflightStateLabel(level)}</span>
    `;
    els.preflightChecks.appendChild(li);
  });
  const ts = report.checked_at || "—";
  const overall = report.passed ? "핵심 통과" : "핵심 실패";
  els.preflightSubtitle.textContent = `마지막 점검: ${ts} · ${overall}`;
}

async function loadPreflight(force = false, options = {}) {
  const allowHidden = !!options.allowHidden || force;
  if (!shouldRunBackgroundPoll(allowHidden)) return state.preflight;
  if (state.preflightRequest) return state.preflightRequest;
  state.preflightRequest = (async () => {
    try {
      const res = await fetch(force ? API.preflightForce : API.preflight);
      if (!res.ok) throw new Error(`bad status ${res.status}`);
      const report = await res.json();
      state.preflight = report;
      renderPreflightPill(report);
      if (!els.preflightPanel.classList.contains("hidden")) {
        renderPreflightPanel(report);
      }
      return report;
    } catch (e) {
      els.preflightPill.classList.remove("ok", "warn");
      els.preflightPill.classList.add("err");
      els.preflightLabel.textContent = "사전 점검: 오프라인";
      return null;
    } finally {
      state.preflightRequest = null;
    }
  })();
  return state.preflightRequest;
}

async function loadRunbook() {
  try {
    const res = await fetch(API.runbookFailureModes);
    if (!res.ok) return;
    const data = await res.json();
    els.preflightRunbook.innerHTML = "";
    (data.modes || []).forEach((mode) => {
      const li = document.createElement("li");
      const rems = (mode.remediation || [])
        .map((r) => `<li>${escapeHtml(r)}</li>`)
        .join("");
      li.innerHTML = `
        <div class="rb-title">${escapeHtml(mode.code)} · ${escapeHtml(mode.label)}</div>
        <div class="rb-symptom">${escapeHtml(mode.symptom || "")}</div>
        <ul class="rb-remediation">${rems}</ul>
      `;
      els.preflightRunbook.appendChild(li);
    });
  } catch (e) {
    // Non-fatal: runbook is static content.
  }
}

function openPreflightPanel() {
  els.preflightPanel.classList.remove("hidden");
  if (state.preflight) renderPreflightPanel(state.preflight);
  else loadPreflight(false).then((r) => r && renderPreflightPanel(r));
}

function closePreflightPanel() {
  els.preflightPanel.classList.add("hidden");
}

// ---------- Qdrant admin panel ----------
async function openQdrantPanel() {
  if (!els.qdrantPanel) return;
  els.qdrantPanel.classList.remove("hidden");
  await loadQdrantInfo();
}

function closeQdrantPanel() {
  if (!els.qdrantPanel) return;
  els.qdrantPanel.classList.add("hidden");
  if (els.qdrantPurgeResult) els.qdrantPurgeResult.textContent = "";
}

function _fmtNumber(n) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString();
}

async function loadQdrantInfo() {
  if (!els.qdrantStats) return;
  els.qdrantStats.innerHTML = "<span class='muted'>Loading…</span>";
  els.qdrantSubtitle.textContent = "컬렉션 상태를 로드 중…";
  try {
    const res = await fetch(API.qdrantInfo);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const info = await res.json();
    renderQdrantInfo(info);
  } catch (err) {
    els.qdrantStats.innerHTML = `<span class='error'>조회 실패: ${escapeHtml(String(err.message || err))}</span>`;
    els.qdrantSubtitle.textContent = "조회 실패";
  }
}

function renderQdrantInfo(info) {
  if (!els.qdrantStats) return;
  const name = info.collection || "—";
  if (!info.exists) {
    els.qdrantSubtitle.textContent = `컬렉션 "${name}" 가 아직 생성되지 않았습니다.`;
    els.qdrantStats.innerHTML = "<span class='muted'>아직 ingest된 문서가 없습니다. 분석 한 번 실행 후 다시 확인하세요.</span>";
    els.qdrantBreakdownList.innerHTML = "<li class='muted'>—</li>";
    return;
  }
  els.qdrantSubtitle.textContent = `컬렉션: ${name} · status: ${info.status || "—"}`;
  const rows = [
    ["Points", _fmtNumber(info.points_count)],
    ["Vectors", _fmtNumber(info.vectors_count)],
    ["Indexed", _fmtNumber(info.indexed_vectors_count)],
    ["Segments", _fmtNumber(info.segments_count)],
    ["Payload fields", (info.payload_fields && info.payload_fields.length) ? info.payload_fields.join(", ") : "—"],
  ];
  els.qdrantStats.innerHTML = rows
    .map(([k, v]) => `<div class='qdrant-stat'><span class='qdrant-stat-k'>${escapeHtml(k)}</span><span class='qdrant-stat-v'>${escapeHtml(String(v))}</span></div>`)
    .join("");

  const bd = info.ticker_breakdown || [];
  if (bd.length === 0) {
    els.qdrantBreakdownList.innerHTML = "<li class='muted'>티커 정보가 있는 문서가 없습니다.</li>";
  } else {
    els.qdrantBreakdownList.innerHTML = bd
      .slice(0, 50)
      .map(
        (row) => `<li><span class='qdrant-bd-ticker'>${escapeHtml(row.ticker)}</span><span class='qdrant-bd-count'>${_fmtNumber(row.count)}</span></li>`,
      )
      .join("");
  }
  els.qdrantBreakdownNote.textContent = info.ticker_breakdown_truncated
    ? "(첫 2000개까지 스캔, 상위 50개 표시)"
    : (bd.length > 50 ? "(상위 50개 표시)" : "");
}

// ---------- Quality / Evaluation dashboard ----------
async function openQualityPanel() {
  if (!els.qualityPanel) return;
  els.qualityPanel.classList.remove("hidden");
  renderGlobalQualityContextSummary();
  await loadQualityDashboard();
}

function closeQualityPanel() {
  if (els.qualityPanel) els.qualityPanel.classList.add("hidden");
}

async function qualityFetchJson(url) {
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data.detail || `HTTP ${res.status}`, data };
    }
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: String(err.message || err), data: null };
  }
}

function renderQualityDataHealth(data) {
  if (!data) return decisionEmpty("데이터 마트 상태를 불러오지 못했습니다.");
  const summary = data.summary || {};
  const status = summary.decision_status || data.status || "unknown";
  const counts = data.table_counts || {};
  const latest = data.latest_run || {};
  const providerRows = Array.isArray(data.recent_provider_status) ? data.recent_provider_status.slice(0, 5) : [];
  const qualityRows = Array.isArray(data.recent_quality_checks) ? data.recent_quality_checks.slice(0, 5) : [];
  const failedCount = Number(summary.failed_provider_rows || 0);
  const staleCount = Number(summary.stale_or_failed_quality_rows || 0);
  const runRows = Number(latest.rows_inserted || 0) + Number(latest.rows_updated || 0);
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
      <span>${escapeHtml(latest.finished_at || latest.started_at || "업데이트 실행 이력 없음")} · ${escapeHtml(latest.market || "all")}</span>
    </div>
    <div class="decision-summary ${escapeHtml(decisionStatusClass(status))}">
      ${failedCount || staleCount
        ? `주의 필요: provider 실패 ${escapeHtml(_fmtNumber(failedCount))}건, 품질 경고 ${escapeHtml(_fmtNumber(staleCount))}건`
        : `업데이트 ${escapeHtml(latest.status || "ok")} · 이번 실행 반영 ${escapeHtml(_fmtNumber(runRows))}행`}
    </div>
    <div class="decision-metric-grid">
      ${decisionMetric("가격 행", _fmtNumber(counts.prices_daily), status)}
      ${decisionMetric("재무 스냅샷", _fmtNumber(counts.fundamentals_snapshots || 0), counts.fundamentals_snapshots ? "ok" : "warn")}
      ${decisionMetric("SEC 공시", _fmtNumber(counts.filings || 0), counts.filings ? "ok" : "warn")}
      ${decisionMetric("SEC 재무팩트", _fmtNumber(counts.sec_financial_facts || 0), counts.sec_financial_facts ? "ok" : "warn")}
      ${decisionMetric("거시 관측치", _fmtNumber(counts.macro_observations || 0), status)}
      ${decisionMetric("뉴스 evidence", _fmtNumber(counts.news_articles || 0), counts.news_articles ? "ok" : "warn")}
    </div>
    <div class="decision-section-title">최근 공급자 상태</div>
    <div class="decision-list compact">
      ${providerRows.length ? providerRows.map((row) => `
        <div class="decision-list-row">
          <span>${escapeHtml(row.provider || "provider")}${row.ticker ? ` · ${escapeHtml(row.ticker)}` : ""}</span>
          <strong class="${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(decisionStatusLabel(row.status || "unknown"))}</strong>
        </div>
      `).join("") : '<div class="muted small">No provider status rows yet.</div>'}
    </div>
    <div class="decision-section-title">최근 품질 점검</div>
    <div class="decision-list compact">
      ${qualityRows.length ? qualityRows.map((row) => `
        <div class="decision-list-row">
          <span>${escapeHtml(row.check_name || "quality")}${row.entity_id ? ` · ${escapeHtml(row.entity_id)}` : ""}</span>
          <strong class="${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(row.status || "unknown")}</strong>
        </div>
      `).join("") : '<div class="muted small">No quality checks recorded yet.</div>'}
    </div>
  `;
}

function renderQualityMacroData(data = {}, refreshStatus = {}) {
  const quality = data.data_quality || data;
  const rows = Array.isArray(data.series) ? data.series.slice(0, 12) : [];
  const scheduler = refreshStatus.scheduler || {};
  const lastResult = scheduler.last_result || {};
  const macroJob = lastResult.jobs?.macro_platform_data || {};
  const intervalHours = Number(scheduler.interval_s || 0) / 3600;
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(quality.status))}">${escapeHtml(quality.status || "unknown")}</span>
      <span>공급자 ${escapeHtml(quality.provider || "mixed")} · 마지막 갱신 ${escapeHtml(quality.last_updated || "사용 불가")}</span>
    </div>
    <div class="macro-quality-grid">
      ${decisionMetric("누락 시계열", _fmtNumber((quality.missing_series || []).length), (quality.missing_series || []).length ? "warn" : "ok")}
      ${decisionMetric("지연 시계열", _fmtNumber((quality.stale_series || []).length), (quality.stale_series || []).length ? "warn" : "ok")}
      ${decisionMetric("오류", _fmtNumber((quality.errors || []).length), (quality.errors || []).length ? "warn" : "ok")}
      ${decisionMetric("갱신 주기", intervalHours ? `${fmtDecimal(intervalHours, 1)}시간` : "대기", "ok")}
      ${decisionMetric("최근 갱신", macroJob.status || "대기", decisionStatusClass(macroJob.status || "unknown"))}
      ${decisionMetric("저장 행", _fmtNumber(Number(macroJob.rows_inserted || 0) + Number(macroJob.rows_updated || 0)), "ok")}
    </div>
    ${(quality.errors || []).length ? `<div class="macro-warning">${escapeHtml(quality.errors.slice(0, 6).join("; "))}</div>` : ""}
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>시계열</th><th>상태</th><th>최근일</th><th>공급자</th></tr></thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.series_id || "")}</td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(row.status || "unknown")}</span></td>
              <td>${escapeHtml(row.latest_date || "사용 불가")}</td>
              <td>${escapeHtml(row.provider || "unknown")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadQualityDashboard() {
  if (!els.qualitySummary) return;
  els.qualitySummary.innerHTML = "<span class='muted'>Loading…</span>";
  els.qualitySubtitle.textContent = "평가 결과를 로드 중…";
  if (els.qualityDataHealth) els.qualityDataHealth.innerHTML = decisionEmpty("데이터 마트 품질을 불러오는 중입니다.");
  if (els.qualityMacroData) els.qualityMacroData.innerHTML = decisionEmpty("매크로 시계열 품질을 불러오는 중입니다.");
  const [evalResult, dataHealthResult, macroQualityResult, macroRefreshResult] = await Promise.all([
    qualityFetchJson(API.evalDashboard),
    qualityFetchJson(API.dataHealth),
    qualityFetchJson(API.macroDataQuality),
    qualityFetchJson(API.macroRefreshStatus),
  ]);
  renderQualityDashboard(evalResult.ok ? evalResult.data : null, {
    evalError: evalResult.error,
    dataHealth: dataHealthResult,
    macroQuality: macroQualityResult,
    macroRefresh: macroRefreshResult,
  });
}

function renderQualityDashboard(data, extras = {}) {
  if (els.qualityDataHealth) {
    els.qualityDataHealth.innerHTML = extras.dataHealth?.ok
      ? renderQualityDataHealth(extras.dataHealth.data)
      : decisionEmpty(`데이터 마트 품질 조회 실패: ${extras.dataHealth?.error || "unknown"}`);
  }
  if (els.qualityMacroData) {
    els.qualityMacroData.innerHTML = extras.macroQuality?.ok
      ? renderQualityMacroData(extras.macroQuality.data, extras.macroRefresh?.data || {})
      : decisionEmpty(`매크로 데이터 품질 조회 실패: ${extras.macroQuality?.error || "unknown"}`);
  }
  if (!data) {
    els.qualitySummary.innerHTML = `<span class='error'>평가 품질 조회 실패: ${escapeHtml(extras.evalError || "unknown")}</span>`;
    els.qualitySubtitle.textContent = "데이터 품질은 아래 섹션에서 확인할 수 있습니다.";
    if (els.qualityCategories) els.qualityCategories.innerHTML = "<li class='muted'>평가 카테고리 데이터 없음.</li>";
    if (els.qualityCases) els.qualityCases.innerHTML = "<li class='muted'>평가 케이스가 없습니다.</li>";
    if (els.qualityCasesNote) els.qualityCasesNote.textContent = "";
    if (els.qualityReport) els.qualityReport.textContent = "(평가 리포트를 불러오지 못했습니다)";
    return;
  }
  const summary = data.summary || {};
  const hasAnything = data.has_report || data.has_results;
  if (!hasAnything) {
    els.qualitySubtitle.textContent = "평가 산출물이 없습니다. quality_review.py 실행 후 다시 확인하세요.";
  } else {
    const parts = [];
    if (data.results_path) parts.push(`results: ${data.results_path}`);
    if (data.report_path) parts.push(`report: ${data.report_path}`);
    els.qualitySubtitle.textContent = parts.join(" · ") || "—";
  }

  const sc = summary.status_counts || {};
  const total = summary.total || 0;
  const kpis = [
    ["Cases", total],
    ["Pass", sc.success || 0],
    ["Partial", sc.partial || 0],
    ["Failed", sc.failed || 0],
    ["Avg confidence", summary.avg_confidence ?? "—"],
    ["Avg purity", summary.avg_purity ?? "—"],
    ["Avg elapsed", summary.avg_elapsed_s != null ? `${summary.avg_elapsed_s}s` : "—"],
  ];
  els.qualitySummary.innerHTML = kpis
    .map(([k, v]) => `<div class='quality-kpi'><span class='quality-kpi-k'>${escapeHtml(k)}</span><span class='quality-kpi-v'>${escapeHtml(String(v))}</span></div>`)
    .join("");

  const cats = summary.categories || [];
  if (cats.length === 0) {
    els.qualityCategories.innerHTML = "<li class='muted'>카테고리 데이터 없음.</li>";
  } else {
    els.qualityCategories.innerHTML = cats
      .map((c) => {
        const passRate = c.count ? Math.round((c.pass / c.count) * 100) : 0;
        const conf = c.avg_confidence != null ? c.avg_confidence : "—";
        return `<li class='quality-category'>
          <div class='quality-category-top'>
            <span class='quality-category-name'>${escapeHtml(c.category)}</span>
            <span class='quality-category-count'>${c.count} cases · ${passRate}% pass</span>
          </div>
          <div class='quality-category-bar'>
            <div class='quality-bar-pass' style='width:${(c.pass / Math.max(c.count, 1)) * 100}%'></div>
            <div class='quality-bar-partial' style='width:${(c.partial / Math.max(c.count, 1)) * 100}%'></div>
            <div class='quality-bar-failed' style='width:${(c.failed / Math.max(c.count, 1)) * 100}%'></div>
          </div>
          <div class='quality-category-meta'>avg confidence: ${escapeHtml(String(conf))}</div>
        </li>`;
      })
      .join("");
  }

  const cases = data.cases || [];
  els.qualityCasesNote.textContent = cases.length ? `(최근 ${cases.length}건)` : "";
  if (cases.length === 0) {
    els.qualityCases.innerHTML = "<li class='muted'>실행된 케이스가 없습니다.</li>";
  } else {
    els.qualityCases.innerHTML = cases
      .slice()
      .reverse()
      .map((c) => {
        const statusClass = c.status === "success" ? "ok" : (c.status === "partial" ? "warn" : "err");
        return `<li class='quality-case'>
          <div class='quality-case-top'>
            <span class='quality-case-status ${statusClass}'>${escapeHtml(c.status || "—")}</span>
            <span class='quality-case-ticker'>${escapeHtml(c.ticker || "")}</span>
            <span class='quality-case-cat'>${escapeHtml(c.category || "")}</span>
            <span class='quality-case-meta'>conf ${escapeHtml(String(c.confidence ?? "—"))} · chunks ${escapeHtml(String(c.context_chunks ?? 0))} · purity ${escapeHtml(String(c.purity_ratio ?? "—"))}</span>
          </div>
          <div class='quality-case-desc'>${escapeHtml(c.desc || c.question || "")}</div>
          ${c.error ? `<div class='quality-case-error'>${escapeHtml(c.error)}</div>` : ""}
        </li>`;
      })
      .join("");
  }

  if (els.qualityReport) {
    els.qualityReport.textContent = data.report_markdown || "(latest_eval_report.md 를 찾을 수 없습니다)";
  }
}

async function runQdrantPurge(dryRun) {
  if (!els.qdrantPurgeResult) return;
  const days = els.qdrantPurgeDays.value.trim();
  const ticker = els.qdrantPurgeTicker.value.trim().toUpperCase();
  if (!days && !ticker) {
    els.qdrantPurgeResult.textContent = "나이(days) 또는 티커를 최소 하나 지정하세요.";
    els.qdrantPurgeResult.className = "qdrant-purge-result error";
    return;
  }
  if (!dryRun) {
    const confirmMsg = `정말 삭제하시겠습니까?\n${days ? "older_than_days=" + days + "일" : ""} ${ticker ? "ticker=" + ticker : ""}`.trim();
    if (!window.confirm(confirmMsg)) return;
  }
  const params = new URLSearchParams();
  if (days) params.set("older_than_days", days);
  if (ticker) params.set("ticker", ticker);
  if (dryRun) params.set("dry_run", "true");
  els.qdrantPurgeResult.className = "qdrant-purge-result muted";
  els.qdrantPurgeResult.textContent = dryRun ? "Dry run 실행 중…" : "Purge 실행 중…";
  try {
    const res = await fetch(`${API.qdrantPurge}?${params.toString()}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.qdrantPurgeResult.className = "qdrant-purge-result ok";
    els.qdrantPurgeResult.textContent = dryRun
      ? `[dry run] scanned=${data.scanned} matched=${data.matched}. 실제 삭제 시 이만큼 제거됩니다.`
      : `✓ 삭제 완료 — scanned=${data.scanned}, matched=${data.matched}, deleted=${data.deleted}.`;
    if (!dryRun) {
      // Refresh stats after a real purge so the UI reflects the new state.
      await loadQdrantInfo();
    }
  } catch (err) {
    els.qdrantPurgeResult.className = "qdrant-purge-result error";
    els.qdrantPurgeResult.textContent = `실패: ${err.message || err}`;
  }
}

// ---------- Config / presets ----------
async function loadConfig() {
  try {
    const res = await fetch(API.config);
    if (!res.ok) {
      renderFinGPTStatus(null);
      return;
    }
    state.config = await res.json();
    if (!safeReadStoredValue(STORAGE.outputLanguage, "")) {
      state.outputLanguage = normalizeOutputLanguage(state.config.output_language || "ko");
    }
    renderModelOptions(state.config.models || []);
    renderQuantamentalAiModelOptions(state.config.models || []);
    renderPresets(state.config.presets || []);
    applyLimits(state.config.limits || {});
    renderFinGPTStatus(state.config);
    applyUiLanguage(state.outputLanguage, { persist: false });
  } catch (e) {
    console.warn("config fetch failed", e);
    renderModelOptions([]);
    renderQuantamentalAiModelOptions([]);
    renderPresets([]);
    renderFinGPTStatus(null);
  }
}

const CLEAN_PRESETS = [
  { id: "risk", label: "단기 리스크", question: "현재 드러나는 주요 단기 리스크와 시장이 과소평가하는 하방 시나리오는 무엇인가요?" },
  { id: "catalyst", label: "성장 촉매", question: "향후 6~12개월 동안 가격을 움직일 핵심 상승 촉매와 검증 지표는 무엇인가요?" },
  { id: "thesis", label: "12개월 투자 가설", question: "최신 공개 정보와 정량 지표를 기준으로 12개월 투자 가설을 정리해주세요." },
  { id: "earnings", label: "실적 신호", question: "최근 실적과 가이던스에서 확인되는 매출, 마진, 비용 구조의 핵심 신호를 요약해주세요." },
  { id: "competitive", label: "경쟁 구도", question: "경쟁 구도가 어떻게 변하고 있고, 가격 결정력과 시장점유율에는 어떤 영향을 주나요?" },
];

const CLEAN_PRESETS_EN = [
  { id: "risk", label: "Near-term risk", question: "What near-term risks are visible now, and which downside scenario is the market underpricing?" },
  { id: "catalyst", label: "Growth catalyst", question: "Which catalysts could move the price over the next 6 to 12 months, and what metrics should verify them?" },
  { id: "thesis", label: "12-month thesis", question: "Build a 12-month investment thesis using the latest public evidence and quantitative metrics." },
  { id: "earnings", label: "Earnings signal", question: "Summarize the key revenue, margin, cost, and guidance signals from recent results." },
  { id: "competitive", label: "Competition", question: "How is the competitive landscape changing, and what does that imply for pricing power and share?" },
];

const UI_LANGUAGE_COPY = {
  ko: {
    languageLabel: "출력 언어",
    pipeline: "수집 -> 적재 -> 검색 -> 추론 -> 분석 -> 보고",
    preflightTitle: "로컬 의존성 상태 확인",
    preflightChecking: "사전 점검: 확인 중",
    quality: "품질",
    qualityTitle: "평가 및 품질 대시보드",
    theme: "테마",
    themeTitle: "테마 전환",
    healthChecking: "api · 확인 중",
    tickerHint: "ticker 없이 질의 가능, ticker는 참고 힌트",
    formLabels: {
      ticker: "티커",
      question: "질문",
      sources: "소스",
      compare: "비교 모드",
      find: "찾기",
      lookback: "조회 기간",
      topK: "상위 K",
      model: "추론 경로",
      hotkey: "실행",
    },
    tickerPlaceholder: "선택: TLT, GLD, BTC-USD",
    questionPlaceholder: "예: 현재 시장이 무시하는 리스크는 무엇인가요?",
    questionHint: "자유 질문 또는 프리셋 선택",
    modeLabels: { auto: "자동", ticker: "종목", topic: "주제" },
    run: "분석 실행",
    latest: "최근 결과",
    commandPanel: "리서치 패널",
    commandOpen: "컨트롤 열기",
    commandHide: "컨트롤 숨기기",
    formNotice: "요청 언어: 한국어",
    dashboardContext: [
      ["Data", "시장 데이터"],
      ["Mode", "근거 우선"],
      ["Runtime", "로컬 전용"],
      ["Execution", "자문용"],
    ],
    dashboardHero: {
      market: ["시장 대시보드", "티커를 입력하면 종목 분석으로, 비워두고 질문만 입력하면 금리·신용·FX·원자재·테마 topic 분석으로 라우팅합니다."],
      macro: ["매크로", "데이터 품질, 레짐, 자산군 영향, 정책 힌트, 리서치 맥락을 AI 해석과 분리해 점검합니다."],
      quant: ["퀀트 랩", "저장 가격 기반 리스크, 전략 검증, 포트폴리오 배분을 같은 조건으로 점검합니다."],
      quantamental: ["Quantamental", "재무제표, 가격, 팩터, 리스크를 deterministic engine으로 계산하고 AI는 구조화 결과만 해석합니다."],
      forecast: ["ML Forecast", "검증 가능한 예측 실험실입니다. 가격 경로가 아니라 OOS forward return, 확률, 신뢰도, 신호, 비용 반영 백테스트를 분리해 점검합니다."],
      "ai-portfolio": ["AI Portfolio", "투자형과 정책을 선택하고, 정량 엔진이 계산한 포트폴리오를 AI가 설명하는 사용자 승인 기반 워크플로우입니다."],
    },
    quantamental: {
      labels: {
        ticker: "티커",
        market: "시장",
        period: "기간",
        years: "연수",
        lookback: "가격 조회",
        style: "전략 스타일",
        peerLimit: "피어 한도",
        scoreMetric: "점수 기준",
        scoreThreshold: "최소 점수",
        scoreScreenLimit: "결과 한도",
      },
      buttons: {
        find: "찾기",
        analyze: "분석",
        refresh: "새로고침",
        aiReport: "AI 보고서",
        compare: "비교",
        screen: "스크린",
        ask: "질문",
        expandPeers: "피어 확장",
        saveSet: "세트 저장",
        loadSet: "세트 불러오기",
      },
      cards: {
        signal: ["Quantamental 신호", "리서치 후보 분류"],
        composite: ["복합 점수 대시보드", "하이브리드 점수와 데이터 품질"],
        screen: ["Signal Screener Top 5", "복합 점수 자동 랭킹"],
        scoreScreen: ["점수 임계값 스크리너", "선택한 점수 기준 이상의 후보"],
        factor: ["팩터 점수 그리드", "가치, 퀄리티, 성장, 모멘텀, 저변동성, 유동성"],
        terminal: ["리서치 터미널", "개요, 재무, 퀀트, 리스크, 밸류에이션, AI, Q&A"],
        quality: ["데이터 품질", "누락 데이터와 제공자 커버리지"],
        compare: ["피어 비교", "배치 비교와 피어 상대 팩터"],
      },
      messages: {
        status: "Quantamental 분석은 리서치 전용이며 투자 자문이 아닙니다.",
        topStatus: "Top 5 스크리너가 신선한 신호 후보를 자동 로드합니다.",
        topEmpty: "Top 5 신호 스크리너가 여기에 표시됩니다.",
        scoreStatus: "최소 점수를 설정한 뒤 현재 Quantamental 유니버스를 스크리닝합니다.",
        scoreEmpty: "점수 임계값 스크리너가 여기에 표시됩니다.",
        compareEmpty: "두 개 이상 티커를 비교해 팩터를 피어 대비 정규화합니다.",
        screenLoading: "Top 5 신호 스크리너가 최신 데이터를 새로고침 중입니다.",
        scoreScreenLoading: "점수 임계값 스크리너가 최신 데이터를 새로고침 중입니다.",
        compareLoading: "피어 비교를 실행 중입니다.",
        qaLoading: "Q&A 답변을 생성하는 중입니다.",
        questionRequired: "질문을 입력해야 합니다.",
        runFirst: "Quantamental 분석을 먼저 실행하세요.",
        tickerRequired: "티커가 필요합니다.",
        noSavedSets: "저장된 세트 없음",
      },
      scoreMetricLabels: {
        composite: "복합",
        value: "가치",
        quality: "품질",
        growth: "성장",
        momentum: "모멘텀",
        low_volatility: "저변동성",
        liquidity: "유동성",
        drawdown_resilience: "낙폭 회복",
        liquidity_stability: "유동성 안정성",
        trend_efficiency: "추세 효율",
        market_resilience: "시장 회복력",
      },
    },
  },
  en: {
    languageLabel: "Output language",
    pipeline: "Collect -> Store -> Search -> Infer -> Analyze -> Report",
    preflightTitle: "Check local dependencies",
    preflightChecking: "Preflight: checking",
    quality: "Quality",
    qualityTitle: "Evaluation and quality dashboard",
    theme: "Theme",
    themeTitle: "Toggle theme",
    healthChecking: "api · checking",
    tickerHint: "Ticker is optional; questions can route by topic",
    formLabels: {
      ticker: "Ticker",
      question: "Question",
      sources: "Sources",
      compare: "Compare mode",
      find: "Find",
      lookback: "Lookback",
      topK: "Top K",
      model: "Inference route",
      hotkey: "run",
    },
    tickerPlaceholder: "Optional: TLT, GLD, BTC-USD",
    questionPlaceholder: "Example: What risk is the market ignoring right now?",
    questionHint: "Free-form question or preset",
    modeLabels: { auto: "Auto", ticker: "Ticker", topic: "Topic" },
    run: "Run analysis",
    latest: "Latest result",
    commandPanel: "Research panel",
    commandOpen: "Open controls",
    commandHide: "Hide controls",
    formNotice: "Request language: English",
    dashboardContext: [
      ["Data", "Market feed"],
      ["Mode", "Evidence-first"],
      ["Runtime", "Local only"],
      ["Execution", "Advisory"],
    ],
    dashboardHero: {
      market: ["Market Dashboard", "Enter a ticker for single-name research, or leave it blank so the question can route to rates, credit, FX, commodities, or themes."],
      macro: ["Macro", "Review data quality, regimes, asset impact, policy hints, and research context separately from AI interpretation."],
      quant: ["Quant Lab", "Evaluate stored-price risk, strategy validation, and portfolio allocation under consistent assumptions."],
      quantamental: ["Quantamental", "Compute fundamentals, price, factor, and risk signals deterministically while AI only interprets the structured output."],
      forecast: ["ML Forecast", "A verifiable forecasting lab for OOS forward returns, probabilities, confidence, signals, and cost-aware backtests."],
      "ai-portfolio": ["AI Portfolio", "Choose investment type and policy, then review user-approved portfolios calculated by the quantitative engine and explained by AI."],
    },
    quantamental: {
      labels: {
        ticker: "Ticker",
        market: "Market",
        period: "Period",
        years: "Years",
        lookback: "Lookback",
        style: "Style",
        peerLimit: "Peer limit",
        scoreMetric: "Score Type",
        scoreThreshold: "Min Score",
        scoreScreenLimit: "Limit",
      },
      buttons: {
        find: "Find",
        analyze: "Analyze",
        refresh: "Refresh",
        aiReport: "AI Report",
        compare: "Compare",
        screen: "Screen",
        ask: "Ask",
        expandPeers: "Expand peers",
        saveSet: "Save set",
        loadSet: "Load set",
      },
      cards: {
        signal: ["Quantamental Signal", "research candidate classification"],
        composite: ["Composite Score Dashboard", "hybrid score and data quality"],
        screen: ["Signal Screener Top 5", "auto-ranked by composite score"],
        scoreScreen: ["Score Threshold Screener", "filter candidates above a selected minimum score"],
        factor: ["Factor Score Grid", "value, quality, growth, momentum, low volatility, liquidity"],
        terminal: ["Research Terminal", "Overview, Fundamentals, Quant, Risk, Valuation, AI, and Q&A"],
        quality: ["Data Quality", "missing data and provider coverage"],
        compare: ["Peer Comparison", "batch compare and peer-relative factors"],
      },
      messages: {
        status: "Quantamental analysis is research-only, not investment advice.",
        topStatus: "Top 5 screener loads fresh signal candidates automatically.",
        topEmpty: "Top 5 signal screener appears here.",
        scoreStatus: "Set a minimum score, then screen the current Quantamental universe.",
        scoreEmpty: "Score threshold screener appears here.",
        compareEmpty: "Compare two or more tickers to normalize factors against peers.",
        screenLoading: "Top 5 signal screener is refreshing fresh data.",
        scoreScreenLoading: "Score threshold screener is refreshing fresh data.",
        compareLoading: "Peer comparison is running.",
        qaLoading: "Q&A answer is being generated.",
        questionRequired: "Question is required.",
        runFirst: "Run Quantamental analysis first.",
        tickerRequired: "Ticker is required.",
        noSavedSets: "No saved sets",
      },
      scoreMetricLabels: {
        composite: "Composite",
        value: "Value",
        quality: "Quality",
        growth: "Growth",
        momentum: "Momentum",
        low_volatility: "Low Volatility",
        liquidity: "Liquidity",
        drawdown_resilience: "Drawdown Resilience",
        liquidity_stability: "Liquidity Stability",
        trend_efficiency: "Trend Efficiency",
        market_resilience: "Market Resilience",
      },
    },
  },
};

const FORM_MESSAGES = {
  ko: {
    tickerRequired: "종목 모드는 ticker가 필요합니다. ticker 없이 질문하려면 자동 또는 주제 모드를 선택하세요.",
    questionRequired: "질문을 입력해야 분석을 실행할 수 있습니다.",
    sourceRequired: "최소 한 개의 소스를 선택해야 합니다.",
    compareRequired: "Compare mode는 2개 이상의 ticker가 필요합니다. 쉼표 또는 공백으로 구분하세요.",
    streamNoResult: "스트림이 결과 이벤트 없이 종료되었습니다.",
  },
  en: {
    tickerRequired: "Ticker mode requires a ticker. Use Auto or Topic mode for tickerless questions.",
    questionRequired: "Enter a question before running analysis.",
    sourceRequired: "Select at least one source.",
    compareRequired: "Compare mode requires at least two tickers separated by commas or spaces.",
    streamNoResult: "The stream closed without a result event.",
  },
};

function normalizeOutputLanguage(value) {
  const clean = String(value || "ko").trim().toLowerCase();
  if (["en", "eng", "english"].includes(clean)) return "en";
  return "ko";
}

function selectedOutputLanguage() {
  return normalizeOutputLanguage(state.outputLanguage || state.config?.output_language || "ko");
}

function formMessage(key) {
  const language = selectedOutputLanguage();
  return FORM_MESSAGES[language]?.[key] || FORM_MESSAGES.ko[key] || key;
}

function setLeadingText(selector, text) {
  const el = document.querySelector(selector);
  if (!el) return;
  const node = Array.from(el.childNodes).find((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
  if (node) node.textContent = `${text} `;
  else el.insertBefore(document.createTextNode(`${text} `), el.firstChild);
}

function dashboardHeroForTab(tab = "market") {
  const copy = UI_LANGUAGE_COPY[selectedOutputLanguage()] || UI_LANGUAGE_COPY.ko;
  return copy.dashboardHero?.[tab] || copy.dashboardHero?.market || UI_LANGUAGE_COPY.ko.dashboardHero.market;
}

function updateDashboardHero(tab = "market") {
  const [title, body] = dashboardHeroForTab(tab);
  const homeTitle = document.querySelector(".home-hero h2");
  const homeCopy = document.querySelector(".home-hero p:not(.eyebrow)");
  if (homeTitle) homeTitle.textContent = title;
  if (homeCopy) homeCopy.textContent = body;
}

function setWrappedLabelText(control, text) {
  const label = control?.closest?.("label");
  const span = label?.querySelector?.("span");
  if (span) span.textContent = text;
}

function setCardCopy(surface, copy) {
  const card = surface?.closest?.(".home-card");
  const [title, subtitle] = copy || [];
  if (!card || !title) return;
  const heading = card.querySelector(".home-card-head h3");
  const caption = card.querySelector(".home-card-head span");
  if (heading) heading.textContent = title;
  if (caption && subtitle) caption.textContent = subtitle;
}

function applyQuantamentalUiLanguage(copy) {
  const q = copy.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  setWrappedLabelText(els.quantamentalTicker, q.labels.ticker);
  setWrappedLabelText(els.quantamentalMarket, q.labels.market);
  setWrappedLabelText(els.quantamentalPeriod, q.labels.period);
  setWrappedLabelText(els.quantamentalYears, q.labels.years);
  setWrappedLabelText(els.quantamentalLookback, q.labels.lookback);
  setWrappedLabelText(els.quantamentalStyle, q.labels.style);
  setWrappedLabelText(els.quantamentalPeerLimit, q.labels.peerLimit);
  setWrappedLabelText(els.quantamentalScoreMetric, q.labels.scoreMetric);
  setWrappedLabelText(els.quantamentalScoreThreshold, q.labels.scoreThreshold);
  setWrappedLabelText(els.quantamentalScoreScreenLimit, q.labels.scoreScreenLimit);
  if (els.quantamentalScoreMetric) {
    Array.from(els.quantamentalScoreMetric.options || []).forEach((option) => {
      option.textContent = q.scoreMetricLabels?.[option.value] || option.textContent;
    });
  }
  if (els.quantamentalTickerOpen) els.quantamentalTickerOpen.textContent = q.buttons.find;
  if (els.quantamentalAnalyze) els.quantamentalAnalyze.textContent = q.buttons.analyze;
  if (els.quantamentalScreenRun) els.quantamentalScreenRun.textContent = q.buttons.refresh;
  if (els.quantamentalScoreScreenRun) els.quantamentalScoreScreenRun.textContent = q.buttons.screen;
  if (els.quantamentalAiRefresh) els.quantamentalAiRefresh.textContent = q.buttons.aiReport;
  if (els.quantamentalCompareRun) els.quantamentalCompareRun.textContent = q.buttons.compare;
  const expandLabel = els.quantamentalExpandPeers?.closest?.("label");
  const expandText = Array.from(expandLabel?.childNodes || []).find((node) => node.nodeType === Node.TEXT_NODE);
  if (expandText) expandText.textContent = ` ${q.buttons.expandPeers}`;
  if (els.quantamentalWatchlistSave) els.quantamentalWatchlistSave.textContent = q.buttons.saveSet;
  if (els.quantamentalWatchlistLoad) els.quantamentalWatchlistLoad.textContent = q.buttons.loadSet;
  setCardCopy(els.quantamentalSignalSurface, q.cards.signal);
  setCardCopy(els.quantamentalScoreSurface, q.cards.composite);
  setCardCopy(els.quantamentalScreenSurface, q.cards.screen);
  setCardCopy(els.quantamentalScoreScreenSurface, q.cards.scoreScreen);
  setCardCopy(els.quantamentalFactorSurface, q.cards.factor);
  setCardCopy(els.quantamentalMainSurface, q.cards.terminal);
  setCardCopy(els.quantamentalDataQualitySurface, q.cards.quality);
  setCardCopy(els.quantamentalCompareSurface, q.cards.compare);
  if (!state.quantamentalLoaded && !state.quantamentalLoading) {
    const starter = quantamentalUi().starter ? quantamentalUi().starter() : decisionEmpty(q.messages.status);
    if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = starter;
    if (els.quantamentalSignalSurface) els.quantamentalSignalSurface.innerHTML = starter;
    if (els.quantamentalScoreSurface) els.quantamentalScoreSurface.innerHTML = starter;
    if (els.quantamentalFactorSurface) els.quantamentalFactorSurface.innerHTML = starter;
    if (els.quantamentalMainSurface) els.quantamentalMainSurface.innerHTML = starter;
    if (els.quantamentalDataQualitySurface) els.quantamentalDataQualitySurface.innerHTML = starter;
  }
  if (!state.quantamentalLoaded && els.quantamentalStatus) els.quantamentalStatus.textContent = q.messages.status;
  if (!state.quantamentalScreenLoaded && !state.quantamentalScreenLoading && els.quantamentalScreenStatus) els.quantamentalScreenStatus.textContent = q.messages.topStatus;
  if (!state.quantamentalScreenLoaded && !state.quantamentalScreenLoading && els.quantamentalScreenSurface) els.quantamentalScreenSurface.innerHTML = decisionEmpty(q.messages.topEmpty);
  if (!state.quantamentalScoreScreen && !state.quantamentalScoreScreenLoading && els.quantamentalScoreScreenStatus) els.quantamentalScoreScreenStatus.textContent = q.messages.scoreStatus;
  if (!state.quantamentalScoreScreen && !state.quantamentalScoreScreenLoading && els.quantamentalScoreScreenSurface) els.quantamentalScoreScreenSurface.innerHTML = decisionEmpty(q.messages.scoreEmpty);
  if (!state.quantamentalComparison && els.quantamentalCompareSurface) els.quantamentalCompareSurface.innerHTML = decisionEmpty(q.messages.compareEmpty);
  renderQuantamentalCompareWatchlists();
}

function applyUiLanguage(language, options = {}) {
  const normalized = normalizeOutputLanguage(language);
  state.outputLanguage = normalized;
  const copy = UI_LANGUAGE_COPY[normalized] || UI_LANGUAGE_COPY.ko;
  document.documentElement.lang = normalized;
  document.title = "FinGPT Local Research Assistant";
  if (options.persist !== false) safeWriteStoredValue(STORAGE.outputLanguage, normalized);
  if (els.languageToggle) {
    els.languageToggle.setAttribute("aria-label", copy.languageLabel);
    els.languageToggle.querySelectorAll("[data-language]").forEach((button) => {
      const active = button.dataset.language === normalized;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.classList.toggle("active", active);
    });
  }
  setText(".pipeline-pill", copy.pipeline);
  if (els.preflightPill) {
    els.preflightPill.title = copy.preflightTitle;
    if (els.preflightLabel && /확인 중|checking/i.test(els.preflightLabel.textContent || "")) {
      els.preflightLabel.textContent = copy.preflightChecking;
    }
  }
  if (els.qualityDashBtn) {
    els.qualityDashBtn.textContent = copy.quality;
    els.qualityDashBtn.title = copy.qualityTitle;
  }
  if (els.themeToggleBtn) {
    els.themeToggleBtn.textContent = copy.theme;
    els.themeToggleBtn.title = copy.themeTitle;
    els.themeToggleBtn.setAttribute("aria-label", copy.themeTitle);
  }
  if (els.healthPill && /확인 중|checking/i.test(els.healthPill.textContent || "")) {
    els.healthPill.textContent = copy.healthChecking;
  }
  if (els.tickerHint) els.tickerHint.textContent = copy.tickerHint;
  if (els.ticker) els.ticker.placeholder = copy.tickerPlaceholder;
  if (els.question) els.question.placeholder = copy.questionPlaceholder;
  setLeadingText('label[for="ticker"]', copy.formLabels.ticker);
  setLeadingText('label[for="question"]', copy.formLabels.question);
  setLeadingText('label[for="lookback"]', copy.formLabels.lookback);
  setLeadingText('label[for="topk"]', copy.formLabels.topK);
  setLeadingText('label[for="model"]', copy.formLabels.model);
  const sourceLabel = document.querySelector("#sourceToggles")?.closest(".field-group")?.querySelector(".field-label");
  if (sourceLabel) sourceLabel.textContent = copy.formLabels.sources;
  const compareLabel = document.querySelector(".compare-toggle span");
  if (compareLabel) compareLabel.textContent = copy.formLabels.compare;
  if (els.tickerSearchOpen) els.tickerSearchOpen.textContent = copy.formLabels.find;
  const qHint = document.querySelector('label[for="question"] .hint');
  if (qHint) qHint.textContent = copy.questionHint;
  els.researchModeInputs().forEach((input) => {
    const span = input.parentElement?.querySelector("span");
    if (span && copy.modeLabels[input.value]) span.textContent = copy.modeLabels[input.value];
  });
  const runLabel = els.runBtn?.querySelector(".btn-label");
  if (runLabel) runLabel.textContent = copy.run;
  if (els.loadLatestBtn) els.loadLatestBtn.textContent = copy.latest;
  const commandLabel = els.commandPanelToggle?.querySelector(".command-panel-label");
  if (commandLabel) commandLabel.textContent = copy.commandPanel;
  const commandState = els.commandPanelToggle?.querySelector(".command-panel-state");
  if (commandState) {
    const collapsed = els.controlPanel?.classList.contains("is-collapsed");
    commandState.textContent = collapsed ? copy.commandOpen : copy.commandHide;
  }
  const contextItems = els.dashboardContextStrip?.querySelectorAll("span") || [];
  copy.dashboardContext.forEach(([label, value], idx) => {
    if (contextItems[idx]) contextItems[idx].innerHTML = `<strong>${escapeHtml(label)}</strong> ${escapeHtml(value)}`;
  });
  if (state.config) renderPresets(state.config.presets || []);
  const runMeta = document.querySelector(".meta-row");
  if (runMeta) runMeta.innerHTML = `<span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> ${escapeHtml(copy.formLabels.hotkey)}`;
  updateDashboardHero(state.activeDashboardTab || "market");
  renderGlobalQualitySummary();
  applyQuantamentalUiLanguage(copy);
  updateQuantamentalAiModelStatus();
  if (state.quantamentalAnalysis) renderQuantamentalAnalysis(state.quantamentalAnalysis);
  if (state.quantamentalScreen) renderQuantamentalScreen(state.quantamentalScreen);
  if (state.quantamentalScoreScreen) renderQuantamentalScoreScreen(state.quantamentalScoreScreen);
  if (
    state.tradingViewInitialized
    && els.tvOverviewWidget
    && state.activeDashboardTab === "market"
    && normalizeTvChartSettings(state.tvChartSettings).source === "tradingview"
  ) {
    mountMarketOverviewChart(state.tvChartSettings);
  }
}

function bindLanguageToggle() {
  if (!els.languageToggle) return;
  els.languageToggle.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      applyUiLanguage(button.dataset.language || "ko", { persist: true });
      persistForm();
    });
  });
}

function isReadablePreset(p) {
  const text = `${p?.label || ""} ${p?.question || ""}`;
  return /[가-힣A-Za-z]/.test(text) && !/\uFFFD/.test(text);
}

function renderModelOptions(models) {
  if (!els.model) return;
  const current = els.model.value || "qwen";
  const rawOptions = Array.isArray(models) && models.length
    ? models.map((m) => (typeof m === "string" ? { id: m, label: m } : m))
    : [{ id: "qwen", label: "qwen2.5:7b (Ollama · 기본)" }];
  const options = rawOptions.filter((m) => (
    m
    && m.id
    && m.enabled !== false
    && (m.id === "qwen" || m.role === "fallback" || m.role === "experimental")
  ));
  if (!options.length) options.push({ id: "qwen", label: "qwen2.5:7b (Ollama · 기본)" });
  els.model.innerHTML = "";
  options.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      const availability = m.availability || "runtime_checked";
      opt.textContent = m.label || m.id;
      opt.title = availability === "runtime_checked"
        ? "Configured route; actual Ollama model availability is checked when a request runs."
        : String(availability);
      opt.dataset.availability = availability;
      els.model.appendChild(opt);
  });
  els.model.value = Array.from(els.model.options).some((opt) => opt.value === current) ? current : "qwen";
}

function normalizeQuantamentalAiModels(models) {
  const runtimeModels = (Array.isArray(models) ? models : [])
    .map((m) => (typeof m === "string" ? { id: m, model: m, label: m } : m))
    .filter((m) => (
      m
      && m.id
      && m.enabled !== false
      && (m.id === "qwen" || String(m.id).toLowerCase().includes("gemma") || m.role === "experimental" || m.role === "fallback")
    ))
    .map((m) => ({
      id: String(m.id),
      model: String(m.model || m.model_name || m.id),
      label: String(m.label || m.model || m.id),
      role: String(m.role || "runtime"),
      availability: String(m.availability || "runtime_checked"),
      note: String(m.availability_note || "Model availability is checked when the AI request runs."),
    }));
  return [
    {
      id: "deterministic",
      model: "",
      label: "Deterministic guardrail",
      role: "guardrail",
      availability: "always_available",
      note: "Uses the deterministic Quantamental interpreter and does not call a local LLM.",
    },
    ...runtimeModels,
  ];
}

function quantamentalAiModelStatusText(option) {
  const isEnglish = selectedOutputLanguage() === "en";
  if (!option || option.id === "deterministic") {
    return isEnglish
      ? "Deterministic guardrail active. No local LLM call is made."
      : "Deterministic 해석이 활성화되어 로컬 LLM을 호출하지 않습니다.";
  }
  const role = option.role === "primary" ? "primary" : option.role;
  const availability = option.availability === "runtime_checked"
    ? (isEnglish ? "runtime checked" : "실행 시 확인")
    : option.availability;
  return isEnglish
    ? `${option.label} · ${role} · ${availability}; fallback remains deterministic if the provider fails.`
    : `${option.label} · ${role} · ${availability}; 공급자 실패 시 deterministic fallback을 유지합니다.`;
}

function selectedQuantamentalAiModelOption() {
  const options = state.quantamentalAiModels?.length
    ? state.quantamentalAiModels
    : normalizeQuantamentalAiModels(state.config?.models || []);
  const selected = els.quantamentalAiModel?.value || "deterministic";
  return options.find((option) => option.id === selected) || options[0];
}

function quantamentalAiRequestOptions() {
  const option = selectedQuantamentalAiModelOption();
  return {
    use_llm: option?.id !== "deterministic",
    model: option?.id === "deterministic" ? null : option?.model,
  };
}

function updateQuantamentalAiModelStatus() {
  if (!els.quantamentalAiModelStatus) return;
  els.quantamentalAiModelStatus.textContent = quantamentalAiModelStatusText(selectedQuantamentalAiModelOption());
}

function renderQuantamentalAiModelOptions(models) {
  state.quantamentalAiModels = normalizeQuantamentalAiModels(models);
  if (!els.quantamentalAiModel) return;
  const current = els.quantamentalAiModel.value || "deterministic";
  els.quantamentalAiModel.innerHTML = "";
  state.quantamentalAiModels.forEach((model) => {
    const opt = document.createElement("option");
    opt.value = model.id;
    opt.textContent = model.id === "deterministic"
      ? model.label
      : `${model.label} · ${model.availability === "runtime_checked" ? "runtime checked" : model.availability}`;
    opt.title = model.note;
    opt.dataset.model = model.model || "";
    opt.dataset.availability = model.availability;
    els.quantamentalAiModel.appendChild(opt);
  });
  els.quantamentalAiModel.value = state.quantamentalAiModels.some((model) => model.id === current)
    ? current
    : "deterministic";
  updateQuantamentalAiModelStatus();
}

function renderFinGPTStatus(config) {
  if (!els.fingptStatus) return;
  const fingpt = config?.fingpt || {};
  const enabled = !!(fingpt.datasets_enabled || fingpt.task_model_enabled);
  els.fingptStatus.classList.toggle("is-enabled", enabled);
  if (!enabled) {
    els.fingptStatus.textContent = "FinGPT 보조 기능 비활성 · 기본 분석 경로에는 영향 없음";
    return;
  }
  const tasks = Array.isArray(fingpt.tasks) && fingpt.tasks.length
    ? fingpt.tasks.join(", ")
    : "sentiment, headline, ner, relation, fiqa_qa, forecaster";
  els.fingptStatus.textContent = `FinGPT 보조 기능 활성: ${tasks}`;
}

function renderPresets(presets) {
  els.presetChips.innerHTML = "";
  const language = selectedOutputLanguage();
  const fallbackPresets = language === "en" ? CLEAN_PRESETS_EN : CLEAN_PRESETS;
  const usable = language === "ko" && Array.isArray(presets) && presets.length && presets.every(isReadablePreset)
    ? presets
    : fallbackPresets;
  usable.forEach((p) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = p.label;
    btn.title = p.question;
    btn.addEventListener("click", () => {
      els.question.value = p.question;
      els.question.focus();
      persistForm();
    });
    els.presetChips.appendChild(btn);
  });
}

function applyLimits(limits) {
  if (limits.lookback_days) {
    const { min, max, default: dflt } = limits.lookback_days;
    els.lookback.min = min;
    els.lookback.max = max;
    if (!els.lookback.dataset.dirty) els.lookback.value = dflt;
  }
  if (limits.top_k) {
    const { min, max, default: dflt } = limits.top_k;
    els.topk.min = min;
    els.topk.max = max;
    if (!els.topk.dataset.dirty) els.topk.value = dflt;
  }
  updateRangeLabels();
}

// ---------- Form ----------
function readForm() {
  const sources = Array.from(els.sourceInputs())
    .filter((i) => i.checked && !i.disabled)
    .map((i) => i.value);
  const raw = els.ticker.value.trim();
  const question = els.question.value.trim();
  const isCompare = !!(els.compareMode && els.compareMode.checked);
  const selectedMode = Array.from(els.researchModeInputs())
    .find((i) => i.checked)?.value || "auto";
  const intent = normalizeResearchIntent({
    tickerRaw: raw,
    question,
    modeHint: selectedMode,
    compare: isCompare,
  });
  return {
    ...intent,
    sources,
    lookback_days: parseInt(els.lookback.value, 10),
    top_k: parseInt(els.topk.value, 10),
    model: els.model.value,
    output_language: selectedOutputLanguage(),
  };
}

function persistForm() {
  try {
    localStorage.setItem(STORAGE.form, JSON.stringify(readForm()));
  } catch (e) { /* ignore */ }
}

function restoreForm() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE.form) || "null");
    if (!saved) return;
    if (saved.ticker) els.ticker.value = saved.ticker;
    if (saved.question) els.question.value = saved.question;
    if (Number.isFinite(saved.lookback_days)) els.lookback.value = saved.lookback_days;
    if (Number.isFinite(saved.top_k)) els.topk.value = saved.top_k;
    if (saved.model && Array.from(els.model.options).some((opt) => opt.value === saved.model)) {
      els.model.value = saved.model;
    }
    if (saved.output_language) {
      applyUiLanguage(saved.output_language, { persist: false });
    }
    if (Array.isArray(saved.sources)) {
      els.sourceInputs().forEach((i) => {
        if (i.disabled) return;
        i.checked = saved.sources.includes(i.value);
      });
    }
    if (saved.compare && els.compareMode) {
      els.compareMode.checked = true;
    }
    if (saved.mode_hint) {
      els.researchModeInputs().forEach((i) => {
        i.checked = i.value === saved.mode_hint;
      });
    }
  } catch (e) { /* ignore */ }
  updateRangeLabels();
  if (typeof updateCompareModeUI === "function") updateCompareModeUI();
}

function updateRangeLabels() {
  els.lookbackValue.textContent = `${els.lookback.value}d`;
  els.topkValue.textContent = els.topk.value;
}

function setFormNotice(message, level = "info") {
  if (!els.formNotice) return;
  if (!message) {
    els.formNotice.classList.add("hidden");
    els.formNotice.textContent = "";
    els.formNotice.classList.remove("warning", "error", "info");
    return;
  }
  els.formNotice.textContent = message;
  els.formNotice.classList.remove("hidden", "warning", "error", "info");
  els.formNotice.classList.add(level);
}

function refreshRoutingNotice() {
  if (!els.ticker || !els.question) return;
  const raw = els.ticker.value.trim();
  const question = els.question.value.trim();
  if (!raw || !question) {
    setFormNotice("");
    return;
  }
  const selectedMode = Array.from(els.researchModeInputs())
    .find((i) => i.checked)?.value || "auto";
  const intent = normalizeResearchIntent({
    tickerRaw: raw,
    question,
    modeHint: selectedMode,
    compare: !!(els.compareMode && els.compareMode.checked),
  });
  if (!intent.stale_ticker_ignored) {
    setFormNotice("");
    return;
  }
  const proxies = Array.isArray(intent.topic_related_tickers) && intent.topic_related_tickers.length
    ? ` 관련 프록시: ${intent.topic_related_tickers.join(", ")}.`
    : "";
  setFormNotice(`${intent.stale_ticker_ignored}는 질문에 직접 언급되지 않아 ${intent.topic_hint || "주제"} 분석으로 처리합니다.${proxies}`, "info");
}

function setText(selector, text) {
  const el = document.querySelector(selector);
  if (el) el.textContent = text;
}

function setCardHeader(surfaceId, title, subtitle = "") {
  const surface = document.getElementById(surfaceId);
  const card = surface?.closest?.(".home-card");
  if (!card) return;
  const heading = card.querySelector(".home-card-head h3");
  const caption = card.querySelector(".home-card-head span");
  if (heading) heading.textContent = title;
  if (caption && subtitle) caption.textContent = subtitle;
}

function fallbackDashboardContextItems(tab = "market") {
  const itemsByTab = {
    market: [
      { label: "데이터", value: "TradingView / Yahoo", status: "ok", detail: "시장 대시보드 기본 데이터" },
      { label: "범위", value: "시장 스냅샷", status: "ok", detail: "시장 테이프와 교차자산 신호" },
      { label: "최신성", value: "가능 시 장중 데이터", status: "warn", detail: "freshness 확인 필요" },
      { label: "작업", value: "새로고침과 점검", status: "ok", detail: "로컬 데이터 갱신" },
    ],
    macro: [
      { label: "데이터", value: "FRED / Yahoo / data mart", status: "ok", detail: "매크로 관측 데이터" },
      { label: "경계", value: "관측 데이터 우선", status: "ok", detail: "AI 해석 전 데이터 확인" },
      { label: "레짐", value: "신호와 AI 해석 분리", status: "warn", detail: "레짐 엔진 결과 우선" },
      { label: "출력", value: "정책 힌트 전용", status: "ok", detail: "자문용 맥락" },
    ],
    quant: [
      { label: "데이터", value: "저장 가격 이력", status: "ok", detail: "data mart 가격" },
      { label: "경계", value: "No-lookahead 검사", status: "warn", detail: "미래 데이터 누수 방지" },
      { label: "체결", value: "다음 봉 기준", status: "ok", detail: "체결 가정 명시" },
      { label: "출력", value: "아티팩트와 리플레이", status: "ok", detail: "재현 가능한 결과" },
    ],
    quantamental: [
      { label: "데이터", value: "yfinance + DART", status: "ok", detail: "시장별 provider coverage" },
      { label: "계산", value: "deterministic + peer", status: "ok", detail: "엔진 산출값 우선" },
      { label: "AI", value: "해석만 수행", status: "warn", detail: "AI는 점수 생성 금지" },
      { label: "출력", value: "classification + audit", status: "ok", detail: "스냅샷 감사" },
    ],
    forecast: [
      { label: "데이터", value: "data_mart 가격", status: "ok", detail: "예측 피처 입력" },
      { label: "검증", value: "Walk-forward 기본", status: "ok", detail: "시계열 검증" },
      { label: "가드", value: "Leakage / embargo", status: "warn", detail: "누수 검사 우선" },
      { label: "출력", value: "자문용 신호만", status: "ok", detail: "매매 지시 아님" },
    ],
    "ai-portfolio": [
      { label: "저장소", value: "Local SQLite", status: "ok", detail: "로컬 포트폴리오 상태" },
      { label: "정책", value: "제약조건 우선", status: "ok", detail: "정책 기반 엔진" },
      { label: "승인", value: "사용자 확인 작업", status: "warn", detail: "자동 리밸런싱 금지" },
      { label: "감사", value: "Hash와 이력", status: "ok", detail: "요청/정책 해시" },
    ],
  };
  return itemsByTab[tab] || itemsByTab.market;
}

function dashboardDecisionCardForTab(tab = "market") {
  return state.dashboardDecisionCardsByTab?.[tab] || null;
}

function setDashboardContextStrip(tab = "market") {
  if (!els.dashboardContextStrip) return;
  const card = dashboardDecisionCardForTab(tab);
  const chips = Array.isArray(card?.chips) && card.chips.length
    ? card.chips
    : fallbackDashboardContextItems(tab);
  els.dashboardContextStrip.dataset.contract = card?.contract_version || "static-fallback";
  els.dashboardContextStrip.innerHTML = chips
    .map((item) => {
      const status = decisionStatusClass(item.status || card?.status || "ok");
      const detail = item.detail || card?.primary_output || "";
      return `
        <span class="decision-card-chip ${escapeHtml(status)}" title="${escapeHtml(detail)}">
          <strong>${escapeHtml(item.label || "Context")}</strong>
          ${escapeHtml(item.value || "")}
          ${detail ? `<small>${escapeHtml(detail)}</small>` : ""}
        </span>
      `;
    })
    .join("");
}

async function loadDashboardDecisionCards(force = false) {
  if (!els.dashboardContextStrip) return null;
  if (state.dashboardDecisionCardsLoaded && !force) return state.dashboardDecisionCardsByTab;
  if (state.dashboardDecisionCardsRequest && !force) return state.dashboardDecisionCardsRequest;
  state.dashboardDecisionCardsRequest = (async () => {
    try {
      const res = await fetch(API.dashboardDecisionCards);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const byTab = {};
      for (const item of Array.isArray(data.items) ? data.items : []) {
        if (item?.tab) {
          byTab[item.tab] = { ...item, contract_version: data.contract_version };
        }
      }
      state.dashboardDecisionCardsByTab = byTab;
      state.dashboardDecisionCardsLoaded = true;
      setDashboardContextStrip(state.activeDashboardTab || "market");
      return byTab;
    } catch (err) {
      els.dashboardContextStrip.dataset.contract = "static-fallback-error";
      console.warn("dashboard decision cards fetch failed", err);
      return state.dashboardDecisionCardsByTab || {};
    } finally {
      state.dashboardDecisionCardsRequest = null;
    }
  })();
  return state.dashboardDecisionCardsRequest;
}

const DASHBOARD_PANEL_VIEWS = new Set(["overview", "details", "operations", "all"]);

function panelViewForTab(tab = "market") {
  if (state.dashboardPanelViewByTab?.[tab]) return state.dashboardPanelViewByTab[tab];
  return "all";
}

function updateDashboardViewControls() {
  if (!els.dashboardViewControls) return;
  const activeTab = state.activeDashboardTab || "market";
  const activeView = panelViewForTab(activeTab);
  const isMarket = activeTab === "market";
  els.dashboardViewControls.hidden = isMarket;
  els.dashboardViewControls.querySelectorAll("[data-panel-view]").forEach((button) => {
    const pressed = !isMarket && button.dataset.panelView === activeView;
    button.classList.toggle("active", pressed);
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
  });
}

function setDashboardPanelView(view = "all", options = {}) {
  const activeTab = options.tab || state.activeDashboardTab || "market";
  const fallback = "all";
  const normalized = DASHBOARD_PANEL_VIEWS.has(view) ? view : fallback;
  if (state.dashboardPanelViewByTab) {
    state.dashboardPanelViewByTab[activeTab] = normalized;
    safeWriteStoredJson(STORAGE.dashboardLayout, state.dashboardPanelViewByTab);
  }
  if (els.homeSurfaceGrid) {
    els.homeSurfaceGrid.dataset.panelView = activeTab === "market" ? "all" : normalized;
  }
  updateDashboardViewControls();
}

function setCommandPanelCollapsed(collapsed, options = {}) {
  if (!els.controlPanel || !els.commandPanelToggle) return;
  els.controlPanel.classList.toggle("is-collapsed", collapsed);
  document.body.classList.toggle("command-panel-expanded", !collapsed);
  els.commandPanelToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  const stateLabel = els.commandPanelToggle.querySelector(".command-panel-state");
  const copy = UI_LANGUAGE_COPY[selectedOutputLanguage()] || UI_LANGUAGE_COPY.ko;
  if (stateLabel) stateLabel.textContent = collapsed ? copy.commandOpen : copy.commandHide;
  if (options.persist) {
    safeWriteStoredValue(STORAGE.controlPanel, collapsed ? "collapsed" : "expanded");
  }
}

function syncCommandPanelForViewport() {
  if (!els.commandPanelToggle) return;
  const stored = safeReadStoredValue(STORAGE.controlPanel, "");
  const shouldCollapse = stored ? stored === "collapsed" : true;
  setCommandPanelCollapsed(Boolean(shouldCollapse));
}

function bindCommandPanelToggle() {
  if (!els.commandPanelToggle) return;
  els.commandPanelToggle.addEventListener("click", () => {
    const nextCollapsed = !els.controlPanel?.classList.contains("is-collapsed");
    setCommandPanelCollapsed(nextCollapsed, { persist: true });
  });
  syncCommandPanelForViewport();
  window.addEventListener("resize", syncCommandPanelForViewport);
}

function applyTheme(theme = "dark", options = {}) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalized;
  if (els.themeToggleBtn) {
    const nextLabel = normalized === "light" ? "다크" : "라이트";
    els.themeToggleBtn.textContent = nextLabel;
    els.themeToggleBtn.setAttribute("aria-pressed", normalized === "light" ? "true" : "false");
    els.themeToggleBtn.setAttribute("title", `${nextLabel} 테마로 전환`);
  }
  if (options.persist) {
    safeWriteStoredValue(STORAGE.theme, normalized);
  }
  if (state.tradingViewInitialized && els.tvOverviewWidget) {
    mountMarketOverviewChart(state.tvChartSettings);
  }
}

function bindThemeToggle() {
  applyTheme(safeReadStoredValue(STORAGE.theme, "dark"));
  if (!els.themeToggleBtn) return;
  els.themeToggleBtn.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(nextTheme, { persist: true });
  });
}

function dashboardTabFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const fromParam = params.get("tab") || params.get("dashboard");
  if (fromParam === "ai-portfolio" || fromParam === "ai") return "ai-portfolio";
  if (fromParam === "ml-forecast" || fromParam === "forecast") return "forecast";
  if (fromParam === "macro") return "macro";
  if (fromParam === "quantamental") return "quantamental";
  if (fromParam === "quant") return "quant";
  if (fromParam === "market") return "market";
  if (window.location.hash === "#ai-portfolio" || window.location.hash === "#ai") return "ai-portfolio";
  if (window.location.hash === "#ml-forecast" || window.location.hash === "#forecast-lab" || window.location.hash === "#forecast") return "forecast";
  if (window.location.hash === "#macro") return "macro";
  if (window.location.hash === "#quantamental") return "quantamental";
  if (window.location.hash === "#quant-lab" || window.location.hash === "#quant") return "quant";
  if (window.location.hash === "#market-dashboard" || window.location.hash === "#market") return "market";
  return "";
}

function setDashboardTab(tab = "market", options = {}) {
  const active = tab === "quantamental" ? "quantamental" : (tab === "quant" ? "quant" : (tab === "forecast" || tab === "ml-forecast" ? "forecast" : (tab === "macro" ? "macro" : (tab === "ai-portfolio" || tab === "ai" ? "ai-portfolio" : "market"))));
  state.activeDashboardTab = active;
  if (els.homeSurfaceGrid) {
    els.homeSurfaceGrid.dataset.dashboardTab = active;
  }
  setDashboardContextStrip(active);
  loadDashboardDecisionCards(false);
  setDashboardPanelView(panelViewForTab(active), { tab: active });
  const buttons = [
    { el: els.marketDashboardTab, tab: "market" },
    { el: els.macroDashboardTab, tab: "macro" },
    { el: els.quantLabTab, tab: "quant" },
    { el: els.quantamentalTab, tab: "quantamental" },
    { el: els.mlForecastTab, tab: "forecast" },
    { el: els.aiPortfolioTab, tab: "ai-portfolio" },
  ];
  buttons.forEach(({ el, tab: buttonTab }) => {
    if (!el) return;
    const isActive = buttonTab === active;
    el.classList.toggle("active", isActive);
    el.setAttribute("aria-selected", isActive ? "true" : "false");
  });
  updateDashboardHero(active);
  if (active === "quant") {
    loadQuantRunHistory(false);
    loadQuantStrategies(false);
  } else if (active === "quantamental") {
    loadQuantamental(false);
  } else if (active === "forecast") {
    loadForecastLab(false);
  } else if (active === "macro") {
    loadMacro(false);
  } else if (active === "ai-portfolio") {
    loadAiPortfolio(false);
  } else {
    loadMarketDashboard(false);
  }
  if (options.updateUrl && window.history?.replaceState) {
    const hash = active === "quantamental" ? "#quantamental" : (active === "quant" ? "#quant-lab" : (active === "forecast" ? "#ml-forecast" : (active === "macro" ? "#macro" : (active === "ai-portfolio" ? "#ai-portfolio" : "#market-dashboard"))));
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
  }
}

function applyUrlUiMode() {
  const params = new URLSearchParams(window.location.search);
  const requestedTab = dashboardTabFromLocation();
  if (requestedTab) setDashboardTab(requestedTab);
  else setDashboardTab(state.activeDashboardTab || "market");
  if (params.get("focus") !== "heatmap") return;
  document.body.classList.add("heatmap-focus-mode");
  setDashboardTab("market");
}

function normalizeStaticLabels() {
  document.title = "FinGPT Local Research Assistant";
  if (els.tickerHint) els.tickerHint.textContent = "ticker 없이 질의 가능, ticker는 참고 힌트";
  if (els.ticker) els.ticker.placeholder = "선택: TLT, GLD, BTC-USD";
  if (els.question) els.question.placeholder = "예: 현재 시장이 무시하는 리스크는 무엇인가요?";
  const modeLabels = {
    auto: "자동",
    ticker: "종목",
    topic: "주제",
  };
  els.researchModeInputs().forEach((input) => {
    const span = input.parentElement?.querySelector("span");
    if (span && modeLabels[input.value]) span.textContent = modeLabels[input.value];
  });
  const qHint = document.querySelector('label[for="question"] .hint');
  if (qHint) qHint.textContent = "자유 질문 또는 프리셋 선택";
  const evidenceSearch = document.getElementById("evidenceSearch");
  if (evidenceSearch) evidenceSearch.placeholder = "검색: 제목, 내용, source, doc_id";
  const homeStatus = document.querySelectorAll(".home-status span");
  if (homeStatus[0]) homeStatus[0].textContent = "OpenBB/Yahoo/FRED/SEC 중심";
  if (homeStatus[1]) homeStatus[1].textContent = "qwen2.5:7b 로컬 추론";
  setText(".market-overview-card .home-card-head h3", "시장 테이프 / 내부 스냅샷");
  setText(".home-chart-card .home-card-head h3", "TradingView 단일 차트");
  setText(".home-heatmap-card .home-card-head h3", "미국 주식 5분봉 히트맵");
  setText(".home-market-panel .home-card-head h3", "내부 시장 스냅샷 (시장 테이프에 통합)");
  setText(".data-mart-card .home-card-head h3", "데이터 마트 상태");
  if (els.marketDashboardTab) els.marketDashboardTab.textContent = "Market Dashboard";
  if (els.macroDashboardTab) els.macroDashboardTab.textContent = "Macro";
  if (els.quantLabTab) els.quantLabTab.textContent = "Quant Lab";
  if (els.quantamentalTab) els.quantamentalTab.textContent = "Quantamental";
  if (els.mlForecastTab) els.mlForecastTab.textContent = "ML Forecast";
  if (els.aiPortfolioTab) els.aiPortfolioTab.textContent = "AI Portfolio";
  setCardHeader("macroOverviewSurface", "매크로 레짐 요약", "데이터, 신호, 해석 분리");
  setCardHeader("macroCoverageSurface", "매크로 데이터 커버리지", "레지스트리, 공급자, 범주");
  setCardHeader("macroIndicatorTable", "핵심 지표", "최근값, 변화, 품질");
  setCardHeader("macroChartSurface", "매크로 차트", "관측 데이터만 표시");
  setCardHeader("macroInterestRatesSurface", "금리", "정책금리, 커브, 실질금리");
  setCardHeader("macroInflationSurface", "인플레이션", "CPI, PCE, 기대 인플레이션");
  setCardHeader("macroGrowthLaborSurface", "성장·고용", "활동, 고용, 실업수당");
  setCardHeader("macroHousingConsumerSurface", "주택·소비", "주택, 소득, 소비신용");
  setCardHeader("macroYieldCurveSurface", "수익률 곡선", "듀레이션과 역전");
  setCardHeader("macroLiquidityCreditSurface", "유동성·신용", "통화량, 연준 자산, 스프레드");
  setCardHeader("macroFinancialConditionsSurface", "금융여건", "스트레스, 대출태도, 은행신용");
  setCardHeader("macroFxDollarSurface", "FX·달러", "시장 프록시와 확장 공급자");
  setCardHeader("macroCommoditiesSurface", "원자재", "금, 에너지, 원자재 프록시");
  setCardHeader("macroRegimeSurface", "매크로 레짐", "규칙 기반 MVP");
  setCardHeader("macroAssetImpactSurface", "자산군 영향", "영향, 신뢰도, 리스크");
  setCardHeader("macroPortfolioHintsSurface", "포트폴리오 정책 힌트", "자문용 신호만 제공");
  setCardHeader("macroBriefSurface", "AI 매크로 브리프", "구조화 입력 또는 폴백");
  setCardHeader("macroDataQualitySurface", "데이터 품질", "누락, 지연, 공급자 오류");
  if (els.macroRefresh) els.macroRefresh.textContent = "데이터 새로고침";
  if (els.macroBriefGenerate) els.macroBriefGenerate.textContent = "AI 매크로 브리프 생성";
  if (els.macroReportExport) els.macroReportExport.textContent = "리포트 내보내기";
  setText(".asset-detail-card .home-card-head h3", "자산 상세");
  setText(".backtest-card .home-card-head h3", "백테스트");
  setText(".portfolio-card .home-card-head h3", "포트폴리오");
  setText(".forecast-setup-card .home-card-head h3", "ML Forecast");
  setText(".forecast-setup-card .home-card-head span", "검증 가능한 예측 실험실");
  setText(".ai-portfolio-overview-card .home-card-head h3", "AI Portfolio");
  setText(".ai-portfolio-overview-card .home-card-head span", "정책 기반 포트폴리오 관리");
  setText(".ai-portfolio-ops-card .home-card-head h3", "운영 상태");
  setText(".ai-portfolio-create-card .home-card-head h3", "Create Portfolio");
  setText(".ai-portfolio-create-card .home-card-head span", "투자형 · 유니버스 · 정책");
  setText(".ai-portfolio-recommendation-card .home-card-head span", "정량 결과 · AI 설명 분리");
  setText(".ai-portfolio-performance-card .home-card-head span", "성과 · 벤치마크 · 위험");
  setText(".ai-portfolio-compliance-card .home-card-head span", "제약조건 검사");
  setText(".ai-portfolio-rebalance-card .home-card-head span", "사용자 승인 기반");
  setText(".ai-portfolio-reports-card .home-card-head span", "성과 · 리밸런싱 리포트");
  setText(".ai-portfolio-history-card .home-card-head span", "정책 · 추천 · 신호 이력");
  if (els.aiPortfolioGenerateQuick) els.aiPortfolioGenerateQuick.textContent = "새 포트폴리오 생성";
  if (els.aiPortfolioCheckRebalanceQuick) els.aiPortfolioCheckRebalanceQuick.textContent = "리밸런싱 점검";
  if (els.aiPortfolioReportQuick) els.aiPortfolioReportQuick.textContent = "리포트 생성";
  setText(".home-news-card .home-card-head h3", "주요 뉴스");
  const runMeta = document.querySelector(".meta-row");
  if (runMeta) runMeta.innerHTML = '<span class="kbd">Ctrl</span> + <span class="kbd">Enter</span> 실행';
  applyUiLanguage(state.outputLanguage || "ko", { persist: false });
  applyUrlUiMode();
}

function showHome() {
  state.lastResponse = null;
  state.lastCollection = null;
  state.lastRequest = null;
  setExportAvailability(false);
  setFormNotice("");
  if (els.compareView) els.compareView.classList.add("hidden");
  els.loadingState.classList.add("hidden");
  els.resultView.classList.add("hidden");
  els.emptyState.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
  loadActiveDashboardResources(false);
}

function showTvFallback(el, message) {
  if (!el) return;
  if (el.dataset?.preserveContent === "true") {
    const messageEl = el.querySelector(".tv-fallback-message");
    if (messageEl) messageEl.textContent = message;
  } else {
    el.textContent = message;
  }
  el.classList.remove("hidden");
}

function hideTvFallback(el) {
  if (el) el.classList.add("hidden");
}

function tradingViewEmbedUrl(scriptSrc, config) {
  let widget = "";
  if (scriptSrc.includes("stock-heatmap")) widget = "stock-heatmap";
  else if (scriptSrc.includes("advanced-chart")) widget = "advanced-chart";
  if (!widget) return "";
  const locale = config.locale || "kr";
  const payload = encodeURIComponent(JSON.stringify(config));
  return `https://s.tradingview.com/embed-widget/${widget}/?locale=${encodeURIComponent(locale)}#${payload}`;
}

function mountTradingViewIframe(container, scriptSrc, config, label) {
  const url = tradingViewEmbedUrl(scriptSrc, config);
  if (!url) return false;
  container.innerHTML = "";
  const iframe = document.createElement("iframe");
  iframe.title = label;
  iframe.src = url;
  iframe.loading = "eager";
  iframe.referrerPolicy = "origin";
  iframe.allow = "clipboard-write; encrypted-media; fullscreen";
  iframe.setAttribute("allowfullscreen", "true");
  iframe.style.width = "100%";
  iframe.style.height = "100%";
  iframe.style.border = "0";
  container.appendChild(iframe);
  return true;
}

function mountTradingViewWidget(container, fallback, scriptSrc, config, label) {
  if (!container) return;
  hideTvFallback(fallback);
  const iframeMounted = mountTradingViewIframe(container, scriptSrc, config, label);
  if (!iframeMounted) {
    container.dataset.tvStatus = "failed";
    showTvFallback(fallback, `${label} 로드에 실패했습니다. 아래 내부 시장 스냅샷을 기준으로 확인하세요.`);
    return;
  }
  container.dataset.tvStatus = "iframe-loading";
  const frame = container.querySelector("iframe");
  if (frame) {
    frame.addEventListener("load", () => {
      container.dataset.tvStatus = "ready";
      hideTvFallback(fallback);
    }, { once: true });
  }

  window.setTimeout(() => {
    if (container.dataset.tvStatus === "ready") return;
    container.dataset.tvStatus = "iframe-fallback";
    showTvFallback(fallback, `${label}는 직접 iframe 경로로 로드 중입니다. 외부 네트워크가 느리면 내부 시장 스냅샷을 함께 확인하세요.`);
  }, 6000);
}

function normalizeTvChartSettings(raw = {}) {
  const source = raw.source === "tradingview" ? "tradingview" : raw.source === "internal" ? "internal" : TV_CHART_DEFAULTS.source;
  const symbolKey = TV_CHART_SYMBOLS[raw.symbolKey] ? raw.symbolKey : TV_CHART_DEFAULTS.symbolKey;
  const interval = TV_CHART_INTERVALS[raw.interval] ? raw.interval : TV_CHART_DEFAULTS.interval;
  let compareKey = TV_CHART_SYMBOLS[raw.compareKey] ? raw.compareKey : "";
  if (compareKey === symbolKey) compareKey = "";
  return { source, symbolKey, interval, compareKey };
}

function tvChartMeta(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  const symbolLabel = TV_CHART_SYMBOLS[safe.symbolKey]?.label || safe.symbolKey;
  const intervalLabel = TV_CHART_INTERVALS[safe.interval] || safe.interval;
  const sourceLabel = safe.source === "internal" ? `Internal ${intervalLabel} data` : intervalLabel;
  const compareLabel = safe.compareKey ? ` · vs ${safe.compareKey}` : "";
  return `${symbolLabel} · ${sourceLabel}${compareLabel}`;
}

function syncTvChartControls(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  if (els.tvChartSource) els.tvChartSource.value = safe.source;
  if (els.tvChartSymbol) els.tvChartSymbol.value = safe.symbolKey;
  if (els.tvChartInterval) els.tvChartInterval.value = safe.interval;
  if (els.tvChartCompare) els.tvChartCompare.value = safe.compareKey;
  if (els.tvOverviewMeta) els.tvOverviewMeta.textContent = tvChartMeta(safe);
}

function tvChartSettingsFromControls() {
  return normalizeTvChartSettings({
    source: els.tvChartSource?.value || state.tvChartSettings?.source,
    symbolKey: els.tvChartSymbol?.value || state.tvChartSettings?.symbolKey,
    interval: els.tvChartInterval?.value || state.tvChartSettings?.interval,
    compareKey: els.tvChartCompare?.value || "",
  });
}

function tradingViewVisualTheme() {
  return document.documentElement.dataset.theme === "light"
    ? {
      theme: "light",
      backgroundColor: "rgba(248, 250, 252, 1)",
      gridColor: "rgba(148, 163, 184, 0.22)",
    }
    : {
      theme: "dark",
      backgroundColor: "rgba(15, 23, 42, 1)",
      gridColor: "rgba(51, 65, 85, 0.35)",
    };
}

function tradingViewOverviewConfig(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  const visual = tradingViewVisualTheme();
  const config = {
    autosize: true,
    symbol: TV_CHART_SYMBOLS[safe.symbolKey].symbol,
    interval: safe.interval,
    timezone: "Etc/UTC",
    theme: visual.theme,
    style: "1",
    locale: selectedOutputLanguage() === "en" ? "en" : "kr",
    backgroundColor: visual.backgroundColor,
    gridColor: visual.gridColor,
    hide_top_toolbar: false,
    allow_symbol_change: true,
    save_image: false,
    calendar: false,
    height: "420",
    width: "100%",
    support_host: "https://www.tradingview.com",
  };
  if (safe.compareKey) {
    config.compareSymbols = [{ symbol: TV_CHART_SYMBOLS[safe.compareKey].symbol, position: "SameScale" }];
  }
  return config;
}

function normalizeInternalChartRows(payload) {
  return (Array.isArray(payload?.items) ? payload.items : [])
    .map((row) => {
      const close = priceValue(row);
      const open = numericOrFallback(row.open, close);
      const high = numericOrFallback(row.high, Math.max(open, close));
      const low = numericOrFallback(row.low, Math.min(open, close));
      return {
        date: row.date || "",
        open,
        high,
        low,
        close,
        volume: numericOrFallback(row.volume, null),
        source: row.source || "",
      };
    })
    .filter((row) => row.date && Number.isFinite(row.close));
}

function internalChartReturnRows(rows) {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => ({ date: row.date || "", value: Number(row.close) }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  if (values.length < 2) return [];
  const base = values[0].value || 1;
  return values.map((row) => ({ date: row.date, value: row.value / base }));
}

function internalIntradayApiInterval(interval) {
  if (interval === "15") return "15m";
  if (interval === "60") return "60m";
  return "5m";
}

function internalOhlcBucketKey(dateValue, interval) {
  const raw = String(dateValue || "");
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw.slice(0, interval === "M" ? 7 : 10);
  if (interval === "M") {
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
  }
  if (interval === "W") {
    const day = date.getUTCDay() || 7;
    const monday = new Date(date);
    monday.setUTCDate(date.getUTCDate() - day + 1);
    return monday.toISOString().slice(0, 10);
  }
  return raw;
}

function aggregateInternalOhlcRows(rows, interval) {
  if (!["W", "M"].includes(interval)) return rows;
  const buckets = new Map();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const close = priceValue(row);
    if (close === null) return;
    const key = internalOhlcBucketKey(row.date, interval);
    const open = numericOrFallback(row.open, close);
    const high = numericOrFallback(row.high, Math.max(open, close));
    const low = numericOrFallback(row.low, Math.min(open, close));
    const volume = numericOrFallback(row.volume, 0);
    const existing = buckets.get(key);
    if (!existing) {
      buckets.set(key, {
        date: row.date || key,
        open,
        high,
        low,
        close,
        adjusted_close: close,
        volume: Number.isFinite(volume) ? volume : null,
        source: row.source || "data_mart:prices_daily",
      });
      return;
    }
    existing.date = row.date || existing.date;
    existing.high = Math.max(Number(existing.high), high);
    existing.low = Math.min(Number(existing.low), low);
    existing.close = close;
    existing.adjusted_close = close;
    if (Number.isFinite(volume) && existing.volume !== null) existing.volume += volume;
  });
  return Array.from(buckets.values());
}

async function fetchInternalChartPayload(symbolKey, interval) {
  const symbolInfo = TV_CHART_SYMBOLS[symbolKey];
  const ticker = symbolInfo?.dataTicker || symbolKey;
  const useIntraday = TV_INTERNAL_INTRADAY_INTERVALS.has(interval);
  const res = await fetch(useIntraday
    ? API.dashboardIntraday(ticker, internalIntradayApiInterval(interval), 500)
    : API.dataPrices(ticker, 520));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const payload = await res.json();
  if (!useIntraday && ["W", "M"].includes(interval)) {
    return {
      ...payload,
      interval,
      source: `${payload.source || "data_mart:prices_daily"}_${interval.toLowerCase()}_aggregate`,
      items: aggregateInternalOhlcRows(payload.items || [], interval),
    };
  }
  return payload;
}

function renderInternalOhlcChart(primaryPayload, comparePayload, settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  const allPrimaryRows = normalizeInternalChartRows(primaryPayload);
  const primaryRows = allPrimaryRows;
  if (primaryRows.length < 2) {
    return decisionEmpty(`내부 가격 데이터가 부족합니다: ${TV_CHART_SYMBOLS[safe.symbolKey]?.dataTicker || safe.symbolKey}`);
  }
  const hasOhlc = primaryRows.some((row) => Number.isFinite(row.open) && Number.isFinite(row.high) && Number.isFinite(row.low));
  const width = Math.max(980, Math.min(5600, primaryRows.length * 8 + 150));
  const height = 390;
  const padLeft = 72;
  const padRight = 56;
  const padTop = 24;
  const padBottom = 44;
  const domainValues = primaryRows.flatMap((row) => [
    Number.isFinite(row.high) ? row.high : row.close,
    Number.isFinite(row.low) ? row.low : row.close,
    row.close,
  ]);
  const { min, max } = paddedChartDomain(domainValues);
  const points = primaryRows.map((row, index) => {
    const x = padLeft + (index / Math.max(1, primaryRows.length - 1)) * (width - padLeft - padRight);
    return {
      ...row,
      x,
      openY: chartY(min, max, row.open, height, padTop, padBottom),
      highY: chartY(min, max, row.high, height, padTop, padBottom),
      lowY: chartY(min, max, row.low, height, padTop, padBottom),
      closeY: chartY(min, max, row.close, height, padTop, padBottom),
    };
  });
  const candleWidth = Math.max(2.8, Math.min(7.5, (width - padLeft - padRight) / Math.max(points.length, 1) * 0.46));
  const candles = points.map((point) => {
    const up = point.close >= point.open;
    const bodyTop = Math.min(point.openY, point.closeY);
    const bodyHeight = Math.max(1.4, Math.abs(point.closeY - point.openY));
    const tooltip = `${point.date} · O ${fmtDecimal(point.open, 2)} · H ${fmtDecimal(point.high, 2)} · L ${fmtDecimal(point.low, 2)} · C ${fmtDecimal(point.close, 2)}`;
    return hasOhlc ? `
      <g class="internal-candle ${up ? "up" : "down"}" data-chart-tooltip="${escapeHtml(tooltip)}">
        <line x1="${point.x.toFixed(2)}" x2="${point.x.toFixed(2)}" y1="${point.highY.toFixed(2)}" y2="${point.lowY.toFixed(2)}"></line>
        <rect x="${(point.x - candleWidth / 2).toFixed(2)}" y="${bodyTop.toFixed(2)}" width="${candleWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1.4"></rect>
        <title>${escapeHtml(tooltip)}</title>
      </g>
    ` : "";
  }).join("");
  const closePoints = svgPolylinePoints(points.map((point) => ({ ...point, y: point.closeY })));
  const first = primaryRows[0];
  const last = primaryRows[primaryRows.length - 1];
  const returnPct = first.close ? (last.close / first.close - 1) * 100 : null;
  const returnClass = Number(returnPct) >= 0 ? "ok" : "warn";
  const compareRows = normalizeInternalChartRows(comparePayload).slice(-primaryRows.length);
  const compareChart = safe.compareKey && compareRows.length >= 2
    ? renderNormalizedComparisonChart({
      primary: internalChartReturnRows(primaryRows),
      benchmark: internalChartReturnRows(compareRows),
      primaryLabel: safe.symbolKey,
      benchmarkLabel: safe.compareKey,
      title: "내부 데이터 상대 수익률 비교",
      status: "ok",
    })
    : "";
  return `
    <div class="internal-chart-shell" data-testid="internal-market-chart">
      <div class="internal-chart-head">
        <div>
          <strong>${escapeHtml(TV_CHART_SYMBOLS[safe.symbolKey]?.label || safe.symbolKey)}</strong>
          <span>${escapeHtml(first.date)} -> ${escapeHtml(last.date)} · ${escapeHtml(String(primaryRows.length))} rows · ${escapeHtml(last.source || primaryPayload?.latest?.source || "data mart")}</span>
        </div>
        <b class="${escapeHtml(returnClass)}">${escapeHtml(returnPct === null ? "-" : fmtPct(returnPct))}</b>
      </div>
      <div class="internal-chart-scroll" tabindex="0" aria-label="Internal chart horizontal scroll">
        <svg class="internal-ohlc-chart" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(safe.symbolKey)} internal OHLC chart">
          ${renderChartYAxis({
            width,
            height,
            padLeft,
            padRight,
            padTop,
            padBottom,
            min,
            max,
            formatter: (value) => fmtDecimal(value, Math.abs(value) >= 100 ? 0 : 2),
          })}
          ${candles}
          <polyline points="${closePoints}" class="internal-close-line"></polyline>
          ${renderChartHoverTargets(points.map((point) => ({ ...point, y: point.closeY, value: point.close })), (point) => `${point.date || "-"} · Close ${fmtDecimal(point.value, 2)}`)}
        </svg>
      </div>
      <div class="internal-chart-hint">좌우 스크롤로 전체 내부 데이터 구간을 확인할 수 있습니다. 최신 구간은 오른쪽 끝입니다.</div>
      <div class="internal-chart-foot">
        <span>Open ${escapeHtml(fmtDecimal(last.open, 2))}</span>
        <span>High ${escapeHtml(fmtDecimal(Math.max(...primaryRows.map((row) => row.high)), 2))}</span>
        <span>Low ${escapeHtml(fmtDecimal(Math.min(...primaryRows.map((row) => row.low)), 2))}</span>
        <span>Close ${escapeHtml(fmtDecimal(last.close, 2))}</span>
      </div>
      ${compareChart}
    </div>
  `;
}

function scrollInternalChartToLatest() {
  const scroller = els.tvOverviewWidget?.querySelector?.(".internal-chart-scroll");
  if (!scroller) return;
  window.requestAnimationFrame(() => {
    scroller.scrollLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth);
  });
}

async function mountInternalMarketChart(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  const symbolInfo = TV_CHART_SYMBOLS[safe.symbolKey];
  if (!els.tvOverviewWidget || !symbolInfo) return;
  state.tvChartSettings = safe;
  syncTvChartControls(safe);
  hideTvFallback(els.tvOverviewFallback);
  els.tvOverviewWidget.dataset.tvStatus = "internal-loading";
  els.tvOverviewWidget.innerHTML = '<div class="home-news-empty">내부 가격 차트를 불러오는 중입니다.</div>';
  try {
    const primaryPromise = fetchInternalChartPayload(safe.symbolKey, safe.interval);
    const comparePromise = safe.compareKey ? fetchInternalChartPayload(safe.compareKey, safe.interval) : Promise.resolve(null);
    const [primaryPayload, comparePayload] = await Promise.all([primaryPromise, comparePromise]);
    els.tvOverviewWidget.innerHTML = renderInternalOhlcChart(primaryPayload, comparePayload, safe);
    scrollInternalChartToLatest();
    els.tvOverviewWidget.dataset.tvStatus = normalizeInternalChartRows(primaryPayload).length >= 2 ? "internal-ready" : "internal-empty";
  } catch (err) {
    els.tvOverviewWidget.dataset.tvStatus = "internal-failed";
    els.tvOverviewWidget.innerHTML = `<div class="home-news-empty">내부 가격 차트 로드 실패: ${escapeHtml(err.message || err)}</div>`;
  }
}

function mountMarketOverviewChart(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  if (safe.source === "internal") {
    mountInternalMarketChart(safe);
    return;
  }
  mountTradingViewOverview(safe);
}

function mountTradingViewOverview(settings = state.tvChartSettings) {
  const safe = normalizeTvChartSettings(settings);
  state.tvChartSettings = safe;
  syncTvChartControls(safe);
  mountTradingViewWidget(
    els.tvOverviewWidget,
    els.tvOverviewFallback,
    TV_ADVANCED_CHART_SCRIPT,
    tradingViewOverviewConfig(safe),
    "TradingView 단일 차트"
  );
}

function applyTvChartSettings(settings = tvChartSettingsFromControls(), options = {}) {
  const safe = normalizeTvChartSettings(settings);
  state.tvChartSettings = safe;
  if (options.persist !== false) {
    safeWriteStoredJson(STORAGE.tvChart, safe);
  }
  state.tradingViewInitialized = true;
  mountMarketOverviewChart(safe);
}

function bindTvChartControls() {
  syncTvChartControls(state.tvChartSettings);
  if (els.tvChartApply) {
    els.tvChartApply.addEventListener("click", () => applyTvChartSettings(tvChartSettingsFromControls()));
  }
  [els.tvChartSource, els.tvChartSymbol, els.tvChartInterval, els.tvChartCompare].forEach((control) => {
    if (!control) return;
    if (control === els.tvChartSource) {
      control.addEventListener("change", () => syncTvChartControls(tvChartSettingsFromControls()));
    }
    control.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyTvChartSettings(tvChartSettingsFromControls());
      }
    });
  });
}

function initializeTradingViewDashboard(force = false) {
  if (state.tradingViewInitialized && !force) return;
  state.tradingViewInitialized = true;
  mountMarketOverviewChart(state.tvChartSettings);
  mountTradingViewWidget(
    els.tvHeatmapWidget,
    els.tvHeatmapFallback,
    "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
    {
      exchanges: [],
      dataSource: "SPX500",
      grouping: "sector",
      blockSize: "market_cap_basic",
      blockColor: "change",
      locale: selectedOutputLanguage() === "en" ? "en" : "kr",
      symbolUrl: "",
      colorTheme: "dark",
      hasTopBar: false,
      isDataSetEnabled: false,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      isMonoSize: false,
      width: "100%",
      height: "100%",
      support_host: "https://www.tradingview.com",
    },
    "TradingView 주식 히트맵"
  );
}

function fmtPct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function heatColor(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "rgb(55, 65, 81)";
  const intensity = Math.min(Math.abs(n) / 3.0, 1);
  if (Math.abs(n) < 0.08) return "rgb(64, 70, 82)";
  if (n > 0) {
    const r = Math.round(28 + intensity * 20);
    const g = Math.round(116 + intensity * 86);
    const b = Math.round(65 + intensity * 44);
    return `rgb(${r}, ${g}, ${b})`;
  }
  const r = Math.round(116 + intensity * 112);
  const g = Math.round(58 - intensity * 8);
  const b = Math.round(70 - intensity * 16);
  return `rgb(${r}, ${g}, ${b})`;
}

function weightedSectorChange(items) {
  let totalWeight = 0;
  let weighted = 0;
  items.forEach((item) => {
    const change = Number(item.change_pct);
    const weight = Math.max(0.2, Number(item.weight) || 1);
    if (!Number.isFinite(change)) return;
    totalWeight += weight;
    weighted += change * weight;
  });
  return totalWeight ? weighted / totalWeight : null;
}

function sectorBreadth(items) {
  const usable = Array.isArray(items) ? items : [];
  const up = usable.filter((item) => Number(item.change_pct) >= 0).length;
  const down = usable.filter((item) => Number(item.change_pct) < 0).length;
  return { up, down, total: usable.length };
}

function heatmapWeight(item) {
  const weight = Number(item?.weight);
  return Number.isFinite(weight) && weight > 0 ? Math.max(weight, 0.2) : 1;
}

function heatmapLayoutWeight(item) {
  return Math.pow(Math.max(heatmapWeight(item), 0.45), 0.82);
}

function heatmapTicker(item) {
  return String(item?.symbol || "").trim().toUpperCase();
}

function fallbackHeatmapClassification(item) {
  const rawSector = String(item?.sector || "").toUpperCase();
  const rawIndustry = String(item?.industry || "").toUpperCase();
  if (HEATMAP_SECTOR_ORDER.includes(rawSector)) {
    return { sector: rawSector, industry: rawIndustry || rawSector };
  }
  if (rawSector.includes("TECH") || rawSector.includes("전자") || rawSector.includes("테크")) {
    return { sector: "TECHNOLOGY", industry: rawIndustry || "INFORMATION TECHNOLOGY" };
  }
  if (rawSector.includes("FIN") || rawSector.includes("금융")) {
    return { sector: "FINANCIAL", industry: rawIndustry || "FINANCIAL SERVICES" };
  }
  if (rawSector.includes("HEALTH") || rawSector.includes("의료") || rawSector.includes("헬스")) {
    return { sector: "HEALTHCARE", industry: rawIndustry || "HEALTHCARE" };
  }
  if (rawSector.includes("ENERGY") || rawSector.includes("에너지")) {
    return { sector: "ENERGY", industry: rawIndustry || "ENERGY" };
  }
  if (rawSector.includes("INDUSTR") || rawSector.includes("제조")) {
    return { sector: "INDUSTRIALS", industry: rawIndustry || "INDUSTRIALS" };
  }
  if (rawSector.includes("CONSUMER") || rawSector.includes("소비")) {
    return { sector: "CONSUMER CYCLICAL", industry: rawIndustry || "CONSUMER SERVICES" };
  }
  return { sector: "OTHER", industry: rawIndustry || (item?.sector ? String(item.sector).toUpperCase() : "UNCATEGORIZED") };
}

function heatmapProfile(item) {
  const backendProfile = fallbackHeatmapClassification(item);
  const staticProfile = HEATMAP_CLASSIFICATION[heatmapTicker(item)];
  if (HEATMAP_SECTOR_ORDER.includes(backendProfile.sector) && item?.industry) return backendProfile;
  return staticProfile || backendProfile;
}

function heatmapSectorRank(sector) {
  const idx = HEATMAP_SECTOR_ORDER.indexOf(sector);
  return idx >= 0 ? idx : HEATMAP_SECTOR_ORDER.length;
}

function heatmapRectStyle(rect) {
  return [
    `left:${Math.max(0, rect.x).toFixed(4)}%`,
    `top:${Math.max(0, rect.y).toFixed(4)}%`,
    `width:${Math.max(0, rect.w).toFixed(4)}%`,
    `height:${Math.max(0, rect.h).toFixed(4)}%`,
  ].join("; ");
}

function treemapWorst(row, side) {
  if (!row.length || side <= 0) return Number.POSITIVE_INFINITY;
  const areas = row.map((entry) => Math.max(0.0001, entry.area));
  const sum = areas.reduce((total, area) => total + area, 0);
  const min = Math.min(...areas);
  const max = Math.max(...areas);
  const sideSq = side * side;
  return Math.max((sideSq * max) / (sum * sum), (sum * sum) / (sideSq * min));
}

function layoutTreemapRow(row, rect, output) {
  const rowArea = row.reduce((sum, entry) => sum + entry.area, 0);
  if (rowArea <= 0 || rect.w <= 0 || rect.h <= 0) return rect;
  if (rect.w >= rect.h) {
    const rowHeight = Math.min(rect.h, rowArea / rect.w);
    let x = rect.x;
    row.forEach((entry, index) => {
      const width = index === row.length - 1
        ? rect.x + rect.w - x
        : Math.min(rect.x + rect.w - x, entry.area / rowHeight);
      output.push({ item: entry.item, x, y: rect.y, w: width, h: rowHeight });
      x += width;
    });
    return { x: rect.x, y: rect.y + rowHeight, w: rect.w, h: Math.max(0, rect.h - rowHeight) };
  }
  const columnWidth = Math.min(rect.w, rowArea / rect.h);
  let y = rect.y;
  row.forEach((entry, index) => {
    const height = index === row.length - 1
      ? rect.y + rect.h - y
      : Math.min(rect.y + rect.h - y, entry.area / columnWidth);
    output.push({ item: entry.item, x: rect.x, y, w: columnWidth, h: height });
    y += height;
  });
  return { x: rect.x + columnWidth, y: rect.y, w: Math.max(0, rect.w - columnWidth), h: rect.h };
}

function squarifyTreemap(entries, rect, valueFn) {
  const totalValue = entries.reduce((sum, entry) => {
    const value = Number(valueFn(entry));
    return sum + (Number.isFinite(value) && value > 0 ? value : 0);
  }, 0);
  if (!entries.length || totalValue <= 0 || rect.w <= 0 || rect.h <= 0) return [];
  const areaScale = (rect.w * rect.h) / totalValue;
  const queue = entries
    .map((entry) => {
      const value = Math.max(0.0001, Number(valueFn(entry)) || 0.0001);
      return { item: entry, area: value * areaScale };
    })
    .sort((a, b) => b.area - a.area);
  const output = [];
  let row = [];
  let remaining = { ...rect };
  while (queue.length) {
    const next = queue[0];
    const side = Math.min(remaining.w, remaining.h);
    if (!row.length || treemapWorst([...row, next], side) <= treemapWorst(row, side)) {
      row.push(next);
      queue.shift();
    } else {
      remaining = layoutTreemapRow(row, remaining, output);
      row = [];
    }
  }
  if (row.length) layoutTreemapRow(row, remaining, output);
  return output;
}

function squarifyTreemapPercent(entries, aspectRatio, valueFn) {
  const aspect = Math.min(Math.max(Number(aspectRatio) || 1, 0.2), 6);
  const layoutRect = aspect >= 1
    ? { x: 0, y: 0, w: 100 * aspect, h: 100 }
    : { x: 0, y: 0, w: 100, h: 100 / aspect };
  return squarifyTreemap(entries, layoutRect, valueFn).map(({ item, x, y, w, h }) => ({
    item,
    x: (x / layoutRect.w) * 100,
    y: (y / layoutRect.h) * 100,
    w: (w / layoutRect.w) * 100,
    h: (h / layoutRect.h) * 100,
  }));
}

function heatmapCanvasAspect() {
  const width = Number(els.homeHeatmap?.clientWidth || 0);
  const height = Number(els.homeHeatmap?.clientHeight || 0);
  if (width > 0 && height > 0) return width / height;
  return 1.85;
}

function heatmapTileSize(rect, sectorRect, industryRect) {
  const globalW = (sectorRect.w * industryRect.w * rect.w) / 10000;
  const globalH = (sectorRect.h * industryRect.h * rect.h) / 10000;
  const area = globalW * globalH;
  if (globalW >= 10 && globalH >= 15 && area >= 180) return "mega";
  if (globalW >= 7 && globalH >= 10 && area >= 80) return "xl";
  if (globalW >= 4.2 && globalH >= 6 && area >= 34) return "lg";
  if (globalW >= 2.6 && globalH >= 4 && area >= 14) return "md";
  if (globalW >= 1.6 && globalH >= 2.5 && area >= 5) return "sm";
  return "xs";
}

function fmtHeatmapAsOf(value) {
  if (!value) return "기준시각 미확인";
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      timeZone: "America/New_York",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  } catch (_) {
    return String(value);
  }
}

const FRESHNESS_LABELS = {
  fresh: "정상",
  delayed: "지연",
  stale: "지연 초과",
  stale_prior_close: "전일 기준",
  closed: "장마감",
  unknown: "미확인",
};

const HEATMAP_SECTOR_ORDER = [
  "TECHNOLOGY",
  "COMMUNICATION SERVICES",
  "CONSUMER CYCLICAL",
  "CONSUMER DEFENSIVE",
  "FINANCIAL",
  "HEALTHCARE",
  "INDUSTRIALS",
  "ENERGY",
  "UTILITIES",
  "REAL ESTATE",
  "BASIC MATERIALS",
  "OTHER",
];

const HEATMAP_SECTOR_ZONES = {
  TECHNOLOGY: { x: 0, y: 0, w: 45, h: 70 },
  FINANCIAL: { x: 0, y: 70, w: 45, h: 30 },
  "CONSUMER CYCLICAL": { x: 45, y: 0, w: 35, h: 30 },
  "COMMUNICATION SERVICES": { x: 45, y: 30, w: 35, h: 38 },
  HEALTHCARE: { x: 45, y: 68, w: 35, h: 32 },
  "CONSUMER DEFENSIVE": { x: 80, y: 0, w: 20, h: 30 },
  INDUSTRIALS: { x: 80, y: 30, w: 20, h: 31 },
  "REAL ESTATE": { x: 80, y: 61, w: 10, h: 18 },
  UTILITIES: { x: 90, y: 61, w: 10, h: 18 },
  ENERGY: { x: 80, y: 79, w: 12, h: 21 },
  "BASIC MATERIALS": { x: 92, y: 79, w: 8, h: 21 },
  OTHER: { x: 92, y: 61, w: 8, h: 18 },
};

const HEATMAP_DISPLAY_MAX = 96;
const HEATMAP_DISPLAY_MIN = 24;

const HEATMAP_CLASSIFICATION = {
  MSFT: { sector: "TECHNOLOGY", industry: "SOFTWARE - INFRASTRUCTURE" },
  ORCL: { sector: "TECHNOLOGY", industry: "SOFTWARE - INFRASTRUCTURE" },
  CRM: { sector: "TECHNOLOGY", industry: "SOFTWARE - APPLICATION" },
  AAPL: { sector: "TECHNOLOGY", industry: "CONSUMER ELECTRONICS" },
  NVDA: { sector: "TECHNOLOGY", industry: "SEMICONDUCTORS" },
  AVGO: { sector: "TECHNOLOGY", industry: "SEMICONDUCTORS" },
  AMD: { sector: "TECHNOLOGY", industry: "SEMICONDUCTORS" },
  MU: { sector: "TECHNOLOGY", industry: "SEMICONDUCTORS" },
  QCOM: { sector: "TECHNOLOGY", industry: "SEMICONDUCTORS" },
  CSCO: { sector: "TECHNOLOGY", industry: "COMMUNICATION EQUIPMENT" },
  GOOGL: { sector: "COMMUNICATION SERVICES", industry: "INTERNET CONTENT & INFORMATION" },
  META: { sector: "COMMUNICATION SERVICES", industry: "INTERNET CONTENT & INFORMATION" },
  NFLX: { sector: "COMMUNICATION SERVICES", industry: "ENTERTAINMENT" },
  AMZN: { sector: "CONSUMER CYCLICAL", industry: "INTERNET RETAIL" },
  TSLA: { sector: "CONSUMER CYCLICAL", industry: "AUTO MANUFACTURERS" },
  HD: { sector: "CONSUMER CYCLICAL", industry: "HOME IMPROVEMENT" },
  MCD: { sector: "CONSUMER CYCLICAL", industry: "RESTAURANTS" },
  BKNG: { sector: "CONSUMER CYCLICAL", industry: "TRAVEL SERVICES" },
  WMT: { sector: "CONSUMER DEFENSIVE", industry: "DISCOUNT STORES" },
  COST: { sector: "CONSUMER DEFENSIVE", industry: "DISCOUNT STORES" },
  PG: { sector: "CONSUMER DEFENSIVE", industry: "HOUSEHOLD & PERSONAL PRODUCTS" },
  KO: { sector: "CONSUMER DEFENSIVE", industry: "BEVERAGES - NON-ALCOHOLIC" },
  PEP: { sector: "CONSUMER DEFENSIVE", industry: "BEVERAGES - NON-ALCOHOLIC" },
  "BRK-B": { sector: "FINANCIAL", industry: "INSURANCE - DIVERSIFIED" },
  JPM: { sector: "FINANCIAL", industry: "BANKS - DIVERSIFIED" },
  BAC: { sector: "FINANCIAL", industry: "BANKS - DIVERSIFIED" },
  V: { sector: "FINANCIAL", industry: "CREDIT SERVICES" },
  MA: { sector: "FINANCIAL", industry: "CREDIT SERVICES" },
  LLY: { sector: "HEALTHCARE", industry: "DRUG MANUFACTURERS - GENERAL" },
  JNJ: { sector: "HEALTHCARE", industry: "DRUG MANUFACTURERS - GENERAL" },
  ABBV: { sector: "HEALTHCARE", industry: "DRUG MANUFACTURERS - GENERAL" },
  UNH: { sector: "HEALTHCARE", industry: "HEALTHCARE PLANS" },
  XOM: { sector: "ENERGY", industry: "OIL & GAS INTEGRATED" },
  CVX: { sector: "ENERGY", industry: "OIL & GAS INTEGRATED" },
  CAT: { sector: "INDUSTRIALS", industry: "FARM & HEAVY CONSTRUCTION" },
  GE: { sector: "INDUSTRIALS", industry: "AEROSPACE & DEFENSE" },
  RTX: { sector: "INDUSTRIALS", industry: "AEROSPACE & DEFENSE" },
};

function isDecisionUsableMarketItem(item) {
  if (!item) return false;
  if (item.is_decision_usable === false) return false;
  const status = item.freshness_status || "unknown";
  return item.status === "ok" && ["fresh", "delayed", "closed"].includes(status);
}

function renderHomeHeatmap(items, meta = {}) {
  if (!els.homeHeatmap) return;
  const usable = Array.isArray(items) ? items.filter(isDecisionUsableMarketItem) : [];
  if (!usable.length) {
    els.homeHeatmap.classList.remove("finviz-treemap");
    els.homeHeatmap.innerHTML = `
      <div class="home-news-empty">
        장중 최신/지연 intraday 데이터가 없어 히트맵을 숨겼습니다.<br>
        전일 기준 데이터는 의사결정용으로 표시하지 않습니다.
      </div>
    `;
    if (els.homeHeatmapMeta) {
      const stale = Number(meta.stale_or_unavailable_count || 0);
      els.homeHeatmapMeta.textContent = stale
        ? `${stale}개 종목이 stale 또는 unavailable 상태입니다. 새로고침으로 5분봉 데이터를 다시 확인하세요.`
        : "intraday 가격 데이터를 확인하지 못했습니다.";
    }
    return;
  }
  const displayTarget = Math.max(
    HEATMAP_DISPLAY_MIN,
    Math.min(HEATMAP_DISPLAY_MAX, Math.ceil(usable.length / 2)),
  );
  const displayItems = usable
    .slice()
    .sort((a, b) => {
      const weightDiff = heatmapWeight(b) - heatmapWeight(a);
      if (weightDiff) return weightDiff;
      return Math.abs(Number(b.change_pct || 0)) - Math.abs(Number(a.change_pct || 0));
    })
    .slice(0, displayTarget);
  const counts = meta.freshness_counts || {};
  const staleTotal = (counts.stale_prior_close || 0) + (counts.stale || 0) + (counts.unknown || 0);
  const latest = meta.latest_as_of ? fmtHeatmapAsOf(meta.latest_as_of) : "미확인";
  if (els.homeHeatmapMeta) {
    els.homeHeatmapMeta.innerHTML = `
      <span>최신 기준시각: ${escapeHtml(latest)} ET</span>
      <span>${escapeHtml(meta.interval || "5m")} intraday</span>
      <span>${escapeHtml(meta.provider || "yfinance")}</span>
      <span>표시 ${escapeHtml(_fmtNumber(displayItems.length))}/${escapeHtml(_fmtNumber(usable.length))}</span>
      ${staleTotal ? `<strong class="stale">제외: ${staleTotal}개 stale</strong>` : '<strong>신선도 정상</strong>'}
    `;
  }
  const profiledItems = displayItems.map((item) => ({ ...item, heatmap_profile: heatmapProfile(item) }));
  const bySector = new Map();
  profiledItems.forEach((item) => {
    const key = item.heatmap_profile.sector || "OTHER";
    if (!bySector.has(key)) bySector.set(key, []);
    bySector.get(key).push(item);
  });
  const sectors = Array.from(bySector.entries())
    .map(([sector, sectorItems]) => [sector, sectorItems.sort((a, b) => (Number(b.weight) || 0) - (Number(a.weight) || 0))])
    .sort((a, b) => {
      const rankDiff = heatmapSectorRank(a[0]) - heatmapSectorRank(b[0]);
      if (rankDiff) return rankDiff;
      return b[1].reduce((sum, row) => sum + heatmapWeight(row), 0) - a[1].reduce((sum, row) => sum + heatmapWeight(row), 0);
    });
  els.homeHeatmap.classList.add("finviz-treemap");
  const canvasAspect = heatmapCanvasAspect();
  const sectorMarkup = sectors.map(([sector, sectorItems]) => {
    const sectorRect = HEATMAP_SECTOR_ZONES[sector] || HEATMAP_SECTOR_ZONES.OTHER;
    const sectorAspect = Math.max(0.2, (sectorRect.w * canvasAspect) / Math.max(sectorRect.h, 1));
    const sectorChange = weightedSectorChange(sectorItems);
    const sectorCls = Number.isFinite(Number(sectorChange)) ? (Number(sectorChange) >= 0 ? "up" : "down") : "muted";
    const sectorChangeText = Number.isFinite(Number(sectorChange)) ? fmtPct(sectorChange) : "-";
    const breadth = sectorBreadth(sectorItems);
    const itemRects = squarifyTreemapPercent(sectorItems, sectorAspect, heatmapLayoutWeight);
    return `
    <section class="finviz-sector stock-heatmap-sector ${sectorCls}" style="${heatmapRectStyle(sectorRect)}">
      <div class="finviz-sector-title stock-sector-title">
        <div>
          <strong>${escapeHtml(sector)}</strong>
          <small>${breadth.up} 상승 · ${breadth.down} 하락</small>
        </div>
        <span class="${sectorCls}">${escapeHtml(sectorChangeText)}</span>
      </div>
      <div class="finviz-sector-body finviz-sector-tiles">
        ${itemRects.map(({ item, ...tileRect }) => {
          const change = item.change_pct;
          const cls = Number(change) >= 0 ? "up" : "down";
          const freshness = item.freshness_status || "unknown";
          const tileSize = heatmapTileSize(tileRect, sectorRect, { x: 0, y: 0, w: 100, h: 100 });
          const industry = item.heatmap_profile?.industry || item.industry || "";
          const title = `${item.symbol} ${item.label || ""} ${fmtPct(change)} · ${industry} · ${fmtHeatmapAsOf(item.as_of)} ET · ${FRESHNESS_LABELS[freshness] || freshness}`;
          return `
            <article class="finviz-heatmap-tile stock-heatmap-tile ${cls} ${freshness} size-${tileSize}" style="${heatmapRectStyle(tileRect)}; --heat-bg:${heatColor(change)}" title="${escapeHtml(title)}">
              <div class="stock-heatmap-main">
                <span class="stock-heatmap-symbol">${escapeHtml(item.symbol || "")}</span>
                <span class="stock-heatmap-change">${escapeHtml(fmtPct(change))}</span>
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
  }).join("");
  els.homeHeatmap.innerHTML = `
    ${sectorMarkup}
    <div class="finviz-legend" aria-label="Heatmap return legend">
      <span class="legend-box legend-down-3">-3%</span>
      <span class="legend-box legend-down-2">-2%</span>
      <span class="legend-box legend-down-1">-1%</span>
      <span class="legend-box legend-flat">0%</span>
      <span class="legend-box legend-up-1">+1%</span>
      <span class="legend-box legend-up-2">+2%</span>
      <span class="legend-box legend-up-3">+3%</span>
    </div>
  `;
}

async function loadDashboardEquityHeatmap(force = false) {
  if (!els.homeHeatmap || (state.dashboardHeatmapLoaded && !force)) return;
  els.homeHeatmap.classList.remove("finviz-treemap");
  els.homeHeatmap.innerHTML = '<div class="home-news-empty">intraday 히트맵 데이터를 불러오는 중입니다.</div>';
  if (els.homeHeatmapMeta) els.homeHeatmapMeta.textContent = "Yahoo/yfinance 5분봉 최신 가격을 확인하는 중입니다.";
  if (els.homeHeatmapRefresh) {
    els.homeHeatmapRefresh.disabled = true;
    els.homeHeatmapRefresh.textContent = force ? "새로고침 중" : "불러오는 중";
  }
  try {
    const url = force ? `${API.dashboardEquityHeatmap}?force=true` : API.dashboardEquityHeatmap;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    renderHomeHeatmap(items, data);
    state.dashboardHeatmapLoaded = true;
  } catch (err) {
    els.homeHeatmap.innerHTML = `<div class="home-news-empty">intraday 히트맵 로드 실패: ${escapeHtml(err.message || err)}</div>`;
    if (els.homeHeatmapMeta) els.homeHeatmapMeta.textContent = "히트맵 데이터 로드 실패";
  } finally {
    if (els.homeHeatmapRefresh) {
      els.homeHeatmapRefresh.disabled = false;
      els.homeHeatmapRefresh.textContent = "데이터 새로고침";
    }
  }
}

async function loadDashboardMarket(force = false) {
  if (!els.homeMarketList || (state.marketLoaded && !force)) return;
  els.homeMarketList.innerHTML = '<div class="home-news-empty">시장 데이터를 불러오는 중입니다.</div>';
  try {
    const res = await fetch(API.dashboardMarket);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    state.dashboardMarketItems = items;
    if (!items.length) {
      els.homeMarketList.innerHTML = '<div class="home-news-empty">표시할 시장 데이터가 없습니다.</div>';
      state.marketLoaded = true;
      return;
    }
    els.homeMarketList.innerHTML = items.map((item) => {
      const r = item.returns || {};
      const dayCls = Number(r["1d"]) >= 0 ? "up" : "down";
      const freshness = item.freshness_status || "unknown";
      const usable = isDecisionUsableMarketItem(item);
      const ageText = Number.isFinite(Number(item.age_minutes)) ? `${Math.round(Number(item.age_minutes))}분` : "";
      const source = item.source || "";
      return `
        <article class="home-market-card ${usable ? "" : "stale"} ${escapeHtml(freshness)}">
          <div class="home-market-head">
            <span class="home-market-symbol">${escapeHtml(item.symbol || "")}</span>
            <span class="home-market-class">${escapeHtml(item.asset_class || "")}</span>
          </div>
          <div class="home-market-label">${escapeHtml(item.label || "")}</div>
          <div class="home-market-price">${item.price === null || item.price === undefined ? "-" : escapeHtml(String(item.price))}</div>
          <div class="home-market-returns">
            <span class="${dayCls}">1D ${escapeHtml(fmtPct(r["1d"]))}</span>
            <span>1M ${escapeHtml(fmtPct(r["1m"]))}</span>
          </div>
          <div class="home-market-meta">
            <span>${escapeHtml(item.as_of || "기준일 미확인")}</span>
            <span>${escapeHtml(source)}</span>
          </div>
          <div class="home-market-freshness ${usable ? "ok" : "warn"}">
            <span>${escapeHtml(FRESHNESS_LABELS[freshness] || freshness)}</span>
            ${ageText ? `<span>${escapeHtml(ageText)}</span>` : ""}
            ${usable ? "" : "<strong>의사결정 제외</strong>"}
          </div>
        </article>
      `;
    }).join("");
    state.marketLoaded = true;
  } catch (err) {
    state.dashboardMarketItems = [];
    els.homeMarketList.innerHTML = `<div class="home-news-empty">시장 데이터 로드 실패: ${escapeHtml(err.message || err)}</div>`;
  }
}

function renderMarketTape(overview) {
  const rendered = window.FinGPTMarketUi?.marketTape?.(overview, { freshnessLabels: FRESHNESS_LABELS });
  if (!rendered) {
    if (els.marketOverviewMeta) els.marketOverviewMeta.textContent = "market module unavailable";
    if (els.marketTapeSurface) els.marketTapeSurface.innerHTML = decisionEmpty("Market UI module is unavailable.");
    return;
  }
  if (els.marketOverviewMeta) els.marketOverviewMeta.textContent = rendered.meta || "";
  if (els.marketTapeSurface) els.marketTapeSurface.innerHTML = rendered.html;
}

function renderMarketSignals(overview) {
  if (!els.marketSignalSurface) return;
  const rendered = window.FinGPTMarketUi?.marketSignals?.(overview);
  els.marketSignalSurface.innerHTML = rendered || decisionEmpty("Market UI module is unavailable.");
}

function crossAssetRequestFromControls() {
  const symbols = parseTickerInput(els.crossAssetSymbols?.value || "")
    .slice(0, 12)
    .join(",");
  return {
    symbols: symbols || "SPY,QQQ,TLT,HYG,LQD,GLD,BTC-USD,DXY,US10Y",
    horizon: els.crossAssetHorizon?.value || "1m",
    topic: textInputValue(els.crossAssetTopic) || "",
  };
}

function crossAssetStateLabel(stateKey) {
  const labels = {
    risk_on: "위험선호",
    risk_off: "방어 우위",
    mixed: "혼재",
    unavailable: "데이터 부족",
  };
  return labels[stateKey] || stateKey || "미확인";
}

function crossAssetRoleLabel(role) {
  const labels = {
    equity: "주식",
    rates: "금리/채권",
    credit: "신용",
    commodity: "원자재",
    crypto: "크립토",
    fx: "FX",
    custom: "사용자",
  };
  return labels[role] || role || "기타";
}

function crossAssetReturnCell(label, value) {
  const cls = Number(value) >= 0 ? "ok" : "warn";
  return `<span class="${escapeHtml(cls)}"><b>${escapeHtml(label)}</b> ${escapeHtml(fmtPct(value))}</span>`;
}

function renderCrossAssetAnalysis(payload) {
  if (!els.crossAssetAnalysisSurface) return;
  const items = Array.isArray(payload?.items) ? payload.items : [];
  const summary = payload?.summary || {};
  if (!items.length) {
    els.crossAssetAnalysisSurface.innerHTML = decisionEmpty("교차자산 분석 결과가 없습니다.");
    return;
  }
  const horizon = payload?.horizon || "1m";
  const maxAbs = Math.max(1, ...items.map((item) => Math.abs(Number(item?.returns?.[horizon] || 0))).filter(Number.isFinite));
  const usable = items.filter((item) => item.is_decision_usable);
  const roleReturns = summary.role_returns || {};
  const roleKeys = ["equity", "credit", "rates", "defensive", "crypto"].filter((key) => roleReturns[key] !== null && roleReturns[key] !== undefined);
  els.crossAssetAnalysisSurface.innerHTML = `
    <div class="cross-asset-summary ${escapeHtml(decisionStatusClass(payload?.status))}">
      <div>
        <span>현재 상태</span>
        <strong>${escapeHtml(crossAssetStateLabel(summary.state))}</strong>
      </div>
      <div>
        <span>Regime score</span>
        <strong>${escapeHtml(fmtDecimal(summary.risk_score, 2))}</strong>
      </div>
      <div>
        <span>사용 가능</span>
        <strong>${escapeHtml(_fmtNumber(usable.length))}/${escapeHtml(_fmtNumber(items.length))}</strong>
      </div>
      <div>
        <span>기준 기간</span>
        <strong>${escapeHtml(String(horizon).toUpperCase())}</strong>
      </div>
    </div>
    <div class="cross-asset-narrative">
      <section>
        <h4>${escapeHtml(summary.title || "교차자산 해석")}</h4>
        <p>${escapeHtml(summary.current_state || "현재 상태를 계산하지 못했습니다.")}</p>
      </section>
      <section>
        <h4>향후 동향</h4>
        <p>${escapeHtml(summary.forward_bias || "추가 데이터 확인이 필요합니다.")}</p>
      </section>
    </div>
    ${roleKeys.length ? `
      <div class="cross-asset-role-strip">
        ${roleKeys.map((key) => crossAssetReturnCell(key === "defensive" ? "방어자산" : crossAssetRoleLabel(key), roleReturns[key])).join("")}
      </div>
    ` : ""}
    <div class="cross-asset-bars">
      ${items.map((item) => {
        const value = item?.returns?.[horizon];
        const n = Number(value);
        const width = Number.isFinite(n) ? Math.max(4, Math.min(100, Math.abs(n) / maxAbs * 100)) : 0;
        const cls = !item.is_decision_usable ? "muted" : n >= 0 ? "up" : "down";
        return `
          <article class="cross-asset-row ${cls}">
            <div class="cross-asset-row-head">
              <strong>${escapeHtml(item.symbol || "")}</strong>
              <span>${escapeHtml(item.label || "")} · ${escapeHtml(crossAssetRoleLabel(item.role))}</span>
              <b>${escapeHtml(fmtPct(value))}</b>
            </div>
            <div class="cross-asset-bar-track"><i style="width:${width.toFixed(1)}%"></i></div>
            <div class="cross-asset-row-meta">
              <span>1D ${escapeHtml(fmtPct(item?.returns?.["1d"]))}</span>
              <span>5D ${escapeHtml(fmtPct(item?.returns?.["5d"]))}</span>
              <span>1M ${escapeHtml(fmtPct(item?.returns?.["1m"]))}</span>
              <span>3M ${escapeHtml(fmtPct(item?.returns?.["3m"]))}</span>
              ${item.error ? `<span class="warn">${escapeHtml(item.error)}</span>` : `<span>${escapeHtml(item.as_of || "")}</span>`}
            </div>
          </article>
        `;
      }).join("")}
    </div>
    <div class="cross-asset-watch">
      ${(Array.isArray(summary.watch_points) ? summary.watch_points : []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
    </div>
    <details class="developer-detail">
      <summary>개발자 진단</summary>
      <pre>${escapeHtml(JSON.stringify({
        provider: payload?.provider,
        engine: payload?.analysis_engine,
        generated_at: payload?.generated_at,
        guardrails: payload?.guardrails,
        contributors: summary.contributors,
      }, null, 2))}</pre>
    </details>
  `;
}

async function loadCrossAssetAnalysis(force = false) {
  if (!els.crossAssetAnalysisSurface || (state.crossAssetAnalysis && !force)) return;
  const request = crossAssetRequestFromControls();
  if (els.crossAssetStatus) els.crossAssetStatus.textContent = "교차자산 데이터를 계산하는 중입니다.";
  if (els.crossAssetRun) els.crossAssetRun.disabled = true;
  els.crossAssetAnalysisSurface.innerHTML = '<div class="home-news-empty">교차자산 분석을 불러오는 중입니다.</div>';
  try {
    const res = await fetch(API.dashboardCrossAssetAnalyze(request));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.crossAssetAnalysis = data;
    renderCrossAssetAnalysis(data);
    if (els.crossAssetStatus) {
      const usable = Number(data.decision_usable_count || 0);
      els.crossAssetStatus.textContent = `${_fmtNumber(usable)}개 자산 기준 · ${fmtDate(data.generated_at)}`;
    }
  } catch (err) {
    els.crossAssetAnalysisSurface.innerHTML = decisionEmpty(`교차자산 분석 실패: ${err.message || err}`);
    if (els.crossAssetStatus) els.crossAssetStatus.textContent = "교차자산 분석 실패";
  } finally {
    if (els.crossAssetRun) els.crossAssetRun.disabled = false;
  }
}

async function loadDashboardMarketOverview(force = false) {
  if ((!els.marketTapeSurface && !els.marketSignalSurface) || (state.marketOverviewLoaded && !force)) return;
  if (els.marketTapeSurface) els.marketTapeSurface.innerHTML = '<div class="home-news-empty">시장 테이프를 불러오는 중입니다.</div>';
  if (els.marketSignalSurface) els.marketSignalSurface.innerHTML = '<div class="home-news-empty">시장 신호를 불러오는 중입니다.</div>';
  try {
    const res = await fetch(API.dashboardMarketOverview);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.marketOverview = data;
    renderMarketTape(data);
    renderMarketSignals(data);
    updateGlobalQualitySummary({
      status: data.status || data.quality_status || data.decision_status || "ok",
      asOf: data.as_of || data.generated_at || data.updated_at || "",
      updatedAt: data.generated_at || data.updated_at || "",
      source: data.provider || data.source || "market overview",
      observations: data.observation_count || data.count || "",
      missing: data.missing_count ? `${data.missing_count}` : "없음",
    });
    state.marketOverviewLoaded = true;
  } catch (err) {
    const message = `시장 overview 로드 실패: ${escapeHtml(err.message || err)}`;
    if (els.marketTapeSurface) els.marketTapeSurface.innerHTML = `<div class="home-news-empty">${message}</div>`;
    if (els.marketSignalSurface) els.marketSignalSurface.innerHTML = `<div class="home-news-empty">${message}</div>`;
    if (els.marketOverviewMeta) els.marketOverviewMeta.textContent = "overview load failed";
    updateGlobalQualitySummary({
      status: "unknown",
      source: "market overview",
      missing: "확인 불가",
    });
  }
}

function decisionStatusClass(status) {
  const key = String(status || "").toLowerCase();
  if (["ok", "success"].includes(key)) return "ok";
  if (["failed", "fail", "error"].includes(key)) return "fail";
  if (["partial", "warn", "stale", "empty", "credentials_missing", "dependency_missing", "unavailable", "missing_series", "provider_error", "transformation_error"].includes(key)) return "warn";
  return "muted";
}

function decisionStatusLabel(status) {
  const key = String(status || "").toLowerCase();
  if (key === "success" || key === "ok") return "정상";
  if (key === "failed" || key === "fail" || key === "error") return "실패";
  if (key === "partial") return "부분";
  if (key === "warn" || key === "stale") return "경고";
  if (key === "empty") return "비어 있음";
  return status || "미확인";
}

function decisionEmpty(message) {
  return `<div class="home-news-empty">${escapeHtml(message)}</div>`;
}

function elapsedText(startedAt) {
  const ms = Math.max(0, Date.now() - Number(startedAt || Date.now()));
  if (ms >= 1000) return `${(ms / 1000).toFixed(ms >= 10000 ? 1 : 2)}초`;
  return `${ms}ms`;
}

function renderActionCompletion(label, startedAt, detail = "", status = "ok") {
  const parts = [detail, `소요 ${elapsedText(startedAt)}`, fmtDate(new Date().toISOString())].filter(Boolean);
  return `
    <div class="decision-completion ${escapeHtml(decisionStatusClass(status))}" role="status" aria-live="polite" data-action-complete="true">
      <strong>${escapeHtml(label)}</strong>
      <span>${escapeHtml(parts.join(" · "))}</span>
    </div>
  `;
}

function setButtonBusy(button, busy, busyText = "처리 중", idleText = null) {
  if (!button) return;
  if (busy) {
    if (idleText !== null || button.getAttribute("aria-busy") !== "true") {
      button.dataset.idleText = idleText !== null ? String(idleText) : (button.textContent || "");
    }
    button.textContent = busyText;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    return;
  }
  button.disabled = false;
  button.removeAttribute("aria-busy");
  if (button.dataset.idleText) {
    button.textContent = button.dataset.idleText;
    delete button.dataset.idleText;
  }
}

function decisionMetric(label, value, status = "") {
  return `
    <div class="decision-metric ${escapeHtml(decisionStatusClass(status))}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "-")}</strong>
    </div>
  `;
}

function numberInputValue(el, fallback, { min = -Infinity, max = Infinity } = {}) {
  const n = Number(el?.value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}

function textInputValue(el) {
  return String(el?.value || "").trim() || null;
}

function priceValue(row) {
  const value = row?.adjusted_close ?? row?.close;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function numericOrFallback(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function pctReturnFromRows(rows, periods) {
  if (!Array.isArray(rows) || rows.length < periods + 1) return null;
  const last = priceValue(rows[rows.length - 1]);
  const prior = priceValue(rows[rows.length - 1 - periods]);
  return last !== null && prior ? (last / prior - 1) * 100 : null;
}

function dailyReturnsFromRows(rows) {
  const returns = [];
  for (let i = 1; i < rows.length; i += 1) {
    const prev = priceValue(rows[i - 1]);
    const current = priceValue(rows[i]);
    if (prev && current !== null) returns.push(current / prev - 1);
  }
  return returns;
}

function stdev(values) {
  const clean = values.map(Number).filter(Number.isFinite);
  if (clean.length < 2) return 0;
  const mean = clean.reduce((sum, value) => sum + value, 0) / clean.length;
  return Math.sqrt(clean.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (clean.length - 1));
}

function annualizedVol(rows, periods = 21) {
  const returns = dailyReturnsFromRows(rows).slice(-periods);
  if (returns.length < 2) return null;
  return stdev(returns) * Math.sqrt(252) * 100;
}

function maxDrawdownPct(rows) {
  let peak = -Infinity;
  let maxDrawdown = 0;
  rows.forEach((row) => {
    const price = priceValue(row);
    if (price === null) return;
    peak = Math.max(peak, price);
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, price / peak - 1);
  });
  return maxDrawdown * 100;
}

function fmtMetricRatio(value) {
  const n = Number(value);
  return Number.isFinite(n) ? fmtPct(n * 100) : "-";
}

function fmtDecimal(value, digits = 2) {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "-";
}

function metricStatusForPct(value, inverse = false) {
  if (value === null || value === undefined || value === "") return "warn";
  const n = Number(value);
  if (!Number.isFinite(n)) return "warn";
  if (inverse) return n <= 0 ? "ok" : "warn";
  return n >= 0 ? "ok" : "warn";
}

function paddedChartDomain(values, includeValues = []) {
  const nums = [...values, ...includeValues].map(Number).filter(Number.isFinite);
  if (!nums.length) return { min: 0, max: 1 };
  let min = Math.min(...nums);
  let max = Math.max(...nums);
  if (min === max) {
    const pad = Math.abs(max) * 0.02 || 1;
    return { min: min - pad, max: max + pad };
  }
  const pad = (max - min) * 0.08;
  min -= pad;
  max += pad;
  return { min, max };
}

function chartY(min, max, value, height, padTop, padBottom) {
  const span = max - min || 1;
  return height - padBottom - ((value - min) / span) * (height - padTop - padBottom);
}

function chartTicks(min, max, count = 4) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || count < 2) return [];
  const step = (max - min) / (count - 1 || 1);
  return Array.from({ length: count }, (_, index) => min + step * index).reverse();
}

function renderChartYAxis({ width, height, padLeft, padRight, padTop, padBottom, min, max, formatter }) {
  const ticks = chartTicks(min, max, 4);
  return `
    <g class="chart-y-axis" aria-hidden="true">
      ${ticks.map((value) => {
        const y = chartY(min, max, value, height, padTop, padBottom);
        return `
          <line class="chart-grid-line" x1="${padLeft}" x2="${width - padRight}" y1="${y.toFixed(2)}" y2="${y.toFixed(2)}"></line>
          <text class="chart-y-label" x="${padLeft - 8}" y="${(y + 3).toFixed(2)}" text-anchor="end">${escapeHtml(formatter(value))}</text>
        `;
      }).join("")}
      <line class="chart-axis-line" x1="${padLeft}" x2="${padLeft}" y1="${padTop}" y2="${height - padBottom}"></line>
      <line class="chart-axis-line" x1="${padLeft}" x2="${width - padRight}" y1="${height - padBottom}" y2="${height - padBottom}"></line>
    </g>
  `;
}

function lineChartPoints(values, width, height, padLeft, padRight, padTop, padBottom, min, max) {
  return values.map((row, index) => {
    const x = padLeft + (index / Math.max(1, values.length - 1)) * (width - padLeft - padRight);
    const y = chartY(min, max, row.value, height, padTop, padBottom);
    return { ...row, x, y };
  });
}

function svgPolylinePoints(points) {
  return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
}

function renderChartHoverTargets(points, tooltipFormatter) {
  return points.map((point) => {
    const tooltip = tooltipFormatter(point);
    return `
      <circle class="chart-data-point" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="2.4"></circle>
      <circle class="chart-hover-point" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="8" data-chart-tooltip="${escapeHtml(tooltip)}">
        <title>${escapeHtml(tooltip)}</title>
      </circle>
    `;
  }).join("");
}

function formatCurveReturn(value, base) {
  const n = Number(value);
  const b = Number(base);
  if (!Number.isFinite(n) || !Number.isFinite(b) || b === 0) return "-";
  return fmtPct((n / b - 1) * 100);
}

function formatCurveAxisValue(value, mode, base) {
  if (mode === "return") return formatCurveReturn(value, base);
  if (mode === "ratio") return formatQuantValue(value);
  return fmtDecimal(value, Math.abs(Number(value)) >= 100 ? 0 : 2);
}

function ensureChartTooltip() {
  let tooltip = document.getElementById("chartTooltip");
  if (!tooltip) {
    tooltip = document.createElement("div");
    tooltip.id = "chartTooltip";
    tooltip.className = "chart-tooltip";
    tooltip.setAttribute("role", "tooltip");
    document.body.appendChild(tooltip);
  }
  return tooltip;
}

function hideChartTooltip() {
  const tooltip = document.getElementById("chartTooltip");
  if (tooltip) tooltip.classList.remove("visible");
}

function showChartTooltip(event, text) {
  if (!text) {
    hideChartTooltip();
    return;
  }
  const tooltip = ensureChartTooltip();
  tooltip.textContent = text;
  tooltip.classList.add("visible");
  const offset = 14;
  const rect = tooltip.getBoundingClientRect();
  let left = event.clientX + offset;
  let top = event.clientY + offset;
  if (left + rect.width > window.innerWidth - 8) left = event.clientX - rect.width - offset;
  if (top + rect.height > window.innerHeight - 8) top = event.clientY - rect.height - offset;
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${Math.max(8, top)}px`;
}

function initChartTooltips() {
  if (state.chartTooltipBound) return;
  state.chartTooltipBound = true;
  document.addEventListener("pointermove", (event) => {
    const rawTarget = event.target;
    const target = rawTarget?.closest ? rawTarget.closest("[data-chart-tooltip]") : null;
    if (!target) {
      hideChartTooltip();
      return;
    }
    showChartTooltip(event, target.dataset.chartTooltip || "");
  });
  document.addEventListener("pointerleave", hideChartTooltip);
  document.addEventListener("scroll", hideChartTooltip, true);
}

function renderMiniPriceLineChart(rows) {
  const points = rows
    .slice(-80)
    .map((row) => ({ date: row.date || "", value: priceValue(row) }))
    .filter((row) => row.value !== null);
  if (points.length < 2) return "";
  const width = 720;
  const height = 200;
  const padLeft = 64;
  const padRight = 16;
  const padTop = 18;
  const padBottom = 26;
  const values = points.map((point) => point.value);
  const actualMin = Math.min(...values);
  const actualMax = Math.max(...values);
  const { min, max } = paddedChartDomain(values);
  const xy = lineChartPoints(points, width, height, padLeft, padRight, padTop, padBottom, min, max);
  const linePoints = svgPolylinePoints(xy);
  const areaPoints = `${padLeft},${height - padBottom} ${linePoints} ${width - padRight},${height - padBottom}`;
  const first = points[0];
  const last = points[points.length - 1];
  const changePct = first.value ? (last.value / first.value - 1) * 100 : null;
  const changeClass = Number(changePct) >= 0 ? "ok" : "warn";
  return `
    <div class="mini-price-line" aria-label="최근 종가 선 차트">
      <div class="mini-price-line-head">
        <span>${escapeHtml(first.date || "-")} -> ${escapeHtml(last.date || "-")}</span>
        <strong class="${escapeHtml(changeClass)}">${escapeHtml(changePct === null ? "-" : fmtPct(changePct))}</strong>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="최근 ${escapeHtml(String(points.length))}개 가격 추이">
        ${renderChartYAxis({
          width,
          height,
          padLeft,
          padRight,
          padTop,
          padBottom,
          min,
          max,
          formatter: (value) => fmtDecimal(value, Math.abs(value) >= 100 ? 0 : 2),
        })}
        <polygon points="${areaPoints}" class="mini-price-area"></polygon>
        <polyline points="${linePoints}" class="mini-price-stroke"></polyline>
        <circle cx="${xy[xy.length - 1].x.toFixed(1)}" cy="${xy[xy.length - 1].y.toFixed(1)}" r="4" class="mini-price-last"></circle>
        ${renderChartHoverTargets(xy, (point) => {
          const periodReturn = first.value ? ` · 기간수익률 ${formatCurveReturn(point.value, first.value)}` : "";
          return `${point.date || "-"} · 종가 ${fmtDecimal(point.value, 2)}${periodReturn}`;
        })}
      </svg>
      <div class="mini-price-line-foot">
        <span>저점 ${escapeHtml(fmtDecimal(actualMin, 2))}</span>
        <span>고점 ${escapeHtml(fmtDecimal(actualMax, 2))}</span>
        <span>최근 ${escapeHtml(fmtDecimal(last.value, 2))}</span>
      </div>
    </div>
  `;
}

function renderRecentPriceRows(rows) {
  return `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>일자</th><th>종가</th><th>거래량</th><th>소스</th></tr></thead>
        <tbody>
          ${rows.slice(-6).reverse().map((row) => `
            <tr>
              <td>${escapeHtml(row.date || "-")}</td>
              <td>${escapeHtml(fmtDecimal(priceValue(row), 2))}</td>
              <td>${escapeHtml(_fmtNumber(row.volume))}</td>
              <td>${escapeHtml(row.source || "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function isoDateOffset(dateText, { months = 0, years = 0 } = {}) {
  if (!dateText) return "";
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  if (years) date.setFullYear(date.getFullYear() - years);
  if (months) date.setMonth(date.getMonth() - months);
  return date.toISOString().slice(0, 10);
}

function localIsoDate(date = new Date()) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function isoDateDayOffset(dateText, days = 0) {
  if (!dateText) return "";
  const date = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  date.setDate(date.getDate() - Number(days || 0));
  return date.toISOString().slice(0, 10);
}

function sanitizeDateInput(value) {
  const text = String(value || "").trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
}

function normalizeCustomGlobalDateOrder(startDate, endDate) {
  const start = sanitizeDateInput(startDate);
  const end = sanitizeDateInput(endDate);
  if (start && end && start > end) {
    return { startDate: end, endDate: start, reordered: true };
  }
  return { startDate: start, endDate: end, reordered: false };
}

function globalRangeValidationMessage(rangeState = state.globalRange) {
  const normalized = normalizeGlobalRange(rangeState?.range);
  if (normalized !== "custom") return state.globalRangeNotice || "";
  if (state.globalRangeNotice) return state.globalRangeNotice;
  const start = sanitizeDateInput(rangeState?.startDate);
  const end = sanitizeDateInput(rangeState?.endDate);
  if (!start && !end) return "Custom 기간은 시작일 또는 종료일이 필요합니다. 현재는 1Y 기본 기간으로 계산합니다.";
  if (!start) return "시작일이 없어 1Y lookback으로 계산합니다.";
  if (!end) return "종료일이 없어 오늘 기준으로 계산합니다.";
  return "";
}

function globalRangeLookbackDays(range = state.globalRange?.range, startDate = state.globalRange?.startDate, endDate = state.globalRange?.endDate) {
  const normalized = normalizeGlobalRange(range);
  if (normalized === "YTD") {
    const today = sanitizeDateInput(endDate) || localIsoDate();
    const start = `${today.slice(0, 4)}-01-01`;
    const diff = Math.ceil((new Date(`${today}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000) + 1;
    return Math.max(1, Math.min(5000, diff));
  }
  if (normalized === "custom") {
    const ordered = normalizeCustomGlobalDateOrder(startDate, endDate);
    const start = ordered.startDate;
    const end = ordered.endDate || localIsoDate();
    if (!start) return DASHBOARD_RANGE_LOOKBACK_DAYS["1Y"];
    const diff = Math.ceil((new Date(`${end}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000) + 1;
    return Number.isFinite(diff) ? Math.max(1, Math.min(5000, diff)) : DASHBOARD_RANGE_LOOKBACK_DAYS["1Y"];
  }
  return DASHBOARD_RANGE_LOOKBACK_DAYS[normalized] || DASHBOARD_RANGE_LOOKBACK_DAYS["1Y"];
}

function globalRangeDateBounds(range = state.globalRange?.range, startDate = state.globalRange?.startDate, endDate = state.globalRange?.endDate) {
  const normalized = normalizeGlobalRange(range);
  const end = sanitizeDateInput(endDate) || localIsoDate();
  if (normalized === "custom") {
    const ordered = normalizeCustomGlobalDateOrder(startDate, endDate || end);
    return { startDate: ordered.startDate, endDate: ordered.endDate || end };
  }
  if (normalized === "MAX") return { startDate: "", endDate: end };
  if (normalized === "YTD") return { startDate: `${end.slice(0, 4)}-01-01`, endDate: end };
  const months = { "1M": 1, "3M": 3, "6M": 6 }[normalized] || 0;
  const years = { "1Y": 1, "3Y": 3, "5Y": 5 }[normalized] || 0;
  if (months || years) return { startDate: isoDateOffset(end, { months, years }), endDate: end };
  if (normalized === "1W") return { startDate: isoDateDayOffset(end, 7), endDate: end };
  if (normalized === "1D") return { startDate: end, endDate: end };
  return { startDate: isoDateOffset(end, { years: 1 }), endDate: end };
}

function globalRangeToAssetRange(range = state.globalRange?.range) {
  const normalized = normalizeGlobalRange(range);
  return {
    "1D": "1d",
    "1W": "1w",
    "1M": "1m",
    "3M": "3m",
    "6M": "6m",
    YTD: "ytd",
    "1Y": "1y",
    "3Y": "3y",
    "5Y": "5y",
    MAX: "all",
    custom: "custom",
  }[normalized] || "1y";
}

function quantamentalLookbackFromRange(range = state.globalRange?.range, startDate = state.globalRange?.startDate, endDate = state.globalRange?.endDate) {
  const days = globalRangeLookbackDays(range, startDate, endDate);
  if (days <= 1) return "1";
  if (days <= 7) return "5";
  if (days <= 31) return "21";
  if (days <= 95) return "63";
  if (days <= 190) return "126";
  if (days <= 380) return "252";
  if (days <= 900) return "756";
  if (days <= 1500) return "1260";
  return "5000";
}

function globalRangeSupportSummary(rangeState = state.globalRange) {
  const range = normalizeGlobalRange(rangeState?.range);
  const bounds = globalRangeDateBounds(range, rangeState?.startDate, rangeState?.endDate);
  const lookbackDays = globalRangeLookbackDays(range, bounds.startDate, bounds.endDate);
  const researchDays = Math.max(
    Number(els.lookback?.min || 1),
    Math.min(Number(els.lookback?.max || 180), lookbackDays),
  );
  const quantamentalBucket = quantamentalLookbackFromRange(range, bounds.startDate, bounds.endDate);
  const dateTargets = "자산·백테스트·포트폴리오·Forecast";
  const dateWindow = range === "custom" && !bounds.startDate
    ? `Custom 시작일 없음(1Y 기본 기간)~${bounds.endDate || "오늘"}`
    : `${bounds.startDate || "시작 제한 없음"}~${bounds.endDate || "오늘"}`;
  return {
    lookbackDays,
    researchDays,
    quantamentalBucket,
    summary: `${selectedRangeLabel()} · 약 ${_fmtNumber(lookbackDays)}일 기준. 날짜 지원 화면은 직접 반영하고, lookback 기반 화면은 지원 버킷으로 변환합니다.`,
    detail: `${dateTargets}: ${dateWindow} · Research: ${_fmtNumber(researchDays)}일 · Quantamental: ${_fmtNumber(Number(quantamentalBucket))}일 버킷`,
  };
}

function setSelectValueIfPresent(select, value) {
  if (!select) return false;
  const exists = Array.from(select.options || []).some((option) => option.value === value);
  if (!exists) return false;
  select.value = value;
  return true;
}

function syncDashboardRangeControls() {
  if (!state.globalRange) state.globalRange = { ...DEFAULT_GLOBAL_RANGE };
  if (els.dashboardRangeSelect) els.dashboardRangeSelect.value = normalizeGlobalRange(state.globalRange.range);
  if (els.dashboardRangeStart) els.dashboardRangeStart.value = sanitizeDateInput(state.globalRange.startDate);
  if (els.dashboardRangeEnd) els.dashboardRangeEnd.value = sanitizeDateInput(state.globalRange.endDate);
  const isCustom = normalizeGlobalRange(state.globalRange.range) === "custom";
  const validationMessage = globalRangeValidationMessage();
  if (els.dashboardRangeControls) els.dashboardRangeControls.classList.toggle("custom-active", isCustom);
  if (els.dashboardRangeControls) els.dashboardRangeControls.classList.toggle("range-warning", Boolean(validationMessage));
  const missingCustomStart = isCustom && !state.globalRangeNotice && !sanitizeDateInput(state.globalRange.startDate);
  const missingCustomEnd = isCustom && !state.globalRangeNotice && !sanitizeDateInput(state.globalRange.endDate);
  if (els.dashboardRangeStart) els.dashboardRangeStart.setAttribute("aria-invalid", missingCustomStart ? "true" : "false");
  if (els.dashboardRangeEnd) els.dashboardRangeEnd.setAttribute("aria-invalid", missingCustomEnd ? "true" : "false");
  if (els.dashboardRangeSupport) {
    const support = globalRangeSupportSummary();
    els.dashboardRangeSupport.textContent = validationMessage ? `${validationMessage} · ${support.summary}` : support.summary;
    els.dashboardRangeSupport.title = support.detail;
    if (els.dashboardRangeControls) els.dashboardRangeControls.dataset.rangeSupport = support.detail;
  }
  renderGlobalQualitySummary();
}

function applyGlobalRangeToControls() {
  const range = normalizeGlobalRange(state.globalRange?.range);
  const bounds = globalRangeDateBounds(range, state.globalRange?.startDate, state.globalRange?.endDate);
  const lookbackDays = globalRangeLookbackDays(range, bounds.startDate, bounds.endDate);
  const cappedResearchLookback = Math.max(
    Number(els.lookback?.min || 1),
    Math.min(Number(els.lookback?.max || 180), lookbackDays),
  );
  if (els.lookback) {
    els.lookback.value = String(cappedResearchLookback);
    els.lookback.dataset.globalRange = range;
  }
  setSelectValueIfPresent(els.assetDetailRange, globalRangeToAssetRange(range));
  if (els.assetDetailStartDate) els.assetDetailStartDate.value = bounds.startDate;
  if (els.assetDetailEndDate) els.assetDetailEndDate.value = bounds.endDate;
  if (els.backtestStartDate) els.backtestStartDate.value = bounds.startDate;
  if (els.backtestEndDate) els.backtestEndDate.value = bounds.endDate;
  if (els.portfolioStartDate) els.portfolioStartDate.value = bounds.startDate;
  if (els.portfolioEndDate) els.portfolioEndDate.value = bounds.endDate;
  if (els.portfolioLookbackDays) els.portfolioLookbackDays.value = String(Math.min(5000, Math.max(1, lookbackDays)));
  if (els.forecastStartDate) els.forecastStartDate.value = bounds.startDate;
  if (els.forecastEndDate) els.forecastEndDate.value = bounds.endDate;
  setSelectValueIfPresent(els.quantamentalLookback, quantamentalLookbackFromRange(range, bounds.startDate, bounds.endDate));
  if (els.aiPortfolioLookbackMonths) {
    const months = range === "MAX" ? 120 : Math.max(1, Math.round(lookbackDays / 21));
    els.aiPortfolioLookbackMonths.value = String(Math.min(120, months));
  }
  if (els.crossAssetHorizon) {
    const horizon = lookbackDays <= 1 ? "1d" : (lookbackDays <= 7 ? "5d" : (lookbackDays <= 63 ? "1m" : "3m"));
    setSelectValueIfPresent(els.crossAssetHorizon, horizon);
  }
  updateRangeLabels();
  syncDashboardRangeControls();
  persistForm();
}

function updateGlobalRangeUrl() {
  if (!window.history?.replaceState) return;
  const params = new URLSearchParams(window.location.search || "");
  const range = normalizeGlobalRange(state.globalRange?.range);
  params.set("range", range);
  if (range === "custom") {
    if (state.globalRange.startDate) params.set("start", state.globalRange.startDate);
    else params.delete("start");
    if (state.globalRange.endDate) params.set("end", state.globalRange.endDate);
    else params.delete("end");
  } else {
    params.delete("start");
    params.delete("end");
  }
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
}

function setGlobalRange(range, options = {}) {
  const normalized = normalizeGlobalRange(range);
  const start = sanitizeDateInput(options.startDate ?? els.dashboardRangeStart?.value ?? state.globalRange?.startDate);
  const end = sanitizeDateInput(options.endDate ?? els.dashboardRangeEnd?.value ?? state.globalRange?.endDate);
  state.globalRangeNotice = "";
  if (normalized === "custom") {
    const ordered = normalizeCustomGlobalDateOrder(start, end);
    if (ordered.reordered) {
      state.globalRangeNotice = "시작일과 종료일이 역순이라 자동으로 정렬했습니다.";
    }
    state.globalRange = { range: normalized, startDate: ordered.startDate, endDate: ordered.endDate };
  } else {
    state.globalRange = { range: normalized, ...globalRangeDateBounds(normalized, start, end) };
  }
  if (options.persist !== false) safeWriteStoredJson(STORAGE.dashboardRange, state.globalRange);
  applyGlobalRangeToControls();
  if (options.updateUrl) updateGlobalRangeUrl();
  if (options.reload) {
    markGlobalQualityRangePending();
    loadActiveDashboardResources(true);
  }
}

function assetDetailOptionsFromControls() {
  return {
    range: els.assetDetailRange?.value || "1y",
    startDate: textInputValue(els.assetDetailStartDate),
    endDate: textInputValue(els.assetDetailEndDate),
    view: els.assetDetailView?.value || "overview",
    benchmark: normalizeTickerToken(els.assetDetailBenchmark?.value || "SPY") || "SPY",
    compareBenchmark: !!els.assetDetailBenchmarkCompare?.checked,
  };
}

function assetDetailRangeStart(latestDate, range) {
  if (!latestDate || range === "all") return "";
  if (range === "custom") return "";
  if (range === "1d") return latestDate;
  if (range === "1w") return isoDateDayOffset(latestDate, 7);
  if (range === "1m") return isoDateOffset(latestDate, { months: 1 });
  if (range === "3m") return isoDateOffset(latestDate, { months: 3 });
  if (range === "6m") return isoDateOffset(latestDate, { months: 6 });
  if (range === "ytd") return `${latestDate.slice(0, 4)}-01-01`;
  if (range === "3y") return isoDateOffset(latestDate, { years: 3 });
  if (range === "5y") return isoDateOffset(latestDate, { years: 5 });
  return isoDateOffset(latestDate, { years: 1 });
}

function assetDetailRefreshStart(options) {
  if (options.startDate) return options.startDate;
  if (options.range === "all") return "";
  return assetDetailRangeStart(options.endDate || localIsoDate(), options.range);
}

function assetDetailPriceQueryOptions(options) {
  const freshness = selectedQuantFreshnessOptions();
  return {
    refresh: true,
    startDate: assetDetailRefreshStart(options),
    endDate: options.endDate || "",
    freshnessProfile: freshness.freshnessProfile,
    requireFreshPrices: freshness.requireFreshPrices,
  };
}

function assetDetailRefreshWarning(data, ticker) {
  const warnings = [];
  const refresh = data?.refresh || {};
  if (refresh.enabled && refresh.attempted) {
    const status = String(refresh.status || "").toLowerCase();
    if (status && !["success", "ok", "partial"].includes(status)) {
      const message = refresh.error ? ` · ${refresh.error}` : "";
      warnings.push(`${ticker} 최신 종가 보강 실패${message}`);
    }
  }
  const audit = data?.asset_freshness || {};
  const freshnessStatus = String(audit.freshness_status || "").toLowerCase();
  if (data?.strict_freshness_violation || freshnessStatus === "stale") {
    warnings.push(`${ticker} 가격 신선도 ${freshnessStatus || "unknown"} · 최근 ${audit.latest_price_date || "unknown"} · 기대 ${data?.expected_latest_date || audit.expected_latest_date || "unknown"} · 지연 ${data?.market_calendar_lag_days ?? audit.market_calendar_lag_days ?? "-"}일`);
  }
  return warnings.join(" · ");
}

function filterPriceRowsByAssetOptions(rows, options) {
  const clean = (Array.isArray(rows) ? rows : [])
    .filter((row) => row?.date && priceValue(row) !== null)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const latestDate = clean[clean.length - 1]?.date || "";
  const rangeStart = assetDetailRangeStart(latestDate, options.range);
  const start = options.startDate || rangeStart;
  const end = options.endDate || latestDate;
  return clean.filter((row) => {
    const date = row.date || "";
    if (start && date < start) return false;
    if (end && date > end) return false;
    return true;
  });
}

function assetDailyReturnRows(rows) {
  const out = [];
  for (let i = 1; i < rows.length; i += 1) {
    const prev = priceValue(rows[i - 1]);
    const current = priceValue(rows[i]);
    if (prev && current !== null) out.push({ date: rows[i].date || "", value: current / prev - 1 });
  }
  return out;
}

function assetReturnCurve(rows) {
  const base = priceValue(rows[0]);
  if (!base) return [];
  return rows
    .map((row) => {
      const value = priceValue(row);
      return value === null ? null : { date: row.date || "", value: value / base - 1 };
    })
    .filter(Boolean);
}

function assetNavCurve(rows) {
  const base = priceValue(rows[0]);
  if (!base) return [];
  return rows
    .map((row) => {
      const value = priceValue(row);
      return value === null ? null : { date: row.date || "", value: value / base };
    })
    .filter(Boolean);
}

function assetDrawdownCurve(rows) {
  let peak = -Infinity;
  return (Array.isArray(rows) ? rows : [])
    .map((row) => {
      const value = priceValue(row);
      if (value === null) return null;
      peak = Math.max(peak, value);
      return { date: row.date || "", value: peak > 0 ? value / peak - 1 : 0 };
    })
    .filter(Boolean);
}

function assetSourceSummary(rows) {
  const counts = new Map();
  rows.forEach((row) => {
    const source = row.source || "unknown";
    counts.set(source, (counts.get(source) || 0) + 1);
  });
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
}

function assetDetailMetrics(rows, latest) {
  const firstPrice = priceValue(rows[0]);
  const lastPrice = priceValue(rows[rows.length - 1] || latest);
  const values = rows.map(priceValue).filter((value) => value !== null);
  const daily = assetDailyReturnRows(rows);
  const best = daily.length ? daily.reduce((a, b) => (b.value > a.value ? b : a), daily[0]) : null;
  const worst = daily.length ? daily.reduce((a, b) => (b.value < a.value ? b : a), daily[0]) : null;
  const positiveRatio = daily.length ? daily.filter((row) => row.value > 0).length / daily.length : null;
  const periodReturn = firstPrice && lastPrice ? lastPrice / firstPrice - 1 : null;
  const high = values.length ? Math.max(...values) : null;
  const low = values.length ? Math.min(...values) : null;
  const currentDrawdown = high && lastPrice ? lastPrice / high - 1 : null;
  const avgVolumeRows = rows.map((row) => Number(row.volume)).filter(Number.isFinite);
  const avgVolume = avgVolumeRows.length
    ? avgVolumeRows.reduce((sum, value) => sum + value, 0) / avgVolumeRows.length
    : null;
  return {
    firstPrice,
    lastPrice,
    periodReturn,
    high,
    low,
    currentDrawdown,
    daily,
    best,
    worst,
    positiveRatio,
    avgVolume,
    vol20: annualizedVol(rows, 21),
    vol60: annualizedVol(rows, 63),
    mdd: maxDrawdownPct(rows),
  };
}

function renderAssetInsightPanel(ticker, rows, metrics, latest, options) {
  const startDate = rows[0]?.date || "-";
  const endDate = rows[rows.length - 1]?.date || "-";
  const sourceRows = assetSourceSummary(rows);
  return `
    <div class="decision-section-title">실무 요약</div>
    <div class="decision-action-list asset-insight-list">
      <div>
        <strong>기간 성과</strong>
        <span>${escapeHtml(ticker)} · ${escapeHtml(startDate)} -> ${escapeHtml(endDate)} · 누적 ${escapeHtml(metrics.periodReturn === null ? "-" : fmtMetricRatio(metrics.periodReturn))}</span>
      </div>
      <div>
        <strong>위험 상태</strong>
        <span>현재 낙폭 ${escapeHtml(metrics.currentDrawdown === null ? "-" : fmtMetricRatio(metrics.currentDrawdown))} · 최악 낙폭 ${escapeHtml(fmtPct(metrics.mdd))} · 60D 변동성 ${escapeHtml(metrics.vol60 === null ? "-" : fmtPct(metrics.vol60))}</span>
      </div>
      <div>
        <strong>데이터 범위</strong>
        <span>선택 ${escapeHtml(_fmtNumber(rows.length))}행 · 보기 ${escapeHtml(options.view)} · 소스 ${escapeHtml(sourceRows.map(([source, count]) => `${source} ${count}`).join(", ") || "unknown")}</span>
      </div>
    </div>
    <div class="decision-list compact">
      <div class="decision-list-row"><span>최고가 / 최저가</span><strong>${escapeHtml(fmtDecimal(metrics.high, 2))} / ${escapeHtml(fmtDecimal(metrics.low, 2))}</strong></div>
      <div class="decision-list-row"><span>최고 일간 수익률</span><strong class="ok">${escapeHtml(metrics.best ? `${metrics.best.date} ${fmtMetricRatio(metrics.best.value)}` : "-")}</strong></div>
      <div class="decision-list-row"><span>최악 일간 수익률</span><strong class="warn">${escapeHtml(metrics.worst ? `${metrics.worst.date} ${fmtMetricRatio(metrics.worst.value)}` : "-")}</strong></div>
      <div class="decision-list-row"><span>상승일 비중</span><strong>${escapeHtml(metrics.positiveRatio === null ? "-" : fmtMetricRatio(metrics.positiveRatio))}</strong></div>
      <div class="decision-list-row"><span>평균 거래량</span><strong>${escapeHtml(metrics.avgVolume === null ? "-" : _fmtNumber(Math.round(metrics.avgVolume)))}</strong></div>
      <div class="decision-list-row"><span>최근 수집</span><strong>${escapeHtml(latest.collected_at || "-")}</strong></div>
    </div>
  `;
}

function renderAssetMetricPanel(rows, metrics, latest) {
  const returns = {
    "1D": pctReturnFromRows(rows, 1),
    "1W": pctReturnFromRows(rows, 5),
    "1M": pctReturnFromRows(rows, 21),
    "3M": pctReturnFromRows(rows, 63),
    "6M": pctReturnFromRows(rows, 126),
    "1Y": pctReturnFromRows(rows, 252),
  };
  return `
    <div class="decision-metric-grid dense">
      ${decisionMetric("기준일", latest.date || rows[rows.length - 1]?.date || "-", "ok")}
      ${decisionMetric("종가", fmtDecimal(metrics.lastPrice, 2), "ok")}
      ${decisionMetric("기간 수익률", metrics.periodReturn === null ? "-" : fmtMetricRatio(metrics.periodReturn), metricStatusForPct(metrics.periodReturn))}
      ${decisionMetric("거래량", _fmtNumber(latest.volume), "ok")}
      ${decisionMetric("선택 범위", `${fmtDecimal(metrics.low, 2)} / ${fmtDecimal(metrics.high, 2)}`, metrics.high ? "ok" : "warn")}
      ${Object.entries(returns).map(([label, value]) => decisionMetric(label, value === null ? "-" : fmtPct(value), metricStatusForPct(value))).join("")}
      ${decisionMetric("20D Vol", metrics.vol20 === null ? "-" : fmtPct(metrics.vol20), metrics.vol20 === null ? "warn" : "ok")}
      ${decisionMetric("60D Vol", metrics.vol60 === null ? "-" : fmtPct(metrics.vol60), metrics.vol60 === null ? "warn" : "ok")}
      ${decisionMetric("MDD", fmtPct(metrics.mdd), metricStatusForPct(metrics.mdd, true))}
      ${decisionMetric("현재 낙폭", metrics.currentDrawdown === null ? "-" : fmtMetricRatio(metrics.currentDrawdown), metricStatusForPct(metrics.currentDrawdown, true))}
    </div>
  `;
}

function renderAssetReturnLineChart(rows) {
  const curve = assetReturnCurve(rows);
  return renderDecisionLineChart(curve, "return", "수익률 곡선", "ok");
}

function renderAssetDrawdownLineChart(rows) {
  const curve = assetDrawdownCurve(rows);
  return renderDecisionLineChart(curve, "drawdown", "낙폭 곡선", "ok");
}

function renderAssetBenchmarkComparison(ticker, rows, benchmarkTicker, benchmarkRows) {
  const primary = assetNavCurve(rows);
  const benchmark = assetNavCurve(benchmarkRows);
  if (primary.length < 2 || benchmark.length < 2) return "";
  return renderNormalizedComparisonChart({
    primary,
    benchmark,
    primaryLabel: ticker,
    benchmarkLabel: benchmarkTicker,
    title: "자산 수익률 비교",
    status: "ok",
  });
}

function renderAssetDataPanel(rows, allRows, latest) {
  const sources = assetSourceSummary(rows);
  return `
    <div class="decision-section-title">데이터 품질</div>
    <div class="decision-metric-grid">
      ${decisionMetric("선택 행", _fmtNumber(rows.length), rows.length ? "ok" : "warn")}
      ${decisionMetric("전체 저장 행", _fmtNumber(allRows.length), allRows.length ? "ok" : "warn")}
      ${decisionMetric("최근 기준일", latest.date || rows[rows.length - 1]?.date || "-", "ok")}
      ${decisionMetric("최근 소스", latest.source || rows[rows.length - 1]?.source || "-", "ok")}
    </div>
    <div class="decision-list compact">
      ${sources.map(([source, count]) => `
        <div class="decision-list-row">
          <span>${escapeHtml(source)}</span>
          <strong>${escapeHtml(_fmtNumber(count))}행</strong>
        </div>
      `).join("") || '<div class="muted small">소스 정보가 없습니다.</div>'}
    </div>
  `;
}

function renderAssetDetailSections({ ticker, rows, allRows, latest, metrics, options, benchmarkRows }) {
  const chartGrid = `
    <div class="decision-chart-grid asset-detail-chart-grid">
      ${renderMiniPriceLineChart(rows)}
      ${renderAssetReturnLineChart(rows)}
      ${renderAssetDrawdownLineChart(rows)}
      ${options.compareBenchmark ? renderAssetBenchmarkComparison(ticker, rows, options.benchmark, benchmarkRows || []) : ""}
    </div>
  `;
  if (options.view === "price") {
    return `${renderAssetMetricPanel(rows, metrics, latest)}${renderMiniPriceLineChart(rows)}${renderRecentPriceRows(rows)}`;
  }
  if (options.view === "returns") {
    return `${renderAssetMetricPanel(rows, metrics, latest)}<div class="decision-chart-grid asset-detail-chart-grid">${renderAssetReturnLineChart(rows)}${options.compareBenchmark ? renderAssetBenchmarkComparison(ticker, rows, options.benchmark, benchmarkRows || []) : ""}</div>${renderRecentPriceRows(rows)}`;
  }
  if (options.view === "risk") {
    return `${renderAssetMetricPanel(rows, metrics, latest)}<div class="decision-chart-grid asset-detail-chart-grid">${renderAssetDrawdownLineChart(rows)}${renderAssetReturnLineChart(rows)}</div>${renderAssetInsightPanel(ticker, rows, metrics, latest, options)}`;
  }
  if (options.view === "data") {
    return `${renderAssetDataPanel(rows, allRows, latest)}${renderRecentPriceRows(rows)}`;
  }
  return `${renderAssetMetricPanel(rows, metrics, latest)}${chartGrid}${renderAssetInsightPanel(ticker, rows, metrics, latest, options)}${renderRecentPriceRows(rows)}${renderAssetDataPanel(rows, allRows, latest)}`;
}

function macroValueText(value, unit = "") {
  if (value === null || value === undefined || value === "") return "사용 불가";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  const digits = Math.abs(num) >= 1000 ? 0 : (Math.abs(num) >= 10 ? 2 : 3);
  return `${fmtDecimal(num, digits)}${unit ? ` ${unit}` : ""}`;
}

function macroQualitySummary(quality = {}) {
  const missing = Array.isArray(quality.missing_series) ? quality.missing_series.length : 0;
  const stale = Array.isArray(quality.stale_series) ? quality.stale_series.length : 0;
  const errors = Array.isArray(quality.errors) ? quality.errors.length : 0;
  return `${quality.status || "unknown"} · 누락 ${missing} · 지연 ${stale} · 오류 ${errors}`;
}

const MACRO_CATEGORY_LABELS = {
  interest_rates: "금리",
  inflation: "인플레이션",
  growth: "성장",
  labor: "고용",
  housing_consumer: "주택·소비",
  yield_curve: "수익률곡선",
  liquidity_credit: "유동성·신용",
  financial_conditions: "금융여건",
  fx_dollar: "FX·달러",
  commodities: "원자재",
  market: "시장",
};

const MACRO_DASHBOARD_TIMEOUT_MS = 20000;
const MACRO_PANEL_TIMEOUT_MS = 30000;

const MACRO_SCENARIO_PRESETS = {
  rates_up: {
    name: "rates_up",
    rate_shock_bp: 100,
    inflation_shock_pct: 0.2,
    growth_shock_pct: -0.2,
    credit_spread_shock_bp: 25,
    oil_shock_pct: 0,
  },
  stagflation: {
    name: "stagflation",
    rate_shock_bp: 75,
    inflation_shock_pct: 1.2,
    growth_shock_pct: -1.0,
    credit_spread_shock_bp: 80,
    oil_shock_pct: 15,
  },
  credit_stress: {
    name: "credit_stress",
    rate_shock_bp: -50,
    inflation_shock_pct: -0.1,
    growth_shock_pct: -1.2,
    credit_spread_shock_bp: 180,
    oil_shock_pct: -8,
  },
};

function macroCountBy(items = [], key) {
  return (Array.isArray(items) ? items : []).reduce((acc, item) => {
    const value = String(item?.[key] || "unknown");
    acc[value] = (acc[value] || 0) + 1;
    return acc;
  }, {});
}

function macroObjectCounts(value) {
  if (!value || Array.isArray(value) || typeof value !== "object") return {};
  return Object.fromEntries(Object.entries(value).map(([key, count]) => [key, Number(count) || 0]));
}

function renderMacroCoverage(data = {}) {
  if (!els.macroCoverageSurface) return;
  const items = Array.isArray(data.items) ? data.items : (Array.isArray(data.series) ? data.series : []);
  const enabled = items.filter((item) => item.enabled !== false);
  const categoryCounts = Object.keys(macroObjectCounts(data.by_category || data.category_counts || data.categories)).length
    ? macroObjectCounts(data.by_category || data.category_counts || data.categories)
    : macroCountBy(enabled, "category");
  const providerCounts = Object.keys(macroObjectCounts(data.by_provider || data.provider_counts || data.providers)).length
    ? macroObjectCounts(data.by_provider || data.provider_counts || data.providers)
    : macroCountBy(enabled, "provider");
  const countryCounts = Object.keys(macroObjectCounts(data.by_country || data.country_counts || data.countries)).length
    ? macroObjectCounts(data.by_country || data.country_counts || data.countries)
    : macroCountBy(enabled, "country");
  const totalCount = enabled.length || data.total_series || data.enabled_series || data.count || 0;
  const categoryRows = Object.entries(categoryCounts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name, count]) => `
      <span class="macro-coverage-chip">
        <strong>${escapeHtml(MACRO_CATEGORY_LABELS[name] || name.replace(/_/g, " "))}</strong>
        <em>${escapeHtml(_fmtNumber(count))}</em>
      </span>
    `)
    .join("");
  const providerRows = Object.entries(providerCounts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name, count]) => `<span>${escapeHtml(name)} ${escapeHtml(_fmtNumber(count))}</span>`)
    .join("");
  const countryRows = Object.entries(countryCounts)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name, count]) => `<span>${escapeHtml(name)} ${escapeHtml(_fmtNumber(count))}</span>`)
    .join("");
  els.macroCoverageSurface.innerHTML = `
    <div class="macro-coverage-grid">
      ${decisionMetric("활성 시계열", _fmtNumber(totalCount), totalCount >= 60 ? "ok" : "warn")}
      ${decisionMetric("범주", _fmtNumber(Object.keys(categoryCounts).length), "ok")}
      ${decisionMetric("FRED", _fmtNumber(providerCounts.fred || 0), "ok")}
      ${decisionMetric("시장 프록시", _fmtNumber(providerCounts.yahoo || 0), providerCounts.yahoo ? "ok" : "muted")}
      ${decisionMetric("국가/지역", _fmtNumber(Object.keys(countryCounts).length), "ok")}
    </div>
    <div class="macro-coverage-section">
      <div class="decision-section-title">범주별 커버리지</div>
      <div class="macro-coverage-chips">${categoryRows || "<span>표시할 범주가 없습니다.</span>"}</div>
    </div>
    <div class="macro-coverage-meta">
      <div><strong>공급자</strong>${providerRows || "<span>없음</span>"}</div>
      <div><strong>국가</strong>${countryRows || "<span>없음</span>"}</div>
    </div>
  `;
}

function macroFilterValues() {
  return {
    category: els.macroCategoryFilter?.value || "",
    provider: els.macroProviderFilter?.value || "",
  };
}

function macroFilterSeriesItems(items = []) {
  const { category, provider } = macroFilterValues();
  return (Array.isArray(items) ? items : []).filter((item) => {
    if (category && String(item.category || "") !== category) return false;
    if (provider && String(item.provider || "") !== provider) return false;
    return true;
  });
}

function macroOptionRows(items = [], key, labels = {}) {
  const values = Array.from(new Set((Array.isArray(items) ? items : [])
    .map((item) => String(item?.[key] || ""))
    .filter(Boolean)))
    .sort((a, b) => a.localeCompare(b));
  return values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(labels[value] || value.replace(/_/g, " "))}</option>`).join("");
}

function renderMacroExplorerFilters(seriesList = {}) {
  const items = Array.isArray(seriesList.items) ? seriesList.items : [];
  const current = macroFilterValues();
  if (els.macroCategoryFilter) {
    els.macroCategoryFilter.innerHTML = `<option value="">전체 범주</option>${macroOptionRows(items, "category", MACRO_CATEGORY_LABELS)}`;
    els.macroCategoryFilter.value = current.category;
  }
  if (els.macroProviderFilter) {
    els.macroProviderFilter.innerHTML = `<option value="">전체 공급자</option>${macroOptionRows(items, "provider")}`;
    els.macroProviderFilter.value = current.provider;
  }
}

function renderMacroComparePlaceholder(items = []) {
  if (!els.macroCompareSurface) return;
  const filtered = macroFilterSeriesItems(items);
  const { category, provider } = macroFilterValues();
  els.macroCompareSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge muted">compare-ready</span>
      <span>필터 ${escapeHtml(category || "전체 범주")} · ${escapeHtml(provider || "전체 공급자")} · 후보 ${escapeHtml(_fmtNumber(filtered.length))}개</span>
    </div>
    ${decisionEmpty("이번 UI 단계에서는 비교 마커와 빈 상태만 제공합니다. 시계열 선택 기반 다중 비교는 회귀 위험을 줄이기 위해 후속 단계로 남깁니다.")}
  `;
}

function renderMacroOverview(data) {
  if (!els.macroOverviewSurface) return;
  const regime = data.regime || {};
  const quality = data.data_quality || {};
  const signals = Array.isArray(data.signals) ? data.signals : [];
  const byName = Object.fromEntries(signals.map((signal) => [signal.name, signal]));
  els.macroOverviewSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(quality.status))}">${escapeHtml(quality.status || "unknown")}</span>
      <span>기준일 ${escapeHtml(data.as_of || "-")} · 공급자 ${escapeHtml(quality.provider || "mixed")}</span>
    </div>
    <div class="macro-status-strip">
      ${decisionMetric("레짐", regime.display_name || regime.name || "unknown", regime.name === "unknown" ? "warn" : "ok")}
      ${decisionMetric("신뢰도", fmtDecimal(Number(regime.confidence || 0), 2), regime.confidence >= 0.5 ? "ok" : "warn")}
      ${decisionMetric("위험 수준", regime.risk_level || "unknown", regime.risk_level === "high" ? "warn" : "ok")}
      ${decisionMetric("성장", byName.growth_signal?.value || "unknown", byName.growth_signal?.value === "unknown" ? "warn" : "ok")}
      ${decisionMetric("인플레이션", byName.inflation_signal?.value || "unknown", byName.inflation_signal?.value === "unknown" ? "warn" : "ok")}
      ${decisionMetric("정책", byName.policy_signal?.value || "unknown", byName.policy_signal?.value === "unknown" ? "warn" : "ok")}
      ${decisionMetric("고용", byName.labor_signal?.value || "unknown", byName.labor_signal?.value === "unknown" ? "warn" : "ok")}
      ${decisionMetric("신용", byName.credit_signal?.value || "unknown", byName.credit_signal?.value === "unknown" ? "warn" : "ok")}
    </div>
    <div class="decision-summary ${escapeHtml(decisionStatusClass(quality.status))}">
      ${escapeHtml(regime.interpretation || "구조화된 매크로 데이터가 충분하지 않아 레짐 해석을 보류합니다.")}
    </div>
    ${quality.status !== "ok" ? `<div class="macro-warning">${escapeHtml(macroQualitySummary(quality))}. 누락되거나 오래된 데이터는 중립 신호가 아니라 증거 부족으로 처리합니다.</div>` : ""}
  `;
}

function renderMacroIndicatorTable(items = []) {
  if (!els.macroIndicatorTable) return;
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    els.macroIndicatorTable.innerHTML = decisionEmpty("표시할 핵심 매크로 지표가 없습니다.");
    return;
  }
  els.macroIndicatorTable.innerHTML = `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>시계열</th><th>최근값</th><th>날짜</th><th>변화</th><th>공급자</th><th>품질</th><th>변환</th></tr></thead>
        <tbody>
          ${rows.map((item) => {
            const latest = item.latest || {};
            const change = item.changes?.change_1_period;
            const quality = item.data_quality || {};
            return `
              <tr>
                <td><strong>${escapeHtml(item.series_id || "")}</strong><br><small>${escapeHtml(item.display_name || "")}</small></td>
                <td>${escapeHtml(macroValueText(latest.value, item.unit))}</td>
                <td>${escapeHtml(latest.date || "사용 불가")}</td>
                <td>${escapeHtml(change === null || change === undefined ? "사용 불가" : fmtDecimal(change, 3))}</td>
                <td>${escapeHtml(item.provider || "unknown")}</td>
                <td><span class="table-status ${escapeHtml(decisionStatusClass(quality.status))}">${escapeHtml(quality.status || "unknown")}</span></td>
                <td>${escapeHtml(latest.metadata?.transform || "level")}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderMacroSeriesChart(item, title = "") {
  const observations = (Array.isArray(item?.observations) ? item.observations : [])
    .slice(-80)
    .map((row) => ({ date: row.date || "", value: Number(row.value) }))
    .filter((row) => row.date && Number.isFinite(row.value));
  if (observations.length < 2) {
    return `
      <div class="decision-chart">
        <div class="decision-chart-head"><span>${escapeHtml(title || item?.display_name || item?.series_id || "시계열")}</span><strong class="warn">사용 불가</strong></div>
        ${decisionEmpty("차트를 만들 관측치가 부족합니다.")}
      </div>
    `;
  }
  const width = 720;
  const height = 210;
  const padLeft = 64;
  const padRight = 18;
  const padTop = 18;
  const padBottom = 30;
  const values = observations.map((row) => row.value);
  const { min, max } = paddedChartDomain(values);
  const points = lineChartPoints(observations, width, height, padLeft, padRight, padTop, padBottom, min, max);
  const latest = observations[observations.length - 1];
  return `
    <div class="decision-chart">
      <div class="decision-chart-head">
        <span>${escapeHtml(title || item.display_name || item.series_id)}</span>
        <strong class="${escapeHtml(decisionStatusClass(item.data_quality?.status))}">${escapeHtml(macroValueText(latest.value, item.unit))}</strong>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(item.series_id || "macro series")} chart">
        ${renderChartYAxis({ width, height, padLeft, padRight, padTop, padBottom, min, max, formatter: (value) => fmtDecimal(value, Math.abs(value) >= 100 ? 0 : 2) })}
        <polyline points="${svgPolylinePoints(points)}" fill="none" stroke="currentColor" stroke-width="2.4" vector-effect="non-scaling-stroke"></polyline>
        ${renderChartHoverTargets(points, (point) => `${point.date || "-"} · ${item.series_id || ""} ${fmtDecimal(point.value, 3)}`)}
      </svg>
      <div class="decision-chart-foot"><span>${escapeHtml(observations[0].date)}</span><span>${escapeHtml(latest.date)}</span></div>
    </div>
  `;
}

function renderMacroCharts(overview) {
  if (!els.macroChartSurface) return;
  const items = Array.isArray(overview?.key_indicators) ? overview.key_indicators : [];
  const chosen = ["DGS10", "T10Y2Y", "CPIAUCSL", "UNRATE", "GDPC1", "VIXCLS"]
    .map((id) => items.find((item) => item.series_id === id))
    .filter(Boolean);
  if (!chosen.length) {
    els.macroChartSurface.innerHTML = decisionEmpty("표시할 차트 관측치가 없습니다.");
    return;
  }
  els.macroChartSurface.innerHTML = `<div class="macro-chart-grid">${chosen.map((item) => renderMacroSeriesChart(item)).join("")}</div>`;
}

function renderMacroCategory(surface, data) {
  if (!surface) return;
  const items = Array.isArray(data?.items) ? data.items : [];
  if (!items.length) {
    surface.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(data?.data_quality?.status))}">${escapeHtml(data?.data_quality?.status || "사용 불가")}</span>
        <span>${escapeHtml((data?.data_quality?.notes || []).join(" ") || "연결된 공급자가 없습니다.")}</span>
      </div>
    `;
    return;
  }
  surface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.data_quality?.status))}">${escapeHtml(data.data_quality?.status || "unknown")}</span>
      <span>${escapeHtml(data.category || "category")} · ${escapeHtml(_fmtNumber(data.count || items.length))}개 지표</span>
    </div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>시계열</th><th>최근값</th><th>날짜</th><th>품질</th></tr></thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td>${escapeHtml(item.series_id || "")}<br><small>${escapeHtml(item.display_name || "")}</small></td>
              <td>${escapeHtml(macroValueText(item.latest?.value, item.unit))}</td>
              <td>${escapeHtml(item.latest?.date || "사용 불가")}</td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(item.data_quality?.status))}">${escapeHtml(item.data_quality?.status || "unknown")}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderMacroSearchStarter(seriesList = {}) {
  if (!els.macroSeriesSearchResults) return;
  const items = Array.isArray(seriesList.items) ? seriesList.items : [];
  renderMacroExplorerFilters(seriesList);
  renderMacroComparePlaceholder(items);
  const preferred = ["DGS10", "CPIAUCSL", "CPILFESL", "UNRATE", "T10Y2Y", "BAMLH0A0HYM2", "DCOILWTICO", "DTWEXBGS"];
  const rows = preferred
    .map((id) => macroFilterSeriesItems(items).find((item) => item.series_id === id))
    .filter(Boolean);
  const filtered = macroFilterSeriesItems(items);
  els.macroSeriesSearchResults.innerHTML = `
    <div class="macro-series-result-grid">
      ${(rows.length ? rows : filtered.slice(0, 8)).map((item) => `
        <button type="button" class="macro-series-result" data-macro-series-id="${escapeHtml(item.series_id || "")}">
          <strong>${escapeHtml(item.series_id || "")}</strong>
          <span>${escapeHtml(item.display_name || "")}</span>
          <em>${escapeHtml(MACRO_CATEGORY_LABELS[item.category] || item.category || "macro")}</em>
        </button>
      `).join("") || decisionEmpty("표시할 매크로 시계열이 없습니다.")}
    </div>
  `;
}

function renderMacroSeriesSearchResults(data = {}) {
  if (!els.macroSeriesSearchResults) return;
  const rawItems = Array.isArray(data.items) ? data.items : [];
  const items = macroFilterSeriesItems(rawItems);
  renderMacroComparePlaceholder(rawItems);
  if (!items.length) {
    els.macroSeriesSearchResults.innerHTML = decisionEmpty("검색 결과가 없습니다. 검색어 또는 범주/공급자 필터를 조정해보세요.");
    return;
  }
  els.macroSeriesSearchResults.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.data_quality?.status))}">${escapeHtml(data.data_quality?.status || "registry")}</span>
      <span>${escapeHtml(data.query || "popular")} · ${escapeHtml(_fmtNumber(items.length))}/${escapeHtml(_fmtNumber(rawItems.length))}개 결과</span>
    </div>
    <div class="macro-series-result-grid">
      ${items.map((item) => {
        const latest = item.latest || {};
        return `
          <button type="button" class="macro-series-result" data-macro-series-id="${escapeHtml(item.series_id || "")}">
            <strong>${escapeHtml(item.series_id || "")}</strong>
            <span>${escapeHtml(item.display_name || "")}</span>
            <em>${escapeHtml(MACRO_CATEGORY_LABELS[item.category] || item.category || "macro")} · ${escapeHtml(macroValueText(latest.value, item.unit))}</em>
            <small>${escapeHtml(item.interpretation_hint || item.description || "구조화된 매크로 레지스트리 항목")}</small>
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function renderMacroSeriesSearchItems(items = [], label = "") {
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) return "";
  return `
    <div class="macro-related-block">
      <div class="decision-section-title">${escapeHtml(label)}</div>
      <div class="macro-series-result-grid compact">
        ${rows.map((item) => `
          <button type="button" class="macro-series-result" data-macro-series-id="${escapeHtml(item.series_id || "")}">
            <strong>${escapeHtml(item.series_id || "")}</strong>
            <span>${escapeHtml(item.display_name || "")}</span>
            <em>${escapeHtml(macroValueText(item.latest?.value, item.unit))} · ${escapeHtml(item.latest?.date || "사용 불가")}</em>
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function renderMacroObservationRows(series = {}) {
  const observations = Array.isArray(series.observations) ? series.observations.slice(-24).reverse() : [];
  if (!observations.length) return decisionEmpty("표시할 원자료 관측치가 없습니다.");
  return `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>날짜</th><th>표시값</th><th>원값</th><th>변환</th><th>비교 기준</th><th>공급원</th></tr></thead>
        <tbody>
          ${observations.map((row) => `
            <tr>
              <td>${escapeHtml(row.date || "-")}</td>
              <td>${escapeHtml(macroValueText(row.value, series.unit))}</td>
              <td>${escapeHtml(row.raw_value === null || row.raw_value === undefined ? "사용 불가" : fmtDecimal(Number(row.raw_value), 3))}</td>
              <td>${escapeHtml(row.metadata?.transform || "level")}</td>
              <td>${escapeHtml(row.metadata?.comparison_date || "-")}</td>
              <td>${escapeHtml(row.source || "unknown")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function macroCachedSeriesSearch(query, limit = 12) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  const terms = normalizedQuery ? normalizedQuery.split(/\s+/).filter(Boolean) : [];
  const items = Array.isArray(state.macroSeriesList?.items) ? state.macroSeriesList.items : [];
  const matched = items.filter((item) => {
    if (!terms.length) return true;
    const haystack = [
      item.series_id,
      item.display_name,
      item.category,
      item.subcategory,
      item.provider,
      ...(Array.isArray(item.aliases) ? item.aliases : []),
    ].filter(Boolean).join(" ").toLowerCase();
    return terms.every((term) => haystack.includes(term));
  }).slice(0, limit);
  return {
    status: "cache_fallback",
    query,
    items: matched,
    data_quality: state.macroDataQuality?.data_quality || state.macroDataQuality || state.macroDashboard?.data_quality || {},
  };
}

function renderMacroSeriesDetail(data = {}) {
  if (!els.macroSeriesDetailSurface) return;
  const series = data.series || {};
  const definition = data.definition || {};
  const stats = data.statistics || {};
  const quality = data.data_quality || series.data_quality || {};
  const interpretation = data.interpretation || {};
  els.macroSeriesDetailSurface.innerHTML = `
    <div class="macro-detail-head">
      <div>
        <strong>${escapeHtml(series.series_id || definition.series_id || "")}</strong>
        <span>${escapeHtml(series.display_name || definition.display_name || "")}</span>
      </div>
      <span class="decision-badge ${escapeHtml(decisionStatusClass(quality.status))}">${escapeHtml(quality.status || "unknown")}</span>
    </div>
    <div class="decision-metric-grid dense">
      ${decisionMetric("최근값", macroValueText(series.latest?.value, series.unit), decisionStatusClass(quality.status))}
      ${decisionMetric("최근일", series.latest?.date || "사용 불가", series.latest ? "ok" : "warn")}
      ${decisionMetric("1기간 변화", stats.change_1_period === null || stats.change_1_period === undefined ? "사용 불가" : fmtDecimal(Number(stats.change_1_period), 3), "ok")}
      ${decisionMetric("3기간 변화", stats.change_3_period === null || stats.change_3_period === undefined ? "사용 불가" : fmtDecimal(Number(stats.change_3_period), 3), "ok")}
      ${decisionMetric("관측치", _fmtNumber(stats.observation_count || 0), stats.observation_count ? "ok" : "warn")}
      ${decisionMetric("범위", `${stats.start_date || "-"} / ${stats.end_date || "-"}`, stats.start_date ? "ok" : "warn")}
      ${decisionMetric("최소/최대", `${fmtDecimal(Number(stats.min || 0), 2)} / ${fmtDecimal(Number(stats.max || 0), 2)}`, stats.observation_count ? "ok" : "warn")}
      ${decisionMetric("빈도", series.frequency || definition.frequency || "-", "ok")}
    </div>
    <div class="decision-summary ${escapeHtml(decisionStatusClass(quality.status))}">
      ${escapeHtml(interpretation.latest_summary || "")}
      ${escapeHtml(interpretation.trend_summary ? ` ${interpretation.trend_summary}` : "")}
      ${escapeHtml(interpretation.macro_use ? ` ${interpretation.macro_use}` : "")}
    </div>
    ${renderMacroSeriesChart(series, series.display_name || series.series_id || "Macro series")}
    ${renderMacroSeriesSearchItems(data.component_series || [], "구성·분해 지표")}
    ${renderMacroSeriesSearchItems(data.related_series || [], "관련 시계열")}
    <div class="decision-section-title">최근 원자료</div>
    ${renderMacroObservationRows(series)}
    ${(quality.errors || quality.notes || []).length ? `<div class="macro-warning">${escapeHtml([...(quality.errors || []), ...(quality.notes || [])].join(" "))}</div>` : ""}
  `;
}

async function loadMacroSeriesDetail(seriesId) {
  const id = String(seriesId || "").trim();
  if (!id || !els.macroSeriesDetailSurface) return;
  els.macroSeriesDetailSurface.innerHTML = decisionEmpty(`${escapeHtml(id)} 상세 데이터를 불러오는 중입니다.`);
  try {
    const data = await macroFetchJsonWithTimeout(API.macroSeriesDetail(id, 240), {}, MACRO_PANEL_TIMEOUT_MS);
    state.macroSeriesDetail = data;
    renderMacroSeriesDetail(data);
  } catch (err) {
    els.macroSeriesDetailSurface.innerHTML = decisionEmpty(`시계열 상세 로드 실패: ${err.message || err}`);
  }
}

async function searchMacroSeries() {
  if (!els.macroSeriesSearchInput) return;
  const query = els.macroSeriesSearchInput.value.trim();
  if (!query) {
    renderMacroSearchStarter(state.macroSeriesList || {});
    await loadMacroDefaultSeriesDetail(state.macroSeriesList || {});
    return;
  }
  setButtonBusy(els.macroSeriesSearchRun, true, "검색 중");
  if (els.macroSeriesSearchResults) {
    els.macroSeriesSearchResults.innerHTML = decisionEmpty("매크로 레지스트리와 저장된 관측치를 검색하는 중입니다.");
  }
  try {
    let data;
    try {
      data = await macroFetchJsonWithTimeout(API.macroSeriesSearch(query, 12), {}, 9000);
    } catch (searchErr) {
      data = macroCachedSeriesSearch(query, 12);
      data.data_quality = {
        ...(data.data_quality || {}),
        status: data.data_quality?.status || "partial",
        notes: [...(data.data_quality?.notes || []), `live search fallback: ${searchErr.message || searchErr}`],
      };
    }
    state.macroSeriesSearch = data;
    renderMacroSeriesSearchResults(data);
    const first = macroFilterSeriesItems(data.items || [])?.[0]?.series_id;
    if (first) await loadMacroSeriesDetail(first);
  } catch (err) {
    if (els.macroSeriesSearchResults) {
      els.macroSeriesSearchResults.innerHTML = decisionEmpty(`매크로 검색 실패: ${err.message || err}`);
    }
  } finally {
    setButtonBusy(els.macroSeriesSearchRun, false);
  }
}

async function loadMacroDefaultSeriesDetail(seriesList = {}) {
  if (!els.macroSeriesDetailSurface) return;
  const existingId = state.macroSeriesDetail?.series?.series_id || state.macroSeriesDetail?.definition?.series_id;
  const detailText = els.macroSeriesDetailSurface.innerText || "";
  if (existingId && !/시계열을 선택하면|Macro series detail|상세 데이터를 불러오는 중/.test(detailText)) return;
  const query = els.macroSeriesSearchInput?.value?.trim?.() || "";
  const cached = macroCachedSeriesSearch(query, 12);
  const candidates = macroFilterSeriesItems(cached.items?.length ? cached.items : (seriesList.items || []));
  const first = candidates[0]?.series_id;
  if (!first) {
    els.macroSeriesDetailSurface.innerHTML = decisionEmpty("로드 가능한 매크로 시계열 상세가 없습니다.");
    return;
  }
  await loadMacroSeriesDetail(first);
}

function renderMacroRegime(regime = {}, signals = []) {
  if (!els.macroRegimeSurface) return;
  const scores = regime.scores || {};
  els.macroRegimeSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(regime.name === "unknown" ? "warn" : "ok")}">${escapeHtml(regime.display_name || regime.name || "unknown")}</span>
      <span>신뢰도 ${escapeHtml(fmtDecimal(Number(regime.confidence || 0), 2))} · 위험 ${escapeHtml(regime.risk_level || "unknown")}</span>
    </div>
    <div class="decision-metric-grid dense">
      ${Object.entries(scores).map(([key, value]) => decisionMetric(key.replace(/_/g, " "), fmtDecimal(Number(value), 1), "ok")).join("")}
    </div>
    <div class="decision-section-title">신호</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>신호</th><th>값</th><th>점수</th><th>신뢰도</th><th>증거</th></tr></thead>
        <tbody>
          ${(Array.isArray(signals) ? signals : []).map((signal) => `
            <tr>
              <td>${escapeHtml(signal.name || "")}</td>
              <td>${escapeHtml(signal.value || "unknown")}</td>
              <td>${escapeHtml(fmtDecimal(Number(signal.score || 0), 1))}</td>
              <td>${escapeHtml(fmtDecimal(Number(signal.confidence || 0), 2))}</td>
              <td>${escapeHtml((signal.evidence || []).slice(0, 3).join(" · ") || "데이터 부족")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    ${(regime.missing_inputs || []).length ? `<div class="macro-warning">누락 입력: ${escapeHtml(regime.missing_inputs.join(", "))}</div>` : ""}
  `;
}

function renderMacroAssetImpact(data) {
  if (!els.macroAssetImpactSurface) return;
  const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
  els.macroAssetImpactSurface.innerHTML = `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>자산군</th><th>영향</th><th>신뢰도</th><th>근거</th><th>핵심 리스크</th></tr></thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td>${escapeHtml(item.asset_class || "")}</td>
              <td><span class="table-status ${escapeHtml(item.impact === "negative" ? "warn" : item.impact === "unknown" ? "muted" : "ok")}">${escapeHtml(item.impact || "unknown")}</span></td>
              <td>${escapeHtml(fmtDecimal(Number(item.confidence || 0), 2))}</td>
              <td>${escapeHtml(item.reason || "")}</td>
              <td>${escapeHtml((item.key_risks || []).join("; ") || "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function macroFallbackEtfCandidates(hint = {}) {
  const rows = [];
  const equityBias = hint.equity_bias || "unknown";
  const bondBias = hint.bond_bias || "unknown";
  const cashBias = hint.cash_bias || "unknown";
  const alternativeBias = hint.alternative_bias || "unknown";
  const durationBias = hint.duration_bias || "unknown";
  const creditBias = hint.credit_bias || "unknown";
  rows.push({
    sleeve: "equity",
    bias: equityBias,
    tickers: equityBias === "lower_range" ? ["USMV", "SPLV"] : (["upper_range", "increase"].includes(equityBias) ? ["SPY", "QQQ", "IWM"] : ["SPY", "VT"]),
    role: equityBias === "lower_range" ? "defensive_equity_or_reduce" : "equity_core",
    rationale: "개별 종목이 아닌 광범위 주식 ETF 후보입니다.",
  });
  rows.push({
    sleeve: "bonds",
    bias: bondBias,
    tickers: durationBias === "shorter" ? ["SHY", "SGOV", "BIL"] : (String(durationBias).startsWith("longer") ? ["BND", "IEF", "TLT"] : ["BND", "IEF"]),
    role: durationBias === "shorter" ? "short_duration_defense" : "core_duration",
    rationale: "금리 민감도와 듀레이션 정책에 맞춘 채권 ETF 후보입니다.",
  });
  rows.push({
    sleeve: "cash",
    bias: cashBias,
    tickers: cashBias === "increase" ? ["SGOV", "BIL"] : ["SGOV"],
    role: "liquidity_buffer",
    rationale: "현금성 유동성 관리용 단기 국채 ETF 후보입니다.",
  });
  rows.push({
    sleeve: "alternatives",
    bias: alternativeBias,
    tickers: ["GLD", "TIP", ...(alternativeBias === "upper_range" ? ["DBC"] : [])],
    role: "diversifier",
    rationale: "인플레이션과 실물자산 민감도 관찰용 ETF 후보입니다.",
  });
  rows.push({
    sleeve: "credit",
    bias: creditBias,
    tickers: creditBias === "higher_quality" || creditBias === "lower_quality" ? ["LQD", "IGSB"] : ["LQD", "HYG"],
    role: "credit_watch",
    rationale: "신용 스프레드와 등급 선호를 반영한 회사채 ETF 후보입니다.",
  });
  return rows;
}

function renderMacroEtfCandidates(hint = {}) {
  const candidates = macroEtfCandidatesFromHint(hint);
  return `
    <div class="macro-etf-panel">
      <div class="decision-section-title">ETF 편입 후보 · 개별종목 제외</div>
      <div class="macro-etf-grid">
        ${candidates.map((item) => `
          <article class="macro-etf-card">
            <div class="macro-etf-card-head">
              <strong>${escapeHtml(item.sleeve || "sleeve")}</strong>
              <span>${escapeHtml(item.bias || "unknown")}</span>
            </div>
            <div class="macro-etf-tickers">
              ${(Array.isArray(item.tickers) ? item.tickers : []).map((ticker) => `<span>${escapeHtml(ticker)}</span>`).join(" ")}
            </div>
            <small>${escapeHtml(item.role || "")}</small>
            <p>${escapeHtml(item.rationale || "")}</p>
          </article>
        `).join("")}
      </div>
      <div class="macro-etf-note">자문용 후보만 표시합니다. AI Portfolio 정책 변경, 주문 생성, 자동 리밸런싱은 실행하지 않습니다.</div>
    </div>
  `;
}

function macroEtfCandidatesFromHint(hint = {}) {
  return Array.isArray(hint.etf_candidates) && hint.etf_candidates.length
    ? hint.etf_candidates
    : macroFallbackEtfCandidates(hint);
}

function macroSleevePlan(item = {}, hint = {}) {
  const sleeve = String(item.sleeve || "").toLowerCase();
  const riskLevel = String(hint.risk_level || "").toLowerCase();
  const equityBias = String(hint.equity_bias || "").toLowerCase();
  const durationBias = String(hint.duration_bias || "").toLowerCase();
  const creditBias = String(hint.credit_bias || "").toLowerCase();
  if (sleeve.includes("equity")) {
    const range = riskLevel === "reduce" || equityBias === "lower_range" ? "25-40%" : (["increase", "upper_range"].includes(equityBias) ? "45-60%" : "35-50%");
    return {
      title: "주식 코어",
      range,
      action: "광범위 주식 ETF를 코어로 두되, 신용·유동성 경고가 있으면 저변동성 ETF를 우선 검토합니다.",
    };
  }
  if (sleeve.includes("bond")) {
    const range = durationBias === "shorter" ? "25-40%" : "30-50%";
    return {
      title: "채권·듀레이션",
      range,
      action: durationBias === "shorter"
        ? "금리 변동성이 높을 때는 단기 국채 ETF로 듀레이션을 줄이고 장기채 편입은 백테스트로 확인합니다."
        : "중기·장기 국채 ETF를 방어축으로 쓰되 금리 상승 구간의 손실 민감도를 별도로 점검합니다.",
    };
  }
  if (sleeve.includes("cash")) {
    return {
      title: "현금성 완충",
      range: riskLevel === "reduce" ? "10-20%" : "5-12%",
      action: "리밸런싱 대기 자금과 변동성 완충 자금입니다. 신호가 약하거나 데이터 품질이 낮을 때 비중을 높입니다.",
    };
  }
  if (sleeve.includes("alternative")) {
    return {
      title: "대체·인플레이션 방어",
      range: "5-15%",
      action: "금, 물가연동채, 원자재 ETF는 주식·채권 동시 약세 구간의 분산효과를 확인한 뒤 제한 비중으로 사용합니다.",
    };
  }
  if (sleeve.includes("credit")) {
    const range = creditBias === "higher_quality" || riskLevel === "reduce" ? "0-8%" : "5-12%";
    return {
      title: "신용 스프레드 관찰",
      range,
      action: "회사채 ETF는 경기·신용 스프레드 민감도가 커서 품질 경고가 있으면 투자등급 중심으로 제한합니다.",
    };
  }
  return {
    title: item.sleeve || "기타",
    range: "0-10%",
    action: "핵심 ETF와 상관관계, 비용, 유동성을 확인한 뒤 보조 비중으로만 검토합니다.",
  };
}

function renderMacroBriefPortfolioPlaybook(hint = {}, brief = {}) {
  const candidates = macroEtfCandidatesFromHint(hint);
  const regime = hint.regime || brief.regime || "unknown";
  const riskLevel = hint.risk_level || "unknown";
  return `
    <div class="macro-brief-playbook">
      <div class="decision-section-title">ETF 포트폴리오 구성 초안</div>
      <div class="decision-summary ok">
        위 포트폴리오 정책 힌트의 ETF 후보를 사용한 자문용 구성 절차입니다. 자동 주문이나 확정 투자비중이 아니며, 실제 적용 전 백테스트와 데이터 품질 확인이 필요합니다.
      </div>
      <div class="decision-status-row">
        <span class="decision-badge ok">Advisory only</span>
        <span>레짐 ${escapeHtml(regime)} · 위험 수준 ${escapeHtml(riskLevel)} · 후보 ${escapeHtml(_fmtNumber(candidates.length))}개 sleeve</span>
      </div>
      <div class="macro-playbook-grid">
        ${candidates.map((item) => {
          const plan = macroSleevePlan(item, hint);
          const tickers = Array.isArray(item.tickers) ? item.tickers : [];
          return `
            <article class="macro-playbook-card">
              <strong>${escapeHtml(plan.title)} · ${escapeHtml(plan.range)}</strong>
              <div class="macro-etf-tickers">${tickers.map((ticker) => `<span>${escapeHtml(ticker)}</span>`).join(" ")}</div>
              <p>${escapeHtml(plan.action)}</p>
            </article>
          `;
        }).join("")}
      </div>
      <div class="decision-section-title">실행 전 점검 순서</div>
      <div class="macro-portfolio-steps">
        <div class="macro-portfolio-step"><strong>1. 후보 ETF 확정</strong><p>각 sleeve에서 비용, 평균 거래량, 추적오차, 중복 노출을 비교해 대표 ETF 1-2개만 남깁니다.</p></div>
        <div class="macro-portfolio-step"><strong>2. 초기 비중 산정</strong><p>위 범위를 출발점으로 삼고, 주식·채권·현금·대체자산의 합계가 100%가 되도록 현금 sleeve에서 미세 조정합니다.</p></div>
        <div class="macro-portfolio-step"><strong>3. 백테스트 검증</strong><p>Quant Lab에서 같은 ETF 묶음과 기간을 넣고 CAGR, 변동성, Sharpe, MDD, 회전율, SPY 대비 성과를 확인합니다.</p></div>
        <div class="macro-portfolio-step"><strong>4. 리밸런싱 규칙</strong><p>월 1회 또는 목표 비중 대비 3-5%p 이탈 시 재검토하고, 매크로 품질 경고가 있으면 신호보다 방어 비중을 우선합니다.</p></div>
        <div class="macro-portfolio-step"><strong>5. 리스크 기록</strong><p>금리 급등, 신용 스프레드 확대, 달러 강세, 원자재 급변 같은 시나리오별 손실 경로를 저장해 다음 의사결정과 비교합니다.</p></div>
      </div>
    </div>
  `;
}

function renderMacroPolicyHint(hint = {}) {
  if (!els.macroPortfolioHintsSurface) return;
  els.macroPortfolioHintsSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${hint.advisory_only ? "ok" : "fail"}">${hint.advisory_only ? "자문 전용" : "점검 필요"}</span>
      <span>레짐 ${escapeHtml(hint.regime || "unknown")} · 리밸런싱 주의 ${hint.rebalance_attention ? "있음" : "없음"}</span>
    </div>
    <div class="decision-metric-grid dense">
      ${decisionMetric("주식 편향", hint.equity_bias || "unknown", "ok")}
      ${decisionMetric("채권 편향", hint.bond_bias || "unknown", "ok")}
      ${decisionMetric("현금 편향", hint.cash_bias || "unknown", "ok")}
      ${decisionMetric("듀레이션 편향", hint.duration_bias || "unknown", "ok")}
      ${decisionMetric("신용 편향", hint.credit_bias || "unknown", "ok")}
      ${decisionMetric("위험 수준", hint.risk_level || "unknown", hint.risk_level === "reduce" ? "warn" : "ok")}
    </div>
    <div class="decision-summary ${escapeHtml(decisionStatusClass(hint.data_quality?.status))}">${escapeHtml(hint.explanation || "")}</div>
    ${renderMacroEtfCandidates(hint)}
    ${(hint.warnings || []).length ? `<div class="macro-warning">${escapeHtml(hint.warnings.join(" "))}</div>` : ""}
  `;
}

function renderMacroDataQuality(data = {}, refreshStatus = {}) {
  if (!els.macroDataQualitySurface) return;
  const quality = data.data_quality || data;
  const rows = Array.isArray(data.series) ? data.series : [];
  const coverage = data.coverage || {};
  const statusCounts = coverage.status_counts || {};
  const scheduler = refreshStatus.scheduler || {};
  const lastResult = scheduler.last_result || {};
  const macroJob = lastResult.jobs?.macro_platform_data || {};
  const autoEnabled = scheduler.enabled && scheduler.jobs?.macro_platform_data;
  const intervalHours = Number(scheduler.interval_s || 0) / 3600;
  els.macroDataQualitySurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(quality.status))}">${escapeHtml(quality.status || "unknown")}</span>
      <span>${escapeHtml(data.scope === "all" ? "전체 registry" : "핵심 지표")} · 공급자 ${escapeHtml(quality.provider || "mixed")} · 마지막 갱신 ${escapeHtml(quality.last_updated || "사용 불가")}</span>
    </div>
    <div class="macro-quality-grid">
      ${decisionMetric("검증 시계열", _fmtNumber(coverage.evaluated_series || rows.length), "ok")}
      ${decisionMetric("정상 시계열", _fmtNumber(statusCounts.ok || 0), (statusCounts.stale || statusCounts.partial || statusCounts.unavailable) ? "warn" : "ok")}
      ${decisionMetric("누락 시계열", _fmtNumber((quality.missing_series || []).length), (quality.missing_series || []).length ? "warn" : "ok")}
      ${decisionMetric("지연 시계열", _fmtNumber((quality.stale_series || []).length), (quality.stale_series || []).length ? "warn" : "ok")}
      ${decisionMetric("오류", _fmtNumber((quality.errors || []).length), (quality.errors || []).length ? "warn" : "ok")}
      ${decisionMetric("메모", _fmtNumber((quality.notes || []).length), "ok")}
      ${decisionMetric("자동 갱신", autoEnabled ? "켜짐" : "꺼짐", autoEnabled ? "ok" : "warn")}
      ${decisionMetric("갱신 주기", intervalHours ? `${fmtDecimal(intervalHours, 1)}시간` : "대기", "ok")}
      ${decisionMetric("최근 갱신", macroJob.status || "대기", decisionStatusClass(macroJob.status || "unknown"))}
      ${decisionMetric("저장 행", _fmtNumber(Number(macroJob.rows_inserted || 0) + Number(macroJob.rows_updated || 0)), "ok")}
    </div>
    ${(quality.errors || []).length ? `<div class="macro-warning">${escapeHtml(quality.errors.slice(0, 6).join("; "))}</div>` : ""}
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>시계열</th><th>상태</th><th>최근일</th><th>신선도 기준</th><th>공급자</th><th>메모</th></tr></thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escapeHtml(row.series_id || "")}<br><small>${escapeHtml(row.category || "")}</small></td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(row.status || "unknown")}</span></td>
              <td>${escapeHtml(row.latest_date || "사용 불가")}</td>
              <td>${escapeHtml(row.frequency || "-")} · ${escapeHtml(_fmtNumber(row.stale_after_days || 0))}일</td>
              <td>${escapeHtml(row.provider || "unknown")}</td>
              <td>${escapeHtml([...(row.errors || []), ...(row.notes || [])].slice(0, 2).join("; "))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderMacroLoadStatus(message, status = "ok", detail = "", startedAt = null, generatedAt = "") {
  if (!els.macroLoadStatus) return;
  const parts = [detail, generatedAt ? fmtDate(generatedAt) : "", startedAt ? `소요 ${elapsedText(startedAt)}` : ""].filter(Boolean);
  els.macroLoadStatus.innerHTML = `
    <div class="decision-completion ${escapeHtml(decisionStatusClass(status))}" role="status" aria-live="polite">
      <strong>${escapeHtml(message)}</strong>
      <span>${escapeHtml(parts.join(" · ") || status)}</span>
    </div>
  `;
}

function setMacroLoadStatus(payload = {}, startedAt = Date.now(), detail = "", status = "ok") {
  const generatedAt = payload.generated_at || payload.as_of || "";
  const statusText = payload.status || status || "unknown";
  renderMacroLoadStatus(`Macro load · ${statusText}`, statusText, detail || "대시보드 집계 완료", startedAt, generatedAt);
}

function renderMacroPanelFailure(surface, label, error) {
  if (!surface) return;
  const message = error?.message || String(error || "unknown");
  surface.innerHTML = decisionEmpty(`${label} 로드 실패: ${message}`);
}

function renderMacroActionPaneStarters() {
  if (els.macroScenarioResult && !state.macroScenario) {
    els.macroScenarioResult.innerHTML = decisionEmpty("시나리오를 선택하면 자산 영향과 sleeve 힌트를 자문용으로만 표시합니다.");
  }
  if (els.macroResearchPreviewResult && !state.macroResearchContext) {
    els.macroResearchPreviewResult.innerHTML = decisionEmpty("티커별 매크로 리서치 컨텍스트를 미리 확인합니다. 결과는 자문용입니다.");
  }
}

function renderMacroProviderHealth(data = {}) {
  if (!els.macroProviderHealthSurface) return;
  const rendered = window.FinGPTMacroUi?.providerHealth?.(data);
  els.macroProviderHealthSurface.innerHTML = rendered || decisionEmpty("Macro UI module is unavailable.");
}

function renderMacroScenarioResult(data = {}, startedAt = Date.now()) {
  const target = els.macroScenarioResult || els.macroScenarioSurface;
  if (!target) return;
  const impacts = Array.isArray(data.asset_impacts) ? data.asset_impacts : [];
  const sleeveHints = Array.isArray(data.sleeve_hints)
    ? data.sleeve_hints
    : Object.entries(data.sleeve_hints || {}).map(([sleeve, hint]) => ({ sleeve, hint }));
  target.innerHTML = `
    ${renderActionCompletion("매크로 시나리오 계산 완료", startedAt, data.scenario?.name || data.scenario?.scenario_name || "scenario", decisionStatusClass(data.risk_level))}
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(data.advisory_only ? "ok" : "fail")}">${data.advisory_only ? "자문 전용" : "점검 필요"}</span>
      <span>위험 수준 ${escapeHtml(data.risk_level || "unknown")} · 데이터 품질 ${escapeHtml(data.data_quality?.status || data.data_quality || "unknown")}</span>
    </div>
    <div class="decision-summary ${escapeHtml(decisionStatusClass(data.risk_level))}">${escapeHtml(data.explanation || "시나리오 설명이 없습니다.")}</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>자산군</th><th>영향</th><th>신뢰도</th><th>근거</th></tr></thead>
        <tbody>
          ${impacts.map((item) => `
            <tr>
              <td>${escapeHtml(item.asset_class || item.asset || "")}</td>
              <td><span class="table-status ${escapeHtml(item.impact === "negative" ? "warn" : item.impact === "positive" ? "ok" : "muted")}">${escapeHtml(item.impact || "unknown")}</span></td>
              <td>${escapeHtml(fmtDecimal(Number(item.confidence || 0), 2))}</td>
              <td>${escapeHtml(item.reason || item.rationale || "-")}</td>
            </tr>
          `).join("") || `<tr><td colspan="4">자산 영향 데이터가 없습니다.</td></tr>`}
        </tbody>
      </table>
    </div>
    <div class="macro-sleeve-hints">
      ${sleeveHints.map((item) => `
        <span><strong>${escapeHtml(item.sleeve || item.name || "")}</strong>${escapeHtml(item.hint || item.action || item.bias || "")}</span>
      `).join("") || "<span>표시할 sleeve 힌트가 없습니다.</span>"}
    </div>
    <div class="macro-warning">이 결과는 포트폴리오 정책 변경, 주문 생성, 자동 리밸런싱을 수행하지 않는 자문용 시나리오입니다.</div>
  `;
}

async function runMacroScenario(presetName) {
  const payload = MACRO_SCENARIO_PRESETS[presetName];
  if (!payload || !els.macroScenarioSurface) return;
  const startedAt = Date.now();
  const target = els.macroScenarioResult || els.macroScenarioSurface;
  if (target) target.innerHTML = decisionEmpty(`${payload.name} 시나리오를 계산하는 중입니다.`);
  try {
    const data = await macroFetchJsonWithTimeout(API.macroScenario, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, MACRO_PANEL_TIMEOUT_MS);
    state.macroScenario = data;
    renderMacroScenarioResult(data, startedAt);
  } catch (err) {
    if (target) target.innerHTML = decisionEmpty(`시나리오 계산 실패: ${err.message || err}`);
  }
}

function renderMacroResearchContext(data = {}, startedAt = Date.now()) {
  if (!els.macroResearchPreviewResult) return;
  const hints = data.portfolio_hints || {};
  const warnings = Array.isArray(data.data_quality_warnings) ? data.data_quality_warnings : [];
  const context = data.macro_context || data.context || data.summary || data.explanation || "";
  els.macroResearchPreviewResult.innerHTML = `
    ${renderActionCompletion("리서치 컨텍스트 미리보기 완료", startedAt, data.ticker || "ticker", warnings.length ? "warn" : "ok")}
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(hints.advisory_only === false ? "fail" : "ok")}">${hints.advisory_only === false ? "점검 필요" : "자문 전용"}</span>
      <span>${escapeHtml(data.ticker || "")} · 품질 경고 ${escapeHtml(_fmtNumber(warnings.length))}개</span>
    </div>
    <div class="decision-summary ${warnings.length ? "warn" : "ok"}">${escapeHtml(typeof context === "string" ? context : JSON.stringify(context))}</div>
    <div class="decision-metric-grid dense">
      ${decisionMetric("레짐", hints.regime || data.regime || "unknown", "ok")}
      ${decisionMetric("주식", hints.equity_bias || "unknown", "ok")}
      ${decisionMetric("채권", hints.bond_bias || "unknown", "ok")}
      ${decisionMetric("위험", hints.risk_level || "unknown", hints.risk_level === "reduce" ? "warn" : "ok")}
    </div>
    ${warnings.length ? `<div class="macro-warning">${escapeHtml(warnings.join(" "))}</div>` : ""}
  `;
}

async function runMacroResearchPreview() {
  const ticker = String(els.macroResearchTicker?.value || "").trim();
  if (!ticker || !els.macroResearchPreviewResult) return;
  const startedAt = Date.now();
  setButtonBusy(els.macroResearchPreviewRun, true, "조회 중");
  els.macroResearchPreviewResult.innerHTML = decisionEmpty(`${escapeHtml(ticker)} 매크로 리서치 컨텍스트를 불러오는 중입니다.`);
  try {
    const data = await macroFetchJsonWithTimeout(API.macroResearchContext(ticker), {}, MACRO_PANEL_TIMEOUT_MS);
    state.macroResearchContext = data;
    renderMacroResearchContext(data, startedAt);
  } catch (err) {
    els.macroResearchPreviewResult.innerHTML = decisionEmpty(`리서치 컨텍스트 조회 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.macroResearchPreviewRun, false);
  }
}

async function macroFetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function macroFetchJsonWithTimeout(url, options = {}, timeoutMs = 9000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await macroFetchJson(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err?.name === "AbortError") throw new Error(`timeout after ${timeoutMs}ms`);
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

let macroCategoryHydrationRun = 0;

async function hydrateMacroCategoryPanels() {
  const runId = ++macroCategoryHydrationRun;
  const panels = [
    [API.macroInterestRates, els.macroInterestRatesSurface, "금리 패널"],
    [API.macroInflation, els.macroInflationSurface, "인플레이션 패널"],
    [API.macroGrowthLabor, els.macroGrowthLaborSurface, "성장·고용 패널"],
    [API.macroHousingConsumer, els.macroHousingConsumerSurface, "주택·소비 패널"],
    [API.macroYieldCurve, els.macroYieldCurveSurface, "수익률곡선 패널"],
    [API.macroLiquidityCredit, els.macroLiquidityCreditSurface, "유동성·신용 패널"],
    [API.macroFinancialConditions, els.macroFinancialConditionsSurface, "금융여건 패널"],
    [API.macroFxDollar, els.macroFxDollarSurface, "FX·달러 패널"],
    [API.macroCommodities, els.macroCommoditiesSurface, "원자재 패널"],
  ];
  for (const [url, surface, label] of panels) {
    if (runId !== macroCategoryHydrationRun) return;
    try {
      const data = await macroFetchJsonWithTimeout(url, {}, MACRO_PANEL_TIMEOUT_MS);
      renderMacroCategory(surface, data);
    } catch (err) {
      renderMacroPanelFailure(surface, label, err);
    }
  }
}

function macroDataSurfaces() {
  return [
    els.macroOverviewSurface,
    els.macroLoadStatus,
    els.macroCoverageSurface,
    els.macroProviderHealthSurface,
    els.macroIndicatorTable,
    els.macroChartSurface,
    els.macroInterestRatesSurface,
    els.macroInflationSurface,
    els.macroGrowthLaborSurface,
    els.macroHousingConsumerSurface,
    els.macroYieldCurveSurface,
    els.macroLiquidityCreditSurface,
    els.macroFinancialConditionsSurface,
    els.macroFxDollarSurface,
    els.macroCommoditiesSurface,
    els.macroRegimeSurface,
    els.macroAssetImpactSurface,
    els.macroCompareSurface,
    els.macroPortfolioHintsSurface,
    els.macroDataQualitySurface,
  ].filter(Boolean);
}

async function loadMacroProgressive(force = false) {
  if (!els.macroOverviewSurface) return false;
  if (!force && state.macroLoaded) return true;
  if (!force && state.macroLoading) return false;
  const startedAt = Date.now();
  const preserveExisting = !!(force && (state.macroLoaded || state.macroDashboard || state.macroOverview));
  state.macroLoading = true;
  setButtonBusy(els.macroRefresh, true, "새로고침 중");
  if (preserveExisting) {
    renderMacroLoadStatus("매크로 대시보드 재로딩 중", "warn", "기존 대시보드 화면을 유지합니다.", startedAt);
  } else {
    macroDataSurfaces().forEach((surface) => { surface.innerHTML = decisionEmpty("매크로 데이터를 불러오는 중입니다."); });
    renderMacroLoadStatus("매크로 대시보드 로드 중", "ok", "집계 데이터를 먼저 불러오는 중입니다.", startedAt);
    renderMacroActionPaneStarters();
  }
  try {
    macroCategoryHydrationRun += 1;
    const dashboard = await macroFetchJsonWithTimeout(API.macroDashboard, {}, MACRO_DASHBOARD_TIMEOUT_MS);
    const overview = dashboard.overview || {};
    const dashboardQuality = dashboard.data_quality || overview.data_quality || {};
    const dashboardRefresh = dashboard.refresh || {};
    state.macroDashboard = dashboard;
    state.macroOverview = overview;
    renderMacroOverview(overview);
    renderMacroCoverage(dashboard.coverage || {});
    renderMacroIndicatorTable(overview.key_indicators || []);
    renderMacroCharts(overview);
    renderMacroRegime(overview.regime || {}, overview.signals || []);
    renderMacroAssetImpact(overview.asset_impact_summary || dashboard.asset_impacts || []);
    renderMacroDataQuality(dashboard.quality_detail || dashboard.data_quality || dashboardQuality, dashboardRefresh);
    renderMacroComparePlaceholder([]);
    renderMacroActionPaneStarters();
    setMacroLoadStatus(dashboard, startedAt, "대시보드 집계 렌더링 완료", dashboard.status || dashboardQuality.status || "ok");

    const panelTasks = [
      ["seriesList", API.macroSeriesList],
      ["providerHealth", API.macroProviderHealth],
      ["portfolioHints", API.macroPortfolioHints],
    ];
    const settled = await Promise.allSettled(
      panelTasks.map(([name, url]) => macroFetchJsonWithTimeout(url, {}, MACRO_PANEL_TIMEOUT_MS)
        .then((data) => ({ name, data }))
        .catch((error) => Promise.reject({ name, error })))
    );
    const results = {};
    const failures = [];
    const failureByName = {};
    settled.forEach((result) => {
      if (result.status === "fulfilled") {
        results[result.value.name] = result.value.data;
      } else {
        const name = result.reason?.name || "unknown";
        const error = result.reason?.error || result.reason;
        failureByName[name] = error;
        failures.push(`${name}: ${error?.message || String(error || "unknown")}`);
      }
    });

    if (results.seriesList) {
      state.macroSeriesList = results.seriesList;
      renderMacroCoverage(results.seriesList);
      renderMacroSearchStarter(results.seriesList);
      await loadMacroDefaultSeriesDetail(results.seriesList);
    } else {
      renderMacroSearchStarter({ items: [] });
    }
    if (results.providerHealth) {
      state.macroProviderHealth = results.providerHealth;
      renderMacroProviderHealth(results.providerHealth);
    } else {
      renderMacroPanelFailure(els.macroProviderHealthSurface, "공급자 상태 패널", failureByName.providerHealth);
    }
    if (results.portfolioHints) {
      state.macroPortfolioHint = results.portfolioHints;
      renderMacroPolicyHint(results.portfolioHints);
    } else {
      renderMacroPanelFailure(els.macroPortfolioHintsSurface, "포트폴리오 힌트 패널", failureByName.portfolioHints);
    }
    state.macroDataQuality = dashboard.quality_detail || dashboard.data_quality || dashboardQuality;
    state.macroRefreshStatus = dashboardRefresh;
    renderMacroDataQuality(state.macroDataQuality, state.macroRefreshStatus);
    state.macroLoaded = true;
    const failureDetail = failures.length
      ? `부분 실패 ${failures.length}개 · ${failures.slice(0, 2).join(" / ")}`
      : `${_fmtNumber(overview.key_indicators?.length || 0)}개 핵심 지표`;
    setMacroLoadStatus(dashboard, startedAt, failureDetail, failures.length ? "partial" : (dashboard.status || "ok"));
    if (els.macroOverviewSurface) {
      els.macroOverviewSurface.insertAdjacentHTML(
        "afterbegin",
        renderActionCompletion("매크로 데이터 갱신 완료", startedAt, failureDetail, failures.length ? "warn" : "ok")
      );
    }
    hydrateMacroCategoryPanels();
    return true;
  } catch (err) {
    const message = err.message || String(err);
    if (preserveExisting) {
      state.macroLoaded = true;
      renderMacroLoadStatus("매크로 대시보드 재로딩 실패", "warn", message, startedAt);
      renderMacroPanelFailure(els.macroDataQualitySurface, "매크로 대시보드 재로딩", err);
    } else {
      macroDataSurfaces().forEach((surface) => {
        surface.innerHTML = decisionEmpty(`매크로 데이터 로드 실패: ${message}`);
      });
      renderMacroActionPaneStarters();
      setMacroLoadStatus({ status: "failed" }, startedAt, message, "fail");
    }
    return false;
  } finally {
    state.macroLoading = false;
    setButtonBusy(els.macroRefresh, false);
  }
}

async function loadMacro(force = false) {
  return loadMacroProgressive(force);
}

async function refreshMacroData() {
  if (!els.macroOverviewSurface) return;
  const startedAt = Date.now();
  setButtonBusy(els.macroRefresh, true, "공급자 갱신 중");
  if (els.macroDataQualitySurface) {
    els.macroDataQualitySurface.innerHTML = decisionEmpty("최신 매크로 공급자 데이터를 데이터마트에 저장하는 중입니다.");
  }
  try {
    const result = await macroFetchJson(API.macroRefreshRun, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lookback_days: 365 * 5 }),
    });
    const refresh = result.refresh || {};
    state.macroLoaded = false;
    const reloaded = await loadMacro(true);
    if (!reloaded) {
      state.macroLoaded = !!(state.macroDashboard || state.macroOverview);
      renderMacroLoadStatus(
        "매크로 공급자 갱신 후 재로딩 실패",
        "warn",
        `${escapeHtml(refresh.status || "unknown")} · 기존 대시보드 화면을 유지합니다.`,
        startedAt
      );
      if (els.macroDataQualitySurface) {
        els.macroDataQualitySurface.insertAdjacentHTML(
          "afterbegin",
          `<div class="macro-warning">공급자 갱신은 응답했지만 대시보드 재로딩에 실패했습니다. 기존 화면을 유지합니다.</div>`
        );
      }
      return;
    }
    if (els.macroOverviewSurface) {
      els.macroOverviewSurface.insertAdjacentHTML(
        "afterbegin",
        renderActionCompletion(
          "매크로 공급자 갱신 완료",
          startedAt,
          `${escapeHtml(refresh.status || "unknown")} · 저장 ${_fmtNumber(Number(refresh.rows_inserted || 0) + Number(refresh.rows_updated || 0))}행`
        )
      );
    }
  } catch (err) {
    const message = err.message || String(err);
    renderMacroLoadStatus("매크로 공급자 갱신 실패", "warn", message, startedAt);
    renderMacroPanelFailure(els.macroDataQualitySurface, "매크로 공급자 갱신", err);
  } finally {
    setButtonBusy(els.macroRefresh, false);
  }
}

async function generateMacroBrief() {
  if (!els.macroBriefSurface) return;
  const startedAt = Date.now();
  setButtonBusy(els.macroBriefGenerate, true, "생성 중");
  els.macroBriefSurface.innerHTML = decisionEmpty("구조화된 매크로 데이터로 상세 브리프를 생성하는 중입니다.");
  try {
    const data = await macroFetchJson(API.macroBrief, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ include_prompt: false, use_llm: false, timeout_s: 8 }),
    });
    state.macroBrief = data;
    let hint = state.macroPortfolioHint;
    if (!hint) {
      try {
        hint = await macroFetchJson(API.macroPortfolioHints);
        state.macroPortfolioHint = hint;
      } catch (hintErr) {
        hint = {};
      }
    }
    els.macroBriefSurface.innerHTML = `
      ${renderActionCompletion("매크로 브리프 생성 완료", startedAt, data.is_fallback ? "규칙 기반 폴백" : "구조화 브리프")}
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(data.is_fallback ? "warn" : "ok")}">${escapeHtml(data.provider || "macro")}</span>
        <span>${data.is_fallback ? "규칙 기반 폴백" : "타임아웃 없는 구조화 생성"} · 품질 ${escapeHtml(data.data_quality?.status || "unknown")}</span>
      </div>
      ${(data.warnings || []).length ? `<div class="macro-warning">${escapeHtml(data.warnings.join(" "))}</div>` : ""}
      <pre class="macro-brief-text">${escapeHtml(data.content || "")}</pre>
      ${renderMacroBriefPortfolioPlaybook(hint, data)}
    `;
  } catch (err) {
    els.macroBriefSurface.innerHTML = decisionEmpty(`매크로 브리프 생성 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.macroBriefGenerate, false);
  }
}

async function exportMacroReport() {
  if (!els.macroBriefSurface) return;
  const startedAt = Date.now();
  const previous = els.macroBriefSurface.innerHTML;
  setButtonBusy(els.macroReportExport, true, "내보내는 중");
  els.macroBriefSurface.innerHTML = decisionEmpty("매크로 리포트 내보내기를 준비하는 중입니다.");
  try {
    const data = await macroFetchJson(API.macroReport);
    const filename = data.filename || `fingpt_macro_report_${Date.now()}.md`;
    downloadBlob(filename, data.content || "", "text/markdown");
    els.macroBriefSurface.innerHTML = `
      ${renderActionCompletion("매크로 리포트 내보내기 완료", startedAt, filename)}
      ${previous || decisionEmpty("브리프는 아직 생성되지 않았습니다.")}
    `;
  } catch (err) {
    els.macroBriefSurface.innerHTML = decisionEmpty(`매크로 리포트 내보내기 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.macroReportExport, false);
  }
}

function renderMetricGrid(metrics, status = "ok") {
  const rows = [
    ["총수익", fmtMetricRatio(metrics.total_return)],
    ["CAGR", fmtMetricRatio(metrics.cagr)],
    ["변동성", fmtMetricRatio(metrics.volatility)],
    ["Sharpe", fmtDecimal(metrics.sharpe, 2)],
    ["Sortino", fmtDecimal(metrics.sortino, 2)],
    ["MDD", fmtMetricRatio(metrics.max_drawdown)],
    ["Calmar", fmtDecimal(metrics.calmar, 2)],
    ["회전율", fmtDecimal(metrics.turnover, 2)],
    ["노출도", fmtMetricRatio(metrics.exposure)],
    ["거래 수", _fmtNumber(metrics.trade_count)],
  ];
  return `<div class="decision-metric-grid dense">${rows.map(([label, value]) => decisionMetric(label, value, status)).join("")}</div>`;
}

function backtestMetricsWithDerivedTotals(metrics, equityCurve) {
  const out = { ...(metrics || {}) };
  if (out.total_return === undefined || out.total_return === null) {
    const points = Array.isArray(equityCurve) ? equityCurve : [];
    const first = Number(points[0]?.equity);
    const last = Number(points[points.length - 1]?.equity);
    if (Number.isFinite(first) && first !== 0 && Number.isFinite(last)) {
      out.total_return = last / first - 1;
    }
  }
  return out;
}

function backtestRequestFromControls() {
  const tickers = parseTickerInput(els.backtestTicker?.value || "");
  const benchmark = normalizeTickerToken(els.backtestBenchmark?.value || "SPY") || "SPY";
  return {
    tickers,
    strategy: els.backtestStrategy?.value || "buy_and_hold",
    benchmark,
    compare_benchmark: !!els.backtestBenchmarkCompare?.checked,
    start_date: textInputValue(els.backtestStartDate),
    end_date: textInputValue(els.backtestEndDate),
    lookback_days: numberInputValue(els.backtestLookbackDays, 756, { min: 2, max: 5000 }),
    short_window: numberInputValue(els.backtestShortWindow, 20, { min: 1, max: 252 }),
    long_window: numberInputValue(els.backtestLongWindow, 50, { min: 2, max: 756 }),
    top_n: numberInputValue(els.backtestTopN, 1, { min: 1, max: 50 }),
    rebalance_every: numberInputValue(els.backtestRebalanceEvery, 21, { min: 1, max: 252 }),
    require_fresh_prices: !!els.backtestRequireFresh?.checked,
    use_research_score: !!els.backtestUseResearchScore?.checked,
    transaction_cost_bps: numberInputValue(els.backtestCostBps, 5, { min: 0, max: 1000 }),
    slippage_bps: numberInputValue(els.backtestSlippageBps, 2, { min: 0, max: 1000 }),
  };
}

function syncPortfolioFromBacktest() {
  const request = state.lastBacktestRequest || backtestRequestFromControls();
  if (els.portfolioTickers) {
    els.portfolioTickers.value = (request.tickers || []).join(",");
    renderSymbolTargetChips("portfolio");
  }
  if (els.portfolioStartDate) els.portfolioStartDate.value = request.start_date || "";
  if (els.portfolioEndDate) els.portfolioEndDate.value = request.end_date || "";
  if (els.portfolioLookbackDays) els.portfolioLookbackDays.value = String(request.lookback_days || 756);
  if (els.portfolioBenchmark) els.portfolioBenchmark.value = request.benchmark || (request.tickers || [])[0] || "SPY";
  if (els.backtestBenchmark) els.backtestBenchmark.value = request.benchmark || "SPY";
}

function enableStrictFreshnessFromUi() {
  if (!els.backtestRequireFresh) return;
  els.backtestRequireFresh.checked = true;
  els.backtestRequireFresh.focus?.();
  if (els.backtestSurface) {
    els.backtestSurface.insertAdjacentHTML(
      "afterbegin",
      '<div class="decision-completion" role="status" aria-live="polite" data-action-complete="true"><strong>최신 가격 강제 옵션이 켜졌습니다.</strong><span>다시 실행하면 공급자 갱신을 먼저 시도하고, 남은 stale 가격은 실패로 처리합니다.</span></div>'
    );
  }
}

async function loadDataHealth(force = false) {
  if (!els.homeDataHealth || (state.dataHealthLoaded && !force)) return;
  els.homeDataHealth.innerHTML = decisionEmpty("가격·거시·뉴스·공시 업데이트 상태를 확인하는 중입니다.");
  try {
    const res = await fetch(API.dataHealth);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const summary = data.summary || {};
    const status = summary.decision_status || data.status || "unknown";
    const counts = data.table_counts || {};
    const latest = data.latest_run || {};
    const providerRows = Array.isArray(data.recent_provider_status) ? data.recent_provider_status.slice(0, 6) : [];
    const qualityRows = Array.isArray(data.recent_quality_checks) ? data.recent_quality_checks.slice(0, 6) : [];
    const failedCount = Number(summary.failed_provider_rows || 0);
    const staleCount = Number(summary.stale_or_failed_quality_rows || 0);
    const coveredEmptyCount = Number(summary.covered_empty_provider_rows || 0);
    const runRows = Number(latest.rows_inserted || 0) + Number(latest.rows_updated || 0);
    els.homeDataHealth.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
        <span>${escapeHtml(latest.finished_at || latest.started_at || "업데이트 실행 이력 없음")} · ${escapeHtml(latest.market || "all")}</span>
      </div>
      <div class="decision-summary ${escapeHtml(decisionStatusClass(status))}">
        ${failedCount || staleCount
          ? `주의 필요: provider 실패 ${failedCount}건, 품질 경고 ${staleCount}건`
          : `업데이트 ${escapeHtml(latest.status || "ok")} · 이번 실행 반영 ${escapeHtml(_fmtNumber(runRows))}행${coveredEmptyCount ? ` · 적용 불가 empty ${escapeHtml(_fmtNumber(coveredEmptyCount))}건 정상 처리` : ""}`}
      </div>
      <div class="decision-metric-grid">
        ${decisionMetric("가격 행", _fmtNumber(counts.prices_daily), status)}
        ${decisionMetric("재무 스냅샷", _fmtNumber(counts.fundamentals_snapshots || 0), counts.fundamentals_snapshots ? "ok" : "warn")}
        ${decisionMetric("거시 관측치", _fmtNumber(counts.macro_observations), status)}
        ${decisionMetric("뉴스 evidence", _fmtNumber(counts.news_articles), counts.news_articles ? "ok" : "warn")}
        ${decisionMetric("공시 evidence", _fmtNumber(counts.filings), counts.filings ? "ok" : "warn")}
      </div>
      <div class="decision-section-title">최근 공급자 상태</div>
      <div class="decision-list">
        ${providerRows.length ? providerRows.map((row) => `
          <div class="decision-list-row">
            <span>${escapeHtml(row.provider || "provider")}${row.ticker ? ` · ${escapeHtml(row.ticker)}` : ""}${row.raw_status === "empty" ? " · empty 보강" : ""}</span>
            <strong class="${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(decisionStatusLabel(row.status || "unknown"))}</strong>
          </div>
        `).join("") : '<div class="muted small">No provider status rows yet.</div>'}
      </div>
      <div class="decision-section-title">최근 품질 점검</div>
      <div class="decision-list compact">
        ${qualityRows.length ? qualityRows.map((row) => `
          <div class="decision-list-row">
            <span>${escapeHtml(row.check_name || "quality")}${row.entity_id ? ` · ${escapeHtml(row.entity_id)}` : ""}</span>
            <strong class="${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(row.status || "unknown")}</strong>
          </div>
        `).join("") : '<div class="muted small">No quality checks recorded yet.</div>'}
      </div>
    `;
    updateGlobalQualitySummary({
      status,
      asOf: latest.finished_at || latest.started_at || data.as_of || "",
      updatedAt: latest.finished_at || latest.started_at || "",
      source: latest.market ? `data mart · ${latest.market}` : "data mart",
      observations: counts.prices_daily || counts.macro_observations || "",
      missing: failedCount || staleCount ? `provider ${failedCount} · quality ${staleCount}` : "없음",
      cache: latest.status || "",
    });
    state.dataHealthLoaded = true;
  } catch (err) {
    els.homeDataHealth.innerHTML = decisionEmpty(`데이터 마트 상태 조회 실패: ${err.message || err}`);
    updateGlobalQualitySummary({
      status: "unknown",
      source: "data mart",
      missing: "확인 불가",
      updatedAt: "",
    });
  }
}

async function loadAssetDetail() {
  if (!els.assetDetailSurface || !els.assetDetailTicker) return;
  const ticker = normalizeTickerToken(els.assetDetailTicker.value || "");
  const options = assetDetailOptionsFromControls();
  if (!ticker) {
    els.assetDetailSurface.innerHTML = decisionEmpty("티커를 입력해야 합니다.");
    return;
  }
  els.assetDetailSurface.innerHTML = decisionEmpty(`${ticker} 최신 종가를 확인한 뒤 선택 기간의 가격, 수익률 곡선, 리스크 지표를 계산하는 중입니다.`);
  try {
    const priceQuery = assetDetailPriceQueryOptions(options);
    const res = await fetch(API.dataPrices(ticker, 5000, priceQuery));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const latest = data.latest || {};
    const refreshWarning = assetDetailRefreshWarning(data, ticker);
    if (!data.count) {
      els.assetDetailSurface.innerHTML = decisionEmpty(`${ticker} 저장 가격이 없습니다. daily_update를 먼저 실행해야 합니다.`);
      return;
    }
    const allRows = Array.isArray(data.items) ? data.items : [];
    const rows = filterPriceRowsByAssetOptions(allRows, options);
    if (rows.length < 2) {
      els.assetDetailSurface.innerHTML = decisionEmpty(`${ticker} 선택 날짜 범위에 계산 가능한 가격 행이 부족합니다. 기간을 넓히거나 전체 범위를 선택하세요.`);
      return;
    }
    const scopedLatest = rows[rows.length - 1] || latest;
    const metrics = assetDetailMetrics(rows, scopedLatest);
    const freshnessStatus = data.asset_freshness?.freshness_status || (data.strict_freshness_violation ? "stale" : "fresh");
    const freshnessClass = freshnessStatus === "fresh" ? "ok" : decisionStatusClass(freshnessStatus);
    let benchmarkRows = [];
    let benchmarkWarning = "";
    if (options.compareBenchmark && options.benchmark && options.benchmark !== ticker) {
      try {
        const benchmarkRes = await fetch(API.dataPrices(options.benchmark, 5000, priceQuery));
        if (!benchmarkRes.ok) throw new Error(`HTTP ${benchmarkRes.status}`);
        const benchmarkData = await benchmarkRes.json();
        const benchmarkRefreshWarning = assetDetailRefreshWarning(benchmarkData, options.benchmark);
        if (benchmarkRefreshWarning) benchmarkWarning = benchmarkRefreshWarning;
        benchmarkRows = filterPriceRowsByAssetOptions(Array.isArray(benchmarkData.items) ? benchmarkData.items : [], options);
        if (benchmarkRows.length < 2) benchmarkWarning = `${options.benchmark} 벤치마크 가격 행이 부족해 비교 곡선을 숨겼습니다.`;
      } catch (err) {
        benchmarkWarning = `${options.benchmark} 벤치마크 조회 실패: ${err.message || err}`;
      }
    }
    els.assetDetailSurface.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(freshnessClass)}">${escapeHtml(freshnessStatus === "fresh" ? "정상" : freshnessStatus)}</span>
        <span>선택 ${escapeHtml(_fmtNumber(rows.length))}/${escapeHtml(_fmtNumber(allRows.length))}행 · ${escapeHtml(rows[0]?.date || "-")} -> ${escapeHtml(scopedLatest.date || "-")} · ${escapeHtml(scopedLatest.source || latest.source || "소스 미확인")}</span>
      </div>
      <div class="decision-chip-row">
        <span>보기 ${escapeHtml(options.view)}</span>
        <span>범위 ${escapeHtml(options.range)}</span>
        <span>시작 ${escapeHtml(options.startDate || "자동")}</span>
        <span>종료 ${escapeHtml(options.endDate || "최신")}</span>
        <span>최신 종가 보강 ${escapeHtml(priceQuery.startDate || "최근")} -> ${escapeHtml(priceQuery.endDate || "제공자 최신")}</span>
        <span>신선도 ${escapeHtml(data.freshness_policy?.profile || priceQuery.freshnessProfile || "research_default")} · 기대 ${escapeHtml(data.expected_latest_date || "unknown")}</span>
        ${options.compareBenchmark ? `<span>벤치마크 ${escapeHtml(options.benchmark)}</span>` : ""}
      </div>
      ${refreshWarning ? `<div class="decision-warning">${escapeHtml(refreshWarning)}</div>` : ""}
      ${benchmarkWarning ? `<div class="decision-warning">${escapeHtml(benchmarkWarning)}</div>` : ""}
      ${renderAssetDetailSections({ ticker, rows, allRows, latest: scopedLatest, metrics, options, benchmarkRows })}
    `;
  } catch (err) {
    els.assetDetailSurface.innerHTML = decisionEmpty(`자산 상세 조회 실패: ${err.message || err}`);
  }
}

function quantFeatureRequestFromControls() {
  const request = backtestRequestFromControls();
  const payload = {
    tickers: request.tickers,
    benchmark: request.benchmark || "SPY",
    start_date: request.start_date,
    end_date: request.end_date,
    freshness_profile: els.backtestFreshnessProfile?.value || "research_default",
    features: [
      { id: "momentum_63d" },
      { id: "risk_adjusted_momentum_63d" },
      { id: "realized_vol_21d" },
      { id: "drawdown_current" },
      { id: "ma_ratio_20_50" },
      { id: "relative_strength_spy_63d" },
    ],
  };
  if (els.backtestRequireFresh?.checked) payload.require_fresh_prices = true;
  return payload;
}

function quantSignalTemplateFromStrategy(strategy) {
  const clean = String(strategy || "").toLowerCase();
  if (clean === "momentum_ranking") return "momentum_ranking";
  if (clean === "risk_adjusted_momentum") return "risk_adjusted_momentum";
  if (clean === "research_confirmed_momentum") return "research_confirmed_momentum";
  if (clean === "moving_average") return "moving_average_trend";
  if (clean === "volatility_targeting") return "volatility_targeting";
  if (clean === "buy_and_hold") return "buy_and_hold";
  return "momentum_ranking";
}

const QUANT_TEMPLATE_LABELS = {
  buy_and_hold: "매수 후 보유",
  moving_average_trend: "이동평균 추세",
  volatility_targeting: "변동성 타깃",
  momentum_ranking: "모멘텀 랭킹",
  risk_adjusted_momentum: "위험조정 모멘텀",
  research_confirmed_momentum: "리서치 확인 모멘텀",
};

const PORTFOLIO_METHOD_LABELS = {
  equal_weight: "동일 비중",
  inverse_volatility: "역변동성",
  risk_parity: "리스크 패리티",
  minimum_volatility: "최소 변동성",
  max_sharpe: "최대 샤프",
  momentum_tilt: "모멘텀 틸트",
};

function quantTemplateLabel(template) {
  return QUANT_TEMPLATE_LABELS[String(template || "")] || String(template || "전략");
}

function portfolioMethodLabel(method) {
  return PORTFOLIO_METHOD_LABELS[String(method || "")] || String(method || "배분 방식");
}

function quantBacktestRequestFromControls() {
  const request = backtestRequestFromControls();
  const payload = {
    strategy_id: state.activeStrategyId || els.backtestStrategyRegistry?.value || null,
    tickers: request.tickers,
    benchmark: request.benchmark || "SPY",
    template: quantSignalTemplateFromStrategy(request.strategy),
    start_date: request.start_date,
    end_date: request.end_date,
    freshness_profile: els.backtestFreshnessProfile?.value || "research_default",
    rebalance_every: request.rebalance_every,
    lookback: request.short_window,
    top_n: request.top_n,
    portfolio_method: els.portfolioMethod?.value || "equal_weight",
    transaction_cost_bps: request.transaction_cost_bps,
    slippage_bps: request.slippage_bps,
    use_research_score: request.use_research_score,
  };
  if (els.backtestRequireFresh?.checked) payload.require_fresh_prices = true;
  return payload;
}

function formatQuantValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  if (Math.abs(num) <= 1.5) return fmtMetricRatio(num);
  return fmtDecimal(num, 2);
}

function renderDiagnosticsChips(values) {
  const items = Array.isArray(values) ? values : [];
  if (!items.length) return '<span>진단 없음</span>';
  return items.slice(0, 6).map((item) => `<span>${escapeHtml(String(item))}</span>`).join("");
}

function formatQuantWarning(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (text.startsWith("excluded_unavailable_assets:")) {
    return `데이터 없는 종목 자동 제외: ${text.replace("excluded_unavailable_assets:", "")}`;
  }
  if (text.startsWith("missing_assets:")) {
    return `데이터 없는 종목: ${text.replace("missing_assets:", "")}`;
  }
  if (text.startsWith("stale_assets:")) {
    return `오래된 가격: ${text.replace("stale_assets:", "")}`;
  }
  if (text === "strict_freshness_violation") return "엄격한 데이터 신선도 조건을 통과하지 못했습니다.";
  if (text === "ticker_universe_empty") return "선택된 종목 유니버스가 없습니다.";
  if (text === "executable_price_universe_empty") return "실행 가능한 가격 이력 종목이 없습니다.";
  if (text.startsWith("local_llm_generation_failed:")) return "로컬 LLM 응답이 불안정해 규칙 기반 초안을 표시했습니다.";
  if (text === "strategy_prompt_required") return "전략 프롬프트가 필요합니다.";
  return text;
}

function formatQuantWarnings(values) {
  return (Array.isArray(values) ? values : [])
    .map(formatQuantWarning)
    .filter(Boolean)
    .join(" ");
}

function renderResearchProvenancePanel(provenance) {
  const entries = Object.entries(provenance || {});
  if (!entries.length) return "";
  return `
    <div class="decision-section-title">리서치 확인</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>종목</th><th>상태</th><th>점수</th><th>실행</th><th>근거</th><th>만료</th></tr></thead>
        <tbody>
          ${entries.map(([ticker, item]) => `
            <tr>
              <td>${escapeHtml(ticker)}</td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(item.status))}">${escapeHtml(item.status || "unknown")}</span></td>
              <td>${escapeHtml(formatQuantValue(item.score))}</td>
              <td>${escapeHtml(item.run_id || "-")}</td>
              <td>${escapeHtml(_fmtNumber((item.evidence_ids || []).length))}</td>
              <td>${escapeHtml(item.expires_at || "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderFreshnessAuditPanel(diagnostics) {
  const policy = diagnostics?.freshness_policy || {};
  const audits = Object.entries(diagnostics?.asset_freshness || {});
  if (!Object.keys(policy).length && !audits.length) return "";
  const staleAuditCount = audits.filter(([, audit]) => {
    const status = String(audit?.freshness_status || "").toLowerCase();
    return ["stale", "stale_prior_close", "unknown", "unavailable", "missing"].includes(status);
  }).length;
  return `
    <div class="decision-section-title">데이터 신선도 정책</div>
    <div class="decision-chip-row">
      <span>${escapeHtml(policy.policy_id || "daily_price_policy")}</span>
      <span>profile ${escapeHtml(policy.profile || "research_default")}</span>
      <span>기준일 ${escapeHtml(diagnostics.expected_latest_date || policy.expected_latest_date || "알 수 없음")}</span>
      <span>허용 지연 ${escapeHtml(String(policy.max_market_calendar_lag_days ?? "-"))}일</span>
      <span>강제 최신 ${policy.require_fresh_prices ? "켜짐" : "꺼짐"}</span>
    </div>
    ${staleAuditCount && !policy.require_fresh_prices ? `
      <div class="decision-warning">
        ${escapeHtml(_fmtNumber(staleAuditCount))}개 자산의 가격 신선도를 다시 확인해야 합니다.
        <button type="button" class="linkish decision-inline-action" data-action="enable-strict-freshness">최신 가격 강제 후 다시 실행</button>
      </div>
    ` : ""}
    ${audits.length ? `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>종목</th><th>상태</th><th>최근일</th><th>지연</th><th>사유</th></tr></thead>
          <tbody>
            ${audits.map(([ticker, audit]) => `
              <tr>
                <td>${escapeHtml(ticker)}</td>
                <td><span class="table-status ${escapeHtml(decisionStatusClass(audit.freshness_status))}">${escapeHtml(audit.freshness_status || "unknown")}</span></td>
                <td>${escapeHtml(audit.latest_price_date || "unknown")}</td>
                <td>${escapeHtml(String(audit.market_calendar_lag_days ?? "-"))}</td>
                <td>${escapeHtml(audit.missing_reason || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : ""}
  `;
}

function renderSnapshotFreshnessBadge(snapshotFreshness = {}) {
  const status = snapshotFreshness.status || "unknown";
  const statusClass = status === "fresh" || status === "historical" ? "ok" : decisionStatusClass(status);
  const expected = snapshotFreshness.current_expected_latest_date || snapshotFreshness.expected_latest_date || "unknown";
  const stale = Array.isArray(snapshotFreshness.stale_assets) ? snapshotFreshness.stale_assets : [];
  const missing = Array.isArray(snapshotFreshness.missing_assets) ? snapshotFreshness.missing_assets : [];
  const detail = status === "historical"
    ? `historical ${snapshotFreshness.historical_end_date || ""}`
    : stale.length
      ? `stale ${stale.slice(0, 3).join(",")}`
      : missing.length
        ? `missing ${missing.slice(0, 3).join(",")}`
        : `expected ${expected}`;
  return `<span class="table-status ${escapeHtml(statusClass)}">${escapeHtml(status)}</span><br><span class="muted small">${escapeHtml(detail)}</span>`;
}

function renderRebalanceSnapshots(weights) {
  const snapshots = (Array.isArray(weights) ? weights : [])
    .filter((row) => row && (row.selected || row.target_weights || row.weights))
    .slice(-5);
  if (!snapshots.length) return "";
  return `
    <div class="decision-section-title">리밸런싱 귀속</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>신호일</th><th>체결일</th><th>선정</th><th>제외</th><th>회전율</th></tr></thead>
        <tbody>
          ${snapshots.map((row) => {
            const selected = Array.isArray(row.selected)
              ? row.selected.join(",")
              : Object.entries(row.weights || row.target_weights || {}).filter(([, weight]) => Number(weight) > 0).map(([ticker]) => ticker).join(",");
            const rejected = Array.isArray(row.rejected) ? row.rejected.join(",") : "";
            return `
              <tr>
                <td>${escapeHtml(row.signal_date || row.date || "")}</td>
                <td>${escapeHtml(row.execution_date || row.date || "")}</td>
                <td>${escapeHtml(selected || "-")}</td>
                <td>${escapeHtml(rejected || "-")}</td>
                <td>${escapeHtml(formatQuantValue(row.turnover ?? ""))}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderRiskContributionBars(contributions) {
  const entries = Object.entries(contributions || {}).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (!entries.length) return "";
  return `
    <div class="portfolio-weight-list">
      ${entries.map(([ticker, contribution]) => `
        <div class="portfolio-weight-row">
          <span>${escapeHtml(ticker)}</span>
          <div><i style="width:${Math.max(2, Math.min(100, Number(contribution) * 100))}%"></i></div>
          <strong>${escapeHtml(fmtPct(Number(contribution) * 100))}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderCorrelationPreview(matrix) {
  const assets = Object.keys(matrix || {}).slice(0, 5);
  if (!assets.length) return "";
  return `
    <div class="decision-section-title">상관관계 행렬</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th></th>${assets.map((asset) => `<th>${escapeHtml(asset)}</th>`).join("")}</tr></thead>
        <tbody>
          ${assets.map((rowAsset) => `
            <tr>
              <td>${escapeHtml(rowAsset)}</td>
              ${assets.map((colAsset) => `<td>${escapeHtml(fmtDecimal(matrix[rowAsset]?.[colAsset], 2))}</td>`).join("")}
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderPortfolioDecisionBrief({ entries, portfolioMetrics, diagnostics, riskContributions, method, benchmark, maxWeight }) {
  const largest = entries[0] || ["-", 0];
  const largestWeight = Number(largest[1] || 0);
  const effectivePositions = Number(diagnostics.effective_number_of_positions);
  const beta = Number(portfolioMetrics.beta_to_benchmark);
  const trackingError = Number(portfolioMetrics.tracking_error);
  const infoRatio = Number(portfolioMetrics.information_ratio);
  const maxRiskEntry = Object.entries(riskContributions || {})
    .sort((a, b) => Number(b[1]) - Number(a[1]))[0] || ["-", 0];
  const concentrationStatus = largestWeight > Math.min(0.5, Number(maxWeight || 1) * 0.95) ? "warn" : "ok";
  const betaStatus = Number.isFinite(beta) && beta > 1.1 ? "warn" : "ok";
  const teStatus = Number.isFinite(trackingError) && trackingError > 0.12 ? "warn" : "ok";
  const rebalanceText = entries
    .slice(0, 4)
    .map(([ticker, weight]) => `${ticker} ${fmtPct(Number(weight) * 100)}`)
    .join(" · ");
  return `
    <div class="decision-practical-grid portfolio-practical-grid">
      ${decisionMetric("배분 방식", portfolioMethodLabel(method), "ok")}
      ${decisionMetric("최대 편입", `${largest[0]} ${fmtPct(largestWeight * 100)}`, concentrationStatus)}
      ${decisionMetric("효과 포지션", fmtDecimal(effectivePositions, 2), Number.isFinite(effectivePositions) && effectivePositions >= 2 ? "ok" : "warn")}
      ${decisionMetric("최대 위험 기여", `${maxRiskEntry[0]} ${fmtPct(Number(maxRiskEntry[1]) * 100)}`, Number(maxRiskEntry[1]) > 0.5 ? "warn" : "ok")}
      ${decisionMetric(`${benchmark} 베타`, fmtDecimal(beta, 2), betaStatus)}
      ${decisionMetric("추적오차", fmtMetricRatio(trackingError), teStatus)}
      ${decisionMetric("정보비율", fmtDecimal(infoRatio, 2), Number.isFinite(infoRatio) && infoRatio > 0 ? "ok" : "warn")}
      ${decisionMetric("리밸런싱 초안", rebalanceText || "-", entries.length ? "ok" : "warn")}
    </div>
    <div class="decision-action-list">
      <div><strong>운용 체크</strong><span>${largestWeight > 0.5 ? "단일 종목 집중도가 높습니다. 최대 비중을 낮추거나 역변동성/리스크 패리티를 비교하세요." : "집중도는 제한 안에 있습니다. 위험 기여도와 상관관계가 같은 방향으로 몰리는지만 확인하세요."}</span></div>
      <div><strong>벤치마크 체크</strong><span>${Number.isFinite(beta) ? `${benchmark} 대비 베타 ${fmtDecimal(beta, 2)}, 추적오차 ${fmtMetricRatio(trackingError)}입니다. 목표가 절대수익이면 낮은 추적오차보다 MDD와 변동성을 우선 보세요.` : "벤치마크 대비 민감도를 계산할 수 없습니다. 벤치마크 가격 누락 여부를 확인하세요."}</span></div>
      <div><strong>실행 체크</strong><span>목표 비중은 주문 전 현재 보유 비중, 세금, 최소 주문 단위, 거래비용을 반영해 최종 주문량으로 변환해야 합니다.</span></div>
    </div>
  `;
}

function compactArtifactPath(path) {
  const raw = String(path || "");
  if (!raw) return "-";
  const parts = raw.replace(/\\/g, "/").split("/");
  return parts.slice(-4).join("/");
}

function renderQuantExportControls(runId) {
  if (!runId) return "";
  const safeRunId = escapeHtml(runId);
  return `
    <div class="decision-chip-row">
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-jsonl" aria-label="JSONL export ${safeRunId}" data-action="export-backtest" data-format="jsonl" data-run-id="${safeRunId}">export JSONL</button>
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-csv" aria-label="CSV export ${safeRunId}" data-action="export-backtest" data-format="csv" data-run-id="${safeRunId}">export CSV</button>
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-parquet" aria-label="Parquet export ${safeRunId}" title="Parquet 내보내기는 pandas와 pyarrow 또는 fastparquet가 설치된 경우에만 성공합니다." data-action="export-backtest" data-format="parquet" data-run-id="${safeRunId}">export Parquet</button>
      <label class="decision-inline-select">
        <span>retention</span>
        <select data-action="export-retention" aria-label="Quant export retention">
          <option value="0">No cleanup</option>
          <option value="3">Keep last 3</option>
          <option value="5">Keep last 5</option>
          <option value="10">Keep last 10</option>
        </select>
      </label>
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-history" aria-label="Export history ${safeRunId}" data-action="export-history" data-run-id="${safeRunId}">export history</button>
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-cleanup-preview" aria-label="Export cleanup preview ${safeRunId}" data-action="export-cleanup-preview" data-run-id="${safeRunId}">cleanup preview</button>
      <button type="button" class="linkish decision-inline-action" data-testid="quant-export-verify-latest" aria-label="Verify latest export ${safeRunId}" data-action="verify-export" data-run-id="${safeRunId}">verify latest export</button>
      <span title="Parquet optional dependency notice">Parquet은 optional dependency 필요</span>
    </div>
  `;
}

function renderDecisionLineChart(rows, key, label, status = "ok") {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => ({ date: row.date || "", value: Number(row[key] ?? row.value) }))
    .filter((row) => Number.isFinite(row.value));
  if (values.length < 2) return "";
  const width = 620;
  const height = 190;
  const padLeft = 64;
  const padRight = 18;
  const padTop = 18;
  const padBottom = 28;
  const nums = values.map((row) => row.value);
  const mode = key === "equity" ? "return" : ["drawdown", "return"].includes(key) ? "ratio" : "number";
  const base = key === "equity" ? (values[0]?.value || 1) : 1;
  const include = key === "equity" ? [base] : ["drawdown", "return"].includes(key) ? [0] : [];
  const { min, max } = paddedChartDomain(nums, include);
  const points = lineChartPoints(values, width, height, padLeft, padRight, padTop, padBottom, min, max);
  const polyline = svgPolylinePoints(points);
  const latest = values[values.length - 1];
  const latestValue = formatCurveAxisValue(latest.value, mode, base);
  return `
    <div class="decision-chart">
      <div class="decision-chart-head">
        <span>${escapeHtml(label)}</span>
        <strong class="${escapeHtml(decisionStatusClass(status))}">${escapeHtml(latestValue)}</strong>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)} curve">
        ${renderChartYAxis({
          width,
          height,
          padLeft,
          padRight,
          padTop,
          padBottom,
          min,
          max,
          formatter: (value) => formatCurveAxisValue(value, mode, base),
        })}
        <polyline points="${polyline}" fill="none" stroke="currentColor" stroke-width="2.4" vector-effect="non-scaling-stroke"></polyline>
        ${renderChartHoverTargets(points, (point) => {
          if (key === "equity") return `${point.date || "-"} · 수익률 ${formatCurveReturn(point.value, base)} · NAV ${fmtDecimal(point.value, 4)}`;
          if (key === "return") return `${point.date || "-"} · 누적 수익률 ${formatQuantValue(point.value)}`;
          if (key === "drawdown") return `${point.date || "-"} · MDD ${formatQuantValue(point.value)}`;
          return `${point.date || "-"} · ${label} ${fmtDecimal(point.value, 4)}`;
        })}
      </svg>
      <div class="decision-chart-foot">
        <span>${escapeHtml(values[0].date)}</span>
        <span>${escapeHtml(latest.date)}</span>
      </div>
    </div>
  `;
}

function normalizedCurve(rows, key = "equity") {
  const values = (Array.isArray(rows) ? rows : [])
    .map((row) => ({ date: row.date || "", value: Number(row[key]) }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  if (values.length < 2) return [];
  const base = values[0].value || 1;
  return values.map((row) => ({ date: row.date, value: row.value / base }));
}

function renderNormalizedComparisonChart({
  primary,
  benchmark,
  primaryLabel = "전략",
  benchmarkLabel = "SPY",
  title = "수익 곡선 비교",
  status = "ok",
} = {}) {
  const primaryRows = (Array.isArray(primary) ? primary : [])
    .map((row) => ({ date: row.date || "", value: Number(row.value) }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  const benchmarkRows = (Array.isArray(benchmark) ? benchmark : [])
    .map((row) => ({ date: row.date || "", value: Number(row.value) }))
    .filter((row) => row.date && Number.isFinite(row.value) && row.value > 0);
  if (primaryRows.length < 2 || benchmarkRows.length < 2) return "";
  const width = 760;
  const height = 230;
  const padLeft = 64;
  const padRight = 18;
  const padTop = 18;
  const padBottom = 30;
  const allValues = [...primaryRows, ...benchmarkRows].map((row) => row.value);
  const { min, max } = paddedChartDomain(allValues, [1]);
  const primaryPoints = lineChartPoints(primaryRows, width, height, padLeft, padRight, padTop, padBottom, min, max);
  const benchmarkPoints = lineChartPoints(benchmarkRows, width, height, padLeft, padRight, padTop, padBottom, min, max);
  const primaryLatest = primaryRows[primaryRows.length - 1]?.value ?? 1;
  const benchmarkLatest = benchmarkRows[benchmarkRows.length - 1]?.value ?? 1;
  return `
    <div class="decision-chart decision-chart-wide">
      <div class="decision-chart-head">
        <span>${escapeHtml(title)}</span>
        <strong class="${escapeHtml(decisionStatusClass(status))}">${escapeHtml(primaryLabel)} ${escapeHtml(fmtPct((primaryLatest - 1) * 100))} · ${escapeHtml(benchmarkLabel)} ${escapeHtml(fmtPct((benchmarkLatest - 1) * 100))}</strong>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
        ${renderChartYAxis({
          width,
          height,
          padLeft,
          padRight,
          padTop,
          padBottom,
          min,
          max,
          formatter: (value) => fmtPct((value - 1) * 100),
        })}
        <polyline points="${svgPolylinePoints(benchmarkPoints)}" fill="none" stroke="#60a5fa" stroke-width="2.2" vector-effect="non-scaling-stroke"></polyline>
        <polyline points="${svgPolylinePoints(primaryPoints)}" fill="none" stroke="#34d399" stroke-width="2.6" vector-effect="non-scaling-stroke"></polyline>
        ${renderChartHoverTargets(benchmarkPoints, (point) => `${point.date || "-"} · ${benchmarkLabel} 수익률 ${fmtPct((point.value - 1) * 100)} · NAV ${fmtDecimal(point.value, 4)}`)}
        ${renderChartHoverTargets(primaryPoints, (point) => `${point.date || "-"} · ${primaryLabel} 수익률 ${fmtPct((point.value - 1) * 100)} · NAV ${fmtDecimal(point.value, 4)}`)}
      </svg>
      <div class="decision-chart-foot">
        <span><i class="legend-line strategy"></i>${escapeHtml(primaryLabel)}</span>
        <span><i class="legend-line benchmark"></i>${escapeHtml(benchmarkLabel)}</span>
      </div>
    </div>
  `;
}

function renderBenchmarkComparisonChart(data, status = "ok") {
  const strategy = normalizedCurve(data.equity_curve, "equity");
  const benchmark = normalizedCurve(data.benchmark_curve, "equity");
  if (strategy.length < 2 || benchmark.length < 2) return "";
  const benchmarkTicker = data.benchmark_ticker || data.benchmark || "SPY";
  return renderNormalizedComparisonChart({
    primary: strategy,
    benchmark,
    primaryLabel: "전략",
    benchmarkLabel: benchmarkTicker,
    title: "수익 곡선 비교",
    status,
  });
}

async function attachBenchmarkComparison(data, request = {}) {
  if (!data || !request?.compare_benchmark) return data;
  const benchmarkTicker = normalizeTickerToken(request.benchmark || data.benchmark || "SPY") || "SPY";
  try {
    const res = await fetch(API.dataPrices(benchmarkTicker, 5000));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    const rows = Array.isArray(payload.items) ? payload.items : [];
    const start = data.date_range?.start || request.start_date || "";
    const end = data.date_range?.end || request.end_date || "";
    const filtered = rows.filter((row) => {
      const date = row.date || "";
      if (start && date < start) return false;
      if (end && date > end) return false;
      return priceValue(row) !== null;
    });
    const base = priceValue(filtered[0]);
    if (!base) throw new Error(`${benchmarkTicker} price history is unavailable`);
    return {
      ...data,
      benchmark_ticker: benchmarkTicker,
      benchmark_curve: filtered.map((row) => ({
        date: row.date || "",
        equity: Number((priceValue(row) / base).toFixed(8)),
      })),
    };
  } catch (err) {
    return {
      ...data,
      benchmark_ticker: benchmarkTicker,
      benchmark_warning: `벤치마크 비교 불가: ${err.message || err}`,
    };
  }
}

function renderQuantDiagnosticsPanel(data) {
  const diagnostics = data.diagnostics || {};
  const artifacts = data.artifacts || {};
  const priceCounts = diagnostics.price_counts || {};
  const chips = [
    `룩어헤드 ${diagnostics.lookahead_safe ? "안전" : "점검 필요"}`,
    `시그널 지연 ${diagnostics.signal_shift_bars ?? 1}봉`,
    diagnostics.execution_assumption || "next_bar_close",
    diagnostics.data_source || "data_mart",
    ...Object.entries(priceCounts).map(([ticker, count]) => `${ticker} ${_fmtNumber(count)}행`),
  ];
  return `
    <div class="decision-section-title">진단</div>
    <div class="decision-chip-row">${chips.map((chip) => `<span>${escapeHtml(chip)}</span>`).join("")}</div>
    ${(diagnostics.excluded_assets || []).length ? `<div class="decision-warning">데이터 없는 종목 자동 제외: ${escapeHtml(diagnostics.excluded_assets.join(", "))}</div>` : ""}
    ${(diagnostics.missing_assets || []).length ? `<div class="decision-warning">데이터 없는 종목: ${escapeHtml(diagnostics.missing_assets.join(", "))}</div>` : ""}
    ${(diagnostics.stale_assets || []).length ? `<div class="decision-warning">오래된 가격: ${escapeHtml(diagnostics.stale_assets.join(", "))}</div>` : ""}
    ${(diagnostics.warnings || []).length ? `<div class="decision-warning">${escapeHtml(formatQuantWarnings(diagnostics.warnings))}</div>` : ""}
    ${renderFreshnessAuditPanel(diagnostics)}
    <div class="decision-section-title">산출물</div>
    <div class="decision-list compact">
      ${["manifest", "config", "metrics", "diagnostics", "equity_curve", "drawdown_curve", "trades", "signals", "weights", "replay_report"].map((name) => `
        <div class="decision-list-row">
          <span>${escapeHtml(name)}</span>
          <strong>${escapeHtml(compactArtifactPath(artifacts[name]))}</strong>
        </div>
      `).join("")}
    </div>
    ${renderQuantExportControls(data.run_id)}
  `;
}

function renderQuantBacktestTables(data) {
  const trades = Array.isArray(data.trades) ? data.trades.slice(-8) : [];
  const signals = Array.isArray(data.signals) ? data.signals.slice(0, 8) : [];
  const weights = Array.isArray(data.weights) ? data.weights : [];
  return `
    ${signals.length ? `
      <div class="decision-section-title">최근 시그널</div>
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>종목</th><th>일자</th><th>점수</th><th>신호</th><th>체결일</th></tr></thead>
          <tbody>
            ${signals.map((row) => `
              <tr>
                <td>${escapeHtml(row.ticker || "")}</td>
                <td>${escapeHtml(row.date || "")}</td>
                <td>${escapeHtml(fmtDecimal(row.final_score, 3))}</td>
                <td><span class="table-status ${Number(row.signal || 0) > 0 ? "ok" : "warn"}">${escapeHtml(fmtDecimal(row.signal, 2))}</span></td>
                <td>${escapeHtml(row.execution_date || "")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : ""}
    ${trades.length ? `
      <div class="decision-section-title">최근 거래</div>
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>일자</th><th>종목</th><th>액션</th><th>비중</th><th>비용</th></tr></thead>
          <tbody>
            ${trades.map((row) => {
              const assetText = row.ticker || row.asset || (Array.isArray(row.selected) ? row.selected.join(",") : "") || "portfolio";
              const actionText = row.action || row.side || row.type || (row.turnover !== undefined ? "rebalance" : "");
              const weightValue = row.weight ?? row.target_weight ?? row.quantity ?? row.turnover;
              return `
                <tr>
                  <td>${escapeHtml(row.date || row.execution_date || "")}</td>
                  <td>${escapeHtml(assetText)}</td>
                  <td>${escapeHtml(actionText)}</td>
                  <td>${escapeHtml(formatQuantValue(weightValue))}</td>
                  <td>${escapeHtml(formatQuantValue(row.cost ?? row.transaction_cost ?? ""))}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    ` : ""}
    ${renderRebalanceSnapshots(weights)}
  `;
}

function renderQuantRunContext(data, request = {}) {
  const manifest = data.manifest || {};
  const config = data.config || request || {};
  const diagnostics = data.diagnostics || {};
  const snapshot = manifest.data_snapshot || data.data_snapshot || {};
  const policy = diagnostics.freshness_policy || snapshot.freshness_policy || {};
  const tickers = data.tickers || config.tickers || request.tickers || [];
  const priceCounts = snapshot.price_counts || diagnostics.price_counts || {};
  const latestDates = snapshot.latest_price_dates || diagnostics.latest_price_dates || {};
  const codeVersion = manifest.code_version || data.code_version || {};
  const configHash = manifest.config_hash || data.config_hash || "";
  const commit = codeVersion.git_commit || "";
  const priceRows = Object.entries(priceCounts).slice(0, 5).map(([ticker, count]) => {
    const latest = latestDates[ticker] ? ` · ${latestDates[ticker]}` : "";
    return `${ticker}:${_fmtNumber(count)}${latest}`;
  });
  return `
    <div class="decision-section-title">Run Context</div>
    <div class="decision-chip-row" data-testid="quant-run-context">
      <span>strategy ${escapeHtml(config.strategy_id || request.strategy_id || state.activeStrategyId || "adhoc")}</span>
      <span>template ${escapeHtml(quantTemplateLabel(data.template || config.template || request.template || "unknown"))}</span>
      <span>universe ${escapeHtml((tickers || []).join(",") || "-")}</span>
      <span>freshness ${escapeHtml(policy.profile || config.freshness_profile || request.freshness_profile || "research_default")}</span>
      <span>cost ${escapeHtml(String(config.transaction_cost_bps ?? request.transaction_cost_bps ?? "-"))}/${escapeHtml(String(config.slippage_bps ?? request.slippage_bps ?? "-"))} bps</span>
      ${configHash ? `<span>config ${escapeHtml(String(configHash).slice(0, 10))}</span>` : ""}
      ${commit ? `<span>commit ${escapeHtml(String(commit).slice(0, 12))}${codeVersion.git_dirty ? " dirty" : ""}</span>` : ""}
    </div>
    ${priceRows.length ? `
      <div class="decision-list compact">
        <div class="decision-list-row"><span>Price snapshot</span><strong>${escapeHtml(priceRows.join(" · "))}</strong></div>
        <div class="decision-list-row"><span>Expected latest</span><strong>${escapeHtml(diagnostics.expected_latest_date || "-")}</strong></div>
      </div>
    ` : ""}
  `;
}

function renderQuantBacktestResult(data, request = {}) {
  if (!els.backtestSurface) return;
  const metrics = backtestMetricsWithDerivedTotals(data.metrics || {}, data.equity_curve);
  const status = data.status || "unknown";
  const benchmarkWarning = data.benchmark_warning
    ? `<div class="decision-warning">${escapeHtml(data.benchmark_warning)}</div>`
    : "";
  els.backtestSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
      <span>${escapeHtml(data.run_id || "run pending")} · ${escapeHtml(data.date_range?.start || request.start_date || "-")} -> ${escapeHtml(data.date_range?.end || request.end_date || "-")}</span>
    </div>
    ${renderQuantRunContext(data, request)}
    ${renderMetricGrid(metrics, status)}
    <div class="decision-chart-grid">
      ${renderDecisionLineChart(data.equity_curve, "equity", "수익 곡선", status)}
      ${renderDecisionLineChart(data.drawdown_curve, "drawdown", "MDD", Number(metrics.max_drawdown || 0) < -0.2 ? "warn" : status)}
      ${renderBenchmarkComparisonChart(data, status)}
    </div>
    ${benchmarkWarning}
    <div class="decision-assumption">
      전략 ${escapeHtml(request.strategy_id || data.config?.strategy_id || state.activeStrategyId || "임시")} · 템플릿 ${escapeHtml(quantTemplateLabel(data.template || request.template || "unknown"))} · 벤치마크 ${escapeHtml(data.benchmark_ticker || data.benchmark || request.benchmark || "-")} · 비용 ${escapeHtml(String(request.transaction_cost_bps ?? data.config?.transaction_cost_bps ?? "-"))}bps · 슬리피지 ${escapeHtml(String(request.slippage_bps ?? data.config?.slippage_bps ?? "-"))}bps
    </div>
    ${renderQuantBacktestTables(data)}
    ${renderQuantDiagnosticsPanel(data)}
    <button type="button" class="linkish decision-inline-action" data-action="sync-backtest-portfolio">이 조건을 포트폴리오에 적용</button>
    ${data.run_id ? `<button type="button" class="linkish decision-inline-action" data-action="replay-backtest" data-run-id="${escapeHtml(data.run_id)}">재현 비교</button>` : ""}
    ${data.run_id ? `<button type="button" class="linkish decision-inline-action" data-action="replay-reports" data-run-id="${escapeHtml(data.run_id)}">재현 이력</button>` : ""}
    ${status === "success" ? "" : decisionEmpty(data.reason || "저장 가격이 부족해 일부 결과만 표시됩니다.")}
  `;
}

function renderReplayReportHistoryTable(history) {
  const items = Array.isArray(history?.items) ? history.items : [];
  if (!items.length) return '<div class="decision-empty">No persisted replay reports yet.</div>';
  const metricKeys = ["total_return", "sharpe", "max_drawdown"].filter((key) =>
    items.some((item) => item.metric_deltas && item.metric_deltas[key] !== undefined)
  );
  return `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead>
          <tr><th>Generated</th><th>Status</th><th>Config</th><th>Tolerance</th>${metricKeys.map((key) => `<th>${escapeHtml(key)}</th>`).join("")}<th>Report</th></tr>
        </thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td>${escapeHtml(fmtDate(item.generated_at) || "-")}</td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(item.status))}">${escapeHtml(item.status || "unknown")}</span></td>
              <td>${item.config_hash_match ? "match" : "changed"}</td>
              <td><span class="table-status ${item.tolerance_passed ? "ok" : "warn"}">${item.tolerance_passed ? "passed" : `fail ${escapeHtml(String(item.tolerance_failure_count || 0))}`}</span></td>
              ${metricKeys.map((key) => `<td>${escapeHtml(formatQuantValue(item.metric_deltas?.[key] ?? 0))}</td>`).join("")}
              <td>${escapeHtml(compactArtifactPath(item.report_path))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderArtifactExportSummary(data) {
  const files = data.files || {};
  const counts = data.row_counts || {};
  const dependency = data.dependency || {};
  const integrityFiles = data.integrity?.files || {};
  const retention = data.retention || {};
  const dependencyMessage = data.status === "dependency_missing"
    ? `<div class="decision-warning">${escapeHtml(dependency.message || "Optional export dependency is missing.")}</div>`
    : "";
  const retentionMessage = retention.retention_applied
    ? `<div class="decision-warning">Retention kept last ${escapeHtml(String(retention.keep_last_exports || 0))} export set(s); pruned ${escapeHtml(String(retention.pruned_export_count || 0))} older set(s).</div>`
    : "";
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.status || "success"))}">${escapeHtml(data.status || "success")}</span>
      <span>${escapeHtml(data.run_id || "")} ${escapeHtml(String(data.format || "").toUpperCase())} export</span>
    </div>
    <div class="decision-chip-row">
      <span>rows ${escapeHtml(_fmtNumber(counts.total || 0))}</span>
      <span>root ${escapeHtml(compactArtifactPath(data.export_root))}</span>
      <span>manifest ${escapeHtml(compactArtifactPath(files.manifest))}</span>
      ${dependency.engine ? `<span>engine ${escapeHtml(dependency.engine)}</span>` : ""}
    </div>
    ${dependencyMessage}
    ${retentionMessage}
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>Section</th><th>Rows</th><th>File</th><th>SHA-256</th><th>Bytes</th></tr></thead>
        <tbody>
          ${Object.keys(counts).filter((name) => name !== "total").map((name) => {
            const filePath = files[name] || files.jsonl || "";
            const integrity = integrityFiles[name] || (files[name] ? {} : integrityFiles.jsonl) || {};
            return `
              <tr>
                <td>${escapeHtml(name)}</td>
                <td>${escapeHtml(_fmtNumber(counts[name]))}</td>
                <td>${escapeHtml(compactArtifactPath(filePath))}</td>
                <td>${escapeHtml(String(integrity.sha256 || "").slice(0, 16) || "-")}</td>
                <td>${escapeHtml(_fmtNumber(integrity.size_bytes || 0))}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
    ${renderQuantExportControls(data.run_id)}
  `;
}

function renderArtifactExportHistory(data) {
  const items = Array.isArray(data.items) ? data.items : [];
  return `
    <div class="decision-status-row">
      <span class="decision-badge ok">${escapeHtml(data.status || "success")}</span>
      <span>${escapeHtml(data.run_id || "")} · ${escapeHtml(_fmtNumber(data.count || 0))} export manifest(s)</span>
    </div>
    ${renderQuantExportControls(data.run_id || "")}
    ${items.length ? `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>Generated</th><th>Format</th><th>Status</th><th>Rows</th><th>Bytes</th><th>Integrity</th><th>Manifest</th><th>Verify</th></tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${escapeHtml(fmtDate(item.generated_at) || "-")}</td>
                <td>${escapeHtml(String(item.format || "unknown").toUpperCase())}</td>
                <td><span class="table-status ${escapeHtml(decisionStatusClass(item.status || "unknown"))}">${escapeHtml(item.status || "unknown")}</span></td>
                <td>${escapeHtml(_fmtNumber(item.total_rows || 0))}</td>
                <td>${escapeHtml(_fmtNumber(item.total_bytes || 0))}</td>
                <td>${item.integrity_available ? "sha256" : "missing"}</td>
                <td>${escapeHtml(compactArtifactPath(item.manifest_path))}</td>
                <td><button type="button" class="linkish" data-testid="quant-export-verify-row" aria-label="Verify ${escapeHtml(String(item.format || "unknown").toUpperCase())} export ${escapeHtml(compactArtifactPath(item.manifest_path || ""))}" data-action="verify-export" data-run-id="${escapeHtml(data.run_id || "")}" data-manifest-path="${escapeHtml(item.manifest_path || "")}">verify</button></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : decisionEmpty("No generated artifact exports have been saved for this run yet.")}
  `;
}

function renderArtifactExportCleanupPlan(data) {
  const kept = Array.isArray(data.kept_exports) ? data.kept_exports : [];
  const prune = Array.isArray(data.prune_exports) ? data.prune_exports : [];
  const applied = !!data.cleanup_applied;
  const statusText = applied ? "export cleanup applied" : "export cleanup preview";
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.status || "success"))}">${escapeHtml(data.status || "success")}</span>
      <span>${escapeHtml(data.run_id || "")} ${statusText}</span>
    </div>
    <div class="decision-chip-row">
      <span>policy ${escapeHtml(data.policy || "keep_last_exports")}</span>
      <span>keep last ${escapeHtml(_fmtNumber(data.keep_last_exports || 0))}</span>
      <span>exports ${escapeHtml(_fmtNumber(data.export_count || 0))}</span>
      <span>prune ${escapeHtml(_fmtNumber(data.prune_export_count || 0))}</span>
      <span>bytes ${escapeHtml(_fmtNumber(applied ? data.total_bytes_pruned || 0 : data.total_bytes_to_prune || 0))}</span>
    </div>
    ${renderQuantExportControls(data.run_id || "")}
    ${!applied && prune.length ? `
      <div class="decision-chip-row">
        <button type="button" class="linkish decision-inline-action" data-action="export-cleanup-apply" data-run-id="${escapeHtml(data.run_id || "")}" data-keep-last="${escapeHtml(String(data.keep_last_exports || 0))}">apply cleanup</button>
      </div>
    ` : ""}
    ${prune.length ? `
      <div class="decision-section-title">${applied ? "Pruned exports" : "Exports that would be pruned"}</div>
      ${renderArtifactExportCleanupTable(prune)}
    ` : decisionEmpty("No generated export directories are eligible for cleanup with this policy.")}
    ${kept.length ? `
      <div class="decision-section-title">Exports kept</div>
      ${renderArtifactExportCleanupTable(kept)}
    ` : ""}
  `;
}

function renderArtifactExportCleanupTable(items) {
  return `
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>Generated</th><th>Format</th><th>Status</th><th>Rows</th><th>Bytes</th><th>Directory</th></tr></thead>
        <tbody>
          ${items.map((item) => `
            <tr>
              <td>${escapeHtml(fmtDate(item.generated_at) || "-")}</td>
              <td>${escapeHtml(String(item.format || "unknown").toUpperCase())}</td>
              <td><span class="table-status ${escapeHtml(decisionStatusClass(item.status || "unknown"))}">${escapeHtml(item.status || "unknown")}</span></td>
              <td>${escapeHtml(_fmtNumber(item.total_rows || 0))}</td>
              <td>${escapeHtml(_fmtNumber(item.total_bytes || item.directory_size_bytes || 0))}</td>
              <td>${escapeHtml(compactArtifactPath(item.directory || item.export_root || ""))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderArtifactExportVerification(data) {
  const files = data.files || {};
  const failures = Array.isArray(data.failures) ? data.failures : [];
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.status || "unknown"))}">${escapeHtml(data.status || "unknown")}</span>
      <span>${escapeHtml(data.run_id || "")} export integrity verification</span>
    </div>
    <div class="decision-chip-row">
      <span>checked ${escapeHtml(_fmtNumber(data.files_checked || 0))}</span>
      <span>passed ${escapeHtml(_fmtNumber(data.files_passed || 0))}</span>
      <span>failed ${escapeHtml(_fmtNumber(data.files_failed || 0))}</span>
      <span>format ${escapeHtml(String(data.format || "unknown").toUpperCase())}</span>
      <span>manifest ${escapeHtml(compactArtifactPath(data.manifest_path))}</span>
    </div>
    ${failures.length ? `<div class="decision-warning">${escapeHtml(failures.map((item) => `${item.file}:${item.reason}`).join(", "))}</div>` : ""}
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>File</th><th>Status</th><th>Expected SHA</th><th>Actual SHA</th><th>Expected bytes</th><th>Actual bytes</th></tr></thead>
        <tbody>
          ${Object.entries(files).map(([name, item]) => `
            <tr>
              <td>${escapeHtml(name)}</td>
              <td><span class="table-status ${item.status === "passed" ? "ok" : "fail"}">${escapeHtml(item.status || "unknown")}</span></td>
              <td>${escapeHtml(String(item.expected_sha256 || "").slice(0, 16) || "-")}</td>
              <td>${escapeHtml(String(item.actual_sha256 || "").slice(0, 16) || "-")}</td>
              <td>${escapeHtml(_fmtNumber(item.expected_size_bytes || 0))}</td>
              <td>${escapeHtml(_fmtNumber(item.actual_size_bytes || 0))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    ${renderQuantExportControls(data.run_id || "")}
  `;
}

function renderQuantReplayComparison(data) {
  if (!els.backtestSurface) return;
  const deltas = data.metric_deltas || {};
  const original = data.original_metrics || {};
  const replay = data.replay_metrics || {};
  const tolerancePolicy = data.tolerance_policy || {};
  const metricTolerances = tolerancePolicy.metrics || {};
  const toleranceFailures = Array.isArray(data.tolerance_failures) ? data.tolerance_failures : [];
  const keys = ["total_return", "cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "turnover", "exposure"]
    .filter((key) => original[key] !== undefined || replay[key] !== undefined || deltas[key] !== undefined);
  const status = data.status || "unknown";
  els.backtestSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
      <span>${escapeHtml(data.run_id || "")} replayed as ${escapeHtml(data.replay_run_id || "")}</span>
    </div>
    <div class="decision-chip-row">
      <span>config hash ${data.config_hash_match ? "matched" : "changed"}</span>
      <span>original ${escapeHtml(String(data.original_config_hash || "-")).slice(0, 10)}</span>
      <span>replay ${escapeHtml(String(data.replay_config_hash || "-")).slice(0, 10)}</span>
      <span>lookahead ${data.diagnostics?.lookahead_safe ? "safe" : "check"}</span>
      <span>tolerance ${data.tolerance_passed ? "passed" : "check"}</span>
    </div>
    <div class="decision-chip-row">
      <button type="button" class="linkish decision-inline-action" data-action="replay-reports" data-run-id="${escapeHtml(data.run_id || "")}">replay report history</button>
    </div>
    ${renderQuantExportControls(data.run_id)}
    <div class="decision-section-title">Replay metric comparison</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>Metric</th><th>Original</th><th>Replay</th><th>Delta</th><th>Tolerance</th></tr></thead>
        <tbody>
          ${keys.map((key) => `
            <tr>
              <td>${escapeHtml(key)}</td>
              <td>${escapeHtml(formatQuantValue(original[key]))}</td>
              <td>${escapeHtml(formatQuantValue(replay[key]))}</td>
              <td><span class="table-status ${Math.abs(Number(deltas[key] || 0)) <= Number(metricTolerances[key] ?? tolerancePolicy.default_abs ?? 0) ? "ok" : "warn"}">${escapeHtml(formatQuantValue(deltas[key] ?? 0))}</span></td>
              <td>${escapeHtml(formatQuantValue(metricTolerances[key] ?? tolerancePolicy.default_abs ?? 0))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    ${toleranceFailures.length ? `<div class="decision-warning">Replay tolerance failures: ${escapeHtml(toleranceFailures.map((item) => `${item.metric}=${item.abs_delta}`).join(", "))}</div>` : ""}
    <div class="decision-section-title">Lineage</div>
    <div class="decision-list compact">
      <div class="decision-list-row"><span>Original generated</span><strong>${escapeHtml(data.original_generated_at || "-")}</strong></div>
      <div class="decision-list-row"><span>Replay generated</span><strong>${escapeHtml(data.replay_generated_at || "-")}</strong></div>
      <div class="decision-list-row"><span>Original commit</span><strong>${escapeHtml(String(data.original_code_version?.git_commit || "-")).slice(0, 12)}</strong></div>
      <div class="decision-list-row"><span>Current commit</span><strong>${escapeHtml(String(data.current_code_version?.git_commit || "-")).slice(0, 12)}</strong></div>
      <div class="decision-list-row"><span>Replay report</span><strong>${escapeHtml(data.report_path || "-")}</strong></div>
    </div>
    <div class="decision-section-title">Replay report history</div>
    ${renderReplayReportHistoryTable(data.report_history || {})}
    ${(data.diagnostics?.warnings || []).length ? `<div class="decision-warning">${escapeHtml(formatQuantWarnings(data.diagnostics.warnings))}</div>` : ""}
  `;
}

async function runQuantBacktestReplay(runId) {
  if (!runId || !els.backtestSurface) return;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} replay comparison is running.`);
  try {
    const res = await fetch(API.quantBacktestReplay(runId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persist_report: true }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderQuantReplayComparison(data);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`리플레이 비교 실패: ${err.message || err}`);
  }
}

async function loadQuantReplayReports(runId) {
  if (!runId || !els.backtestSurface) return;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} replay report history is loading.`);
  try {
    const res = await fetch(`${API.quantBacktestReplayReports(runId)}?limit=20`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ok">${escapeHtml(data.status || "success")}</span>
        <span>${escapeHtml(data.run_id || runId)} · ${escapeHtml(_fmtNumber(data.count || 0))} replay reports</span>
      </div>
      <div class="decision-chip-row">
        <button type="button" class="linkish decision-inline-action" data-action="replay-backtest" data-run-id="${escapeHtml(runId)}">run new replay</button>
      </div>
      ${renderQuantExportControls(runId)}
      ${renderReplayReportHistoryTable(data)}
    `;
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`리플레이 리포트 이력 조회 실패: ${err.message || err}`);
  }
}

async function exportQuantBacktestArtifact(runId, format = "jsonl") {
  if (!runId || !els.backtestSurface) return;
  const cleanFormat = String(format || "jsonl").toLowerCase();
  const keepLast = selectedQuantExportRetention();
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} ${cleanFormat.toUpperCase()} export is being prepared.`);
  try {
    const payload = { format: cleanFormat };
    if (keepLast > 0) payload.keep_last_exports = keepLast;
    const res = await fetch(API.quantBacktestExport(runId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = renderArtifactExportSummary(data);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`백테스트 산출물 내보내기 실패: ${err.message || err}`);
  }
}

function selectedQuantExportRetention() {
  const field = els.backtestSurface?.querySelector?.('[data-action="export-retention"]');
  const value = Number(field?.value || 0);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

async function loadQuantExportHistory(runId) {
  if (!runId || !els.backtestSurface) return;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} export history is loading.`);
  try {
    const res = await fetch(`${API.quantBacktestExports(runId)}?limit=20`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = renderArtifactExportHistory(data);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`내보내기 이력 조회 실패: ${err.message || err}`);
  }
}

async function previewQuantExportCleanup(runId) {
  if (!runId || !els.backtestSurface) return;
  const keepLast = selectedQuantExportRetention() || 5;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} export cleanup preview is loading.`);
  try {
    const qs = new URLSearchParams({ keep_last_exports: String(keepLast) });
    const res = await fetch(`${API.quantBacktestExportCleanupPreview(runId)}?${qs.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = renderArtifactExportCleanupPlan(data);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`내보내기 정리 미리보기 실패: ${err.message || err}`);
  }
}

async function applyQuantExportCleanup(runId, keepLast = 5) {
  if (!runId || !els.backtestSurface) return;
  const resolvedKeepLast = Number(keepLast || selectedQuantExportRetention() || 5);
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} export cleanup is applying.`);
  try {
    const res = await fetch(API.quantBacktestExportCleanup(runId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keep_last_exports: resolvedKeepLast }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = renderArtifactExportCleanupPlan(data);
    loadQuantRunHistory(true);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`내보내기 정리 실행 실패: ${err.message || err}`);
  }
}

async function verifyQuantExport(runId, manifestPath = "") {
  if (!runId || !els.backtestSurface) return;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} export integrity is being verified.`);
  try {
    const payload = manifestPath ? { export_manifest_path: manifestPath } : {};
    const res = await fetch(API.quantBacktestExportVerify(runId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.backtestSurface.innerHTML = renderArtifactExportVerification(data);
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`내보내기 무결성 검증 실패: ${err.message || err}`);
  }
}

async function runQuantFeaturePreview() {
  if (!els.quantFeatureSurface) return;
  const startedAt = Date.now();
  setButtonBusy(els.quantFeatureRun, true, "계산 중");
  const resolution = await resolveBacktestUniverseAvailability(els.quantFeatureSurface);
  if (!resolution.ok) {
    setButtonBusy(els.quantFeatureRun, false);
    return;
  }
  const request = quantFeatureRequestFromControls();
  if (!request.tickers.length) {
    els.quantFeatureSurface.innerHTML = decisionEmpty("퀀트 랩 유니버스에 종목을 하나 이상 입력하세요.");
    setButtonBusy(els.quantFeatureRun, false);
    return;
  }
  els.quantFeatureSurface.innerHTML = decisionEmpty(`${request.tickers.join(", ")} 팩터를 계산하는 중입니다.`);
  try {
    const res = await fetch(API.quantFeatures, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.lastFeatureResult = data;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const diagnostics = data.diagnostics || {};
    const status = data.status || "unknown";
    els.quantFeatureSurface.innerHTML = `
      ${renderActionCompletion("팩터 미리보기 완료", startedAt, `${_fmtNumber(rows.length)}개 종목`)}
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
        <span>${escapeHtml(data.as_of || "알 수 없음")} · ${escapeHtml(request.benchmark)} 벤치마크 · 데이터 마트</span>
      </div>
      ${(resolution.data?.unavailable || []).length ? renderUniverseResolutionNotice(resolution.data) : ""}
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>종목</th><th>기준일</th><th>신선도</th><th>모멘텀</th><th>위험조정</th><th>변동성</th><th>낙폭</th><th>추세</th><th>상대강도</th></tr></thead>
          <tbody>
            ${rows.map((row) => {
              const features = row.features || {};
              return `
                <tr>
                  <td>${escapeHtml(row.ticker || "")}</td>
                  <td>${escapeHtml(row.as_of || "알 수 없음")}</td>
                  <td><span class="table-status ${escapeHtml(decisionStatusClass(row.freshness_status))}">${escapeHtml(row.freshness_status || "알 수 없음")}</span></td>
                  <td>${escapeHtml(formatQuantValue(features.momentum_63d))}</td>
                  <td>${escapeHtml(formatQuantValue(features.risk_adjusted_momentum_63d))}</td>
                  <td>${escapeHtml(formatQuantValue(features.realized_vol_21d))}</td>
                  <td>${escapeHtml(formatQuantValue(features.drawdown_current))}</td>
                  <td>${escapeHtml(formatQuantValue(features.ma_ratio_20_50))}</td>
                  <td>${escapeHtml(formatQuantValue(features.relative_strength_spy_63d))}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
      <div class="decision-chip-row">
        ${Object.entries(diagnostics.price_counts || {}).map(([ticker, count]) => `<span>${escapeHtml(ticker)} ${escapeHtml(_fmtNumber(count))}행</span>`).join("")}
      </div>
      ${renderFreshnessAuditPanel(diagnostics)}
      ${(diagnostics.excluded_assets || []).length ? `<div class="decision-warning">데이터 없는 종목 자동 제외: ${escapeHtml(diagnostics.excluded_assets.join(", "))}</div>` : ""}
      ${(diagnostics.missing_assets || []).length ? `<div class="decision-warning">데이터 없는 종목: ${escapeHtml(diagnostics.missing_assets.join(", "))}</div>` : ""}
      ${(diagnostics.stale_assets || []).length ? `<div class="decision-warning">오래된 가격: ${escapeHtml(diagnostics.stale_assets.join(", "))}</div>` : ""}
    `;
  } catch (err) {
    els.quantFeatureSurface.innerHTML = decisionEmpty(`팩터 미리보기 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.quantFeatureRun, false);
  }
}

function renderSignalDecisionBrief(rows, diagnostics, template) {
  const signals = rows.map((row) => Number(row.signal || 0));
  const active = signals.filter((value) => value > 0).length;
  const neutral = signals.filter((value) => value === 0).length;
  const negative = Math.max(0, rows.length - active - neutral);
  const scoreValues = rows.map((row) => Number(row.final_score)).filter(Number.isFinite);
  const avgScore = scoreValues.length
    ? scoreValues.reduce((sum, value) => sum + value, 0) / scoreValues.length
    : null;
  const execution = diagnostics.execution_assumption || "next_bar_close";
  const shift = diagnostics.signal_shift_bars ?? 1;
  const selected = rows
    .filter((row) => Number(row.signal || 0) > 0)
    .map((row) => row.ticker)
    .filter(Boolean)
    .join(", ");
  const decisionTone = active ? "ok" : "warn";
  return `
    <div class="decision-practical-grid signal-practical-grid">
      ${decisionMetric("전략 템플릿", quantTemplateLabel(template), "ok")}
      ${decisionMetric("매수 신호", `${active}/${rows.length}`, decisionTone)}
      ${decisionMetric("중립/제외", `${neutral + negative}`, neutral + negative ? "warn" : "ok")}
      ${decisionMetric("평균 점수", fmtDecimal(avgScore, 3), avgScore === null ? "warn" : "ok")}
      ${decisionMetric("체결 가정", execution === "next_bar_close" ? "다음 봉 종가" : execution, "ok")}
      ${decisionMetric("시그널 지연", `${shift}봉`, Number(shift) >= 1 ? "ok" : "fail")}
    </div>
    <div class="decision-summary ${decisionTone}">
      ${active
        ? `현재 조건에서는 ${escapeHtml(selected || "선정 종목")}에만 포지션을 부여합니다. 신호일과 체결일을 분리해 look-ahead를 피하고, 다음 백테스트/포트폴리오 입력으로 바로 검증하세요.`
        : "현재 조건에서는 매수 후보가 없습니다. 모멘텀 기간, Top N, 리서치 점수 사용 여부, 데이터 신선도 조건을 완화해 재검토하세요."}
    </div>
  `;
}

async function runQuantSignalPreview() {
  if (!els.quantSignalSurface) return;
  const startedAt = Date.now();
  setButtonBusy(els.quantSignalRun, true, "생성 중");
  const resolution = await resolveBacktestUniverseAvailability(els.quantSignalSurface);
  if (!resolution.ok) {
    setButtonBusy(els.quantSignalRun, false);
    return;
  }
  const base = quantFeatureRequestFromControls();
  const template = quantSignalTemplateFromStrategy(els.backtestStrategy?.value);
  if (!base.tickers.length) {
    els.quantSignalSurface.innerHTML = decisionEmpty("퀀트 랩 유니버스에 종목을 하나 이상 입력하세요.");
    setButtonBusy(els.quantSignalRun, false);
    return;
  }
  els.quantSignalSurface.innerHTML = decisionEmpty(`${base.tickers.join(", ")} 시그널을 생성하는 중입니다.`);
  try {
    const res = await fetch(API.quantSignals, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...base, template, use_research_score: !!els.backtestUseResearchScore?.checked }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.lastSignalResult = data;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const diagnostics = data.diagnostics || {};
    const status = data.status || "unknown";
    els.quantSignalSurface.innerHTML = `
      ${renderActionCompletion("시그널 생성 완료", startedAt, `${_fmtNumber(rows.length)}개 종목`)}
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
        <span>${escapeHtml(quantTemplateLabel(template))} · ${escapeHtml(diagnostics.execution_assumption || "next_bar_close")} · ${escapeHtml(String(diagnostics.signal_shift_bars || 1))}봉 지연</span>
      </div>
      ${(resolution.data?.unavailable || []).length ? renderUniverseResolutionNotice(resolution.data) : ""}
      ${renderSignalDecisionBrief(rows, diagnostics, template)}
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>종목</th><th>신호일</th><th>점수</th><th>신호</th><th>체결일</th><th>진단</th></tr></thead>
          <tbody>
            ${rows.map((row) => `
              <tr>
                <td>${escapeHtml(row.ticker || "")}</td>
                <td>${escapeHtml(row.date || "알 수 없음")}</td>
                <td>${escapeHtml(fmtDecimal(row.final_score, 3))}</td>
                <td><span class="table-status ${Number(row.signal || 0) > 0 ? "ok" : "warn"}">${escapeHtml(fmtDecimal(row.signal, 2))}</span></td>
                <td>${escapeHtml(row.execution_date || "다음 가용 봉")}</td>
                <td><div class="decision-chip-row compact">${renderDiagnosticsChips(row.diagnostics)}</div></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      ${renderResearchProvenancePanel(diagnostics.research_score_provenance)}
      ${renderFreshnessAuditPanel(diagnostics)}
      ${(data.warnings || []).length ? `<div class="decision-warning">${escapeHtml(formatQuantWarnings(data.warnings))}</div>` : ""}
    `;
  } catch (err) {
    els.quantSignalSurface.innerHTML = decisionEmpty(`시그널 생성 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.quantSignalRun, false);
  }
}

function quantStrategyDraftFromControls() {
  const request = quantBacktestRequestFromControls();
  return {
    strategy_id: "custom_momentum_review_v1",
    name: "Custom Momentum Review",
    frequency: "daily",
    features: {
      momentum_63d: { id: "momentum_63d", lookback: 63 },
      ...(request.template === "risk_adjusted_momentum" ? { risk_adjusted_momentum_63d: { id: "risk_adjusted_momentum_63d", lookback: 63 } } : {}),
      realized_vol_21d: { id: "realized_vol_21d", lookback: 21 },
      ...(request.use_research_score ? { research_score: { id: "research_score", max_age_days: 7 } } : {}),
    },
    signal: { type: "rank_top_n", top_n: request.top_n || 2 },
    portfolio: { method: request.portfolio_method || "equal_weight", max_weight: 0.5 },
    execution: {
      trade_at: "next_bar_close",
      transaction_cost_bps: request.transaction_cost_bps ?? 5,
      slippage_bps: request.slippage_bps ?? 2,
    },
    diagnostics: {
      freshness_profile: request.freshness_profile || "research_default",
      require_fresh_prices: !!request.require_fresh_prices,
      require_no_lookahead: true,
    },
  };
}

function strategyCodeOnlyPayload(strategy) {
  const clean = { ...(strategy || quantStrategyDraftFromControls()) };
  delete clean.universe;
  delete clean.benchmark;
  delete clean.created_at;
  delete clean.updated_at;
  delete clean.source;
  delete clean.migration_history;
  return clean;
}

function setStrategyEditor(strategy) {
  if (!els.strategyDefinitionJson) return;
  els.strategyDefinitionJson.value = JSON.stringify(strategyCodeOnlyPayload(strategy), null, 2);
  state.activeStrategyId = String(strategy?.strategy_id || "");
}

function strategyGenerationContextFromControls() {
  const request = quantBacktestRequestFromControls();
  return {
    template: request.template,
    top_n: request.top_n,
    lookback: request.lookback,
    vol_lookback: numberInputValue(els.backtestShortWindow, 21, { min: 1, max: 252 }),
    rebalance_every: request.rebalance_every,
    portfolio_method: request.portfolio_method,
    transaction_cost_bps: request.transaction_cost_bps,
    slippage_bps: request.slippage_bps,
    freshness_profile: request.freshness_profile,
    require_fresh_prices: !!request.require_fresh_prices,
    use_research_score: !!request.use_research_score,
    research_max_age_days: 7,
  };
}

function renderStrategyPromptReview(data) {
  if (!els.strategyPromptReviewSurface) return;
  const advantages = Array.isArray(data?.advantages) ? data.advantages : [];
  const disadvantages = Array.isArray(data?.disadvantages) ? data.disadvantages : [];
  const warnings = Array.isArray(data?.warnings) ? data.warnings : [];
  const listHtml = (items, empty) => items.length
    ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : `<p>${escapeHtml(empty)}</p>`;
  els.strategyPromptReviewSurface.innerHTML = `
    <div class="strategy-review-card">
      <strong>장점</strong>
      ${listHtml(advantages, "생성된 전략의 장점이 없습니다. 프롬프트를 더 구체화하세요.")}
    </div>
    <div class="strategy-review-card warn">
      <strong>단점</strong>
      ${listHtml(disadvantages, "검증 전에는 과최적화, 데이터 공백, 비용 민감도를 확인해야 합니다.")}
      ${warnings.length ? `<p class="muted small">주의: ${escapeHtml(formatQuantWarnings(warnings))}</p>` : ""}
    </div>
  `;
}

async function runQuantStrategyGenerate() {
  if (!els.strategyPromptInput || !els.strategyDefinitionJson) return;
  const prompt = els.strategyPromptInput.value.trim();
  if (!prompt) {
    showQuantStrategyMessage("전략 프롬프트를 먼저 작성하세요.", "failed");
    return;
  }
  const button = els.quantStrategyGenerate;
  if (button) {
    button.disabled = true;
    button.textContent = "생성 중";
  }
  showQuantStrategyMessage("로컬 LLM이 전략 정의(JSON)를 생성하는 중입니다.", "partial");
  try {
    const res = await fetch(API.quantStrategyGenerate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        context: strategyGenerationContextFromControls(),
        use_local_llm: true,
        timeout_s: 45,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    if (!data.strategy) throw new Error("생성된 전략 코드가 없습니다.");
    state.lastStrategyGeneration = data;
    setStrategyEditor(data.strategy);
    renderStrategyPromptReview(data);
    await runQuantStrategyDryRun(data.strategy);
  } catch (err) {
    showQuantStrategyMessage(`전략 생성 실패: ${err.message || err}`, "failed");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "로컬 LLM 생성";
    }
  }
}

function strategyPayloadFromEditor() {
  const raw = els.strategyDefinitionJson?.value || "";
  if (!raw.trim()) return quantStrategyDraftFromControls();
  return strategyCodeOnlyPayload(JSON.parse(raw));
}

function applyStrategyToControls(strategy) {
  if (!strategy || typeof strategy !== "object") return;
  const universe = Array.isArray(strategy.universe) ? strategy.universe : [];
  if (universe.length && els.backtestTicker) setBacktestUniverse(universe);
  if (universe.length && els.portfolioTickers) {
    els.portfolioTickers.value = universe.join(",");
    renderSymbolTargetChips("portfolio");
  }
  if (strategy.benchmark && els.portfolioBenchmark) els.portfolioBenchmark.value = strategy.benchmark;
  if (strategy.benchmark && els.backtestBenchmark) els.backtestBenchmark.value = strategy.benchmark;
  const portfolio = strategy.portfolio || {};
  if (portfolio.method && els.portfolioMethod) els.portfolioMethod.value = portfolio.method;
  if (portfolio.max_weight && els.portfolioMaxWeight) els.portfolioMaxWeight.value = String(portfolio.max_weight);
  const signal = strategy.signal || {};
  if (signal.top_n && els.backtestTopN) els.backtestTopN.value = String(signal.top_n);
  const execution = strategy.execution || {};
  if (execution.transaction_cost_bps !== undefined && els.backtestCostBps) {
    els.backtestCostBps.value = String(execution.transaction_cost_bps);
  }
  if (execution.slippage_bps !== undefined && els.backtestSlippageBps) {
    els.backtestSlippageBps.value = String(execution.slippage_bps);
  }
  const diagnostics = strategy.diagnostics || {};
  if (diagnostics.freshness_profile && els.backtestFreshnessProfile) {
    els.backtestFreshnessProfile.value = diagnostics.freshness_profile;
  }
  if (els.backtestRequireFresh && diagnostics.require_fresh_prices !== undefined) {
    els.backtestRequireFresh.checked = !!diagnostics.require_fresh_prices;
  }
  if (els.backtestUseResearchScore) {
    const features = strategy.features || {};
    els.backtestUseResearchScore.checked = !!features.research_score;
  }
  if (els.backtestStrategy) {
    const hasResearchScore = !!(strategy.features || {}).research_score;
    els.backtestStrategy.value = hasResearchScore
      ? "research_confirmed_momentum"
      : signal.type === "rank_top_n"
        ? "momentum_ranking"
        : "moving_average";
  }
  state.activeStrategyId = String(strategy.strategy_id || "");
  if (els.backtestStrategyRegistry) {
    populateBacktestStrategyRegistry();
    els.backtestStrategyRegistry.value = state.activeStrategyId;
  }
}

function populateBacktestStrategyRegistry() {
  if (!els.backtestStrategyRegistry) return;
  const items = Array.isArray(state.quantStrategyItems) ? state.quantStrategyItems : [];
  const selected = state.activeStrategyId || els.backtestStrategyRegistry.value || "";
  els.backtestStrategyRegistry.innerHTML = `
    <option value="">전략 거버넌스 선택</option>
    ${items.map((item) => {
      const id = item.strategy_id || "";
      const label = item.name || id;
      const source = item.source || "default";
      return `<option value="${escapeHtml(id)}">${escapeHtml(label)} · ${escapeHtml(source)}</option>`;
    }).join("")}
  `;
  if (selected && items.some((item) => item.strategy_id === selected)) {
    els.backtestStrategyRegistry.value = selected;
  }
}

function renderQuantStrategyList(extraHtml = "") {
  if (!els.quantStrategySurface) return;
  const items = Array.isArray(state.quantStrategyItems) ? state.quantStrategyItems : [];
  populateBacktestStrategyRegistry();
  if (!items.length) {
    els.quantStrategySurface.innerHTML = `${extraHtml}${decisionEmpty("아직 사용할 수 있는 전략 정의가 없습니다.")}`;
    return;
  }
  els.quantStrategySurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ok">성공</span>
      <span>${escapeHtml(_fmtNumber(items.length))}개 전략 · 다음 봉 체결 필수</span>
    </div>
    ${extraHtml}
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>전략</th><th>출처</th><th>버전</th><th>체결</th><th>팩터</th><th>작업</th></tr></thead>
        <tbody>
          ${items.map((item) => {
            const features = item.features && typeof item.features === "object" ? Object.keys(item.features) : [];
            const execution = item.execution || {};
            const source = item.source || "default";
            const strategyId = item.strategy_id || "";
            return `
              <tr>
                <td>${escapeHtml(item.name || strategyId)}</td>
                <td>${escapeHtml(source)}</td>
                <td>${escapeHtml(`${item.schema_version || "default"} / ${item.strategy_version || "-"}`)}</td>
                <td><span class="table-status ${execution.trade_at === "next_bar_close" ? "ok" : "fail"}">${escapeHtml(execution.trade_at || "-")}</span></td>
                <td>${escapeHtml(features.join(", ") || "-")}</td>
                <td>
                  <button type="button" class="linkish" data-testid="quant-strategy-row-load" aria-label="전략 불러오기 ${escapeHtml(strategyId)}" data-strategy-load="${escapeHtml(strategyId)}">불러오기</button>
                  <button type="button" class="linkish" data-testid="quant-strategy-row-dry-run" aria-label="전략 검증 ${escapeHtml(strategyId)}" data-strategy-dry="${escapeHtml(strategyId)}">검증</button>
                  ${source === "user" ? `<button type="button" class="linkish" data-testid="quant-strategy-row-delete" aria-label="전략 삭제 ${escapeHtml(strategyId)}" data-strategy-delete="${escapeHtml(strategyId)}">삭제</button>` : ""}
                </td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
  els.quantStrategySurface.querySelectorAll("[data-strategy-load]").forEach((button) => {
    button.addEventListener("click", () => loadQuantStrategyDetail(button.dataset.strategyLoad || ""));
  });
  els.quantStrategySurface.querySelectorAll("[data-strategy-dry]").forEach((button) => {
    button.addEventListener("click", async () => {
      const strategy = await fetchQuantStrategy(button.dataset.strategyDry || "");
      if (strategy) {
        setStrategyEditor(strategy);
        applyStrategyToControls(strategy);
        runQuantStrategyDryRun(strategy);
      }
    });
  });
  els.quantStrategySurface.querySelectorAll("[data-strategy-delete]").forEach((button) => {
    button.addEventListener("click", () => deleteQuantStrategy(button.dataset.strategyDelete || ""));
  });
}

function renderQuantStrategyResult(data) {
  if (!els.quantStrategyResultSurface) return;
  const diagnostics = data.diagnostics || {};
  const status = data.status || "unknown";
  const strategy = data.strategy || {};
  els.quantStrategyResultSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
      <span>${escapeHtml(strategy.strategy_id || state.activeStrategyId || "전략")} · 검증 ${data.valid ? "통과" : "점검 필요"}</span>
    </div>
    <div class="decision-chip-row">
      <span>체결 ${escapeHtml(diagnostics.execution_trade_at || "-")}</span>
      <span>룩어헤드 ${diagnostics.lookahead_safe ? "안전" : "점검"}</span>
      <span>스키마 ${escapeHtml(diagnostics.schema_version || strategy.schema_version || "-")}</span>
      <span>버전 ${escapeHtml(diagnostics.strategy_version || strategy.strategy_version || "-")}</span>
      ${(diagnostics.feature_ids || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
    </div>
    ${(diagnostics.migration_history || []).length ? `<div class="decision-warning">전략 스키마 자동 마이그레이션: ${escapeHtml(diagnostics.migration_history.map((item) => item.migration || item.to_schema_version || "migration").join(", "))}</div>` : ""}
    ${(diagnostics.missing_features || []).length ? `<div class="decision-warning">누락 팩터: ${escapeHtml(diagnostics.missing_features.join(", "))}</div>` : ""}
    ${(data.warnings || []).length ? `<div class="decision-warning">${escapeHtml(formatQuantWarnings(data.warnings))}</div>` : ""}
  `;
}

async function loadQuantStrategies(force = false) {
  if (!els.quantStrategySurface || (state.quantStrategiesLoaded && !force)) return;
  const startedAt = Date.now();
  setButtonBusy(els.quantStrategyRefresh, true, "새로고침 중");
  els.quantStrategySurface.innerHTML = decisionEmpty("저장된 전략 목록을 불러오는 중입니다.");
  try {
    const res = await fetch(API.quantStrategies);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.quantStrategyItems = Array.isArray(data.items) ? data.items : [];
    state.quantStrategiesLoaded = true;
    renderQuantStrategyList(renderActionCompletion("전략 목록 갱신 완료", startedAt, `${_fmtNumber(state.quantStrategyItems.length)}개 전략`));
    if (!els.strategyDefinitionJson?.value.trim()) {
      setStrategyEditor(state.quantStrategyItems[0] || quantStrategyDraftFromControls());
    }
  } catch (err) {
    els.quantStrategySurface.innerHTML = decisionEmpty(`전략 목록 조회 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.quantStrategyRefresh, false);
  }
}

async function fetchQuantStrategy(strategyId) {
  if (!strategyId) return null;
  const res = await fetch(API.quantStrategy(strategyId));
  const data = await res.json();
  if (!res.ok) {
    showQuantStrategyMessage(`전략 불러오기 실패: ${data.detail || `HTTP ${res.status}`}`, "failed");
    return null;
  }
  return data;
}

async function loadQuantStrategyDetail(strategyId) {
  const strategy = await fetchQuantStrategy(strategyId);
  if (!strategy) return;
  setStrategyEditor(strategy);
  applyStrategyToControls(strategy);
  populateBacktestStrategyRegistry();
  showQuantStrategyMessage(`${strategy.strategy_id || "전략"}을 작업 영역에 불러왔습니다.`, "success");
}

async function runQuantStrategyDryRun(strategy = null) {
  if (!els.quantStrategyResultSurface) return;
  let payload = strategy;
  try {
    payload = payload || strategyPayloadFromEditor();
  } catch (err) {
    showQuantStrategyMessage(`전략 코드 JSON이 올바르지 않습니다: ${err.message || err}`, "failed");
    return;
  }
  els.quantStrategyResultSurface.innerHTML = decisionEmpty("전략 검증이 팩터와 다음 봉 체결 정책을 확인하는 중입니다.");
  try {
    const res = await fetch(API.quantStrategyDryRun, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    if (data.strategy) {
      setStrategyEditor(data.strategy);
      applyStrategyToControls(data.strategy);
    }
    renderQuantStrategyResult(data);
  } catch (err) {
    showQuantStrategyMessage(`전략 검증 실패: ${err.message || err}`, "failed");
  }
}

async function saveQuantStrategy() {
  let payload;
  try {
    payload = strategyPayloadFromEditor();
  } catch (err) {
    showQuantStrategyMessage(`전략 코드 JSON이 올바르지 않습니다: ${err.message || err}`, "failed");
    return;
  }
  els.quantStrategyResultSurface.innerHTML = decisionEmpty("전략 정의를 저장하는 중입니다.");
  try {
    const res = await fetch(API.quantStrategySave, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    if (data.strategy) setStrategyEditor(data.strategy);
    showQuantStrategyMessage(`${data.strategy?.strategy_id || payload.strategy_id} 저장 완료.`, "success");
    state.quantStrategiesLoaded = false;
    await loadQuantStrategies(true);
  } catch (err) {
    showQuantStrategyMessage(`전략 저장 실패: ${err.message || err}`, "failed");
  }
}

async function deleteQuantStrategy(strategyId = "") {
  let id = strategyId || state.activeStrategyId || "";
  try {
    if (!id) id = strategyPayloadFromEditor().strategy_id || "";
    if (!id) {
      showQuantStrategyMessage("삭제할 저장 전략이 선택되지 않았습니다.", "failed");
      return;
    }
    const res = await fetch(API.quantStrategy(id), { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    showQuantStrategyMessage(`${data.strategy_id || id} 삭제 완료.`, "success");
    setStrategyEditor(quantStrategyDraftFromControls());
    state.quantStrategiesLoaded = false;
    await loadQuantStrategies(true);
  } catch (err) {
    showQuantStrategyMessage(`전략 삭제 실패: ${err.message || err}`, "failed");
  }
}

function showQuantStrategyMessage(message, status = "success") {
  if (!els.quantStrategyResultSurface) return;
  els.quantStrategyResultSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

async function runHomeBacktest() {
  if (!els.backtestSurface || !els.backtestTicker) return;
  const startedAt = Date.now();
  setButtonBusy(els.backtestRun, true, "실행 중");
  try {
    const resolution = await resolveBacktestUniverseAvailability(els.backtestSurface);
    if (!resolution.ok) {
      if (!els.backtestSurface.textContent.trim() || !selectedBacktestUniverse().length) {
        els.backtestSurface.innerHTML = decisionEmpty("백테스트할 티커를 하나 이상 입력해야 합니다.");
      }
      els.backtestSurface.insertAdjacentHTML(
        "afterbegin",
        renderActionCompletion("백테스트 실행 보류", startedAt, resolution.error ? "종목 데이터 확인 실패" : "실행 가능한 가격 이력 없음", "warn")
      );
      return;
    }
    const legacyRequest = backtestRequestFromControls();
    const request = quantBacktestRequestFromControls();
    if (!request.tickers.length) {
      els.backtestSurface.innerHTML = `${renderActionCompletion("백테스트 실행 보류", startedAt, "티커 입력 필요", "warn")}${decisionEmpty("백테스트할 티커를 하나 이상 입력해야 합니다.")}`;
      return;
    }
    state.lastBacktestRequest = legacyRequest;
    state.lastQuantBacktestRequest = request;
    els.backtestSurface.innerHTML = decisionEmpty(`${request.tickers.join(", ")} 백테스트를 실행 중입니다.`);
    const res = await fetch(API.quantBacktest, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    const enriched = await attachBenchmarkComparison(data, { ...request, ...legacyRequest });
    state.lastBacktestResult = enriched;
    syncPortfolioFromBacktest();
    renderQuantBacktestResult(enriched, { ...request, ...legacyRequest });
    els.backtestSurface.insertAdjacentHTML(
      "afterbegin",
      renderActionCompletion("백테스트 완료", startedAt, `${data.run_id || "run"} · ${data.status || "success"}`)
    );
    if (resolution.data && (resolution.data.unavailable || []).length) {
      els.backtestSurface.insertAdjacentHTML("afterbegin", renderUniverseResolutionNotice(resolution.data));
    }
    loadQuantRunHistory(true);
  } catch (err) {
    els.backtestSurface.innerHTML = `${renderActionCompletion("백테스트 실패", startedAt, err.message || String(err), "fail")}${decisionEmpty(`백테스트 실패: ${err.message || err}`)}`;
  } finally {
    setButtonBusy(els.backtestRun, false);
  }
}

function normalizeQuantBundle(bundle) {
  const config = bundle.config || {};
  const manifest = bundle.manifest || {};
  const files = manifest.files || {};
  return {
    status: bundle.status || "success",
    run_id: bundle.run_id || manifest.run_id || "",
    template: config.template || "unknown",
    tickers: config.tickers || [],
    benchmark: config.benchmark || "",
    date_range: {
      start: config.start_date || "",
      end: config.end_date || "",
    },
    metrics: bundle.metrics || {},
    equity_curve: Array.isArray(bundle.equity_curve) ? bundle.equity_curve : [],
    drawdown_curve: Array.isArray(bundle.drawdown_curve) ? bundle.drawdown_curve : [],
    trades: Array.isArray(bundle.trades) ? bundle.trades : [],
    signals: Array.isArray(bundle.signals) ? bundle.signals : [],
    weights: Array.isArray(bundle.weights) ? bundle.weights : [],
    diagnostics: bundle.diagnostics || {},
    artifacts: files,
    manifest,
    data_snapshot: manifest.data_snapshot || {},
    config_hash: manifest.config_hash || "",
    code_version: manifest.code_version || {},
    replay_reports: bundle.replay_reports || {},
    config,
  };
}

async function loadQuantBacktestArtifact(runId) {
  if (!runId || !els.backtestSurface) return;
  els.backtestSurface.innerHTML = decisionEmpty(`${runId} artifact bundle is loading.`);
  try {
    const res = await fetch(API.quantBacktestBundle(runId));
    const bundle = await res.json();
    if (!res.ok) throw new Error(bundle.detail || `HTTP ${res.status}`);
    const data = normalizeQuantBundle(bundle);
    const artifactRequest = {
      ...(data.config || {}),
      benchmark: data.config?.benchmark || els.backtestBenchmark?.value || "SPY",
      compare_benchmark: !!els.backtestBenchmarkCompare?.checked,
    };
    const enriched = await attachBenchmarkComparison(data, artifactRequest);
    state.lastBacktestResult = enriched;
    state.lastQuantBacktestRequest = artifactRequest;
    state.lastBacktestRequest = artifactRequest;
    renderQuantBacktestResult(enriched, artifactRequest);
    syncPortfolioFromBacktest();
  } catch (err) {
    els.backtestSurface.innerHTML = decisionEmpty(`백테스트 산출물 불러오기 실패: ${err.message || err}`);
  }
}

function renderQuantExportStorageReport(data) {
  const rendered = window.FinGPTQuantUi?.exportStorageReport?.(data);
  return rendered || decisionEmpty("Quant UI module is unavailable.");
}

function renderCrossRunExportCleanupPlan(data) {
  const candidates = Array.isArray(data.candidates) ? data.candidates : [];
  const pruned = Array.isArray(data.pruned_exports) ? data.pruned_exports : [];
  const applied = !!data.cleanup_applied;
  const shown = applied ? pruned : candidates;
  if (!applied) {
    state.lastCrossRunExportCleanupPreview = data;
  }
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.status || "success"))}">${escapeHtml(data.status || "success")}</span>
      <span>cross-run export cleanup ${applied ? "applied" : "preview"}</span>
    </div>
    <div class="decision-chip-row">
      <span>keep last ${escapeHtml(_fmtNumber(data.keep_last_exports || 0))}</span>
      <span>stale ${escapeHtml(_fmtNumber(data.stale_after_days || 0))}d</span>
      <span>eligible ${escapeHtml(_fmtNumber(data.eligible_export_count || 0))}</span>
      <span>candidates ${escapeHtml(_fmtNumber(data.candidate_count || 0))}</span>
      <span>bytes ${escapeHtml(_fmtNumber(applied ? data.total_bytes_pruned || 0 : data.total_bytes_to_prune || 0))}</span>
      <span>preview ${escapeHtml(String(data.preview_id || "").slice(0, 12))}</span>
    </div>
    ${!applied && candidates.length ? `
      <div class="decision-chip-row">
        <button type="button" class="linkish decision-inline-action danger" data-action="cross-run-cleanup-apply">apply exact preview</button>
      </div>
    ` : ""}
    ${shown.length ? `
      <div class="decision-section-title">${applied ? "Pruned exports" : "Exports that would be pruned"}</div>
      ${renderArtifactExportCleanupTable(shown)}
    ` : decisionEmpty("No cross-run export directories match this cleanup policy.")}
  `;
}

async function previewCrossRunExportCleanup(keepLast = 1, staleAfterDays = 0) {
  if (!els.quantRunHistorySurface) return;
  const params = new URLSearchParams({
    keep_last_exports: String(keepLast || 1),
    stale_after_days: String(staleAfterDays ?? 0),
    limit: "50",
  });
    els.quantRunHistorySurface.innerHTML = decisionEmpty("실행 간 내보내기 정리 미리보기를 불러오는 중입니다.");
  try {
    const res = await fetch(`${API.quantExportCleanupPreview}?${params.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.quantRunHistorySurface.innerHTML = renderCrossRunExportCleanupPlan(data);
  } catch (err) {
    els.quantRunHistorySurface.innerHTML = decisionEmpty(`실행 간 내보내기 정리 미리보기 실패: ${err.message || err}`);
  }
}

async function applyCrossRunExportCleanup() {
  if (!els.quantRunHistorySurface) return;
  const preview = state.lastCrossRunExportCleanupPreview || {};
  const candidateIds = Array.isArray(preview.candidate_ids) ? preview.candidate_ids : [];
  els.quantRunHistorySurface.innerHTML = decisionEmpty("Applying exact cross-run export cleanup preview.");
  try {
    const res = await fetch(API.quantExportCleanup, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preview_id: preview.preview_id || "",
        candidate_ids: candidateIds,
        keep_last_exports: preview.keep_last_exports || 1,
        stale_after_days: preview.stale_after_days ?? 0,
        limit: preview.limit || 50,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.lastCrossRunExportCleanupPreview = null;
    els.quantRunHistorySurface.innerHTML = renderCrossRunExportCleanupPlan(data);
  } catch (err) {
    els.quantRunHistorySurface.innerHTML = decisionEmpty(`실행 간 내보내기 정리 실행 실패: ${err.message || err}`);
  }
}

async function loadQuantExportStorageReport() {
  if (!els.quantRunHistorySurface) return;
    els.quantRunHistorySurface.innerHTML = decisionEmpty("실행 간 내보내기 저장소 리포트를 불러오는 중입니다.");
  try {
    const res = await fetch(`${API.quantExportStorage}?limit=20&stale_after_days=30`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.quantRunHistorySurface.innerHTML = renderQuantExportStorageReport(data);
    els.quantRunHistorySurface.querySelectorAll("[data-quant-run-id]").forEach((button) => {
      button.addEventListener("click", () => loadQuantBacktestArtifact(button.dataset.quantRunId || ""));
    });
  } catch (err) {
    els.quantRunHistorySurface.innerHTML = decisionEmpty(`내보내기 저장소 리포트 조회 실패: ${err.message || err}`);
  }
}

function setQuantRunCompareSelection(runId, selected) {
  const clean = String(runId || "").trim();
  if (!clean) return;
  const current = Array.isArray(state.quantRunCompareSelection) ? state.quantRunCompareSelection.slice() : [];
  const without = current.filter((item) => item !== clean);
  if (selected) {
    without.push(clean);
    state.quantRunCompareSelection = without.slice(-2);
  } else {
    state.quantRunCompareSelection = without;
  }
  syncQuantRunCompareSelectionState();
}

function syncQuantRunCompareSelectionState() {
  const selected = Array.isArray(state.quantRunCompareSelection) ? state.quantRunCompareSelection : [];
  if (!els.quantRunHistorySurface) return;
  els.quantRunHistorySurface.querySelectorAll('[data-action="toggle-run-compare"]').forEach((input) => {
    const runId = input.dataset.runId || "";
    input.checked = selected.includes(runId);
  });
  const status = els.quantRunHistorySurface.querySelector('[data-testid="quant-run-compare-status"]');
  if (status) {
    status.textContent = selected.length
      ? `비교 선택 ${selected.length}/2 · ${selected.map((item) => item.slice(0, 24)).join(" vs ")}`
      : "비교할 실행 2개를 선택하세요.";
  }
  const button = els.quantRunHistorySurface.querySelector('[data-testid="quant-run-compare-selected"]');
  if (button) {
    button.disabled = selected.length !== 2;
  }
}

function renderQuantRunComparison(data) {
  const runs = Array.isArray(data.runs) ? data.runs : [];
  const primary = runs[0] || {};
  const comparison = runs[1] || {};
  const metrics = Array.isArray(data.metrics) ? data.metrics : [];
  const differences = Array.isArray(data.config_differences) ? data.config_differences : [];
  const lineage = data.lineage || {};
  const diagnostics = data.diagnostics || {};
  return `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(data.status || "success"))}">${escapeHtml(data.status || "success")}</span>
      <span>${escapeHtml(data.primary_run_id || "")} vs ${escapeHtml(data.comparison_run_id || "")}</span>
    </div>
    <div class="decision-chip-row" data-testid="quant-run-compare-result">
      <span>schema ${escapeHtml(data.schema_version || "-")}</span>
      <span>config ${lineage.config_hash_match ? "match" : "changed"}</span>
      <span>code ${lineage.code_commit_match ? "match" : "changed"}</span>
      <span>snapshot ${lineage.data_snapshot_match ? "match" : "changed"}</span>
      <span>lookahead ${diagnostics.lookahead_safe_all ? "safe" : "check"}</span>
    </div>
    <div class="decision-chip-row">
      ${runs.map((run) => `<button type="button" class="linkish decision-inline-action" data-action="open-quant-run" data-run-id="${escapeHtml(run.run_id || "")}">open ${escapeHtml(String(run.run_id || "").slice(0, 20))}</button>`).join("")}
      <button type="button" class="linkish decision-inline-action" data-action="refresh-run-history">실행 이력으로 돌아가기</button>
    </div>
    <div class="decision-list compact">
      <div class="decision-list-row"><span>Primary</span><strong>${escapeHtml(primary.template || "-")} · ${escapeHtml((primary.tickers || []).join(",") || "-")} · ${escapeHtml(fmtDate(primary.generated_at) || "-")}</strong></div>
      <div class="decision-list-row"><span>Comparison</span><strong>${escapeHtml(comparison.template || "-")} · ${escapeHtml((comparison.tickers || []).join(",") || "-")} · ${escapeHtml(fmtDate(comparison.generated_at) || "-")}</strong></div>
      <div class="decision-list-row"><span>Data warnings</span><strong>stale ${escapeHtml(_fmtNumber((diagnostics.stale_assets || []).length))} · missing ${escapeHtml(_fmtNumber((diagnostics.missing_assets || []).length))} · warnings ${escapeHtml(_fmtNumber(diagnostics.warning_count || 0))}</strong></div>
    </div>
    <div class="decision-section-title">Metric delta</div>
    <div class="decision-table-wrap">
      <table class="decision-table">
        <thead><tr><th>Metric</th><th>Primary</th><th>Comparison</th><th>Delta</th><th>Relative</th></tr></thead>
        <tbody>
          ${metrics.map((row) => `
            <tr>
              <td>${escapeHtml(row.metric || "")}</td>
              <td>${escapeHtml(formatQuantValue(row.primary))}</td>
              <td>${escapeHtml(formatQuantValue(row.comparison))}</td>
              <td><span class="table-status ${Math.abs(Number(row.delta || 0)) < 1e-10 ? "ok" : "warn"}">${escapeHtml(formatQuantValue(row.delta))}</span></td>
              <td>${row.relative_delta === null || row.relative_delta === undefined ? "-" : escapeHtml(fmtMetricRatio(row.relative_delta))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
    <div class="decision-section-title">Config differences</div>
    ${differences.length ? `
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>Field</th><th>Primary</th><th>Comparison</th></tr></thead>
          <tbody>
            ${differences.map((row) => `
              <tr>
                <td>${escapeHtml(row.field || "")}</td>
                <td>${escapeHtml(formatCompareValue(row.primary))}</td>
                <td>${escapeHtml(formatCompareValue(row.comparison))}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : decisionEmpty("두 실행의 주요 설정 차이가 없습니다.")}
  `;
}

function formatCompareValue(value) {
  if (Array.isArray(value)) return value.join(",");
  if (value && typeof value === "object") return JSON.stringify(value);
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

async function compareSelectedQuantRuns() {
  if (!els.quantRunHistorySurface) return;
  const selected = Array.isArray(state.quantRunCompareSelection) ? state.quantRunCompareSelection.slice(0, 2) : [];
  if (selected.length !== 2) {
    syncQuantRunCompareSelectionState();
    return;
  }
  els.quantRunHistorySurface.innerHTML = decisionEmpty(`${selected[0]} vs ${selected[1]} 비교를 불러오는 중입니다.`);
  try {
    const res = await fetch(API.quantBacktestsCompare, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: selected }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    els.quantRunHistorySurface.innerHTML = renderQuantRunComparison(data);
  } catch (err) {
    els.quantRunHistorySurface.innerHTML = decisionEmpty(`실행 비교 실패: ${err.message || err}`);
  }
}

async function loadQuantRunHistory(force = false) {
  if (!els.quantRunHistorySurface || (state.quantRunHistoryLoaded && !force)) return;
  const startedAt = Date.now();
  setButtonBusy(els.quantRunHistoryRefresh, true, "새로고침 중");
  els.quantRunHistorySurface.innerHTML = decisionEmpty("퀀트 랩 산출물 이력을 불러오는 중입니다.");
  try {
    const res = await fetch(`${API.quantBacktests}?limit=8`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    const items = Array.isArray(data.items) ? data.items : [];
    state.quantRunHistoryLoaded = true;
    if (!items.length) {
      els.quantRunHistorySurface.innerHTML = `${renderActionCompletion("실행 이력 갱신 완료", startedAt, "0개 실행")}${decisionEmpty("아직 저장된 퀀트 랩 백테스트 산출물이 없습니다.")}`;
      return;
    }
    els.quantRunHistorySurface.innerHTML = `
      ${renderActionCompletion("실행 이력 갱신 완료", startedAt, `${_fmtNumber(items.length)}개 실행`)}
      <div class="decision-status-row">
        <span class="decision-badge ok">${escapeHtml(data.status || "success")}</span>
        <span>${escapeHtml(_fmtNumber(data.count))} saved runs</span>
      </div>
      <div class="decision-chip-row" data-testid="quant-run-compare-controls">
        <span data-testid="quant-run-compare-status">비교할 실행 2개를 선택하세요.</span>
        <button type="button" class="linkish decision-inline-action" data-testid="quant-run-compare-selected" data-action="run-compare-selected" disabled>선택 비교</button>
      </div>
      <div class="decision-table-wrap">
        <table class="decision-table">
          <thead><tr><th>Compare</th><th>Run</th><th>Template</th><th>Universe</th><th>Sharpe</th><th>MDD</th><th>Context</th><th>Data</th><th>Lookahead</th><th>Actions</th></tr></thead>
          <tbody>
            ${items.map((item) => {
              const metrics = item.metrics || {};
              const diagnostics = item.diagnostics || {};
              const policy = item.freshness_policy || item.data_snapshot?.freshness_policy || {};
              const configHash = String(item.config_hash || "").slice(0, 10);
              return `
                <tr>
                  <td><input type="checkbox" data-testid="quant-run-compare" aria-label="Compare ${escapeHtml(item.run_id || "")}" data-action="toggle-run-compare" data-run-id="${escapeHtml(item.run_id || "")}" ${state.quantRunCompareSelection.includes(item.run_id) ? "checked" : ""} /></td>
                  <td>${escapeHtml(item.run_id || "")}</td>
                  <td>${escapeHtml(item.template || "")}</td>
                  <td>${escapeHtml((item.tickers || []).join(","))}</td>
                  <td>${escapeHtml(fmtDecimal(metrics.sharpe, 2))}</td>
                  <td>${escapeHtml(fmtMetricRatio(metrics.max_drawdown))}</td>
                  <td>${escapeHtml(policy.profile || "-")}${configHash ? ` · ${escapeHtml(configHash)}` : ""}</td>
                  <td>${renderSnapshotFreshnessBadge(item.snapshot_freshness || item.data_snapshot?.snapshot_freshness || {})}</td>
                  <td><span class="table-status ${diagnostics.lookahead_safe ? "ok" : "fail"}">${diagnostics.lookahead_safe ? "safe" : "check"}</span></td>
                  <td>
                    <details class="row-action-menu">
                      <summary>Actions</summary>
                      <div class="row-action-list">
                        <button type="button" class="linkish" data-testid="quant-replay-reports" aria-label="Replay reports ${escapeHtml(item.run_id || "")}" data-quant-replay-reports-id="${escapeHtml(item.run_id || "")}">reports ${escapeHtml(_fmtNumber(item.replay_reports?.count || 0))}</button>
                        <button type="button" class="linkish" data-testid="quant-run-open" aria-label="Open quant run ${escapeHtml(item.run_id || "")}" data-quant-run-id="${escapeHtml(item.run_id || "")}">open</button>
                        <button type="button" class="linkish" data-testid="quant-replay-compare" aria-label="Replay compare ${escapeHtml(item.run_id || "")}" data-quant-replay-id="${escapeHtml(item.run_id || "")}">compare</button>
                        <button type="button" class="linkish" data-testid="quant-run-export-jsonl" aria-label="JSONL export ${escapeHtml(item.run_id || "")}" data-quant-export-id="${escapeHtml(item.run_id || "")}" data-format="jsonl">jsonl</button>
                        <button type="button" class="linkish" data-testid="quant-run-export-parquet" aria-label="Parquet export ${escapeHtml(item.run_id || "")}" title="Parquet 내보내기는 pandas와 pyarrow 또는 fastparquet가 필요합니다." data-quant-export-id="${escapeHtml(item.run_id || "")}" data-format="parquet">parquet</button>
                      </div>
                    </details>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
      <div class="decision-chip-row">
        ${items.slice(0, 3).map((item) => `<span>${escapeHtml(fmtDate(item.generated_at))} · ${escapeHtml(compactArtifactPath(item.manifest))}</span>`).join("")}
      </div>
    `;
    els.quantRunHistorySurface.querySelectorAll("[data-quant-run-id]").forEach((button) => {
      button.addEventListener("click", () => loadQuantBacktestArtifact(button.dataset.quantRunId || ""));
    });
    els.quantRunHistorySurface.querySelectorAll("[data-quant-replay-id]").forEach((button) => {
      button.addEventListener("click", () => runQuantBacktestReplay(button.dataset.quantReplayId || ""));
    });
    els.quantRunHistorySurface.querySelectorAll("[data-quant-replay-reports-id]").forEach((button) => {
      button.addEventListener("click", () => loadQuantReplayReports(button.dataset.quantReplayReportsId || ""));
    });
    els.quantRunHistorySurface.querySelectorAll("[data-quant-export-id]").forEach((button) => {
      button.addEventListener("click", () => exportQuantBacktestArtifact(button.dataset.quantExportId || "", button.dataset.format || "jsonl"));
    });
    syncQuantRunCompareSelectionState();
  } catch (err) {
    els.quantRunHistorySurface.innerHTML = decisionEmpty(`실행 이력 로드 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.quantRunHistoryRefresh, false);
  }
}

async function runPortfolioOptimize() {
  if (!els.portfolioSurface || !els.portfolioTickers) return;
  const startedAt = Date.now();
  setButtonBusy(els.portfolioOptimize, true, "최적화 중");
  let tickers = parseTickerInput(els.portfolioTickers.value || "");
  if (!tickers.length) {
    els.portfolioSurface.innerHTML = decisionEmpty("최적화할 티커를 하나 이상 입력해야 합니다.");
    setButtonBusy(els.portfolioOptimize, false);
    return;
  }
  const resolution = await resolvePortfolioUniverseAvailability(els.portfolioSurface);
  if (!resolution.ok) {
    setButtonBusy(els.portfolioOptimize, false);
    return;
  }
  tickers = resolution.tickers;
  const startDate = textInputValue(els.portfolioStartDate);
  const endDate = textInputValue(els.portfolioEndDate);
  const lookbackDays = numberInputValue(els.portfolioLookbackDays, 756, { min: 2, max: 5000 });
  const maxWeight = numberInputValue(els.portfolioMaxWeight, 0.6, { min: 0.01, max: 1 });
  const benchmark = normalizeTickerToken(els.portfolioBenchmark?.value || "SPY") || "SPY";
  const covarianceMethod = els.portfolioCovarianceMethod?.value || "sample";
  const shrinkageAlpha = numberInputValue(els.portfolioShrinkageAlpha, 0.1, { min: 0, max: 1 });
  const freshnessOptions = selectedQuantFreshnessOptions();
  els.portfolioSurface.innerHTML = decisionEmpty(`${tickers.join(", ")} 포트폴리오 최적화를 실행 중입니다.`);
  try {
    const payload = {
      tickers,
      method: els.portfolioMethod?.value || "equal_weight",
      benchmark,
      start_date: startDate,
      end_date: endDate,
      lookback_days: lookbackDays,
      max_weight: maxWeight,
      covariance_method: covarianceMethod,
      shrinkage_alpha: shrinkageAlpha,
      freshness_profile: freshnessOptions.freshnessProfile,
    };
    if (freshnessOptions.requireFreshPrices) payload.require_fresh_prices = true;
    const res = await fetch(API.portfolioOptimize, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    const weights = data.weights || {};
    const entries = Object.entries(weights).sort((a, b) => Number(b[1]) - Number(a[1]));
    const status = data.status || "unknown";
    const diagnostics = data.diagnostics || {};
    const returnCounts = data.return_counts || {};
    const portfolioMetrics = data.portfolio_metrics || {};
    const riskContributions = data.risk_contributions || {};
    const correlationMatrix = data.correlation_matrix || {};
    els.portfolioSurface.innerHTML = `
      ${renderActionCompletion("포트폴리오 최적화 완료", startedAt, `${_fmtNumber(entries.length)}개 자산`)}
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">${escapeHtml(decisionStatusLabel(status))}</span>
        <span>${escapeHtml(portfolioMethodLabel(data.method || ""))} · ${escapeHtml(data.benchmark || benchmark)} 벤치마크 · 비중 합계 ${escapeHtml(String(data.sum_weights ?? "-"))}</span>
      </div>
      ${renderUniverseResolutionNotice(resolution.data)}
      <div class="decision-summary ok">
        ${escapeHtml(tickers.join(", "))} · ${escapeHtml(startDate || "조회 기간")} -> ${escapeHtml(endDate || "최근")} · ${escapeHtml(String(lookbackDays))}일 가격 기준
      </div>
      ${renderFreshnessAuditPanel(data)}
      ${renderPortfolioDecisionBrief({
        entries,
        portfolioMetrics,
        diagnostics,
        riskContributions,
        method: data.method || els.portfolioMethod?.value,
        benchmark: data.benchmark || benchmark,
        maxWeight,
      })}
      <div class="portfolio-weight-list">
        ${entries.length ? entries.map(([ticker, weight]) => `
          <div class="portfolio-weight-row">
            <span>${escapeHtml(ticker)}</span>
            <div><i style="width:${Math.max(2, Math.min(100, Number(weight) * 100))}%"></i></div>
            <strong>${escapeHtml(fmtPct(Number(weight) * 100))}</strong>
          </div>
        `).join("") : '<div class="muted small">사용 가능한 비중 결과가 없습니다.</div>'}
      </div>
      <div class="decision-metric-grid dense">
        ${decisionMetric("자산 수", _fmtNumber(diagnostics.asset_count || entries.length), status)}
        ${decisionMetric("최대 비중", fmtPct(Number(data.max_weight || maxWeight) * 100), status)}
        ${decisionMetric("최소 비중", entries.length ? fmtPct(Math.min(...entries.map(([, weight]) => Number(weight))) * 100) : "-", status)}
        ${decisionMetric("수익률 샘플", _fmtNumber(Object.values(returnCounts).reduce((sum, value) => sum + Number(value || 0), 0)), status)}
        ${decisionMetric("기대수익", fmtMetricRatio(portfolioMetrics.expected_annual_return), status)}
        ${decisionMetric("예상 변동성", fmtMetricRatio(portfolioMetrics.annualized_volatility), status)}
        ${decisionMetric("예상 Sharpe", fmtDecimal(portfolioMetrics.sharpe, 2), status)}
        ${decisionMetric("초과수익", fmtMetricRatio(portfolioMetrics.active_annual_return), status)}
        ${decisionMetric("추적오차", fmtMetricRatio(portfolioMetrics.tracking_error), status)}
        ${decisionMetric("정보비율", fmtDecimal(portfolioMetrics.information_ratio, 2), status)}
        ${decisionMetric("베타", fmtDecimal(portfolioMetrics.beta_to_benchmark, 2), status)}
        ${decisionMetric("공분산", `${diagnostics.covariance_method || "sample"}${diagnostics.covariance_shrinkage_used ? ` ${fmtDecimal(diagnostics.shrinkage_alpha, 2)}` : ""}`, diagnostics.uses_covariance ? "ok" : "warn")}
        ${decisionMetric("효과 포지션", fmtDecimal(diagnostics.effective_number_of_positions, 2), status)}
      </div>
      ${Object.keys(riskContributions).length ? `
        <div class="decision-section-title">위험 기여도</div>
        ${renderRiskContributionBars(riskContributions)}
      ` : ""}
      ${renderCorrelationPreview(correlationMatrix)}
      ${Object.keys(returnCounts).length ? `
        <div class="decision-section-title">데이터 사용량</div>
        <div class="decision-chip-row">
          ${Object.entries(returnCounts).map(([ticker, count]) => `<span>${escapeHtml(ticker)} ${escapeHtml(_fmtNumber(count))}개 수익률</span>`).join("")}
        </div>
      ` : ""}
      ${(data.missing_assets || []).length ? `<div class="decision-warning">누락 데이터: ${escapeHtml(data.missing_assets.join(", "))}</div>` : ""}
      ${(data.warnings || []).length ? `<div class="decision-warning">${escapeHtml(formatQuantWarnings(data.warnings))}</div>` : ""}
    `;
  } catch (err) {
    els.portfolioSurface.innerHTML = decisionEmpty(`포트폴리오 최적화 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.portfolioOptimize, false);
  }
}

function aiNumberInput(el, fallback, { min = -Infinity, max = Infinity } = {}) {
  const value = Number(el?.value);
  if (!Number.isFinite(value)) return fallback;
  return Math.max(min, Math.min(max, value));
}

function aiRangeInput(el, fallback) {
  const parts = String(el?.value || "").split(",").map((item) => Number(item.trim()));
  const min = Number.isFinite(parts[0]) ? parts[0] : fallback[0];
  const max = Number.isFinite(parts[1]) ? parts[1] : fallback[1];
  return { min: Math.max(0, Math.min(100, min)), max: Math.max(0, Math.min(100, Math.max(min, max))) };
}

const AI_PORTFOLIO_UNIVERSE_LABELS = {
  default_multi_asset: "프리셋 · 기본 멀티에셋",
  quant_lab_default: "프리셋 · Quant Lab 기본",
  sp500_top_200: "프리셋 · 미국 대형주 200",
  etf_core_100: "프리셋 · 주요 ETF 100",
  kr_300: "프리셋 · 한국 300",
  crypto_core: "프리셋 · 암호화폐 2",
  all_supported: "프리셋 · 전체 지원 602",
  custom: "직접 입력 · 쉼표 구분 심볼",
};

function aiPortfolioSelectedUniverseLabel() {
  const selected = els.aiPortfolioUniverse?.value || "default_multi_asset";
  const apiItem = state.aiPortfolioUniverses.find((item) => item.id === selected);
  if (apiItem?.display_name) {
    return `${apiItem.source_type === "direct_input" ? "직접 입력" : "프리셋"} · ${apiItem.display_name}`;
  }
  return AI_PORTFOLIO_UNIVERSE_LABELS[selected] || selected;
}

function syncAiPortfolioUniverseMode() {
  const selected = els.aiPortfolioUniverse?.value || "default_multi_asset";
  const isCustom = selected === "custom";
  if (els.aiPortfolioCustomUniverse) {
    els.aiPortfolioCustomUniverse.disabled = !isCustom;
    els.aiPortfolioCustomUniverse.setAttribute("aria-disabled", isCustom ? "false" : "true");
  }
  if (els.aiPortfolioCustomUniverseWrap) {
    els.aiPortfolioCustomUniverseWrap.classList.toggle("is-disabled", !isCustom);
  }
  if (els.aiPortfolioUniverseStatus) {
    const customCount = parseTickerInput(els.aiPortfolioCustomUniverse?.value || "").length;
    els.aiPortfolioUniverseStatus.classList.toggle("warn", isCustom && !customCount);
    els.aiPortfolioUniverseStatus.classList.toggle("ok", !isCustom || customCount > 0);
    els.aiPortfolioUniverseStatus.textContent = isCustom
      ? `현재 사용: 직접 입력 심볼 목록 · ${customCount}개`
      : `현재 사용: ${aiPortfolioSelectedUniverseLabel()} · 직접 입력값은 무시됨`;
  }
}

function aiPortfolioUniverseId() {
  syncAiPortfolioUniverseMode();
  const selected = els.aiPortfolioUniverse?.value || "default_multi_asset";
  if (selected === "custom") {
    const raw = String(els.aiPortfolioCustomUniverse?.value || "").trim();
    return raw ? `custom:${raw}` : "default_multi_asset";
  }
  return selected;
}

function aiPortfolioPolicyOverrides() {
  return {
    target_volatility: aiNumberInput(els.aiPortfolioTargetVolatility, 12, { min: 0, max: 100 }),
    max_drawdown_alert: aiNumberInput(els.aiPortfolioMaxDrawdown, -15, { max: 0 }),
    min_cash_weight: aiNumberInput(els.aiPortfolioMinCash, 5, { min: 0, max: 100 }),
    max_single_asset_weight: aiNumberInput(els.aiPortfolioMaxSingle, 30, { min: 1, max: 100 }),
    max_sector_weight: aiNumberInput(els.aiPortfolioMaxSector, 40, { min: 1, max: 100 }),
    rebalance_frequency: els.aiPortfolioRebalanceFrequency?.value || "monthly",
    weight_drift_threshold: aiNumberInput(els.aiPortfolioDriftThreshold, 5, { min: 0, max: 100 }),
    max_turnover: aiNumberInput(els.aiPortfolioMaxTurnover, 20, { min: 0, max: 100 }),
    optimization_method: els.aiPortfolioOptimization?.value || "risk_parity",
    lookback_window_months: aiNumberInput(els.aiPortfolioLookbackMonths, 12, { min: 1, max: 120 }),
    risk_model: els.aiPortfolioRiskModel?.value || "diagonal_shrinkage",
    expected_return_model: els.aiPortfolioExpectedReturn?.value || "momentum_adjusted_historical",
    asset_allocation_ranges: {
      equity: aiRangeInput(els.aiPortfolioEquityRange, [50, 75]),
      bond: aiRangeInput(els.aiPortfolioBondRange, [15, 35]),
      cash: aiRangeInput(els.aiPortfolioCashRange, [0, 15]),
      alternative: aiRangeInput(els.aiPortfolioAlternativeRange, [0, 15]),
    },
  };
}

function aiPortfolioRequest() {
  return {
    portfolio_name: String(els.aiPortfolioName?.value || "AI Portfolio").trim() || "AI Portfolio",
    investment_type: state.aiPortfolioSelectedType || "balanced_growth",
    universe_id: aiPortfolioUniverseId(),
    initial_capital: aiNumberInput(els.aiPortfolioInitialCapital, 10000000, { min: 0 }),
    monthly_contribution: aiNumberInput(els.aiPortfolioMonthlyContribution, 0, { min: 0 }),
    target_return: aiNumberInput(els.aiPortfolioTargetReturn, 0),
    benchmark: normalizeTickerToken(els.aiPortfolioBenchmark?.value || "SPY") || "SPY",
    automation_level: els.aiPortfolioAutomation?.value || "alert_only",
    policy_overrides: aiPortfolioPolicyOverrides(),
  };
}

function applyAiPortfolioTemplate(template) {
  if (!template) return;
  state.aiPortfolioSelectedType = template.id || state.aiPortfolioSelectedType;
  const ranges = template.asset_allocation_ranges || {};
  const limits = template.risk_limits || {};
  const rebalance = template.rebalance_policy || {};
  const quant = template.quant_settings || {};
  if (els.aiPortfolioTargetVolatility) els.aiPortfolioTargetVolatility.value = String(limits.target_volatility ?? 12);
  if (els.aiPortfolioMaxDrawdown) els.aiPortfolioMaxDrawdown.value = String(limits.max_drawdown_alert ?? -15);
  if (els.aiPortfolioMinCash) els.aiPortfolioMinCash.value = String(limits.min_cash_weight ?? ranges.cash?.min ?? 0);
  if (els.aiPortfolioMaxSingle) els.aiPortfolioMaxSingle.value = String(limits.max_single_asset_weight ?? 30);
  if (els.aiPortfolioMaxSector) els.aiPortfolioMaxSector.value = String(limits.max_sector_weight ?? 40);
  if (els.aiPortfolioRebalanceFrequency) els.aiPortfolioRebalanceFrequency.value = rebalance.frequency || "monthly";
  if (els.aiPortfolioDriftThreshold) els.aiPortfolioDriftThreshold.value = String(rebalance.weight_drift_threshold ?? 5);
  if (els.aiPortfolioMaxTurnover) els.aiPortfolioMaxTurnover.value = String(rebalance.max_turnover ?? 20);
  if (els.aiPortfolioOptimization) els.aiPortfolioOptimization.value = quant.optimization_method || "risk_parity";
  if (els.aiPortfolioLookbackMonths) els.aiPortfolioLookbackMonths.value = String(quant.lookback_window_months ?? 12);
  if (els.aiPortfolioRiskModel) els.aiPortfolioRiskModel.value = quant.risk_model || "diagonal_shrinkage";
  if (els.aiPortfolioExpectedReturn) els.aiPortfolioExpectedReturn.value = quant.expected_return_model || "momentum_adjusted_historical";
  if (els.aiPortfolioEquityRange && ranges.equity) els.aiPortfolioEquityRange.value = `${ranges.equity.min},${ranges.equity.max}`;
  if (els.aiPortfolioBondRange && ranges.bond) els.aiPortfolioBondRange.value = `${ranges.bond.min},${ranges.bond.max}`;
  if (els.aiPortfolioCashRange && ranges.cash) els.aiPortfolioCashRange.value = `${ranges.cash.min},${ranges.cash.max}`;
  if (els.aiPortfolioAlternativeRange && ranges.alternative) els.aiPortfolioAlternativeRange.value = `${ranges.alternative.min},${ranges.alternative.max}`;
}

function renderAiPortfolioInvestmentTypes(items) {
  if (!els.aiPortfolioInvestmentTypes) return;
  if (!items.length) {
    els.aiPortfolioInvestmentTypes.innerHTML = decisionEmpty("투자 유형 템플릿을 불러오지 못했습니다.");
    return;
  }
  els.aiPortfolioInvestmentTypes.innerHTML = items.map((item) => {
    const active = item.id === state.aiPortfolioSelectedType ? " active" : "";
    const ranges = item.asset_allocation_ranges || {};
    const summary = Object.entries(ranges).map(([key, value]) => `${key} ${value.min}-${value.max}%`).join(" · ");
    return `
      <button type="button" class="ai-investment-card${active}" data-ai-investment-type="${escapeHtml(item.id)}">
        <strong>${escapeHtml(item.display_name || item.id)}</strong>
        <span>${escapeHtml(item.risk_level || "risk")}</span>
        <small>${escapeHtml(summary)}</small>
      </button>
    `;
  }).join("");
}

async function loadAiPortfolio(force = false) {
  if (!force && state.aiPortfolioLoaded) return;
  state.aiPortfolioLoaded = true;
  if (els.aiPortfolioOverviewSurface) els.aiPortfolioOverviewSurface.innerHTML = decisionEmpty("AI Portfolio 템플릿을 불러오는 중입니다.");
  try {
    const [typesRes, universeRes] = await Promise.all([
      fetch(API.aiPortfolioInvestmentTypes),
      fetch(API.aiPortfolioUniverses),
    ]);
    const data = await typesRes.json();
    const universeData = await universeRes.json();
    if (!typesRes.ok) throw new Error(data.detail || `HTTP ${typesRes.status}`);
    if (!universeRes.ok) throw new Error(universeData.detail || `HTTP ${universeRes.status}`);
    const items = Array.isArray(data.items) ? data.items : [];
    state.aiPortfolioUniverses = Array.isArray(universeData.items) ? universeData.items : [];
    state.aiPortfolioInvestmentTypes = items;
    renderAiPortfolioInvestmentTypes(items);
    applyAiPortfolioTemplate(items.find((item) => item.id === state.aiPortfolioSelectedType) || items[0]);
    syncAiPortfolioUniverseMode();
    if (els.aiPortfolioOverviewSurface) {
      els.aiPortfolioOverviewSurface.innerHTML = `
        <div class="decision-status-row">
          <span class="decision-badge ok">ready</span>
          <span>${escapeHtml(String(items.length))}개 정책 템플릿 · ${escapeHtml(String(state.aiPortfolioUniverses.length))}개 유니버스 옵션 로드 · 브로커 주문 실행 없음</span>
        </div>
        <div class="decision-summary ok">정책, 정량 엔진, AI 설명, 리밸런싱 승인 흐름이 분리된 워크플로우입니다.</div>
      `;
    }
  } catch (err) {
    state.aiPortfolioLoaded = false;
    if (els.aiPortfolioOverviewSurface) els.aiPortfolioOverviewSurface.innerHTML = decisionEmpty(`AI Portfolio 로드 실패: ${err.message || err}`);
  }
  loadAiPortfolioOps(force);
  loadAiPortfolioPolicies(force);
}

function aiPortfolioDashboardUrl() {
  const params = new URLSearchParams({ limit: "12" });
  const policyId = aiActivePolicyId();
  if (policyId) params.set("policy_id", policyId);
  return `${API.aiPortfolioDashboard}?${params.toString()}`;
}

function aiPortfolioDashboardCacheFresh(url = aiPortfolioDashboardUrl()) {
  return !!(
    state.aiPortfolioDashboard &&
    state.aiPortfolioDashboardUrl === url &&
    Date.now() - state.aiPortfolioDashboardFetchedAt < AI_PORTFOLIO_DASHBOARD_CACHE_TTL_MS
  );
}

function clearAiPortfolioDashboardCache() {
  state.aiPortfolioOpsLoaded = false;
  state.aiPortfolioDashboard = null;
  state.aiPortfolioDashboardFetchedAt = 0;
  state.aiPortfolioDashboardUrl = "";
  state.aiPortfolioDashboardRequest = null;
  state.aiPortfolioDashboardRequestUrl = "";
  state.aiPortfolioDashboardCacheVersion += 1;
  state.aiPortfolioOperations = [];
}

async function fetchAiPortfolioDashboard(force = false) {
  const url = aiPortfolioDashboardUrl();
  if (!force && aiPortfolioDashboardCacheFresh(url)) return state.aiPortfolioDashboard;
  if (state.aiPortfolioDashboardRequest && state.aiPortfolioDashboardRequestUrl === url) {
    return state.aiPortfolioDashboardRequest;
  }
  const cacheVersion = state.aiPortfolioDashboardCacheVersion;
  state.aiPortfolioDashboardRequestUrl = url;
  const request = (async () => {
    const res = await fetch(url);
    const dashboard = await res.json();
    if (!res.ok) throw new Error(dashboard.detail || `dashboard HTTP ${res.status}`);
    if (cacheVersion !== state.aiPortfolioDashboardCacheVersion) {
      const err = new Error("AI Portfolio dashboard request was superseded");
      err.superseded = true;
      throw err;
    }
    state.aiPortfolioDashboard = dashboard;
    state.aiPortfolioDashboardUrl = url;
    state.aiPortfolioDashboardFetchedAt = Date.now();
    state.aiPortfolioOperations = dashboard.operation_summary?.recent_operations || [];
    state.aiPortfolioOpsLoaded = true;
    return dashboard;
  })();
  state.aiPortfolioDashboardRequest = request;
  try {
    return await request;
  } finally {
    if (state.aiPortfolioDashboardRequest === request) {
      state.aiPortfolioDashboardRequest = null;
      state.aiPortfolioDashboardRequestUrl = "";
    }
  }
}

function renderAiPortfolioCoverage(rows) {
  if (!els.aiPortfolioCoverageSurface) return;
  if (!Array.isArray(rows) || !rows.length) {
    els.aiPortfolioCoverageSurface.innerHTML = decisionEmpty("표시할 AI Portfolio coverage 정보가 없습니다.");
    return;
  }
  els.aiPortfolioCoverageSurface.innerHTML = `
    <div class="decision-section-title">Coverage Heatmap</div>
    <div class="ai-coverage-heatmap">
      ${rows.map((row) => {
        const pct = row.pct !== null && row.pct !== undefined ? `${fmtDecimal(row.pct, 1)}%` : "unavailable";
        const ratio = row.total_count ? `${_fmtNumber(row.available_count || 0)}/${_fmtNumber(row.total_count)}` : "";
        return `
          <div class="ai-coverage-cell ${escapeHtml(decisionStatusClass(row.status))}">
            <span>${escapeHtml(row.label || row.id || "coverage")}</span>
            <strong>${escapeHtml(pct)}</strong>
            <small>${escapeHtml(ratio || row.detail || row.status || "")}</small>
          </div>
        `;
      }).join("")}
    </div>
    <div class="decision-list compact">
      ${rows.map((row) => `
        <div class="decision-list-row">
          <span><strong>${escapeHtml(row.label || row.id)}</strong><br><small>${escapeHtml(row.detail || "")}${row.latest_at ? ` · ${escapeHtml(row.latest_at)}` : ""}</small></span>
          <strong class="${escapeHtml(decisionStatusClass(row.status))}">${escapeHtml(row.status || "unavailable")}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAiPortfolioSnapshotTimeline(items) {
  if (!els.aiPortfolioSnapshotTimelineSurface) return;
  if (!Array.isArray(items) || !items.length) {
    els.aiPortfolioSnapshotTimelineSurface.innerHTML = decisionEmpty("아직 생성된 성과 스냅샷이 없습니다. 성과 스냅샷 작업을 실행하면 timeline에 기록됩니다.");
    return;
  }
  els.aiPortfolioSnapshotTimelineSurface.innerHTML = `
    <div class="decision-section-title">Snapshot Timeline</div>
    <div class="ai-snapshot-timeline">
      ${items.slice(0, 12).map((item) => `
        <div class="ai-snapshot-point ${escapeHtml(decisionStatusClass(item.coverage_status))}">
          <span>${escapeHtml(item.date || item.created_at || "-")}</span>
          <strong>${escapeHtml(item.portfolio_value !== null && item.portfolio_value !== undefined ? _fmtNumber(item.portfolio_value) : "NAV unavailable")}</strong>
          <small>
            ${escapeHtml(item.period_return !== null && item.period_return !== undefined ? `Return ${fmtPct(item.period_return)}` : "Return unavailable")}
            · ${escapeHtml(item.price_available_pct !== null && item.price_available_pct !== undefined ? `Price ${fmtDecimal(item.price_available_pct, 1)}%` : "Price unavailable")}
          </small>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAiPortfolioOpsDashboard(dashboard) {
  if (!els.aiPortfolioOpsSurface) return;
  const aiPortfolioUi = window.FinGPTAiPortfolioUi || {};
  const store = dashboard?.store_status || {};
  const collections = store.collections || {};
  const health = dashboard?.data_health_summary || {};
  const counts = health.table_counts || {};
  const legacy = Array.isArray(store.legacy_json) ? store.legacy_json : [];
  const legacyExisting = legacy.filter((item) => item.exists);
  const selected = dashboard?.selected_policy;
  const operationSummary = dashboard?.operation_summary || {};
  const legacyRows = legacyExisting.map((item) => `
    <div class="decision-list-row">
      <span>${escapeHtml(item.collection)} · ${escapeHtml(String(item.item_count || 0))} legacy rows</span>
      <strong class="warn">seed only</strong>
    </div>
  `).join("");
  els.aiPortfolioOpsSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ok">${escapeHtml(store.primary_store || "sqlite")}</span>
      <span>${escapeHtml(selected ? `${selected.portfolio_name} · ${selected.data_quality_status}` : "선택된 정책 없음")}</span>
    </div>
    ${typeof aiPortfolioUi.dashboardMeta === "function" ? aiPortfolioUi.dashboardMeta(dashboard) : ""}
    <div class="decision-metric-grid dense">
      ${decisionMetric("정책", String(collections.policies?.item_count || dashboard?.policy_counts?.total || 0), "ok")}
      ${decisionMetric("활성 정책", String(dashboard?.policy_counts?.active || 0), dashboard?.policy_counts?.active ? "ok" : "warn")}
      ${decisionMetric("추천", String(collections.recommendations?.item_count || 0), "ok")}
      ${decisionMetric("스냅샷", String(collections.snapshots?.item_count || 0), collections.snapshots?.item_count ? "ok" : "warn")}
      ${decisionMetric("작업", String(operationSummary.total_count || collections.operations?.item_count || 0), operationSummary.total_count ? "ok" : "warn")}
      ${decisionMetric("가격 행", _fmtNumber(counts.prices_daily || 0), counts.prices_daily ? "ok" : "warn")}
      ${decisionMetric("재무 스냅샷", _fmtNumber(counts.fundamentals_snapshots || 0), counts.fundamentals_snapshots ? "ok" : "warn")}
      ${decisionMetric("SEC 팩트", _fmtNumber(counts.sec_financial_facts || 0), counts.sec_financial_facts ? "ok" : "warn")}
    </div>
    <div class="decision-summary ${legacyExisting.length ? "warn" : "ok"}">
      현재 쓰기 경로: SQLite · ${escapeHtml(store.write_path || store.db_path || "-")}
      ${legacyExisting.length ? " · legacy JSON 파일은 migration seed로만 사용됩니다." : " · legacy JSON 잔여 파일 없음"}
    </div>
    <div class="decision-section-title">Legacy JSON 상태</div>
    <div class="decision-list compact">
      ${legacyRows || '<div class="muted small">legacy JSON 파일이 감지되지 않았습니다.</div>'}
    </div>
  `;
  renderAiPortfolioCoverage(dashboard?.coverage_rows || []);
  renderAiPortfolioSnapshotTimeline(dashboard?.snapshot_timeline || []);
}

async function loadAiPortfolioOps(force = false) {
  const dashboardUrl = aiPortfolioDashboardUrl();
  if (!els.aiPortfolioOpsSurface || (!force && state.aiPortfolioOpsLoaded && aiPortfolioDashboardCacheFresh(dashboardUrl))) {
    if (state.aiPortfolioDashboard) {
      renderAiPortfolioOpsDashboard(state.aiPortfolioDashboard);
      renderAiPortfolioOperations(state.aiPortfolioOperations);
    }
    return;
  }
  if (force || !state.aiPortfolioDashboard) {
    els.aiPortfolioOpsSurface.innerHTML = decisionEmpty("AI Portfolio 운영 대시보드를 확인하는 중입니다.");
    if (els.aiPortfolioCoverageSurface) els.aiPortfolioCoverageSurface.innerHTML = decisionEmpty("데이터 coverage를 불러오는 중입니다.");
    if (els.aiPortfolioSnapshotTimelineSurface) els.aiPortfolioSnapshotTimelineSurface.innerHTML = decisionEmpty("스냅샷 timeline을 불러오는 중입니다.");
  }
  try {
    const dashboard = await fetchAiPortfolioDashboard(force);
    renderAiPortfolioOpsDashboard(dashboard);
    renderAiPortfolioOperations(state.aiPortfolioOperations);
  } catch (err) {
    if (err?.superseded) return;
    els.aiPortfolioOpsSurface.innerHTML = decisionEmpty(`운영 상태 조회 실패: ${err.message || err}`);
    if (els.aiPortfolioCoverageSurface) els.aiPortfolioCoverageSurface.innerHTML = decisionEmpty("coverage 조회 실패");
    if (els.aiPortfolioSnapshotTimelineSurface) els.aiPortfolioSnapshotTimelineSurface.innerHTML = decisionEmpty("snapshot timeline 조회 실패");
  }
}

function aiActivePolicyId() {
  return state.aiPortfolioPolicy?.policy_id || "";
}

function renderAiPortfolioPolicies(items) {
  if (!els.aiPortfolioPolicyListSurface) return;
  if (!Array.isArray(items) || !items.length) {
    els.aiPortfolioPolicyListSurface.innerHTML = decisionEmpty("저장된 AI Portfolio 정책이 없습니다.");
    return;
  }
  els.aiPortfolioPolicyListSurface.innerHTML = `
    <div class="decision-list compact">
      ${items.slice(0, 8).map((item) => `
        <div class="decision-list-row">
          <span><strong>${escapeHtml(item.portfolio_name || item.policy_id)}</strong><br><small>${escapeHtml(item.investment_type || "-")} · ${escapeHtml(item.universe_id || "-")} · ${escapeHtml(item.updated_at || item.created_at || "")}</small></span>
          <strong class="${item.status === "active" ? "ok" : "warn"}">${escapeHtml(item.status || "draft")}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAiPortfolioOperations(items) {
  if (!els.aiPortfolioOperationsSurface) return;
  if (!Array.isArray(items) || !items.length) {
    els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty("아직 실행된 운영 작업이 없습니다.");
    return;
  }
  const operationList = window.FinGPTAiPortfolioUi?.operationList?.(items);
  if (operationList) {
    els.aiPortfolioOperationsSurface.innerHTML = operationList;
    return;
  }
  els.aiPortfolioOperationsSurface.innerHTML = `
    <div class="decision-list compact">
      ${items.slice(0, 8).map((item) => `
        <div class="decision-list-row">
          <span><strong>${escapeHtml(item.operation_type || "operation")}</strong><br><small>${escapeHtml(item.created_at || "")} · ${escapeHtml(item.operation_id || "")}</small></span>
          <strong class="${escapeHtml(decisionStatusClass(item.status || "unknown"))}">${escapeHtml(item.status || "-")}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

async function loadAiPortfolioPolicies(force = false) {
  if (!els.aiPortfolioPolicyListSurface) return;
  if (!force && state.aiPortfolioPolicies.length) {
    renderAiPortfolioPolicies(state.aiPortfolioPolicies);
    return;
  }
  els.aiPortfolioPolicyListSurface.innerHTML = decisionEmpty("정책 목록을 불러오는 중입니다.");
  try {
    const res = await fetch(API.aiPortfolioPolicies);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    state.aiPortfolioPolicies = Array.isArray(data.items) ? data.items : [];
    renderAiPortfolioPolicies(state.aiPortfolioPolicies);
  } catch (err) {
    els.aiPortfolioPolicyListSurface.innerHTML = decisionEmpty(`정책 목록 로드 실패: ${err.message || err}`);
  }
}

function renderAiRecommendationDiff(diff) {
  if (!els.aiPortfolioRecommendationDiffSurface) return;
  const changes = Array.isArray(diff?.changes) ? diff.changes : [];
  if (!changes.length) {
    els.aiPortfolioRecommendationDiffSurface.innerHTML = decisionEmpty(diff?.message || "비교할 추천 변경이 없습니다.");
    return;
  }
  els.aiPortfolioRecommendationDiffSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ok">${escapeHtml(diff.status || "available")}</span>
      <span>${escapeHtml(diff.previous_recommendation_id || "")} -> ${escapeHtml(diff.latest_recommendation_id || "")}</span>
    </div>
    <div class="portfolio-weight-list">
      ${changes.slice(0, 12).map((item) => `
        <div class="portfolio-weight-row ai-diff-row">
          <span>${escapeHtml(item.ticker)}</span>
          <div><i style="width:${Math.min(100, Math.abs(Number(item.change) || 0) * 4)}%"></i></div>
          <strong>${escapeHtml(item.change > 0 ? "+" : "")}${escapeHtml(fmtPct(item.change))}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

async function loadAiRecommendationDiff(policyId = aiActivePolicyId()) {
  if (!policyId || !els.aiPortfolioRecommendationDiffSurface) return;
  els.aiPortfolioRecommendationDiffSurface.innerHTML = decisionEmpty("추천 변경분을 계산하는 중입니다.");
  try {
    const res = await fetch(API.aiPortfolioRecommendationDiff(policyId));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiRecommendationDiff(data);
  } catch (err) {
    els.aiPortfolioRecommendationDiffSurface.innerHTML = decisionEmpty(`추천 비교 실패: ${err.message || err}`);
  }
}

async function runAiPortfolioHydrateData({ missingOnly = false } = {}) {
  const actionButton = missingOnly ? els.aiPortfolioRetryMissing : els.aiPortfolioHydrateData;
  setButtonBusy(actionButton, true, missingOnly ? "재시도 중" : "보강 중");
  if (els.aiPortfolioOperationsSurface) {
    els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty("가격/재무 데이터 보강 작업을 실행하는 중입니다. 네트워크 상태에 따라 시간이 걸릴 수 있습니다.");
  }
  const quality = state.aiPortfolioRecommendation?.data_quality || {};
  const missing = [...(quality.missing_assets || []), ...(quality.insufficient_assets || [])].filter(Boolean);
  const payload = {
    hydrate_prices: true,
    hydrate_fundamentals: true,
    max_assets: 250,
    min_price_rows: 42,
  };
  if (missingOnly && missing.length) {
    payload.tickers = missing;
  } else if (aiActivePolicyId()) {
    payload.policy_id = aiActivePolicyId();
  } else {
    payload.universe_id = aiPortfolioUniverseId();
  }
  try {
    const res = await fetch(API.aiPortfolioHydrate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiPortfolioOperations([data]);
    clearAiPortfolioDashboardCache();
    loadAiPortfolioOps(true);
  } catch (err) {
    if (els.aiPortfolioOperationsSurface) els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty(`데이터 보강 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(actionButton, false);
  }
}

async function runAiPortfolioSnapshotJob() {
  setButtonBusy(els.aiPortfolioSnapshotJob, true, "스냅샷 중");
  if (els.aiPortfolioOperationsSurface) els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty("성과 스냅샷 작업을 실행하는 중입니다.");
  const payload = aiActivePolicyId() ? { policy_id: aiActivePolicyId(), active_only: false } : { active_only: true };
  try {
    const res = await fetch(API.aiPortfolioSnapshotJob, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiPortfolioOperations([data]);
    clearAiPortfolioDashboardCache();
    loadAiPortfolioOps(true);
    loadAiPortfolioHistory();
  } catch (err) {
    if (els.aiPortfolioOperationsSurface) els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty(`성과 스냅샷 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.aiPortfolioSnapshotJob, false);
  }
}

async function runAiPortfolioSecRefresh() {
  setButtonBusy(els.aiPortfolioSecRefresh, true, "SEC 갱신 중");
  if (els.aiPortfolioOperationsSurface) {
    els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty("SEC 10-K/10-Q/8-K와 companyfacts 재무 데이터를 갱신하는 중입니다.");
  }
  const payload = {
    forms: ["10-K", "10-Q", "8-K"],
    lookback_days: 1095,
    max_assets: 250,
    hydrate_financials: true,
  };
  if (aiActivePolicyId()) {
    payload.policy_id = aiActivePolicyId();
  } else {
    payload.universe_id = aiPortfolioUniverseId();
  }
  try {
    const res = await fetch(API.aiPortfolioSecRefresh, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiPortfolioOperations([data]);
    clearAiPortfolioDashboardCache();
    loadAiPortfolioOps(true);
  } catch (err) {
    if (els.aiPortfolioOperationsSurface) els.aiPortfolioOperationsSurface.innerHTML = decisionEmpty(`SEC 데이터 갱신 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.aiPortfolioSecRefresh, false);
  }
}

function aiWeightsTable(weights) {
  if (!Array.isArray(weights) || !weights.length) return decisionEmpty("표시할 추천 비중이 없습니다.");
  return `
    <div class="portfolio-weight-list">
      ${weights.map((item) => `
        <div class="portfolio-weight-row">
          <span>${escapeHtml(item.ticker)} <small>${escapeHtml(item.asset_class || "")}</small></span>
          <div><i style="width:${Math.max(2, Math.min(100, Number(item.weight) || 0))}%"></i></div>
          <strong>${escapeHtml(fmtPct(item.weight))}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAiPortfolioResult(data) {
  const policy = data.policy || {};
  const rec = data.recommendation || {};
  state.aiPortfolioPolicy = policy;
  state.aiPortfolioRecommendation = rec;
  const quality = rec.data_quality || data.data_quality || {};
  const backtest = rec.backtest_metrics || {};
  const risk = rec.risk_metrics || {};
  const check = rec.constraint_check || {};
  const warnings = [...(data.warnings || []), ...(quality.warnings || [])].filter(Boolean);
  const hydration = quality.hydration || {};
  const universeText = quality.universe_label
    ? `${quality.universe_source === "direct_input" ? "직접 입력" : "프리셋"} · ${quality.universe_label}`
    : policy.universe_id || "";
  if (els.aiPortfolioOverviewSurface) {
    els.aiPortfolioOverviewSurface.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(decisionStatusClass(rec.status || "generated"))}">${escapeHtml(rec.status || "generated")}</span>
        <span>${escapeHtml(policy.portfolio_name || "AI Portfolio")} · ${escapeHtml(policy.investment_type || "")} · ${escapeHtml(universeText)}</span>
      </div>
      <div class="decision-metric-grid dense">
        ${decisionMetric("정책 상태", policy.status || "-", "ok")}
        ${decisionMetric("자동화", policy.automation_level || "-", policy.automation_level === "auto_paper_rebalance" ? "warn" : "ok")}
        ${decisionMetric("가격 사용", `${quality.available_asset_count || 0}/${quality.asset_count || 0}`, quality.price_data_available ? "ok" : "warn")}
        ${decisionMetric("백테스트", quality.backtest_available ? "available" : "unavailable", quality.backtest_available ? "ok" : "warn")}
        ${decisionMetric("보강 상태", hydration.status || "not_checked", hydration.status === "failed" ? "warn" : "ok")}
        ${decisionMetric("섹터 메타", quality.metadata_coverage?.sector_pct !== undefined ? `${quality.metadata_coverage.sector_pct}%` : "unavailable", "ok")}
      </div>
      ${warnings.length ? `<div class="decision-warning">${escapeHtml(warnings.join("; "))}</div>` : ""}
    `;
  }
  if (els.aiPortfolioRecommendationSurface) {
    els.aiPortfolioRecommendationSurface.innerHTML = `
      ${aiWeightsTable(rec.weights || [])}
      <div class="decision-summary ${escapeHtml(check.status === "pass" ? "ok" : "warn")}">제약조건: ${escapeHtml(check.status || "unchecked")}</div>
      <div class="prose">${escapeHtml(rec.ai_explanation || "AI 설명이 없습니다.").replace(/\n/g, "<br>")}</div>
    `;
  }
  if (els.aiPortfolioPerformanceSurface) {
    els.aiPortfolioPerformanceSurface.innerHTML = `
      <div class="decision-metric-grid dense">
        ${decisionMetric("총수익률", backtest.status === "available" ? fmtPct(backtest.total_return_pct) : "unavailable", backtest.status === "available" ? "ok" : "warn")}
        ${decisionMetric("MDD", backtest.status === "available" ? fmtPct(backtest.max_drawdown_pct) : "unavailable", backtest.status === "available" ? "ok" : "warn")}
        ${decisionMetric("Sharpe", backtest.status === "available" ? fmtDecimal(backtest.sharpe, 2) : "unavailable", backtest.status === "available" ? "ok" : "warn")}
        ${decisionMetric("예상 변동성", risk.annualized_volatility_pct !== undefined ? fmtPct(risk.annualized_volatility_pct) : "unavailable", risk.annualized_volatility_pct !== undefined ? "ok" : "warn")}
      </div>
      ${backtest.reason ? `<div class="decision-warning">${escapeHtml(backtest.reason)}</div>` : ""}
    `;
  }
  if (els.aiPortfolioComplianceSurface) {
    const violations = Array.isArray(check.violations) ? check.violations : [];
    els.aiPortfolioComplianceSurface.innerHTML = `
      <div class="decision-status-row">
        <span class="decision-badge ${escapeHtml(check.status === "pass" ? "ok" : check.status === "warning" ? "warn" : "err")}">${escapeHtml(check.status || "unchecked")}</span>
        <span>${escapeHtml(String(violations.length))}개 위반/경고</span>
      </div>
      <div class="decision-metric-grid dense">
        ${Object.entries(check.allocation_by_asset_class || {}).map(([key, value]) => decisionMetric(key, fmtPct(value), "ok")).join("")}
      </div>
      <div class="decision-summary ${quality.price_data_available ? "ok" : "warn"}">
        유니버스: ${escapeHtml(universeText || "-")} · 가격 이력 사용 ${escapeHtml(String(quality.available_asset_count || 0))}/${escapeHtml(String(quality.asset_count || 0))} ·
        누락 ${escapeHtml(String((quality.missing_assets || []).length))}개 · 자동 보강 ${escapeHtml(String(hydration.status || "not_checked"))}
      </div>
      ${violations.length ? `<ul class="decision-action-list">${violations.map((item) => `<li><strong>${escapeHtml(item.rule)}</strong><span>${escapeHtml(item.message)}</span></li>`).join("")}</ul>` : decisionEmpty("정책 위반이 없습니다.")}
    `;
  }
  loadAiPortfolioHistory();
  loadAiPortfolioPolicies(true);
  loadAiRecommendationDiff(policy.policy_id);
}

async function runAiPortfolioGenerate() {
  await loadAiPortfolio(false);
  if (els.aiPortfolioOverviewSurface) els.aiPortfolioOverviewSurface.innerHTML = decisionEmpty("정책 기반 포트폴리오를 생성하는 중입니다.");
  try {
    const res = await fetch(API.aiPortfolioGenerate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aiPortfolioRequest()),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data));
    renderAiPortfolioResult(data);
    clearAiPortfolioDashboardCache();
    loadAiPortfolioOps(true);
  } catch (err) {
    if (els.aiPortfolioOverviewSurface) els.aiPortfolioOverviewSurface.innerHTML = decisionEmpty(`AI Portfolio 생성 실패: ${err.message || err}`);
  }
}

function parseAiCurrentWeights(raw) {
  const text = String(raw || "").trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
  } catch (_) {
    // Continue with loose "SPY 40, TLT 30" parsing.
  }
  const out = {};
  text.split(/[,\n]+/).forEach((part) => {
    const match = part.trim().match(/^([A-Za-z0-9.\-]+)\s*[:= ]\s*(-?\d+(?:\.\d+)?)$/);
    if (match) out[normalizeTickerToken(match[1])] = Number(match[2]);
  });
  return out;
}

function setAiRebalanceButtons(enabled) {
  [els.aiPortfolioApproveRebalance, els.aiPortfolioRejectRebalance, els.aiPortfolioDeferRebalance].forEach((button) => {
    if (button) button.disabled = !enabled;
  });
}

function renderAiPortfolioSignal(signal) {
  state.aiPortfolioSignal = signal;
  setAiRebalanceButtons(Boolean(signal?.signal_id));
  if (!els.aiPortfolioRebalanceSurface) return;
  const changes = Array.isArray(signal?.recommended_changes) ? signal.recommended_changes : [];
  els.aiPortfolioRebalanceSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${signal?.rebalance_required ? "warn" : "ok"}">${signal?.rebalance_required ? "approval_required" : "no_action"}</span>
      <span>${escapeHtml((signal?.trigger_type || []).join(", ") || "no trigger")}</span>
    </div>
    <div class="decision-metric-grid dense">
      ${decisionMetric("상태", signal?.status || "-", signal?.rebalance_required ? "warn" : "ok")}
      ${decisionMetric("변경 수", String(changes.length), changes.length ? "warn" : "ok")}
      ${decisionMetric("예상 회전율", signal?.turnover_estimate !== undefined && signal?.turnover_estimate !== null ? fmtPct(signal.turnover_estimate) : "unavailable", changes.length ? "warn" : "ok")}
      ${decisionMetric("만료", signal?.expires_at || "not required", signal?.expires_at ? "warn" : "ok")}
      ${decisionMetric("다음 점검", signal?.next_review_at || "-", "ok")}
      ${decisionMetric("브로커 실행", signal?.estimated_risk_after?.broker_execution || "not_supported", "warn")}
    </div>
    ${changes.length ? `<ul class="decision-action-list">${changes.map((item) => `<li><strong>${escapeHtml(item.ticker)}</strong><span>${escapeHtml(fmtPct(item.current_weight))} -> ${escapeHtml(fmtPct(item.target_weight))} · ${escapeHtml(item.change > 0 ? "+" : "")}${escapeHtml(fmtPct(item.change))} (${escapeHtml(item.action)})</span></li>`).join("")}</ul>` : decisionEmpty("리밸런싱 변경이 필요하지 않습니다.")}
    ${signal?.decision_reason ? `<div class="decision-summary ok">사용자 조치 사유: ${escapeHtml(signal.decision_reason)}</div>` : ""}
    <div class="prose">${escapeHtml(signal?.ai_explanation || "").replace(/\n/g, "<br>")}</div>
  `;
}

async function runAiPortfolioRebalanceCheck() {
  if (!state.aiPortfolioPolicy?.policy_id) {
    await runAiPortfolioGenerate();
  }
  const policyId = state.aiPortfolioPolicy?.policy_id;
  if (!policyId) return;
  if (els.aiPortfolioRebalanceSurface) els.aiPortfolioRebalanceSurface.innerHTML = decisionEmpty("리밸런싱 룰을 점검하는 중입니다.");
  try {
    const res = await fetch(API.aiPortfolioRebalanceCheck, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        policy_id: policyId,
        current_weights: parseAiCurrentWeights(els.aiPortfolioCurrentWeights?.value || ""),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiPortfolioSignal(data.signal || data);
    loadAiPortfolioHistory();
  } catch (err) {
    if (els.aiPortfolioRebalanceSurface) els.aiPortfolioRebalanceSurface.innerHTML = decisionEmpty(`리밸런싱 점검 실패: ${err.message || err}`);
  }
}

async function updateAiPortfolioSignal(action) {
  const signalId = state.aiPortfolioSignal?.signal_id;
  if (!signalId) return;
  try {
    const res = await fetch(API.aiPortfolioRebalanceAction(signalId, action), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: `UI ${action}`, actor: "user" }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    renderAiPortfolioSignal(data);
    loadAiPortfolioHistory();
  } catch (err) {
    if (els.aiPortfolioRebalanceSurface) els.aiPortfolioRebalanceSurface.innerHTML += `<div class="decision-warning">신호 업데이트 실패: ${escapeHtml(err.message || err)}</div>`;
  }
}

async function generateAiPortfolioReport(reportType = "weekly") {
  if (!state.aiPortfolioPolicy?.policy_id) {
    await runAiPortfolioGenerate();
  }
  const policyId = state.aiPortfolioPolicy?.policy_id;
  if (!policyId) return;
  if (els.aiPortfolioReportsSurface) els.aiPortfolioReportsSurface.innerHTML = decisionEmpty("리포트를 생성하는 중입니다.");
  try {
    const res = await fetch(API.aiPortfolioReportsGenerate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policy_id: policyId, report_type: reportType }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    if (els.aiPortfolioReportsSurface) {
      els.aiPortfolioReportsSurface.innerHTML = `<pre class="report-md">${escapeHtml(data.content || data.markdown || "")}</pre>`;
    }
    loadAiPortfolioHistory();
  } catch (err) {
    if (els.aiPortfolioReportsSurface) els.aiPortfolioReportsSurface.innerHTML = decisionEmpty(`리포트 생성 실패: ${err.message || err}`);
  }
}

async function loadAiPortfolioHistory() {
  const policyId = state.aiPortfolioPolicy?.policy_id;
  if (!policyId || !els.aiPortfolioHistorySurface) return;
  try {
    const res = await fetch(API.aiPortfolioHistory(policyId));
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    const items = Array.isArray(data.items) ? data.items.slice(0, 12) : [];
    els.aiPortfolioHistorySurface.innerHTML = items.length ? `
      <ul class="decision-action-list">
        ${items.map((item) => `<li><strong>${escapeHtml(item.event_type || "event")}</strong><span>${escapeHtml(item.summary || "")}<br><small>${escapeHtml(item.event_time || "")}</small></span></li>`).join("")}
      </ul>
    ` : decisionEmpty("아직 기록된 이력이 없습니다.");
  } catch (err) {
    els.aiPortfolioHistorySurface.innerHTML = decisionEmpty(`이력 로드 실패: ${err.message || err}`);
  }
}

const NEWS_CATEGORY_LABELS = {
  all: "전체",
  equity_index: "주식/지수",
  rates_credit: "금리/신용",
  macro_policy: "매크로",
  ai_semis: "AI/반도체",
  earnings: "실적",
  commodity: "원자재",
  crypto: "크립토",
  company_news: "회사 뉴스",
  topic_news: "주제 뉴스",
  market: "기타",
};

function renderNewsCategories(items) {
  if (!els.homeNewsCategories) return;
  const counts = items.reduce((acc, item) => {
    const key = item.category || "market";
    acc[key] = (acc[key] || 0) + 1;
    acc.all = (acc.all || 0) + 1;
    return acc;
  }, {});
  const order = ["all", "equity_index", "macro_policy", "rates_credit", "ai_semis", "earnings", "commodity", "crypto", "market"];
  if (!counts[state.dashboardNewsCategory]) state.dashboardNewsCategory = "all";
  els.homeNewsCategories.innerHTML = order
    .filter((key) => counts[key])
    .map((key) => `
      <button type="button" class="news-category-chip ${state.dashboardNewsCategory === key ? "active" : ""}" data-category="${escapeHtml(key)}">
        ${escapeHtml(NEWS_CATEGORY_LABELS[key] || key)} <span>${counts[key]}</span>
      </button>
    `).join("");
  els.homeNewsCategories.querySelectorAll(".news-category-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.dashboardNewsCategory = btn.dataset.category || "all";
      renderDashboardNews();
    });
  });
}

function renderDashboardNews() {
  if (!els.homeNewsList) return;
  const category = state.dashboardNewsCategory || "all";
  const items = category === "all"
    ? state.dashboardNewsItems
    : state.dashboardNewsItems.filter((item) => (item.category || "market") === category);
  renderNewsCategories(state.dashboardNewsItems);
  if (!items.length) {
    els.homeNewsList.innerHTML = '<div class="home-news-empty">선택한 카테고리에 표시할 뉴스가 없습니다.</div>';
    return;
  }
  els.homeNewsList.innerHTML = items.slice(0, 20).map((item) => {
    const date = item.published_at ? fmtDate(item.published_at) : (item.collected_at ? fmtDate(item.collected_at) : "");
    const href = item.url ? `href="${escapeHtml(item.url)}" target="_blank" rel="noopener"` : "";
    const categoryLabel = NEWS_CATEGORY_LABELS[item.category || "market"] || item.category || "기타";
    const sourceTier = Number(item.source_tier);
    const sourceClass = sourceTier === 0 ? "major" : (sourceTier >= 3 ? "low" : "");
    return `
      <article class="home-news-card">
        <div class="home-news-meta">
          <span>${escapeHtml(categoryLabel)}</span>
          <span>${escapeHtml(item.symbol || "MARKET")}</span>
          <span class="news-source ${sourceClass}">${escapeHtml(item.source || "")}</span>
          <span>${escapeHtml(date)}</span>
        </div>
        <a ${href} class="home-news-title">${escapeHtml(item.title || "Untitled")}</a>
      </article>
    `;
  }).join("");
}

function newsSearchRequestFromControls() {
  return {
    ticker: normalizeTickerToken(els.homeNewsTicker?.value || ""),
    topic: textInputValue(els.homeNewsTopic) || "",
  };
}

function renderFocusedNews(items, meta = {}) {
  if (!els.homeNewsFocusedList) return;
  const clean = Array.isArray(items) ? items : [];
  if (!clean.length) {
    els.homeNewsFocusedList.innerHTML = '<div class="home-news-empty">입력한 티커/주제에 대한 뉴스가 없습니다. 검색어를 조금 넓혀서 다시 시도하세요.</div>';
    return;
  }
  const focused = clean.filter((item) => ["company_news", "topic_news"].includes(item.category || ""));
  const seen = new Set(focused.map((item) => item.url || item.title || JSON.stringify(item)));
  const display = [
    ...focused,
    ...clean.filter((item) => !seen.has(item.url || item.title || JSON.stringify(item))),
  ].slice(0, 10);
  els.homeNewsFocusedList.innerHTML = `
    <div class="focused-news-head">
      <strong>${escapeHtml(meta.ticker || meta.topic || "맞춤 뉴스")}</strong>
      <span>${escapeHtml(meta.selection_policy || "focused query")} · ${escapeHtml(fmtDate(meta.generated_at) || "")}</span>
    </div>
    ${display.map((item) => {
      const date = item.published_at ? fmtDate(item.published_at) : (item.collected_at ? fmtDate(item.collected_at) : "");
      const href = item.url ? `href="${escapeHtml(item.url)}" target="_blank" rel="noopener"` : "";
      const categoryLabel = NEWS_CATEGORY_LABELS[item.category || "market"] || item.category || "기타";
      const sourceTier = Number(item.source_tier);
      const sourceClass = sourceTier === 0 ? "major" : (sourceTier >= 3 ? "low" : "");
      return `
        <article class="home-news-card focused">
          <div class="home-news-meta">
            <span>${escapeHtml(categoryLabel)}</span>
            <span>${escapeHtml(item.symbol || "")}</span>
            <span class="news-source ${sourceClass}">${escapeHtml(item.source || "")}</span>
            <span>${escapeHtml(date)}</span>
          </div>
          <a ${href} class="home-news-title">${escapeHtml(item.title || "Untitled")}</a>
          ${item.summary ? `<p class="home-news-summary">${escapeHtml(String(item.summary).slice(0, 180))}</p>` : ""}
        </article>
      `;
    }).join("")}
  `;
}

async function loadFocusedDashboardNews(force = false) {
  if (!els.homeNewsFocusedList) return;
  const request = newsSearchRequestFromControls();
  if (!request.ticker && !request.topic) {
    if (force) {
      els.homeNewsFocusedList.innerHTML = '<div class="home-news-empty">티커나 주제를 입력하면 관련 회사/주제 뉴스가 현재 주요 뉴스 위에 추가됩니다.</div>';
    }
    return;
  }
  if (els.homeNewsSearchStatus) els.homeNewsSearchStatus.textContent = "맞춤 뉴스를 불러오는 중입니다.";
  if (els.homeNewsSearchRun) els.homeNewsSearchRun.disabled = true;
  els.homeNewsFocusedList.innerHTML = '<div class="home-news-empty">회사/주제 뉴스를 불러오는 중입니다.</div>';
  try {
    const res = await fetch(API.dashboardNews({ limit: 18, ticker: request.ticker, topic: request.topic, query: request.topic }));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    state.focusedNewsItems = items;
    renderFocusedNews(items, data);
    if (els.homeNewsSearchStatus) els.homeNewsSearchStatus.textContent = `${_fmtNumber(items.length)}개 뉴스 · ${fmtDate(data.generated_at)}`;
  } catch (err) {
    state.focusedNewsItems = [];
    els.homeNewsFocusedList.innerHTML = `<div class="home-news-empty">맞춤 뉴스 로드 실패: ${escapeHtml(err.message || err)}</div>`;
    if (els.homeNewsSearchStatus) els.homeNewsSearchStatus.textContent = "맞춤 뉴스 로드 실패";
  } finally {
    if (els.homeNewsSearchRun) els.homeNewsSearchRun.disabled = false;
  }
}

async function loadDashboardNews(force = false) {
  if (!els.homeNewsList || (state.dashboardLoaded && !force)) return;
  els.homeNewsList.innerHTML = '<div class="home-news-empty">뉴스를 불러오는 중입니다.</div>';
  try {
    const res = await fetch(API.dashboardNews({ limit: 20 }));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) {
      els.homeNewsList.innerHTML = '<div class="home-news-empty">표시할 최신 뉴스가 없습니다.</div>';
      state.dashboardNewsItems = [];
      renderNewsCategories([]);
      state.dashboardLoaded = true;
      return;
    }
    state.dashboardNewsItems = items;
    renderDashboardNews();
    state.dashboardLoaded = true;
  } catch (err) {
    els.homeNewsList.innerHTML = `<div class="home-news-empty">뉴스 로드 실패: ${escapeHtml(err.message || err)}</div>`;
  }
}

function loadMarketDashboard(force = false) {
  initializeTradingViewDashboard(force);
  loadDashboardMarketOverview(force);
  Promise.allSettled([
    loadDashboardEquityHeatmap(force),
    loadDashboardMarket(force),
    loadDataHealth(force),
    loadDashboardNews(force),
    loadCrossAssetAnalysis(force),
  ]).then(() => loadDashboardMarketOverview(true));
}

function forecastDatasetConfigFromControls() {
  return {
    ticker: normalizeTickerToken(els.forecastTicker?.value || "MSFT") || "MSFT",
    benchmark: normalizeTickerToken(els.forecastBenchmark?.value || "QQQ") || "QQQ",
    start_date: els.forecastStartDate?.value || null,
    end_date: els.forecastEndDate?.value || null,
    frequency: "1d",
    include_macro: !!els.forecastIncludeMacro?.checked,
    include_cross_asset: !!els.forecastIncludeCrossAsset?.checked,
    include_technical: true,
    data_source: "data_mart:prices_daily",
    adjusted_price: true,
  };
}

function forecastRunRequestFromControls() {
  const horizon = numberInputValue(els.forecastHorizon, 5, { min: 1, max: 252 });
  const targetType = els.forecastTargetType?.value || "forward_return";
  const featureGroups = ["returns", "momentum", "volatility", "trend", "mean_reversion", "volume"];
  if (els.forecastIncludeCrossAsset?.checked) featureGroups.push("cross_asset");
  if (els.forecastIncludeMacro?.checked) featureGroups.push("macro");
  return {
    dataset_config: forecastDatasetConfigFromControls(),
    feature_config: {
      feature_groups: featureGroups,
      selected_features: [],
      rolling_windows: [5, 20, 60, 200],
      feature_shift: 1,
      missing_value_policy: "drop",
    },
    target_config: {
      target_type: targetType,
      horizon,
      threshold: 0,
      benchmark: normalizeTickerToken(els.forecastBenchmark?.value || "QQQ") || "QQQ",
    },
    validation_config: {
      validation_method: els.forecastValidation?.value || "walk_forward",
      train_window: "3y",
      validation_window: "6m",
      test_window: "6m",
      step_size: "1m",
      purge_window: "auto",
      embargo_window: 5,
      expanding: true,
      shuffle: false,
      random_state: 42,
    },
    model_config: {
      model_type: targetType === "direction" ? "classification" : "regression",
      model_name: els.forecastModel?.value || "ridge_regression",
      hyperparameters: {},
      scaling: true,
      feature_selection: "none",
      hyperparameter_search: false,
      seed: 42,
    },
    signal_config: {
      signal_method: "threshold_confidence",
      bullish_threshold: 0.01,
      bearish_threshold: -0.01,
      strong_bullish_threshold: 0.03,
      strong_bearish_threshold: -0.03,
      probability_threshold: 0.55,
      confidence_threshold: 0.55,
      volatility_filter_enabled: true,
      max_forecast_volatility: 0.40,
      trend_filter_enabled: true,
      regime_filter_enabled: true,
      smoothing_window: 1,
      cooldown_period: 0,
      max_position_size: 1.0,
      long_only: true,
      allow_short: false,
    },
    backtest_config: {
      strategy_type: "long_cash",
      signal_threshold: 0,
      long_only: true,
      allow_short: false,
      max_position_size: 1.0,
      rebalance_frequency: "daily",
      commission_bps: 5,
      slippage_bps: 2,
      spread_bps: 0,
      benchmark: normalizeTickerToken(els.forecastBenchmark?.value || "QQQ") || "QQQ",
      initial_capital: 1.0,
      execution_delay_bars: 1,
    },
    visualization_config: {
      show_forecast_cone: true,
      show_signal_overlay: true,
      show_actual_vs_predicted: true,
      show_residuals: true,
      show_feature_importance: true,
      show_equity_curve: true,
      show_drawdown: true,
      show_rolling_sharpe: true,
      show_signal_history: true,
      show_position_exposure: true,
      show_model_comparison: true,
    },
  };
}

async function forecastFetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail || data.error || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function loadForecastLab(force = false) {
  if (!force && state.forecastLoaded) return;
  state.forecastLoaded = true;
  await Promise.allSettled([
    loadForecastModels(force),
    loadForecastAiProviderStatus(force),
    loadForecastDrift(force),
    loadForecastModelComparison(force),
    loadForecastJobs(force),
    loadForecastHistory(force),
    loadForecastRegistry(force),
  ]);
}

async function loadForecastModels(force = false) {
  if (!els.forecastModel || (!force && state.forecastModelsLoaded)) return;
  try {
    const data = await forecastFetchJson(API.forecastModels);
    state.forecastModels = data.models || [];
    state.forecastModelsLoaded = true;
    const preferred = els.forecastModel.value || "ridge_regression";
    els.forecastModel.innerHTML = state.forecastModels.map((item) => {
      const disabled = item.available ? "" : " disabled";
      const suffix = item.available ? "" : " (unavailable)";
      return `<option value="${escapeHtml(item.model_name)}"${disabled}>${escapeHtml(item.model_name + suffix)}</option>`;
    }).join("");
    if ([...els.forecastModel.options].some((option) => option.value === preferred && !option.disabled)) {
      els.forecastModel.value = preferred;
    }
  } catch (err) {
    if (els.forecastRegistrySurface) els.forecastRegistrySurface.innerHTML = decisionEmpty(`모델 목록 로드 실패: ${err.message || err}`);
  }
}

async function runForecastDatasetPreview() {
  if (!els.forecastDatasetSurface) return;
  setButtonBusy(els.forecastPreviewDataset, true, "로딩 중");
  els.forecastDatasetSurface.innerHTML = decisionEmpty("데이터셋을 확인하는 중입니다.");
  try {
    const data = await forecastFetchJson(API.forecastDatasetPreview, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_config: forecastDatasetConfigFromControls() }),
    });
    renderForecastDataset(data);
  } catch (err) {
    els.forecastDatasetSurface.innerHTML = decisionEmpty(`데이터셋 미리보기 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastPreviewDataset, false);
  }
}

async function runForecastDatasetHydrate() {
  if (!els.forecastDatasetSurface) return;
  setButtonBusy(els.forecastHydrateDataset, true, "저장 중");
  els.forecastDatasetSurface.innerHTML = decisionEmpty("가격/매크로 데이터를 찾아 data mart에 저장하는 중입니다.");
  try {
    const data = await forecastFetchJson(API.forecastDatasetHydrate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_config: forecastDatasetConfigFromControls(),
        include_benchmark: true,
        include_macro: !!els.forecastIncludeMacro?.checked,
      }),
    });
    renderForecastDatasetHydration(data);
    if (data.dataset_preview) renderForecastDataset(data.dataset_preview);
    await loadDataHealth(true);
  } catch (err) {
    els.forecastDatasetSurface.innerHTML = decisionEmpty(`데이터 저장 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastHydrateDataset, false);
  }
}

async function runForecastFeatureAndLeakagePreview() {
  setButtonBusy(els.forecastBuildFeatures, true, "점검 중");
  if (els.forecastFeatureSurface) els.forecastFeatureSurface.innerHTML = decisionEmpty("feature와 leakage check를 계산하는 중입니다.");
  try {
    const request = forecastRunRequestFromControls();
    const [featureData, leakageData] = await Promise.all([
      forecastFetchJson(API.forecastFeaturesBuild, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_config: request.dataset_config, feature_config: request.feature_config }),
      }),
      forecastFetchJson(API.forecastLeakageCheck, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }),
    ]);
    renderForecastFeatures(featureData);
    renderForecastLeakage(leakageData.leakage_check || leakageData);
  } catch (err) {
    if (els.forecastFeatureSurface) els.forecastFeatureSurface.innerHTML = decisionEmpty(`feature/leakage 점검 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastBuildFeatures, false);
  }
}

async function runForecastExperiment() {
  const startedAt = Date.now();
  setButtonBusy(els.forecastRunTrain, true, "실험 중");
  forecastSetAllSurfacesLoading("ML Forecast 실험을 실행하는 중입니다. Walk-forward OOS 예측, 신호, 비용 반영 백테스트를 같은 요청에서 계산합니다.");
  try {
    const payload = await forecastFetchJson(API.forecastTrain, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(forecastRunRequestFromControls()),
    });
    state.lastForecastPayload = payload;
    renderForecastPayload(payload, startedAt);
    await Promise.allSettled([loadForecastHistory(true), loadForecastRegistry(true)]);
  } catch (err) {
    if (els.forecastResultSurface) els.forecastResultSurface.innerHTML = decisionEmpty(`ML Forecast 실행 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastRunTrain, false);
  }
}

async function runForecastQueuedJob() {
  setButtonBusy(els.forecastQueueJob, true, "제출 중");
  if (els.forecastJobsSurface) els.forecastJobsSurface.innerHTML = decisionEmpty("Forecast job을 제출하는 중입니다.");
  try {
    const request = forecastRunRequestFromControls();
    const data = await forecastFetchJson(API.forecastJobs, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request,
        runtime_budget_s: forecastRuntimeBudgetSeconds(request),
        notes: "ui_async_forecast_job",
      }),
    });
    renderForecastJobs([data]);
    scheduleForecastJobPoll(data.job_id);
    await loadForecastJobs(true);
  } catch (err) {
    if (els.forecastJobsSurface) els.forecastJobsSurface.innerHTML = decisionEmpty(`Forecast job 제출 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastQueueJob, false);
  }
}

function forecastRuntimeBudgetSeconds(request) {
  const model = String(request?.model_config?.model_name || "");
  if (["lstm", "gru", "temporal_cnn", "transformer", "temporal_fusion_transformer"].includes(model)) return 1800;
  if (["xgboost", "lightgbm"].includes(model)) return 1200;
  return 600;
}

function forecastSetAllSurfacesLoading(message) {
  [
    els.forecastLeakageSurface,
    els.forecastResultSurface,
    els.forecastSignalSurface,
    els.forecastSignalQualitySurface,
    els.forecastVizSurface,
    els.forecastBacktestSurface,
    els.forecastEvaluationSurface,
    els.forecastExplainSurface,
    els.forecastAiSurface,
  ].forEach((surface) => {
    if (surface) surface.innerHTML = decisionEmpty(message);
  });
}

function renderForecastPayload(payload, startedAt = Date.now()) {
  renderForecastDataset({ ...(payload.dataset_preview || {}), data_snapshot: payload.data_snapshot || payload.dataset_preview?.data_snapshot || {} });
  renderForecastFeatures(payload.feature_payload || {});
  renderForecastLeakage(payload.leakage_check || {});
  renderForecastResult(payload.forecast_result || {}, startedAt);
  renderForecastSignal(payload.signal_result || {});
  renderForecastSignalQuality(payload.signal_quality || {});
  renderForecastVisualization(payload.visualization || {});
  renderForecastBacktest(payload.backtest_result || {});
  renderForecastEvaluation(payload.model_evaluation || {});
  renderForecastExplainability(payload.explainability || {});
  renderForecastAi(payload.ai_interpretation || {});
}

function renderForecastDataset(data) {
  if (!els.forecastDatasetSurface) return;
  const quality = data.data_quality || {};
  const snapshot = data.data_snapshot || {};
  const priceCoverage = snapshot.price_coverage || {};
  const benchmarkCoverage = snapshot.benchmark_coverage || {};
  const macroCoverage = snapshot.macro_coverage || {};
  els.forecastDatasetSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("상태", quality.status || data.status || "unknown", decisionStatusClass(quality.status || data.status))}
      ${decisionMetric("가격 행", _fmtNumber(data.rows || quality.rows || 0), (data.rows || quality.rows) ? "ok" : "warn")}
      ${decisionMetric("기간", `${quality.start_date || "-"} ~ ${quality.end_date || "-"}`, "ok")}
      ${decisionMetric("결측률", fmtPercent(quality.missing_ratio || 0), (quality.missing_ratio || 0) > 0.1 ? "warn" : "ok")}
      ${decisionMetric("수정가격", quality.adjusted_price_status || "unknown", decisionStatusClass(quality.adjusted_price_status))}
      ${decisionMetric("벤치마크", quality.benchmark_availability || "unknown", decisionStatusClass(quality.benchmark_availability))}
    </div>
    ${snapshot.data_snapshot_id ? `
      <div class="decision-surface compact-surface">
        <div class="decision-mini-row">
          <span>Data Snapshot: ${escapeHtml(snapshot.data_snapshot_id)}</span>
          <span>Coverage hash: ${escapeHtml((snapshot.source_coverage_hash || "").slice(0, 16))}</span>
        </div>
        <div class="decision-mini-row">
          <span>Price ${escapeHtml(String(priceCoverage.rows || 0))} rows · ${escapeHtml(priceCoverage.coverage_hash || "")}</span>
          <span>Benchmark ${escapeHtml(String(benchmarkCoverage.rows || 0))} rows · Macro ${escapeHtml(macroCoverage.status || "not_requested")}</span>
        </div>
      </div>
    ` : ""}
    ${(quality.warnings || data.warnings || []).length ? `<div class="decision-warning">${escapeHtml((quality.warnings || data.warnings).join(", "))}</div>` : ""}
  `;
}

function renderForecastDatasetHydration(data) {
  if (!els.forecastDatasetSurface) return;
  const price = data.price_update || {};
  const macro = data.macro_update || {};
  const preview = data.dataset_preview || {};
  els.forecastDatasetSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Hydration", data.status || "unknown", data.status === "success" ? "ok" : "warn")}
      ${decisionMetric("Tickers", (data.tickers || []).join(", "), "ok")}
      ${decisionMetric("Price rows", _fmtNumber((price.rows_inserted || 0) + (price.rows_updated || 0)), "ok")}
      ${decisionMetric("Macro rows", macro ? _fmtNumber((macro.rows_inserted || 0) + (macro.rows_updated || 0)) : "N/A", macro ? "ok" : "warn")}
      ${decisionMetric("Available rows", _fmtNumber(preview.rows || 0), (preview.rows || 0) >= 120 ? "ok" : "warn")}
    </div>
  `;
}

function renderForecastFeatures(data) {
  if (!els.forecastFeatureSurface) return;
  const summary = data.summary || {};
  const missing = summary.missing_by_feature || {};
  const topMissing = Object.entries(missing).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 8);
  els.forecastFeatureSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Feature 수", _fmtNumber(summary.feature_count || 0), summary.feature_count ? "ok" : "warn")}
      ${decisionMetric("행 수", _fmtNumber(summary.row_count || 0), summary.row_count ? "ok" : "warn")}
      ${decisionMetric("Feature shift", `${summary.feature_shift ?? 1}봉`, Number(summary.feature_shift ?? 1) >= 1 ? "ok" : "fail")}
      ${decisionMetric("평균 결측률", fmtPercent(summary.missing_ratio || 0), (summary.missing_ratio || 0) > 0.5 ? "warn" : "ok")}
    </div>
    <div class="decision-chip-row">${(summary.feature_groups || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
    ${topMissing.length ? `<div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Feature</th><th>Missing</th></tr></thead><tbody>${topMissing.map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(fmtPercent(value))}</td></tr>`).join("")}</tbody></table></div>` : ""}
  `;
}

function renderForecastLeakage(check) {
  if (!els.forecastLeakageSurface) return;
  const status = check.status || "warning";
  els.forecastLeakageSurface.innerHTML = `
    <div class="decision-status-row">
      <span class="decision-badge ${escapeHtml(decisionStatusClass(status))}">Leakage ${escapeHtml(status)}</span>
      <span>${escapeHtml(check.checked_at || "not checked")}</span>
    </div>
    ${(check.issues || []).length ? `<div class="decision-warning">${escapeHtml(check.issues.join(", "))}</div>` : `<div class="decision-summary ok">random split, shuffle, target contamination, purge/embargo, 1-bar delay 조건이 통과했습니다.</div>`}
    ${(check.recommendations || []).length ? `<ul class="forecast-note-list">${check.recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
  `;
}

function renderForecastResult(result, startedAt) {
  if (!els.forecastResultSurface) return;
  const confidence = result.model_confidence || {};
  const predictionType = result.prediction_type || "forward_return";
  const labelTarget = ["direction", "triple_barrier_label", "quantile_return"].includes(predictionType);
  const intervalAvailable = result.p10 !== null && result.p10 !== undefined && result.p50 !== null && result.p50 !== undefined && result.p90 !== null && result.p90 !== undefined;
  const expectedLabel = labelTarget ? "Expected return (OOS calibrated)" : predictionType === "volatility" ? "Expected return" : "Expected return";
  els.forecastResultSurface.innerHTML = `
    ${renderActionCompletion("ML Forecast 결과", startedAt, result.experiment_id || "")}
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Target", predictionType, "ok")}
      ${decisionMetric(expectedLabel, fmtPercent(result.expected_return), result.expected_return === null || result.expected_return === undefined ? "warn" : "ok")}
      ${decisionMetric("Probability up", fmtPercent(result.probability_up), result.probability_up >= 0.55 ? "ok" : "warn")}
      ${decisionMetric("P10/P50/P90", intervalAvailable ? `${fmtPercent(result.p10)} / ${fmtPercent(result.p50)} / ${fmtPercent(result.p90)}` : "unavailable", intervalAvailable ? "ok" : "warn")}
      ${decisionMetric("Forecast vol", fmtPercent(result.forecast_volatility), result.forecast_volatility > 0.4 ? "warn" : "ok")}
      ${decisionMetric("Confidence", `${fmtDecimal(confidence.score, 3)} ${confidence.level || ""}`, confidence.score >= 0.6 ? "ok" : "warn")}
      ${decisionMetric("Model", result.model_id || "unavailable", result.model_id ? "ok" : "warn")}
    </div>
    ${labelTarget ? `<div class="decision-summary ok">라벨/분류 타깃의 expected return은 라벨 값을 수익률로 표시하지 않고, OOS 예측 확률과 과거 forward return 조건부 평균으로 보정한 값입니다.</div>` : ""}
    ${(result.warnings || []).length ? `<div class="decision-warning">${escapeHtml(result.warnings.join(", "))}</div>` : ""}
  `;
}

function renderForecastSignal(signal) {
  if (!els.forecastSignalSurface) return;
  els.forecastSignalSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Signal", signal.signal || "unavailable", signal.signal === "unavailable" ? "warn" : "ok")}
      ${decisionMetric("Score", fmtDecimal(signal.signal_score, 3), "ok")}
      ${decisionMetric("Position", fmtPercent(signal.position_target), signal.position_target ? "ok" : "warn")}
      ${decisionMetric("Advisory", signal.advisory_only ? "only" : "unknown", signal.advisory_only ? "ok" : "fail")}
    </div>
    <div class="decision-chip-row">${(signal.reason_codes || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
    ${(signal.warnings || []).length ? `<div class="decision-warning">${escapeHtml(signal.warnings.join(", "))}</div>` : ""}
  `;
}

function renderForecastSignalQuality(quality) {
  if (!els.forecastSignalQualitySurface) return;
  els.forecastSignalQualitySurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("신호 수", _fmtNumber(quality.signal_count || 0), quality.signal_count ? "ok" : "warn")}
      ${decisionMetric("Hit rate", fmtPercent(quality.hit_rate), quality.hit_rate >= 0.5 ? "ok" : "warn")}
      ${decisionMetric("Bullish 후 평균", fmtPercent(quality.average_forward_return_after_bullish), "ok")}
      ${decisionMetric("Bearish 후 평균", fmtPercent(quality.average_forward_return_after_bearish), "ok")}
      ${decisionMetric("False positive", fmtPercent(quality.false_positive_rate), quality.false_positive_rate > 0.5 ? "warn" : "ok")}
      ${decisionMetric("Turnover", fmtDecimal(quality.turnover, 3), quality.turnover > 5 ? "warn" : "ok")}
    </div>
  `;
}

function renderForecastVisualization(viz) {
  if (!els.forecastVizSurface) return;
  els.forecastVizSurface.innerHTML = `
    <div class="forecast-chart-grid">
      ${renderForecastLineChart("Price & Signal", viz.price_series || [], "price")}
      ${renderForecastIntervalChart(viz.prediction_intervals || [])}
      ${renderForecastActualPredicted(viz.actual_vs_predicted || [])}
      ${renderForecastResidualChart(viz.residuals || [])}
      ${renderForecastDistribution(viz.prediction_distribution || [])}
      ${renderForecastLineChart("Equity Curve", viz.equity_curve || [], "equity", viz.benchmark_curve || [])}
      ${renderForecastLineChart("Drawdown", viz.drawdown_series || [], "drawdown")}
      ${renderForecastLineChart("Rolling Sharpe", viz.rolling_sharpe || [], "rolling_sharpe")}
      ${renderForecastLineChart("Position Exposure", viz.position_exposure || [], "position")}
      ${renderForecastLineChart("Turnover", viz.turnover || [], "turnover")}
      ${renderForecastMonthlyHeatmap(viz.monthly_return_heatmap || [])}
      ${renderForecastConfusionMatrix(viz.confusion_matrix || {})}
      ${renderForecastRegimePerformance(viz.regime_performance || [])}
      ${renderForecastFeatureImportance(viz.feature_importance || [])}
      ${renderForecastFeatureImportance(viz.permutation_importance || [], "Permutation Importance", "normalized_importance")}
      ${renderForecastFeatureImportance(viz.shap_importance || [], "SHAP Importance", "importance")}
      ${renderForecastFoldChart(viz.fold_metrics || [])}
      ${renderForecastModelComparison(viz.model_comparison || [])}
      ${renderForecastDataQuality(viz.data_quality_summary || {})}
      ${renderForecastSignalTimeline(viz.signal_history || [])}
    </div>
  `;
}

function renderForecastBacktest(backtest) {
  if (!els.forecastBacktestSurface) return;
  const metrics = backtest.metrics || {};
  const assumptions = backtest.assumptions || {};
  els.forecastBacktestSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Total return", fmtPercent(metrics.total_return), "ok")}
      ${decisionMetric("Benchmark", fmtPercent(metrics.benchmark_return), "ok")}
      ${decisionMetric("Excess", fmtPercent(metrics.excess_return), metrics.excess_return >= 0 ? "ok" : "warn")}
      ${decisionMetric("Sharpe", fmtDecimal(metrics.sharpe, 3), metrics.sharpe > 0 ? "ok" : "warn")}
      ${decisionMetric("Max DD", fmtPercent(metrics.max_drawdown), metrics.max_drawdown < -0.2 ? "warn" : "ok")}
      ${decisionMetric("Cost impact", fmtPercent(metrics.transaction_cost_impact), "ok")}
      ${decisionMetric("1-bar delay", `${assumptions.execution_delay_bars || 0}봉`, Number(assumptions.execution_delay_bars || 0) >= 1 ? "ok" : "fail")}
    </div>
  `;
}

function renderForecastEvaluation(evaluation) {
  if (!els.forecastEvaluationSurface) return;
  const reg = evaluation.regression_metrics || {};
  const stability = evaluation.stability_metrics || {};
  const overfit = evaluation.overfitting_check || {};
  els.forecastEvaluationSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Directional accuracy", fmtPercent(reg.directional_accuracy || reg.accuracy), "ok")}
      ${decisionMetric("IC", fmtDecimal(reg.ic, 3), Math.abs(reg.ic || 0) > 0.02 ? "ok" : "warn")}
      ${decisionMetric("RMSE", fmtDecimal(reg.rmse, 4), "ok")}
      ${decisionMetric("Fold count", _fmtNumber(stability.fold_count || 0), stability.fold_count ? "ok" : "warn")}
      ${decisionMetric("Purged CV folds", _fmtNumber(stability.purged_cv_fold_count || 0), stability.purged_cv_fold_count ? "ok" : "warn")}
      ${decisionMetric("Purged CV acc", fmtPercent(stability.purged_cv_directional_accuracy), stability.purged_cv_directional_accuracy ? "ok" : "warn")}
      ${decisionMetric("Dispersion", fmtDecimal(stability.directional_accuracy_dispersion, 3), stability.directional_accuracy_dispersion > 0.2 ? "warn" : "ok")}
      ${decisionMetric("Overfit gap", fmtDecimal(overfit.gap, 3), (overfit.gap || 0) > 0.15 ? "warn" : "ok")}
    </div>
  `;
}

function renderForecastExplainability(explain) {
  if (!els.forecastExplainSurface) return;
  els.forecastExplainSurface.innerHTML = `
    ${renderForecastFeatureImportance(explain.feature_importance || [])}
    ${renderForecastFeatureImportance(explain.permutation_importance || [], "Permutation Importance", "normalized_importance")}
    ${renderForecastFeatureImportance(explain.shap_importance || [], "SHAP Importance", "importance")}
    <ul class="forecast-note-list">${(explain.reason_codes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    ${(explain.warnings || []).length ? `<div class="decision-warning">${escapeHtml(explain.warnings.join(", "))}</div>` : ""}
  `;
}

function renderForecastAi(ai) {
  if (!els.forecastAiSurface) return;
  els.forecastAiSurface.innerHTML = `
    <div class="decision-status-row"><span class="decision-badge warn">${escapeHtml(ai.provider || "deterministic_fallback")}</span><span>구조화 ML output만 사용</span></div>
    <pre class="forecast-ai-text">${escapeHtml(ai.content || "AI interpretation unavailable.")}</pre>
  `;
}

function renderForecastAiFromLastPayload() {
  if (!state.lastForecastPayload) {
    if (els.forecastAiSurface) els.forecastAiSurface.innerHTML = decisionEmpty("먼저 ML Forecast 실험을 실행하세요.");
    return;
  }
  renderForecastAi(state.lastForecastPayload.ai_interpretation || {});
}

async function renderForecastProviderAiFromLastPayload() {
  if (!state.lastForecastPayload) {
    if (els.forecastAiSurface) els.forecastAiSurface.innerHTML = decisionEmpty("먼저 ML Forecast 실험을 실행하세요.");
    return;
  }
  setButtonBusy(els.forecastGenerateProviderAi, true, "LLM 확인 중");
  if (els.forecastAiSurface) els.forecastAiSurface.innerHTML = decisionEmpty("Provider AI 해석을 생성하고 numeric grounding guard를 적용하는 중입니다.");
  try {
    const data = await forecastFetchJson(API.forecastAiInterpretation, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...state.lastForecastPayload, use_llm: true, timeout_s: 20 }),
    });
    renderForecastAi(data);
  } catch (err) {
    if (els.forecastAiSurface) els.forecastAiSurface.innerHTML = decisionEmpty(`Provider AI 해석 실패: ${err.message || err}`);
  } finally {
    setButtonBusy(els.forecastGenerateProviderAi, false);
  }
}

async function loadForecastAiProviderStatus(force = false) {
  if (!els.forecastAiProviderSurface) return;
  if (!force && els.forecastAiProviderSurface.dataset.loaded === "true") return;
  try {
    const data = await forecastFetchJson(API.forecastAiProviderHealth);
    els.forecastAiProviderSurface.dataset.loaded = "true";
    els.forecastAiProviderSurface.innerHTML = `
      <div class="decision-practical-grid forecast-metric-grid">
        ${decisionMetric("Provider", data.provider || "unknown", data.status === "ok" ? "ok" : "warn")}
        ${decisionMetric("Model", data.model || "unknown", data.model_available ? "ok" : "warn")}
        ${decisionMetric("Guard", data.guard_policy || "unknown", "ok")}
      </div>
      ${(data.available_models || []).length ? `<div class="forecast-chip-row">${data.available_models.slice(0, 6).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : decisionEmpty("사용 가능한 provider model 목록이 없습니다.")}
      ${data.error ? `<div class="decision-warning">${escapeHtml(data.error)}</div>` : ""}
    `;
  } catch (err) {
    els.forecastAiProviderSurface.innerHTML = decisionEmpty(`AI provider 상태 확인 실패: ${err.message || err}`);
  }
}

async function loadForecastJobs(force = false) {
  if (!els.forecastJobsSurface) return;
  if (!force && els.forecastJobsSurface.dataset.loaded === "true") return;
  try {
    const data = await forecastFetchJson(`${API.forecastJobs}?limit=10`);
    els.forecastJobsSurface.dataset.loaded = "true";
    renderForecastJobs(data.items || []);
  } catch (err) {
    els.forecastJobsSurface.innerHTML = decisionEmpty(`Forecast job 로드 실패: ${err.message || err}`);
  }
}

function renderForecastJobs(items) {
  if (!els.forecastJobsSurface) return;
  const rendered = window.FinGPTForecastUi?.jobs?.(items);
  els.forecastJobsSurface.innerHTML = rendered || decisionEmpty("Forecast UI module is unavailable.");
}

function scheduleForecastJobPoll(jobId) {
  if (!jobId) return;
  if (state.forecastJobPollTimer) window.clearInterval(state.forecastJobPollTimer);
  state.forecastJobPollTimer = window.setInterval(() => refreshForecastJob(jobId), 2500);
}

async function refreshForecastJob(jobId) {
  if (!jobId) return;
  try {
    const data = await forecastFetchJson(API.forecastJob(jobId));
    await loadForecastJobs(true);
    if (["succeeded", "failed", "cancelled"].includes(data.job_status)) {
      if (state.forecastJobPollTimer) window.clearInterval(state.forecastJobPollTimer);
      state.forecastJobPollTimer = null;
      if (data.job_status === "succeeded" && data.result?.status && data.result.status !== "failed") {
        state.lastForecastPayload = data.result;
        renderForecastPayload(data.result, Date.now());
        await Promise.allSettled([loadForecastHistory(true), loadForecastRegistry(true), loadForecastModelComparison(true), loadForecastDrift(true)]);
      }
    }
  } catch (err) {
    if (els.forecastJobsSurface) els.forecastJobsSurface.insertAdjacentHTML("afterbegin", `<div class="decision-warning">Forecast job 상태 확인 실패: ${escapeHtml(err.message || err)}</div>`);
  }
}

async function cancelForecastJob(jobId) {
  if (!jobId) return;
  await forecastFetchJson(API.forecastJobCancel(jobId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: "ui_cancel_request" }),
  });
  await loadForecastJobs(true);
}

async function retryForecastJob(jobId) {
  if (!jobId) return;
  const data = await forecastFetchJson(API.forecastJobRetry(jobId), { method: "POST" });
  renderForecastJobs([data]);
  scheduleForecastJobPoll(data.job_id);
  await loadForecastJobs(true);
}

async function loadForecastHistory(force = false) {
  if (!els.forecastHistorySurface) return;
  if (!force && els.forecastHistorySurface.dataset.loaded === "true") return;
  try {
    const data = await forecastFetchJson(`${API.forecastExperiments}?limit=10`);
    const items = data.items || [];
    els.forecastHistorySurface.dataset.loaded = "true";
    els.forecastHistorySurface.innerHTML = items.length ? `
      <div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Experiment</th><th>Ticker</th><th>Status</th><th>Model</th><th>Data Snapshot</th></tr></thead><tbody>
        ${items.map((item) => `<tr><td><button type="button" class="linkish" data-action="forecast-experiment-detail" data-experiment-id="${escapeHtml(item.experiment_id || "")}">${escapeHtml(item.experiment_id || "")}</button></td><td>${escapeHtml(item.ticker || "")}</td><td>${escapeHtml(item.status || "")}</td><td>${escapeHtml(item.model_id || "")}</td><td>${escapeHtml(item.data_snapshot_id || "")}</td></tr>`).join("")}
      </tbody></table></div>
    ` : decisionEmpty("저장된 ML Forecast 실험이 없습니다.");
  } catch (err) {
    els.forecastHistorySurface.innerHTML = decisionEmpty(`실험 이력 로드 실패: ${err.message || err}`);
  }
}

async function loadForecastDrift(force = false) {
  if (!els.forecastDriftSurface) return;
  if (!force && els.forecastDriftSurface.dataset.loaded === "true") return;
  const body = state.lastForecastPayload?.experiment?.experiment_id
    ? { experiment_id: state.lastForecastPayload.experiment.experiment_id, recent_window: 30 }
    : { ticker: normalizeTickerToken(els.forecastTicker?.value || "MSFT") || "MSFT", recent_window: 30 };
  try {
    const data = await forecastFetchJson(API.forecastDriftCheck, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    els.forecastDriftSurface.dataset.loaded = "true";
    renderForecastDrift(data);
  } catch (err) {
    els.forecastDriftSurface.innerHTML = decisionEmpty(`Drift 확인 실패: ${err.message || err}`);
  }
}

function renderForecastDrift(data) {
  if (!els.forecastDriftSurface) return;
  const metrics = data.metrics || {};
  const drift = data.drift_status || data.status || "unknown";
  els.forecastDriftSurface.innerHTML = `
    <div class="decision-practical-grid forecast-metric-grid">
      ${decisionMetric("Drift", drift, drift === "pass" ? "ok" : (drift === "fail" ? "fail" : "warn"))}
      ${decisionMetric("OOS rows", _fmtNumber(data.oos_count || 0), data.oos_count ? "ok" : "warn")}
      ${decisionMetric("Recent acc", fmtPercent(metrics.recent_directional_accuracy), "ok")}
      ${decisionMetric("Hist acc", fmtPercent(metrics.historical_directional_accuracy), "ok")}
      ${decisionMetric("Acc drop", fmtPercent(metrics.accuracy_drop), metrics.accuracy_drop > 0.12 ? "warn" : "ok")}
      ${decisionMetric("MAE increase", fmtDecimal(metrics.mae_increase, 4), metrics.mae_increase > 0 ? "warn" : "ok")}
    </div>
    ${(data.warnings || []).map((item) => `<div class="decision-warning">${escapeHtml(item)}</div>`).join("")}
  `;
}

async function loadForecastModelComparison(force = false) {
  if (!els.forecastModelComparisonSurface) return;
  if (!force && els.forecastModelComparisonSurface.dataset.loaded === "true") return;
  try {
    const ticker = normalizeTickerToken(els.forecastTicker?.value || "");
    const url = ticker ? `${API.forecastModelComparison}?limit=20&ticker=${encodeURIComponent(ticker)}` : `${API.forecastModelComparison}?limit=20`;
    const data = await forecastFetchJson(url);
    els.forecastModelComparisonSurface.dataset.loaded = "true";
    renderForecastModelComparisonTable(data.items || []);
  } catch (err) {
    els.forecastModelComparisonSurface.innerHTML = decisionEmpty(`모델 비교 로드 실패: ${err.message || err}`);
  }
}

function renderForecastModelComparisonTable(items) {
  if (!els.forecastModelComparisonSurface) return;
  els.forecastModelComparisonSurface.innerHTML = items.length ? `
    <div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Experiment</th><th>Model</th><th>Confidence</th><th>Signal</th><th>Sharpe</th><th>MDD</th></tr></thead><tbody>
      ${items.map((item) => `<tr><td>${escapeHtml(item.experiment_id || "")}</td><td>${escapeHtml(item.model_id || "")}</td><td>${escapeHtml(fmtDecimal(item.confidence, 3))} ${escapeHtml(item.confidence_level || "")}</td><td>${escapeHtml(fmtPercent(item.signal_quality?.hit_rate))}</td><td>${escapeHtml(fmtDecimal(item.backtest?.sharpe, 3))}</td><td>${escapeHtml(fmtPercent(item.backtest?.max_drawdown))}</td></tr>`).join("")}
    </tbody></table></div>
  ` : decisionEmpty("비교할 ML Forecast 실험이 없습니다.");
}

async function loadForecastRegistry(force = false) {
  if (!els.forecastRegistrySurface) return;
  if (!force && els.forecastRegistrySurface.dataset.loaded === "true") return;
  try {
    const [data, audit] = await Promise.all([
      forecastFetchJson(API.forecastRegistry),
      forecastFetchJson(`${API.forecastRegistryAudit}?limit=20`).catch((err) => ({ status: "failed", items: [], error: err.message || String(err) })),
    ]);
    const items = data.items || [];
    const auditItems = audit.items || [];
    els.forecastRegistrySurface.dataset.loaded = "true";
    els.forecastRegistrySurface.innerHTML = items.length ? `
      <div class="decision-mini-row">
        <span>Storage: ${escapeHtml(data.storage || "unknown")}</span>
        <span>Items: ${escapeHtml(String(data.count || items.length))}</span>
      </div>
      <div id="forecastRegistryIntegrityResult" class="decision-surface compact-surface">${decisionEmpty("모델 행의 verify를 누르면 signed artifact 무결성을 확인합니다.")}</div>
      <div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Model</th><th>Ticker</th><th>Target</th><th>Status</th><th>Metric</th><th>Artifact</th><th>Action</th></tr></thead><tbody>
        ${items.map((item) => `<tr><td>${escapeHtml(item.model_id || "")}</td><td>${escapeHtml(item.ticker || "")}</td><td>${escapeHtml(item.target || "")} ${escapeHtml(String(item.horizon || ""))}d</td><td>${escapeHtml(item.status || "")}</td><td>${escapeHtml(fmtPercent(item.metrics?.directional_accuracy || item.metrics?.accuracy))}</td><td>${escapeHtml(compactArtifactPath(item.artifact_path || ""))}</td><td><button type="button" class="linkish" data-action="forecast-verify-artifact" data-model-id="${escapeHtml(item.model_id || "")}">verify</button> <button type="button" class="linkish" data-action="forecast-promote" data-model-id="${escapeHtml(item.model_id || "")}">promote</button> <button type="button" class="linkish" data-action="forecast-deprecate" data-model-id="${escapeHtml(item.model_id || "")}">deprecate</button></td></tr>`).join("")}
      </tbody></table></div>
      <div class="decision-surface compact-surface">
        <strong>Registry Audit</strong>
        ${auditItems.length ? `
          <div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Time</th><th>Model</th><th>Action</th><th>Status</th><th>Notes</th></tr></thead><tbody>
            ${auditItems.map((item) => `<tr><td>${escapeHtml(item.created_at || "")}</td><td>${escapeHtml(item.model_id || "")}</td><td>${escapeHtml(item.action || "")}</td><td>${escapeHtml(item.previous_status || "")} -> ${escapeHtml(item.new_status || "")}</td><td>${escapeHtml(item.notes || "")}</td></tr>`).join("")}
          </tbody></table></div>
        ` : decisionEmpty(audit.error ? `Audit 로드 실패: ${audit.error}` : "아직 registry audit 이력이 없습니다.")}
      </div>
    ` : decisionEmpty("등록된 ML Forecast 모델이 없습니다.");
  } catch (err) {
    els.forecastRegistrySurface.innerHTML = decisionEmpty(`모델 레지스트리 로드 실패: ${err.message || err}`);
  }
}

async function updateForecastModelStatus(action, modelId) {
  const endpoint = action === "forecast-promote" ? API.forecastPromoteModel : API.forecastDeprecateModel;
  if (!modelId || !endpoint) return;
  try {
    await forecastFetchJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId, notes: "ui_registry_action" }),
    });
    els.forecastRegistrySurface.dataset.loaded = "false";
    await loadForecastRegistry(true);
  } catch (err) {
    if (els.forecastRegistrySurface) els.forecastRegistrySurface.insertAdjacentHTML("afterbegin", `<div class="decision-warning">모델 상태 변경 실패: ${escapeHtml(err.message || err)}</div>`);
  }
}

async function verifyForecastModelArtifact(modelId) {
  if (!modelId || !API.forecastVerifyArtifact) return;
  const target = document.getElementById("forecastRegistryIntegrityResult") || els.forecastRegistrySurface;
  if (target) target.innerHTML = `<div class="home-news-empty">모델 아티팩트 무결성 확인 중...</div>`;
  try {
    const data = await forecastFetchJson(API.forecastVerifyArtifact, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId, notes: "ui_artifact_verify" }),
    });
    const checks = data.checks || {};
    const status = data.status === "success" ? "ok" : "fail";
    if (target) {
      target.innerHTML = `
        <div class="decision-practical-grid forecast-metric-grid">
          ${decisionMetric("Integrity", data.status || "unknown", status)}
          ${decisionMetric("SHA-256", checks.sha256_matches ? "match" : "fail", checks.sha256_matches ? "ok" : "fail")}
          ${decisionMetric("Bytes", checks.bytes_match ? "match" : "fail", checks.bytes_match ? "ok" : "fail")}
          ${decisionMetric("Signature", checks.signature_matches ? "match" : "fail", checks.signature_matches ? "ok" : "fail")}
        </div>
        <div class="decision-mini-row">
          <span>Model ${escapeHtml(data.model_id || modelId)}</span>
          <span>${escapeHtml(compactArtifactPath(data.integrity_path || ""))}</span>
        </div>
        ${(data.errors || []).map((item) => `<div class="decision-warning">${escapeHtml(item)}</div>`).join("")}
      `;
    }
  } catch (err) {
    if (target) target.innerHTML = decisionEmpty(`아티팩트 검증 실패: ${err.message || err}`);
  }
}

async function openForecastExperimentDetail(experimentId) {
  if (!experimentId || !els.forecastDetailModal || !els.forecastDetailBody) return;
  els.forecastDetailTitle.textContent = experimentId;
  els.forecastDetailBody.innerHTML = decisionEmpty("실험 상세와 registry audit를 불러오는 중입니다.");
  els.forecastDetailModal.classList.remove("hidden");
  try {
    const detail = await forecastFetchJson(API.forecastExperiment(experimentId));
    const modelId = detail.forecast_result?.model_id || detail.experiment?.artifact_refs?.model_id || "";
    const audit = modelId
      ? await forecastFetchJson(`${API.forecastRegistryAudit}?model_id=${encodeURIComponent(modelId)}&limit=20`).catch((err) => ({ status: "failed", items: [], error: err.message || String(err) }))
      : { status: "empty", items: [] };
    renderForecastExperimentDetail(detail, audit);
  } catch (err) {
    els.forecastDetailBody.innerHTML = decisionEmpty(`실험 상세 로드 실패: ${err.message || err}`);
  }
}

function closeForecastExperimentDetail() {
  els.forecastDetailModal?.classList.add("hidden");
}

function renderForecastExperimentDetail(payload, audit = {}) {
  if (!els.forecastDetailBody) return;
  const experiment = payload.experiment || {};
  const forecast = payload.forecast_result || {};
  const signal = payload.signal_result || {};
  const snapshot = payload.data_snapshot || {};
  const feature = payload.feature_payload || {};
  const target = payload.target_config || experiment.target_config || {};
  const validation = experiment.validation_config || {};
  const model = experiment.model_config || {};
  const leakage = payload.leakage_check || {};
  const training = payload.training_result || {};
  const aggregate = training.aggregate_metrics || {};
  const artifactRefs = experiment.artifact_refs || {};
  const auditItems = audit.items || [];
  els.forecastDetailBody.innerHTML = `
    <div class="forecast-detail-grid">
      <section class="forecast-detail-section">
        <h3>Run Identity</h3>
        <div class="decision-practical-grid forecast-metric-grid">
          ${decisionMetric("Status", payload.status || experiment.status || "unknown", decisionStatusClass(payload.status || experiment.status))}
          ${decisionMetric("Ticker", forecast.ticker || experiment.ticker || "", "ok")}
          ${decisionMetric("Model", forecast.model_id || "", "ok")}
          ${decisionMetric("Signal", signal.signal || forecast.signal || "unavailable", decisionStatusClass(signal.signal || forecast.signal))}
          ${decisionMetric("Confidence", fmtDecimal(forecast.model_confidence?.score, 3), "ok")}
          ${decisionMetric("Created", experiment.created_at || payload.generated_at || "", "ok")}
        </div>
      </section>
      <section class="forecast-detail-section">
        <h3>Data Snapshot</h3>
        ${forecastDetailRows([
          ["data_snapshot_id", snapshot.data_snapshot_id],
          ["source_coverage_hash", snapshot.source_coverage_hash],
          ["price_rows", snapshot.price_coverage?.rows],
          ["price_range", `${snapshot.price_coverage?.start_date || ""} -> ${snapshot.price_coverage?.end_date || ""}`],
          ["benchmark_rows", snapshot.benchmark_coverage?.rows],
          ["feature_schema_hash", snapshot.feature_schema_hash],
        ])}
      </section>
      <section class="forecast-detail-section">
        <h3>Feature / Target / Validation</h3>
        ${forecastDetailRows([
          ["feature_count", (feature.feature_names || []).length],
          ["feature_shift", feature.summary?.feature_shift],
          ["target_type", target.target_type],
          ["horizon", target.horizon],
          ["validation_method", validation.validation_method],
          ["purge_window", validation.purge_window],
          ["embargo_window", validation.embargo_window],
          ["model_name", model.model_name],
        ])}
      </section>
      <section class="forecast-detail-section">
        <h3>Leakage / OOS Metrics</h3>
        ${forecastDetailRows([
          ["leakage_status", leakage.status],
          ["issues", (leakage.issues || []).join(", ")],
          ["mae", aggregate.mae],
          ["rmse", aggregate.rmse],
          ["directional_accuracy", aggregate.directional_accuracy],
          ["ic", aggregate.ic],
          ["purged_cv_status", training.purged_combinatorial_cv?.status],
          ["purged_cv_folds", training.purged_combinatorial_cv?.fold_count],
        ])}
      </section>
      <section class="forecast-detail-section">
        <h3>Artifacts</h3>
        ${forecastDetailRows(Object.entries(artifactRefs).map(([key, value]) => [key, compactArtifactPath(value)]))}
      </section>
      <section class="forecast-detail-section">
        <h3>Registry Audit</h3>
        ${auditItems.length ? `
          <div class="decision-table-wrap"><table class="decision-table"><thead><tr><th>Time</th><th>Action</th><th>Status</th><th>Notes</th></tr></thead><tbody>
            ${auditItems.map((item) => `<tr><td>${escapeHtml(item.created_at || "")}</td><td>${escapeHtml(item.action || "")}</td><td>${escapeHtml(item.previous_status || "")} -> ${escapeHtml(item.new_status || "")}</td><td>${escapeHtml(item.notes || "")}</td></tr>`).join("")}
          </tbody></table></div>
        ` : decisionEmpty(audit.error ? `Audit 로드 실패: ${audit.error}` : "연결된 registry audit가 없습니다.")}
      </section>
    </div>
  `;
}

function forecastDetailRows(rows) {
  const cleanRows = (rows || []).filter((row) => row && row[0]);
  if (!cleanRows.length) return decisionEmpty("표시할 상세 값이 없습니다.");
  return `
    <div class="decision-table-wrap"><table class="decision-table forecast-detail-table"><tbody>
      ${cleanRows.map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value === null || value === undefined || value === "" ? "N/A" : String(value))}</td></tr>`).join("")}
    </tbody></table></div>
  `;
}

function fmtPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "N/A";
  return `${(num * 100).toFixed(2)}%`;
}

function renderForecastLineChart(title, rows, valueKey, comparisonRows = []) {
  if (!rows.length) return `<div class="forecast-chart-card"><strong>${escapeHtml(title)}</strong>${decisionEmpty("표시할 OOS 데이터가 없습니다.")}</div>`;
  const values = rows.map((row) => Number(row[valueKey])).filter(Number.isFinite);
  if (!values.length) return `<div class="forecast-chart-card"><strong>${escapeHtml(title)}</strong>${decisionEmpty("차트 값이 없습니다.")}</div>`;
  const width = 360;
  const height = 150;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = rows.map((row, idx) => {
    const value = Number(row[valueKey]);
    const x = rows.length === 1 ? 0 : (idx / (rows.length - 1)) * width;
    const y = height - ((value - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const comparisonValues = comparisonRows.map((row) => Number(row[valueKey])).filter(Number.isFinite);
  const comparisonPoints = comparisonValues.length ? comparisonRows.map((row, idx) => {
    const value = Number(row[valueKey]);
    const x = comparisonRows.length === 1 ? 0 : (idx / (comparisonRows.length - 1)) * width;
    const y = height - ((value - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ") : "";
  return `
    <div class="forecast-chart-card">
      <strong>${escapeHtml(title)}</strong>
      <svg class="forecast-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
        <polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2" />
        ${comparisonPoints ? `<polyline points="${comparisonPoints}" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 3" />` : ""}
      </svg>
      <span>${escapeHtml(rows[0]?.date || "")} ~ ${escapeHtml(rows[rows.length - 1]?.date || "")}</span>
    </div>
  `;
}

function renderForecastActualPredicted(rows) {
  if (!rows.length) return `<div class="forecast-chart-card"><strong>Actual vs Predicted</strong>${decisionEmpty("OOS 예측이 없습니다.")}</div>`;
  const points = rows.slice(-160);
  return `
    <div class="forecast-chart-card">
      <strong>Actual vs Predicted</strong>
      <div class="forecast-scatter">
        ${points.map((row) => {
          const pred = Math.max(-0.2, Math.min(0.2, Number(row.predicted_return || 0)));
          const actual = Math.max(-0.2, Math.min(0.2, Number(row.actual_forward_return || 0)));
          const left = ((pred + 0.2) / 0.4) * 100;
          const top = 100 - ((actual + 0.2) / 0.4) * 100;
          return `<span style="left:${left}%;top:${top}%"></span>`;
        }).join("")}
      </div>
    </div>
  `;
}

function renderForecastResidualChart(rows) {
  if (!rows.length) return `<div class="forecast-chart-card"><strong>Residuals</strong>${decisionEmpty("잔차 데이터가 없습니다.")}</div>`;
  return renderForecastLineChart("Residuals", rows, "residual");
}

function renderForecastIntervalChart(items) {
  if (!items.length) return `<div class="forecast-chart-card"><strong>Forecast Interval</strong>${decisionEmpty("prediction interval이 없습니다.")}</div>`;
  const item = items[0] || {};
  return `
    <div class="forecast-chart-card">
      <strong>Forecast Interval</strong>
      <div class="decision-practical-grid forecast-metric-grid">
        ${decisionMetric("P10", fmtPercent(item.p10), "ok")}
        ${decisionMetric("P50", fmtPercent(item.p50), "ok")}
        ${decisionMetric("P90", fmtPercent(item.p90), "ok")}
      </div>
      <span>${escapeHtml(item.note || "Return interval; not a guaranteed price path.")}</span>
    </div>
  `;
}

function renderForecastDistribution(values) {
  const nums = (values || []).map(Number).filter(Number.isFinite);
  if (!nums.length) return `<div class="forecast-chart-card"><strong>Prediction Distribution</strong>${decisionEmpty("예측 분포 데이터가 없습니다.")}</div>`;
  const bins = Array.from({ length: 8 }, () => 0);
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  nums.forEach((value) => {
    const idx = Math.min(bins.length - 1, Math.max(0, Math.floor(((value - min) / span) * bins.length)));
    bins[idx] += 1;
  });
  const peak = Math.max(...bins, 1);
  return `
    <div class="forecast-chart-card">
      <strong>Prediction Distribution</strong>
      <div class="forecast-bars">${bins.map((count, idx) => `<div><span>Bin ${idx + 1}</span><b style="width:${Math.max(2, (count / peak) * 100)}%"></b></div>`).join("")}</div>
      <span>${escapeHtml(fmtPercent(min))} ~ ${escapeHtml(fmtPercent(max))}</span>
    </div>
  `;
}

function renderForecastFeatureImportance(items, title = "Feature Importance", valueKey = "importance") {
  if (!items.length) return `<div class="forecast-chart-card"><strong>${escapeHtml(title)}</strong>${decisionEmpty(`${title}가 없습니다.`)}</div>`;
  const max = Math.max(...items.map((item) => Number(item[valueKey] || item.importance || 0)), 1e-9);
  return `
    <div class="forecast-chart-card">
      <strong>${escapeHtml(title)}</strong>
      <div class="forecast-bars">${items.slice(0, 10).map((item) => {
        const value = Number(item[valueKey] || item.importance || 0);
        return `<div><span>${escapeHtml(item.feature || "")}</span><b style="width:${Math.max(2, (value / max) * 100)}%"></b></div>`;
      }).join("")}</div>
    </div>
  `;
}

function renderForecastFoldChart(folds) {
  if (!folds.length) return `<div class="forecast-chart-card"><strong>Walk-forward Folds</strong>${decisionEmpty("fold 성능이 없습니다.")}</div>`;
  return `
    <div class="forecast-chart-card">
      <strong>Walk-forward Folds</strong>
      <div class="forecast-bars">${folds.map((fold) => {
        const value = Number(fold.metrics?.directional_accuracy || fold.metrics?.accuracy || 0);
        return `<div><span>Fold ${escapeHtml(String(fold.fold_id))}</span><b style="width:${Math.max(2, value * 100)}%"></b></div>`;
      }).join("")}</div>
    </div>
  `;
}

function renderForecastSignalTimeline(items) {
  if (!items.length) return `<div class="forecast-chart-card"><strong>Signal History</strong>${decisionEmpty("신호 이력이 없습니다.")}</div>`;
  return `
    <div class="forecast-chart-card">
      <strong>Signal History</strong>
      <div class="forecast-signal-timeline">${items.slice(-80).map((item) => `<span class="${escapeHtml(String(item.signal || "neutral").replace("_", "-"))}" title="${escapeHtml(item.date || "")} ${escapeHtml(item.signal || "")}"></span>`).join("")}</div>
    </div>
  `;
}

function renderForecastModelComparison(items) {
  if (!items.length) return `<div class="forecast-chart-card"><strong>Model Comparison</strong>${decisionEmpty("모델 비교 데이터가 없습니다.")}</div>`;
  const scored = items.map((item) => ({ ...item, score: Number(item.directional_accuracy || item.accuracy || item.ic || 0) }));
  const max = Math.max(...scored.map((item) => Math.abs(item.score)), 1e-9);
  return `
    <div class="forecast-chart-card">
      <strong>Model Comparison</strong>
      <div class="forecast-bars">${scored.map((item) => `<div><span>${escapeHtml(item.model || "model")}</span><b style="width:${Math.max(2, (Math.abs(item.score) / max) * 100)}%"></b></div>`).join("")}</div>
    </div>
  `;
}

function renderForecastDataQuality(summary) {
  const missing = summary.missing_by_feature || {};
  const items = Object.entries(missing).slice(0, 10);
  if (!items.length) return `<div class="forecast-chart-card"><strong>Data Quality</strong>${decisionEmpty("missing value summary가 없습니다.")}</div>`;
  const max = Math.max(...items.map(([, value]) => Number(value || 0)), 1e-9);
  return `
    <div class="forecast-chart-card">
      <strong>Data Quality</strong>
      <div class="forecast-bars">${items.map(([name, value]) => `<div><span>${escapeHtml(name)}</span><b style="width:${Math.max(2, (Number(value || 0) / max) * 100)}%"></b></div>`).join("")}</div>
      <span>Missing ratio ${escapeHtml(fmtPercent(summary.missing_ratio))}</span>
    </div>
  `;
}

function renderForecastMonthlyHeatmap(items) {
  if (!items.length) return `<div class="forecast-chart-card"><strong>Monthly Return Heatmap</strong>${decisionEmpty("월별 수익률 데이터가 없습니다.")}</div>`;
  const maxAbs = Math.max(...items.map((item) => Math.abs(Number(item.return || 0))), 1e-9);
  return `
    <div class="forecast-chart-card">
      <strong>Monthly Return Heatmap</strong>
      <div class="forecast-heatmap">${items.map((item) => {
        const value = Number(item.return || 0);
        const alpha = Math.max(0.12, Math.min(0.9, Math.abs(value) / maxAbs));
        const color = value >= 0 ? `rgba(22, 163, 74, ${alpha})` : `rgba(220, 38, 38, ${alpha})`;
        return `<span style="background:${color}" title="${escapeHtml(item.month || "")} ${escapeHtml(fmtPercent(value))}">${escapeHtml(item.month || "")}<b>${escapeHtml(fmtPercent(value))}</b></span>`;
      }).join("")}</div>
    </div>
  `;
}

function renderForecastConfusionMatrix(matrix) {
  const total = Object.values(matrix || {}).map(Number).filter(Number.isFinite).reduce((sum, value) => sum + value, 0);
  if (!total) return `<div class="forecast-chart-card"><strong>Confusion Matrix</strong>${decisionEmpty("방향성 혼동행렬 데이터가 없습니다.")}</div>`;
  return `
    <div class="forecast-chart-card">
      <strong>Confusion Matrix</strong>
      <div class="forecast-confusion">
        <span>TP<b>${escapeHtml(String(matrix.true_positive || 0))}</b></span>
        <span>FP<b>${escapeHtml(String(matrix.false_positive || 0))}</b></span>
        <span>FN<b>${escapeHtml(String(matrix.false_negative || 0))}</b></span>
        <span>TN<b>${escapeHtml(String(matrix.true_negative || 0))}</b></span>
      </div>
    </div>
  `;
}

function renderForecastRegimePerformance(items) {
  if (!items.length) return `<div class="forecast-chart-card"><strong>Regime Performance</strong>${decisionEmpty("레짐별 성능 데이터가 없습니다.")}</div>`;
  return `
    <div class="forecast-chart-card">
      <strong>Regime Performance</strong>
      <div class="forecast-bars">${items.map((item) => {
        const value = Number(item.directional_score || 0);
        return `<div><span>${escapeHtml(item.regime || "")} (${escapeHtml(String(item.observations || 0))})</span><b style="width:${Math.max(2, value * 100)}%"></b></div>`;
      }).join("")}</div>
      <span>source: realized_forward_return_proxy</span>
    </div>
  `;
}

function quantamentalUi() {
  return window.FinGPTQuantamentalUi || {};
}

function quantamentalRequestFromControls() {
  const ticker = normalizeTickerToken(els.quantamentalTicker?.value || "");
  return {
    ticker,
    market: els.quantamentalMarket?.value || "US",
    period: els.quantamentalPeriod?.value || "annual",
    years: Number(els.quantamentalYears?.value || 5),
    lookback: els.quantamentalLookback?.value || "252",
    style: els.quantamentalStyle?.value || "balanced",
    output_language: selectedOutputLanguage(),
  };
}

function renderQuantamentalStarter() {
  const ui = quantamentalUi();
  const starter = ui.starter ? ui.starter() : decisionEmpty("Quantamental module is loading.");
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = starter;
  if (els.quantamentalSignalSurface) els.quantamentalSignalSurface.innerHTML = starter;
  if (els.quantamentalScoreSurface) els.quantamentalScoreSurface.innerHTML = starter;
  if (els.quantamentalFactorSurface) els.quantamentalFactorSurface.innerHTML = starter;
  if (els.quantamentalMainSurface) els.quantamentalMainSurface.innerHTML = starter;
  if (els.quantamentalDataQualitySurface) els.quantamentalDataQualitySurface.innerHTML = starter;
  if (els.quantamentalStatus) els.quantamentalStatus.textContent = q.messages.status;
  if (els.quantamentalCompareSurface) els.quantamentalCompareSurface.innerHTML = decisionEmpty(q.messages.compareEmpty);
  if (els.quantamentalScreenSurface) els.quantamentalScreenSurface.innerHTML = decisionEmpty(q.messages.topEmpty);
  if (els.quantamentalScreenStatus) els.quantamentalScreenStatus.textContent = q.messages.topStatus;
  if (els.quantamentalScoreScreenSurface) els.quantamentalScoreScreenSurface.innerHTML = decisionEmpty(q.messages.scoreEmpty);
  if (els.quantamentalScoreScreenStatus) els.quantamentalScoreScreenStatus.textContent = q.messages.scoreStatus;
}

function setQuantamentalLoading(isLoading, message = "Quantamental analysis를 계산하는 중입니다.") {
  state.quantamentalLoading = isLoading;
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  setButtonBusy(
    els.quantamentalAnalyze,
    isLoading,
    selectedOutputLanguage() === "en" ? "Analyzing" : "분석 중",
    q.buttons.analyze,
  );
  const ui = quantamentalUi();
  const content = ui.loading ? ui.loading(message) : decisionEmpty(message);
  if (!isLoading) return;
  if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = content;
  if (els.quantamentalSignalSurface) els.quantamentalSignalSurface.innerHTML = content;
  if (els.quantamentalScoreSurface) els.quantamentalScoreSurface.innerHTML = content;
  if (els.quantamentalFactorSurface) els.quantamentalFactorSurface.innerHTML = content;
  if (els.quantamentalMainSurface) els.quantamentalMainSurface.innerHTML = content;
  if (els.quantamentalDataQualitySurface) els.quantamentalDataQualitySurface.innerHTML = content;
}

function renderQuantamentalAnalysis(data) {
  const ui = quantamentalUi();
  if (!ui.companyHeader) {
    renderQuantamentalStarter();
    return;
  }
  if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = ui.companyHeader(data);
  if (els.quantamentalSignalSurface) els.quantamentalSignalSurface.innerHTML = ui.signalCard(data);
  if (els.quantamentalScoreSurface) els.quantamentalScoreSurface.innerHTML = ui.scoreDashboard(data);
  if (els.quantamentalFactorSurface) els.quantamentalFactorSurface.innerHTML = ui.factorGrid(data);
  if (els.quantamentalMainSurface) els.quantamentalMainSurface.innerHTML = ui.mainPanel(data, state.quantamentalActiveTab || "overview");
  if (els.quantamentalDataQualitySurface) els.quantamentalDataQualitySurface.innerHTML = ui.dataQuality(data);
  const quality = data?.data_quality || {};
  const freshness = quality.freshness || {};
  const usedData = data?.ai_report?.data_snapshot || data?.ai_report?.report?.used_data || {};
  updateGlobalQualitySummary({
    status: quality.quality_level || freshness.status || data?.status || "unknown",
    asOf: usedData.data_basis_date || freshness.as_of || data?.generated_at || "",
    updatedAt: usedData.ai_snapshot_at || data?.generated_at || "",
    source: usedData.data_source || "quantamental engine",
    observations: usedData.observation_count || quality.observation_count || data?.quant?.observation_count || "",
    missing: (usedData.missing_data || (quality.missing_sections || []).length)
      ? (usedData.missing_data || (quality.missing_sections || []).join(", "))
      : "없음",
    aiSnapshotAt: usedData.ai_snapshot_at || data?.generated_at || "",
  });
  if (els.quantamentalStatus) {
    const quality = data?.data_quality?.quality_level || "unknown";
    const signal = data?.signal?.signal_label || "Insufficient Data";
    const isEnglish = selectedOutputLanguage() === "en";
    els.quantamentalStatus.textContent = isEnglish
      ? `${data?.ticker || ""} · ${signal} · data quality ${quality}`
      : `${data?.ticker || ""} · ${signal} · 데이터 품질 ${quality}`;
    els.quantamentalStatus.className = `form-notice ${["ok", "success"].includes(data?.status) ? "success" : "info"}`;
  }
}

function renderQuantamentalScreen(data) {
  const ui = quantamentalUi();
  if (els.quantamentalScreenSurface) {
    els.quantamentalScreenSurface.innerHTML = ui.topSignals ? ui.topSignals(data) : `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  }
  if (els.quantamentalScreenStatus) {
    const summary = data?.freshness_summary || {};
    const isEnglish = selectedOutputLanguage() === "en";
    els.quantamentalScreenStatus.textContent = isEnglish
      ? `${data?.scored_count ?? 0}/${data?.requested_count ?? 0} scored · freshness ${summary.status || "unknown"} · ${data?.style || "balanced"}`
      : `${data?.scored_count ?? 0}/${data?.requested_count ?? 0}개 산출 · 신선도 ${summary.status || "unknown"} · ${data?.style || "balanced"}`;
    els.quantamentalScreenStatus.className = `form-notice ${data?.status === "ok" ? "success" : "info"}`;
  }
}

function quantamentalScoreScreenThreshold() {
  const raw = Number(els.quantamentalScoreThreshold?.value || 70);
  const threshold = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : 70;
  if (els.quantamentalScoreThreshold) els.quantamentalScoreThreshold.value = String(threshold);
  return threshold;
}

function quantamentalScoreScreenLimit() {
  const raw = Number(els.quantamentalScoreScreenLimit?.value || 20);
  return Number.isFinite(raw) ? Math.max(1, Math.min(50, raw)) : 20;
}

function quantamentalScoreScreenMetric() {
  const raw = String(els.quantamentalScoreMetric?.value || "composite");
  return ["composite", "value", "quality", "growth", "momentum", "low_volatility", "liquidity", "drawdown_resilience", "liquidity_stability", "trend_efficiency", "market_resilience"].includes(raw) ? raw : "composite";
}

function quantamentalScoreMetricLabel(scoreKey) {
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  return q.scoreMetricLabels?.[scoreKey] || scoreKey || "composite";
}

function renderQuantamentalScoreScreen(data) {
  const ui = quantamentalUi();
  if (els.quantamentalScoreScreenSurface) {
    els.quantamentalScoreScreenSurface.innerHTML = ui.scoreScreen ? ui.scoreScreen(data) : `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  }
  if (els.quantamentalScoreScreenStatus) {
    const summary = data?.freshness_summary || {};
    const isEnglish = selectedOutputLanguage() === "en";
    const scoreLabel = quantamentalScoreMetricLabel(data?.score_key || quantamentalScoreScreenMetric());
    els.quantamentalScoreScreenStatus.textContent = isEnglish
      ? `${data?.returned_count ?? 0}/${data?.matched_count ?? 0} returned · ${scoreLabel} >= ${fmtDecimal(data?.min_score, 1)} · freshness ${summary.status || "unknown"}`
      : `${data?.returned_count ?? 0}/${data?.matched_count ?? 0}개 반환 · ${scoreLabel} >= ${fmtDecimal(data?.min_score, 1)} · 신선도 ${summary.status || "unknown"}`;
    els.quantamentalScoreScreenStatus.className = `form-notice ${data?.status === "ok" ? "success" : "info"}`;
  }
}

async function loadQuantamentalScreen(force = false) {
  if (!els.quantamentalScreenSurface || state.quantamentalScreenLoading) return;
  if (state.quantamentalScreenLoaded && !force) {
    renderQuantamentalScreen(state.quantamentalScreen);
    return;
  }
  const request = quantamentalRequestFromControls();
  state.quantamentalScreenLoading = true;
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  setButtonBusy(
    els.quantamentalScreenRun,
    true,
    selectedOutputLanguage() === "en" ? "Screening" : "스크리닝",
    q.buttons.refresh,
  );
  if (els.quantamentalScreenSurface) {
    els.quantamentalScreenSurface.innerHTML = quantamentalUi().loading ? quantamentalUi().loading(q.messages.screenLoading) : decisionEmpty(q.messages.screenLoading);
  }
  try {
    const data = await quantamentalFetchJson(API.quantamentalTopSignals({
      market: request.market,
      period: request.period,
      years: request.years,
      lookback: request.lookback,
      style: request.style,
      limit: 5,
      refreshStale: true,
      // Force reloads bypass the UI cache; stale-aware server refresh keeps Top 5 fast.
      forceRefresh: false,
      outputLanguage: request.output_language,
    }));
    state.quantamentalScreen = data;
    state.quantamentalScreenLoaded = true;
    renderQuantamentalScreen(data);
  } catch (err) {
    const message = err.message || String(err);
    if (els.quantamentalScreenSurface) {
      els.quantamentalScreenSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error(message) : decisionEmpty(message);
    }
    if (els.quantamentalScreenStatus) {
      els.quantamentalScreenStatus.textContent = message;
      els.quantamentalScreenStatus.className = "form-notice error";
    }
  } finally {
    state.quantamentalScreenLoading = false;
    setButtonBusy(els.quantamentalScreenRun, false);
    if (els.quantamentalScreenRun) els.quantamentalScreenRun.textContent = q.buttons.refresh;
  }
}

async function runQuantamentalScoreScreen() {
  if (!els.quantamentalScoreScreenSurface || state.quantamentalScoreScreenLoading) return;
  const request = quantamentalRequestFromControls();
  const scoreKey = quantamentalScoreScreenMetric();
  const threshold = quantamentalScoreScreenThreshold();
  const limit = quantamentalScoreScreenLimit();
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  state.quantamentalScoreScreenLoading = true;
  setButtonBusy(
    els.quantamentalScoreScreenRun,
    true,
    selectedOutputLanguage() === "en" ? "Screening" : "스크리닝",
    q.buttons.screen,
  );
  if (els.quantamentalScoreScreenSurface) {
    els.quantamentalScoreScreenSurface.innerHTML = quantamentalUi().loading ? quantamentalUi().loading(q.messages.scoreScreenLoading) : decisionEmpty(q.messages.scoreScreenLoading);
  }
  try {
    const data = await quantamentalFetchJson(API.quantamentalScoreScreen({
      market: request.market,
      period: request.period,
      years: request.years,
      lookback: request.lookback,
      style: request.style,
      scoreKey,
      minScore: threshold,
      limit,
      refreshStale: true,
      forceRefresh: true,
      outputLanguage: request.output_language,
    }));
    state.quantamentalScoreScreen = data;
    renderQuantamentalScoreScreen(data);
  } catch (err) {
    const message = err.message || String(err);
    if (els.quantamentalScoreScreenSurface) {
      els.quantamentalScoreScreenSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error(message) : decisionEmpty(message);
    }
    if (els.quantamentalScoreScreenStatus) {
      els.quantamentalScoreScreenStatus.textContent = message;
      els.quantamentalScoreScreenStatus.className = "form-notice error";
    }
  } finally {
    state.quantamentalScoreScreenLoading = false;
    setButtonBusy(els.quantamentalScoreScreenRun, false);
    if (els.quantamentalScoreScreenRun) els.quantamentalScoreScreenRun.textContent = q.buttons.screen;
  }
}

async function quantamentalFetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (_) {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const detail = data.detail?.message || data.detail || data.error || `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function runQuantamentalAnalysis() {
  const request = quantamentalRequestFromControls();
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  if (!request.ticker) {
    if (els.quantamentalStatus) {
      els.quantamentalStatus.textContent = q.messages.tickerRequired;
      els.quantamentalStatus.className = "form-notice error";
    }
    if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = quantamentalUi().error ? quantamentalUi().error(q.messages.tickerRequired) : decisionEmpty(q.messages.tickerRequired);
    return;
  }
  if (els.quantamentalTicker) els.quantamentalTicker.value = request.ticker;
  setQuantamentalLoading(true, selectedOutputLanguage() === "en" ? "Quantamental analysis is calculating." : "Quantamental 분석을 계산하는 중입니다.");
  try {
    const data = await quantamentalFetchJson(API.quantamentalAnalysis(request.ticker, {
      market: request.market,
      period: request.period,
      years: request.years,
      lookback: request.lookback,
      style: request.style,
      includeAi: true,
      useLlm: false,
      outputLanguage: request.output_language,
    }));
    const previousSnapshotId = quantamentalSnapshotId(state.quantamentalAnalysis);
    if (previousSnapshotId && previousSnapshotId !== data?.snapshot?.snapshot_id) {
      state.quantamentalLastSnapshotId = previousSnapshotId;
    }
    state.quantamentalAnalysis = data;
    state.quantamentalLoaded = true;
    renderQuantamentalAnalysis(data);
  } catch (err) {
    const message = err.message || String(err);
    const content = quantamentalUi().error ? quantamentalUi().error(message) : decisionEmpty(message);
    if (els.quantamentalCompanySurface) els.quantamentalCompanySurface.innerHTML = content;
    if (els.quantamentalSignalSurface) els.quantamentalSignalSurface.innerHTML = content;
    if (els.quantamentalStatus) {
      els.quantamentalStatus.textContent = message;
      els.quantamentalStatus.className = "form-notice error";
    }
  } finally {
    setQuantamentalLoading(false);
  }
}

async function refreshQuantamentalAiReport() {
  if (!state.quantamentalAnalysis) {
    await runQuantamentalAnalysis();
    return;
  }
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  setButtonBusy(els.quantamentalAiRefresh, true, "AI", q.buttons.aiReport);
  try {
    const aiOptions = quantamentalAiRequestOptions();
    const report = await quantamentalFetchJson(API.quantamentalAiReport, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        context: state.quantamentalAnalysis,
        use_llm: aiOptions.use_llm,
        model: aiOptions.model,
        output_language: selectedOutputLanguage(),
      }),
    });
    state.quantamentalAnalysis = { ...state.quantamentalAnalysis, ai_report: report };
    state.quantamentalActiveTab = "ai";
    renderQuantamentalAnalysis(state.quantamentalAnalysis);
  } catch (err) {
    if (els.quantamentalMainSurface) els.quantamentalMainSurface.insertAdjacentHTML("afterbegin", `<div class="decision-warning">AI report failed: ${escapeHtml(err.message || err)}</div>`);
  } finally {
    setButtonBusy(els.quantamentalAiRefresh, false);
    if (els.quantamentalAiRefresh) els.quantamentalAiRefresh.textContent = q.buttons.aiReport;
  }
}

async function askQuantamentalQuestion() {
  const questionEl = document.getElementById("quantamentalQuestion");
  const surface = document.getElementById("quantamentalQaSurface");
  const question = String(questionEl?.value || "").trim();
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  if (!question) {
    if (surface) surface.innerHTML = quantamentalUi().error ? quantamentalUi().error(q.messages.questionRequired) : decisionEmpty(q.messages.questionRequired);
    return;
  }
  if (!state.quantamentalAnalysis) {
    if (surface) surface.innerHTML = quantamentalUi().error ? quantamentalUi().error(q.messages.runFirst) : decisionEmpty(q.messages.runFirst);
    return;
  }
  const button = document.getElementById("quantamentalAsk");
  setButtonBusy(button, true, selectedOutputLanguage() === "en" ? "Asking" : "질문 중", q.buttons.ask || "Ask");
  if (surface) surface.innerHTML = quantamentalUi().loading ? quantamentalUi().loading(q.messages.qaLoading) : decisionEmpty(q.messages.qaLoading);
  try {
    const aiOptions = quantamentalAiRequestOptions();
    const answer = await quantamentalFetchJson(API.quantamentalAiQa, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        context: state.quantamentalAnalysis,
        use_llm: aiOptions.use_llm,
        model: aiOptions.model,
        output_language: selectedOutputLanguage(),
      }),
    });
    if (surface) surface.innerHTML = quantamentalUi().qaAnswer ? quantamentalUi().qaAnswer(answer) : `<pre>${escapeHtml(JSON.stringify(answer, null, 2))}</pre>`;
  } catch (err) {
    if (surface) surface.innerHTML = quantamentalUi().error ? quantamentalUi().error(err.message || String(err)) : decisionEmpty(err.message || String(err));
  } finally {
    setButtonBusy(button, false);
  }
}

function quantamentalCompareTickersFromControl() {
  return String(els.quantamentalCompareTickers?.value || "")
    .split(/[\s,]+/)
    .map((item) => normalizeTickerToken(item))
    .filter(Boolean)
    .filter((item, idx, arr) => arr.indexOf(item) === idx)
    .slice(0, 20);
}

function quantamentalPeerLimitFromControl() {
  const value = Number(els.quantamentalPeerLimit?.value || 8);
  return Number.isFinite(value) ? Math.max(2, Math.min(20, value)) : 8;
}

async function loadQuantamentalCompareWatchlists() {
  let loadedFromServer = false;
  try {
    const payload = await quantamentalFetchJson(API.quantamentalCompareWatchlists);
    const items = Array.isArray(payload.items) ? payload.items : [];
    state.quantamentalCompareWatchlists = items
      .filter((item) => item && item.name && Array.isArray(item.tickers))
      .slice(0, 48);
    loadedFromServer = true;
  } catch (_) {
    loadedFromServer = false;
  }
  if (loadedFromServer) {
    renderQuantamentalCompareWatchlists();
    return;
  }
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE.quantamentalCompareWatchlists) || "[]");
    state.quantamentalCompareWatchlists = Array.isArray(parsed) ? parsed.filter((item) => item && item.name && Array.isArray(item.tickers)).slice(0, 20) : [];
  } catch (_) {
    state.quantamentalCompareWatchlists = [];
  }
  renderQuantamentalCompareWatchlists();
}

function persistQuantamentalCompareWatchlists() {
  localStorage.setItem(STORAGE.quantamentalCompareWatchlists, JSON.stringify(state.quantamentalCompareWatchlists || []));
  renderQuantamentalCompareWatchlists();
}

function renderQuantamentalCompareWatchlists() {
  if (!els.quantamentalWatchlistSelect) return;
  const items = Array.isArray(state.quantamentalCompareWatchlists) ? state.quantamentalCompareWatchlists : [];
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  els.quantamentalWatchlistSelect.innerHTML = items.length
    ? items.map((item, idx) => `<option value="${idx}">${escapeHtml(item.name)} (${escapeHtml(String((item.tickers || []).length))})</option>`).join("")
    : `<option value="">${escapeHtml(q.messages.noSavedSets)}</option>`;
}

async function saveQuantamentalCompareWatchlist() {
  const tickers = quantamentalCompareTickersFromControl();
  if (tickers.length < 2) {
    if (els.quantamentalCompareSurface) els.quantamentalCompareSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error("At least two tickers are required to save a comparison set.") : decisionEmpty("At least two tickers are required to save a comparison set.");
    return;
  }
  const name = String(els.quantamentalWatchlistName?.value || tickers.slice(0, 4).join(" ")).trim().slice(0, 40) || "Quantamental Set";
  const request = quantamentalRequestFromControls();
  const payload = {
    name,
    tickers,
    market: request.market,
    style: request.style,
    expand_peer_universe: !!els.quantamentalExpandPeers?.checked,
    peer_limit: quantamentalPeerLimitFromControl(),
  };
  try {
    const saved = await quantamentalFetchJson(API.quantamentalCompareWatchlists, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const item = saved.item || payload;
    const next = (state.quantamentalCompareWatchlists || []).filter((entry) => entry.id !== item.id && entry.name !== item.name);
    next.unshift(item);
    state.quantamentalCompareWatchlists = next.slice(0, 48);
    renderQuantamentalCompareWatchlists();
  } catch (_) {
    const next = (state.quantamentalCompareWatchlists || []).filter((item) => item.name !== name);
    next.unshift({ ...payload, saved_at: new Date().toISOString(), storage: "localStorage_fallback" });
    state.quantamentalCompareWatchlists = next.slice(0, 20);
    persistQuantamentalCompareWatchlists();
  }
}

function loadQuantamentalCompareWatchlist() {
  const idx = Number(els.quantamentalWatchlistSelect?.value || 0);
  const item = (state.quantamentalCompareWatchlists || [])[idx];
  if (!item || !Array.isArray(item.tickers)) return;
  if (els.quantamentalCompareTickers) els.quantamentalCompareTickers.value = item.tickers.join(" ");
  if (els.quantamentalWatchlistName) els.quantamentalWatchlistName.value = item.name || "";
  if (els.quantamentalMarket && item.market) els.quantamentalMarket.value = item.market;
  if (els.quantamentalStyle && item.style) els.quantamentalStyle.value = item.style;
  if (els.quantamentalExpandPeers) els.quantamentalExpandPeers.checked = !!item.expand_peer_universe;
  if (els.quantamentalPeerLimit && item.peer_limit) els.quantamentalPeerLimit.value = String(item.peer_limit);
}

function quantamentalComparisonCsv(data) {
  const rows = Array.isArray(data?.rows) ? data.rows : [];
  const headers = ["ticker", "signal_label", "final_score", "peer_strength", "peer_rank", "peer_group", "quality_level", "sector", "industry"];
  const lines = [headers.join(",")];
  rows.forEach((row) => {
    lines.push([
      row.ticker,
      row.signal_label,
      row.final_score,
      row.peer_relative?.relative_strength_score,
      row.peer_relative?.rank,
      row.peer_relative?.group_key,
      row.quality_level,
      row.sector,
      row.industry,
    ].map(csvCell).join(","));
  });
  return lines.join("\n");
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function exportQuantamentalCompareCsv() {
  if (!state.quantamentalComparison) {
    if (els.quantamentalCompareSurface) els.quantamentalCompareSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error("Run comparison before exporting CSV.") : decisionEmpty("Run comparison before exporting CSV.");
    return;
  }
  const ticker = (state.quantamentalComparison.rows || [])[0]?.ticker || "comparison";
  downloadBlob(`quantamental_compare_${ticker}_${Date.now()}.csv`, quantamentalComparisonCsv(state.quantamentalComparison), "text/csv");
}

function quantamentalSnapshotId(data = state.quantamentalAnalysis) {
  return data?.snapshot?.snapshot_id || "";
}

async function exportQuantamentalSnapshot(format = "json") {
  const snapshotId = quantamentalSnapshotId();
  if (!snapshotId) {
    if (els.quantamentalMainSurface) els.quantamentalMainSurface.insertAdjacentHTML("afterbegin", `<div class="decision-warning">Snapshot is not available yet.</div>`);
    return;
  }
  const res = await fetch(API.quantamentalSnapshotExport(snapshotId, format));
  const text = await res.text();
  if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
  downloadBlob(`quantamental_${snapshotId}.${format}`, text, format === "csv" ? "text/csv" : "application/json");
}

async function diffQuantamentalSnapshot() {
  const snapshotId = quantamentalSnapshotId();
  const previous = state.quantamentalLastSnapshotId;
  if (!snapshotId || !previous || previous === snapshotId) {
    if (els.quantamentalMainSurface) els.quantamentalMainSurface.insertAdjacentHTML("afterbegin", `<div class="decision-warning">Run another analysis snapshot before diffing.</div>`);
    return;
  }
  const diff = await quantamentalFetchJson(API.quantamentalSnapshotDiff(previous, snapshotId));
  if (els.quantamentalMainSurface) {
    els.quantamentalMainSurface.insertAdjacentHTML("afterbegin", quantamentalUi().snapshotDiff ? quantamentalUi().snapshotDiff(diff) : `<pre>${escapeHtml(JSON.stringify(diff, null, 2))}</pre>`);
  }
}

async function previewQuantamentalSnapshotRetention() {
  const ticker = state.quantamentalAnalysis?.ticker || "";
  const preview = await quantamentalFetchJson(API.quantamentalSnapshotRetention({ ticker, keepLast: 5, dryRun: true }), { method: "POST" });
  if (els.quantamentalMainSurface) {
    els.quantamentalMainSurface.insertAdjacentHTML("afterbegin", quantamentalUi().snapshotRetention ? quantamentalUi().snapshotRetention(preview) : `<pre>${escapeHtml(JSON.stringify(preview, null, 2))}</pre>`);
  }
}

async function runQuantamentalCompare() {
  const tickers = quantamentalCompareTickersFromControl();
  const request = quantamentalRequestFromControls();
  if (tickers.length < 2) {
    if (els.quantamentalCompareSurface) {
      els.quantamentalCompareSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error("At least two tickers are required.") : decisionEmpty("At least two tickers are required.");
    }
    return;
  }
  const q = UI_LANGUAGE_COPY[selectedOutputLanguage()]?.quantamental || UI_LANGUAGE_COPY.en.quantamental;
  setButtonBusy(
    els.quantamentalCompareRun,
    true,
    selectedOutputLanguage() === "en" ? "Comparing" : "비교 중",
    q.buttons.compare,
  );
  if (els.quantamentalCompareSurface) {
    els.quantamentalCompareSurface.innerHTML = quantamentalUi().loading ? quantamentalUi().loading(q.messages.compareLoading) : decisionEmpty(q.messages.compareLoading);
  }
  try {
    const data = await quantamentalFetchJson(API.quantamentalCompare, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tickers,
        market: request.market,
        period: request.period,
        years: request.years,
        lookback: request.lookback,
        style: request.style,
        include_ai: false,
        use_llm: false,
        expand_peer_universe: !!els.quantamentalExpandPeers?.checked,
        peer_limit: quantamentalPeerLimitFromControl(),
        output_language: request.output_language,
      }),
    });
    state.quantamentalComparison = data;
    if (els.quantamentalCompareSurface) {
      els.quantamentalCompareSurface.innerHTML = quantamentalUi().comparisonTable ? quantamentalUi().comparisonTable(data) : `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
    }
  } catch (err) {
    if (els.quantamentalCompareSurface) {
      els.quantamentalCompareSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error(err.message || String(err)) : decisionEmpty(err.message || String(err));
    }
  } finally {
    setButtonBusy(els.quantamentalCompareRun, false);
    if (els.quantamentalCompareRun) els.quantamentalCompareRun.textContent = q.buttons.compare;
  }
}

function loadQuantamental(force = false) {
  if (!els.quantamentalMainSurface) return;
  if (!state.quantamentalLoaded || force) {
    renderQuantamentalStarter();
  } else {
    renderQuantamentalAnalysis(state.quantamentalAnalysis);
  }
  loadQuantamentalScreen(force);
}

function loadActiveDashboardResources(force = false) {
  loadDashboardDecisionCards(force);
  if (state.activeDashboardTab === "quant") {
    loadQuantRunHistory(force);
    loadQuantStrategies(force);
    return;
  }
  if (state.activeDashboardTab === "quantamental") {
    loadQuantamental(force);
    return;
  }
  if (state.activeDashboardTab === "forecast") {
    loadForecastLab(force);
    return;
  }
  if (state.activeDashboardTab === "macro") {
    loadMacro(force);
    return;
  }
  if (state.activeDashboardTab === "ai-portfolio") {
    loadAiPortfolio(force);
    return;
  }
  loadMarketDashboard(force);
}

// ---------- History (server-persisted via /api/v1/runs) ----------
async function fetchHistory(ticker) {
  try {
    const qs = new URLSearchParams({ limit: "40" });
    if (ticker) qs.set("ticker", ticker);
    const res = await fetch(`${API.runs}?${qs.toString()}`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.items) ? data.items : [];
  } catch {
    return [];
  }
}

async function renderHistory(filterTicker = null) {
  const items = await fetchHistory(filterTicker);
  els.historyList.innerHTML = "";
  if (els.historySummary) {
    els.historySummary.textContent = items.length ? `${items.length} runs` : "";
  }
  if (els.historyToggleBtn) {
    els.historyToggleBtn.classList.toggle("hidden", items.length <= 5);
    els.historyToggleBtn.textContent = state.historyExpanded ? "접기" : "펼치기";
  }
  if (!items.length) {
    els.historyList.innerHTML = '<li class="history-empty">아직 실행된 분석이 없습니다.</li>';
    return;
  }
  const visibleItems = state.historyExpanded ? items.slice(0, 40) : items.slice(0, 5);
  visibleItems.forEach((item) => {
    const li = document.createElement("li");
    li.className = "history-item";
    const statusCls = statusClass(item.status);
    const whenLocal = item.created_at ? new Date(item.created_at).toLocaleString() : "";
    li.innerHTML = `
      <span class="hi-ticker">${escapeHtml(item.ticker)}</span>
      <span class="hi-time">${escapeHtml(whenLocal)}</span>
      <span class="hi-status ${statusCls}">${escapeHtml(item.status || "")}</span>
    `;
    li.title = item.question || "";
    li.dataset.runId = item.id;
    li.addEventListener("click", () => loadRun(item.id));
    els.historyList.appendChild(li);
  });
  if (!state.historyExpanded && items.length > visibleItems.length) {
    const li = document.createElement("li");
    li.className = "history-more";
    li.textContent = `최근 5개만 표시 중 · ${items.length - visibleItems.length}개 더 있음`;
    els.historyList.appendChild(li);
  }
}

async function loadRun(runId) {
  try {
    const res = await fetch(API.run(runId));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const art = data.artifacts || {};
    if (art.response) {
      renderResponse(art.response, art.collection || null, art.request || null);
      if (art.request) {
        els.ticker.value = art.request.ticker || "";
        els.question.value = art.request.question || "";
      }
      if (art.report_md) {
        els.reportMd.textContent = art.report_md;
      }
      await renderTickerSummary(data.ticker);
    }
  } catch (e) {
    alert("과거 실행 불러오기 실패: " + e.message);
  }
}

// ---------- Watchlist ----------
async function renderWatchlist(options = {}) {
  if (!els.watchlistList) return;
  const force = !!options.force;
  if (!shouldRunBackgroundPoll(force)) return state.watchlistItems;
  if (state.watchlistRequest) return state.watchlistRequest;
  state.watchlistRequest = (async () => {
    try {
      const res = await fetch(API.watchlist);
      if (!res.ok) return state.watchlistItems;
      const data = await res.json();
      const items = data.items || [];

      if (els.watchlistSchedStatus) {
        const sched = data.scheduler || {};
        const running = sched.running ? "on" : "off";
        els.watchlistSchedStatus.textContent = `sched · ${running} · ${sched.runs_triggered ?? 0} runs`;
        els.watchlistSchedStatus.classList.toggle("on", !!sched.running);
      }

      if (items.length === 0) {
        els.watchlistList.innerHTML = `<li class="watchlist-empty">저장된 Watchlist 항목이 없습니다.</li>`;
        state.watchlistItems = [];
        return state.watchlistItems;
      }

      els.watchlistList.innerHTML = items
        .map((it) => {
          const last = it.last_run_at ? timeAgo(it.last_run_at) : "—";
          const status = it.last_run_status
            ? `<span class="status-badge ${statusClass(it.last_run_status)}">${escapeHtml(decisionStatusLabel(it.last_run_status))}</span>`
            : `<span class="status-badge neutral">신규</span>`;
          const interval = it.interval_hours
            ? `<span class="wl-interval">${it.interval_hours}시간마다</span>`
            : `<span class="wl-interval muted">수동</span>`;
          const enabled = it.enabled ? "" : `<span class="wl-paused">일시정지</span>`;
          const err = it.last_run_error
            ? `<div class="wl-error" title="${escapeHtml(it.last_run_error)}">${escapeHtml(it.last_run_error.slice(0, 80))}</div>`
            : "";
          return `
            <li class="watchlist-item" data-id="${escapeHtml(it.id)}">
              <div class="wl-top">
                <div class="wl-ticker">${escapeHtml(it.ticker)}</div>
                ${status}
                ${enabled}
              </div>
              <div class="wl-question" title="${escapeHtml(it.question)}">${escapeHtml(it.question.length > 80 ? it.question.slice(0, 80) + "…" : it.question)}</div>
              <div class="wl-meta">
                ${interval}
                <span class="wl-last">최근: ${last}</span>
                <span class="wl-count">· ${it.run_count || 0}회</span>
              </div>
              ${err}
              <div class="wl-actions">
                <button type="button" class="linkish wl-run" data-id="${escapeHtml(it.id)}" title="지금 실행">실행</button>
                <button type="button" class="linkish wl-load" data-id="${escapeHtml(it.id)}" title="폼에 불러오기">불러오기</button>
                <button type="button" class="linkish wl-toggle" data-id="${escapeHtml(it.id)}" data-enabled="${it.enabled}" title="일시정지/재개">${it.enabled ? "정지" : "재개"}</button>
                <button type="button" class="linkish danger wl-delete" data-id="${escapeHtml(it.id)}" title="삭제">삭제</button>
              </div>
            </li>`;
        })
        .join("");

      state.watchlistItems = items;
      wireWatchlistActions();
      return state.watchlistItems;
    } catch (err) {
      if (els.watchlistList) {
        els.watchlistList.innerHTML = `<li class="watchlist-empty">Watchlist를 불러오지 못했습니다.</li>`;
      }
      if (els.watchlistSchedStatus) {
        els.watchlistSchedStatus.textContent = "sched · 연결 실패";
        els.watchlistSchedStatus.classList.remove("on");
      }
      return state.watchlistItems;
    } finally {
      state.watchlistRequest = null;
    }
  })();
  return state.watchlistRequest;
}

function wireWatchlistActions() {
  els.watchlistList.querySelectorAll(".wl-run").forEach((btn) => {
    btn.addEventListener("click", () => watchlistRunNow(btn.dataset.id));
  });
  els.watchlistList.querySelectorAll(".wl-load").forEach((btn) => {
    btn.addEventListener("click", () => watchlistLoadToForm(btn.dataset.id));
  });
  els.watchlistList.querySelectorAll(".wl-toggle").forEach((btn) => {
    btn.addEventListener("click", () => watchlistToggle(btn.dataset.id, btn.dataset.enabled !== "true"));
  });
  els.watchlistList.querySelectorAll(".wl-delete").forEach((btn) => {
    btn.addEventListener("click", () => watchlistDelete(btn.dataset.id));
  });
}

async function watchlistAddFromForm() {
  const payload = readForm();
  if (!payload.ticker || !payload.question) {
    alert("Ticker / Question 을 먼저 채워주세요.");
    return;
  }
  const intervalStr = prompt(
    "자동 실행 주기 (시간 단위, 비워두면 수동 실행만):",
    ""
  );
  let interval_hours = null;
  if (intervalStr && intervalStr.trim()) {
    const parsed = parseFloat(intervalStr);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      alert("잘못된 주기입니다. 양수 시간 값을 입력하세요.");
      return;
    }
    interval_hours = parsed;
  }
  try {
    const res = await fetch(API.watchlist, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker: payload.ticker,
        question: payload.question,
        sources: payload.sources,
        lookback_days: payload.lookback_days,
        top_k: payload.top_k,
        model: payload.model,
        interval_hours,
        enabled: true,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    await renderWatchlist();
  } catch (err) {
    alert(`Watchlist 저장 실패: ${err.message || err}`);
  }
}

async function watchlistRunNow(id) {
  const btn = els.watchlistList.querySelector(`.wl-run[data-id="${id}"]`);
  if (btn) { btn.disabled = true; btn.textContent = "running…"; }
  try {
    const res = await fetch(`${API.watchlist}/${encodeURIComponent(id)}/run`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    await renderWatchlist();
    await renderHistory();
    if (data.response) {
      renderResponse(data.response, null, {
        ticker: data.response.ticker,
        question: data.response.question,
      });
    }
  } catch (err) {
    alert(`실행 실패: ${err.message || err}`);
    if (btn) { btn.disabled = false; btn.textContent = "run"; }
  }
}

function watchlistLoadToForm(id) {
  const item = (state.watchlistItems || []).find((x) => x.id === id);
  if (!item) return;
  els.ticker.value = item.ticker;
  els.question.value = item.question;
  els.lookback.value = String(item.lookback_days);
  els.topk.value = String(item.top_k);
  els.model.value = item.model;
  els.sourceInputs().forEach((i) => {
    if (i.disabled) return;
    i.checked = (item.sources || []).includes(i.value);
  });
  updateRangeLabels();
  persistForm();
  els.ticker.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function watchlistToggle(id, enable) {
  try {
    const res = await fetch(`${API.watchlist}/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !!enable,
        // Required fields must be echoed back for the request schema; store-side
        // merge preserves everything else.
        ticker: (state.watchlistItems.find(x => x.id === id) || {}).ticker,
        question: (state.watchlistItems.find(x => x.id === id) || {}).question,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    await renderWatchlist();
  } catch (err) {
    alert(`토글 실패: ${err.message || err}`);
  }
}

async function watchlistDelete(id) {
  const item = (state.watchlistItems || []).find((x) => x.id === id);
  if (!item) return;
  if (!confirm(`'${item.ticker}' Watchlist 항목을 삭제하시겠습니까?`)) return;
  try {
    const res = await fetch(`${API.watchlist}/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await renderWatchlist();
  } catch (err) {
    alert(`삭제 실패: ${err.message || err}`);
  }
}

function timeAgo(iso) {
  try {
    const ts = new Date(iso).getTime();
    if (!ts) return "—";
    const diff = (Date.now() - ts) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
  } catch { return "—"; }
}

async function renderTickerSummary(ticker) {
  if (!ticker) { els.tickerSummary?.classList.add("hidden"); return; }
  if (!els.tickerSummary) return;
  try {
    const res = await fetch(API.runSummary(ticker));
    if (!res.ok) { els.tickerSummary.classList.add("hidden"); return; }
    const data = await res.json();
    const points = data.points || [];
    if (!points.length) { els.tickerSummary.classList.add("hidden"); return; }
    els.tickerSummary.classList.remove("hidden");
    renderSparkline(points);
  } catch {
    els.tickerSummary?.classList.add("hidden");
  }
}

function renderSparkline(points) {
  if (!els.sparkline) return;
  const w = 280;
  const h = 86;
  const padLeft = 34;
  const padRight = 8;
  const padTop = 8;
  const padBottom = 16;
  const vals = points.map(p => Number(p.confidence || 0));
  const n = vals.length;
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", h);
  const maxV = Math.max(1, ...vals);
  const minV = 0;
  const yFor = (value) => chartY(minV, maxV, value, h, padTop, padBottom);

  [1, 0.5, 0].forEach((value) => {
    const y = yFor(value);
    const grid = document.createElementNS(svgNS, "line");
    grid.setAttribute("class", "chart-grid-line");
    grid.setAttribute("x1", String(padLeft));
    grid.setAttribute("x2", String(w - padRight));
    grid.setAttribute("y1", y.toFixed(1));
    grid.setAttribute("y2", y.toFixed(1));
    svg.appendChild(grid);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("class", "chart-y-label");
    label.setAttribute("x", String(padLeft - 7));
    label.setAttribute("y", (y + 3).toFixed(1));
    label.setAttribute("text-anchor", "end");
    label.textContent = `${Math.round(value * 100)}%`;
    svg.appendChild(label);
  });

  const axis = document.createElementNS(svgNS, "line");
  axis.setAttribute("class", "chart-axis-line");
  axis.setAttribute("x1", String(padLeft));
  axis.setAttribute("x2", String(padLeft));
  axis.setAttribute("y1", String(padTop));
  axis.setAttribute("y2", String(h - padBottom));
  svg.appendChild(axis);

  if (n >= 2) {
    const step = (w - padLeft - padRight) / (n - 1);
    const path = vals.map((v, i) => {
      const x = padLeft + i * step;
      const y = yFor(v);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const p = document.createElementNS(svgNS, "path");
    p.setAttribute("d", path);
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", "#5ec2a4");
    p.setAttribute("stroke-width", "1.8");
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("stroke-linejoin", "round");
    svg.appendChild(p);
  }

  points.forEach((pt, i) => {
    const confidence = Number(pt.confidence || 0);
    const x = padLeft + (n > 1 ? i * ((w - padLeft - padRight) / (n - 1)) : ((w - padLeft - padRight) / 2));
    const y = yFor(confidence);
    const c = document.createElementNS(svgNS, "circle");
    c.setAttribute("cx", x);
    c.setAttribute("cy", y.toFixed(1));
    c.setAttribute("r", "2.5");
    const tone = (pt.sentiment || "").toLowerCase();
    c.setAttribute("fill", tone.includes("pos") ? "#4ade80" : tone.includes("neg") ? "#f87171" : "#9aa3b2");
    svg.appendChild(c);
    const hit = document.createElementNS(svgNS, "circle");
    const tooltip = `${pt.created_at || pt.run_id || `#${i + 1}`} · 신뢰도 ${fmtDecimal(confidence * 100, 0)}% · ${pt.status || "-"} / ${pt.sentiment || "-"}`;
    hit.setAttribute("class", "chart-hover-point");
    hit.setAttribute("cx", x);
    hit.setAttribute("cy", y.toFixed(1));
    hit.setAttribute("r", "7");
    hit.setAttribute("data-chart-tooltip", tooltip);
    const title = document.createElementNS(svgNS, "title");
    title.textContent = tooltip;
    hit.appendChild(title);
    svg.appendChild(hit);
  });

  els.sparkline.innerHTML = "";
  els.sparkline.appendChild(svg);

  if (els.sparklineLabel) {
    const last = points[points.length - 1];
    els.sparklineLabel.textContent = `최근 ${points.length}회 · 최종 ${last.status}/${last.sentiment}`;
  }
}

// ---------- Stage animation ----------
function progressNode(stage) {
  if (!stage || !els.progressStages) return null;
  return els.progressStages.querySelector(`[data-stage="${stage}"]`);
}

function startStageAnimation() {
  state.stageIndex = 0;
  if (!els.progressStages) return;
  STAGES.forEach((s) => {
    const node = progressNode(s);
    if (!node) return;
    node.classList.remove("active", "done");
  });
  const advance = () => {
    if (state.stageIndex < STAGES.length) {
      STAGES.forEach((s, i) => {
        const node = progressNode(s);
        if (!node) return;
        if (i < state.stageIndex) { node.classList.add("done"); node.classList.remove("active"); }
        else if (i === state.stageIndex) { node.classList.add("active"); node.classList.remove("done"); }
      });
      state.stageIndex++;
    }
  };
  advance();
  // simulated stage progression: Collect=3s, Ingest=2s, Retrieve=2s, Infer=20s+, Analyze=2s, Report=1s
  const delays = [3500, 2200, 2000, 20000, 2500, 1500];
  const tick = () => {
    if (state.stageIndex >= STAGES.length) return;
    state.stageTimer = setTimeout(() => {
      advance();
      tick();
    }, delays[state.stageIndex - 1] || 2000);
  };
  tick();
}

function finishStageAnimation() {
  clearTimeout(state.stageTimer);
  if (!els.progressStages) return;
  STAGES.forEach((s) => {
    const node = progressNode(s);
    if (!node) return;
    node.classList.remove("active");
    node.classList.add("done");
  });
}

function startTimer() {
  state.startedAt = Date.now();
  const tick = () => {
    const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
    const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const ss = String(elapsed % 60).padStart(2, "0");
    els.loadingTimer.textContent = `${mm}:${ss}`;
  };
  tick();
  state.pendingTimer = setInterval(tick, 1000);
}
function stopTimer() {
  clearInterval(state.pendingTimer);
}

function setExportAvailability(enabled) {
  const controls = [
    els.downloadMdBtn,
    els.downloadJsonBtn,
    els.openHtmlBtn,
    document.getElementById("exportToggleBtn"),
  ].filter(Boolean);
  controls.forEach((node) => {
    node.disabled = !enabled;
    node.classList.toggle("disabled", !enabled);
  });
}

async function fetchLatestCollectionArtifact() {
  try {
    const latest = await fetch(API.latest);
    if (!latest.ok) return null;
    const blob = await latest.json();
    return blob.collection || null;
  } catch {
    return null;
  }
}

async function runStreamAnalysis(url, payload, renderRequest) {
  let finalData = null;
  let streamError = null;
  state.activeRequest = renderRequest;
  state.streamHasPartial = false;
  setExportAvailability(false);

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
  });
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try { detail = (await res.json())?.detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }

  for await (const frame of iterSseFrames(res.body)) {
    if (!frame.event) continue;
    handleStreamEvent(frame.event, frame.data);
    if (frame.event === "result") {
      finalData = frame.data;
    } else if (frame.event === "pipeline_failed") {
      streamError = frame.data?.reason || "Pipeline failed";
    }
  }

  if (streamError && !finalData) {
    throw new Error(streamError);
  }
  if (!finalData) {
    throw new Error(formMessage("streamNoResult"));
  }

  if (finalData.mode === "multi_ticker") {
    renderCompareResponse(finalData);
  } else {
    renderResponse(finalData, null, renderRequest);
    fetchLatestCollectionArtifact().then((collection) => {
      if (!collection || state.lastResponse !== finalData) return;
      state.lastCollection = collection;
      renderDiagnostics(renderRequest, collection);
    }).catch(() => {});
  }
}

// ---------- Run analysis ----------
async function runAnalysis(e) {
  e.preventDefault();
  const payload = readForm();
  setFormNotice("");

  const requiresTicker = payload.compare || payload.mode_hint === "ticker";
  if (requiresTicker && !payload.ticker) {
    els.ticker.focus();
    setFormNotice(formMessage("tickerRequired"), "warning");
    return;
  }
  if (!payload.question) {
    els.question.focus();
    setFormNotice(formMessage("questionRequired"), "warning");
    return;
  }
  if (payload.sources.length === 0) {
    setFormNotice(formMessage("sourceRequired"), "warning");
    return;
  }

  if (payload.compare) {
    if (payload.tickers.length < 2) {
      setFormNotice(formMessage("compareRequired"), "warning");
      els.ticker.focus();
      return;
    }
    persistForm();
    await runCompare(payload);
    return;
  }

  persistForm();
  if (payload.stale_ticker_ignored) {
    const proxies = Array.isArray(payload.topic_related_tickers) && payload.topic_related_tickers.length
      ? ` 관련 프록시: ${payload.topic_related_tickers.join(", ")}.`
      : "";
    setFormNotice(`${payload.stale_ticker_ignored}는 질문에 직접 언급되지 않아 ${payload.topic_hint || "주제"} 분석으로 처리합니다.${proxies}`, "info");
  }
  setLoading(true, payload.ticker || "TOPIC");
  if (payload.stale_ticker_ignored) {
    const topicTickers = Array.isArray(payload.topic_related_tickers) && payload.topic_related_tickers.length
      ? ` 관련 프록시: ${payload.topic_related_tickers.join(", ")}.`
      : "";
    els.loadingSub.textContent = `${payload.stale_ticker_ignored}는 질문에 직접 언급되지 않아 주제 분석으로 처리합니다.${topicTickers}`;
  } else if (payload.extracted_ticker) {
    els.loadingSub.textContent = `질문에서 ${payload.extracted_ticker} 티커를 감지했습니다. Universal 라우터로 경로를 판별합니다.`;
  }
  try {
    await runStreamAnalysis(API.universalStream, payload, payload);
    renderHistory();
    if (payload.ticker && !payload.compare) renderTickerSummary(payload.ticker);
  } catch (err) {
    console.error(err);
    renderFailure(payload, err.message || String(err));
  } finally {
    state.activeRequest = null;
    setLoading(false);
  }
}

// ---------- Compare mode ----------
async function runCompare(payload) {
  // Compare mode owns the full-page state; wipe any prior single-run so the
  // post-compare setLoading(false) call doesn't flash the old result back in.
  state.lastResponse = null;
  state.lastCollection = null;
  state.lastRequest = null;
  setLoading(true, payload.tickers.join(", "));
  els.loadingSub.textContent = `${payload.tickers.length}개 티커 동시 분석 중…`;
  resetProgressStages();

  try {
    const body = {
      tickers: payload.tickers,
      question: payload.question,
      sources: payload.sources,
      lookback_days: payload.lookback_days,
      top_k: payload.top_k,
      model: payload.model,
      output_language: payload.output_language,
      concurrency: 2,
    };
    const res = await fetch(API.compare, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.detail || `HTTP ${res.status}`);
    }
    // Hide loading/empty, then reveal the compare view without touching
    // resultView visibility.
    els.loadingState.classList.add("hidden");
    els.emptyState.classList.add("hidden");
    els.runBtn.disabled = false;
    els.runBtn.classList.remove("loading");
    stopTimer();
    finishStageAnimation();
    renderCompareResponse(data);
    renderHistory();
  } catch (err) {
    console.error(err);
    renderFailure({ ticker: payload.tickers.join(","), question: payload.question }, err.message || String(err));
    setLoading(false);
  }
}

function renderCompareResponse(data) {
  state.lastResponse = null;
  state.lastCollection = null;
  state.lastRequest = null;
  setExportAvailability(false);

  els.emptyState.classList.add("hidden");
  els.loadingState.classList.add("hidden");
  els.resultView.classList.add("hidden");
  els.compareView.classList.remove("hidden");

  const results = data.results || {};
  const tickers = data.tickers || Object.keys(results);

  els.compareMeta.textContent = `${tickers.length} tickers · ${data.elapsed_s ?? "?"}s · concurrency=${data.concurrency ?? 1}`;

  // Side-by-side metric table
  const rows = [
    { label: "Status", cell: (r) => `<span class="status-badge ${statusClass(r.status)}">${(r.status || "").toUpperCase()}</span>` },
    { label: "Sentiment", cell: (r) => r.sentiment || "—" },
    { label: "Confidence", cell: (r) => (r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "—") },
    { label: "Bull / Bear", cell: (r) => `${(r.bull_points || []).length} / ${(r.bear_points || []).length}` },
    { label: "Citations", cell: (r) => (r.citations || []).length },
    { label: "Latency", cell: (r) => (r.execution_meta?.pipeline_latency_s != null ? `${r.execution_meta.pipeline_latency_s}s` : "—") },
    { label: "Producing model", cell: (r) => r.execution_meta?.producing_model || "—" },
  ];
  const header = `<thead><tr><th></th>${tickers.map((t) => {
    const r = results[t] || {};
    const label = compareSymbolDisplay(t, r);
    return `<th><span class="compare-symbol">${escapeHtml(t)}</span><small>${escapeHtml(label)}</small></th>`;
  }).join("")}</tr></thead>`;
  const bodyHtml = rows
    .map((row) => {
      const cells = tickers
        .map((t) => {
          const r = results[t] || {};
          return `<td>${row.cell(r)}</td>`;
        })
        .join("");
      return `<tr><th>${row.label}</th>${cells}</tr>`;
    })
    .join("");
  els.compareTable.innerHTML = `<table class="compare-grid">${header}<tbody>${bodyHtml}</tbody></table>`;

  // Summaries — one card per ticker
  const cards = tickers.map((t) => {
    const r = results[t] || {};
    const err = r.error_metadata ? `<div class="compare-error">${escapeHtml(r.error_metadata)}</div>` : "";
    const bull = (r.bull_points || []).slice(0, 3).map((b) => `<li>${escapeHtml(b)}</li>`).join("");
    const bear = (r.bear_points || []).slice(0, 3).map((b) => `<li>${escapeHtml(b)}</li>`).join("");
    const label = compareSymbolDisplay(t, r);
    const metrics = renderCompareMetricChips(r);
    return `
      <div class="compare-card ${statusClass(r.status)}">
        <div class="compare-card-head">
          <h4><span>${escapeHtml(t)}</span><small>${escapeHtml(label)}</small></h4>
          <span class="status-badge ${statusClass(r.status)}">${(r.status || "").toUpperCase()}</span>
        </div>
        ${err}
        ${metrics}
        <p class="compare-summary">${escapeHtml(r.summary || "—")}</p>
        <div class="compare-sides">
          <div class="compare-side bull"><h5>Bull</h5><ul>${bull || "<li class='muted'>—</li>"}</ul></div>
          <div class="compare-side bear"><h5>Bear</h5><ul>${bear || "<li class='muted'>—</li>"}</ul></div>
        </div>
        <p class="compare-conclusion">${escapeHtml(r.conclusion || "")}</p>
      </div>`;
  });
  els.compareSummaries.innerHTML = cards.join("");
}

function compareSymbolDisplay(ticker, response = {}) {
  const symbol = normalizeTickerToken(ticker);
  const snapshots = response.execution_meta?.extras?.structured_context?.price_snapshot || [];
  const exact = snapshots.find((row) => normalizeTickerToken(row.ticker) === symbol) || snapshots[0] || null;
  if (exact?.display_name) return exact.display_name;
  const catalog = SYMBOL_CATALOG.find((item) => item.symbol === symbol);
  return catalog?.name || SYMBOL_NAME_OVERRIDES[symbol] || symbol;
}

function compareMetricLabel(metric) {
  const name = String(metric?.name || "").toLowerCase();
  if (name.includes("adjusted close")) return "기준 종가";
  if (name.includes("21d_pct")) return "1개월 수익률";
  if (name.includes("63d_pct")) return "3개월 수익률";
  if (name.includes("1d_pct")) return "1일 수익률";
  if (name.includes("realized_vol_20d_pct")) return "20일 변동성";
  return "";
}

function renderCompareMetricChips(response = {}) {
  const seen = new Set();
  const chips = (response.key_metrics || [])
    .map((metric) => {
      const label = compareMetricLabel(metric);
      if (!label || seen.has(label)) return "";
      seen.add(label);
      const unit = metric.unit && metric.unit !== "price" ? metric.unit : "";
      const asOf = metric.as_of && metric.as_of !== "unknown" ? ` · ${metric.as_of}` : "";
      return `
        <span class="compare-metric-chip">
          <em>${escapeHtml(label)}</em>
          <strong>${escapeHtml(String(metric.value ?? "—"))}${escapeHtml(unit)}</strong>
          <small>${escapeHtml(asOf.replace(/^ · /, ""))}</small>
        </span>`;
    })
    .filter(Boolean)
    .slice(0, 5);
  return chips.length ? `<div class="compare-metric-chips">${chips.join("")}</div>` : "";
}

function updateCompareModeUI() {
  const on = !!(els.compareMode && els.compareMode.checked);
  const mode = Array.from(els.researchModeInputs()).find((i) => i.checked)?.value || "auto";
  if (!els.ticker) return;
  const placeholder = on
    ? "AAPL, MSFT, NVDA"
    : mode === "topic"
      ? "선택: TLT, GLD, BTC-USD"
      : mode === "ticker"
        ? "필수: AAPL"
        : "선택: TLT, GLD, BTC-USD 또는 AAPL";
  els.ticker.placeholder = placeholder;
  if (els.tickerHint) {
    els.tickerHint.textContent = on
      ? "쉼표/공백으로 2-5개 티커 구분"
      : mode === "topic"
        ? "ticker 없이 질의 가능, ticker는 참고 힌트"
        : mode === "ticker"
          ? "종목 분석은 ticker 필수"
          : "ticker 선택 입력, 비워두면 주제/거시 질의";
  }
  // Swap chip behavior: in compare mode chips append with a comma rather than replace.
  els.ticker.dataset.mode = on ? "compare" : "single";
}

// ---------- SSE helpers ----------
async function* iterSseFrames(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const frame = parseSseFrame(raw);
        if (frame) yield frame;
      }
    }
  } finally {
    try { reader.releaseLock(); } catch { /* ignore */ }
  }
}

function parseSseFrame(raw) {
  if (!raw || raw.startsWith(":")) return null;
  let event = "message";
  const dataLines = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  const payload = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(payload) };
  } catch {
    return { event, data: payload };
  }
}

function handleStreamEvent(event, data) {
  if (event === "stream_open") {
    state.streamStartedAt = Date.now();
    state.streamHasPartial = false;
    resetProgressStages();
    setExportAvailability(false);
    return;
  }
  if (event === "stage_started") {
    markStageActive(data?.stage);
    const substatus = describeStageStart(data);
    if (substatus) els.loadingSub.textContent = substatus;
    return;
  }
  if (event === "stage_completed") {
    markStageDone(data?.stage, data);
    const substatus = describeStageDone(data);
    if (substatus) els.loadingSub.textContent = substatus;
    return;
  }
  if (event === "pipeline_completed") {
    finishStageAnimation();
    els.loadingSub.textContent = `최종 정리 완료 · ${data?.elapsed_s ?? "?"}s`;
    return;
  }
  if (event === "partial_result") {
    state.streamHasPartial = true;
    const payload = data?.payload || data;
    if (payload && typeof payload === "object") {
      renderResponse(payload, state.lastCollection, state.activeRequest || state.lastRequest);
    }
    els.loadingSub.textContent = "초기 판단 생성 완료 · 심화 보강 중";
    return;
  }
  if (event === "pipeline_failed") {
    els.loadingSub.textContent = `실패: ${data?.reason || "unknown"}`;
    return;
  }
}

function resetProgressStages() {
  if (!els.progressStages) return;
  STAGES.forEach((s) => {
    const node = progressNode(s);
    if (node) node.classList.remove("active", "done");
  });
}

function markStageActive(stage) {
  const node = progressNode(stage);
  if (!node) return;
  els.progressStages.querySelectorAll("[data-stage].active").forEach((n) => n.classList.remove("active"));
  node.classList.add("active");
  node.classList.remove("done");
}

function markStageDone(stage, data) {
  const node = progressNode(stage);
  if (!node) return;
  node.classList.remove("active");
  node.classList.add("done");
  if (data?.status && data.status !== "ok") {
    node.classList.add("warn");
  }
}

function describeStageStart(data) {
  const s = data?.stage;
  if (!s) return "";
  const map = {
    collect: "관련 문서 수집 중",
    ingest: `벡터 DB 적재 중 (${data.documents ?? 0} docs)`,
    retrieve: `컨텍스트 검색 중 (top_k=${data.top_k ?? "?"})`,
    infer: `LLM 추론 중 (${data.chunks ?? 0} chunks)`,
    analyze: "분석 결과 정리 중",
    report: "리포트 생성 중",
    output: "산출물 저장 중",
  };
  return map[s] || `${s} 진행 중`;
}

function describeStageDone(data) {
  const s = data?.stage;
  if (!s) return "";
  const dur = data.duration_s != null ? `${data.duration_s}s` : "";
  const extras = [];
  if (s === "collect") {
    if (data.cache_hit) extras.push(`cache ${formatAge(data.cache_age_s)}`);
    if (data.documents != null) extras.push(`${data.documents} docs`);
    if ((data.degraded_sources || []).length) extras.push(`degraded: ${data.degraded_sources.join(", ")}`);
  } else if (s === "retrieve" && data.chunks != null) {
    extras.push(`${data.chunks} chunks`);
  } else if (s === "analyze" && data.sentiment) {
    extras.push(`${data.sentiment}${data.confidence != null ? ` ${Math.round(data.confidence * 100)}%` : ""}`);
  }
  const extraStr = extras.length ? ` · ${extras.join(" · ")}` : "";
  return `${s} 완료${dur ? ` · ${dur}` : ""}${extraStr}`;
}

function setLoading(isLoading, ticker) {
  els.emptyState.classList.toggle("hidden", true);
  els.loadingState.classList.toggle("hidden", !isLoading);
  els.resultView.classList.toggle("hidden", isLoading || !state.lastResponse);
  if (els.compareView) els.compareView.classList.toggle("hidden", isLoading || state.lastResponse !== null);
  els.runBtn.disabled = isLoading;
  els.runBtn.classList.toggle("loading", isLoading);
  if (isLoading) {
    setExportAvailability(false);
    els.loadingTicker.textContent = ticker || "분석 중";
    els.loadingSub.textContent = "스트림 연결 중";
    startTimer();
    resetProgressStages();
  } else {
    stopTimer();
    finishStageAnimation();
  }
}

// ---------- Render ----------
function cleanLine(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function normalizeProseLines(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim());
}

function isProseHeading(line) {
  return /^(핵심 분석|핵심 지표|Synthesis|Decision Edge|결론|요약|상방 동인|하방 리스크|관련 종목|관련 자산|불확실성|투자 판단|시장 가격|시나리오 분석|실행 전략)$/i.test(line)
    || /^\(\d+\)\s+/.test(line)
    || /^#{1,6}\s+/.test(line);
}

function compactProseLines(lines) {
  const out = [];
  (Array.isArray(lines) ? lines : []).forEach((line) => {
    const text = String(line ?? "");
    if (!text.trim()) {
      if (out.length && out[out.length - 1] !== "") out.push("");
      return;
    }
    out.push(text.trim());
  });
  while (out.length && out[0] === "") out.shift();
  while (out.length && out[out.length - 1] === "") out.pop();
  return out;
}

function joinProseLines(lines) {
  return compactProseLines(lines).join("\n");
}

function renderProse(container, value, fallback = "—") {
  if (!container) return;
  const lines = compactProseLines(normalizeProseLines(value));
  container.innerHTML = "";
  if (!lines.length) {
    const p = document.createElement("p");
    p.className = "prose-paragraph muted";
    p.textContent = fallback;
    container.appendChild(p);
    return;
  }

  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const p = document.createElement("p");
    p.className = "prose-paragraph";
    p.textContent = paragraph.join(" ");
    container.appendChild(p);
    paragraph = [];
  };

  const closeList = () => {
    list = null;
  };

  lines.forEach((line) => {
    if (!line) {
      flushParagraph();
      closeList();
      return;
    }
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (!list) {
        list = document.createElement("ul");
        list.className = "prose-list";
        container.appendChild(list);
      }
      const li = document.createElement("li");
      li.textContent = bullet[1].trim();
      list.appendChild(li);
      return;
    }
    closeList();
    if (isProseHeading(line)) {
      flushParagraph();
      const heading = document.createElement("h4");
      heading.className = "prose-heading";
      heading.textContent = line.replace(/^#{1,6}\s+/, "");
      container.appendChild(heading);
      return;
    }
    paragraph.push(line);
  });
  flushParagraph();
}

function dedupeKey(value) {
  return cleanLine(value).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

function uniqueTextItems(items) {
  const out = [];
  const seen = new Set();
  (Array.isArray(items) ? items : []).forEach((item) => {
    const text = cleanLine(item);
    if (!text) return;
    const key = dedupeKey(text);
    if (key && seen.has(key)) return;
    if (key) seen.add(key);
    out.push(text);
  });
  return out;
}

function dedupeReportLines(lines) {
  const keepRepeat = /^(핵심 분석|Synthesis|Decision Edge|결론|상방 동인|하방 리스크|관련 종목|관련 자산|불확실성|\(\d+\)|요약|상승 촉매|하락 촉매|투자 판단)/i;
  const seen = new Set();
  return (Array.isArray(lines) ? lines : []).filter((line) => {
    const text = cleanLine(line);
    if (!text) return true;
    if (keepRepeat.test(text) || text === "") return true;
    const key = dedupeKey(text.replace(/^-+\s*/, "").replace(/^결론:\s*/, ""));
    if (!key) return true;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function listLines(items, emptyText = "식별된 항목 없음") {
  const values = uniqueTextItems((Array.isArray(items) ? items : [])
    .map((item) => cleanLine(typeof item === "string" ? item : item?.text || item))
    .filter(Boolean));
  return values.length ? values.map((item) => `- ${item}`) : [`- ${emptyText}`];
}

function formatMetricLine(metric) {
  if (!metric) return "";
  const name = cleanLine(metric.name);
  const value = cleanLine(metric.value);
  if (!name || !value) return "";
  const context = cleanLine(metric.context);
  const asOf = cleanLine(metric.as_of || metric.asOf);
  const unit = cleanLine(metric.unit);
  const source = cleanLine(metric.source);
  const asOfText = asOf || "기준일 미확인";
  const sourceText = source ? ` · 출처: ${source}` : "";
  return `${name}: ${value}${unit ? ` ${unit}` : ""} [기준일: ${asOfText}${sourceText}]${context ? ` (${context})` : ""}`;
}

function metricLines(metrics) {
  return listLines(
    (Array.isArray(metrics) ? metrics : []).map(formatMetricLine).filter(Boolean),
    "정량 지표가 추출되지 않았습니다."
  );
}

function compactMetricLine(metric) {
  const name = cleanLine(metric?.name);
  const value = cleanLine(metric?.value);
  if (!name || !value) return "";
  const unit = cleanLine(metric?.unit);
  const asOf = cleanLine(metric?.as_of || metric?.asOf) || "기준일 미확인";
  const source = cleanLine(metric?.source);
  return `${name} ${value}${unit ? ` ${unit}` : ""} · ${asOf}${source ? ` · ${source}` : ""}`;
}

function buildTopicHeadlineSummary(data) {
  const risks = (data.key_risks || []).map((x) => cleanLine(x.text || x)).filter(Boolean).slice(0, 3);
  const drivers = (data.key_drivers || []).map((x) => cleanLine(x.text || x)).filter(Boolean).slice(0, 2);
  const scenarioCount = Array.isArray(data.scenario_analysis) ? data.scenario_analysis.length : 0;
  const lines = [];
  if (data.executive_summary || data.summary) lines.push(cleanLine(data.executive_summary || data.summary));
  if (risks.length) lines.push(`핵심 리스크: ${risks.join(" / ")}`);
  if (drivers.length) lines.push(`확인할 상방 동인: ${drivers.join(" / ")}`);
  if (scenarioCount) lines.push(`시나리오 ${scenarioCount}개와 실행 전략 ${(data.execution_strategy || []).length}개를 기준으로 의사결정을 분해했습니다.`);
  return uniqueTextItems(lines).join("\n");
}

function buildTopicDecisionMemo(data, ...sections) {
  const lines = [];
  sections.filter(Boolean).forEach((section, index) => {
    if (index > 0) lines.push("");
    lines.push(section);
  });
  return joinProseLines(dedupeReportLines(lines));
}

function renderMetricTable(metrics) {
  if (!els.metricsTable) return;
  const rows = Array.isArray(metrics) ? metrics.filter((m) => m && cleanLine(m.name) && cleanLine(m.value)) : [];
  els.metricsTable.innerHTML = "";
  if (!rows.length) {
    els.metricsTable.innerHTML = `<div class="metric-empty">정량 지표가 추출되지 않았습니다.</div>`;
    return;
  }
  const evidenceIndex = buildEvidenceIndex(state.evidenceRaw);
  const table = document.createElement("table");
  table.className = "metric-table";
  table.innerHTML = `
    <thead><tr><th>지표</th><th>값</th><th>단위</th><th>기준일</th><th>출처</th><th>상태</th><th>맥락</th><th>근거</th></tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  rows.forEach((metric) => {
    const tr = document.createElement("tr");
    const docIds = Array.isArray(metric.evidence_doc_ids) ? metric.evidence_doc_ids : [];
    const evidenceTd = document.createElement("td");
    evidenceTd.className = "metric-evidence";
    if (docIds.length) {
      docIds.forEach((docId) => {
        const item = evidenceIndex.get(String(docId));
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "evidence-chip metric-chip";
        chip.textContent = item
          ? `${truncateLabel(docId, 10)} · ${item.date || "unknown"}`
          : `doc ${truncateLabel(docId, 10)}`;
        chip.title = item ? `${item.source || "doc"} · ${item.date || "unknown"}\n${item.title || docId}` : `doc_id: ${docId}`;
        chip.addEventListener("click", () => jumpToEvidence(docId));
        evidenceTd.appendChild(chip);
      });
    } else {
      evidenceTd.textContent = "근거 링크 없음";
      evidenceTd.className = "metric-evidence muted";
    }
    [
      metric.name,
      metric.value,
      metric.unit || "",
      metric.as_of || "unknown",
      metric.source || "",
      [metric.freshness_status || "unknown", metric.grounding_status || ""].filter(Boolean).join(" / "),
      metric.context || "",
    ].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = cleanLine(value) || "—";
      tr.appendChild(td);
    });
    tr.appendChild(evidenceTd);
    tbody.appendChild(tr);
  });
  els.metricsTable.appendChild(table);
}

function normalizeTextItem(item, fallback = "") {
  if (typeof item === "string") return cleanLine(item);
  if (!item || typeof item !== "object") return fallback;
  return cleanLine(item.text || item.title || item.scenario || item.strategy || item.conclusion || item.expected_outcome || fallback);
}

function renderDocBadges(container, docIds) {
  const ids = Array.isArray(docIds) ? docIds.filter(Boolean) : [];
  if (!ids.length) {
    const note = document.createElement("span");
    note.className = "evidence-note";
    note.textContent = "근거 링크 없음";
    container.appendChild(note);
    return;
  }
  const evidenceIndex = buildEvidenceIndex(state.evidenceRaw);
  ids.forEach((docId) => {
    const item = evidenceIndex.get(String(docId));
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "evidence-chip metric-chip";
    chip.textContent = item
      ? `${truncateLabel(docId, 10)} · ${item.date || "unknown"}`
      : `doc ${truncateLabel(docId, 10)}`;
    chip.title = item ? `${item.source || "doc"} · ${item.date || "unknown"}\n${item.title || docId}` : `doc_id: ${docId}`;
    chip.addEventListener("click", () => jumpToEvidence(docId));
    container.appendChild(chip);
  });
}

function getQuantMetrics(data, snapshot = null) {
  const snap = snapshot || data?.execution_meta?.extras?.quant_snapshot || {};
  const snapMetrics = Array.isArray(snap.metrics) ? snap.metrics : [];
  const keyMetrics = Array.isArray(data?.key_metrics) ? data.key_metrics : [];
  return snapMetrics.length ? snapMetrics : keyMetrics;
}

function metricSearchText(metric) {
  return [
    metric?.name,
    metric?.context,
    metric?.source,
    metric?.unit,
  ].filter(Boolean).join(" ").toLowerCase();
}

function findMetric(metrics, needles) {
  const terms = Array.isArray(needles) ? needles : [needles];
  const lowered = terms.map((term) => String(term || "").toLowerCase()).filter(Boolean);
  return (metrics || []).find((metric) => lowered.some((term) => metricSearchText(metric).includes(term))) || null;
}

function parseMetricNumber(metric) {
  const value = metric?.value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const match = String(value ?? "").replace(/,/g, "").match(/[+-]?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function formatMetricValue(metric) {
  if (!metric) return "—";
  const raw = cleanLine(metric.value);
  const unit = cleanLine(metric.unit || "");
  if (!raw) return "—";
  if (unit === "%" && !String(raw).includes("%")) return `${raw}%`;
  if (unit && unit !== "price" && unit !== "index" && !String(raw).includes(unit)) return `${raw} ${unit}`;
  return raw;
}

function metricDocIds(metric) {
  return Array.isArray(metric?.evidence_doc_ids) ? metric.evidence_doc_ids.filter(Boolean) : [];
}

function cleanTextArray(value) {
  if (Array.isArray(value)) return value.map((item) => cleanLine(item)).filter(Boolean);
  const single = cleanLine(value);
  return single ? [single] : [];
}

function collectMetricDocIds(metrics, patterns, fallback = []) {
  const ids = [];
  (patterns || []).forEach((pattern) => {
    ids.push(...metricDocIds(findMetric(metrics, pattern)));
  });
  if (!ids.length && Array.isArray(fallback)) ids.push(...fallback.filter(Boolean));
  return Array.from(new Set(ids.map(String))).slice(0, 4);
}

function buildQuantRegime(metrics, data) {
  const extras = data?.execution_meta?.extras || {};
  const snapshot = extras.quant_snapshot || {};
  const snapshotRegime = snapshot.regime || {};
  const latest = findMetric(metrics, ["최신 종가", "latest close"]);
  const momentum1m = findMetric(metrics, ["1개월 가격 모멘텀", "1m momentum"]);
  const momentum3m = findMetric(metrics, ["3개월 가격 모멘텀", "3m momentum"]);
  const sma20 = findMetric(metrics, ["sma20"]);
  const sma50 = findMetric(metrics, ["sma50"]);
  const sma200 = findMetric(metrics, ["sma200"]);
  const rsi = findMetric(metrics, ["rsi"]);
  const macd = findMetric(metrics, ["macd"]);
  const volatility = findMetric(metrics, ["실현 변동성", "realized volatility"]);
  const volume = findMetric(metrics, ["평균 대비 거래량", "volume"]);

  const m1 = parseMetricNumber(momentum1m);
  const m3 = parseMetricNumber(momentum3m);
  const d20 = parseMetricNumber(sma20);
  const d50 = parseMetricNumber(sma50);
  const d200 = parseMetricNumber(sma200);
  const rsiValue = parseMetricNumber(rsi);
  const macdValue = parseMetricNumber(macd);
  const volValue = parseMetricNumber(volatility);
  const volRatio = parseMetricNumber(volume);

  let trendTitle = "가격 레짐 판단 보류";
  if (m1 !== null || d20 !== null || d50 !== null || d200 !== null) {
    const shortPositive = (m1 ?? 0) > 0 && (d20 ?? 0) > 0 && (d50 ?? 0) > 0;
    const longConfirmed = (d200 ?? 0) > 0;
    const mediumWeak = (m3 ?? 0) < 0 || (d200 ?? 0) < 0;
    if (shortPositive && longConfirmed) trendTitle = "상승 추세 우위";
    else if (shortPositive && mediumWeak) trendTitle = "단기 반등 우위, 장기 추세 검증 필요";
    else if ((m1 ?? 0) < 0 && (d20 ?? 0) < 0) trendTitle = "하락 모멘텀 우위";
    else trendTitle = "혼조 레짐";
  }

  let momentumTitle = "모멘텀 신호 제한";
  if (rsiValue !== null || macdValue !== null) {
    if ((rsiValue ?? 50) >= 70 && (macdValue ?? 0) > 0) momentumTitle = "상승 모멘텀은 강하지만 과열 리스크 존재";
    else if ((rsiValue ?? 50) <= 30) momentumTitle = "침체권 반등 후보";
    else if ((macdValue ?? 0) > 0) momentumTitle = "모멘텀 개선 구간";
    else if ((macdValue ?? 0) < 0) momentumTitle = "모멘텀 둔화 구간";
  }

  let riskTitle = "리스크 신호 추가 확인 필요";
  if ((rsiValue ?? 0) >= 70 || (volValue ?? 0) >= 35 || (d200 ?? 0) < 0) {
    riskTitle = "추격 매수보다 확인 매수가 유리한 리스크 구조";
  } else if ((m1 ?? 0) > 0 && (macdValue ?? 0) > 0) {
    riskTitle = "상방 추세 유지 가능성이 있으나 이벤트 확인 필요";
  }

  const evidenceFallback = Array.isArray(data?.cited_doc_ids) ? data.cited_doc_ids : [];
  const importantMetrics = [latest, momentum1m, momentum3m, sma20, sma50, sma200, rsi, macd, volatility, volume].filter(Boolean);
  const signalLine = importantMetrics.slice(0, 4).map((metric) => `${cleanLine(metric.name)} ${formatMetricValue(metric)}`).join(" · ");
  const confirmingLine = cleanTextArray(snapshotRegime.confirming_signals).slice(0, 4).join(" · ");
  const invalidationLine = cleanTextArray(snapshotRegime.invalidation_signals).slice(0, 4).join(" · ");
  const snapshotFreshness = snapshot.freshness_status || snapshot.data_freshness || "";
  const biasBody = [
    signalLine ? `핵심 지표: ${signalLine}` : "",
    confirmingLine ? `확인 신호: ${confirmingLine}` : "",
    invalidationLine ? `무효화/주의 신호: ${invalidationLine}` : "",
    snapshotFreshness ? `신선도: ${snapshotFreshness}` : "",
  ].filter(Boolean).join(" ");

  return {
    cards: [
      {
        label: "Bias",
        title: cleanLine(snapshotRegime.decision_bias) || trendTitle,
        body: biasBody || "가격, 추세, 변동성 지표가 충분하지 않아 레짐을 보수적으로 해석해야 합니다.",
        docIds: collectMetricDocIds(metrics, [["1개월 가격 모멘텀"], ["sma20"], ["sma50"], ["sma200"]], evidenceFallback),
      },
      {
        label: "Momentum",
        title: momentumTitle,
        body: [
          rsi ? `RSI(14) ${formatMetricValue(rsi)}는 단기 과열/침체 여부를 판단하는 핵심 신호입니다.` : "",
          macd ? `MACD 히스토그램 ${formatMetricValue(macd)}는 추세 가속 또는 둔화를 확인하는 보조 신호입니다.` : "",
        ].filter(Boolean).join(" "),
        docIds: collectMetricDocIds(metrics, [["rsi"], ["macd"]], evidenceFallback),
      },
      {
        label: "Risk",
        title: riskTitle,
        body: [
          volatility ? `20일 실현 변동성 ${formatMetricValue(volatility)}를 기준으로 포지션 크기와 손절 폭을 조정해야 합니다.` : "",
          volume ? `거래량 신호 ${formatMetricValue(volume)}는 가격 움직임의 신뢰도를 검증하는 데 사용합니다.` : "",
          (d200 ?? 0) < 0 ? "SMA200 아래에 머무르면 장기 추세가 완전히 복원됐다고 보기 어렵습니다." : "",
        ].filter(Boolean).join(" ") || "현재 지표만으로는 리스크 강도를 단정하기 어렵습니다.",
        docIds: collectMetricDocIds(metrics, [["실현 변동성"], ["volume"], ["sma200"]], evidenceFallback),
      },
      {
        label: "Decision Read",
        title: data?.sentiment ? `${data.sentiment} · confidence ${data.confidence ?? "—"}` : "정량 판단",
        body: "정량 판단은 방향성보다 조건부 의사결정에 초점을 둡니다. 추세 지속은 모멘텀 유지와 거래량 확인이 필요하고, 과열 신호가 있으면 분할 진입과 손절 기준을 먼저 정해야 합니다.",
        docIds: collectMetricDocIds(metrics, [["최신 종가"], ["1개월 가격 모멘텀"], ["rsi"]], evidenceFallback),
      },
    ],
  };
}

function renderQuantRegime(data, metrics) {
  if (!metrics.length) return null;
  const regime = buildQuantRegime(metrics, data);
  const section = document.createElement("section");
  section.className = "quant-section quant-regime-section";
  section.innerHTML = `<h4>Quant Regime & Decision Read</h4>`;
  const grid = document.createElement("div");
  grid.className = "quant-regime-grid";
  regime.cards.forEach((item) => {
    const card = document.createElement("article");
    card.className = "quant-regime-card";
    card.innerHTML = `
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <p>${escapeHtml(item.body || "판단 근거가 제한적입니다.")}</p>
    `;
    const badges = document.createElement("div");
    badges.className = "evidence-chips";
    renderDocBadges(badges, item.docIds || []);
    card.appendChild(badges);
    grid.appendChild(card);
  });
  section.appendChild(grid);
  return section;
}

function deriveScenarioPackage(data) {
  const extras = data?.execution_meta?.extras || {};
  const snapshot = extras.quant_snapshot || {};
  const metrics = getQuantMetrics(data, snapshot);
  const ticker = data?.ticker || snapshot.target || "대상 자산";
  const evidenceFallback = Array.isArray(data?.cited_doc_ids) ? data.cited_doc_ids : [];
  const bull = Array.isArray(data?.bull_points) ? data.bull_points.map((x) => normalizeTextItem(x)).filter(Boolean) : [];
  const bear = Array.isArray(data?.bear_points) ? data.bear_points.map((x) => normalizeTextItem(x)).filter(Boolean) : [];
  const timeline = data?.catalyst_timeline || {};
  const catalysts = [
    ...cleanTextArray(timeline.near_term),
    ...cleanTextArray(timeline.mid_term),
    ...cleanTextArray(timeline.long_term),
  ];

  const momentum1m = findMetric(metrics, ["1개월 가격 모멘텀", "1m momentum"]);
  const momentum3m = findMetric(metrics, ["3개월 가격 모멘텀", "3m momentum"]);
  const sma20 = findMetric(metrics, ["sma20"]);
  const sma50 = findMetric(metrics, ["sma50"]);
  const sma200 = findMetric(metrics, ["sma200"]);
  const rsi = findMetric(metrics, ["rsi"]);
  const macd = findMetric(metrics, ["macd"]);
  const volatility = findMetric(metrics, ["실현 변동성", "realized volatility"]);
  const m1 = parseMetricNumber(momentum1m);
  const m3 = parseMetricNumber(momentum3m);
  const d20 = parseMetricNumber(sma20);
  const d50 = parseMetricNumber(sma50);
  const d200 = parseMetricNumber(sma200);
  const rsiValue = parseMetricNumber(rsi);
  const macdValue = parseMetricNumber(macd);

  const baseDocs = collectMetricDocIds(metrics, [["1개월 가격 모멘텀"], ["sma20"], ["sma50"], ["rsi"]], evidenceFallback);
  const bullDocs = collectMetricDocIds(metrics, [["macd"], ["sma200"], ["3개월 가격 모멘텀"]], evidenceFallback);
  const bearDocs = collectMetricDocIds(metrics, [["rsi"], ["실현 변동성"], ["sma20"], ["sma200"]], evidenceFallback);

  const trendRead = [
    momentum1m ? `1개월 모멘텀 ${formatMetricValue(momentum1m)}` : "",
    momentum3m ? `3개월 모멘텀 ${formatMetricValue(momentum3m)}` : "",
    sma20 ? `SMA20 괴리 ${formatMetricValue(sma20)}` : "",
    sma200 ? `SMA200 괴리 ${formatMetricValue(sma200)}` : "",
  ].filter(Boolean).join(", ");
  const momentumRead = [
    rsi ? `RSI ${formatMetricValue(rsi)}` : "",
    macd ? `MACD 히스토그램 ${formatMetricValue(macd)}` : "",
  ].filter(Boolean).join(", ");

  const scenarios = [
    {
      scenario: "Base: 상승 후 검증 구간",
      probability: "조건부 기본 시나리오",
      expected_outcome: trendRead
        ? `${ticker}는 ${trendRead} 기준으로 단기 가격 탄력은 확인되지만, 중기 추세와 장기 평균선 복원 여부가 다음 판단 변수입니다.`
        : `${ticker}는 가격/추세 데이터가 제한적이므로 수집 근거와 다음 실적 이벤트 확인이 필요합니다.`,
      asset_implication: "추세가 유지되면 완만한 상방은 열려 있지만, 과열 신호가 있으면 신규 진입 기대값은 낮아집니다.",
      decision_read: "분할 접근과 확인 매수 중심. 한 번에 추격하기보다 SMA20/50 지지와 거래량 동반 여부를 확인합니다.",
      evidence_doc_ids: baseDocs,
    },
    {
      scenario: "Bull: 모멘텀 재가속과 기대치 상향",
      probability: "상방 시나리오",
      expected_outcome: [
        momentumRead || "모멘텀 지표 개선",
        bull[0] || catalysts[0] || "실적/가이던스 또는 핵심 사업 지표 개선",
      ].filter(Boolean).join(" + "),
      asset_implication: (d200 ?? 0) < 0
        ? "SMA200 회복과 함께 중장기 추세 복원이 확인되면 멀티플 리레이팅 여지가 커집니다."
        : "이미 장기 추세가 우호적이면 실적 확인 시 상방 탄력이 커질 수 있습니다.",
      decision_read: "상승 추세가 거래량과 함께 재확인될 때 포지션을 증액하고, 과열권에서는 돌파 후 눌림을 우선합니다.",
      evidence_doc_ids: bullDocs,
    },
    {
      scenario: "Bear: 과열 해소 또는 기대치 미달",
      probability: "하방 리스크 시나리오",
      expected_outcome: [
        (rsiValue ?? 0) >= 70 ? `RSI ${formatMetricValue(rsi)} 과열권` : "모멘텀 둔화",
        volatility ? `변동성 ${formatMetricValue(volatility)}` : "",
        bear[0] || "실적/가이던스가 현재 기대를 충족하지 못하는 경우",
      ].filter(Boolean).join(" + "),
      asset_implication: "단기 평균선 이탈 또는 MACD 둔화가 동반되면 최근 상승분의 되돌림과 밸류에이션 압축 위험이 커집니다.",
      decision_read: "손절/감액 기준을 SMA20/50 이탈, MACD 음전환, 이벤트 후 가이던스 하향으로 명확히 둡니다.",
      evidence_doc_ids: bearDocs,
    },
  ];

  const strategies = [
    {
      strategy: "확인 매수 / 분할 진입",
      trigger: (d20 ?? 0) > 0 && (d50 ?? 0) > 0
        ? "가격이 SMA20/50 위에서 유지되고 MACD가 양수권을 유지할 때"
        : "가격이 단기 평균선을 회복하고 거래량이 평균 이상으로 동반될 때",
      rationale: "모멘텀은 방향성을 보여주지만 진입 가격의 기대값은 지지선 확인과 변동성 조절에서 결정됩니다.",
      risk_control: "RSI가 70 이상이면 추격 매수 비중을 줄이고, 눌림 또는 실적 확인 후 증액합니다.",
      evidence_doc_ids: baseDocs,
    },
    {
      strategy: "리스크 감액 / 무효화 기준",
      trigger: "SMA20/50 이탈, MACD 히스토그램 음전환, 또는 실적/가이던스가 현재 투자 가설을 훼손할 때",
      rationale: "기술적 추세가 약화되는 구간에서는 좋은 기업이어도 6~12개월 기대수익 대비 변동성 부담이 커집니다.",
      risk_control: "포지션 크기를 줄이고 다음 지지선 또는 새 펀더멘털 근거가 나올 때까지 재진입을 유보합니다.",
      evidence_doc_ids: bearDocs,
    },
  ];

  if ((m1 ?? 0) > 0 && (m3 ?? 0) < 0) {
    strategies.push({
      strategy: "중기 추세 복원 확인",
      trigger: "1개월 모멘텀은 유지되지만 3개월 모멘텀 또는 SMA200이 아직 약할 때",
      rationale: "단기 반등과 중기 추세 전환은 다른 신호입니다. SMA200 회복 또는 3개월 모멘텀 개선이 확인되어야 더 공격적인 비중 확대가 정당화됩니다.",
      risk_control: "장기 평균선 회복 전에는 목표 비중을 제한합니다.",
      evidence_doc_ids: collectMetricDocIds(metrics, [["3개월 가격 모멘텀"], ["sma200"]], evidenceFallback),
    });
  }

  return { scenarios, strategies };
}

function fallbackScenarioPackage(data) {
  const ticker = data?.ticker || data?.theme || "대상 자산";
  const docs = Array.isArray(data?.cited_doc_ids) ? data.cited_doc_ids.slice(0, 4) : [];
  const summary = cleanLine(data?.summary || data?.conclusion || "");
  return {
    scenarios: [
      {
        scenario: "Base: 확인된 근거 유지",
        probability: "기본 경로",
        expected_outcome: summary || `${ticker}의 현재 투자 가설은 확인된 근거가 유지되는지에 달려 있습니다.`,
        asset_implication: "가격은 기존 추세를 크게 벗어나기보다 핵심 지표와 이벤트 확인에 민감하게 반응할 가능성이 큽니다.",
        decision_read: "신규 진입은 분할로 제한하고, 핵심 지표가 같은 방향으로 정렬되는지 확인합니다.",
        evidence_doc_ids: docs,
      },
      {
        scenario: "Bull: 기대치 상향",
        probability: "상방 경로",
        expected_outcome: "실적, 수급, 정책 또는 기술적 모멘텀이 동시에 개선되면 시장 기대가 상향될 수 있습니다.",
        asset_implication: "상방 리레이팅은 단순 뉴스보다 가격 모멘텀, 거래량, 가이던스 개선이 함께 확인될 때 신뢰도가 높습니다.",
        decision_read: "상승 확인 후 눌림 또는 돌파 재확인 구간에서 비중 확대를 검토합니다.",
        evidence_doc_ids: docs,
      },
      {
        scenario: "Bear: 기대치 훼손",
        probability: "하방 경로",
        expected_outcome: "핵심 지표 둔화, 이벤트 실망, 유동성 악화가 겹치면 최근 가격 기대가 훼손될 수 있습니다.",
        asset_implication: "평균선 이탈, 모멘텀 둔화, 변동성 확대가 동반되면 손실 확대 가능성이 커집니다.",
        decision_read: "무효화 기준을 먼저 정하고, 손절 또는 감액 트리거를 지표 기반으로 집행합니다.",
        evidence_doc_ids: docs,
      },
    ],
    strategies: [
      {
        strategy: "조건부 분할 진입",
        trigger: "가격/모멘텀/거래량이 같은 방향으로 확인될 때",
        rationale: "근거가 완전히 정렬되지 않은 구간에서는 진입 단가와 변동성 관리가 기대수익을 좌우합니다.",
        risk_control: "초기 비중을 제한하고 핵심 지표가 훼손되면 추가 매수를 중단합니다.",
        evidence_doc_ids: docs,
      },
      {
        strategy: "무효화 기준 선집행",
        trigger: "주요 평균선 이탈, 모멘텀 음전환, 실적/정책 이벤트 실망",
        rationale: "방향성 판단보다 손실 제한 조건을 먼저 고정해야 포지션 관리가 일관됩니다.",
        risk_control: "사전에 정한 감액/손절 기준을 지표 기준일과 함께 기록합니다.",
        evidence_doc_ids: docs,
      },
    ],
  };
}

function renderQuantSnapshot(data) {
  if (!els.quantSnapshot) return;
  const extras = data?.execution_meta?.extras || {};
  const snapshot = extras.quant_snapshot || {};
  const metrics = getQuantMetrics(data, snapshot);
  const shockRows = snapshot.rate_shock_scenarios || snapshot.stress_scenarios || [];
  const exposures = snapshot.factor_exposures || {};
  els.quantSnapshot.innerHTML = "";

  if (!metrics.length && !Object.keys(snapshot).length) {
    els.quantSnapshot.innerHTML = `<div class="metric-empty">정량 snapshot이 없습니다. 수집 가능한 데이터가 부족하거나 종목/자산군에 맞는 deterministic engine이 아직 적용되지 않았습니다.</div>`;
    return;
  }

  const meta = document.createElement("div");
  meta.className = "quant-meta-grid";
  const metaRows = [
    ["asset_class", snapshot.asset_class || data?.mode || "—"],
    ["target", snapshot.target || data?.ticker || data?.theme || "—"],
    ["as_of", snapshot.as_of || "—"],
    ["freshness", snapshot.freshness_status || extras.data_freshness?.overall_status || "unknown"],
    ["source", snapshot.source || "deterministic_quant"],
  ];
  meta.innerHTML = metaRows
    .map(([k, v]) => `<div class="quant-meta"><span>${escapeHtml(k)}</span><strong>${escapeHtml(String(v || "—"))}</strong></div>`)
    .join("");
  els.quantSnapshot.appendChild(meta);

  const regimePanel = renderQuantRegime(data, metrics);
  if (regimePanel) els.quantSnapshot.appendChild(regimePanel);

  const tableWrap = document.createElement("div");
  tableWrap.className = "metric-table-wrap top-gap";
  const table = document.createElement("table");
  table.className = "metric-table";
  table.innerHTML = `<thead><tr><th>지표</th><th>값</th><th>단위</th><th>기준일</th><th>출처</th><th>상태</th><th>맥락</th></tr></thead><tbody></tbody>`;
  const tbody = table.querySelector("tbody");
  metrics.forEach((metric) => {
    const tr = document.createElement("tr");
    [
      metric.name,
      metric.value,
      metric.unit || "",
      metric.as_of || "unknown",
      metric.source || snapshot.source || "",
      metric.freshness_status || snapshot.freshness_status || "unknown",
      metric.context || "",
    ].forEach((value) => {
      const td = document.createElement("td");
      td.textContent = cleanLine(value) || "—";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tableWrap.appendChild(table);
  els.quantSnapshot.appendChild(tableWrap);

  if (Array.isArray(shockRows) && shockRows.length) {
    const section = document.createElement("section");
    section.className = "quant-section";
    section.innerHTML = `<h4>Stress / Shock Table</h4>`;
    const shockTable = document.createElement("table");
    shockTable.className = "metric-table";
    const columns = Array.from(new Set(shockRows.flatMap((row) => Object.keys(row || {})))).slice(0, 8);
    shockTable.innerHTML = `<thead><tr>${columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead><tbody></tbody>`;
    const shockBody = shockTable.querySelector("tbody");
    shockRows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((col) => {
        const td = document.createElement("td");
        td.textContent = cleanLine(row?.[col]) || "—";
        tr.appendChild(td);
      });
      shockBody.appendChild(tr);
    });
    section.appendChild(shockTable);
    els.quantSnapshot.appendChild(section);
  }

  if (exposures && typeof exposures === "object" && Object.keys(exposures).length) {
    const exposureBox = document.createElement("div");
    exposureBox.className = "quant-section";
    exposureBox.innerHTML = `<h4>Factor / Proxy Exposure</h4><pre class="mini-code">${escapeHtml(JSON.stringify(exposures, null, 2))}</pre>`;
    els.quantSnapshot.appendChild(exposureBox);
  }
}

function normalizeRiskItem(item, fallbackLabel = "리스크") {
  if (typeof item === "string") {
    return { label: fallbackLabel, title: cleanLine(item), body: "", evidence_doc_ids: [] };
  }
  const source = item && typeof item === "object" ? item : {};
  return {
    label: cleanLine(source.label || source.category || source.type || fallbackLabel),
    title: cleanLine(source.title || source.name || source.risk || source.text || source.scenario || source.strategy || fallbackLabel),
    body: cleanLine(source.body || source.description || source.context || source.impact || source.expected_outcome || source.rationale || ""),
    evidence_doc_ids: Array.isArray(source.evidence_doc_ids) ? source.evidence_doc_ids.filter(Boolean) : [],
  };
}

function collectRiskCards(data) {
  const extras = data?.execution_meta?.extras || {};
  const snapshot = extras.quant_snapshot || {};
  const cards = [];
  const metrics = getQuantMetrics(data, snapshot);
  const fallbackDocs = Array.isArray(data?.cited_doc_ids) ? data.cited_doc_ids.slice(0, 4) : [];
  const exposures = snapshot.factor_exposures || {};

  if (exposures && typeof exposures === "object" && (exposures.primary || Array.isArray(exposures.secondary))) {
    const primary = cleanLine(exposures.primary || "market_beta");
    const secondary = Array.isArray(exposures.secondary) ? exposures.secondary.map(cleanLine).filter(Boolean).join(", ") : cleanLine(exposures.secondary);
    cards.push({
      label: "Factor Exposure",
      title: `주요 노출: ${primary}`,
      body: secondary ? `보조 노출 축은 ${secondary}입니다. 같은 방향으로 악화되면 손실 분포가 비선형으로 커질 수 있습니다.` : "보조 노출 축이 제한적으로 확인됩니다.",
      evidence_doc_ids: fallbackDocs,
    });
  }

  const shockRows = firstNonEmptyArray(snapshot.stress_table, snapshot.rate_shock_scenarios).slice(0, 4);
  if (shockRows.length) {
    const shockText = shockRows.map((row) => {
      const shock = cleanLine(row.shock_bp !== undefined ? `${row.shock_bp}bp` : row.scenario || row.name || row.shock || "");
      const impact = cleanLine(row.estimated_price_impact_pct || row.impact || row.pnl || row.expected_move || "");
      return [shock, impact].filter(Boolean).join(" ");
    }).filter(Boolean).join(" / ");
    cards.push({
      label: "Stress / Shock",
      title: "민감도 기반 손실 구간",
      body: shockText || "스트레스 테이블은 존재하지만 표시 가능한 영향값이 제한적입니다.",
      evidence_doc_ids: fallbackDocs,
    });
  }

  const invalidation = firstNonEmptyArray(snapshot.regime?.invalidation_signals, extras.invalidation_signals).map(normalizeTextItem).filter(Boolean);
  if (invalidation.length) {
    cards.push({
      label: "Invalidation",
      title: "투자 가설 무효화 신호",
      body: invalidation.slice(0, 3).join(" / "),
      evidence_doc_ids: fallbackDocs,
    });
  }

  const volatility = findMetric(metrics, ["실현 변동성", "realized volatility"]);
  const rsi = findMetric(metrics, ["rsi"]);
  const sma20 = findMetric(metrics, ["sma20"]);
  const volValue = parseMetricNumber(volatility);
  const rsiValue = parseMetricNumber(rsi);
  if (volatility || rsi || sma20) {
    const pieces = [
      volatility ? `변동성 ${formatMetricValue(volatility)}` : "",
      rsi ? `RSI ${formatMetricValue(rsi)}` : "",
      sma20 ? `SMA20 괴리 ${formatMetricValue(sma20)}` : "",
    ].filter(Boolean);
    const body = [
      pieces.join(", "),
      (rsiValue ?? 0) >= 70 ? "과열권에서는 호재 반영 후 되돌림 리스크가 커집니다." : "",
      (volValue ?? 0) >= 30 ? "변동성 수준이 높아 포지션 크기와 손절 기준을 보수적으로 둬야 합니다." : "",
    ].filter(Boolean).join(" ");
    cards.push({
      label: "Technical Risk",
      title: "가격·변동성 리스크",
      body: body || "기술적 리스크 지표가 제한적으로 확인됩니다.",
      evidence_doc_ids: collectMetricDocIds(metrics, [["실현 변동성"], ["rsi"], ["sma20"]], fallbackDocs),
    });
  }

  firstNonEmptyArray(data?.key_risks, data?.bear_points, extras.key_risks)
    .map((item) => normalizeRiskItem(item, "Evidence-backed Risk"))
    .filter((item) => item.title)
    .slice(0, 4)
    .forEach((item) => cards.push(item));

  if (Array.isArray(snapshot.missing_axes) && snapshot.missing_axes.length) {
    cards.push({
      label: "Data Gap",
      title: "추가 확인이 필요한 데이터 축",
      body: snapshot.missing_axes.slice(0, 6).join(", "),
      evidence_doc_ids: [],
    });
  }

  return cards;
}

function renderRiskPanel(data) {
  if (!els.riskPanel) return;
  const extras = data?.execution_meta?.extras || {};
  const blocks = collectRiskCards(data);
  if (extras.error_type) blocks.unshift({ label: "오류/부분응답 분류", title: String(extras.error_type), body: "", evidence_doc_ids: [] });
  if (data?.uncertainty) blocks.unshift({ label: "불확실성", title: cleanLine(data.uncertainty), body: "", evidence_doc_ids: [] });
  if (Array.isArray(extras.blocking_missing_buckets) && extras.blocking_missing_buckets.length) {
    blocks.push({ label: "차단된 근거 버킷", title: extras.blocking_missing_buckets.join(", "), body: "", evidence_doc_ids: [] });
  }
  if (Array.isArray(extras.warning_missing_buckets) && extras.warning_missing_buckets.length) {
    blocks.push({ label: "경고 근거 버킷", title: extras.warning_missing_buckets.join(", "), body: "", evidence_doc_ids: [] });
  }
  if (data?.risk_management) {
    const risk = data.risk_management;
    if (Array.isArray(risk.main_risks) && risk.main_risks.length) {
      blocks.push({
        label: `Risk Management · ${risk.risk_level || "unknown"}`,
        title: risk.main_risks.slice(0, 3).map(cleanLine).filter(Boolean).join(" · "),
        body: cleanLine(risk.position_sizing_comment || ""),
        evidence_doc_ids: [],
      });
    }
    if (Array.isArray(risk.invalidating_conditions) && risk.invalidating_conditions.length) {
      blocks.push({
        label: "View Invalidation",
        title: risk.invalidating_conditions.slice(0, 3).map(cleanLine).filter(Boolean).join(" · "),
        body: "이 조건이 발생하면 기존 투자 판단을 재검토해야 합니다.",
        evidence_doc_ids: [],
      });
    }
  }
  if (data?.confidence_rationale) {
    const cr = data.confidence_rationale;
    const caps = Array.isArray(cr.caps_applied) ? cr.caps_applied : [];
    const fixed = (value) => Number(value || 0).toFixed(2);
    blocks.push({
      label: "Confidence Rationale",
      title: `final ${fixed(cr.final_confidence ?? data.confidence)} · evidence ${fixed(cr.evidence_coverage)} · numeric ${fixed(cr.numeric_grounding_rate)}`,
      body: caps.length ? caps.slice(0, 2).map(cleanLine).join(" · ") : "신뢰도 캡이 적용되지 않았거나 제한적입니다.",
      evidence_doc_ids: [],
    });
  }
  if (extras.data_freshness?.overall_status) blocks.push({ label: "데이터 신선도", title: extras.data_freshness.overall_status, body: "", evidence_doc_ids: [] });
  if (extras.validation_summary) blocks.push({ label: "검증 요약", title: JSON.stringify(extras.validation_summary), body: "", evidence_doc_ids: [] });

  els.riskPanel.innerHTML = "";
  if (!blocks.length) {
    els.riskPanel.innerHTML = `<div class="metric-empty">추가 리스크 진단 정보가 없습니다.</div>`;
    return;
  }
  blocks.slice(0, 12).forEach((block) => {
    const card = document.createElement("article");
    card.className = "risk-card";
    card.innerHTML = `
      <span>${escapeHtml(block.label || "Risk")}</span>
      <strong>${escapeHtml(block.title || "명시 없음")}</strong>
      ${block.body ? `<p>${escapeHtml(block.body)}</p>` : ""}
    `;
    const badges = document.createElement("div");
    badges.className = "evidence-chips";
    renderDocBadges(badges, block.evidence_doc_ids || []);
    card.appendChild(badges);
    els.riskPanel.appendChild(card);
  });
}

function firstNonEmptyArray(...values) {
  for (const value of values) {
    if (Array.isArray(value)) {
      const cleaned = value.filter((item) => {
        if (item === null || item === undefined) return false;
        if (typeof item === "string" || typeof item === "number") return Boolean(cleanLine(item));
        if (typeof item === "object") {
          return Object.values(item).some((inner) => {
            if (Array.isArray(inner)) return inner.length > 0;
            return Boolean(cleanLine(inner));
          });
        }
        return false;
      });
      if (cleaned.length) return cleaned;
    }
  }
  return [];
}

function normalizeScenarioItem(item) {
  if (typeof item === "string") {
    return {
      scenario: cleanLine(item),
      probability: "조건부",
      expected_outcome: cleanLine(item),
      asset_implication: "가격과 리스크 판단은 핵심 지표가 같은 방향으로 확인되는지에 따라 달라집니다.",
      evidence_doc_ids: [],
    };
  }
  const source = item && typeof item === "object" ? item : {};
  return {
    ...source,
    scenario: cleanLine(source.scenario || source.title || source.name || source.case || source.label) || "Scenario",
    probability: cleanLine(source.probability || source.trigger || source.condition || source.assumption) || "명시 없음",
    expected_outcome: cleanLine(source.expected_outcome || source.outcome || source.summary || source.thesis || source.view) || "명시 없음",
    asset_implication: cleanLine(source.asset_implication || source.market_impact || source.impact || source.implication || source.decision_read) || "명시 없음",
    decision_read: cleanLine(source.decision_read || source.action || source.strategy || source.decision),
    evidence_doc_ids: Array.isArray(source.evidence_doc_ids) ? source.evidence_doc_ids.filter(Boolean) : [],
  };
}

function scenarioSimulationToScenarios(simulation) {
  if (!simulation || typeof simulation !== "object" || !Array.isArray(simulation.scenarios)) return [];
  return simulation.scenarios.map((scenario) => normalizeScenarioItem({
    scenario: scenario.name || scenario.id,
    probability: scenario.probability != null ? `${Math.round(Number(scenario.probability) * 100)}%` : "명시 없음",
    expected_outcome: scenario.expected_reaction || scenario.assumptions?.join(" · "),
    asset_implication: [
      scenario.direction ? `Direction: ${scenario.direction}` : "",
      Array.isArray(scenario.triggers) && scenario.triggers.length ? `Triggers: ${scenario.triggers.join(" · ")}` : "",
      Array.isArray(scenario.invalidation_signals) && scenario.invalidation_signals.length ? `Invalidation: ${scenario.invalidation_signals.join(" · ")}` : "",
    ].filter(Boolean).join(" / "),
    decision_read: scenario.expected_reaction,
    evidence_doc_ids: Array.isArray(scenario.evidence_doc_ids) ? scenario.evidence_doc_ids : [],
  }));
}

function scenarioSimulationToStrategies(simulation) {
  const decision = simulation?.decision_implication;
  if (!decision || typeof decision !== "object") return [];
  return [
    normalizeStrategyItem({
      strategy: `Scenario decision framework: ${decision.bias || "mixed"}`,
      trigger: Array.isArray(decision.entry_conditions) ? decision.entry_conditions.join(" · ") : "",
      rationale: Array.isArray(decision.monitoring_indicators) ? decision.monitoring_indicators.join(" · ") : "",
      risk_control: Array.isArray(decision.risk_management) ? decision.risk_management.join(" · ") : decision.disclaimer,
      evidence_doc_ids: [],
    }),
  ];
}

function normalizeStrategyItem(item) {
  if (typeof item === "string") {
    return {
      strategy: cleanLine(item),
      trigger: "핵심 지표 확인",
      rationale: cleanLine(item),
      risk_control: "포지션 크기와 손절 기준을 사전에 고정합니다.",
      evidence_doc_ids: [],
    };
  }
  const source = item && typeof item === "object" ? item : {};
  return {
    ...source,
    strategy: cleanLine(source.strategy || source.title || source.name || source.action || source.decision) || "Strategy",
    trigger: cleanLine(source.trigger || source.entry || source.condition || source.when) || "명시 없음",
    rationale: cleanLine(source.rationale || source.reason || source.thesis || source.why) || "명시 없음",
    risk_control: cleanLine(source.risk_control || source.risk_management || source.stop || source.invalidation) || "명시 없음",
    evidence_doc_ids: Array.isArray(source.evidence_doc_ids) ? source.evidence_doc_ids.filter(Boolean) : [],
  };
}

function scenarioBundleToArray(bundle) {
  if (!bundle || typeof bundle !== "object" || Array.isArray(bundle)) return [];
  const specs = [
    ["base_case", "Base Case"],
    ["bull_case", "Bull Case"],
    ["bear_case", "Bear Case"],
  ];
  return specs
    .map(([key, label]) => {
      const item = bundle[key];
      if (!item || typeof item !== "object") return null;
      return {
        scenario: label,
        probability: item.probability !== undefined && item.probability !== null ? String(item.probability) : "명시 없음",
        expected_outcome: cleanLine(item.thesis || item.expected_outcome || item.summary) || "명시 없음",
        asset_implication: [
          Array.isArray(item.drivers) && item.drivers.length ? `Drivers: ${item.drivers.map(cleanLine).filter(Boolean).join(" · ")}` : "",
          Array.isArray(item.risks) && item.risks.length ? `Risks: ${item.risks.map(cleanLine).filter(Boolean).join(" · ")}` : "",
        ].filter(Boolean).join(" / ") || "명시 없음",
        decision_read: cleanLine(item.thesis || ""),
        evidence_doc_ids: Array.isArray(item.evidence_doc_ids) ? item.evidence_doc_ids.filter(Boolean) : [],
      };
    })
    .filter(Boolean);
}

function scenarioSources(data) {
  const extras = data?.execution_meta?.extras || {};
  const simulation = extras.scenario_simulation;
  const simulated = scenarioSimulationToScenarios(simulation);
  if (simulated.length) return simulated;
  const bundled = scenarioBundleToArray(data?.scenario_analysis);
  if (bundled.length) return bundled.map(normalizeScenarioItem);
  return firstNonEmptyArray(
    data?.scenario_analysis,
    data?.fallback_scenario_analysis,
    extras.scenario_analysis,
    extras.fallback_scenario_analysis,
    extras.scenarios,
    extras.scenario_table,
    extras.quant_snapshot?.scenario_analysis
  ).map(normalizeScenarioItem);
}

function strategySources(data) {
  const extras = data?.execution_meta?.extras || {};
  const simulationStrategies = scenarioSimulationToStrategies(extras.scenario_simulation);
  if (simulationStrategies.length) return simulationStrategies;
  return firstNonEmptyArray(
    data?.execution_strategy,
    data?.fallback_execution_strategy,
    extras.execution_strategy,
    extras.fallback_execution_strategy,
    extras.strategies,
    extras.execution_plan,
    extras.quant_snapshot?.execution_strategy
  ).map(normalizeStrategyItem);
}

function renderScenarioPanel(data) {
  if (!els.scenarioPanel) return;
  const existingScenarios = scenarioSources(data);
  const existingStrategies = strategySources(data);
  let derived = { scenarios: [], strategies: [] };
  if (!existingScenarios.length || !existingStrategies.length) {
    try {
      derived = deriveScenarioPackage(data);
    } catch (err) {
      console.warn("scenario derivation failed", err);
    }
  }
  if (!derived.scenarios.length || !derived.strategies.length) {
    const fallback = fallbackScenarioPackage(data);
    if (!derived.scenarios.length) derived.scenarios = fallback.scenarios;
    if (!derived.strategies.length) derived.strategies = fallback.strategies;
  }
  const scenarios = existingScenarios.length ? existingScenarios : derived.scenarios.map(normalizeScenarioItem);
  const strategies = existingStrategies.length ? existingStrategies : derived.strategies.map(normalizeStrategyItem);
  els.scenarioPanel.innerHTML = "";
  const simulation = data?.execution_meta?.extras?.scenario_simulation;

  if (!scenarios.length && !strategies.length) {
    els.scenarioPanel.innerHTML = `<div class="metric-empty">시나리오/실행 전략이 생성되지 않았습니다.</div>`;
    return;
  }

  if (simulation && typeof simulation === "object") {
    const status = simulation.status || "unknown";
    const scores = simulation.scores || {};
    const summary = document.createElement("section");
    summary.className = "scenario-card scenario-simulation-summary";
    summary.innerHTML = `
      <h4>Scenario Simulation</h4>
      <p><strong>Status:</strong> ${escapeHtml(status)}</p>
      <p><strong>Evidence strength:</strong> ${escapeHtml(scores.evidence_strength != null ? Number(scores.evidence_strength).toFixed(2) : "명시 없음")} · <strong>Risk score:</strong> ${escapeHtml(scores.risk_score != null ? Number(scores.risk_score).toFixed(2) : "명시 없음")}</p>
    `;
    els.scenarioPanel.appendChild(summary);
  }

  if (scenarios.length) {
    const grid = document.createElement("div");
    grid.className = "scenario-grid";
    scenarios.forEach((scenario) => {
      const card = document.createElement("article");
      card.className = "scenario-card";
      card.innerHTML = `
        <h4>${escapeHtml(scenario.scenario || scenario.title || "Scenario")}</h4>
        <p><strong>확률/조건:</strong> ${escapeHtml(scenario.probability || scenario.trigger || "명시 없음")}</p>
        <p><strong>예상 전개:</strong> ${escapeHtml(scenario.expected_outcome || "명시 없음")}</p>
        <p><strong>자산 영향:</strong> ${escapeHtml(scenario.asset_implication || scenario.decision_read || "명시 없음")}</p>
      `;
      const badges = document.createElement("div");
      badges.className = "evidence-chips";
      renderDocBadges(badges, scenario.evidence_doc_ids || []);
      card.appendChild(badges);
      grid.appendChild(card);
    });
    els.scenarioPanel.appendChild(grid);
  }

  if (strategies.length) {
    const section = document.createElement("section");
    section.className = "strategy-list top-gap";
    section.innerHTML = `<h4>Execution Strategy</h4>`;
    strategies.forEach((strategy) => {
      const item = document.createElement("article");
      item.className = "scenario-card";
      item.innerHTML = `
        <h4>${escapeHtml(strategy.strategy || strategy.title || "Strategy")}</h4>
        <p><strong>진입/트리거:</strong> ${escapeHtml(strategy.trigger || "명시 없음")}</p>
        <p><strong>근거:</strong> ${escapeHtml(strategy.rationale || "명시 없음")}</p>
        <p><strong>리스크 관리:</strong> ${escapeHtml(strategy.risk_control || "명시 없음")}</p>
      `;
      const badges = document.createElement("div");
      badges.className = "evidence-chips";
      renderDocBadges(badges, strategy.evidence_doc_ids || []);
      item.appendChild(badges);
      section.appendChild(item);
    });
    els.scenarioPanel.appendChild(section);
  }
}

function sectionLines(label, sections) {
  const lines = [label];
  if (!Array.isArray(sections) || !sections.length) {
    lines.push("- 식별된 항목 없음");
    return lines;
  }
  sections.forEach((section) => {
    if (section.title) lines.push(`- ${section.title}`);
    (section.bullets || []).forEach((bullet) => lines.push(`  - ${bullet}`));
    if (section.conclusion) lines.push(`  결론: ${section.conclusion}`);
  });
  return lines;
}

function formatTopicDecisionSections(data) {
  if (!data) return "";
  const lines = [];
  lines.push("핵심 분석");
  lines.push(...sectionLines("(1) 대상/주제 개요", data.asset_overview));
  lines.push(...sectionLines("(2) 거시/정책 환경", data.macro_regime));
  lines.push(...sectionLines("(3) 가격/시장 구조", data.rate_structure));

  if (Array.isArray(data.scenario_analysis) && data.scenario_analysis.length) {
    lines.push("(4) 시나리오 분석");
    data.scenario_analysis.forEach((scenario) => {
      lines.push(`- ${scenario.scenario || "Scenario"}${scenario.probability ? ` (${scenario.probability})` : ""}`);
      if (scenario.expected_outcome) lines.push(`  예상 전개: ${scenario.expected_outcome}`);
      if (scenario.asset_implication) lines.push(`  자산 영향: ${scenario.asset_implication}`);
      if (scenario.decision_read) lines.push(`  판단: ${scenario.decision_read}`);
    });
  } else {
    lines.push("(4) 시나리오 분석");
    lines.push("- 식별된 항목 없음");
  }

  lines.push("(5) 리스크 요인");
  lines.push(...listLines(data.key_risks));

  lines.push("(6) 촉매 및 실행 전략");
  if (Array.isArray(data.execution_strategy) && data.execution_strategy.length) {
    data.execution_strategy.forEach((strategy) => {
      lines.push(`- ${strategy.strategy || "Strategy"}`);
      if (strategy.trigger) lines.push(`  조건: ${strategy.trigger}`);
      if (strategy.rationale) lines.push(`  근거: ${strategy.rationale}`);
      if (strategy.risk_control) lines.push(`  리스크 관리: ${strategy.risk_control}`);
    });
  } else {
    lines.push("- 식별된 항목 없음");
  }

  lines.push("(7) 시장 가격 vs 현실");
  const pricingLines = [];
  (data.rate_structure || []).forEach((section) => {
    if (section.conclusion) pricingLines.push(section.conclusion);
  });
  (data.investment_judgment || []).forEach((section) => {
    if (section.conclusion) pricingLines.push(section.conclusion);
  });
  (data.scenario_analysis || []).slice(0, 2).forEach((scenario) => {
    if (scenario.decision_read || scenario.asset_implication) {
      pricingLines.push(`${scenario.scenario || "Scenario"}: ${scenario.decision_read || scenario.asset_implication}`);
    }
  });
  lines.push(...listLines(pricingLines, "가격 판단은 Quant 탭의 수치와 시나리오를 함께 확인해야 합니다."));

  lines.push("");
  lines.push("Synthesis (핵심 판단 구간)");
  lines.push(...listLines([data.core_thesis]));
  lines.push(...sectionLines("투자 판단", data.investment_judgment));

  lines.push("");
  lines.push("Decision Edge");
  lines.push("상방 동인");
  lines.push(...listLines(data.key_drivers));
  lines.push("하방 리스크");
  lines.push(...listLines(data.key_risks));
  if (Array.isArray(data.related_tickers) && data.related_tickers.length) {
    lines.push("관련 자산 / 표현 수단");
    lines.push(...listLines(data.related_tickers.map((t) => `${t.ticker} (${t.role}): ${t.rationale}`)));
  }
  if (data.uncertainty) {
    lines.push("불확실성");
    lines.push(`- ${data.uncertainty}`);
  }

  lines.push("");
  lines.push("결론");
  const conclusions = (data.investment_judgment || []).map((s) => s.conclusion).filter(Boolean);
  lines.push(...listLines(conclusions.length ? conclusions : [data.core_thesis]));
  return joinProseLines(dedupeReportLines(lines));
}

function formatEquityDecisionMemo(data) {
  if (!data || data.status === "failed") return data?.conclusion || "";
  const lines = [];
  const bull = Array.isArray(data.bull_points) ? data.bull_points : [];
  const bear = Array.isArray(data.bear_points) ? data.bear_points : [];
  const timeline = data.catalyst_timeline || {};
  const near = Array.isArray(timeline.near_term) ? timeline.near_term : [];
  const mid = Array.isArray(timeline.mid_term) ? timeline.mid_term : [];
  const long = Array.isArray(timeline.long_term) ? timeline.long_term : [];
  const bullishCatalysts = [...near, ...mid, ...long].filter((item) => /\[Bullish\]|상승|성장|수요|개선|beat|upside/i.test(item));
  const bearishCatalysts = [...near, ...mid, ...long].filter((item) => /\[Bearish\]|하락|리스크|압박|둔화|miss|downside/i.test(item));
  const macro = [...bull, ...bear, ...near, ...mid].filter((item) => /금리|연준|인플레이션|유동성|macro|rate|fed|inflation|liquidity/i.test(item));
  const ai = [...bull, ...bear].filter((item) => /AI|인공지능|cloud|클라우드|GPU|Copilot|OpenAI|Google|Amazon|AWS|Azure|NVIDIA/i.test(item));
  const cost = [...bull, ...bear].filter((item) => /margin|마진|cost|비용|capex|opex|hiring|구조조정/i.test(item));

  if (data.decision_view) {
    lines.push("Decision View");
    lines.push(`- Rating: ${data.decision_view.rating || "neutral"} · confidence ${data.decision_view.confidence ?? data.confidence ?? "—"}`);
    if (data.decision_view.decision_summary) lines.push(`- ${data.decision_view.decision_summary}`);
    if (data.decision_view.primary_thesis) lines.push(`- 핵심 논지: ${data.decision_view.primary_thesis}`);
    if (Array.isArray(data.decision_view.what_would_change_my_view) && data.decision_view.what_would_change_my_view.length) {
      lines.push("판단 변경 조건");
      lines.push(...listLines(data.decision_view.what_would_change_my_view));
    }
    lines.push("");
  }

  lines.push("핵심 분석");
  lines.push("(1) 거시 환경");
  lines.push(...listLines(macro, "수집 근거에서 거시 민감도가 직접 확인되지 않았습니다."));
  lines.push("(2) 사업 및 매출 동인");
  lines.push(...listLines(bull.slice(0, 4)));
  lines.push("(3) 비용 구조 및 마진");
  lines.push(...listLines(cost, "비용 구조와 마진 변화는 추가 실적/가이던스 확인이 필요합니다."));
  lines.push("(4) AI 전략 및 경쟁 포지션");
  lines.push(...listLines(ai, "AI가 핵심 투자 변수인지 현재 근거만으로는 확인되지 않습니다."));
  lines.push("(5) 리스크 요인");
  lines.push(...listLines(bear.slice(0, 4)));
  lines.push("(6) 촉매 요인 (단기 / 중기)");
  lines.push("상승 촉매");
  lines.push(...listLines(bullishCatalysts.length ? bullishCatalysts : bull.slice(0, 2)));
  lines.push("하락 촉매");
  lines.push(...listLines(bearishCatalysts.length ? bearishCatalysts : bear.slice(0, 2)));
  lines.push("(7) 시장 가격 vs 현실");
  lines.push(...metricLines(data.key_metrics));
  if (data.uncertainty) lines.push(`- 시장이 놓칠 수 있는 지점 / 근거 공백: ${data.uncertainty}`);
  lines.push("");
  lines.push("Synthesis (핵심 판단 구간)");
  lines.push(...listLines([data.conclusion]));
  lines.push("");
  lines.push("Decision Edge");
  lines.push("판단 체크포인트");
  lines.push(...listLines(data.open_questions || [], "추가 확인 질문 없음"));
  lines.push("");
  lines.push("결론");
  lines.push(...listLines([data.conclusion, data.uncertainty ? `판단 변경 조건: ${data.uncertainty}` : "판단 변경 조건: 다음 실적/가이던스와 핵심 리스크 트리거 확인"]));
  return joinProseLines(dedupeReportLines(lines));
}

function classifyResponseBanner(data, isFastPhase) {
  const extras = data?.execution_meta?.extras || {};
  const warnings = Array.isArray(extras.warnings) ? extras.warnings.filter(Boolean) : [];
  const errorType = extras.error_type || "";
  const friendlyByType = {
    validation_error: "입력 검증 오류입니다. 종목 모드에서는 ticker가 필요하고, ticker 없이 질문하려면 자동 또는 주제 모드를 사용하세요.",
    data_unavailable: "핵심 데이터 일부를 가져오지 못했습니다. 가능한 대체 데이터로 보수적 판단을 표시합니다.",
    evidence_sparse: "근거가 부족한 축이 있습니다. 누락된 데이터 축은 Diagnostics에서 확인하세요.",
    model_json_error: "모델의 구조화 JSON 출력이 불안정했습니다. 가능한 경우 로컬 정량/규칙 기반 보정 결과를 표시합니다.",
    model_language_error: "모델 출력 언어가 요청 기준을 위반했습니다. 한국어 우세 검증을 통과한 보정 결과만 사용해야 합니다.",
    provider_entitlement: "일부 유료/권한 필요 provider가 제한되었습니다. Yahoo/FRED/수집 문서 기반 대체 경로를 확인하세요.",
    infrastructure_error: "로컬 인프라 오류입니다. Ollama, Qdrant, 네트워크 상태를 확인하세요.",
    unknown_error: "분류되지 않은 오류입니다. Diagnostics와 서버 로그를 확인하세요.",
  };
  if (isFastPhase) {
    return {
      level: "info",
      message: data?.error_metadata || "초기 판단입니다. 심화 분석을 계속 진행합니다.",
    };
  }
  if (data?.status === "failed") {
    return { level: "error", message: friendlyByType[errorType] || data?.error_metadata || "요청이 실패했습니다." };
  }
  if (errorType === "validation_error") {
    return { level: "none", message: "" };
  }
  if (errorType && friendlyByType[errorType]) {
    return { level: errorType === "evidence_sparse" || errorType === "provider_entitlement" ? "warning" : "info", message: friendlyByType[errorType] };
  }
  if (data?.error_metadata) {
    return { level: "warning", message: data.error_metadata };
  }
  if (warnings.length) {
    return { level: "warning", message: warnings.join(" | ") };
  }
  if (data?.status === "partial") {
    return {
      level: "warning",
      message: data?.uncertainty || "일부 근거가 부족해 보수적으로 해석해야 합니다.",
    };
  }
  return { level: "none", message: "" };
}

function renderResponse(data, collection, request) {
  if (data && (data.mode === "sector_macro" || data.mode === "concept")) {
    const decisionMemo = formatTopicDecisionSections(data);
    const decisionView = data.decision_view
      ? `Decision View\n- Rating: ${data.decision_view.rating || "neutral"} · confidence ${data.decision_view.confidence ?? "—"}\n- ${data.decision_view.decision_summary || ""}\n- 핵심 논지: ${data.decision_view.primary_thesis || ""}`
      : "";
    const uncertainty = data.uncertainty ? `불확실성\n${data.uncertainty}` : "";
    const keyMetrics = Array.isArray(data.key_metrics) && data.key_metrics.length
      ? `핵심 지표\n${data.key_metrics.map(formatMetricLine).filter(Boolean).map((line) => `- ${line}`).join("\n")}`
      : "";
    const related = Array.isArray(data.related_tickers) && data.related_tickers.length
      ? `관련 종목\n${data.related_tickers.map((t) => `- ${t.ticker} (${t.role}): ${t.rationale}`).join("\n")}`
      : "";
    data = {
      ...data,
      ticker: data.theme || "TOPIC",
      summary: buildTopicHeadlineSummary(data),
      conclusion: buildTopicDecisionMemo(data, decisionView, decisionMemo, uncertainty, keyMetrics, related),
      sentiment: "Neutral",
      confidence: data.decision_view?.confidence ?? data.confidence ?? data.confidence_rationale?.final_confidence ?? 0,
      bull_points: (data.key_drivers || []).map((d) => d.text || String(d)),
      bear_points: (data.key_risks || []).map((d) => d.text || String(d)),
      bull_evidence_ids: (data.key_drivers || []).map((d) => d.evidence_doc_ids || []),
      bear_evidence_ids: (data.key_risks || []).map((d) => d.evidence_doc_ids || []),
    };
  }
  const phase = data?.execution_meta?.extras?.phase || "final";
  const isFastPhase = phase === "fast";
  state.lastResponse = data;
  state.lastCollection = collection;
  state.lastRequest = request;

  els.emptyState.classList.add("hidden");
  els.loadingState.classList.add("hidden");
  els.resultView.classList.remove("hidden");
  if (els.compareView) els.compareView.classList.add("hidden");

  // Header
  els.resTicker.textContent = data.ticker || "";
  els.resStatus.textContent = isFastPhase ? "INITIAL" : (data.status || "").toUpperCase();
  els.resStatus.className = `status-badge ${statusClass(data.status)}`;
  els.resQuestion.textContent = data.question || "";

  if (els.resCacheBadge) {
    const cacheHit = collection?.cache_hit ?? data?.execution_meta?.extras?.cache_hit;
    const cacheAge = collection?.cache_age_s ?? 0;
    const cacheLabel = cacheAge ? `cache · ${formatAge(cacheAge)}` : "cache · reused";
    const hit = !!cacheHit;
    if (hit) {
      els.resCacheBadge.textContent = cacheLabel;
      els.resCacheBadge.classList.remove("hidden");
    } else {
      els.resCacheBadge.classList.add("hidden");
    }
  }

  // Error / warning banner
  const banner = classifyResponseBanner(data, isFastPhase);
  if (banner.level === "none") {
    els.errorBanner.classList.add("hidden");
    els.errorBanner.classList.remove("failed", "warning", "info");
  } else {
    els.errorBanner.textContent = banner.message;
    els.errorBanner.classList.remove("hidden");
    els.errorBanner.classList.toggle("failed", banner.level === "error");
    els.errorBanner.classList.toggle("warning", banner.level === "warning");
    els.errorBanner.classList.toggle("info", banner.level === "info");
  }

  // KPIs
  const sentiment = data.sentiment || "Neutral";
  els.resSentiment.textContent = sentiment;
  els.resSentiment.className = "kpi-value " + sentimentTone(sentiment);

  const conf = Number(data.confidence || 0);
  els.resConfidence.textContent = conf.toFixed(2);
  els.confidenceFill.style.width = `${Math.max(0, Math.min(1, conf)) * 100}%`;

  els.resCitationCount.textContent = (data.citations || []).length;
  els.resChunkCount.textContent = (data.raw_context || []).length;

  // Tabs content
  renderProse(els.resSummary, data.summary || "—");
  const isTopicMode = data && (data.mode === "sector_macro" || data.mode === "concept");
  renderProse(els.resConclusion, (isTopicMode ? data.conclusion : formatEquityDecisionMemo(data) || data.conclusion) || "—");

  // Evidence must be indexed before Bull/Bear render so chips can resolve titles.
  renderEvidence(data.raw_context || []);
  renderMetricTable(data.key_metrics || []);
  renderQuantSnapshot(data);
  renderRiskPanel(data);
  renderScenarioPanel(data);
  renderBullBear(
    data.bull_points || [],
    data.bear_points || [],
    data.bull_evidence_ids || [],
    data.bear_evidence_ids || []
  );
  renderCitations(data.citations || []);
  renderDiagnostics(request, collection);
  renderExecutionMeta(data.execution_meta || null);
  renderRaw(data);
  setExportAvailability(!isFastPhase && !!state.lastResponse && data.status !== "failed");
  if (isFastPhase) {
    els.reportMd.textContent = "# 최종 보고서 생성 중입니다.";
  } else {
    fetchMarkdownReport();
  }
}

function renderFailure(request, message) {
  const synthetic = {
    ticker: request.ticker,
    question: request.question,
    status: "failed",
    error_metadata: message,
    summary: "요청이 실패했습니다.",
    sentiment: "Neutral",
    confidence: 0,
    conclusion: "서버 또는 파이프라인 오류입니다. 로그를 확인해주세요.",
    citations: [],
    raw_context: [],
    bull_points: [],
    bear_points: [],
  };
  renderResponse(synthetic, null, request);
}

function sentimentTone(s) {
  const key = (s || "").toLowerCase();
  if (["positive", "bullish"].includes(key)) return "pos";
  if (["negative", "bearish"].includes(key)) return "neg";
  return "neu";
}

function renderBullBear(bull, bear, bullEv, bearEv) {
  const evidenceIndex = buildEvidenceIndex(state.evidenceRaw);

  const fill = (ul, items, evidence, emptyMsg) => {
    ul.innerHTML = "";
    if (!items.length) {
      ul.innerHTML = `<li class="muted">${emptyMsg}</li>`;
      return;
    }
    items.forEach((p, i) => {
      const text = typeof p === "string" ? p : (p.text || JSON.stringify(p));
      const ids = Array.isArray(evidence) && Array.isArray(evidence[i]) ? evidence[i] : [];
      const li = document.createElement("li");
      const textDiv = document.createElement("div");
      textDiv.className = "tpoint-text";
      textDiv.textContent = text;
      li.appendChild(textDiv);
      if (ids.length) {
        const chipRow = document.createElement("div");
        chipRow.className = "evidence-chips";
        ids.forEach((docId) => {
          const chip = document.createElement("button");
          chip.type = "button";
          chip.className = "evidence-chip";
          const item = evidenceIndex.get(String(docId));
          const label = item ? (item.title || docId) : docId;
          chip.textContent = item ? truncateLabel(label, 34) : `doc ${truncateLabel(docId, 14)}`;
          chip.title = item ? `${item.source || "doc"} · ${item.date || ""}\n${label}` : `doc_id: ${docId}`;
          chip.addEventListener("click", () => jumpToEvidence(docId));
          chipRow.appendChild(chip);
        });
        li.appendChild(chipRow);
      } else {
        const note = document.createElement("div");
        note.className = "evidence-note";
        note.textContent = "근거 링크 없음";
        li.appendChild(note);
      }
      ul.appendChild(li);
    });
  };
  fill(els.bullList, bull, bullEv, "식별된 상승 촉매 없음");
  fill(els.bearList, bear, bearEv, "식별된 하락 리스크 없음");
}

function buildEvidenceIndex(items) {
  const map = new Map();
  (items || []).forEach((it, idx) => {
    const docId = (it && it.metadata && it.metadata.doc_id) || it?.doc_id || it?.id;
    if (docId) map.set(String(docId), { ...it, _index: idx });
  });
  return map;
}

function truncateLabel(text, n) {
  const s = String(text || "");
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

function jumpToEvidence(docId) {
  const evidenceTab = document.querySelector('.tab[data-tab="evidence"]');
  if (evidenceTab) evidenceTab.click();
  els.evidenceSearch.value = "";
  applyEvidenceFilter();
  setTimeout(() => {
    const target = els.evidenceList.querySelector(`[data-doc-id="${CSS.escape(String(docId))}"]`);
    if (target) {
      target.open = true;
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("highlight");
      setTimeout(() => target.classList.remove("highlight"), 1400);
    }
  }, 60);
}

function renderEvidence(items) {
  state.evidenceRaw = items;
  applyEvidenceFilter();
}

function applyEvidenceFilter() {
  const q = (els.evidenceSearch.value || "").toLowerCase().trim();
  const items = state.evidenceRaw.filter((it) => {
    if (!q) return true;
    return (
      (it.title || "").toLowerCase().includes(q) ||
      (it.chunk || "").toLowerCase().includes(q) ||
      (it.source || "").toLowerCase().includes(q)
    );
  });
  els.evidenceList.innerHTML = "";
  if (!items.length) {
    els.evidenceList.innerHTML = `<li class="muted" style="padding:14px;color:var(--text-mute);font-size:12px;">근거 컨텍스트가 없습니다.</li>`;
    return;
  }
  items.forEach((it, idx) => {
    const li = document.createElement("details");
    li.className = "evidence-item";
    if (idx < 2) li.open = true;
    const docId = (it && it.metadata && it.metadata.doc_id) || it.doc_id || it.id || "";
    if (docId) li.dataset.docId = String(docId);
    const score = typeof it.score === "number" ? it.score.toFixed(3) : "—";
    li.innerHTML = `
      <summary>
        <span class="ev-source">${escapeHtml(it.source || "doc")}</span>
        <span class="ev-title">${escapeHtml(it.title || "Untitled")}</span>
        <span class="ev-date">${escapeHtml(it.date || "")}</span>
        <span class="ev-score">score ${score}</span>
      </summary>
      <div class="ev-body">${escapeHtml(it.chunk || "")}</div>
    `;
    els.evidenceList.appendChild(li);
  });
}

function renderCitations(cits) {
  els.citationsList.innerHTML = "";
  if (!cits.length) {
    els.citationsList.innerHTML = `<li style="color:var(--text-mute);font-family:inherit;">인용된 자료가 없습니다.</li>`;
    return;
  }
  cits.forEach((c) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="cit-source">${escapeHtml(c.source || "")}</span>
      <span class="cit-title">${escapeHtml(c.title || "")}</span>
      <span class="cit-date">${escapeHtml(c.date || "")}</span>
    `;
    els.citationsList.appendChild(li);
  });
}

function kvPairs(container, obj) {
  container.innerHTML = "";
  if (!obj) {
    container.innerHTML = `<span class="k">—</span><span class="v">데이터 없음</span>`;
    return;
  }
  Object.entries(obj).forEach(([k, v]) => {
    const kEl = document.createElement("span"); kEl.className = "k"; kEl.textContent = k;
    const vEl = document.createElement("span"); vEl.className = "v";
    vEl.textContent = typeof v === "object" ? JSON.stringify(v) : String(v);
    container.appendChild(kEl); container.appendChild(vEl);
  });
}

function renderDiagnostics(request, collection) {
  kvPairs(els.diagRequest, request ? {
    ticker: request.ticker,
    question: request.question,
    mode_hint: request.mode_hint,
    intent_kind: request.intent_kind,
    extracted_ticker: request.extracted_ticker || "",
    route_hint: request.route_hint,
    sources: (request.sources || []).join(", "),
    lookback_days: request.lookback_days,
    top_k: request.top_k,
    model: request.model,
  } : null);

  els.sourceResultsBody.innerHTML = "";
  els.providerResultsBody.innerHTML = "";

  if (!collection) {
    const noData = `<tr><td colspan="5" style="color:var(--text-mute);">수집 진단 데이터 없음</td></tr>`;
    els.sourceResultsBody.innerHTML = noData;
    els.providerResultsBody.innerHTML = noData;
    kvPairs(els.diagRetrieval, null);
    return;
  }

  (collection.source_results || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.source)}</td>
      <td><span class="st ${sourceStatusClass(r.status)}">${escapeHtml(r.status)}</span></td>
      <td>${escapeHtml(String(r.doc_count ?? 0))}</td>
      <td>${escapeHtml(String(r.elapsed_s ?? "—"))}s</td>
      <td>${escapeHtml(r.detail || "")}</td>
    `;
    els.sourceResultsBody.appendChild(tr);
  });

  (collection.provider_results || []).forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.source)}</td>
      <td><span class="st ${sourceStatusClass(r.status)}">${escapeHtml(r.status)}</span></td>
      <td>${escapeHtml(String(r.doc_count ?? 0))}</td>
      <td>${escapeHtml(String(r.elapsed_s ?? "—"))}s</td>
      <td>${escapeHtml(r.detail || "")}</td>
    `;
    els.providerResultsBody.appendChild(tr);
  });

  kvPairs(els.diagRetrieval, {
    run_started_at: collection.run_started_at || "—",
    freshness_cutoff: collection.freshness_cutoff || "—",
    retrieval_policy: collection.retrieval_policy || "—",
    current_doc_ids: (collection.current_doc_ids || []).length,
    lookback_days: collection.lookback_days || "—",
    cache_hit: collection.cache_hit ? `yes · ${formatAge(collection.cache_age_s)} old` : "no",
    cached_at: collection.cached_at || "—",
  });
}

function formatAge(sec) {
  const s = Number(sec || 0);
  if (!s || s <= 0) return "0s";
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

const STAGE_ORDER = ["collect", "ingest", "retrieve", "infer", "analyze", "report", "output"];

function renderExecutionMeta(meta) {
  if (!els.diagInference) return;
  if (!meta || typeof meta !== "object") {
    kvPairs(els.diagInference, null);
    els.stageTimeline.innerHTML = "";
    return;
  }
  const extras = meta.extras || {};
  const formatGate = (gate) => {
    if (!gate || typeof gate !== "object") return "—";
    if (gate.ok === true) return "ok";
    const missing = gate.completeness?.missing;
    if (!missing || typeof missing !== "object") return "not_ok";
    const short = Object.entries(missing)
      .filter(([, value]) => Number(value || 0) > 0)
      .map(([key, value]) => `${key}:${value}`)
      .join(", ");
    return short || "not_ok";
  };
  const shown = {
    primary_model: meta.primary_model || "—",
    producing_model: meta.producing_model || "—",
    fallback_used: meta.fallback_used === null || meta.fallback_used === undefined ? "—" : String(meta.fallback_used),
    fallback_available: meta.fallback_available === null || meta.fallback_available === undefined ? "—" : String(meta.fallback_available),
    retry_count: meta.retry_count ?? "—",
    total_latency_s: meta.total_latency_s ?? "—",
    pipeline_latency_s: meta.pipeline_latency_s ?? "—",
    prompt_char_count: meta.prompt_char_count ?? "—",
    chunks_used: meta.chunks_used ?? "—",
    lens: meta.lens || "—",
    context_horizon: meta.context_horizon || "—",
    phase: extras.phase || "—",
    retrieval_mode: extras.retrieval_mode || "—",
    cache_hit: extras.cache_hit === null || extras.cache_hit === undefined ? "—" : String(extras.cache_hit),
    ingest_skipped_docs: extras.ingest_skipped_docs ?? "—",
    deep_pass_skipped: extras.deep_pass_skipped === null || extras.deep_pass_skipped === undefined ? "—" : String(extras.deep_pass_skipped),
    deep_pass_reason: Array.isArray(extras.deep_pass_reason) ? (extras.deep_pass_reason.join(", ") || "—") : (extras.deep_pass_reason || "—"),
    warnings: Array.isArray(extras.warnings) ? (extras.warnings.join(" | ") || "—") : (extras.warnings || "—"),
    blocking_evidence_buckets: Array.isArray(extras.blocking_evidence_buckets) ? (extras.blocking_evidence_buckets.join(", ") || "—") : (extras.blocking_evidence_buckets || "—"),
    warning_evidence_buckets: Array.isArray(extras.warning_evidence_buckets) ? (extras.warning_evidence_buckets.join(", ") || "—") : (extras.warning_evidence_buckets || "—"),
    blocking_missing_buckets: Array.isArray(extras.blocking_missing_buckets) ? (extras.blocking_missing_buckets.join(", ") || "—") : (extras.blocking_missing_buckets || "—"),
    warning_missing_buckets: Array.isArray(extras.warning_missing_buckets) ? (extras.warning_missing_buckets.join(", ") || "—") : (extras.warning_missing_buckets || "—"),
    substituted_buckets: Array.isArray(extras.substituted_buckets) ? (extras.substituted_buckets.join(", ") || "—") : (extras.substituted_buckets || "—"),
    error_type: extras.error_type || "—",
    data_freshness: extras.data_freshness || "—",
    provider_status: extras.provider_status || "—",
    model_capabilities: extras.model_capabilities || "—",
    validation_summary: extras.validation_summary || "—",
    retrieval_plan: extras.retrieval_plan || "—",
    quality_metrics: extras.quality_metrics || "—",
    numeric_grounding_warnings: Array.isArray(extras.numeric_grounding_warnings) ? (extras.numeric_grounding_warnings.join(" | ") || "—") : (extras.numeric_grounding_warnings || "—"),
    confidence_caps: Array.isArray(extras.confidence_caps) ? (extras.confidence_caps.join(" | ") || "—") : (extras.confidence_caps || "—"),
    run_manifest: extras.run_manifest || "—",
    fast_gate: formatGate(extras.fast_gate),
    final_gate: formatGate(extras.final_gate),
  };
  kvPairs(els.diagInference, shown);

  els.stageTimeline.innerHTML = "";
  const stageTimings = extras.stage_timings || {};
  const normalizeStage = (name) => {
    const raw = String(name || "");
    if (raw.startsWith("retrieve")) return "retrieve";
    if (raw.startsWith("infer")) return "infer";
    return raw;
  };
  const ran = new Set(Array.isArray(meta.stages_ran) ? meta.stages_ran : []);
  Object.keys(stageTimings).forEach((name) => ran.add(normalizeStage(name)));
  STAGE_ORDER.forEach((name) => {
    const durations = Object.entries(stageTimings)
      .filter(([key]) => normalizeStage(key) === name)
      .map(([, value]) => `${value}s`);
    const pill = document.createElement("span");
    pill.className = "stage-pill " + (ran.has(name) ? "ran" : "skipped");
    pill.textContent = durations.length ? `${name} ${durations.join(" / ")}` : name;
    els.stageTimeline.appendChild(pill);
  });
}

function renderRaw(data) {
  els.rawJson.textContent = JSON.stringify(data, null, 2);
}

async function fetchMarkdownReport() {
  try {
    const res = await fetch(API.reportMd);
    if (res.ok) {
      els.reportMd.textContent = await res.text();
    } else {
      els.reportMd.textContent = "# Report not available yet.";
    }
  } catch {
    els.reportMd.textContent = "# Report not available.";
  }
}

// ---------- Tabs ----------
function bindTabs() {
  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      els.tabs.forEach((t) => t.classList.toggle("active", t === tab));
      els.tabPanels.forEach((p) => p.classList.toggle("active", p.dataset.panel === target));
    });
  });
}

// ---------- Downloads ----------
function downloadBlob(name, text, type = "text/plain") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
}

function bindDownloads() {
  els.downloadMdBtn.addEventListener("click", async () => {
    try {
      const res = await fetch(API.reportMd);
      const text = res.ok ? await res.text() : els.reportMd.textContent;
      const ticker = state.lastResponse?.ticker || "report";
      downloadBlob(`fingpt_${ticker}_${Date.now()}.md`, text, "text/markdown");
    } catch (e) { alert("Markdown 다운로드 실패: " + e.message); }
  });

  els.downloadJsonBtn.addEventListener("click", () => {
    if (!state.lastResponse) return;
    const ticker = state.lastResponse.ticker || "response";
    downloadBlob(`fingpt_${ticker}_${Date.now()}.json`, JSON.stringify(state.lastResponse, null, 2), "application/json");
  });

  els.openHtmlBtn.addEventListener("click", () => {
    window.open(API.reportHtml, "_blank", "noopener");
  });

  const exportToggle = document.getElementById("exportToggleBtn");
  const exportMenu = document.getElementById("exportMenu");
  if (exportToggle && exportMenu) {
    exportToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      exportMenu.classList.toggle("hidden");
    });
    // Dismiss when clicking anywhere outside — feels native without managing focus.
    document.addEventListener("click", (e) => {
      if (!exportMenu.classList.contains("hidden") && !exportMenu.contains(e.target) && e.target !== exportToggle) {
        exportMenu.classList.add("hidden");
      }
    });
    exportMenu.querySelectorAll("button[data-export]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        exportMenu.classList.add("hidden");
        const kind = btn.dataset.export;
        try {
          await runExport(kind);
        } catch (err) {
          alert(`Export 실패: ${err.message || err}`);
        }
      });
    });
  }
}

async function runExport(kind) {
  if (!state.lastResponse) {
    alert("먼저 분석을 실행하거나 히스토리에서 불러오세요.");
    return;
  }
  // kind => endpoint + query string. The server reads the latest archived
  // response when run_id is omitted, so single-runs just work.
  let url, filename, mime;
  const ticker = state.lastResponse.ticker || "analysis";
  const stamp = Date.now();
  if (kind === "csv") {
    url = "/api/v1/outputs/export/csv";
    filename = `fingpt_${ticker}_${stamp}.csv`;
    mime = "text/csv";
  } else if (kind === "jsonl") {
    url = "/api/v1/outputs/export/jsonl?include_raw_context=true";
    filename = `fingpt_${ticker}_${stamp}.jsonl`;
    mime = "application/x-ndjson";
  } else if (kind === "jsonl-lean") {
    url = "/api/v1/outputs/export/jsonl?include_raw_context=false";
    filename = `fingpt_${ticker}_${stamp}_lean.jsonl`;
    mime = "application/x-ndjson";
  } else {
    return;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${detail.slice(0, 160)}`);
  }
  const text = await res.text();
  downloadBlob(filename, text, mime);
}

// ---------- Load latest ----------
async function loadLatest() {
  try {
    const res = await fetch(API.latest);
    if (!res.ok) throw new Error("no data");
    const blob = await res.json();
    if (!blob.response) {
      alert("이전 실행 결과를 찾을 수 없습니다. 먼저 한 번 분석을 실행하세요.");
      return;
    }
    renderResponse(blob.response, blob.collection || null, blob.request || null);
  } catch (e) {
    alert("최신 결과 로드 실패: " + e.message);
  }
}

// ---------- Bindings ----------
function openDateInputPicker(input) {
  if (!input || input.disabled || input.readOnly) return;
  input.focus({ preventScroll: true });
  if (typeof input.showPicker !== "function") return;
  try {
    input.showPicker();
  } catch (_err) {
    // Browser may reject showPicker outside direct user activation; focus is still useful fallback.
  }
}

function bindDateInputs() {
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    input.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || input.disabled || input.readOnly) return;
      if (typeof input.showPicker === "function") {
        event.preventDefault();
        openDateInputPicker(input);
      }
    });
    input.addEventListener("keydown", (event) => {
      if (!["Enter", " ", "ArrowDown"].includes(event.key)) return;
      event.preventDefault();
      openDateInputPicker(input);
    });
  });
}

function bindInputs() {
  bindDateInputs();
  els.tickerChips.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const chipTicker = btn.dataset.ticker;
      if (els.compareMode && els.compareMode.checked) {
        const current = els.ticker.value
          .split(/[\s,]+/)
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean);
        if (!current.includes(chipTicker)) current.push(chipTicker);
        els.ticker.value = current.join(", ");
      } else {
        els.ticker.value = chipTicker;
      }
      els.ticker.focus();
      persistForm();
      refreshRoutingNotice();
    });
  });
  if (els.tickerSearchOpen) els.tickerSearchOpen.addEventListener("click", () => openSymbolPicker("research"));
  if (els.crossAssetSymbolOpen) els.crossAssetSymbolOpen.addEventListener("click", () => openSymbolPicker("crossAssetSymbols"));
  if (els.crossAssetRun) els.crossAssetRun.addEventListener("click", () => loadCrossAssetAnalysis(true));
  [els.crossAssetSymbols, els.crossAssetTopic].forEach((input) => {
    if (!input) return;
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      loadCrossAssetAnalysis(true);
    });
  });
  if (els.crossAssetHorizon) els.crossAssetHorizon.addEventListener("change", () => loadCrossAssetAnalysis(true));
  if (els.homeNewsTickerOpen) els.homeNewsTickerOpen.addEventListener("click", () => openSymbolPicker("homeNewsTicker"));
  if (els.homeNewsSearchRun) els.homeNewsSearchRun.addEventListener("click", () => loadFocusedDashboardNews(true));
  [els.homeNewsTicker, els.homeNewsTopic].forEach((input) => {
    if (!input) return;
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      loadFocusedDashboardNews(true);
    });
  });
  if (els.compareMode) {
    els.compareMode.addEventListener("change", () => {
      updateCompareModeUI();
      persistForm();
      refreshRoutingNotice();
    });
    updateCompareModeUI();
  }
  els.ticker.addEventListener("input", () => { persistForm(); refreshRoutingNotice(); });
  els.researchModeInputs().forEach((i) => i.addEventListener("change", () => {
    updateCompareModeUI();
    persistForm();
    refreshRoutingNotice();
  }));
  els.question.addEventListener("input", () => { persistForm(); refreshRoutingNotice(); });
  els.model.addEventListener("change", persistForm);
  els.sourceInputs().forEach((i) => i.addEventListener("change", persistForm));

  els.lookback.addEventListener("input", () => {
    els.lookback.dataset.dirty = "1";
    updateRangeLabels(); persistForm();
  });
  els.topk.addEventListener("input", () => {
    els.topk.dataset.dirty = "1";
    updateRangeLabels(); persistForm();
  });

  els.form.addEventListener("submit", runAnalysis);

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });

  els.loadLatestBtn.addEventListener("click", loadLatest);
  if (els.homeBtn) els.homeBtn.addEventListener("click", showHome);
  if (els.marketDashboardTab) {
    els.marketDashboardTab.addEventListener("click", () => setDashboardTab("market", { updateUrl: true }));
  }
  if (els.macroDashboardTab) {
    els.macroDashboardTab.addEventListener("click", () => setDashboardTab("macro", { updateUrl: true }));
  }
  if (els.quantLabTab) {
    els.quantLabTab.addEventListener("click", () => setDashboardTab("quant", { updateUrl: true }));
  }
  if (els.quantamentalTab) {
    els.quantamentalTab.addEventListener("click", () => setDashboardTab("quantamental", { updateUrl: true }));
  }
  if (els.mlForecastTab) {
    els.mlForecastTab.addEventListener("click", () => setDashboardTab("forecast", { updateUrl: true }));
  }
  if (els.aiPortfolioTab) {
    els.aiPortfolioTab.addEventListener("click", () => setDashboardTab("ai-portfolio", { updateUrl: true }));
  }
  if (els.homeDashboardTabs) {
    els.homeDashboardTabs.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-dashboard-tab]") : rawTarget;
      const nextTab = target?.dataset?.dashboardTab;
      if (!nextTab) return;
      event.preventDefault();
      setDashboardTab(nextTab, { updateUrl: true });
    });
  }
  if (els.dashboardViewControls) {
    els.dashboardViewControls.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-panel-view]") : rawTarget;
      const nextView = target?.dataset?.panelView;
      if (!nextView) return;
      event.preventDefault();
      setDashboardPanelView(nextView);
    });
  }
  if (els.dashboardRangeSelect) {
    els.dashboardRangeSelect.addEventListener("change", () => {
      setGlobalRange(els.dashboardRangeSelect.value, { persist: true, updateUrl: true, reload: true });
    });
  }
  [els.dashboardRangeStart, els.dashboardRangeEnd].forEach((input) => {
    if (!input) return;
    input.addEventListener("change", () => {
      setGlobalRange("custom", {
        startDate: els.dashboardRangeStart?.value || "",
        endDate: els.dashboardRangeEnd?.value || "",
        persist: true,
        updateUrl: true,
        reload: true,
      });
    });
  });
  window.addEventListener("hashchange", () => {
    const requestedTab = dashboardTabFromLocation();
    if (requestedTab) setDashboardTab(requestedTab);
  });
  if (els.homeNewsRefresh) els.homeNewsRefresh.addEventListener("click", () => {
    loadMarketDashboard(true);
    loadFocusedDashboardNews(true);
  });
  document.addEventListener("click", (event) => {
    const rawTarget = event.target;
    const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
    if (target?.dataset?.action === "enable-strict-freshness") {
      event.preventDefault();
      enableStrictFreshnessFromUi();
    }
  });
  if (els.homeHeatmapRefresh) els.homeHeatmapRefresh.addEventListener("click", () => loadDashboardEquityHeatmap(true));
  if (els.dataHealthRefresh) els.dataHealthRefresh.addEventListener("click", () => loadDataHealth(true));
  if (els.macroRefresh) els.macroRefresh.addEventListener("click", () => refreshMacroData());
  if (els.macroBriefGenerate) els.macroBriefGenerate.addEventListener("click", () => generateMacroBrief());
  if (els.macroReportExport) els.macroReportExport.addEventListener("click", () => exportMacroReport());
  if (els.macroSeriesSearchRun) els.macroSeriesSearchRun.addEventListener("click", () => searchMacroSeries());
  [els.macroCategoryFilter, els.macroProviderFilter].forEach((control) => {
    if (!control) return;
    control.addEventListener("change", () => {
      if (state.macroSeriesSearch?.items?.length) {
        renderMacroSeriesSearchResults(state.macroSeriesSearch);
      } else {
        renderMacroSearchStarter(state.macroSeriesList || {});
      }
    });
  });
  if (els.macroScenarioSurface) {
    els.macroScenarioSurface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest('[data-action="macro-scenario"]') : null;
      if (!target?.dataset?.scenarioPreset) return;
      event.preventDefault();
      runMacroScenario(target.dataset.scenarioPreset);
    });
  }
  if (els.macroResearchPreviewRun) els.macroResearchPreviewRun.addEventListener("click", () => runMacroResearchPreview());
  if (els.macroResearchTicker) {
    els.macroResearchTicker.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runMacroResearchPreview();
      }
    });
  }
  if (els.macroSeriesSearchInput) {
    els.macroSeriesSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchMacroSeries();
      }
    });
  }
  [els.macroSeriesSearchResults, els.macroSeriesDetailSurface].forEach((surface) => {
    if (!surface) return;
    surface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-macro-series-id]") : null;
      if (!target?.dataset?.macroSeriesId) return;
      event.preventDefault();
      loadMacroSeriesDetail(target.dataset.macroSeriesId);
    });
  });
  if (els.assetDetailLoad) els.assetDetailLoad.addEventListener("click", loadAssetDetail);
  if (els.assetDetailTickerOpen) els.assetDetailTickerOpen.addEventListener("click", () => openSymbolPicker("assetDetailTicker"));
  if (els.assetDetailBenchmarkOpen) els.assetDetailBenchmarkOpen.addEventListener("click", () => openSymbolPicker("assetDetailBenchmark"));
  if (els.assetDetailTicker) {
    els.assetDetailTicker.addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadAssetDetail();
    });
  }
  [els.assetDetailRange, els.assetDetailStartDate, els.assetDetailEndDate, els.assetDetailView, els.assetDetailBenchmark, els.assetDetailBenchmarkCompare].forEach((control) => {
    if (control) control.addEventListener("change", () => {
      if (els.assetDetailSurface?.querySelector?.(".decision-status-row")) loadAssetDetail();
    });
  });
  if (els.quantFeatureRun) els.quantFeatureRun.addEventListener("click", runQuantFeaturePreview);
  if (els.quantSignalRun) els.quantSignalRun.addEventListener("click", runQuantSignalPreview);
  if (els.quantStrategyRefresh) els.quantStrategyRefresh.addEventListener("click", () => loadQuantStrategies(true));
  if (els.quantStrategyNewDraft) els.quantStrategyNewDraft.addEventListener("click", () => {
    setStrategyEditor(quantStrategyDraftFromControls());
    renderStrategyPromptReview({
      advantages: ["현재 백테스트 조건에서 바로 검증 가능한 보수적 JSON 초안입니다."],
      disadvantages: ["프롬프트 기반 생성이 아니므로 진입/청산 아이디어는 직접 조정해야 합니다."],
      warnings: [],
    });
    showQuantStrategyMessage("현재 퀀트 랩 조건으로 전략 초안을 만들었습니다.", "success");
  });
  if (els.quantStrategyGenerate) els.quantStrategyGenerate.addEventListener("click", runQuantStrategyGenerate);
  if (els.quantStrategyDryRun) els.quantStrategyDryRun.addEventListener("click", () => runQuantStrategyDryRun());
  if (els.quantStrategySave) els.quantStrategySave.addEventListener("click", saveQuantStrategy);
  if (els.quantStrategyDelete) els.quantStrategyDelete.addEventListener("click", () => deleteQuantStrategy());
  if (els.quantRunHistoryRefresh) els.quantRunHistoryRefresh.addEventListener("click", () => loadQuantRunHistory(true));
  if (els.quantExportStorageReport) els.quantExportStorageReport.addEventListener("click", loadQuantExportStorageReport);
  if (els.quantCrossRunCleanupPreview) els.quantCrossRunCleanupPreview.addEventListener("click", () => previewCrossRunExportCleanup(1, 0));
  if (els.quantRunHistorySurface) {
    els.quantRunHistorySurface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
      if (target && target.dataset && target.dataset.action === "cross-run-cleanup-preview") {
        previewCrossRunExportCleanup(target.dataset.keepLast || 1, target.dataset.staleAfterDays || 0);
      }
      if (target && target.dataset && target.dataset.action === "cross-run-cleanup-apply") {
        applyCrossRunExportCleanup();
      }
      if (target && target.dataset && target.dataset.action === "toggle-run-compare") {
        setQuantRunCompareSelection(target.dataset.runId || "", !!target.checked);
      }
      if (target && target.dataset && target.dataset.action === "run-compare-selected") {
        compareSelectedQuantRuns();
      }
      if (target && target.dataset && target.dataset.action === "open-quant-run") {
        loadQuantBacktestArtifact(target.dataset.runId || "");
      }
      if (target && target.dataset && target.dataset.action === "refresh-run-history") {
        loadQuantRunHistory(true);
      }
    });
  }
  if (els.backtestRun) els.backtestRun.addEventListener("click", runHomeBacktest);
  if (els.forecastTickerOpen) els.forecastTickerOpen.addEventListener("click", () => openSymbolPicker("forecastTicker"));
  if (els.forecastBenchmarkOpen) els.forecastBenchmarkOpen.addEventListener("click", () => openSymbolPicker("forecastBenchmark"));
  if (els.forecastPreviewDataset) els.forecastPreviewDataset.addEventListener("click", runForecastDatasetPreview);
  if (els.forecastHydrateDataset) els.forecastHydrateDataset.addEventListener("click", runForecastDatasetHydrate);
  if (els.forecastBuildFeatures) els.forecastBuildFeatures.addEventListener("click", runForecastFeatureAndLeakagePreview);
  if (els.forecastRunTrain) els.forecastRunTrain.addEventListener("click", runForecastExperiment);
  if (els.forecastQueueJob) els.forecastQueueJob.addEventListener("click", runForecastQueuedJob);
  if (els.forecastGenerateAi) els.forecastGenerateAi.addEventListener("click", renderForecastAiFromLastPayload);
  if (els.forecastGenerateProviderAi) els.forecastGenerateProviderAi.addEventListener("click", renderForecastProviderAiFromLastPayload);
  if (els.forecastAiProviderCheck) els.forecastAiProviderCheck.addEventListener("click", () => loadForecastAiProviderStatus(true));
  if (els.forecastDriftRefresh) els.forecastDriftRefresh.addEventListener("click", () => loadForecastDrift(true));
  if (els.forecastModelComparisonRefresh) els.forecastModelComparisonRefresh.addEventListener("click", () => loadForecastModelComparison(true));
  if (els.forecastJobsRefresh) els.forecastJobsRefresh.addEventListener("click", () => loadForecastJobs(true));
  if (els.forecastHistoryRefresh) els.forecastHistoryRefresh.addEventListener("click", () => loadForecastHistory(true));
  if (els.forecastRegistryRefresh) els.forecastRegistryRefresh.addEventListener("click", () => loadForecastRegistry(true));
  if (els.forecastJobsSurface) {
    els.forecastJobsSurface.addEventListener("click", async (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
      if (!target || !target.dataset) return;
      if (target.dataset.action === "forecast-job-refresh") {
        await refreshForecastJob(target.dataset.jobId);
      } else if (target.dataset.action === "forecast-job-cancel") {
        await cancelForecastJob(target.dataset.jobId);
      } else if (target.dataset.action === "forecast-job-retry") {
        await retryForecastJob(target.dataset.jobId);
      } else if (target.dataset.action === "forecast-experiment-detail") {
        await openForecastExperimentDetail(target.dataset.experimentId);
      }
    });
  }
  if (els.forecastHistorySurface) {
    els.forecastHistorySurface.addEventListener("click", async (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
      if (target?.dataset?.action === "forecast-experiment-detail") {
        await openForecastExperimentDetail(target.dataset.experimentId);
      }
    });
  }
  if (els.forecastDetailClose) els.forecastDetailClose.addEventListener("click", closeForecastExperimentDetail);
  if (els.forecastDetailModal) {
    els.forecastDetailModal.addEventListener("click", (event) => {
      if (event.target === els.forecastDetailModal) closeForecastExperimentDetail();
    });
  }
  if (els.forecastRegistrySurface) {
    els.forecastRegistrySurface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
      if (!target || !target.dataset || !target.dataset.modelId) return;
      if (target.dataset.action === "forecast-promote" || target.dataset.action === "forecast-deprecate") {
        updateForecastModelStatus(target.dataset.action, target.dataset.modelId);
      } else if (target.dataset.action === "forecast-verify-artifact") {
        verifyForecastModelArtifact(target.dataset.modelId);
      }
    });
  }
  if (els.quantamentalAnalyze) els.quantamentalAnalyze.addEventListener("click", runQuantamentalAnalysis);
  if (els.quantamentalTicker) {
    els.quantamentalTicker.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runQuantamentalAnalysis();
      }
    });
    els.quantamentalTicker.addEventListener("input", () => {
      els.quantamentalTicker.value = String(els.quantamentalTicker.value || "").toUpperCase();
    });
  }
  if (els.quantamentalTickerOpen) els.quantamentalTickerOpen.addEventListener("click", () => openSymbolPicker("quantamentalTicker"));
  if (els.quantamentalAiRefresh) els.quantamentalAiRefresh.addEventListener("click", refreshQuantamentalAiReport);
  if (els.quantamentalAiModel) els.quantamentalAiModel.addEventListener("change", updateQuantamentalAiModelStatus);
  if (els.quantamentalCompareRun) els.quantamentalCompareRun.addEventListener("click", runQuantamentalCompare);
  if (els.quantamentalScreenRun) els.quantamentalScreenRun.addEventListener("click", () => loadQuantamentalScreen(true));
  if (els.quantamentalScoreScreenRun) els.quantamentalScoreScreenRun.addEventListener("click", runQuantamentalScoreScreen);
  if (els.quantamentalScoreThreshold) {
    els.quantamentalScoreThreshold.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runQuantamentalScoreScreen();
      }
    });
    els.quantamentalScoreThreshold.addEventListener("change", quantamentalScoreScreenThreshold);
  }
  if (els.quantamentalWatchlistSave) els.quantamentalWatchlistSave.addEventListener("click", () => saveQuantamentalCompareWatchlist().catch((err) => {
    if (els.quantamentalCompareSurface) els.quantamentalCompareSurface.innerHTML = quantamentalUi().error ? quantamentalUi().error(err.message || String(err)) : decisionEmpty(err.message || String(err));
  }));
  if (els.quantamentalWatchlistLoad) els.quantamentalWatchlistLoad.addEventListener("click", loadQuantamentalCompareWatchlist);
  if (els.quantamentalCompareCsv) els.quantamentalCompareCsv.addEventListener("click", exportQuantamentalCompareCsv);
  if (els.quantamentalCompareTickers) {
    els.quantamentalCompareTickers.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runQuantamentalCompare();
      }
    });
  }
  [els.quantamentalMarket, els.quantamentalPeriod, els.quantamentalYears, els.quantamentalLookback, els.quantamentalStyle, els.quantamentalScoreMetric, els.quantamentalScoreScreenLimit].forEach((control) => {
    if (!control) return;
    control.addEventListener("change", () => {
      state.quantamentalScreenLoaded = false;
      state.quantamentalScoreScreen = null;
    });
  });
  if (els.quantamentalMainSurface) {
    els.quantamentalMainSurface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const tabTarget = rawTarget?.closest ? rawTarget.closest("[data-quantamental-tab]") : null;
      if (tabTarget?.dataset?.quantamentalTab) {
        event.preventDefault();
        state.quantamentalActiveTab = tabTarget.dataset.quantamentalTab;
        if (state.quantamentalAnalysis) renderQuantamentalAnalysis(state.quantamentalAnalysis);
        return;
      }
      const askTarget = rawTarget?.closest ? rawTarget.closest("#quantamentalAsk") : null;
      if (askTarget) {
        event.preventDefault();
        askQuantamentalQuestion();
      }
      const actionTarget = rawTarget?.closest ? rawTarget.closest("[data-quantamental-action]") : null;
      if (actionTarget?.dataset?.quantamentalAction) {
        event.preventDefault();
        const action = actionTarget.dataset.quantamentalAction;
        if (action === "export-snapshot-json") exportQuantamentalSnapshot("json").catch((err) => alert(`Snapshot export failed: ${err.message || err}`));
        if (action === "export-snapshot-csv") exportQuantamentalSnapshot("csv").catch((err) => alert(`Snapshot export failed: ${err.message || err}`));
        if (action === "diff-snapshot") diffQuantamentalSnapshot().catch((err) => alert(`Snapshot diff failed: ${err.message || err}`));
        if (action === "retention-preview") previewQuantamentalSnapshotRetention().catch((err) => alert(`Retention preview failed: ${err.message || err}`));
      }
    });
  }
  if (els.backtestTicker) els.backtestTicker.addEventListener("input", () => {
    state.lastUniverseResolution = null;
    renderBacktestUniverseChips();
  });
  if (els.backtestUniverseOpen) els.backtestUniverseOpen.addEventListener("click", () => openSymbolPicker("backtest"));
  if (els.backtestBenchmarkOpen) els.backtestBenchmarkOpen.addEventListener("click", () => openSymbolPicker("backtestBenchmark"));
  if (els.backtestStrategy) {
    els.backtestStrategy.addEventListener("change", () => {
      state.activeStrategyId = "";
      if (els.backtestStrategyRegistry) els.backtestStrategyRegistry.value = "";
    });
  }
  if (els.backtestStrategyRegistry) {
    els.backtestStrategyRegistry.addEventListener("change", () => {
      const strategyId = els.backtestStrategyRegistry.value || "";
      if (!strategyId) {
        state.activeStrategyId = "";
        return;
      }
      loadQuantStrategyDetail(strategyId);
    });
  }
  if (els.symbolPickerClose) els.symbolPickerClose.addEventListener("click", closeSymbolPicker);
  if (els.symbolPickerApply) els.symbolPickerApply.addEventListener("click", closeSymbolPicker);
  if (els.symbolPickerClear) {
    els.symbolPickerClear.addEventListener("click", () => {
      setSymbolTargetSymbols(state.symbolPickerTarget || symbolPickerTarget("backtest"), []);
      renderSymbolPicker();
    });
  }
  if (els.symbolPickerAddFiltered) els.symbolPickerAddFiltered.addEventListener("click", addFilteredSymbolsToBacktestUniverse);
  if (els.symbolPickerRemoveFiltered) els.symbolPickerRemoveFiltered.addEventListener("click", removeFilteredSymbolsFromBacktestUniverse);
  if (els.symbolPickerSearch) els.symbolPickerSearch.addEventListener("input", renderSymbolPicker);
  if (els.symbolPickerCountry) els.symbolPickerCountry.addEventListener("change", renderSymbolPicker);
  if (els.symbolPickerSector) els.symbolPickerSector.addEventListener("change", renderSymbolPicker);
  if (els.symbolPickerSummary) {
    els.symbolPickerSummary.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-symbol-scope]") : rawTarget;
      if (target?.dataset?.symbolScope) applySymbolPickerScope(target.dataset.symbolScope);
    });
  }
  if (els.symbolPickerSelected) {
    els.symbolPickerSelected.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const selectAll = rawTarget?.closest ? rawTarget.closest("[data-symbol-select-all]") : null;
      const clearSelected = rawTarget?.closest ? rawTarget.closest("[data-symbol-clear-selected]") : null;
      if (selectAll) addFilteredSymbolsToBacktestUniverse();
      if (clearSelected) {
        setSymbolTargetSymbols(state.symbolPickerTarget || symbolPickerTarget("backtest"), []);
        renderSymbolPicker();
      }
    });
  }
  if (els.symbolPickerTabs) {
    els.symbolPickerTabs.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-symbol-type]") : rawTarget;
      if (!target?.dataset?.symbolType) return;
      setSymbolPickerType(target.dataset.symbolType || "all");
      renderSymbolPicker();
    });
  }
  if (els.symbolPickerList) {
    els.symbolPickerList.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-symbol-toggle]") : rawTarget;
      if (target?.dataset?.symbolToggle) toggleSymbolPickerItem(target.dataset.symbolToggle);
    });
  }
  if (els.symbolPickerModal) {
    els.symbolPickerModal.addEventListener("click", (event) => {
      if (event.target === els.symbolPickerModal) closeSymbolPicker();
    });
  }
  if (els.backtestSurface) {
    els.backtestSurface.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-action]") : rawTarget;
      if (target && target.dataset && target.dataset.action === "sync-backtest-portfolio") {
        syncPortfolioFromBacktest();
      }
      if (target && target.dataset && target.dataset.action === "replay-backtest") {
        runQuantBacktestReplay(target.dataset.runId || "");
      }
      if (target && target.dataset && target.dataset.action === "replay-reports") {
        loadQuantReplayReports(target.dataset.runId || "");
      }
      if (target && target.dataset && target.dataset.action === "export-backtest") {
        exportQuantBacktestArtifact(target.dataset.runId || "", target.dataset.format || "jsonl");
      }
      if (target && target.dataset && target.dataset.action === "export-history") {
        loadQuantExportHistory(target.dataset.runId || "");
      }
      if (target && target.dataset && target.dataset.action === "export-cleanup-preview") {
        previewQuantExportCleanup(target.dataset.runId || "");
      }
      if (target && target.dataset && target.dataset.action === "export-cleanup-apply") {
        applyQuantExportCleanup(target.dataset.runId || "", target.dataset.keepLast || "");
      }
      if (target && target.dataset && target.dataset.action === "verify-export") {
        verifyQuantExport(target.dataset.runId || "", target.dataset.manifestPath || "");
      }
    });
  }
  if (els.portfolioSyncBacktest) {
    els.portfolioSyncBacktest.addEventListener("click", syncPortfolioFromBacktest);
  }
  if (els.portfolioTickers) {
    els.portfolioTickers.addEventListener("input", () => renderSymbolTargetChips("portfolio"));
  }
  if (els.portfolioUniverseOpen) els.portfolioUniverseOpen.addEventListener("click", () => openSymbolPicker("portfolio"));
  if (els.portfolioBenchmarkOpen) els.portfolioBenchmarkOpen.addEventListener("click", () => openSymbolPicker("portfolioBenchmark"));
  if (els.portfolioOptimize) els.portfolioOptimize.addEventListener("click", runPortfolioOptimize);
  if (els.aiPortfolioInvestmentTypes) {
    els.aiPortfolioInvestmentTypes.addEventListener("click", (event) => {
      const rawTarget = event.target;
      const target = rawTarget?.closest ? rawTarget.closest("[data-ai-investment-type]") : rawTarget;
      const typeId = target?.dataset?.aiInvestmentType;
      if (!typeId) return;
      const template = state.aiPortfolioInvestmentTypes.find((item) => item.id === typeId);
      applyAiPortfolioTemplate(template);
      renderAiPortfolioInvestmentTypes(state.aiPortfolioInvestmentTypes);
    });
  }
  if (els.aiPortfolioGenerate) els.aiPortfolioGenerate.addEventListener("click", runAiPortfolioGenerate);
  if (els.aiPortfolioOpsRefresh) {
    els.aiPortfolioOpsRefresh.addEventListener("click", () => {
      clearAiPortfolioDashboardCache();
      loadAiPortfolioOps(true);
    });
  }
  if (els.aiPortfolioRefreshPolicies) els.aiPortfolioRefreshPolicies.addEventListener("click", () => loadAiPortfolioPolicies(true));
  if (els.aiPortfolioHydrateData) els.aiPortfolioHydrateData.addEventListener("click", () => runAiPortfolioHydrateData({ missingOnly: false }));
  if (els.aiPortfolioRetryMissing) els.aiPortfolioRetryMissing.addEventListener("click", () => runAiPortfolioHydrateData({ missingOnly: true }));
  if (els.aiPortfolioSnapshotJob) els.aiPortfolioSnapshotJob.addEventListener("click", runAiPortfolioSnapshotJob);
  if (els.aiPortfolioSecRefresh) els.aiPortfolioSecRefresh.addEventListener("click", runAiPortfolioSecRefresh);
  if (els.aiPortfolioUniverse) els.aiPortfolioUniverse.addEventListener("change", syncAiPortfolioUniverseMode);
  if (els.aiPortfolioCustomUniverse) {
    els.aiPortfolioCustomUniverse.addEventListener("input", () => {
      renderSymbolTargetChips("aiPortfolioCustomUniverse");
      syncAiPortfolioUniverseMode();
    });
  }
  if (els.aiPortfolioCustomUniverseOpen) {
    els.aiPortfolioCustomUniverseOpen.addEventListener("click", () => {
      if (els.aiPortfolioUniverse) els.aiPortfolioUniverse.value = "custom";
      syncAiPortfolioUniverseMode();
      openSymbolPicker("aiPortfolioCustomUniverse");
    });
  }
  if (els.aiPortfolioBenchmarkOpen) els.aiPortfolioBenchmarkOpen.addEventListener("click", () => openSymbolPicker("aiPortfolioBenchmark"));
  if (els.aiPortfolioGenerateQuick) {
    els.aiPortfolioGenerateQuick.addEventListener("click", () => {
      setDashboardTab("ai-portfolio", { updateUrl: true });
      runAiPortfolioGenerate();
    });
  }
  if (els.aiPortfolioCheckRebalance) els.aiPortfolioCheckRebalance.addEventListener("click", runAiPortfolioRebalanceCheck);
  if (els.aiPortfolioCheckRebalanceQuick) els.aiPortfolioCheckRebalanceQuick.addEventListener("click", runAiPortfolioRebalanceCheck);
  if (els.aiPortfolioApproveRebalance) els.aiPortfolioApproveRebalance.addEventListener("click", () => updateAiPortfolioSignal("approve"));
  if (els.aiPortfolioRejectRebalance) els.aiPortfolioRejectRebalance.addEventListener("click", () => updateAiPortfolioSignal("reject"));
  if (els.aiPortfolioDeferRebalance) els.aiPortfolioDeferRebalance.addEventListener("click", () => updateAiPortfolioSignal("defer"));
  if (els.aiPortfolioReportWeekly) els.aiPortfolioReportWeekly.addEventListener("click", () => generateAiPortfolioReport("weekly"));
  if (els.aiPortfolioReportMonthly) els.aiPortfolioReportMonthly.addEventListener("click", () => generateAiPortfolioReport("monthly"));
  if (els.aiPortfolioReportRebalance) els.aiPortfolioReportRebalance.addEventListener("click", () => generateAiPortfolioReport("rebalance"));
  if (els.aiPortfolioReportQuick) els.aiPortfolioReportQuick.addEventListener("click", () => generateAiPortfolioReport("weekly"));
  if (els.aiPortfolioAdvancedToggle && els.aiPortfolioPolicyForm) {
    els.aiPortfolioAdvancedToggle.addEventListener("change", () => {
      els.aiPortfolioPolicyForm.classList.toggle("hidden", !els.aiPortfolioAdvancedToggle.checked);
    });
  }
  if (els.historyToggleBtn) {
    els.historyToggleBtn.addEventListener("click", () => {
      state.historyExpanded = !state.historyExpanded;
      renderHistory();
    });
  }
  els.clearHistoryBtn.addEventListener("click", () => {
    alert("서버 기반 히스토리는 디스크에 영속 저장됩니다.\n삭제가 필요하면 data/outputs/runs/ 폴더와 data/runs.db 파일을 직접 정리하세요.");
  });

  els.evidenceSearch.addEventListener("input", applyEvidenceFilter);

  if (els.preflightPill) {
    els.preflightPill.addEventListener("click", () => {
      if (els.preflightPanel.classList.contains("hidden")) openPreflightPanel();
      else closePreflightPanel();
    });
  }
  if (els.preflightClose) {
    els.preflightClose.addEventListener("click", closePreflightPanel);
  }
  if (els.preflightRefresh) {
    els.preflightRefresh.addEventListener("click", async () => {
      els.preflightLabel.textContent = "preflight…";
      els.preflightPill.classList.remove("ok", "warn", "err");
      const r = await loadPreflight(true);
      if (r) renderPreflightPanel(r);
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !els.preflightPanel.classList.contains("hidden")) {
      closePreflightPanel();
    }
  });

  if (els.qdrantAdminBtn) {
    els.qdrantAdminBtn.addEventListener("click", () => {
      if (els.qdrantPanel.classList.contains("hidden")) openQdrantPanel();
      else closeQdrantPanel();
    });
  }
  if (els.qdrantClose) els.qdrantClose.addEventListener("click", closeQdrantPanel);
  if (els.qdrantRefresh) els.qdrantRefresh.addEventListener("click", loadQdrantInfo);
  if (els.qdrantPurgeDryRun) els.qdrantPurgeDryRun.addEventListener("click", () => runQdrantPurge(true));
  if (els.qdrantPurgeRun) els.qdrantPurgeRun.addEventListener("click", () => runQdrantPurge(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && els.qdrantPanel && !els.qdrantPanel.classList.contains("hidden")) {
      closeQdrantPanel();
    }
  });

  if (els.qualityDashBtn) {
    els.qualityDashBtn.addEventListener("click", () => {
      if (els.qualityPanel.classList.contains("hidden")) openQualityPanel();
      else closeQualityPanel();
    });
  }
  if (els.globalQualitySummary) {
    els.globalQualitySummary.addEventListener("click", () => {
      if (els.qualityPanel.classList.contains("hidden")) openQualityPanel();
      else closeQualityPanel();
    });
  }
  if (els.qualityClose) els.qualityClose.addEventListener("click", closeQualityPanel);
  if (els.qualityRefresh) els.qualityRefresh.addEventListener("click", loadQualityDashboard);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && els.qualityPanel && !els.qualityPanel.classList.contains("hidden")) {
      closeQualityPanel();
    }
    if (e.key === "Escape" && els.symbolPickerModal && !els.symbolPickerModal.classList.contains("hidden")) {
      closeSymbolPicker();
    }
    if (e.key === "Escape" && els.forecastDetailModal && !els.forecastDetailModal.classList.contains("hidden")) {
      closeForecastExperimentDetail();
    }
  });
}

// ---------- Init ----------
(async function init() {
  bindThemeToggle();
  bindLanguageToggle();
  normalizeStaticLabels();
  bindTabs();
  bindDownloads();
  bindInputs();
  await loadConfig();
  bindCommandPanelToggle();
  bindTvChartControls();
  initChartTooltips();
  restoreForm();
  syncDashboardRangeControls();
  applyGlobalRangeToControls();
  renderGlobalQualitySummary();
  syncAiPortfolioUniverseMode();
  renderBacktestUniverseChips();
  renderSymbolTargetChips("portfolio");
  renderSymbolTargetChips("aiPortfolioCustomUniverse");
  populateBacktestStrategyRegistry();
  renderHistory();
  loadQuantamentalCompareWatchlists().catch(() => {});
  renderWatchlist({ force: true });
  loadActiveDashboardResources(false);
  if (els.watchlistAddBtn) {
    els.watchlistAddBtn.addEventListener("click", watchlistAddFromForm);
  }
  // Poll watchlist every 30s so scheduled runs and last_run_at timestamps stay fresh.
  state.watchlistTimer = setInterval(() => renderWatchlist(), 30000);
  checkHealth();
  loadRunbook();
  loadPreflight(false, { allowHidden: true });
  state.preflightTimer = setInterval(() => loadPreflight(false), 60000);
  document.addEventListener("visibilitychange", () => {
    if (!shouldRunBackgroundPoll()) return;
    renderWatchlist();
    loadPreflight(false);
  });
})();
