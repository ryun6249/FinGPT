from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

from pipelines.data_mart.storage.db import connect, init_db
from pipelines.data_mart.storage.schema import SCHEMA_VERSION


def test_init_db_creates_data_mart_tables(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    resolved = init_db(db_path)

    assert resolved == db_path
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "assets",
            "prices_daily",
            "macro_series",
            "macro_observations",
            "news_articles",
            "filings",
            "sec_company_registry",
            "sec_financial_facts",
            "data_update_runs",
            "provider_status",
            "data_quality_checks",
        }.issubset(tables)
        version = conn.execute("SELECT version FROM schema_migrations").fetchone()[0]
        assert version == SCHEMA_VERSION


def test_init_db_is_idempotent_and_uses_wal(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    init_db(db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        migrations = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert migrations == 1
        assert journal_mode.lower() == "wal"


def test_init_db_is_thread_safe_for_concurrent_read_paths(tmp_path) -> None:
    db_path = tmp_path / "research_mart.db"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: init_db(db_path), range(16)))

    assert results == [db_path] * 16
    with connect(db_path) as conn:
        migrations = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert migrations == 1
        assert busy_timeout >= 30000
