from __future__ import annotations

from pipelines.signals.base import SignalRow


def generate_latest_signals(
    feature_rows: list[dict[str, object]],
    *,
    template: str = "momentum_ranking",
    research_scores: dict[str, float | None] | None = None,
) -> list[dict[str, object]]:
    template = str(template or "momentum_ranking").strip().lower()
    research_scores = research_scores or {}
    if template == "buy_and_hold":
        return [_row_from_score(row, 1.0, signal=1.0, research_score=research_scores.get(str(row.get("ticker") or ""))).to_dict() for row in feature_rows]
    if template == "volatility_targeting":
        return [_volatility_target_row(row, research_score=research_scores.get(str(row.get("ticker") or ""))).to_dict() for row in feature_rows]
    if template in {"momentum_ranking", "moving_average_trend", "research_confirmed_momentum", "risk_adjusted_momentum"}:
        scored = [
            _row_from_score(
                row,
                _score_features(
                    row.get("features") if isinstance(row.get("features"), dict) else {},
                    research_scores.get(str(row.get("ticker") or "")),
                    risk_adjusted=template == "risk_adjusted_momentum",
                ),
                research_score=research_scores.get(str(row.get("ticker") or "")),
            )
            for row in feature_rows
        ]
        ranked = sorted(scored, key=lambda item: item.final_score if item.final_score is not None else -999.0, reverse=True)
        if template in {"momentum_ranking", "risk_adjusted_momentum"}:
            winners = {item.ticker for item in ranked[: max(1, min(2, len(ranked)))] if (item.final_score or 0.0) > 0}
            return [
                SignalRow(
                    date=item.date,
                    ticker=item.ticker,
                    factor_values=item.factor_values,
                    research_score=item.research_score,
                    final_score=item.final_score,
                    signal=1.0 if item.ticker in winners else 0.0,
                    execution_date=item.execution_date,
                    diagnostics=item.diagnostics,
                ).to_dict()
                for item in scored
            ]
        return [item.to_dict() for item in scored]
    return [
        SignalRow(
            date=str(row.get("as_of") or ""),
            ticker=str(row.get("ticker") or ""),
            factor_values=row.get("features") if isinstance(row.get("features"), dict) else {},
            signal=0.0,
            diagnostics=[f"unsupported_signal_template:{template}"],
        ).to_dict()
        for row in feature_rows
    ]


def _row_from_score(
    row: dict[str, object],
    score: float | None,
    *,
    signal: float | None = None,
    research_score: float | None = None,
) -> SignalRow:
    ticker = str(row.get("ticker") or "").strip().upper()
    date = str(row.get("as_of") or "")
    diagnostics = list(row.get("diagnostics") or []) if isinstance(row.get("diagnostics"), list) else []
    factor_values = row.get("features") if isinstance(row.get("features"), dict) else {}
    if not date:
        diagnostics.append("signal_date_missing")
    diagnostics.append("execution_date_requires_next_available_bar")
    resolved_signal = signal if signal is not None else (1.0 if (score or 0.0) >= 0.55 else 0.0)
    return SignalRow(
        date=date,
        ticker=ticker,
        factor_values=factor_values,
        research_score=research_score,
        final_score=round(score, 6) if score is not None else None,
        signal=float(resolved_signal),
        execution_date=None,
        diagnostics=diagnostics,
    )


def _volatility_target_row(row: dict[str, object], *, research_score: float | None = None) -> SignalRow:
    features = row.get("features") if isinstance(row.get("features"), dict) else {}
    vol = _as_float(features.get("realized_vol_21d"))
    diagnostics = list(row.get("diagnostics") or []) if isinstance(row.get("diagnostics"), list) else []
    diagnostics.append("execution_date_requires_next_available_bar")
    if vol is None or vol <= 0:
        diagnostics.append("volatility_target_missing")
        signal = 0.0
        score = None
    else:
        signal = max(0.0, min(1.5, 0.12 / vol))
        score = max(-1.0, min(1.0, (0.35 - vol) / 0.35))
    return SignalRow(
        date=str(row.get("as_of") or ""),
        ticker=str(row.get("ticker") or "").strip().upper(),
        factor_values=features,
        research_score=research_score,
        final_score=round(score, 6) if score is not None else None,
        signal=round(signal, 6),
        execution_date=None,
        diagnostics=diagnostics,
    )


def _score_features(
    features: dict[str, object],
    research_score: float | None = None,
    *,
    risk_adjusted: bool = False,
) -> float | None:
    if not features:
        return None
    momentum = _as_float(features.get("momentum_63d") or features.get("momentum_21d") or features.get("return_5d"))
    risk_adjusted_momentum = _as_float(features.get("risk_adjusted_momentum_63d"))
    relative_strength = _as_float(features.get("relative_strength_spy_63d"))
    vol = _as_float(features.get("realized_vol_21d"))
    trend = _as_float(features.get("ma_ratio_20_50") or features.get("ma_ratio_50_200"))
    drawdown = _as_float(features.get("drawdown_current"))
    score = 0.0
    weight = 0.0
    if risk_adjusted and risk_adjusted_momentum is not None:
        score += max(-1.0, min(1.0, risk_adjusted_momentum)) * 0.50
        weight += 0.50
    elif momentum is not None:
        score += max(-1.0, min(1.0, momentum * 5.0)) * 0.45
        weight += 0.45
    if risk_adjusted and relative_strength is not None:
        score += max(-1.0, min(1.0, relative_strength * 5.0)) * 0.15
        weight += 0.15
    if trend is not None:
        score += max(-1.0, min(1.0, trend * 10.0)) * 0.25
        weight += 0.25
    if vol is not None:
        score += max(-1.0, min(1.0, (0.35 - vol) / 0.35)) * 0.15
        weight += 0.15
    if drawdown is not None:
        score += max(-1.0, min(1.0, 1.0 + drawdown * 4.0)) * 0.15
        weight += 0.15
    if research_score is not None:
        score = score * 0.75 + research_score * 0.25
        weight = max(weight, 0.75) + 0.25
    if weight <= 0:
        return None
    return max(-1.0, min(1.0, score / weight))


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
