"""Project events — the engineering activity record.

Every meaningful change is recorded as an event. Events serve three consumers
from one write:

- the **Engineering Timeline**, which `10_UI_UX_Plan.md` requires to preserve
  completed stages so engineering history stays visible;
- the **live agent stream** in Milestone 6, which pushes these to the browser;
- the **audit trail**, since events are append-only and never revised.

Events describe what happened. They are not the source of truth for current
state — that is the artifact model. Deriving state by replaying events would be
event sourcing, which this is deliberately not: it adds reconstruction complexity
for a benefit the artifact version history already provides.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import AgentRole, LifecycleStage


class EventType(StrEnum):
    """What happened.

    Covers the notification triggers listed in `06_Product_Architecture.md`:
    agent completion, approval requests, architecture conflicts, requirement
    changes, test failures, documentation updates, dependency conflicts.
    """

    PROJECT_CREATED = "project_created"

    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_BLOCKED = "stage_blocked"

    AGENT_STARTED = "agent_started"
    AGENT_PROGRESS = "agent_progress"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_REVISED = "artifact_revised"
    ARTIFACT_APPROVED = "artifact_approved"
    ARTIFACT_MARKED_STALE = "artifact_marked_stale"
    ARTIFACT_REVIEWED = "artifact_reviewed"

    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    CHANGES_REQUESTED = "changes_requested"

    CONFLICT_DETECTED = "conflict_detected"
    IMPACT_ANALYSED = "impact_analysed"


class ProjectEvent(BaseModel):
    """One recorded occurrence in a project's engineering history."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: new_id(IdPrefix.EVENT))
    project_id: str
    type: EventType

    stage: LifecycleStage | None = None
    role: AgentRole | None = None

    summary: str = Field(description="One line, rendered directly in the timeline.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific detail: artifact IDs, versions, impact counts.",
    )

    correlation_id: str | None = Field(
        default=None, description="Ties the event to the request and logs that produced it."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
