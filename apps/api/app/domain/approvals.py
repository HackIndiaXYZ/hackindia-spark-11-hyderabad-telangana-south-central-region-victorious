"""Human approval gates.

Required by five specification documents — `05`, `06`, `09`, `10`, and `12` —
which makes this the least negotiable feature in the MVP.

:class:`ApprovalRequest` carries exactly the five fields `10_UI_UX_Plan.md`
requires the Approval Center to show: what changed, why it changed, which agents
were involved, the downstream impact, and the available actions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.traceability import ImpactAnalysis


class ApprovalKind(StrEnum):
    """What is being approved.

    The set named in `09_MVP_Roadmap.md` ("Users must approve: Requirements,
    Architecture, Technology Stack, Major Engineering Decisions, Final Code
    Generation") plus requirement changes, which trigger the re-synchronisation
    flow in Milestone 8.
    """

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    TECHNOLOGY_SELECTION = "technology_selection"
    ENGINEERING_DECISION = "engineering_decision"
    CODE_GENERATION = "code_generation"
    REQUIREMENT_CHANGE = "requirement_change"
    RESYNCHRONISATION = "resynchronisation"


class ApprovalStatus(StrEnum):
    """Outcome of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"

    @property
    def is_decided(self) -> bool:
        return self is not ApprovalStatus.PENDING

    @property
    def unblocks_progress(self) -> bool:
        """Whether the orchestrator may proceed past this gate."""
        return self is ApprovalStatus.APPROVED


class ApprovalRequest(BaseModel):
    """A decision suspended pending human review.

    While one of these is pending, the orchestration graph is genuinely halted —
    no downstream artifact is written. `12_Risk_Analysis.md` lists Excessive
    Automation as a High risk mitigated by "human approval checkpoints"; a gate
    that merely notified the user while work continued would not be one.
    """

    id: str = Field(default_factory=lambda: new_id(IdPrefix.APPROVAL))
    project_id: str
    kind: ApprovalKind
    stage: LifecycleStage

    title: str
    what_changed: str = Field(description="Plain-language description of the change.")
    why: str = Field(description="Reasoning that produced it.")

    requested_by: AgentRole
    agents_involved: list[AgentRole] = Field(
        default_factory=list, description="Every role that contributed."
    )

    artifact_ids: list[str] = Field(
        default_factory=list, description="Artifacts under review."
    )
    impact: ImpactAnalysis | None = Field(
        default=None,
        description=(
            "Downstream blast radius, computed before the decision so the reviewer "
            "sees the consequences of approving rather than discovering them after."
        ),
    )

    status: ApprovalStatus = ApprovalStatus.PENDING
    feedback: str | None = Field(
        default=None,
        description=(
            "Reviewer's note on rejection or change request. Fed back into the "
            "agent's context on re-run, so a rejection teaches rather than repeats."
        ),
    )
    decided_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_pending(self) -> bool:
        return self.status is ApprovalStatus.PENDING
