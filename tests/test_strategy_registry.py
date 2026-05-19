from __future__ import annotations

from pipelines.strategies.registry import get_strategy, list_strategies
from pipelines.strategies.storage import delete_strategy, load_strategy, migrate_strategy, save_strategy, validate_strategy


def test_default_strategy_registry_contains_no_lookahead_policy() -> None:
    strategies = list_strategies()

    assert get_strategy("momentum_ranking_v1") is not None
    risk_adjusted = get_strategy("risk_adjusted_momentum_v1")
    assert risk_adjusted is not None
    assert risk_adjusted["features"]["risk_adjusted_momentum_63_21"]["id"] == "risk_adjusted_momentum_63_21"
    assert risk_adjusted["signal"]["score_mode"] == "risk_adjusted_momentum"
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
