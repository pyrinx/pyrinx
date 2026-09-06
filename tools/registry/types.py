"""Tool registry type definitions.

Defines ToolDef, the descriptor used to register a tool with the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tools.policy.tags import Tag
from tools.policy.validator import validate_tags


@dataclass
class ToolDef:
    """Descriptor for a registerable tool.

    Encapsulates all metadata and handler logic required to register and
    dispatch a tool. Validates tags on construction.

    Attributes:
        name: Unique tool identifier used by the registry.
        description: Human-readable summary of what the tool does.
        category: Broad classification used for policy and routing.
        parameters: JSON-schema-compatible parameter definition.
        handler: Callable invoked by the registry dispatcher. Receives
            a dict of arguments and an AppContext.
        tags: Optional W4 classification tags. Maximum four tags, at most
            one per namespace (what, who, when, where). Produce tags via
            the policy namespaces::

                from tools.policy.tags import what, who, when, where

                tags = [what.extraction, who.html, when.response, where.body]

    Raises:
        TypeError: If any tag is not a Tag instance.
        ValueError: If tags exceed four items or repeat a namespace.
    """

    name: str
    description: str
    category: Any
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    tags: list[Tag] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate tags on construction."""
        validate_tags(self.tags)
