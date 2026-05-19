# Runbook

## Production Baseline
- Inference backend: Ollama
- Production primary: `qwen2.5:7b`
- Experimental fallback: `gemma4:e4b`
- Experimental fallback policy: disabled by default; do not enable on the production path unless explicitly re-running experiments
- Supported local vector-store baseline: Docker Desktop-managed Qdrant via `compose.yaml`
- Collection baseline: Yahoo/yfinance `news`, SEC EDGAR filings, Google News RSS, FRED macro series, and yfinance price history. OpenBB news is compatibility-gated and opt-in. Alpha Vantage news is an additional key-backed fallback behind the primary chain. FMP stock news/transcripts are auxiliary unless `FMP_ENABLED=true`.
- Retrieval policy: `current_run_only`; historical Qdrant documents must not mask a current collection miss

## Required Services
- Python `3.11.x`
- Ollama running locally on `http://localhost:11434`
- Qdrant running locally on `http://localhost:6333`

## Environment Variables
Copy `.env.example` to `.env` and set:
- `FMP_API_KEY`: optional. Required only when `FMP_ENABLED=true` for auxiliary FMP stock-news or transcript collection; missing or insufficient entitlement is reported explicitly
- `ALPHA_VANTAGE_API_KEY`: optional. Required only when `ALPHA_VANTAGE_ENABLED=true`; used as an additional news fallback after Yahoo/SEC/Google/OpenBB.
- `OPENBB_NEWS_ENABLED`: default `false`. Enable only after `python scripts/check_openbb_compat.py` shows the OpenBB news runtime is healthy.
- `SEC_USER_AGENT`: required for compliant SEC EDGAR access; set to an organization/contact string before sustained use
- `QDRANT_URL`: defaults to `http://localhost:6333`
- `QDRANT_API_KEY`: optional unless your Qdrant requires auth
- `OLLAMA_BASE_URL`: defaults to `http://localhost:11434`
- `PRIMARY_MODEL`: keep as `qwen2.5:7b`
- `DATA_MART_BACKEND`: defaults to `sqlite`
- `DATA_MART_DB_PATH`: defaults to `data/research_mart.db`; structured price, macro, news, provider, quality, backtest input data lives here
- `DATA_MART_DUCKDB_PATH`: optional analytics backend path for future DuckDB workloads
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: optional; when both are set, `scripts/run_daily_update.ps1` sends retry/failure alerts
- `ENABLE_EXPERIMENTAL_FALLBACK`: keep `false` in production
- `EXPERIMENTAL_FALLBACK_MODEL`: keep as `gemma4:e4b` only for explicit experiments

## Official Start Command
Run this at the start of every operator session:
```bash
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1
```

OpenBB Workspace custom agent를 실제로 연결하는 운영 세션에서는 agent SDK 의존성까지 설치합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1 -WithOpenBBAgent
```

What it does:
- validates the repo-local Python runtime
- starts local Qdrant with `docker compose up -d qdrant` when `QDRANT_URL` is local
- waits for `http://localhost:6333/collections`
- runs `python -m core.preflight`

If `QDRANT_URL` points to a remote host, Docker startup is skipped and only preflight is executed.

## Preflight Command
Run directly when you need diagnostics without changing service state:
```bash
python -m core.preflight
```

## OpenBB Workspace Agent Adapter

FinGPT can be exposed to OpenBB Workspace as an optional custom agent without
changing the existing FinGPT API/UI routes. The adapter is disabled by default.

1. Install optional dependencies only when using Workspace integration:
   ```bash
   pip install -r requirements-openbb-agent.txt
   ```
   또는 Windows 운영 스크립트로 한 번에 설치합니다.
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1 -WithOpenBBAgent
   ```
2. Enable the adapter in `.env`:
   ```bash
   OPENBB_AGENT_ENABLED=true
   OPENBB_AGENT_PUBLIC_URL=http://127.0.0.1:8000
   ```
3. Start the FinGPT web/API server, then register the base URL in OpenBB
   Workspace. Workspace discovers the agent from:
   - `GET /agents.json`
   - `POST /query`
4. Validate the contract before connecting Workspace:
   ```bash
   python scripts/check_openbb_agent_compat.py --probe-query
   ```

The adapter maps OpenBB messages and selected widget ticker context into the
existing FinGPT universal pipeline. It streams text, tables, citations, and
partial-result warnings back to Workspace. FinGPT remains the source of truth
for analysis, quant snapshots, citations, and `as_of` provenance.

When `OPENBB_AGENT_ENABLED=true`, `openbb-ai` and `sse-starlette` are no longer
treated as optional. `core.preflight`, `validation_gate.py`, and
`check_provider_versions.py --require-openbb-agent` fail if those packages are
missing or outside policy. With the default disabled setting they remain
warning-only so the core FinGPT UI/API stays independent from Workspace.

Expected critical green checks:
- `QDRANT_SERVICE`: reachable
- `QDRANT_QUERY_STACK`: retrieval-ready
- `YFINANCE_FEED`: reachable
- `OLLAMA_SERVICE`: reachable
- `OLLAMA_MODEL (qwen2.5:7b)`: installed

Warning-only collection checks:
- `OPENBB_PACKAGE`: package/version check for the installed OpenBB stack. This must be healthy for OpenBB opt-in operation.
- `OPENBB_NEWS_RUNTIME`: optional OpenBB `news.company` runtime check. Disabled by default; failures are warning-only unless you explicitly depend on OpenBB news.
- `QDRANT_COLLECTION_SCHEMA`: persistent Qdrant collection schema check. If an old dense-only collection is detected, the runtime tries sparse-vector auto-migration; otherwise it records dense fallback as warning-only while add/query continue working.
- `FMP_API_KEY`: disabled by default. Missing or rejected means auxiliary FMP-backed coverage will be skipped.
- `ALPHA_VANTAGE_NEWS`: optional Alpha Vantage news/sentiment endpoint. Failures are warning-only because Yahoo/SEC/Google remain primary.
- `FRED_MACRO`: FRED rates/macro endpoint for rates, FX, commodities, credit, and macro-sensitive topic runs.
- `FMP_STOCK_NEWS`: optional FMP stock-news endpoint. Yahoo/SEC/Google/FRED runs can still proceed when this is disabled or entitlement-limited.
- `SEC_FILINGS`: SEC EDGAR ticker-map probe failed or was rate-limited; Yahoo/Google/FRED runs can still proceed, but official filing fallback is degraded
- `TRANSCRIPT_PROVIDER`: optional FMP transcript dates endpoint. News-only runs can still proceed.
- `entitlement_required`: the API key is valid enough to reach FMP, but the current account plan cannot access that endpoint; this is an account/plan issue, not a code defect

## Recovery Commands
Manual Qdrant recovery:
```bash
docker compose up -d qdrant
docker logs fingpt-qdrant
```

Docker compose validation:
```bash
docker compose config --quiet
```

Do not paste full `docker compose config` output into issues, PRs, or logs
when environment variables may contain secrets. Use
`docker compose config --quiet` for validation.

Model recovery:
```bash
ollama serve
ollama pull qwen2.5:7b
```

If repeated malformed/truncated JSON persists after the built-in self-retry:
```bash
ollama serve
powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1 -RunQualityReview
```

Experimental fallback recovery:
```bash
set ENABLE_EXPERIMENTAL_FALLBACK=true
ollama pull gemma4:e4b
```

## Quality Gates and Typecheck Policy
The required local and CI quality gates are:

```bash
python scripts/check_env_example.py
python -m ruff check app core pipelines scripts tests setup.py quality_review.py
python -m compileall app core pipelines scripts tests
python -m pytest -q
python scripts/check_ui_contract.py
docker compose config --quiet
```

`mypy` is not a required gate yet. The repository does not currently ship a
project mypy configuration or a dev dependency pin for mypy. Add mypy gradually
after the active runtime, API, and quant modules have typed boundaries that can
pass without weakening checks.

## Universe and Survivorship Bias Policy

### Scope

This project may use provider-specific current index constituents,
user-supplied ticker lists, cached market data, or external APIs. Unless a
point-in-time constituent database is explicitly configured, backtests over
equity universes may be exposed to survivorship bias.

### What is controlled

- No-lookahead signal generation.
- Next-bar or delayed execution where configured.
- Transaction cost assumptions.
- Slippage assumptions.
- Time-series split, purge, and embargo safeguards for ML workflows.
- Missing or invalid ticker handling without fake success.

### What is not fully controlled by default

- Delisted securities coverage.
- Point-in-time index membership.
- Corporate action completeness across providers.
- Provider-specific historical constituent changes.
- Full survivorship-free universe reconstruction.

### Required practice for research-grade backtests

- Use point-in-time constituent snapshots when evaluating index universes.
- Store the universe definition with the backtest artifact.
- Record provider, retrieval time, adjustment policy, and filtering rules.
- Do not compare a current-constituent universe against historical benchmark
  returns as if it were survivorship-free.
- Mark results as exploratory unless delisted coverage and point-in-time
  membership are verified.

### Report labeling

Backtest reports must label universe policy as one of:

- `point_in_time_verified`
- `current_constituents_only`
- `user_supplied_static_list`
- `provider_unknown`
- `single_asset`

Reports that are not `point_in_time_verified` must include a
survivorship-bias warning.

## Single Research Run
```bash
python app/cli/main.py --ticker MSFT --question "Summarize recent earnings risks and opportunities" --lookback-days 30 --top-k 5
```

Default sources are `news transcript`. `report` is a known but disabled source and should not be used as the only source.

## Structured Data Mart Operations
The structured mart is intentionally separate from `data/runs.db` and Qdrant:

- `data/runs.db`: research execution history only.
- `data/research_mart.db`: assets, daily prices, macro observations, news article metadata, filings, data-update runs, provider status, and quality checks.
- Qdrant: text evidence chunks for current-run retrieval.

Initialize or inspect the mart:
```powershell
python scripts/daily_update.py --market us --dry-run --skip-news --skip-macro --json
python scripts/daily_update.py --market us --start-date 2025-01-01 --json
python scripts/daily_update.py --market kr --skip-macro --json
```

`--market us` captures yfinance prices, Macro registry data, Google News RSS metadata, and SEC EDGAR filing metadata by default. Macro registry data includes active FRED economic series plus Yahoo Finance market proxies used by the Macro tab. Use `--skip-filings` for provider-isolation recovery runs or when SEC is rate-limited. KR runs skip SEC filings because they are not SEC-covered instruments.

Watchlists live at:
```text
config/watchlists/core_us.yaml
config/watchlists/core_kr.yaml
```

Operational interpretation:
- `provider_status.status=ok`: provider returned usable rows.
- `provider_status.status=partial`: some tickers/series failed; inspect `details_json`.
- `provider_status.status=credentials_missing`: expected for direct FRED API collection until `FRED_API_KEY` is set. The Macro tab refresh job can fall back to FRED public CSV when no key is configured, and records that as `provider=fred_csv`.
- `provider_status.status=empty`: provider was reachable but returned no usable current rows; this is common for thin news/filing coverage and should be shown as no coverage, not as a hard failure.
- `data_quality_checks.status=warn`: data is stale or incomplete; UI must not render this as success.
- `data_quality_checks.status=fail`: duplicate or structurally invalid data; fix before using reports for decisions.

Manual stale-data recovery:
```powershell
python scripts/daily_update.py --market us --retry-failed --json
python scripts/daily_update.py --market us --watchlist config/watchlists/core_us.yaml --start-date 2024-01-01 --json
python -c "from pipelines.data_mart.jobs.update_macro_daily import update_macro_platform_data; print(update_macro_platform_data().status)"
```

Macro tab freshness checks:
- `GET /api/v1/macro/data-quality` validates every enabled Macro registry series, not just the overview indicators. Use `?scope=overview` only when you intentionally want the smaller overview-only check.
- Some FRED series use observation-period dates rather than release timestamps. Keep registry `stale_after_days` aligned with release lag before treating a refreshed but old-looking observation date as stale.
- `BUSLOANS` is monthly in the FRED graph CSV path used by the refresh job; do not classify it as a weekly series for freshness or YoY transforms.

If the mart DB is corrupt, move it aside rather than deleting it blindly:
```powershell
Move-Item data/research_mart.db data/research_mart.db.bak
python scripts/daily_update.py --market us --json
```

## Windows Daily Scheduler
Use `scripts/run_daily_update.ps1` from Windows Task Scheduler. It activates `.venv` when present, runs `scripts/daily_update.py`, retries once after 5 minutes, then runs a fallback attempt without news capture. Telegram alerts are sent only when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set.

Recommended Asia/Seoul schedules:
- 07:00: US close update.
- 18:00: Korea close update.
- 22:00: US premarket issue update.

Example Task Scheduler action:
```powershell
powershell.exe -ExecutionPolicy Bypass -File F:\LLM\FinGPT\scripts\run_daily_update.ps1 -Market us
```

For Korea close:
```powershell
powershell.exe -ExecutionPolicy Bypass -File F:\LLM\FinGPT\scripts\run_daily_update.ps1 -Market kr -SkipMacro
```

## In-Process Data Mart Auto Refresh
FastAPI also starts a local in-process data mart scheduler. It is intended for workstation freshness while the web app is running, not as a distributed job runner.

Useful controls:
```text
DATA_MART_AUTO_REFRESH_ENABLED=true
DATA_MART_AUTO_REFRESH_SEC_ENABLED=true
DATA_MART_AUTO_REFRESH_MACRO_ENABLED=true
DATA_MART_AUTO_REFRESH_INTERVAL_HOURS=24
DATA_MART_AUTO_REFRESH_INITIAL_DELAY_S=120
DATA_MART_AUTO_REFRESH_MACRO_LOOKBACK_DAYS=1825
```

Status endpoints:
```text
GET /api/v1/data/auto-refresh/status
GET /api/v1/macro/refresh/status
POST /api/v1/macro/refresh
```

## Verification Gate
Run this after infrastructure changes or before calling the system production-ready:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1
```

What it runs:
```text
1. scripts/bootstrap_local.ps1
2. python -m pytest .\tests -q
3. node --check .\app\web\app.js
4. python -m core.preflight
5. provider/OpenBB compatibility gates
6. OpenBB agent contract dry-run when enabled
7. static UI/API contract smoke for `/ui/`
```

The default gate is intentionally bounded and does not run local LLM live smoke.
For release-candidate validation, run the full live path explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1 -ReleaseCandidate
```

This adds:

```text
1. CLI smoke (MSFT / TLT / TLT topic / AI semiconductors)
2. API smoke (analyze / universal / compare / stream / outputs / runs / watchlist)
3. python quality_review.py --suite all
4. python scripts/profile_topic_latency.py
```

### FinGPT Auxiliary Evaluation
Run the auxiliary FinGPT task fixture gate explicitly when validating FinGPT-style
classification or forecasting support:

```powershell
.\venv311\Scripts\python.exe scripts\validation_gate.py --include-fingpt-eval
```

Expected result: `fingpt_eval_gate` is `passed`, `invalid_outputs` is `0`, and
the default production model remains `qwen2.5:7b`. `gemma4:e4b` remains an
experimental fallback option only.

## Benchmark Commands
Primary answer-quality benchmark:
```bash
python quality_review.py --suite all
python quality_review.py --suite topic --measure-latency
python scripts/profile_topic_latency.py
```

## Failure Modes
| Signal | Meaning | Operator Action |
| --- | --- | --- |
| `Docker CLI missing` | Local Qdrant cannot be managed from this repo. | Install Docker Desktop and reopen PowerShell. |
| `Docker daemon down` | Docker Desktop is installed, but containers cannot start. | Start Docker Desktop, then rerun `scripts/bootstrap_local.ps1`. |
| `container stopped/exited` | The repo-managed Qdrant container exists but is not serving traffic. | Run `docker compose up -d qdrant`, then check `docker logs fingpt-qdrant`. |
| `port 6333 conflict` | Another process is blocking the local Qdrant port. | Stop the named process or free the port before restarting Qdrant. |
| `QDRANT_QUERY_STACK failed` | Qdrant HTTP is reachable, but local embedding/add/query path is broken. | Treat the vector layer as non-ready and repair the local qdrant-client / fastembed runtime before proceeding. |
| `news timeout` | Yahoo Finance feed metadata did not return within the bounded collection budget. | Retry once, then treat Yahoo Finance/network health as degraded. A `news` timeout can force `partial` because it is the primary source. |
| `news:yfinance empty, news:sec_filings ok` | Yahoo had no fresh usable coverage, but SEC supplied official filing evidence. | Treat as official but thinner than article/transcript evidence; inspect the linked filing if making a high-stakes call. |
| `news:google_news_rss ok` | Google News RSS supplied fresh article evidence without paid credentials. | Treat as evidence-backed, but verify article source quality in the Evidence tab. |
| `news:alpha_vantage_news ok` | Alpha Vantage supplied key-backed news/sentiment evidence. | Treat as a useful fallback, but watch plan limits and stale dates. |
| `news:fmp_stock_news disabled` | FMP is not part of the default hot path. | No action needed unless you intentionally want FMP as an auxiliary provider. |
| `fmp_stock_news entitlement_required` | FMP stock-news fallback is blocked by account/API entitlement. | Continue with Yahoo/SEC/Google/FRED, or enable/upgrade the FMP plan if this auxiliary source matters. |
| `news:sec_filings ok` | SEC EDGAR supplied recent filing metadata as current-run evidence. | Treat as official but thinner than article/transcript evidence; inspect the linked filing if making a high-stakes call. |
| `SEC_FILINGS rate_limited` | SEC EDGAR is throttling or rejecting request cadence/user-agent. | Set a real `SEC_USER_AGENT`, slow the request cadence, and rerun preflight. |
| `transcript provider unavailable` | FMP transcript endpoint could not be reached or returned an upstream error. | Treat as supplementary-source degradation. If `news` is healthy, the run can remain `success`. |
| `transcript entitlement_required` | FMP transcript endpoint is reachable but the API key/account lacks transcript access. | Treat as non-critical for normal news-backed runs. Fix account entitlement if transcripts are required. |
| `report disabled` | The request referenced a known but unsupported production source. | Remove `report` from the request. Mixed requests will continue and log `report=disabled`; `report`-only requests fail precheck. |
| `no usable primary source` | All requested primary sources ended in `timeout`, `failed`, or `empty`. | Treat the run as collection-degraded and investigate Yahoo Finance/network access before trusting output. |
| `no usable current-run primary documents` | The run has no fresh primary evidence from this execution. | The pipeline should skip retrieval/inference and return `partial`; do not override this with old Qdrant context. |
| `stale Qdrant context blocked` | Qdrant returned chunks, but none matched current-run `doc_id`s. | Treat as correct safety behavior; inspect collection coverage rather than retrieval tuning first. |
| `data mart empty` | `data/research_mart.db` exists but prices/macro tables have no usable rows. | Run `python scripts/daily_update.py --market us --json`, then check `/api/v1/data/health`. |
| `provider_status partial` | Daily update completed with one or more failed tickers/series. | Inspect `details_json`, rerun with `--retry-failed`, and treat downstream UI/report output as partial until fixed. |
| `macro credentials_missing` | FRED was skipped because `FRED_API_KEY` is unset. | This is warning-only for local default runs; set `FRED_API_KEY` before relying on macro regime analysis. |
| `prices_freshness warn` | Latest stored daily price is older than the quality threshold. | Re-run the relevant watchlist after market close; do not present the stored price snapshot as fresh. |
| `scheduler fallback mode` | `run_daily_update.ps1` reached the third attempt and skipped news capture. | Treat the update as recovered but partial; check provider status and optional Telegram alert text. |
| `JSON malformed/truncated after retry` | Ollama stayed reachable, but `qwen2.5:7b` still failed structured output after the built-in self-retry. | Treat this as local inference instability. Restart Ollama, confirm `qwen2.5:7b` is intact, then rerun `scripts/verify_production_path.ps1 -RunQualityReview`. |
| `status=failed` | Required subsystem broke or inference aborted. Treat as non-usable output. | Fix the failing dependency first. |
| `status=partial` | Pipeline completed, but evidence coverage degraded. Use with caution. | Check `error_metadata`, retrieval depth, and source freshness. |
| `fallback_used=true` | Production primary failed and the experimental route took over. This should be rare and non-default. | Treat as anomaly. Inspect primary-model failure before trusting the run. |
| `retry_count>0` | Primary recovered after one structured-output retry because the first pass was empty, malformed, truncated, or schema-invalid. | Watch for model instability or prompt/context pressure. |
| `low-context output` | The answer was produced from thin evidence, usually paired with `partial` or very few retrieved chunks. | Re-run with broader lookback or verify the name is genuinely sparse-news. |

## TLT / Topic Output Interpretation
- TLT topic runs include `execution_meta.extras.quant_snapshot`. This deterministic layer records Treasury-yield metrics, curve/real-yield proxies when available, TLT price trend when available, duration proxy, and rate-shock sensitivity.
- Credit, FX, commodity, crypto, and sector/theme topic runs also produce proxy quant snapshots when source data exists. Examples: HYG/LQD/SPY for credit, EURUSD/DXY proxies for FX, GLD/USO for commodities, BTC/ETH for crypto.
- Every `key_metrics` item must show value, unit, `as_of`, source, evidence ids, and freshness status. If the evidence date cannot be resolved, the UI/report shows `unknown`; this is a freshness warning, not a hidden success.
- `missing_evidence_buckets` means a blocking evidence axis is absent. `warning_evidence_buckets` means the run can still be usable; for TLT, missing latest catalyst/news is warning-only when macro plus market-structure or quant substitute exists.
- `substituted_buckets` lists buckets filled by deterministic data. For example, a duration/price snapshot can satisfy market-structure requirements even when Qdrant retrieval has no separate market-structure chunk.
- `partial` must include actionable uncertainty: which source, bucket, entitlement, or freshness axis is missing. Parser/LLM errors are separate from evidence gaps in diagnostics.

## Model Routing Notes
- `qwen2.5:7b` is the production baseline for final structured JSON/report generation.
- `fingpt` is not used as a final report generator in production routing. It is capability-gated as a future auxiliary model for event extraction, sentiment/risk tagging, and financial tone classification.
- Check `execution_meta.extras.model_capabilities` when debugging model behavior. If a run says `fingpt_policy=auxiliary_only_routed_to_qwen_for_final_json`, that is expected behavior.
- Raw parser exceptions should not appear in the UI. They should map to `model_json_error` with a Korean recovery/action message.

## Interpretation Notes
- `fallback_used`: `false` is the normal production state. `true` means you are no longer on the clean production baseline.
- `retry_count`: `0` is normal. Non-zero means `qwen2.5:7b` recovered after one structured-output retry, which is operationally useful but should still be monitored.
- `partial` vs `failed`:
  - `partial` means the system stayed up but evidence quality was constrained.
  - `failed` means a required stage broke and the output is not production-usable.
- `low-context output`: usually indicated by empty retrieval, a thin evidence list in the report, or an explicit hallucination-risk warning in `error_metadata`.
- Collection logs:
  - `[COLLECT_PROVIDER] source=news provider=yfinance status=empty docs=0 elapsed=1.2s`
  - `[COLLECT_PROVIDER] source=news provider=sec_filings status=ok docs=1 elapsed=0.6s`
  - `[COLLECT_PROVIDER] source=news provider=google_news_rss status=ok docs=3 elapsed=0.8s`
  - `[COLLECT_PROVIDER] source=news provider=alpha_vantage_news status=ok docs=3 elapsed=0.8s`
  - `[COLLECT_PROVIDER] source=news provider=fmp_stock_news status=disabled docs=0 elapsed=0.0s`
  - `[COLLECT_SOURCE] source=news status=ok docs=8 elapsed=7.4s`
  - `[COLLECT_SOURCE] source=transcript status=no_data_in_window docs=0 elapsed=1.1s`
  - `[COLLECT_SUMMARY] usable_docs=8 degraded_sources=['transcript']`
- `data/outputs/latest_collection.json`: first place to inspect collection truth. It contains `current_doc_ids`, `source_results`, `provider_results`, `freshness_cutoff`, and `retrieval_policy=current_run_only`.

## Acceptance Flow
Use this sequence when closing out local production hardening:
1. `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1`
2. `python scripts/check_ui_contract.py`
3. `powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1 -ReleaseCandidate`
3. `reports/validation_latest.md`의 수동 UI 체크리스트를 따라 `/ui/`를 확인
