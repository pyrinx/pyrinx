"""Create junction rows linking hypotheses/findings to evidence."""

from __future__ import annotations

from database.connection import connect
from database.repository.common import require_exists, touch
from database.validation import non_empty_str


def link_hypothesis_evidence(
    hypothesis_id: str,
    evidence_id: str,
) -> dict[str, object]:
    return _link(
        "hypotheses_evidences",
        "hypothesis_id",
        "hypotheses",
        hypothesis_id,
        "evidence_id",
        "evidences",
        evidence_id,
        "hypothesis_id",
        "evidence_id",
    )


def link_finding_evidence(
    finding_id: str,
    evidence_id: str,
) -> dict[str, object]:
    return _link(
        "findings_evidences",
        "finding_id",
        "findings",
        finding_id,
        "evidence_id",
        "evidences",
        evidence_id,
        "finding_id",
        "evidence_id",
    )


def _link(
    junction: str,
    left_column: str,
    left_table: str,
    left_id: str,
    right_column: str,
    right_table: str,
    right_id: str,
    left_field: str,
    right_field: str,
) -> dict[str, object]:
    left_id = non_empty_str(left_id, left_field)
    right_id = non_empty_str(right_id, right_field)

    with connect() as conn:
        require_exists(conn, left_table, left_id, left_field)
        require_exists(conn, right_table, right_id, right_field)

        cursor = conn.execute(
            f"""
            INSERT INTO {junction} ({left_column}, {right_column})
            VALUES (?, ?)
            ON CONFLICT ({left_column}, {right_column}) DO NOTHING
            """,
            (left_id, right_id),
        )

        created = cursor.rowcount == 1

        touch(conn, left_table, left_id)
        touch(conn, right_table, right_id)

    return {
        left_field: left_id,
        right_field: right_id,
        "created": created,
    }
