"""Session creation, closing and retrieval helpers."""

from __future__ import annotations

from database.connection import connect
from database.identifiers import insert_with_unique_id
from database.repository.common import batch_get, fetch_one, require_exists
from database.validation import non_empty_str

_FIELDS = (
    "id",
    "target",
    "status",
    "vuln_class",
    "created_at",
)


def create_session(target: str, vuln_class: str) -> dict[str, object]:
    """Create and return a new session row."""
    target = non_empty_str(target, "target")
    vuln_class = non_empty_str(vuln_class, "vuln_class")

    with connect() as conn:
        session_id = insert_with_unique_id(
            conn,
            "sessions",
            {
                "target": target,
                "status": "active",
                "vuln_class": vuln_class,
            },
        )
        return fetch_one(conn, "sessions", session_id, _FIELDS)


def close_session(session_id: str) -> dict[str, object]:
    """Mark a session as closed and return the updated row."""
    session_id = non_empty_str(session_id, "session_id")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        conn.execute(
            "UPDATE sessions SET status = 'closed' WHERE id = ?", (session_id,)
        )

        return fetch_one(conn, "sessions", session_id, _FIELDS)


def get_session(ids: list[str]) -> list[dict[str, object]]:
    """Fetch multiple sessions by id (errors inline)."""
    return batch_get(ids, "sessions", _FIELDS)
