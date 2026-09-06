"""W4 tag validation.

Enforces structural rules for tool tag collections:
    - Every item must be a Tag instance produced by a defined namespace.
    - No namespace may appear more than once.
    - At most four tags total (one per namespace, W4 ceiling).
"""

from __future__ import annotations

from .tags import Tag

_MAX_TAGS = 4


def validate_tags(tags: list[Tag]) -> None:
    """Validate a tool tag list against W4 policy rules.

    All four namespaces are optional. Empty tag lists are valid.

    Args:
        tags: Tag list to validate.

    Raises:
        TypeError: If any item is not a Tag instance produced by a namespace.
        ValueError: If the list exceeds four tags, or if any namespace
            appears more than once.
    """
    if not tags:
        return

    _check_all_are_tags(tags)
    _check_max_count(tags)
    _check_no_duplicate_namespaces(tags)


def _check_all_are_tags(tags: list[Tag]) -> None:
    """Validate that all items are Tag instances."""
    for item in tags:
        if not isinstance(item, Tag):
            raise TypeError(
                f"Tags must be Tag instances produced by a policy namespace "
                f"(what, who, when, where). Got: {type(item).__name__!r} ({item!r}). "
                f"Use the namespace directly, e.g. what.extraction."
            )


def _check_max_count(tags: list[Tag]) -> None:
    """Validate that tag count does not exceed the W4 ceiling."""
    if len(tags) > _MAX_TAGS:
        raise ValueError(
            f"A tool may have at most {_MAX_TAGS} tags (one per W4 namespace). "
            f"Got {len(tags)}: {tags!r}."
        )


def _check_no_duplicate_namespaces(tags: list[Tag]) -> None:
    """Validate that no namespace appears more than once."""
    seen: dict[str, Tag] = {}

    for tag in tags:
        if tag.namespace in seen:
            raise ValueError(
                f"Namespace '{tag.namespace}' appears more than once. "
                f"First: {seen[tag.namespace]!r}, duplicate: {tag!r}. "
                f"Each W4 namespace may be used at most once per tool."
            )
        seen[tag.namespace] = tag
