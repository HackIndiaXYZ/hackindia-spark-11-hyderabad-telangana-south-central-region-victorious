"""Deterministic structural checks over a produced artifact.

These carry the weight of the review score, and reasoning only adjusts it within
a bounded range. Three reasons:

- `12_Risk_Analysis.md` rates AI Hallucination a High risk. A reviewer that is
  purely a language model can invent a weakness, or miss a real one, and a score
  built entirely on that is not evidence of anything.
- The demo runs on recorded fixtures. If the score came from replayed prose,
  every artifact would score identically and the number would be theatre.
  Structural checks read the *actual* artifact, so scores genuinely differ.
- A structural finding is a fact a user can verify — "declares no upstream" is
  checkable. An opinion is not.

Each check returns points and, when it deducts, a finding explaining why. The
findings are the reviewer's evidence, and they survive into the stored review so
the workspace can show what was measured rather than only what was concluded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.artifacts import Artifact, ArtifactType, ArtifactVersion
from app.domain.lifecycle import LifecycleStage
from app.domain.reviews import ReviewFinding

#: Weights, summing to 100. Traceability and substance dominate because they are
#: the properties the whole platform depends on: an artifact nobody can trace is
#: invisible to impact analysis, and an empty one is not work.
TRACEABILITY_POINTS = 25
CONTENT_POINTS = 25
SUBSTANCE_POINTS = 20
CONFIDENCE_POINTS = 15
COMPLETENESS_POINTS = 15

#: A body shorter than this is a heading with nothing under it.
_THIN_BODY_CHARS = 400
_RICH_BODY_CHARS = 1200

#: Structured fields each artifact type is expected to carry. Absence is a real
#: defect: downstream agents read these fields, not the prose.
_EXPECTED_CONTENT: dict[ArtifactType, tuple[str, ...]] = {
    ArtifactType.PRD: ("functional_requirements", "objective"),
    ArtifactType.USER_STORIES: ("user_stories",),
    ArtifactType.ACCEPTANCE_CRITERIA: ("criteria",),
    ArtifactType.BUSINESS_ANALYSIS: ("feasibility",),
    ArtifactType.GAP_ANALYSIS: ("gaps",),
    ArtifactType.RISK_REGISTER: ("risks",),
    ArtifactType.SYSTEM_ARCHITECTURE: ("components", "style"),
    ArtifactType.TECHNOLOGY_DECISION: ("choices",),
    ArtifactType.API_CONTRACT: ("endpoints",),
    ArtifactType.DATABASE_SCHEMA: ("entities",),
    ArtifactType.IMPLEMENTATION_PLAN: ("tasks",),
    ArtifactType.REPOSITORY_STRUCTURE: ("tree",),
    ArtifactType.SOURCE_FILE: ("content", "path"),
    ArtifactType.TEST_PLAN: ("strategy",),
    ArtifactType.TEST_CASES: ("test_cases",),
    ArtifactType.COVERAGE_REPORT: ("entries",),
    ArtifactType.DEPLOYMENT_PLAN: ("checklist",),
}


@dataclass
class CheckResult:
    """The outcome of running every structural check."""

    score: int
    strengths: list[ReviewFinding] = field(default_factory=list)
    weaknesses: list[ReviewFinding] = field(default_factory=list)
    suggestions: list[ReviewFinding] = field(default_factory=list)

    def as_evidence(self) -> str:
        """Render the findings for a reviewing model's context.

        The model is shown what was measured so its judgement builds on the
        evidence rather than re-deriving it — and so it cannot contradict a fact.
        """
        lines = [f"Structural score: {self.score}/100"]
        for label, findings in (
            ("Verified strengths", self.strengths),
            ("Detected weaknesses", self.weaknesses),
        ):
            if findings:
                lines.append(f"\n{label}:")
                lines.extend(f"- {finding.text}" for finding in findings)
        return "\n".join(lines)


def run_checks(
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    upstream_count: int,
    is_first_stage: bool,
) -> CheckResult:
    """Score an artifact on properties that can be measured rather than judged."""
    result = CheckResult(score=0)

    result.score += _traceability(artifact, upstream_count, is_first_stage, result)
    result.score += _structured_content(artifact, version, result)
    result.score += _substance(version, result)
    result.score += _confidence(version, result)
    result.score += _type_completeness(artifact, version, result)

    return result


def _traceability(
    artifact: Artifact, upstream_count: int, is_first_stage: bool, result: CheckResult
) -> int:
    """Does the artifact declare what it was derived from?

    The first stage legitimately has no upstream, so it is credited in full
    rather than penalised for a property it cannot have.
    """
    if is_first_stage:
        result.strengths.append(
            ReviewFinding(text="Originates the project; no upstream expected.")
        )
        return TRACEABILITY_POINTS

    if upstream_count == 0:
        result.weaknesses.append(
            ReviewFinding(
                text=(
                    "Declares no upstream artifacts, so a change to its inputs "
                    "could not flag it as out of date."
                )
            )
        )
        return 0

    result.strengths.append(
        ReviewFinding(text=f"Traced to {upstream_count} upstream artifact(s).")
    )
    return TRACEABILITY_POINTS


def _structured_content(
    artifact: Artifact, version: ArtifactVersion, result: CheckResult
) -> int:
    """Is there structured content for downstream agents to read?

    Downstream specialists read fields, not prose. An artifact whose content is
    empty forces the next agent to parse a document, which is exactly the
    coupling the platform's structured contracts exist to avoid.
    """
    if not version.content:
        result.weaknesses.append(
            ReviewFinding(
                text=(
                    "Carries no structured content; downstream agents would have "
                    "to parse the prose."
                )
            )
        )
        return 0

    populated = [
        key
        for key, value in version.content.items()
        if value not in (None, "", [], {})
    ]

    if not populated:
        result.weaknesses.append(
            ReviewFinding(text="Structured content is present but every field is empty.")
        )
        return 0

    result.strengths.append(
        ReviewFinding(text=f"Structured content populated across {len(populated)} field(s).")
    )
    return CONTENT_POINTS


def _substance(version: ArtifactVersion, result: CheckResult) -> int:
    """Is the rendered document substantive, or a heading with nothing under it?"""
    length = len(version.body_markdown)

    if length < _THIN_BODY_CHARS:
        result.weaknesses.append(
            ReviewFinding(
                text=f"Document is thin ({length} characters); likely under-specified."
            )
        )
        result.suggestions.append(
            ReviewFinding(text="Expand with the detail a downstream engineer would need.")
        )
        return SUBSTANCE_POINTS // 4

    if length < _RICH_BODY_CHARS:
        result.strengths.append(ReviewFinding(text="Document has adequate detail."))
        return SUBSTANCE_POINTS * 3 // 4

    result.strengths.append(
        ReviewFinding(text=f"Document is detailed ({length} characters).")
    )
    return SUBSTANCE_POINTS


def _confidence(version: ArtifactVersion, result: CheckResult) -> int:
    """How confident was the specialist that produced it?

    `12_Risk_Analysis.md` names confidence scoring as a hallucination mitigation.
    The mitigation only bites if something acts on a low score — this does.
    """
    confidence = version.confidence

    if confidence is None:
        result.weaknesses.append(
            ReviewFinding(text="Producing agent reported no confidence.")
        )
        return 0

    if confidence < 0.5:
        result.weaknesses.append(
            ReviewFinding(
                text=f"Producing agent reported low confidence ({confidence:.0%})."
            )
        )
        result.suggestions.append(
            ReviewFinding(text="Route to a human before downstream work builds on it.")
        )
        return 0

    if confidence < 0.75:
        return CONFIDENCE_POINTS // 2

    result.strengths.append(
        ReviewFinding(text=f"Produced with {confidence:.0%} confidence.")
    )
    return CONFIDENCE_POINTS


def _type_completeness(
    artifact: Artifact, version: ArtifactVersion, result: CheckResult
) -> int:
    """Does the artifact carry the fields its type is supposed to carry?"""
    expected = _EXPECTED_CONTENT.get(artifact.type)

    if not expected:
        # Documentation artifacts are prose by design; substance already covers
        # them, and inventing a field requirement would penalise correct output.
        return COMPLETENESS_POINTS

    missing = [
        key
        for key in expected
        if not version.content.get(key)
    ]

    if not missing:
        result.strengths.append(
            ReviewFinding(text=f"Carries every field expected of a {artifact.type.value}.")
        )
        return COMPLETENESS_POINTS

    result.weaknesses.append(
        ReviewFinding(
            text=(
                f"Missing expected field(s) for a {artifact.type.value}: "
                + ", ".join(missing)
            )
        )
    )
    result.suggestions.append(
        ReviewFinding(text=f"Populate {', '.join(missing)} so downstream agents can read it.")
    )
    return round(COMPLETENESS_POINTS * (1 - len(missing) / len(expected)))


def is_first_stage(stage: LifecycleStage) -> bool:
    """Whether a stage legitimately has no upstream to declare."""
    return stage is LifecycleStage.REQUIREMENT_DISCOVERY
