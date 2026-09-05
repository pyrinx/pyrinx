"""SQLite connection helpers and schema initialization."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .exceptions import DatabaseError

_BASE_DIR: Path = Path(__file__).resolve().parent.parent
_SCHEMA_PATH: Path = _BASE_DIR / "database" / "schema.sql"
_DB_PATH: Path = _BASE_DIR / "storage" / "data.db"

_CONNECT_TIMEOUT_SECONDS: int = 5
_BUSY_TIMEOUT_MS: int = 5000


def _initialize_schema() -> None:
    """Ensure the database file exists and the schema is applied.

    Raises:
        DatabaseError: If the schema file is missing or initialization fails.
    """
    if not _SCHEMA_PATH.is_file():
        raise DatabaseError(f"schema file not found: {_SCHEMA_PATH}")

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        script = _SCHEMA_PATH.read_text(encoding="utf-8")
        # Using sqlite3.connect context manager ensures the script runs on a
        # temporary connection solely for initialization.
        with sqlite3.connect(_DB_PATH) as conn:
            conn.executescript(script)
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseError(f"failed to initialize database: {exc}") from exc


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Context manager yielding a configured sqlite3.Connection.

    The function initializes the schema if necessary, sets sensible pragmas,
    yields an open connection and commits on success, rolling back on error.

    Yields:
        sqlite3.Connection: Configured connection object.

    Raises:
        DatabaseError: If connecting to the database fails.
    """
    _initialize_schema()

    try:
        conn = sqlite3.connect(
            _DB_PATH,
            timeout=_CONNECT_TIMEOUT_SECONDS,
            isolation_level="DEFERRED",
        )
    except sqlite3.Error as exc:
        raise DatabaseError(f"failed to connect to database: {exc}") from exc

    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        yield conn
        conn.commit()
    except Exception:
        # Preserve original exception while ensuring DB is left consistent.
        conn.rollback()
        raise
    finally:
        conn.close()
