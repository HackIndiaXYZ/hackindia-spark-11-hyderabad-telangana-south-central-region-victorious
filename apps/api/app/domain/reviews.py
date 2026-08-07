"""Engineering review of a produced artifact.

The organization checks its own work. After a specialist produces an artifact, a
reviewer scores it and records what is strong, what is weak, and what would
improve it — the engineering-review step a real organization performs before the
work reaches a human.

`12_Risk_Analysis.md` prescribes "cross-validation between engineering agents" as
a mitigation for AI hallucination. The Business Analyst already validates the
Product Manager's requirements; this generalises that check to every artifact,
independent of the specialist that produced it.

A review is attached to an artifact **version**, not to an artifact. Revising an
artifact produces a new version that has not been reviewed, exactly as it has not
been approved — a score must never outlive the content it was given.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import AgentRole, LifecycleStage


class ReviewVerdict(StrEnum):
    """The reviewer's overall judgement."""

    APPROVED = "approved"
    """Sound as produced."""

    APPROVED_WITH_SUGGESTIONS = "approved_with_suggestions"
    """Usable, with improvements worth making."""

    NEEDS_REVISION = "needs_revision"
    """A defect a downstream specialist would inherit."""

    @property
    def is_acceptable(self) -> bool:
        """Whether downstream work may proceed on this artifact."""
        return self is not ReviewVerdict.NEEDS_REVISION


class ReviewFinding(BaseModel):
    """One observation, with the check that produced it.

    ``source`` distinguishes a deterministic structural check from a reasoned
    judgement. A user reading a weakness deserves to know whether it is a fact
    about the artifact or an opinion about it.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    source: str = Field(
        default="check",
        description="'check' for a deterministic rule, 'reasoning' for a model judgement.",
    )


class ArtifactReview(BaseModel):
    """A scored review of one version of one artifact."""

    id: str = Field(default_factory=lambda: new_id(IdPrefix.REVIEW))
    project_id: str
    artifact_id: str
    artifact_version: int = Field(ge=1)

    stage: LifecycleStage
    role: AgentRole = Field(description="The specialist whose work is under review.")
    produced_by_run_id: str | None = None

    quality_score: int = Field(
        ge=0,
        le=100,
        description=(
            "Composite score. The deterministic checks set the floor and carry the "
            "weight, so a score means something even with no model available; "
            "reasoning adjusts it within a bounded range."
        ),
    )
    verdict: ReviewVerdict = ReviewVerdict.APPROVED

    summary: str = Field(default="", description="One line, shown in lists.")
    strengths: list[ReviewFinding] = Field(default_factory=list)
    weaknesses: list[ReviewFinding] = Field(default_factory=list)
    suggestions: list[ReviewFinding] = Field(default_factory=list)

    deterministic_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="The structural score before any reasoning adjustment.",
    )
    reasoning_applied: bool = Field(
        default=False,
        description=(
            "Whether a model contributed. False means the review is purely "
            "structural — honest, and visibly so in the workspace."
        ),
    )
    reviewer_provider: str | None = None
    reviewer_model: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def band(self) -> str:
        """Coarse quality band, for badges and grouping."""
        if self.quality_score >= 85:
            return "strong"
        if self.quality_score >= 70:
            return "sound"
        if self.quality_score >= 50:
            return "weak"
        return "poor"
