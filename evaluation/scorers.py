"""Deterministic scorers for the AI Engineering Organization.

`02_Proposed_Solution.md` requires evaluation datasets, scorecards, and
optimization reports to be produced throughout development as evidence of
continuous improvement. These are the scorers behind those scorecards.

Every scorer is deterministic and computed from what the organization actually
produced. None asks a language model to judge quality: `12_Risk_Analysis.md`
rates AI Hallucination a High risk, and a hallucinating grader would report
improvement that did not happen — the one failure that makes an evaluation
harness worse than none.

What that buys is precision, not breadth. These measure *structural* properties —
is every requirement traceable, does every technology decision record its
alternatives, does staleness clear after a rebuild. They cannot measure whether a
requirement is a good idea. That judgement stays with the human at the approval
gate, which is where the specification puts it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.artifacts import ArtifactType
from app.domain.lifecycle import LifecycleStage
from app.domain.traceability import stale_edges
from app.memory.repository import SharedMemory

#: The eight artifacts `09_MVP_Roadmap.md` says the MVP must generate.
REQUIRED_ARTIFACTS: frozenset[ArtifactType] = frozenset(
    {
        ArtifactType.PRD,
        ArtifactType.USER_STORIES,
        ArtifactType.SYSTEM_ARCHITECTURE,
        ArtifactType.API_CONTRACT,
        ArtifactType.DATABASE_SCHEMA,
        ArtifactType.SOURCE_FILE,
        ArtifactType.README,
        ArtifactType.ARCHITECTURE_DOCUMENT,
    }
)


@dataclass
class Score:
    """One measured property of a run."""

    name: str
    value: float
    """Normalised 0.0-1.0, so scores are comparable across runs."""

    detail: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def percent(self) -> str:
        return f"{self.value:.0%}"


@dataclass
class Scorecard:
    """Every score for one project brief."""

    case_id: str
    project_name: str
    scores: list[Score] = field(default_factory=list)

    @property
    def overall(self) -> float:
        """Unweighted mean. Every property here is a pass/fail engineering
        obligation, so weighting one above another would be an opinion the
        specification does not express."""
        return sum(score.value for score in self.scores) / len(self.scores) if self.scores else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "project_name": self.project_name,
            "overall": round(self.overall, 4),
            "scores": [
                {
                    "name": score.name,
                    "value": round(score.value, 4),
                    "detail": score.detail,
                    "raw": score.raw,
                }
                for score in self.scores
            ],
        }


async def score_project(memory: SharedMemory, project_id: str) -> list[Score]:
    """Run every scorer against a completed project."""
    project = await memory.projects.get(project_id)
    artifacts = [
        artifact
        for artifact in await memory.artifacts.list_for_project(project_id)
        if artifact.has_content
    ]
    edges = await memory.traces.list_for_project(project_id)
    versions = await memory.artifacts.current_versions(project_id)
    runs = await memory.runs.list_for_project(project_id)
    approvals = await memory.approvals.list_for_project(project_id)

    # Structured content lives on the version, not the artifact, so the scorers
    # that inspect it are handed the resolved payloads rather than re-reading.
    contents: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if artifact.type in {ArtifactType.COVERAGE_REPORT, ArtifactType.TECHNOLOGY_DECISION}:
            resolved = await memory.artifacts.get_version(artifact.id)
            contents[artifact.id] = resolved.version.content

    return [
        _lifecycle_completion(project),
        _artifact_completeness(artifacts),
        _traceability_completeness(artifacts, edges),
        _staleness_after_completion(edges, versions),
        _requirement_coverage(artifacts, contents),
        _decision_reviewability(artifacts, contents),
        _approval_discipline(approvals),
        _agent_transparency(runs),
    ]


def _lifecycle_completion(project: Any) -> Score:
    """Did the organization finish the lifecycle `09_MVP_Roadmap.md` defines?"""
    working = [stage for stage in LifecycleStage if stage is not LifecycleStage.IDEA]
    completed = set(project.completed_stages)
    done = [stage for stage in working if stage in completed]

    return Score(
        name="lifecycle_completion",
        value=len(done) / len(working),
        detail=f"{len(done)}/{len(working)} stages completed",
        raw={"missing": [stage.value for stage in working if stage not in completed]},
    )


def _artifact_completeness(artifacts: list[Any]) -> Score:
    """Were all eight required artifacts produced?"""
    produced = {artifact.type for artifact in artifacts}
    missing = REQUIRED_ARTIFACTS - produced

    return Score(
        name="artifact_completeness",
        value=(len(REQUIRED_ARTIFACTS) - len(missing)) / len(REQUIRED_ARTIFACTS),
        detail=(
            f"{len(REQUIRED_ARTIFACTS) - len(missing)}/{len(REQUIRED_ARTIFACTS)} "
            "required artifacts"
        ),
        raw={"missing": sorted(item.value for item in missing)},
    )


def _traceability_completeness(artifacts: list[Any], edges: list[Any]) -> Score:
    """Can every downstream artifact be traced to what produced it?

    The property the whole platform rests on. An orphan is invisible to impact
    analysis, so a requirement change would silently fail to flag it.
    """
    downstream = {edge.downstream_artifact_id for edge in edges}
    first_stage = LifecycleStage.REQUIREMENT_DISCOVERY

    expected = [artifact for artifact in artifacts if artifact.stage is not first_stage]
    orphans = [artifact for artifact in expected if artifact.id not in downstream]

    return Score(
        name="traceability_completeness",
        value=(len(expected) - len(orphans)) / len(expected) if expected else 1.0,
        detail=f"{len(expected) - len(orphans)}/{len(expected)} downstream artifacts traced",
        raw={"orphans": [artifact.title for artifact in orphans]},
    )


def _staleness_after_completion(edges: list[Any], versions: dict[str, int]) -> Score:
    """Is the delivered project internally consistent?

    A finished project with stale derivations means something was built on a
    version that has since moved. Measured *after* completion, so it also detects
    a re-synchronisation that failed to actually clear staleness — the regression
    documented in `optimization-report.md`.
    """
    stale = stale_edges(edges, versions)

    return Score(
        name="internal_consistency",
        value=1.0 if not stale else 0.0,
        detail="no stale derivations" if not stale else f"{len(stale)} stale derivations",
        raw={"stale_count": len(stale)},
    )


def _requirement_coverage(
    artifacts: list[Any], contents: dict[str, dict[str, Any]]
) -> Score:
    """What fraction of requirements does the QA agent report as tested?

    Read from the coverage report the QA Engineer produced, so this measures the
    organization's own honesty about coverage as much as the coverage itself: an
    agent that quietly omitted uncovered requirements would score *higher* here
    while being less trustworthy, which is why the orphan and traceability
    scorers sit alongside it.
    """
    report = next(
        (a for a in artifacts if a.type is ArtifactType.COVERAGE_REPORT), None
    )
    if report is None:
        return Score(
            name="requirement_coverage",
            value=0.0,
            detail="no coverage report produced",
        )

    content = contents.get(report.id, {})
    covered = int(content.get("covered", 0))
    total = int(content.get("total", 0))

    return Score(
        name="requirement_coverage",
        value=covered / total if total else 0.0,
        detail=f"{covered}/{total} requirements covered by tests",
        raw={"covered": covered, "total": total},
    )


def _decision_reviewability(
    artifacts: list[Any], contents: dict[str, dict[str, Any]]
) -> Score:
    """Can a human actually review the technology decisions?

    `09_MVP_Roadmap.md` puts technology selection behind an approval gate. A
    decision recorded without the alternatives considered and the trade-off
    accepted cannot be approved on its merits — it can only be rubber-stamped.
    """
    decision = next(
        (a for a in artifacts if a.type is ArtifactType.TECHNOLOGY_DECISION), None
    )
    if decision is None:
        return Score(
            name="decision_reviewability",
            value=0.0,
            detail="no technology decisions recorded",
        )

    choices = contents.get(decision.id, {}).get("choices", [])
    if not choices:
        return Score(name="decision_reviewability", value=0.0, detail="no choices recorded")

    reviewable = [
        choice
        for choice in choices
        if choice.get("alternatives") and str(choice.get("rationale", "")).strip()
    ]

    return Score(
        name="decision_reviewability",
        value=len(reviewable) / len(choices),
        detail=f"{len(reviewable)}/{len(choices)} decisions record alternatives and rationale",
        raw={"total_choices": len(choices)},
    )


def _approval_discipline(approvals: list[Any]) -> Score:
    """Were the approvals `09_MVP_Roadmap.md` requires actually raised?

    Requirements, architecture, and final code generation are structural gates;
    technology selection is raised by the architect. A run that reached delivery
    without passing them did not keep the human in control.
    """
    required = {"requirements", "architecture", "code_generation"}
    raised = {approval.kind.value for approval in approvals}
    present = required & raised

    return Score(
        name="approval_discipline",
        value=len(present) / len(required),
        detail=f"{len(present)}/{len(required)} required gates raised",
        raw={"missing": sorted(required - raised), "all_raised": sorted(raised)},
    )


def _agent_transparency(runs: list[Any]) -> Score:
    """Did every agent explain itself?

    `12_Risk_Analysis.md` mitigates Loss of User Trust with explainable reasoning
    and confidence scoring. A run without both is opaque regardless of how good
    its output was.
    """
    completed = [run for run in runs if run.completed_at is not None]
    if not completed:
        return Score(name="agent_transparency", value=0.0, detail="no completed runs")

    explained = [
        run
        for run in completed
        if run.confidence is not None and str(run.reasoning_summary).strip()
    ]

    return Score(
        name="agent_transparency",
        value=len(explained) / len(completed),
        detail=f"{len(explained)}/{len(completed)} runs report reasoning and confidence",
        raw={"runs": len(completed)},
    )
