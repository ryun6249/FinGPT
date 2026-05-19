from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

# Paths
CORE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = CORE_DIR.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"
RAW_DIR = DATA_DIR / "raw"

class Settings(BaseSettings):
    # App General
    base_dir: Path = Field(default=BASE_DIR)
    data_dir: Path = Field(default=DATA_DIR)
    outputs_dir: Path = Field(default=OUTPUTS_DIR)
    raw_dir: Path = Field(default=RAW_DIR)

    # Structured data mart. This is separate from ``data/runs.db`` (research
    # execution history) and Qdrant (document evidence retrieval).
    data_mart_backend: str = Field(default="sqlite")
    data_mart_db_path: Path = Field(default=DATA_DIR / "research_mart.db")
    data_mart_duckdb_path: Path = Field(default=DATA_DIR / "research_mart.duckdb")

    # Qdrant Database
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str = Field(default="")
    collection_name: str = Field(default="market_docs")

    # Production inference baseline
    ollama_base_url: str = Field(default="http://localhost:11434")
    primary_model: str = Field(default="qwen2.5:7b")
    gemma4_model: str = Field(default="gemma4:e4b")
    enable_experimental_fallback: bool = Field(default=False)
    experimental_fallback_model: str = Field(default="gemma4:e4b")

    # Localization
    output_language: str = Field(default="ko")

    # Retrieval strategy. ``multi_query`` fans the user question into three
    # semantically distinct sub-queries (raw, risk-focused, catalyst-focused)
    # and fuses the results with Reciprocal Rank Fusion to improve recall on
    # broad thesis questions. Set to ``single`` to revert to the legacy
    # single-query path.
    retrieval_strategy: str = Field(default="multi_query")

    # Cross-encoder reranker. Runs after multi-query RRF to improve precision
    # on the final context set; fail-open behavior lives in the reranker module.
    reranker_enabled: bool = Field(default=True)
    reranker_model: str = Field(default="Xenova/ms-marco-MiniLM-L-6-v2")
    reranker_candidate_pool: int = Field(default=30)

    # Fixed finance/fundamentals snapshot injected outside RAG for supported assets.
    fundamentals_card_enabled: bool = Field(default=True)
    fundamentals_card_timeout_s: float = Field(default=8.0)

    # Ingest chunking. Disabling keeps legacy one-vector-per-document ingest.
    ingest_chunking_enabled: bool = Field(default=True)
    ingest_chunk_tokens: int = Field(default=512)
    ingest_chunk_overlap: int = Field(default=64)
    max_chunks_per_parent: int = Field(default=1)

    # Hybrid dense + sparse retrieval. New collections are created with sparse
    # vector config. Existing dense-only collections are auto-upgraded when the
    # installed qdrant-client/server combination supports sparse vector updates;
    # otherwise runtime add/query paths fail open to dense-only retrieval.
    hybrid_search_enabled: bool = Field(default=True)
    sparse_model: str = Field(default="Qdrant/bm25")
    hybrid_search_auto_migrate_sparse: bool = Field(default=True)

    # Topic mode / universal routing.
    topic_mode_enabled: bool = Field(default=True)
    router_model: str = Field(default="qwen2.5:7b")
    topic_retrieval_top_k: int = Field(default=15)
    topic_max_related_tickers: int = Field(default=8)

    # Embedding model used by FastEmbed for vectorization. The default keeps
    # backward compatibility with existing ``market_docs`` collections
    # (384-dim vectors). Upgrading to ``BAAI/bge-base-en-v1.5`` (768-dim)
    # requires dropping and re-ingesting the collection.
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_vector_size: int = Field(default=384)

    # Web UI / API surface
    # Comma-separated list of allowed origins for CORS. Default stays local-only
    # because the project is positioned as a privacy-preserving local assistant.
    # Set to "*" in .env only if you intentionally want to serve the UI to other hosts.
    web_cors_origins: str = Field(default="http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8010,http://localhost:8010")

    # Optional Quant Lab adapters. Qlib stays disabled by default so the
    # deterministic data-mart-backed engine remains the startup/runtime path.
    quant_lab_qlib_enabled: bool = Field(default=False)
    qlib_provider_uri: str = Field(default="")

    # Optional MiroFish-style scenario simulation layer. Disabled by default
    # so the existing research path and report output remain unchanged.
    scenario_simulation_enabled: bool = Field(default=False)
    scenario_simulation_max_personas: int = Field(default=6)
    scenario_simulation_min_personas: int = Field(default=5)
    scenario_simulation_debate_rounds: int = Field(default=1)
    scenario_simulation_max_scenarios: int = Field(default=4)
    scenario_simulation_llm_enabled: bool = Field(default=True)
    scenario_simulation_strict_evidence: bool = Field(default=True)
    scenario_simulation_fail_open: bool = Field(default=True)

    # Collection cache — small in-memory TTL cache to avoid re-hammering FMP / SEC /
    # Yahoo when the user re-runs the same (ticker, sources, lookback) within a
    # short window (e.g. retrying with a different question). Set TTL to 0 to
    # disable the cache entirely.
    collection_cache_ttl_s: int = Field(default=300)
    collection_cache_max_entries: int = Field(default=32)

    # Data provider policy. The production hot path is key-light by default:
    # Yahoo/yfinance, FRED, SEC EDGAR, and Google News RSS are primary. OpenBB
    # remains installed and compatibility-checked, but its news runtime is
    # opt-in because some 4.6.x provider combinations can break at import time.
    # FMP is auxiliary and disabled unless explicitly enabled.
    data_provider_priority: str = Field(default="yfinance,sec,google,openbb,alpha_vantage,fmp")
    alpha_vantage_enabled: bool = Field(default=False)
    openbb_enabled: bool = Field(default=True)
    openbb_news_enabled: bool = Field(default=False)
    openbb_agent_enabled: bool = Field(default=False)
    openbb_agent_id: str = Field(default="fingpt-local-research")
    openbb_agent_name: str = Field(default="FinGPT Local Research")
    openbb_agent_public_url: str = Field(default="http://127.0.0.1:8000")
    openbb_agent_allow_origins: str = Field(default="https://pro.openbb.co,http://localhost:1420,http://127.0.0.1:1420")
    fmp_enabled: bool = Field(default=False)
    transcript_provider: str = Field(default="fmp_optional")

    # Pluggable risk engine. Supported: ``heuristic`` (default, zero deps) or
    # ``finbert`` (opt-in, requires transformers + torch + the public
    # ``ProsusAI/finbert`` weights). When FinBERT deps are missing the pipeline
    # logs a warning and falls back to heuristic so the system stays functional.
    risk_engine: str = Field(default="heuristic")
    finbert_model_name: str = Field(default="ProsusAI/finbert")

    # API Keys
    alpha_vantage_api_key: str = Field(default="")
    fmp_api_key: str = Field(default="")
    hf_token: str = Field(default="")
    hf_model_revision: str = Field(default="main")

    # SEC EDGAR fair-access identity. Operators should replace the default
    # with an organization/contact string before sustained automated use.
    sec_user_agent: str = Field(default="FinGPTLocalResearch/1.0 contact@example.com")
    sec_request_delay_s: float = Field(default=0.12)
    dart_api_key: str = Field(default="")
    dart_request_timeout_s: float = Field(default=12.0)

    # Local structured data auto refresh. This is an in-process workstation
    # scheduler, not a distributed job runner. It polls SEC/company data on a
    # conservative interval and never blocks API startup.
    data_mart_auto_refresh_enabled: bool = Field(default=True)
    data_mart_auto_refresh_sec_enabled: bool = Field(default=True)
    data_mart_auto_refresh_macro_enabled: bool = Field(default=True)
    data_mart_auto_refresh_interval_hours: float = Field(default=24.0)
    data_mart_auto_refresh_initial_delay_s: float = Field(default=120.0)
    data_mart_auto_refresh_universe_id: str = Field(default="all_supported")
    data_mart_auto_refresh_max_assets: int = Field(default=250)
    data_mart_auto_refresh_sec_lookback_days: int = Field(default=365 * 3)
    data_mart_auto_refresh_macro_lookback_days: int = Field(default=365 * 5)

    # FRED (Federal Reserve Economic Data) powers the macro bundle for bonds
    # and rate-sensitive assets. Free to register at https://fred.stlouisfed.org.
    # When empty, the FRED provider fast-skips with ``credentials_missing`` and
    # the macro bundle falls back to yfinance price series + Google News.
    fred_api_key: str = Field(default="")
    ecos_api_key: str = Field(default="")
    macro_provider_timeout_s: float = Field(default=8.0)
    macro_yahoo_default_period: str = Field(default="5y")

    # Macro bundle knobs. Price-history lookback is independent from news
    # lookback because macro charts benefit from a longer window even when the
    # user requests a 7-day news cutoff.
    macro_price_lookback_days: int = Field(default=90)
    macro_news_query_language: str = Field(default="en")
    
    # Legacy Hugging Face model configurations kept for archival compatibility
    base_model_name: str = Field(default="meta-llama/Llama-2-7b-hf")
    adapter_model_name: str = Field(default="FinGPT/fingpt-mt_llama2-7b_lora")
    enable_4bit: bool = Field(default=True)
    max_new_tokens: int = Field(default=384)

    # Optional FinGPT task datasets and task-specific model adapters. Dataset
    # loading is disabled by default so offline/local runs do not import or
    # require the Hugging Face datasets package.
    fingpt_datasets_enabled: bool = Field(default=False)
    fingpt_dataset_cache_dir: Path = Field(default=DATA_DIR / "fingpt_datasets")
    fingpt_dataset_max_rows: int = Field(default=500)
    fingpt_task_model_enabled: bool = Field(default=False)
    fingpt_task_model_name: str = Field(default="FinGPT/fingpt-mt_llama3-8b_lora")

    # Ensure settings load from .env correctly
    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

def load_settings() -> Settings:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
