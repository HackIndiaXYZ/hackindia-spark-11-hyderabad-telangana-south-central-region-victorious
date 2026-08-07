"""Engineering artifacts and their append-only version history.

The model separates two things that are usually conflated:

- **Artifact** — stable identity. "The system architecture for project X." Its ID
  never changes, so traceability edges pointing at it survive every revision.
- **ArtifactVersion** — immutable content at a point in time. Never updated, only
  superseded.

That separation is what makes `12_Risk_Analysis.md`'s "version-controlled
engineering artifacts" mitigation real: revising an artifact appends a version
and leaves every prior version intact and citable, so a decision made in week one
can still be inspected exactly as the agent that consumed it saw it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import AgentRole, LifecycleStage


class ArtifactType(StrEnum):
    """Every artifact the MVP organization produces.

    Drawn from the Engineering Artifacts list in `09_MVP_Roadmap.md` and the
    per-agent outputs in `05_AI_Agent_Architecture.md`.
    """

    # Product Manager
    PRD = "prd"
    USER_STORIES = "user_stories"
    FUNCTIONAL_REQUIREMENTS = "functional_requirements"
    NON_FUNCTIONAL_REQUIREMENTS = "non_functional_requirements"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"

    # Business Analyst
    BUSINESS_ANALYSIS = "business_analysis"
    GAP_ANALYSIS = "gap_analysis"
    RISK_REGISTER = "risk_register"

    # Software Architect
    SYSTEM_ARCHITECTURE = "system_architecture"
    API_CONTRACT = "api_contract"
    DATABASE_SCHEMA = "database_schema"
    TECHNOLOGY_DECISION = "technology_decision"
    ENGINEERING_DECISION = "engineering_decision"
    IMPLEMENTATION_PLAN = "implementation_plan"

    # Full Stack Engineer
    REPOSITORY_STRUCTURE = "repository_structure"
    SOURCE_FILE = "source_file"

    # QA Engineer
    TEST_PLAN = "test_plan"
    TEST_CASES = "test_cases"
    COVERAGE_REPORT = "coverage_report"

    # Documentation
    README = "readme"
    API_DOCUMENTATION = "api_documentation"
    ARCHITECTURE_DOCUMENT = "architecture_document"
    DEVELOPER_GUIDE = "developer_guide"
    CHANGELOG = "changelog"
    DEPLOYMENT_PLAN = "deployment_plan"


class ArtifactStatus(StrEnum):
    """Approval state of an artifact.

    Deliberately excludes staleness. Whether an artifact has fallen behind its
    upstream is *derived* from the traceability graph
    (:func:`app.domain.traceability.stale_edges`), never stored — a stored flag
    would be one more thing that can silently disagree with reality, which is the
    exact failure this platform exists to prevent.
    """

    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactVersion(BaseModel):
    """Immutable content of an artifact at one point in time."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: new_id(IdPrefix.VERSION))
    artifact_id: str
    version: int = Field(ge=1, description="1-based, contiguous, never reused.")

    body_markdown: str = Field(
        description="Rendered form, shown in the workspace and the Knowledge Base."
    )
    content: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured form, validated against the producing agent's output "
            "contract. Downstream agents read this rather than parsing prose."
        ),
    )

    produced_by_run_id: str | None = Field(
        default=None,
        description=(
            "The agent run that authored this version. Half of the traceability "
            "guarantee: every artifact answers 'which agent produced me, and why'."
        ),
    )
    summary: str = Field(
        default="",
        description="One line on what changed and why, shown in version history.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Producing agent's self-reported confidence. `12_Risk_Analysis.md` "
            "lists confidence scoring as a hallucination mitigation."
        ),
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Artifact(BaseModel):
    """Stable identity of an engineering artifact across all its versions."""

    id: str = Field(default_factory=lambda: new_id(IdPrefix.ARTIFACT))
    project_id: str
    type: ArtifactType
    title: str

    stage: LifecycleStage = Field(description="Lifecycle stage that produced it.")
    owner_role: AgentRole = Field(description="Agent role responsible for it.")

    status: ArtifactStatus = ArtifactStatus.DRAFT
    current_version: int = Field(default=0, ge=0, description="0 until first write.")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def has_content(self) -> bool:
        """Whether any version has been written yet."""
        return self.current_version > 0

    @property
    def is_approved(self) -> bool:
        return self.status is ArtifactStatus.APPROVED


class ArtifactWithVersion(BaseModel):
    """An artifact together with one of its versions.

    The shape the API and agents actually want: identity plus content, resolved
    in a single read rather than two.
    """

    artifact: Artifact
    version: ArtifactVersion

    @property
    def is_latest(self) -> bool:
        return self.version.version == self.artifact.current_version
