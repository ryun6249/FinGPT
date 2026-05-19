"""
Inference runner factory.

Routes inference requests to the appropriate adapter based on the requested route.
Production defaults stay pinned to the Ollama-backed Qwen baseline.
"""

from typing import Any, Dict, List

from core.config.settings import load_settings
from core.schemas.request import _coerce_output_language
from core.schemas.fundamentals import FundamentalsCard
from core.schemas.retrieval import RetrievalItem
from core.utils.model_capabilities import model_capability_dict

PRODUCTION_ROUTE_ALIASES = {"qwen", "mistral", "ollama", "primary", "llama-2", ""}
FINGPT_AUXILIARY_ALIASES = {"fingpt"}
EXPLICIT_GEMMA4_ALIASES = {"gemma4"}
EXPERIMENTAL_GEMMA_ALIASES = {"gemma", "gemma-experimental"}


def resolve_model_name(model_name: str, settings) -> str:
    route = (model_name or "").strip().lower()
    if route in PRODUCTION_ROUTE_ALIASES:
        return settings.primary_model
    if route in FINGPT_AUXILIARY_ALIASES:
        # FinGPT is intentionally treated as an auxiliary capability profile in
        # this local stack. Final structured reports still use the production
        # Qwen/Ollama path because the legacy FinGPT adapter is not reliable for
        # Korean JSON report generation.
        return settings.primary_model
    if route in EXPLICIT_GEMMA4_ALIASES:
        return getattr(settings, "gemma4_model", "") or settings.experimental_fallback_model
    if route in EXPERIMENTAL_GEMMA_ALIASES:
        if not settings.enable_experimental_fallback:
            raise ValueError(
                "Gemma is not part of the production route. Set ENABLE_EXPERIMENTAL_FALLBACK=true to run it explicitly."
            )
        return settings.experimental_fallback_model
    raise ValueError(
        f"Unsupported model route '{model_name}'. Supported routes: qwen, mistral, ollama, primary, fingpt, llama-2, gemma4, gemma-experimental."
    )


def run_inference(
    ticker: str,
    question: str,
    context: List[RetrievalItem],
    model_name: str,
    task_type: str = "general",
    horizon: str = "unspecified",
    fundamentals: FundamentalsCard | None = None,
    output_language: str | None = None,
) -> Dict[str, Any]:
    settings = load_settings()
    settings.output_language = _coerce_output_language(output_language or getattr(settings, "output_language", "ko"))
    from pipelines.infer.ollama_adapter import OllamaAdapter

    resolved_model_name = resolve_model_name(model_name, settings)
    runner = OllamaAdapter(settings, model_name=resolved_model_name)
    result = runner.run_inference(ticker, question, context, task_type=task_type, horizon=horizon, fundamentals=fundamentals)
    meta = result.setdefault("_meta", {}) if isinstance(result, dict) else {}
    if isinstance(meta, dict):
        meta["model_capabilities"] = model_capability_dict(model_name, resolved_model_name)
        if (model_name or "").strip().lower() == "fingpt":
            meta["fingpt_policy"] = "auxiliary_only_routed_to_qwen_for_final_json"
    return result
