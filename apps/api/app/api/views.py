"""Assembles API responses from shared memory.

Routers stay thin: they parse a request, call one function here, and return the
result. Response assembly lives in this module because it frequently needs
several reads combined — an artifact list plus the staleness computed from the
traceability graph — and putting that in a router would make it untestable
without HTTP.
"""

from __future__ import annotations

from app.api.schemas import (
    AgentCard,
    ApprovalView,
    ArtifactDetail,
    ArtifactSummary,
    EventView,
    ImpactedArtifactView,
    ProjectDetail,
    ProjectSummary,
    StageSummary,
    TraceEdgeView,
    TraceGraph,
    TraceNode,
    VersionSummary,
)
from app.domain.agents import AgentRun
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import (
    ROLE_TITLES,
    STAGE_OWNERS,
    STAGE_SEQUENCE,
    LifecycleStage,
    StageStatus,
)
from app.memory.repository import SharedMemory

#: Stages that represent work. ``IDEA`` is the state a project starts in.
WORKING_STAGES = tuple(stage for stage in STAGE_SEQUENCE if stage is not LifecycleStage.IDEA)


async def stale_ids(memory: SharedMemory, project_id: str) -> set[str]:
    """Artifacts whose upstream has moved on since they were derived.

    Computed from the graph on every read rather than stored (ADR-0007), so it
    cannot disagree with reality.
    """
    entries = await memory.traces.stale_edges(project_id)
    return {stale.edge.downstream_artifact_id for stale in entries}


async def project_summary(memory: SharedMemory, project_id: str) -> ProjectSummary:
    project = await memory.projects.get(project_id)
    artifacts = await memory.artifacts.list_for_project(project_id)
    pending = await memory.approvals.list_for_project(project_id, pending_only=True)

    return ProjectSummary.build(
        project,
        artifact_count=len([a for a in artifacts if a.has_content]),
        pending_approvals=len(pending),
        total_stages=len(WORKING_STAGES),
    )


async def list_projects(memory: SharedMemory, *, limit: int = 50) -> list[ProjectSummary]:
    projects = await memory.projects.list_all(limit=limit)

    summaries = []
    for project in projects:
        artifacts = await memory.artifacts.list_for_project(project.id)
        pending = await memory.approvals.list_for_project(project.id, pending_only=True)
        summaries.append(
            ProjectSummary.build(
                project,
                artifact_count=len([a for a in artifacts if a.has_content]),
                pending_approvals=len(pending),
                total_stages=len(WORKING_STAGES),
            )
        )
    return summaries


async def project_detail(memory: SharedMemory, project_id: str) -> ProjectDetail:
    """A project with its complete stage timeline.

    Every working stage appears, including ones not yet started —
    `10_UI_UX_Plan.md` requires the timeline to show the whole lifecycle so a
    user can see what happens next, not only what has happened.
    """
    project = await memory.projects.get(project_id)
    artifacts = await memory.artifacts.list_for_project(project_id)
    pending = await memory.approvals.list_for_project(project_id, pending_only=True)

    counts: dict[LifecycleStage, int] = {}
    for artifact in artifacts:
        if artifact.has_content:
            counts[artifact.stage] = counts.get(artifact.stage, 0) + 1

    stages = []
    for stage in WORKING_STAGES:
        state = project.stage_state(stage)
        role = STAGE_OWNERS.get(stage)
        stages.append(
            StageSummary(
                stage=stage,
                status=state.status if state else StageStatus.PENDING,
                owner_role=role,
                owner_title=ROLE_TITLES[role] if role else None,
                started_at=state.started_at if state else None,
                completed_at=state.completed_at if state else None,
                artifact_count=counts.get(stage, 0),
            )
        )

    summary = ProjectSummary.build(
        project,
        artifact_count=len([a for a in artifacts if a.has_content]),
        pending_approvals=len(pending),
        total_stages=len(WORKING_STAGES),
    )
    return ProjectDetail(**summary.model_dump(), stages=stages)


async def list_artifacts(
    memory: SharedMemory,
    project_id: str,
    *,
    stage: LifecycleStage | None = None,
    artifact_type: ArtifactType | None = None,
) -> list[ArtifactSummary]:
    artifacts = await memory.artifacts.list_for_project(
        project_id, stage=stage, artifact_type=artifact_type
    )
    stale = await stale_ids(memory, project_id)

    return [
        ArtifactSummary.build(artifact, is_stale=artifact.id in stale)
        for artifact in artifacts
        if artifact.has_content
    ]


async def artifact_detail(
    memory: SharedMemory, artifact_id: str, *, version: int | None = None
) -> ArtifactDetail:
    resolved = await memory.artifacts.get_version(artifact_id, version)
    history = await memory.artifacts.list_versions(artifact_id)
    stale = await stale_ids(memory, resolved.artifact.project_id)

    return ArtifactDetail.from_resolved(
        resolved,
        is_stale=resolved.artifact.id in stale,
        versions=[
            VersionSummary(
                version=item.version,
                summary=item.summary,
                confidence=item.confidence,
                produced_by_run_id=item.produced_by_run_id,
                created_at=item.created_at,
            )
            for item in reversed(history)
        ],
    )


async def organization(memory: SharedMemory, project_id: str) -> list[AgentCard]:
    """Every specialist's current state, in lifecycle order.

    Specialists that have not run yet appear as idle rather than being omitted:
    `10_UI_UX_Plan.md` asks users to see the whole organization, and an agent
    missing from the view is indistinguishable from one that does not exist.
    """
    runs = await memory.runs.list_for_project(project_id)

    # Oldest first, so the last write per stage is the most recent run.
    latest_by_stage: dict[LifecycleStage, AgentRun] = {
        run.stage: run for run in sorted(runs, key=lambda item: item.started_at)
    }

    cards = []
    for stage in WORKING_STAGES:
        run = latest_by_stage.get(stage)
        if run is not None:
            cards.append(AgentCard.from_run(run))
        elif (role := STAGE_OWNERS.get(stage)) is not None:
            cards.append(AgentCard.idle(stage, role))

    return cards


async def list_approvals(
    memory: SharedMemory, project_id: str, *, pending_only: bool = False
) -> list[ApprovalView]:
    project = await memory.projects.get(project_id)
    requests = await memory.approvals.list_for_project(project_id, pending_only=pending_only)
    artifacts = {
        artifact.id: artifact
        for artifact in await memory.artifacts.list_for_project(project_id)
    }
    stale = await stale_ids(memory, project_id)

    views = []
    for request in requests:
        impacted = []
        if request.impact is not None:
            for item in request.impact.impacted:
                artifact = artifacts.get(item.artifact_id)
                impacted.append(
                    ImpactedArtifactView(
                        artifact_id=item.artifact_id,
                        title=artifact.title if artifact else item.artifact_id,
                        type=artifact.type if artifact else None,
                        depth=item.depth,
                        via_kind=item.via_kind.value,
                    )
                )

        views.append(
            ApprovalView.build(
                request,
                project_name=project.name,
                artifacts=[
                    ArtifactSummary.build(artifacts[aid], is_stale=aid in stale)
                    for aid in request.artifact_ids
                    if aid in artifacts
                ],
                impacted=impacted,
            )
        )
    return views


async def list_events(
    memory: SharedMemory, project_id: str, *, limit: int = 200, after_id: str | None = None
) -> list[EventView]:
    events = await memory.events.list_for_project(project_id, limit=limit, after_id=after_id)
    return [EventView.build(event) for event in events]


async def trace_graph(memory: SharedMemory, project_id: str) -> TraceGraph:
    """The full traceability graph, with staleness resolved per edge.

    Both node and edge staleness are returned so the UI can render *why* an
    artifact is stale — which specific derivation went out of date — rather than
    only that it is.
    """
    artifacts = {
        artifact.id: artifact
        for artifact in await memory.artifacts.list_for_project(project_id)
        if artifact.has_content
    }
    edges = await memory.traces.list_for_project(project_id)
    current = await memory.artifacts.current_versions(project_id)
    stale_edge_ids = {
        stale.edge.id: stale for stale in await memory.traces.stale_edges(project_id)
    }
    stale_nodes = {stale.edge.downstream_artifact_id for stale in stale_edge_ids.values()}

    return TraceGraph(
        project_id=project_id,
        nodes=[
            TraceNode(
                id=artifact.id,
                title=artifact.title,
                type=artifact.type,
                stage=artifact.stage,
                role=artifact.owner_role,
                version=artifact.current_version,
                is_stale=artifact.id in stale_nodes,
            )
            for artifact in artifacts.values()
        ],
        edges=[
            TraceEdgeView(
                id=edge.id,
                upstream_artifact_id=edge.upstream_artifact_id,
                downstream_artifact_id=edge.downstream_artifact_id,
                kind=edge.kind.value,
                upstream_version=edge.upstream_version,
                current_upstream_version=current.get(
                    edge.upstream_artifact_id, edge.upstream_version
                ),
                is_stale=edge.id in stale_edge_ids,
                rationale=edge.rationale,
            )
            for edge in edges
            # Edges to artifacts without content would render as dangling nodes.
            if edge.upstream_artifact_id in artifacts
            and edge.downstream_artifact_id in artifacts
        ],
        stale_artifact_ids=sorted(stale_nodes),
    )
