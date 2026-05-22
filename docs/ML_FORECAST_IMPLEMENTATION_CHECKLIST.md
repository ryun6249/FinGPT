# ML Forecast Implementation Checklist

Updated: 2026-05-22
Source of truth for the ML Forecast implementation in `F:\LLM\FinGPT`.

## 1. Repository Inspection
- Status: DONE
- frontend framework: Static HTML/CSS/JavaScript served by FastAPI from `app/web`.
- backend framework: FastAPI in `app/api/server.py`.
- routing structure: Domain routers live under `app/api/routers`; the new router is mounted at `/api/v1/forecast` and `/api/forecast`.
- API client structure: `app/web/app.js` uses a top-level `API` map and feature-specific fetch helpers.
- state management structure: Plain JavaScript `state` object in `app/web/app.js`.
- styling/design system: Existing `home-card`, `decision-surface`, `decision-form`, `decision-table`, `decision-badge`, and `ghost-btn` patterns in `app/web/styles.css`.
- chart library: Inline SVG/HTML chart helpers in `app/web/app.js`; no new chart dependency.
- existing Quant Lab / FinGPT modules: `core/schemas/quant.py`, `pipelines/orchestration/quant_lab_pipeline.py`, `pipelines/factors`, `pipelines/signals`, `pipelines/backtest`, `app/api/routers/quant_lab.py`.
- existing price data provider: SQLite data mart `prices_daily` via `pipelines.data_mart.storage.repository.get_prices`; no synthetic fallback prices were added.
- existing universe provider: `core.utils.symbol_registry`, AI Portfolio universe templates, Quant Lab universe resolver.
- existing backtest module: `pipelines/backtest/engine.py`, metrics, artifacts, export/replay support. ML Forecast uses a separated forecast-signal backtester.
- existing AI/LLM integration module: `pipelines/infer/runner_factory.py`, Ollama adapter, prompt helpers. ML Forecast MVP uses deterministic fallback interpretation.
- existing Macro integration point: `app/api/routers/macro.py`, `pipelines/macro/macro_service.py`, `pipelines/macro/research_context.py`.
- existing AI Portfolio integration point: `app/api/routers/ai_portfolio.py`, `pipelines/ai_portfolio/service.py`, local store.
- existing storage/database/file persistence layer: data mart SQLite, AI Portfolio SQLite/JSON, Quant Lab artifacts. ML Forecast stores experiment JSON, signed model artifact JSON, macro regime JSON, and SQLite registry/audit data under `data/forecast_lab`.
- existing test/build/lint commands: `python -m pytest`, `node --check app\web\app.js`, `python scripts\check_ui_contract.py`, `python -m core.preflight`.
- ML/forecast related existing code: Only legacy archived forecaster under `legacy/archive/fingpt/FinGPT_Forecaster`; no active ML Forecast Lab found.
- existing visualization components: Inline SVG renderers in `app/web/app.js`.

## 2. Architecture Decision
- Status: DONE, including previously partial optional integration surfaces.
- selected backend module structure: `core/schemas/forecast.py`, `pipelines/forecast/*`, `app/api/routers/forecast.py`.
- selected frontend module structure: Existing static dashboard extended in `app/web/index.html`, `app/web/app.js`, `app/web/styles.css`.
- data loader design: Load adjusted daily price and benchmark bars from the data mart. Missing live data returns controlled unavailable/insufficient responses.
- feature engineering design: Return, momentum, volatility, trend, mean reversion, volume, and benchmark-relative features. Default `feature_shift=1`.
- target builder design: `forward_return`, `direction`, `volatility`, `excess_return`, `quantile_return`, and `triple_barrier_label` are implemented. Label/classification targets use OOS forward-return calibration before any expected-return display.
- leakage checker design: Checks random/KFold split, shuffle, feature shift, target-like features, purge, embargo, unavailable data, and 1-bar execution delay.
- validation design: Walk-forward default with expanding/rolling support, purge window, embargo, and compacted windows for short history.
- model trainer design: Baselines, scikit-learn regressors/classifiers, optional XGBoost/LightGBM, and optional PyTorch sequence model families. Missing optional packages are reported as unavailable instead of crashing the app.
- signal generator design: Converts structured ML outputs into advisory-only signals using expected return, probability, confidence, volatility, leakage, data quality, and trend/context filters.
- signal evaluator design: Uses out-of-sample predictions only.
- backtest design: Long/cash MVP, optional short-capable mapping interface, 1-bar delay, commission, slippage, spread, turnover, drawdown, benchmark comparison.
- visualization design: Backend returns a `VisualizationPayload`; frontend renders diagnostic charts or explicit unavailable states.
- model registry design: SQLite registry and audit trail at `data/forecast_lab/model_registry.sqlite3`, with legacy JSON migration support.
- experiment history storage: JSON experiments at `data/forecast_lab/experiments/{experiment_id}.json`; runtime artifacts are git-ignored.
- AI interpretation design: Korean deterministic fallback plus prompt template guardrails; optional Ollama-backed generation is guarded by numeric-grounding, decimal/percent equivalence, and advisory-only validators. Provider health and a live guarded provider call are verified; unsafe provider output still falls back.
- Macro tab connection: Historical FRED macro observations are hydrated into the data mart and exposed as shifted macro features; macro alignment/regime conflict is now passed into the signal context as a warning-only filter.
- AI Portfolio connection: Advisory-only portfolio signal endpoint exists; no auto rebalance.
- Universe forecast design: `ForecastUniverseRunRequest` resolves preset or custom universes, reuses the existing `ForecastRunRequest`/`predict()` path per asset, caps the synchronous run, preserves per-asset failures, and ranks advisory-only candidates by confidence, expected return, probability, signal score, or risk-adjusted score.
- live data fallback policy: No fake values. Return unavailable/insufficient/failed with warnings and errors.
- future extension points: richer cross-asset regime modeling, purged combinatorial CV, queue-based long-running training, registry audit UI, and team-grade artifact key management.

## 3. Implementation Phases
- Phase 1: ML Forecast route/tab, page shell, experiment setup UI - Status: DONE
- Phase 2: dataset builder, price data loader, data quality model - Status: DONE
- Phase 3: feature engineering, target builder, leakage checks - Status: DONE
- Phase 4: baseline/ML model trainer, walk-forward validation - Status: DONE
- Phase 5: forecast output, model confidence, prediction intervals - Status: DONE
- Phase 6: signal generator, signal quality evaluator, signal-to-position mapping - Status: DONE
- Phase 7: backtest engine, financial metrics, transaction cost handling - Status: DONE
- Phase 8: visualization dashboard, forecast charts, signal charts, evaluation charts - Status: DONE
- Phase 9: explainability, feature importance, AI interpretation - Status: DONE
- Phase 10: experiment history, model registry, integration points - Status: DONE
- Phase 11: tests, validation, smoke checks, documentation - Status: DONE
- Priority continuation 2026-05-09: data snapshot governance, registry audit UI, and purged combinatorial CV diagnostics - Status: DONE
- Priority continuation 2026-05-11: async forecast jobs and experiment detail drawer - Status: DONE
- Priority continuation 2026-05-22: universe ML Forecast Lab, batch ranking, and UI placement - Status: DONE

## 4. Detailed Task Format

### [MF-001] Repository Inspection and Control Document
- Status: DONE
- Target Files:
  - docs/ML_FORECAST_IMPLEMENTATION_CHECKLIST.md
- Expected Behavior:
  - Track implementation and final verification state.
- Implementation Notes:
  - Repo structure and final reconciliation recorded here.
- Leakage / Bias Check:
  - N/A.
- Visualization Notes:
  - N/A.
- Verification Method:
  - file review
- Verification Command:
  - N/A
- Result Notes:
  - This document was updated after code, tests, and browser smoke verification.

### [MF-002] Backend Forecast Schemas and API Router
- Status: DONE
- Target Files:
  - core/schemas/forecast.py
  - app/api/routers/forecast.py
  - app/api/server.py
- Expected Behavior:
  - Forecast APIs expose controlled schemas and do not invent market data or model outputs.
- Implementation Notes:
  - Added Pydantic schemas, forecast router, and dual mount prefixes.
- Leakage / Bias Check:
  - Defaults use walk-forward validation, `shuffle=false`, purge, embargo, and 1-bar execution delay.
- Visualization Notes:
  - Visualization endpoint returns structured payload from actual experiment artifacts.
- Verification Method:
  - compile, pytest, API smoke
- Verification Command:
  - `python -m compileall core\schemas\forecast.py pipelines\forecast app\api\routers\forecast.py`
  - `python -m pytest tests\test_forecast_lab.py -q`
- Result Notes:
  - DONE. Targeted forecast test result after priority closure: 30 passed. Full-suite result is refreshed in the final verification section.

### [MF-003] Forecast Pipeline Services
- Status: DONE
- Target Files:
  - pipelines/forecast/
- Expected Behavior:
  - End-to-end dataset preview, features, targets, leakage check, training, forecast, signal, quality, backtest, visualization, explainability, registry, and integrations.
- Implementation Notes:
  - Pipeline outputs are traceable to data mart prices and configuration.
- Leakage / Bias Check:
  - Feature shift, purge, embargo, no random split, no shuffle, no same-bar execution.
- Visualization Notes:
  - Payload includes OOS predictions, prediction intervals, residuals, feature importance, equity/drawdown, position, signal history, fold metrics, model comparison, and data quality.
- Verification Method:
  - backend unit/API tests and browser smoke
- Verification Command:
  - `python -m pytest tests\test_forecast_lab.py -q`
- Result Notes:
  - DONE. Live SPY/QQQ horizon 20 `triple_barrier_label` run succeeded with macro availability `ok`, leakage `pass`, OOS-calibrated expected return, advisory signal, and stored visualization payload.

### [MF-004] ML Forecast Frontend Surface
- Status: DONE
- Target Files:
  - app/web/index.html
  - app/web/app.js
  - app/web/styles.css
  - scripts/check_ui_contract.py
- Expected Behavior:
  - Visible ML Forecast tab supports setup, preview, feature/leakage checks, training, forecast, signal, backtest, visualization, AI interpretation, history, and registry.
- Implementation Notes:
  - Extended existing static dashboard patterns and added cache-busted asset URLs.
- Leakage / Bias Check:
  - Leakage panel shows pass/warning/fail and recommendations.
- Visualization Notes:
  - Charts render from payload; unavailable data shows explicit empty states.
- Verification Method:
  - node syntax, UI contract, browser smoke
- Verification Command:
  - `node --check app\web\app.js`
  - `python scripts\check_ui_contract.py`
- Result Notes:
  - DONE. Browser smoke on fresh `http://host.docker.internal:8124/ui/?fresh=20260508calibrated#ml-forecast` verified tab visibility, Hydrate button, target options, successful train/forecast, OOS-calibrated label-target display, and visualization sections.

### [MF-005] Tests and Final Reconciliation
- Status: DONE
- Target Files:
  - tests/test_forecast_lab.py
  - docs/ML_FORECAST_IMPLEMENTATION_CHECKLIST.md
- Expected Behavior:
  - Tests cover key leakage, validation, signal, backtest, AI fallback, persistence, and API contracts.
- Implementation Notes:
  - Existing regression tests were preserved.
- Leakage / Bias Check:
  - Tests assert random/shuffle/same-bar/data-unavailable failures.
- Visualization Notes:
  - Tests assert visualization payload schema and live browser smoke confirmed rendered charts.
- Verification Method:
  - targeted and full pytest
- Verification Command:
  - `python -m pytest tests -q`
- Result Notes:
  - DONE. Targeted forecast and UI contract tests pass after the remaining ML Forecast hardening; full-suite result is refreshed in the final verification section.

### [MF-006] Optional Advanced Forecasting Extensions
- Status: DONE
- Target Files:
  - pipelines/forecast/models or future extension modules
- Expected Behavior:
  - Optional explainers, boosted-model dependencies, and PyTorch sequence models are controlled and do not break the app when dependencies are absent.
- Implementation Notes:
  - `scikit-learn` is a runtime dependency, so ridge/logistic/random-forest/gradient-boosting models are available in `venv311` and UI/API.
  - `xgboost`, `lightgbm`, and `torch` were installed in `venv311`, listed in `requirements-forecast-optional.txt`, exposed as available, and wired into train/forecast.
  - SHAP package absence no longer leaves the explainability chart partial: a deterministic model-agnostic Shapley occlusion approximation fills `shap_importance`, while real SHAP can still be added later as an optional enhancement.
  - LSTM/GRU/temporal CNN/transformer/TFT now train through a lightweight optional PyTorch sequence backend when `torch` is installed; otherwise they return controlled `torch_missing` errors instead of crashing.
- Leakage / Bias Check:
  - Future extensions must keep walk-forward/purge/embargo as defaults.
- Visualization Notes:
  - Current charts cover required MVP diagnostics, including monthly heatmap, confusion matrix, and realized-forward-return proxy regime performance.
- Verification Method:
  - unit tests, live API smoke, browser smoke
- Verification Command:
  - `python -m pytest tests\test_forecast_lab.py -q`
  - `POST /api/v1/forecast/train` with `xgboost`, `lightgbm`, and `lstm` on port 8130
- Result Notes:
  - DONE. XGBoost and LightGBM live train smoke returned `status=success`; Shapley fallback produced 15 explanation rows; LSTM live train smoke returned `status=success` with signed artifact integrity refs.

### [MF-007] Async Forecast Jobs and Experiment Detail Drawer
- Status: DONE
- Target Files:
  - `core/schemas/forecast.py`
  - `pipelines/forecast/jobs.py`
  - `app/api/routers/forecast.py`
  - `app/web/index.html`
  - `app/web/app.js`
  - `app/web/styles.css`
  - `scripts/check_ui_contract.py`
  - `tests/test_forecast_lab.py`
  - `tests/test_ui_routing_contract.py`
- Expected Behavior:
  - ML Forecast can submit long-running train/forecast runs as background jobs with persistent local status, structured errors, retry, and cancellation request visibility.
  - Experiment history can open a detail drawer that surfaces data snapshot, feature/target config, leakage, validation, artifact refs, registry, and audit context without requiring direct JSON file inspection.
- Leakage / Bias Check:
  - Job execution must reuse the existing `ForecastRunRequest` path, keeping walk-forward, purge/embargo, feature shift, advisory-only, and fail-closed data behavior unchanged.
- Visualization Notes:
  - UI additions must preserve the existing static `/ui/` dashboard patterns and provide loading, empty, failed, and success states.
- Verification Method:
  - schema/API unit tests, UI contract checks, JS syntax check, live API/browser smoke.
- Verification Command:
  - `python -m compileall -q core\schemas\forecast.py pipelines\forecast\jobs.py app\api\routers\forecast.py`
  - `node --check app\web\app.js`
  - `python scripts\check_ui_contract.py`
  - `python -m pytest tests\test_forecast_lab.py -q`
  - `python -m pytest tests\test_ui_routing_contract.py -q`
  - `python -m ruff check pipelines\forecast\jobs.py app\api\routers\forecast.py core\schemas\forecast.py tests\test_forecast_lab.py tests\test_ui_routing_contract.py scripts\check_ui_contract.py`
- Result Notes:
  - DONE. Added persistent SQLite forecast job storage, job submit/list/detail/cancel/retry API, UI Queue Job action, Forecast Jobs panel, and experiment detail drawer.
  - Live API smoke on fresh `http://127.0.0.1:8142` submitted `fj_e7a7d32eacbf46a6ae3d`; it completed `succeeded` with experiment `exp_e0b38904da258988cf7d`.
  - Browser smoke on `http://127.0.0.1:8142/ui/#ml-forecast` verified `Queue Job`, `Forecast Jobs`, job result link, experiment detail drawer with `Data Snapshot`, `Feature / Target / Validation`, `Registry Audit`, and zero console errors.

### [MF-008] Universe ML Forecast Lab
- Status: DONE
- Target Files:
  - `core/schemas/forecast.py`
  - `pipelines/forecast/service.py`
  - `app/api/routers/forecast.py`
  - `app/web/index.html`
  - `app/web/app.js`
  - `app/web/styles.css`
  - `scripts/check_ui_contract.py`
  - `scripts/ai_portfolio_ui_smoke.py`
  - `tests/test_forecast_lab.py`
  - `tests/test_ui_routing_contract.py`
- Expected Behavior:
  - ML Forecast supports both single-ticker deep analysis and a universe-level lab that applies the same model, target, validation, leakage, and advisory-only rules across a bounded custom or preset universe.
  - Results preserve failed/unavailable assets, expose data quality and leakage status per ticker, rank successful assets, and allow experiment detail drill-down for generated runs.
- Implementation Notes:
  - Added `POST /api/v1/forecast/universe/run`.
  - Presets reuse the shared AI Portfolio universe resolver; custom symbols reuse the shared symbol picker.
  - Synchronous UI default is capped to 6 assets and backend cap is 25 assets to avoid hiding long-running work in the request path.
- Leakage / Bias Check:
  - Each asset reuses the existing `ForecastRunRequest` path, keeping `feature_shift=1`, walk-forward validation, purge/embargo, and 1-bar delay unchanged.
- Visualization Notes:
  - The new card is placed after `Forecast Result` and before the full `Visualization Dashboard`, so universe ranking acts as a candidate-selection layer without displacing single-asset diagnostics.
- Verification Method:
  - compile, JS syntax, UI contract, targeted unit/API tests, browser smoke.
- Verification Command:
  - `python -m py_compile core\schemas\forecast.py pipelines\forecast\service.py app\api\routers\forecast.py`
  - `node --check app\web\app.js`
  - `python scripts\check_ui_contract.py --output reports\ui_contract_forecast_universe.json`
  - `python -m pytest tests\test_forecast_lab.py tests\test_ui_routing_contract.py -q`
- Result Notes:
  - DONE. Final command results are recorded in the current verification section below.

## 5. Backend Checklist
- forecast module/package creation: DONE
- schemas/types creation: DONE
- data loader: DONE
- price provider integration: DONE
- data snapshot id/source coverage hash: DONE
- dataset preview service: DONE
- feature engineering service: DONE
- target builder service: DONE
- leakage checker: DONE
- validation splitter: DONE
- baseline models: DONE
- ML models: DONE
- optional advanced models: DONE
- signed reproducible model artifact packaging: DONE
- trainer: DONE
- predictor: DONE
- universe forecast resolver/API: DONE
- evaluator: DONE
- forecast signal generator: DONE
- signal quality evaluator: DONE
- confidence scorer: DONE
- prediction interval estimator: DONE
- backtester: DONE
- visualization data API: DONE
- explainability service: DONE
- AI interpretation service: DONE
- experiment store: DONE
- async forecast job store: DONE
- model registry: DONE
- SQLite registry audit trail: DONE
- registry audit timeline UI: DONE
- registry artifact verification API: DONE
- promotion eligibility policy: DONE
- API routes: DONE
- error handling: DONE
- data quality handling: DONE

## 6. Frontend Checklist
- ML Forecast tab/route: DONE
- Forecast page shell: DONE
- Experiment setup panel: DONE
- Dataset Builder: DONE
- Feature Lab: DONE
- Target Builder: DONE
- Model Trainer panel: DONE
- Forecast Result panel: DONE
- Forecast Universe Lab panel: DONE
- Signal Generator panel: DONE
- Signal Quality panel: DONE
- Backtest Result panel: DONE
- Model Evaluation panel: DONE
- Visualization Dashboard: DONE
- Explainability panel: DONE
- AI Interpretation panel: DONE
- Experiment History panel: DONE
- Forecast Jobs panel: DONE
- Experiment Detail drawer: DONE
- Model Registry panel: DONE
- Leakage Check panel: DONE
- loading states: DONE
- error states: DONE
- insufficient data states: DONE
- leakage warning states: DONE
- validation result states: DONE

## 7. ML/Finance Checklist
- forward return target: DONE
- direction target: DONE
- volatility target: DONE
- quantile return target: DONE
- excess return target: DONE
- triple barrier label: DONE
- feature shift: DONE
- no random split: DONE
- walk-forward validation: DONE
- purged combinatorial CV diagnostic: DONE
- purge window: DONE
- embargo option: DONE
- transaction cost: DONE
- slippage: DONE
- turnover: DONE
- benchmark comparison: DONE
- out-of-sample metrics: DONE
- overfitting warning: DONE
- model confidence score: DONE
- signal score: DONE
- signal quality metrics: DONE
- signal-to-position mapping: DONE
- 1-bar execution delay: DONE

## 8. Visualization Checklist
- price chart with signal overlay: DONE
- forecast cone / prediction interval chart: DONE
- actual vs predicted chart: DONE
- residual chart: DONE
- prediction distribution chart: DONE
- feature importance chart: DONE
- permutation importance chart: DONE
- optional SHAP/Shapley importance chart: DONE
- equity curve chart: DONE
- drawdown chart: DONE
- rolling Sharpe chart: DONE
- monthly return heatmap: DONE
- signal history chart: DONE
- position exposure chart: DONE
- turnover chart: DONE
- confusion matrix for classification target: DONE
- walk-forward fold performance chart: DONE
- regime-specific performance chart: DONE
- data quality / missing value visualization: DONE
- model comparison chart: DONE

## 9. Signal Generator Checklist
- forecast-to-signal conversion: DONE
- signal thresholds: DONE
- probability threshold: DONE
- confidence threshold: DONE
- volatility filter: DONE
- trend filter: DONE
- regime filter: DONE
- signal smoothing: DONE
- signal cooldown: DONE
- position sizing: DONE
- long/cash mapping: DONE
- optional long/short mapping: DONE
- signal quality metrics: DONE
- signal explanation: DONE
- advisory-only portfolio signal: DONE

## 10. AI Layer Checklist
- forecast explanation prompt: DONE
- signal explanation prompt: DONE
- model diagnostic prompt: DONE
- backtest interpretation prompt: DONE
- feature importance explanation prompt: DONE
- risk scenario explanation prompt: DONE
- visualization summary prompt: DONE
- research context summary prompt: DONE
- no invented numeric outputs: DONE
- no future price certainty: DONE
- structured ML output only: DONE
- no manipulated metrics: DONE
- signal/model limitations stated: DONE
- leakage/validation state mentioned: DONE
- no direct buy/sell order instruction: DONE
- provider-backed LLM call: DONE
- provider health/status check: DONE
- provider latency fail-closed policy: DONE
- validation gate provider policy check: DONE

## 11. Testing and Verification Checklist
- backend unit tests: DONE
- frontend tests or manual verification: DONE
- API smoke tests: DONE
- leakage tests: DONE
- walk-forward split tests: DONE
- feature/target alignment tests: DONE
- signal generator tests: DONE
- signal-to-position tests: DONE
- backtest tests: DONE
- visualization data schema tests: DONE
- model trainer tests: DONE
- lint/syntax: DONE
- build/UI contract: DONE
- existing app regression check: DONE

## 12. Acceptance Criteria Checklist
- ML Forecast tab/page is visible: DONE
- ticker input/select works: DONE
- dataset preview works: DONE
- feature group selection path exists: DONE
- target setting works: DONE
- model selection works and disables unavailable models: DONE
- scikit-learn ML models are available in the supported `venv311` runtime: DONE
- train/forecast API exists: DONE
- random split is not the default: DONE
- leakage check exists: DONE
- walk-forward validation exists: DONE
- forecast result displays: DONE
- prediction interval/uncertainty displays: DONE
- model confidence displays: DONE
- signal generator exists: DONE
- signal quality displays: DONE
- backtest result displays: DONE
- transaction cost setting/default exists: DONE
- key visualization charts exist: DONE
- universe ML ranking exists: DONE
- AI interpretation uses structured ML output only: DONE
- experiment history is saved: DONE
- data snapshot artifact is saved: DONE
- model registry exists: DONE
- Macro/AI Portfolio connection points exist: DONE
- existing FinGPT/Quant Lab features not broken by tests: DONE
- verification results recorded in this file: DONE

## 13. Final Completion Summary

| Area | DONE | PARTIAL | BLOCKED | NOT_DONE | Notes |
|---|---:|---:|---:|---:|---|
| Repository Inspection | 1 | 0 | 0 | 0 | Repo surfaces recorded. |
| Architecture | 20 | 0 | 0 | 0 | Provider health, live guarded provider call, optional model boundaries, and signed artifact integrity are implemented. |
| Backend | 35 | 0 | 0 | 0 | Scikit-learn MVP models, XGBoost/LightGBM, optional PyTorch sequence models, signed artifacts, universe forecast ranking, permutation importance, and Shapley fallback are done. |
| Frontend | 27 | 0 | 0 | 0 | Browser smoke verified, including provider health, drift/model comparison, registry actions, visualization, and universe ranking surface. |
| Data Loader | 5 | 0 | 0 | 0 | Data mart plus yfinance/FRED hydrate API; no fake prices. |
| Feature Engineering | 8 | 0 | 0 | 0 | Macro features use historical FRED observations with timestamp alignment. |
| Target Builder | 6 | 0 | 0 | 0 | Forward, direction, volatility, excess, quantile, triple barrier. |
| Validation | 6 | 0 | 0 | 0 | Walk-forward, purge, embargo, and purged combinatorial CV diagnostic. |
| Models | 11 | 0 | 0 | 0 | Baseline, scikit-learn MVP models, XGBoost/LightGBM, and PyTorch LSTM/GRU/Temporal CNN/Transformer/TFT paths are available in `venv311`. |
| Forecast | 9 | 0 | 0 | 0 | Expected return, probability, intervals, confidence; label targets use OOS return calibration. |
| Signal Generator | 14 | 0 | 0 | 0 | Regime conflict is warning-only by design and does not flip signals. |
| Backtest | 10 | 0 | 0 | 0 | OOS, 1-bar delay, costs, benchmark. |
| Visualization | 19 | 0 | 0 | 0 | Permutation and Shapley/SHAP-compatible importance charts render from experiment payloads. |
| AI Layer | 13 | 0 | 0 | 0 | Deterministic fallback plus guarded Ollama provider path; live grounded provider call passed. |
| Experiment History | 2 | 0 | 0 | 0 | Runtime artifacts and local signing key are git-ignored. |
| Model Registry | 4 | 0 | 0 | 0 | Promote/deprecate endpoints and UI actions verified. |
| Integrations | 5 | 0 | 0 | 0 | Macro context, advisory portfolio signal, and research context endpoints exist. |
| Tests | 25 | 0 | 0 | 0 | Targeted tests after continuation passed; full suite result is refreshed below. |
| Acceptance Criteria | 27 | 0 | 0 | 0 | Core, optional-runtime, and universe forecast acceptance items are done; remaining roadmap items are enhancement work, not open implementation gaps. |

### Commands Executed
- 2026-05-22 universe continuation: `python -m py_compile core\schemas\forecast.py pipelines\forecast\service.py app\api\routers\forecast.py`
- 2026-05-22 universe continuation: `node --check app\web\app.js`
- 2026-05-22 universe continuation: `python scripts\check_ui_contract.py --output reports\ui_contract_forecast_universe.json`
- 2026-05-22 universe continuation: `python -m pytest tests\test_forecast_lab.py tests\test_ui_routing_contract.py -q`
- 2026-05-22 universe continuation: restarted `http://127.0.0.1:8000` with `scripts\run_web.ps1`; `/api/v1/health` and `/ui/` returned 200.
- 2026-05-22 universe continuation: live API smoke `POST /api/v1/forecast/universe/run` with custom `MSFT`, `historical_mean`, `max_assets=1`.
- 2026-05-22 universe continuation: Playwright browser smoke on `http://127.0.0.1:8000/ui/?v=20260522-forecast-universe-v1#ml-forecast`, executed `Run Universe ML`, and saved `reports\forecast_universe_smoke.png`.
- 2026-05-22 universe continuation: `python scripts\ai_portfolio_ui_smoke.py --base-url http://127.0.0.1:8000 --timeout-s 180 --output reports\ai_portfolio_ui_smoke_forecast_universe.json`
- `python -m compileall core\schemas\forecast.py pipelines\forecast app\api\routers\forecast.py pipelines\data_mart\storage\repository.py`
- `python -m compileall app core pipelines scripts`
- `node --check app\web\app.js`
- `python -m pytest tests\test_forecast_lab.py -q`
- `python -m pytest tests\test_validation_gate.py -q`
- `python -m pytest tests\test_forecast_lab.py tests\test_validation_gate.py -q`
- `python -m pytest tests\test_ui_routing_contract.py tests\test_forecast_lab.py -q`
- `python -m pytest tests\test_quant_lab_api.py tests\test_api_routing_contract.py tests\test_ui_routing_contract.py tests\test_forecast_lab.py -q`
- `python -m pytest tests -q`
- `python -m pytest .\tests -q`
- `python scripts\check_ui_contract.py`
- `python -m core.preflight`
- `python -m pip check`
- `venv311\Scripts\python.exe -m pip check`
- `python -m ruff check pipelines\forecast app\api\routers\forecast.py core\schemas\forecast.py tests\test_forecast_lab.py`
- `python -m ruff check scripts\validation_gate.py tests\test_validation_gate.py pipelines\forecast app\api\routers\forecast.py core\schemas\forecast.py tests\test_forecast_lab.py tests\test_ui_routing_contract.py`
- `venv311\Scripts\python.exe -m pip install "scikit-learn>=1.4.0,<2.0.0"`
- `venv311\Scripts\python.exe -m pip install "xgboost>=2.0.0,<4.0.0" "lightgbm>=4.0.0,<5.0.0"`
- `venv311\Scripts\python.exe -m pip install "torch>=2.2,<3"`
- `venv311\Scripts\python.exe -m pytest tests\test_forecast_lab.py -q`
- `python scripts\validation_gate.py --browser-ui-timeout 180`
- `python scripts\validation_gate.py`
- `python -m pytest tests/test_ui_routing_contract.py tests/test_forecast_lab.py -q`
- `python quality_review.py --suite all --case-limit 2 --output data\outputs\quality_review_ml_forecast_sample.json`
- Live API smoke on fresh port 8130: `/api/v1/forecast/models` verified ridge/logistic/random-forest/gradient-boosting availability in `venv311`.
- Live API smoke on fresh port 8130: `POST /api/v1/forecast/train` with `ridge_regression` returned `status=success`, model artifact JSON, and permutation importance rows.
- Live API smoke on fresh port 8130: `POST /api/v1/forecast/train` with `xgboost` and `lightgbm` returned `status=success`, model artifacts, permutation importance rows, and Shapley fallback rows.
- Live API smoke on fresh port 8130: `POST /api/v1/forecast/train` with `lstm` returned `status=success`, signed artifact integrity manifest, and verified SHA-256/HMAC checks.
- Live AI provider smoke: `generate_ai_interpretation(..., use_llm=True, timeout_s=90)` returned `status=success`, `provider=ollama:qwen2.5:7b`, and `numeric_grounding_guard_passed`.
- Browser smoke on port 8130: ML Forecast registry deprecate/promote UI actions changed model status without console errors.
- Data hydrate command: `update_prices_daily(["SPY","QQQ","MSFT","TLT","GLD","AAPL","NVDA"], start_date="2021-05-09")`
- Macro hydrate command: `update_macro_daily(("DGS2","DGS10","T10Y2Y","DFF","CPIAUCSL","DTWEXBGS","VIXCLS"), start_date=<5y lookback>)`
- API smoke: `TestClient(app).post("/api/v1/forecast/train", ...)` with SPY/QQQ, macro, cross-asset, `triple_barrier_label`, walk-forward, smoothing/cooldown.
- Live API smoke on fresh port 8126: `/health`, `/models`, `/model-comparison`, `/drift/check`, `/batch-predict`.
- Fresh server: `python -m uvicorn app.api.server:app --host 0.0.0.0 --port 8124`
- Fresh server: `powershell -ExecutionPolicy Bypass -File scripts\run_web.ps1` with `FINGPT_WEB_PORT=8126`
- Browser smoke: `http://host.docker.internal:8124/ui/?fresh=20260508calibrated#ml-forecast`
- Browser smoke: `http://127.0.0.1:8126/ui/?fresh=20260508current#ml-forecast`

### Test Results
- 2026-05-22 universe continuation: py_compile passed for forecast schema, service, and router.
- 2026-05-22 universe continuation: `node --check app\web\app.js` passed.
- 2026-05-22 universe continuation: UI contract passed with `missing_markers: []`; output saved to `reports\ui_contract_forecast_universe.json`.
- 2026-05-22 universe continuation: targeted pytest passed, `78 passed, 4 subtests passed`.
- 2026-05-22 universe continuation: live API smoke returned `status=success`, `count=1`, selected `MSFT`, first item `MSFT/success`.
- 2026-05-22 universe continuation: Playwright UI smoke found the Forecast Universe Lab, rendered `MSFT` ranking table, and reported zero console errors.
- 2026-05-22 universe continuation: cross-dashboard smoke passed with zero console errors; output saved to `reports\ai_portfolio_ui_smoke_forecast_universe.json`.
- compileall: passed.
- `node --check app\web\app.js`: passed.
- `python -m ruff check pipelines\forecast app\api\routers\forecast.py core\schemas\forecast.py tests\test_forecast_lab.py`: passed.
- `tests/test_forecast_lab.py`: 32 passed after data snapshot and purged CV continuation.
- `venv311\Scripts\python.exe -m pytest tests\test_forecast_lab.py -q`: 27 passed before priority closure; current ambient runtime forecast suite is 30 passed.
- `tests/test_ui_routing_contract.py tests/test_forecast_lab.py`: 55 passed.
- route/API/UI targeted subset: 68 passed.
- full suite after continuation: 557 passed, 3 subtests passed.
- UI contract: passed, `missing_markers: []`.
- preflight: all critical dependencies operational. Qdrant, OpenBB package policy, Yahoo/SEC, Ollama service and `qwen2.5:7b` passed; FRED macro returned a non-critical upstream 500 warning and macro runs should use fallback proxies when that recurs.
- default `pip check` and `venv311` `pip check`: no broken requirements found.
- validation gate: `python scripts\validation_gate.py` exited 0 and `data/outputs/validation_latest.json` recorded `automated_passed=true` with runtime, code, model baseline, provider compatibility, forecast AI provider policy, OpenBB agent contract, UI contract, infrastructure, skipped live-smoke, and skipped browser UI phases.
- quality review sample: gate failures `0`; 2 cases ended `partial` because local LLM timed out and deterministic fallback was used.

### Data Saved
- Price data saved in `data/research_mart.db` / `prices_daily`: SPY, QQQ, MSFT, TLT, GLD, AAPL, NVDA each have 1,255 rows from 2021-05-10 through 2026-05-07.
- Macro data saved in `data/research_mart.db` / `macro_observations`: DGS2 latest 2026-05-06, DGS10 latest 2026-05-06, T10Y2Y latest 2026-05-07, DFF latest 2026-05-06, CPIAUCSL latest 2026-03-01, DTWEXBGS latest 2026-05-01, VIXCLS latest 2026-05-06.
- Data mart counts after hydration: `prices_daily=202972`, `macro_observations=74603`.
- New forecast runs save `data_snapshot` payloads with `data_snapshot_id`, `source_coverage_hash`, price/benchmark coverage hashes, macro coverage, and feature schema hash under `data/forecast_lab/data_snapshots/`.

### API and Browser Smoke Result
- API smoke: `status=success`, `prediction_type=triple_barrier_label`, macro availability `ok`, leakage `pass`, no warnings, monthly heatmap length `25`, stored confusion matrix and regime-performance rows present.
- Live API smoke on 8126: forecast health `ok`, model count `13`, model comparison `success`, drift check `success` with `drift_status=fail` for the latest QQQ sample because recent OOS directional accuracy degraded and recent MAE increased, batch prediction `success` for SPY and QQQ with two successful advisory forecasts.
- Browser smoke: fresh 8124 server, SPY/QQQ, horizon 20, `triple_barrier_label`, `historical_mean`, macro/cross-asset enabled.
- Browser result: success; result panel showed `Target=triple_barrier_label`, `Expected return (OOS calibrated)=1.53%`, probability up `75.27%`, interval `-1.41% / 1.53% / 4.02%`, confidence `0.843 high`.
- Browser signal: `moderate_bullish`, advisory only, volatility filter warning visible.
- Browser visualization: monthly return heatmap, confusion matrix, and regime-performance sections rendered.
- Browser smoke on fresh 8126 current code: dataset preview `ok`, 1,255 rows, 0.00% missing; feature build generated 30 shifted features; train/forecast produced `exp_5ea500a99d2123014b39`, expected return `0.25%`, probability up `51.92%`, confidence `0.687 medium`, neutral advisory-only signal.
- Browser smoke on fresh 8130 current code: `/api/v1/health` returned build id `298084268167`; ML Forecast showed ridge/logistic/random-forest/gradient-boosting models as available; provider health showed Ollama `qwen2.5:7b` and `numeric_grounding_and_advisory_only`; drift/model comparison sections rendered; model registry deprecate/promote UI actions both updated the row state with no console errors.
- Live ridge smoke on 8130: `POST /api/v1/forecast/train` with SPY/QQQ and `ridge_regression` returned `status=success`, model `mlf_87bdd113fd257bbe`, expected return `0.00136526`, confidence `0.513845`, neutral signal, model artifact under `data/forecast_lab/model_artifacts`, and 15 permutation-importance rows.
- Browser smoke on fresh 8130 after optional model closure: `xgboost`, `lightgbm`, and `lstm` showed as enabled model options with no console error/warning entries.
- Browser smoke on current 8130 after priority closure: `#ml-forecast` route rendered, registry surface existed, 11 artifact verify buttons were present, one legacy row showed controlled integrity failure, and a signed LSTM artifact verified `Integrity success / SHA-256 match / Bytes match / Signature match` with no console errors.
- Continuation API/unit verification: forecast train payload now includes `data_snapshot`, experiment list includes `data_snapshot_id`, signed model artifact embeds the same snapshot id/hash, registry UI renders `Registry Audit`, and `walk_forward_plus_purged_cv` adds purged combinatorial CV diagnostics without replacing walk-forward OOS backtest.
- Browser smoke on fresh 8131 after continuation: ML Forecast route rendered, `walk_forward_plus_purged_cv` option existed, Preview Dataset showed `Data Snapshot: ds_3340ae9f482a8ffb588c` and coverage hash, registry audit timeline rendered, 11 verify buttons were present, and console errors were empty.
- Live XGBoost smoke on 8130: `status=success`, model `mlf_35a5106896dc1cdb`, 15 permutation-importance rows, 15 Shapley fallback rows, neutral signal, and expected warning `selected_model_underperformed_baseline`.
- Live LightGBM smoke on 8130: `status=success`, model `mlf_6dbc1707b182f7d1`, 15 Shapley fallback rows, and expected warning `selected_model_underperformed_baseline`.
- Live LSTM smoke on 8130: `status=success`, model `mlf_6d01e99657db962d`, expected return `-0.01853377`, confidence `0.496472`, neutral advisory signal, artifact SHA-256 `fe01fff4efa3c5eee0c1cdab508da2e023c3eb3a9c3159093294e822fbab2564`, and integrity verification `success`.

### Failed or Limited Verification
- MCP Docker browser initially saw a stale app on `host.docker.internal:8014`; a fresh validation server was started on port 8124 and later a current-code server on 8126.
- A stale port-8124 process returned 404 for new `/model-comparison` and `/drift/check` endpoints; the refreshed current-code server passed the same live API smoke.
- The validation gate's built-in browser UI phase is skipped unless live-smoke or release-candidate mode is used; separate Browser/Playwright verification was completed.
- Provider-backed LLM interpretation previously fell back on timeout/grounding issues; after decimal/percent guard correction and prompt hardening, a bounded live provider call passed. Ungrounded provider output still falls back by design.

### Operational Limits and Follow-up Work
- Provider-backed AI interpretation is DONE for guarded local usage. It is still intentionally fail-closed: timeout, direct-order language, or ungrounded numbers return deterministic fallback.
- Deep sequence training is now implemented through the optional PyTorch backend. Production-grade deep learning governance remains an enhancement area: early stopping, calibrated intervals, GPU/CPU budget controls, queue-based long-running jobs, and promotion thresholds.
- Signed reproducible metadata artifacts are implemented. Team deployments should replace the local generated signing key with `FORECAST_ARTIFACT_SIGNING_KEY` or a KMS-backed key rotation policy.
- Richer multi-asset regime modeling remains an enhancement roadmap item, not an open PARTIAL/BLOCKED/NOT_DONE implementation item.

### Changed Files
- `.gitignore`
- `app/api/server.py`
- `app/api/routers/system.py`
- `app/api/routers/forecast.py`
- `app/web/index.html`
- `app/web/app.js`
- `app/web/styles.css`
- `core/schemas/forecast.py`
- `core/utils/build_info.py`
- `docs/ML_FORECAST_IMPLEMENTATION_CHECKLIST.md`
- `docs/ML_FORECAST_DEEP_VERIFICATION_AND_ADVANCEMENT_PLAN.md`
- `pipelines/data_mart/storage/repository.py`
- `pipelines/forecast/__init__.py`
- `pipelines/forecast/ai_interpretation.py`
- `pipelines/forecast/backtester.py`
- `pipelines/forecast/common.py`
- `pipelines/forecast/confidence.py`
- `pipelines/forecast/data_loader.py`
- `pipelines/forecast/diagnostics.py`
- `pipelines/forecast/evaluator.py`
- `pipelines/forecast/experiment_store.py`
- `pipelines/forecast/explainability.py`
- `pipelines/forecast/feature_engineering.py`
- `pipelines/forecast/integrations/__init__.py`
- `pipelines/forecast/integrations/macro_context.py`
- `pipelines/forecast/integrations/portfolio_signal.py`
- `pipelines/forecast/integrations/research_context.py`
- `pipelines/forecast/jobs.py`
- `pipelines/forecast/leakage.py`
- `pipelines/forecast/modeling.py`
- `pipelines/forecast/registry_policy.py`
- `pipelines/forecast/signal_evaluator.py`
- `pipelines/forecast/signal_generator.py`
- `pipelines/forecast/target_builder.py`
- `pipelines/forecast/validation.py`
- `pipelines/forecast/visualization.py`
- `requirements.txt`
- `requirements-forecast-optional.txt`
- `scripts/check_ui_contract.py`
- `scripts/validation_gate.py`
- `tests/test_forecast_lab.py`
- `tests/test_ui_routing_contract.py`
- `tests/test_validation_gate.py`
