"""The traceability graph and impact preview over HTTP.

`04_Existing_Solutions.md` names these as the questions no tool on the market
answers. These verify the answers through the endpoints the workspace calls.
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
from app.domain.traceability import TraceEdge, TraceKind, current_edges
from app.main import create_app

PREFIX = "/api/v1"


@pytest_asyncio.fixture
async def api() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url="sqlite+aiosqlite:///file:tracedb?mode=memory&cache=shared&uri=true"
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


async def project_with_work(api: AsyncClient) -> str:
    """A project advanced past its first approval gate."""
    project_id: str = (
        await api.post(
            f"{PREFIX}/projects",
            json={
                "name": "Hospital Management System",
                "description": "Patients, appointments, billing, doctors.",
            },
        )
    ).json()["id"]

    await api.post(f"{PREFIX}/projects/{project_id}/advance")
    pending = (
        await api.get(f"{PREFIX}/projects/{project_id}/approvals?pending=true")
    ).json()
    await api.post(
        f"{PREFIX}/approvals/{pending[0]['id']}/decision", json={"decision": "approved"}
    )
    await api.post(f"{PREFIX}/projects/{project_id}/advance")
    return project_id


# --- Edge deduplication -------------------------------------------------------


def test_current_edges_keeps_only_the_latest_declaration() -> None:
    """An agent that reruns declares a new edge; the old one is history.

    Without this an artifact could never stop being stale: rebuilding it adds a
    fresh edge, but the superseded one still cites the old upstream version.
    """
    older = TraceEdge(
        project_id="prj_1",
        upstream_artifact_id="art_up",
        downstream_artifact_id="art_down",
        kind=TraceKind.DERIVES_FROM,
        upstream_version=1,
    )
    newer = older.model_copy(
        update={
            "id": "edg_new",
            "upstream_version": 2,
            "created_at": older.created_at.replace(year=older.created_at.year + 1),
        }
    )

    result = current_edges([older, newer])

    assert len(result) == 1
    assert result[0].upstream_version == 2


def test_current_edges_keeps_distinct_dependencies() -> None:
    """Two different upstreams are two dependencies, not one superseding another."""
    base = TraceEdge(
        project_id="prj_1",
        upstream_artifact_id="art_a",
        downstream_artifact_id="art_down",
        upstream_version=1,
    )
    other = base.model_copy(update={"id": "edg_2", "upstream_artifact_id": "art_b"})

    assert len(current_edges([base, other])) == 2


def test_different_kinds_are_distinct_dependencies() -> None:
    """`derives_from` and `tests` between the same pair mean different things."""
    derives = TraceEdge(
        project_id="prj_1",
        upstream_artifact_id="art_a",
        downstream_artifact_id="art_b",
        kind=TraceKind.DERIVES_FROM,
        upstream_version=1,
    )
    tests = derives.model_copy(update={"id": "edg_2", "kind": TraceKind.TESTS})

    assert len(current_edges([derives, tests])) == 2


# --- Graph endpoint -----------------------------------------------------------


async def test_graph_returns_nodes_and_edges(api: AsyncClient) -> None:
    project_id = await project_with_work(api)

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0
    assert graph["stale_artifact_ids"] == []

    node = graph["nodes"][0]
    assert {"id", "title", "type", "stage", "role", "version", "is_stale"} <= set(node)


async def test_graph_edges_reference_only_present_nodes(api: AsyncClient) -> None:
    """A dangling edge would render as an arrow to nowhere."""
    project_id = await project_with_work(api)

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()
    ids = {node["id"] for node in graph["nodes"]}

    for edge in graph["edges"]:
        assert edge["upstream_artifact_id"] in ids
        assert edge["downstream_artifact_id"] in ids


async def test_graph_declares_one_edge_per_dependency(api: AsyncClient) -> None:
    """Rendering a superseded edge would draw the same dependency twice."""
    project_id = await project_with_work(api)

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()
    pairs = [
        (edge["upstream_artifact_id"], edge["downstream_artifact_id"], edge["kind"])
        for edge in graph["edges"]
    ]

    assert len(pairs) == len(set(pairs))


async def test_graph_marks_staleness_on_nodes_and_edges(api: AsyncClient) -> None:
    """The UI shows *which* derivation went out of date, not only that one did."""
    project_id = await project_with_work(api)
    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]

    await api.post(
        f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/revise",
        json={"body_markdown": "# Revised requirements", "summary": "Scope change"},
    )

    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert graph["stale_artifact_ids"]
    stale_edges = [edge for edge in graph["edges"] if edge["is_stale"]]
    assert stale_edges
    assert stale_edges[0]["current_upstream_version"] > stale_edges[0]["upstream_version"]


# --- Impact preview -----------------------------------------------------------


async def test_impact_preview_reports_the_blast_radius(api: AsyncClient) -> None:
    """The question asked *before* the change, not reported after it."""
    project_id = await project_with_work(api)
    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]

    preview = (
        await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/impact")
    ).json()

    assert preview["artifact_id"] == prd["id"]
    assert preview["artifact_title"] == prd["title"]
    assert len(preview["impacted"]) > 0
    assert preview["stages_affected"]

    item = preview["impacted"][0]
    assert item["title"], "impacted artifacts are named, not just identified"
    assert item["depth"] >= 1


async def test_impact_preview_changes_nothing(api: AsyncClient) -> None:
    """Computing impact must never be mistaken for applying it."""
    project_id = await project_with_work(api)
    prd = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]

    await api.get(f"{PREFIX}/projects/{project_id}/artifacts/{prd['id']}/impact")

    after = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts?type=prd")).json()[0]
    graph = (await api.get(f"{PREFIX}/projects/{project_id}/traceability")).json()

    assert after["current_version"] == prd["current_version"]
    assert graph["stale_artifact_ids"] == []


async def test_impact_of_a_leaf_artifact_is_empty(api: AsyncClient) -> None:
    """A terminal artifact affects nothing downstream."""
    project_id = await project_with_work(api)
    artifacts = (await api.get(f"{PREFIX}/projects/{project_id}/artifacts")).json()
    architecture = next(
        item for item in artifacts if item["type"] == "system_architecture"
    )

    preview = (
        await api.get(
            f"{PREFIX}/projects/{project_id}/artifacts/{architecture['id']}/impact"
        )
    ).json()

    assert preview["impacted"] == []
    assert preview["stages_affected"] == []


async def test_impact_of_an_unknown_artifact_is_a_404(api: AsyncClient) -> None:
    project_id = await project_with_work(api)

    response = await api.get(
        f"{PREFIX}/projects/{project_id}/artifacts/art_missing/impact"
    )

    assert response.status_code == 404
