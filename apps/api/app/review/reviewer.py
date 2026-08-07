"""The engineering reviewer.

Scores every artifact the organization produces. Composed of two layers:

1. **Deterministic checks** (:mod:`app.review.checks`) measure structural
   properties and set the score. They always run.
2. **Reasoning**, when a provider is available, reads the artifact *and the
   evidence from layer 1* and contributes prose plus a bounded score adjustment.

Reasoning can move the score by at most :data:`MAX_ADJUSTMENT`. That cap is the
whole design: a model can sharpen a judgement, but it cannot overturn a measured
fact, and it cannot manufacture a high score for an artifact that declares no
upstream and carries no structured content.

**Fail-open, always.** A review is a quality signal, not a gate on production. If
the provider errors, times out, or returns something unusable, the structural
review stands and the agent run completes normally. An organization that stops
working because its reviewer is unavailable would be worse than one that does not
review at all.

Helix (Mutagent's ADL conductor) specifies, evaluates, and optimizes *this
reviewer* at development time. It is not invoked here: `07_System_Architecture.md`
places Mutagent outside the runtime execution path, and nothing in this module
imports it.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from app.core.config import ReviewSettings
from app.core.logging import get_logger
from app.domain.artifacts import Artifact, ArtifactVersion
from app.domain.reviews import ArtifactReview, ReviewFinding, ReviewVerdict
from app.llm.provider import CompletionRequest, LLMProvider, Message, Role
from app.review.checks import CheckResult, is_first_stage, run_checks

logger = get_logger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "engineering_review.md"

#: The most a model may move the structural score, in either direction. Wide
#: enough for a real judgement to matter, narrow enough that a hallucinated
#: verdict cannot rescue a structurally broken artifact.
MAX_ADJUSTMENT = 12

#: How much of the artifact the reviewer reads. Enough to judge, bounded so a
#: large generated file cannot blow the context budget.
_BODY_EXCERPT_CHARS = 6000


class ReviewJudgement(BaseModel):
    """What the reviewing model returns."""

    summary: str = Field(
        max_length=300, description="One line a user reads in a list."
    )
    score_adjustment: int = Field(
        ge=-MAX_ADJUSTMENT,
        le=MAX_ADJUSTMENT,
        description=(
            "Adjustment to the structural score. Positive only for quality the "
            "checks cannot see; negative for a defect they missed."
        ),
    )
    strengths: list[str] = Field(default_factory=list, max_length=6)
    weaknesses: list[str] = Field(default_factory=list, max_length=6)
    suggestions: list[str] = Field(default_factory=list, max_length=6)


class EngineeringReviewer:
    """Reviews an artifact and returns a scored, evidenced verdict."""

    def __init__(
        self,
        provider: LLMProvider | None,
        settings: ReviewSettings,
    ) -> None:
        self._provider = provider
        self._settings = settings

    async def review(
        self,
        artifact: Artifact,
        version: ArtifactVersion,
        *,
        upstream_count: int,
    ) -> ArtifactReview:
        """Score one version of one artifact.

        Args:
            artifact: The artifact under review.
            version: The version whose content is being judged.
            upstream_count: How many upstream artifacts it declared.

        Returns:
            A review. Never raises — a failure downgrades to the structural
            review rather than propagating.
        """
        checks = run_checks(
            artifact,
            version,
            upstream_count=upstream_count,
            is_first_stage=is_first_stage(artifact.stage),
        )

        judgement = await self._judge(artifact, version, checks)

        score = checks.score
        strengths = list(checks.strengths)
        weaknesses = list(checks.weaknesses)
        suggestions = list(checks.suggestions)
        summary = _structural_summary(checks)

        # Only credit the provider when it actually contributed.
        provider = self._provider if judgement is not None else None

        if judgement is not None:
            score = max(0, min(100, checks.score + judgement.score_adjustment))
            summary = judgement.summary or summary
            strengths += [
                ReviewFinding(text=item, source="reasoning") for item in judgement.strengths
            ]
            weaknesses += [
                ReviewFinding(text=item, source="reasoning") for item in judgement.weaknesses
            ]
            suggestions += [
                ReviewFinding(text=item, source="reasoning")
                for item in judgement.suggestions
            ]

        return ArtifactReview(
            project_id=artifact.project_id,
            artifact_id=artifact.id,
            artifact_version=version.version,
            stage=artifact.stage,
            role=artifact.owner_role,
            produced_by_run_id=version.produced_by_run_id,
            quality_score=score,
            verdict=self._verdict(score),
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            deterministic_score=checks.score,
            reasoning_applied=judgement is not None,
            reviewer_provider=provider.name if provider is not None else None,
            reviewer_model=provider.model if provider is not None else None,
        )

    def _verdict(self, score: int) -> ReviewVerdict:
        """Map a score onto a verdict using the configured thresholds."""
        if score < self._settings.revision_threshold:
            return ReviewVerdict.NEEDS_REVISION
        if score < self._settings.strong_threshold:
            return ReviewVerdict.APPROVED_WITH_SUGGESTIONS
        return ReviewVerdict.APPROVED

    async def _judge(
        self, artifact: Artifact, version: ArtifactVersion, checks: CheckResult
    ) -> ReviewJudgement | None:
        """Ask a model for a judgement, or return ``None`` if unavailable.

        Every failure path returns ``None`` deliberately. The caller then keeps
        the structural review, and `reasoning_applied` records that no model
        contributed — so the workspace shows an honest score rather than a
        confident-looking one produced by nothing.
        """
        if self._provider is None or not self._settings.use_reasoning:
            return None

        try:
            response = await self._provider.complete_structured(
                CompletionRequest(
                    system=PROMPT_PATH.read_text(encoding="utf-8"),
                    messages=[
                        Message(
                            role=Role.USER,
                            content=_render_request(artifact, version, checks),
                        )
                    ],
                    # Keyed by artifact type so a recorded corpus stays readable
                    # and one recording covers every project of that shape.
                    fixture_key=f"review.{artifact.type.value}",
                    metadata={"stage": artifact.stage.value, "type": artifact.type.value},
                    max_tokens=1500,
                ),
                ReviewJudgement,
            )
            return response.value

        # Broad by design: reviewing is fail-open, so ANY provider fault must
        # degrade to the structural review rather than surface to the agent.
        except Exception:  # noqa: BLE001
            logger.warning(
                "Review reasoning unavailable; keeping the structural review",
                extra={"artifact_id": artifact.id, "type": artifact.type.value},
            )
            return None


def _render_request(
    artifact: Artifact, version: ArtifactVersion, checks: CheckResult
) -> str:
    """Compose what the reviewing model sees."""
    body = version.body_markdown[:_BODY_EXCERPT_CHARS]
    truncated = len(version.body_markdown) > _BODY_EXCERPT_CHARS

    return "\n".join(
        [
            f"# Artifact under review: {artifact.title}",
            "",
            f"- Type: {artifact.type.value}",
            f"- Produced during: {artifact.stage.value}",
            f"- By: {artifact.owner_role.value}",
            f"- Version: {version.version}",
            "",
            "## Structural analysis already performed",
            "",
            checks.as_evidence(),
            "",
            "## Content",
            "",
            body + ("\n\n_(truncated)_" if truncated else ""),
        ]
    )


def _structural_summary(checks: CheckResult) -> str:
    """A summary for when no model contributed."""
    if not checks.weaknesses:
        return f"Structural review passed with {checks.score}/100; no defects detected."
    return (
        f"Structural review scored {checks.score}/100 with "
        f"{len(checks.weaknesses)} issue(s) detected."
    )
