"""Agent execution state and transition rules.

This module defines the AgentStep state machine and AgentState, a small
dataclass that captures the agent's current session, pointers into domain
objects (hypothesis, evidence, finding, etc.), counters for turns, and a
threading.Event used to request stopping.

The state machine enforces a set of allowed transitions and guards operations
that require an active session. The public API is intentionally small and
side effects (state mutation) are explicit on the AgentState instance.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = ["AgentState", "AgentStep"]


# -- State machine -----------------------------------------------------------
class AgentStep(str, Enum):
    """Named agent workflow steps."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    HYPOTHESIS = "hypothesis"
    SELECT_APPROACH = "select_approach"
    TESTING = "testing"
    EVIDENCE = "evidence"
    FINDING = "finding"
    KNOWLEDGE = "knowledge"
    REPORTING = "reporting"


_TRANSITIONS: dict[AgentStep, frozenset[AgentStep]] = {
    AgentStep.IDLE: frozenset({AgentStep.ANALYZING}),
    AgentStep.ANALYZING: frozenset({AgentStep.HYPOTHESIS, AgentStep.IDLE}),
    AgentStep.HYPOTHESIS: frozenset({AgentStep.SELECT_APPROACH, AgentStep.IDLE}),
    AgentStep.SELECT_APPROACH: frozenset({AgentStep.TESTING, AgentStep.IDLE}),
    AgentStep.TESTING: frozenset({AgentStep.EVIDENCE, AgentStep.IDLE}),
    AgentStep.EVIDENCE: frozenset(
        {
            AgentStep.FINDING,
            AgentStep.HYPOTHESIS,
            AgentStep.IDLE,
        }
    ),
    AgentStep.FINDING: frozenset({AgentStep.KNOWLEDGE, AgentStep.IDLE}),
    AgentStep.KNOWLEDGE: frozenset({AgentStep.REPORTING, AgentStep.IDLE}),
    AgentStep.REPORTING: frozenset({AgentStep.IDLE}),
}

# Steps that require a bound session (anything except IDLE).
_STEPS_REQUIRING_SESSION: frozenset[AgentStep] = frozenset(
    step for step in _TRANSITIONS if step is not AgentStep.IDLE
)

# Field collections used for resets.
_POINTER_FIELDS: tuple[str, ...] = (
    "active_hypothesis_id",
    "active_exchange_id",
    "active_evidence_id",
    "active_finding_id",
    "last_knowledge_id",
)

_COUNTER_FIELDS: tuple[str, ...] = (
    "turn_index",
    "turns_in_step",
)


# -- Utilities ---------------------------------------------------------------
def _require_nonempty(value: str, name: str) -> str:
    """Validate that a string is non-empty after stripping.

    Args:
        value: Input string to validate.
        name: Logical name of the value used in the error message.

    Returns:
        The stripped string.

    Raises:
        ValueError: If the stripped string is empty.
    """
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{name!r} must not be blank")
    return stripped


# -- State container ---------------------------------------------------------
@dataclass
class AgentState:
    """Runtime state for a single agent session.

    Attributes:
        session_id: Bound session identifier or None when unbound.
        target: Target URL/host for the session.
        vuln_class: Vulnerability class under investigation.
        step: Current workflow step.
        active_*: IDs pointing to active domain objects (hypothesis, evidence, ...).
        turn_index: Absolute count of agent turns since bind().
        turns_in_step: Count of turns spent in the current step.
        stop_event: Event that can be set by external code to request stopping.
    """

    session_id: str | None = None
    target: str | None = None
    vuln_class: str | None = None

    step: AgentStep = AgentStep.IDLE

    active_hypothesis_id: str | None = None
    active_exchange_id: str | None = None
    active_evidence_id: str | None = None
    active_finding_id: str | None = None
    last_knowledge_id: str | None = None

    turn_index: int = 0
    turns_in_step: int = 0

    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    # -- Guards and transitions ---------------------------------------------
    def _guard_session(self) -> None:
        """Raise if no session is bound to this state."""
        if not self.session_id:
            raise RuntimeError("operation requires a bound session — call bind() first")

    def advance(self, next_step: AgentStep) -> None:
        """Advance the agent to the next workflow step.

        The method validates the requested step, enforces session requirements
        for steps that need one, and resets per-step counters.

        Args:
            next_step: Desired AgentStep to transition to.

        Raises:
            TypeError: If next_step is not an AgentStep.
            ValueError: If the transition is not allowed from the current step.
            RuntimeError: If the next step requires a session but none is bound.
        """
        if not isinstance(next_step, AgentStep):
            raise TypeError(
                f"next_step must be AgentStep, got {type(next_step).__name__!r}"
            )

        if next_step == self.step:
            return

        if next_step in _STEPS_REQUIRING_SESSION:
            self._guard_session()

        allowed = _TRANSITIONS[self.step]
        if next_step not in allowed:
            allowed_values = sorted(s.value for s in allowed)
            raise ValueError(
                f"illegal transition: {self.step.value!r} → "
                f"{next_step.value!r}; allowed: {allowed_values}"
            )

        self.step = next_step
        self.turns_in_step = 0

    # -- Turn bookkeeping ---------------------------------------------------
    def note_turn(self) -> None:
        """Record a single agent turn (increments overall and per-step counters)."""
        self.turn_index += 1
        self.turns_in_step += 1

    # -- Pointer setters ----------------------------------------------------
    def set_hypothesis(self, hypothesis_id: str | None) -> None:
        """Set or clear the active hypothesis pointer."""
        self.active_hypothesis_id = (
            None
            if hypothesis_id is None
            else _require_nonempty(hypothesis_id, "hypothesis_id")
        )

    def set_exchange(self, exchange_id: str | None) -> None:
        """Set or clear the active exchange pointer."""
        self.active_exchange_id = (
            None
            if exchange_id is None
            else _require_nonempty(exchange_id, "exchange_id")
        )

    def set_evidence(self, evidence_id: str | None) -> None:
        """Set or clear the active evidence pointer."""
        self.active_evidence_id = (
            None
            if evidence_id is None
            else _require_nonempty(evidence_id, "evidence_id")
        )

    def set_finding(self, finding_id: str | None) -> None:
        """Set or clear the active finding pointer."""
        self.active_finding_id = (
            None if finding_id is None else _require_nonempty(finding_id, "finding_id")
        )

    def set_knowledge(self, knowledge_id: str | None) -> None:
        """Record the last knowledge identifier produced by the agent."""
        self.last_knowledge_id = (
            None
            if knowledge_id is None
            else _require_nonempty(knowledge_id, "knowledge_id")
        )

    # -- Session binding ---------------------------------------------------
    def bind(self, session_id: str, target: str, vuln_class: str) -> None:
        """Bind the AgentState to a session and initialize counters.

        The method resets transient state, then sets the provided session values.

        Args:
            session_id: Non-empty session identifier.
            target: Non-empty target URL/host.
            vuln_class: Non-empty vulnerability class name.
        """
        self._reset()
        self.session_id = _require_nonempty(session_id, "session_id")
        self.target = _require_nonempty(target, "target")
        self.vuln_class = _require_nonempty(vuln_class, "vuln_class")

    def unbind(self) -> None:
        """Unbind any session and reset transient state."""
        self._reset()
        self.session_id = None
        self.target = None
        self.vuln_class = None

    def _reset(self) -> None:
        """Reset transient state: step, pointers, counters, and stop event flag."""
        self.step = AgentStep.IDLE

        for field_name in _POINTER_FIELDS:
            setattr(self, field_name, None)

        for field_name in _COUNTER_FIELDS:
            setattr(self, field_name, 0)

        self.stop_event.clear()

    # -- Stop flag ---------------------------------------------------------
    def is_stopped(self) -> bool:
        """Return True when an external stop has been requested."""
        return self.stop_event.is_set()

    # -- Inspection --------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of the current agent state."""
        return {
            "session_id": self.session_id,
            "target": self.target,
            "vuln_class": self.vuln_class,
            "step": self.step.value,
            "active_hypothesis_id": self.active_hypothesis_id,
            "active_exchange_id": self.active_exchange_id,
            "active_evidence_id": self.active_evidence_id,
            "active_finding_id": self.active_finding_id,
            "last_knowledge_id": self.last_knowledge_id,
            "turn_index": self.turn_index,
            "turns_in_step": self.turns_in_step,
            "stopped": self.is_stopped(),
        }
