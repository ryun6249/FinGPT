# FinGPT 로컬 리서치 어시스턴트

FinGPT와 RAG(Retrieval-Augmented Generation)를 결합한 **로컬 실행형 금융 리서치 어시스턴트**입니다. 외부 API에 의존하지 않고 프라이버시를 유지한 채로, 종목 하나에 대한 심층 분석을 한 번의 명령으로 실행할 수 있습니다.

## 시작 방법

### 최단 경로 (한 줄 실행)

Windows에서 원클릭 스크립트 한 개로 환경 준비부터 샘플 분석까지 끝낼 수 있습니다.

```bash
cd FinGPT
powershell -ExecutionPolicy Bypass -File scripts/quickstart.ps1
```

원하는 종목과 질문으로 실행하려면 파라미터를 전달하세요.

```bash
powershell -ExecutionPolicy Bypass -File scripts/quickstart.ps1 -Ticker NVDA -Question "다음 분기 핵심 상방/하방 촉매는?"
```

이 스크립트는 다음 작업을 자동으로 수행합니다.

- `venv311` 가상환경 생성 및 활성화
- `requirements.txt` 의존성 설치
- `.env` 파일 준비 (없으면 `.env.example`에서 복사)
- Qdrant/Ollama 연결 상태 점검
- 지정한 종목으로 샘플 리서치 실행

### 사전 준비

스크립트 실행 전에 아래 도구가 설치 및 실행 상태여야 합니다.

1. **Python 3.11** — 프로젝트 표준 런타임 버전입니다.
2. **Docker Desktop** — 벡터 DB인 Qdrant를 띄우기 위해 필요하며, **실행 중** 상태여야 합니다.
3. **Ollama** — 로컬 LLM 추론에 사용합니다.
   - [ollama.com](https://ollama.com/)에서 설치합니다.
   - 설치 후 `ollama serve`로 데몬을 띄웁니다 (트레이에서 이미 실행 중이면 "port in use" 오류가 뜨지만 무시해도 됩니다).
   - 기본 모델을 내려받습니다: `ollama pull qwen2.5:7b`.

### 단계별 수동 실행 (스크립트를 쓰지 않을 때)

원클릭 스크립트가 맞지 않거나 각 단계를 직접 확인하고 싶을 때 사용합니다.

```bash
cd FinGPT

py -3.11 -m venv venv311
.\venv311\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env

powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1

# OpenBB Workspace custom agent를 실제로 연결할 때만 선택 실행
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local.ps1 -WithOpenBBAgent

python app/cli/main.py --ticker AAPL --question "최근 실적 발표에서 가장 중요한 단기 리스크는 무엇인가?"
```

### 웹 UI 실행 (선택)

브라우저에서 종목, 질문, 소스, 조회 기간, top-k, 모델 라우트를 바꿔가며 실행하고 싶다면 웹 UI를 띄우세요. 요약·상승/하락 테제·인용·증거 문서·원본 JSON까지 한 화면에서 확인할 수 있습니다.

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_web.ps1
```

- UI: `http://127.0.0.1:8000/ui/`
- API 문서: `http://127.0.0.1:8000/docs`

### Local Data Mart Update

Structured financial data is stored separately from Qdrant in `data/research_mart.db`.
Use this for daily prices, macro observations, news metadata, SEC filing metadata, provider status, and data quality checks:

```bash
python scripts/daily_update.py --market us --json
python scripts/daily_update.py --market kr --skip-macro --json
```

Use `--skip-news`, `--skip-macro`, or `--skip-filings` when a provider is intentionally unavailable during a recovery run.

For Windows Task Scheduler, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_daily_update.ps1 -Market us
```

Qdrant remains the document evidence store for news, filings, transcripts, and current-run RAG chunks. `data/runs.db` remains the research-run history database.

### Strategy Research Lab

The UI includes an Auto Trading tab at `/ui/#auto-trading`.
It owns strategy definition, local LLM strategy drafts, dry-run validation, repo-local deterministic strategy optimization, failure diagnostics, structured hypotheses, validation evidence, and version tracking under `/api/v1/quant/strategy-research/*`.
The top `Auto Trading Workbench` card is the strategy operation surface: choose the asset universe, edit the governed JSON strategy script, generate a local-LLM draft, validate it, run the Quant backtest, view internal-data entry/exit markers, and launch Bayesian optimization from the same tab. It also exposes Python Strategy Lab through `POST /api/v1/quant/python-strategy/run`: natural-language intent is converted into validated Python strategy code plus a parameter manifest, then the same manifest drives backtest, Bayesian optimization, verified result explanation, parameter sensitivity, and indicator-style entry/exit visuals for Supertrend, moving-average crossover, and RSI reversion strategies.

The Bayesian optimization path uses Optuna TPE when available and exposes an explicit fallback status if Optuna is unavailable. The BTCUSDT 4H Supertrend preset is repo-local deterministic evidence; protected LEAN/live/broker evidence remains fail-closed unless `/api/v1/quant/strategy-research/protected-runtime/status` reports availability.

This workflow is for strategy research evidence only. It does not provide financial advice, live execution, protected LEAN evidence, or buy/sell recommendations. See `docs/strategy-research-user-guide.md` for usage and verification commands.

수동으로 띄울 때는 다음 명령을 사용합니다.

```bash
python -m uvicorn app.api.server:app --host 127.0.0.1 --port 8000 --reload
```

---

## 동작 방식

입력은 **종목 코드(ticker)** 와 **질문(question)** 두 가지뿐입니다. 어시스턴트는 아래 6단계를 순서대로 실행합니다.

1. **Collect (수집)**: 소스별 타임아웃에 따라 원문 문서를 모읍니다. 기본 소스는 `news`이고, `transcript`는 보조, `report`는 운영 경로에서 의도적으로 꺼져 있습니다.
2. **Ingest (적재)**: 이번 실행에서 모은 문서를 정규화해 벡터 DB(Qdrant)에 넣습니다.
3. **Retrieve (검색)**: 시맨틱 검색으로 관련 컨텍스트를 뽑은 뒤, 이번 실행에서 수집된 문서 ID만 남겨 **과거 문서가 결과에 섞이지 않도록** 격리합니다.
4. **Infer (추론)**: 프롬프트와 컨텍스트를 Ollama의 구조화 출력 경로로 전달합니다. JSON이 깨지거나 잘리면 제한된 횟수만큼 자동 재시도합니다.
5. **Analyze (분석)**: 모델 출력 JSON을 파싱해 감성(sentiment), 상승/하락 촉매, 핵심 수치, 타임라인 같은 속성으로 매핑합니다.
6. **Report (보고)**: 최종 Markdown/HTML 보고서를 생성해 `data/outputs/`에 저장합니다.

더 자세한 설계는 `docs/PROJECT_MAP.md`, `docs/ARCHITECTURE.md`를 참고하세요.

### 기술 스택 요약

- **뉴스 수집**: Yahoo Finance를 1차로 시도하고, 결과가 부족하면 SEC EDGAR 최근 공시 → Google News RSS → OpenBB(호환성 통과/옵션) → Alpha Vantage(옵션) → FMP(옵션) 순서로 보강합니다.
- **트랜스크립트**: 기본값은 비활성화입니다. `FMP_ENABLED=true`와 `FMP_API_KEY`를 설정한 경우에만 FMP 트랜스크립트를 보조 소스로 사용합니다.
- **벡터 DB**: Qdrant (Docker Desktop 기반, 저장소의 Compose 스택이 자동으로 띄움).
- **LLM**: 로컬 Ollama. 운영 기본 모델은 `qwen2.5:7b`이며, `gemma4:e4b`는 실험용 옵션으로만 제공됩니다.

## 문제 해결

### `Error: listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address...`

Ollama가 이미 트레이에서 돌고 있다는 신호입니다. `ollama serve`를 다시 띄울 필요 없이 다음 단계로 넘어가면 됩니다.

### `docker: command not found` 또는 `Docker daemon not reachable`

Docker Desktop이 설치되어 있고 실행 중인지 확인하세요. 방금 설치했다면 터미널이나 PC를 한 번 재시작하면 해결됩니다.

### `app/cli/main.py` 실행 시 `No such file or directory`

현재 경로가 `FinGPT` 루트가 아닐 때 발생합니다. `pwd`로 경로를 확인하고 `ls`로 `app/` 폴더가 있는지 확인하세요.

## 기타 명령어

- **벤치마크 스윕**: `python quality_review.py --suite all`
- **토픽 지연시간 프로파일**: `python quality_review.py --suite topic --measure-latency`
- **지연시간 프로파일 아티팩트 생성**: `python scripts/profile_topic_latency.py`
- **빠른 통합 검증 게이트**: `powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1`
- **UI/API 계약 스모크**: `python scripts/check_ui_contract.py`
- **릴리스 후보 live 검증**: `powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1 -ReleaseCandidate`
- **OpenBB Workspace agent 포함 검증**: `powershell -ExecutionPolicy Bypass -File scripts/verify_production_path.ps1 -WithOpenBBAgent`

실행 결과는 `data/outputs/` 폴더에 구조화 JSON, Markdown 보고서, 렌더링된 HTML 형태로 저장됩니다.

## 출력 기준일 / Topic 정량 보강

- 모든 `key_metrics` 값은 `as_of` 기준일을 포함합니다. 모델이 누락하면 근거 문서 날짜로 보강하고, 그래도 없으면 `unknown`으로 표시합니다.
- UI와 보고서는 핵심 지표를 `지표 / 값 / 단위 / 기준일 / 출처 / freshness / 맥락 / 근거` 표로 보여줍니다. 근거 doc id는 Evidence 탭의 원문으로 연결됩니다.
- Topic quant snapshot은 rates/bonds(TLT), credit, FX, commodity, crypto, sector/theme 프록시를 지원합니다. TLT는 10Y/30Y 금리, 10Y-2Y 곡선, 실질금리 proxy, TLT 가격 흐름, duration proxy, 금리 충격 민감도를 deterministic하게 생성합니다.
- 이 스냅샷은 `execution_meta.extras.quant_snapshot`과 `key_metrics`에 들어가며, LLM은 숫자를 새로 만들지 않고 해석만 합니다.
- FRED/FMP entitlement 또는 뉴스 부족은 가능한 경우 `partial + actionable uncertainty`로 표현합니다. parser/LLM JSON 오류와 evidence 부족은 UI diagnostics에서 분리됩니다.

## 모델 운용 정책

- `qwen2.5:7b`가 최종 JSON/report 생성의 production baseline입니다.
- `fingpt` route는 final structured report 생성기가 아니라 보조 capability로 분류합니다. 현재 adapter policy는 FinGPT를 event extraction, sentiment/risk tagging, financial tone classification 같은 보조 작업 후보로 제한하고, final JSON은 qwen production path로 라우팅합니다.
- 모델별 capability(`json_reliability`, `korean_reliability`, `structured_output_support`, `finance_reasoning`, `gpu_required`)는 `execution_meta.extras.model_capabilities`에 기록됩니다.

## 수집 동작 상세

- 지원되는 소스는 `news`, `transcript`, `macro`, 그리고 비활성 상태인 `report`입니다. 기본값(CLI/UI)은 `news transcript`입니다.
- `report`는 등록만 되어 있고 현재는 수집이 꺼진 상태입니다. `report`만 단독 요청하면 사전 검증에서 막히고, 다른 소스와 섞여 있을 때는 `report=disabled`로 로그에 남습니다.
- `news`는 주식 종목의 기본 소스입니다. Yahoo Finance를 먼저 시도하고, 최신 문서가 3개 미만이면 기본 정책상 **SEC EDGAR 최근 공시 → Google News RSS → OpenBB news(옵션) → Alpha Vantage(옵션) → FMP 종목 뉴스(옵션)** 순으로 보강합니다.
- `transcript`는 기본 hot path에서 꺼져 있습니다. `FMP_ENABLED=true`, `TRANSCRIPT_PROVIDER=fmp_optional`, `FMP_API_KEY`를 모두 설정한 경우에만 FMP 안정(stable) 엔드포인트를 보조 소스로 호출합니다.
- `macro`는 채권 ETF, 원자재 ETF, FX(`EURUSD=X`), 선물(`GC=F`), 암호화폐(`BTC-USD`) 같은 비주식 자산의 기본 소스입니다. FRED(금리/CPI/달러 인덱스), yfinance 가격 이력, Google News RSS를 함께 묶어 반환합니다. 비주식 종목에 기본 소스(`news transcript`)를 그대로 쓰면 `news`는 자동으로 macro 번들로 전환되고 `transcript`는 `skipped`로 처리됩니다.
- 이번 실행에서 사용할 수 있는 1차 문서가 하나도 없으면 Retrieve/Infer 단계는 건너뜁니다. 이 경우 오래된 Qdrant 문서로 답하는 대신 `partial` 상태와 함께 "컨텍스트 없음" 가설을 반환합니다.
- `data/outputs/latest_collection.json` 파일에는 소스/프로바이더 상태, 수집된 문서 ID, 최신성 기준 시점, 그리고 `current_run_only` 검색 정책이 기록됩니다.
- SEC EDGAR를 꾸준히 쓰려면 `.env`에 `SEC_USER_AGENT`(조직/연락처 형태 문자열)를 설정하세요. macro 번들의 FRED 경로를 쓰려면 `FRED_API_KEY`를 설정하세요([fred.stlouisfed.org](https://fred.stlouisfed.org)에서 발급).

## 지원 자산 범위

| 자산군 | 예시 종목 | 기본 소스 | 트랜스크립트 |
| --- | --- | --- | --- |
| 미국 개별 주식 | `AAPL`, `MSFT`, `NVDA` | yfinance + SEC + Google RSS + optional OpenBB/Alpha Vantage/FMP | optional FMP 실적 콜 |
| 미국 ETF (일반) | `SPY`, `QQQ`, `XLK` | yfinance + issuer profile + Google RSS + optional OpenBB/Alpha Vantage/FMP | — |
| 미국 채권 ETF | `TLT`, `IEF`, `AGG`, `HYG` | yfinance + issuer profile + `macro`(FRED/Yahoo) + optional OpenBB/Alpha Vantage/FMP | — |
| 미국 원자재 ETF | `GLD`, `SLV`, `USO`, `DBC` | yfinance + issuer profile + `macro` + optional OpenBB/Alpha Vantage/FMP | — |
| 해외 상장 주식 | `005930.KS`, `9988.HK` | yfinance + Google News | — |
| FX 페어 (Yahoo) | `EURUSD=X`, `USDJPY=X` | `macro` 번들 | — |
| 선물 (Yahoo) | `GC=F`(금), `CL=F`(WTI), `ZN=F`(10Y) | `macro` 번들 | — |
| 암호화폐 (Yahoo) | `BTC-USD`, `ETH-USD` | `macro` 번들 | — |

종목 코드 사전 검증 정규식은 `[A-Z0-9.\-=]{1,12}` 이므로 Yahoo 형식의 FX/선물 심볼도 그대로 허용됩니다.

### ETF 발행사 프로필 자동 수집

iShares, SPDR, Vanguard, Invesco, ARK, Schwab, J.P. Morgan, Global X, USCF 등 ETF로 인식되는 종목은 요청 소스와 상관없이 발행사 상품 페이지를 자동으로 가져와 `etf_profile` 문서로 추가합니다. 안정성을 위해 3단계 대체 경로를 씁니다.

1. **큐레이션된 발행사 URL** (예: `https://www.ishares.com/us/products/239454/...`)을 trafilatura로 파싱
2. **Yahoo Finance `/profile`** 페이지를 trafilatura로 파싱
3. **yfinance 메타데이터**(`longBusinessSummary`, 카테고리, expense ratio, AUM, inception)를 자연어 단락으로 합성 (SPDR/Vanguard/Schwab 같은 JS 기반 SPA 페이지일 때 사용)

ETF가 아닌 종목은 조용히 건너뛰며, 추가 API 키는 필요 없습니다.

## Research upgrades: rerank, chunk, hybrid, topic mode

Recent retrieval and routing improvements are controlled by feature flags so
the legacy ticker workflow can be restored without code changes.

CLI examples:

```powershell
python app/cli/main.py --ticker AAPL --question "recent catalysts?"
python app/cli/main.py --ticker TLT --question "scenario risks?" --simulate
python app/cli/main.py --question "Fed의 2026년 금리 경로가 성장주에 미치는 영향은?"
python app/cli/main.py --topic "AI semiconductors" --question "short-term risks?"
```

API:

- Existing ticker endpoint remains unchanged: `POST /api/v1/research`.
- Universal auto-routing endpoint: `POST /api/v1/research/universal`.
- Universal responses include a top-level `mode` so clients can distinguish
  ticker, compare, sector/macro, and concept reports.
- Ticker, universal, compare, and topic request bodies can set
  `scenario_simulation_enabled: true|false` to override the environment flag
  for that request.

Operational flags:

```env
RERANKER_ENABLED=true
FUNDAMENTALS_CARD_ENABLED=true
INGEST_CHUNKING_ENABLED=true
HYBRID_SEARCH_ENABLED=true
TOPIC_MODE_ENABLED=true
SCENARIO_SIMULATION_ENABLED=false
```

Rollback is flag-based for Phase 1, 2, 4, and 5:

```env
RERANKER_ENABLED=false
FUNDAMENTALS_CARD_ENABLED=false
HYBRID_SEARCH_ENABLED=false
TOPIC_MODE_ENABLED=false
SCENARIO_SIMULATION_ENABLED=false
```

Chunking can also be disabled with `INGEST_CHUNKING_ENABLED=false`, but data
already stored as chunks remains in Qdrant until the collection is recreated.
When enabling chunking and hybrid BM25 for an existing collection, recreate the
collection once and re-ingest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/migrate_collection.ps1
python app/cli/main.py --ticker AAPL --question "smoke test"
```

The new chunked payload stores `doc_id` as the chunk id and `parent_doc_id` as
the source document id. Readers accept both fields for backward compatibility.

## Scenario Simulation Layer

This optional layer adds evidence-grounded base/bull/bear/tail scenarios,
market participant personas, agent-style views, risk triggers, deterministic
scenario scores, and a decision checklist.

It is disabled by default:

```env
SCENARIO_SIMULATION_ENABLED=false
```

It does not replace the existing RAG/research pipeline and does not perform
deterministic price prediction. Results are stored under:

```text
response.execution_meta.extras["scenario_simulation"]
```

Rollback is done by setting:

```env
SCENARIO_SIMULATION_ENABLED=false
```

For one-off CLI runs, `--simulate` enables the layer and `--no-simulate`
disables it for that process only.

## 문서

- 제품 규칙: [PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md)
- 내부 구조 지도: [PROJECT_MAP.md](docs/PROJECT_MAP.md)
- 실행/진단 가이드: [RUNBOOK.md](docs/RUNBOOK.md)
- 향후 계획: [ROADMAP.md](docs/ROADMAP.md)
- 최신 업데이트 제안: [UPDATE_PROPOSAL.md](docs/UPDATE_PROPOSAL.md)
- 사용 사례: [Use_Cases.md](docs/Use_Cases.md)

> 참고: 과거 벤치마크, 아카이브된 스택 버전, 프로토타입 코드는 `legacy/` 디렉터리에 따로 모아두었으며 메인 실행 경로에서는 제외됩니다.
