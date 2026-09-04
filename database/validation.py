"""Validation helpers for values stored in the database."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from typing import Any

from .exceptions import ValidationError

HTTP_METHODS: frozenset[str] = frozenset(
    {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
        "TRACE",
        "CONNECT",
    }
)

SESSION_STATUSES: frozenset[str] = frozenset({"active", "closed"})

HYPOTHESIS_STATUSES: frozenset[str] = frozenset(
    {
        "proposed",
        "testing",
        "supported",
        "rejected",
        "inconclusive",
    }
)


def non_empty_str(value: Any, field: str) -> str:
    """Validate that value is a non-empty string and return the stripped value."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field!r} must be a non-empty string")
    return value.strip()


def optional_str(value: Any, field: str) -> str | None:
    """Validate that value is a string or None and return value unchanged."""
    if value is not None and not isinstance(value, str):
        raise ValidationError(f"{field!r} must be a string or None")
    return value


def one_of(value: Any, allowed: Iterable[str], field: str) -> str:
    """Validate that value is one of allowed options."""
    allowed_set = frozenset(allowed)
    if value not in allowed_set:
        raise ValidationError(
            f"{field!r} must be one of {sorted(allowed_set)}, got {value!r}"
        )
    return value


def int_range(value: Any, low: int, high: int, field: str) -> int:
    """Validate that value is an int within [low, high]."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field!r} must be an int, got {type(value).__name__}")

    if not low <= value <= high:
        raise ValidationError(
            f"{field!r} must be between {low} and {high}, got {value}"
        )

    return value


def float_range(value: Any, low: float, high: float, field: str) -> float:
    """Validate that value is a finite number within [low, high]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field!r} must be a number, got {type(value).__name__}")

    coerced = float(value)

    if not math.isfinite(coerced) or not low <= coerced <= high:
        raise ValidationError(
            f"{field!r} must be between {low} and {high}, got {coerced}"
        )

    return coerced


def bool_value(value: Any, field: str) -> bool:
    """Validate that value is a boolean."""
    if not isinstance(value, bool):
        raise ValidationError(f"{field!r} must be a bool, got {type(value).__name__}")
    return value


def json_object(value: Any, field: str) -> str:
    """Ensure value is a JSON object or JSON string representing an object.

    Returns:
        Canonical JSON string for storage.
    """
    return _validate_json_container(value, dict, field, "object")


def json_array(value: Any, field: str) -> str:
    """Ensure value is a JSON array or JSON string representing an array.

    Returns:
        Canonical JSON string for storage.
    """
    return _validate_json_container(value, list, field, "array")


def id_list(value: Any, field: str = "ids") -> list[str]:
    """Validate a non-empty list of non-empty string ids."""
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{field!r} must be a non-empty list")

    return [
        non_empty_str(item, f"{field}[{index}]") for index, item in enumerate(value)
    ]


def _validate_json_container(
    value: Any,
    expected_type: type,
    field: str,
    container_name: str,
) -> str:
    """Validate a JSON container (object or array) and return canonical JSON."""
    if isinstance(value, expected_type):
        return json.dumps(value)

    if not isinstance(value, str):
        raise ValidationError(
            f"{field!r} must be a {container_name} or JSON {container_name} string"
        )

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{field!r} is not valid JSON: {exc}") from exc

    if not isinstance(parsed, expected_type):
        raise ValidationError(f"{field!r} must be a JSON {container_name}")

    return json.dumps(parsed)
