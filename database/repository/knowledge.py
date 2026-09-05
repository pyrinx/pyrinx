"""Repository functions for long-term knowledge storage."""

from __future__ import annotations

import json

from database.connection import connect
from database.identifiers import insert_with_unique_id
from database.repository.common import (
    batch_get,
    fetch_one,
    fetch_rows,
    update_one,
)
from database.validation import (
    json_array,
    non_empty_str,
    optional_str,
)

_FIELDS = (
    "id",
    "summary",
    "indicators",
    "attack_surface",
    "attack_vector",
    "vuln_class",
    "tags",
    "created_at",
)


def create_knowledge(
    summary: str,
    indicators: list | str | None = None,
    attack_surface: str | None = None,
    attack_vector: str | None = None,
    vuln_class: str | None = None,
    tags: list | str | None = None,
) -> dict[str, object]:
    summary = non_empty_str(summary, "summary")
    attack_surface = optional_str(attack_surface, "attack_surface")
    attack_vector = optional_str(attack_vector, "attack_vector")
    vuln_class = optional_str(vuln_class, "vuln_class")

    indicators = [] if indicators is None else indicators
    tags = [] if tags is None else tags

    indicators = json_array(indicators, "indicators")
    tags = json_array(tags, "tags")

    with connect() as conn:
        knowledge_id = insert_with_unique_id(
            conn,
            "knowledges",
            {
                "summary": summary,
                "indicators": indicators,
                "attack_surface": attack_surface,
                "attack_vector": attack_vector,
                "vuln_class": vuln_class,
                "tags": tags,
            },
        )

        row = fetch_one(conn, "knowledges", knowledge_id, _FIELDS)

    return _decode(row)


def get_knowledge(ids: list[str]) -> list[dict[str, object]]:
    return batch_get(ids, "knowledges", _FIELDS, _decode)


def list_knowledge(vuln_class: str) -> list[str]:
    vuln_class = non_empty_str(vuln_class, "vuln_class")

    filters = {"vuln_class": vuln_class}

    with connect() as conn:
        rows = fetch_rows(conn, "knowledges", fields=["id"], filters=filters)

    return [r["id"] for r in rows]


def update_knowledge(
    knowledge_id: str,
    summary: str | None = None,
    indicators: list | str | None = None,
    attack_surface: str | None = None,
    attack_vector: str | None = None,
    vuln_class: str | None = None,
    tags: list | str | None = None,
) -> dict[str, object]:
    knowledge_id = non_empty_str(knowledge_id, "knowledge_id")

    updates: dict[str, object] = {}
    if summary is not None:
        updates["summary"] = non_empty_str(summary, "summary")
    if indicators is not None:
        updates["indicators"] = json_array(indicators, "indicators")
    if attack_surface is not None:
        updates["attack_surface"] = optional_str(attack_surface, "attack_surface")
    if attack_vector is not None:
        updates["attack_vector"] = optional_str(attack_vector, "attack_vector")
    if vuln_class is not None:
        updates["vuln_class"] = optional_str(vuln_class, "vuln_class")
    if tags is not None:
        updates["tags"] = json_array(tags, "tags")

    with connect() as conn:
        row = update_one(
            conn=conn,
            table="knowledges",
            row_id=knowledge_id,
            updates=updates,
            fields=_FIELDS,
        )

    return _decode(row)


def _decode(row: dict[str, object]) -> dict[str, object]:
    row["indicators"] = json.loads(row["indicators"])
    row["tags"] = json.loads(row["tags"])
    return row
