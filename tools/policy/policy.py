"""Default tool policy mapping agent steps to tool categories.

This module defines which tool categories are available for each agent step,
enabling policy-driven tool selection during agent execution.
"""

from core.agent_state import AgentStep
from tools.policy.categories import ToolCategory

# Mapping from agent step to allowed tool categories.
# Tools matching the allowed categories for a step become available to the agent.
TOOL_POLICY: dict[AgentStep, frozenset[ToolCategory]] = {
    AgentStep.IDLE: frozenset({ToolCategory.RECON}),
    AgentStep.ANALYZING: frozenset(
        {
            ToolCategory.RECON,
            ToolCategory.ANALYSIS,
            ToolCategory.KNOWLEDGE,
            ToolCategory.HYPOTHESIS,
            ToolCategory.EVIDENCE,
            ToolCategory.FINDING,
        }
    ),
    AgentStep.HYPOTHESIS: frozenset(
        {
            ToolCategory.KNOWLEDGE,
            ToolCategory.HYPOTHESIS,
            ToolCategory.EVIDENCE,
        }
    ),
    AgentStep.SELECT_APPROACH: frozenset(
        {
            ToolCategory.APPROACH,
            ToolCategory.HYPOTHESIS,
        }
    ),
    AgentStep.TESTING: frozenset(
        {
            ToolCategory.TESTING,
            ToolCategory.ANALYSIS,
            ToolCategory.EVIDENCE,
            ToolCategory.APPROACH,
            ToolCategory.HYPOTHESIS,
        }
    ),
    AgentStep.EVIDENCE: frozenset(
        {
            ToolCategory.EVIDENCE,
            ToolCategory.ANALYSIS,
            ToolCategory.KNOWLEDGE,
        }
    ),
    AgentStep.FINDING: frozenset(
        {
            ToolCategory.FINDING,
            ToolCategory.EVIDENCE,
            ToolCategory.HYPOTHESIS,
        }
    ),
    AgentStep.KNOWLEDGE: frozenset(
        {
            ToolCategory.KNOWLEDGE,
            ToolCategory.EVIDENCE,
            ToolCategory.ANALYSIS,
        }
    ),
    AgentStep.REPORTING: frozenset(
        {
            ToolCategory.REPORTING,
            ToolCategory.FINDING,
            ToolCategory.EVIDENCE,
            ToolCategory.KNOWLEDGE,
        }
    ),
}
