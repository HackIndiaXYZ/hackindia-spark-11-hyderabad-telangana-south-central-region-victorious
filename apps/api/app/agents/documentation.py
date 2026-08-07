"""Documentation Agent — documentation and deployment preparation.

`05_AI_Agent_Architecture.md`: maintain documentation, synchronize project
knowledge, generate API and architecture documentation, generate the README.

It also owns deployment preparation in the MVP. `09_MVP_Roadmap.md` ends the
lifecycle at "Deployment Preparation" but excludes the DevOps Agent from the V1
roster — `11_Future_Roadmap.md` places it in V2. The stage still has to be owned
by someone, and what `13_Demo_and_Pitch.md` Step 11 asks to display is a
deployment checklist and environment configuration: documents, produced from
decisions the organization has already made. See ADR-0010.
"""

from __future__ import annotations

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.rendering import bullets, code_block, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext


class DocumentationOutput(AgentOutput):
    """What the Documentation agent produces."""

    readme: str = Field(
        description=(
            "Complete README in markdown: what the project is, how to run it, "
            "and how it is laid out. Written for someone who has never seen it."
        )
    )
    api_documentation: str = Field(
        description="Endpoint reference in markdown, derived from the API contract."
    )
    architecture_document: str = Field(
        description=(
            "Architecture narrative: the decisions and their reasoning, not a "
            "restatement of the component table."
        )
    )
    developer_guide: str = Field(
        description="How to work on this codebase: setup, conventions, gotchas."
    )
    changelog: str = Field(
        description="Initial changelog entry describing what the organization built."
    )


class DocumentationAgent(BaseAgent[DocumentationOutput]):
    """Generates the project's documentation from what was actually built."""

    role = AgentRole.DOCUMENTATION
    stage = LifecycleStage.DOCUMENTATION
    output_model = DocumentationOutput
    prompt_name = "documentation"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Write the documentation for **{context.project_name}**.\n\n"
            "Document what the organization actually decided and built — the "
            "architecture, the API, the schema, the scaffold — not what a "
            "project of this kind usually contains. Every statement must be "
            "supported by an artifact in your context.\n\n"
            "The architecture document should explain *why* the design is the "
            "way it is. The component table already exists; restating it adds "
            "nothing that reading the architecture artifact would not give.\n\n"
            "Be accurate about completeness. The generated repository is a "
            "scaffold, and the README must not imply otherwise."
        )

    def compose_artifacts(
        self, output: DocumentationOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)

        def draft(
            artifact_type: ArtifactType, title: str, body: str, summary: str
        ) -> ArtifactDraft:
            return ArtifactDraft(
                type=artifact_type,
                title=title,
                body_markdown=body,
                content={"markdown": body},
                summary=summary,
                derived_from=links,
            )

        return [
            draft(
                ArtifactType.README,
                f"README — {context.project_name}",
                output.readme,
                "Project README",
            ),
            draft(
                ArtifactType.API_DOCUMENTATION,
                f"API Documentation — {context.project_name}",
                output.api_documentation,
                "Endpoint reference",
            ),
            draft(
                ArtifactType.ARCHITECTURE_DOCUMENT,
                f"Architecture Document — {context.project_name}",
                output.architecture_document,
                "Architecture narrative and rationale",
            ),
            draft(
                ArtifactType.DEVELOPER_GUIDE,
                f"Developer Guide — {context.project_name}",
                output.developer_guide,
                "Setup, conventions, and gotchas",
            ),
            draft(
                ArtifactType.CHANGELOG,
                f"Changelog — {context.project_name}",
                output.changelog,
                "Initial release notes",
            ),
        ]


class DeploymentPreparationOutput(AgentOutput):
    """What the Documentation agent produces for deployment readiness."""

    overview: str = Field(description="How this system is intended to be deployed.")
    checklist: list[str] = Field(
        default_factory=list,
        description="Ordered steps to take a build to production.",
    )
    environment_variables: list[str] = Field(
        default_factory=list,
        description="Each as 'NAME — what it configures'. Never include values.",
    )
    containerisation: str = Field(
        default="",
        description="Dockerfile or compose content, if containerisation applies.",
    )
    rollback: list[str] = Field(
        default_factory=list, description="How to reverse a bad release."
    )
    outstanding: list[str] = Field(
        default_factory=list,
        description="What must be resolved before this could genuinely ship.",
    )


class DeploymentPreparationAgent(BaseAgent[DeploymentPreparationOutput]):
    """Prepares the deployment plan from the documented system."""

    role = AgentRole.DOCUMENTATION
    stage = LifecycleStage.DEPLOYMENT_PREPARATION
    output_model = DeploymentPreparationOutput
    prompt_name = "deployment_preparation"

    def describe_task(self) -> str:
        return "Documentation Engineer · deployment preparation"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Prepare **{context.project_name}** for deployment.\n\n"
            "Base the plan on the technology decisions and architecture already "
            "approved — do not introduce infrastructure the organization never "
            "chose.\n\n"
            "List environment variables by name and purpose only. Never include "
            "a value, real or example: a deployment document is exactly where a "
            "credential gets committed by accident.\n\n"
            "Be honest in `outstanding` about what still blocks a real "
            "production release. The scaffold is not a running system, and a "
            "deployment plan that pretends otherwise is worse than none."
        )

    def compose_artifacts(
        self, output: DeploymentPreparationOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        plan = sections(
            heading(f"Deployment Plan — {context.project_name}"),
            heading("Overview", 2),
            paragraph(output.overview),
            heading("Checklist", 2),
            bullets(output.checklist),
            heading("Environment variables", 2),
            paragraph("_Names and purposes only. Values belong in a secret store._"),
            table(
                ["Variable", "Purpose"],
                [
                    [part.strip() for part in entry.split("—", 1)]
                    if "—" in entry
                    else [entry, ""]
                    for entry in output.environment_variables
                ],
            ),
            heading("Containerisation", 2),
            code_block(output.containerisation, "dockerfile")
            if output.containerisation
            else "_Not applicable._",
            heading("Rollback", 2),
            bullets(output.rollback),
            heading("Outstanding before production", 2),
            bullets(output.outstanding),
        )

        return [
            ArtifactDraft(
                type=ArtifactType.DEPLOYMENT_PLAN,
                title=f"Deployment Plan — {context.project_name}",
                body_markdown=plan,
                content={
                    "checklist": output.checklist,
                    "environment_variables": output.environment_variables,
                    "rollback": output.rollback,
                    "outstanding": output.outstanding,
                },
                summary=(
                    f"{len(output.checklist)} steps, "
                    f"{len(output.outstanding)} items outstanding"
                ),
                derived_from=self._links(output),
            )
        ]
