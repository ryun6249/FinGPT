from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from core.config.settings import load_settings


SYSTEM_PROMPT = """You answer questions about a Quantamental Engine payload.

Use only the supplied deterministic metrics, risk flags, data-quality warnings,
and signal label. Do not create scores or signals. Do not give direct trading
orders. Return JSON only with answer, evidence_metrics, caveats, and
not_investment_advice=true.
"""

_DIRECT_ORDER_RE = re.compile(
    r"\b(buy now|sell now|must buy|must sell|go long|go short|short it|all in|liquidate)\b|"
    r"무조건\s*(매수|매도)|반드시\s*(매수|매도)|전량\s*(매수|매도)",
    re.IGNORECASE,
)


def answer_question(
    question: str,
    context: dict[str, Any],
    *,
    use_llm: bool = False,
    model: str | None = None,
    timeout_s: float = 30.0,
    language: str = "ko",
) -> dict[str, Any]:
    clean_question = str(question or "").strip()
    language = _normalize_language(language or context.get("output_language"))
    fallback = _fallback_answer(clean_question, context, language=language)
    if not use_llm:
        fallback["warnings"].append("llm_not_used_deterministic_qa_active")
        return fallback
    try:
        raw_text, provider, latency_s = _call_local_llm(clean_question, context, model=model, timeout_s=timeout_s, language=language)
        parsed = _parse_answer(raw_text)
        if _DIRECT_ORDER_RE.search(json.dumps(parsed, ensure_ascii=False)):
            raise ValueError("direct_order_language_detected")
        parsed.update(
            {
                "status": "success",
                "provider": provider,
                "question": clean_question,
                "latency_s": latency_s,
                "prompt_template": SYSTEM_PROMPT,
                "not_investment_advice": True,
                "output_language": language,
                "warnings": [
                    f"llm_latency_s={latency_s}",
                    "deterministic_context_only",
                    "advisory_only_guard_passed",
                    "json_schema_guard_passed",
                ],
            }
        )
        return parsed
    except Exception as exc:  # noqa: BLE001
        fallback["warnings"] = [
            "llm_provider_failed_or_rejected_output",
            f"fallback_reason:{type(exc).__name__}:{exc}",
            "deterministic_qa_active",
        ]
        return fallback


def _fallback_answer(question: str, context: dict[str, Any], *, language: str = "ko") -> dict[str, Any]:
    signal = context.get("deterministic_signal") or {}
    scores = context.get("deterministic_scores") or {}
    risk = context.get("risk") or {}
    quality = context.get("data_quality") or {}
    q_lower = question.lower()
    evidence = _evidence(scores, signal, risk, quality, language=language)
    if "sell" in q_lower or "risk" in q_lower or "매도" in question or "리스크" in question:
        answer = (
            f"The deterministic risk view is {risk.get('risk_level') or 'unknown'} with flags "
            f"{', '.join(str(x) for x in (risk.get('risk_flags') or [])[:6]) or 'none available'}. "
            "Sell Risk, when present, is a Signal Engine risk classification, not an instruction to sell."
            if language == "en"
            else (
                f"Deterministic 리스크 관점은 {risk.get('risk_level') or 'unknown'}이며 플래그는 "
                f"{', '.join(str(x) for x in (risk.get('risk_flags') or [])[:6]) or '없음'}입니다. "
                "Sell Risk가 표시되더라도 Signal Engine의 리스크 분류일 뿐 매도 지시가 아닙니다."
            )
        )
    elif "buy" in q_lower or "candidate" in q_lower or "매수" in question:
        answer = (
            f"The deterministic signal is {signal.get('signal_label') or 'Insufficient Data'} with "
            f"confidence {signal.get('signal_confidence') or 'low'}. Buy Candidate labels are generated "
            "only by the Signal Engine and must be treated as research classifications."
            if language == "en"
            else (
                f"Deterministic 신호는 {signal.get('signal_label') or 'Insufficient Data'}이고 "
                f"신뢰도는 {signal.get('signal_confidence') or 'low'}입니다. Buy Candidate 라벨은 "
                "Signal Engine이 만든 리서치 분류이며 매수 지시가 아닙니다."
            )
        )
    elif "quality" in q_lower or "data" in q_lower or "데이터" in question:
        answer = (
            f"Data quality is {quality.get('level') or 'unknown'} with score {quality.get('score')}. "
            f"Missing sections: {', '.join(str(x) for x in (quality.get('missing_sections') or [])) or 'none'}."
            if language == "en"
            else (
                f"데이터 품질은 {quality.get('level') or 'unknown'}이고 점수는 {quality.get('score')}입니다. "
                f"누락 섹션: {', '.join(str(x) for x in (quality.get('missing_sections') or [])) or '없음'}."
            )
        )
    else:
        answer = (
            f"{context.get('ticker') or 'This ticker'} has deterministic signal "
            f"{signal.get('signal_label') or 'Insufficient Data'} and final score {scores.get('final_score')}. "
            "The AI layer is interpreting, not changing, these engine outputs."
            if language == "en"
            else (
                f"{context.get('ticker') or '이 티커'}의 deterministic 신호는 "
                f"{signal.get('signal_label') or 'Insufficient Data'}이고 최종 점수는 {scores.get('final_score')}입니다. "
                "AI 레이어는 엔진 출력을 변경하지 않고 해석만 합니다."
            )
        )
    caveats = (
        [
            "This is not investment advice.",
            "The answer is constrained to available deterministic Quantamental Engine data.",
        ]
        if language == "en"
        else [
            "투자 자문이 아닙니다.",
            "답변은 사용 가능한 deterministic Quantamental Engine 데이터로 제한됩니다.",
        ]
    )
    if quality.get("warnings"):
        caveats.append(
            ("Data warnings: " if language == "en" else "데이터 경고: ")
            + ", ".join(str(item) for item in quality.get("warnings")[:5])
        )
    return {
        "status": "partial",
        "provider": "deterministic_qa",
        "question": question,
        "answer": answer,
        "evidence_metrics": evidence,
        "caveats": caveats,
        "not_investment_advice": True,
        "output_language": language,
        "warnings": [],
        "source_policy": "qa_interprets_deterministic_engine_only",
    }


def _evidence(
    scores: dict[str, Any],
    signal: dict[str, Any],
    risk: dict[str, Any],
    quality: dict[str, Any],
    *,
    language: str = "ko",
) -> list[dict[str, Any]]:
    labels = {
        "signal_label": "Signal label" if language == "en" else "신호 라벨",
        "signal_confidence": "Signal confidence" if language == "en" else "신호 신뢰도",
        "final_score": "Final score" if language == "en" else "최종 점수",
        "fundamental_score": "Fundamental score" if language == "en" else "펀더멘털 점수",
        "quant_score": "Quant score" if language == "en" else "퀀트 점수",
        "risk_level": "Risk level" if language == "en" else "리스크 수준",
        "data_quality": "Data quality" if language == "en" else "데이터 품질",
    }
    return [
        {"label": labels["signal_label"], "value": signal.get("signal_label"), "source": "deterministic_signal_engine"},
        {"label": labels["signal_confidence"], "value": signal.get("signal_confidence"), "source": "deterministic_signal_engine"},
        {"label": labels["final_score"], "value": scores.get("final_score"), "source": "hybrid_score_engine"},
        {"label": labels["fundamental_score"], "value": scores.get("fundamental_score"), "source": "fundamental_engine"},
        {"label": labels["quant_score"], "value": scores.get("quant_score"), "source": "quant_engine"},
        {"label": labels["risk_level"], "value": risk.get("risk_level"), "source": "risk_engine"},
        {"label": labels["data_quality"], "value": quality.get("score"), "source": "data_quality_engine"},
    ]


def _call_local_llm(question: str, context: dict[str, Any], *, model: str | None, timeout_s: float, language: str) -> tuple[str, str, float]:
    settings = load_settings()
    selected_model = model or str(settings.primary_model or "qwen2.5:7b")
    language_instruction = (
        "Write answer and caveats in Korean."
        if language == "ko"
        else "Write answer and caveats in English."
    )
    prompt = (
        SYSTEM_PROMPT
        + f"\n{language_instruction}\nQUESTION:\n"
        + question
        + "\n\nQUANTAMENTAL_CONTEXT_JSON:\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    )
    started = time.time()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": selected_model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 800},
            "keep_alive": "5m",
        },
        timeout=max(1.0, min(float(timeout_s or 30.0), 90.0)),
    )
    response.raise_for_status()
    body = response.json()
    text = str(body.get("response") or "").strip()
    if not text:
        raise ValueError("empty_llm_response")
    return text, f"ollama:{selected_model}", round(time.time() - started, 2)


def _parse_answer(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed_json:{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("json_root_not_object")
    answer = str(parsed.get("answer") or "").strip()
    if not answer:
        raise ValueError("missing_answer")
    evidence = parsed.get("evidence_metrics")
    caveats = parsed.get("caveats")
    if not isinstance(evidence, list):
        raise ValueError("missing_evidence_metrics")
    if not isinstance(caveats, list):
        raise ValueError("missing_caveats")
    return {
        "answer": answer,
        "evidence_metrics": evidence,
        "caveats": caveats,
    }


def _normalize_language(value: Any) -> str:
    clean = str(value or "ko").strip().lower()
    return "en" if clean in {"en", "eng", "english"} else "ko"
