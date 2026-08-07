"""Software Architect Agent — architecture and development planning.

`05_AI_Agent_Architecture.md`: system architecture, component design, service
decomposition, scalability planning, API planning, technology recommendations.

Two stages, two agents, one role. The architect designs the system in
``ARCHITECTURE`` and sequences the work in ``DEVELOPMENT_PLANNING``. They are
separate agents because each has a distinct output contract and a distinct
approval gate between them — `09_MVP_Roadmap.md` requires architecture sign-off
before work is planned against it.
"""

from __future__ import annotations

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.models import (
    ApiEndpoint,
    Component,
    DataEntity,
    ImplementationTask,
    TechnologyChoice,
)
from app.agents.rendering import bullets, code_block, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext


class ArchitectOutput(AgentOutput):
    """What the Software Architect produces during design."""

    style: str = Field(
        description="The architectural style chosen, e.g. 'modular monolith'."
    )
    style_rationale: str = Field(
        description="Why this style suits these requirements and this scale."
    )

    components: list[Component] = Field(default_factory=list)
    technology_choices: list[TechnologyChoice] = Field(default_factory=list)
    api_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    data_entities: list[DataEntity] = Field(default_factory=list)

    scalability_notes: list[str] = Field(default_factory=list)
    security_notes: list[str] = Field(
        default_factory=list,
        description="Authentication, authorisation, and data-protection decisions.",
    )


class SoftwareArchitectAgent(BaseAgent[ArchitectOutput]):
    """Turns validated requirements into a system design."""

    role = AgentRole.SOFTWARE_ARCHITECT
    stage = LifecycleStage.ARCHITECTURE
    output_model = ArchitectOutput
    prompt_name = "software_architect"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Design the system architecture for **{context.project_name}**.\n\n"
            "Every component must trace to the requirements it serves, and every "
            "technology choice must name what you considered and rejected, with "
            "the trade-off you accepted. A choice recorded without alternatives "
            "cannot be reviewed, and a human approves this before implementation.\n\n"
            "Take the Business Analyst's questioned requirements and gaps "
            "seriously. If a gap blocks a sound design, raise it in `concerns` "
            "rather than designing around it silently.\n\n"
            "Set `requires_approval` when your technology selections commit the "
            "project to something costly to reverse."
        )

    def compose_artifacts(
        self, output: ArchitectOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)

        architecture = sections(
            heading(f"System Architecture — {context.project_name}"),
            heading("Architectural style", 2),
            paragraph(f"**{output.style}**"),
            paragraph(output.style_rationale),
            heading("Components", 2),
            table(
                ["Component", "Responsibility", "Depends on", "Requirements"],
                [
                    [item.name, item.responsibility, item.depends_on, item.requirement_ids]
                    for item in output.components
                ],
            ),
            heading("Component diagram", 2),
            code_block(_mermaid(output.components), "mermaid"),
            heading("Scalability", 2),
            bullets(output.scalability_notes),
            heading("Security", 2),
            bullets(output.security_notes),
        )

        technology = sections(
            heading(f"Technology Decisions — {context.project_name}"),
            paragraph(
                "Each decision records what was considered and what the choice "
                "costs. These require human approval before implementation."
            ),
            table(
                ["Layer", "Choice", "Alternatives considered", "Rationale", "Trade-offs"],
                [
                    [
                        item.layer,
                        item.choice,
                        item.alternatives,
                        item.rationale,
                        item.tradeoffs,
                    ]
                    for item in output.technology_choices
                ],
            ),
        )

        api = sections(
            heading(f"API Contract — {context.project_name}"),
            table(
                ["Method", "Path", "Purpose", "Request", "Response", "Requirements"],
                [
                    [
                        item.method,
                        item.path,
                        item.purpose,
                        item.request_summary,
                        item.response_summary,
                        item.requirement_ids,
                    ]
                    for item in output.api_endpoints
                ],
            ),
        )

        schema = sections(
            heading(f"Database Schema — {context.project_name}"),
            *[
                sections(
                    heading(entity.name, 2),
                    paragraph(entity.purpose),
                    table(
                        ["Field", "Type", "Nullable", "Description"],
                        [
                            [field.name, field.type, str(field.nullable), field.description]
                            for field in entity.fields
                        ],
                    ),
                    heading("Relationships", 3),
                    bullets(entity.relationships),
                )
                for entity in output.data_entities
            ],
        )

        return [
            ArtifactDraft(
                type=ArtifactType.SYSTEM_ARCHITECTURE,
                title=f"System Architecture — {context.project_name}",
                body_markdown=architecture,
                content={
                    "style": output.style,
                    "components": [c.model_dump(mode="json") for c in output.components],
                    "scalability_notes": output.scalability_notes,
                    "security_notes": output.security_notes,
                },
                summary=f"{output.style} with {len(output.components)} components",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.TECHNOLOGY_DECISION,
                title=f"Technology Decisions — {context.project_name}",
                body_markdown=technology,
                content={
                    "choices": [
                        c.model_dump(mode="json") for c in output.technology_choices
                    ]
                },
                summary=f"{len(output.technology_choices)} technology decisions",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.API_CONTRACT,
                title=f"API Contract — {context.project_name}",
                body_markdown=api,
                content={
                    "endpoints": [e.model_dump(mode="json") for e in output.api_endpoints]
                },
                summary=f"{len(output.api_endpoints)} endpoints",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.DATABASE_SCHEMA,
                title=f"Database Schema — {context.project_name}",
                body_markdown=schema,
                content={
                    "entities": [e.model_dump(mode="json") for e in output.data_entities]
                },
                summary=f"{len(output.data_entities)} entities",
                derived_from=links,
            ),
        ]


class ImplementationPlanOutput(AgentOutput):
    """What the Software Architect produces while planning the build."""

    sequencing_rationale: str = Field(
        description="Why the work is ordered this way, in terms of risk and dependency."
    )
    tasks: list[ImplementationTask] = Field(default_factory=list)
    milestones: list[str] = Field(
        default_factory=list, description="Checkpoints where something is demonstrable."
    )


class ImplementationPlannerAgent(BaseAgent[ImplementationPlanOutput]):
    """Breaks an approved architecture into ordered, dependency-aware work."""

    role = AgentRole.SOFTWARE_ARCHITECT
    stage = LifecycleStage.DEVELOPMENT_PLANNING
    output_model = ImplementationPlanOutput
    prompt_name = "implementation_planner"

    def describe_task(self) -> str:
        return "Software Architect · implementation planning"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Sequence the implementation of **{context.project_name}** from the "
            "approved architecture.\n\n"
            "Produce tasks (T-nn) that each name the component they belong to, "
            "the requirements they satisfy, and the tasks they depend on. Order "
            "the work so that the riskiest and most foundational parts are built "
            "first — a plan that defers the hard part is not a plan.\n\n"
            "Every task must be small enough that its completion is unambiguous."
        )

    def compose_artifacts(
        self, output: ImplementationPlanOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        plan = sections(
            heading(f"Implementation Plan — {context.project_name}"),
            heading("Sequencing rationale", 2),
            paragraph(output.sequencing_rationale),
            heading("Tasks", 2),
            table(
                ["ID", "Task", "Component", "Depends on", "Requirements", "Estimate"],
                [
                    [
                        task.id,
                        task.title,
                        task.component,
                        task.depends_on,
                        task.requirement_ids,
                        task.estimate,
                    ]
                    for task in output.tasks
                ],
            ),
            heading("Milestones", 2),
            bullets(output.milestones),
        )

        return [
            ArtifactDraft(
                type=ArtifactType.IMPLEMENTATION_PLAN,
                title=f"Implementation Plan — {context.project_name}",
                body_markdown=plan,
                content={
                    "tasks": [task.model_dump(mode="json") for task in output.tasks],
                    "milestones": output.milestones,
                },
                summary=f"{len(output.tasks)} tasks across {len(output.milestones)} milestones",
                derived_from=self._links(output),
            )
        ]


def _mermaid(components: list[Component]) -> str:
    """Render a component dependency diagram.

    Mermaid because the workspace renders it natively and it stays readable as
    raw text inside a generated repository.
    """
    if not components:
        return "graph TD\n    empty[No components defined]"

    lines = ["graph TD"]
    aliases = {component.name: f"c{index}" for index, component in enumerate(components)}

    for component in components:
        lines.append(f'    {aliases[component.name]}["{component.name}"]')

    for component in components:
        for dependency in component.depends_on:
            if dependency in aliases:
                lines.append(f"    {aliases[component.name]} --> {aliases[dependency]}")

    return "\n".join(lines)
