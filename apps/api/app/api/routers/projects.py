"""Project lifecycle endpoints.

The whole workspace is served from here: creating a project, advancing it,
reading its artifacts, agents, approvals, timeline, and traceability graph.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    ProjectDetail,
    ProjectSummary,
    TraceGraph,
)
from app.core.logging import get_logger
from app.domain.approvals import ApprovalStatus
from app.domain.artifacts import ArtifactStatus, ArtifactType
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


approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])


@approvals_router.post(
    "/{approval_id}/decision",
    response_model=ApprovalView,
    summary="Decide an approval request",
)
async def decide_approval(
    approval_id: str,
    memory: MemoryDep,
    decision: Annotated[ApprovalDecisionRequest, Body()],
) -> ApprovalView:
    """Approve, reject, or request changes.

    Rejecting requires feedback: it is fed back into the agent's context on
    re-run, so a rejection teaches rather than repeats. Rejecting without saying
    why would leave the organization to guess.
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

    request = await memory.approvals.get(approval_id)
    request.status = decision.decision
    request.feedback = decision.feedback
    request.decided_at = datetime.now(UTC)
    await memory.approvals.update(request)

    # Approving a gate approves the artifacts it was protecting: the reviewer has
    # signed off on exactly those, and leaving them in draft would make the
    # approval invisible everywhere else in the workspace.
    if decision.decision.unblocks_progress:
        for artifact_id in request.artifact_ids:
            artifact = await memory.artifacts.get(artifact_id)
            artifact.status = ArtifactStatus.APPROVED
            await memory.artifacts.update(artifact)

    await memory.events.append(
        ProjectEvent(
            project_id=request.project_id,
            type=(
                EventType.APPROVAL_GRANTED
                if decision.decision.unblocks_progress
                else EventType.APPROVAL_REJECTED
            ),
            stage=request.stage,
            summary=f"{decision.decision.value.replace('_', ' ').title()}: {request.title}",
            payload={"approval_id": request.id, "kind": request.kind.value},
        )
    )

    logger.info(
        "Approval decided",
        extra={"approval_id": approval_id, "decision": decision.decision.value},
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
