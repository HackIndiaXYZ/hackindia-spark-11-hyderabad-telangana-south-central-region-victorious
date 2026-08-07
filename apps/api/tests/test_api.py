"""HTTP API surface.

Exercised through the real app with the real container, so routing, dependency
injection, error handling, and serialisation are all covered. The organization
runs on the fixture provider, so no test makes a network call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
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
from app.main import create_app

PREFIX = "/api/v1"


@pytest_asyncio.fixture
async def api() -> AsyncIterator[AsyncClient]:
    """The real application, on an isolated in-memory database."""
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url="sqlite+aiosqlite:///file:apidb?mode=memory&cache=shared&uri=true"
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
        yield client


async def create_project(api: AsyncClient, name: str = "Hospital Management System") -> str:
    response = await api.post(
        f"{PREFIX}/projects",
        json={
            "name": name,
            "description": "Managing patients, appointments, billing, and doctors.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- Project creation ---------------------------------------------------------


async def test_project_is_created_from_two_fields(api: AsyncClient) -> None:
    """07_System_Architecture.md: a name and a description, nothing else."""
    response = await api.post(
        f"{PREFIX}/projects",
        json={"name": "Hospital System", "description": "Patients and appointments."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("prj_")
    assert body["current_stage"] == "idea"
    assert body["completed_stages"] == 0
    assert body["total_stages"] == 8


async def test_empty_name_is_rejected(api: AsyncClient) -> None:
    response = await api.post(
        f"{PREFIX}/projects", json={"name": "", "description": "Something."}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"


async def test_unknown_project_returns_the_error_envelope(api: AsyncClient) -> None:
    response = await api.get(f"{PREFIX}/projects/prj_missing")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["correlation_id"]


async def test_projects_are_listed_with_progress(api: AsyncClient) -> None:
    await create_project(api, "First")
    await create_project(api, "Second")

    response = await api.get(f"{PREFIX}/projects")

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"First", "Second"}


# --- Project detail -----------------------------------------------------------


async def test_detail_lists_every_lifecycle_stage(api: AsyncClient) -> None:
    """The timeline shows what happens next, not only what has happened."""
    project_id = await create_project(api)

    response = await api.get(f"{PREFIX}/projects/{project_id}")

    stages = response.json()["stages"]
    assert len(stages) == 8
    assert stages[0]["stage"] == "requirement_discovery"
    assert stages[0]["owner_title"] == "Product Manager"
    assert all(stage["status"] == "pending" for stage in stages)


# --- Organization view --------------------------------------------------------


async def test_organization_lists_every_specialist_including_idle(
    api: AsyncClient,
) -> None:
    """An agent missing from the view is indistinguishable from one that does not exist."""
    project_id = await create_project(api)

    response = await api.get(f"{PREFIX}/projects/{project_id}/agents")

    cards = response.json()
    assert len(cards) == 8
    assert all(card["status"] == "idle" for card in cards)
    assert {card["title"] for card in cards} >= {
        "Product Manager",
        "Business Analyst",
        "Software Architect",
        "Full Stack Engineer",
        "QA Engineer",
        "Documentation Engineer",
    }


async def test_executive_is_absent_from_the_organization_view(
    api: AsyncClient,
) -> None:
    """15_Development_Guidelines.md: it coordinates, it does not perform work."""
    project_id = await create_project(api)

    cards = (await api.get(f"{PREFIX}/projects/{project_id}/agents")).json()

    assert all(card["role"] != "executive" for card in cards)


# --- Advancing the workflow ---------------------------------------------------


async def test_advance_runs_the_organization_and_halts_at_a_gate(
    api: AsyncClient,
) -> None:
    """The demo path, over HTTP, on recorded fixtures — no network involved."""
    project_id = await create_project(api)

    body = (await api.post(f"{PREFIX}/projects/{project_id}/advance")).json()

    assert body["executed_stages"] == ["requirement_discovery", "business_validation"]
    assert body["halt_action"] == "await_approval"
    assert body["pending_approval_id"] is not None

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    assert {artifact["type"] for artifact in artifacts} >= {"prd", "user_stories"}

    # The gate genuinely halts: nothing downstream exists yet.
    assert all(artifact["stage"] != "architecture" for artifact in artifacts)


async def test_approving_a_gate_lets_the_organization_continue(
    api: AsyncClient,
) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    pending = (await api.get(f"{PREFIX}/projects/{project_id}/approvals?pending=true")).json()
    assert len(pending) == 1

    decision = await api.post(
        f"{PREFIX}/approvals/{pending[0]['id']}/decision", json={"decision": "approved"}
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    body = (await api.post(f"{PREFIX}/projects/{project_id}/advance")).json()
    assert "architecture" in body["executed_stages"]


async def test_agents_report_their_work_after_running(api: AsyncClient) -> None:
    """The Organization view's data, over HTTP."""
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    cards = (await api.get(f"{PREFIX}/projects/{project_id}/agents")).json()
    by_stage = {card["stage"]: card for card in cards}

    product_manager = by_stage["requirement_discovery"]
    assert product_manager["status"] == "completed"
    assert product_manager["confidence"] is not None
    assert product_manager["reasoning_summary"]
    assert product_manager["total_tokens"] > 0
    assert by_stage["implementation"]["status"] == "idle"


async def test_traceability_graph_connects_produced_artifacts(
    api: AsyncClient,
) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0
    assert graph["stale_artifact_ids"] == []


async def test_artifact_detail_carries_body_and_history(api: AsyncClient) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    prd = next(item for item in artifacts if item["type"] == "prd")

    detail = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}")
    ).json()

    assert "FR-01" in detail["body_markdown"]
    assert detail["is_latest"] is True
    assert detail["versions"][0]["version"] == 1
    assert detail["content"]["functional_requirements"]


async def test_advancing_an_unknown_project_is_a_404(api: AsyncClient) -> None:
    response = await api.post(f"{PREFIX}/projects/prj_missing/advance")

    assert response.status_code == 404


# --- Artifacts, events, traceability ------------------------------------------


async def test_new_project_has_no_artifacts(api: AsyncClient) -> None:
    project_id = await create_project(api)

    response = await api.get(f"{PREFIX}/projects/{project_id}/artifacts")

    assert response.status_code == 200
    assert response.json() == []


async def test_creation_is_recorded_on_the_timeline(api: AsyncClient) -> None:
    project_id = await create_project(api)

    events = (await api.get(f"{PREFIX}/projects/{project_id}/events")).json()

    assert events[0]["type"] == "project_created"
    assert "Hospital Management System" in events[0]["summary"]


async def test_traceability_graph_is_empty_but_well_formed(api: AsyncClient) -> None:
    project_id = await create_project(api)

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert graph["project_id"] == project_id
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["stale_artifact_ids"] == []


# --- Approvals ----------------------------------------------------------------


async def test_pending_approvals_endpoint_is_empty_initially(api: AsyncClient) -> None:
    await create_project(api)

    response = await api.get(f"{PREFIX}/approvals")

    assert response.status_code == 200
    assert response.json() == []


async def test_rejecting_without_feedback_is_refused(api: AsyncClient) -> None:
    """A rejection with no reason leaves the organization to guess."""
    response = await api.post(
        f"{PREFIX}/approvals/apr_missing/decision",
        json={"decision": "changes_requested"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_pending_is_not_a_decision(api: AsyncClient) -> None:
    response = await api.post(
        f"{PREFIX}/approvals/apr_missing/decision", json={"decision": "pending"}
    )

    assert response.status_code == 422


async def test_deciding_an_unknown_approval_is_a_404(api: AsyncClient) -> None:
    response = await api.post(
        f"{PREFIX}/approvals/apr_missing/decision", json={"decision": "approved"}
    )

    assert response.status_code == 404


# --- Contract shape -----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/projects",
        "/approvals",
    ],
)
async def test_collections_return_arrays(api: AsyncClient, path: str) -> None:
    response = await api.get(f"{PREFIX}{path}")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_openapi_documents_the_workspace_surface(api: AsyncClient) -> None:
    """The generated schema is what the web client is typed against."""
    schema = (await api.get("/openapi.json")).json()
    paths = schema["paths"]

    assert f"{PREFIX}/projects" in paths
    assert f"{PREFIX}/projects/{{project_id}}/advance" in paths
    assert f"{PREFIX}/projects/{{project_id}}/traceability" in paths
    assert f"{PREFIX}/approvals/{{approval_id}}/decision" in paths


# --- Helix Review -------------------------------------------------------------


async def test_every_produced_artifact_is_reviewed_as_it_lands(api: AsyncClient) -> None:
    """Review is automatic. Nothing in the workflow asks for it."""
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()

    assert summary["artifacts_reviewed"] == len(artifacts)
    assert 0 < summary["overall_score"] <= 100


async def test_review_summary_scores_each_specialist(api: AsyncClient) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()

    assert summary["by_role"]
    for role in summary["by_role"]:
        assert role["artifacts_reviewed"] >= 1
        assert 0 <= role["average_score"] <= 100
        assert role["lowest_score"] <= role["average_score"]


async def test_scores_are_not_uniform_across_artifacts(api: AsyncClient) -> None:
    """A reviewer that scores everything alike has measured nothing."""
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()
    scores = {review["quality_score"] for review in summary["reviews"]}

    assert len(scores) > 1


async def test_every_review_carries_evidence_from_the_checks(api: AsyncClient) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()

    for review in summary["reviews"]:
        findings = review["strengths"] + review["weaknesses"] + review["suggestions"]
        assert any(finding["source"] == "check" for finding in findings)
        assert 0 <= review["deterministic_score"] <= 100


async def test_a_review_travels_with_its_artifact(api: AsyncClient) -> None:
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    prd = next(item for item in artifacts if item["type"] == "prd")

    detail = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}")
    ).json()

    assert detail["review"] is not None
    assert detail["review"]["artifact_version"] == detail["version"]
    assert detail["review"]["artifact_id"] == prd["id"]


async def test_a_human_revision_is_not_passed_off_as_reviewed(api: AsyncClient) -> None:
    """Reviews are per version. A version no agent produced has none."""
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    prd = next(item for item in artifacts if item["type"] == "prd")

    await api.post(
        f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/revise",
        json={"body_markdown": "# Requirements\n\nRewritten by hand.", "summary": "Human edit"},
    )

    detail = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}")
    ).json()
    assert detail["version"] == 2
    assert detail["review"] is None

    # The agent's review of v1 is still readable exactly as it was written.
    original = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}?version=1")
    ).json()
    assert original["review"]["artifact_version"] == 1


async def test_reviews_for_a_project_with_no_work_are_empty_but_well_formed(
    api: AsyncClient,
) -> None:
    project_id = await create_project(api)

    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()

    assert summary["artifacts_reviewed"] == 0
    assert summary["overall_score"] == 0
    assert summary["by_role"] == []
    assert summary["reviews"] == []


async def test_recommendations_are_specific_and_never_repeat(api: AsyncClient) -> None:
    """A template sentence three times reads as noise, not emphasis."""
    project_id = await create_project(api)
    await api.post(f"{PREFIX}/projects/{project_id}/advance")

    summary = (await api.get(f"{PREFIX}/projects/{project_id}/reviews")).json()
    texts = [item["text"] for item in summary["recommendations"]]

    assert texts
    assert len(texts) == len(set(texts))
    # Specific before generic: the model's suggestions name something in the
    # artifact, the checks' suggestions are templates.
    sources = [item["source"] for item in summary["recommendations"]]
    assert sources == sorted(sources, key=lambda source: source != "reasoning")
