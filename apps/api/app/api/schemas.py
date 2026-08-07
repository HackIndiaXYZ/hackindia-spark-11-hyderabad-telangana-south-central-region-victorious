"""Request and response models for the HTTP API.

Separate from the domain models on purpose. Domain models express engineering
meaning and change when the engineering model changes; these express a wire
contract and change when clients need them to. Collapsing the two would make
every domain refactor a breaking API change.

Response models are also where field selection happens: an artifact list must not
carry every version body, or the Knowledge Base would transfer megabytes to
render a table of contents.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.agents import AgentRun
from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType, ArtifactWithVersion
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import ROLE_TITLES, AgentRole, LifecycleStage, StageStatus
from app.domain.projects import Project

# --- Projects -----------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Everything needed to start a project.

    Two fields, deliberately. `07_System_Architecture.md`: "Every project begins
    with minimal onboarding by asking only for a project name and a brief
    description, allowing users to enter the workspace immediately without
    lengthy setup."
    """

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)


class StageSummary(BaseModel):
    """One stage's progress, for the Engineering Timeline."""

    stage: LifecycleStage
    status: StageStatus
    owner_role: AgentRole | None = None
    owner_title: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    artifact_count: int = 0


class ProjectSummary(BaseModel):
    """A project as it appears in a list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    current_stage: LifecycleStage
    completed_stages: int
    total_stages: int
    artifact_count: int = 0
    pending_approvals: int = 0
    updated_at: datetime

    @property
    def progress(self) -> float:
        return self.completed_stages / self.total_stages if self.total_stages else 0.0

    @classmethod
    def build(
        cls,
        project: Project,
        *,
        artifact_count: int = 0,
        pending_approvals: int = 0,
        total_stages: int = 8,
    ) -> ProjectSummary:
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            current_stage=project.current_stage,
            completed_stages=len(project.completed_stages),
            total_stages=total_stages,
            artifact_count=artifact_count,
            pending_approvals=pending_approvals,
            updated_at=project.updated_at,
        )


class ProjectDetail(ProjectSummary):
    """A project with its full stage timeline."""

    stages: list[StageSummary] = Field(default_factory=list)


# --- Artifacts ----------------------------------------------------------------


class ArtifactSummary(BaseModel):
    """An artifact without its body, for lists and the Knowledge Base."""

    id: str
    project_id: str
    type: ArtifactType
    title: str
    stage: LifecycleStage
    owner_role: AgentRole
    owner_title: str
    status: ArtifactStatus
    current_version: int
    is_stale: bool = Field(
        default=False,
        description=(
            "Computed from the traceability graph, never stored — an artifact is "
            "stale when an inbound edge cites an older version than its upstream "
            "currently has."
        ),
    )
    updated_at: datetime

    @classmethod
    def build(cls, artifact: Artifact, *, is_stale: bool = False) -> ArtifactSummary:
        return cls(
            id=artifact.id,
            project_id=artifact.project_id,
            type=artifact.type,
            title=artifact.title,
            stage=artifact.stage,
            owner_role=artifact.owner_role,
            owner_title=ROLE_TITLES[artifact.owner_role],
            status=artifact.status,
            current_version=artifact.current_version,
            is_stale=is_stale,
            updated_at=artifact.updated_at,
        )


class VersionSummary(BaseModel):
    """One entry of an artifact's version history."""

    version: int
    summary: str
    confidence: float | None
    produced_by_run_id: str | None
    created_at: datetime


class ArtifactDetail(ArtifactSummary):
    """An artifact with one version's content."""

    version: int
    body_markdown: str
    content: dict[str, Any] = Field(default_factory=dict)
    version_summary: str = ""
    confidence: float | None = None
    produced_by_run_id: str | None = None
    is_latest: bool = True
    versions: list[VersionSummary] = Field(default_factory=list)

    @classmethod
    def from_resolved(
        cls,
        resolved: ArtifactWithVersion,
        *,
        is_stale: bool = False,
        versions: list[VersionSummary] | None = None,
    ) -> ArtifactDetail:
        """Build from an artifact resolved together with one of its versions.

        Named differently from ``ArtifactSummary.build`` deliberately: it takes a
        different input type, so overriding would be a Liskov violation dressed
        up as reuse.
        """
        base = ArtifactSummary.build(resolved.artifact, is_stale=is_stale)
        return cls(
            **base.model_dump(),
            version=resolved.version.version,
            body_markdown=resolved.version.body_markdown,
            content=resolved.version.content,
            version_summary=resolved.version.summary,
            confidence=resolved.version.confidence,
            produced_by_run_id=resolved.version.produced_by_run_id,
            is_latest=resolved.is_latest,
            versions=versions or [],
        )


# --- Agents -------------------------------------------------------------------


class AgentCard(BaseModel):
    """One agent's state, as the Organization view renders it.

    `10_UI_UX_Plan.md` requires each agent to show current status, assigned
    responsibilities, current task, confidence level, dependencies, generated
    outputs, and recent decisions. Keyed by stage rather than role because a role
    can own two stages (ADR-0010).
    """

    stage: LifecycleStage
    role: AgentRole
    title: str
    status: str
    task: str = ""
    reasoning_summary: str = ""
    confidence: float | None = None
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    blocked_on: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    total_tokens: int = 0
    duration_seconds: float | None = None
    run_id: str | None = None
    started_at: datetime | None = None

    @classmethod
    def idle(cls, stage: LifecycleStage, role: AgentRole) -> AgentCard:
        """A specialist that has not yet been asked to do anything."""
        return cls(stage=stage, role=role, title=ROLE_TITLES[role], status="idle")

    @classmethod
    def from_run(cls, run: AgentRun) -> AgentCard:
        return cls(
            stage=run.stage,
            role=run.role,
            title=ROLE_TITLES[run.role],
            status=run.status.value,
            task=run.task,
            reasoning_summary=run.reasoning_summary,
            confidence=run.confidence,
            input_artifact_ids=run.input_artifact_ids,
            output_artifact_ids=run.output_artifact_ids,
            blocked_on=run.blocked_on,
            provider=run.provider,
            model=run.model,
            total_tokens=run.token_usage.total,
            duration_seconds=run.duration_seconds,
            run_id=run.id,
            started_at=run.started_at,
        )


# --- Approvals ----------------------------------------------------------------


class ImpactedArtifactView(BaseModel):
    """One artifact inside a change's blast radius, resolved for display."""

    artifact_id: str
    title: str
    type: ArtifactType | None = None
    depth: int
    via_kind: str


class ApprovalView(BaseModel):
    """An approval request with the five fields a reviewer needs.

    `10_UI_UX_Plan.md`: what changed, why it changed, which agents were involved,
    the downstream impact, and the available actions.
    """

    id: str
    project_id: str
    project_name: str = ""
    kind: ApprovalKind
    stage: LifecycleStage
    title: str
    what_changed: str
    why: str
    requested_by: AgentRole
    agents_involved: list[AgentRole] = Field(default_factory=list)
    agent_titles: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactSummary] = Field(default_factory=list)
    impacted: list[ImpactedArtifactView] = Field(default_factory=list)
    status: ApprovalStatus
    feedback: str | None = None
    created_at: datetime
    decided_at: datetime | None = None

    @classmethod
    def build(
        cls,
        request: ApprovalRequest,
        *,
        project_name: str = "",
        artifacts: list[ArtifactSummary] | None = None,
        impacted: list[ImpactedArtifactView] | None = None,
    ) -> ApprovalView:
        return cls(
            id=request.id,
            project_id=request.project_id,
            project_name=project_name,
            kind=request.kind,
            stage=request.stage,
            title=request.title,
            what_changed=request.what_changed,
            why=request.why,
            requested_by=request.requested_by,
            agents_involved=request.agents_involved,
            agent_titles=[ROLE_TITLES[role] for role in request.agents_involved],
            artifacts=artifacts or [],
            impacted=impacted or [],
            status=request.status,
            feedback=request.feedback,
            created_at=request.created_at,
            decided_at=request.decided_at,
        )


class ReviseArtifactRequest(BaseModel):
    """A human's revision of an engineering artifact.

    Appends a version; it never edits one. The version downstream agents consumed
    must stay readable, and the new version is what makes their work stale.
    """

    body_markdown: str = Field(min_length=1)
    summary: str = Field(
        default="",
        max_length=300,
        description="What changed, shown in version history and the impact preview.",
    )
    content: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Structured content, if the caller has it. Omitted for a prose edit, "
            "in which case the markdown is the truth for this version."
        ),
    )


class ApprovalDecisionRequest(BaseModel):
    """A human's decision on an approval gate."""

    decision: ApprovalStatus = Field(
        description="approved, rejected, or changes_requested."
    )
    feedback: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "Required when not approving. Fed back into the agent's context on "
            "re-run, so a rejection teaches rather than repeats."
        ),
    )


# --- Events and orchestration -------------------------------------------------


class EventView(BaseModel):
    """One entry of the engineering timeline."""

    id: str
    type: EventType
    stage: LifecycleStage | None = None
    role: AgentRole | None = None
    role_title: str | None = None
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def build(cls, event: ProjectEvent) -> EventView:
        return cls(
            id=event.id,
            type=event.type,
            stage=event.stage,
            role=event.role,
            role_title=ROLE_TITLES[event.role] if event.role else None,
            summary=event.summary,
            payload=event.payload,
            created_at=event.created_at,
        )


class AdvanceResponse(BaseModel):
    """The outcome of asking the organization to make progress."""

    project_id: str
    executed_stages: list[LifecycleStage] = Field(default_factory=list)
    halt_action: str | None = None
    halt_reason: str = ""
    pending_approval_id: str | None = None
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


# --- Traceability -------------------------------------------------------------


class TraceNode(BaseModel):
    """One artifact in the traceability graph."""

    id: str
    title: str
    type: ArtifactType
    stage: LifecycleStage
    role: AgentRole
    version: int
    is_stale: bool = False


class TraceEdgeView(BaseModel):
    """One dependency in the traceability graph."""

    id: str
    upstream_artifact_id: str
    downstream_artifact_id: str
    kind: str
    upstream_version: int
    current_upstream_version: int
    is_stale: bool = False
    rationale: str = ""


class TraceGraph(BaseModel):
    """The full traceability graph for a project."""

    project_id: str
    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdgeView] = Field(default_factory=list)
    stale_artifact_ids: list[str] = Field(default_factory=list)
