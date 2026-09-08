"""Tool registry type definitions.

Defines ToolDef, the descriptor used to register a tool with the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
        tags: 2 to 3 tags describing the tool. Exactly one ACTION tag is
            required, plus at least one of FOR / FROM::

                from tools.policy.tags import ACTION, FOR, FROM

                tags = [ACTION.extract, FOR.link, FROM.html]

    Raises:
        ValueError: If tags violate the tag policy (see validate_tags).
    """

    name: str
    description: str
    category: Any
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate tags on construction."""
        validate_tags(self.tags)
