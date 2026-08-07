"""Agent framework: execution template, orphan guard, and provider portability."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput
from app.agents.prompts import PromptError, available_prompts, load_prompt, render_prompt
from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.agents import AgentRunStatus, TokenUsage
from app.domain.artifacts import Artifact, ArtifactType, ArtifactVersion
from app.domain.errors import ProviderError, ValidationError
from app.domain.events import EventType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project
from app.domain.traceability import TraceKind
from app.events.bus import EventBus
from app.llm.fixture_provider import FixtureProvider
from app.llm.provider import CompletionRequest, CompletionResponse, StructuredResponse
from app.memory.context_builder import ContextBuilder, ProjectContext
from app.memory.sql_repository import SqlSharedMemory


class ArchitectOutput(AgentOutput):
    """A minimal agent contract for exercising the framework."""

    recommended_stack: list[str] = Field(default_factory=list)


class SampleAgent(BaseAgent[ArchitectOutput]):
    role = AgentRole.SOFTWARE_ARCHITECT
    stage = LifecycleStage.ARCHITECTURE
    output_model = ArchitectOutput
    prompt_name = "engineering_organization"

    def build_task(self, context: ProjectContext) -> str:
        return f"Design the architecture using {len(context.entries)} upstream artifact(s)."


class ScriptedProvider:
    """Returns a prepared output, recording what it was asked."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        return CompletionResponse(
            text="", usage=TokenUsage(), model=self.model, provider=self.name
        )

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        self.requests.append(request)
        return StructuredResponse(
            value=schema.model_validate(self._payload),
            raw_json=json.dumps(self._payload),
            usage=TokenUsage(input_tokens=100, output_tokens=200),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        yield ""

    async def aclose(self) -> None:
        return None


class ExplodingProvider(ScriptedProvider):
    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        raise ProviderError("upstream model unavailable")


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:agentdb?mode=memory&cache=shared&uri=true")
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


async def add_upstream(memory: SqlSharedMemory, project: Project) -> Artifact:
    """Create an approved requirements artifact in an upstream stage."""
    artifact = await memory.artifacts.create(
        Artifact(
            project_id=project.id,
            type=ArtifactType.PRD,
            title="Product Requirements",
            stage=LifecycleStage.REQUIREMENT_DISCOVERY,
            owner_role=AgentRole.PRODUCT_MANAGER,
        )
    )
    await memory.artifacts.append_version(
        artifact.id,
        ArtifactVersion(
            artifact_id=artifact.id, version=1, body_markdown="Twelve requirements."
        ),
    )
    return artifact


def build_agent(memory: SqlSharedMemory, provider: ScriptedProvider) -> SampleAgent:
    return SampleAgent(
        memory,
        provider,
        ContextBuilder(memory.projects, memory.artifacts),
        EventBus(memory.events),
    )


def output_payload(upstream_id: str | None, **overrides: object) -> dict[str, object]:
    artifacts: list[dict[str, object]] = [
        {
            "type": ArtifactType.SYSTEM_ARCHITECTURE.value,
            "title": "System Architecture",
            "body_markdown": "## Components\n\nModular monolith.",
            "content": {"components": ["api", "web"]},
            "summary": "Initial architecture",
            "derived_from": (
                [
                    {
                        "upstream_artifact_id": upstream_id,
                        "kind": TraceKind.DERIVES_FROM.value,
                        "rationale": "Requirements define the domain model.",
                    }
                ]
                if upstream_id
                else []
            ),
        }
    ]
    payload: dict[str, object] = {
        "reasoning": "A modular monolith fits the stated scale.",
        "confidence": 0.84,
        "artifacts": artifacts,
        "concerns": [],
        "requires_approval": False,
        "approval_reason": "",
        "recommended_stack": ["FastAPI", "PostgreSQL"],
    }
    payload.update(overrides)
    return payload


# --- Execution template -------------------------------------------------------


async def test_agent_writes_artifact_and_records_the_run(
    memory: SqlSharedMemory, project: Project
) -> None:
    upstream = await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload(upstream.id))

    result = await build_agent(memory, provider).run(project.id)

    assert len(result.artifact_ids) == 1
    run = await memory.runs.get(result.run_id)
    assert run.status is AgentRunStatus.COMPLETED
    assert run.confidence == 0.84
    assert run.reasoning_summary.startswith("A modular monolith")
    assert run.output_artifact_ids == result.artifact_ids
    assert run.input_artifact_ids == [upstream.id]
    assert run.provider == "scripted"


async def test_agent_writes_trace_edges_at_the_consumed_version(
    memory: SqlSharedMemory, project: Project
) -> None:
    """The edge must cite the version actually read — ADR-0007's mechanism."""
    upstream = await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload(upstream.id))

    result = await build_agent(memory, provider).run(project.id)

    edges = await memory.traces.list_for_project(project.id)
    assert len(edges) == 1
    assert edges[0].upstream_artifact_id == upstream.id
    assert edges[0].downstream_artifact_id == result.artifact_ids[0]
    assert edges[0].upstream_version == 1
    assert edges[0].created_by_run_id == result.run_id


async def test_downstream_goes_stale_when_upstream_is_revised(
    memory: SqlSharedMemory, project: Project
) -> None:
    """End to end: an agent's output falls out of date when its input changes."""
    upstream = await add_upstream(memory, project)
    await build_agent(memory, ScriptedProvider(output_payload(upstream.id))).run(project.id)

    assert await memory.traces.stale_edges(project.id) == []

    await memory.artifacts.append_version(
        upstream.id,
        ArtifactVersion(artifact_id=upstream.id, version=1, body_markdown="Fifteen requirements."),
    )

    stale = await memory.traces.stale_edges(project.id)
    assert len(stale) == 1
    assert stale[0].versions_behind == 1


async def test_agent_publishes_lifecycle_events(
    memory: SqlSharedMemory, project: Project
) -> None:
    upstream = await add_upstream(memory, project)

    await build_agent(memory, ScriptedProvider(output_payload(upstream.id))).run(project.id)

    types = [event.type for event in await memory.events.list_for_project(project.id)]
    assert EventType.AGENT_STARTED in types
    assert EventType.ARTIFACT_CREATED in types
    assert EventType.AGENT_COMPLETED in types


async def test_context_reaches_the_provider(
    memory: SqlSharedMemory, project: Project
) -> None:
    upstream = await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload(upstream.id))

    await build_agent(memory, provider).run(project.id)

    sent = provider.requests[0]
    assert "Twelve requirements." in sent.messages[0].content
    assert "Hospital System" in sent.messages[0].content
    assert sent.fixture_key == "software_architect.architecture"


async def test_reviewer_feedback_is_passed_to_the_agent(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A rejection must teach, not merely repeat."""
    upstream = await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload(upstream.id))

    await build_agent(memory, provider).run(
        project.id, feedback="Too granular — start with a modular monolith."
    )

    combined = " ".join(message.content for message in provider.requests[0].messages)
    assert "modular monolith" in combined


async def test_concerns_raise_a_conflict_event(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Agents flag upstream problems rather than working around them."""
    upstream = await add_upstream(memory, project)
    payload = output_payload(upstream.id, concerns=["Billing requirements are ambiguous."])

    result = await build_agent(memory, ScriptedProvider(payload)).run(project.id)

    assert result.has_concerns
    types = [event.type for event in await memory.events.list_for_project(project.id)]
    assert EventType.CONFLICT_DETECTED in types


async def test_failure_marks_the_run_and_publishes(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A failed agent must be visible in the Organization view, not absent."""
    await add_upstream(memory, project)

    with pytest.raises(ProviderError):
        await build_agent(memory, ExplodingProvider({})).run(project.id)

    runs = await memory.runs.list_for_project(project.id)
    assert runs[0].status is AgentRunStatus.FAILED
    assert runs[0].error is not None
    assert "upstream model unavailable" in runs[0].error

    types = [event.type for event in await memory.events.list_for_project(project.id)]
    assert EventType.AGENT_FAILED in types


# --- Orphan guard (ADR-0007) --------------------------------------------------


async def test_artifact_without_declared_upstream_is_rejected(
    memory: SqlSharedMemory, project: Project
) -> None:
    """An orphan is invisible to impact analysis, so the run fails instead."""
    await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload(None))

    with pytest.raises(ValidationError, match="declares no upstream"):
        await build_agent(memory, provider).run(project.id)

    assert await memory.artifacts.list_for_project(
        project.id, stage=LifecycleStage.ARCHITECTURE
    ) == []


async def test_artifact_citing_unseen_upstream_is_rejected(
    memory: SqlSharedMemory, project: Project
) -> None:
    """An agent cannot claim to have used what it was never given."""
    await add_upstream(memory, project)
    provider = ScriptedProvider(output_payload("art_never_supplied"))

    with pytest.raises(ValidationError, match="not in the agent's context"):
        await build_agent(memory, provider).run(project.id)


async def test_first_stage_may_produce_artifacts_with_no_upstream(
    memory: SqlSharedMemory, project: Project
) -> None:
    """The guard triggers on context being present, not unconditionally."""

    class FirstStageAgent(SampleAgent):
        stage = LifecycleStage.REQUIREMENT_DISCOVERY
        role = AgentRole.PRODUCT_MANAGER

    payload = output_payload(None)
    payload["artifacts"] = [
        {
            "type": ArtifactType.PRD.value,
            "title": "Product Requirements",
            "body_markdown": "Twelve requirements.",
            "content": {},
            "summary": "Initial PRD",
            "derived_from": [],
        }
    ]

    agent = FirstStageAgent(
        memory,
        ScriptedProvider(payload),
        ContextBuilder(memory.projects, memory.artifacts),
        EventBus(memory.events),
    )
    result = await agent.run(project.id)

    assert len(result.artifact_ids) == 1


# --- Provider portability -----------------------------------------------------


async def test_the_same_agent_runs_unchanged_across_providers(
    memory: SqlSharedMemory, project: Project, tmp_path: Path
) -> None:
    """ADR-0004's guarantee, verified rather than asserted.

    The identical agent class runs against a scripted provider and a
    fixture-backed one with no code change — only the injected provider differs.
    """
    upstream = await add_upstream(memory, project)
    payload = output_payload(upstream.id)

    scripted_result = await build_agent(memory, ScriptedProvider(payload)).run(project.id)

    (tmp_path / "software_architect.architecture.json").write_text(
        json.dumps({"value": payload, "usage": {"input_tokens": 1, "output_tokens": 2}}),
        encoding="utf-8",
    )
    fixture_result = await build_agent(memory, FixtureProvider(tmp_path)).run(project.id)  # type: ignore[arg-type]

    assert scripted_result.output.confidence == fixture_result.output.confidence
    assert scripted_result.output.reasoning == fixture_result.output.reasoning
    assert len(fixture_result.artifact_ids) == 1

    runs = await memory.runs.list_for_project(project.id)
    assert {run.provider for run in runs} == {"scripted", "fixture"}


# --- Prompt loading -----------------------------------------------------------


def test_shared_system_prompt_is_present() -> None:
    assert "engineering_organization" in available_prompts()
    assert "derived_from" in load_prompt("engineering_organization")


def test_missing_prompt_lists_what_is_available() -> None:
    with pytest.raises(PromptError) as exc_info:
        load_prompt("no_such_agent")

    assert "available" in exc_info.value.details


def test_unsubstituted_variables_fail_loudly(tmp_path: Path) -> None:
    """An unfilled placeholder reaching a model is far harder to diagnose."""
    from app.agents import prompts as prompts_module

    template = prompts_module.PROMPT_DIR / "_test_template.md"
    template.write_text("Project: $project_name\nStage: $stage", encoding="utf-8")
    prompts_module.load_prompt.cache_clear()

    try:
        assert "Hospital" in render_prompt("_test_template", project_name="Hospital", stage="x")

        with pytest.raises(PromptError, match="not supplied"):
            render_prompt("_test_template", project_name="Hospital")
    finally:
        template.unlink()
        prompts_module.load_prompt.cache_clear()
