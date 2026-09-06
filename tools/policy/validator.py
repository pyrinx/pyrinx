"""W4 tag validation.

Enforces structural rules for tool tag collections:
    - At least one tag is required.
    - Every item must be a Tag instance produced by a defined namespace.
    - Every tag's namespace must be one of the four W4 namespaces (what, who, when, where).
    - Every tag's value must be a defined member of its namespace.
    - No namespace may appear more than once.
    - At most four tags total (one per namespace, W4 ceiling).
"""

from __future__ import annotations

from .tags import NAMESPACE_QUESTIONS, Tag, _What, _When, _Where, _Who

_MAX_TAGS = 4

# Sourced from namespace classes — single source of truth for valid members.
_NAMESPACE_MEMBERS: dict[str, frozenset[str]] = {
    "what": frozenset(k for k, v in vars(_What).items() if isinstance(v, Tag)),
    "who": frozenset(k for k, v in vars(_Who).items() if isinstance(v, Tag)),
    "when": frozenset(k for k, v in vars(_When).items() if isinstance(v, Tag)),
    "where": frozenset(k for k, v in vars(_Where).items() if isinstance(v, Tag)),
}

_VALID_NAMESPACES: frozenset[str] = frozenset(NAMESPACE_QUESTIONS)


def validate_tags(tags: list[Tag]) -> None:
    """Validate a tool tag list against W4 policy rules.

    All four namespaces are optional, but at least one tag is required.

    Args:
        tags: Tag list to validate. Must contain between 1 and 4 tags.

    Raises:
        TypeError: If any item is not a ``Tag`` instance.
        ValueError: If the list is empty, exceeds four tags, contains an
            unknown namespace or value, or repeats a namespace.
    """
    _check_min_count(tags)
    _check_all_are_tags(tags)
    _check_all_are_registered(tags)
    _check_max_count(tags)
    _check_no_duplicate_namespaces(tags)


def _check_min_count(tags: list[Tag]) -> None:
    if not tags:
        raise ValueError(
            "A tool must have at least one tag. "
            "Use the policy namespaces, e.g. tags=[what.extraction]."
        )


def _check_all_are_tags(tags: list[Tag]) -> None:
    """Validate that all items are Tag instances."""
    for item in tags:
        if not isinstance(item, Tag):
            raise TypeError(
                f"Tags must be Tag instances produced by a policy namespace "
                f"(what, who, when, where). Got: {type(item).__name__!r} ({item!r}). "
                f"Use the namespace directly, e.g. what.extraction."
            )


def _check_all_are_registered(tags: list[Tag]) -> None:
    for tag in tags:
        if tag.namespace not in _VALID_NAMESPACES:
            raise ValueError(
                f"'{tag.namespace}' is not a valid W4 namespace. "
                f"Valid namespaces: {sorted(_VALID_NAMESPACES)}. "
                f"Use the policy namespace instances directly, e.g. what.extraction."
            )

        valid_values = _NAMESPACE_MEMBERS[tag.namespace]
        if tag.value not in valid_values:
            raise ValueError(
                f"'{tag.value}' is not a defined member of the '{tag.namespace}' namespace. "
                f"Defined members: {sorted(valid_values)}. "
                f"Use the namespace instance directly, e.g. {tag.namespace}.{min(valid_values)}."
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
