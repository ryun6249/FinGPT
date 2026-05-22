from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import httpx

from core.config.settings import load_settings
from pipelines.strategies.storage import validate_strategy


STRATEGY_CODE_FIELDS = {
    "strategy_id",
    "name",
    "schema_version",
    "strategy_version",
    "frequency",
    "features",
    "signal",
    "portfolio",
    "execution",
    "diagnostics",
}

STRATEGY_GENERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "strategy": {"type": "object"},
        "advantages": {"type": "array", "items": {"type": "string"}},
        "disadvantages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["strategy", "advantages", "disadvantages"],
}

DEFAULT_PARAMETER_SEARCH_SPACE: dict[str, list[Any]] = {
    "lookback": [21, 42, 63, 126],
    "vol_lookback": [14, 21, 42],
    "top_n": [1, 2, 3, 5],
    "rebalance_every": [5, 10, 21, 42],
    "transaction_cost_bps": [2, 5, 10],
    "slippage_bps": [1, 2, 5],
    "portfolio_method": ["equal_weight", "inverse_volatility", "risk_parity", "minimum_volatility", "max_sharpe"],
}

PARAMETER_OBJECTIVES = {
    "risk_adjusted_return",
    "drawdown_control",
    "turnover_control",
    "balanced",
}

SYSTEM_PROMPT = """
You generate deterministic FinGPT Quant Lab strategy JSON.
Return exactly one JSON object matching the provided schema.
The strategy is not Python code. It must be a strategy definition JSON object only.
Do not include universe, tickers, benchmark, markdown, or explanations inside strategy.
execution.trade_at must be next_bar_close.
advantages and disadvantages must be natural Korean sentences only.
Do not write Chinese, Japanese, Hanja, mojibake, or garbled text in any narrative field.
""".strip()

_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
_CJK_IDEOGRAPH_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_JAPANESE_RE = re.compile(r"[\u3040-\u30ff]")
_MOJIBAKE_RE = re.compile(r"[ÃÂ�]|(?:[ìíëê][\x80-\xff]?)|(?:[æäåçèé][\x80-\xff]?)")


def generate_strategy_from_prompt(
    prompt: str,
    *,
    context: dict[str, Any] | None = None,
    use_local_llm: bool = True,
    timeout_s: float = 24.0,
    parameter_tuning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_prompt = str(prompt or "").strip()
    context = dict(context or {})
    tuning = _normalize_parameter_tuning(parameter_tuning)
    fallback = _fallback_generation(clean_prompt, context, tuning)
    if not clean_prompt:
        fallback["status"] = "failed"
        fallback["warnings"] = ["strategy_prompt_required"]
        fallback["progress"] = _generation_progress("failed", "프롬프트가 없어 LLM 호출을 시작하지 않았습니다.", 100)
        return fallback

    if not use_local_llm:
        return fallback

    settings = load_settings()
    model = str(getattr(settings, "primary_model", "") or "qwen2.5:7b")
    base_url = str(getattr(settings, "ollama_base_url", "") or "http://localhost:11434")
    try:
        raw = _call_local_llm(
            base_url=base_url,
            model=model,
            prompt=_strategy_prompt(clean_prompt, context, fallback["strategy"], tuning),
            timeout_s=max(4.0, min(float(timeout_s or 24.0), 45.0)),
        )
        parsed = _extract_json_object(raw)
        strategy = _code_only_strategy(parsed.get("strategy") if isinstance(parsed.get("strategy"), dict) else parsed)
        strategy = _repair_required_strategy_fields(strategy, clean_prompt, context)
        strategy, tuning_report = _apply_parameter_tuning(
            strategy,
            clean_prompt,
            context,
            tuning,
            source="local_llm_guided_with_guardrails",
        )
        validate_strategy(strategy)
        advantages, advantages_repaired = _clean_korean_review_list(parsed.get("advantages"), fallback["advantages"])
        disadvantages, disadvantages_repaired = _clean_korean_review_list(
            parsed.get("disadvantages"),
            fallback["disadvantages"],
        )
        warnings = []
        if advantages_repaired or disadvantages_repaired:
            warnings.append("strategy_review_language_repaired_to_korean")
        return {
            "status": "success",
            "model_status": "local_llm",
            "model": model,
            "strategy": strategy,
            "advantages": advantages,
            "disadvantages": disadvantages,
            "warnings": warnings,
            "llm_diagnostics": _llm_diagnostics(
                requested=True,
                attempted=True,
                status="success",
                model=model,
                fallback_used=False,
                base_url=base_url,
            ),
            "progress": _generation_progress("completed", "로컬 LLM 응답과 전략 JSON 검증이 완료되었습니다.", 100),
            "parameter_tuning": tuning_report,
        }
    except Exception as exc:  # noqa: BLE001
        fallback["model_status"] = "fallback_after_llm_error"
        fallback["model"] = model
        fallback["warnings"] = [f"local_llm_generation_failed:{type(exc).__name__}"]
        fallback["llm_diagnostics"] = _llm_diagnostics(
            requested=True,
            attempted=True,
            status="failed_fallback_used",
            model=model,
            fallback_used=True,
            base_url=base_url,
            error_type=type(exc).__name__,
        )
        fallback["progress"] = _generation_progress("fallback_completed", "LLM 호출 실패 후 결정론적 전략 초안으로 전환했습니다.", 100)
        return fallback


def _call_local_llm(*, base_url: str, model: str, prompt: str, timeout_s: float) -> str:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "format": STRATEGY_GENERATION_SCHEMA,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 1400},
            "keep_alive": "5m",
        },
        timeout=timeout_s,
    )
    response.raise_for_status()
    payload = response.json()
    text = str(payload.get("response") or "").strip()
    if not text:
        raise ValueError("empty local LLM response")
    return text


def _strategy_prompt(
    prompt: str,
    context: dict[str, Any],
    fallback_strategy: dict[str, Any],
    parameter_tuning: dict[str, Any],
) -> str:
    tuning_note = ""
    if parameter_tuning.get("enabled"):
        tuning_note = (
            "Parameter tuning request: choose strategy parameters inside this search space, "
            "keep execution.trade_at as next_bar_close, and keep the strategy code-only. "
            f"{json.dumps(parameter_tuning, ensure_ascii=False, sort_keys=True)}"
        )
        context = {**context, "parameter_tuning_request": parameter_tuning, "parameter_tuning_instruction": tuning_note}
    return "\n".join(
        [
            "사용자가 원하는 전략을 FinGPT Quant Lab 전략 JSON으로 변환하세요.",
            "응답은 반드시 JSON 객체 하나만 반환하세요. markdown, 주석, 코드펜스는 금지입니다.",
            "strategy 객체에는 실제 전략 정의만 넣고, 설명 문장은 advantages/disadvantages 배열에만 넣으세요.",
            "strategy 안에는 universe, tickers, benchmark를 넣지 마세요. 이 값들은 백테스트 UI가 별도로 관리합니다.",
            "advantages와 disadvantages의 모든 항목은 자연스러운 한국어 문장이어야 합니다.",
            "중국어, 일본어, 한자, 깨진 문자, mojibake를 사용하지 마세요. 확신이 없으면 쉬운 한국어로 다시 쓰세요.",
            "지원 지표: momentum_63d, realized_vol_21d, drawdown_current, ma_ratio_20_50, relative_strength_spy_63d, research_score.",
            "지원 신호: rank_top_n, trend_filter, volatility_target.",
            "지원 포트폴리오 방식: equal_weight, inverse_volatility, risk_parity, minimum_volatility, max_sharpe, momentum_tilt.",
            "execution.trade_at은 반드시 next_bar_close로 설정하세요.",
            f"현재 UI 컨텍스트: {json.dumps(context, ensure_ascii=False, sort_keys=True)}",
            f"기본 안전 초안: {json.dumps(fallback_strategy, ensure_ascii=False, sort_keys=True)}",
            f"사용자 프롬프트: {prompt}",
        ]
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("strategy generation returned non-object JSON")
    return parsed


def _fallback_generation(prompt: str, context: dict[str, Any], parameter_tuning: dict[str, Any]) -> dict[str, Any]:
    strategy = _repair_required_strategy_fields({}, prompt, context)
    strategy, tuning_report = _apply_parameter_tuning(
        strategy,
        prompt,
        context,
        parameter_tuning,
        source="deterministic_rules",
    )
    return {
        "status": "success",
        "model_status": "deterministic_fallback",
        "model": "deterministic_rules",
        "strategy": strategy,
        "advantages": [
            "다음 봉 종가 체결을 고정해 룩어헤드 편향을 줄입니다.",
            "모멘텀과 변동성 조건을 함께 사용해 단순 수익률 순위보다 위험을 더 명시적으로 반영합니다.",
            "종목 유니버스와 벤치마크를 전략 정의에서 분리해 같은 전략을 여러 백테스트 조건에 재사용할 수 있습니다.",
        ],
        "disadvantages": [
            "프롬프트가 모호하면 진입, 청산, 리밸런싱 조건이 보수적인 기본값으로 해석됩니다.",
            "거래비용, 슬리피지, 리밸런싱 주기에 민감하므로 실제 사용 전 백테스트 검증이 필요합니다.",
            "로컬 데이터 마트에 가격 이력이 없는 종목은 실행 유니버스에서 제외됩니다.",
        ],
        "warnings": [] if prompt else ["strategy_prompt_required"],
        "llm_diagnostics": _llm_diagnostics(
            requested=False,
            attempted=False,
            status="not_requested",
            model="deterministic_rules",
            fallback_used=True,
        ),
        "progress": _generation_progress("deterministic_completed", "결정론적 전략 초안 생성이 완료되었습니다.", 100),
        "parameter_tuning": tuning_report,
    }


def _normalize_parameter_tuning(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    objective = str(raw.get("objective") or "risk_adjusted_return").strip().lower()
    if objective not in PARAMETER_OBJECTIVES:
        objective = "risk_adjusted_return"
    search_space = _normalize_search_space(raw.get("search_space"))
    return {
        "enabled": bool(raw.get("enabled", False)),
        "objective": objective,
        "risk_profile": str(raw.get("risk_profile") or "balanced").strip().lower()[:40] or "balanced",
        "search_space": search_space,
        "notes": str(raw.get("notes") or "").strip()[:600],
    }


def _normalize_search_space(value: Any) -> dict[str, list[Any]]:
    source = value if isinstance(value, dict) else {}
    normalized: dict[str, list[Any]] = {}
    for key, defaults in DEFAULT_PARAMETER_SEARCH_SPACE.items():
        raw_values = source.get(key) if key in source else defaults
        if not isinstance(raw_values, list):
            raw_values = defaults
        values: list[Any] = []
        for item in raw_values:
            if key == "portfolio_method":
                method = str(item or "").strip().lower()
                if method in DEFAULT_PARAMETER_SEARCH_SPACE["portfolio_method"] and method not in values:
                    values.append(method)
                continue
            try:
                number = float(item)
            except (TypeError, ValueError):
                continue
            if not number.is_integer() and key in {"lookback", "vol_lookback", "top_n", "rebalance_every"}:
                continue
            clean_number: int | float = int(number) if number.is_integer() else round(number, 4)
            if clean_number not in values:
                values.append(clean_number)
        normalized[key] = values or list(defaults)
    return normalized


def _apply_parameter_tuning(
    strategy: dict[str, Any],
    prompt: str,
    context: dict[str, Any],
    parameter_tuning: dict[str, Any],
    *,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not parameter_tuning.get("enabled"):
        return strategy, {
            "enabled": False,
            "status": "disabled",
            "objective": parameter_tuning.get("objective") or "risk_adjusted_return",
            "source": source,
            "search_space": parameter_tuning.get("search_space") or DEFAULT_PARAMETER_SEARCH_SPACE,
            "applied_values": {},
            "adjusted_fields": [],
            "recommendations": ["파라미터 자동 조정이 꺼져 있어 기존 전략 값을 유지했습니다."],
        }

    search_space = parameter_tuning.get("search_space") or DEFAULT_PARAMETER_SEARCH_SPACE
    prompt_lower = str(prompt or "").lower()
    objective = str(parameter_tuning.get("objective") or "risk_adjusted_return")
    asset_count = int(context.get("asset_count") or len(context.get("tickers") or []) or 0)
    requested_top_n = int(context.get("top_n") or 2)

    if objective == "drawdown_control" or any(token in prompt_lower for token in ["drawdown", "mdd", "risk control"]):
        lookback = _choose_from_space(search_space, "lookback", 63, preference="high")
        vol_lookback = _choose_from_space(search_space, "vol_lookback", 21, preference="high")
        portfolio_method = _choose_method(search_space, ["risk_parity", "inverse_volatility", "minimum_volatility"])
        rebalance_every = _choose_from_space(search_space, "rebalance_every", 21, preference="high")
    elif objective == "turnover_control" or any(token in prompt_lower for token in ["turnover", "cost", "low trade"]):
        lookback = _choose_from_space(search_space, "lookback", 63, preference="high")
        vol_lookback = _choose_from_space(search_space, "vol_lookback", 21, preference="middle")
        portfolio_method = _choose_method(search_space, ["inverse_volatility", "equal_weight", "risk_parity"])
        rebalance_every = _choose_from_space(search_space, "rebalance_every", 21, preference="high")
    elif any(token in prompt_lower for token in ["short", "fast", "단기", "빠른"]):
        lookback = _choose_from_space(search_space, "lookback", 42, preference="low")
        vol_lookback = _choose_from_space(search_space, "vol_lookback", 14, preference="low")
        portfolio_method = _choose_method(search_space, ["equal_weight", "momentum_tilt", "max_sharpe"])
        rebalance_every = _choose_from_space(search_space, "rebalance_every", 10, preference="low")
    else:
        lookback = _choose_from_space(search_space, "lookback", int(context.get("lookback") or 63), preference="middle")
        vol_lookback = _choose_from_space(search_space, "vol_lookback", int(context.get("vol_lookback") or 21), preference="middle")
        portfolio_method = _choose_method(search_space, ["max_sharpe", "inverse_volatility", "equal_weight"])
        rebalance_every = _choose_from_space(search_space, "rebalance_every", int(context.get("rebalance_every") or 21), preference="middle")

    top_n_cap = asset_count if asset_count > 0 else 50
    top_n = int(_choose_from_space(search_space, "top_n", requested_top_n, preference="middle"))
    top_n = max(1, min(top_n, top_n_cap))
    transaction_cost_bps = float(_choose_from_space(search_space, "transaction_cost_bps", float(context.get("transaction_cost_bps") or 5), preference="middle"))
    slippage_bps = float(_choose_from_space(search_space, "slippage_bps", float(context.get("slippage_bps") or 2), preference="middle"))

    tuned = _code_only_strategy(strategy)
    features = tuned.get("features") if isinstance(tuned.get("features"), dict) else {}
    for feature_id in ("momentum_63d", "risk_adjusted_momentum_63d"):
        if feature_id in features and isinstance(features[feature_id], dict):
            features[feature_id]["lookback"] = int(lookback)
    if "momentum_63d" not in features:
        features["momentum_63d"] = {"id": "momentum_63d", "lookback": int(lookback)}
    if "realized_vol_21d" in features and isinstance(features["realized_vol_21d"], dict):
        features["realized_vol_21d"]["lookback"] = int(vol_lookback)
    else:
        features["realized_vol_21d"] = {"id": "realized_vol_21d", "lookback": int(vol_lookback)}
    tuned["features"] = features

    signal = tuned.get("signal") if isinstance(tuned.get("signal"), dict) else {"type": "rank_top_n"}
    signal["top_n"] = top_n
    tuned["signal"] = signal

    portfolio = tuned.get("portfolio") if isinstance(tuned.get("portfolio"), dict) else {}
    portfolio["method"] = portfolio_method
    portfolio.setdefault("max_weight", float(context.get("max_weight") or 0.5))
    tuned["portfolio"] = portfolio

    execution = tuned.get("execution") if isinstance(tuned.get("execution"), dict) else {}
    execution["trade_at"] = "next_bar_close"
    execution["transaction_cost_bps"] = transaction_cost_bps
    execution["slippage_bps"] = slippage_bps
    tuned["execution"] = execution

    applied_values = {
        "lookback": int(lookback),
        "vol_lookback": int(vol_lookback),
        "top_n": top_n,
        "rebalance_every": int(rebalance_every),
        "transaction_cost_bps": transaction_cost_bps,
        "slippage_bps": slippage_bps,
        "portfolio_method": portfolio_method,
    }
    adjusted_fields = [
        "features.momentum_63d.lookback",
        "features.realized_vol_21d.lookback",
        "signal.top_n",
        "portfolio.method",
        "execution.transaction_cost_bps",
        "execution.slippage_bps",
        "diagnostics.rebalance_every",
    ]
    diagnostics = tuned.get("diagnostics") if isinstance(tuned.get("diagnostics"), dict) else {}
    diagnostics["rebalance_every"] = int(rebalance_every)
    diagnostics["parameter_tuning"] = {
        "enabled": True,
        "objective": objective,
        "source": source,
        "applied_values": applied_values,
        "adjusted_fields": adjusted_fields,
    }
    tuned["diagnostics"] = diagnostics

    return tuned, {
        "enabled": True,
        "status": "applied",
        "objective": objective,
        "source": source,
        "search_space": search_space,
        "applied_values": applied_values,
        "adjusted_fields": adjusted_fields,
        "recommendations": [
            f"{lookback}일 신호 룩백과 {vol_lookback}일 변동성 룩백을 사용합니다.",
            f"상위 {top_n}개 자산과 {portfolio_method} 배분을 적용합니다.",
            f"리밸런싱 {rebalance_every}일, 비용 {transaction_cost_bps:g}bps, 슬리피지 {slippage_bps:g}bps를 검증 기준으로 둡니다.",
        ],
    }


def _choose_from_space(search_space: dict[str, list[Any]], key: str, fallback: int | float, *, preference: str) -> int | float:
    values = sorted(float(item) for item in search_space.get(key, []) if isinstance(item, (int, float)))
    if not values:
        return fallback
    if preference == "low":
        return int(values[0]) if values[0].is_integer() else values[0]
    if preference == "high":
        return int(values[-1]) if values[-1].is_integer() else values[-1]
    target = float(fallback)
    chosen = min(values, key=lambda item: abs(item - target))
    return int(chosen) if chosen.is_integer() else chosen


def _choose_method(search_space: dict[str, list[Any]], preferences: list[str]) -> str:
    methods = [str(item) for item in search_space.get("portfolio_method", [])]
    for method in preferences:
        if method in methods:
            return method
    return methods[0] if methods else "equal_weight"


def _llm_diagnostics(
    *,
    requested: bool,
    attempted: bool,
    status: str,
    model: str,
    fallback_used: bool,
    base_url: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "requested": requested,
        "attempted": attempted,
        "status": status,
        "model": model,
        "fallback_used": fallback_used,
    }
    if base_url:
        diagnostics["base_url"] = base_url
    if error_type:
        diagnostics["error_type"] = error_type
    return diagnostics


def _generation_progress(stage: str, message: str, percent: int) -> dict[str, Any]:
    return {
        "mode": "synchronous_estimate",
        "stage": stage,
        "message": message,
        "percent": max(0, min(100, int(percent))),
    }


def _repair_required_strategy_fields(strategy: dict[str, Any], prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    clean = _code_only_strategy(strategy)
    prompt_hash = hashlib.sha1(
        prompt.encode("utf-8", errors="ignore"),
        usedforsecurity=False,
    ).hexdigest()[:10]
    lookback = _number_near(
        prompt,
        [r"(\d{2,4})\s*일", r"(\d{2,4})\s*day", r"(\d{2,4})d"],
        int(context.get("lookback") or 63),
    )
    vol_lookback = _number_near(
        prompt,
        [r"(\d{1,3})\s*일\s*변동성", r"변동성\s*(\d{1,3})", r"vol(?:atility)?\s*(\d{1,3})"],
        int(context.get("vol_lookback") or 21),
    )
    top_n = _number_near(
        prompt,
        [r"top\s*(\d{1,2})", r"상위\s*(\d{1,2})", r"(\d{1,2})\s*개"],
        int(context.get("top_n") or 2),
    )
    top_n = max(1, min(top_n, 50))

    prompt_lower = prompt.lower()
    use_research = bool(context.get("use_research_score")) or any(
        token in prompt_lower for token in ["research", "news", "리서치", "뉴스", "근거", "공시"]
    )
    portfolio_method = str(context.get("portfolio_method") or "equal_weight").lower()
    if "risk parity" in prompt_lower or "리스크 패리티" in prompt_lower:
        portfolio_method = "risk_parity"
    elif "minimum vol" in prompt_lower or "최소 변동" in prompt_lower:
        portfolio_method = "minimum_volatility"
    elif "inverse vol" in prompt_lower or "변동성 역가중" in prompt_lower or "역변동성" in prompt_lower:
        portfolio_method = "inverse_volatility"
    elif "max sharpe" in prompt_lower or "샤프" in prompt_lower:
        portfolio_method = "max_sharpe"

    strategy_id = str(clean.get("strategy_id") or f"prompt_strategy_{prompt_hash}").strip().lower()
    strategy_id = re.sub(r"[^a-z0-9_-]+", "_", strategy_id).strip("_") or f"prompt_strategy_{prompt_hash}"
    clean["strategy_id"] = strategy_id[:80]
    name = str(clean.get("name") or "").strip()
    clean["name"] = _strategy_name(prompt) if not name or _has_disallowed_language(name) else name[:120]
    clean.setdefault("schema_version", "quant_strategy_v1")
    clean.setdefault("strategy_version", "1")
    clean.setdefault("frequency", "daily")
    features = clean.get("features") if isinstance(clean.get("features"), dict) else {}
    features.setdefault("momentum_63d", {"id": "momentum_63d", "lookback": lookback})
    features.setdefault("realized_vol_21d", {"id": "realized_vol_21d", "lookback": vol_lookback})
    if "drawdown" in prompt_lower or "mdd" in prompt_lower or "낙폭" in prompt_lower or "드로다운" in prompt_lower:
        features.setdefault("drawdown_current", {"id": "drawdown_current"})
    if "trend" in prompt_lower or "이동평균" in prompt_lower or "추세" in prompt_lower:
        features.setdefault("ma_ratio_20_50", {"id": "ma_ratio_20_50"})
    if use_research:
        features.setdefault("research_score", {"id": "research_score", "max_age_days": int(context.get("research_max_age_days") or 7)})
    clean["features"] = features
    clean.setdefault("signal", {"type": "rank_top_n", "top_n": top_n})
    if isinstance(clean.get("signal"), dict):
        clean["signal"].setdefault("type", "rank_top_n")
        clean["signal"].setdefault("top_n", top_n)
    clean.setdefault("portfolio", {"method": portfolio_method, "max_weight": float(context.get("max_weight") or 0.5)})
    if isinstance(clean.get("portfolio"), dict):
        clean["portfolio"].setdefault("method", portfolio_method)
        clean["portfolio"].setdefault("max_weight", float(context.get("max_weight") or 0.5))
    clean["execution"] = {
        **(clean.get("execution") if isinstance(clean.get("execution"), dict) else {}),
        "trade_at": "next_bar_close",
        "transaction_cost_bps": float(context.get("transaction_cost_bps") or 5),
        "slippage_bps": float(context.get("slippage_bps") or 2),
    }
    diagnostics = clean.get("diagnostics") if isinstance(clean.get("diagnostics"), dict) else {}
    diagnostics.update(
        {
            "require_no_lookahead": True,
            "prompt_hash": prompt_hash,
            "freshness_profile": context.get("freshness_profile") or "research_default",
            "require_fresh_prices": bool(context.get("require_fresh_prices")),
        }
    )
    clean["diagnostics"] = diagnostics
    return _code_only_strategy(clean)


def _strategy_name(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(prompt or "").strip())
    if not cleaned or _has_disallowed_language(cleaned):
        return "Prompt Strategy"
    return cleaned[:36].rstrip(" ,.;") or "Prompt Strategy"


def _number_near(prompt: str, patterns: list[str], fallback: int) -> int:
    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            continue
    return fallback


def _clean_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = " ".join(str(item or "").split()).strip()
        if text:
            out.append(text[:240])
    return out[:6]


def _clean_korean_review_list(value: Any, fallback: list[str]) -> tuple[list[str], bool]:
    raw = _clean_text_list(value)
    cleaned = [item for item in raw if _is_usable_korean_review_text(item)]
    repaired = len(cleaned) != len(raw)
    for fallback_item in fallback:
        if len(cleaned) >= 2:
            break
        if fallback_item not in cleaned:
            cleaned.append(fallback_item)
            repaired = True
    if not cleaned:
        return fallback[:6], bool(raw)
    return cleaned[:6], repaired


def _is_usable_korean_review_text(text: Any) -> bool:
    value = " ".join(str(text or "").split()).strip()
    if not value or _has_disallowed_language(value):
        return False
    return len(_HANGUL_RE.findall(value)) >= 4


def _has_disallowed_language(text: Any) -> bool:
    value = str(text or "")
    return bool(_CJK_IDEOGRAPH_RE.search(value) or _JAPANESE_RE.search(value) or _MOJIBAKE_RE.search(value))


def _code_only_strategy(strategy: dict[str, Any] | None) -> dict[str, Any]:
    source = strategy if isinstance(strategy, dict) else {}
    clean = {key: value for key, value in source.items() if key in STRATEGY_CODE_FIELDS}
    clean.pop("universe", None)
    clean.pop("benchmark", None)
    return clean
