from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from core.config.settings import load_settings
from core.schemas.macro import MacroBriefResponse, MacroOverview
from pipelines.infer.runner_factory import resolve_model_name
from pipelines.macro.asset_impact import get_asset_impacts
from pipelines.macro.portfolio_hints import get_portfolio_policy_hint
from pipelines.macro.prompts import AI_MACRO_BRIEF_SYSTEM_PROMPT, AI_MACRO_BRIEF_TEMPLATE


def _fmt_number(value: Any, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "사용 불가"
    return f"{numeric:.{digits}f}"


def _change_text(item) -> str:
    changes = item.changes or {}
    one = changes.get("change_1_period")
    three = changes.get("change_3_period")
    twelve = changes.get("change_12_period")
    return (
        f"1기간 {_fmt_number(one)}, 3기간 {_fmt_number(three)}, "
        f"12기간 {_fmt_number(twelve)}"
    )


def _indicator_line(item) -> str:
    latest = item.latest
    if not latest or latest.value is None:
        return f"- {item.display_name} ({item.series_id}): 사용 가능한 최신 관측치 없음 (품질={item.data_quality.status})"
    return (
        f"- {item.display_name} ({item.series_id}): {latest.value:.3f} {item.unit}, "
        f"기준일 {latest.date}, {_change_text(item)}, 품질={item.data_quality.status}, 공급자={item.provider}"
    )


def _compact_brief_payload(overview: MacroOverview) -> dict[str, Any]:
    impacts = get_asset_impacts(overview.regime, overview.signals)
    hint = get_portfolio_policy_hint(overview.regime, overview.data_quality)
    return {
        "macro_overview": {
            "as_of": overview.as_of,
            "key_indicators": [
                {
                    "series_id": item.series_id,
                    "display_name": item.display_name,
                    "category": item.category,
                    "unit": item.unit,
                    "frequency": item.frequency,
                    "provider": item.provider,
                    "latest": item.latest.model_dump(mode="json") if item.latest else None,
                    "changes": item.changes,
                    "data_quality": item.data_quality.model_dump(mode="json"),
                }
                for item in overview.key_indicators
            ],
            "data_quality": overview.data_quality.model_dump(mode="json"),
        },
        "macro_signals": [item.model_dump(mode="json") for item in overview.signals],
        "macro_regime": overview.regime.model_dump(mode="json"),
        "recent_changes": {
            item.series_id: item.changes
            for item in overview.key_indicators
            if item.changes
        },
        "asset_impact": [item.model_dump(mode="json") for item in impacts],
        "portfolio_policy_hints": hint.model_dump(mode="json"),
        "data_quality": overview.data_quality.model_dump(mode="json"),
    }


def _format_prompt(payload: dict[str, Any]) -> str:
    block = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return (
        AI_MACRO_BRIEF_TEMPLATE
        .replace("{{macro_overview}}", json.dumps(payload["macro_overview"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{macro_signals}}", json.dumps(payload["macro_signals"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{macro_regime}}", json.dumps(payload["macro_regime"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{recent_changes}}", json.dumps(payload["recent_changes"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{asset_impact}}", json.dumps(payload["asset_impact"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{portfolio_policy_hints}}", json.dumps(payload["portfolio_policy_hints"], ensure_ascii=False, sort_keys=True, default=str))
        .replace("{{data_quality}}", json.dumps(payload["data_quality"], ensure_ascii=False, sort_keys=True, default=str))
        + "\n\nSTRICT INPUT PAYLOAD JSON:\n"
        + block
    )


_NUMERIC_TOKEN_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?")
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
_CJK_IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_JAPANESE_RE = re.compile(r"[\u3040-\u30ff]")
_MOJIBAKE_RE = re.compile(r"(?:占|筌|疫|梨|�|\?{3,})")
_DIRECT_TRADE_RE = re.compile(
    r"\b(buy|sell|short|go long|go short)\b|매수하라|매도하라|공매도|롱\s*진입|숏\s*진입",
    re.IGNORECASE,
)


def _decimal_token(token: str) -> Decimal | None:
    value = str(token or "").strip().rstrip("%")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _allowed_numeric_values(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for token in _NUMERIC_TOKEN_RE.findall(text or ""):
        parsed = _decimal_token(token)
        if parsed is not None:
            values.append(parsed)
    values.extend(Decimal(item) for item in range(0, 13))
    return values


def _find_ungrounded_numeric_tokens(output: str, prompt: str) -> list[str]:
    allowed = _allowed_numeric_values(prompt)
    out: list[str] = []
    for token in _NUMERIC_TOKEN_RE.findall(output or ""):
        parsed = _decimal_token(token)
        if parsed is None:
            continue
        if any(abs(parsed - candidate) <= Decimal("0.01") for candidate in allowed):
            continue
        normalized = str(token)
        if normalized not in out:
            out.append(normalized)
        if len(out) >= 10:
            break
    return out


def _safe_rejection_reason(exc: Exception) -> str:
    raw = str(exc or "")
    lowered = raw.lower()
    if "direct trading language" in lowered:
        return "Macro brief guard rejected direct trading language."
    if "ungrounded numeric" in lowered or "grounding guard" in lowered:
        return "Macro brief grounding guard rejected ungrounded numeric token(s)."
    if "language guard" in lowered:
        return "Macro brief language guard rejected provider output."
    if "empty" in lowered:
        return "Macro brief provider returned empty output."
    if "timeout" in lowered or "timed out" in lowered:
        return "Macro brief provider timed out."
    return f"Macro brief provider unavailable or rejected output: {type(exc).__name__}"


def _korean_language_issue(output: str) -> str:
    text = " ".join(str(output or "").split())
    if not text:
        return "Macro brief language guard rejected empty output."
    hangul = len(_HANGUL_RE.findall(text))
    cjk = len(_CJK_IDEOGRAPH_RE.findall(text))
    japanese = len(_JAPANESE_RE.findall(text))
    mojibake = len(_MOJIBAKE_RE.findall(text))
    latin_words = len(re.findall(r"\b[A-Za-z]{4,}\b", text))
    if japanese or mojibake:
        return "Macro brief language guard rejected Japanese or mojibake text."
    if cjk >= 3:
        return "Macro brief language guard rejected Chinese/Hanja-style prose."
    if hangul < 10 and latin_words >= 8:
        return "Macro brief language guard rejected mostly non-Korean prose."
    return ""


def _call_ollama_macro_brief(*, prompt: str, model: str | None, timeout_s: float) -> tuple[str, str, float]:
    settings = load_settings()
    requested_model = str(model or "qwen").strip() or "qwen"
    try:
        resolved_model = resolve_model_name(requested_model, settings)
    except ValueError:
        if requested_model == str(settings.primary_model) or ":" in requested_model or "/" in requested_model:
            resolved_model = requested_model
        else:
            raise
    started = time.time()
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        json={
            "model": resolved_model,
            "system": AI_MACRO_BRIEF_SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 1200,
                "num_ctx": 8192,
            },
            "keep_alive": "5m",
        },
        timeout=max(1.0, float(timeout_s)),
    )
    if response.status_code != 200:
        raise ConnectionError(f"Ollama macro brief returned HTTP {response.status_code}: {response.text[:200]}")
    body = response.json()
    text = str(body.get("response") or "").strip()
    if not text:
        raise ValueError("Ollama macro brief returned empty text.")
    return text, resolved_model, round(time.time() - started, 2)


def _signal_value(overview: MacroOverview, name: str) -> str:
    for signal in overview.signals:
        if signal.name == name:
            evidence = "; ".join(signal.evidence[:3]) if signal.evidence else "증거 부족"
            return f"{signal.value} (점수 {signal.score:.1f}, 신뢰도 {signal.confidence:.2f}) - {evidence}"
    return "unknown - 관련 신호를 계산할 입력이 부족합니다."


def _indicator_block(overview: MacroOverview, category: str, limit: int = 8) -> str:
    rows = [item for item in overview.key_indicators if item.category == category]
    if not rows:
        return "- 해당 범주의 핵심 지표가 현재 브리프 입력에 없습니다."
    return "\n".join(_indicator_line(item) for item in rows[:limit])


def _portfolio_block(hint) -> str:
    lines = [
        f"- 주식 비중 방향: {hint.equity_bias}",
        f"- 채권 비중 방향: {hint.bond_bias}; 듀레이션 방향: {hint.duration_bias}; 신용위험 방향: {hint.credit_bias}",
        f"- 현금/대체자산 방향: 현금 {hint.cash_bias}, 대체 {hint.alternative_bias}",
        f"- 리밸런싱 주의: {hint.rebalance_attention}; 위험 수준: {hint.risk_level}",
        f"- 해석: {hint.explanation}",
    ]
    if hint.etf_candidates:
        lines.append("- ETF 슬리브 후보:")
        for candidate in hint.etf_candidates:
            tickers = ", ".join(candidate.tickers) if candidate.tickers else "지정 없음"
            lines.append(
                f"  - {candidate.sleeve}: {candidate.bias}; 후보 {tickers}; 역할 {candidate.role}; 근거 {candidate.rationale}"
            )
    lines.extend(
        [
            "- 구성 방식: 레짐 신뢰도가 낮거나 데이터 품질이 partial/stale이면 핵심 주식·채권·현금 슬리브를 넓은 범위로 유지하고, 단일 지표 하나로 비중을 크게 바꾸지 않습니다.",
            "- 실행 점검: 금리, 인플레이션, 신용스프레드, 변동성 신호가 같은 방향으로 확인될 때만 리밸런싱 강도를 높입니다.",
            "- 제한: 이 항목은 포트폴리오 리서치 메모이며 주문 생성이나 확정 비중 지시가 아닙니다.",
        ]
    )
    if hint.warnings:
        lines.append(f"- 경고: {'; '.join(hint.warnings[:5])}")
    return "\n".join(lines)


def _fallback_brief(
    overview: MacroOverview,
    *,
    include_prompt: bool = False,
    extra_warnings: list[str] | None = None,
    llm_attempted: bool = False,
) -> MacroBriefResponse:
    impacts = get_asset_impacts(overview.regime, overview.signals)
    hint = get_portfolio_policy_hint(overview.regime, overview.data_quality)
    available = [item for item in overview.key_indicators if item.latest and item.latest.value is not None]
    missing_or_stale = [*overview.data_quality.missing_series, *overview.data_quality.stale_series]
    asset_lines = "\n".join(
        f"- {item.asset_class}: {item.impact}; 신뢰도 {item.confidence:.2f}; 근거 {item.reason}; 주요 리스크 {', '.join(item.key_risks) or '없음'}"
        for item in impacts
    )
    all_key_rows = "\n".join(_indicator_line(item) for item in overview.key_indicators[:18])
    brief = f"""1. 현재 매크로 레짐
{overview.regime.display_name} ({overview.regime.name})로 분류됩니다. 신뢰도는 {overview.regime.confidence:.2f}, 위험 수준은 {overview.regime.risk_level}입니다. {overview.regime.interpretation or '레짐 해석을 만들 입력이 부족합니다.'}

2. 핵심 데이터 확인
사용 가능한 핵심 지표는 {len(available)}/{len(overview.key_indicators)}개입니다.
{all_key_rows if all_key_rows else '- 사용 가능한 핵심 지표가 없습니다.'}

3. 최근 변화
최근 변화는 저장된 관측치에서만 계산했습니다. 1기간, 3기간, 12기간 변화가 없으면 관측치 길이가 부족하거나 공급자 데이터가 비어 있다는 뜻입니다. 누락 또는 지연 지표: {', '.join(missing_or_stale) or '현재 표시된 항목 없음'}.

4. 인플레이션 평가
신호: {_signal_value(overview, 'inflation_signal')}
{_indicator_block(overview, 'inflation', 10)}
해석: CPI, Core CPI, PCE, Core PCE, trimmed/median/sticky 계열을 함께 봐야 합니다. 헤드라인 CPI 하나만으로 물가 압력이 완화됐다고 결론 내리지 않고, 에너지·식품·근원·기대인플레이션이 같은 방향인지 확인해야 합니다.

5. 성장과 고용 평가
성장 신호: {_signal_value(overview, 'growth_signal')}
고용 신호: {_signal_value(overview, 'labor_signal')}
{_indicator_block(overview, 'growth', 8)}
{_indicator_block(overview, 'labor', 8)}
해석: GDP와 산업생산은 느린 지표이고, 실업률·신규실업수당청구·구인건수는 고용 둔화를 더 빨리 보여줄 수 있습니다. 서로 엇갈리면 레짐 신뢰도를 낮춰야 합니다.

6. 금리, 유동성, 신용 평가
정책 신호: {_signal_value(overview, 'policy_signal')}
유동성 신호: {_signal_value(overview, 'liquidity_signal')}
신용 신호: {_signal_value(overview, 'credit_signal')}
{_indicator_block(overview, 'interest_rates', 10)}
{_indicator_block(overview, 'liquidity_credit', 8)}
해석: 장단기 금리, 실질금리, 기대인플레이션, 신용스프레드를 같이 봐야 듀레이션·주식 밸류에이션·크레딧 위험을 분리할 수 있습니다.

7. 자산군별 시사점
{asset_lines or '- 자산군 영향도를 만들 신호가 부족합니다.'}

8. ETF 기반 포트폴리오 구성 메모
{_portfolio_block(hint)}

9. 다음에 추적할 지표
- 금리: DGS2, DGS10, T10Y2Y, DFII10, T5YIFR
- 물가: CPIAUCSL, CPILFESL, CPIENGSL, CPIUFDSL, PCEPI, PCEPILFE, MEDCPIM158SFRBCLE
- 성장/고용: GDPC1, INDPRO, RSAFS, UNRATE, PAYEMS, ICSA, JTSJOL
- 위험/유동성: BAMLH0A0HYM2, BAMLC0A0CM, VIXCLS, M2SL, WALCL

10. 결론
현재 브리프는 구조화된 Macro payload만 사용했습니다. 데이터 품질이 {overview.data_quality.status}이면 결론을 확정하지 말고, 누락·지연 계열을 먼저 채운 뒤 포트폴리오 조정 강도를 정해야 합니다."""
    warnings = []
    if overview.data_quality.status != "ok":
        warnings.append(f"매크로 데이터 품질={overview.data_quality.status} 상태에서 브리프를 생성했습니다.")
    warnings.append(
        "로컬 LLM 호출 실패 또는 제한 시간 초과로 구조화 규칙 기반 브리프를 반환했습니다."
        if llm_attempted
        else "타임아웃을 피하기 위해 로컬 LLM 호출 없이 구조화 규칙 기반 브리프를 반환했습니다."
    )
    warnings.extend(extra_warnings or [])
    return MacroBriefResponse(
        status="success",
        provider="rule_based_fallback" if llm_attempted else "structured_macro_rules",
        is_fallback=llm_attempted,
        content=brief,
        prompt_template=(AI_MACRO_BRIEF_SYSTEM_PROMPT + "\n\n" + AI_MACRO_BRIEF_TEMPLATE) if include_prompt else None,
        data_quality=overview.data_quality,
        warnings=warnings,
    )


def generate_brief(
    overview: MacroOverview,
    *,
    include_prompt: bool = False,
    use_llm: bool = False,
    model: str | None = None,
    timeout_s: float = 45.0,
) -> MacroBriefResponse:
    payload = _compact_brief_payload(overview)
    prompt = _format_prompt(payload)
    if not use_llm:
        return _fallback_brief(overview, include_prompt=include_prompt)
    try:
        content, resolved_model, latency_s = _call_ollama_macro_brief(
            prompt=prompt,
            model=model,
            timeout_s=timeout_s,
        )
        ungrounded = _find_ungrounded_numeric_tokens(content, prompt)
        if ungrounded:
            raise ValueError(
                "Macro brief grounding guard rejected ungrounded numeric token(s): "
                + ", ".join(ungrounded)
            )
        language_issue = _korean_language_issue(content)
        if language_issue:
            raise ValueError(language_issue)
        if _DIRECT_TRADE_RE.search(content):
            raise ValueError("Macro brief guard rejected direct trading language.")
        warnings = []
        if overview.data_quality.status != "ok":
            warnings.append(
                f"매크로 데이터 품질={overview.data_quality.status} 상태에서 LLM 브리프를 생성했습니다. "
                "누락 또는 지연 데이터는 불확실성으로 처리해야 합니다."
            )
        warnings.append("근거 검증 통과: 숫자 토큰을 구조화된 Macro payload와 대조했습니다.")
        warnings.append("자문 전용: 포트폴리오 정책을 바로 변경하거나 주문을 생성하지 않습니다.")
        return MacroBriefResponse(
            status="success",
            provider=f"ollama:{resolved_model}",
            is_fallback=False,
            content=content,
            prompt_template=(AI_MACRO_BRIEF_SYSTEM_PROMPT + "\n\n" + prompt) if include_prompt else None,
            data_quality=overview.data_quality,
            warnings=[*warnings, f"llm_latency_s={latency_s}"],
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback_brief(
            overview,
            include_prompt=include_prompt,
            extra_warnings=[f"로컬 LLM 매크로 브리프를 사용할 수 없어 구조화 브리프를 사용했습니다: {_safe_rejection_reason(exc)}"],
            llm_attempted=True,
        )
