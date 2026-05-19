from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

KNOWN_COLLECTION_SOURCES = ("news", "transcript", "report", "macro", "fundamentals", "filings")
DEFAULT_COLLECTION_SOURCES = ("news", "macro", "fundamentals", "filings", "transcript")
# ``news`` is the only *required* primary source — if it fails we degrade to
# ``partial``. ``macro`` is treated as primary for non-equity assets (bonds,
# FX, commodities), where it is the only relevant ground-truth channel.
# Keeping it in this tuple means the pipeline will mark a run as partial if
# the macro fetchers all fail on a non-equity ticker, which matches how we
# already handle degraded equity news collection.
PRIMARY_COLLECTION_SOURCES = ("news", "macro")
DISABLED_COLLECTION_SOURCES = ("report",)

SupportedInferenceRoute = Literal[
    "qwen",
    "mistral",
    "ollama",
    "primary",
    "fingpt",
    "llama-2",
    "gemma4",
    "gemma",
    "gemma-experimental",
]
SupportedOutputLanguage = Literal["ko", "en"]

class AnalysisRequest(BaseModel):
    ticker: Optional[str] = Field(default=None, description="The stock ticker symbol to analyze.")
    question: str = Field(..., description="The specific user question regarding the ticker.")
    sources: List[str] = Field(
        default_factory=lambda: list(DEFAULT_COLLECTION_SOURCES),
        description="Information sources to pull data from.",
    )
    lookback_days: int = Field(default=90, description="The number of past days for data retrieval. Default widened for data-rich grounded analysis.")
    top_k: int = Field(default=15, ge=1, le=20, description="Number of document chunks to retrieve for context. Default widened to expose the LLM to more corroborating/contradicting evidence.")
    model: SupportedInferenceRoute = Field(
        default="qwen",
        description=(
            "Inference route selector. Production baseline is qwen2.5 via Ollama. "
            "Legacy aliases route to the same primary. gemma4 is an explicit experimental option; "
            "legacy Gemma fallback routes remain gated."
        ),
    )
    output_dir: Optional[str] = Field(default=None, description="Path to save outputs.")
    output_language: SupportedOutputLanguage = Field(
        default="ko",
        description="Per-request output language for generated analysis and reports.",
    )
    scenario_simulation_enabled: Optional[bool] = Field(
        default=None,
        description="Optional per-request override for the default-off scenario simulation layer.",
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def _clean_optional_ticker(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().upper()
        return cleaned or None

    @field_validator("question", mode="before")
    @classmethod
    def _clean_question(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("sources", mode="before")
    @classmethod
    def _clean_sources(cls, value: Any) -> list[str]:
        return _coerce_sources(value)

    @field_validator("output_language", mode="before")
    @classmethod
    def _clean_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


class UniversalRequest(BaseModel):
    question: str = Field(..., description="User question to route to ticker, compare, or topic analysis.")
    ticker: Optional[str] = Field(default=None, description="Optional ticker hint for routing.")
    mode_hint: Optional[Literal["auto", "ticker", "topic"]] = Field(default="auto")
    sources: List[str] = Field(default_factory=lambda: list(DEFAULT_COLLECTION_SOURCES))
    lookback_days: int = Field(default=90)
    top_k: int = Field(default=15, ge=1, le=20)
    model: SupportedInferenceRoute = Field(default="qwen")
    output_dir: Optional[str] = Field(default=None)
    output_language: SupportedOutputLanguage = Field(
        default="ko",
        description="Per-request output language for generated analysis and reports.",
    )
    scenario_simulation_enabled: Optional[bool] = Field(
        default=None,
        description="Optional per-request override for the default-off scenario simulation layer.",
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def _clean_optional_ticker(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip().upper()
        return cleaned or None

    @field_validator("question", mode="before")
    @classmethod
    def _clean_question(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("sources", mode="before")
    @classmethod
    def _clean_sources(cls, value: Any) -> list[str]:
        return _coerce_sources(value)

    @field_validator("mode_hint", mode="before")
    @classmethod
    def _clean_mode_hint(cls, value: Any) -> str:
        value = str(value or "auto").strip().lower()
        return value if value in {"auto", "ticker", "topic"} else "auto"

    @field_validator("output_language", mode="before")
    @classmethod
    def _clean_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


# Hard cap on fan-out keeps local Ollama/Qdrant/FMP from getting hammered and
# matches the project's "single-workstation" posture. Raise only after
# benchmarking real-world latency on the target machine.
COMPARE_MAX_TICKERS = 5
COMPARE_MAX_CONCURRENCY = 3


class CompareRequest(BaseModel):
    """Batch analysis request that shares question/sources across N tickers."""

    tickers: List[str] = Field(
        ...,
        min_length=2,
        max_length=COMPARE_MAX_TICKERS,
        description=f"List of 2–{COMPARE_MAX_TICKERS} tickers to compare side-by-side.",
    )
    question: str = Field(..., description="Shared question applied to every ticker.")
    sources: List[str] = Field(
        default_factory=lambda: list(DEFAULT_COLLECTION_SOURCES),
        description="Information sources to pull data from.",
    )
    lookback_days: int = Field(default=90)
    top_k: int = Field(default=15, ge=1, le=20)
    model: SupportedInferenceRoute = Field(default="qwen")
    output_language: SupportedOutputLanguage = Field(
        default="ko",
        description="Per-request output language applied to each ticker analysis.",
    )
    concurrency: int = Field(
        default=2,
        ge=1,
        le=COMPARE_MAX_CONCURRENCY,
        description=(
            "Maximum pipelines to run in parallel. Keep small on a single local "
            "machine to avoid starving Ollama/Qdrant/FMP quotas."
        ),
    )
    scenario_simulation_enabled: Optional[bool] = Field(
        default=None,
        description="Optional per-request override applied to each ticker analysis.",
    )

    @field_validator("tickers", mode="before")
    @classmethod
    def _clean_tickers(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            raw = value.replace(",", " ").split()
        else:
            raw = list(value or [])
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw:
            ticker = str(item or "").strip().upper()
            if ticker and ticker not in seen:
                seen.add(ticker)
                cleaned.append(ticker)
        return cleaned

    @field_validator("question", mode="before")
    @classmethod
    def _clean_question(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("sources", mode="before")
    @classmethod
    def _clean_sources(cls, value: Any) -> list[str]:
        return _coerce_sources(value)

    @field_validator("output_language", mode="before")
    @classmethod
    def _clean_output_language(cls, value: Any) -> str:
        return _coerce_output_language(value)


def _coerce_sources(value: Any) -> list[str]:
    if value is None:
        raw = list(DEFAULT_COLLECTION_SOURCES)
    elif isinstance(value, str):
        raw = value.replace(",", " ").split()
    else:
        try:
            raw = list(value)
        except TypeError:
            raw = list(DEFAULT_COLLECTION_SOURCES)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        source = str(item or "").strip().lower()
        if not source or source in seen:
            continue
        seen.add(source)
        cleaned.append(source)
    return cleaned or list(DEFAULT_COLLECTION_SOURCES)


def _coerce_output_language(value: Any) -> str:
    clean = str(value or "ko").strip().lower()
    if clean in {"en", "eng", "english"}:
        return "en"
    if clean in {"ko", "kor", "korean", "kr", "한국어"}:
        return "ko"
    return "ko"
