"""Context assembly: scoping, prioritisation, and budgeting."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio

from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType, ArtifactVersion
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project
from app.memory.context_builder import CHARS_PER_TOKEN, ContextBuilder
from app.memory.sql_repository import SqlSharedMemory


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:ctxdb?mode=memory&cache=shared&uri=true")
    )
    await database.create_schema()
    try:
        yield SqlSharedMemory(database)
    finally:
        await database.aclose()


@pytest_asyncio.fixture
async def project(memory: SqlSharedMemory) -> Project:
    return await memory.projects.create(
        Project(name="Hospital System", description="Patients, appointments, billing.")
    )


async def add_artifact(
    memory: SqlSharedMemory,
    project: Project,
    *,
    title: str,
    stage: LifecycleStage,
    body: str,
    artifact_type: ArtifactType = ArtifactType.PRD,
    role: AgentRole = AgentRole.PRODUCT_MANAGER,
    status: ArtifactStatus = ArtifactStatus.DRAFT,
) -> Artifact:
    artifact = await memory.artifacts.create(
        Artifact(
            project_id=project.id,
            type=artifact_type,
            title=title,
            stage=stage,
            owner_role=role,
            status=status,
        )
    )
    await memory.artifacts.append_version(
        artifact.id,
        ArtifactVersion(artifact_id=artifact.id, version=1, body_markdown=body),
    )
    return artifact


def builder(memory: SqlSharedMemory, *, token_budget: int = 24_000) -> ContextBuilder:
    return ContextBuilder(memory.projects, memory.artifacts, token_budget=token_budget)


async def test_first_stage_has_no_upstream_context(
    memory: SqlSharedMemory, project: Project
) -> None:
    context = await builder(memory).build(
        project.id,
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        role=AgentRole.PRODUCT_MANAGER,
    )

    assert context.entries == []
    assert "first stage" in context.render()


async def test_upstream_artifacts_are_included(
    memory: SqlSharedMemory, project: Project
) -> None:
    await add_artifact(
        memory,
        project,
        title="Product Requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="Twelve functional requirements.",
    )

    context = await builder(memory).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert [entry.artifact.title for entry in context.entries] == ["Product Requirements"]
    assert "Twelve functional requirements." in context.render()


async def test_downstream_artifacts_are_excluded(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A later stage's output must not contaminate an earlier decision."""
    await add_artifact(
        memory,
        project,
        title="Requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="upstream",
    )
    await add_artifact(
        memory,
        project,
        title="Test Plan",
        stage=LifecycleStage.TESTING,
        body="downstream",
        artifact_type=ArtifactType.TEST_PLAN,
        role=AgentRole.QA_ENGINEER,
    )

    context = await builder(memory).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    titles = [entry.artifact.title for entry in context.entries]
    assert titles == ["Requirements"]


async def test_empty_artifacts_are_skipped(memory: SqlSharedMemory, project: Project) -> None:
    """An artifact with no version yet has nothing to contribute."""
    await memory.artifacts.create(
        Artifact(
            project_id=project.id,
            type=ArtifactType.PRD,
            title="Not yet written",
            stage=LifecycleStage.REQUIREMENT_DISCOVERY,
            owner_role=AgentRole.PRODUCT_MANAGER,
        )
    )

    context = await builder(memory).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert context.entries == []


async def test_approved_artifacts_outrank_drafts(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Agents should reason over what a human sanctioned, first."""
    await add_artifact(
        memory,
        project,
        title="Draft requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="draft",
        status=ArtifactStatus.DRAFT,
    )
    await add_artifact(
        memory,
        project,
        title="Approved requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="approved",
        status=ArtifactStatus.APPROVED,
    )

    context = await builder(memory).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert context.entries[0].artifact.title == "Approved requirements"


async def test_type_filter_narrows_the_view(memory: SqlSharedMemory, project: Project) -> None:
    await add_artifact(
        memory,
        project,
        title="Requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="reqs",
        artifact_type=ArtifactType.PRD,
    )
    await add_artifact(
        memory,
        project,
        title="Acceptance Criteria",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="criteria",
        artifact_type=ArtifactType.ACCEPTANCE_CRITERIA,
    )

    context = await builder(memory).build(
        project.id,
        stage=LifecycleStage.TESTING,
        role=AgentRole.QA_ENGINEER,
        include_types={ArtifactType.ACCEPTANCE_CRITERIA},
    )

    assert [entry.artifact.title for entry in context.entries] == ["Acceptance Criteria"]


async def test_budget_truncates_an_oversized_artifact(
    memory: SqlSharedMemory, project: Project
) -> None:
    await add_artifact(
        memory,
        project,
        title="Enormous requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="x" * (1000 * CHARS_PER_TOKEN),
    )

    context = await builder(memory, token_budget=500).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert context.entries[0].included_fully is False
    assert context.estimated_tokens <= 500
    assert "truncated" in context.render()


async def test_omitted_artifacts_are_reported_not_hidden(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A thin answer must be explainable by what the agent was not shown."""
    await add_artifact(
        memory,
        project,
        title="Approved and large",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="x" * (400 * CHARS_PER_TOKEN),
        status=ArtifactStatus.APPROVED,
    )
    await add_artifact(
        memory,
        project,
        title="Dropped draft",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="y" * (400 * CHARS_PER_TOKEN),
        status=ArtifactStatus.DRAFT,
    )

    context = await builder(memory, token_budget=450).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert "Dropped draft" in context.omitted
    assert "Dropped draft" in context.render()


async def test_context_exposes_input_artifact_ids_for_traceability(
    memory: SqlSharedMemory, project: Project
) -> None:
    """These become the upstream half of the trace edges the agent will write."""
    artifact = await add_artifact(
        memory,
        project,
        title="Requirements",
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        body="reqs",
    )

    context = await builder(memory).build(
        project.id, stage=LifecycleStage.ARCHITECTURE, role=AgentRole.SOFTWARE_ARCHITECT
    )

    assert context.artifact_ids == [artifact.id]


async def test_render_includes_the_project_brief(
    memory: SqlSharedMemory, project: Project
) -> None:
    """The user's own description travels with every agent invocation."""
    rendered = (
        await builder(memory).build(
            project.id,
            stage=LifecycleStage.REQUIREMENT_DISCOVERY,
            role=AgentRole.PRODUCT_MANAGER,
        )
    ).render()

    assert "Hospital System" in rendered
    assert "Patients, appointments, billing." in rendered
