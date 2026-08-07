"""Product Manager Agent.

`05_AI_Agent_Architecture.md`: clarify objectives, identify target users, define
functional and non-functional requirements, prioritise features, create the PRD.
Outputs a Product Requirement Document, user stories, a feature list, and
acceptance criteria.

The first stage with real work, and the one every later stage derives from. Its
acceptance criteria are what the QA agent traces test cases back to, so they are
required to be testable rather than aspirational.
"""

from __future__ import annotations

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.models import Requirement, UserStory
from app.agents.rendering import bullets, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext


class ProductManagerOutput(AgentOutput):
    """What the Product Manager produces."""

    objective: str = Field(
        description="What the product is actually trying to achieve, in one paragraph."
    )
    target_users: list[str] = Field(
        default_factory=list, description="Who this is for, specifically."
    )
    functional_requirements: list[Requirement] = Field(default_factory=list)
    non_functional_requirements: list[Requirement] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    out_of_scope: list[str] = Field(
        default_factory=list,
        description=(
            "What this product deliberately will not do. A scope boundary is a "
            "product decision, and omitting it is how scope creeps silently."
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Ambiguities in the brief that a human should resolve.",
    )


class ProductManagerAgent(BaseAgent[ProductManagerOutput]):
    """Transforms an idea into structured, prioritised requirements."""

    role = AgentRole.PRODUCT_MANAGER
    stage = LifecycleStage.REQUIREMENT_DISCOVERY
    output_model = ProductManagerOutput
    prompt_name = "product_manager"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Define the product requirements for **{context.project_name}**.\n\n"
            "Work only from the project description. Where it is silent on "
            "something material, make a reasonable assumption, state it in "
            "`open_questions`, and continue — do not stall, and do not invent "
            "detail you then treat as given.\n\n"
            "Produce functional requirements (FR-nn), non-functional requirements "
            "(NFR-nn), and user stories (US-nn) whose acceptance criteria are "
            "specific enough for a QA engineer to write a test against without "
            "asking you a question."
        )

    def compose_artifacts(
        self, output: ProductManagerOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)

        prd = sections(
            heading(f"Product Requirements — {context.project_name}"),
            heading("Objective", 2),
            paragraph(output.objective),
            heading("Target users", 2),
            bullets(output.target_users),
            heading("Functional requirements", 2),
            table(
                ["ID", "Requirement", "Priority", "Rationale"],
                [
                    [item.id, item.title, item.priority.value, item.rationale]
                    for item in output.functional_requirements
                ],
            ),
            heading("Non-functional requirements", 2),
            table(
                ["ID", "Requirement", "Priority", "Detail"],
                [
                    [item.id, item.title, item.priority.value, item.description]
                    for item in output.non_functional_requirements
                ],
            ),
            heading("Out of scope", 2),
            bullets(output.out_of_scope),
            heading("Open questions", 2),
            bullets(output.open_questions),
        )

        stories = sections(
            heading(f"User Stories — {context.project_name}"),
            *[
                sections(
                    heading(f"{story.id} — {story.i_want}", 2),
                    paragraph(
                        f"**As a** {story.as_a} **I want** {story.i_want} "
                        f"**so that** {story.so_that}"
                    ),
                    paragraph(f"_Priority: {story.priority.value} · "
                              f"Requirements: {', '.join(story.requirement_ids) or '—'}_"),
                    heading("Acceptance criteria", 3),
                    bullets(story.acceptance_criteria),
                )
                for story in output.user_stories
            ],
        )

        criteria = sections(
            heading(f"Acceptance Criteria — {context.project_name}"),
            paragraph(
                "Every criterion below is traceable to a user story. The QA "
                "Engineer writes test cases against these."
            ),
            table(
                ["Story", "Criterion", "Requirements"],
                [
                    [story.id, criterion, story.requirement_ids]
                    for story in output.user_stories
                    for criterion in story.acceptance_criteria
                ],
            ),
        )

        return [
            ArtifactDraft(
                type=ArtifactType.PRD,
                title=f"Product Requirements — {context.project_name}",
                body_markdown=prd,
                content={
                    "objective": output.objective,
                    "target_users": output.target_users,
                    "functional_requirements": [
                        item.model_dump(mode="json")
                        for item in output.functional_requirements
                    ],
                    "non_functional_requirements": [
                        item.model_dump(mode="json")
                        for item in output.non_functional_requirements
                    ],
                    "out_of_scope": output.out_of_scope,
                    "open_questions": output.open_questions,
                },
                summary=(
                    f"{len(output.functional_requirements)} functional and "
                    f"{len(output.non_functional_requirements)} non-functional requirements"
                ),
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.USER_STORIES,
                title=f"User Stories — {context.project_name}",
                body_markdown=stories,
                content={
                    "user_stories": [
                        story.model_dump(mode="json") for story in output.user_stories
                    ]
                },
                summary=f"{len(output.user_stories)} user stories",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.ACCEPTANCE_CRITERIA,
                title=f"Acceptance Criteria — {context.project_name}",
                body_markdown=criteria,
                content={
                    "criteria": [
                        {
                            "story_id": story.id,
                            "criterion": criterion,
                            "requirement_ids": story.requirement_ids,
                        }
                        for story in output.user_stories
                        for criterion in story.acceptance_criteria
                    ]
                },
                summary=(
                    f"{sum(len(s.acceptance_criteria) for s in output.user_stories)} "
                    "testable criteria"
                ),
                derived_from=links,
            ),
        ]
