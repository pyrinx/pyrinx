"""Discoverable tool registry and dispatch utilities.

Provides tool discovery from the tools.definitions package, a registry for
registered tools, and dispatch logic for invoking tools by name.

The discovery process:
    1. Iterates through submodules under tools.definitions.
    2. Imports each submodule's tool.py module.
    3. Registers any ToolDef instance found in the TOOL variable.

The dispatch process:
    1. Looks up the tool by name in the registry.
    2. Parses arguments as JSON if needed.
    3. Invokes the tool's handler with arguments and context.
    4. Returns the result as a JSON string.
"""

import importlib
import json
import pkgutil
from collections.abc import Iterable
from typing import Any

import tools.definitions
from core.agent_context import AppContext
from core.agent_state import AgentStep
from tools.policy.policy import TOOL_POLICY
from tools.registry.types import ToolDef

__all__ = [
    "REGISTRY",
    "ToolDef",
    "discover_tools",
    "dispatch",
    "tool_schemas",
]

# Global registry of discovered tools, keyed by name.
REGISTRY: dict[str, ToolDef] = {}


class DispatchError(Exception):
    """Raised when a tool dispatch fails.

    Wraps exceptions from tool execution, validation errors, or
    misconfigurations (e.g., unknown tool names, invalid JSON).
    """


def discover_tools() -> None:
    """Discover and register tools from the tools.definitions package.

    Iterates through submodules under tools.definitions, imports each
    submodule's tool module, and registers any ToolDef instance found in the
    TOOL variable. Clears the registry before discovering.

    Raises:
        TypeError: If a module's TOOL variable is not a ToolDef instance.
        RuntimeError: If a duplicate tool name is encountered.
    """
    REGISTRY.clear()

    for module_info in pkgutil.iter_modules(tools.definitions.__path__):
        package_name = module_info.name
        module_name = f"tools.definitions.{package_name}.tool"

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # Only skip tool packages that have no tool.py module.
            # Re-raise if the missing module is a dependency of the tool —
            # that indicates a broken installation, not an absent tool file.
            if exc.name != module_name:
                raise
            continue

        tool = getattr(module, "TOOL", None)
        if tool is None:
            continue

        if not isinstance(tool, ToolDef):
            raise TypeError(
                f"{module_name}.TOOL must be a ToolDef instance, "
                f"got {type(tool).__name__}"
            )

        if tool.name in REGISTRY:
            raise RuntimeError(f"Duplicate tool name: {tool.name!r}")

        REGISTRY[tool.name] = tool


def tool_schemas(
    step: AgentStep,
    tags: Iterable[str],
) -> list[dict[str, Any]]:
    """Return filtered tool schemas matching policy categories and tags.

    Filters the registry to tools matching both the policy for the given step
    and the provided tags (intersection match), then returns their schemas
    formatted for dispatch.

    Args:
        step: The current agent step, used to look up allowed categories.
        tags: Iterable of tag values to filter by. A tool is included if at
            least one of its tags has a value matching the query.

    Returns:
        A list of tool schema dicts formatted as OpenAI function definitions.
        Each dict contains type, function name, description, and parameters.
        Results are sorted by tool name.
    """
    allowed_categories = TOOL_POLICY.get(step, frozenset())
    target_tags = set(tags)

    selected_tools = [
        tool
        for tool in REGISTRY.values()
        if tool.category in allowed_categories
        and not target_tags.isdisjoint(str(tag) for tag in tool.tags)
    ]

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in sorted(selected_tools, key=lambda t: t.name)
    ]


def dispatch(
    name: str,
    arguments: dict[str, Any] | str,
    ctx: AppContext,
) -> str:
    """Dispatch a tool by name with provided arguments and context.

    Looks up the tool in the registry, validates arguments, invokes the tool's
    handler, and returns a JSON-encoded result.

    Args:
        name: Tool name (must be registered in REGISTRY). Leading and trailing
            whitespace is stripped.
        arguments: Tool arguments as a dict or JSON string. Must be a JSON
            object / dict when parsed.
        ctx: Application context passed to the tool handler.

    Returns:
        A JSON string representing the tool result. If the handler returns
        a string, it is returned verbatim; otherwise the result is JSON-encoded.

    Raises:
        DispatchError: If the tool name is invalid, unknown, not found in the
            registry, arguments are not valid JSON, the handler raises an
            exception, or the result is not JSON-serializable.
    """
    if not isinstance(name, str) or not name.strip():
        raise DispatchError("Tool name must be a non-empty string.")

    tool = REGISTRY.get(name.strip())
    if tool is None:
        known = ", ".join(sorted(REGISTRY.keys()))
        raise DispatchError(f"Unknown tool {name!r}. Known tools: {known}.")

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise DispatchError(f"Invalid tool arguments JSON: {exc}") from exc

    if not isinstance(arguments, dict):
        raise DispatchError("'arguments' must be a JSON object / dict.")

    try:
        result = tool.handler(arguments, ctx)
    except Exception as exc:
        raise DispatchError(f"{type(exc).__name__}: {exc}") from exc

    if isinstance(result, str):
        return result

    try:
        return json.dumps(result, default=str)
    except TypeError as exc:
        raise DispatchError(f"Tool result is not JSON-serializable: {exc}") from exc


# Populate registry on module import.
discover_tools()
