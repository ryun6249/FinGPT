# Macro Implementation Checklist

Status values used in this document: `TODO`, `IN_PROGRESS`, `DONE`, `PARTIAL`, `BLOCKED`, `NOT_DONE`.

This document is the source of truth for the Macro implementation. Items are marked `DONE` only when implementation and verification evidence exists. Items that are intentionally left as future work are marked `NOT_DONE`. Items that are implemented but not fully integrated or not fully verified are marked `PARTIAL`.

## 1. Repository Inspection

- frontend framework: Static HTML/CSS/JavaScript served from `app/web` through FastAPI `StaticFiles`; no `package.json` or React build step found.
- backend framework: FastAPI app in `app/api/server.py`.
- routing structure: API routers live under `app/api/routers`; existing convention is `/api/v1/*`; compatibility aliases can be registered by including the same router under a second prefix.
- API client structure: `app/web/app.js` has a top-level `API` object and uses `fetch` directly.
- state management structure: `app/web/app.js` top-level `state` object plus DOM element registry `els`.
- styling/design system: `app/web/styles.css` with `home-card`, `decision-surface`, `decision-metric-grid`, `decision-table`, `dashboard-tab`, chart, and status badge primitives.
- chart library: No external chart library in the local UI; reusable inline SVG helpers exist in `app/web/app.js`.
- existing Quant Lab / FinGPT modules: Quant routes under `app/api/routers/quant_lab.py`; orchestration under `pipelines/orchestration/quant_lab_pipeline.py`; Quant schemas under `core/schemas/quant.py`.
- existing data provider modules: Collection providers under `pipelines/collect`; data-mart providers under `pipelines/data_mart/providers`; FRED collectors already exist.
- existing AI/LLM integration modules: Local inference adapters under `pipelines/infer`; AI Portfolio explanation fallback under `pipelines/ai_portfolio/explainer.py`.
- existing cache/storage/database layer: SQLite data mart under `pipelines/data_mart/storage`, with `macro_series` and `macro_observations` tables already present.
- existing test/build/lint commands: Pytest is configured by `pytest.ini`; static UI contract check is `python scripts/check_ui_contract.py`; JS syntax can be checked with `node --check app\web\app.js`; no npm build script found.
- Macro related existing code: Existing macro collection/RAG support exists in `pipelines/collect/macro_collector.py`, `pipelines/collect/fred_collector.py`, `pipelines/data_mart/providers/fred_provider.py`, and `pipelines/data_mart/jobs/update_macro_daily.py`, but there was no Macro dashboard platform layer or API router before this work.
- AI Portfolio or research workflow connection points: AI Portfolio service layer is under `pipelines/ai_portfolio`; research API is under `app/api/routers/research.py`; this implementation exposes Macro research context as a service/API integration point without mutating existing research prompt paths.

## 2. Architecture Decision

- selected backend module structure: Added `core/schemas/macro.py`, `pipelines/macro/*`, and `app/api/routers/macro.py`.
- selected frontend module structure: Extended the existing static dashboard tab model in `app/web/index.html`, `app/web/app.js`, and `app/web/styles.css` rather than adding a new React-style page tree.
- data provider abstraction: Added provider base classes plus `DataMartMacroProvider`, `FredProvider`, and `UnavailableProvider`.
- config-driven series registry: Added registry in `pipelines/macro/series_registry.py` with required FRED-style series, expanded enabled coverage, and disabled future placeholders.
- regime engine design: Rule-based, score-driven, transparent, with unknown/low-confidence fallback when insufficient inputs are available.
- AI prompt/service connection: Stored prompt templates in `pipelines/macro/prompts.py`; MVP returns a rule-based fallback brief from structured Macro payload only.
- data quality handling: Per-series and aggregate status with `ok`, `partial`, `stale`, `unavailable`; preserves missing/stale/provider/transformation errors.
- cache use: Uses existing local data mart rows as the first cache; fetches from FRED only when a usable API key is available; otherwise returns unavailable without fabricated values. Service-level TTL cache avoids repeated live fetches within a short window.
- live provider fallback policy: If no data-mart rows and no live provider/key, returns empty observations and explicit unavailable quality.
- future extension points: Provider adapters for ECOS/OECD/WorldBank/Yahoo, country/provider filters, additional registry entries, ML/factor regime classifiers, report automation, and direct research prompt injection.
- 2026-05-09 coverage expansion: Enabled registry coverage now spans 74 series across rates, inflation, growth, labor, housing/consumer, liquidity/credit, financial conditions, FX/dollar, commodities, and market proxies.

## 3. Implementation Phases

- Phase 1: Macro route/tab, page shell, overview UI, data quality UI. Status: DONE.
- Phase 2: macro series registry, provider abstraction, data quality model. Status: DONE.
- Phase 3: backend macro APIs, overview/series/category endpoints. Status: DONE.
- Phase 4: interest rates, inflation, growth/labor, yield curve panels and charts. Status: DONE.
- Phase 5: macro regime engine, scoring logic, regime classification. Status: DONE.
- Phase 6: asset impact mapping, portfolio policy hints. Status: DONE.
- Phase 7: AI Macro Brief, research context provider. Status: DONE for guarded optional Ollama invocation, fallback brief, research context API, and single-ticker/ETF research-pipeline injection. Current live Ollama output was rejected by the grounding guard and correctly fell back.
- Phase 8: extensibility hooks for countries/providers/indicators. Status: DONE for ECOS/OECD/WorldBank/Yahoo adapter classes, provider routing, provider health metadata, expanded FRED coverage, Yahoo FX/commodity category surfaces, and UI data-coverage visibility. Current ECOS live data is BLOCKED without `ECOS_API_KEY`.
- Phase 9: tests, validation, smoke checks, documentation. Status: DONE because compile, targeted tests, UI contract, JS syntax, broader Macro/research/topic ruff, full pytest, live API smoke, and browser navigation passed. `npm run build` remains N/A because this static UI has no `package.json` build script.

## 4. Detailed Task Format

### [M0] Repository Inspection And Checklist Control
- Status: DONE
- Target Files:
  - `docs/MACRO_IMPLEMENTATION_CHECKLIST.md`
  - `app/api/server.py`
  - `app/web/index.html`
  - `app/web/app.js`
  - `app/web/styles.css`
  - `pipelines/collect/fred_collector.py`
  - `pipelines/data_mart/providers/fred_provider.py`
  - `pipelines/data_mart/storage/schema.py`
- Expected Behavior:
  - The implementation starts from the actual repo structure and records decisions before code changes.
- Implementation Notes:
  - Existing UI is static HTML/CSS/JS; backend is FastAPI; local macro storage already exists in the data mart.
- Extension Notes:
  - Use this file for final reconciliation and future Macro platform expansion.
- Verification Method:
  - Code inspection.
- Verification Command:
  - `rg --files`
  - `Get-Content app\api\server.py`
  - `Select-String -Path pipelines\data_mart\storage\schema.py -Pattern "macro" -Context 3,20`
- Result Notes:
  - DONE. Inspection completed before implementation.

### [P1-UI] Macro Dashboard Tab And Shell
- Status: DONE
- Target Files:
  - `app/web/index.html`
  - `app/web/app.js`
  - `app/web/styles.css`
  - `scripts/check_ui_contract.py`
  - `tests/test_ui_routing_contract.py`
- Expected Behavior:
  - Macro tab is visible, URL-addressable, and renders overview/data-quality/regime/impact/brief surfaces.
- Implementation Notes:
  - Reused dashboard tab primitives and added `macro-surface` sections.
  - Added `#macro` addressability and Macro tab state.
- Extension Notes:
  - Can later split into component files if the web UI moves to a bundler.
- Verification Method:
  - Static UI contract, JS syntax, route smoke, browser smoke.
- Verification Command:
  - `node --check app\web\app.js`
  - `python scripts\check_ui_contract.py --output reports\macro_ui_contract.json`
  - Browser MCP: `http://host.docker.internal:8013/ui/#macro`
- Result Notes:
  - DONE. Macro tab rendered in browser; tab active state, `data-dashboard-tab="macro"`, overview, table, data quality, asset impact, advisory hint, and fallback brief were visible.

### [P2-BACKEND-MODELS] Macro Schemas, Registry, Providers, Quality
- Status: DONE
- Target Files:
  - `core/schemas/macro.py`
  - `pipelines/macro/series_registry.py`
  - `pipelines/macro/providers/base.py`
  - `pipelines/macro/providers/storage.py`
  - `pipelines/macro/providers/fred.py`
  - `pipelines/macro/providers/unavailable.py`
  - `pipelines/macro/data_quality.py`
  - `pipelines/macro/transforms.py`
- Expected Behavior:
  - Registry-driven series definitions and provider abstraction return structured data with explicit quality.
- Implementation Notes:
  - Uses data mart cache first, FRED only with a usable API key, otherwise unavailable.
  - `FRED_API_KEY=0`, `false`, `disabled`, `none`, `null`, or empty string disables live FRED for deterministic unavailable smoke checks.
- Extension Notes:
  - Add ECOS/OECD/WorldBank/Yahoo providers behind the same provider contract.
- Verification Method:
  - Unit tests and API smoke.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py -q`
  - FRED-disabled API smoke with `FRED_API_KEY=0`
- Result Notes:
  - DONE. Required series load, unavailable provider returns no fake observations, unknown series returns controlled 404, and every API surface carries data quality.

### [P3-BACKEND-API] Macro API Router
- Status: DONE
- Target Files:
  - `app/api/server.py`
  - `app/api/routers/macro.py`
  - `tests/test_api_router_split.py`
  - `tests/test_macro_platform.py`
- Expected Behavior:
  - Required Macro APIs exist under `/api/v1/macro/*` plus `/api/macro/*` compatibility aliases.
- Implementation Notes:
  - Router stays thin; service logic lives under `pipelines/macro`.
- Extension Notes:
  - Add filters for country/provider later without changing response schema.
- Verification Method:
  - Route tests, TestClient smoke, live HTTP smoke.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py tests\test_api_router_split.py -q`
  - `Invoke-WebRequest http://127.0.0.1:8013/api/v1/macro/overview`
- Result Notes:
  - DONE. Live server returned 200 for health, UI, macro health, series, overview, regime, data-quality, and brief endpoints.

### [P4-FRONTEND-PANELS] Category Panels And Charts
- Status: DONE
- Target Files:
  - `app/web/index.html`
  - `app/web/app.js`
  - `app/web/styles.css`
- Expected Behavior:
  - Interest rates, inflation, growth/labor, yield curve, liquidity/credit, FX/dollar, and commodities panels show series tables/charts or unavailable states.
- Implementation Notes:
  - Reused inline SVG chart helpers; no fabricated observations are displayed.
  - FX/dollar and commodities panels are provider-extension surfaces and can show unavailable/empty states.
- Extension Notes:
  - Add multi-country/provider controls later.
- Verification Method:
  - UI contract and browser smoke.
- Verification Command:
  - `python scripts\check_ui_contract.py --output reports\macro_ui_contract.json`
  - Browser MCP screenshot `macro-dashboard-8013-loaded.png`
- Result Notes:
  - DONE. Category panels, charts, stale states, unavailable visibility, and data-quality text rendered.

### [P5-REGIME] Macro Regime Engine
- Status: DONE
- Target Files:
  - `pipelines/macro/regime_engine.py`
  - `tests/test_macro_platform.py`
- Expected Behavior:
  - Growth/inflation/labor/policy/liquidity/credit scores and signals produce transparent regime classifications, with unknown fallback for insufficient data.
- Implementation Notes:
  - Rule-based MVP only; exposes missing inputs and confidence.
  - Insufficient data does not force a regime classification.
- Extension Notes:
  - Future ML/factor classifier can implement the same service boundary.
- Verification Method:
  - Synthetic scenario tests plus unavailable-data fallback tests.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py -q`
- Result Notes:
  - DONE. Unknown low-confidence fallback and synthetic goldilocks classification are covered by tests.

### [P6-IMPACT-HINTS] Asset Impact And Portfolio Hints
- Status: DONE
- Target Files:
  - `pipelines/macro/asset_impact.py`
  - `pipelines/macro/portfolio_hints.py`
  - `tests/test_macro_platform.py`
- Expected Behavior:
  - Asset impact and portfolio policy hints are advisory only and include confidence, reasons, risks, and data quality.
- Implementation Notes:
  - No trade orders are created and AI Portfolio policy is not mutated.
- Extension Notes:
  - AI Portfolio can consume these hints later after explicit approval flows are designed.
- Verification Method:
  - Unit/API tests and browser smoke.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py -q`
- Result Notes:
  - DONE. Required asset classes are returned, and policy hint has `advisory_only=true`.

### [P7-AI-RESEARCH] AI Macro Brief And Research Context
- Status: DONE
- Target Files:
  - `pipelines/macro/prompts.py`
  - `pipelines/macro/ai_brief.py`
  - `pipelines/macro/research_context.py`
  - `app/api/routers/macro.py`
  - `app/web/app.js`
  - `tests/test_macro_platform.py`
- Expected Behavior:
  - AI Macro Brief uses only structured Macro payload; fallback brief is explicit; research context API returns structured context.
- Implementation Notes:
  - Brief generation now supports optional guarded Ollama invocation via `use_llm=true`.
  - If the model times out, returns empty text, uses direct trading language, or emits ungrounded numeric tokens, the service returns the deterministic `rule_based_fallback`.
  - Macro research context is converted into a `macro:platform` retrieval item and injected into the single-ticker research pipeline when the request source includes `macro` and the ticker/question is macro-relevant.
- Extension Notes:
  - Topic-mode and sector-wide prompt injection should be hardened separately after topic prompt-contract tests are added.
- Verification Method:
  - Unit/API tests, live API smoke, browser brief-generation smoke.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py -q`
  - `Invoke-WebRequest -Method POST http://127.0.0.1:8014/api/v1/macro/brief`
  - Browser MCP click on `macroBriefGenerate`
- Result Notes:
  - DONE. Prompt template, fallback service, optional guarded LLM path, UI, research context API, and single-ticker research-context injection are implemented and verified. Live Ollama was reachable but its generated brief introduced an ungrounded `4.5%` token, so the guard rejected it and returned fallback as designed.

### [P8-EXTENSIBILITY] Providers, Countries, Indicators Hooks
- Status: DONE
- Target Files:
  - `pipelines/macro/series_registry.py`
  - `pipelines/macro/providers/base.py`
  - `app/api/routers/macro.py`
- Expected Behavior:
  - `/providers`, `/countries`, `/health`, expanded category APIs, and future placeholder metadata exist without fake data.
- Implementation Notes:
  - Added ECOS, OECD, World Bank, and Yahoo provider adapters behind the common provider contract.
  - Yahoo FX/commodity/market proxy entries are enabled and route through yfinance.
  - Expanded default FRED-backed coverage to 69 enabled FRED series plus 5 Yahoo market proxies.
  - Added visible Macro data coverage UI and new `housing-consumer` and `financial-conditions` category surfaces.
  - ECOS/OECD/World Bank entries are registry-visible but disabled in default dashboards to avoid surprise key/network dependencies; direct series fetches can use their adapters.
- Extension Notes:
  - ECOS requires `ECOS_API_KEY`; OECD/World Bank registry entries can be enabled once operator latency and country coverage policy are chosen.
- Verification Method:
  - Unit tests, targeted ruff, API smoke, browser smoke.
- Verification Command:
  - `python -m pytest tests\test_macro_platform.py -q`
  - `python -m ruff check core\schemas\macro.py core\config\settings.py pipelines\macro app\api\routers\macro.py pipelines\orchestration\topic_pipeline.py tests\test_macro_platform.py tests\test_topic_pipeline.py`
  - `Invoke-WebRequest http://127.0.0.1:8015/api/v1/macro/fx-dollar`
  - `Invoke-WebRequest http://127.0.0.1:8015/api/v1/macro/commodities`
- Result Notes:
  - DONE. Mocked provider tests cover World Bank, OECD SDMX, Yahoo/yfinance, and ECOS missing-key behavior. Live smoke on port 8015 returned `fx-dollar count=1 quality=ok providers=yahoo`, `commodities count=2 quality=ok providers=yahoo`, and provider metadata listed `data_mart,fred,ecos,oecd,worldbank,yahoo,unavailable`.
  - DONE. 2026-05-09 expansion added 74 enabled registry entries and category surfaces for housing/consumer and financial conditions.

### [P9-VERIFY-DOCS] Tests, Validation, Final Reconciliation
- Status: DONE
- Target Files:
  - `tests/test_macro_platform.py`
  - `tests/test_ui_routing_contract.py`
  - `tests/test_api_router_split.py`
  - `docs/MACRO_IMPLEMENTATION_CHECKLIST.md`
- Expected Behavior:
  - Relevant tests and smoke checks are run; checklist reflects actual implementation and failures.
- Implementation Notes:
  - Core Macro acceptance is verified by targeted pytest, full pytest, compile, JS syntax, broader ruff, UI contract, API smoke, and browser smoke.
- Extension Notes:
  - Add deeper prompt-content assertions for topic-mode Macro sections if the topic prompt schema changes.
- Verification Method:
  - Pytest, JS syntax, UI contract, API smoke, browser smoke.
- Verification Command:
  - `python -m compileall -q core\schemas\macro.py pipelines\macro app\api\routers\macro.py app\api\server.py pipelines\orchestration\research_pipeline.py`
  - `python -m pytest tests\test_macro_platform.py tests\test_api_router_split.py tests\test_ui_routing_contract.py -q`
  - `node --check app\web\app.js`
  - `python scripts\check_ui_contract.py --output reports\macro_ui_contract.json`
  - `python -m pytest tests -q`
  - Browser MCP: `http://host.docker.internal:8015/ui/#macro`
- Result Notes:
  - DONE. Fresh compile, targeted tests, UI contract, JS syntax, broader Macro/research/topic ruff, full pytest, live API smoke, and browser navigation passed. The prior `research_pipeline.py` E402/F841/F601 lint blockers were remediated.

## 5. Backend Checklist

- macro module/package creation: DONE (`pipelines/macro`).
- series registry/config creation: DONE (`pipelines/macro/series_registry.py`).
- provider abstraction creation: DONE (`pipelines/macro/providers/base.py`).
- FRED-style provider adapter: DONE (`pipelines/macro/providers/fred.py`).
- future ECOS/OECD/WorldBank/Yahoo provider extension point: DONE for adapter classes and provider routing; ECOS live data is BLOCKED without `ECOS_API_KEY`.
- data normalization: DONE (`pipelines/macro/transforms.py`).
- data transformations: DONE (`level`, `yoy_percent`, and change calculations).
- data quality model: DONE (`core/schemas/macro.py`, `pipelines/macro/data_quality.py`).
- cache/staleness handling: DONE (data mart first, live FRED fallback, TTL service cache, per-series stale checks).
- overview service: DONE (`pipelines/macro/macro_service.py`).
- category service: DONE.
- series service: DONE.
- regime engine: DONE.
- asset impact service: DONE.
- portfolio policy hint service: DONE.
- research context service: DONE as API integration point, single-ticker/ETF research-pipeline injection, and topic/sector Macro context injection.
- AI macro brief service: DONE for prompt template, fallback, optional guarded Ollama invocation, and grounding-guard fallback.
- error handling: DONE for controlled unavailable/provider/transformation/unknown-series paths.
- unavailable/stale/partial data handling: DONE.
- API routes: DONE.

## 6. Frontend Checklist

- Macro route/tab: DONE.
- MacroPage equivalent in existing static dashboard: DONE.
- Macro overview cards: DONE.
- key indicator table: DONE.
- data quality panel: DONE.
- Interest Rates panel: DONE.
- Inflation panel: DONE.
- Growth & Labor panel: DONE.
- Yield Curve panel: DONE.
- Liquidity & Credit panel: DONE.
- FX & Dollar panel: DONE with Yahoo DXY proxy when yfinance is available; unavailable state remains explicit if the provider fails.
- Commodities panel: DONE with Yahoo GLD/USO proxies when yfinance is available; unavailable state remains explicit if the provider fails.
- Macro Regime panel: DONE.
- Asset Impact panel: DONE.
- Portfolio Policy Hints panel: DONE.
- AI Macro Brief panel: DONE with fallback brief generation.
- MacroSeriesChart: DONE using inline SVG chart helpers.
- loading states: DONE.
- error states: DONE.
- stale data states: DONE.
- insufficient data states: DONE.
- responsive layout: DONE through existing dashboard responsive CSS plus Macro grid rules.
- existing UI style integration: DONE.
- Export Report action: DONE. UI button and `/api/v1/macro/report` Markdown report endpoint are implemented and smoke-tested.

## 7. Macro Regime Engine Checklist

- growth score: DONE.
- inflation score: DONE.
- labor score: DONE.
- policy score: DONE.
- liquidity score: DONE.
- credit score: DONE.
- risk level: DONE.
- confidence score: DONE.
- unknown/low confidence fallback: DONE.
- transparent rule documentation: DONE in code comments and evidence fields.
- regime classification: DONE.
- regime-to-asset mapping: DONE.
- regime-to-portfolio-hint mapping: DONE.
- future ML/factor-model extension point: DONE for an auditable factor-prototype classifier exposed through `engine=factor`; NOT_DONE for a trained ML classifier because labeled regime history/model governance are outside this MVP.

## 8. AI Layer Checklist

- AI Macro Brief prompt: DONE (`pipelines/macro/prompts.py`).
- Macro Regime Explanation prompt: DONE as part of prompt template and fallback sections.
- Asset Impact Explanation prompt: DONE as part of prompt template and fallback sections.
- Portfolio Policy Hint Explanation prompt: DONE as part of prompt template and fallback sections.
- Research Context Summary prompt: DONE at service/API context level, single-ticker research-pipeline injection level, and topic/sector Macro context injection level.

Prompt constraints:
- data fabrication prohibited: DONE.
- market result guarantees prohibited: DONE.
- structured Macro data only: DONE.
- data, interpretation, implication separation: DONE.
- missing/stale data surfaced: DONE.
- direct buy/sell instructions prohibited: DONE.
- uncertainty required: DONE.

AI integration status:
- deterministic fallback brief: DONE.
- live LLM call: DONE as optional guarded Ollama path. Current live smoke rejected one model output for an ungrounded `4.5%` token and returned fallback, which is the intended fail-closed behavior.

## 9. Testing and Verification Checklist

- backend unit tests: DONE (`tests/test_macro_platform.py`).
- frontend tests or manual verification: DONE for static routing/UI contract and browser smoke.
- API smoke tests: DONE.
- lint: DONE. JS syntax check passed, targeted ruff passed, and broader ruff including `pipelines/orchestration/research_pipeline.py` passed after cleanup.
- build: DONE for fresh Python compile; N/A for npm because no `package.json` build script exists.
- route smoke check: DONE.
- data quality smoke check: DONE.
- regime engine scenario tests: DONE.
- existing app regression check: DONE. Full pytest suite passed.

Executed commands and results:

| Command | Result |
|---|---|
| `python -m compileall -q core\schemas\macro.py pipelines\macro app\api\routers\macro.py app\api\server.py pipelines\orchestration\research_pipeline.py` | PASS |
| `python -m pytest tests\test_macro_platform.py -q` | PASS, 20 tests |
| `python -m pytest tests\test_macro_platform.py tests\test_topic_pipeline.py tests\test_api_router_split.py tests\test_ui_routing_contract.py -q` | PASS, 50 tests |
| `python -m pytest tests -q` | PASS, 518 tests and 3 subtests |
| `node --check app\web\app.js` | PASS |
| `python -m ruff check core\schemas\macro.py core\config\settings.py pipelines\macro app\api\routers\macro.py pipelines\orchestration\topic_pipeline.py tests\test_macro_platform.py tests\test_topic_pipeline.py` | PASS |
| `python -m ruff check core\schemas\macro.py core\config\settings.py pipelines\macro app\api\routers\macro.py pipelines\orchestration\research_pipeline.py pipelines\orchestration\topic_pipeline.py tests\test_macro_platform.py tests\test_topic_pipeline.py` | PASS |
| `python scripts\check_ui_contract.py --output reports\macro_ui_contract.json` | PASS, missing markers `[]` |
| `python -m pytest tests\test_macro_platform.py tests\test_ui_routing_contract.py -q` after 2026-05-09 coverage expansion | PASS, 48 tests |
| `node --check app\web\app.js` after 2026-05-09 coverage expansion | PASS |
| `python scripts\check_ui_contract.py` after 2026-05-09 coverage expansion | PASS, missing markers `[]` |
| Live API smoke on `http://127.0.0.1:8002/api/v1/macro/health` after 2026-05-09 coverage expansion | PASS: `registry_series=74`, 10 enabled categories |
| Live Macro refresh for replacement series `BUSINV,DCOILBRENTEU` on `http://127.0.0.1:8002/api/v1/macro/refresh` | PASS: `status=success`, `fred:ok`, 1,318 rows inserted, no provider errors |
| FRED-disabled API smoke with `FRED_API_KEY=0` | PASS: series/overview/regime/data-quality/brief return unavailable/unknown/fallback without fake observations |
| Live API smoke on `http://127.0.0.1:8013` | PASS: health/UI/macro health/series/overview/regime/data-quality/brief returned HTTP 200 |
| Live API smoke on `http://127.0.0.1:8014` | PASS: health/report/guarded brief returned HTTP 200; guarded live LLM rejected ungrounded `4.5%` and returned fallback |
| Live API smoke on `http://127.0.0.1:8015` | PASS: health/UI/macro health/providers/overview/factor regime/fx-dollar/commodities/YAHOO_GLD/brief returned HTTP 200 |
| Live API smoke on `http://127.0.0.1:8015` after final lint cleanup | PASS: `/api/v1/health`, `/api/v1/macro/health`, `/api/v1/macro/overview`, and POST `/api/v1/macro/brief` returned HTTP 200/success; brief remained explicit `rule_based_fallback` with partial data-quality warnings |
| Browser smoke on `http://host.docker.internal:8013/ui/#macro` | PASS: Macro tab rendered, active tab state correct, table/chart/regime/impact/advisory/fallback visible, console warnings/errors 0 |
| Browser smoke on `http://host.docker.internal:8014/ui/#macro` | PASS: Macro tab rendered, Export Report button visible, active tab state correct, table/chart/regime/impact/advisory visible, console warnings/errors 0 |
| Browser smoke on `http://host.docker.internal:8015/ui/#macro` | PASS: Browser MCP navigation reached the Macro route and reported page title `FinGPT Local Research Assistant` |
| Browser smoke on `http://127.0.0.1:8002/ui/?fresh=macroExpandedCoverage#macro` | PASS: coverage card showed 74 active series, housing/consumer showed 8 indicators, financial conditions showed 4 indicators, console warnings/errors 0 |

Failed or limited verification:

- Playwright MCP direct URL `http://127.0.0.1:8013/ui/#macro` from Docker browser failed with connection refused; `http://host.docker.internal:8013/ui/#macro` succeeded.
- Playwright default profile path was locked by another browser process; Docker browser MCP was used successfully.
- npm build was not run because no `package.json` build script exists for this static UI.
- Trained ML regime classification was not implemented; the delivered classifier is a transparent rule-based engine plus an auditable factor-prototype engine.

## 10. Acceptance Criteria Checklist

- Macro tab/page is visible: DONE.
- Macro overview loads: DONE.
- Key indicator cards/table exists: DONE.
- Data quality status is visible: DONE.
- Missing data is not fabricated: DONE.
- series registry exists: DONE.
- provider abstraction exists: DONE.
- overview API exists: DONE.
- series API exists: DONE.
- category API exists: DONE.
- regime API exists: DONE.
- asset impact API exists: DONE.
- AI Macro Brief or fallback brief exists: DONE.
- portfolio policy hints are advisory only: DONE.
- research context integration point exists: DONE.
- UI handles loading/error/stale/unavailable states: DONE.
- AI uses only structured Macro payload: DONE. Live LLM output is accepted only after grounding guard; otherwise fallback is returned.
- Existing FinGPT/Quant Lab core navigation is not broken by static routing contract: DONE.
- Verification results are recorded in this MD file: DONE.

## 11. Final Completion Summary

| Area | DONE | PARTIAL | BLOCKED | NOT_DONE | Notes |
|---|---:|---:|---:|---:|---|
| Repository Inspection | 1 | 0 | 0 | 0 | Actual FastAPI/static UI/data mart structure recorded. |
| Architecture | 1 | 0 | 0 | 0 | Macro platform layer added with explicit boundaries. |
| Backend | 22 | 0 | 1 | 0 | ECOS/OECD/WorldBank/Yahoo adapters and routing added; ECOS live data requires `ECOS_API_KEY`. |
| Frontend | 22 | 0 | 0 | 0 | Export report is implemented. |
| Data Provider | 11 | 0 | 1 | 0 | FRED/data mart/unavailable plus ECOS/OECD/WorldBank/Yahoo adapters implemented; ECOS live data blocked without key. |
| Regime Engine | 14 | 0 | 0 | 1 | Rule-based and factor-prototype classifiers done; trained ML classifier remains future work. |
| Asset Impact | 5 | 0 | 0 | 0 | Required asset classes covered. |
| Portfolio Hints | 6 | 0 | 0 | 0 | Advisory-only; no portfolio mutation. |
| AI Layer | 8 | 0 | 0 | 0 | Prompt/fallback plus optional guarded Ollama invocation done. |
| Research Context | 5 | 0 | 0 | 0 | Service/API plus single-ticker/ETF and topic/sector injection done. |
| Extensibility | 5 | 0 | 1 | 0 | Provider adapters and hooks exist; ECOS runtime data requires key/config. |
| Tests | 11 | 0 | 0 | 1 | Full pytest passed; broader Macro/research/topic ruff passed; npm build N/A. |
| Acceptance Criteria | 19 | 0 | 0 | 0 | Core Macro MVP acceptance met with live UI/API smoke. |

Known limitations:

- Live AI/LLM Macro Brief generation is enabled as a guarded optional path. The latest live Ollama smoke was rejected by the numeric grounding guard because the model introduced an ungrounded `4.5%`; fallback was returned.
- Macro context is injected into the single-ticker/ETF research pipeline and topic/sector pipeline when macro context is relevant.
- ECOS/OECD/WorldBank/Yahoo provider adapters are implemented. ECOS live data is unavailable until `ECOS_API_KEY` and verified ECOS item-code policy are configured. OECD and World Bank remain disabled in default dashboards but can be fetched directly through the provider contract.
- The factor classifier is an auditable prototype-distance classifier, not a trained ML model.
- First live FRED cache miss can be slower than cached UI loads; service TTL cache reduces repeated fetches.
- `npm run build` was not run because this repo surface has no npm build script.

Changed files for Macro implementation:

- `app/api/server.py`
- `app/api/routers/macro.py`
- `app/web/index.html`
- `app/web/app.js`
- `app/web/styles.css`
- `core/schemas/macro.py`
- `pipelines/macro/__init__.py`
- `pipelines/macro/series_registry.py`
- `pipelines/macro/providers/__init__.py`
- `pipelines/macro/providers/base.py`
- `pipelines/macro/providers/ecos.py`
- `pipelines/macro/providers/storage.py`
- `pipelines/macro/providers/fred.py`
- `pipelines/macro/providers/oecd.py`
- `pipelines/macro/providers/unavailable.py`
- `pipelines/macro/providers/worldbank.py`
- `pipelines/macro/providers/yahoo.py`
- `pipelines/macro/transforms.py`
- `pipelines/macro/data_quality.py`
- `pipelines/macro/macro_service.py`
- `pipelines/macro/regime_engine.py`
- `pipelines/macro/asset_impact.py`
- `pipelines/macro/portfolio_hints.py`
- `pipelines/macro/research_context.py`
- `pipelines/macro/prompts.py`
- `pipelines/macro/ai_brief.py`
- `pipelines/orchestration/research_pipeline.py`
- `pipelines/orchestration/topic_pipeline.py`
- `scripts/check_ui_contract.py`
- `tests/test_api_router_split.py`
- `tests/test_ui_routing_contract.py`
- `tests/test_macro_platform.py`
- `tests/test_topic_pipeline.py`
- `docs/MACRO_IMPLEMENTATION_CHECKLIST.md`

Out-of-scope worktree note:

- `pipelines/strategies/generator.py`, `tests/test_quant_lab_api.py`, and untracked `tests/test_strategy_generator.py` are present in the working tree but are not part of this Macro implementation scope.

## 12. Macro Data Auto Refresh Extension

Status values below follow the same `DONE` / `PARTIAL` / `BLOCKED` / `NOT_DONE` convention.

| ID | Task | Target Files | Status | Evidence |
|---|---|---|---|---|
| M10-1 | Refresh every active Macro-tab series from the Macro registry, not only the legacy 6-series FRED list. | `pipelines/data_mart/jobs/update_macro_daily.py` | DONE | `update_macro_platform_data()` stores all selected active FRED and Yahoo proxy series under UI-facing series ids. |
| M10-2 | Preserve explicit unavailable states for providers that require keys or are disabled. | `pipelines/data_mart/jobs/update_macro_daily.py`, `pipelines/macro/providers/*` | DONE | ECOS remains unavailable without `ECOS_API_KEY`; disabled providers are not silently fabricated. |
| M10-3 | Add a manual Macro refresh API. | `app/api/routers/macro.py`, `core/schemas/macro.py` | DONE | `POST /api/v1/macro/refresh` returns run id, provider statuses, stored rows, and refreshed data quality. |
| M10-4 | Add Macro auto refresh to the existing in-process data mart scheduler. | `core/config/settings.py`, `pipelines/data_mart/scheduler.py` | DONE | Scheduler status now lists `macro_platform_data` and runs SEC plus Macro jobs without blocking startup. |
| M10-5 | Make the Macro tab refresh button update provider data instead of only reloading cached UI data. | `app/web/app.js`, `scripts/check_ui_contract.py`, `tests/test_ui_routing_contract.py` | DONE | `refreshMacroData()` calls the refresh API, clears stale UI state, reloads Macro panels, and shows auto-refresh status. |
| M10-6 | Repair Korean Macro brief/report output so the tab does not surface mojibake. | `pipelines/macro/prompts.py`, `pipelines/macro/ai_brief.py`, `pipelines/macro/macro_service.py`, `tests/test_macro_platform.py` | DONE | Fallback brief, prompts, warnings, and exported report now use Korean text with language-guard tests. |
| M10-7 | Keep CLI daily update behavior aligned with the Macro tab. | `scripts/daily_update.py` | DONE | `--skip-macro` still works; the default Macro job now calls `update_macro_platform_data()`. |

Operational notes:

- `DATA_MART_AUTO_REFRESH_ENABLED=false` disables the in-process scheduler.
- `DATA_MART_AUTO_REFRESH_MACRO_ENABLED=false` disables only the Macro data job.
- `DATA_MART_AUTO_REFRESH_MACRO_LOOKBACK_DAYS` controls the historical window used when the scheduler refreshes Macro data.
- FRED uses the configured API key when available. The Macro refresh job also supports a conservative public FRED CSV fallback when no key is configured, while the interactive Macro provider path still reports missing FRED credentials instead of fabricating observations.
- The scheduler is process-local. It refreshes while the FastAPI app is running; external OS/CI scheduling can still call `scripts/daily_update.py` if a detached job is required.

## 13. Macro Platform Advancement

This section tracks the dashboard/provider-health/scenario expansion for the static `/ui/#macro` workbench.

| ID | Task | Target Files | Status | Evidence |
|---|---|---|---|---|
| M13-1 | Add a dashboard-first Macro API that returns registry coverage, latest observations, heatmap/summary inputs, quality state, and advisory metadata. | `app/api/routers/macro.py`, `core/schemas/macro.py`, `pipelines/macro/dashboard.py` | DONE | `GET /api/v1/macro/dashboard` is covered by `tests/test_macro_platform.py`. |
| M13-2 | Expose provider and scheduler health without hiding unavailable or unconfigured providers. | `app/api/routers/macro.py`, `pipelines/macro/provider_health.py` | DONE | `GET /api/v1/macro/provider-health` returns provider, enabled/configured flags, latest status, row counts, and errors. |
| M13-3 | Add deterministic advisory-only scenario analysis. | `app/api/routers/macro.py`, `core/schemas/macro.py`, `pipelines/macro/scenario.py` | DONE | `POST /api/v1/macro/scenario` returns asset impacts, sleeve hints, data quality, explanation, and `advisory_only=true`; no orders or policy mutation are exposed. |
| M13-4 | Convert the Macro tab to progressive dashboard loading with independent panel failures. | `app/web/index.html`, `app/web/app.js`, `app/web/styles.css` | DONE | Dashboard, provider health, filters, compare shell, scenario starter, and research preview render as separate surfaces. |
| M13-5 | Keep static UI contracts and routing tests aligned with the new Macro DOM/API markers. | `scripts/check_ui_contract.py`, `tests/test_ui_routing_contract.py` | DONE | Contract checks include Macro dashboard/provider/scenario/research markers only within Macro scope. |
| M13-6 | Add repeatable browser smoke for desktop and mobile Macro tab validation. | `scripts/macro_ui_smoke.py` | DONE | Script starts a disposable FastAPI server when no URL is provided, verifies progressive surfaces, search, advisory scenario, research preview, console errors, and mojibake tokens. |
| M13-7 | Make Macro freshness evidence cover every enabled registry series. | `pipelines/macro/macro_service.py`, `pipelines/macro/dashboard.py`, `pipelines/macro/series_registry.py`, `app/web/app.js` | DONE | `/api/v1/macro/data-quality` defaults to full-registry validation, dashboard coverage uses the same aggregate quality, and `BUSLOANS`/`CSUSHPISA` release-lag thresholds are aligned with provider output. |

Recommended validation gate:

- `python -m pytest tests\test_macro_platform.py tests\test_ui_routing_contract.py -q`
- `node --check app\web\app.js`
- `python scripts\check_ui_contract.py --output reports\macro_ui_contract.json`
- `python -m ruff check core/schemas/macro.py app/api/routers/macro.py pipelines/macro/dashboard.py pipelines/macro/provider_health.py pipelines/macro/scenario.py tests/test_macro_platform.py scripts/macro_ui_smoke.py`
- `python scripts\macro_ui_smoke.py --width 1440 --height 1200 --timeout-s 120`
- `python scripts\macro_ui_smoke.py --width 390 --height 844 --timeout-s 120`

Remaining extension backlog:

- Multi-series chart overlays and correlation/regime-aware comparisons in `macroCompareSurface`.
- Provider drill-down history from stored update runs rather than latest status only.
- Custom user-entered shock scenarios after the preset API path has accumulated enough smoke evidence.
