"""Tools registry module for tool discovery and dispatch.

Provides the central registry for all discoverable tools, tool schema filtering,
and tool dispatch logic for agent execution.
"""

from tools.registry.registry import (
    REGISTRY,
    DispatchError,
    discover_tools,
    dispatch,
    tool_schemas,
)
from tools.registry.types import ToolDef

__all__ = [
    "REGISTRY",
    "DispatchError",
    "ToolDef",
    "discover_tools",
    "dispatch",
    "tool_schemas",
]
