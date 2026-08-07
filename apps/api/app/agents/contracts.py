"""Agent output contracts.

Every agent returns a validated instance of a contract derived from
:class:`AgentOutput`. Two consequences follow, both required by the
specification:

- Downstream agents read structured fields rather than parsing prose, which is
  what `05_AI_Agent_Architecture.md` means by "structured communication over
  isolated prompt execution".
- Every output carries reasoning and confidence, which `12_Risk_Analysis.md`
  names as the mitigations for AI hallucination and loss of user trust. They are
  required fields, so an agent cannot omit them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.artifacts import ArtifactType
from app.domain.traceability import TraceKind


class TraceLink(BaseModel):
    """A declared dependency on an upstream artifact.

    The agent's own account of what it used and why. Becoming a
    :class:`app.domain.traceability.TraceEdge` when the artifact is persisted,
    this is what makes the traceability graph a record of actual reasoning rather
    than an inferred guess.
    """

    model_config = ConfigDict(frozen=True)

    upstream_artifact_id: str = Field(
        description="ID of an artifact supplied in this agent's context."
    )
    kind: TraceKind = TraceKind.DERIVES_FROM
    rationale: str = Field(
        default="",
        max_length=500,
        description="Why this upstream informed the output. Shown in impact previews.",
    )


class ArtifactDraft(BaseModel):
    """An artifact an agent proposes to write."""

    type: ArtifactType
    title: str = Field(min_length=1, max_length=300)

    body_markdown: str = Field(
        min_length=1,
        description="Rendered form, shown in the workspace and Knowledge Base.",
    )
    content: dict[str, object] = Field(
        default_factory=dict,
        description="Structured form that downstream agents read instead of the prose.",
    )
    summary: str = Field(
        default="",
        max_length=300,
        description="One line on what this is or what changed, shown in version history.",
    )

    derived_from: list[TraceLink] = Field(
        default_factory=list,
        description=(
            "Upstream artifacts this was produced from. Required whenever the "
            "agent was given any context — see BaseAgent's orphan guard."
        ),
    )


class AgentOutput(BaseModel):
    """Base contract every agent output extends."""

    reasoning: str = Field(
        min_length=1,
        description=(
            "Why the agent decided what it did. Surfaced in the Agent "
            "Organization view; not an internal debugging field."
        ),
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The agent's own assessment. Low confidence is a legitimate answer "
            "and should route to human review rather than be inflated."
        ),
    )
    artifacts: list[ArtifactDraft] = Field(
        default_factory=list, description="Artifacts to write to shared memory."
    )

    concerns: list[str] = Field(
        default_factory=list,
        description=(
            "Problems found in upstream work. `02_Proposed_Solution.md` requires "
            "each stage to be able to flag inconsistencies in the stages before "
            "it, rather than silently working around them."
        ),
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this output should stop at a human gate before proceeding.",
    )
    approval_reason: str = Field(
        default="", description="Why approval is needed, shown in the Approval Center."
    )


class AgentResult(BaseModel):
    """What an agent run produced, after persistence.

    Returned to the orchestrator, which decides what happens next.
    """

    run_id: str
    output: AgentOutput
    artifact_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)

    @property
    def has_concerns(self) -> bool:
        return bool(self.output.concerns)
