"""Structured engineering values shared across agent contracts.

`05_AI_Agent_Architecture.md` requires agents to exchange structured artifacts
rather than prose, so a downstream agent reads fields instead of re-parsing a
document. These are those fields.

Each type carries a stable, human-readable identifier (``FR-01``, ``US-03``).
Those identifiers are what let the QA agent trace a test case back to an
acceptance criterion, and the architect tie a component to the requirements it
serves — traceability *inside* an artifact, complementing the artifact-level
graph in :mod:`app.domain.traceability`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    """MoSCoW prioritisation.

    `05_AI_Agent_Architecture.md` lists "Prioritize features" as a Product
    Manager responsibility. MoSCoW is used because it forces an explicit
    "won't" — a scope boundary, which is what makes the MVP argument checkable.
    """

    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class Severity(StrEnum):
    """Impact of a gap, risk, or defect."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Likelihood(StrEnum):
    """Probability of a risk materialising."""

    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


class Requirement(BaseModel):
    """One functional or non-functional requirement."""

    id: str = Field(description="Stable identifier, e.g. FR-01 or NFR-03.")
    title: str = Field(max_length=200)
    description: str = Field(description="What the system must do, specifically.")
    priority: Priority = Priority.SHOULD
    rationale: str = Field(
        default="",
        description="Why this is required. The part a codebase can never recover.",
    )


class UserStory(BaseModel):
    """A requirement expressed from the user's point of view."""

    id: str = Field(description="Stable identifier, e.g. US-01.")
    as_a: str = Field(description="The role the story serves.")
    i_want: str
    so_that: str = Field(description="The outcome that makes it worth building.")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Testable conditions. The QA agent traces test cases to these.",
    )
    requirement_ids: list[str] = Field(
        default_factory=list, description="Requirements this story realises."
    )
    priority: Priority = Priority.SHOULD


class Gap(BaseModel):
    """Something missing or underspecified in upstream work."""

    area: str = Field(description="What the gap concerns.")
    description: str
    severity: Severity = Severity.MEDIUM
    recommendation: str = Field(description="What should be done about it.")
    requirement_ids: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    """A risk to delivery or to the product."""

    description: str
    impact: Severity = Severity.MEDIUM
    likelihood: Likelihood = Likelihood.POSSIBLE
    mitigation: str = Field(description="How the risk is reduced or absorbed.")


class Component(BaseModel):
    """A unit of the system architecture."""

    name: str
    responsibility: str = Field(description="What it owns. One responsibility.")
    depends_on: list[str] = Field(
        default_factory=list, description="Other component names it requires."
    )
    requirement_ids: list[str] = Field(
        default_factory=list, description="Requirements this component serves."
    )


class TechnologyChoice(BaseModel):
    """A technology decision with its alternatives and trade-offs.

    Alternatives and trade-offs are required rather than optional: a decision
    recorded without them is unreviewable, and `09_MVP_Roadmap.md` puts
    technology selection behind a human approval gate.
    """

    layer: str = Field(description="Where it applies, e.g. backend, database.")
    choice: str
    alternatives: list[str] = Field(
        default_factory=list, description="What was considered and not chosen."
    )
    rationale: str
    tradeoffs: str = Field(default="", description="What this choice costs.")


class ApiEndpoint(BaseModel):
    """One endpoint of the API contract."""

    method: str = Field(description="HTTP method, uppercase.")
    path: str = Field(description="Route, e.g. /api/v1/patients/{id}.")
    purpose: str
    request_summary: str = Field(default="", description="Shape of the request body.")
    response_summary: str = Field(default="", description="Shape of the response.")
    requirement_ids: list[str] = Field(default_factory=list)


class DataField(BaseModel):
    """One column of a data entity."""

    name: str
    type: str = Field(description="Storage type, e.g. uuid, text, timestamptz.")
    nullable: bool = False
    description: str = ""


class DataEntity(BaseModel):
    """A table or aggregate in the data model."""

    name: str
    purpose: str
    fields: list[DataField] = Field(default_factory=list)
    relationships: list[str] = Field(
        default_factory=list, description="e.g. 'many-to-one with Patient'."
    )


class ImplementationTask(BaseModel):
    """One unit of implementation work."""

    id: str = Field(description="Stable identifier, e.g. T-01.")
    title: str
    description: str
    component: str = Field(default="", description="Component it belongs to.")
    depends_on: list[str] = Field(
        default_factory=list, description="Task IDs that must finish first."
    )
    requirement_ids: list[str] = Field(default_factory=list)
    estimate: str = Field(default="", description="Rough size, e.g. 'half a day'.")


class SourceFile(BaseModel):
    """One generated file of the repository scaffold.

    Per ADR-0006 the organization produces an inspectable scaffold rather than a
    runnable application, so ``content`` is real code a reviewer can read and
    judge — not a placeholder — but the project as a whole is not claimed to run.
    """

    path: str = Field(description="Repository-relative path.")
    language: str = Field(default="", description="For syntax highlighting.")
    purpose: str = Field(description="Why this file exists.")
    content: str = Field(description="The file's contents.")


class TestCase(BaseModel):
    """One test, traced to what it verifies."""

    id: str = Field(description="Stable identifier, e.g. TC-01.")
    title: str
    given: str
    when: str
    then: str
    kind: str = Field(default="unit", description="unit, integration, or regression.")
    acceptance_criteria: str = Field(
        default="",
        description=(
            "The acceptance criterion this verifies, quoted from the user story. "
            "Traceability from a test back to the requirement that justifies it."
        ),
    )
    requirement_ids: list[str] = Field(default_factory=list)


class CoverageEntry(BaseModel):
    """Whether a requirement is covered by tests."""

    requirement_id: str
    covered: bool
    test_case_ids: list[str] = Field(default_factory=list)
    note: str = Field(default="", description="Why, when not covered.")
