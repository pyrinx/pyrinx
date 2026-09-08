"""Resolve available tools for an agent step using policy.

Filters the tool registry to tools matching the policy requirements for a
given agent step, groups results by category, and returns a JSON summary.
"""

import json
from collections import defaultdict
from dataclasses import dataclass

from core.agent_state import AgentStep
from tools.policy.categories import ToolCategory
from tools.policy.policy import TOOL_POLICY


@dataclass(frozen=True, slots=True)
class ToolPointer:
    """A lightweight reference to an available tool.

    Describes an available tool for use in an agent step, including its
    name, description, category, and classification tags.

    Attributes:
        tool_name: Unique identifier for the tool.
        tool_desc: Human-friendly description of what the tool does.
        category: ToolCategory indicating the tool's purpose.
        tags: Frozenset of W4 tags classifying the tool.
    """

    tool_name: str
    tool_desc: str
    category: ToolCategory
    tags: frozenset[str]


def resolve_tool_pointers(step: AgentStep) -> str:
    """Return a JSON string of tools available for the given agent step.

    Consults TOOL_POLICY to determine allowed categories, filters the tool
    registry to matching tools, and groups results by category. Deduplicates
    tool names and tags within each category.

    Args:
        step: The current agent step.

    Returns:
        A JSON string with category information, deduplicated tool names,
        and tag values. Empty collections if no tools match the policy.
    """
    from tools.registry import REGISTRY

    categories = TOOL_POLICY.get(step, frozenset())

    tools = [
        tool
        for tool in REGISTRY.values()
        if getattr(tool, "category", None) in categories
    ]

    tools.sort(key=lambda t: t.name)

    grouped: dict[str, dict] = defaultdict(lambda: {"tools": set(), "tags": set()})

    for tool in tools:
        key = tool.category.value
        grouped[key]["tools"].add(tool.name)
        grouped[key]["tags"].update(tool.tags)

    all_tools: list[str] = sorted(
        {t for data in grouped.values() for t in data["tools"]}
    )
    all_tags: list[str] = [
        str(tag)
        for tag in sorted({tag for data in grouped.values() for tag in data["tags"]})
    ]

    return json.dumps(
        {
            "category": step.value,
            "tools": all_tools,
            "tags": all_tags,
        }
    )
