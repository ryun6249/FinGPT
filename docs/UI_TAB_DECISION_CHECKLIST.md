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

- [x] Risk: add enterprise risk control plane after Macro.
  - Keep in first viewport: command bar, decision-usable status, risk index, confidence, freshness, and top drivers.
  - Show a typed input receipt in the first-flow surface so users can verify normalized mode, subjects, position weights, compatibility notes, and replay notes before comparing outputs.
  - Show the deterministic decision brief near the executive strip: review questions, watch items, blocked reasons, and service-contract notes.
  - Show a consolidated decision path in the first-flow surface so the user sees the next action, linked workflow, Forecast validation launch, and service gate without scanning every diagnostic panel.
  - Show a decision-quality summary in the first-flow surface so confidence, data-quality gates, input normalization, service readiness, release status, and ML Forecast validation availability are visible as one `ok`, `review`, or `blocked` status.
  - Show a decision compass in the first-flow surface so the user sees the intended sequence: verify input/quality, review evidence coverage, run Forecast validation, control AI narrative output, and review the service gate.
  - Show an evidence-coverage matrix in the first-flow surface and evidence drawer so input, company, macro, scenario, Forecast-validation, service-release, and evidence-inventory domains are visible as `ok`, `review`, or `blocked`.
  - Show AI output guardrails in the first-flow surface and evidence drawer so any model-written Risk narrative has required evidence refs, blocked-claim rules, citation policy, and prompt context before it is reused or shared.
  - Show a per-subject compatibility matrix in the first-flow surface and evidence drawer so users can see which Risk, Quantamental, Macro, ML Forecast, AI Portfolio, and service workflows are supported or blocked before navigating away.
  - Show a structured action checklist in the first-flow surface so data-quality, top-driver, scenario, asset-proxy, portfolio concentration, and release-gate follow-ups are visible as `ok`, `review`, or `blocked`.
  - Show structured monitoring triggers in the same first-flow surface so users know which data-quality, driver, transmission, scenario, proxy-scope, and release-readiness changes should be watched after the run.
  - Show a compact priority risk map in the first-flow surface so the highest company, macro, and data-quality cells are visible without forcing users into the full evidence drawer.
  - Show a compact confidence-factor ladder in the first-flow surface so users can see whether confidence is driven by company coverage, macro coverage, data quality, scenario coverage, or service controls.
  - Show a typed handoff queue in the first-flow surface so the next workflow is explicit: Risk evidence repair, Macro pressure review, Quantamental drilldown, ML Forecast validation test, AI Portfolio overlay review, or service-wrapper release gate.
  - Show typed ML validation tests in the first-flow surface so the user can run the right ML Forecast experiment next: walk-forward baseline, macro-feature leakage check, severe-scenario backtest, asset-proxy validation, portfolio component OOS check, or blocked data-gate recheck.
  - Show a Forecast validation plan in the first-flow surface and evidence drawer so the user can see the primary ML test, run order, experiment controls, acceptance criteria, and blocked reasons before launching Forecast.
  - Render existing Risk visuals as first-class visual surfaces: SVG driver contribution bars, transmission flow map, and scenario stress heatmap before the detail tables/cards.
  - Render a first-flow visual control plane before the longer cards: readiness radar for risk pressure, decision quality, evidence coverage, confidence, Forecast validation, and AI guardrails; workflow lane for input receipt, decision path, evidence, Forecast, service gate, and AI controls.
  - Add a causal path map in the first-flow visual control plane so users can scan input receipt -> priority driver -> transmission path -> scenario stress -> Forecast validation -> service gate without reading every detailed card first.
  - Extend the visual control plane with an evidence trace map and service gate rail so the user can inspect source coverage, compatibility, Forecast validation, lineage, AI grounding, readiness, release checks, actions, and monitoring without reading every list card first.
  - Add a coverage topology in the first-flow surface and evidence drawer so evidence domains, counts, freshness/scope, workflow support, and blocked workflow counts are visible before opening long compatibility lists.
  - Add a pressure stack in the first-flow surface and evidence drawer so risk index, top driver pressure, dominant transmission delta, scenario stress, data penalty, and Forecast validation are visible as one scan-first composition.
  - Actionable ML validation tests must include an ML Forecast launch link that prefills ticker, benchmark, horizon, validation method, target type, macro/cross-asset switches, Risk test id, and Risk input hash. Blocked data-gate tests should not expose a Forecast launch link.
  - Risk-originated Forecast launches must render a compact ML Forecast handoff plan and persist Risk source context into the Forecast request payload.
  - Show structured service-readiness in the same first-flow surface: `ready`, `review_required`, or `blocked`, with checklist evidence, warnings, blockers, and next steps.
  - Show a typed release packet in the first-flow surface and evidence drawer: API/UI routes, required audit fields, validation commands, deployment checks, rollback triggers, data dependencies, and explicit limitations.
  - Show run lineage in the evidence drawer: service version, replay fields, adapter status, subject count, evidence count, and freshness counts.
  - Portfolio mode accepts compact weighted input such as `NVDA:0.40, MSFT:0.35, TLT:0.25` and normalizes weights before calling the API.
  - KR/EN toggle must update both static Risk UI labels and backend-generated decision brief text through `output_language`.
  - ETF/macro proxy symbols such as `TLT`, `HYG`, and `SPY` must show limited asset-proxy coverage instead of fabricated company fundamentals.
  - Show: company vectors, macro pressure, transmission matrix, scenario matrix, evidence, input hash, and calculation policy.
  - Guard: unknown, partial, stale, and error states remain visible and are not presented as valid conclusions.
  - Prohibit: direct buy/sell/hold instructions or AI-generated risk scores.

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
