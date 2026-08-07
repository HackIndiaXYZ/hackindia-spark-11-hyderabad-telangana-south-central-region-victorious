"""Project lifecycle endpoints.

The whole workspace is served from here: creating a project, advancing it,
reading its artifacts, agents, approvals, timeline, and traceability graph.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Query, status

from app.api import views
from app.api.deps import MemoryDep, RunnerDep
from app.api.schemas import (
    AdvanceResponse,
    AgentCard,
    ApprovalDecisionRequest,
    ApprovalView,
    ArtifactDetail,
    ArtifactSummary,
    CreateProjectRequest,
    EventView,
    ImpactPreview,
    ProjectDetail,
    ProjectReviewSummary,
    ProjectSummary,
    ReviseArtifactRequest,
    TraceGraph,
)
from app.core.logging import get_logger
from app.domain.approvals import ApprovalStatus
from app.domain.artifacts import ArtifactType, ArtifactVersion
from app.domain.errors import ValidationError
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import LifecycleStage
from app.domain.projects import Project

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    request: CreateProjectRequest, memory: MemoryDep
) -> ProjectSummary:
    """Start a project from a name and a description.

    Nothing else is asked for. `07_System_Architecture.md` requires the user to
    enter the workspace immediately, with the organization discovering
    requirements from there rather than through an upfront interview.
    """
    project = await memory.projects.create(
        Project(name=request.name, description=request.description)
    )

    await memory.events.append(
        ProjectEvent(
            project_id=project.id,
            type=EventType.PROJECT_CREATED,
            summary=f"Project created: {project.name}",
            payload={"name": project.name},
        )
    )

    logger.info("Project created", extra={"project_id": project.id})
    return await views.project_summary(memory, project.id)


@router.get("", response_model=list[ProjectSummary], summary="List projects")
async def list_projects(
    memory: MemoryDep, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[ProjectSummary]:
    return await views.list_projects(memory, limit=limit)


@router.get("/{project_id}", response_model=ProjectDetail, summary="Project detail")
async def get_project(project_id: str, memory: MemoryDep) -> ProjectDetail:
    return await views.project_detail(memory, project_id)


@router.post(
    "/{project_id}/advance",
    response_model=AdvanceResponse,
    summary="Advance the engineering workflow",
)
async def advance_project(project_id: str, runner: RunnerDep) -> AdvanceResponse:
    """Let the organization work until it needs a human.

    Returns when an approval gate is reached, a blocking conflict is found, or
    the lifecycle completes. Calling again after a decision resumes — state lives
    in shared memory, not in the graph (ADR-0009).
    """
    outcome = await runner.advance(project_id)

    return AdvanceResponse(
        project_id=outcome.project_id,
        executed_stages=outcome.executed_stages,
        halt_action=outcome.halt_action.value if outcome.halt_action else None,
        halt_reason=outcome.halt_reason,
        pending_approval_id=outcome.pending_approval_id,
        conflicts=outcome.conflicts,
        error=outcome.error,
    )


@router.get(
    "/{project_id}/artifacts",
    response_model=list[ArtifactSummary],
    summary="List engineering artifacts",
)
async def list_artifacts(
    project_id: str,
    memory: MemoryDep,
    stage: LifecycleStage | None = None,
    # Exposed as `?type=` because that reads naturally in a URL, while the
    # parameter avoids shadowing the builtin.
    artifact_type: Annotated[ArtifactType | None, Query(alias="type")] = None,
) -> list[ArtifactSummary]:
    return await views.list_artifacts(
        memory, project_id, stage=stage, artifact_type=artifact_type
    )


@router.get(
    "/{project_id}/agents",
    response_model=list[AgentCard],
    summary="The AI engineering organization",
)
async def get_organization(project_id: str, memory: MemoryDep) -> list[AgentCard]:
    """Every specialist and its current state, including those not yet running."""
    return await views.organization(memory, project_id)


@router.get(
    "/{project_id}/approvals",
    response_model=list[ApprovalView],
    summary="Approval requests",
)
async def list_approvals(
    project_id: str, memory: MemoryDep, pending: bool = False
) -> list[ApprovalView]:
    return await views.list_approvals(memory, project_id, pending_only=pending)


@router.get(
    "/{project_id}/events",
    response_model=list[EventView],
    summary="Engineering timeline",
)
async def list_events(
    project_id: str,
    memory: MemoryDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    after: str | None = None,
) -> list[EventView]:
    """Activity oldest first. ``after`` resumes from a known event id."""
    return await views.list_events(memory, project_id, limit=limit, after_id=after)


@router.get(
    "/{project_id}/reviews",
    response_model=ProjectReviewSummary,
    summary="Helix Review — engineering quality of every artifact",
)
async def get_reviews(project_id: str, memory: MemoryDep) -> ProjectReviewSummary:
    """Overall score, per-specialist scores, recommendations, and full history.

    Reviews come from the organization's own review layer. Helix — Mutagent's ADL
    conductor — specifies and evaluates that reviewer at development time, and is
    deliberately absent from this request path: `07_System_Architecture.md` keeps
    Mutagent outside the runtime execution path.
    """
    summary: ProjectReviewSummary = await views.project_reviews(memory, project_id)
    return summary


@router.get(
    "/{project_id}/traceability",
    response_model=TraceGraph,
    summary="Traceability graph",
)
async def get_traceability(project_id: str, memory: MemoryDep) -> TraceGraph:
    """Every artifact and the dependencies between them, with staleness resolved."""
    return await views.trace_graph(memory, project_id)


@router.get(
    "/{project_id}/artifacts/{artifact_id}",
    response_model=ArtifactDetail,
    summary="Artifact detail",
)
async def get_artifact(
    project_id: str,
    artifact_id: str,
    memory: MemoryDep,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> ArtifactDetail:
    """One artifact with its content and full version history.

    Omitting ``version`` returns the latest. Any earlier version remains readable
    exactly as the agent that consumed it saw it (ADR-0007).
    """
    return await views.artifact_detail(memory, artifact_id, version=version)


@router.get(
    "/{project_id}/artifacts/{artifact_id}/impact",
    response_model=ImpactPreview,
    summary="What changing this artifact would affect",
)
async def get_impact(
    project_id: str, artifact_id: str, memory: MemoryDep
) -> ImpactPreview:
    """Compute the blast radius of a change without making one.

    The question `04_Existing_Solutions.md` says no tool answers, asked *before*
    the change rather than reported after it.
    """
    return await views.impact_preview(memory, project_id, artifact_id)


@router.post(
    "/{project_id}/artifacts/{artifact_id}/revise",
    response_model=ArtifactDetail,
    summary="Revise an artifact",
)
async def revise_artifact(
    project_id: str,
    artifact_id: str,
    memory: MemoryDep,
    revision: Annotated[ReviseArtifactRequest, Body()],
) -> ArtifactDetail:
    """Append a human-authored revision to an artifact.

    The change a user makes when a requirement turns out to be wrong. It appends
    a version rather than editing in place, so the version the agents downstream
    consumed stays readable, and every traceability edge pointing at this
    artifact now cites an older version than it currently has — which is exactly
    how those downstream artifacts become stale (ADR-0007).

    Nothing is regenerated here. The impact is computed and returned so the user
    can see the blast radius before deciding what to do about it.
    """
    artifact = await memory.artifacts.get(artifact_id)

    if artifact.project_id != project_id:
        raise ValidationError(
            "Artifact does not belong to this project",
            details={"artifact_id": artifact_id, "project_id": project_id},
        )

    await memory.artifacts.append_version(
        artifact_id,
        ArtifactVersion(
            artifact_id=artifact_id,
            version=1,  # Assigned by the repository.
            body_markdown=revision.body_markdown,
            content=artifact_content_or_empty(revision),
            summary=revision.summary or "Revised by a human",
        ),
    )

    impact = await memory.traces.analyse_impact(project_id, artifact_id)

    await memory.events.append(
        ProjectEvent(
            project_id=project_id,
            type=EventType.ARTIFACT_REVISED,
            stage=artifact.stage,
            summary=f"{artifact.title} was revised — {len(impact.impacted)} artifacts affected",
            payload={
                "artifact_id": artifact_id,
                "impacted_artifact_ids": impact.artifact_ids,
            },
        )
    )

    logger.info(
        "Artifact revised",
        extra={
            "project_id": project_id,
            "artifact_id": artifact_id,
            "impacted": len(impact.impacted),
        },
    )
    return await views.artifact_detail(memory, artifact_id)


def artifact_content_or_empty(revision: ReviseArtifactRequest) -> dict[str, object]:
    """Structured content for a human revision.

    A person edits prose, not the structured fields an agent emits. Carrying the
    previous structure forward would leave it describing text that no longer
    exists, so it is dropped and the markdown becomes the truth for this version.
    """
    return dict(revision.content or {})


approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])


@approvals_router.post(
    "/{approval_id}/decision",
    response_model=ApprovalView,
    summary="Decide an approval request",
)
async def decide_approval(
    approval_id: str,
    memory: MemoryDep,
    runner: RunnerDep,
    decision: Annotated[ApprovalDecisionRequest, Body()],
) -> ApprovalView:
    """Approve, reject, or request changes.

    Rejecting requires feedback: it is fed back into the agent's context on
    re-run, so a rejection teaches rather than repeats. Rejecting without saying
    why would leave the organization to guess.

    The consequences of a decision — approving the reviewed artifacts, or
    reopening the stage that produced them — belong to the Executive AI, which
    coordinates the organization. This endpoint only validates and delegates.
    """
    if decision.decision is ApprovalStatus.PENDING:
        raise ValidationError(
            "A decision cannot be 'pending'",
            details={"allowed": ["approved", "rejected", "changes_requested"]},
        )

    if not decision.decision.unblocks_progress and not (decision.feedback or "").strip():
        raise ValidationError(
            "Feedback is required when not approving",
            details={"decision": decision.decision.value},
        )

    request = await runner.executive.record_decision(
        approval_id, decision.decision, decision.feedback
    )

    views_list = await views.list_approvals(memory, request.project_id)
    return next(view for view in views_list if view.id == approval_id)


@approvals_router.get(
    "", response_model=list[ApprovalView], summary="Pending approvals across projects"
)
async def list_pending(memory: MemoryDep) -> list[ApprovalView]:
    """Everything waiting on a human, for the dashboard."""
    pending = await memory.approvals.list_pending()

    collected: list[ApprovalView] = []
    for project_id in dict.fromkeys(request.project_id for request in pending):
        collected.extend(
            await views.list_approvals(memory, project_id, pending_only=True)
        )
    return collected
