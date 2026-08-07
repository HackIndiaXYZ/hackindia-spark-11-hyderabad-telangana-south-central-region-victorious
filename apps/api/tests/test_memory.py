"""Shared organizational memory against a real database.

These run on SQLite via the same SQLAlchemy layer used in production, so they
exercise the actual repository implementation rather than a substitute.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from itertools import pairwise

import pytest
import pytest_asyncio

from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.agents import AgentRun, AgentRunStatus, TokenUsage
from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.domain.errors import NotFoundError
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project
from app.domain.traceability import TraceEdge, TraceKind
from app.memory.sql_repository import SqlSharedMemory


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    """A fresh in-memory database per test.

    ``StaticPool`` is not needed: aiosqlite's shared-cache URI keeps one database
    alive across connections for the duration of the test.
    """
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:memdb?mode=memory&cache=shared&uri=true")
    )
    await database.create_schema()
    try:
        yield SqlSharedMemory(database)
    finally:
        await database.aclose()


@pytest_asyncio.fixture
async def project(memory: SqlSharedMemory) -> Project:
    return await memory.projects.create(
        Project(name="Hospital Management System", description="Patients, appointments, billing.")
    )


async def make_artifact(
    memory: SqlSharedMemory,
    project: Project,
    *,
    artifact_type: ArtifactType = ArtifactType.PRD,
    stage: LifecycleStage = LifecycleStage.REQUIREMENT_DISCOVERY,
    role: AgentRole = AgentRole.PRODUCT_MANAGER,
    title: str = "Product Requirements",
    status: ArtifactStatus = ArtifactStatus.DRAFT,
) -> Artifact:
    return await memory.artifacts.create(
        Artifact(
            project_id=project.id,
            type=artifact_type,
            title=title,
            stage=stage,
            owner_role=role,
            status=status,
        )
    )


# --- Projects -----------------------------------------------------------------


async def test_project_round_trips(memory: SqlSharedMemory, project: Project) -> None:
    fetched = await memory.projects.get(project.id)

    assert fetched.name == "Hospital Management System"
    assert fetched.current_stage is LifecycleStage.IDEA


async def test_missing_project_raises_not_found(memory: SqlSharedMemory) -> None:
    with pytest.raises(NotFoundError):
        await memory.projects.get("prj_missing")


async def test_project_stage_advances(memory: SqlSharedMemory, project: Project) -> None:
    project.current_stage = LifecycleStage.ARCHITECTURE
    await memory.projects.update(project)

    assert (await memory.projects.get(project.id)).current_stage is LifecycleStage.ARCHITECTURE


# --- Artifact versioning ------------------------------------------------------


async def test_new_artifact_has_no_content(memory: SqlSharedMemory, project: Project) -> None:
    artifact = await make_artifact(memory, project)

    assert artifact.current_version == 0
    assert artifact.has_content is False


async def test_appending_a_version_advances_the_artifact(
    memory: SqlSharedMemory, project: Project
) -> None:
    artifact = await make_artifact(memory, project)

    await memory.artifacts.append_version(
        artifact.id,
        ArtifactVersion(artifact_id=artifact.id, version=1, body_markdown="# PRD v1"),
    )

    resolved = await memory.artifacts.get_version(artifact.id)
    assert resolved.artifact.current_version == 1
    assert resolved.version.body_markdown == "# PRD v1"
    assert resolved.is_latest


async def test_versions_are_append_only(memory: SqlSharedMemory, project: Project) -> None:
    """The guarantee behind 12_Risk_Analysis.md's version-control mitigation."""
    artifact = await make_artifact(memory, project)

    await memory.artifacts.append_version(
        artifact.id, ArtifactVersion(artifact_id=artifact.id, version=1, body_markdown="v1 body")
    )
    await memory.artifacts.append_version(
        artifact.id, ArtifactVersion(artifact_id=artifact.id, version=1, body_markdown="v2 body")
    )

    versions = await memory.artifacts.list_versions(artifact.id)

    assert [v.version for v in versions] == [1, 2]
    assert versions[0].body_markdown == "v1 body", "v1 must survive intact"
    assert versions[1].body_markdown == "v2 body"


async def test_version_number_is_assigned_by_the_repository(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A caller-supplied number is ignored, so concurrent writers cannot collide."""
    artifact = await make_artifact(memory, project)

    stored = await memory.artifacts.append_version(
        artifact.id,
        ArtifactVersion(artifact_id=artifact.id, version=99, body_markdown="body"),
    )

    assert stored.version == 1


async def test_historical_version_is_retrievable(
    memory: SqlSharedMemory, project: Project
) -> None:
    """An agent's decision must remain inspectable as that agent saw it."""
    artifact = await make_artifact(memory, project)
    for body in ("v1", "v2", "v3"):
        await memory.artifacts.append_version(
            artifact.id, ArtifactVersion(artifact_id=artifact.id, version=1, body_markdown=body)
        )

    historical = await memory.artifacts.get_version(artifact.id, version=1)

    assert historical.version.body_markdown == "v1"
    assert historical.is_latest is False


async def test_get_version_on_empty_artifact_raises(
    memory: SqlSharedMemory, project: Project
) -> None:
    artifact = await make_artifact(memory, project)

    with pytest.raises(NotFoundError, match="no versions"):
        await memory.artifacts.get_version(artifact.id)


async def test_current_versions_returns_the_whole_project(
    memory: SqlSharedMemory, project: Project
) -> None:
    """One query feeds project-wide staleness detection."""
    first = await make_artifact(memory, project, title="PRD")
    second = await make_artifact(
        memory,
        project,
        artifact_type=ArtifactType.SYSTEM_ARCHITECTURE,
        stage=LifecycleStage.ARCHITECTURE,
        role=AgentRole.SOFTWARE_ARCHITECT,
        title="Architecture",
    )

    await memory.artifacts.append_version(
        first.id, ArtifactVersion(artifact_id=first.id, version=1, body_markdown="a")
    )
    await memory.artifacts.append_version(
        first.id, ArtifactVersion(artifact_id=first.id, version=1, body_markdown="b")
    )
    await memory.artifacts.append_version(
        second.id, ArtifactVersion(artifact_id=second.id, version=1, body_markdown="c")
    )

    assert await memory.artifacts.current_versions(project.id) == {first.id: 2, second.id: 1}


async def test_artifacts_filter_by_stage(memory: SqlSharedMemory, project: Project) -> None:
    await make_artifact(memory, project)
    await make_artifact(
        memory,
        project,
        artifact_type=ArtifactType.SYSTEM_ARCHITECTURE,
        stage=LifecycleStage.ARCHITECTURE,
        role=AgentRole.SOFTWARE_ARCHITECT,
    )

    result = await memory.artifacts.list_for_project(
        project.id, stage=LifecycleStage.ARCHITECTURE
    )

    assert [a.type for a in result] == [ArtifactType.SYSTEM_ARCHITECTURE]


# --- Traceability through the repository --------------------------------------


async def test_staleness_is_detected_end_to_end(
    memory: SqlSharedMemory, project: Project
) -> None:
    """The Milestone 8 scenario, exercised against real persistence.

    Requirements are revised; the architecture derived from the earlier version
    is reported stale — with no flag written anywhere.
    """
    requirements = await make_artifact(memory, project, title="Requirements")
    architecture = await make_artifact(
        memory,
        project,
        artifact_type=ArtifactType.SYSTEM_ARCHITECTURE,
        stage=LifecycleStage.ARCHITECTURE,
        role=AgentRole.SOFTWARE_ARCHITECT,
        title="System Architecture",
    )

    await memory.artifacts.append_version(
        requirements.id,
        ArtifactVersion(artifact_id=requirements.id, version=1, body_markdown="reqs v1"),
    )
    await memory.artifacts.append_version(
        architecture.id,
        ArtifactVersion(artifact_id=architecture.id, version=1, body_markdown="arch v1"),
    )
    await memory.traces.add_edge(
        TraceEdge(
            project_id=project.id,
            upstream_artifact_id=requirements.id,
            downstream_artifact_id=architecture.id,
            kind=TraceKind.DERIVES_FROM,
            upstream_version=1,
        )
    )

    assert await memory.traces.stale_edges(project.id) == []

    # The user revises requirements.
    await memory.artifacts.append_version(
        requirements.id,
        ArtifactVersion(artifact_id=requirements.id, version=1, body_markdown="reqs v2"),
    )

    stale = await memory.traces.stale_edges(project.id)

    assert len(stale) == 1
    assert stale[0].edge.downstream_artifact_id == architecture.id
    assert stale[0].versions_behind == 1


async def test_impact_analysis_reads_the_persisted_graph(
    memory: SqlSharedMemory, project: Project
) -> None:
    ids = ["art_reqs", "art_arch", "art_api"]
    for upstream, downstream in pairwise(ids):
        await memory.traces.add_edge(
            TraceEdge(
                project_id=project.id,
                upstream_artifact_id=upstream,
                downstream_artifact_id=downstream,
                upstream_version=1,
            )
        )

    analysis = await memory.traces.analyse_impact(project.id, "art_reqs")

    assert analysis.artifact_ids == ["art_arch", "art_api"]


async def test_edges_are_queryable_in_both_directions(
    memory: SqlSharedMemory, project: Project
) -> None:
    await memory.traces.add_edge(
        TraceEdge(
            project_id=project.id,
            upstream_artifact_id="art_reqs",
            downstream_artifact_id="art_arch",
            upstream_version=1,
        )
    )

    downstream = await memory.traces.downstream_of("art_reqs")
    upstream = await memory.traces.upstream_of("art_arch")

    assert len(downstream) == 1
    assert len(upstream) == 1
    assert downstream[0].id == upstream[0].id


# --- Agent runs ---------------------------------------------------------------


async def test_agent_run_lifecycle(memory: SqlSharedMemory, project: Project) -> None:
    run = await memory.runs.create(
        AgentRun(
            project_id=project.id,
            role=AgentRole.PRODUCT_MANAGER,
            stage=LifecycleStage.REQUIREMENT_DISCOVERY,
            task="Draft the PRD",
        )
    )

    run.status = AgentRunStatus.COMPLETED
    run.confidence = 0.82
    run.reasoning_summary = "Derived twelve requirements from the description."
    run.token_usage = TokenUsage(input_tokens=1200, output_tokens=3400)
    await memory.runs.update(run)

    fetched = await memory.runs.get(run.id)

    assert fetched.status is AgentRunStatus.COMPLETED
    assert fetched.confidence == 0.82
    assert fetched.token_usage.total == 4600


async def test_latest_run_per_role_drives_the_organization_view(
    memory: SqlSharedMemory, project: Project
) -> None:
    for task in ("first pass", "revision"):
        await memory.runs.create(
            AgentRun(
                project_id=project.id,
                role=AgentRole.SOFTWARE_ARCHITECT,
                stage=LifecycleStage.ARCHITECTURE,
                task=task,
            )
        )

    latest = await memory.runs.latest_for_role(project.id, AgentRole.SOFTWARE_ARCHITECT)

    assert latest is not None
    assert latest.task == "revision"


async def test_latest_run_is_none_for_an_idle_role(
    memory: SqlSharedMemory, project: Project
) -> None:
    assert await memory.runs.latest_for_role(project.id, AgentRole.QA_ENGINEER) is None


# --- Approvals ----------------------------------------------------------------


async def test_approval_decision_is_recorded(
    memory: SqlSharedMemory, project: Project
) -> None:
    request = await memory.approvals.create(
        ApprovalRequest(
            project_id=project.id,
            kind=ApprovalKind.TECHNOLOGY_SELECTION,
            stage=LifecycleStage.ARCHITECTURE,
            title="Adopt PostgreSQL",
            what_changed="Selected PostgreSQL over MongoDB.",
            why="Relational integrity for billing records.",
            requested_by=AgentRole.SOFTWARE_ARCHITECT,
            agents_involved=[AgentRole.SOFTWARE_ARCHITECT, AgentRole.BUSINESS_ANALYST],
        )
    )

    assert (await memory.approvals.list_pending())[0].id == request.id

    request.status = ApprovalStatus.APPROVED
    await memory.approvals.update(request)

    assert await memory.approvals.list_pending() == []
    assert (await memory.approvals.get(request.id)).status.unblocks_progress


async def test_rejection_feedback_survives_for_agent_rerun(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Feedback is fed back into agent context, so a rejection teaches."""
    request = await memory.approvals.create(
        ApprovalRequest(
            project_id=project.id,
            kind=ApprovalKind.ARCHITECTURE,
            stage=LifecycleStage.ARCHITECTURE,
            title="Microservice split",
            what_changed="Proposed seven services.",
            why="Independent scaling.",
            requested_by=AgentRole.SOFTWARE_ARCHITECT,
        )
    )

    request.status = ApprovalStatus.CHANGES_REQUESTED
    request.feedback = "Too granular for an MVP — start with a modular monolith."
    await memory.approvals.update(request)

    fetched = await memory.approvals.get(request.id)
    assert fetched.feedback is not None
    assert "modular monolith" in fetched.feedback
    assert fetched.status.unblocks_progress is False


# --- Events -------------------------------------------------------------------


async def test_events_are_returned_in_order(
    memory: SqlSharedMemory, project: Project
) -> None:
    for index in range(3):
        await memory.events.append(
            ProjectEvent(
                project_id=project.id,
                type=EventType.AGENT_COMPLETED,
                summary=f"event {index}",
            )
        )

    events = await memory.events.list_for_project(project.id)

    assert [e.summary for e in events] == ["event 0", "event 1", "event 2"]


async def test_event_cursor_replays_only_what_was_missed(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Stream resumption: a reconnecting browser must not replay everything."""
    stored = [
        await memory.events.append(
            ProjectEvent(
                project_id=project.id, type=EventType.AGENT_PROGRESS, summary=f"event {index}"
            )
        )
        for index in range(4)
    ]

    resumed = await memory.events.list_for_project(project.id, after_id=stored[1].id)

    assert [e.summary for e in resumed] == ["event 2", "event 3"]


async def test_unknown_cursor_replays_from_the_start(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A stale cursor must self-heal rather than return an empty stream."""
    await memory.events.append(
        ProjectEvent(project_id=project.id, type=EventType.PROJECT_CREATED, summary="created")
    )

    resumed = await memory.events.list_for_project(project.id, after_id="evt_unknown")

    assert len(resumed) == 1
