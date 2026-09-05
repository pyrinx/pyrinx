"""Common database utility helpers used by repository modules."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from typing import Any

from database.connection import connect
from database.exceptions import ValidationError
from database.validation import id_list


def require_exists(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    field: str,
) -> None:
    """Raise ValidationError when a referenced row does not exist."""
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE id = ?",
        (row_id,),
    ).fetchone()

    if row is None:
        raise ValidationError(
            f"{field!r} references a non-existent {table} row: {row_id!r}"
        )


def touch(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
) -> None:
    """Update last_accessed_at timestamp for a single row."""
    conn.execute(
        """
        UPDATE {table}
        SET last_accessed_at =
            strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """.replace("{table}", table),
        (row_id,),
    )


def touch_many(
    conn: sqlite3.Connection,
    table: str,
    row_ids: Sequence[str],
) -> None:
    """Update last_accessed_at for multiple rows (no-op for empty list)."""
    if not row_ids:
        return

    placeholders = ", ".join("?" for _ in row_ids)
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
    conn.execute(
        f"""
        UPDATE {table}
        SET last_accessed_at =
            strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id IN ({placeholders})
        """,
        tuple(row_ids),
    )


def fetch_one(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    fields: Sequence[str],
) -> dict[str, Any]:
    """Fetch a single row as a dict and touch its last_accessed_at.

    Raises:
        ValidationError: If the row does not exist.
    """
    # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
    columns = ", ".join(fields)

    row = conn.execute(
        f"SELECT {columns} FROM {table} WHERE id = ?",
        (row_id,),
    ).fetchone()

    if row is None:
        raise ValidationError(f"{table!r} row does not exist: {row_id!r}")

    touch(conn, table, row_id)

    return dict(row)


def batch_get(
    ids: Any,
    table: str,
    fields: Sequence[str],
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch multiple rows by id; returns errors inline for missing/failed rows."""
    clean_ids = id_list(ids)

    with connect() as conn:
        result: list[dict[str, Any]] = []

        for row_id in clean_ids:
            try:
                row = fetch_one(conn, table, row_id, fields)

                if transform is not None:
                    row = transform(row)

                result.append(row)
            except (ValidationError, sqlite3.Error) as exc:
                result.append(
                    {
                        "id": row_id,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        return result


def fetch_rows(
    conn: sqlite3.Connection,
    table: str,
    fields: Sequence[str] = ("id",),
    filters: dict[str, Any] | None = None,
    order_by: str = "created_at DESC",
) -> list[dict[str, Any]]:
    """Fetch multiple rows with optional equality filters and touch them."""
    query_fields = list(fields)
    has_id = "id" in query_fields
    if not has_id:
        query_fields.append("id")

    columns = ", ".join(query_fields)

    active_filters = {k: v for k, v in (filters or {}).items() if v is not None}

    if active_filters:
        where_clause = " AND ".join(f"{col} = ?" for col in active_filters)
        query = (
            # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
            f"SELECT {columns} FROM {table} WHERE {where_clause} ORDER BY {order_by}"
        )
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
        values = tuple(active_filters.values())
        rows = conn.execute(query, values).fetchall()
    else:
        query = f"SELECT {columns} FROM {table} ORDER BY {order_by}"
        rows = conn.execute(query).fetchall()

    row_dicts = [dict(row) for row in rows]

    retrieved_ids = [r["id"] for r in row_dicts]
    touch_many(conn, table, retrieved_ids)

    if not has_id:
        for r in row_dicts:
            r.pop("id", None)

    return row_dicts


def update_one(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    updates: dict[str, Any],
    filters: dict[str, Any] | None = None,
    fields: Sequence[str] = ("id",),
) -> dict[str, Any]:
    """Apply updates to a single row and return the resulting row.

    Raises:
        ValidationError: If there are no updates or the row does not exist /
            does not match provided filters.
    """
    active_updates = {k: v for k, v in updates.items() if v is not None}
    if not active_updates:
        raise ValidationError("No valid fields provided for update")

    set_clause = ", ".join(f"{col} = ?" for col in active_updates)
    where_conditions = ["id = ?"]
    params = list(active_updates.values())
    params.append(row_id)

    active_filters = {k: v for k, v in (filters or {}).items() if v is not None}
    for col, val in active_filters.items():
        where_conditions.append(f"{col} = ?")
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
        params.append(val)

    where_clause = " AND ".join(where_conditions)
    query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

    cursor = conn.execute(query, tuple(params))

    if cursor.rowcount == 0:
        if active_filters:
            filter_desc = ", ".join(f"{k}='{v}'" for k, v in active_filters.items())
            raise ValidationError(
                f"{table!r} row '{row_id}' does not exist or does not match criteria ({filter_desc})"
            )
        raise ValidationError(f"{table!r} row does not exist: {row_id!r}")

    return fetch_one(conn, table, row_id, fields)
