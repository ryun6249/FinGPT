# Continuous Enhancement Log

## Current Project Summary
- Project purpose: Local financial research workstation that combines market data, macro data, quant/backtest workflows, Quantamental analysis, ML Forecast, AI Portfolio, and local LLM briefing surfaces.
- Main frontend structure: Static FastAPI-served UI under `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`, plus domain modules under `app/web/modules/`.
- Main backend structure: FastAPI routers under `app/api/routers/`, shared request/response contracts under `core/schemas/`, and orchestration/services under `pipelines/`.
- Data flow: UI calls `/api/v1/*` routes; routers delegate to pipeline services; data-mart, macro, price, portfolio, forecast, and quantamental services normalize provider/cache output before rendering.
- AI/LLM flow: Primary research requests route through configured inference aliases such as `qwen`; experimental Gemma routes are exposed only from config when supported. Quantamental AI interprets deterministic engine payloads and must preserve deterministic scores/signals.
- Visualization flow: The static UI renders HTML/SVG/table surfaces, internal price charts, TradingView fallback/option widgets, heatmaps, Quant Lab charts, Forecast charts, Quantamental factor/score visualizations, and AI Portfolio dashboard surfaces.
- Testing flow: Python/pytest contract tests validate static UI markers, API contracts, quantamental behavior, and smoke scripts; browser smoke scripts cover the static `/ui/` surface when a local server is running.

## Current Problems
- Compatibility: The worktree already contains many unrelated pending changes, so this run must avoid broad rewrites and preserve existing static UI/API contracts.
- Data consistency: Period controls exist in several feature panels, but there is no single dashboard-level range selector that synchronizes the main KPI/chart/table/briefing inputs.
- UI consistency: `Core / Diagnostics / Operations / All` exists, but non-market tabs can still default to narrower persisted views, hiding important surfaces on first entry.
- Visualization: Chart/data surfaces expose range and freshness details unevenly; titles and status text are not always tied to the selected global period.
- AI briefing: Quantamental AI already has deterministic-signal guardrails, but the briefing context does not consistently carry a user-readable data snapshot summary.
- Data freshness: Detailed diagnostics exist, but a concise top-right quality summary is not always visible without opening the deeper quality panel.
- Translation quality: Korean/English UI output exists and should keep financial terms, tickers, dates, numbers, and units stable.
- Performance: Several dashboards can refetch independently; this run should keep global range updates explicit and avoid hidden background loops.
- Code structure: Existing static UI is large and stateful; improvements should add small adapter-style helpers instead of moving major surfaces.
- User experience: First-time dashboard entry should show all relevant sections, plus a simple quality/range context that reduces navigation friction.

## Enhancement Plan
- Priority 1: Make `All` the default dashboard panel view for all dashboard tabs while preserving Core/Diagnostics/Operations as filters.
- Priority 2: Add a top-right quality summary and dashboard-level range selector, then synchronize existing tab controls from the selected period where safely supported.
- Priority 3: Add Quantamental AI briefing data-snapshot guardrails and document verified model availability truthfully without fake Gemma/Qwen status.

## Validation Plan
- Build: No frontend package manifest is present in the repo root; validate with Python contract tests and import/runtime smoke instead of `npm run build`.
- Lint: No repo-level JS lint command is configured; use targeted static contract tests and UI contract script.
- Unit test: Run targeted pytest for UI routing/static contracts and Quantamental AI API behavior.
- Integration test: Run Quantamental API tests and local FastAPI UI smoke where available.
- UI test: Start the supported local web launcher and verify `/ui/` through the available browser/smoke tooling.
- Data quality test: Check that the quality summary renders from data-health, macro quality, and Quantamental quality payloads without exposing raw diagnostic failures.
- AI hallucination guard test: Verify Quantamental AI fallback/report includes source period, basis date/source, observation count or `Unavailable`/`확인 불가`, and preserves deterministic signal labels.

## Completion Checklist

### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

### AI Briefing
- [x] Gemma/Qwen availability is checked
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가
- [x] Translation preserves numbers/dates/units

### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| Python syntax | `python -m py_compile pipelines/quantamental/ai_service.py app/api/routers/system.py` | Passed | Used `venv311` when available. |
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax only. |
| Static UI/API tests | `pytest tests/test_ui_routing_contract.py tests/test_quantamental_api.py -q` | Passed | `59 passed, 4 subtests passed`. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New global quality/range markers included. |
| Browser smoke | `python scripts/ai_portfolio_ui_smoke.py --timeout-s 120 --output reports/ai_portfolio_ui_smoke_continuous_20260519.json` | Passed | Versioned scripts, dashboard tab matrix, Quantamental language/top-5/score smoke, no console errors. |
| Live browser DOM | Playwright MCP at `http://host.docker.internal:8351/ui/?range=1Y#quantamental` | Passed | Quantamental tab rendered with `panelView=all`, global range visible, no horizontal overflow. |
| Mobile DOM | Playwright MCP resized to `390x900` | Passed | Top quality summary and range controls fit without horizontal overflow. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no `package.json`/`pnpm-lock.yaml`; this static UI is served by FastAPI and validated through Python/Playwright smoke. |

## 2026-05-19 Continuous Enhancement Run

- Branch: `automation/continuous-enhancement-20260519-0402`.
- Scope: preserved the current app structure and added only incremental dashboard/global-control and Quantamental AI-guardrail improvements.
- All default: dashboard panel defaults now reset to `All` for all tabs via a layout version key while keeping Core/Diagnostics/Operations filters.
- Quality summary: top-right `globalQualitySummary` shows status, 기준일, update time, and selected period; detailed source/observation/missing/AI snapshot fields are available in the tooltip and refreshed from data health, macro quality, market overview, and Quantamental analysis.
- Period selection: `dashboardRangeSelect` supports `1D`, `1W`, `1M`, `3M`, `6M`, `YTD`, `1Y`, `3Y`, `5Y`, `MAX`, and `custom`, writes URL query state, and synchronizes existing research, asset detail, backtest, portfolio, forecast, cross-asset, AI Portfolio, and Quantamental controls where those surfaces support the range.
- AI briefing: Quantamental AI context now includes `used_data`/`data_snapshot`; deterministic fallback and LLM outputs are forced to include used data, key changes, interpretation, scenarios, user actions, guardrails, and unavailable-value handling.
- Model selection: `/api/v1/config` now marks Qwen/Gemma routes as runtime-checked instead of implying local model availability without request-time verification.

## 2026-05-19 Continuous Enhancement Run 05:02

- Branch: `automation/continuous-enhancement-20260519-0502`.
- Current status: the previous run already added All-default panel behavior, a global range selector, and Quantamental AI used-data guardrails. This run kept that architecture intact and narrowed scope to the top-right quality summary UX.
- Problem found: the quality summary carried observation count, missing-data status, and AI snapshot time in tooltip/detail text, but the always-visible top-right badge only showed status, basis date, update time, and period.
- Change: the `globalQualitySummary` badge now directly renders `관측치`, `결측`, and `AI 기준` alongside quality status, 기준일, 업데이트, and 기간. Missing counts are normalized to user-readable labels such as `없음`, `있음`, or `n개`; long timestamps are compacted to avoid layout overflow.
- UI resilience: the badge now wraps predictably on desktop and 390px mobile, keeps an accessible Korean `aria-label`, and preserves the click-through quality panel behavior.
- Contract coverage: static UI contract checks now require the observation, missing-data, and AI-snapshot markers so future regressions do not hide these fields again.

### 05:02 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax. |
| Python syntax | `python -m py_compile scripts/check_ui_contract.py` | Passed | Contract script remains importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New quality summary markers included. |
| UI routing tests | `python -m pytest tests/test_ui_routing_contract.py -q` | Passed | `39 passed, 4 subtests passed`. |
| UI module tests | `python -m pytest tests/test_ui_modules.py -q` | Passed | `2 passed`. |
| AI briefing guard regression | `python -m pytest tests/test_quantamental_api.py -q` | Passed | `20 passed`; used-data guard contract preserved. |
| Diff hygiene | `git diff --check -- app/web/index.html app/web/app.js app/web/styles.css tests/test_ui_routing_contract.py scripts/check_ui_contract.py` | Passed | No whitespace errors in touched files. |
| Live desktop UI | `playwright-cli` at `http://127.0.0.1:8352/ui/?range=1Y#quantamental` | Passed | Quality badge exposes all seven fields in the accessibility snapshot. |
| Live mobile UI | `playwright-cli resize 390 900` + DOM check | Passed | `horizontalOverflow=false`, `panelView=all`, quality fields remain visible. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no frontend package manifest; static UI is validated through Python contracts and Playwright. |

## 2026-05-19 Continuous Enhancement Run 06:02

- Branch: `automation/continuous-enhancement-20260519-0602`.
- Current status: the prior automation PRs already cover All-default selection, the top-right quality summary, global range state, and Quantamental AI used-data guardrails. This run kept those contracts intact and focused on two practical UX gaps: custom range safety and All-view category clarity.
- Compatibility: no API contract, schema, strategy entry/exit, trading/order, secret, or environment-file behavior was changed. The existing Core/Diagnostics/Operations/All filter remains unchanged, with All still the default.
- Data consistency: custom dashboard ranges now normalize reversed start/end dates before they propagate into KPI, chart, table, and AI briefing controls. Incomplete custom ranges show a user-readable warning instead of silently looking like a valid exact date range.
- UI/UX: All view now gives cards a lightweight Core, Diagnostics, or Operations label derived from their existing `data-panel-tier`, so the full view is easier to scan without hiding any surface.
- Mobile: desktop and 390px browser checks showed no horizontal overflow after the new range warning and tier labels.
- AI briefing: no AI prompt/model behavior was changed in this slice; existing Quantamental deterministic-signal preservation and not-investment-advice checks were re-verified through API and UI smoke tests.

### 06:02 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax. |
| Python syntax | `python -m py_compile scripts/check_ui_contract.py` | Passed | Contract script remains importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New custom-range and All-view markers included. |
| UI routing tests | `python -m pytest tests/test_ui_routing_contract.py -q` | Passed | `39 passed, 4 subtests passed`. |
| UI module tests | `python -m pytest tests/test_ui_modules.py -q` | Passed | `2 passed`. |
| AI briefing guard regression | `python -m pytest tests/test_quantamental_api.py -q` | Passed | `20 passed`; deterministic AI guard contract preserved. |
| Diff hygiene | `git diff --check -- app/web/app.js app/web/styles.css scripts/check_ui_contract.py tests/test_ui_routing_contract.py` | Passed | No whitespace errors in touched files. |
| Live desktop UI | Playwright MCP at `http://127.0.0.1:8362/ui/?range=1Y#quantamental` | Passed | `panelView=all`; visible Quantamental cards show Core/Diagnostics/Operations labels. |
| Custom range UI | Playwright MCP DOM interaction | Passed | Reversed `2026-05-19` to `2026-01-01` input normalized to `2026-01-01~2026-05-19` and URL state was corrected. |
| Live mobile UI | Playwright MCP resized to `390x900` | Passed | `horizontalOverflow=false`; quality summary and custom range warning remained visible. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8362 --timeout-s 120 --output reports/ai_portfolio_ui_smoke_continuous_20260519_0602.json` | Passed | No console errors; dashboard tab surface matrix and Quantamental language/top-5/score smoke passed. |
| Quantamental browser smoke | `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8362 --output reports/quantamental_ui_smoke_continuous_20260519_0602.json` | Passed | Required tickers, invalid ticker, GLOBAL resolver, Top 5, threshold screener, overview axes, comparison, Q&A, and audit smoke passed. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no frontend package manifest; static UI is validated through Python contracts and Playwright. |

### 06:02 Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 09:20 Final

- Branch: `automation/continuous-enhancement-20260519-0920`.
- Current project summary: the project remains a FastAPI-served local financial research workstation with static `app/web` UI, Python API routers/services, deterministic Quantamental engines, runtime-checked local LLM routes, and Python/Playwright validation.
- Scope selected: previous runs already completed All-default filtering, top-right quality summaries, global range controls, range-support copy, and Quantamental AI used-data sections. This slice focused on truthful model selection for Quantamental AI report/Q&A.
- Compatibility: no API contract was broken; `/api/v1/config` only adds a `model` field to each UI model option while preserving existing `id`, `label`, `role`, `enabled`, `availability`, and `availability_note`.
- UI/UX: Quantamental analysis report now has an `AI 모델` selector. The default remains `Deterministic guardrail`; Qwen/Gemma options are populated from `/api/v1/config` and labeled as runtime-checked.
- AI briefing: explicit AI report/Q&A refreshes now send `use_llm=true` and the concrete configured model only when the user selects a runtime-checked model. Initial Quantamental analysis still uses deterministic interpretation by default.
- Translation: Korean status text explains that Qwen/Gemma are checked at execution time and deterministic fallback remains active if the provider fails.
- Performance: no background LLM call or polling was added; LLM use remains explicit user action only.
- Cache safety: `styles.css` and `app.js` bundle query versions were bumped to `20260519-continuous-enhancement-v3`.

### 09:20 Final Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static UI controller syntax. |
| Python syntax | `python -m py_compile app/api/routers/system.py scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | API router and smoke scripts importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New Quantamental AI model markers and JS markers included. |
| API/UI targeted tests | `python -m pytest tests/test_ui_routing_contract.py tests/test_api_routing_contract.py -q` | Passed | `52 passed, 4 subtests passed`. |
| Quantamental AI guard tests | `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_ui_ai_panel.py tests/test_ui_modules.py -q` | Passed | `23 passed`; used-data and advisory guardrails preserved. |
| Full test suite | `python -m pytest -q` | Passed | `691 passed, 9 subtests passed in 140.47s`. |
| Diff hygiene | `git diff --check -- ...` | Passed | No whitespace errors in touched files. |
| Live server | `scripts/run_web.ps1` on `http://127.0.0.1:8395` | Passed | `/api/v1/health` and `/ui/?range=1Y#quantamental` returned 200. |
| Quantamental browser smoke | `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8395 --output reports/quantamental_ui_smoke_continuous_20260519_0920.json` | Passed | Required tickers, invalid ticker, GLOBAL resolver, Top 5, score screen, overview axes, comparison, Q&A, and audit smoke passed. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8395 --timeout-s 180 --output reports/ai_portfolio_ui_smoke_continuous_20260519_0920_retry.json` | Passed on retry | First parallel run timed out on Macro series search; standalone retry passed with no console errors. |
| Model selector DOM | Playwright inline DOM check | Passed | Deterministic, Qwen, and Gemma runtime-checked options visible; no desktop/mobile horizontal overflow. |
| Model request payload | Playwright intercepted AI report POST | Passed | Selecting Qwen sent `use_llm=true`, `model=qwen2.5:7b`, `output_language=ko`. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no `package.json`/`pnpm-lock.yaml`; static UI is validated through Python/Playwright. |

### 09:20 Final Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period where supported
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked as runtime-checked config, not claimed as preinstalled
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가 or unavailable
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

### 09:20 Implementation Results

- Branch: `automation/continuous-enhancement-20260519-0920`.
- Scope selected: previous runs already completed All-default filtering, top-right quality summaries, global range controls, range-support copy, and Quantamental AI used-data sections. This slice focused on truthful model selection for Quantamental AI report/Q&A.
- Compatibility: no API contract was broken; `/api/v1/config` only adds a `model` field to each UI model option while preserving existing `id`, `label`, `role`, `enabled`, `availability`, and `availability_note`.
- UI/UX: Quantamental analysis report now has an `AI 모델` selector. The default remains `Deterministic guardrail`; Qwen/Gemma options are populated from `/api/v1/config` and labeled as runtime-checked.
- AI briefing: explicit AI report/Q&A refreshes now send `use_llm=true` and the concrete configured model only when the user selects a runtime-checked model. Initial Quantamental analysis still uses deterministic interpretation by default.
- Translation: Korean status text explains that Qwen/Gemma are checked at execution time and deterministic fallback remains active if the provider fails.
- Performance: no background LLM call or polling was added; LLM use remains explicit user action only.
- Cache safety: `styles.css` and `app.js` bundle query versions were bumped to `20260519-continuous-enhancement-v3`.

### 09:20 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static UI controller syntax. |
| Python syntax | `python -m py_compile app/api/routers/system.py scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | API router and smoke scripts importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New Quantamental AI model markers and JS markers included. |
| API/UI targeted tests | `python -m pytest tests/test_ui_routing_contract.py tests/test_api_routing_contract.py -q` | Passed | `52 passed, 4 subtests passed`. |
| Quantamental AI guard tests | `python -m pytest tests/test_quantamental_api.py tests/test_quantamental_ui_ai_panel.py tests/test_ui_modules.py -q` | Passed | `23 passed`; used-data and advisory guardrails preserved. |
| Full test suite | `python -m pytest -q` | Passed | `691 passed, 9 subtests passed in 140.47s`. |
| Diff hygiene | `git diff --check -- ...` | Passed | No whitespace errors in touched files. |
| Live server | `scripts/run_web.ps1` on `http://127.0.0.1:8395` | Passed | `/api/v1/health` and `/ui/?range=1Y#quantamental` returned 200. |
| Quantamental browser smoke | `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8395 --output reports/quantamental_ui_smoke_continuous_20260519_0920.json` | Passed | Required tickers, invalid ticker, GLOBAL resolver, Top 5, score screen, overview axes, comparison, Q&A, and audit smoke passed. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8395 --timeout-s 180 --output reports/ai_portfolio_ui_smoke_continuous_20260519_0920_retry.json` | Passed on retry | First parallel run timed out on Macro series search; standalone retry passed with no console errors. |
| Model selector DOM | Playwright inline DOM check | Passed | Deterministic, Qwen, and Gemma runtime-checked options visible; no desktop/mobile horizontal overflow. |
| Model request payload | Playwright intercepted AI report POST | Passed | Selecting Qwen sent `use_llm=true`, `model=qwen2.5:7b`, `output_language=ko`. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no `package.json`/`pnpm-lock.yaml`; static UI is validated through Python/Playwright. |

### 09:20 Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period where supported
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked as runtime-checked config, not claimed as preinstalled
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가 or unavailable
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 09:20

## Current Project Summary
- Project purpose: FastAPI-served local financial research workstation for market, macro, Quant Lab, Quantamental, ML Forecast, AI Portfolio, and grounded AI briefing workflows.
- Main frontend structure: Static UI in `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`, plus domain renderers in `app/web/modules/`.
- Main backend structure: FastAPI routers under `app/api/routers/`, shared schemas under `core/schemas/`, and services/pipelines under `pipelines/`.
- Data flow: UI controls call `/api/v1/*`; routers delegate to deterministic services and data stores; UI renders quality/range context from returned payloads.
- AI/LLM flow: Qwen is the primary configured route; Gemma-family routes are experimental/runtime-checked. Quantamental AI must interpret deterministic engine output and preserve scores/signals.
- Visualization flow: Static HTML/SVG/table components render charts and status surfaces; global range state is mapped to exact-date or lookback-bucket surfaces.
- Testing flow: Python contract tests, Node syntax checks, FastAPI API tests, and browser smoke scripts validate the static UI and API behavior.

## Current Problems
- Compatibility: The branch already contains prior automation commits and unrelated dirty workspace files, so this run must avoid broad rewrites.
- Data consistency: Global range and quality summaries exist; this run does not change data calculations.
- UI consistency: Quantamental AI exposed used-data evidence, but the UI still hardcoded deterministic AI calls even though backend request models already support `model` and `use_llm`.
- Visualization: No chart renderer gap selected for this slice.
- AI briefing: Qwen/Gemma availability was documented in config, but Quantamental AI report/Q&A controls did not let the user intentionally choose a runtime-checked model.
- Data freshness: Existing top-right quality badge and detail panel remain the source of truth.
- Translation quality: New UI copy must keep Korean/English concise and avoid changing ticker/date/number values.
- Performance: Model selection must not add background LLM calls; non-deterministic models should run only on explicit AI report/Q&A actions.
- Code structure: Keep model routing as a small adapter around existing `/api/v1/config` and Quantamental AI request paths.
- User experience: The selector must clearly say that Qwen/Gemma availability is checked at request time and deterministic fallback remains active.

## Enhancement Plan
- Priority 1: Add explicit runtime-checked model metadata (`model`) to `/api/v1/config` so UI does not infer model names from labels.
- Priority 2: Add a Quantamental AI model selector with deterministic default, Qwen/Gemma options from config, and user-readable fallback status.
- Priority 3: Wire selected model only into explicit AI report/Q&A requests, preserving deterministic initial analysis and existing guardrails.

## Validation Plan
- Build: Run JS/Python syntax checks; no npm/pnpm package build exists in repo root.
- Lint: Use existing UI contract and diff hygiene checks because no JS linter is configured.
- Unit test: Run targeted API/UI contract tests.
- Integration test: Run Quantamental API guard regression.
- UI test: Start the local FastAPI UI and verify the selector/status in desktop/mobile DOM if the server starts cleanly.
- Data quality test: Verify top-right quality/range contracts remain present.
- AI hallucination guard test: Verify Quantamental AI report tests still preserve used-data and deterministic guardrails.

## 2026-05-19 Continuous Enhancement Run 09:02

- Branch: `automation/continuous-enhancement-20260519-0902`.
- Current status: previous automation slices already added All-default dashboard views, the top-right quality summary, global range controls, range support copy, and Quantamental backend AI used-data guardrails. This run kept those contracts intact and focused on making the AI briefing evidence visible in the UI.
- Compatibility: no API schema, strategy entry/exit logic, trading/order execution, environment files, or secrets were changed.
- Data consistency: when the global range changes and a reload starts, the top-right quality badge now clears stale observations and shows a user-readable pending state (`갱신 중`, `확인 중`, `재계산 대기`) until fresh tab data replaces it.
- UI/UX: the Quantamental AI tab now renders a dedicated `사용 데이터` / `Used Data` block with data basis date, analysis period, source, observation count, missing-data state, model, AI snapshot time, and cache state.
- AI briefing: the Quantamental AI tab now exposes the structured guardrail sections already produced by the backend: key changes, interpretation, scenarios, and user actions. The UI still treats AI as interpretation over deterministic engine output only.
- Translation: Korean and English labels for the new AI data/guardrail sections were added in the Quantamental UI module and verified for UTF-8/mojibake safety.
- Performance: no new network request was added; the AI tab renders from the existing `ai_report` payload, and the range pending state is a local UI state transition.

### 09:02 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax. |
| JS module syntax | `node --check app/web/modules/quantamental-ui.js` | Passed | Quantamental UI module syntax. |
| Python syntax | `python -m py_compile scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | Contract and smoke scripts remain importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New bundle and quality pending markers included; no mojibake/placeholder lines. |
| UI routing tests | `python -m pytest tests/test_ui_routing_contract.py -q` | Passed | `39 passed, 4 subtests passed`. |
| Quantamental AI UI module test | `python -m pytest tests/test_quantamental_ui_ai_panel.py -q` | Passed | AI used-data and guardrail sections render in English and Korean. |
| UI module tests | `python -m pytest tests/test_ui_modules.py -q` | Passed | `2 passed`; existing dirty file was not staged by this run. |
| AI briefing guard regression | `python -m pytest tests/test_quantamental_api.py -q` | Passed | `20 passed`; backend used-data and advisory guardrails preserved. |
| Diff hygiene | `git diff --check -- app/web/app.js app/web/index.html app/web/modules/quantamental-ui.js scripts/ai_portfolio_ui_smoke.py scripts/check_ui_contract.py tests/test_ui_routing_contract.py tests/test_quantamental_ui_ai_panel.py` | Passed | No whitespace errors in files selected for this run. |
| Live desktop UI | Playwright MCP at `http://host.docker.internal:8392/ui/?range=1Y#quantamental` | Passed | Quantamental active, `panelView=all`, v12 module loaded, no horizontal overflow. |
| AI tab DOM fixture | Playwright MCP module render fixture | Passed | `quantamental-ai-used-data`, key changes, and user actions appeared with Korean copy. |
| Quality pending DOM | Playwright MCP direct pending-state check | Passed | Top-right quality badge showed `업데이트: 갱신 중`, `결측: 확인 중`, `AI 기준: 재계산 대기`. |
| Mobile DOM | Playwright MCP resized to `390x900` | Passed | `horizontalOverflow=false`, quality badge and AI used-data marker remained visible. |
| Quantamental browser smoke | `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8392 --output reports/quantamental_ui_smoke_continuous_20260519_0902.json` | Passed | Required tickers, invalid ticker, GLOBAL resolver, Top 5, score screen, overview axes, comparison, Q&A, and audit smoke passed. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8392 --timeout-s 150 --output reports/ai_portfolio_ui_smoke_continuous_20260519_0902_retry.json` | Passed | First parallel run timed out on Macro search while Quantamental smoke was also running; direct API check passed and the standalone retry passed with no console errors. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no frontend package manifest; static UI is validated through Python contracts and browser smoke. |

### 09:02 Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 08:04

- Branch: `automation/continuous-enhancement-20260519-0804`.
- Current project summary: the project remains a FastAPI-served local financial research workstation with static UI, Python API routers/services, deterministic Quantamental engines, data-quality summaries, and local LLM interpretation guards.
- Scope selected: prior automation PRs already added All-default filtering, top-right quality badges, range controls, and quality-panel context. This run focused on data-period truthfulness so users do not assume every tab receives the exact same date range when some surfaces only support lookback buckets.
- Compatibility: no API response schema, data provider, model route, trading/order logic, strategy entry/exit condition, secret, or environment-file behavior was changed.
- Data consistency: the global range helper now exposes a user-readable support summary showing date-supported surfaces, capped Research lookback, and the Quantamental bucket used for the selected period.
- UI/UX: the dashboard range note and quality panel now say that date-supported screens receive the selected dates directly while lookback-based screens are mapped to supported buckets.
- Visualization: no chart renderer or calculation logic changed in this slice; the selected range explanation was verified against the Quantamental UI surface and existing chart/overview smoke.
- AI briefing: no prompt/model behavior changed; existing Quantamental AI used-data and deterministic-output guard contracts were re-run.
- Translation: Korean copy was kept concise and verified through the UTF-8 UI contract script with no mojibake or placeholder lines.
- Performance: the new range-support summary is derived from existing client state and does not add network requests, timers, or background refresh loops.

### 08:04 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax. |
| Python syntax | `python -m py_compile scripts/check_ui_contract.py` | Passed | Contract script remains importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New range-support markers included; no mojibake or placeholder lines. |
| UI routing tests | `python -m pytest tests/test_ui_routing_contract.py -q` | Passed | `39 passed, 4 subtests passed`. |
| UI module tests | `python -m pytest tests/test_ui_modules.py -q` | Passed | `2 passed`. |
| AI briefing guard regression | `python -m pytest tests/test_quantamental_api.py -q` | Passed | `20 passed`; deterministic AI guard contract preserved. |
| Diff hygiene | `git diff --check -- app/web/index.html app/web/app.js app/web/styles.css scripts/check_ui_contract.py tests/test_ui_routing_contract.py docs/CONTINUOUS_ENHANCEMENT_LOG.md` | Passed | No whitespace errors in touched files. |
| Live desktop UI | Playwright CLI at `http://127.0.0.1:8382/ui/?range=1Y#quantamental` | Passed | `panelView=all`; dashboard support note and quality panel range-support detail visible. |
| Live mobile UI | Playwright CLI resized to `390x900` | Passed | `horizontalOverflow=false`; support note and range-support detail fit within viewport. |
| Quantamental browser smoke | `python scripts/quantamental_ui_smoke.py --base-url http://127.0.0.1:8382 --output reports/quantamental_ui_smoke_continuous_20260519_0804.json` | Passed | Required tickers, invalid ticker, GLOBAL resolver, Top 5, threshold screener, overview axes, comparison, Q&A, and audit smoke passed. |
| Quantamental API data/AI smoke | `GET /api/v1/quantamental/analysis/AAPL?...include_ai=true&use_llm=false` | Passed | Wrote `reports/quantamental_api_continuous_20260519_0804.json`; AI report remains data-snapshot based. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no frontend package manifest; static UI is validated through Python contracts and Playwright. |

### 08:04 Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period where exact date support exists
- [x] Lookback-only surfaces now disclose bucket conversion
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked by existing runtime-checked config path
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 07:02

- Branch: `automation/continuous-enhancement-20260519-0702`.
- Current project summary: the repo remains a FastAPI-served local financial research workstation with a static `app/web` shell, Python API routers/services, data-mart backed market/macro/quantamental flows, local LLM routing, and Python/Playwright validation rather than a package-managed frontend build.
- Scope selected: the previous automation PRs already added All-default dashboard filtering, global period controls, top-right quality badges, and Quantamental AI used-data guardrails. This run kept those contracts intact and improved the click-through quality panel so users can understand the top-right badge without reading internal diagnostics.
- Compatibility: no API response schema, trading/order logic, strategy entry/exit condition, data provider, model route, secret, or environment file behavior was changed.
- Data consistency: the quality panel now mirrors the same global quality context as the top-right badge: data source, selected range, basis date, last update, observation count, missing-data state, cache state, and AI analysis basis time.
- UI/UX: added a responsive `qualityContextSummary` block at the top of the quality dashboard, using concise user-facing Korean labels instead of raw diagnostic exceptions.
- Visualization: no chart math or chart renderer changed in this slice; existing chart/range behavior was re-verified through UI contract and browser smoke.
- AI briefing: no prompt/model logic changed; existing Quantamental used-data and hallucination guard contracts were re-run.
- Translation: Korean labels were added directly in the static UI and verified through the UTF-8 contract script with no mojibake/placeholder failures.
- Performance: the new detail block is rendered from already-held client state and does not add extra network requests or background polling.

### 07:02 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js` | Passed | Static JavaScript syntax. |
| Python syntax | `python -m py_compile scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | Contract and smoke scripts remain importable. |
| UI contract | `python scripts/check_ui_contract.py` | Passed | New quality context markers included; no mojibake or placeholder lines. |
| UI routing tests | `python -m pytest tests/test_ui_routing_contract.py -q` | Passed | `39 passed, 4 subtests passed`. |
| UI module tests | `python -m pytest tests/test_ui_modules.py -q` | Passed | `2 passed`. |
| AI briefing guard regression | `python -m pytest tests/test_quantamental_api.py -q` | Passed | `20 passed`; deterministic AI guard contract preserved. |
| Diff hygiene | `git diff --check -- app/web/index.html app/web/app.js app/web/styles.css scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py tests/test_ui_routing_contract.py docs/CONTINUOUS_ENHANCEMENT_LOG.md` | Passed | No whitespace errors in touched files. |
| Live desktop UI | Playwright MCP at `http://host.docker.internal:8372/ui/?range=1Y#quantamental` | Passed | `qualityContextSummary` visible after clicking top quality badge; bundle version v2 loaded. |
| Live mobile UI | Playwright MCP resized to `390x900` | Passed | `horizontalOverflow=false`; quality context uses one-column layout and does not overflow. |
| Browser console | Playwright MCP console check | Passed | No console errors after opening the quality panel. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8372 --timeout-s 120 --output reports/ai_portfolio_ui_smoke_continuous_20260519_0702.json` | Passed | The first run failed on the old v1 bundle selector; after updating the smoke script to v2 it passed with no console errors. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no frontend package manifest; static UI is validated through Python contracts and Playwright. |

### 07:02 Completion Checklist

#### Compatibility
- [x] Existing features still work
- [x] Existing API contracts are not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range selection works
- [x] KPI/chart/table use the same selected period
- [x] Data source and 기준일 are displayed
- [x] Missing data is handled
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh data distinction is clear

#### UI
- [x] Default view is All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font sizes are readable
- [x] Layout spacing is consistent
- [x] Cards/tables/charts are aligned
- [x] Mobile layout is acceptable
- [x] Loading state exists
- [x] Empty state exists
- [x] Error state exists

#### Visualization
- [x] Chart titles are meaningful
- [x] Axis labels are readable
- [x] Tooltips are useful
- [x] Legends are not confusing
- [x] Period selection updates charts
- [x] No chart overflow or label collision

#### AI Briefing
- [x] Gemma/Qwen availability is checked
- [x] Model selection is not fake
- [x] AI output includes used data period
- [x] AI output includes 기준일/source/observation count
- [x] AI does not invent unsupported numbers
- [x] Unverified facts are marked as 확인 불가
- [x] Translation preserves numbers/dates/units

#### Validation
- [x] Lint executed or reason documented
- [x] Build executed or reason documented
- [x] Tests executed or reason documented
- [x] UI validation executed or reason documented
- [x] Data validation executed or reason documented
- [x] AI briefing validation executed or reason documented

#### Documentation
- [x] docs/CONTINUOUS_ENHANCEMENT_LOG.md updated
- [x] README updated if needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 09:20 Closure

- Branch: `automation/continuous-enhancement-20260519-0920`.
- Final scope: added truthful Quantamental AI model selection without changing strategy logic, data providers, schemas, secrets, or default deterministic analysis behavior.
- Final validation: `node --check app/web/app.js`, `python -m py_compile app/api/routers/system.py scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py`, `python scripts/check_ui_contract.py`, targeted UI/API/Quantamental tests, full `python -m pytest -q`, Quantamental browser smoke, AI Portfolio browser smoke retry, and Playwright DOM/payload checks all passed.
- Remaining limit: Qwen/Gemma options are runtime-checked and not claimed as locally installed; provider failure still falls back to deterministic interpretation.

## 2026-05-19 Continuous Enhancement Run 11:03

## Current Project Summary
- Project purpose: Local financial research workstation with FastAPI APIs and a static `/ui/` shell for market, macro, Quant Lab, Quantamental, ML Forecast, AI Portfolio, and local LLM interpretation workflows.
- Main frontend structure: `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`, and small domain modules under `app/web/modules/`.
- Main backend structure: FastAPI app setup in `app/api/server.py`; routers under `app/api/routers/`; shared schemas in `core/schemas/`; services under `pipelines/`.
- Data flow: UI range and tab state call `/api/v1/*` endpoints; Python services normalize provider/cache data before rendering UI cards, charts, tables, and AI briefing sections.
- AI/LLM flow: `/api/v1/config` exposes runtime-checked Qwen/Gemma routes; Quantamental UI keeps deterministic guardrail as default and sends an LLM model only on explicit AI actions.
- Visualization flow: Static UI cards and chart surfaces render from server payloads; global range controls synchronize supported date/range controls.
- Testing flow: Static contract script, Python route tests, UI module fixture tests, syntax checks, and Playwright screenshots are the available lightweight validation path.

## Current Problems
- Compatibility: The previous automation branch is still open, so this run is stacked on top of `automation/continuous-enhancement-20260519-0920` instead of rebasing onto `master`.
- Data consistency: Standard ranges could reuse a stale custom range end date from localStorage or disabled date inputs.
- UI consistency: `/ui/quantamental` client route returned 404 even though the static UI expects client-side routes under `/ui/`.
- Visualization: Dashboard range date inputs could truncate the final digit at desktop widths.
- AI briefing: Qwen/Gemma availability remains runtime-checked; no fake local availability was added.
- Data freshness: Top-right quality summary remains visible, but fresh values still depend on each tab's data payload.
- Translation quality: Korean/English static contract checks still pass; no numeric/date translation logic changed.
- Performance: No background polling or extra LLM calls were added.
- Code structure: Changes are limited to route fallback and UI range/tab helpers.
- User experience: Mobile tab navigation could leave the active tab partly clipped.

## Enhancement Plan
- Priority 1: Reset standard global ranges to current date bounds instead of stale custom bounds.
- Priority 2: Preserve static asset 404 behavior while serving `index.html` for extensionless `/ui/<client-route>` paths.
- Priority 3: Improve dashboard range and mobile tab layout so dates and active tabs remain readable.

## Validation Plan
- Build: No repo-level frontend package manifest; use syntax and contract checks.
- Lint: Use `git diff --check` and static UI contract because no JS linter is configured.
- Unit test: Run targeted UI/API route tests.
- Integration test: Run FastAPI static contract and live local server route checks.
- UI test: Capture Playwright desktop/mobile screenshots against `/ui/?range=1Y#quantamental`.
- Data quality test: Verify top-right quality/range markers remain present.
- AI hallucination guard test: Verify Quantamental AI UI panel fixture still exposes used-data and guardrail sections.

### 11:03 Changes

- Compatibility: Added `UiStaticFiles` in `app/api/server.py` so `/ui/quantamental` falls back to `index.html`, while asset-like missing paths such as `/ui/not-found-bundle.js` still return 404.
- Data consistency: `initGlobalRangeFromLocation()` and `setGlobalRange()` now use custom start/end dates only for `custom`; standard ranges recalculate bounds from the current local date.
- UI/UX: Dashboard date columns now fit full `YYYY-MM-DD` values, and mobile dashboard tabs use horizontal scroll with active-tab horizontal alignment only.
- Visualization: Range support copy and the visible range controls now reflect the current standard period without stale custom anchors.
- AI Briefing: No model/provider behavior changed; existing deterministic guardrail and runtime-checked model selector were revalidated through UI contract tests.
- Translation: No translation or label-generation logic changed.
- Performance: No new network calls, polling loops, or synchronous heavy work were added.

### 11:03 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js`; `node --check app/web/modules/quantamental-ui.js` | Passed | Static UI controller and Quantamental module parse. |
| Python syntax | `python -m py_compile app/api/server.py scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | Server fallback and scripts import. |
| UI/API contract | `python scripts/check_ui_contract.py` | Passed | `/ui/` 200, `/ui/quantamental` 200, missing asset 404, no missing markers. |
| Targeted tests | `python -m pytest tests/test_ui_routing_contract.py tests/test_ui_modules.py tests/test_quantamental_ui_ai_panel.py tests/test_api_routing_contract.py -q` | Passed | `55 passed, 4 subtests passed`. |
| Diff hygiene | `git diff --check -- app/api/server.py app/web/index.html app/web/app.js app/web/styles.css scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py tests/test_ui_routing_contract.py` | Passed | Only CRLF normalization warnings. |
| Live server | `python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8403` | Passed | `/api/v1/health`, `/ui/?range=1Y#quantamental`, `/ui/quantamental` checked. |
| UI screenshots | `npx playwright screenshot` desktop `1440x1000` and mobile `390x900` | Passed | Files written under `reports/ui_continuous_20260519_1103_*final2.png`. |
| Model availability | `GET /api/v1/config` | Passed | Qwen and Gemma remain `runtime_checked`; local installation is not claimed. |
| Quantamental API regression | `python -m pytest tests/test_quantamental_api.py -q` | Blocked | Clean stacked worktree only has tracked `pipelines/quantamental/ai_service.py`; missing `pipelines.quantamental.service` exists outside this branch as prior dirty/untracked work. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no `package.json` or `pnpm-lock.yaml`. |

### 11:03 Completion Checklist

#### Compatibility
- [x] Existing UI route flow preserved
- [x] Static asset 404 behavior preserved
- [x] Existing API contracts touched by this run are not broken
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Standard range selection no longer reuses stale custom bounds
- [x] Range markers and quality summary remain visible
- [x] Missing data behavior was not relaxed or fabricated
- [x] Cache/fresh data distinction remains unchanged

#### UI
- [x] Default view remains All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Date input text fits in desktop range controls
- [x] Mobile tabs keep the active tab readable without vertical scroll jumps
- [x] Loading/empty/error state markers remain in the static contract

#### Visualization
- [x] Period selection continues to update supported controls
- [x] Range support copy remains visible
- [x] Desktop and mobile screenshots were captured

#### AI Briefing
- [x] Gemma/Qwen availability checked through `/api/v1/config`
- [x] Model selection is not fake
- [x] Existing used-data UI guard fixture passed
- [x] No unsupported facts or generated metrics were added

#### Validation
- [x] Lint/diff hygiene executed
- [x] Build exclusion documented
- [x] Tests executed with blocker documented
- [x] UI validation executed
- [x] Data validation executed through range contract
- [x] AI briefing validation executed through UI fixture and config check

#### Documentation
- [x] `docs/CONTINUOUS_ENHANCEMENT_LOG.md` updated
- [x] README update not needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 12:03

## Current Project Summary
- Project purpose: FastAPI-served local financial research workstation for market, macro, Quant Lab, Quantamental, ML Forecast, AI Portfolio, and grounded AI briefing workflows.
- Main frontend structure: Static `/ui/` shell under `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`, with domain modules under `app/web/modules/`.
- Main backend structure: FastAPI app in `app/api/server.py`, routers under `app/api/routers/`, shared contracts in `core/schemas/`, and services under `pipelines/`.
- Data flow: UI controls call `/api/v1/*`; Python routers/services normalize provider/cache data before rendering dashboard cards, charts, tables, and briefing panels.
- AI/LLM flow: `/api/v1/config` exposes runtime-checked Qwen/Gemma options; Quantamental AI UI defaults to deterministic guardrail and sends LLM models only on explicit user actions.
- Visualization flow: Static cards/charts render from server payloads; global range, quality summary, and panel filters remain the primary dashboard context controls.
- Testing flow: Python contract scripts/tests, API route tests, JS syntax checks, and Playwright screenshots/smoke are the current lightweight validation path.

## Current Problems
- Compatibility: This worktree is a clean stacked branch above previous automation PRs; it still lacks the broader tracked Quantamental router/service implementation present only as prior dirty/untracked work outside this branch.
- Data consistency: Global range and quality contracts are present, but browser smoke still reaches missing Quantamental endpoints in this clean branch.
- UI consistency: `Core / Diagnostics / Operations / All` still defaults to All and the top-right quality badge remains visible.
- Visualization: Browser screenshots show desktop/mobile `/ui/?range=1Y#quantamental`; no chart renderer logic changed in this slice.
- AI briefing: Quantamental UI/fixture guardrails render used-data sections, but full Quantamental API validation remains blocked by missing `pipelines.quantamental.service` in this branch.
- Data freshness: Decision context strip now has a server-backed contract; tab-specific freshness values still depend on their data payloads.
- Translation quality: Static HTML was already checked for mojibake; this run expands checks to dynamic JS UI copy and Quantamental AI panel output.
- Performance: No background polling, heavy calculation, or LLM call was added.
- Code structure: Added a small dashboard API contract and contract-test helpers without moving frontend ownership boundaries.
- User experience: Dashboard context chips now load from `/api/v1/dashboard/decision-cards` instead of failing 404 and falling back silently.

## Enhancement Plan
- Priority 1: Add server-backed dashboard decision context cards for every dashboard tab.
- Priority 2: Extend UI contract checks to dynamic JavaScript copy so runtime Korean/English labels cannot regress to mojibake.
- Priority 3: Re-run browser checks and document the remaining Quantamental clean-branch blocker separately from this run's changes.

## Validation Plan
- Build: No repo-level frontend package manifest; validate with syntax checks and Python contracts.
- Lint: Use `git diff --check`; no JS lint command is configured.
- Unit test: Run dashboard/API/UI routing and Quantamental AI panel fixture tests.
- Integration test: Run `/api/v1/dashboard/decision-cards`, static UI contract, and live local server route checks.
- UI test: Capture Playwright desktop/mobile screenshots and DOM-check All/quality/range/decision-card contract.
- Data quality test: Verify `globalQualitySummary` and `qualityContextSummary` markers remain present and dynamic copy has no mojibake.
- AI hallucination guard test: Verify Quantamental AI panel fixture still exposes used data, key changes, interpretation, scenarios, user actions, and blocks mojibake/placeholder output.

### 12:03 Changes

- Compatibility: Added `/api/v1/dashboard/decision-cards` without changing existing dashboard, market, macro, strategy, trading/order, secret, or model routes.
- Data consistency: Dashboard context cards now explicitly identify advisory-only purpose, primary output, and tab-level data/guardrail context instead of leaving UI fallback as the only source.
- UI/UX: The top dashboard context strip now receives `dashboard_decision_cards.v1` from the API; mobile DOM check confirmed no horizontal overflow at 390px.
- Visualization: No chart math changed; screenshots were captured for desktop and mobile `/ui/?range=1Y#quantamental`.
- AI Briefing: Dynamic JS copy and Quantamental AI panel fixture now fail tests on CJK-mojibake/replacement-character output; the panel still requires used-data and guardrail sections.
- Translation: Extended contract checks from static HTML into `app.js` and all domain modules under `app/web/modules/`.
- Performance: Decision cards are static contract metadata and add no provider calls, polling loops, or LLM calls.

### 12:03 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| JS syntax | `node --check app/web/app.js`; `node --check app/web/modules/quantamental-ui.js` | Passed | Static UI controller and Quantamental module parse. |
| Python syntax | `python -m py_compile app/api/routers/dashboard.py scripts/check_ui_contract.py tests/test_dashboard_api.py tests/test_ui_routing_contract.py tests/test_quantamental_ui_ai_panel.py` | Passed | Router, contract script, and tests compile. |
| UI contract | `python scripts/check_ui_contract.py --output reports/ui_contract_continuous_20260519_1203_after_api.json` | Passed | Static HTML and dynamic JS mojibake checks passed; `/ui/quantamental` 200 and missing asset 404 preserved. |
| Targeted tests | `python -m pytest tests/test_dashboard_api.py tests/test_api_routing_contract.py tests/test_ui_routing_contract.py tests/test_quantamental_ui_ai_panel.py tests/test_ui_modules.py -q` | Passed | `68 passed, 4 subtests passed`. |
| Diff hygiene | `git diff --check -- app/api/routers/dashboard.py scripts/check_ui_contract.py tests/test_dashboard_api.py tests/test_ui_routing_contract.py tests/test_quantamental_ui_ai_panel.py` | Passed | Only CRLF normalization warnings. |
| Live API | `GET /api/v1/dashboard/decision-cards` on `http://127.0.0.1:8408` | Passed | Returned 200 with `dashboard_decision_cards.v1`. |
| UI screenshots | `npx playwright screenshot --viewport-size "1440,1000"` and `"390,900"` | Passed | Files written to `reports/ui_continuous_20260519_1203_desktop.png` and `reports/ui_continuous_20260519_1203_mobile.png`. |
| Mobile DOM | Playwright DOM check at `390x900` | Passed | `horizontalOverflow=false`, `panelView=all`, `decisionContract=dashboard_decision_cards.v1`, Quantamental tab selected. |
| AI Portfolio browser smoke | `python scripts/ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8408 --timeout-s 120 --output reports/ai_portfolio_ui_smoke_continuous_20260519_1203_after_api.json` | Blocked | Decision-card 404 fixed, but clean branch still lacks `/api/v1/quantamental/*`; smoke times out on Quantamental Top 5 404. |
| Quantamental API regression | `python -m pytest tests/test_quantamental_api.py -q` | Blocked | Existing clean-branch blocker: `ImportError: cannot import name 'service' from 'pipelines.quantamental'`. |
| npm/pnpm build/lint/test | Not run | Excluded | Repo root has no `package.json` or `pnpm-lock.yaml`. |

### 12:03 Completion Checklist

#### Compatibility
- [x] Existing UI/API flows touched by this run still work
- [x] Existing API contracts were not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy logic change
- [x] No secret or env file exposure

#### Data
- [x] Date range controls remain present and URL-compatible
- [x] Data source and 기준일 markers remain in the quality contract
- [x] Missing data labels remain user-readable
- [x] Data quality summary is visible at top-right
- [x] Cache/fresh distinction remains unchanged

#### UI
- [x] Default view remains All
- [x] Core/Diagnostics/Operations filters still exist
- [x] Font and spacing changes were not introduced
- [x] Desktop/mobile screenshots captured
- [x] Loading/empty/error markers remain in static contract

#### Visualization
- [x] Chart contracts were not changed
- [x] Period controls still render
- [x] Desktop/mobile screenshots show no immediate layout overflow

#### AI Briefing
- [x] Gemma/Qwen availability remains runtime-checked through existing config
- [x] Model selection remains truthful
- [x] AI panel output includes used-data guardrail sections in fixture tests
- [x] Dynamic copy mojibake/placeholder guard added
- [x] Translation preserves numbers/dates/units in the AI panel fixture

#### Validation
- [x] Lint/diff hygiene executed
- [x] Build exclusion documented
- [x] Tests executed with existing blocker documented
- [x] UI validation executed
- [x] Data validation executed through UI/API contract checks
- [x] AI briefing validation executed through Quantamental UI fixture

#### Documentation
- [x] `docs/CONTINUOUS_ENHANCEMENT_LOG.md` updated
- [x] README update not needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result

## 2026-05-19 Continuous Enhancement Run 13:05

## Current Project Summary
- Project purpose: FastAPI-served local financial research workstation for market, macro, Quant Lab, Quantamental, ML Forecast, AI Portfolio, and grounded AI briefing workflows.
- Main frontend structure: Static `/ui/` shell under `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`, with small domain modules under `app/web/modules/`.
- Main backend structure: FastAPI app in `app/api/server.py`, routers under `app/api/routers/`, shared contracts in `core/schemas/`, and services under `pipelines/`.
- Data flow: UI controls call `/api/v1/*`; Python routers/services normalize provider/cache data before rendering dashboard cards, charts, tables, strategy data, and briefing panels.
- AI/LLM flow: `/api/v1/config` exposes runtime-checked Qwen/Gemma options; this run did not add background LLM calls or change AI model routing.
- Visualization flow: Static cards/charts render from server payloads; global range, quality summary, and panel filters remain the primary dashboard context controls.
- Testing flow: Python contract scripts/tests, API route tests, JS syntax checks, browser DOM checks, and Playwright screenshots are the current lightweight validation path.

## Current Problems
- Compatibility: The clean stacked branch still lacks the broader Quantamental router/service files present only in another dirty worktree; `tests/test_quantamental_api.py` remains blocked at import collection.
- Data consistency: Quant Lab strategy data exposed momentum and volatility separately, but did not include a first-class risk-adjusted momentum factor/template for rank-based strategy evaluation.
- UI consistency: Quant Lab strategy dropdown did not expose the new risk-adjusted template because it did not exist yet.
- Visualization: No chart renderer logic changed; Quant Lab strategy labels and artifact data remain the visible interpretation layer for this slice.
- AI briefing: No AI prompt/model behavior changed; existing Quantamental AI guardrails were not touched.
- Data freshness: Existing Quant Lab freshness profiles and top-right quality summary remain unchanged.
- Translation quality: Added Korean UI label `위험조정 모멘텀`; no ticker/date/number translation path changed.
- Performance: The new algorithm reuses the existing factor preview/backtest pipeline and does not add polling, provider calls, or synchronous LLM work.
- Code structure: The implementation stays inside existing factor, signal, backtest, strategy registry, API config, UI, and test boundaries.
- User experience: Users can now select a volatility-aware momentum strategy from Quant Lab and from Strategy Governance defaults.

## Enhancement Plan
- Priority 1: Add deterministic `risk_adjusted_momentum_63_21` factor data to the Quant Lab factor catalog and default feature set.
- Priority 2: Add `risk_adjusted_momentum` signal/backtest template while preserving the next-bar execution and no-lookahead policy.
- Priority 3: Expose the strategy through default strategy data and Quant Lab UI without changing existing strategy semantics.

## Validation Plan
- Build: No repo-level frontend package manifest; validate with syntax checks and Python contracts.
- Lint: Use `git diff --check`; no JS lint command is configured.
- Unit test: Run factor, signal, backtest, strategy registry, Quant Lab API/pipeline tests.
- Integration test: Run `/api/v1/quant/config`, `/api/v1/quant/strategy/list`, static UI contract, and live server checks.
- UI test: Verify Quant Lab tab in browser and capture mobile Playwright screenshot.
- Data quality test: Verify the strategy uses `data_mart:prices_daily`, freshness policy diagnostics, and persisted artifact data snapshot.
- AI hallucination guard test: Not changed in this slice; verify no new LLM or AI briefing behavior was added.

### 13:05 Changes

- Compatibility: Existing strategy templates, API request/response shapes, execution policy, secrets, and trading/order code were not changed.
- Data Consistency: Added `risk_adjusted_momentum_63_21`, computed as 63-day momentum divided by 21-day realized volatility with a deterministic volatility floor.
- UI/UX: Added `위험조정 모멘텀` to the Quant Lab strategy selector and Strategy Governance mapping.
- Visualization: No chart math changed; the new strategy label and score mode are visible in Quant Lab strategy/report surfaces.
- AI Briefing: No AI prompt/model changes; the new quant algorithm is deterministic and does not ask the model to invent metrics.
- Translation: The new Korean UI label is static, concise, and does not alter ticker/date/unit formatting.
- Performance: The algorithm reuses existing in-memory price arrays and factor preview data; no new provider fetch path or background loop was added.

### 13:05 Validation Results

| Check | Command / Tool | Result | Notes |
|---|---|---|---|
| Python syntax | `python -m py_compile pipelines/factors/core.py pipelines/factors/catalog.py pipelines/signals/rule_based.py pipelines/backtest/engine.py pipelines/orchestration/quant_lab_pipeline.py pipelines/strategies/registry.py scripts/check_ui_contract.py scripts/ai_portfolio_ui_smoke.py` | Passed | New factor, strategy, and contract files compile. |
| JS syntax | `node --check app/web/app.js` | Passed | Static UI controller parses. |
| Strategy data JSON | PowerShell heredoc piped to `python -` JSON load | Passed | `config/quant_strategies/defaults.yaml` remains valid JSON content. |
| UI contract | `python scripts/check_ui_contract.py --output reports/ui_contract_continuous_20260519_1305_pretest.json` | Passed | New risk-adjusted option and JS label markers included. |
| Targeted quant tests | `python -m pytest tests/test_factor_catalog.py tests/test_signal_generation.py tests/test_backtest_engine.py tests/test_strategy_registry.py -q` | Passed | `18 passed`. |
| Quant Lab/API/UI routing tests | `python -m pytest tests/test_quant_lab_pipeline.py tests/test_quant_lab_api.py tests/test_ui_routing_contract.py tests/test_api_routing_contract.py -q` | Passed | `81 passed, 4 subtests passed`. |
| Focused rerun | `python -m pytest tests/test_backtest_engine.py tests/test_quant_lab_pipeline.py tests/test_quant_lab_api.py -q` | Passed | `33 passed`. |
| Full pytest | `python -m pytest -q` | Blocked | Existing clean-branch blocker: `ImportError: cannot import name 'service' from 'pipelines.quantamental'`; `pipelines/quantamental/service.py` is absent in this worktree. |
| Diff hygiene | `git diff --check` | Passed | Only expected Windows CRLF conversion warnings. |
| Live API | `GET /api/v1/quant/config`; `GET /api/v1/quant/strategy/list` on `http://127.0.0.1:8413` | Passed | `risk_adjusted_momentum` template and `risk_adjusted_momentum_v1` strategy returned. |
| Browser UI | Browser MCP at `http://host.docker.internal:8413/ui/?range=1Y#quant` | Passed with known unrelated console error | Quant Lab active, `panelView=all`, risk-adjusted option visible/selectable, no desktop horizontal overflow. Console error is the known clean-branch missing Quantamental watchlist route. |
| Mobile screenshot | `npx playwright screenshot --viewport-size "390,900" http://127.0.0.1:8413/ui/?range=1Y#quant reports/ui_continuous_20260519_1305_quant_mobile.png` | Passed | Mobile screenshot written; direct Node Playwright DOM check was unavailable because local `playwright` module is not installed. |

### 13:05 Completion Checklist

#### Compatibility
- [x] Existing UI/API flows touched by this run still work
- [x] Existing API contracts were not broken
- [x] Existing UI flow is preserved
- [x] No unauthorized strategy entry/exit condition changed
- [x] No secret or env file exposure

#### Data
- [x] New risk-adjusted factor is deterministic and uses price data from `data_mart:prices_daily`
- [x] Factor preview, signal, and backtest use the same selected Quant Lab date/range inputs
- [x] Data source and freshness diagnostics remain present
- [x] Missing data behavior was not relaxed or fabricated
- [x] Data quality summary remains visible at top-right
- [x] Cache/fresh distinction remains unchanged

#### UI
- [x] Default view remains All
- [x] Core/Diagnostics/Operations filters still exist
- [x] New strategy option is visible and selectable in Quant Lab
- [x] Desktop browser DOM showed no horizontal overflow
- [x] Mobile screenshot captured
- [x] Loading/empty/error markers remain in static contract

#### Visualization
- [x] Chart contracts were not changed
- [x] Period controls still render
- [x] Strategy label and score mode are visible in Quant Lab report paths

#### AI Briefing
- [x] Gemma/Qwen availability remains runtime-checked through existing config
- [x] Model selection remains truthful
- [x] No unsupported AI facts or generated metrics were added
- [x] New quant calculations are computed in code, not by AI

#### Validation
- [x] Lint/diff hygiene executed
- [x] Build exclusion documented
- [x] Tests executed with existing blocker documented
- [x] UI validation executed
- [x] Data validation executed through API/config/tests
- [x] AI briefing validation documented as unchanged

#### Documentation
- [x] `docs/CONTINUOUS_ENHANCEMENT_LOG.md` updated
- [x] README update not needed
- [x] PR summary includes changed files
- [x] PR summary includes validation result
