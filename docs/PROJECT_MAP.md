# Project Map

This document outlines the main directories and their responsibilities.

- `app/`
  - `cli/`: Contains CLI implementations mapping arguments into request objects.
  - `api/`: Scaffold area strictly intended for exposing the identical pipeline over REST via FastAPI/Flask in the future.
- `core/`
  - `config/`: Configuration rules mapping `.env` and hardcoded project limits into typed configurations (`Settings`).
  - `schemas/`: Structured request and response boundaries (Pydantic), including optional scenario simulation contracts.
  - `prompts/`: Isolated text layouts to decouple string building from Python parsing.
  - `utils/`: Common cross-cutting helpers (e.g. data normalization).
- `pipelines/`
  - `collect/`: Source-aware collection logic for Yahoo Finance news and direct FMP transcripts.
  - `ingest/`: Embedding extraction and Qdrant ingestion rules.
  - `retrieve/`: Query embeddings and semantic cosine similarity search methods.
  - `infer/`: Logic for handling different LLMs (`FinGPTAdapter`, `RunnerFactory`).
  - `analyze/`: Deterministic data manipulation post-LLM extraction (e.g., sentiment parsing, mapping confidence).
  - `macro/`: Macro registry, providers, dashboard aggregation, provider-health reporting, advisory-only scenario analysis, regime/asset-impact/portfolio-hint services, and research-context integration.
  - `risk/`: Enterprise-macro risk orchestration, Quantamental company adapters, Macro adapters, data-quality policy, transmission modeling, scenario matrix, and weighted aggregation.
  - `simulate/`: Optional default-off scenario simulation layer for evidence-grounded base/bull/bear/tail cases, personas, debate views, risk triggers, and deterministic scores.
  - `orchestration/`: Binds all the preceding modules into an end-to-end operational execution pipe (`research_pipeline.py`).
- `data/`: Outputs, storage, raw ingested chunks, and DB results.
- `reports/`: Evaluated reports and latest analysis summaries.
- `scripts/`: Operational and validation scripts, including `macro_ui_smoke.py` for static Macro tab browser verification and `check_ui_contract.py` for static dashboard contract coverage.
- `tests/`: Project test suite, including production and unit tests.
- `legacy/`: Consolidated area for research validation, archived stack versions, and experiments.

Key Risk workbench files:

- `core/schemas/risk.py`: typed API contracts for Risk workbench requests and responses, including the input receipt, decision brief, consolidated decision path, decision-quality summary, decision compass, evidence-coverage matrix, compatibility matrix, AI output guardrails, action checklist, monitoring triggers, priority map, confidence-factor ladder, ML validation tests with Forecast prefill links, Forecast validation plan, structured service-readiness gate, run-lineage packet, and release packet.
- `core/schemas/forecast.py`: ML Forecast requests include `ForecastSourceContext`, preserving Risk-originated validation test id, input hash, test type, label, and priority through train/job requests.
- `app/api/routers/risk.py`: FastAPI routes under `/api/v1/risk`.
- `pipelines/risk/aggregation.py`: score direction, weights, input hashes, concentration penalty, and driver contribution helpers.
- `pipelines/risk/service.py`: orchestration layer that combines company, macro, transmission, scenario, data-quality, input-receipt, decision-brief, decision-path, decision-quality, decision-compass, evidence-coverage, compatibility-matrix, AI-output-control, action-checklist, monitoring-trigger, priority-map, confidence-factor, ML-validation-test, Forecast validation plan, ML Forecast launch-prefill, run-lineage, service-readiness, and release-packet outputs.
- `pipelines/risk/company.py`: adapter over Quantamental analysis output; no duplicate SEC, fundamental, or quant calculations. It also marks ETF/macro-proxy symbols as limited asset-proxy risk subjects when price evidence exists.
- `pipelines/risk/macro.py`: adapter over Macro dashboard output.
- `pipelines/risk/data_quality.py`: fail-closed data-quality and confidence policy, including non-blocking missing-fundamental handling for supported asset proxies.
- `pipelines/risk/transmission.py`: deterministic macro-to-company transmission channels.
- `pipelines/risk/scenario.py`: deterministic stress scenario matrix.
- Risk responses expose `input_receipt`, `decision_brief`, `decision_path`, `decision_quality`, `decision_compass`, `evidence_coverage`, `compatibility_matrix`, `ai_output_controls`, `priority_map`, `confidence_factors`, `handoff_queue`, `ml_validation_tests`, `forecast_validation_plan`, `run_lineage`, and `release_packet` so clients can show normalized inputs, review questions, the top action/workflow path, first-flow quality status, a compact user workflow, coverage by input/company/macro/scenario/Forecast/service/evidence domain, per-subject workflow compatibility gates, model-output guardrails, priority risk cells, confidence-score reasons, next workflow handoffs, ML Forecast experiment recommendations with direct prefill URLs, a selected Forecast test plan with controls and acceptance criteria, blocked reasons, service notes, replay fields, adapter status, evidence/freshness counts, and deployability checks from the same typed contract.
