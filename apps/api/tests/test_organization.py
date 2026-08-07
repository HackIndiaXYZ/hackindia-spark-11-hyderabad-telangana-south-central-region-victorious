"""The full engineering organization, end to end.

Runs the `13_Demo_and_Pitch.md` hospital scenario through all nine lifecycle
stages with the real agents, the real Executive AI, the real workflow graph, and
real persistence.

The provider is scripted per agent — each factory below is a worked example of
what that agent's contract expects — but it reads artifact IDs out of the
rendered context exactly as a live model must, so the traceability contract is
exercised rather than bypassed.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from pydantic import BaseModel

from app.agents.organization import AGENT_CLASSES, build_organization
from app.core.config import DatabaseSettings
from app.db.session import Database
from app.domain.agents import TokenUsage
from app.domain.approvals import ApprovalStatus
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import STAGE_OWNERS, AgentRole, LifecycleStage
from app.domain.projects import Project
from app.events.bus import EventBus
from app.llm.provider import CompletionRequest, CompletionResponse, StructuredResponse
from app.memory.context_builder import ContextBuilder
from app.memory.sql_repository import SqlSharedMemory
from app.orchestration.dispatcher import RegistryDispatcher
from app.orchestration.runner import OrchestrationRunner

ARTIFACT_ID_PATTERN = re.compile(r"art_[0-9a-f]{32}")

#: The eight artifacts `09_MVP_Roadmap.md` says the MVP must generate.
REQUIRED_ARTIFACTS = {
    ArtifactType.PRD,
    ArtifactType.USER_STORIES,
    ArtifactType.SYSTEM_ARCHITECTURE,
    ArtifactType.API_CONTRACT,
    ArtifactType.DATABASE_SCHEMA,
    ArtifactType.SOURCE_FILE,
    ArtifactType.README,
    ArtifactType.ARCHITECTURE_DOCUMENT,
}


# --- Scripted payloads, one per agent contract --------------------------------


def _product_manager() -> dict[str, Any]:
    return {
        "objective": "Coordinate patient care, scheduling, and billing in one system.",
        "target_users": ["Reception staff", "Doctors", "Billing administrators"],
        "functional_requirements": [
            {
                "id": "FR-01",
                "title": "Register a patient",
                "description": "Staff can create a patient record with demographics.",
                "priority": "must",
                "rationale": "Nothing else in the system works without a patient record.",
            },
            {
                "id": "FR-02",
                "title": "Book an appointment",
                "description": "Staff book a patient with a doctor at a time slot.",
                "priority": "must",
                "rationale": "Scheduling is the primary daily workflow.",
            },
        ],
        "non_functional_requirements": [
            {
                "id": "NFR-01",
                "title": "Patient data confidentiality",
                "description": "Records are accessible only to authorised roles.",
                "priority": "must",
                "rationale": "Clinical data carries regulatory obligations.",
            }
        ],
        "user_stories": [
            {
                "id": "US-01",
                "as_a": "receptionist",
                "i_want": "to book an appointment for a patient",
                "so_that": "the patient is seen by the right doctor",
                "acceptance_criteria": [
                    "Booking a free slot succeeds and returns a confirmation.",
                    "Booking an already-taken slot is rejected with a conflict error.",
                ],
                "requirement_ids": ["FR-02"],
                "priority": "must",
            }
        ],
        "out_of_scope": ["Insurance claim submission"],
        "open_questions": ["Which regulatory regime applies to this deployment?"],
    }


def _business_analyst() -> dict[str, Any]:
    return {
        "feasibility": "viable_with_changes",
        "assessment": "The core workflows are sound; access control is underspecified.",
        "validated_requirement_ids": ["FR-01", "FR-02"],
        "questioned_requirement_ids": ["NFR-01"],
        "gaps": [
            {
                "area": "Access control",
                "description": "NFR-01 names no roles or permission model.",
                "severity": "high",
                "recommendation": "Define roles before the architecture is designed.",
                "requirement_ids": ["NFR-01"],
            }
        ],
        "risks": [
            {
                "description": "Clinical data handling may require regional certification.",
                "impact": "high",
                "likelihood": "possible",
                "mitigation": "Confirm the applicable regime before go-live.",
            }
        ],
        "opportunities": ["Appointment reminders would reduce no-shows."],
    }


def _architect() -> dict[str, Any]:
    return {
        "style": "Modular monolith",
        "style_rationale": "One team, no independent scaling need; seams allow later split.",
        "components": [
            {
                "name": "patients",
                "responsibility": "Owns patient records and demographics.",
                "depends_on": [],
                "requirement_ids": ["FR-01"],
            },
            {
                "name": "scheduling",
                "responsibility": "Owns appointments and slot availability.",
                "depends_on": ["patients"],
                "requirement_ids": ["FR-02"],
            },
        ],
        "technology_choices": [
            {
                "layer": "database",
                "choice": "PostgreSQL",
                "alternatives": ["MongoDB"],
                "rationale": "Appointments need transactional integrity across tables.",
                "tradeoffs": "Flexible clinical notes need a JSONB column.",
            }
        ],
        "api_endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/appointments",
                "purpose": "Book an appointment.",
                "request_summary": "patient_id, doctor_id, slot",
                "response_summary": "appointment with confirmation code",
                "requirement_ids": ["FR-02"],
            }
        ],
        "data_entities": [
            {
                "name": "patient",
                "purpose": "A person receiving care.",
                "fields": [
                    {"name": "id", "type": "uuid", "nullable": False, "description": "PK"},
                    {"name": "name", "type": "text", "nullable": False, "description": ""},
                ],
                "relationships": ["one-to-many with appointment"],
            }
        ],
        "scalability_notes": ["Single instance is sufficient at the stated scale."],
        "security_notes": ["Role-based access on every patient-scoped endpoint."],
    }


def _planner() -> dict[str, Any]:
    return {
        "sequencing_rationale": "Data model first; scheduling conflict logic is riskiest.",
        "tasks": [
            {
                "id": "T-01",
                "title": "Patient schema and migrations",
                "description": "Create the patient table and its migration.",
                "component": "patients",
                "depends_on": [],
                "requirement_ids": ["FR-01"],
                "estimate": "half a day",
            },
            {
                "id": "T-02",
                "title": "Appointment booking with conflict rejection",
                "description": "Booking endpoint that rejects double-booked slots.",
                "component": "scheduling",
                "depends_on": ["T-01"],
                "requirement_ids": ["FR-02"],
                "estimate": "one day",
            },
        ],
        "milestones": ["Appointments can be booked and listed through the API."],
    }


def _engineer() -> dict[str, Any]:
    return {
        "repository_tree": ["app/", "app/patients/models.py", "app/scheduling/api.py"],
        "stack_summary": "FastAPI over PostgreSQL, matching the approved decisions.",
        "files": [
            {
                "path": "app/patients/models.py",
                "language": "python",
                "purpose": "Patient record model, realising FR-01.",
                "content": "class Patient:\n    id: UUID\n    name: str\n",
            }
        ],
        "not_implemented": ["Authentication flows", "Database migrations"],
    }


def _qa() -> dict[str, Any]:
    return {
        "strategy": "Cover booking conflicts first — the highest-risk behaviour.",
        "test_cases": [
            {
                "id": "TC-01",
                "title": "Double booking is rejected",
                "given": "a slot already booked with a doctor",
                "when": "a second booking is made for the same slot",
                "then": "the request is rejected with a conflict error",
                "kind": "integration",
                "acceptance_criteria": (
                    "Booking an already-taken slot is rejected with a conflict error."
                ),
                "requirement_ids": ["FR-02"],
            }
        ],
        "coverage": [
            {"requirement_id": "FR-01", "covered": False, "test_case_ids": [],
             "note": "No acceptance criteria were written for patient registration."},
            {"requirement_id": "FR-02", "covered": True, "test_case_ids": ["TC-01"], "note": ""},
        ],
        "defects": ["The scaffold has no endpoint for FR-01 despite it being a must."],
        "untestable": ["NFR-01 names no roles, so authorisation cannot be tested."],
    }


def _documentation() -> dict[str, Any]:
    return {
        "readme": "# Hospital Management System\n\nScaffold only; not a running system.",
        "api_documentation": "## POST /api/v1/appointments\n\nBooks an appointment.",
        "architecture_document": "A modular monolith was chosen because one team owns it.",
        "developer_guide": "Run migrations before starting the API.",
        "changelog": "## 0.1.0\n\nInitial scaffold generated.",
    }


def _deployment() -> dict[str, Any]:
    return {
        "overview": "Containerised deployment behind a managed PostgreSQL instance.",
        "checklist": ["Run migrations and confirm the schema version."],
        "environment_variables": ["DATABASE_URL — PostgreSQL connection string"],
        "containerisation": "FROM python:3.12-slim",
        "rollback": ["Redeploy the previous image; column drops are not reversible."],
        "outstanding": ["Authentication is not implemented.", "FR-01 has no endpoint."],
    }


PAYLOADS: dict[str, dict[str, Any]] = {
    "product_manager.requirement_discovery": _product_manager(),
    "business_analyst.business_validation": _business_analyst(),
    "software_architect.architecture": _architect(),
    "software_architect.development_planning": _planner(),
    "full_stack_engineer.implementation": _engineer(),
    "qa_engineer.testing": _qa(),
    "documentation.documentation": _documentation(),
    "documentation.deployment_preparation": _deployment(),
}


class OrganizationProvider:
    """Returns each agent's scripted payload, citing whatever context it saw."""

    name = "scripted_org"
    model = "scripted-org-1"

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise NotImplementedError

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        key = request.fixture_key or ""
        self.seen.append(key)

        payload = dict(PAYLOADS.get(key, {}))

        if payload:
            context_text = " ".join(message.content for message in request.messages)
            upstream = sorted(set(ARTIFACT_ID_PATTERN.findall(context_text)))
            payload |= {
                "reasoning": f"Completed {key} from {len(upstream)} upstream artifact(s).",
                "confidence": 0.87,
                "sources": [
                    {
                        "upstream_artifact_id": artifact_id,
                        "kind": "derives_from",
                        "rationale": "Consumed as upstream engineering input.",
                    }
                    for artifact_id in upstream
                ],
                "artifacts": [],
                "concerns": [],
                "requires_approval": False,
                "approval_reason": "",
            }
        else:
            # The Executive AI's approval narration, which has its own contract.
            payload = {
                "title": "Approve upstream work",
                "what_changed": "The organization produced artifacts for review.",
                "why": "The next stage builds directly on them.",
            }

        return StructuredResponse(
            value=schema.model_validate(payload),
            raw_json="{}",
            usage=TokenUsage(input_tokens=400, output_tokens=900),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        yield ""

    async def aclose(self) -> None:
        return None


# --- Fixtures -----------------------------------------------------------------


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:orgdb?mode=memory&cache=shared&uri=true")
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
            description=(
                "A platform for managing patients, appointments, billing, doctors, "
                "and hospital operations."
            ),
        )
    )


@pytest.fixture
def provider() -> OrganizationProvider:
    return OrganizationProvider()


def build_runner(
    memory: SqlSharedMemory, provider: OrganizationProvider
) -> OrchestrationRunner:
    events = EventBus(memory.events)
    context = ContextBuilder(memory.projects, memory.artifacts)

    dispatcher = RegistryDispatcher()
    for agent in build_organization(memory, provider, context, events):  # type: ignore[arg-type]
        dispatcher.register(agent)

    return OrchestrationRunner(memory, provider, events, dispatcher)  # type: ignore[arg-type]


async def run_lifecycle(
    memory: SqlSharedMemory, runner: OrchestrationRunner, project_id: str
) -> list[str]:
    """Advance to completion, granting each approval as a human would.

    Bounded so a workflow that stops making progress fails the test rather than
    looping.
    """
    executed: list[str] = []

    for _ in range(12):
        outcome = await runner.advance(project_id)
        executed.extend(stage.value for stage in outcome.executed_stages)

        if outcome.is_complete:
            return executed

        if outcome.awaiting_approval:
            for request in await memory.approvals.list_for_project(
                project_id, pending_only=True
            ):
                request.status = ApprovalStatus.APPROVED
                await memory.approvals.update(request)
            continue

        if outcome.is_blocked:
            raise AssertionError(f"Workflow blocked: {outcome.halt_reason}")

    raise AssertionError("Workflow did not complete within the iteration budget")


# --- Organization structure ---------------------------------------------------


def test_every_agent_matches_the_domain_owner_of_its_stage() -> None:
    """A mis-wired organization must be impossible, not merely unlikely."""
    for agent_class in AGENT_CLASSES:
        assert STAGE_OWNERS[agent_class.stage] is agent_class.role


def test_every_working_stage_has_an_agent() -> None:
    covered = {agent_class.stage for agent_class in AGENT_CLASSES}
    expected = {stage for stage in LifecycleStage if stage is not LifecycleStage.IDEA}

    assert covered == expected


def test_roster_matches_the_mvp_specification() -> None:
    """09_MVP_Roadmap.md's roster, minus the Executive AI which coordinates only."""
    roles = {agent_class.role for agent_class in AGENT_CLASSES}

    assert roles == {
        AgentRole.PRODUCT_MANAGER,
        AgentRole.BUSINESS_ANALYST,
        AgentRole.SOFTWARE_ARCHITECT,
        AgentRole.FULL_STACK_ENGINEER,
        AgentRole.QA_ENGINEER,
        AgentRole.DOCUMENTATION,
    }
    assert AgentRole.EXECUTIVE not in roles


def test_every_agent_has_its_own_prompt_and_contract() -> None:
    """05_AI_Agent_Architecture.md: independent modules, not one prompt reused."""
    from app.agents.prompts import available_prompts

    prompts = set(available_prompts())
    contracts = {agent_class.output_model for agent_class in AGENT_CLASSES}

    for agent_class in AGENT_CLASSES:
        assert agent_class.prompt_name in prompts, agent_class.__name__

    # Two agents share the Documentation role but not a contract or a prompt.
    assert len(contracts) == len(AGENT_CLASSES)


def test_dispatcher_rejects_a_role_that_does_not_own_the_stage() -> None:
    from app.agents.product_manager import ProductManagerAgent

    class Impostor(ProductManagerAgent):
        role = AgentRole.QA_ENGINEER

    dispatcher = RegistryDispatcher()

    with pytest.raises(ValueError, match="owned by"):
        dispatcher.register(Impostor(None, None, None, None))  # type: ignore[arg-type]


# --- Full lifecycle -----------------------------------------------------------


async def test_full_lifecycle_produces_every_required_artifact(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """The completion criterion: all eight artifacts from 09_MVP_Roadmap.md."""
    executed = await run_lifecycle(memory, build_runner(memory, provider), project.id)

    assert len(executed) == 8, executed

    produced = {
        artifact.type for artifact in await memory.artifacts.list_for_project(project.id)
    }
    missing = REQUIRED_ARTIFACTS - produced
    assert not missing, f"missing required artifacts: {sorted(t.value for t in missing)}"


async def test_every_agent_ran_exactly_once(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    runs = await memory.runs.list_for_project(project.id)
    stages = sorted(run.stage.value for run in runs)

    assert len(runs) == 8
    assert len(set(stages)) == 8


async def test_confidence_is_recorded_on_every_run(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """12_Risk_Analysis.md names confidence scoring as a hallucination mitigation."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    runs = await memory.runs.list_for_project(project.id)

    assert all(run.confidence is not None for run in runs)
    assert all(run.reasoning_summary for run in runs)
    assert all(run.token_usage.total > 0 for run in runs)


async def test_no_agent_writes_another_agents_artifacts(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """05_AI_Agent_Architecture.md: agents must not modify each other's state."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    for artifact in await memory.artifacts.list_for_project(project.id):
        assert STAGE_OWNERS[artifact.stage] is artifact.owner_role


async def test_every_downstream_artifact_declares_its_upstream(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """The orphan guard, verified across the whole organization."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    artifacts = await memory.artifacts.list_for_project(project.id)
    first_stage = LifecycleStage.REQUIREMENT_DISCOVERY

    for artifact in artifacts:
        if artifact.stage is first_stage:
            continue
        upstream = await memory.traces.upstream_of(artifact.id)
        assert upstream, f"{artifact.title} declares no upstream"


async def test_a_requirement_change_reaches_the_documentation(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """The differentiator, across the full organization.

    Changing the PRD marks artifacts stale all the way to the generated README —
    which is the question `04_Existing_Solutions.md` says no tool answers.
    """
    from app.domain.artifacts import ArtifactVersion

    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    prd = (
        await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.PRD)
    )[0]
    impact = await memory.traces.analyse_impact(project.id, prd.id)

    readme = (
        await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.README)
    )[0]
    assert readme.id in impact.artifact_ids, "the README must trace back to the PRD"

    await memory.artifacts.append_version(
        prd.id,
        ArtifactVersion(artifact_id=prd.id, version=1, body_markdown="# Revised requirements"),
    )

    stale_entries = await memory.traces.stale_edges(project.id)
    stale = {entry.edge.downstream_artifact_id for entry in stale_entries}
    assert stale, "revising the PRD must make its downstream stale"


# --- Rendering ----------------------------------------------------------------


async def test_artifacts_render_from_structured_output(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """The document and the structured content cannot disagree — same source."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    prd = await memory.artifacts.get_version(
        (await memory.artifacts.list_for_project(project.id, artifact_type=ArtifactType.PRD))[0].id
    )

    assert "FR-01" in prd.version.body_markdown
    assert "Register a patient" in prd.version.body_markdown
    assert prd.version.content["functional_requirements"][0]["id"] == "FR-01"


async def test_architecture_renders_a_component_diagram(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    architecture = await memory.artifacts.get_version(
        (
            await memory.artifacts.list_for_project(
                project.id, artifact_type=ArtifactType.SYSTEM_ARCHITECTURE
            )
        )[0].id
    )

    body = architecture.version.body_markdown
    assert "```mermaid" in body
    assert "graph TD" in body
    assert "scheduling" in body


async def test_coverage_report_names_uncovered_requirements(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """Coverage measured against requirements, so a gap is visible as a gap."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    coverage = await memory.artifacts.get_version(
        (
            await memory.artifacts.list_for_project(
                project.id, artifact_type=ArtifactType.COVERAGE_REPORT
            )
        )[0].id
    )

    body = coverage.version.body_markdown
    assert "1 of 2 requirements covered" in body
    assert "FR-01" in body
    assert "No acceptance criteria" in body


async def test_deployment_plan_lists_variables_without_values(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """A deployment document is where a credential gets committed by accident."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    plan = await memory.artifacts.get_version(
        (
            await memory.artifacts.list_for_project(
                project.id, artifact_type=ArtifactType.DEPLOYMENT_PLAN
            )
        )[0].id
    )

    body = plan.version.body_markdown
    assert "DATABASE_URL" in body
    assert "PostgreSQL connection string" in body
    assert "Values belong in a secret store" in body


async def test_scaffold_states_what_it_does_not_implement(
    memory: SqlSharedMemory, project: Project, provider: OrganizationProvider
) -> None:
    """ADR-0006: the output must never imply a runnable application."""
    await run_lifecycle(memory, build_runner(memory, provider), project.id)

    structure = await memory.artifacts.get_version(
        (
            await memory.artifacts.list_for_project(
                project.id, artifact_type=ArtifactType.REPOSITORY_STRUCTURE
            )
        )[0].id
    )

    body = structure.version.body_markdown
    assert "not a running application" in body
    assert "Authentication flows" in body
