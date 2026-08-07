"""Agent runs and the structured message contract between agents.

`05_AI_Agent_Architecture.md` specifies that "agents communicate using structured
messages instead of free-form conversations", with every interaction carrying
sender, receiver, task, context, dependencies, decision, confidence, and required
actions. :class:`AgentMessage` is that contract, expressed as a type.

:class:`AgentRun` is the persisted record of one agent doing one piece of work.
It is what the Agent Organization view renders, and what
`10_UI_UX_Plan.md` requires each agent to expose: current status, assigned
responsibilities, current task, confidence level, dependencies, generated
outputs, recent decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import AgentRole, LifecycleStage


class AgentRunStatus(StrEnum):
    """What an agent is doing right now.

    These are exactly the states `07_System_Architecture.md` requires the
    workspace to distinguish: "whether an agent is active, waiting for
    dependencies, requesting approval, reviewing another agent's work, or idle".
    """

    QUEUED = "queued"
    ACTIVE = "active"
    WAITING_ON_DEPENDENCY = "waiting_on_dependency"
    AWAITING_APPROVAL = "awaiting_approval"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Whether no further transition is expected."""
        return self in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }

    @property
    def is_running(self) -> bool:
        """Whether the agent is occupying orchestration capacity."""
        return self in {
            AgentRunStatus.ACTIVE,
            AgentRunStatus.REVIEWING,
        }


class AgentMessage(BaseModel):
    """A structured communication between two agents.

    Routed through the Executive AI rather than sent peer to peer, per
    `05_AI_Agent_Architecture.md`: "Agents should avoid directly modifying each
    other's internal state and instead exchange structured messages through the
    Executive AI (Engineering Director)."
    """

    model_config = ConfigDict(frozen=True)

    sender: AgentRole
    receiver: AgentRole
    task: str = Field(description="What the receiver is being asked to do.")

    context_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts the receiver should read. Resolved from shared memory.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Artifact IDs that must exist and be approved before proceeding.",
    )

    decision: str | None = Field(
        default=None, description="The decision being communicated, if any."
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    required_actions: list[str] = Field(
        default_factory=list, description="What the receiver must do in response."
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TokenUsage(BaseModel):
    """Tokens consumed by one agent run.

    Recorded because `12_Risk_Analysis.md` rates High Token Consumption a Medium
    risk. Measuring it is the precondition for the caching decision deferred in
    ADR-0005 — the intent is to decide from data rather than assumption.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class AgentRun(BaseModel):
    """One agent performing one unit of engineering work.

    The unit of observability for the whole platform: the Agent Organization view
    renders live runs, the Engineering Timeline renders completed ones, and every
    artifact version points back to the run that produced it.
    """

    id: str = Field(default_factory=lambda: new_id(IdPrefix.AGENT_RUN))
    project_id: str
    role: AgentRole
    stage: LifecycleStage

    status: AgentRunStatus = AgentRunStatus.QUEUED
    task: str = Field(default="", description="Human-readable current task.")

    reasoning_summary: str = Field(
        default="",
        description=(
            "Why the agent decided what it did, in prose. `12_Risk_Analysis.md` "
            "names explainable reasoning as the mitigation for loss of user trust; "
            "this is the field the workspace surfaces to earn it."
        ),
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    input_artifact_ids: list[str] = Field(
        default_factory=list, description="Artifacts read as context."
    )
    output_artifact_ids: list[str] = Field(
        default_factory=list, description="Artifacts written."
    )
    blocked_on: list[str] = Field(
        default_factory=list,
        description="Artifact IDs the run is waiting for, shown as its dependencies.",
    )

    provider: str | None = Field(default=None, description="LLM provider used.")
    model: str | None = Field(default=None)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    requires_approval: bool = Field(
        default=False,
        description=(
            "Whether the agent judged its own output too consequential to proceed "
            "on without a human. `09_MVP_Roadmap.md` requires approval of "
            "technology selection and major engineering decisions, neither of "
            "which is stage-shaped — they arise from what an agent concludes, so "
            "the agent has to be able to raise the gate itself."
        ),
    )
    approval_reason: str = Field(
        default="", description="Why the agent asked for review."
    )

    correlation_id: str | None = Field(
        default=None,
        description=(
            "Ties this run to the HTTP request that triggered it and to every log "
            "line it emitted."
        ),
    )
    error: str | None = Field(default=None, description="Failure detail, if failed.")

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock duration, or ``None`` while still running."""
        if self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()
