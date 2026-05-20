# TODO UI Review

## Implemented In This Pass

- Side-docked research panel: the existing research controls now default to a collapsed left rail on desktop, with the existing toggle preserving the expanded/collapsed choice in local storage.
- Market dashboard order: the existing TradingView single chart now appears above the market tape and cross-asset signal cards.
- Market snapshot consolidation: the standalone internal market snapshot card is visually removed from the market dashboard because the same market tape context is now presented through the primary market tape/snapshot surface. The hidden DOM node remains in place for script and contract compatibility.
- Theme toggle: added a real light/dark theme toggle using local storage and CSS variables only.
- Saved dashboard panel view: existing dashboard panel view selection now persists in local storage without changing API behavior.
- TradingView chart controls: added real symbol, interval, and comparison controls that remount the existing TradingView widget and persist the selected view in local storage.
- Internal OHLC chart source: added a real `Internal data` source that uses existing daily price rows plus a new internal dashboard intraday OHLC endpoint, renders local OHLC/close charts, supports relative comparison, and fails visibly when rows are unavailable.
- Internal intraday charting: the `5m`, `15m`, and `1h` chart intervals now use `/api/v1/dashboard/market/intraday/{ticker}` instead of the external TradingView embed when `Internal data` is selected.
- Persisted intraday chart cache: internal intraday chart responses now reuse `dashboard_snapshots` for a short durable cache and can fall back to an expired snapshot when the provider fails.
- Macro Explorer default detail: the Macro tab now automatically loads the default searched series detail so 구성·분해 지표 and related series are visible without requiring an extra click.
- Macro data refresh hardening: Macro refresh now retries failed FRED API series through the existing public CSV fallback and the live data mart was refreshed successfully.
- CSS cleanup guardrail: kept the final override layer as the active source of truth and added explicit contract coverage for the new chart controls. Older broad selector cleanup remains gated on a dedicated visual regression harness.
- AI Portfolio dashboard request guard: the operations refresh path now reuses a short-lived dashboard cache and deduplicates concurrent dashboard requests so tab hydration does not fan out into duplicate API calls.
- Domain UI module split: Market tape/signals, Macro provider health, Forecast jobs, Quant export storage, and AI Portfolio dashboard fragments now live in dedicated `app/web/modules/*.js` render helpers. The duplicated `app.js` renderer bodies for those surfaces were removed; `app.js` now keeps only a small module-unavailable guard.
- Versioned static asset guard: `/ui/` now loads unchanged domain modules with `20260514-domain-modules`, AI Portfolio UI with `20260520-ai-portfolio-ops-v1`, and the main bundle with the current purpose-layout cache key; UI contract/smoke checks assert those exact scripts.
- Fixture-backed module contracts: `tests/test_ui_modules.py` executes the static UI modules in Node, validates representative payload rendering, verifies action markers, and checks HTML escaping for user/provider-controlled fields.
- Dashboard browser smoke matrix: `scripts/ai_portfolio_ui_smoke.py` now asserts module globals and visible primary surfaces across Market, Macro, Quant Lab, ML Forecast, and AI Portfolio tabs, not only the AI Portfolio landing state.
- Non-destructive dashboard action smoke: the browser smoke now clicks a representative safe action per dashboard area: internal Market chart apply, Macro series search, Quant run-history refresh, Forecast provider/jobs refresh, and AI Portfolio operations refresh. The smoke initializes the chart source to internal data to avoid external TradingView console noise while still validating the local UI path.

## Deferred Features

- Aggressive deletion of older CSS override blocks: this can be done after snapshot coverage across Market, Macro, Quant Lab, ML Forecast, AI Portfolio, modals, and mobile states.
- Full `app.js` decomposition: the next safe slice is to move event binding and API orchestration per domain after each extracted renderer has broader fixture and browser coverage.

## Potential Future UX Improvements

- Dashboard section density presets for Market, Macro, Quant Lab, Forecast, AI Portfolio.
- Long research report outline navigation when Markdown output grows large.
- More explicit source grouping by provider/date when backend response contracts expose stable metadata.
- Keyboard-first command palette if product navigation grows further.
- Per-dashboard module contracts: split the current shared module fixture test into domain-specific cases when renderer payloads grow.
- Browser regression matrix: extend the current safe action checks into deeper workflow-level checks only for operations with explicit success/failure states and bounded runtime.

## Design Risks

- `app/web/styles.css` has several accumulated override blocks. The current pass centralizes the final visual layer at the bottom, but a future cleanup could remove obsolete earlier rules after broader regression testing.
- Static HTML contains many cross-feature surfaces. Strong visual hierarchy must avoid hiding controls that scripts expect to be present.
- Very dense dashboard tabs may still require browser-specific tuning after real data loads.
- TradingView embed availability still depends on the external TradingView host when `TradingView embed` is selected. The internal chart source and internal market tape remain the fail-open path.
- The domain modules intentionally use global `window.FinGPT*Ui` bridges because the static app has no bundler yet. A future ES module or build-step migration should happen only after the current static contract tests cover all tab entrypoints.

## Items Not Changed Because They Could Affect Logic

- Existing API endpoint names and backend request/response schemas were not changed. One additive dashboard intraday endpoint was introduced for real internal chart intervals.
- No DOM ids, `data-testid` values, form field names, or button bindings were removed.
- No model/LLM routing, prompt, analysis pipeline, or data mart behavior was changed.
- No source/evidence schema or financial content interpretation was changed.
- No new fake metrics, fake sources, fake confidence values, or non-working buttons were added.
