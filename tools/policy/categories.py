"""Tool categories used to group tools by purpose.

Tool categories enable policy-driven tool selection, allowing the agent to
choose appropriate tools based on its current step or task phase. Each category
represents a distinct role or phase in the investigation/analysis workflow.
"""

from enum import StrEnum


class ToolCategory(StrEnum):
    """Categories for tools to aid policy and discovery.

    Each category aligns with a phase in the agent's workflow:
    - RECON: Initial reconnaissance and data gathering.
    - ANALYSIS: Analysis and processing of gathered data.
    - KNOWLEDGE: Knowledge retrieval and fact-checking.
    - HYPOTHESIS: Hypothesis formation and structuring.
    - APPROACH: Strategic approach selection and planning.
    - TESTING: Test execution and validation.
    - EVIDENCE: Evidence collection and documentation.
    - FINDING: Finding formulation and conclusion.
    - REPORTING: Report generation and communication.
    """

    RECON = "recon"
    ANALYSIS = "analysis"
    KNOWLEDGE = "knowledge"
    HYPOTHESIS = "hypothesis"
    APPROACH = "approach"
    TESTING = "testing"
    EVIDENCE = "evidence"
    FINDING = "finding"
    REPORTING = "reporting"
