"""Orchestration graph state.

Deliberately thin. `15_Development_Guidelines.md` makes shared memory the single
source of truth, so this envelope carries only what one traversal needs to route
itself — never project knowledge. Every node reads current facts from shared
memory rather than from accumulated state.

That choice is what makes the workflow resumable across process restarts:
resuming is re-entering the graph, which re-reads memory. See ADR-0009.
"""

from __future__ import annotations

from typing import TypedDict

#: Nodes traversed per stage (coordinate + execute), times nine stages, plus
#: gates and a margin. LangGraph's default of 25 would halt a healthy run
#: partway through, which reads as a mysterious stall rather than a limit.
RECURSION_LIMIT = 120


class OrchestrationState(TypedDict, total=False):
    """State carried through one traversal of the workflow graph."""

    project_id: str

    next_action: str | None
    """The :class:`~app.orchestration.executive.CoordinationAction` the Executive
    decided on. The single field routing reads, so a new action cannot
    accidentally fall through to execution."""

    stage: str | None
    """Stage the current decision concerns. ``None`` before the first assessment."""

    gate: str | None
    """The :class:`~app.domain.approvals.ApprovalKind` blocking the stage, when
    the decision was to request approval."""

    executed_stages: list[str]
    """Stages executed during this traversal, for the returned outcome."""

    halted: bool
    halt_action: str | None
    """The :class:`~app.orchestration.executive.CoordinationAction` that stopped it."""

    halt_reason: str | None
    pending_approval_id: str | None

    conflicts: list[dict[str, object]]
    """Conflicts observed at the halt, serialised for the API response."""

    error: str | None
    """Set when a dispatched agent failed. The traversal stops; the run record
    and the failure event are written by the agent itself."""
