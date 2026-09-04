"""ID generation and insertion helpers for the database.

Note: the module name mirrors the original layout (indentifiers.py). It provides
a safe insert helper that retries on primary-key collisions.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from collections.abc import Mapping
from typing import Any

from .exceptions import RaceConditionError

_ID_LOCK = threading.Lock()
_id_counter: int = 0

MAX_ID_RETRIES: int = 5

TABLE_PREFIXES: dict[str, str] = {
    "sessions": "ses",
    "exchange": "exc",
    "evidence": "evi",
    "hypothesis": "hyp",
    "finding": "fin",
    "knowledge": "kno",
}


def generate_id(prefix: str) -> str:
    """Generate a reasonably unique identifier using a prefix, timestamp,
    counter and random suffix.

    The generated value is not guaranteed globally unique; callers that need
    uniqueness should handle integrity errors and retry (see
    insert_with_unique_id).
    """
    global _id_counter

    with _ID_LOCK:
        _id_counter = (_id_counter + 1) % 0xFFFF
        counter = _id_counter

    milliseconds = int(time.time() * 1000)
    random_suffix = os.urandom(4).hex()

    return f"{prefix}{milliseconds}{counter:04x}{random_suffix}"


def insert_with_unique_id(
    conn: sqlite3.Connection,
    table: str,
    columns: Mapping[str, Any],
) -> str:
    """Insert a row into `table` with a generated unique id.

    The function will attempt `MAX_ID_RETRIES` different ids and raise
    RaceConditionError if a unique id cannot be generated.

    Args:
        conn: Open sqlite3.Connection.
        table: Target table name (must be a key in TABLE_PREFIXES).
        columns: Mapping of column name -> value (excluding the id column).

    Returns:
        The generated unique id for the inserted row.

    Raises:
        ValueError: If the table is unsupported.
        RaceConditionError: If unique id generation repeatedly collides.
        sqlite3.IntegrityError: Any integrity error that is not a primary-key
            collision is re-raised.
    """
    prefix = TABLE_PREFIXES.get(table)
    if prefix is None:
        raise ValueError(f"unsupported database table: {table!r}")

    column_names = ["id", *columns]
    placeholders = ", ".join("?" for _ in column_names)
    names = ", ".join(column_names)
    statement = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"

    last_error: sqlite3.IntegrityError | None = None

    for _ in range(MAX_ID_RETRIES):
        new_id = generate_id(prefix)

        try:
            conn.execute(statement, [new_id, *columns.values()])
            return new_id
        except sqlite3.IntegrityError as exc:
            if not _is_primary_key_collision(exc):
                # Integrity errors other than primary key collisions are real
                # constraints violations and should be surfaced to the caller.
                raise
            last_error = exc

    raise RaceConditionError(
        f"could not generate a unique id for {table!r} after {MAX_ID_RETRIES} attempts"
    ) from last_error


def _is_primary_key_collision(error: sqlite3.IntegrityError) -> bool:
    """Return True when the integrity error looks like an `id` primary-key
    collision for our generated ids.
    """
    message = str(error).lower()
    return "unique constraint failed" in message and ".id" in message
