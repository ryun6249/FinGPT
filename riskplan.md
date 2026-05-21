# Risk Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional enterprise-macro Risk tab that explains company-specific vulnerabilities, macro pressure, transmission channels, scenario damage paths, portfolio overlays, and data-quality limits without turning the surface into a buy/sell recommender.

> **Execution status (2026-05-21 KST): COMPLETE.** The Risk bounded context, API routes, dashboard card, static UI, tests, docs, and browser verification were completed. Verified smoke cases: `NVDA`, `JPM`, `TLT`, and `INVALID_TEST_TICKER_123`; desktop and 390px mobile output rendered without horizontal overflow, and invalid ticker output failed closed.
>
> **Enhancement status (2026-05-21 KST): VERIFIED.** Continuous enhancement now treats ETF and macro proxy inputs such as `TLT`, `HYG`, and `SPY` as limited asset-proxy risk subjects when price and macro evidence exist. Missing company fundamentals and SEC evidence stay visible, while invalid tickers and missing price/quant inputs still fail closed. Fresh browser verification used `http://127.0.0.1:8780/ui/#risk` with desktop and 390px mobile overflow `0`.
>
> **Service-readiness enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes structured `service_readiness` with `ready`, `review_required`, or `blocked` status, checklist evidence, warnings, blockers, and next steps. The first-flow Risk UI renders this beside the decision brief in KR/EN, with latest browser verification on `http://127.0.0.1:8792/ui/#risk`; desktop and 390px mobile overflow were `0`.
>
> **Action-checklist enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `action_checklist` that turns outputs into concrete, evidence-linked next checks for data quality, top drivers, severe scenarios, asset-proxy scope, portfolio concentration, and service release readiness. Fresh browser verification used `http://127.0.0.1:8793/ui/#risk`; desktop and 390px mobile rendered without horizontal overflow.
>
> **Monitoring-trigger enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes typed `monitoring_triggers` for data-quality gates, dominant drivers, macro transmission channels, severe scenarios, asset-proxy scope, and service release readiness. The first-flow Risk UI renders the triggers beside the action checklist so users can see what should be monitored after a run without treating the output as a trade recommendation. Fresh browser verification used `http://127.0.0.1:8794/ui/#risk`; desktop and 390px mobile rendered without horizontal overflow.
>
> **Priority-map and run-lineage enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a compact `priority_map` for the highest-risk company, macro, and data-quality cells plus `run_lineage` for replay fields, adapter status, evidence counts, freshness counts, and service version. The first-flow Risk UI renders the priority map in the decision brief and the lineage packet in the evidence drawer so users can compare, save, or service-wrap runs without losing audit context.
>
> **Confidence-factor and output-quality enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes typed `confidence_factors` for company coverage, macro backdrop, data quality, scenario coverage, and service controls. The first-flow UI renders these factors as a compact confidence basis ladder, and API tests guard Korean/English Risk output against mojibake regressions.
>
> **Workflow-handoff enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `handoff_queue` that turns a run into the next best local workflow: Risk evidence repair, Macro pressure review, Quantamental drilldown, ML Forecast validation test, AI Portfolio overlay review, and service-wrapper release gate. Browser verification used `http://127.0.0.1:8797/ui/#risk`; desktop and 390px mobile rendered without horizontal overflow, and the full regression suite passed with `723 passed, 9 subtests passed`.
>
> **ML-validation enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes typed `ml_validation_tests` that translate a Risk run into concrete ML Forecast validation experiments: walk-forward baseline, macro-feature leakage check, severe-scenario forecast backtest, asset-proxy validation, portfolio component OOS check, or blocked data-gate recheck. The first-flow Risk UI renders these tests beside the handoff queue so users can see exactly what forecast validation should run next.
>
> **ML Forecast handoff-prefill enhancement status (2026-05-21 KST): VERIFIED.** Each actionable Risk `ml_validation_tests` row now carries typed `forecast_prefill` settings and a `launch_href` that opens `/ui/?tab=ml-forecast...#ml-forecast` with ticker, benchmark, horizon, validation method, target type, macro/cross-asset switches, Risk test id, and Risk input hash prefilled. Browser verification used `http://127.0.0.1:8801/ui/#risk` plus the generated ML Forecast launch URL; desktop and 390px mobile overflow were `0`, invalid tickers remained fail-closed, and blocked data-gate tests do not expose a Forecast launch link.
>
> **Decision-path enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `decision_path` that consolidates the top action, linked workflow, Forecast validation launch, service gate, and evidence refs into one first-flow summary. Browser verification used `http://127.0.0.1:8802/ui/#risk`; NVDA desktop, TLT mobile, invalid ticker fail-closed, and generated ML Forecast prefill all rendered with horizontal overflow `0`.
>
> **Risk-to-Forecast source-context enhancement status (2026-05-21 KST): VERIFIED.** This slice carries Risk ML validation metadata into ML Forecast launch URLs and `ForecastRunRequest.source_context`, then renders a compact Forecast handoff plan so users can verify dataset, leakage, and training steps without losing the Risk input hash. Browser verification used `http://127.0.0.1:8803/ui/#risk`; NVDA Risk to Forecast handoff, Forecast queued-job request context, TLT mobile, and invalid-ticker fail-closed output all passed with horizontal overflow `0`.
>
> **Release-packet enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `release_packet` that turns each run into a deployability contract: API/UI routes, required audit fields, validation commands, deployment checks, rollback triggers, data dependencies, and limitations. The first-flow UI renders the packet beside service readiness, and the evidence drawer exposes the routes and validation commands for operators. Fresh verification used `http://127.0.0.1:8804/ui/#risk`; NVDA desktop, TLT 390px mobile, and invalid-ticker fail-closed output rendered with horizontal overflow `0` and console errors `0`.
>
> **Input-receipt enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `input_receipt` that shows normalized mode, subjects, position weights, compatibility notes, and replay notes. The first-flow Risk UI renders this beside the decision path so users can immediately see what the service actually analyzed before comparing downstream panels. Fresh verification used `http://127.0.0.1:8805/ui/#risk`; NVDA desktop, TLT 390px mobile, and invalid-ticker fail-closed output rendered with horizontal overflow `0`, console errors `0`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **Decision-quality enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now adds a typed `decision_quality` summary that compresses confidence, data-quality gates, input receipt, service readiness, release packet, and ML Forecast validation availability into one status, score, basis, blockers, and next-action list. The first-flow Risk UI renders it beside the decision path so users can quickly see whether a run is ready, review-bound, or blocked without changing risk-score math. Fresh verification used `http://127.0.0.1:8806/ui/#risk`; NVDA desktop, TLT 390px mobile, and invalid-ticker fail-closed output rendered with horizontal overflow `0`, console errors `0`, `app.js?v=20260521-risk-forecast-v32`, `styles.css?v=20260521-risk-forecast-v30`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **Evidence-coverage enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now includes a typed `evidence_coverage` matrix for input normalization, company/asset profile coverage, macro backdrop, scenario stress coverage, ML Forecast validation coverage, service release coverage, and evidence inventory. The first-flow Risk UI and evidence drawer render each domain as `ok`, `review`, or `blocked`, so users can see what is trustworthy, what needs review, and what blocks service use without changing Risk score math. Fresh verification used `http://127.0.0.1:8807/ui/#risk`; NVDA desktop, TLT 390px mobile, invalid-ticker fail-closed output, and Risk-to-Forecast prefill rendered with horizontal overflow `0`, console errors `0`, `app.js?v=20260521-risk-forecast-v33`, `styles.css?v=20260521-risk-forecast-v31`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **AI-output-control enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now adds typed `ai_output_controls` for grounded model-written Risk narratives: status, language, required evidence refs, allowed and blocked claims, citation policy, review instructions, and prompt context. The first-flow Risk UI and evidence drawer render the guardrails so advanced AI output can stay tied to deterministic Risk contracts, ML Forecast validation context, and release readiness instead of inventing missing metrics or service-readiness claims. Fresh verification used `http://127.0.0.1:8808/ui/#risk`; NVDA desktop, TLT 390px mobile, invalid-ticker fail-closed output, and API smoke for weighted portfolio all passed with horizontal overflow `0`, console errors `0`, `app.js?v=20260521-risk-forecast-v34`, `styles.css?v=20260521-risk-forecast-v32`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **Decision-compass enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now adds typed `decision_compass` with a compact user workflow over input/quality verification, evidence coverage review, ML Forecast validation, AI narrative controls, and service gate review. The first-flow Risk UI renders it as the top decision navigator so users can see the intended next steps without scanning every diagnostic panel. Fresh verification used `http://127.0.0.1:8809/ui/#risk`; NVDA desktop, TLT 390px mobile, invalid-ticker fail-closed output, and weighted `NVDA/MSFT/TLT` API smoke all returned the compass; body/critical overflow was `0`, console errors were `0`, invalid ticker Forecast links were `0`, `app.js?v=20260521-risk-forecast-v35`, `styles.css?v=20260521-risk-forecast-v33`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **Compatibility-matrix enhancement status (2026-05-21 KST): VERIFIED.** The Risk response adds typed `compatibility_matrix` rows so each requested subject shows supported and blocked downstream workflows before users move to Quantamental, Macro, ML Forecast, AI Portfolio, or service exposure. The first-flow UI and evidence drawer render the matrix; fresh verification used `http://127.0.0.1:8811/ui/#risk` with NVDA desktop, TLT 390px mobile, and invalid ticker fail-closed output. Body/critical overflow was `0`, console errors were `0`, invalid ticker Forecast links were `0`, `app.js?v=20260521-risk-forecast-v36`, `styles.css?v=20260521-risk-forecast-v34`, and the full regression suite passed with `724 passed, 9 subtests passed`.
>
> **Forecast-validation-plan enhancement status (2026-05-21 KST): VERIFIED.** The Risk response now adds typed `forecast_validation_plan` so users can see the primary ML Forecast test, run order, experiment controls, acceptance criteria, and blocked reasons before launching Forecast. The first-flow UI and evidence drawer render the plan with cache-busted assets `app.js?v=20260521-risk-forecast-v37` and `styles.css?v=20260521-risk-forecast-v35`. Fresh verification used `http://127.0.0.1:8812/ui/#risk`; NVDA desktop, TLT 390px mobile, and invalid-ticker fail-closed output rendered with horizontal overflow `0`, console errors `0`, invalid ticker Forecast links `0`, and the full regression suite passed with `725 passed, 9 subtests passed`.

**Architecture:** Add a new `risk` bounded context that orchestrates existing Quantamental, Macro, Portfolio, and Dashboard services through typed adapters. The UI remains a thin static `/ui/` client that renders deterministic risk contracts from `/api/v1/risk/*`; risk math, data-quality policy, evidence mapping, and scenario logic live in backend services.

**Tech Stack:** FastAPI, Pydantic schemas, existing FinGPT Python service modules, static HTML/CSS/JavaScript UI, pytest, existing UI contract scripts, existing macro and quantamental data mart contracts.

---

## 0. Product Definition

The Risk tab is a `Risk Control Plane`, not a signal generator.

It must answer:

> What company-specific and macro-driven risks currently threaten this company, watchlist, or portfolio, and through which channels could conditions deteriorate?

Primary workflows:

1. `Company Risk Review`: analyze one company such as `NVDA`, `MSFT`, `AAPL`, or `JPM`.
2. `Watchlist Risk Board`: compare multiple tickers with the same risk vector contract.
3. `Portfolio Risk Overlay`: weight company risks by position size and concentration.
4. `Macro Shock Drilldown`: inspect how rates, credit, liquidity, inflation, dollar, and commodity shocks transmit into companies or holdings.
5. `Evidence Review`: audit freshness, source coverage, SEC flags, macro series, and calculation policy.

Non-goals:

1. Do not provide direct buy/sell/hold recommendations.
2. Do not let AI invent risk scores, financial metrics, macro values, or missing data.
3. Do not mutate AI Portfolio policies, rebalance proposals, or saved portfolios automatically.
4. Do not use the existing text-only `pipelines/analyze/risk_analysis.py` as the core Risk tab engine.
5. Do not collapse company, macro, scenario, and portfolio logic into one route or one frontend file.

---

## 1. Existing System Boundaries To Reuse

Use these current surfaces as source-of-truth inputs:

| Domain | Existing files | Role in Risk tab |
| --- | --- | --- |
| Static UI shell | `app/web/index.html`, `app/web/app.js`, `app/web/styles.css` | Add the `Risk` dashboard tab, state, renderers, loading/error/empty states, and responsive layout. |
| Dashboard contracts | `app/api/routers/dashboard.py`, `core/schemas/dashboard.py`, `scripts/check_ui_contract.py` | Add a `risk` decision-card contract and UI contract coverage. |
| Quantamental company risk | `pipelines/quantamental/risk_engine.py`, `fundamental_engine.py`, `quant_engine.py`, `sec_evidence.py`, `service.py` | Source company fundamentals, price risk, SEC flags, freshness, and existing strict data-quality logic. |
| Macro platform | `app/api/routers/macro.py`, `pipelines/macro/dashboard.py`, `regime_engine.py`, `scenario.py`, `provider_health.py`, `series_registry.py` | Source macro regime, provider health, macro data quality, scenario shock outputs, and series evidence. |
| Portfolio risk | `pipelines/analyze/portfolio_quant.py`, `core/schemas/portfolio.py`, `app/api/routers/research.py` | Source concentration, factor exposure, deterministic stress rows, and weighted exposure logic. |
| AI Portfolio ops | `app/api/routers/ai_portfolio.py`, `core/schemas/ai_portfolio.py`, `pipelines/ai_portfolio/service.py` | Optional source for portfolio coverage, snapshot timeline, policy context, and operations metadata. |

Important architectural decision:

- `pipelines/analyze/risk_analysis.py` remains an inference-output helper for bull/bear risk text.
- New enterprise-macro risk logic belongs in `pipelines/risk/`.

---

## 2. Target File Structure

Create:

```text
core/schemas/risk.py
pipelines/risk/__init__.py
pipelines/risk/aggregation.py
pipelines/risk/company.py
pipelines/risk/data_quality.py
pipelines/risk/macro.py
pipelines/risk/scenario.py
pipelines/risk/service.py
pipelines/risk/transmission.py
app/api/routers/risk.py
tests/test_risk_aggregation.py
tests/test_risk_transmission.py
tests/test_risk_data_quality.py
tests/test_risk_workbench_api.py
tests/test_ui_risk_contract.py
```

Modify:

```text
app/api/server.py
app/api/routers/dashboard.py
app/web/index.html
app/web/app.js
app/web/styles.css
scripts/check_ui_contract.py
docs/ARCHITECTURE.md
docs/PROJECT_MAP.md
docs/UI_TAB_DECISION_CHECKLIST.md
```

Do not modify:

```text
pipelines/analyze/risk_analysis.py
core/interfaces/risk.py
```

Those files serve different text-analysis responsibilities and should not become the new Risk tab architecture.

---

## 3. Domain Ontology

Every risk output should be decomposed into vectors.

Risk vectors:

```text
company_solvency
company_cash_flow_quality
company_earnings_quality
valuation_fragility
market_behavior
macro_policy_rates
macro_growth_inflation
credit_liquidity
transmission_sensitivity
portfolio_concentration
data_integrity
```

Risk level scale:

```text
low
moderate
elevated
high
unknown
```

Risk index direction:

```text
0   = lowest detected risk
100 = highest detected risk
null = insufficient evidence
```

Decision usability:

```text
decision_usable=true
```

means the result is suitable for analysis support. It does not mean the model recommends an investment action.

```text
decision_usable=false
```

means one or more required data surfaces are missing, stale, or provider-degraded enough to block decision use.

---

## 4. Scoring Policy

Base company/watchlist score:

```text
risk_index =
  company_fundamental_vulnerability * 0.25
+ market_behavior_risk              * 0.20
+ macro_regime_risk                 * 0.20
+ credit_liquidity_risk             * 0.15
+ transmission_sensitivity          * 0.10
+ data_quality_penalty              * 0.10
```

Portfolio score:

```text
portfolio_risk_index =
  weighted_company_risk             * 0.30
+ weighted_market_behavior_risk     * 0.15
+ macro_regime_risk                 * 0.15
+ credit_liquidity_risk             * 0.15
+ weighted_transmission_sensitivity * 0.10
+ concentration_penalty             * 0.05
+ data_quality_penalty              * 0.10
```

Quantamental score conversion:

```text
company_fundamental_vulnerability = clamp(100 - quantamental_risk_score, 0, 100)
```

Risk level mapping:

```text
0-24    low
25-49   moderate
50-74   elevated
75-100  high
null    unknown
```

Data-quality penalty:

```text
missing_price_data             +25
stale_price_data               +15
missing_fundamentals           +20
stale_fundamentals             +12
macro_coverage_low             +10
provider_health_degraded       +10
scenario_inputs_partial         +8
sec_unavailable                 +0 risk penalty, confidence penalty only
sec_stale_or_flagged            +5
```

Confidence policy:

```text
start at 100
- missing critical company data: 25
- stale critical company data: 15
- macro regime unknown: 20
- provider health degraded: 10
- SEC unavailable: 8
- partial scenario inputs: 8
- invalid ticker: 100 and decision_usable=false
```

Clamp confidence to `0..100`.

---

## 5. API Contract

### 5.1 Routes

Create `app/api/routers/risk.py` with:

```text
GET  /api/v1/risk/health
POST /api/v1/risk/workbench
GET  /api/v1/risk/company/{ticker}
GET  /api/v1/risk/macro
POST /api/v1/risk/scenario
```

Version-1 route behavior:

| Route | Purpose | Heavy work |
| --- | --- | --- |
| `/health` | Confirms risk service wiring and dependency status. | No |
| `/workbench` | Main company/watchlist/portfolio risk analysis. | Bounded sync |
| `/company/{ticker}` | Focused company risk profile. | Bounded sync |
| `/macro` | Macro backdrop in risk-specific format. | Bounded sync |
| `/scenario` | Deterministic stress matrix for supplied subjects. | Bounded sync |

Add async jobs only when large watchlists or forced refresh behavior is implemented.

### 5.2 Request Schema

Target Pydantic shape:

```python
class RiskPosition(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    weight: float = Field(..., ge=0.0, le=1.0)
    market_value: float | None = Field(default=None, ge=0.0)


class RiskWorkbenchRequest(BaseModel):
    mode: Literal["company", "watchlist", "portfolio"] = "company"
    tickers: list[str] = Field(default_factory=list, max_length=25)
    positions: list[RiskPosition] | None = None
    market: str = "US"
    lookback_days: int = Field(default=756, ge=63, le=2520)
    scenario_set: Literal["base_adverse_severe", "rates_credit_liquidity", "inflation_growth_policy"] = "base_adverse_severe"
    include_sec: bool = True
    include_macro_scenarios: bool = True
    force_refresh: bool = False
```

Validation rules:

```text
company mode: exactly one ticker required
watchlist mode: 1..25 tickers required
portfolio mode: positions required and weight sum must be > 0
duplicate tickers: normalize and dedupe for company/watchlist, reject duplicate portfolio positions unless merged explicitly
invalid empty ticker: HTTP 422
```

### 5.3 Response Schema

Target Pydantic shape:

```python
class RiskEvidenceItem(BaseModel):
    evidence_id: str
    source: str
    label: str
    value: str | float | int | None = None
    as_of: datetime | None = None
    freshness: Literal["fresh", "stale", "missing", "unknown"] = "unknown"
    url: str | None = None
    notes: list[str] = Field(default_factory=list)


class RiskVector(BaseModel):
    vector: Literal[
        "company_solvency",
        "company_cash_flow_quality",
        "company_earnings_quality",
        "valuation_fragility",
        "market_behavior",
        "macro_policy_rates",
        "macro_growth_inflation",
        "credit_liquidity",
        "transmission_sensitivity",
        "portfolio_concentration",
        "data_integrity",
    ]
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    level: Literal["low", "moderate", "elevated", "high", "unknown"]
    confidence: float = Field(..., ge=0.0, le=100.0)
    direction: Literal["higher_is_riskier"] = "higher_is_riskier"
    top_drivers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    decision_usable: bool = True


class RiskWorkbenchResponse(BaseModel):
    risk_run_id: str
    input_hash: str
    mode: Literal["company", "watchlist", "portfolio"]
    risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: Literal["low", "moderate", "elevated", "high", "unknown"]
    confidence: float = Field(..., ge=0.0, le=100.0)
    decision_usable: bool
    as_of: datetime
    primary_drivers: list[str] = Field(default_factory=list)
    risk_vectors: list[RiskVector] = Field(default_factory=list)
    company_profiles: list[RiskCompanyProfile] = Field(default_factory=list)
    macro_backdrop: RiskMacroBackdrop
    transmission_channels: list[RiskTransmissionChannel] = Field(default_factory=list)
    scenario_matrix: list[RiskScenarioResult] = Field(default_factory=list)
    portfolio_overlay: RiskPortfolioOverlay | None = None
    evidence: list[RiskEvidenceItem] = Field(default_factory=list)
    data_quality: RiskDataQuality
    calculation_policy: RiskCalculationPolicy
```

The actual implementation can split these classes across the same `core/schemas/risk.py` file, but keep transport models centralized.

---

## 6. UI Information Architecture

Add a top-level dashboard tab:

```text
Market | Macro | Risk | Quantamental | Quant Lab | ML Forecast | AI Portfolio
```

Risk should sit after Macro because macro context is a major driver, and before Quantamental because Risk consumes company-level quantamental data but is a broader decision-control surface.

### 6.1 Risk Screen Panels

Required panels:

1. `Risk Command Bar`
   - Mode segmented control: `Company`, `Watchlist`, `Portfolio`
   - Ticker input
   - Portfolio positions toggle or compact editor
   - Scenario preset select
   - Lookback select
   - Refresh action

2. `Executive Risk Strip`
   - Risk Index
   - Risk Level
   - Confidence
   - Decision usable badge
   - As-of timestamp
   - Top three drivers

3. `Driver Waterfall`
   - Company vulnerability contribution
   - Market behavior contribution
   - Macro regime contribution
   - Credit/liquidity contribution
   - Transmission contribution
   - Data quality penalty

4. `Company Risk Stack`
   - Ticker
   - Overall company risk
   - Solvency
   - Cash-flow quality
   - Earnings quality
   - Valuation fragility
   - Market risk
   - SEC flag
   - Freshness

5. `Macro Pressure Panel`
   - Policy/rates
   - Inflation
   - Growth/labor
   - Yield curve
   - Credit
   - Liquidity
   - Dollar
   - Commodities

6. `Transmission Matrix`
   - Rows: transmission channels
   - Columns: pressure, sensitivity, affected subjects, risk delta, evidence

7. `Scenario Matrix`
   - Base
   - Adverse
   - Severe
   - Rate shock
   - Credit shock
   - Liquidity shock
   - Inflation shock
   - Growth shock

8. `Evidence Drawer`
   - SEC evidence
   - Macro series evidence
   - Provider health
   - Data freshness
   - Calculation method
   - Input hash and run id

### 6.2 UI States

Every panel must support:

```text
loading
loaded
empty
partial
error
stale
```

Do not hide `partial` or `stale` under diagnostics. Risk decisions depend on seeing these states.

---

## 7. Implementation Tasks

### Task 1: Add Core Risk Schemas

**Files:**

- Create: `core/schemas/risk.py`
- Test: `tests/test_risk_workbench_api.py`

- [x] **Step 1: Write schema import test**

Create `tests/test_risk_workbench_api.py` with:

```python
from core.schemas.risk import RiskWorkbenchRequest


def test_risk_workbench_request_accepts_company_mode():
    request = RiskWorkbenchRequest(mode="company", tickers=["NVDA"])
    assert request.mode == "company"
    assert request.tickers == ["NVDA"]
    assert request.lookback_days == 756
```

- [x] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests/test_risk_workbench_api.py::test_risk_workbench_request_accepts_company_mode -q
```

Expected:

```text
ModuleNotFoundError: No module named 'core.schemas.risk'
```

- [x] **Step 3: Create minimal schema file**

Create `core/schemas/risk.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


RiskMode = Literal["company", "watchlist", "portfolio"]
RiskLevel = Literal["low", "moderate", "elevated", "high", "unknown"]
FreshnessState = Literal["fresh", "stale", "missing", "unknown"]


class RiskPosition(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    weight: float = Field(..., ge=0.0, le=1.0)
    market_value: float | None = Field(default=None, ge=0.0)


class RiskWorkbenchRequest(BaseModel):
    mode: RiskMode = "company"
    tickers: list[str] = Field(default_factory=list, max_length=25)
    positions: list[RiskPosition] | None = None
    market: str = "US"
    lookback_days: int = Field(default=756, ge=63, le=2520)
    scenario_set: Literal[
        "base_adverse_severe",
        "rates_credit_liquidity",
        "inflation_growth_policy",
    ] = "base_adverse_severe"
    include_sec: bool = True
    include_macro_scenarios: bool = True
    force_refresh: bool = False

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "RiskWorkbenchRequest":
        normalized = [ticker.strip().upper() for ticker in self.tickers if ticker.strip()]
        self.tickers = list(dict.fromkeys(normalized))
        if self.mode == "company" and len(self.tickers) != 1:
            raise ValueError("company mode requires exactly one ticker")
        if self.mode == "watchlist" and not self.tickers:
            raise ValueError("watchlist mode requires at least one ticker")
        if self.mode == "portfolio":
            if not self.positions:
                raise ValueError("portfolio mode requires positions")
            if sum(position.weight for position in self.positions) <= 0:
                raise ValueError("portfolio mode requires positive total weight")
        return self
```

- [x] **Step 4: Expand schemas in the same file**

Add these models after `RiskWorkbenchRequest`:

```python
class RiskEvidenceItem(BaseModel):
    evidence_id: str
    source: str
    label: str
    value: str | float | int | None = None
    as_of: datetime | None = None
    freshness: FreshnessState = "unknown"
    url: str | None = None
    notes: list[str] = Field(default_factory=list)


class RiskVector(BaseModel):
    vector: Literal[
        "company_solvency",
        "company_cash_flow_quality",
        "company_earnings_quality",
        "valuation_fragility",
        "market_behavior",
        "macro_policy_rates",
        "macro_growth_inflation",
        "credit_liquidity",
        "transmission_sensitivity",
        "portfolio_concentration",
        "data_integrity",
    ]
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=100.0)
    direction: Literal["higher_is_riskier"] = "higher_is_riskier"
    top_drivers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    decision_usable: bool = True


class RiskDataQuality(BaseModel):
    decision_usable: bool = True
    freshness: FreshnessState = "unknown"
    missing_inputs: list[str] = Field(default_factory=list)
    stale_inputs: list[str] = Field(default_factory=list)
    provider_warnings: list[str] = Field(default_factory=list)
    penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    confidence_penalty: float = Field(default=0.0, ge=0.0, le=100.0)


class RiskCompanyProfile(BaseModel):
    ticker: str
    risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    vectors: list[RiskVector] = Field(default_factory=list)
    primary_drivers: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskMacroBackdrop(BaseModel):
    regime: str = "unknown"
    risk_level: RiskLevel = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    vectors: list[RiskVector] = Field(default_factory=list)
    primary_pressures: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class RiskTransmissionChannel(BaseModel):
    channel: str
    pressure: RiskLevel
    sensitivity: float = Field(..., ge=0.0, le=1.0)
    risk_delta: float = Field(..., ge=0.0, le=100.0)
    affected_subjects: list[str] = Field(default_factory=list)
    mechanism: str
    evidence_refs: list[str] = Field(default_factory=list)


class RiskScenarioResult(BaseModel):
    scenario_id: str
    label: str
    severity: Literal["base", "adverse", "severe"]
    risk_index_delta: float
    projected_risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    top_damage_channels: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RiskPortfolioOverlay(BaseModel):
    weighted_risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    concentration_penalty: float = Field(default=0.0, ge=0.0, le=100.0)
    largest_contributors: list[str] = Field(default_factory=list)
    scenario_exposures: list[RiskScenarioResult] = Field(default_factory=list)


class RiskCalculationPolicy(BaseModel):
    score_direction: Literal["higher_is_riskier"] = "higher_is_riskier"
    version: str = "risk-workbench-v1"
    weights: dict[str, float] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskWorkbenchResponse(BaseModel):
    risk_run_id: str
    input_hash: str
    mode: RiskMode
    risk_index: float | None = Field(default=None, ge=0.0, le=100.0)
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=100.0)
    decision_usable: bool
    as_of: datetime
    primary_drivers: list[str] = Field(default_factory=list)
    risk_vectors: list[RiskVector] = Field(default_factory=list)
    company_profiles: list[RiskCompanyProfile] = Field(default_factory=list)
    macro_backdrop: RiskMacroBackdrop = Field(default_factory=RiskMacroBackdrop)
    transmission_channels: list[RiskTransmissionChannel] = Field(default_factory=list)
    scenario_matrix: list[RiskScenarioResult] = Field(default_factory=list)
    portfolio_overlay: RiskPortfolioOverlay | None = None
    evidence: list[RiskEvidenceItem] = Field(default_factory=list)
    data_quality: RiskDataQuality = Field(default_factory=RiskDataQuality)
    calculation_policy: RiskCalculationPolicy = Field(default_factory=RiskCalculationPolicy)
```

- [x] **Step 5: Run schema tests**

Run:

```powershell
python -m pytest tests/test_risk_workbench_api.py -q
```

Expected:

```text
1 passed
```

---

### Task 2: Implement Aggregation Math

**Files:**

- Create: `pipelines/risk/__init__.py`
- Create: `pipelines/risk/aggregation.py`
- Test: `tests/test_risk_aggregation.py`

- [x] **Step 1: Write aggregation tests**

Create `tests/test_risk_aggregation.py`:

```python
from pipelines.risk.aggregation import (
    clamp_score,
    risk_level_for_score,
    weighted_risk_index,
)


def test_risk_level_for_score_maps_expected_boundaries():
    assert risk_level_for_score(None) == "unknown"
    assert risk_level_for_score(0) == "low"
    assert risk_level_for_score(24.99) == "low"
    assert risk_level_for_score(25) == "moderate"
    assert risk_level_for_score(50) == "elevated"
    assert risk_level_for_score(75) == "high"
    assert risk_level_for_score(100) == "high"


def test_weighted_risk_index_uses_base_policy():
    result = weighted_risk_index(
        {
            "company_fundamental_vulnerability": 60,
            "market_behavior_risk": 70,
            "macro_regime_risk": 50,
            "credit_liquidity_risk": 40,
            "transmission_sensitivity": 80,
            "data_quality_penalty": 10,
        }
    )
    assert result == 54.0


def test_clamp_score_bounds_values():
    assert clamp_score(-10) == 0
    assert clamp_score(120) == 100
    assert clamp_score(None) is None
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_risk_aggregation.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'pipelines.risk'
```

- [x] **Step 3: Implement aggregation helpers**

Create `pipelines/risk/__init__.py`:

```python
"""Enterprise-macro risk workbench services."""
```

Create `pipelines/risk/aggregation.py`:

```python
from __future__ import annotations

from core.schemas.risk import RiskLevel


BASE_RISK_WEIGHTS: dict[str, float] = {
    "company_fundamental_vulnerability": 0.25,
    "market_behavior_risk": 0.20,
    "macro_regime_risk": 0.20,
    "credit_liquidity_risk": 0.15,
    "transmission_sensitivity": 0.10,
    "data_quality_penalty": 0.10,
}


def clamp_score(value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(100.0, float(value))), 2)


def risk_level_for_score(value: float | None) -> RiskLevel:
    if value is None:
        return "unknown"
    score = clamp_score(value)
    if score is None:
        return "unknown"
    if score < 25:
        return "low"
    if score < 50:
        return "moderate"
    if score < 75:
        return "elevated"
    return "high"


def weighted_risk_index(
    components: dict[str, float | None],
    weights: dict[str, float] | None = None,
) -> float | None:
    policy = weights or BASE_RISK_WEIGHTS
    weighted_total = 0.0
    weight_total = 0.0
    for key, weight in policy.items():
        value = components.get(key)
        if value is None:
            continue
        weighted_total += clamp_score(value) * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return round(weighted_total / weight_total, 2)
```

- [x] **Step 4: Run aggregation tests**

Run:

```powershell
python -m pytest tests/test_risk_aggregation.py -q
```

Expected:

```text
3 passed
```

---

### Task 3: Implement Data-Quality Policy

**Files:**

- Create: `pipelines/risk/data_quality.py`
- Test: `tests/test_risk_data_quality.py`

- [x] **Step 1: Write data-quality tests**

Create `tests/test_risk_data_quality.py`:

```python
from pipelines.risk.data_quality import evaluate_risk_data_quality


def test_data_quality_marks_missing_price_data_not_usable():
    result = evaluate_risk_data_quality(
        missing_inputs=["price_data"],
        stale_inputs=[],
        provider_warnings=[],
        sec_unavailable=False,
    )
    assert result.decision_usable is False
    assert result.penalty == 25
    assert "price_data" in result.missing_inputs


def test_sec_unavailable_lowers_confidence_without_risk_penalty():
    result = evaluate_risk_data_quality(
        missing_inputs=[],
        stale_inputs=[],
        provider_warnings=[],
        sec_unavailable=True,
    )
    assert result.decision_usable is True
    assert result.penalty == 0
    assert result.confidence_penalty == 8
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_risk_data_quality.py -q
```

Expected:

```text
ModuleNotFoundError or ImportError for evaluate_risk_data_quality
```

- [x] **Step 3: Implement data-quality helper**

Create `pipelines/risk/data_quality.py`:

```python
from __future__ import annotations

from core.schemas.risk import RiskDataQuality


RISK_PENALTIES: dict[str, float] = {
    "price_data": 25,
    "fundamentals": 20,
    "macro_coverage": 10,
    "provider_health": 10,
    "scenario_inputs": 8,
}

STALE_PENALTIES: dict[str, float] = {
    "price_data": 15,
    "fundamentals": 12,
    "sec_filing": 5,
}

CONFIDENCE_PENALTIES: dict[str, float] = {
    "missing_critical_company_data": 25,
    "stale_critical_company_data": 15,
    "macro_regime_unknown": 20,
    "provider_health_degraded": 10,
    "sec_unavailable": 8,
    "partial_scenario_inputs": 8,
}


def evaluate_risk_data_quality(
    *,
    missing_inputs: list[str],
    stale_inputs: list[str],
    provider_warnings: list[str],
    sec_unavailable: bool,
) -> RiskDataQuality:
    risk_penalty = 0.0
    confidence_penalty = 0.0

    for item in missing_inputs:
        risk_penalty += RISK_PENALTIES.get(item, 0.0)
        if item in {"price_data", "fundamentals"}:
            confidence_penalty += CONFIDENCE_PENALTIES["missing_critical_company_data"]

    for item in stale_inputs:
        risk_penalty += STALE_PENALTIES.get(item, 0.0)
        if item in {"price_data", "fundamentals"}:
            confidence_penalty += CONFIDENCE_PENALTIES["stale_critical_company_data"]

    if provider_warnings:
        confidence_penalty += CONFIDENCE_PENALTIES["provider_health_degraded"]
        risk_penalty += RISK_PENALTIES["provider_health"]

    if sec_unavailable:
        confidence_penalty += CONFIDENCE_PENALTIES["sec_unavailable"]

    decision_usable = "price_data" not in missing_inputs and "fundamentals" not in missing_inputs
    freshness = "missing" if missing_inputs else "stale" if stale_inputs else "fresh"

    return RiskDataQuality(
        decision_usable=decision_usable,
        freshness=freshness,
        missing_inputs=missing_inputs,
        stale_inputs=stale_inputs,
        provider_warnings=provider_warnings,
        penalty=min(100.0, risk_penalty),
        confidence_penalty=min(100.0, confidence_penalty),
    )
```

- [x] **Step 4: Run data-quality tests**

Run:

```powershell
python -m pytest tests/test_risk_data_quality.py -q
```

Expected:

```text
2 passed
```

---

### Task 4: Implement Company Risk Adapter

**Files:**

- Create: `pipelines/risk/company.py`
- Modify only if necessary: `tests/test_risk_workbench_api.py`

- [x] **Step 1: Define adapter behavior**

The company adapter must:

1. Normalize ticker.
2. Call existing Quantamental service functions rather than reimplementing fundamentals or price-risk logic.
3. Convert existing `risk_score` direction into `risk_index` direction.
4. Preserve SEC evidence as evidence items.
5. Return `RiskCompanyProfile` plus evidence list and data-quality observations.

- [x] **Step 2: Create adapter with dependency seams**

Create `pipelines/risk/company.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from core.schemas.risk import (
    RiskCompanyProfile,
    RiskEvidenceItem,
    RiskVector,
)
from pipelines.risk.aggregation import clamp_score, risk_level_for_score


@dataclass(frozen=True)
class CompanyRiskBundle:
    profile: RiskCompanyProfile
    evidence: list[RiskEvidenceItem]
    missing_inputs: list[str]
    stale_inputs: list[str]
    sec_unavailable: bool


def quantamental_score_to_risk_index(score: float | None) -> float | None:
    if score is None:
        return None
    return clamp_score(100.0 - score)


def build_company_profile_from_quantamental_payload(
    ticker: str,
    payload: dict,
) -> CompanyRiskBundle:
    normalized = ticker.strip().upper()
    risk_payload = payload.get("risk") or {}
    source_score = risk_payload.get("risk_score")
    risk_index = quantamental_score_to_risk_index(source_score)
    risk_level = risk_level_for_score(risk_index)

    flags = list(risk_payload.get("risk_flags") or [])
    evidence = [
        RiskEvidenceItem(
            evidence_id=f"{normalized}:risk_flag:{index}",
            source="quantamental",
            label="Risk flag",
            value=flag,
            freshness="unknown",
        )
        for index, flag in enumerate(flags)
    ]

    vectors = [
        RiskVector(
            vector="market_behavior",
            score=risk_index,
            level=risk_level,
            confidence=75.0 if risk_index is not None else 0.0,
            top_drivers=flags[:3],
            evidence_refs=[item.evidence_id for item in evidence],
            decision_usable=risk_index is not None,
        )
    ]

    missing_inputs: list[str] = []
    if payload.get("company") is None:
        missing_inputs.append("fundamentals")
    if payload.get("quant") is None:
        missing_inputs.append("price_data")

    sec_unavailable = payload.get("sec") is None and payload.get("sec_evidence") is None

    return CompanyRiskBundle(
        profile=RiskCompanyProfile(
            ticker=normalized,
            risk_index=risk_index,
            risk_level=risk_level,
            confidence=75.0 if risk_index is not None else 0.0,
            vectors=vectors,
            primary_drivers=flags[:5],
            evidence_refs=[item.evidence_id for item in evidence],
        ),
        evidence=evidence,
        missing_inputs=missing_inputs,
        stale_inputs=[],
        sec_unavailable=sec_unavailable,
    )
```

- [x] **Step 3: Add focused tests for score direction**

Append to `tests/test_risk_workbench_api.py`:

```python
from pipelines.risk.company import quantamental_score_to_risk_index


def test_quantamental_score_is_inverted_for_risk_index():
    assert quantamental_score_to_risk_index(90) == 10
    assert quantamental_score_to_risk_index(25) == 75
    assert quantamental_score_to_risk_index(None) is None
```

- [x] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_risk_workbench_api.py -q
```

Expected:

```text
all tests pass
```

---

### Task 5: Implement Macro Risk Adapter

**Files:**

- Create: `pipelines/risk/macro.py`
- Test: `tests/test_risk_aggregation.py`

- [x] **Step 1: Define macro vector mapping**

Mapping:

```text
policy/rates -> macro_policy_rates
inflation/growth/labor -> macro_growth_inflation
credit/liquidity/financial conditions -> credit_liquidity
unknown or insufficient signal count -> unknown and decision_usable=false for macro vector only
```

- [x] **Step 2: Create macro adapter**

Create `pipelines/risk/macro.py`:

```python
from __future__ import annotations

from core.schemas.risk import RiskEvidenceItem, RiskMacroBackdrop, RiskVector
from pipelines.risk.aggregation import risk_level_for_score


MACRO_LEVEL_TO_SCORE: dict[str, float | None] = {
    "low": 15.0,
    "moderate": 40.0,
    "elevated": 65.0,
    "high": 85.0,
    "unknown": None,
}


def macro_level_to_score(level: str | None) -> float | None:
    if not level:
        return None
    return MACRO_LEVEL_TO_SCORE.get(str(level).lower(), None)


def build_macro_backdrop_from_payload(payload: dict) -> tuple[RiskMacroBackdrop, list[RiskEvidenceItem]]:
    regime = payload.get("regime") or {}
    risk_level = str(regime.get("risk_level") or "unknown").lower()
    score = macro_level_to_score(risk_level)
    level = risk_level_for_score(score)
    signals = list(regime.get("signals") or [])

    evidence = [
        RiskEvidenceItem(
            evidence_id=f"macro:signal:{index}",
            source="macro",
            label=str(signal.get("name") or signal.get("category") or f"signal_{index}"),
            value=signal.get("value"),
            freshness="unknown",
            notes=[str(signal.get("interpretation"))] if signal.get("interpretation") else [],
        )
        for index, signal in enumerate(signals)
        if isinstance(signal, dict)
    ]

    vector = RiskVector(
        vector="macro_growth_inflation",
        score=score,
        level=level,
        confidence=70.0 if score is not None else 0.0,
        top_drivers=[item.label for item in evidence[:3]],
        evidence_refs=[item.evidence_id for item in evidence],
        decision_usable=score is not None,
    )

    return (
        RiskMacroBackdrop(
            regime=str(regime.get("label") or regime.get("regime") or "unknown"),
            risk_level=level,
            confidence=70.0 if score is not None else 0.0,
            vectors=[vector],
            primary_pressures=[item.label for item in evidence[:5]],
            evidence_refs=[item.evidence_id for item in evidence],
        ),
        evidence,
    )
```

- [x] **Step 3: Add test for unknown macro handling**

Append to `tests/test_risk_aggregation.py`:

```python
from pipelines.risk.macro import build_macro_backdrop_from_payload


def test_macro_backdrop_unknown_when_regime_missing():
    backdrop, evidence = build_macro_backdrop_from_payload({})
    assert backdrop.risk_level == "unknown"
    assert backdrop.confidence == 0
    assert backdrop.vectors[0].decision_usable is False
    assert evidence == []
```

- [x] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_risk_aggregation.py -q
```

Expected:

```text
all tests pass
```

---

### Task 6: Implement Transmission Model

**Files:**

- Create: `pipelines/risk/transmission.py`
- Test: `tests/test_risk_transmission.py`

- [x] **Step 1: Write transmission tests**

Create `tests/test_risk_transmission.py`:

```python
from pipelines.risk.transmission import build_transmission_channels


def test_nvda_gets_growth_valuation_channel():
    channels = build_transmission_channels(
        tickers=["NVDA"],
        macro_pressures={"real_rates": "elevated", "liquidity": "elevated"},
        company_vulnerabilities={"NVDA": 70},
    )
    channel_ids = {channel.channel for channel in channels}
    assert "real_rates_to_growth_valuation" in channel_ids
    assert "liquidity_tightening_to_multiple_compression" in channel_ids


def test_jpm_gets_curve_and_credit_channels():
    channels = build_transmission_channels(
        tickers=["JPM"],
        macro_pressures={"yield_curve": "high", "credit": "elevated"},
        company_vulnerabilities={"JPM": 55},
    )
    channel_ids = {channel.channel for channel in channels}
    assert "curve_inversion_to_banks_credit" in channel_ids
    assert "credit_spread_to_financial_conditions" in channel_ids
```

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_risk_transmission.py -q
```

Expected:

```text
ImportError for build_transmission_channels
```

- [x] **Step 3: Implement deterministic transmission catalog**

Create `pipelines/risk/transmission.py`:

```python
from __future__ import annotations

from core.schemas.risk import RiskTransmissionChannel
from pipelines.risk.aggregation import risk_level_for_score


PRESSURE_SCORE: dict[str, float] = {
    "low": 15.0,
    "moderate": 40.0,
    "elevated": 65.0,
    "high": 85.0,
    "unknown": 0.0,
}

GROWTH_TICKERS = {"NVDA", "MSFT", "AAPL", "QQQ", "TSLA", "AMD", "ASML"}
BANK_TICKERS = {"JPM", "BAC", "C", "WFC", "GS", "MS"}
DURATION_TICKERS = {"TLT", "IEF", "EDV"}


def _pressure_value(value: str | None) -> float:
    return PRESSURE_SCORE.get(str(value or "unknown").lower(), 0.0)


def _risk_delta(pressure: str | None, sensitivity: float, vulnerability: float) -> float:
    return round((_pressure_value(pressure) / 100.0) * sensitivity * (vulnerability / 100.0) * 100.0, 2)


def build_transmission_channels(
    *,
    tickers: list[str],
    macro_pressures: dict[str, str],
    company_vulnerabilities: dict[str, float],
) -> list[RiskTransmissionChannel]:
    normalized = [ticker.strip().upper() for ticker in tickers]
    channels: list[RiskTransmissionChannel] = []

    for ticker in normalized:
        vulnerability = company_vulnerabilities.get(ticker, 50.0)

        if ticker in GROWTH_TICKERS and macro_pressures.get("real_rates") in {"elevated", "high"}:
            delta = _risk_delta(macro_pressures.get("real_rates"), 0.85, vulnerability)
            channels.append(
                RiskTransmissionChannel(
                    channel="real_rates_to_growth_valuation",
                    pressure=risk_level_for_score(_pressure_value(macro_pressures.get("real_rates"))),
                    sensitivity=0.85,
                    risk_delta=delta,
                    affected_subjects=[ticker],
                    mechanism="Higher real rates pressure long-duration equity multiples.",
                    evidence_refs=["DGS10", "DFII10", "T5YIFR"],
                )
            )

        if ticker in GROWTH_TICKERS and macro_pressures.get("liquidity") in {"elevated", "high"}:
            delta = _risk_delta(macro_pressures.get("liquidity"), 0.75, vulnerability)
            channels.append(
                RiskTransmissionChannel(
                    channel="liquidity_tightening_to_multiple_compression",
                    pressure=risk_level_for_score(_pressure_value(macro_pressures.get("liquidity"))),
                    sensitivity=0.75,
                    risk_delta=delta,
                    affected_subjects=[ticker],
                    mechanism="Tighter liquidity raises the discount-rate burden on high-multiple equities.",
                    evidence_refs=["WALCL", "M2SL", "NFCI"],
                )
            )

        if ticker in BANK_TICKERS and macro_pressures.get("yield_curve") in {"elevated", "high"}:
            delta = _risk_delta(macro_pressures.get("yield_curve"), 0.80, vulnerability)
            channels.append(
                RiskTransmissionChannel(
                    channel="curve_inversion_to_banks_credit",
                    pressure=risk_level_for_score(_pressure_value(macro_pressures.get("yield_curve"))),
                    sensitivity=0.80,
                    risk_delta=delta,
                    affected_subjects=[ticker],
                    mechanism="Curve inversion can pressure bank net interest margin and signal late-cycle credit risk.",
                    evidence_refs=["T10Y2Y", "T10Y3M"],
                )
            )

        if ticker in BANK_TICKERS and macro_pressures.get("credit") in {"elevated", "high"}:
            delta = _risk_delta(macro_pressures.get("credit"), 0.80, vulnerability)
            channels.append(
                RiskTransmissionChannel(
                    channel="credit_spread_to_financial_conditions",
                    pressure=risk_level_for_score(_pressure_value(macro_pressures.get("credit"))),
                    sensitivity=0.80,
                    risk_delta=delta,
                    affected_subjects=[ticker],
                    mechanism="Wider credit spreads raise expected loss sensitivity and tighten financial conditions.",
                    evidence_refs=["BAMLH0A0HYM2", "BAMLC0A0CM"],
                )
            )

        if ticker in DURATION_TICKERS and macro_pressures.get("real_rates") in {"elevated", "high"}:
            delta = _risk_delta(macro_pressures.get("real_rates"), 0.95, vulnerability)
            channels.append(
                RiskTransmissionChannel(
                    channel="real_rates_to_duration_drawdown",
                    pressure=risk_level_for_score(_pressure_value(macro_pressures.get("real_rates"))),
                    sensitivity=0.95,
                    risk_delta=delta,
                    affected_subjects=[ticker],
                    mechanism="Long-duration bonds are directly exposed to real-rate repricing.",
                    evidence_refs=["DGS10", "DFII10"],
                )
            )

    return sorted(channels, key=lambda channel: channel.risk_delta, reverse=True)
```

- [x] **Step 4: Run transmission tests**

Run:

```powershell
python -m pytest tests/test_risk_transmission.py -q
```

Expected:

```text
2 passed
```

---

### Task 7: Implement Scenario Matrix

**Files:**

- Create: `pipelines/risk/scenario.py`
- Test: `tests/test_risk_transmission.py`

- [x] **Step 1: Add scenario test**

Append to `tests/test_risk_transmission.py`:

```python
from pipelines.risk.scenario import build_scenario_matrix


def test_scenario_matrix_projects_risk_index_delta():
    scenarios = build_scenario_matrix(
        current_risk_index=60,
        transmission_deltas={"real_rates_to_growth_valuation": 8, "credit_spread_to_financial_conditions": 4},
        scenario_set="base_adverse_severe",
    )
    assert [scenario.severity for scenario in scenarios] == ["base", "adverse", "severe"]
    assert scenarios[0].projected_risk_index == 63
    assert scenarios[2].projected_risk_index > scenarios[1].projected_risk_index
```

- [x] **Step 2: Implement scenario builder**

Create `pipelines/risk/scenario.py`:

```python
from __future__ import annotations

from core.schemas.risk import RiskScenarioResult
from pipelines.risk.aggregation import clamp_score


SCENARIO_MULTIPLIERS: dict[str, list[tuple[str, str, float]]] = {
    "base_adverse_severe": [
        ("base", "Base stress", 0.25),
        ("adverse", "Adverse macro stress", 0.75),
        ("severe", "Severe macro stress", 1.25),
    ],
    "rates_credit_liquidity": [
        ("base", "Rates pressure", 0.35),
        ("adverse", "Rates and credit pressure", 0.90),
        ("severe", "Rates, credit, and liquidity shock", 1.40),
    ],
    "inflation_growth_policy": [
        ("base", "Sticky inflation", 0.35),
        ("adverse", "Sticky inflation with growth slowdown", 0.85),
        ("severe", "Policy error with growth shock", 1.35),
    ],
}


def build_scenario_matrix(
    *,
    current_risk_index: float | None,
    transmission_deltas: dict[str, float],
    scenario_set: str,
) -> list[RiskScenarioResult]:
    if current_risk_index is None:
        return []

    total_delta = sum(max(0.0, value) for value in transmission_deltas.values())
    top_channels = [
        channel for channel, _ in sorted(transmission_deltas.items(), key=lambda item: item[1], reverse=True)[:3]
    ]

    scenarios: list[RiskScenarioResult] = []
    for severity, label, multiplier in SCENARIO_MULTIPLIERS.get(
        scenario_set,
        SCENARIO_MULTIPLIERS["base_adverse_severe"],
    ):
        delta = round(total_delta * multiplier, 2)
        scenarios.append(
            RiskScenarioResult(
                scenario_id=f"{scenario_set}:{severity}",
                label=label,
                severity=severity,
                risk_index_delta=delta,
                projected_risk_index=clamp_score(current_risk_index + delta),
                top_damage_channels=top_channels,
            )
        )
    return scenarios
```

- [x] **Step 3: Run scenario tests**

Run:

```powershell
python -m pytest tests/test_risk_transmission.py -q
```

Expected:

```text
all tests pass
```

---

### Task 8: Implement Risk Service Orchestration

**Files:**

- Create: `pipelines/risk/service.py`
- Test: `tests/test_risk_workbench_api.py`

- [x] **Step 1: Add service shape test**

Append to `tests/test_risk_workbench_api.py`:

```python
from pipelines.risk.service import build_risk_workbench_response


def test_service_builds_fail_closed_response_for_invalid_subject():
    response = build_risk_workbench_response(
        request=RiskWorkbenchRequest(mode="company", tickers=["INVALID_TEST_TICKER_123"]),
        company_payloads={},
        macro_payload={},
    )
    assert response.decision_usable is False
    assert response.risk_level == "unknown"
    assert "INVALID_TEST_TICKER_123" in response.primary_drivers[0]
```

- [x] **Step 2: Implement service seam**

Create `pipelines/risk/service.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from core.schemas.risk import (
    RiskCalculationPolicy,
    RiskDataQuality,
    RiskMacroBackdrop,
    RiskWorkbenchRequest,
    RiskWorkbenchResponse,
)
from pipelines.risk.aggregation import BASE_RISK_WEIGHTS, risk_level_for_score, weighted_risk_index
from pipelines.risk.company import build_company_profile_from_quantamental_payload
from pipelines.risk.data_quality import evaluate_risk_data_quality
from pipelines.risk.macro import build_macro_backdrop_from_payload
from pipelines.risk.scenario import build_scenario_matrix
from pipelines.risk.transmission import build_transmission_channels


def _input_hash(request: RiskWorkbenchRequest) -> str:
    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_risk_workbench_response(
    *,
    request: RiskWorkbenchRequest,
    company_payloads: dict[str, dict],
    macro_payload: dict,
) -> RiskWorkbenchResponse:
    normalized_tickers = request.tickers or [position.ticker.upper() for position in request.positions or []]
    missing_company_payloads = [ticker for ticker in normalized_tickers if ticker not in company_payloads]

    company_profiles = []
    evidence = []
    missing_inputs = []
    stale_inputs = []
    sec_unavailable = False

    for ticker in normalized_tickers:
        payload = company_payloads.get(ticker)
        if payload is None:
            missing_inputs.append("price_data")
            missing_inputs.append("fundamentals")
            continue
        bundle = build_company_profile_from_quantamental_payload(ticker, payload)
        company_profiles.append(bundle.profile)
        evidence.extend(bundle.evidence)
        missing_inputs.extend(bundle.missing_inputs)
        stale_inputs.extend(bundle.stale_inputs)
        sec_unavailable = sec_unavailable or bundle.sec_unavailable

    macro_backdrop, macro_evidence = build_macro_backdrop_from_payload(macro_payload)
    evidence.extend(macro_evidence)

    if missing_company_payloads:
        data_quality = RiskDataQuality(
            decision_usable=False,
            freshness="missing",
            missing_inputs=sorted(set(missing_inputs)),
            penalty=100.0,
            confidence_penalty=100.0,
        )
        return RiskWorkbenchResponse(
            risk_run_id=f"risk_{uuid4().hex[:12]}",
            input_hash=_input_hash(request),
            mode=request.mode,
            risk_index=None,
            risk_level="unknown",
            confidence=0.0,
            decision_usable=False,
            as_of=datetime.now(timezone.utc),
            primary_drivers=[f"Missing company risk payload for {', '.join(missing_company_payloads)}"],
            company_profiles=company_profiles,
            macro_backdrop=macro_backdrop,
            evidence=evidence,
            data_quality=data_quality,
            calculation_policy=RiskCalculationPolicy(weights=BASE_RISK_WEIGHTS),
        )

    data_quality = evaluate_risk_data_quality(
        missing_inputs=sorted(set(missing_inputs)),
        stale_inputs=sorted(set(stale_inputs)),
        provider_warnings=[],
        sec_unavailable=sec_unavailable,
    )

    company_component = (
        sum(profile.risk_index for profile in company_profiles if profile.risk_index is not None) / len(company_profiles)
        if company_profiles
        else None
    )
    macro_component = macro_backdrop.vectors[0].score if macro_backdrop.vectors else None

    vulnerabilities = {
        profile.ticker: profile.risk_index or 50.0
        for profile in company_profiles
    }
    transmission_channels = build_transmission_channels(
        tickers=[profile.ticker for profile in company_profiles],
        macro_pressures={
            "real_rates": macro_backdrop.risk_level,
            "liquidity": macro_backdrop.risk_level,
            "credit": macro_backdrop.risk_level,
            "yield_curve": macro_backdrop.risk_level,
        },
        company_vulnerabilities=vulnerabilities,
    )
    transmission_component = max((channel.risk_delta for channel in transmission_channels), default=0.0)

    risk_index = weighted_risk_index(
        {
            "company_fundamental_vulnerability": company_component,
            "market_behavior_risk": company_component,
            "macro_regime_risk": macro_component,
            "credit_liquidity_risk": macro_component,
            "transmission_sensitivity": transmission_component,
            "data_quality_penalty": data_quality.penalty,
        }
    )
    risk_level = risk_level_for_score(risk_index)
    confidence = max(0.0, min(100.0, 100.0 - data_quality.confidence_penalty))

    scenario_matrix = build_scenario_matrix(
        current_risk_index=risk_index,
        transmission_deltas={channel.channel: channel.risk_delta for channel in transmission_channels},
        scenario_set=request.scenario_set,
    )

    primary_drivers = [
        *(profile.primary_drivers[0:1] for profile in company_profiles if profile.primary_drivers),
    ]
    flat_drivers = [driver for group in primary_drivers for driver in group]
    if transmission_channels:
        flat_drivers.append(transmission_channels[0].mechanism)

    return RiskWorkbenchResponse(
        risk_run_id=f"risk_{uuid4().hex[:12]}",
        input_hash=_input_hash(request),
        mode=request.mode,
        risk_index=risk_index,
        risk_level=risk_level,
        confidence=confidence,
        decision_usable=data_quality.decision_usable and macro_backdrop.risk_level != "unknown",
        as_of=datetime.now(timezone.utc),
        primary_drivers=flat_drivers[:5],
        risk_vectors=[vector for profile in company_profiles for vector in profile.vectors] + macro_backdrop.vectors,
        company_profiles=company_profiles,
        macro_backdrop=macro_backdrop,
        transmission_channels=transmission_channels,
        scenario_matrix=scenario_matrix,
        evidence=evidence,
        data_quality=data_quality,
        calculation_policy=RiskCalculationPolicy(weights=BASE_RISK_WEIGHTS),
    )
```

- [x] **Step 3: Run service tests**

Run:

```powershell
python -m pytest tests/test_risk_workbench_api.py -q
```

Expected:

```text
all tests pass
```

---

### Task 9: Add FastAPI Router

**Files:**

- Create: `app/api/routers/risk.py`
- Modify: `app/api/server.py`
- Test: `tests/test_risk_workbench_api.py`

- [x] **Step 1: Add API test using TestClient pattern already present in repo**

Extend `tests/test_risk_workbench_api.py` with the repo's existing app import pattern:

```python
from fastapi.testclient import TestClient

from app.api.server import app


client = TestClient(app)


def test_risk_health_endpoint():
    response = client.get("/api/v1/risk/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["service"] == "risk"
```

- [x] **Step 2: Create router**

Create `app/api/routers/risk.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from core.schemas.risk import RiskWorkbenchRequest, RiskWorkbenchResponse
from pipelines.risk.service import build_risk_workbench_response


router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/health")
async def risk_health() -> dict[str, str]:
    return {"status": "ok", "service": "risk"}


@router.post("/workbench", response_model=RiskWorkbenchResponse)
async def risk_workbench(request: RiskWorkbenchRequest) -> RiskWorkbenchResponse:
    return build_risk_workbench_response(
        request=request,
        company_payloads={},
        macro_payload={},
    )


@router.get("/company/{ticker}", response_model=RiskWorkbenchResponse)
async def risk_company(ticker: str) -> RiskWorkbenchResponse:
    request = RiskWorkbenchRequest(mode="company", tickers=[ticker])
    return build_risk_workbench_response(
        request=request,
        company_payloads={},
        macro_payload={},
    )


@router.get("/macro")
async def risk_macro() -> dict[str, str]:
    return {"status": "ok", "scope": "macro"}


@router.post("/scenario")
async def risk_scenario(request: RiskWorkbenchRequest) -> RiskWorkbenchResponse:
    return build_risk_workbench_response(
        request=request,
        company_payloads={},
        macro_payload={},
    )
```

- [x] **Step 3: Register router**

Modify `app/api/server.py` to import and include the router using existing route style:

```python
from app.api.routers import risk
```

and:

```python
app.include_router(risk.router, prefix="/api/v1")
```

- [x] **Step 4: Replace stub payloads with real service calls**

After route shape is green, wire `risk_workbench` to existing Quantamental and Macro service functions through adapter seams. Keep slow or blocking calls behind `asyncio.to_thread` if existing macro/quantamental routes already use that pattern.

Concrete target:

```python
@router.post("/workbench", response_model=RiskWorkbenchResponse)
async def risk_workbench(request: RiskWorkbenchRequest) -> RiskWorkbenchResponse:
    company_payloads = await load_company_payloads(request)
    macro_payload = await load_macro_payload()
    return build_risk_workbench_response(
        request=request,
        company_payloads=company_payloads,
        macro_payload=macro_payload,
    )
```

`load_company_payloads` must call the existing Quantamental service layer, not duplicate SEC, fundamental, or quant calculations.

- [x] **Step 5: Run API tests**

Run:

```powershell
python -m pytest tests/test_risk_workbench_api.py -q
```

Expected:

```text
all tests pass
```

---

### Task 10: Add Dashboard Decision Card Contract

**Files:**

- Modify: `app/api/routers/dashboard.py`
- Modify: `scripts/check_ui_contract.py`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_ui_routing_contract.py`

- [x] **Step 1: Add contract test**

Add a dashboard test that expects a risk decision card:

```python
def test_dashboard_decision_cards_include_risk():
    response = client.get("/api/v1/dashboard/decision-cards")
    assert response.status_code == 200
    payload = response.json()
    card_ids = {card["id"] for card in payload["cards"]}
    assert "risk" in card_ids
```

- [x] **Step 2: Add risk card to existing decision-card registry**

In `app/api/routers/dashboard.py`, extend the existing decision card definitions with:

```python
{
    "id": "risk",
    "label": "Risk",
    "status": "available",
    "summary": "Enterprise and macro risk workbench with company, macro, transmission, scenario, and data-quality views.",
    "href": "/ui/#risk",
    "priority": 3,
}
```

Match the actual existing field names in `_DECISION_CARD_CONTRACTS`; do not introduce a parallel structure.

- [x] **Step 3: Add UI contract markers**

Extend `scripts/check_ui_contract.py` to require:

```text
riskDashboardTab
riskWorkbenchPanel
riskExecutiveStrip
riskDriverWaterfall
riskCompanyTable
riskMacroPressurePanel
riskTransmissionMatrix
riskScenarioMatrix
riskEvidenceDrawer
```

- [x] **Step 4: Run contract tests**

Run:

```powershell
python -m pytest tests/test_dashboard_api.py tests/test_ui_routing_contract.py -q
python scripts/check_ui_contract.py
```

Expected:

```text
pytest passes
UI contract script exits 0
```

---

### Task 11: Add Static UI Markup

**Files:**

- Modify: `app/web/index.html`
- Test: `scripts/check_ui_contract.py`

- [x] **Step 1: Add Risk dashboard tab**

Add a top-level button near existing dashboard tabs:

```html
<button
  id="riskDashboardTab"
  class="dashboard-tab"
  type="button"
  data-dashboard-tab-target="risk"
  aria-pressed="false"
>
  Risk
</button>
```

Use the exact classes and data attributes already used by neighboring dashboard tabs.

- [x] **Step 2: Add Risk panel section**

Add a dashboard section:

```html
<section
  id="riskWorkbenchPanel"
  class="dashboard-panel"
  data-dashboard-tab="risk"
  data-panel-tier="primary"
  hidden
>
  <div class="risk-command-bar" id="riskCommandBar">
    <div class="segmented-control" role="group" aria-label="Risk mode">
      <button type="button" data-risk-mode="company" aria-pressed="true">Company</button>
      <button type="button" data-risk-mode="watchlist" aria-pressed="false">Watchlist</button>
      <button type="button" data-risk-mode="portfolio" aria-pressed="false">Portfolio</button>
    </div>
    <input id="riskTickerInput" type="text" value="NVDA" aria-label="Risk ticker input" />
    <select id="riskScenarioSelect" aria-label="Risk scenario set">
      <option value="base_adverse_severe">Base / adverse / severe</option>
      <option value="rates_credit_liquidity">Rates / credit / liquidity</option>
      <option value="inflation_growth_policy">Inflation / growth / policy</option>
    </select>
    <button id="riskRefreshButton" type="button">Run Risk</button>
  </div>

  <div id="riskExecutiveStrip" class="risk-executive-strip" aria-live="polite"></div>
  <div id="riskDriverWaterfall" class="risk-driver-waterfall"></div>
  <div id="riskCompanyTable" class="risk-company-table"></div>
  <div id="riskMacroPressurePanel" class="risk-macro-pressure-panel"></div>
  <div id="riskTransmissionMatrix" class="risk-transmission-matrix"></div>
  <div id="riskScenarioMatrix" class="risk-scenario-matrix"></div>
  <details id="riskEvidenceDrawer" class="risk-evidence-drawer">
    <summary>Evidence and data quality</summary>
    <div id="riskEvidenceContent"></div>
  </details>
</section>
```

Refine class names to match existing naming conventions if the repo already uses another dashboard-panel class pattern.

- [x] **Step 3: Run UI contract check**

Run:

```powershell
python scripts/check_ui_contract.py
```

Expected:

```text
contract check passes
```

---

### Task 12: Add Frontend State, API Client, Renderers

**Files:**

- Modify: `app/web/app.js`
- Test: `tests/test_ui_modules.py`
- Test: `scripts/check_ui_contract.py`

- [x] **Step 1: Add API route constants**

Extend the existing API object:

```javascript
risk: {
  health: `${API_BASE}/risk/health`,
  workbench: `${API_BASE}/risk/workbench`,
  company: (ticker) => `${API_BASE}/risk/company/${encodeURIComponent(ticker)}`,
  macro: `${API_BASE}/risk/macro`,
  scenario: `${API_BASE}/risk/scenario`,
},
```

- [x] **Step 2: Add state**

Extend app state:

```javascript
risk: {
  mode: "company",
  tickers: ["NVDA"],
  scenarioSet: "base_adverse_severe",
  loading: false,
  error: null,
  response: null,
},
```

- [x] **Step 3: Add loader**

Add a loader that follows existing fetch/error patterns:

```javascript
async function loadRiskWorkbench() {
  state.risk.loading = true;
  state.risk.error = null;
  renderRiskWorkbench();

  const payload = {
    mode: state.risk.mode,
    tickers: state.risk.tickers,
    scenario_set: state.risk.scenarioSet,
    include_sec: true,
    include_macro_scenarios: true,
    force_refresh: false,
  };

  try {
    const response = await fetch(API.risk.workbench, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`Risk request failed with HTTP ${response.status}`);
    }
    state.risk.response = await response.json();
  } catch (error) {
    state.risk.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.risk.loading = false;
    renderRiskWorkbench();
  }
}
```

- [x] **Step 4: Add renderer shell**

```javascript
function renderRiskWorkbench() {
  const strip = document.getElementById("riskExecutiveStrip");
  const waterfall = document.getElementById("riskDriverWaterfall");
  const companyTable = document.getElementById("riskCompanyTable");
  const macroPanel = document.getElementById("riskMacroPressurePanel");
  const transmission = document.getElementById("riskTransmissionMatrix");
  const scenarios = document.getElementById("riskScenarioMatrix");
  const evidence = document.getElementById("riskEvidenceContent");

  if (!strip || !waterfall || !companyTable || !macroPanel || !transmission || !scenarios || !evidence) {
    return;
  }

  if (state.risk.loading) {
    strip.innerHTML = `<div class="status-row">Loading risk workbench...</div>`;
    waterfall.innerHTML = "";
    companyTable.innerHTML = "";
    macroPanel.innerHTML = "";
    transmission.innerHTML = "";
    scenarios.innerHTML = "";
    evidence.innerHTML = "";
    return;
  }

  if (state.risk.error) {
    strip.innerHTML = `<div class="error-state">${escapeHtml(state.risk.error)}</div>`;
    return;
  }

  const result = state.risk.response;
  if (!result) {
    strip.innerHTML = `<div class="empty-state">Run a risk analysis to view company and macro risk.</div>`;
    return;
  }

  renderRiskExecutiveStrip(strip, result);
  renderRiskDriverWaterfall(waterfall, result);
  renderRiskCompanyTable(companyTable, result.company_profiles || []);
  renderRiskMacroPanel(macroPanel, result.macro_backdrop);
  renderRiskTransmissionMatrix(transmission, result.transmission_channels || []);
  renderRiskScenarioMatrix(scenarios, result.scenario_matrix || []);
  renderRiskEvidence(evidence, result);
}
```

Use the repo's existing escaping helper name. If it is not `escapeHtml`, use the actual helper.

- [x] **Step 5: Add event bindings**

Bind:

```javascript
document.getElementById("riskRefreshButton")?.addEventListener("click", () => {
  const tickerInput = document.getElementById("riskTickerInput");
  const scenarioSelect = document.getElementById("riskScenarioSelect");
  state.risk.tickers = String(tickerInput?.value || "NVDA")
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean);
  state.risk.scenarioSet = String(scenarioSelect?.value || "base_adverse_severe");
  loadRiskWorkbench();
});
```

Also integrate with the existing dashboard tab click handler so `#risk` activates the Risk panel.

- [x] **Step 6: Run JS and UI checks**

Run:

```powershell
node --check app/web/app.js
python scripts/check_ui_contract.py
python -m pytest tests/test_ui_modules.py -q
```

Expected:

```text
all checks pass
```

---

### Task 13: Add Risk CSS

**Files:**

- Modify: `app/web/styles.css`

- [x] **Step 1: Add tab visibility rules**

Extend existing dashboard tab CSS selectors to include:

```css
[data-active-dashboard-tab="risk"] [data-dashboard-tab]:not([data-dashboard-tab="risk"]) {
  display: none;
}
```

Match the existing selector style in the file rather than duplicating a conflicting visibility system.

- [x] **Step 2: Add stable panel layouts**

Add compact, professional layouts:

```css
.risk-command-bar {
  display: grid;
  grid-template-columns: minmax(220px, auto) minmax(160px, 1fr) minmax(180px, auto) auto;
  gap: 0.75rem;
  align-items: center;
}

.risk-executive-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 0.75rem;
}

.risk-driver-waterfall,
.risk-company-table,
.risk-macro-pressure-panel,
.risk-transmission-matrix,
.risk-scenario-matrix,
.risk-evidence-drawer {
  min-width: 0;
}

.risk-company-table table,
.risk-transmission-matrix table,
.risk-scenario-matrix table {
  width: 100%;
  border-collapse: collapse;
}

@media (max-width: 760px) {
  .risk-command-bar,
  .risk-executive-strip {
    grid-template-columns: 1fr;
  }
}
```

Adjust variable names, spacing, and color tokens to existing stylesheet conventions.

- [x] **Step 3: Browser smoke**

After local server starts, open:

```text
http://127.0.0.1:<port>/ui/#risk
```

Verify:

```text
Risk tab is active
No text overlaps at desktop width
No horizontal overflow at mobile width
Loading, empty, error, and loaded states render coherently
Evidence drawer is reachable
```

---

### Task 14: Documentation Updates

**Files:**

- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PROJECT_MAP.md`
- Modify: `docs/UI_TAB_DECISION_CHECKLIST.md`

- [x] **Step 1: Update architecture**

Add a section:

```markdown
### Enterprise-Macro Risk Workbench

The Risk workbench is a deterministic orchestration layer over Quantamental, Macro, Portfolio, and Dashboard services. It does not generate investment recommendations. It exposes company risk vectors, macro backdrop, transmission channels, scenario matrix, evidence, freshness, and decision-usable status through `/api/v1/risk/*`.

Risk scores use `higher_is_riskier` direction. Source scores with opposite direction, including Quantamental company risk scores, are converted at the adapter boundary and annotated in the calculation policy.
```

- [x] **Step 2: Update project map**

Add:

```markdown
- `pipelines/risk/`: enterprise-macro risk orchestration, company adapter, macro adapter, transmission model, scenario matrix, data-quality policy, and weighted aggregation.
- `core/schemas/risk.py`: typed API contracts for Risk workbench requests and responses.
- `app/api/routers/risk.py`: FastAPI routes under `/api/v1/risk`.
```

- [x] **Step 3: Update UI checklist**

Add Risk tab acceptance:

```markdown
### Risk Tab

- Shows decision-usable and freshness status in the first viewport.
- Decomposes risk into company, market, macro, credit/liquidity, transmission, and data-quality components.
- Shows evidence and calculation policy.
- Handles unknown, partial, stale, and error states without presenting them as valid risk conclusions.
- Does not display direct buy/sell/hold instructions.
```

---

### Task 15: Full Verification Ladder

**Files:**

- No new files

- [x] **Step 1: Python syntax**

Run:

```powershell
python -m py_compile core/schemas/risk.py app/api/routers/risk.py pipelines/risk/aggregation.py pipelines/risk/company.py pipelines/risk/data_quality.py pipelines/risk/macro.py pipelines/risk/scenario.py pipelines/risk/service.py pipelines/risk/transmission.py
```

Expected:

```text
no output and exit code 0
```

- [x] **Step 2: Targeted unit tests**

Run:

```powershell
python -m pytest tests/test_risk_aggregation.py tests/test_risk_transmission.py tests/test_risk_data_quality.py tests/test_risk_workbench_api.py -q
```

Expected:

```text
all tests pass
```

- [x] **Step 3: Existing integration regression**

Run:

```powershell
python -m pytest tests/test_quantamental_api.py tests/test_macro_platform.py tests/test_dashboard_api.py tests/test_ai_portfolio_api.py -q
```

Expected:

```text
all tests pass or pre-existing unrelated failures are documented with exact failure names
```

- [x] **Step 4: Frontend syntax and contract**

Run:

```powershell
node --check app/web/app.js
python scripts/check_ui_contract.py
python -m pytest tests/test_ui_modules.py tests/test_ui_routing_contract.py -q
```

Expected:

```text
all checks pass
```

- [x] **Step 5: Browser verification**

Start the supported web server using the repo's existing launcher. Then verify:

```text
/ui/#risk
```

Manual smoke cases:

```text
NVDA: real-rate, liquidity, valuation transmission visible
JPM: curve and credit transmission visible
TLT: duration/rates stress visible
INVALID_TEST_TICKER_123: fail-closed, no fabricated metrics
```

Acceptance:

```text
Risk tab loads
Run Risk button works
Risk Executive Strip renders
Risk Driver Waterfall renders
Company Risk Table renders
Macro Pressure Panel renders
Transmission Matrix renders
Scenario Matrix renders
Evidence Drawer renders
Unknown/partial/stale states are visible and not hidden
No direct buy/sell recommendation appears
```

---

## 8. Implementation Order

Execute in this order:

1. Schemas
2. Aggregation
3. Data quality
4. Company adapter
5. Macro adapter
6. Transmission
7. Scenario
8. Service
9. Router
10. Dashboard decision-card contract
11. UI markup
12. JS state/render/load
13. CSS
14. Docs
15. Full verification

Stop conditions:

1. If Quantamental service call shape differs from assumptions, inspect `pipelines/quantamental/service.py` and adapt the company adapter instead of duplicating calculations.
2. If Macro dashboard payload shape differs from assumptions, inspect `pipelines/macro/dashboard.py` and adapt `pipelines/risk/macro.py`.
3. If existing working tree contains unrelated user changes in touched files, preserve them and patch only the Risk-specific sections.
4. If browser smoke cannot run because the server is unavailable, report the exact launcher command, port, and error.

---

## 9. Definition Of Done

The Risk tab is done only when:

1. `/api/v1/risk/health` works.
2. `/api/v1/risk/workbench` returns typed deterministic risk output.
3. Company, macro, transmission, scenario, evidence, and data-quality fields are populated or explicitly marked unavailable.
4. `/ui/#risk` loads and renders all required panels.
5. Invalid tickers fail closed.
6. Stale/missing data is visible in the first user journey.
7. No AI-generated score or fabricated metric is used.
8. Existing Macro, Quantamental, Dashboard, AI Portfolio, and UI contract tests are not regressed.
9. Documentation explains the boundary and score direction.

---

## 10. First Execution Recommendation

Start with Tasks 1-3 in one small implementation slice:

```text
core/schemas/risk.py
pipelines/risk/aggregation.py
pipelines/risk/data_quality.py
tests/test_risk_aggregation.py
tests/test_risk_data_quality.py
tests/test_risk_workbench_api.py
```

This creates the contract and deterministic scoring foundation without touching the UI or live routers. After that foundation is green, proceed to adapters and API wiring.
