# Quant Lab Advancement Implementation Checklist

Scope: extend the existing FinGPT-native Quant Lab at `/ui/#quant-lab` without replacing the deterministic engine or adding a parallel quant stack.

## Implementation Items

| ID | Item | Files | Acceptance | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| QLA-1 | Reconfirm current Quant Lab baseline | `app/web/app.js`, `app/api/routers/quant_lab.py`, `pipelines/orchestration/quant_lab_pipeline.py` | Existing run history, replay, export, and strategy governance surfaces remain intact. | DONE | Baseline inspection found manifest lineage and replay helpers already present. |
| QLA-2 | Add run-context summary to the backtest result surface | `app/web/app.js` | Backtest results and reopened artifacts show strategy, universe, freshness, cost, lineage, and data snapshot context. | DONE | `data-testid="quant-run-context"` is rendered after opening a saved run or completing a backtest. |
| QLA-3 | Add two-run comparison backend | `pipelines/orchestration/quant_lab_pipeline.py`, `app/api/routers/quant_lab.py` | API compares two saved runs without mutating artifacts and returns metric deltas, config differences, diagnostics, and lineage. | DONE | Added `POST /api/v1/quant/backtests/compare` and read-only pipeline comparison. |
| QLA-4 | Add run-history compare workflow in the Quant Lab UI | `app/web/app.js`, `scripts/check_ui_contract.py`, `tests/test_ui_routing_contract.py` | Operator can select exactly two saved runs and render a comparison table from the UI. | DONE | Run history now has compare checkboxes, selection state, and comparison rendering. |
| QLA-5 | Add focused API/pipeline/UI contract tests | `tests/test_quant_lab_pipeline.py`, `tests/test_quant_lab_api.py`, `tests/test_ui_routing_contract.py` | Targeted Quant Lab tests pass. | DONE | `49 passed` for Quant Lab API, pipeline, and UI routing contract tests. |
| QLA-6 | Verify live UI on `127.0.0.1:8002` or a fresh local server | `scripts/quant_lab_ui_smoke.py` | Browser smoke or targeted Playwright check confirms no console errors and visible compare controls. | DONE | Full Quant Lab Playwright smoke passed on `8002` with run compare, cross-run cleanup preview, and `console_errors=[]`; targeted Playwright also rendered `quant_lab_run_compare_v1`. |
| QLA-7 | Auto-refresh stale Quant Lab price dependencies | `app/api/routers/quant_lab.py`, `app/web/app.js` | Universe preflight can hydrate missing prices, refresh stale selected assets and benchmarks, and fail closed when `decision_review` still has stale data. | DONE | `POST /api/v1/quant/universe/resolve` returns freshness policy, asset audit, stale assets, strict violation state, and stale refresh metadata. |
| QLA-8 | Audit benchmark data used by feature/signal previews | `pipelines/orchestration/quant_lab_pipeline.py`, `tests/test_quant_lab_pipeline.py` | Relative-strength benchmark prices are included in freshness diagnostics, warnings, and strict freshness checks. | DONE | Feature preview diagnostics now include benchmark latest dates and stale status even when the benchmark is not a selected row. |
| QLA-9 | Extend freshness contract to asset detail and portfolio optimization | `app/api/routers/data.py`, `app/api/routers/portfolio.py`, `app/web/app.js` | Asset-detail price reads expose freshness audit fields; portfolio optimization includes selected assets plus benchmark in strict freshness validation. | DONE | Direct API calls now return freshness policy, asset audit, latest dates, stale assets, and strict violation state instead of relying only on UI preflight. |
| QLA-10 | Add risk-adjusted momentum strategy path | `pipelines/factors/*`, `pipelines/backtest/engine.py`, `pipelines/orchestration/quant_lab_pipeline.py`, `app/web/app.js`, `app/web/index.html` | Quant Lab exposes a deterministic `risk_adjusted_momentum_63d` factor and `risk_adjusted_momentum` template without changing existing strategy behavior. | DONE | Factor preview, signal matrix, backtest API, browser UI, and full pytest passed on 2026-05-19. |

## Guardrails

- Do not make Qlib a default runtime dependency.
- Do not let an LLM decide portfolio weights or execution actions.
- Keep saved artifacts under `data/quant_lab/backtests/{run_id}`.
- Treat stale or partial data as visible decision context, not as silent success.
- Preserve the existing static `/ui/` architecture.

## Latest Freshness Verification

- Local refresh for `SPY`, `TLT`, `GLD`, and `QQQ` inserted or updated provider-backed rows through `2026-05-15`.
- `decision_review` validation reported `strict_freshness_violation=false`; each default asset had latest price date `2026-05-15` and market-calendar lag `0`.
- Targeted checks: `python -m pytest tests\test_quant_lab_api.py tests\test_quant_lab_pipeline.py -q`, `python -m pytest tests\test_data_mart_api.py tests\test_portfolio_optimizer.py -q`, `python -m pytest tests\test_ui_routing_contract.py tests\test_ui_modules.py -q`, `python scripts\check_ui_contract.py`, and live browser smoke on `http://127.0.0.1:8247/ui/#quant`.
