# FinGPT Strategy Research Optimization Plan

## 0. Inspection Result

Status after implementation: **FinGPT-native MVP implemented for repo-local deterministic strategy research.** The original Quant Web service architecture still does not exist in this repository, so the implementation is intentionally integrated into FinGPT Quant Lab instead of copying Quant Web `services/*` boundaries.

The prompt targets the `ryun6249/quant-web` monorepo shape:

- `apps/web`
- `services/api-gateway`
- `services/backtest-service`
- `packages/contracts`
- `packages/sdk-py`
- service-owned Alembic migrations

This checkout is `F:\LLM\FinGPT`. Those Quant Web service boundaries do not exist here. The matching FinGPT surfaces are:

- Static workstation UI: `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`
- Quant API owner: `app/api/routers/quant_lab.py`, mounted under `/api/v1/quant/*`
- Quant contracts: `core/schemas/quant.py`
- Strategy registry and governance: `pipelines/strategies/registry.py`, `pipelines/strategies/storage.py`
- Backtest runtime and artifacts: `pipelines/backtest/*`, `pipelines/orchestration/quant_lab_pipeline.py`
- Forecast and model validation: `app/api/routers/forecast.py`, `pipelines/forecast/*`
- Quant Model Lab: `pipelines/orchestration/quant_model_lab.py`, `pipelines/model_profiles/storage.py`
- Existing tests: `tests/test_quant_lab_api.py`, `tests/test_quant_lab_pipeline.py`, `tests/test_forecast_lab.py`, `tests/test_ui_routing_contract.py`
- Browser checks: `scripts/check_ui_contract.py`, `scripts/quant_lab_ui_smoke.py`

Initial inspection evidence:

- No implemented `StrategyResearch*`, `StrategyOptimization*`, `StrategyDiagnostics*`, `StrategyHypothesis`, or `StrategyValidation*` contracts were found outside this plan before implementation.
- No `/api/v1/quant/strategy-research/*` route existed before implementation.
- Quant Lab already has backtest runs, replay, diagnostics artifacts, exports, strategy generation/dry-run, model profiles, and `cross_sectional_rank` Model Lab support.
- The dedicated workflow requested by the prompt - strategy versions, optimization trials, structured hypotheses, accept/reject decisions, validation results, and Strategy Research Lab UI - is now implemented as a FinGPT-native MVP under `/api/v1/quant/strategy-research/*` and the dedicated Auto Trading tab.

## 1. Existing Architecture Summary

FinGPT is a single FastAPI plus static workstation app, not a multi-service Quant Web monorepo.

Important boundaries:

- Browser calls the mounted FastAPI app under `/api/v1/*`; there is no separate `api-gateway`.
- Quant Lab owns strategy research-adjacent workflow under `/api/v1/quant/*`.
- Numeric market data is stored through the data mart, not a backtest-service database.
- Backtest artifacts are filesystem-backed under `data/quant_lab/backtests/{run_id}/`.
- Run-history style metadata is already artifact-oriented; a new strategy-research slice should start artifact-first.
- Forecast validation already supports walk-forward, purge/embargo, and optional purged CV diagnostics.
- Risk outputs already create ML validation handoffs, but they are not strategy-research hypotheses.

## 2. Existing Quant Lab Capabilities

Already implemented:

- Factor preview through `/api/v1/quant/features/preview`
- Signal generation through `/api/v1/quant/signals/generate`
- Deterministic backtests through `/api/v1/quant/backtest`
- Saved run listing and artifact bundle retrieval
- Replay comparison with config hash matching
- JSONL/CSV export and guarded cleanup
- Strategy save, dry-run, generate, migrate, list, detail, delete
- Model Profile save, dry-run, list, detail, delete
- Model Lab run/job paths for `single_asset`, `universe_per_asset`, and `cross_sectional_rank`
- UI coverage in the dedicated Auto Trading tab
- Browser smoke support through `scripts/quant_lab_ui_smoke.py`

## 3. Existing Limitations Against The Prompt

Missing or incomplete relative to the Quant Web prompt:

- No `StrategyResearchConfig`, `StrategyOptimizationRun`, `StrategyOptimizationTrial`, `StrategyDiagnosticsRun`, `StrategyHypothesis`, or `StrategyValidationResult` contracts.
- No strategy research artifact store or SQLite index.
- No explicit strategy version object with parent lineage, module configs, complexity score, and decision reason.
- No optimization API that stores trials and separates best parameters from recommended parameters.
- No diagnostics API that tags failed trades into structured failure causes.
- No persisted hypothesis queue with pending/accepted/rejected status.
- No validation API combining in-sample, out-of-sample, walk-forward, parameter stability, Monte Carlo, and cost stress.
- No UI panel dedicated to strategy research optimization, diagnostics, hypotheses, validation, and version comparison.
- No dedicated regression tests for strategy-research optimization/hypothesis/validation behavior.

## 4. FinGPT-Native Extension Points

Do not copy Quant Web service layout into this repo. Add a FinGPT-native slice:

- Contracts: extend `core/schemas/quant.py`.
- API: extend `app/api/routers/quant_lab.py` under `/api/v1/quant/strategy-research/*`.
- Runtime: add `pipelines/orchestration/strategy_research.py`.
- Persistence: add artifact-first storage under `data/quant_lab/strategy_research/{research_run_id}/`.
- Indexing: add `pipelines/strategy_research/storage.py` for JSON index files first; only add SQLite if artifact scanning becomes too slow.
- UI: add the dedicated Auto Trading tab in `app/web/index.html`, `app/web/app.js`, and `app/web/styles.css`.
- Existing strategy source: reuse `pipelines/strategies/storage.py` and `pipelines/strategies/registry.py`.
- Existing backtest source: reuse `run_quant_backtest(...)` from `pipelines/orchestration/quant_lab_pipeline.py`.
- Existing validation source: reuse forecast walk-forward concepts where applicable, but keep strategy backtest validation separate from Forecast model validation.

## 5. Contract Changes Required

Add additive Pydantic models in `core/schemas/quant.py`:

- `StrategyResearchStatus`
- `StrategyResearchConfig`
- `StrategyResearchStrategy`
- `StrategyResearchVersion`
- `StrategyResearchExperiment`
- `StrategyOptimizationRequest`
- `StrategyOptimizationRun`
- `StrategyOptimizationTrial`
- `StrategyDiagnosticsRequest`
- `StrategyDiagnosticsRun`
- `StrategyFailureTag`
- `StrategyHypothesis`
- `StrategyHypothesisDecisionRequest`
- `StrategyValidationRequest`
- `StrategyValidationResult`
- `StrategyValidationSummary`
- `StrategyResearchBackendStatus`

Serialization rules:

- Keep metric values as JSON-safe strings or floats consistently with existing Quant Lab payloads.
- Preserve existing `QuantBacktestRequest` and `QuantBacktestResponse` shape.
- Keep decision states explicit: `pending`, `accepted`, `rejected`, `archived`.
- Keep lifecycle states explicit: `queued`, `running`, `succeeded`, `failed`.
- Include evidence posture fields: `evidence_class`, `evidence_notes`, `verified_by`, and optional artifact paths where useful.

## 6. Persistence Plan

Phase 1 uses artifact-first persistence:

```text
data/quant_lab/strategy_research/
  strategies/
    {strategy_id}.json
  versions/
    {version_id}.json
  experiments/
    {experiment_id}/
      request.json
      optimization-summary.json
      optimization-trials.json
      diagnostics-summary.json
      hypotheses.json
      validation-result.json
      manifest.json
  index/
    strategies.json
    versions.json
    optimizations.json
    diagnostics.json
    hypotheses.json
    validations.json
```

Phase 2 may add a SQLite index only if needed:

- `data/quant_lab/strategy_research/index.sqlite`
- No foreign keys to data mart or output run DBs.
- Store cross-artifact references as explicit string ids.
- Keep JSON artifacts as the source of audit detail.

No Alembic migration is required for the first FinGPT-native implementation.

## 7. API Plan

Add routes under `/api/v1/quant/strategy-research/*`:

- `GET /api/v1/quant/strategy-research/backend-status`
- `GET /api/v1/quant/strategy-research/strategies`
- `POST /api/v1/quant/strategy-research/strategies`
- `GET /api/v1/quant/strategy-research/strategies/{strategy_id}`
- `GET /api/v1/quant/strategy-research/strategies/{strategy_id}/versions`
- `POST /api/v1/quant/strategy-research/strategies/{strategy_id}/versions`
- `POST /api/v1/quant/strategy-research/strategies/{strategy_id}/optimize`
- `GET /api/v1/quant/strategy-research/optimizations`
- `GET /api/v1/quant/strategy-research/optimizations/{optimization_id}`
- `GET /api/v1/quant/strategy-research/optimizations/{optimization_id}/trials`
- `POST /api/v1/quant/strategy-research/strategies/{strategy_id}/diagnose`
- `GET /api/v1/quant/strategy-research/diagnostics`
- `GET /api/v1/quant/strategy-research/diagnostics/{diagnostics_id}`
- `POST /api/v1/quant/strategy-research/strategies/{strategy_id}/hypotheses/generate`
- `GET /api/v1/quant/strategy-research/hypotheses`
- `GET /api/v1/quant/strategy-research/hypotheses/{hypothesis_id}`
- `POST /api/v1/quant/strategy-research/hypotheses/{hypothesis_id}/accept`
- `POST /api/v1/quant/strategy-research/hypotheses/{hypothesis_id}/reject`
- `POST /api/v1/quant/strategy-research/strategies/{strategy_id}/validate`
- `GET /api/v1/quant/strategy-research/validations`
- `GET /api/v1/quant/strategy-research/validations/{validation_id}`

Compatibility rule:

- Existing `/api/v1/quant/backtest`, strategy, model-profile, and model-lab routes must remain unchanged.
- Browser calls remain same-origin FastAPI calls through existing UI helpers; no direct internal file reads from frontend.

## 8. Strategy Model Design For FinGPT

Represent a strategy as separate modules:

- Core logic: existing strategy registry identity; protected from automatic LLM mutation.
- Optional filters: ADX, RSI, volatility, volume, trend, or existing factor gates.
- Risk module: stop, drawdown guard, exposure cap, volatility sizing.
- Exit module: signal exit, time exit, trailing stop, profit target.
- Position sizing: equal weight, risk target, volatility target, fixed fraction.

Rules:

- A hypothesis may propose optional filters, risk, exit, or sizing changes.
- A hypothesis must not modify core logic automatically.
- One experiment should add one major filter/rule unless explicitly configured otherwise.
- Complexity penalty must increase with additional filters, extra parameters, and rule stacking.
- Every accepted version must reference validation evidence.

## 9. Initial Presets

Use two presets to avoid blocking on data coverage:

1. FinGPT local default preset:
   - `risk_adjusted_momentum_v1`
   - Multi-asset equity/ETF universe
   - Daily bars from existing data mart
   - Purpose: deterministic local verification

2. Prompt-compatible research preset:
   - `BTCUSDT 4H Supertrend Research Preset`
   - Implemented as a repo-local deterministic 4H Supertrend engine.
   - Uses local data mart `BTCUSDT`/`BTC-USD` rows when available.
   - Uses a clearly labeled synthetic 4H fallback when local BTCUSDT coverage is absent.
   - Protected LEAN/live evidence is checked separately and remains fail-closed unless runtime detection reports availability.

Supertrend implementation status:

- Implemented inside `pipelines/orchestration/strategy_research.py` to keep strategy research evidence separate from generic factor previews.
- `stop_trigger_model=close_confirmed` exits long positions only when the close is below the trailing stop line.
- `stop_trigger_model=intrabar` uses the low breach path and is labeled as deterministic bar evidence.

## 10. Optimization Engine Plan

Add `pipelines/orchestration/strategy_research.py` with:

- `grid_search`
- `random_search`
- `bayesian` with Optuna TPE when `optuna` is installed
- deterministic surrogate fallback only when Optuna is unavailable, reported in backend status

Composite score:

```text
0.30 * normalized_sharpe
+ 0.25 * normalized_calmar
+ 0.20 * normalized_profit_factor
+ 0.15 * normalized_expectancy
- 0.10 * drawdown_penalty
- complexity_penalty
- overfitting_penalty
- low_trade_count_penalty
- concentration_penalty
```

Guards:

- Reject NaN/inf metrics.
- Reject invalid parameter values.
- Flag low trade count.
- Flag return concentration.
- Flag excessive drawdown.
- Keep best parameters separate from recommended parameters.
- Recommended parameters must consider OOS, stability, costs, drawdown, trade count, and complexity.

## 11. Diagnostics Engine Plan

Source inputs:

- Quant backtest trades artifact
- Equity curve artifact
- Drawdown curve artifact
- Signals artifact
- Config and data snapshot artifacts

Output:

- Summary
- Failure distribution
- Top failure causes
- Drawdown analysis
- Market regime analysis
- Long/short or selected/unselected analysis where available
- Cost impact analysis
- Parameter sensitivity notes
- Recommended hypotheses
- Rejected hypotheses

Failure tags:

- Choppy Market Loss
- Late Entry
- Early Exit
- Volatility Spike
- Low Volume Trap
- Trend Reversal
- Overtrading
- Stop Too Tight
- Stop Too Wide
- Regime Mismatch
- Fee Drag
- Weak Trend Entry
- False Breakout
- Poor Reward/Risk
- Return Concentration Risk
- Low Trade Count Risk
- OOS Degradation
- Parameter Instability

If current Quant Lab artifacts are insufficient for a tag, return `insufficient_evidence` instead of fabricating evidence.

## 12. Hypothesis Generation Plan

Start rule-based. Do not require live LLM.

Use deterministic problem-to-change mapping:

- Choppy loss -> ADX/choppiness/Bollinger width filter
- Volatility spike -> volatility percentile filter or close-confirmed stop
- Fee drag -> lower turnover or wider rebalance interval
- Return concentration -> exit module or diversification change
- Low trade count -> reject or widen universe, not accept
- Parameter instability -> reject spike and test neighboring parameters

Each hypothesis must include:

- `problem`
- `hypothesis`
- `proposed_change`
- `expected_effect`
- `risk`
- `validation_required`
- `decision`
- `status`

Duplicate suppression:

- Key by `strategy_id + version_id + problem + stable proposed_change`.
- Re-running generation must reuse matching hypotheses instead of stacking duplicates.

Optional LLM later:

- Use local LLM only behind a feature flag.
- Store prompt, model, schema version, and validation requirements.
- Keep all LLM hypotheses pending until validation evidence exists.

## 13. Validation Engine Plan

Minimum MVP:

- In-sample / out-of-sample split
- Walk-forward splits
- Parameter neighborhood stability
- Cost stress at 1x, 2x, 3x fees/slippage
- Monte Carlo trade resampling when trade count is sufficient

Acceptance flags:

- OOS return does not collapse
- OOS Sharpe/Sortino does not materially degrade
- Max drawdown remains within threshold
- Profit factor remains acceptable under cost stress
- Trade count is sufficient
- Return is not concentrated in one or two trades
- Parameter neighborhood is stable
- Complexity increase is justified

Rejection flags:

- In-sample only improvement
- OOS degradation
- Too few trades
- MDD increase
- Cost stress destroys expectancy
- Single parameter spike
- Excessive indicator stacking
- Core logic changed without explicit approval

## 14. UI Integration Plan

Add a compact Strategy Research section inside the dedicated Auto Trading tab.

Panels:

1. Strategy overview
   - strategy id, version, core logic, asset/universe, timeframe, status, complexity
2. Optimization
   - method, search space, best parameters, recommended parameters, trial table, score chart
3. Backtest evidence
   - metric strip, equity/drawdown, trade table, artifact references
4. Failure diagnostics
   - failure tag distribution, top causes, regime/cost/drawdown summaries
5. Hypothesis lab
   - structured hypotheses, risk, expected effect, validation requirements, accept/reject
6. Validation
   - IS/OOS metrics, walk-forward table, Monte Carlo, parameter stability, cost stress
7. Versions
   - lineage, status, complexity, decision reason, source experiment

UI rules:

- Keep existing dense Quant Lab visual language.
- Add loading, empty, error, and insufficient-evidence states.
- Keep Korean output where FinGPT surfaces currently use Korean text.
- Avoid financial advice wording.
- Display deterministic/advisory evidence boundaries clearly.

## 15. Files Expected To Change

Core implementation:

- `core/schemas/quant.py`
- `app/api/routers/quant_lab.py`
- `pipelines/orchestration/strategy_research.py`
- `pipelines/strategy_research/storage.py`
- `pipelines/strategy_research/__init__.py`
- Supertrend research logic is isolated in `pipelines/orchestration/strategy_research.py`; generic factor catalog files are not required for the MVP.
- `pipelines/strategies/registry.py`
- `pipelines/strategies/storage.py`

Frontend:

- `app/web/index.html`
- `app/web/app.js`
- `app/web/styles.css`

Tests:

- `tests/test_strategy_research.py`
- `tests/test_quant_lab_api.py`
- `tests/test_ui_routing_contract.py`
- `tests/test_ui_risk_contract.py` only if Risk handoff changes
- `scripts/quant_lab_ui_smoke.py`
- `scripts/check_ui_contract.py`

Docs:

- `docs/strategy-research-optimization-plan.md`
- `docs/QUANT_LAB_ADVANCEMENT_IMPLEMENTATION_CHECKLIST.md`
- `docs/ARCHITECTURE.md`
- `README.md` if user-facing commands change

## 16. Testing Plan

Targeted unit/API tests:

- strategy research backend status
- seed/list strategies
- create/list versions
- optimization run
- optimization trial persistence
- invalid parameter rejection
- NaN/inf guard
- diagnostics generation
- insufficient evidence diagnostics
- hypothesis generation
- duplicate hypothesis suppression
- hypothesis accept/reject
- validation result
- OOS degradation flag
- parameter stability flag
- cost stress flag
- Monte Carlo insufficient-evidence and success paths

UI/contract tests:

- Strategy Research section exists in Auto Trading tab
- no forbidden advice wording
- deterministic/advisory evidence warning visible
- hypothesis duplicate count remains stable after repeated generation
- validation panel renders accepted/rejected flags

Commands:

```powershell
python -m pytest tests\test_strategy_research.py -q
python -m pytest tests\test_quant_lab_api.py -q
python -m pytest tests\test_ui_routing_contract.py tests\test_ui_risk_contract.py -q
python scripts\check_ui_contract.py
python scripts\quant_lab_ui_smoke.py --timeout-s 180
```

Then broaden if the touched surface is large:

```powershell
python -m pytest tests -q
python -m core.preflight
```

## 17. Rollout Phases

Phase 1: Confirm current baseline

- Run targeted Quant Lab and UI routing tests.
- Capture current Quant Lab browser baseline if UI is about to change.
- Confirm local BTCUSDT 4H handling through data mart rows or the labeled deterministic synthetic fallback.

Phase 2: Contracts and artifact store

- Add Pydantic contracts.
- Add artifact writer/reader/index helpers.
- Add seed strategy research records.
- Add storage tests.

Phase 3: Optimization MVP

- Add grid/random/Optuna TPE Bayesian candidate generation.
- Execute via existing Quant backtest runtime.
- Persist trials and summary artifacts.
- Add composite scoring and guard flags.

Phase 4: Diagnostics and hypotheses

- Derive diagnostics from trade/equity/drawdown/signal artifacts.
- Add rule-based hypothesis generator.
- Add duplicate suppression and accept/reject decisions.

Phase 5: Validation

- Add IS/OOS split.
- Add walk-forward segments.
- Add parameter stability.
- Add cost stress.
- Add Monte Carlo when trade count allows.

Phase 6: UI

- Add Strategy Research section to Auto Trading.
- Reuse existing panels, tables, metric strips, and warning styling.
- Add Korean explanations and advisory boundaries.

Phase 7: Docs and verification

- Update architecture/checklist docs.
- Run targeted then broader tests.
- Run browser smoke.
- Document limitations and protected/unavailable evidence.

## 18. Risks And Compatibility Constraints

- Do not create a separate app.
- Do not copy Quant Web multi-service architecture into FinGPT.
- Do not break existing Quant Lab routes or artifacts.
- Do not change `QuantBacktestResponse` incompatibly.
- Do not claim live-market/protected validation from deterministic local evidence.
- Do not treat cross-sectional rank output as trade advice.
- Do not accept LLM-generated strategy changes without validation evidence.
- Do not claim protected/live Supertrend validation unless protected runtime status and evidence explicitly support it.
- Do not hide data freshness, lookahead, execution-delay, or survivorship warnings.
- Keep artifact paths under controlled project data directories.

## 19. Completion Checklist

- [x] Repo inspected.
- [x] Quant Web layout mismatch documented.
- [x] Existing FinGPT extension points identified.
- [x] Current non-implementation of dedicated Strategy Research MVP documented.
- [x] Strategy Research contracts added.
- [x] Artifact-first store added.
- [x] Strategy/version seed records added.
- [x] Optimization engine added.
- [x] Diagnostics engine added.
- [x] Hypothesis generator added.
- [x] Validation engine added.
- [x] API routes added.
- [x] Quant Lab UI section added.
- [x] Tests added.
- [x] Browser smoke updated and passing.
- [x] Docs updated after implementation.

## 20. Implemented Slice

The Quant Web prompt has now been applied to `F:\LLM\FinGPT` as a compatible FinGPT-native MVP, not as a direct Quant Web service-port.

Implemented files and surfaces:

- `core/schemas/quant.py`
- `pipelines/strategy_research/storage.py`
- `pipelines/orchestration/strategy_research.py`
- `app/api/routers/quant_lab.py`
- `app/web/index.html`
- `app/web/app.js`
- `app/web/styles.css`
- `tests/test_strategy_research.py`
- `tests/test_ui_routing_contract.py`
- `scripts/check_ui_contract.py`
- `docs/strategy-research-user-guide.md`

Implemented APIs:

- `/api/v1/quant/strategy-research/backend-status`
- `/api/v1/quant/strategy-research/strategies`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}/versions`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}/optimize`
- `/api/v1/quant/strategy-research/optimizations`
- `/api/v1/quant/strategy-research/optimizations/{optimization_id}`
- `/api/v1/quant/strategy-research/optimizations/{optimization_id}/trials`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}/diagnose`
- `/api/v1/quant/strategy-research/diagnostics`
- `/api/v1/quant/strategy-research/diagnostics/{diagnostics_id}`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}/hypotheses/generate`
- `/api/v1/quant/strategy-research/hypotheses`
- `/api/v1/quant/strategy-research/hypotheses/{hypothesis_id}`
- `/api/v1/quant/strategy-research/hypotheses/{hypothesis_id}/accept`
- `/api/v1/quant/strategy-research/hypotheses/{hypothesis_id}/reject`
- `/api/v1/quant/strategy-research/strategies/{strategy_id}/validate`
- `/api/v1/quant/strategy-research/validations`
- `/api/v1/quant/strategy-research/validations/{validation_id}`

Persistence:

- artifact-first storage under `data/quant_lab/strategy_research`
- Quant Lab UI integration

Verification status:

- Python syntax and API smoke: passed.
- `tests/test_strategy_research.py`: passed.
- `scripts/check_ui_contract.py`: passed.
- `tests/test_ui_routing_contract.py`: passed after adding Strategy Research UI contract markers.
- `python -m pytest tests\test_strategy_research.py tests\test_quant_lab_api.py tests\test_ui_routing_contract.py tests\test_ui_risk_contract.py -q`: `69 passed, 4 subtests passed`.
- `python scripts\quant_lab_ui_smoke.py --timeout-s 180`: passed, including Strategy Research optimization, diagnostics, hypotheses, validation, feature preview, signal matrix, backtest, replay/export, portfolio, and run-history checks; latest screenshot `reports/browser_ui/quant_lab_ui_smoke_1779429033.png`.
- `python -m pytest tests -q`: `748 passed, 9 subtests passed`.
- `python -m ruff check`: passed after active-path Ruff configuration in `pyproject.toml`.
- `python -m core.preflight`: critical dependencies operational; SEC filings remain non-critical blocked until `SEC_USER_AGENT` is configured.
- Codex in-app browser verification on `http://127.0.0.1:61928/ui/#auto-trading`: Auto Trading tab selected, Strategy Governance and Strategy Research visible, Quant Lab backtest hidden, and the control card showed the protected runtime fail-closed boundary.
