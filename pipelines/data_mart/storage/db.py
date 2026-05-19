from __future__ import annotations

import sqlite3
from pathlib import Path

from core.config.settings import load_settings
from pipelines.data_mart.models import utc_now_iso
from pipelines.data_mart.storage.schema import DDL_STATEMENTS, SCHEMA_VERSION


FINGPT_ANNOTATIONS_TABLE = "fingpt_article_annotations"
FINGPT_ANNOTATIONS_OLD_TABLE = "fingpt_article_annotations_old"
ADDITIVE_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "filings": (
        ("cik", "TEXT"),
        ("accession_number", "TEXT"),
        ("report_date", "TEXT"),
        ("fiscal_year", "INTEGER"),
        ("fiscal_period", "TEXT"),
        ("primary_document", "TEXT"),
        ("description", "TEXT"),
        ("raw_json", "TEXT NOT NULL DEFAULT '{}'"),
    ),
    "financial_statements": (
        ("total_liabilities", "REAL"),
        ("stockholders_equity", "REAL"),
        ("gross_profit", "REAL"),
        ("operating_income", "REAL"),
        ("net_income", "REAL"),
    ),
}


class ManagedConnection(sqlite3.Connection):
    """SQLite connection that closes when used as a context manager."""

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def default_db_path() -> Path:
    settings = load_settings()
    configured = str(getattr(settings, "data_mart_db_path", "") or "").strip()
    return Path(configured) if configured else settings.data_dir / "research_mart.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15, factory=ManagedConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _fingpt_annotations_table_ddl() -> str:
    for statement in DDL_STATEMENTS:
        if f"CREATE TABLE IF NOT EXISTS {FINGPT_ANNOTATIONS_TABLE}" in statement:
            return statement
    raise RuntimeError(f"Missing DDL for {FINGPT_ANNOTATIONS_TABLE}")


def _fingpt_annotations_index_ddls() -> tuple[str, ...]:
    return tuple(
        statement
        for statement in DDL_STATEMENTS
        if statement.startswith("CREATE INDEX IF NOT EXISTS idx_fingpt_annotations_")
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def _ensure_additive_columns(conn: sqlite3.Connection) -> None:
    for table_name, columns in ADDITIVE_COLUMNS.items():
        if not _table_exists(conn, table_name):
            continue
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")}
        for column_name, column_ddl in columns:
            if column_name in existing:
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}")


def _fingpt_annotations_needs_model_id_rebuild(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, FINGPT_ANNOTATIONS_TABLE):
        return False
    columns = {row["name"]: row for row in conn.execute(f"PRAGMA table_info({FINGPT_ANNOTATIONS_TABLE})")}
    model_id = columns.get("model_id")
    if model_id is None:
        return True
    return int(model_id["notnull"] or 0) != 1 or str(model_id["dflt_value"] or "") != "''"


def _copy_fingpt_annotations_rows(conn: sqlite3.Connection, model_expr: str) -> None:
    # Table names and model expression are internal migration constants.
    if model_expr not in {"COALESCE(model_id, '')", "''"}:
        raise ValueError(f"unsupported model_id migration expression: {model_expr}")
    sql = "\n".join(
        [
            "INSERT INTO " + FINGPT_ANNOTATIONS_TABLE + "(",
            """
            article_id, ticker, task, label, confidence, source, model_id, metadata_json, created_at
            )
            SELECT article_id, ticker, task, label, confidence, source, model_id, metadata_json, created_at
            FROM (
                SELECT
                article_id,
                ticker,
                task,
                label,
                confidence,
                source,
                """,
            model_expr + " AS model_id,",
            """
                metadata_json,
                created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY article_id, task, source, """,
            model_expr,
            """
                    ORDER BY created_at DESC, rowid DESC
                ) AS row_rank
                FROM """,
            FINGPT_ANNOTATIONS_OLD_TABLE,
            """
            )
            WHERE row_rank = 1
            """,
        ]
    )
    conn.execute(sql)


def _migrate_fingpt_annotations_model_id(conn: sqlite3.Connection) -> None:
    if not _fingpt_annotations_needs_model_id_rebuild(conn):
        return

    columns = {row["name"]: row for row in conn.execute(f"PRAGMA table_info({FINGPT_ANNOTATIONS_TABLE})")}
    model_expr = "COALESCE(model_id, '')" if "model_id" in columns else "''"

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"DROP TABLE IF EXISTS {FINGPT_ANNOTATIONS_OLD_TABLE}")
        conn.execute(f"ALTER TABLE {FINGPT_ANNOTATIONS_TABLE} RENAME TO {FINGPT_ANNOTATIONS_OLD_TABLE}")
        conn.execute(_fingpt_annotations_table_ddl())
        _copy_fingpt_annotations_rows(conn, model_expr)
        conn.execute(f"DROP TABLE {FINGPT_ANNOTATIONS_OLD_TABLE}")
        for statement in _fingpt_annotations_index_ddls():
            conn.execute(statement)
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def init_db(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path is not None else default_db_path()
    with connect(path) as conn:
        for statement in DDL_STATEMENTS:
            conn.execute(statement)
        conn.commit()
        _ensure_additive_columns(conn)
        conn.commit()
        _migrate_fingpt_annotations_model_id(conn)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now_iso()),
        )
        conn.commit()
    return path
