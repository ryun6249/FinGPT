from __future__ import annotations

from core.schemas.quant import QuantModelProfile
from pipelines.model_profiles.storage import delete_model_profile, load_model_profile, save_model_profile, validate_model_profile
from pipelines.orchestration.quant_model_lab import compile_forecast_request, compile_universe_request
from pipelines.strategies.registry import get_strategy, list_strategies
from pipelines.strategies.storage import delete_strategy, load_strategy, migrate_strategy, save_strategy, validate_strategy


def test_default_strategy_registry_contains_no_lookahead_policy() -> None:
    strategies = list_strategies()

    assert get_strategy("momentum_ranking_v1") is not None
    assert all(item["execution"]["trade_at"] == "next_bar_close" for item in strategies)


def test_strategy_storage_roundtrip(tmp_path) -> None:
    strategy = {"strategy_id": "custom_test_v1", "name": "Custom", "execution": {"trade_at": "next_bar_close"}}

    path = save_strategy(strategy, tmp_path)
    loaded = load_strategy("custom_test_v1", tmp_path)
    assert path.exists()
    deleted = delete_strategy("custom_test_v1", tmp_path)

    assert loaded is not None
    assert loaded["strategy_id"] == strategy["strategy_id"]
    assert loaded["schema_version"] == "quant_strategy_v1"
    assert loaded["strategy_version"] == "1"
    assert loaded["source"] == "user"
    assert loaded["created_at"]
    assert loaded["updated_at"]
    assert deleted is True


def test_strategy_validation_rejects_same_bar_execution() -> None:
    strategy = {"strategy_id": "bad", "execution": {"trade_at": "same_bar_close"}}

    try:
        validate_strategy(strategy)
    except ValueError as exc:
        assert "next_bar_close" in str(exc)
    else:
        raise AssertionError("same-bar strategy should be rejected")


def test_strategy_migration_normalizes_legacy_schema() -> None:
    strategy = {
        "strategy_id": "legacy_momentum",
        "schema_version": "quant_strategy_v0",
        "execution": {"trade_at": "next_bar_close"},
    }

    migrated = migrate_strategy(strategy)

    assert migrated["schema_version"] == "quant_strategy_v1"
    assert migrated["strategy_version"] == "1"
    assert migrated["migration_history"][0]["from_schema_version"] == "quant_strategy_v0"


def test_strategy_migration_rejects_unknown_schema() -> None:
    try:
        migrate_strategy({"strategy_id": "future", "schema_version": "quant_strategy_v99"})
    except ValueError as exc:
        assert "unsupported strategy schema_version" in str(exc)
    else:
        raise AssertionError("unsupported strategy schema should be rejected")


def test_model_profile_storage_roundtrip(tmp_path) -> None:
    profile = QuantModelProfile(
        profile_id="custom_model_profile_v1",
        strategy_id="momentum_ranking_v1",
        tickers=["msft", "nvda", "msft"],
        benchmark="qqq",
        run_mode="universe_per_asset",
    )

    path = save_model_profile(profile, tmp_path)
    loaded = load_model_profile("custom_model_profile_v1", tmp_path)

    assert path.exists()
    assert loaded is not None
    assert loaded.profile_id == "custom_model_profile_v1"
    assert loaded.schema_version == "quant_model_profile_v1"
    assert loaded.tickers == ["MSFT", "NVDA"]
    assert loaded.benchmark == "QQQ"
    assert loaded.created_at
    assert loaded.updated_at
    deleted = delete_model_profile("custom_model_profile_v1", tmp_path)
    assert deleted is True


def test_model_profile_rejects_same_bar_execution() -> None:
    profile = QuantModelProfile(profile_id="bad_delay_v1")
    profile = profile.model_copy(update={"backtest_config": profile.backtest_config.model_copy(update={"execution_delay_bars": 0})})

    try:
        validate_model_profile(profile)
    except ValueError as exc:
        assert "execution_delay_bars" in str(exc)
    else:
        raise AssertionError("model profile should reject same-bar execution")


def test_quant_model_lab_adapter_compiles_forecast_requests() -> None:
    profile = QuantModelProfile(
        profile_id="adapter_profile_v1",
        strategy_id="momentum_ranking_v1",
        tickers=["MSFT", "NVDA"],
        benchmark="QQQ",
        max_assets=2,
        ranking_metric="expected_return",
    )
    strategy = {"strategy_id": "momentum_ranking_v1", "execution": {"trade_at": "next_bar_close"}}

    run_request = compile_forecast_request(profile, strategy=strategy, ticker="NVDA")
    universe_request = compile_universe_request(profile, strategy=strategy)

    assert run_request.dataset_config.ticker == "NVDA"
    assert run_request.dataset_config.benchmark == "QQQ"
    assert run_request.target_config.benchmark == "QQQ"
    assert run_request.backtest_config.execution_delay_bars == 1
    assert run_request.source_context.source == "quant_model_lab"
    assert run_request.source_context.profile_id == "adapter_profile_v1"
    assert run_request.source_context.strategy_id == "momentum_ranking_v1"
    assert run_request.source_context.profile_hash
    assert universe_request.max_assets == 2
    assert universe_request.ranking_metric == "expected_return"
