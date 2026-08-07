"""The approval loop: gates, rejection, revision, and re-approval.

`09_MVP_Roadmap.md` requires human approval of requirements, architecture,
technology selection, major engineering decisions, and final code generation.
Three are stage gates; two are raised by agents. Both paths are exercised here,
along with what happens when a reviewer says no.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import (
    DatabaseSettings,
    Environment,
    LLMProvider,
    LLMSettings,
    ObservabilitySettings,
    Settings,
)
from app.db.session import Database
from app.domain.approvals import ApprovalKind
from app.domain.artifacts import ArtifactStatus, ArtifactType
from app.domain.lifecycle import LifecycleStage, StageStatus
from app.main import create_app
from app.memory.repository import SharedMemory

PREFIX = "/api/v1"


@pytest_asyncio.fixture
async def api() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url="sqlite+aiosqlite:///file:approvaldb?mode=memory&cache=shared&uri=true"
        ),
        llm=LLMSettings(provider=LLMProvider.FIXTURE),
        observability=ObservabilitySettings(log_level="ERROR", json_logs=False),
    )
    app = create_app(settings)

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        await app.state.container.resolve(Database).create_schema()
        client.app_ref = app  # type: ignore[attr-defined]
        yield client


def memory_of(api: AsyncClient) -> SharedMemory:
    return api.app_ref.state.container.resolve(SharedMemory)  # type: ignore[attr-defined,type-abstract]


async def start_project(api: AsyncClient) -> str:
    response = await api.post(
        f"{PREFIX}/projects",
        json={
            "name": "Hospital Management System",
            "description": "Patients, appointments, billing, doctors, and operations.",
        },
    )
    project_id: str = response.json()["id"]
    await api.post(f"{PREFIX}/projects/{project_id}/advance")
    return project_id


async def pending(api: AsyncClient, project_id: str) -> list[dict]:
    response = await api.get(f"{PREFIX}/projects/{project_id}/approvals?pending=true")
    return list(response.json())


async def decide(
    api: AsyncClient, approval_id: str, decision: str, feedback: str | None = None
) -> dict:
    response = await api.post(
        f"{PREFIX}/approvals/{approval_id}/decision",
        json={"decision": decision, "feedback": feedback},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


# --- The gate halts -----------------------------------------------------------


async def test_gate_blocks_downstream_work(api: AsyncClient) -> None:
    """12_Risk_Analysis.md: a gate that notified while work continued is not a gate."""
    project_id = await start_project(api)

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()

    assert [item for item in artifacts if item["stage"] == "requirement_discovery"]
    assert not [item for item in artifacts if item["stage"] == "architecture"]


async def test_approving_marks_the_reviewed_artifacts_approved(
    api: AsyncClient,
) -> None:
    """A sign-off must be visible everywhere, not only on the approval record."""
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    await decide(api, request["id"], "approved")

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    reviewed = {item["id"] for item in request["artifacts"]}
    approved = {item["id"] for item in artifacts if item["status"] == "approved"}

    assert reviewed
    assert reviewed <= approved


# --- Rejection ----------------------------------------------------------------


async def test_rejection_reopens_the_stage_that_produced_the_work(
    api: AsyncClient,
) -> None:
    """The problem is with the work, so its author runs again — not the blocked stage."""
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    await decide(
        api, request["id"], "changes_requested", "Billing scope is unclear — split it out."
    )

    project = (await api.get(f"{PREFIX}/projects/{project_id}")).json()
    by_stage = {stage["stage"]: stage["status"] for stage in project["stages"]}

    assert by_stage["requirement_discovery"] == "pending"


async def test_rejection_feedback_reaches_the_agent_on_rerun(
    api: AsyncClient,
) -> None:
    """A rejection must teach. The feedback travels into the agent's context."""
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    await decide(api, request["id"], "changes_requested", "Split billing out.")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    memory = memory_of(api)
    runs = await memory.runs.list_for_project(project_id)
    discovery_runs = [
        run for run in runs if run.stage is LifecycleStage.REQUIREMENT_DISCOVERY
    ]

    assert len(discovery_runs) == 2, "the Product Manager must have run again"


async def test_rerun_revises_rather_than_duplicating(api: AsyncClient) -> None:
    """A second run produces v2 of the same artifact, not a competing copy.

    Duplicating would fork the traceability graph and trigger the duplicate
    authority conflict; versioning keeps one stable identity across revisions.
    """
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    before = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")
    ).json()
    assert len(before) == 1
    assert before[0]["current_version"] == 1

    await decide(api, request["id"], "changes_requested", "Split billing out.")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    after = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()

    assert len(after) == 1, "revising must not create a second PRD"
    assert after[0]["id"] == before[0]["id"], "identity must survive the revision"
    assert after[0]["current_version"] == 2


async def test_revised_work_is_no_longer_approved(api: AsyncClient) -> None:
    """Answering a rejection with content nobody has reviewed must not stay approved."""
    project_id = await start_project(api)
    first = (await pending(api, project_id))[0]
    await decide(api, first["id"], "approved")

    memory = memory_of(api)
    prd = (
        await memory.artifacts.list_for_project(project_id, artifact_type=ArtifactType.PRD)
    )[0]
    assert prd.status is ArtifactStatus.APPROVED

    # Reopen the stage by rejecting a later gate covering the same artifacts.
    await api.post(f"{PREFIX}/projects/{project_id}/advance")
    architecture_gate = (await pending(api, project_id))[0]
    await decide(api, architecture_gate["id"], "changes_requested", "Reconsider the split.")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    revised = await memory.artifacts.get(
        (
            await memory.artifacts.list_for_project(
                project_id, artifact_type=ArtifactType.SYSTEM_ARCHITECTURE
            )
        )[0].id
    )
    assert revised.status is ArtifactStatus.DRAFT


async def test_a_fresh_gate_is_raised_after_revision(api: AsyncClient) -> None:
    """A rejection applies to the version reviewed, not to the project forever.

    Without this the project would deadlock: the old decision would keep blocking
    a stage whose inputs have since been rewritten.
    """
    project_id = await start_project(api)
    first = (await pending(api, project_id))[0]

    await decide(api, first["id"], "changes_requested", "Split billing out.")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    outstanding = await pending(api, project_id)

    assert outstanding, "the revised work must come back for a decision"
    assert outstanding[0]["id"] != first["id"]
    assert outstanding[0]["kind"] == ApprovalKind.REQUIREMENTS.value


async def test_the_project_recovers_after_a_rejection(api: AsyncClient) -> None:
    """End to end: reject, revise, approve, and the lifecycle continues."""
    project_id = await start_project(api)

    first = (await pending(api, project_id))[0]
    await decide(api, first["id"], "changes_requested", "Split billing out.")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    second = (await pending(api, project_id))[0]
    await decide(api, second["id"], "approved")
    result = (await api.post(f"{PREFIX}/projects/{project_id}/advance")).json()

    assert "architecture" in result["executed_stages"]


# --- Agent-requested gates ----------------------------------------------------


async def test_agent_can_raise_its_own_approval_gate(api: AsyncClient) -> None:
    """09_MVP_Roadmap.md requires technology selection to be approved.

    That gate is not stage-shaped — it exists because the architect concluded its
    choice was expensive to reverse, so the agent raises it.
    """
    project_id = await start_project(api)
    await decide(api, (await pending(api, project_id))[0]["id"], "approved")

    # Architecture runs, and its agent sets requires_approval.
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    memory = memory_of(api)
    architect_run = next(
        run
        for run in await memory.runs.list_for_project(project_id)
        if run.stage is LifecycleStage.ARCHITECTURE
    )
    assert architect_run.requires_approval is True
    assert architect_run.approval_reason

    kinds = {item["kind"] for item in await pending(api, project_id)}
    assert ApprovalKind.TECHNOLOGY_SELECTION.value in kinds


async def test_agent_gate_reviews_what_the_agent_produced(api: AsyncClient) -> None:
    """A stage gate protects inputs; an agent gate reviews outputs."""
    project_id = await start_project(api)
    await decide(api, (await pending(api, project_id))[0]["id"], "approved")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    gate = next(
        item
        for item in await pending(api, project_id)
        if item["kind"] == ApprovalKind.TECHNOLOGY_SELECTION.value
    )
    types = {artifact["type"] for artifact in gate["artifacts"]}

    assert ArtifactType.TECHNOLOGY_DECISION.value in types


async def test_agent_gate_is_not_raised_twice(api: AsyncClient) -> None:
    project_id = await start_project(api)
    await decide(api, (await pending(api, project_id))[0]["id"], "approved")

    await api.post(f"{PREFIX}/projects/{project_id}/advance")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    technology_gates = [
        item
        for item in (await api.get(f"{PREFIX}/projects/{project_id}/approvals")).json()
        if item["kind"] == ApprovalKind.TECHNOLOGY_SELECTION.value
    ]

    assert len(technology_gates) == 1


# --- Human revision -----------------------------------------------------------


async def test_revising_an_artifact_appends_a_version(api: AsyncClient) -> None:
    """The version downstream agents consumed must stay readable."""
    project_id = await start_project(api)
    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]

    response = await api.post(
        f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/revise",
        json={
            "body_markdown": "# Requirements (revised)\n\nBilling is now its own requirement.",
            "summary": "Split billing out",
        },
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["version"] == 2
    assert len(detail["versions"]) == 2
    assert "Billing is now its own requirement" in detail["body_markdown"]

    original = (
        await api.get(
            f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}?version=1"
        )
    ).json()
    assert "FR-01" in original["body_markdown"]


async def test_revising_makes_downstream_work_stale(api: AsyncClient) -> None:
    """The differentiator, through the API a user actually calls."""
    project_id = await start_project(api)
    await decide(api, (await pending(api, project_id))[0]["id"], "approved")
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    graph_before = (
        await api.get(f"{PREFIX}/projects/{project_id}/traceability")
    ).json()
    assert graph_before["stale_artifact_ids"] == []

    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]
    await api.post(
        f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/revise",
        json={"body_markdown": "# Requirements (revised)", "summary": "Scope change"},
    )

    graph_after = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert graph_after["stale_artifact_ids"], "downstream work must be flagged stale"
    assert any(edge["is_stale"] for edge in graph_after["edges"])


async def test_revising_an_artifact_from_another_project_is_refused(
    api: AsyncClient,
) -> None:
    project_id = await start_project(api)
    other = (
        await api.post(
            f"{PREFIX}/projects", json={"name": "Other", "description": "Unrelated."}
        )
    ).json()["id"]

    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]

    response = await api.post(
        f"{PREFIX}/projects/{other}/artifacts/{prd['id']}/revise",
        json={"body_markdown": "Tampered."},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- Timeline -----------------------------------------------------------------


async def test_decisions_appear_on_the_timeline(api: AsyncClient) -> None:
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    await decide(api, request["id"], "approved")

    events = (await api.get(f"{PREFIX}/projects/{project_id}/events")).json()
    types = {event["type"] for event in events}

    assert "approval_requested" in types
    assert "approval_granted" in types


async def test_rejection_appears_on_the_timeline(api: AsyncClient) -> None:
    project_id = await start_project(api)
    request = (await pending(api, project_id))[0]

    await decide(api, request["id"], "changes_requested", "Not specific enough.")

    events = (await api.get(f"{PREFIX}/projects/{project_id}/events")).json()

    assert any(event["type"] == "approval_rejected" for event in events)
    assert any("Changes Requested" in event["summary"] for event in events)


async def test_stage_status_reflects_the_pending_gate(api: AsyncClient) -> None:
    project_id = await start_project(api)

    project = (await api.get(f"{PREFIX}/projects/{project_id}")).json()
    architecture = next(
        stage for stage in project["stages"] if stage["stage"] == "architecture"
    )

    assert architecture["status"] == StageStatus.AWAITING_APPROVAL.value
