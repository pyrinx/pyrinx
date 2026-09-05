"""Repository functions for hypothesis."""

from __future__ import annotations

from database.connection import connect
from database.identifiers import insert_with_unique_id
from database.repository.common import (
    batch_get,
    fetch_one,
    fetch_rows,
    require_exists,
)
from database.validation import (
    HYPOTHESIS_STATUSES,
    non_empty_str,
    one_of,
    optional_str,
)

_FIELDS = (
    "id",
    "session_id",
    "parent_id",
    "claim",
    "rationale",
    "test",
    "expected_result",
    "status",
    "vuln_class",
    "created_at",
    "updated_at",
)


def create_hypothesis(
    session_id: str,
    claim: str,
    parent_id: str | None = None,
    rationale: str | None = None,
    test: str | None = None,
    expected_result: str | None = None,
    status: str = "proposed",
    vuln_class: str | None = None,
) -> dict[str, object]:
    session_id = non_empty_str(session_id, "session_id")
    claim = non_empty_str(claim, "claim")
    rationale = optional_str(rationale, "rationale")
    test = optional_str(test, "test")
    expected_result = optional_str(expected_result, "expected_result")
    vuln_class = optional_str(vuln_class, "vuln_class")
    status = one_of(status, HYPOTHESIS_STATUSES, "status")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        if parent_id is not None:
            parent_id = non_empty_str(parent_id, "parent_id")
            require_exists(conn, "hypotheses", parent_id, "parent_id")

        hypothesis_id = insert_with_unique_id(
            conn,
            "hypotheses",
            {
                "session_id": session_id,
                "parent_id": parent_id,
                "claim": claim,
                "rationale": rationale,
                "test": test,
                "expected_result": expected_result,
                "status": status,
                "vuln_class": vuln_class,
            },
        )

        return fetch_one(conn, "hypotheses", hypothesis_id, _FIELDS)


def update_hypothesis_status(hypothesis_id: str, status: str) -> dict[str, object]:
    hypothesis_id = non_empty_str(hypothesis_id, "hypothesis_id")
    status = one_of(status, HYPOTHESIS_STATUSES, "status")

    with connect() as conn:
        require_exists(conn, "hypotheses", hypothesis_id, "hypothesis_id")

        conn.execute(
            """
            UPDATE hypotheses
            SET status = ?,
                updated_at = strftime(
                    '%Y-%m-%dT%H:%M:%fZ', 'now'
                )
            WHERE id = ?
            """,
            (status, hypothesis_id),
        )

        return fetch_one(conn, "hypotheses", hypothesis_id, _FIELDS)


def get_hypothesis(ids: list[str]) -> list[dict[str, object]]:
    return batch_get(ids, "hypotheses", _FIELDS)


def list_hypotheses(
    session_id: str | None = None,
    vuln_class: str | None = None,
) -> list[dict[str, object]]:
    session_id = optional_str(session_id, "session_id")
    vuln_class = optional_str(vuln_class, "vuln_class")

    with connect() as conn:
        return fetch_rows(
            conn=conn,
            table="hypotheses",
            fields=("id", "parent_id", "status"),
            filters={
                "session_id": session_id,
                "vuln_class": vuln_class,
            },
            order_by="created_at ASC",
        )
