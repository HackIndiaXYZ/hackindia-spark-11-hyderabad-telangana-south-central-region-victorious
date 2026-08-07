"""Business Analyst Agent.

`05_AI_Agent_Architecture.md`: validate business feasibility, market
understanding, competitor analysis, risk identification, requirement validation.
Outputs a business analysis, gap analysis, and opportunity report.

This is the platform's cross-validation step. `12_Risk_Analysis.md` prescribes
"cross-validation between engineering agents" as a mitigation for AI
hallucination, and this agent is where it happens: it reviews the Product
Manager's output and is expected to disagree with it where disagreement is
warranted. An analyst that validates everything is providing no signal.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.models import Gap, Risk
from app.agents.rendering import bullets, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext


class Feasibility(StrEnum):
    """Overall verdict on whether the requirements are viable as a product."""

    VIABLE = "viable"
    VIABLE_WITH_CHANGES = "viable_with_changes"
    NOT_VIABLE = "not_viable"


class BusinessAnalystOutput(AgentOutput):
    """What the Business Analyst produces."""

    feasibility: Feasibility = Feasibility.VIABLE
    assessment: str = Field(description="The reasoning behind the verdict.")

    validated_requirement_ids: list[str] = Field(
        default_factory=list, description="Requirement IDs that hold up to scrutiny."
    )
    questioned_requirement_ids: list[str] = Field(
        default_factory=list,
        description="Requirement IDs that are unclear, contradictory, or unjustified.",
    )

    gaps: list[Gap] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    opportunities: list[str] = Field(
        default_factory=list,
        description="Value the requirements do not yet capture.",
    )


class BusinessAnalystAgent(BaseAgent[BusinessAnalystOutput]):
    """Validates requirements before anything is designed from them."""

    role = AgentRole.BUSINESS_ANALYST
    stage = LifecycleStage.BUSINESS_VALIDATION
    output_model = BusinessAnalystOutput
    prompt_name = "business_analyst"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Validate the requirements for **{context.project_name}** before the "
            "organization designs anything from them.\n\n"
            "Your value here is scrutiny. Name the requirement IDs that do not "
            "hold up and say precisely why — ambiguous, contradictory, "
            "unjustified, or unbounded. Identify gaps between what was asked for "
            "and what the product would actually need to work.\n\n"
            "If the requirements are genuinely sound, say so and explain what "
            "you checked. Do not manufacture criticism, and do not validate "
            "everything by default — either is a failure of this role."
        )

    def compose_artifacts(
        self, output: BusinessAnalystOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)

        analysis = sections(
            heading(f"Business Analysis — {context.project_name}"),
            heading("Verdict", 2),
            paragraph(f"**{output.feasibility.value.replace('_', ' ').title()}**"),
            paragraph(output.assessment),
            heading("Requirement validation", 2),
            paragraph(
                f"**Validated ({len(output.validated_requirement_ids)}):** "
                f"{', '.join(output.validated_requirement_ids) or '—'}"
            ),
            paragraph(
                f"**Questioned ({len(output.questioned_requirement_ids)}):** "
                f"{', '.join(output.questioned_requirement_ids) or '—'}"
            ),
            heading("Opportunities", 2),
            bullets(output.opportunities),
        )

        gap_analysis = sections(
            heading(f"Gap Analysis — {context.project_name}"),
            table(
                ["Area", "Gap", "Severity", "Recommendation", "Requirements"],
                [
                    [
                        gap.area,
                        gap.description,
                        gap.severity.value,
                        gap.recommendation,
                        gap.requirement_ids,
                    ]
                    for gap in output.gaps
                ],
            ),
        )

        risk_register = sections(
            heading(f"Risk Register — {context.project_name}"),
            table(
                ["Risk", "Impact", "Likelihood", "Mitigation"],
                [
                    [risk.description, risk.impact.value, risk.likelihood.value, risk.mitigation]
                    for risk in output.risks
                ],
            ),
        )

        return [
            ArtifactDraft(
                type=ArtifactType.BUSINESS_ANALYSIS,
                title=f"Business Analysis — {context.project_name}",
                body_markdown=analysis,
                content={
                    "feasibility": output.feasibility.value,
                    "validated_requirement_ids": output.validated_requirement_ids,
                    "questioned_requirement_ids": output.questioned_requirement_ids,
                    "opportunities": output.opportunities,
                },
                summary=f"Feasibility: {output.feasibility.value.replace('_', ' ')}",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.GAP_ANALYSIS,
                title=f"Gap Analysis — {context.project_name}",
                body_markdown=gap_analysis,
                content={"gaps": [gap.model_dump(mode="json") for gap in output.gaps]},
                summary=f"{len(output.gaps)} gaps identified",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.RISK_REGISTER,
                title=f"Risk Register — {context.project_name}",
                body_markdown=risk_register,
                content={"risks": [risk.model_dump(mode="json") for risk in output.risks]},
                summary=f"{len(output.risks)} risks recorded",
                derived_from=links,
            ),
        ]
