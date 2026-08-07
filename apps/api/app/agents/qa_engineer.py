"""QA Engineer Agent.

`05_AI_Agent_Architecture.md`: test planning, unit, integration, and regression
testing, validation. Outputs test cases, bug reports, and coverage reports.

Every test case is required to name the acceptance criterion it verifies. That
turns coverage into a statement about *requirements* rather than about lines of
code — the QA agent can report that FR-07 has no test, which is a far more useful
finding than a percentage.
"""

from __future__ import annotations

from pydantic import Field

from app.agents.base import BaseAgent
from app.agents.contracts import AgentOutput, ArtifactDraft
from app.agents.models import CoverageEntry, TestCase
from app.agents.rendering import bullets, heading, paragraph, sections, table
from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.memory.context_builder import ProjectContext


class QAEngineerOutput(AgentOutput):
    """What the QA Engineer produces."""

    strategy: str = Field(
        description="The testing approach and why it fits this system's risks."
    )
    test_cases: list[TestCase] = Field(default_factory=list)
    coverage: list[CoverageEntry] = Field(
        default_factory=list,
        description="One entry per requirement, including uncovered ones.",
    )
    defects: list[str] = Field(
        default_factory=list,
        description=(
            "Problems found by inspecting the scaffold against the design — "
            "missing endpoints, schema mismatches, unhandled cases."
        ),
    )
    untestable: list[str] = Field(
        default_factory=list,
        description="Requirements too vague to test, named so they can be fixed.",
    )


class QAEngineerAgent(BaseAgent[QAEngineerOutput]):
    """Verifies the implementation against the requirements it came from."""

    role = AgentRole.QA_ENGINEER
    stage = LifecycleStage.TESTING
    output_model = QAEngineerOutput
    prompt_name = "qa_engineer"

    def build_task(self, context: ProjectContext) -> str:
        return (
            f"Plan and specify testing for **{context.project_name}**.\n\n"
            "Write test cases (TC-nn) in given/when/then form. Every case must "
            "quote the acceptance criterion it verifies and name the requirement "
            "IDs it covers — a test that cannot be traced to a requirement is a "
            "test nobody can justify keeping.\n\n"
            "Report coverage per requirement, including the ones with no test, "
            "and say why. Inspect the generated scaffold against the architecture "
            "and API contract, and record real mismatches in `defects`.\n\n"
            "If a requirement is too vague to test, put it in `untestable` rather "
            "than inventing an interpretation."
        )

    def compose_artifacts(
        self, output: QAEngineerOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        links = self._links(output)
        covered = sum(1 for entry in output.coverage if entry.covered)
        total = len(output.coverage)

        plan = sections(
            heading(f"Test Plan — {context.project_name}"),
            heading("Strategy", 2),
            paragraph(output.strategy),
            heading("Defects found", 2),
            bullets(output.defects),
            heading("Requirements that cannot be tested as written", 2),
            bullets(output.untestable),
        )

        cases = sections(
            heading(f"Test Cases — {context.project_name}"),
            table(
                ["ID", "Title", "Kind", "Given", "When", "Then", "Verifies"],
                [
                    [
                        case.id,
                        case.title,
                        case.kind,
                        case.given,
                        case.when,
                        case.then,
                        case.acceptance_criteria or ", ".join(case.requirement_ids),
                    ]
                    for case in output.test_cases
                ],
            ),
        )

        coverage = sections(
            heading(f"Coverage Report — {context.project_name}"),
            paragraph(
                f"**{covered} of {total} requirements covered**"
                if total
                else "_No requirements were available to assess._"
            ),
            paragraph(
                "Coverage is measured against requirements rather than code, so "
                "an uncovered requirement is visible as a gap rather than hidden "
                "behind a percentage."
            ),
            table(
                ["Requirement", "Covered", "Test cases", "Note"],
                [
                    [
                        entry.requirement_id,
                        "yes" if entry.covered else "no",
                        entry.test_case_ids,
                        entry.note,
                    ]
                    for entry in output.coverage
                ],
            ),
        )

        return [
            ArtifactDraft(
                type=ArtifactType.TEST_PLAN,
                title=f"Test Plan — {context.project_name}",
                body_markdown=plan,
                content={
                    "strategy": output.strategy,
                    "defects": output.defects,
                    "untestable": output.untestable,
                },
                summary=f"{len(output.defects)} defects, {len(output.untestable)} untestable",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.TEST_CASES,
                title=f"Test Cases — {context.project_name}",
                body_markdown=cases,
                content={
                    "test_cases": [case.model_dump(mode="json") for case in output.test_cases]
                },
                summary=f"{len(output.test_cases)} test cases",
                derived_from=links,
            ),
            ArtifactDraft(
                type=ArtifactType.COVERAGE_REPORT,
                title=f"Coverage Report — {context.project_name}",
                body_markdown=coverage,
                content={
                    "covered": covered,
                    "total": total,
                    "entries": [entry.model_dump(mode="json") for entry in output.coverage],
                },
                summary=f"{covered}/{total} requirements covered",
                derived_from=links,
            ),
        ]
