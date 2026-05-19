# Quantamental Implementation Plan

Repository: `ryun6249/fingpt-local-research-assistant`

Feature: `Quantamental` tab

Quantamental = Quant + Fundamental.

Status as of 2026-05-16 KST: implemented and verified in the local `F:\LLM\FinGPT` checkout.

Checklist rule: checked items below are implemented and verified in this repository. Original template paths under `backend/*` and `src/*` are not used by this app; the matching implementation lives under FastAPI `app/api`, schemas in `core`, deterministic engines in `pipelines`, and static UI files in `app/web`.

Enhancement status: the prior optional enhancement candidates have now been implemented where the local environment allows them: peer-relative scoring, broader peer-universe expansion, SEC provenance/excerpts plus opt-in filing-text excerpts, key-gated DART/KR provider support, live-verified KRX price fallback parsing, persisted snapshots with export/diff/retention, server-backed batch comparison watchlist/CSV UI/API, freshness audit with stale/missing/unknown retry, strict freshness gating for core signal data, an always-on Top 5 Quantamental signal screener with backwards-compatible `top`/`top_count`/`ranked_rows`/`screened_rows` response aliases, a score-threshold screener for selected `score_key` plus `min_score` candidate filtering, a fast cached Top 5 screening path, KR/EN UI output controls, and axis-annotated overview charts.

---

## 1. Repository Analysis

- [x] Frontend framework identified: static HTML/CSS/vanilla JavaScript served from `app/web` by FastAPI `StaticFiles`.
- [x] Routing structure identified: `/ui/` with hash dashboard tabs; Quantamental is addressable via `#quantamental`.
- [x] Navigation/tab system identified: `data-dashboard-tab`, `setDashboardTab`, `dashboardTabFromLocation`, and `loadActiveDashboardResources`.
- [x] Component/module structure identified: shared rendering in `app/web/app.js`, domain render modules under `app/web/modules`.
- [x] Styling system identified: `app/web/styles.css`.
- [x] API client pattern identified: `API` constant plus fetch helpers in `app/web/app.js`.
- [x] Backend framework identified: FastAPI in `app/api/server.py`.
- [x] Router registration pattern identified: routers included in `app/api/server.py`, with dual `/api/v1/<domain>` and `/api/<domain>` prefixes for newer domains.
- [x] Schema pattern identified: Pydantic models under `core/schemas`.
- [x] Service pattern identified: deterministic domain code under `pipelines/<domain>`.
- [x] LLM pattern identified: local Ollama-compatible provider is optional; deterministic fallback is the default verified path.
- [x] Test pattern identified: `pytest`; static UI contracts via Python tests/scripts; browser smoke via Playwright.
- [x] Runtime launcher identified: `scripts/run_web.ps1` exists; verification used direct `python -m uvicorn` on an isolated port.

---

## 2. Files Added / Modified

### Added

- [x] `app/api/routers/quantamental.py`
- [x] `app/web/modules/quantamental-ui.js`
- [x] `pipelines/quantamental/__init__.py`
- [x] `pipelines/quantamental/cache.py`
- [x] `pipelines/quantamental/providers.py`
- [x] `pipelines/quantamental/fundamental_engine.py`
- [x] `pipelines/quantamental/quant_engine.py`
- [x] `pipelines/quantamental/factor_engine.py`
- [x] `pipelines/quantamental/peer_engine.py`
- [x] `pipelines/quantamental/risk_engine.py`
- [x] `pipelines/quantamental/hybrid_score_engine.py`
- [x] `pipelines/quantamental/signal_engine.py`
- [x] `pipelines/quantamental/sec_evidence.py`
- [x] `pipelines/quantamental/snapshot_store.py`
- [x] `pipelines/quantamental/watchlist_store.py`
- [x] `pipelines/quantamental/ai_service.py`
- [x] `pipelines/quantamental/qa_service.py`
- [x] `pipelines/quantamental/service.py`
- [x] `tests/test_quantamental_engines.py`
- [x] `tests/test_quantamental_api.py`
- [x] `scripts/quantamental_ui_smoke.py`

### Modified

- [x] `app/api/server.py`
- [x] `app/api/routers/dashboard.py`
- [x] `app/web/app.js`
- [x] `app/web/index.html`
- [x] `app/web/styles.css`
- [x] `.env.example`
- [x] `core/config/settings.py`
- [x] `core/schemas/quantamental.py`
- [x] `pipelines/data_mart/storage/repository.py`
- [x] `scripts/check_ui_contract.py`
- [x] `tests/test_ui_modules.py`
- [x] `tests/test_ui_routing_contract.py`
- [x] `docs/QUANTAMENTAL_IMPLEMENTATION_PLAN.md`

---

## 3. Backend Implementation Checklist

### Schemas

- [x] Company overview schema
- [x] Fundamental statement schema
- [x] Fundamental metrics schema
- [x] Price history schema
- [x] Quant metrics schema
- [x] Factor scores schema
- [x] Risk metrics schema
- [x] Hybrid composite score schema
- [x] Signal schema
- [x] AI report request/response schema
- [x] Q&A request/response schema
- [x] Data quality schema
- [x] Error schema

### Providers

- [x] yfinance company/fundamental/price provider
- [x] OpenDART-backed KR company/fundamental provider boundary
- [x] Naver Finance KRX daily price fallback parser for KR price history
- [x] Provider factory via `provider_for_market`
- [x] US market support
- [x] KR market support through `DART_API_KEY`, with fail-closed missing-key behavior
- [x] GLOBAL market support through yfinance symbols with `ACWI` benchmark and no fabricated data
- [x] Source metadata and fetched timestamps
- [x] Missing field normalization
- [x] Provider error handling
- [x] TTL cache that does not cache failed/error payloads

### Fundamental Engine

- [x] Growth metrics
- [x] Profitability metrics
- [x] Stability metrics
- [x] Cash flow metrics
- [x] Valuation metrics
- [x] Earnings quality metrics
- [x] Accounting risk flags
- [x] Safe division
- [x] Missing data handling
- [x] Tests for division-by-zero and missing data

### Quant Engine

- [x] Price data normalization
- [x] Daily returns
- [x] Cumulative returns
- [x] Momentum metrics
- [x] Trend metrics
- [x] SMA/EMA
- [x] Volatility metrics
- [x] Drawdown metrics
- [x] Sharpe ratio
- [x] Sortino ratio
- [x] Calmar ratio
- [x] VaR/CVaR
- [x] Liquidity metrics
- [x] Insufficient price-history handling
- [x] Tests

### Factor / Risk / Hybrid / Signal

- [x] Value score
- [x] Quality score
- [x] Growth score
- [x] Momentum score
- [x] Low volatility score
- [x] Liquidity score
- [x] Peer-relative factor normalization
- [x] Peer-relative ranking by industry, sector, or request fallback
- [x] Score clamping
- [x] Missing data behavior
- [x] Price, volatility, drawdown, balance sheet, valuation, liquidity, and data-quality risk
- [x] SEC filing/facts evidence can contribute quality/risk context
- [x] Risk level and risk flags
- [x] Balanced style
- [x] Quality Growth style
- [x] Value style
- [x] Momentum style
- [x] Defensive style
- [x] Final hybrid score calculation
- [x] Conflict classification
- [x] Strong Buy Candidate
- [x] Buy Candidate
- [x] Accumulate Watch
- [x] Neutral / Hold-Watch
- [x] Avoid
- [x] Sell Risk / Reduce Risk
- [x] Insufficient Data
- [x] Signal score, confidence, rationale, warnings
- [x] Major risk and low data-quality override
- [x] Tests

### AI Report and Q&A

- [x] Structured deterministic context builder
- [x] System prompt and JSON-only LLM prompt
- [x] JSON schema enforcement
- [x] JSON parsing
- [x] Malformed JSON fallback
- [x] LLM failure fallback
- [x] Signal interpretation without score/signal override
- [x] Conflict analysis
- [x] Bull case
- [x] Bear case
- [x] Missing data warning
- [x] Context-based Q&A
- [x] Evidence metrics
- [x] Caveats
- [x] Not-investment-advice flag
- [x] Direct investment command guard
- [x] Tests

### APIs

- [x] `GET /api/quantamental/company/{ticker}`
- [x] `GET /api/quantamental/fundamentals/{ticker}`
- [x] `GET /api/quantamental/quant/{ticker}`
- [x] `GET /api/quantamental/factors/{ticker}`
- [x] `GET /api/quantamental/risk/{ticker}`
- [x] `GET /api/quantamental/composite/{ticker}`
- [x] `GET /api/quantamental/signal/{ticker}`
- [x] `GET /api/quantamental/analysis/{ticker}`
- [x] `POST /api/quantamental/analysis`
- [x] `POST /api/quantamental/ai/report`
- [x] `POST /api/quantamental/ai/qa`
- [x] `GET /api/quantamental/compare`
- [x] `POST /api/quantamental/compare`
- [x] `GET /api/quantamental/screen/top-signals`
- [x] `POST /api/quantamental/screen/top-signals`
- [x] `GET /api/quantamental/screen/by-score`
- [x] `POST /api/quantamental/screen/by-score`
- [x] `GET /api/quantamental/compare/watchlists`
- [x] `POST /api/quantamental/compare/watchlists`
- [x] `PUT /api/quantamental/compare/watchlists/{item_id}`
- [x] `DELETE /api/quantamental/compare/watchlists/{item_id}`
- [x] `GET /api/quantamental/sec/{ticker}`
- [x] `GET /api/quantamental/snapshots`
- [x] `GET /api/quantamental/snapshots/{snapshot_id}`
- [x] `GET /api/quantamental/snapshots/{snapshot_id}/export`
- [x] `GET /api/quantamental/snapshots/diff`
- [x] `POST /api/quantamental/snapshots/retention`
- [x] Matching `/api/v1/quantamental/*` endpoints
- [x] Router registration
- [x] Structured errors and partial/fail-open data behavior

---

## 4. Frontend Implementation Checklist

### Data Shape and API

- [x] Static Quantamental data-shape handling
- [x] Company shape handling
- [x] Fundamental shape handling
- [x] Quant shape handling
- [x] Factor shape handling
- [x] Risk shape handling
- [x] Composite shape handling
- [x] Signal shape handling
- [x] AI report shape handling
- [x] Q&A shape handling
- [x] Peer-comparison shape handling
- [x] SEC evidence shape handling
- [x] Snapshot metadata shape handling
- [x] Snapshot export/diff/retention shape handling
- [x] Peer-universe expansion shape handling
- [x] Data quality shape handling
- [x] Freshness audit shape handling
- [x] Top 5 screener shape handling
- [x] API client functions in `app/web/app.js`

### Page and Navigation

- [x] Quantamental tab
- [x] `#quantamental` route/hash
- [x] Quantamental page/surfaces
- [x] Existing navigation preserved
- [x] Active tab state
- [x] Loading state
- [x] Error state

### UI Components

- [x] Search/control bar
- [x] Ticker symbol picker uses the shared finder UI and applies a selected symbol to the Quantamental ticker input
- [x] Company header
- [x] Signal card
- [x] Composite score dashboard
- [x] Always-on Top 5 Signal Screener card
- [x] Score Threshold Screener card with score type, minimum score, and result limit controls
- [x] Top 5 response compatibility aliases for `top`, `top_signals`, `top_count`, `freshness`, `summary`, `ranked_rows`, and `screened_rows`
- [x] Factor grid
- [x] Overview tab with explicit chart axes, chart notes, coverage, and missing-value disclosure
- [x] Fundamentals tab
- [x] Quant tab
- [x] Risk tab
- [x] Valuation tab
- [x] AI report tab
- [x] Q&A tab
- [x] Q&A prompt/button/empty-state localization for KR/EN
- [x] Detail-panel KR/EN localization for overview metrics, chart labels, freshness/audit tables, Top 5, comparison, snapshot, and evidence surfaces
- [x] Peer comparison tab
- [x] SEC evidence tab
- [x] Audit/snapshot tab
- [x] Batch peer-comparison card and table
- [x] Broader peer-universe controls
- [x] Peer-comparison saved watchlists
- [x] Peer-comparison CSV export
- [x] Snapshot export/diff/retention controls
- [x] Freshness matrix in Data Quality with section status, as-of date, age, basis, and action
- [x] Data quality panel
- [x] Loading state
- [x] Error state

### Charts

- [x] Price + SMA chart
- [x] Cumulative return chart
- [x] Rolling volatility chart
- [x] Drawdown chart
- [x] Volume chart
- [x] Revenue / income chart
- [x] Margin chart
- [x] Cash flow chart
- [x] Balance sheet chart
- [x] ROE / ROA chart
- [x] Empty chart state
- [x] Missing value handling

### Signal UI and Safety

- [x] Signal label display
- [x] Signal score display
- [x] Signal confidence display
- [x] Time horizon in backend payload
- [x] Rationale list
- [x] Warning list
- [x] Visible not-investment-advice disclaimer
- [x] Insufficient data state

---

## 5. Error Handling Checklist

- [x] Empty ticker
- [x] Invalid ticker
- [x] Unsupported market
- [x] GET query validation errors return structured 400 responses instead of server errors
- [x] Provider failure
- [x] DART API key missing
- [x] Financial data missing
- [x] Price data missing
- [x] Partial data
- [x] Insufficient lookback / price history
- [x] AI failure fallback
- [x] Malformed AI JSON fallback
- [x] Chart unavailable
- [x] Signal unavailable / insufficient data
- [x] Existing app remains functional

---

## 6. Security and Investment Safety Checklist

- [x] Validate ticker input
- [x] No shell execution from user input
- [x] No frontend API keys
- [x] No secrets in logs
- [x] No system prompt leakage in UI outputs
- [x] No direct investment advice
- [x] No guaranteed returns
- [x] No unsupported price targets
- [x] Buy/Sell labels are candidate/risk classifications only
- [x] Disclaimer visible in UI
- [x] AI cannot override deterministic signal

---

## 7. Enhancement Completion Checklist

- [x] Peer-relative factor normalization by sector/industry with deterministic fallback to the submitted comparison set.
- [x] Peer-relative strength score and rank are surfaced in backend payloads and the Factor Grid/Peer tab.
- [x] Broader peer-universe expansion can add sector/industry candidates from local `asset_metadata` when requested.
- [x] SEC filing-derived quality/risk evidence is attached to US analyses when local data-mart SEC facts exist.
- [x] SEC evidence can add risk flags without letting AI mutate deterministic scores/signals.
- [x] SEC evidence includes concept-level provenance and filing metadata excerpts for audit display and AI interpretation context.
- [x] SEC evidence can opt into live filing-text excerpts and risk-factor section extraction through `include_filing_text=true`.
- [x] DART-backed KR provider is wired through `DART_API_KEY` and `DART_REQUEST_TIMEOUT_S`.
- [x] KR missing-key state is fail-closed and visible as `dart_api_key_missing`; no fabricated KR fundamentals are returned.
- [x] KR price history can fall back to parsed Naver Finance KRX daily data when `yfinance` has no usable rows.
- [x] Persisted Quantamental snapshots are saved for successful and structured-failed analyses.
- [x] Snapshot list/detail APIs support audit/replay.
- [x] Snapshot CSV/JSON export, snapshot diff, and retention-preview/delete plumbing are implemented.
- [x] Snapshot destructive retention path is verified against a temporary Quantamental store.
- [x] Batch comparison API supports multi-ticker peer comparison and returns rows, analyses, and peer-group metadata.
- [x] Batch comparison UI supports ticker input, comparison execution, and peer-relative table rendering.
- [x] Batch comparison UI supports server-backed saved watchlists with localStorage fallback and CSV export.
- [x] `GLOBAL` market path routes to the yfinance provider with `ACWI` benchmark and visible provider/data-quality warnings when upstream data is incomplete.
- [x] GLOBAL SEC evidence can resolve mapped ADR/dual-listed aliases such as `ASML.AS -> ASML` and includes `20-F`/`6-K` filings when local SEC data exists.
- [x] GLOBAL peer expansion has a static liquid-peer fallback when local `asset_metadata` has no candidates; added peers are still analyzed by the normal deterministic/provider path.
- [x] Shared symbol picker includes representative GLOBAL equity symbols and a `global_equity` filter.
- [x] GLOBAL symbol resolver maps curated local/common aliases such as `7203 -> 7203.T` and exposes explicit ambiguity/resolution warnings in deterministic payloads.
- [x] GLOBAL SEC hydration has an operator script and API dry-run planner for mapped ADR/dual-listed aliases.
- [x] Shared symbol picker includes the expanded representative GLOBAL equity set used by the resolver.
- [x] Analysis responses include a section-level freshness audit for company, fundamentals, prices, and SEC evidence.
- [x] Stale refreshable sections trigger one forced-refresh retry before the response is returned.
- [x] Missing, failed, or unknown refreshable sections also trigger one forced-refresh retry before the response is returned.
- [x] Strict freshness gate blocks deterministic signals when company, fundamentals, or prices remain stale/missing/failed/unknown after retry.
- [x] `force_refresh` is available on analysis and compare request paths for explicit operator refreshes.
- [x] Top 5 screener ranks only fresh, usable core-data candidates from the configured/default universe by deterministic composite score, data quality, freshness score, and ticker as tie-breakers.
- [x] Top 5 screener excludes insufficient-data rows from the ranked recommendations while preserving failures/warnings in the payload.
- [x] Top 5 default auto-load uses a bounded six-candidate core-data screen and caches successful responses briefly; explicit custom ticker lists still support larger operator-driven screens.
- [x] Top 5 fast path intentionally skips optional SEC overlay and reports `screening_fast_path_sec_overlay_skipped`; full single-name/compare analysis still includes SEC evidence by default.
- [x] Score-threshold screener uses the same freshness-gated deterministic ranking as Top 5, then filters candidates by selected `score_key` plus `min_score` and returns `matches`, `matched_count`, `returned_count`, selected-score fields, and audit-compatible `ranked_rows`/`screened_rows`.
- [x] Quantamental overview charts now show date x-axis, y-axis units/ticks, legends, and explanatory notes for price, returns, volatility, drawdown, volume, fundamentals, margins, cash flow, balance sheet, and ROE/ROA.

---

## 8. Verification

Last verified: 2026-05-17 00:11 KST in the local `F:\LLM\FinGPT` checkout.

### Command Discovery

- [x] `requirements.txt` exists.
- [x] `requirements-dev.txt` exists.
- [x] `pytest.ini` exists.
- [x] `README.md` exists.
- [x] `scripts/run_web.ps1` exists.
- [x] `package.json` is absent, so npm lint/build/test commands were not run.
- [x] `pyproject.toml` is absent, so no pyproject lint/typecheck command exists.
- [x] `Makefile` is absent.
- [x] `.github/workflows` is absent in this checkout; only issue/funding metadata exists under `.github`.

### Commands Run

| Command | Result | Notes |
|---|---:|---|
| `python -m py_compile core/schemas/quantamental.py pipelines/quantamental/service.py app/api/routers/quantamental.py scripts/check_ui_contract.py scripts/quantamental_ui_smoke.py` | PASS | Syntax guard after freshness audit, forced refresh flags, Top 5 screener API, and smoke coverage updates |
| `python -m py_compile pipelines/quantamental/service.py app/api/routers/quantamental.py tests/test_quantamental_api.py` | PASS | Syntax guard after strict freshness gate and section endpoint `force_refresh` query wiring |
| `node --check app/web/app.js` | PASS | Static app JS syntax after screener wiring, freshness controls, and early event binding fix |
| `node --check app/web/modules/quantamental-ui.js` | PASS | Quantamental UI module syntax after detailed overview, screener renderer, and strict-gate UI additions |
| `Get-ChildItem app\web\modules\*.js \| ForEach-Object { node --check $_.FullName }` | PASS | Static UI module syntax across bundled modules |
| `python scripts/check_ui_contract.py` | PASS | UI/API contract markers for `quantamentalTopSignals`, `loadQuantamentalScreen`, and `quantamental-ui.js?v=20260516-quantamental-v8` |
| `python scripts/check_ui_contract.py` | PASS | UI/API contract markers after cache bump to `quantamental-ui.js?v=20260516-quantamental-v9` and `app.js?v=20260516-quantamental-i18n-v4` |
| `python -m py_compile core/schemas/quantamental.py pipelines/quantamental/service.py app/api/routers/quantamental.py scripts/check_ui_contract.py scripts/quantamental_ui_smoke.py tests/test_quantamental_api.py` | PASS | Syntax guard after score-threshold screener schema/API/service/UI-smoke wiring |
| `node --check app/web/app.js` | PASS | Static app JS syntax after score-threshold screener controls, API client, and event binding |
| `node --check app/web/modules/quantamental-ui.js` | PASS | Quantamental UI module syntax after score-threshold table renderer |
| `python -m pytest tests/test_quantamental_api.py tests/test_ui_modules.py tests/test_ui_routing_contract.py -q` | PASS | `58 passed, 4 subtests passed`; includes `/screen/by-score`, score threshold UI renderer, static markers, and cache-busted bundle contracts |
| `python scripts/check_ui_contract.py` | PASS | UI/API contract markers for `quantamentalScoreScreen`, `runQuantamentalScoreScreen`, score threshold controls, and `quantamental-ui.js?v=20260516-quantamental-v10` |
| `python -m pytest tests/test_quantamental_engines.py tests/test_quantamental_api.py -q` | PASS | `38 passed`; confirms existing Quantamental deterministic engines plus new score-threshold API contract |
| Live HTTP smoke on `http://127.0.0.1:8000/api/v1/quantamental/screen/by-score?tickers=AAPL%20MSFT%20NVDA&min_score=0&limit=3&include_ai=false&output_language=ko` | PASS | HTTP 200; returned 3 matches sorted by deterministic score with `screening_policy=rank_fresh_complete_core_data_then_filter_min_score_sec_overlay_skipped_for_speed` |
| Browser Use in-app browser to `http://127.0.0.1:8000/ui/?v=20260516-quantamental-i18n-v5#quantamental` | PASS | Rendered Score Threshold Screener, ran minimum score `0` and limit `10`, displayed 10 rows, saved screenshot to `reports/browser_ui/quantamental-score-threshold-8000.png`, and saw zero console warnings/errors |
| `python -m py_compile core/schemas/quantamental.py pipelines/quantamental/service.py app/api/routers/quantamental.py scripts/check_ui_contract.py scripts/quantamental_ui_smoke.py scripts/ai_portfolio_ui_smoke.py tests/test_quantamental_api.py tests/test_ui_modules.py tests/test_ui_routing_contract.py` | PASS | Syntax guard after selected score-key screener request/schema/UI smoke updates |
| `node --check app/web/app.js`; `node --check app/web/modules/quantamental-ui.js` | PASS | Static JS syntax after score-key selector, selected-score table, and `score_key` API wiring |
| `python -m pytest tests/test_quantamental_api.py tests/test_ui_modules.py tests/test_ui_routing_contract.py -q` | PASS | `59 passed, 4 subtests passed`; covers selected `score_key=quality`, default-universe limit sizing, selected-score UI renderer, cache-busted `quantamental-ui.js?v=20260516-quantamental-v11`, and `app.js?v=20260516-quantamental-i18n-v6` |
| `python scripts/check_ui_contract.py` | PASS | UI/API/static contract markers passed for `quantamentalScoreMetric`, `score_key`, selected-score controls, and `/ui/quantamental` fallback |
| Live HTTP smoke on `http://127.0.0.1:8000/api/v1/quantamental/screen/by-score?score_key=momentum&min_score=0&limit=10&include_ai=false&output_language=ko` | PASS | HTTP 200; returned `score_key=momentum`, `matched_count=10`, `returned_count=10`, and 10 `matches` from the default universe |
| Browser Use in-app browser to `http://127.0.0.1:8000/ui/?v=20260516-quantamental-i18n-v6#quantamental` | PASS | Verified score-type options `복합/가치/품질/성장/모멘텀/저변동성/유동성`; ran `모멘텀`, minimum `0`, limit `10`; rendered 10 rows; saved `reports/browser_ui/quantamental-score-threshold-momentum-8000.png` |
| `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_engines.py tests/test_ui_routing_contract.py tests/test_ui_modules.py -q` | PASS | `70 passed, 4 subtests passed`; includes freshness audit, refresh retry, Top 5 screen ranking, UI module axes, and routing contract |
| `python -m pytest tests/test_output_language_request.py tests/test_quantamental_api.py tests/test_quantamental_engines.py tests/test_ui_modules.py tests/test_ui_routing_contract.py -q` | PASS | `76 passed, 4 subtests passed`; includes output-language normalization, Top 5 response aliases, and versioned static bundle contracts |
| `python -m pytest tests/test_quantamental_api.py tests/test_ui_modules.py tests/test_ui_routing_contract.py -q` | PASS | `51 passed, 4 subtests passed`; strict freshness gate blocks stale prices as `Insufficient Data` and keeps Top 5 rows signal-usable only |
| Direct service smoke via PowerShell here-string Python | PASS | AAPL freshness `fresh`, score `100`, company/fundamentals/prices/SEC all fresh; custom AAPL/MSFT/NVDA/TSLA/AMD/CRM screen returned top 5 ranked by deterministic composite score |
| `python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8259` | PASS | Fresh local server reached by `/api/v1/quantamental/health`; health reported `freshness_audit_and_stale_refresh_retry`, `top_signal_screener`, and `axis_annotated_overview_charts` |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8259 --output reports/quantamental_ui_smoke_latest.json` | PASS | Browser smoke now verifies Top 5 screener row count, freshness text, overview x/y axes and missing-value explanation, shared ticker picker, GLOBAL resolver, styles, invalid ticker, Q&A, watchlists, CSV, and snapshot retention preview |
| Browser Use in-app browser to `http://127.0.0.1:8259/ui/#quantamental` | PASS | Rendered Quantamental, verified Top 5 table, shared picker modal, AAPL analysis, overview axis/missing-value text, screenshot evidence, and zero console warnings/errors |
| Browser Use in-app browser to `http://127.0.0.1:8290/ui/#quantamental` | PASS | Verified EN/KR language toggle, Top 5 refresh label stays localized after busy state, AAPL analysis, all Quantamental detail tabs, KR Q&A, Market/Macro/Quant Lab/ML Forecast/AI Portfolio tab loading, and zero console warnings/errors |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8290 --output reports/quantamental_ui_smoke_automation3_latest.json` | PASS | Browser smoke verified Top 5 5 rows, AAPL/MSFT/NVDA/TSLA/invalid paths, GLOBAL resolver, Q&A, comparison/watchlist/CSV, and snapshot audit |
| `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8290 --timeout-s 180 --output reports/ai_portfolio_ui_smoke_automation3_latest.json` | PASS | Cross-dashboard smoke verified versioned scripts, all dashboard tab surfaces, Quantamental KR/EN toggle and Top 5, and no console errors |
| `python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8262` | PASS | Fresh local server reached by `/api/v1/quantamental/health`; health reported `strict_freshness_gate` |
| HTTP API smoke against `http://127.0.0.1:8262` | PASS | AAPL returned freshness `fresh`, integrity `ok`, `usable_for_signal=true`, all core sections fresh; custom AAPL/MSFT/NVDA/TSLA/AMD/CRM screen returned top 5 with `usable_for_signal=true` and no warnings |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8262 --output reports/quantamental_ui_smoke_latest.json` | PASS | Browser smoke verified strict-gate UI fields, Top 5 `Integrity` column, fresh usable candidates, ticker picker, GLOBAL resolver, styles, invalid ticker, Q&A, watchlists, CSV, and snapshot retention preview |
| Browser Use in-app browser to `http://127.0.0.1:8262/ui/#quantamental` | PASS | Verified strict-gate rendering (`Signal Usable yes`, `blocking none`), Top 5 integrity column, AAPL analysis, screenshot evidence, and zero console warnings/errors |
| `python -m py_compile pipelines/quantamental/watchlist_store.py pipelines/quantamental/sec_evidence.py pipelines/quantamental/service.py app/api/routers/quantamental.py scripts/quantamental_ui_smoke.py` | PASS | Remaining-limit changes: server compare watchlists, SEC filing-text excerpts, service/router/smoke syntax guard |
| `python -m py_compile app/api/routers/quantamental.py` | PASS | Re-run after GET validation-error hardening |
| `python -m py_compile app/api/server.py scripts/check_ui_contract.py` | PASS | Static UI fallback fix syntax guard |
| `node --check app/web/app.js` | PASS | Static app JS syntax |
| `node --check app/web/modules/quantamental-ui.js` | PASS | Quantamental UI module syntax |
| `python scripts/check_ui_contract.py` | PASS | UI/API contract markers; no missing markers; `/ui/quantamental` returns 200 and missing `.js` assets still return 404 |
| `python -m pytest tests/test_ui_modules.py -q` | PASS | `1 passed`; Quantamental UI module contract still loads |
| `python -m pytest tests/test_ui_routing_contract.py -q` | PASS | `33 passed, 4 subtests passed`; includes shared Quantamental ticker picker contract, app cache version, and direct UI client-route fallback |
| `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_engines.py -q` | PASS | `25 passed in 8.26s`; includes server compare watchlists, destructive snapshot retention in temp store, SEC filing-text excerpts, KRX fallback provider path, division-by-zero, missing data, insufficient price history, AI fallback, malformed JSON, direct-order guard, peer expansion, snapshots, SEC provenance/excerpts, and DART missing-key coverage |
| `python -m pytest tests/test_quantamental_api.py -q` | PASS | `11 passed in 4.42s`; re-run after GET validation-error hardening |
| `python -m pytest tests/test_ui_modules.py tests/test_ui_routing_contract.py tests/test_quantamental_api.py tests/test_quantamental_engines.py -q` | PASS | `58 passed, 4 subtests passed in 5.03s`; includes UI renderers, routing contract, Quantamental engines, API contract, and server watchlist markers |
| `python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8233` | PASS | Fresh local server reached by `/api/v1/quantamental/health`; health reported `server_side_compare_watchlists`, `sec_filing_text_excerpt`, and `krx_price_fallback` |
| Python urllib API smoke against `http://127.0.0.1:8221` | PASS | Report: `reports/quantamental_remaining_api_latest.json`; checked peer expansion, snapshot diff/export/retention preview, SEC provenance/excerpts, KR company missing-key, and KR quant path |
| Python urllib limits API smoke against `http://127.0.0.1:8233` | PASS | Report: `reports/quantamental_limits_api_latest.json`; checked server compare watchlist create/list/delete, SEC filing-text opt-in, live Naver KRX rows for 005930, and DART credential status |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8233 --output reports/quantamental_ui_smoke_latest.json` | PASS | Historical pre-GLOBAL-enable browser UI smoke; passed tickers, all strategy styles, empty ticker, legacy negative market case, tabs, Q&A, disclaimers, server-backed watchlist save/load, comparison CSV download, and snapshot retention preview |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8001 --output reports/quantamental_ui_smoke_latest.json` | PASS | Browser UI smoke re-run after ticker finder change; verified shared picker opens, selects `MSFT`, applies the ticker, then validates tickers, styles, invalid ticker, Q&A, comparison CSV, and snapshot retention preview |
| `python -m py_compile pipelines/quantamental/providers.py pipelines/quantamental/service.py scripts/quantamental_ui_smoke.py tests/test_quantamental_api.py tests/test_quantamental_engines.py` | PASS | Syntax guard after enabling `GLOBAL` through yfinance and updating the smoke/test contracts |
| `python scripts/check_ui_contract.py` | PASS | Re-run after Quantamental static cache version bump to `v5`; no missing markers |
| `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_engines.py tests/test_ui_routing_contract.py tests/test_ui_modules.py -q` | PASS | `61 passed, 4 subtests passed`; includes GLOBAL health/provider routing, UI cache contract, Quantamental API/engine tests, and UI module/routing tests |
| `python -m pytest tests/test_quantamental_api.py::test_quantamental_health_lists_global_as_supported_and_quant_uses_global_benchmark tests/test_quantamental_engines.py::test_global_market_routes_to_yfinance_provider -q` | PASS | `2 passed`; direct coverage that `GLOBAL` is supported, routes to yfinance, and uses `ACWI` benchmark |
| PowerShell here-string direct service check via `@'...'@ \| python -` | PASS | `supported_markets=['US','KR','GLOBAL']`, `unsupported_markets=[]`, `ASML.AS` `GLOBAL` quant `status=ok`, `provider_status=ok`, `benchmark_ticker=ACWI` |
| Bash-style heredoc check `python - <<'PY' ...` in PowerShell | FAIL | PowerShell rejected Bash heredoc syntax; rerun successfully with the here-string command above |
| HTTP API smoke `GET /api/v1/quantamental/analysis/ASML.AS?market=GLOBAL&period=annual&years=3&lookback=63&style=balanced&include_ai=false` on `http://127.0.0.1:8001` | PASS | HTTP 200; company `ASML Holding N.V.`, market `GLOBAL`, status `ok`, signal `Buy Candidate`, data quality `good`, benchmark `ACWI` |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8001 --output reports/quantamental_ui_smoke_global_latest.json` | PASS | Browser UI smoke now includes `ASML.AS` with `market=GLOBAL`; status `Buy Candidate`, data quality `good`, no `unsupported_market`, plus existing tickers/styles/Q&A/watchlist/CSV/snapshot checks |
| `python -m compileall app core pipelines scripts tests -q` | PASS | Re-run after GLOBAL provider/service/UI contract changes |
| `python -m py_compile pipelines/quantamental/sec_evidence.py pipelines/quantamental/peer_engine.py tests/test_quantamental_engines.py` | PASS | Syntax guard after GLOBAL SEC ADR alias fallback and global peer fallback changes |
| `node --check app/web/app.js` | PASS | Re-run after adding representative GLOBAL symbols and the shared `global_equity` picker scope |
| `python -m pytest tests/test_quantamental_engines.py::test_global_peer_universe_uses_static_fallback_when_metadata_is_empty tests/test_quantamental_engines.py::test_global_sec_evidence_uses_adr_alias_for_dual_listed_symbols tests/test_quantamental_engines.py::test_global_sec_evidence_skips_when_no_sec_alias -q` | PASS | `3 passed`; covers global peer fallback, SEC ADR alias evidence, and skipped evidence for unmapped global tickers |
| `python scripts/check_ui_contract.py` | PASS | Re-run after Quantamental static cache version bump to `v6`; no missing markers |
| `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_engines.py tests/test_ui_routing_contract.py tests/test_ui_modules.py -q` | PASS | `64 passed, 4 subtests passed`; includes GLOBAL symbol picker contract, SEC alias fallback, peer fallback, API, engine, and UI contracts |
| `python -m compileall app core pipelines scripts tests -q` | PASS | Re-run after SEC/peer/UI updates |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8001 --output reports/quantamental_ui_smoke_global_latest.json` | PASS | Browser UI smoke after remediation: `ASML.AS` with `market=GLOBAL`, `SEC evidence: ok`, 6 SEC filings, 120 SEC facts, no `unsupported_market` |
| Python here-string `update_sec_company_data(['ASML'], forms=['20-F','6-K','10-K','10-Q','8-K'], lookback_days=1825, filing_limit_per_ticker=20, hydrate_financials=True)` | PASS | Hydrated local SEC data for ADR alias `ASML`; `rows_inserted=262`, `filing_count=20`, `fact_count=240`, run `31a139814cad4c8d965447d3296a265a` |
| HTTP API smoke `GET /api/v1/quantamental/sec/ASML.AS?market=GLOBAL` on `http://127.0.0.1:8001` | PASS | HTTP 200; `status=ok`, `sec_ticker=ASML`, filings `6`, facts `120`, forms `20-F,6-K`, warning `sec_evidence_global_adr_fallback:ASML` |
| HTTP API smoke `GET /api/v1/quantamental/analysis/ASML.AS?market=GLOBAL&period=annual&years=3&lookback=63&style=balanced&include_ai=false` on `http://127.0.0.1:8001` | PASS | HTTP 200; company `ASML Holding N.V.`, signal `Accumulate Watch`, data quality `good`, SEC evidence `ok`, benchmark `ACWI` |
| HTTP API smoke `POST /api/v1/quantamental/compare` with `ASML.AS,TSM`, `market=GLOBAL`, `expand_peer_universe=true` | PASS | HTTP 200; 4 comparison rows, peer status `ok`, added `AAPL,NVDA`, no warning; static fallback remains covered by unit test when metadata is empty |
| Browser Use in-app browser to `http://127.0.0.1:8001/ui/#quantamental` with `ASML.AS`, `market=GLOBAL` | PASS | Shared picker found `ASML.AS`, `global_equity` scope exists, Signal/Composite/Fundamental/Quant/Risk rendered, `SEC evidence: ok · filings 6 · facts 120`, visible disclaimer, zero console errors |
| `python -m py_compile pipelines/quantamental/global_market.py pipelines/quantamental/sec_evidence.py pipelines/quantamental/sec_hydration.py pipelines/quantamental/providers.py pipelines/quantamental/service.py app/api/routers/quantamental.py scripts/quantamental_global_sec_hydrate.py tests/test_quantamental_engines.py tests/test_quantamental_api.py` | PASS | Syntax guard after shared GLOBAL resolver, SEC hydration planner, provider metadata, and API route additions |
| `node --check app/web/app.js` | PASS | Re-run after expanded GLOBAL symbol picker entries |
| `python scripts/quantamental_global_sec_hydrate.py --tickers ASML.AS,7203,9999.T --dry-run --output reports/quantamental_global_sec_hydrate_dry_run.json` | PASS | Dry-run mapped `ASML.AS -> ASML`, `7203 -> TM`, and skipped unmapped `9999.T` without writes |
| `python -m pytest tests/test_quantamental_engines.py::test_global_symbol_resolver_maps_common_local_aliases tests/test_quantamental_engines.py::test_yfinance_global_provider_uses_resolved_symbol tests/test_quantamental_engines.py::test_global_sec_hydration_plan_maps_known_aliases_and_skips_unknown tests/test_quantamental_api.py::test_quantamental_resolve_endpoint_and_global_sec_hydration_dry_run -q` | PASS | `4 passed`; covers resolver, yfinance provider use of resolved symbol, SEC hydration plan, and API dry-run |
| `python scripts/check_ui_contract.py` | PASS | Re-run after Quantamental static cache version bump to `v7`; no missing markers |
| `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_engines.py tests/test_ui_routing_contract.py tests/test_ui_modules.py -q` | PASS | `68 passed, 4 subtests passed`; includes resolver API, hydration dry-run API, expanded global picker, Quantamental engines, and UI contracts |
| HTTP API smoke `GET /api/v1/quantamental/resolve/7203?market=GLOBAL` on `http://127.0.0.1:8001` | PASS | HTTP 200; provider ticker `7203.T`, SEC alias `TM`, warning `global_symbol_resolved_to_yfinance:7203.T` |
| HTTP API smoke `POST /api/v1/quantamental/sec/global/hydrate?dry_run=true` on `http://127.0.0.1:8001` | PASS | HTTP 200; dry-run plan returned SEC tickers `ASML,TM` and did not write data |
| HTTP API smoke `GET /api/v1/quantamental/analysis/7203?market=GLOBAL&period=annual&years=3&lookback=63&style=balanced&include_ai=false` on `http://127.0.0.1:8001` | PASS | HTTP 200; resolved to Toyota via `7203.T`, data quality `good`, visible resolver warning, no `unsupported_market` |
| Playwright browser to `http://127.0.0.1:8001/ui/#quantamental` with `7203`, `market=GLOBAL` | PASS | UI rendered Toyota, Signal Card, Composite Score, Factor Grid, data quality, `global_symbol_resolved_to_yfinance:7203.T`, disclaimer, no `unsupported_market`, zero console errors |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8001 --output reports/quantamental_ui_smoke_global_resolver_latest.json` | PASS | Browser smoke now includes ASML GLOBAL SEC evidence and `7203 -> 7203.T` resolver warning path; report passed |
| `python -m compileall app core pipelines scripts tests -q` | PASS | Project-wide Python compilation after resolver/hydration changes |
| `node --check app/web/modules/quantamental-ui.js` | PASS | Quantamental UI module syntax after smoke-script/UI contract changes |
| `python scripts/check_provider_versions.py --output reports/provider_versions_latest.json` | PASS | Provider compatibility policy passed with `critical_passed=true`, `warning_count=0` |
| `python -m py_compile pipelines/data_mart/storage/db.py pipelines/data_mart/storage/repository.py pipelines/forecast/experiment_store.py pipelines/forecast/jobs.py pipelines/macro/providers/storage.py pipelines/output/run_history.py pipelines/backtest/artifact_exports.py tests/test_quant_lab_api.py` | PASS | Syntax guard after SQL hardening and Quant Lab export-retention path validation |
| `python -m py_compile core/utils/qdrant_helpers.py tests/test_qdrant_helpers.py tests/test_hybrid_search.py` | PASS | Syntax guard after Qdrant compatibility warning handling |
| `python -m py_compile pipelines/quantamental/providers.py scripts/quantamental_dart_live_smoke.py tests/test_quantamental_engines.py` | PASS | Syntax guard after DART financial-statement mapping hardening and credentialed live-smoke script addition |
| `DART_API_KEY=<provided> python scripts/quantamental_dart_live_smoke.py --ticker 005930 --period annual --years 5 --lookback 252 --output reports/quantamental_dart_live_latest.json` | PASS | Credentialed OpenDART live smoke; provider company `삼성전자`, 5 annual rows, service fundamentals `ok`, data quality `good`, deterministic signal preserved |
| `DART_API_KEY=<provided> python scripts/quantamental_dart_live_smoke.py --ticker 005930 --period annual --years 5 --lookback 252 --base-url http://127.0.0.1:8001 --output reports/quantamental_dart_live_http_latest.json` | PASS | Credentialed HTTP/API smoke through the running server; company, fundamentals, and analysis all returned HTTP 200 and no `dart_api_key_missing` warning |
| `python -m compileall app core pipelines scripts tests -q` | PASS | Project-wide Python compilation |
| `node --check app/web/app.js` plus `node --check app/web/modules/*.js` | PASS | Static UI JavaScript syntax across bundled app modules |
| `python -m pytest tests/test_data_mart_repository.py tests/test_data_mart_api.py tests/test_daily_update.py tests/test_data_quality_checks.py tests/test_macro_platform.py tests/test_forecast_lab.py tests/test_output_collection_sidecar.py tests/test_quant_lab_api.py -q` | PASS | `102 passed in 37.61s`; data mart, macro, forecast, output history, Quant Lab, and export cleanup compatibility after SQL/export changes |
| `python -m pytest tests/test_qdrant_helpers.py tests/test_hybrid_search.py tests/test_preflight.py -q` | PASS | `28 passed, 2 subtests passed`; Qdrant local warning suppression and high-level add/query compatibility wrappers |
| `python -m bandit -r app core pipelines scripts -x legacy,venv311,data,reports -ll -f json -o reports/bandit_medium_high_latest.json` | PASS | Codex Security medium/high gate; `high=0`, `medium=0`, report saved to `reports/bandit_medium_high_latest.json` |
| `python scripts/check_provider_versions.py --output reports/provider_versions_latest.json` | PASS | Re-run after GLOBAL changes; provider compatibility policy passed with `critical_passed=true`, `warning_count=0` |
| `python scripts/check_openbb_compat.py --output reports/openbb_compat_latest.json` | PASS | OpenBB compatibility; package/import/pip/yfinance/SEC checks passed, OpenBB news runtime intentionally disabled |
| `python scripts/validation_gate.py --include-fingpt-eval` | PASS | Integrated validation gate with FinGPT eval; `automated_passed=true`, artifacts written under `data/outputs` and `reports` |
| `powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1` | PASS | Production baseline path through `venv311`, Docker/Qdrant bootstrap, preflight, and integrated validation gate; warning-free final run |
| MCP_DOCKER browser navigate/evaluate to `http://host.docker.internal:8233/ui/#quantamental` | PASS | In-app browser rendered Quantamental, verified server-backed watchlist save/delete, executed AAPL analysis, and verified visible disclaimer |
| Browser Use in-app browser to `http://127.0.0.1:8001/ui/#quantamental` | PASS | Verified Quantamental tab, shared `찾기` button, picker title/description/apply label, `MSFT` selection, analysis result, Fundamental/Quant/Risk/AI/Q&A tabs, Q&A answer, and zero browser console errors |
| Browser Use in-app browser to `http://127.0.0.1:8001/ui/quantamental` | PASS | Reproduced the previously failing direct client route, verified it now serves the UI instead of `Not Found`, then rechecked `/ui/#quantamental` with AAPL analysis and zero browser console errors |
| Browser Use in-app browser to `http://127.0.0.1:8001/ui/#quantamental` | PASS | Final live verification after project-wide fixes; AAPL rendered signal/score/factors/data quality, shared picker opened, invalid ticker rendered `Insufficient Data`, no `Not Found`, and zero browser console errors |
| Browser Use in-app browser to `http://127.0.0.1:8001/ui/#quantamental` with `005930`, `market=KR` | PASS | Credentialed DART UI verification; rendered `삼성전자`, `Buy Candidate`, data quality `good`, no `dart_api_key_missing`, no `Not Found`, and zero browser console errors |
| `python -m pytest tests -q` | PASS | Current full regression after i18n/Top 5 compatibility hardening: `681 passed, 9 subtests passed in 177.87s` |
| `node --check app/web/app.js; node --check app/web/modules/quantamental-ui.js` | PASS | Static UI JavaScript syntax after Top 5 fast-path and smoke-script hardening |
| `python scripts/check_ui_contract.py` | PASS | UI/API/static contract markers passed after KR/EN and Quantamental Top 5 changes |
| `python -m compileall app core pipelines scripts tests` | PASS | Project-wide Python compilation after schema/router/service/smoke changes |
| `python -m pytest tests -q` | PASS | Full regression after Top 5 fast screening cache: `681 passed, 9 subtests passed in 172.87s` |
| HTTP API smoke `GET /api/v1/quantamental/screen/top-signals?limit=5&include_ai=false&output_language=ko` on `http://127.0.0.1:8307` | PASS | Cold default Top 5 returned `requested=6`, `top=5`, `freshness=fresh`, policy `rank_only_fresh_complete_core_data_after_retry_sec_overlay_skipped_for_speed` in `13.9s`; cached repeat returned `cache_hit=true` in `100ms` |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8307 --tickers AAPL,MSFT,NVDA,TSLA,INVALID_TEST_TICKER_123 --output reports/automation_3_quantamental_ui_smoke.json` | PASS | Browser smoke verified KR/EN, Top 5 5 rows, AAPL/MSFT/NVDA/TSLA/invalid paths, ASML GLOBAL, Toyota resolver, Q&A, comparison/watchlist/CSV, and snapshot audit |
| `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8307 --timeout-s 240 --output reports/automation_3_cross_dashboard_smoke.json` | PASS | Cross-dashboard browser smoke verified versioned scripts, all dashboard tabs, Quantamental language toggle and Top 5, and no console errors |
| Browser Use in-app browser to `http://127.0.0.1:8307/ui/?manual=automation-3#quantamental` | PASS | Direct manual click verification showed EN/KR toggle states, Top 5 status text, 5 visible rows, and usable integrity labels |
| `node --check app/web/modules/quantamental-ui.js`; `node --check app/web/app.js` | PASS | Static JS syntax after Quantamental detail-panel KR/EN localization |
| `python -m pytest tests/test_ui_modules.py tests/test_ui_routing_contract.py tests/test_quantamental_api.py -q` | PASS | `57 passed, 4 subtests passed`; covers Korean Quantamental copy, no mojibake markers, Top 5 aliases, and UI routing contracts |
| `python scripts/check_ui_contract.py` | PASS | UI/API/static contract markers still pass after detail-panel localization |
| `python -m compileall -q app core pipelines scripts tests` | PASS | Project-wide Python compilation after this automation pass |
| HTTP API smoke on `http://127.0.0.1:8317/api/v1/quantamental/screen/top-signals` | PASS | Forced fresh Top 5 returned `requested=6`, `top_count=5`, `freshness=fresh`, tickers `NVDA,AMD,AAPL,MSFT,CRM` in `11638ms`; cached repeat returned `cache_hit=true` in `30ms` |
| Browser Use in-app browser to `http://127.0.0.1:8317/ui/?automation=3-refresh#quantamental` | PASS | Clicked EN/KR toggle, Top 5 refresh, AAPL analysis, all Quantamental detail tabs, Q&A, Market/Macro/Quant Lab/ML Forecast/AI Portfolio tabs; Korean overview showed `최근 가격`, `커버리지`, `Y: 가격`; console warn/error count `0` |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8317 --tickers AAPL,MSFT,NVDA,TSLA,INVALID_TEST_TICKER_123 --output reports/automation_3_quantamental_ui_smoke_8317.json` | PASS | Browser smoke verified required ticker set, invalid ticker fail-closed path, GLOBAL ASML/Toyota resolver paths, Top 5 5 rows, comparison/watchlist/CSV, Q&A, snapshot audit |
| `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8317 --timeout-s 240 --output reports/automation_3_cross_dashboard_smoke_8317.json` | PASS | Cross-dashboard browser smoke verified versioned scripts, domain module globals, all dashboard tab surfaces, Quantamental language toggle and Top 5; no console errors |
| `python -m pytest tests -q` | PASS | Full regression after detail-panel KR/EN localization: `682 passed, 9 subtests passed in 162.53s` |
| Browser Use in-app browser to `http://127.0.0.1:8317/ui/?automation=3-next#quantamental` | PASS | Clicked KR/EN toggle, Top 5 refresh, AAPL analysis, all Quantamental detail tabs, and Q&A; Top 5 rendered five rows with Korean copy and console warn/error count `0` |
| `python -m pytest tests/test_quantamental_api.py::test_quantamental_top_signal_screen_returns_ranked_top_five tests/test_ui_modules.py::test_domain_ui_modules_render_fixture_payloads tests/test_ui_modules.py::test_quantamental_korean_copy_is_not_mojibake -q` | PASS | `3 passed`; covers Top 5 `ranked_rows`/`screened_rows` aliases and UI fallback from `rows`/`freshness` payloads |
| HTTP API smoke on `http://127.0.0.1:8329/api/v1/quantamental/screen/top-signals` | PASS | Custom Top 5 returned `requested_count=6`, `top_count=5`, `ranked_rows_len=6`, `screened_rows_len=6`, `top_signals == ranked_rows[:5]`, `screened_rows == rows`, and `freshness=fresh` in `13621ms` |
| Browser Use in-app browser to `http://127.0.0.1:8329/ui/?automation=3-compat#quantamental` | PASS | Clicked KR/EN, Top 5 auto/manual refresh, AAPL analysis, all Quantamental detail tabs, Q&A, and dashboard tabs Market/Macro/Quant Lab/ML Forecast/AI Portfolio/Quantamental; console warn/error count `0` |
| `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8329 --tickers AAPL,MSFT,NVDA,TSLA,INVALID_TEST_TICKER_123 --output reports\automation_3_quantamental_ui_smoke_8329.json` | PASS | Browser smoke verified required ticker set, invalid ticker fail-closed path, GLOBAL ASML/Toyota resolver paths, Top 5 5 rows, comparison/watchlist/CSV, Q&A, snapshot audit |
| `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8329 --timeout-s 240 --output reports\automation_3_cross_dashboard_smoke_8329.json` | PASS | Cross-dashboard browser smoke verified versioned scripts, domain module globals, all dashboard tab surfaces, Quantamental language toggle and Top 5; no console errors |
| `python -m compileall -q app core pipelines scripts tests` | PASS | Project-wide Python compilation after Top 5 compatibility alias/fallback update |
| `python -m pytest tests -q` | PASS | Full regression after Top 5 compatibility alias/fallback update: `682 passed, 9 subtests passed in 166.13s` |

### Failures, Fixes, and Current-Run Adjustments

- Quantamental's top-level KR/EN toggle already drove API language and Top 5 copy, but detail panels still had many fixed English labels. `app/web/modules/quantamental-ui.js` now localizes overview metrics, chart labels/notes, data-quality tables, SEC/audit/AI/Q&A helper labels, comparison, snapshot, and evidence states; `tests/test_ui_modules.py` now renders Korean fixtures and blocks known mojibake markers.
- Current Browser Use showed the Quantamental surface itself was clean, but the Top 5 compatibility contract still favored `top_signals`/`top` only. The screen service now also exposes explicit `ranked_rows` and `screened_rows`, and the UI renderer can consume `ranked_rows` or legacy `rows` plus `freshness` without rendering an empty Top 5 card.
- Snapshot persistence initially failed because the UPSERT statement in `pipelines/quantamental/snapshot_store.py` had an extra closing parenthesis before `ON CONFLICT`; fixed and reran targeted and full tests.
- The peer-comparison card was initially hidden from the default Core dashboard view because it used `data-panel-tier="operations"`; moved it to the primary tier and reran UI smoke successfully.
- One first-pass manual API smoke command failed because the ad hoc validation script checked stale field paths (`data_quality.level` / `data_quality.score`) instead of the current response fields (`data_quality.quality_level` / `data_quality.data_quality_score`). The implementation was not changed; the validation command was corrected and rerun successfully.
- GET compare initially treated `tickers=AAPL%20MSFT` as one ticker and returned a server error. Fixed the GET parser to accept comma or whitespace separators and added API coverage.
- GET analysis with invalid style query values initially surfaced a Pydantic validation exception as a server error. Fixed GET validation handling to return structured HTTP 400 and added API coverage.
- PowerShell `Invoke-WebRequest`/`Invoke-RestMethod` returned intermittent local `NullReferenceException` in this shell, so the current API smoke uses Python `urllib` and writes `reports/quantamental_remaining_api_latest.json`.
- MCP_DOCKER cannot use host `127.0.0.1` from its browser namespace; current browser verification succeeded through `host.docker.internal:8233`.
- Browser Use in-app browser timed out on `host.docker.internal:8001` in the current run, then succeeded through `http://127.0.0.1:8001/ui/#quantamental`.
- `scripts/quantamental_ui_smoke.py` initially failed when it clicked the Top 5 refresh button while the automatic screen was still loading; the smoke now waits for the button to return to idle before clicking.
- Default Top 5 auto-load was too heavy when it analyzed the full default universe with SEC overlay; the screen now evaluates a bounded six-candidate core-data set, caches successful responses for the UI hot path, and leaves SEC overlay enabled for full analysis paths.
- Browser UI verification used the repository Playwright smoke script against host loopback `http://127.0.0.1:8233/ui/#quantamental`.
- Direct navigation to `/ui/quantamental` initially returned `{"detail":"Not Found"}` because `StaticFiles` only served real files and `/ui/` index routes. Fixed `app/api/server.py` with a UI static fallback that serves `index.html` for extensionless client routes while preserving 404 for missing asset files.
- `python scripts/check_ui_contract.py` initially failed after the Quantamental module cache key was bumped from `v4` to `v5`; updated the contract marker and reran successfully.
- One direct service check initially used Bash heredoc syntax (`python - <<'PY'`) in PowerShell and failed before running Python. Re-ran the same check with a PowerShell here-string and confirmed `GLOBAL` support plus `ACWI` benchmark.
- GLOBAL SEC evidence initially remained missing for `ASML.AS` because local SEC facts existed only under the ADR ticker `ASML`; added ADR alias fallback, hydrated ASML `20-F`/`6-K` SEC data, and verified `ASML.AS` now shows SEC evidence `ok`.
- A first single-ticker compare smoke was invalid because compare requires at least two tickers; reran with `ASML.AS` and `TSM`.
- First live API smoke for `/api/v1/quantamental/resolve/7203` returned 404 because port `8001` was still serving the previous process image. Restarted the server on `127.0.0.1:8001` with the current checkout and reran resolver/hydration/analysis API smokes successfully.
- `7203` GLOBAL analysis intentionally surfaces `SEC evidence: missing` until the mapped SEC alias `TM` is hydrated locally; the new hydration script/API dry-run identifies that mapping instead of silently guessing.
- Codex Security/Bandit medium gate flagged SQL string construction in data-mart, forecast, macro, and output-history paths. The affected queries now use fixed internal SQL fragments plus bound parameters/allowlisted identifiers; the medium/high gate now reports zero findings.
- Quant Lab export retention did not explicitly revalidate the current export directory and prune targets as direct children of the run export root. Added `_validate_direct_export_dir`, applied it to retention and cleanup paths, and added regression coverage.
- `venv311` production validation emitted Qdrant client compatibility warnings for loopback API-key wording and deprecated high-level `add`/`query` methods. Centralized the calls behind compatibility wrappers and broadened local warning suppression; the production validation path now completes without those warnings.
- Credentialed DART live verification exposed that OpenDART financial rows from non-balance/income/cash-flow statements could overwrite mapped balance-sheet and cash-flow fields. Fixed DART account mapping to respect statement type and exact account identifiers, then added regression coverage for equity-statement and cash-flow overwrite cases.
- Server-side comparison watchlist and SEC filing-text opt-in were added after the previous run; browser smoke and API smoke now verify those paths on port `8233`.
- Live DART API data retrieval was executed with a provided `DART_API_KEY`; the key is not stored in the repository or reports. Missing-key fail-closed behavior remains covered by tests.
- First current-run UI smoke failed because the Quantamental default dashboard view hid detail cards; default Quantamental view now uses `all`, and the smoke passes.
- The headless smoke initially clicked the Quantamental ticker finder before async config loading had attached event listeners. Event binding now happens before `loadConfig()`, so fast clicks open the shared picker reliably.
- A stale-price test provider showed stale data could still yield a deterministic classification after retry. Added the strict freshness gate so stale/missing/failed/unknown company, fundamentals, or prices force `Insufficient Data`, lower data quality, and expose `blocking_sections`.
- Previously fixed issues remain covered by tests: invalid ticker AI fallback, English/Korean direct-order rejection, malformed AI JSON fallback, provider failure fallback, division-by-zero, missing data, and insufficient price history.

### Manual Ticker Results

| Ticker | Company | Fundamental | Quant | Factors | Hybrid | Signal | SEC Evidence | Snapshot | AI | Q&A | Data Quality |
|---|---|---|---|---|---:|---|---|---|---|---|---|
| AAPL | PASS | PASS | PASS | PASS | 70.67 | Accumulate Watch | PASS | PASS | PASS deterministic fallback | PASS | good |
| MSFT | PASS | PASS | PASS | PASS | 63.94 | Avoid | PASS | PASS | PASS deterministic fallback | PASS | good |
| NVDA | PASS | PASS | PASS | PASS | 82.06 | Buy Candidate | PASS | PASS | PASS deterministic fallback | PASS | good |
| TSLA | PASS | PASS | PASS | PASS | 55.59 | Neutral / Hold-Watch | PASS | PASS | PASS deterministic fallback | PASS | good |
| INVALID_TEST_TICKER_123 | Structured failed state | Insufficient | Insufficient | Insufficient | N/A | Insufficient Data | Not applicable | PASS | PASS deterministic fallback | PASS | poor, `ticker_validation_failed` |

Valid ticker scores can move slightly because the live yfinance price window updates. The signal is deterministic for the fetched payload.

### Enhancement API Results

- [x] `GET /api/v1/quantamental/compare?tickers=AAPL%20MSFT&expand_peer_universe=true&peer_limit=4` returned 3 rows and added `NVDA` from local data-mart sector/industry metadata.
- [x] `GET /api/v1/quantamental/sec/AAPL` returned status `ok` with 12 concept-provenance rows, 5 filing excerpts, and 3 sample filings.
- [x] `GET /api/v1/quantamental/sec/AAPL?include_filing_text=true&filing_text_timeout_s=2` returned 5 filing excerpts sourced from `sec_filing_text` in the current live smoke.
- [x] `GET /api/v1/quantamental/snapshots/diff` returned status `ok` for two AAPL snapshots.
- [x] `GET /api/v1/quantamental/snapshots/{snapshot_id}/export?format=csv` returned a CSV body containing `snapshot_id`.
- [x] `POST /api/v1/quantamental/snapshots/retention?ticker=AAPL&keep_last=2&dry_run=true` returned status `ok`; destructive deletion was not executed.
- [x] Snapshot destructive retention was executed against a temporary test store and pruned 2 of 3 AAPL snapshots while preserving the latest row.
- [x] `POST/GET/PUT/DELETE /api/v1/quantamental/compare/watchlists` persisted a server-side comparison set, listed it, updated it, and deleted it from the JSON store.
- [x] `GET /api/v1/quantamental/company/005930?market=KR` returned status `ok` with `삼성전자`, `opendart`, KRX metadata, and a present corp code when `DART_API_KEY` was provided.
- [x] `GET /api/v1/quantamental/fundamentals/005930?market=KR&period=annual&years=5` returned status `ok`, 5 annual OpenDART rows, 37 populated deterministic metrics, and 2025 latest-statement fields including revenue, net income, assets, equity, liabilities, current assets/liabilities, cash, debt, OCF, capex, and FCF.
- [x] `GET /api/v1/quantamental/analysis/005930?market=KR&period=annual&years=5&lookback=252` returned status `ok`, data quality `good`, deterministic `Buy Candidate` signal, and no missing-key warning.
- [x] Missing-key behavior remains fail-closed and covered by `test_quantamental_kr_dart_provider_fails_closed_without_key`.
- [x] `GET /api/v1/quantamental/quant/005930?market=KR&lookback=80` returned status `ok` through `yfinance_kr`; the KRX fallback parser is unit-tested and remains available if yfinance returns no rows.
- [x] Direct live Naver KRX fallback smoke for `005930` returned 5 daily rows ending `2026-05-15` with last close `276500.0`.
- [x] `GET /api/v1/quantamental/resolve/7203?market=GLOBAL` returned `7203.T`, SEC alias `TM`, and warning `global_symbol_resolved_to_yfinance:7203.T`.
- [x] `POST /api/v1/quantamental/sec/global/hydrate?dry_run=true` returned a write-free plan mapping `ASML.AS -> ASML` and `7203 -> TM`, while skipping unmapped `9999.T`.
- [x] `GET /api/v1/quantamental/analysis/AAPL?...` returned freshness `fresh`, freshness score `100`, and fresh company/fundamentals/prices/SEC sections in the current live service smoke.
- [x] `POST /api/v1/quantamental/screen/top-signals` with `AAPL,MSFT,NVDA,TSLA,AMD,CRM` returned top 5 rows ranked as `NVDA`, `AMD`, `AAPL`, `MSFT`, `CRM`; all rows had fresh data in that smoke.
- [x] Current HTTP smoke returned AAPL `data_integrity.status=ok`, `usable_for_signal=true`, no `blocking_sections`, and custom screen rows all `usable_for_signal=true` with empty warnings.

### Frontend Verification Coverage

- [x] Quantamental tab renders at `/ui/#quantamental`.
- [x] Direct client route `/ui/quantamental` renders the same static UI instead of FastAPI `Not Found`.
- [x] Quantamental ticker control uses the same shared `찾기` symbol picker pattern as the other ticker fields; browser verification selected `MSFT` and applied it before analysis.
- [x] Ticker, market, period, years, lookback, and strategy-style controls are operable.
- [x] Signal Card, Composite Score, Factor Grid, Fundamental, Quant, Risk, AI, and Q&A tabs render.
- [x] Peer, SEC, and Audit tabs render.
- [x] Browser Use verified `005930` with `market=KR` using credentialed OpenDART: `삼성전자`, deterministic signal, score, factor, quality, and tab surfaces rendered without console errors.
- [x] Browser Use verified `ASML.AS` with `market=GLOBAL`: shared picker result, market label `Global`, company `ASML Holding N.V.`, deterministic `Accumulate Watch`, Composite Score, Factor Grid, data quality `good`, `SEC evidence: ok · filings 6 · facts 120`, visible disclaimer, no `unsupported_market`, and zero browser console errors.
- [x] Playwright verified `7203` with `market=GLOBAL`: resolver mapped to Toyota via `7203.T`, displayed `global_symbol_resolved_to_yfinance:7203.T`, Signal Card, Composite Score, Factor Grid, data quality `good`, visible disclaimer, no `unsupported_market`, and zero browser console errors.
- [x] Peer Comparison card accepts multiple tickers, can expand peers, saves/loads server-backed watchlists with localStorage fallback, exports CSV, and renders the comparison table.
- [x] Audit tab exposes snapshot JSON/CSV export, diff, and retention preview controls.
- [x] Missing/invalid ticker and provider-unavailable states render visible failed/insufficient-data states without breaking the page.
- [x] Data-quality warnings and errors are visible for invalid/provider-unavailable inputs.
- [x] Top 5 Signal Screener auto-loads on Quantamental tab entry and displays exactly five ranked rows when scored candidates exist.
- [x] Score Threshold Screener exposes selected score type (`복합`, `가치`, `품질`, `성장`, `모멘텀`, `저변동성`, `유동성`), minimum score, and result limit controls; browser verification with `모멘텀`, minimum `0`, and limit `10` rendered exactly 10 rows.
- [x] Data Quality displays freshness status, freshness score, section-level as-of dates, age, basis, and refreshability.
- [x] Data Quality displays strict integrity status, signal usability, blocking sections, and optional issue sections.
- [x] Overview displays explicit `X: date` and per-chart `Y:` units plus explanatory chart notes and missing-value handling text.
- [x] Top 5 Signal Screener table displays candidate integrity and only promotes usable core-data rows.
- [x] Browser Use verified the current rendered page on port `8259`: Top 5 table visible, shared picker modal visible, AAPL analysis rendered, overview axis/missing-value text present, and zero console warnings/errors.
- [x] Browser Use verified the current rendered page on port `8262`: strict-gate UI visible, AAPL signal usable, Top 5 integrity visible, and zero console warnings/errors.

### Safety Verification

- [x] AI report and Q&A use deterministic engine context.
- [x] AI fallback preserves the deterministic Signal Engine label.
- [x] Tests cover malformed AI JSON, provider failure fallback, and direct-order rejection.
- [x] UI disclaimer says research classification only and not investment advice.
- [x] `Buy Candidate` and `Sell Risk / Reduce Risk` are generated by `pipelines/quantamental/signal_engine.py`, not by AI.
- [x] Manual smoke scan found no English or Korean direct-order language such as `buy now`, `sell now`, `must buy`, `must sell`, or equivalent mandatory buy/sell phrases in report/Q&A outputs.

---

## 9. Confirmed Current Limits

- US equities are supported through yfinance plus local SEC evidence when the data mart has filings/facts.
- KR equities are wired through OpenDART and require `DART_API_KEY`; credentialed 005930 company/fundamental/analysis retrieval is verified, and missing-key behavior remains fail-closed.
- The provided DART key was used only as a process environment variable during verification; it is not stored in repository files or generated reports.
- KR price history fallback parsing is implemented for Naver Finance KRX daily rows; live direct fallback smoke for `005930` passed, and the provider fallback path is unit-tested by forcing empty `yfinance_kr` history.
- GLOBAL equities and ETFs route through an exchange-aware yfinance resolver with `ACWI` as the default benchmark; representative global symbols are available in the shared picker, but coverage still depends on Yahoo Finance symbol availability and the curated alias map.
- yfinance data can be incomplete, delayed, or revised.
- Top 5 screening is deterministic and always available for the configured/default universe; rows are promoted only when company, fundamentals, and prices are fresh/complete after retry. The default UI auto-load uses a fast cached core-data screen and skips optional SEC overlay for speed, while full single-name and compare analysis still include SEC evidence by default. Provider outages, exchange holidays, or unavailable optional SEC evidence remain visible as blocked/optional sections instead of being silently used.
- Broader peer-universe expansion first uses local `asset_metadata` sector/industry coverage and has a deterministic static liquid-peer fallback for `GLOBAL` when metadata is empty; added peers are still analyzed by providers, no scores are fabricated.
- SEC evidence supports US tickers and mapped GLOBAL ADR/dual-listed aliases such as `ASML.AS -> ASML`; ASML `20-F`/`6-K` data is hydrated locally and verified. A dry-run planner and operator script (`scripts/quantamental_global_sec_hydrate.py`) identify mapped SEC aliases such as `7203 -> TM`; non-SEC-listed or unmapped global equities still return visible missing/skipped evidence until a valid alias exists and data is hydrated. Filing-text excerpts remain opt-in and depend on SEC availability, rate limits, and a valid `SEC_USER_AGENT`.
- Persisted snapshots are local SQLite audit records under the configured Quantamental data directory.
- Snapshot retention destructive deletion is verified against temporary test stores; production/manual destructive deletion was intentionally not run against the user's real snapshot history.
- Peer-comparison watchlists are server-backed JSON records under the Quantamental data directory, with browser `localStorage` retained only as an offline fallback.
- AI provider use is optional; deterministic fallback is the default and verified path.
- Signals are research classifications, not investment advice.

---

## 10. Optional Further Enhancements

These are not required for the completed checklist above, but they are the next high-leverage upgrades after the current enhancement pass:

- Add an official KRX/KIS provider adapter with explicit rate-limit and holiday handling if the current Naver/yfinance KR path proves unreliable in longer live runs.
- Continue expanding the curated GLOBAL ADR/dual-listed alias map beyond the currently covered representative symbols.
- Wire `scripts/quantamental_global_sec_hydrate.py` into Windows Task Scheduler or the existing data-mart scheduler so mapped GLOBAL SEC aliases refresh automatically.
- Persist fetched SEC filing text excerpts into the data mart if repeated full-text SEC calls become too slow or rate-limited.
- Add a richer UI diff/replay view for snapshots, including charted score deltas and field-level drilldown.
- Add CI workflow coverage for the Quantamental targeted subset if this repository enables `.github/workflows`.
