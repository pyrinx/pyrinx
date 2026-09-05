"""Repository functions for findings."""

from __future__ import annotations

from database.connection import connect
from database.identifiers import insert_with_unique_id
from database.repository.common import (
    batch_get,
    fetch_one,
    fetch_rows,
    require_exists,
    update_one,
)
from database.validation import (
    bool_value,
    non_empty_str,
    optional_str,
)

_FIELDS = (
    "id",
    "session_id",
    "title",
    "detail",
    "impact",
    "verified",
    "vuln_class",
    "created_at",
)


def create_finding(
    session_id: str,
    title: str,
    detail: str | None = None,
    impact: str | None = None,
    verified: bool = False,
    vuln_class: str | None = None,
) -> dict[str, object]:
    """Create a finding and return the stored row with normalized fields."""
    session_id = non_empty_str(session_id, "session_id")
    title = non_empty_str(title, "title")
    detail = optional_str(detail, "detail")
    impact = optional_str(impact, "impact")
    vuln_class = optional_str(vuln_class, "vuln_class")
    verified = bool_value(verified, "verified")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        finding_id = insert_with_unique_id(
            conn,
            "findings",
            {
                "session_id": session_id,
                "title": title,
                "detail": detail,
                "impact": impact,
                "verified": int(verified),
                "vuln_class": vuln_class,
            },
        )

        row = fetch_one(conn, "findings", finding_id, _FIELDS)

    row["verified"] = bool(row["verified"])
    return row


def get_finding(ids: list[str]) -> list[dict[str, object]]:
    return batch_get(ids, "findings", _FIELDS, _normalize)


def update_finding_verification(
    finding_id: str,
    session_id: str,
    verified: bool,
) -> dict[str, object]:
    finding_id = non_empty_str(finding_id, "finding_id")
    session_id = non_empty_str(session_id, "session_id")
    verified = bool_value(verified, "verified")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        row = update_one(
            conn=conn,
            table="findings",
            row_id=finding_id,
            updates={"verified": int(verified)},
            filters={"session_id": session_id},
            fields=_FIELDS,
        )

    return _normalize(row)


def list_findings(
    session_id: str | None = None,
    vuln_class: str | None = None,
) -> list[dict[str, object]]:
    session_id = optional_str(session_id, "session_id")
    vuln_class = optional_str(vuln_class, "vuln_class")

    with connect() as conn:
        rows = fetch_rows(
            conn=conn,
            table="findings",
            fields=("id", "title", "verified", "vuln_class"),
            filters={
                "session_id": session_id,
                "vuln_class": vuln_class,
            },
            order_by="created_at ASC",
        )

    for row in rows:
        row["verified"] = bool(row["verified"])

    return rows


def _normalize(row: dict[str, object]) -> dict[str, object]:
    row["verified"] = bool(row["verified"])
    return row
