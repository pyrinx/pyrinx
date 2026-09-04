"""Repository functions for HTTP exchange records."""

from __future__ import annotations

import json

from database.connection import connect
from database.identifiers import insert_with_unique_id
from database.repository.common import (
    batch_get,
    fetch_one,
    require_exists,
)
from database.validation import (
    HTTP_METHODS,
    int_range,
    json_object,
    non_empty_str,
    one_of,
    optional_str,
)

_FIELDS = (
    "id",
    "session_id",
    "url",
    "method",
    "status_code",
    "request_headers",
    "response_headers",
    "request_body",
    "response_body",
    "response_time",
    "vuln_class",
    "created_at",
)

_HEADER_FIELDS = (
    "id",
    "session_id",
    "request_headers",
    "response_headers",
)

_BODY_FIELDS = (
    "id",
    "session_id",
    "url",
    "request_body",
    "response_body",
)


def create_exchange(
    session_id: str,
    url: str,
    method: str,
    status_code: int,
    request_headers: dict | str | None = None,
    response_headers: dict | str | None = None,
    request_body: str | None = None,
    response_body: str | None = None,
    response_time: str | None = None,
    vuln_class: str | None = None,
) -> dict[str, object]:
    """Create an exchange row and return a summarized representation."""
    session_id = non_empty_str(session_id, "session_id")
    url = non_empty_str(url, "url")
    method = one_of(method, HTTP_METHODS, "method")
    status_code = int_range(status_code, 100, 599, "status_code")
    request_body = optional_str(request_body, "request_body")
    response_body = optional_str(response_body, "response_body")
    response_time = optional_str(response_time, "response_time")
    vuln_class = optional_str(vuln_class, "vuln_class")

    request_headers = {} if request_headers is None else request_headers
    response_headers = {} if response_headers is None else response_headers

    request_headers = json_object(request_headers, "request_headers")
    response_headers = json_object(response_headers, "response_headers")

    with connect() as conn:
        require_exists(conn, "sessions", session_id, "session_id")

        exchange_id = insert_with_unique_id(
            conn,
            "exchange",
            {
                "session_id": session_id,
                "url": url,
                "method": method,
                "status_code": status_code,
                "request_headers": request_headers,
                "response_headers": response_headers,
                "request_body": request_body,
                "response_body": response_body,
                "response_time": response_time,
                "vuln_class": vuln_class,
            },
        )

        row = fetch_one(conn, "exchange", exchange_id, _FIELDS)

    return _summarize(row)


def get_exchange(ids: list[str]) -> list[dict[str, object]]:
    """Return summarized exchange records for given ids."""
    return batch_get(ids, "exchange", _FIELDS[:-1], _summarize)


def get_exchange_headers(ids: list[str]) -> list[dict[str, object]]:
    """Return decoded JSON header objects for given exchange ids."""
    return batch_get(ids, "exchange", _HEADER_FIELDS, _decode_headers)


def get_exchange_body(ids: list[str]) -> list[dict[str, object]]:
    """Return exchange body payloads for given ids."""
    return batch_get(ids, "exchange", _BODY_FIELDS)


def _summarize(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "url": row["url"],
        "method": row["method"],
        "status_code": row["status_code"],
        "request_header_count": len(json.loads(row["request_headers"])),
        "response_header_count": len(json.loads(row["response_headers"])),
        "request_body_bytes": _body_size(row["request_body"]),
        "response_body_bytes": _body_size(row["response_body"]),
        "response_time": row["response_time"],
        "vuln_class": row["vuln_class"],
    }


def _decode_headers(row: dict[str, object]) -> dict[str, object]:
    row["request_headers"] = json.loads(row["request_headers"])
    row["response_headers"] = json.loads(row["response_headers"])
    return row


def _body_size(body: str | None) -> int:
    return len((body or "").encode("utf-8"))
