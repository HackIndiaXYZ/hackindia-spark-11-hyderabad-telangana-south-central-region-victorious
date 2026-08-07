"""Conflict detection across agent outputs.

`12_Risk_Analysis.md` rates Agent Coordination Failure a High risk — "multiple
engineering agents may generate conflicting recommendations or inconsistent
engineering artifacts" — and prescribes conflict detection as a mitigation.
`02_Proposed_Solution.md` requires each stage to be able to surface a problem
discovered late "rather than silently working around it".

Every detector here is deterministic. A conflict is a structural fact about the
artifacts and the traceability graph — an architecture derived from superseded
requirements, two competing sources of truth for one artifact type, an agent's
own stated concern left unresolved. None of that requires a language model, and
using one would put hallucination risk into the mechanism whose entire job is
catching inconsistency.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.agents import AgentRun
from app.domain.artifacts import Artifact, ArtifactStatus
from app.domain.lifecycle import AgentRole
from app.domain.traceability import TraceEdge, stale_edges

#: Below this, an agent is signalling that it was not confident in its own work.
#: `12_Risk_Analysis.md` names confidence scoring as a hallucination mitigation;
#: the mitigation only bites if something acts on a low score.
LOW_CONFIDENCE_THRESHOLD = 0.5


class ConflictKind(StrEnum):
    """What kind of inconsistency was found."""

    STALE_DERIVATION = "stale_derivation"
    """An artifact was derived from a version of its upstream that has moved on."""

    DUPLICATE_AUTHORITY = "duplicate_authority"
    """Two approved artifacts of the same type — two competing sources of truth."""

    UNRESOLVED_CONCERN = "unresolved_concern"
    """An agent flagged a problem with upstream work that nothing has addressed."""

    LOW_CONFIDENCE = "low_confidence"
    """An agent completed work it was not confident in."""


class ConflictSeverity(StrEnum):
    """How a conflict should affect the workflow."""

    BLOCKING = "blocking"
    """Progress must stop; proceeding would build on a known inconsistency."""

    ADVISORY = "advisory"
    """Worth a human's attention, but not a reason to halt."""


class Conflict(BaseModel):
    """One detected inconsistency."""

    kind: ConflictKind
    severity: ConflictSeverity
    summary: str = Field(description="One line, rendered directly in the workspace.")
    artifact_ids: list[str] = Field(default_factory=list)
    roles: list[AgentRole] = Field(default_factory=list)
    detail: dict[str, object] = Field(default_factory=dict)


def detect_conflicts(
    *,
    artifacts: Iterable[Artifact],
    edges: Iterable[TraceEdge],
    current_versions: Mapping[str, int],
    runs: Iterable[AgentRun],
    concerns_by_run: Mapping[str, list[str]] | None = None,
) -> list[Conflict]:
    """Return every inconsistency detectable from current project state.

    Args:
        artifacts: Every artifact in the project.
        edges: Every traceability edge.
        current_versions: Artifact ID to current version.
        runs: Agent runs, used for confidence and attribution.
        concerns_by_run: Concerns each run raised about upstream work.

    Returns:
        Conflicts, blocking ones first, then in detection order.
    """
    artifact_list = list(artifacts)
    run_list = list(runs)
    by_id = {artifact.id: artifact for artifact in artifact_list}

    found: list[Conflict] = [
        *_stale_derivations(edges, current_versions, by_id),
        *_duplicate_authority(artifact_list),
        *_unresolved_concerns(run_list, concerns_by_run or {}),
        *_low_confidence(run_list),
    ]

    found.sort(key=lambda conflict: 0 if conflict.severity is ConflictSeverity.BLOCKING else 1)
    return found


def blocking(conflicts: Iterable[Conflict]) -> list[Conflict]:
    """Filter to conflicts that must halt progress."""
    return [conflict for conflict in conflicts if conflict.severity is ConflictSeverity.BLOCKING]


def _stale_derivations(
    edges: Iterable[TraceEdge],
    current_versions: Mapping[str, int],
    by_id: Mapping[str, Artifact],
) -> list[Conflict]:
    """Artifacts whose upstream has advanced past the version they consumed.

    Blocking. This is the exact question `04_Existing_Solutions.md` says no tool
    answers — continuing to build on a stale derivation is how an architecture
    quietly stops matching its requirements.
    """
    conflicts: list[Conflict] = []

    for stale in stale_edges(edges, current_versions):
        downstream = by_id.get(stale.edge.downstream_artifact_id)
        upstream = by_id.get(stale.edge.upstream_artifact_id)

        downstream_title = downstream.title if downstream else stale.edge.downstream_artifact_id
        upstream_title = upstream.title if upstream else stale.edge.upstream_artifact_id

        conflicts.append(
            Conflict(
                kind=ConflictKind.STALE_DERIVATION,
                severity=ConflictSeverity.BLOCKING,
                summary=(
                    f"{downstream_title} was derived from {upstream_title} v"
                    f"{stale.edge.upstream_version}, which is now v"
                    f"{stale.current_upstream_version}"
                ),
                artifact_ids=[
                    stale.edge.downstream_artifact_id,
                    stale.edge.upstream_artifact_id,
                ],
                roles=[downstream.owner_role] if downstream else [],
                detail={
                    "versions_behind": stale.versions_behind,
                    "trace_kind": stale.edge.kind.value,
                },
            )
        )

    return conflicts


def _duplicate_authority(artifacts: Iterable[Artifact]) -> list[Conflict]:
    """Two approved artifacts of the same type in one project.

    Blocking. `15_Development_Guidelines.md` requires shared memory to be *the*
    single source of truth; two approved system architectures means downstream
    agents can read different answers to the same question.
    """
    approved: dict[tuple[str, str], list[Artifact]] = defaultdict(list)

    for artifact in artifacts:
        if artifact.status is ArtifactStatus.APPROVED and artifact.has_content:
            approved[(artifact.type.value, artifact.stage.value)].append(artifact)

    return [
        Conflict(
            kind=ConflictKind.DUPLICATE_AUTHORITY,
            severity=ConflictSeverity.BLOCKING,
            summary=(
                f"{len(group)} approved '{artifact_type}' artifacts exist; "
                "downstream agents would have competing sources of truth"
            ),
            artifact_ids=[artifact.id for artifact in group],
            roles=sorted({artifact.owner_role for artifact in group}),
            detail={"artifact_type": artifact_type, "stage": stage},
        )
        for (artifact_type, stage), group in approved.items()
        if len(group) > 1
    ]


def _unresolved_concerns(
    runs: Iterable[AgentRun], concerns_by_run: Mapping[str, list[str]]
) -> list[Conflict]:
    """Concerns an agent raised about upstream work.

    Advisory rather than blocking: a concern is an agent's judgement, and a human
    should weigh it. Escalating every one to blocking would make agents reluctant
    to raise them, which is the opposite of what `02_Proposed_Solution.md` asks
    for.
    """
    by_id = {run.id: run for run in runs}

    return [
        Conflict(
            kind=ConflictKind.UNRESOLVED_CONCERN,
            severity=ConflictSeverity.ADVISORY,
            summary=f"{run.role.value.replace('_', ' ').title()}: {concern}",
            artifact_ids=list(run.output_artifact_ids),
            roles=[run.role],
            detail={"run_id": run_id, "stage": run.stage.value},
        )
        for run_id, concerns in concerns_by_run.items()
        if (run := by_id.get(run_id)) is not None
        for concern in concerns
    ]


def _low_confidence(runs: Iterable[AgentRun]) -> list[Conflict]:
    """Completed work the producing agent was not confident in.

    Advisory: low confidence is an honest signal, and the correct response is
    human review rather than halting. Treating it as blocking would pressure
    agents toward inflated scores, defeating the safeguard.
    """
    return [
        Conflict(
            kind=ConflictKind.LOW_CONFIDENCE,
            severity=ConflictSeverity.ADVISORY,
            summary=(
                f"{run.role.value.replace('_', ' ').title()} reported "
                f"{run.confidence:.0%} confidence in {run.stage.value.replace('_', ' ')}"
            ),
            artifact_ids=list(run.output_artifact_ids),
            roles=[run.role],
            detail={"run_id": run.id, "confidence": run.confidence},
        )
        for run in runs
        if run.confidence is not None and run.confidence < LOW_CONFIDENCE_THRESHOLD
    ]
