"""The engineering workflow, end to end.

These exercise the real path: a real LangGraph traversal, the real Executive AI,
real `BaseAgent` subclasses, and real persistence. Only the reasoning provider is
substituted — and it is substituted with one that reads artifact IDs out of the
rendered context exactly as a language model must, so the traceability contract
is genuinely exercised rather than bypassed.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from pydantic import BaseModel

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput
from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.approvals import ApprovalKind, ApprovalStatus
from app.domain.artifacts import ArtifactStatus, ArtifactType, ArtifactVersion
from app.domain.errors import ProviderError
from app.domain.events import EventType
from app.domain.lifecycle import AgentRole, LifecycleStage, StageStatus
from app.domain.projects import Project
from app.domain.traceability import TraceKind
from app.events.bus import EventBus
from app.llm.provider import CompletionRequest, CompletionResponse, StructuredResponse
from app.memory.context_builder import ContextBuilder, ProjectContext
from app.memory.sql_repository import SqlSharedMemory
from app.orchestration.conflicts import ConflictKind
from app.orchestration.runner import OrchestrationRunner

ARTIFACT_ID_PATTERN = re.compile(r"art_[0-9a-f]{32}")


class StageOutput(AgentOutput):
    """Output contract shared by the test agents."""


class ContextAwareProvider:
    """Produces artifacts that cite whatever upstream the context contained.

    Deliberately parses artifact IDs out of the rendered context, which is what a
    real model must do to satisfy the orphan guard. A provider that was handed the
    IDs directly would test the graph while bypassing the contract that makes the
    traceability graph trustworthy.
    """

    name = "context_aware"
    model = "context-aware-1"

    def __init__(self, produces: dict[str, list[tuple[ArtifactType, str]]]) -> None:
        self._produces = produces
        self.calls: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        self.calls.append(request)

        stage = request.metadata.get("stage", "")
        context_text = " ".join(message.content for message in request.messages)
        upstream = sorted(set(ARTIFACT_ID_PATTERN.findall(context_text)))

        links = [
            {
                "upstream_artifact_id": artifact_id,
                "kind": TraceKind.DERIVES_FROM.value,
                "rationale": "Produced from this upstream artifact.",
            }
            for artifact_id in upstream
        ]

        artifacts = [
            {
                "type": artifact_type.value,
                "title": title,
                "body_markdown": f"# {title}\n\nProduced during {stage}.",
                "content": {"stage": stage},
                "summary": f"{title} v1",
                "derived_from": links,
            }
            for artifact_type, title in self._produces.get(stage, [])
        ]

        from app.domain.agents import TokenUsage

        return StructuredResponse(
            value=schema.model_validate(
                {
                    "reasoning": f"Completed {stage} from {len(upstream)} upstream artifact(s).",
                    "confidence": 0.86,
                    "artifacts": artifacts,
                    "concerns": [],
                    "requires_approval": False,
                    "approval_reason": "",
                }
            ),
            raw_json="{}",
            usage=TokenUsage(input_tokens=50, output_tokens=120),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        yield ""

    async def aclose(self) -> None:
        return None


def make_agent(
    agent_role: AgentRole, agent_stage: LifecycleStage
) -> type[BaseAgent[StageOutput]]:
    """Build a real BaseAgent subclass for a role and stage.

    ``build_task`` is defined in the class body rather than assigned afterwards:
    ``__abstractmethods__`` is computed at class creation, so a later assignment
    would leave the class uninstantiable.
    """

    class _Agent(BaseAgent[StageOutput]):
        role = agent_role
        stage = agent_stage
        output_model = StageOutput
        prompt_name = "engineering_organization"

        def build_task(self, context: ProjectContext) -> str:
            return f"Perform {agent_stage.value} for this project."

    _Agent.__name__ = f"{agent_role.value}_agent"
    return _Agent


#: What each stage's agent produces. Types match STAGE_INPUTS so the lifecycle
#: actually advances rather than stalling on a missing input.
STAGE_OUTPUTS: dict[str, list[tuple[ArtifactType, str]]] = {
    LifecycleStage.REQUIREMENT_DISCOVERY.value: [
        (ArtifactType.PRD, "Product Requirements"),
        (ArtifactType.ACCEPTANCE_CRITERIA, "Acceptance Criteria"),
    ],
    LifecycleStage.BUSINESS_VALIDATION.value: [
        (ArtifactType.BUSINESS_ANALYSIS, "Business Analysis"),
    ],
    LifecycleStage.ARCHITECTURE.value: [
        (ArtifactType.SYSTEM_ARCHITECTURE, "System Architecture"),
    ],
}


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:orchdb?mode=memory&cache=shared&uri=true")
    )
    await database.create_schema()
    try:
        yield SqlSharedMemory(database)
    finally:
        await database.aclose()


@pytest_asyncio.fixture
async def project(memory: SqlSharedMemory) -> Project:
    return await memory.projects.create(
        Project(
            name="Hospital Management System",
            description="Patients, appointments, billing, doctors, and operations.",
        )
    )


def build_runner(
    memory: SqlSharedMemory,
    *,
    provider: object | None = None,
    roles: dict[AgentRole, LifecycleStage] | None = None,
) -> OrchestrationRunner:
    from app.orchestration.dispatcher import RegistryDispatcher

    resolved_provider = provider or ContextAwareProvider(STAGE_OUTPUTS)
    events = EventBus(memory.events)
    context = ContextBuilder(memory.projects, memory.artifacts)

    # `is None` rather than a falsy check: an explicitly empty mapping means "an
    # organization with no agents", which is a case under test.
    if roles is None:
        roles = {
            AgentRole.PRODUCT_MANAGER: LifecycleStage.REQUIREMENT_DISCOVERY,
            AgentRole.BUSINESS_ANALYST: LifecycleStage.BUSINESS_VALIDATION,
            AgentRole.SOFTWARE_ARCHITECT: LifecycleStage.ARCHITECTURE,
        }

    dispatcher = RegistryDispatcher()
    for role, stage in roles.items():
        agent_class = make_agent(role, stage)
        dispatcher.register(agent_class(memory, resolved_provider, context, events))  # type: ignore[arg-type]

    return OrchestrationRunner(memory, resolved_provider, events, dispatcher)  # type: ignore[arg-type]


async def approve_latest(memory: SqlSharedMemory, project_id: str) -> None:
    """Grant the pending approval, as a human would in the Approval Center."""
    pending = await memory.approvals.list_for_project(project_id, pending_only=True)
    for request in pending:
        request.status = ApprovalStatus.APPROVED
        await memory.approvals.update(request)


# --- Lifecycle advance --------------------------------------------------------


async def test_workflow_advances_through_the_first_stages(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Idea → Requirement Discovery → Business Validation, then halts at a gate.

    The Architecture stage is gated on requirements approval per
    09_MVP_Roadmap.md, so the traversal stops there rather than proceeding.
    """
    outcome = await build_runner(memory).advance(project.id)

    assert outcome.executed_stages == [
        LifecycleStage.REQUIREMENT_DISCOVERY,
        LifecycleStage.BUSINESS_VALIDATION,
    ]
    assert outcome.awaiting_approval
    assert outcome.pending_approval_id is not None


async def test_architecture_proceeds_once_requirements_are_approved(
    memory: SqlSharedMemory, project: Project
) -> None:
    """The full criterion: Idea → Requirements → Validation → Architecture."""
    runner = build_runner(memory)

    first = await runner.advance(project.id)
    assert first.awaiting_approval

    await approve_latest(memory, project.id)

    second = await runner.advance(project.id)

    assert LifecycleStage.ARCHITECTURE in second.executed_stages

    architecture = await memory.artifacts.list_for_project(
        project.id, artifact_type=ArtifactType.SYSTEM_ARCHITECTURE
    )
    assert len(architecture) == 1
    assert architecture[0].has_content


async def test_traversal_is_resumable_across_runner_instances(
    memory: SqlSharedMemory, project: Project
) -> None:
    """ADR-0009: state lives in shared memory, not a checkpointer.

    A second runner — as a different process would build — resumes correctly
    because it reads the same memory rather than in-process graph state.
    """
    await build_runner(memory).advance(project.id)
    await approve_latest(memory, project.id)

    resumed = await build_runner(memory).advance(project.id)

    assert LifecycleStage.ARCHITECTURE in resumed.executed_stages


# --- Approval gates -----------------------------------------------------------


async def test_gate_genuinely_halts_before_downstream_work(
    memory: SqlSharedMemory, project: Project
) -> None:
    """12_Risk_Analysis.md: a gate that notified while work continued is not a gate."""
    await build_runner(memory).advance(project.id)

    architecture = await memory.artifacts.list_for_project(
        project.id, stage=LifecycleStage.ARCHITECTURE
    )
    assert architecture == [], "no architecture may exist while requirements await approval"


async def test_gate_records_the_five_reviewer_fields(
    memory: SqlSharedMemory, project: Project
) -> None:
    """10_UI_UX_Plan.md requires: what changed, why, who was involved, impact, actions."""
    await build_runner(memory).advance(project.id)

    request = (await memory.approvals.list_for_project(project.id, pending_only=True))[0]

    assert request.kind is ApprovalKind.REQUIREMENTS
    assert request.what_changed
    assert request.why
    assert request.requested_by is AgentRole.EXECUTIVE
    assert request.agents_involved
    assert request.artifact_ids


async def test_rejection_blocks_and_feedback_reaches_the_agent(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A rejection must teach on re-run rather than merely repeat."""
    provider = ContextAwareProvider(STAGE_OUTPUTS)
    runner = build_runner(memory, provider=provider)

    await runner.advance(project.id)

    pending = (await memory.approvals.list_for_project(project.id, pending_only=True))[0]
    pending.status = ApprovalStatus.CHANGES_REQUESTED
    pending.feedback = "Billing scope is unclear — split it out."
    await memory.approvals.update(pending)

    blocked = await runner.advance(project.id)

    assert blocked.is_blocked
    assert "Billing scope is unclear" in blocked.halt_reason


async def test_no_second_gate_is_raised_while_one_is_pending(
    memory: SqlSharedMemory, project: Project
) -> None:
    runner = build_runner(memory)

    await runner.advance(project.id)
    second = await runner.advance(project.id)

    assert second.awaiting_approval
    assert len(await memory.approvals.list_for_project(project.id)) == 1


# --- Conflict detection -------------------------------------------------------


async def test_stale_derivation_halts_the_workflow(
    memory: SqlSharedMemory, project: Project
) -> None:
    """A conflicting state is detected rather than silently built upon."""
    runner = build_runner(memory)
    await runner.advance(project.id)
    await approve_latest(memory, project.id)
    await runner.advance(project.id)

    # A human revises the requirements the architecture was derived from.
    prd = (
        await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.PRD)
    )[0]
    await memory.artifacts.append_version(
        prd.id,
        ArtifactVersion(artifact_id=prd.id, version=1, body_markdown="# Revised requirements"),
    )

    outcome = await runner.advance(project.id)

    assert outcome.is_blocked
    assert not outcome.made_progress
    kinds = {conflict["kind"] for conflict in outcome.conflicts}
    assert ConflictKind.STALE_DERIVATION.value in kinds


async def test_duplicate_approved_artifacts_halt_the_workflow(
    memory: SqlSharedMemory, project: Project
) -> None:
    runner = build_runner(memory)
    await runner.advance(project.id)

    prds = await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.PRD)
    for prd in prds:
        prd.status = ArtifactStatus.APPROVED
        await memory.artifacts.update(prd)

    duplicate = await memory.artifacts.create(
        prds[0].model_copy(update={"id": "art_" + "d" * 32, "status": ArtifactStatus.APPROVED})
    )
    await memory.artifacts.append_version(
        duplicate.id,
        ArtifactVersion(artifact_id=duplicate.id, version=1, body_markdown="# Competing PRD"),
    )

    outcome = await runner.advance(project.id)

    assert outcome.is_blocked
    kinds = {conflict["kind"] for conflict in outcome.conflicts}
    assert ConflictKind.DUPLICATE_AUTHORITY.value in kinds


# --- Traceability through orchestration ---------------------------------------


async def test_orchestrated_agents_build_a_connected_trace_graph(
    memory: SqlSharedMemory, project: Project
) -> None:
    """Every downstream artifact traces back to what it was derived from."""
    runner = build_runner(memory)
    await runner.advance(project.id)
    await approve_latest(memory, project.id)
    await runner.advance(project.id)

    architecture = (
        await memory.artifacts.list_for_project(
            project.id, artifact_type=ArtifactType.SYSTEM_ARCHITECTURE
        )
    )[0]

    upstream = await memory.traces.upstream_of(architecture.id)
    assert upstream, "the architecture must declare what it was derived from"

    prd = (
        await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.PRD)
    )[0]
    impact = await memory.traces.analyse_impact(project.id, prd.id)
    assert architecture.id in impact.artifact_ids


# --- Observability ------------------------------------------------------------


async def test_every_transition_is_recorded(
    memory: SqlSharedMemory, project: Project
) -> None:
    await build_runner(memory).advance(project.id)

    types = {event.type for event in await memory.events.list_for_project(project.id)}

    assert EventType.STAGE_STARTED in types
    assert EventType.STAGE_COMPLETED in types
    assert EventType.AGENT_STARTED in types
    assert EventType.AGENT_COMPLETED in types
    assert EventType.ARTIFACT_CREATED in types
    assert EventType.APPROVAL_REQUESTED in types


async def test_structured_assignment_is_recorded(
    memory: SqlSharedMemory, project: Project
) -> None:
    """05_AI_Agent_Architecture.md's structured communication model, made visible."""
    await build_runner(memory).advance(project.id)

    events = await memory.events.list_for_project(project.id)
    assignments = [
        event.payload["assignment"]
        for event in events
        if "assignment" in event.payload
    ]

    assert assignments
    first = assignments[0]
    assert isinstance(first, dict)
    for field in ("sender", "receiver", "task", "required_actions"):
        assert field in first
    assert first["sender"] == AgentRole.EXECUTIVE.value


async def test_project_stage_state_tracks_progress(
    memory: SqlSharedMemory, project: Project
) -> None:
    await build_runner(memory).advance(project.id)

    updated = await memory.projects.get(project.id)
    completed = set(updated.completed_stages)

    assert LifecycleStage.REQUIREMENT_DISCOVERY in completed
    assert LifecycleStage.BUSINESS_VALIDATION in completed

    architecture_state = updated.stage_state(LifecycleStage.ARCHITECTURE)
    assert architecture_state is not None
    assert architecture_state.status is StageStatus.AWAITING_APPROVAL


# --- Failure handling ---------------------------------------------------------


async def test_unregistered_stage_halts_with_an_explanation(
    memory: SqlSharedMemory, project: Project
) -> None:
    """An empty organization must state why it cannot proceed, not silently pass."""
    runner = build_runner(memory, roles={})

    outcome = await runner.advance(project.id)

    assert outcome.is_blocked
    assert "No agent is registered" in outcome.halt_reason
    assert not outcome.made_progress


async def test_agent_failure_halts_and_marks_the_stage_blocked(
    memory: SqlSharedMemory, project: Project
) -> None:
    class FailingProvider(ContextAwareProvider):
        async def complete_structured[T: BaseModel](
            self, request: CompletionRequest, schema: type[T]
        ) -> StructuredResponse[T]:
            raise ProviderError("model unavailable")

    outcome = await build_runner(
        memory,
        provider=FailingProvider(STAGE_OUTPUTS),
        roles={AgentRole.PRODUCT_MANAGER: LifecycleStage.REQUIREMENT_DISCOVERY},
    ).advance(project.id)

    assert outcome.is_blocked
    assert outcome.error is not None

    updated = await memory.projects.get(project.id)
    state = updated.stage_state(LifecycleStage.REQUIREMENT_DISCOVERY)
    assert state is not None
    assert state.status is StageStatus.BLOCKED


async def test_advancing_an_unknown_project_raises(memory: SqlSharedMemory) -> None:
    from app.domain.errors import NotFoundError

    with pytest.raises(NotFoundError):
        await build_runner(memory).advance("prj_missing")


# --- Executive boundary -------------------------------------------------------


async def test_executive_produces_no_engineering_artifacts(
    memory: SqlSharedMemory, project: Project
) -> None:
    """15_Development_Guidelines.md: the Executive coordinates, never performs.

    Enforced structurally — ExecutiveAI is not a BaseAgent and has no artifact
    path — and asserted here so a future change that gave it one would fail.
    """
    runner = build_runner(memory)
    await runner.advance(project.id)
    await approve_latest(memory, project.id)
    await runner.advance(project.id)

    artifacts = await memory.artifacts.list_for_project(project.id)

    assert artifacts, "the specialists must have produced work"
    assert all(artifact.owner_role is not AgentRole.EXECUTIVE for artifact in artifacts)

    runs = await memory.runs.list_for_project(project.id)
    assert all(run.role is not AgentRole.EXECUTIVE for run in runs)
