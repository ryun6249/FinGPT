# UI Tab Decision Checklist

Updated: 2026-05-16

Scope: static FinGPT `/ui/` dashboard only. Preserve API routes, schemas, service logic, model behavior, storage, and analysis output semantics.

## Compatibility Decision

- [x] Proceed with CSS and static HTML tier/order changes only.
- [x] Preserve all existing element ids, `data-testid` markers, API constants, fetch paths, and event bindings.
- [x] Keep destructive actions and backend data contracts unchanged.
- [x] Do not add fake decision metrics or fabricated outputs.
- [x] Verify with syntax checks, UI contract checks, and live browser tab inspection.

## Implementation Checklist

- [x] Market Dashboard: move decision surfaces before visual/reference panels.
  - Keep: market tape, cross-asset signals, data health, heatmap.
  - Reduce: TradingView chart and news first-screen priority.

- [x] Macro: make regime and data quality the first Core surfaces.
  - Keep: regime summary, data quality, coverage, Macro Explorer.
  - Reduce: Explorer-first layout and disconnected/future-hook surfaces in Core.

- [x] Quant Lab: make backtest and portfolio the Core workflow.
  - Keep: backtest, portfolio optimizer, strategy/signal diagnostics.
  - Reduce: standalone asset-detail priority in Core.

- [x] Quantamental: reduce Core from seven primary cards to three primary cards.
  - Keep in Core: setup/company, deterministic signal, composite score.
  - Move to Details: factor grid, research terminal, data quality.
  - Move to Operations: peer comparison/watchlists/export.

- [x] ML Forecast: reduce Core from six primary cards to four primary cards.
  - Keep in Core: setup, dataset quality, leakage check, forecast result.
  - Move to Details: feature lab and signal generator.
  - Keep Operations: jobs, registry, drift, model comparison, provider guard.

- [x] AI Portfolio: put recommendation before create form.
  - Keep: policy overview, recommendation, create form, compliance, rebalancing.
  - Reduce: create-form dominance when no active policy is selected.

- [x] Left command panel: avoid desktop overlap when opened.
  - Keep: collapsible side rail.
  - Improve: expanded state reserves layout space instead of covering the workbench.

- [x] Mobile tab bar: reduce visible horizontal-scroll clutter.
  - Keep: all top-level tabs.
  - Improve: stable horizontal scrolling without exposed browser scrollbar.

## Backend Decision Card Contract

- [x] Add a backend-backed common "decision card" contract per tab.
  - Endpoint: `GET /api/v1/dashboard/decision-cards`
  - Compatibility: metadata-only contract; no synthetic scores, no buy/sell recommendations, no route/schema changes outside the dashboard namespace.
  - UI: reuse `#dashboardContextStrip` so existing tab layout and selectors remain stable.
  - Evidence boundary: Market may include cached local snapshot freshness evidence; other tabs expose source endpoints, guardrails, primary output, and next action without pretending a run has completed.
