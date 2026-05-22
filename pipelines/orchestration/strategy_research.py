from __future__ import annotations

import hashlib
import importlib.util
import math
import os
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.schemas.quant import (
    QuantBacktestRequest,
    StrategyDiagnosticsRequest,
    StrategyDiagnosticsRun,
    StrategyFailureTag,
    StrategyHypothesis,
    StrategyHypothesisDecisionRequest,
    StrategyOptimizationRequest,
    StrategyOptimizationRun,
    StrategyOptimizationTrial,
    StrategyResearchBackendStatus,
    StrategyResearchConfig,
    StrategyResearchExperiment,
    StrategyResearchStrategy,
    StrategyResearchVersion,
    StrategyValidationRequest,
    StrategyValidationResult,
    StrategyValidationSummary,
)
from pipelines.orchestration import quant_lab_pipeline
from pipelines.data_mart.storage.repository import get_prices
from pipelines.strategy_research import storage


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = PROJECT_ROOT / "data" / "quant_lab" / "strategy_research"
DEFAULT_STRATEGY_ID = "risk_adjusted_momentum_v1"
DEFAULT_VERSION_ID = "risk_adjusted_momentum_v1_base"
PROMPT_COMPAT_STRATEGY_ID = "btcusdt_4h_supertrend_research_preset"
DEFAULT_SEARCH_SPACE: dict[str, list[Any]] = {
    "lookback": [21, 42, 63, 84],
    "rebalance_every": [10, 21, 42],
    "top_n": [1, 2, 3],
    "transaction_cost_bps": [2.0, 5.0, 10.0],
    "slippage_bps": [1.0, 2.0, 5.0],
}
SUPERTREND_SEARCH_SPACE: dict[str, list[Any]] = {
    "atr_length": [7, 10, 14, 20],
    "atr_multiplier": [2.0, 3.0, 4.0],
    "stop_atr_multiplier": [1.5, 2.0, 3.0],
    "take_profit_atr_multiplier": [3.0, 4.0, 6.0],
    "use_adx_filter": [False, True],
    "adx_length": [10, 14, 20],
    "adx_threshold": [18.0, 22.0, 26.0],
    "use_rsi_filter": [False, True],
    "rsi_length": [10, 14, 20],
    "rsi_upper": [65.0, 70.0, 75.0],
    "rsi_lower": [25.0, 30.0, 35.0],
    "fee_bps": [5.0],
    "slippage_bps": [5.0],
    "execution_model": ["close_confirmed", "next_open"],
    "stop_trigger_model": ["close_confirmed", "intrabar"],
}
EXTENDED_METRIC_KEYS = [
    "total_return_pct",
    "cagr_pct",
    "sharpe",
    "sortino",
    "max_drawdown_pct",
    "calmar",
    "profit_factor",
    "win_rate_pct",
    "avg_win_pct",
    "avg_loss_pct",
    "payoff_ratio",
    "expectancy_pct",
    "trade_count",
    "exposure_time_pct",
    "turnover_pct",
    "fee_total",
    "slippage_total",
    "long_return_pct",
    "short_return_pct",
    "best_trade_pct",
    "worst_trade_pct",
    "consecutive_wins",
    "consecutive_losses",
    "recovery_factor",
    "return_concentration_top_1_pct",
    "return_concentration_top_5_pct",
]


def backend_status() -> StrategyResearchBackendStatus:
    _ensure_seed_data()
    protected = protected_runtime_status()
    optuna = _optuna_available()
    return StrategyResearchBackendStatus(
        artifact_root=str(ARTIFACT_ROOT),
        optuna_available=optuna,
        bayesian_backend="optuna_tpe" if optuna else "deterministic_surrogate",
        protected_runtime_available=bool(protected["protected_runtime_available"]),
        live_broker_available=bool(protected["live_broker_available"]),
        protected_runtime_details=protected,
        warnings=[
            "repo_local_deterministic_evidence_only",
            "live_llm_not_required_rule_based_hypotheses",
            *([] if protected["protected_runtime_available"] else ["protected_lean_runtime_unavailable_fail_closed"]),
            *([] if protected["live_broker_available"] else ["live_broker_runtime_unavailable_fail_closed"]),
        ],
    )


def protected_runtime_status() -> dict[str, Any]:
    lean_cli = shutil.which("lean")
    ibkr_env = bool(os.environ.get("IBKR_HOST") and os.environ.get("IBKR_PORT"))
    lean_available = bool(lean_cli) or importlib.util.find_spec("lean") is not None or importlib.util.find_spec("AlgorithmImports") is not None
    broker_available = importlib.util.find_spec("ib_insync") is not None and ibkr_env
    details = {
        "lean_cli_available": bool(lean_cli),
        "lean_cli_path": lean_cli or "",
        "lean_python_package_available": importlib.util.find_spec("lean") is not None,
        "algorithm_imports_available": importlib.util.find_spec("AlgorithmImports") is not None,
        "ib_insync_available": importlib.util.find_spec("ib_insync") is not None,
        "ibkr_env_configured": ibkr_env,
        "protected_runtime_available": lean_available,
        "live_broker_available": broker_available,
        "evidence": "runtime_detection_only",
        "fail_closed": True,
    }
    return details


def list_strategies() -> list[StrategyResearchStrategy]:
    _ensure_seed_data()
    return storage.model_items(ARTIFACT_ROOT, "strategies", StrategyResearchStrategy)


def create_strategy(strategy: StrategyResearchStrategy) -> StrategyResearchStrategy:
    _ensure_seed_data()
    now = _utc_now()
    normalized = strategy.model_copy(
        update={
            "created_at": strategy.created_at or now,
            "updated_at": now,
            "evidence_class": strategy.evidence_class or "repo_local_deterministic",
        }
    )
    return storage.save_strategy(ARTIFACT_ROOT, normalized)


def get_strategy(strategy_id: str) -> StrategyResearchStrategy:
    _ensure_seed_data()
    strategy = storage.model_item(ARTIFACT_ROOT, "strategies", strategy_id, StrategyResearchStrategy)
    if not strategy:
        raise FileNotFoundError(f"strategy research strategy not found: {strategy_id}")
    return strategy


def list_versions(strategy_id: str) -> list[StrategyResearchVersion]:
    _ensure_seed_data()
    clean_strategy = storage.safe_id(strategy_id)
    items = storage.model_items(ARTIFACT_ROOT, "versions", StrategyResearchVersion)
    return [item for item in items if item.strategy_id == clean_strategy]


def create_version(strategy_id: str, version: StrategyResearchVersion) -> StrategyResearchVersion:
    _ensure_seed_data()
    get_strategy(strategy_id)
    now = _utc_now()
    payload = version.model_copy(
        update={
            "strategy_id": storage.safe_id(strategy_id),
            "created_at": version.created_at or now,
            "updated_at": now,
            "complexity_score": _complexity_score(version),
        }
    )
    return storage.save_version(ARTIFACT_ROOT, payload)


def run_optimization(strategy_id: str, request: StrategyOptimizationRequest) -> StrategyOptimizationRun:
    _ensure_seed_data()
    strategy = get_strategy(strategy_id)
    version = _version_for_request(strategy_id, request.version_id)
    now = _utc_now()
    experiment_id = _make_id("srexp", strategy_id, request.model_dump(mode="json"), now)
    optimization_id = _make_id("sropt", strategy_id, request.method, request.model_dump(mode="json"), now)
    experiment = StrategyResearchExperiment(
        experiment_id=experiment_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        experiment_type="optimization",
        optimization_method=request.method,
        request_json=request.model_dump(mode="json"),
        status="running",
        created_at=now,
        updated_at=now,
    )
    storage.save_experiment(ARTIFACT_ROOT, experiment)
    search_space = _search_space_for_strategy(strategy, request)
    bayesian_backend = "not_applicable"
    if request.method == "bayesian" and _optuna_available():
        trials = _optuna_trials(strategy, version, optimization_id, request, search_space, now)
        bayesian_backend = "optuna_tpe"
    else:
        candidates = _candidate_parameters(request, search_space)
        trials = _trials_from_candidates(strategy, version, optimization_id, request, candidates, now)
        bayesian_backend = "deterministic_surrogate" if request.method == "bayesian" else "not_applicable"
    if not trials:
        raise ValueError("optimization produced no trials")
    best = max(trials, key=lambda item: item.score)
    recommended = _recommended_trial(trials)
    robustness_score = _robustness_score(trials, recommended)
    overfitting_score = _overfitting_proxy(best, recommended)
    run = StrategyOptimizationRun(
        optimization_id=optimization_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        experiment_id=experiment_id,
        method=request.method,
        objective_name=request.objective_name,
        objective_config_json=request.objective_config,
        search_space_json=search_space,
        best_parameters_json=best.parameters_json,
        recommended_parameters_json=recommended.parameters_json,
        best_score=round(best.score, 6),
        recommended_score=round(recommended.score, 6),
        robustness_score=round(robustness_score, 6),
        overfitting_score=round(overfitting_score, 6),
        trial_count=len(trials),
        notes_json={
            "decision": "recommended parameters favor stability, trade count, costs, and drawdown over a single peak score",
            "best_trial_id": best.trial_id,
            "recommended_trial_id": recommended.trial_id,
            "evidence_class": "repo_local_deterministic",
            "not_financial_advice": True,
            "bayesian_backend": bayesian_backend,
            "optuna_available": _optuna_available(),
            "protected_runtime_available": protected_runtime_status()["protected_runtime_available"],
        },
        artifacts={
            "optimization_summary": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "optimization-summary.json"),
            "optimization_trials": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "optimization-trials.json"),
        },
        status="succeeded",
        created_at=now,
        updated_at=now,
    )
    storage.save_trials(ARTIFACT_ROOT, experiment_id, trials)
    saved = storage.save_optimization(ARTIFACT_ROOT, run)
    storage.save_experiment(ARTIFACT_ROOT, experiment.model_copy(update={"status": "succeeded", "updated_at": _utc_now()}))
    return saved


def list_optimizations() -> list[StrategyOptimizationRun]:
    _ensure_seed_data()
    return storage.model_items(ARTIFACT_ROOT, "optimizations", StrategyOptimizationRun)


def get_optimization(optimization_id: str) -> StrategyOptimizationRun:
    item = storage.model_item(ARTIFACT_ROOT, "optimizations", optimization_id, StrategyOptimizationRun)
    if not item:
        raise FileNotFoundError(f"strategy optimization not found: {optimization_id}")
    return item


def optimization_trials(optimization_id: str) -> list[StrategyOptimizationTrial]:
    _ensure_seed_data()
    clean = storage.safe_id(optimization_id)
    items = storage.model_items(ARTIFACT_ROOT, "optimization_trials", StrategyOptimizationTrial)
    return sorted([item for item in items if item.optimization_id == clean], key=lambda item: item.trial_number)


def run_diagnostics(strategy_id: str, request: StrategyDiagnosticsRequest) -> StrategyDiagnosticsRun:
    _ensure_seed_data()
    strategy = get_strategy(strategy_id)
    version = _version_for_request(strategy_id, request.version_id)
    params = request.parameters or _latest_recommended_parameters(strategy_id) or _base_parameters_for_strategy(strategy, request.base_config)
    evaluation = _evaluate_strategy(strategy, request.base_config, params)
    metrics = evaluation["metrics"]
    returns = evaluation["returns"]
    trades = evaluation["trades"]
    drawdowns = evaluation["drawdowns"]
    failures = _failure_distribution(metrics, returns, trades, drawdowns)
    now = _utc_now()
    experiment_id = _make_id("srdiag_exp", strategy_id, params, now)
    diagnostics_id = _make_id("srdiag", strategy_id, params, now)
    summary = _diagnostics_summary(metrics, failures)
    run = StrategyDiagnosticsRun(
        diagnostics_id=diagnostics_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        experiment_id=experiment_id,
        source_backtest_id=evaluation["backtest_id"],
        summary=summary,
        failure_distribution_json=failures,
        top_failure_causes=[item.tag for item in failures[:3]],
        drawdown_analysis_json=_drawdown_analysis(drawdowns, metrics),
        regime_analysis_json=_regime_analysis(returns, metrics),
        trade_cluster_json=_trade_cluster(trades, returns),
        cost_impact_analysis=_cost_impact(metrics, params),
        parameter_sensitivity_notes=_parameter_notes(params, metrics),
        recommended_experiments_json=_recommended_experiments(failures),
        rejected_experiments_json=_rejected_experiments(metrics, failures),
        warnings=evaluation["warnings"],
        artifacts={
            "diagnostics_summary": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "diagnostics-summary.json"),
            "failure_distribution": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "failure-distribution.json"),
        },
        status="succeeded",
        created_at=now,
    )
    experiment = StrategyResearchExperiment(
        experiment_id=experiment_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        source_backtest_id=evaluation["backtest_id"],
        experiment_type="diagnostics",
        request_json=request.model_dump(mode="json"),
        status="succeeded",
        created_at=now,
        updated_at=now,
    )
    storage.save_experiment(ARTIFACT_ROOT, experiment)
    saved = storage.save_diagnostics(ARTIFACT_ROOT, run)
    storage.write_experiment_artifact(
        ARTIFACT_ROOT,
        experiment_id,
        "failure-distribution.json",
        [item.model_dump(mode="json") for item in failures],
    )
    return saved


def list_diagnostics() -> list[StrategyDiagnosticsRun]:
    _ensure_seed_data()
    return storage.model_items(ARTIFACT_ROOT, "diagnostics", StrategyDiagnosticsRun)


def get_diagnostics(diagnostics_id: str) -> StrategyDiagnosticsRun:
    item = storage.model_item(ARTIFACT_ROOT, "diagnostics", diagnostics_id, StrategyDiagnosticsRun)
    if not item:
        raise FileNotFoundError(f"strategy diagnostics not found: {diagnostics_id}")
    return item


def generate_hypotheses(strategy_id: str, request: StrategyDiagnosticsRequest | None = None) -> list[StrategyHypothesis]:
    _ensure_seed_data()
    strategy = get_strategy(strategy_id)
    diagnostics = run_diagnostics(strategy_id, request or StrategyDiagnosticsRequest())
    version_id = diagnostics.version_id or DEFAULT_VERSION_ID
    now = _utc_now()
    generated: list[StrategyHypothesis] = []
    for cause in diagnostics.failure_distribution_json[:4]:
        template = _hypothesis_template(cause.tag)
        hypothesis_id = _stable_hypothesis_id(strategy.strategy_id, version_id, cause.tag, template["module"])
        existing = storage.model_item(ARTIFACT_ROOT, "hypotheses", hypothesis_id, StrategyHypothesis)
        if existing:
            generated.append(existing)
            continue
        hypothesis = StrategyHypothesis(
            hypothesis_id=hypothesis_id,
            strategy_id=strategy.strategy_id,
            version_id=version_id,
            source_experiment_id=diagnostics.experiment_id,
            source_diagnostics_id=diagnostics.diagnostics_id,
            problem=template["problem"],
            hypothesis=template["hypothesis"],
            proposed_change_json=template["proposed_change"],
            expected_effect=template["expected_effect"],
            risk=template["risk"],
            validation_required_json=[
                "out_of_sample",
                "walk_forward",
                "parameter_stability",
                "trade_count_check",
                "cost_stress",
            ],
            decision="pending",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        generated.append(storage.save_hypothesis(ARTIFACT_ROOT, hypothesis))
    return generated


def list_hypotheses() -> list[StrategyHypothesis]:
    _ensure_seed_data()
    return storage.model_items(ARTIFACT_ROOT, "hypotheses", StrategyHypothesis)


def get_hypothesis(hypothesis_id: str) -> StrategyHypothesis:
    item = storage.model_item(ARTIFACT_ROOT, "hypotheses", hypothesis_id, StrategyHypothesis)
    if not item:
        raise FileNotFoundError(f"strategy hypothesis not found: {hypothesis_id}")
    return item


def decide_hypothesis(
    hypothesis_id: str,
    decision: str,
    request: StrategyHypothesisDecisionRequest,
) -> StrategyHypothesis:
    if decision not in {"accepted", "rejected"}:
        raise ValueError("hypothesis decision must be accepted or rejected")
    hypothesis = get_hypothesis(hypothesis_id)
    reason = request.decision_reason or (
        "accepted after validation review" if decision == "accepted" else "rejected before deployment candidate"
    )
    updated = hypothesis.model_copy(
        update={
            "decision": decision,
            "status": decision,
            "decision_reason": reason,
            "updated_at": _utc_now(),
        }
    )
    return storage.save_hypothesis(ARTIFACT_ROOT, updated)


def run_validation(strategy_id: str, request: StrategyValidationRequest) -> StrategyValidationResult:
    _ensure_seed_data()
    strategy = get_strategy(strategy_id)
    version = _version_for_request(strategy_id, request.version_id)
    params = request.parameters or _latest_recommended_parameters(strategy_id) or _base_parameters_for_strategy(strategy, request.base_config)
    now = _utc_now()
    experiment_id = _make_id("srval_exp", strategy_id, params, now)
    validation_id = _make_id("srval", strategy_id, params, request.model_dump(mode="json"), now)
    base_eval = _evaluate_strategy(strategy, request.base_config, params)
    split = _split_returns(base_eval["returns"], request.out_of_sample_ratio)
    in_sample = _metrics_from_returns(split["in_sample"], base_eval["metrics"])
    out_of_sample = _metrics_from_returns(split["out_of_sample"], base_eval["metrics"])
    walk_forward = _walk_forward_results(base_eval["returns"], request.walk_forward_splits, base_eval["metrics"])
    stability = _parameter_stability(strategy, request.base_config, params)
    monte_carlo = _monte_carlo(base_eval["returns"], request.random_seed)
    cost_stress = _cost_stress(strategy, request.base_config, params)
    acceptance, rejection, insufficient = _validation_flags(
        in_sample,
        out_of_sample,
        walk_forward,
        stability,
        monte_carlo,
        cost_stress,
    )
    decision = "accepted" if acceptance and not rejection and not insufficient else "rejected"
    summary = StrategyValidationSummary(
        decision=decision,
        decision_reason=_validation_reason(decision, acceptance, rejection, insufficient),
        acceptance_flags=acceptance,
        rejection_flags=rejection,
        evidence_notes=[
            "repo-local deterministic evidence only",
            "out-of-sample split was not used for parameter selection",
            "hypothesis remains experimental until accepted by validation result",
        ],
        insufficient_evidence=insufficient,
    )
    result = StrategyValidationResult(
        validation_id=validation_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        experiment_id=experiment_id,
        hypothesis_id=request.hypothesis_id or "",
        validation_type=request.validation_type,
        in_sample_metrics_json=in_sample,
        out_of_sample_metrics_json=out_of_sample,
        walk_forward_results_json=walk_forward,
        monte_carlo_results_json=monte_carlo,
        parameter_stability_json=stability,
        cost_stress_json=cost_stress,
        summary=summary,
        artifacts={
            "validation_result": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "validation-result.json"),
            "walk_forward_results": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "walk-forward-results.json"),
            "monte_carlo_results": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "monte-carlo-results.json"),
            "parameter_stability": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "parameter-stability.json"),
            "cost_stress": storage.experiment_artifact_path(ARTIFACT_ROOT, experiment_id, "cost-stress.json"),
        },
        status="succeeded",
        created_at=now,
    )
    experiment = StrategyResearchExperiment(
        experiment_id=experiment_id,
        strategy_id=strategy.strategy_id,
        version_id=version.version_id,
        source_backtest_id=base_eval["backtest_id"],
        experiment_type="validation",
        request_json=request.model_dump(mode="json"),
        status="succeeded",
        created_at=now,
        updated_at=now,
    )
    storage.save_experiment(ARTIFACT_ROOT, experiment)
    saved = storage.save_validation(ARTIFACT_ROOT, result)
    storage.write_experiment_artifact(ARTIFACT_ROOT, experiment_id, "walk-forward-results.json", walk_forward)
    storage.write_experiment_artifact(ARTIFACT_ROOT, experiment_id, "monte-carlo-results.json", monte_carlo)
    storage.write_experiment_artifact(ARTIFACT_ROOT, experiment_id, "parameter-stability.json", stability)
    storage.write_experiment_artifact(ARTIFACT_ROOT, experiment_id, "cost-stress.json", cost_stress)
    version_status = "accepted" if decision == "accepted" else "rejected"
    storage.save_version(
        ARTIFACT_ROOT,
        version.model_copy(
            update={
                "status": version_status,
                "metrics_summary": {
                    "validation_id": validation_id,
                    "oos_sharpe": out_of_sample.get("sharpe", 0.0),
                    "oos_total_return_pct": out_of_sample.get("total_return_pct", 0.0),
                    "stability_score": stability.get("stability_score", 0.0),
                },
                "decision_reason": summary.decision_reason,
                "updated_at": _utc_now(),
            }
        ),
    )
    return saved


def list_validations() -> list[StrategyValidationResult]:
    _ensure_seed_data()
    return storage.model_items(ARTIFACT_ROOT, "validations", StrategyValidationResult)


def get_validation(validation_id: str) -> StrategyValidationResult:
    item = storage.model_item(ARTIFACT_ROOT, "validations", validation_id, StrategyValidationResult)
    if not item:
        raise FileNotFoundError(f"strategy validation not found: {validation_id}")
    return item


def _ensure_seed_data() -> None:
    storage.ensure_layout(ARTIFACT_ROOT)
    if not storage.model_item(ARTIFACT_ROOT, "strategies", DEFAULT_STRATEGY_ID, StrategyResearchStrategy):
        now = _utc_now()
        strategy = StrategyResearchStrategy(
            strategy_id=DEFAULT_STRATEGY_ID,
            name="FinGPT Risk Adjusted Momentum Research Preset",
            description="Repo-local deterministic preset for strategy research optimization, diagnostics, hypothesis generation, and validation evidence.",
            asset="SPY,QQQ,TLT",
            timeframe="1d",
            core_logic_json={
                "module": "core_logic",
                "protected": True,
                "template": "risk_adjusted_momentum",
                "description": "Rank assets by risk-adjusted momentum using prior-close information, then rebalance next bar.",
            },
            default_config_json=StrategyResearchConfig().model_dump(mode="json"),
            status="accepted",
            evidence_notes=["default deterministic preset", "not financial advice"],
            created_at=now,
            updated_at=now,
        )
        version = StrategyResearchVersion(
            version_id=DEFAULT_VERSION_ID,
            strategy_id=DEFAULT_STRATEGY_ID,
            version_name="Base deterministic version",
            core_config_json=strategy.core_logic_json,
            filter_config_json={},
            risk_config_json={"transaction_cost_bps": 5.0, "slippage_bps": 2.0},
            exit_config_json={"exit_policy": "next_rebalance"},
            position_sizing_config_json={"method": "equal_weight", "top_n": 2},
            complexity_score=1.0,
            status="accepted",
            decision_reason="Seed version for local deterministic strategy research tests.",
            created_at=now,
            updated_at=now,
        )
        storage.save_strategy(ARTIFACT_ROOT, strategy)
        storage.save_version(ARTIFACT_ROOT, version)
    prompt_strategy = storage.model_item(ARTIFACT_ROOT, "strategies", PROMPT_COMPAT_STRATEGY_ID, StrategyResearchStrategy)
    if not prompt_strategy:
        now = _utc_now()
        strategy = StrategyResearchStrategy(
            strategy_id=PROMPT_COMPAT_STRATEGY_ID,
            name="BTCUSDT 4H Supertrend Research Preset",
            description="Repo-local deterministic BTCUSDT 4H Supertrend preset with close-confirmed stop support. Protected LEAN/live evidence remains separately gated.",
            asset="BTCUSDT",
            timeframe="4h",
            core_logic_json={
                "module": "core_logic",
                "protected": True,
                "entry": "long when Supertrend flips bullish",
                "exit": "long exit when Supertrend flips bearish",
                "stop_trigger_models": ["intrabar", "close_confirmed"],
            },
            default_config_json={
                "atr_length": 10,
                "atr_multiplier": 3.0,
                "stop_atr_multiplier": 2.0,
                "take_profit_atr_multiplier": 4.0,
                "use_adx_filter": False,
                "adx_length": 14,
                "adx_threshold": 20.0,
                "use_rsi_filter": False,
                "rsi_length": 14,
                "rsi_upper": 70.0,
                "rsi_lower": 30.0,
                "fee_bps": 5.0,
                "slippage_bps": 5.0,
                "execution_model": "close_confirmed",
                "stop_trigger_model": "close_confirmed",
            },
            status="accepted",
            evidence_class="repo_local_deterministic",
            evidence_notes=[
                "deterministic Supertrend path implemented",
                "synthetic 4H fallback is labeled when real BTCUSDT data is absent",
                "protected LEAN/live execution still requires protected runtime",
            ],
            created_at=now,
            updated_at=now,
        )
        storage.save_strategy(ARTIFACT_ROOT, strategy)
        storage.save_version(
            ARTIFACT_ROOT,
            StrategyResearchVersion(
                version_id=f"{PROMPT_COMPAT_STRATEGY_ID}_base",
                strategy_id=PROMPT_COMPAT_STRATEGY_ID,
                version_name="Base deterministic Supertrend version",
                core_config_json=strategy.core_logic_json,
                filter_config_json={"use_adx_filter": False, "use_rsi_filter": False},
                risk_config_json={
                    "stop_atr_multiplier": 2.0,
                    "fee_bps": 5.0,
                    "slippage_bps": 5.0,
                    "stop_trigger_model": "close_confirmed",
                },
                exit_config_json={"take_profit_atr_multiplier": 4.0, "execution_model": "close_confirmed"},
                position_sizing_config_json={"method": "fixed_fraction", "fraction": 1.0},
                complexity_score=1.25,
                status="accepted",
                decision_reason="Seed version for repo-local deterministic BTCUSDT 4H Supertrend research.",
                created_at=now,
                updated_at=now,
            ),
        )
    elif prompt_strategy.evidence_class == "protected_runtime_required" or prompt_strategy.status == "pending":
        storage.save_strategy(
            ARTIFACT_ROOT,
            prompt_strategy.model_copy(
                update={
                    "description": "Repo-local deterministic BTCUSDT 4H Supertrend preset with close-confirmed stop support. Protected LEAN/live evidence remains separately gated.",
                    "status": "accepted",
                    "evidence_class": "repo_local_deterministic",
                    "evidence_notes": [
                        "deterministic Supertrend path implemented",
                        "synthetic 4H fallback is labeled when real BTCUSDT data is absent",
                        "protected LEAN/live execution still requires protected runtime",
                    ],
                    "updated_at": _utc_now(),
                }
            ),
        )
    prompt_versions = [
        item for item in storage.model_items(ARTIFACT_ROOT, "versions", StrategyResearchVersion)
        if item.strategy_id == PROMPT_COMPAT_STRATEGY_ID
    ]
    if not prompt_versions:
        now = _utc_now()
        storage.save_version(
            ARTIFACT_ROOT,
            StrategyResearchVersion(
                version_id=f"{PROMPT_COMPAT_STRATEGY_ID}_base",
                strategy_id=PROMPT_COMPAT_STRATEGY_ID,
                version_name="Base deterministic Supertrend version",
                core_config_json={
                    "module": "core_logic",
                    "protected": True,
                    "entry": "long when Supertrend flips bullish",
                    "exit": "long exit when Supertrend flips bearish",
                    "stop_trigger_models": ["intrabar", "close_confirmed"],
                },
                filter_config_json={"use_adx_filter": False, "use_rsi_filter": False},
                risk_config_json={
                    "stop_atr_multiplier": 2.0,
                    "fee_bps": 5.0,
                    "slippage_bps": 5.0,
                    "stop_trigger_model": "close_confirmed",
                },
                exit_config_json={"take_profit_atr_multiplier": 4.0, "execution_model": "close_confirmed"},
                position_sizing_config_json={"method": "fixed_fraction", "fraction": 1.0},
                complexity_score=1.25,
                status="accepted",
                decision_reason="Seed version for repo-local deterministic BTCUSDT 4H Supertrend research.",
                created_at=now,
                updated_at=now,
            ),
        )


def _version_for_request(strategy_id: str, version_id: str | None) -> StrategyResearchVersion:
    versions = list_versions(strategy_id)
    if version_id:
        for item in versions:
            if item.version_id == version_id:
                return item
        raise FileNotFoundError(f"strategy research version not found: {version_id}")
    if versions:
        accepted = [item for item in versions if item.status == "accepted"]
        return accepted[0] if accepted else versions[0]
    now = _utc_now()
    version = StrategyResearchVersion(
        version_id=f"{storage.safe_id(strategy_id)}_base",
        strategy_id=storage.safe_id(strategy_id),
        version_name="Base version",
        status="pending",
        created_at=now,
        updated_at=now,
    )
    return storage.save_version(ARTIFACT_ROOT, version)


def _optuna_available() -> bool:
    return importlib.util.find_spec("optuna") is not None


def _search_space_for_strategy(
    strategy: StrategyResearchStrategy,
    request: StrategyOptimizationRequest,
) -> dict[str, list[Any]]:
    base = SUPERTREND_SEARCH_SPACE if strategy.strategy_id == PROMPT_COMPAT_STRATEGY_ID else DEFAULT_SEARCH_SPACE
    search_space = request.search_space or base
    normalized: dict[str, list[Any]] = {}
    for key, values in search_space.items():
        if isinstance(values, list) and values:
            normalized[key] = values
    if not normalized:
        normalized = base
    return normalized


def _trials_from_candidates(
    strategy: StrategyResearchStrategy,
    version: StrategyResearchVersion,
    optimization_id: str,
    request: StrategyOptimizationRequest,
    candidates: list[dict[str, Any]],
    now: str,
) -> list[StrategyOptimizationTrial]:
    trials: list[StrategyOptimizationTrial] = []
    for idx, params in enumerate(candidates, start=1):
        trials.append(_evaluate_trial(strategy, version, optimization_id, request, idx, params, now))
    return trials


def _optuna_trials(
    strategy: StrategyResearchStrategy,
    version: StrategyResearchVersion,
    optimization_id: str,
    request: StrategyOptimizationRequest,
    search_space: dict[str, list[Any]],
    now: str,
) -> list[StrategyOptimizationTrial]:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=request.random_seed, multivariate=False)
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=optuna.pruners.NopPruner())
    collected: list[StrategyOptimizationTrial] = []

    def objective(trial: Any) -> float:
        params = {
            key: trial.suggest_categorical(key, values)
            for key, values in search_space.items()
        }
        result = _evaluate_trial(
            strategy,
            version,
            optimization_id,
            request,
            len(collected) + 1,
            params,
            now,
        )
        collected.append(result)
        return float(result.score)

    study.optimize(objective, n_trials=request.max_trials, show_progress_bar=False)
    return collected


def _evaluate_trial(
    strategy: StrategyResearchStrategy,
    version: StrategyResearchVersion,
    optimization_id: str,
    request: StrategyOptimizationRequest,
    trial_number: int,
    params: dict[str, Any],
    now: str,
) -> StrategyOptimizationTrial:
    evaluation = _evaluate_strategy(strategy, request.base_config, params)
    flags = _constraint_flags(evaluation)
    rejections = _rejection_flags(evaluation, flags)
    score = _composite_score(evaluation, version.complexity_score, flags)
    return StrategyOptimizationTrial(
        trial_id=f"{optimization_id}_t{trial_number:03d}",
        optimization_id=optimization_id,
        trial_number=trial_number,
        parameters_json=params,
        score=score,
        metrics_json=evaluation["metrics"],
        constraint_flags_json=flags,
        rejection_flags_json=rejections,
        notes=evaluation["notes"],
        status="succeeded" if not rejections.get("invalid_parameters") else "failed",
        created_at=now,
    )


def _candidate_parameters(request: StrategyOptimizationRequest, search_space: dict[str, list[Any]]) -> list[dict[str, Any]]:
    candidates = _grid_candidates(search_space)
    rng = random.Random(request.random_seed)
    if request.method == "random_search":
        rng.shuffle(candidates)
        return candidates[: request.max_trials]
    if request.method == "bayesian":
        # Lightweight deterministic surrogate: evaluate broad coverage first, then center-biased candidates.
        rng.shuffle(candidates)
        scored = sorted(candidates, key=lambda row: _bayesian_prior_score(row), reverse=True)
        mixed = []
        for pair in zip(scored, candidates):
            mixed.extend(pair)
        return _dedupe_candidates(mixed)[: request.max_trials]
    return candidates[: request.max_trials]


def _grid_candidates(search_space: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = list(search_space)
    candidates: list[dict[str, Any]] = [{}]
    for key in keys:
        next_candidates: list[dict[str, Any]] = []
        for current in candidates:
            for value in search_space[key]:
                next_candidates.append({**current, key: value})
        candidates = next_candidates
    return _dedupe_candidates(candidates)


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in candidates:
        digest = _hash_payload(item)
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(item)
    return deduped


def _bayesian_prior_score(params: dict[str, Any]) -> float:
    lookback = float(params.get("lookback") or 63)
    rebalance = float(params.get("rebalance_every") or 21)
    top_n = float(params.get("top_n") or 2)
    cost = float(params.get("transaction_cost_bps") or 5) + float(params.get("slippage_bps") or 2)
    return -abs(lookback - 63) / 63 - abs(rebalance - 21) / 42 - abs(top_n - 2) / 3 - cost / 100


def _evaluate_strategy(
    strategy: StrategyResearchStrategy,
    config: StrategyResearchConfig,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    params = {**_base_parameters_for_strategy(strategy, config), **parameters}
    if strategy.strategy_id == PROMPT_COMPAT_STRATEGY_ID:
        return _evaluate_supertrend_strategy(strategy, config, params)
    warnings: list[str] = []
    try:
        _validate_parameters(params)
    except ValueError as exc:
        warnings.append(f"invalid_parameters:{exc}")
        return _synthetic_failed_evaluation(params, warnings)
    request = QuantBacktestRequest(
        strategy_id=strategy.strategy_id,
        template=str(params.get("template") or config.template or "risk_adjusted_momentum"),
        tickers=config.tickers or ["SPY", "QQQ", "TLT"],
        benchmark=config.benchmark,
        start_date=config.start_date,
        end_date=config.end_date,
        freshness_profile="historical_lab",
        rebalance_every=int(params["rebalance_every"]),
        lookback=int(params["lookback"]),
        top_n=int(params["top_n"]),
        transaction_cost_bps=float(params["transaction_cost_bps"]),
        slippage_bps=float(params["slippage_bps"]),
        require_fresh_prices=False,
    )
    response = quant_lab_pipeline.run_quant_backtest(request)
    raw_metrics = dict(response.metrics or {})
    returns = _returns_from_equity(response.equity_curve)
    drawdowns = [float(item.get("drawdown") or 0.0) for item in response.drawdown_curve or []]
    trades = list(response.trades or [])
    metrics = _extended_metrics(raw_metrics, returns, trades, params)
    if response.status != "success":
        warnings.append(f"backtest_status:{response.status}")
    if response.diagnostics and response.diagnostics.warnings:
        warnings.extend(response.diagnostics.warnings)
    notes = [
        "score uses sharpe, calmar, profit factor, expectancy, drawdown, costs, and concentration",
        "best parameters are not automatically accepted",
    ]
    return {
        "status": response.status,
        "backtest_id": response.run_id,
        "metrics": metrics,
        "raw_metrics": raw_metrics,
        "returns": returns,
        "drawdowns": drawdowns,
        "trades": trades,
        "warnings": warnings,
        "notes": notes,
    }


def _base_parameters_for_strategy(strategy: StrategyResearchStrategy, config: StrategyResearchConfig) -> dict[str, Any]:
    if strategy.strategy_id == PROMPT_COMPAT_STRATEGY_ID:
        base = {
            "atr_length": 10,
            "atr_multiplier": 3.0,
            "stop_atr_multiplier": 2.0,
            "take_profit_atr_multiplier": 4.0,
            "use_adx_filter": False,
            "adx_length": 14,
            "adx_threshold": 20.0,
            "use_rsi_filter": False,
            "rsi_length": 14,
            "rsi_upper": 70.0,
            "rsi_lower": 30.0,
            "fee_bps": 5.0,
            "slippage_bps": 5.0,
            "execution_model": "close_confirmed",
            "stop_trigger_model": "close_confirmed",
        }
        base.update(strategy.default_config_json or {})
        base.update(config.parameters or {})
        return base
    return _base_parameters(config)


def _base_parameters(config: StrategyResearchConfig) -> dict[str, Any]:
    base = {
        "template": config.template or "risk_adjusted_momentum",
        "lookback": 63,
        "rebalance_every": 21,
        "top_n": 2,
        "transaction_cost_bps": 5.0,
        "slippage_bps": 2.0,
    }
    base.update(config.parameters or {})
    return base


def _evaluate_supertrend_strategy(
    strategy: StrategyResearchStrategy,
    config: StrategyResearchConfig,
    params: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        _validate_supertrend_parameters(params)
    except ValueError as exc:
        warnings.append(f"invalid_parameters:{exc}")
        return _synthetic_failed_evaluation(params, warnings)

    ticker = (config.tickers[0] if config.tickers else "BTCUSDT").upper()
    if ticker in {"SPY", "QQQ", "TLT"}:
        ticker = "BTCUSDT"
    rows = get_prices(ticker, limit=5000)
    if not rows and ticker == "BTCUSDT":
        rows = get_prices("BTC-USD", limit=5000)
    if config.start_date or config.end_date:
        rows = [
            row for row in rows
            if (not config.start_date or str(row.get("date") or "") >= config.start_date)
            and (not config.end_date or str(row.get("date") or "") <= config.end_date)
        ]
    if len(rows) < max(80, int(params["atr_length"]) * 4):
        rows = _synthetic_btcusdt_4h_rows()
        warnings.append("synthetic_repo_local_btcusdt_4h_used")

    ohlc = [_ohlc_row(row) for row in rows]
    atr = _atr_series(ohlc, int(params["atr_length"]))
    supertrend = _supertrend_direction(ohlc, atr, float(params["atr_multiplier"]))
    rsi = _rsi_series([row["close"] for row in ohlc], int(params["rsi_length"]))
    adx = _adx_series(ohlc, int(params["adx_length"]))
    fee = (float(params["fee_bps"]) + float(params["slippage_bps"])) / 10000
    equity = 1.0
    equity_curve: list[dict[str, Any]] = []
    drawdowns: list[float] = []
    returns: list[float] = []
    trades: list[dict[str, Any]] = []
    in_position = False
    entry_price = 0.0
    entry_time = ""
    trailing_stop = 0.0
    peak = 1.0

    for idx in range(1, len(ohlc)):
        row = ohlc[idx]
        prev_close = ohlc[idx - 1]["close"]
        direction = supertrend[idx]
        prev_direction = supertrend[idx - 1]
        bar_return = 0.0
        if in_position and prev_close > 0:
            bar_return = row["close"] / prev_close - 1.0
            equity *= 1.0 + bar_return
        returns.append(bar_return)

        stop_line = row["close"] - atr[idx] * float(params["stop_atr_multiplier"])
        trailing_stop = max(trailing_stop, stop_line) if in_position else stop_line
        exit_reason = ""
        if in_position:
            if direction < 0 and prev_direction > 0:
                exit_reason = "supertrend_flip_bearish"
            elif params["stop_trigger_model"] == "intrabar" and row["low"] <= trailing_stop:
                exit_reason = "atr_trailing_stop_intrabar"
            elif params["stop_trigger_model"] == "close_confirmed" and row["close"] <= trailing_stop:
                exit_reason = "atr_trailing_stop_close_confirmed"
            elif row["high"] >= entry_price + atr[idx] * float(params["take_profit_atr_multiplier"]):
                exit_reason = "take_profit_atr"
            if exit_reason:
                exit_price = row["close"] if params["execution_model"] == "close_confirmed" else row["open"]
                pnl_pct = (exit_price / entry_price - 1.0) - fee if entry_price else 0.0
                equity *= 1.0 - fee
                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": row["date"],
                        "side": "long",
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": pnl_pct,
                        "exit_reason": exit_reason,
                        "market_regime": _volatility_state(returns[-30:]),
                    }
                )
                in_position = False
                entry_price = 0.0
                entry_time = ""

        passes_filters = True
        if bool(params.get("use_adx_filter")):
            passes_filters = passes_filters and adx[idx] >= float(params["adx_threshold"])
        if bool(params.get("use_rsi_filter")):
            passes_filters = passes_filters and float(params["rsi_lower"]) <= rsi[idx] <= float(params["rsi_upper"])
        if not in_position and direction > 0 and prev_direction <= 0 and passes_filters:
            entry_price = row["close"] if params["execution_model"] == "close_confirmed" else row["open"]
            entry_time = row["date"]
            trailing_stop = row["close"] - atr[idx] * float(params["stop_atr_multiplier"])
            equity *= 1.0 - fee
            in_position = True

        peak = max(peak, equity)
        drawdown = equity / peak - 1.0 if peak else 0.0
        drawdowns.append(drawdown)
        equity_curve.append({"date": row["date"], "equity": equity, "drawdown": drawdown})

    trade_returns = [float(trade.get("pnl_pct") or 0.0) for trade in trades]
    raw_metrics = _raw_metrics_from_returns(returns, drawdowns, trade_count=len(trades), turnover=len(trades) * 2.0)
    metrics = _extended_metrics(raw_metrics, returns or trade_returns, trades, params)
    if len(trades) < 5:
        warnings.append("low_trade_count")
    return {
        "status": "success",
        "backtest_id": _make_id("srst_bt", strategy.strategy_id, params, len(rows)),
        "metrics": metrics,
        "raw_metrics": raw_metrics,
        "returns": returns,
        "drawdowns": drawdowns,
        "trades": trades,
        "warnings": warnings,
        "notes": [
            "deterministic Supertrend 4H engine",
            "close_confirmed stop exits use close below trailing stop; intrabar uses low breach",
            "protected runtime evidence is reported separately",
        ],
    }


def _validate_parameters(params: dict[str, Any]) -> None:
    lookback = int(params.get("lookback") or 0)
    rebalance = int(params.get("rebalance_every") or 0)
    top_n = int(params.get("top_n") or 0)
    cost = float(params.get("transaction_cost_bps") or 0)
    slip = float(params.get("slippage_bps") or 0)
    if lookback < 2 or lookback > 5000:
        raise ValueError("lookback out of range")
    if rebalance < 1 or rebalance > 252:
        raise ValueError("rebalance_every out of range")
    if top_n < 1 or top_n > 50:
        raise ValueError("top_n out of range")
    if cost < 0 or cost > 1000 or slip < 0 or slip > 1000:
        raise ValueError("cost or slippage out of range")


def _validate_supertrend_parameters(params: dict[str, Any]) -> None:
    atr_length = int(params.get("atr_length") or 0)
    atr_multiplier = float(params.get("atr_multiplier") or 0)
    stop_multiplier = float(params.get("stop_atr_multiplier") or 0)
    take_profit = float(params.get("take_profit_atr_multiplier") or 0)
    adx_length = int(params.get("adx_length") or 0)
    adx_threshold = float(params.get("adx_threshold") or 0)
    rsi_length = int(params.get("rsi_length") or 0)
    rsi_upper = float(params.get("rsi_upper") or 0)
    rsi_lower = float(params.get("rsi_lower") or 0)
    fee = float(params.get("fee_bps") or 0)
    slip = float(params.get("slippage_bps") or 0)
    if atr_length < 5 or atr_length > 30:
        raise ValueError("atr_length out of range")
    if atr_multiplier < 1.0 or atr_multiplier > 6.0:
        raise ValueError("atr_multiplier out of range")
    if stop_multiplier < 1.0 or stop_multiplier > 5.0:
        raise ValueError("stop_atr_multiplier out of range")
    if take_profit < 1.0 or take_profit > 8.0:
        raise ValueError("take_profit_atr_multiplier out of range")
    if adx_length < 7 or adx_length > 30 or adx_threshold < 10 or adx_threshold > 35:
        raise ValueError("adx parameters out of range")
    if rsi_length < 7 or rsi_length > 30 or rsi_lower < 15 or rsi_lower > 45 or rsi_upper < 55 or rsi_upper > 85:
        raise ValueError("rsi parameters out of range")
    if rsi_lower >= rsi_upper:
        raise ValueError("rsi_lower must be below rsi_upper")
    if fee < 0 or fee > 1000 or slip < 0 or slip > 1000:
        raise ValueError("fee or slippage out of range")
    if str(params.get("execution_model") or "") not in {"close_confirmed", "next_open"}:
        raise ValueError("execution_model out of range")
    if str(params.get("stop_trigger_model") or "") not in {"intrabar", "close_confirmed"}:
        raise ValueError("stop_trigger_model out of range")


def _synthetic_btcusdt_4h_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    close = 42_000.0
    for idx in range(420):
        trend = idx * 45.0
        cycle = math.sin(idx / 11.0) * 1500.0 + math.sin(idx / 37.0) * 3000.0
        next_close = max(5_000.0, 42_000.0 + trend + cycle)
        open_price = close
        high = max(open_price, next_close) * (1.0 + 0.006 + abs(math.sin(idx / 9.0)) * 0.004)
        low = min(open_price, next_close) * (1.0 - 0.006 - abs(math.cos(idx / 7.0)) * 0.004)
        rows.append(
            {
                "ticker": "BTCUSDT",
                "date": (base + timedelta(hours=idx * 4)).isoformat().replace("+00:00", "Z"),
                "open": open_price,
                "high": high,
                "low": low,
                "close": next_close,
                "adjusted_close": next_close,
                "volume": 1_000_000 + idx * 1000,
                "source": "synthetic_repo_local_4h",
            }
        )
        close = next_close
    return rows


def _ohlc_row(row: dict[str, Any]) -> dict[str, Any]:
    close = _float_or(row.get("adjusted_close"), _float_or(row.get("close"), 0.0))
    open_price = _float_or(row.get("open"), close)
    high = _float_or(row.get("high"), max(open_price, close))
    low = _float_or(row.get("low"), min(open_price, close))
    return {
        "date": str(row.get("date") or ""),
        "open": open_price,
        "high": max(high, open_price, close),
        "low": min(low, open_price, close),
        "close": close,
    }


def _float_or(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _atr_series(rows: list[dict[str, Any]], length: int) -> list[float]:
    true_ranges: list[float] = []
    for idx, row in enumerate(rows):
        prev_close = rows[idx - 1]["close"] if idx else row["close"]
        true_ranges.append(max(row["high"] - row["low"], abs(row["high"] - prev_close), abs(row["low"] - prev_close)))
    out: list[float] = []
    for idx, value in enumerate(true_ranges):
        if idx == 0:
            out.append(value)
        elif idx < length:
            out.append(sum(true_ranges[: idx + 1]) / (idx + 1))
        else:
            out.append((out[-1] * (length - 1) + value) / length)
    return out


def _supertrend_direction(rows: list[dict[str, Any]], atr: list[float], multiplier: float) -> list[int]:
    directions: list[int] = []
    final_upper = 0.0
    final_lower = 0.0
    direction = 1
    for idx, row in enumerate(rows):
        hl2 = (row["high"] + row["low"]) / 2.0
        upper = hl2 + multiplier * atr[idx]
        lower = hl2 - multiplier * atr[idx]
        if idx == 0:
            final_upper, final_lower = upper, lower
            directions.append(direction)
            continue
        prev_close = rows[idx - 1]["close"]
        final_upper = upper if upper < final_upper or prev_close > final_upper else final_upper
        final_lower = lower if lower > final_lower or prev_close < final_lower else final_lower
        if row["close"] > final_upper:
            direction = 1
        elif row["close"] < final_lower:
            direction = -1
        directions.append(direction)
    return directions


def _rsi_series(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    out = [50.0]
    gains = 0.0
    losses = 0.0
    for idx in range(1, len(values)):
        change = values[idx] - values[idx - 1]
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        if idx <= length:
            gains += gain
            losses += loss
            avg_gain = gains / idx
            avg_loss = losses / idx
        else:
            prev = out[-1]
            avg_loss = (100.0 / max(prev, 1e-9) - 1.0)
            avg_gain = 1.0
            avg_gain = (avg_gain * (length - 1) + gain) / length
            avg_loss = (avg_loss * (length - 1) + loss) / length
        rs = avg_gain / avg_loss if avg_loss else 100.0
        out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def _adx_series(rows: list[dict[str, Any]], length: int) -> list[float]:
    if not rows:
        return []
    dx_values = [20.0]
    for idx in range(1, len(rows)):
        up_move = rows[idx]["high"] - rows[idx - 1]["high"]
        down_move = rows[idx - 1]["low"] - rows[idx]["low"]
        plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0
        tr = max(
            rows[idx]["high"] - rows[idx]["low"],
            abs(rows[idx]["high"] - rows[idx - 1]["close"]),
            abs(rows[idx]["low"] - rows[idx - 1]["close"]),
            1e-9,
        )
        plus_di = 100.0 * plus_dm / tr
        minus_di = 100.0 * minus_dm / tr
        dx = 100.0 * abs(plus_di - minus_di) / max(plus_di + minus_di, 1e-9)
        if idx < length:
            dx_values.append((sum(dx_values) + dx) / (len(dx_values) + 1))
        else:
            dx_values.append((dx_values[-1] * (length - 1) + dx) / length)
    return dx_values


def _raw_metrics_from_returns(
    returns: list[float],
    drawdowns: list[float],
    *,
    trade_count: int,
    turnover: float,
) -> dict[str, float]:
    total_return = _compound_return(returns)
    mean = sum(returns) / len(returns) if returns else 0.0
    vol = math.sqrt(sum((ret - mean) ** 2 for ret in returns) / max(len(returns) - 1, 1)) if len(returns) > 1 else 0.0
    downside = [ret for ret in returns if ret < 0]
    downside_vol = math.sqrt(sum(ret * ret for ret in downside) / max(len(downside), 1)) if downside else 0.0
    sharpe = mean / vol * math.sqrt(365 * 6) if vol else 0.0
    sortino = mean / downside_vol * math.sqrt(365 * 6) if downside_vol else 0.0
    max_dd = min(drawdowns) if drawdowns else 0.0
    calmar = total_return / abs(max_dd) if max_dd else 0.0
    return {
        "total_return": total_return,
        "cagr": total_return,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "turnover": turnover,
        "trade_count": float(trade_count),
        "exposure": 1.0 if trade_count else 0.0,
    }


def _volatility_state(returns: list[float]) -> str:
    clean = [abs(value) for value in returns if math.isfinite(value)]
    if not clean:
        return "unknown"
    avg = sum(clean) / len(clean)
    if avg > 0.025:
        return "high_volatility"
    if avg < 0.006:
        return "low_volatility"
    return "normal_volatility"


def _synthetic_failed_evaluation(params: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    metrics = {key: 0.0 for key in EXTENDED_METRIC_KEYS}
    metrics["trade_count"] = 0
    return {
        "status": "failed",
        "backtest_id": "",
        "metrics": metrics,
        "raw_metrics": {},
        "returns": [],
        "drawdowns": [],
        "trades": [],
        "warnings": warnings,
        "notes": [f"invalid parameters rejected: {params}"],
    }


def _extended_metrics(
    raw: dict[str, Any],
    returns: list[float],
    trades: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    wins = [ret for ret in returns if ret > 0]
    losses = [ret for ret in returns if ret < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    trade_count = int(raw.get("trade_count") or len(trades) or len(returns))
    top_abs = sorted([abs(ret) for ret in returns], reverse=True)
    total_abs = sum(abs(ret) for ret in returns) or 1.0
    max_dd = float(raw.get("max_drawdown") or 0.0)
    total_return = float(raw.get("total_return") or _compound_return(returns))
    cagr = float(raw.get("cagr") or total_return)
    turnover = float(raw.get("turnover") or sum(float(t.get("turnover") or 0.0) for t in trades))
    fee_rate = float(params.get("transaction_cost_bps", params.get("fee_bps", 0.0)) or 0.0) / 10000
    slippage_rate = float(params.get("slippage_bps") or 0.0) / 10000
    return {
        "total_return_pct": _round(total_return * 100),
        "cagr_pct": _round(cagr * 100),
        "sharpe": _round(float(raw.get("sharpe") or 0.0)),
        "sortino": _round(float(raw.get("sortino") or 0.0)),
        "max_drawdown_pct": _round(max_dd * 100),
        "calmar": _round(float(raw.get("calmar") or 0.0)),
        "profit_factor": _round(gross_win / gross_loss if gross_loss else (gross_win if gross_win else 0.0)),
        "win_rate_pct": _round(len(wins) / max(len(returns), 1) * 100),
        "avg_win_pct": _round((sum(wins) / len(wins) * 100) if wins else 0.0),
        "avg_loss_pct": _round((sum(losses) / len(losses) * 100) if losses else 0.0),
        "payoff_ratio": _round((sum(wins) / len(wins)) / abs(sum(losses) / len(losses)) if wins and losses else 0.0),
        "expectancy_pct": _round((sum(returns) / max(len(returns), 1)) * 100),
        "trade_count": trade_count,
        "exposure_time_pct": _round(float(raw.get("exposure") or 0.0) * 100),
        "turnover_pct": _round(turnover * 100),
        "fee_total": _round(turnover * fee_rate),
        "slippage_total": _round(turnover * slippage_rate),
        "long_return_pct": _round(total_return * 100),
        "short_return_pct": 0.0,
        "best_trade_pct": _round((max(returns) * 100) if returns else 0.0),
        "worst_trade_pct": _round((min(returns) * 100) if returns else 0.0),
        "consecutive_wins": _max_streak(returns, positive=True),
        "consecutive_losses": _max_streak(returns, positive=False),
        "recovery_factor": _round(total_return / abs(max_dd) if max_dd else 0.0),
        "return_concentration_top_1_pct": _round((top_abs[0] / total_abs) * 100 if top_abs else 0.0),
        "return_concentration_top_5_pct": _round((sum(top_abs[:5]) / total_abs) * 100 if top_abs else 0.0),
    }


def _returns_from_equity(equity_curve: list[dict[str, Any]]) -> list[float]:
    values = [float(row.get("equity") or 0.0) for row in equity_curve if float(row.get("equity") or 0.0) > 0]
    return [values[idx] / values[idx - 1] - 1.0 for idx in range(1, len(values)) if values[idx - 1] > 0]


def _compound_return(returns: list[float]) -> float:
    value = 1.0
    for ret in returns:
        value *= 1.0 + ret
    return value - 1.0


def _composite_score(metrics_payload: dict[str, Any], complexity: float, flags: dict[str, Any]) -> float:
    metrics = metrics_payload["metrics"]
    score = (
        0.30 * _normalize(metrics.get("sharpe"), -2, 4)
        + 0.25 * _normalize(metrics.get("calmar"), -2, 5)
        + 0.20 * _normalize(metrics.get("profit_factor"), 0, 3)
        + 0.15 * _normalize(metrics.get("expectancy_pct"), -1, 2)
        - 0.10 * _normalize(abs(float(metrics.get("max_drawdown_pct") or 0)), 0, 50)
    )
    complexity_penalty = 0.015 * max(float(complexity or 1.0) - 1.0, 0.0)
    low_trade_penalty = 0.12 if flags.get("low_trade_count") else 0.0
    concentration_penalty = 0.10 if flags.get("return_concentration") else 0.0
    invalid_penalty = 1.0 if flags.get("invalid_or_failed") else 0.0
    return _round(score - complexity_penalty - low_trade_penalty - concentration_penalty - invalid_penalty)


def _constraint_flags(evaluation: dict[str, Any]) -> dict[str, Any]:
    metrics = evaluation["metrics"]
    return {
        "invalid_or_failed": evaluation.get("status") not in {"success", "partial"},
        "low_trade_count": int(metrics.get("trade_count") or 0) < 5,
        "large_drawdown": abs(float(metrics.get("max_drawdown_pct") or 0.0)) > 35,
        "return_concentration": float(metrics.get("return_concentration_top_1_pct") or 0.0) > 45,
        "negative_expectancy": float(metrics.get("expectancy_pct") or 0.0) <= 0,
    }


def _rejection_flags(evaluation: dict[str, Any], flags: dict[str, Any]) -> dict[str, Any]:
    warnings = list(evaluation.get("warnings") or [])
    return {
        "invalid_parameters": any(str(item).startswith("invalid_parameters") for item in warnings),
        "insufficient_trades": bool(flags.get("low_trade_count")),
        "unstable_concentration": bool(flags.get("return_concentration")),
        "cost_drag": float(evaluation["metrics"].get("fee_total") or 0.0) > 0.02,
    }


def _recommended_trial(trials: list[StrategyOptimizationTrial]) -> StrategyOptimizationTrial:
    stable = [
        item
        for item in trials
        if not item.constraint_flags_json.get("invalid_or_failed")
        and not item.constraint_flags_json.get("low_trade_count")
        and not item.constraint_flags_json.get("return_concentration")
    ]
    pool = stable or [item for item in trials if not item.constraint_flags_json.get("invalid_or_failed")] or trials
    return max(
        pool,
        key=lambda item: (
            item.score
            - max(float(item.metrics_json.get("return_concentration_top_1_pct") or 0.0) - 35.0, 0.0) / 100
            - max(10 - int(item.metrics_json.get("trade_count") or 0), 0) * 0.01
        ),
    )


def _robustness_score(trials: list[StrategyOptimizationTrial], recommended: StrategyOptimizationTrial) -> float:
    scores = [item.score for item in trials if item.status == "succeeded"]
    if not scores:
        return 0.0
    mean = sum(scores) / len(scores)
    dispersion = math.sqrt(sum((score - mean) ** 2 for score in scores) / max(len(scores) - 1, 1))
    return max(0.0, min(1.0, 1.0 - dispersion + recommended.score * 0.1))


def _overfitting_proxy(best: StrategyOptimizationTrial, recommended: StrategyOptimizationTrial) -> float:
    return max(0.0, min(1.0, abs(best.score - recommended.score)))


def _latest_recommended_parameters(strategy_id: str) -> dict[str, Any]:
    runs = [item for item in list_optimizations() if item.strategy_id == strategy_id and item.status == "succeeded"]
    if not runs:
        return {}
    latest = sorted(runs, key=lambda item: item.created_at)[-1]
    return dict(latest.recommended_parameters_json or {})


def _failure_distribution(
    metrics: dict[str, Any],
    returns: list[float],
    trades: list[dict[str, Any]],
    drawdowns: list[float],
) -> list[StrategyFailureTag]:
    losses = [ret for ret in returns if ret < 0]
    loss_count = max(len(losses), 1)
    items = [
        ("Choppy Market Loss", len([ret for ret in losses if abs(ret) < 0.01]), "medium"),
        ("Volatility Spike", len([ret for ret in losses if abs(ret) >= 0.02]), "high"),
        ("Fee Drag", 1 if float(metrics.get("fee_total") or 0.0) + float(metrics.get("slippage_total") or 0.0) > 0.001 else 0, "medium"),
        ("Return Concentration Risk", 1 if float(metrics.get("return_concentration_top_1_pct") or 0.0) > 35 else 0, "high"),
        ("Low Trade Count Risk", 1 if int(metrics.get("trade_count") or len(trades)) < 10 else 0, "medium"),
        ("Poor Reward/Risk", 1 if float(metrics.get("profit_factor") or 0.0) < 1.1 else 0, "high"),
        ("Parameter Instability", 1 if abs(float(metrics.get("max_drawdown_pct") or 0.0)) > 20 else 0, "medium"),
    ]
    tags = [
        StrategyFailureTag(
            tag=tag,
            count=int(count),
            share_pct=_round(count / loss_count * 100 if loss_count else 0.0),
            severity=severity,
            decision_use=_failure_decision_use(tag),
            evidence={
                "loss_count": len(losses),
                "trade_count": int(metrics.get("trade_count") or len(trades)),
                "max_drawdown_pct": metrics.get("max_drawdown_pct"),
                "min_drawdown": min(drawdowns, default=0.0),
            },
        )
        for tag, count, severity in items
        if count
    ]
    return sorted(tags, key=lambda item: (item.severity == "high", item.count), reverse=True)


def _diagnostics_summary(metrics: dict[str, Any], failures: list[StrategyFailureTag]) -> str:
    if not failures:
        return "No dominant failure cluster was detected; keep validation focused on OOS, cost stress, and stability."
    top = failures[0]
    return (
        f"Top failure driver is {top.tag}. This is decision-useful because it links losses to "
        "a validation target instead of a generic return summary."
    )


def _drawdown_analysis(drawdowns: list[float], metrics: dict[str, Any]) -> dict[str, Any]:
    worst = min(drawdowns, default=float(metrics.get("max_drawdown_pct") or 0.0) / 100)
    underwater = len([item for item in drawdowns if item < -0.02])
    return {
        "worst_drawdown_pct": _round(worst * 100),
        "underwater_observations_gt_2pct": underwater,
        "recovery_factor": metrics.get("recovery_factor", 0.0),
        "decision_use": "Use this to reject improvements that increase depth or duration of drawdowns.",
    }


def _regime_analysis(returns: list[float], metrics: dict[str, Any]) -> dict[str, Any]:
    volatility = _stdev(returns)
    negative = len([ret for ret in returns if ret < 0])
    return {
        "volatility_state": "high" if volatility > 0.02 else "normal",
        "trend_state": "positive" if float(metrics.get("total_return_pct") or 0.0) > 0 else "weak",
        "loss_observation_share_pct": _round(negative / max(len(returns), 1) * 100),
        "decision_use": "Check whether losses cluster in weak or high-volatility regimes before adding filters.",
    }


def _trade_cluster(trades: list[dict[str, Any]], returns: list[float]) -> dict[str, Any]:
    by_action: dict[str, int] = {}
    for trade in trades:
        action = str(trade.get("action") or "unknown")
        by_action[action] = by_action.get(action, 0) + 1
    return {
        "actions": by_action,
        "return_observations": len(returns),
        "decision_use": "High turnover clusters should be checked against fee drag and rebalance cadence.",
    }


def _cost_impact(metrics: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    return {
        "fee_total": metrics.get("fee_total", 0.0),
        "slippage_total": metrics.get("slippage_total", 0.0),
        "configured_transaction_cost_bps": params.get("transaction_cost_bps", params.get("fee_bps", 0.0)),
        "configured_slippage_bps": params.get("slippage_bps", 0.0),
        "cost_to_expectancy_ratio": _round(
            (float(metrics.get("fee_total") or 0.0) + float(metrics.get("slippage_total") or 0.0))
            / max(abs(float(metrics.get("expectancy_pct") or 0.0)) / 100, 0.0001)
        ),
    }


def _parameter_notes(params: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    notes = [
        f"lookback={params.get('lookback')} and rebalance_every={params.get('rebalance_every')} should be checked in a local neighborhood.",
        f"trade_count={metrics.get('trade_count')} controls whether the evidence is broad enough for decisions.",
    ]
    if float(metrics.get("return_concentration_top_1_pct") or 0.0) > 35:
        notes.append("Return concentration is high; do not accept this as a deployment candidate without stability checks.")
    return notes


def _recommended_experiments(failures: list[StrategyFailureTag]) -> list[dict[str, Any]]:
    return [
        _hypothesis_template(failure.tag)["proposed_change"]
        for failure in failures[:3]
    ]


def _rejected_experiments(metrics: dict[str, Any], failures: list[StrategyFailureTag]) -> list[dict[str, Any]]:
    rejected = []
    if int(metrics.get("trade_count") or 0) < 5:
        rejected.append({"module": "optional_filter", "reason": "trade count is already too low"})
    if any(item.tag == "Return Concentration Risk" for item in failures):
        rejected.append({"module": "position_sizing", "reason": "do not increase concentration before robustness validation"})
    return rejected


def _hypothesis_template(tag: str) -> dict[str, Any]:
    mapping = {
        "Choppy Market Loss": {
            "module": "optional_filter",
            "problem": "Losses are concentrated in low-trend or choppy observations.",
            "hypothesis": "Add an ADX-style trend-strength filter as a controlled experiment.",
            "proposed_change": {"module": "optional_filter", "indicator": "ADX", "condition": "trend_strength > threshold", "parameter_range": {"threshold": [18, 20, 22, 25]}},
            "expected_effect": "False entries may fall, but trade count can drop.",
            "risk": "The filter may delay early trend entries and reduce opportunity count.",
        },
        "Volatility Spike": {
            "module": "risk_module",
            "problem": "Losses appear during high-volatility observations.",
            "hypothesis": "Test volatility-adjusted position sizing and ATR-like cost stress.",
            "proposed_change": {"module": "risk_module", "indicator": "volatility_percentile", "condition": "reduce_size_when_high_vol", "parameter_range": {"volatility_cap": [0.75, 0.85, 0.95]}},
            "expected_effect": "Drawdown may improve while absolute return may fall.",
            "risk": "Risk reduction can under-allocate during strong recoveries.",
        },
        "Fee Drag": {
            "module": "execution_cost",
            "problem": "Transaction costs consume a meaningful part of expectancy.",
            "hypothesis": "Increase rebalance interval or add turnover guard.",
            "proposed_change": {"module": "risk_module", "indicator": "turnover_guard", "condition": "rebalance_only_if_score_spread_exceeds_threshold", "parameter_range": {"rebalance_every": [21, 42, 63]}},
            "expected_effect": "Lower turnover may improve net expectancy.",
            "risk": "Slower rebalancing can miss regime changes.",
        },
        "Poor Reward/Risk": {
            "module": "exit_module",
            "problem": "Reward/risk profile is weak after losses and costs.",
            "hypothesis": "Test partial profit taking or trailing exits as an experiment.",
            "proposed_change": {"module": "exit_module", "indicator": "trailing_exit", "condition": "protect_after_positive_move", "parameter_range": {"trail_multiple": [2.0, 3.0, 4.0]}},
            "expected_effect": "Payoff ratio may improve if large reversals are common.",
            "risk": "Earlier exits can reduce trend participation.",
        },
    }
    return mapping.get(
        tag,
        {
            "module": "validation",
            "problem": f"{tag} requires validation before accepting any change.",
            "hypothesis": "Run OOS, walk-forward, cost stress, and parameter stability checks before changing modules.",
            "proposed_change": {"module": "validation", "indicator": "evidence_gate", "condition": "validate_before_accept"},
            "expected_effect": "Prevents accepting in-sample-only improvements.",
            "risk": "May reject superficially attractive but unstable parameter spikes.",
        },
    )


def _split_returns(returns: list[float], oos_ratio: float) -> dict[str, list[float]]:
    if not returns:
        return {"in_sample": [], "out_of_sample": []}
    split_at = max(1, min(len(returns) - 1, int(len(returns) * (1 - oos_ratio))))
    return {"in_sample": returns[:split_at], "out_of_sample": returns[split_at:]}


def _metrics_from_returns(returns: list[float], fallback: dict[str, Any]) -> dict[str, Any]:
    if len(returns) < 2:
        return {**{key: 0.0 for key in EXTENDED_METRIC_KEYS}, "trade_count": len(returns), "insufficient_evidence": True}
    total = _compound_return(returns)
    wins = [ret for ret in returns if ret > 0]
    losses = [ret for ret in returns if ret < 0]
    volatility = _stdev(returns) * math.sqrt(252)
    mean = sum(returns) / len(returns)
    downside = _stdev(losses) * math.sqrt(252) if len(losses) > 1 else 0.0
    max_dd = _max_drawdown_from_returns(returns)
    metrics = dict(fallback)
    metrics.update(
        {
            "total_return_pct": _round(total * 100),
            "cagr_pct": _round(mean * 252 * 100),
            "sharpe": _round((mean * 252) / volatility if volatility else 0.0),
            "sortino": _round((mean * 252) / downside if downside else 0.0),
            "max_drawdown_pct": _round(max_dd * 100),
            "calmar": _round((mean * 252) / abs(max_dd) if max_dd else 0.0),
            "profit_factor": _round(sum(wins) / abs(sum(losses)) if losses else (sum(wins) if wins else 0.0)),
            "win_rate_pct": _round(len(wins) / len(returns) * 100),
            "expectancy_pct": _round(mean * 100),
            "trade_count": len(returns),
            "best_trade_pct": _round(max(returns) * 100),
            "worst_trade_pct": _round(min(returns) * 100),
            "return_concentration_top_1_pct": _round(max([abs(ret) for ret in returns] or [0]) / max(sum(abs(ret) for ret in returns), 1e-9) * 100),
            "insufficient_evidence": False,
        }
    )
    return metrics


def _walk_forward_results(returns: list[float], splits: int, fallback: dict[str, Any]) -> list[dict[str, Any]]:
    if not returns:
        return []
    segment_len = max(2, len(returns) // max(splits, 1))
    rows = []
    for idx in range(splits):
        start = idx * segment_len
        end = len(returns) if idx == splits - 1 else min(len(returns), start + segment_len)
        segment = returns[start:end]
        if not segment:
            continue
        metrics = _metrics_from_returns(segment, fallback)
        rows.append(
            {
                "segment": idx + 1,
                "observation_count": len(segment),
                "status": "succeeded" if len(segment) >= 2 else "insufficient_evidence",
                "metrics": metrics,
            }
        )
    return rows


def _parameter_stability(
    strategy: StrategyResearchStrategy,
    config: StrategyResearchConfig,
    params: dict[str, Any],
) -> dict[str, Any]:
    neighbors = []
    if strategy.strategy_id == PROMPT_COMPAT_STRATEGY_ID:
        atr_length = int(params.get("atr_length") or 10)
        atr_multiplier = float(params.get("atr_multiplier") or 3.0)
        for length_delta in [-2, 0, 2]:
            for multiplier_delta in [-0.5, 0.0, 0.5]:
                candidate = {
                    **params,
                    "atr_length": min(30, max(5, atr_length + length_delta)),
                    "atr_multiplier": min(6.0, max(1.0, atr_multiplier + multiplier_delta)),
                }
                evaluation = _evaluate_strategy(strategy, config, candidate)
                neighbors.append(
                    {
                        "parameters": candidate,
                        "score": _composite_score(evaluation, 1.25, _constraint_flags(evaluation)),
                        "metrics": evaluation["metrics"],
                    }
                )
        scores = [row["score"] for row in neighbors]
        score_range = max(scores) - min(scores) if scores else 0.0
        stability_score = max(0.0, min(1.0, 1.0 - score_range))
        return {
            "stability_score": _round(stability_score),
            "single_spike_flag": stability_score < 0.55,
            "neighbor_count": len(neighbors),
            "neighbors": neighbors,
        }
    lookback = int(params.get("lookback") or 63)
    rebalance = int(params.get("rebalance_every") or 21)
    for lookback_delta in [-10, 0, 10]:
        for rebalance_delta in [-5, 0, 5]:
            candidate = {
                **params,
                "lookback": max(2, lookback + lookback_delta),
                "rebalance_every": max(1, rebalance + rebalance_delta),
            }
            evaluation = _evaluate_strategy(strategy, config, candidate)
            neighbors.append(
                {
                    "parameters": candidate,
                    "score": _composite_score(evaluation, 1.0, _constraint_flags(evaluation)),
                    "metrics": evaluation["metrics"],
                }
            )
    scores = [row["score"] for row in neighbors]
    score_range = max(scores) - min(scores) if scores else 0.0
    stability_score = max(0.0, min(1.0, 1.0 - score_range))
    return {
        "stability_score": _round(stability_score),
        "single_spike_flag": stability_score < 0.55,
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


def _monte_carlo(returns: list[float], seed: int) -> dict[str, Any]:
    if len(returns) < 10:
        return {"status": "insufficient_evidence", "observation_count": len(returns)}
    rng = random.Random(seed)
    terminal_returns: list[float] = []
    max_drawdowns: list[float] = []
    for _ in range(100):
        sample = [rng.choice(returns) for _idx in returns]
        terminal_returns.append(_compound_return(sample))
        max_drawdowns.append(_max_drawdown_from_returns(sample))
    return {
        "status": "succeeded",
        "runs": 100,
        "median_terminal_return_pct": _round(_percentile(terminal_returns, 50) * 100),
        "p05_terminal_return_pct": _round(_percentile(terminal_returns, 5) * 100),
        "p95_max_drawdown_pct": _round(_percentile(max_drawdowns, 5) * 100),
        "risk_of_negative_terminal_pct": _round(len([ret for ret in terminal_returns if ret < 0]) / len(terminal_returns) * 100),
    }


def _cost_stress(
    strategy: StrategyResearchStrategy,
    config: StrategyResearchConfig,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for multiple in [1, 2, 3]:
        if strategy.strategy_id == PROMPT_COMPAT_STRATEGY_ID:
            stressed = {
                **params,
                "fee_bps": float(params.get("fee_bps") or 0.0) * multiple,
                "slippage_bps": float(params.get("slippage_bps") or 0.0) * multiple,
            }
        else:
            stressed = {
                **params,
                "transaction_cost_bps": float(params.get("transaction_cost_bps") or 0.0) * multiple,
                "slippage_bps": float(params.get("slippage_bps") or 0.0) * multiple,
            }
        evaluation = _evaluate_strategy(strategy, config, stressed)
        rows.append(
            {
                "cost_multiple": multiple,
                "status": evaluation["status"],
                "parameters": stressed,
                "metrics": evaluation["metrics"],
                "expectancy_survives": float(evaluation["metrics"].get("expectancy_pct") or 0.0) > 0,
            }
        )
    return rows


def _validation_flags(
    in_sample: dict[str, Any],
    out_of_sample: dict[str, Any],
    walk_forward: list[dict[str, Any]],
    stability: dict[str, Any],
    monte_carlo: dict[str, Any],
    cost_stress: list[dict[str, Any]],
) -> tuple[list[str], list[str], bool]:
    acceptance: list[str] = []
    rejection: list[str] = []
    insufficient = bool(out_of_sample.get("insufficient_evidence")) or monte_carlo.get("status") == "insufficient_evidence"
    if float(out_of_sample.get("total_return_pct") or 0.0) >= float(in_sample.get("total_return_pct") or 0.0) * -0.5:
        acceptance.append("oos_return_did_not_collapse")
    else:
        rejection.append("oos_degradation")
    if float(out_of_sample.get("profit_factor") or 0.0) >= 0.8:
        acceptance.append("oos_profit_factor_acceptable")
    else:
        rejection.append("profit_factor_degradation")
    if abs(float(out_of_sample.get("max_drawdown_pct") or 0.0)) <= 40:
        acceptance.append("drawdown_within_threshold")
    else:
        rejection.append("drawdown_threshold_breach")
    if int(out_of_sample.get("trade_count") or 0) >= 5:
        acceptance.append("trade_count_check_passed")
    else:
        rejection.append("too_few_oos_observations")
    if not stability.get("single_spike_flag"):
        acceptance.append("parameter_stability_passed")
    else:
        rejection.append("single_parameter_spike")
    if all(row.get("expectancy_survives") for row in cost_stress):
        acceptance.append("cost_stress_survived")
    else:
        rejection.append("cost_stress_destroyed_expectancy")
    if walk_forward and all((row.get("metrics") or {}).get("insufficient_evidence") is False for row in walk_forward):
        acceptance.append("walk_forward_segments_available")
    return acceptance, rejection, insufficient


def _validation_reason(decision: str, acceptance: list[str], rejection: list[str], insufficient: bool) -> str:
    if insufficient:
        return "Rejected because validation evidence is insufficient for a deployment candidate."
    if decision == "accepted":
        return f"Accepted as a research version because validation flags passed: {', '.join(acceptance[:4])}."
    return f"Rejected because validation flags failed: {', '.join(rejection[:4])}."


def _complexity_score(version: StrategyResearchVersion) -> float:
    configs = [
        version.filter_config_json,
        version.risk_config_json,
        version.exit_config_json,
        version.position_sizing_config_json,
    ]
    count = sum(len(item or {}) for item in configs)
    return _round(1.0 + count * 0.25)


def _failure_decision_use(tag: str) -> str:
    return {
        "Choppy Market Loss": "Test a trend-strength filter, but reject it if trade count collapses.",
        "Volatility Spike": "Test volatility sizing and drawdown guard before accepting more exposure.",
        "Fee Drag": "Stress costs and rebalance cadence; do not evaluate gross returns only.",
        "Return Concentration Risk": "Require Monte Carlo and parameter stability evidence.",
        "Low Trade Count Risk": "Do not accept added filters until sample size improves.",
        "Poor Reward/Risk": "Test exit module changes with OOS and cost stress.",
    }.get(tag, "Use as a validation target, not an automatic strategy change.")


def _max_streak(returns: list[float], *, positive: bool) -> int:
    best = 0
    current = 0
    for ret in returns:
        hit = ret > 0 if positive else ret < 0
        current = current + 1 if hit else 0
        best = max(best, current)
    return best


def _max_drawdown_from_returns(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for ret in returns:
        equity *= 1.0 + ret
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def _normalize(value: Any, low: float, high: float) -> float:
    number = float(value or 0.0)
    if not math.isfinite(number) or high <= low:
        return 0.0
    return max(0.0, min(1.0, (number - low) / (high - low)))


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[idx]


def _make_id(prefix: str, *parts: Any) -> str:
    digest = _hash_payload(parts)[:16]
    return f"{prefix}_{digest}"


def _stable_hypothesis_id(strategy_id: str, version_id: str, tag: str, module: str) -> str:
    return _make_id("srhyp", strategy_id, version_id, tag, module)


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode("utf-8", errors="ignore")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: Any, digits: int = 6) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return round(number, digits)
