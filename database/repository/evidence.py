"""Repository functions for evidence rows."""

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
    float_range,
    non_empty_str,
    optional_str,
)

_FIELDS = (
    "id",
    "session_id",
    "exchange_id",
    "observation",
    "observed_value",
    "confidence",
    "vuln_class",
    "created_at",
)


def create_evidence(
    session_id: str,
    observation: str,
    observed_value: str | None = None,
    confidence: float = 0.5,
    exchange_id: str | None = None,
    vuln_class: str | None = None,
) -> dict[str, object]:
    """Create a new evidence row and return the stored row."""
    session_id = non_empty_str(session_id, "session_id")
    observation = non_empty_str(observation, "observation")
    observed_value = optional_str(observed_value, "observed_value")
    vuln_class = optional_str(vuln_class, "vuln_class")
    confidence = float_range(confidence, 0.0, 1.0, "confidence")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        if exchange_id is not None:
            exchange_id = non_empty_str(exchange_id, "exchange_id")
            require_exists(conn, "exchanges", exchange_id, "exchange_id")

        evidence_id = insert_with_unique_id(
            conn,
            "evidences",
            {
                "session_id": session_id,
                "exchange_id": exchange_id,
                "observation": observation,
                "observed_value": observed_value,
                "confidence": confidence,
                "vuln_class": vuln_class,
            },
        )

        return fetch_one(conn, "evidences", evidence_id, _FIELDS)


def get_evidence(ids: list[str]) -> list[dict[str, object]]:
    """Fetch multiple evidence rows by id (errors inline)."""
    return batch_get(ids, "evidences", _FIELDS)


def list_evidence(
    session_id: str | None = None,
    vuln_class: str | None = None,
) -> list[dict[str, object]]:
    """List evidence rows with optional filters."""
    session_id = optional_str(session_id, "session_id")
    vuln_class = optional_str(vuln_class, "vuln_class")

    with connect() as conn:
        return fetch_rows(
            conn=conn,
            table="evidences",
            fields=("id", "exchange_id", "observation", "confidence"),
            filters={
                "session_id": session_id,
                "vuln_class": vuln_class,
            },
            order_by="created_at ASC",
        )
