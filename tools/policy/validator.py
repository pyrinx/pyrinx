"""Tag validation.

Rules:
    - 2 to 3 tags total.
    - Exactly one ACTION tag.
    - At least one of FOR or FROM.
    - No namespace used twice.
    - Every tag must be a defined member of ACTION / FOR / FROM.
"""

from __future__ import annotations

from .tags import _Action, _For, _From

_MIN_TAGS = 2
_MAX_TAGS = 3


def _members(cls: type) -> frozenset[str]:
    return frozenset(
        value
        for key, value in vars(cls).items()
        if not key.startswith("_") and isinstance(value, str)
    )


_NAMESPACE_OF: dict[str, str] = {
    **{value: "ACTION" for value in _members(_Action)},
    **{value: "FOR" for value in _members(_For)},
    **{value: "FROM" for value in _members(_From)},
}


def validate_tags(tags: list[str]) -> None:
    """Validate a tool's tag list.

    Args:
        tags: 2 to 3 plain-string tags, e.g. [ACTION.extract, FOR.link].

    Raises:
        ValueError: If the tag list violates policy.
    """
    if not _MIN_TAGS <= len(tags) <= _MAX_TAGS:
        raise ValueError(
            f"tags must contain {_MIN_TAGS}-{_MAX_TAGS} items, got {len(tags)}"
        )

    seen: set[str] = set()
    for tag in tags:
        namespace = _NAMESPACE_OF.get(tag)
        if namespace is None:
            raise ValueError(f"'{tag}' is not a valid tag")
        if namespace in seen:
            raise ValueError(f"duplicate {namespace} tag: '{tag}'")
        seen.add(namespace)

    if "ACTION" not in seen:
        raise ValueError("missing required ACTION tag")
    if not seen & {"FOR", "FROM"}:
        raise ValueError("missing FOR or FROM tag")
