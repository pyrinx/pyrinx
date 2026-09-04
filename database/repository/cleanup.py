"""Helpers to remove expired or orphaned rows from storage."""

from __future__ import annotations

from database.connection import connect

STALE_AFTER = "-1 hour"

_CHILD_TABLES = (
    "exchange",
    "evidence",
    "hypothesis",
    "finding",
)


def cleanup_expired_data() -> dict[str, int]:
    """Remove old or orphaned child rows and closed sessions.

    Returns:
        Mapping of table name -> number of deleted rows.
    """
    deleted: dict[str, int] = {}

    with connect() as conn:
        for table in _CHILD_TABLES:
            cursor = conn.execute(
                """
                DELETE FROM {table}
                WHERE session_id IN (
                    SELECT id
                    FROM sessions
                    WHERE status = 'closed'
                )
                OR (
                    session_id IN (
                        SELECT id
                        FROM sessions
                        WHERE status = 'active'
                    )
                    AND last_accessed_at <=
                        strftime(
                            '%Y-%m-%dT%H:%M:%fZ',
                            'now',
                            ?
                        )
                )
                """.replace("{table}", table),
                (STALE_AFTER,),
            )
            deleted[table] = cursor.rowcount

        cursor = conn.execute(
            """
            DELETE FROM sessions
            WHERE status = 'closed'
              AND NOT EXISTS (
                  SELECT 1
                  FROM exchange
                  WHERE exchange.session_id = sessions.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM evidence
                  WHERE evidence.session_id = sessions.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM hypothesis
                  WHERE hypothesis.session_id = sessions.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM finding
                  WHERE finding.session_id = sessions.id
              )
            """
        )
        deleted["sessions"] = cursor.rowcount

    return deleted
