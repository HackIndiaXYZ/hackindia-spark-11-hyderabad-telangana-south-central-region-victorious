"""Traceability edges, staleness, and change impact.

`04_Existing_Solutions.md` identifies the gap no existing tool fills:

    Is the architecture still consistent with the latest requirements?
    Which downstream components are affected by this requirement change?

This module is the answer, and it is the reason the whole platform is more than a
code generator. Two design choices carry it.

**Edges bind artifact identity, but record upstream version.**
An edge points from an upstream artifact to a downstream one and remembers *which
version of the upstream* the downstream was derived from. Because artifact IDs
are stable across revisions, the graph survives every edit; because the version
is recorded, the graph knows when a derivation has gone out of date.

**Staleness is computed, never stored.**
An artifact is stale when an edge cites an upstream version older than that
upstream's current version. There is no flag to set, so there is no flag to
forget to set — the property this platform claims about engineering artifacts is
one it structurally cannot violate itself.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ids import IdPrefix, new_id


class TraceKind(StrEnum):
    """The engineering relationship an edge represents.

    Kinds are not interchangeable: an architecture that *derives from* a
    requirement goes stale when the requirement changes, whereas a business
    analysis that *validates* one only needs re-examining. Milestone 8 uses this
    to propose proportionate re-synchronisation instead of regenerating
    everything downstream.
    """

    DERIVES_FROM = "derives_from"
    """Downstream content was produced from upstream content."""

    IMPLEMENTS = "implements"
    """Downstream realises an upstream specification (code implements a design)."""

    VALIDATES = "validates"
    """Downstream checks upstream (business analysis validates requirements)."""

    TESTS = "tests"
    """Downstream verifies upstream (test cases test acceptance criteria)."""

    DOCUMENTS = "documents"
    """Downstream describes upstream (API docs document an API contract)."""

    REFINES = "refines"
    """Downstream adds detail without changing intent."""


class TraceEdge(BaseModel):
    """A directed dependency between two artifacts.

    Immutable. A changed derivation is a new edge, so the history of how the
    project was reasoned about is preserved alongside the artifacts themselves.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: new_id(IdPrefix.TRACE_EDGE))
    project_id: str

    upstream_artifact_id: str = Field(description="The artifact depended upon.")
    downstream_artifact_id: str = Field(description="The artifact that depends.")
    kind: TraceKind = TraceKind.DERIVES_FROM

    upstream_version: int = Field(
        ge=1,
        description=(
            "Version of the upstream artifact this derivation consumed. The field "
            "that makes staleness computable rather than declared."
        ),
    )

    created_by_run_id: str | None = Field(
        default=None, description="Agent run that established the dependency."
    )
    rationale: str = Field(
        default="",
        description="Why the dependency exists, surfaced in the impact preview.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StaleEdge(BaseModel):
    """An edge whose upstream has advanced past the version it cites."""

    edge: TraceEdge
    current_upstream_version: int

    @property
    def versions_behind(self) -> int:
        return self.current_upstream_version - self.edge.upstream_version


class ImpactedArtifact(BaseModel):
    """One artifact inside a change's blast radius."""

    artifact_id: str
    depth: int = Field(
        ge=1, description="Edge hops from the changed artifact. 1 is direct."
    )
    via_kind: TraceKind = Field(description="Relationship on the path's final hop.")
    path: list[str] = Field(
        description="Artifact IDs from the changed artifact to this one, inclusive."
    )


class ImpactAnalysis(BaseModel):
    """Everything a change to one artifact would affect.

    Computed and shown to the user *before* anything is regenerated — the
    "downstream impact" field the Approval Center requires in
    `10_UI_UX_Plan.md`.
    """

    changed_artifact_id: str
    impacted: list[ImpactedArtifact] = Field(default_factory=list)

    @property
    def artifact_ids(self) -> list[str]:
        return [item.artifact_id for item in self.impacted]

    @property
    def direct(self) -> list[ImpactedArtifact]:
        """Artifacts one hop downstream — those that change most certainly."""
        return [item for item in self.impacted if item.depth == 1]

    @property
    def is_empty(self) -> bool:
        return not self.impacted


def stale_edges(
    edges: Iterable[TraceEdge],
    current_versions: Mapping[str, int],
) -> list[StaleEdge]:
    """Return edges whose upstream artifact has advanced past the cited version.

    Args:
        edges: Edges to examine.
        current_versions: Artifact ID to its current version number.

    Returns:
        One entry per out-of-date edge. An edge whose upstream is missing from
        ``current_versions`` is skipped rather than assumed stale — an unknown
        artifact is a caller bug, and guessing would produce false alarms in the
        one place the platform must be trustworthy.
    """
    results: list[StaleEdge] = []

    for edge in edges:
        current = current_versions.get(edge.upstream_artifact_id)
        if current is None:
            continue
        if current > edge.upstream_version:
            results.append(StaleEdge(edge=edge, current_upstream_version=current))

    return results


def stale_artifact_ids(
    edges: Iterable[TraceEdge],
    current_versions: Mapping[str, int],
) -> set[str]:
    """Return the artifacts that are out of date with respect to their upstream."""
    return {stale.edge.downstream_artifact_id for stale in stale_edges(edges, current_versions)}


def analyse_impact(
    changed_artifact_id: str,
    edges: Iterable[TraceEdge],
    *,
    max_depth: int | None = None,
) -> ImpactAnalysis:
    """Compute the transitive downstream blast radius of a change.

    Breadth-first, so each artifact is reported at its *shortest* path from the
    change — the most direct explanation of why it is affected, which is what the
    impact preview should show a reviewer.

    Cycles are possible in a real project graph (an architecture decision that
    feeds back into a requirement), so visited artifacts are never re-expanded.
    The changed artifact is excluded from its own impact set even if a cycle
    returns to it.

    Args:
        changed_artifact_id: The artifact being modified.
        edges: Every edge in the project.
        max_depth: Optional hop limit, for previewing immediate effects only.

    Returns:
        The impacted set, ordered by depth then by discovery.
    """
    downstream_by_upstream: dict[str, list[TraceEdge]] = {}
    for edge in edges:
        downstream_by_upstream.setdefault(edge.upstream_artifact_id, []).append(edge)

    impacted: list[ImpactedArtifact] = []
    visited: set[str] = {changed_artifact_id}
    queue: deque[tuple[str, int, list[str]]] = deque(
        [(changed_artifact_id, 0, [changed_artifact_id])]
    )

    while queue:
        artifact_id, depth, path = queue.popleft()

        if max_depth is not None and depth >= max_depth:
            continue

        for edge in downstream_by_upstream.get(artifact_id, []):
            target = edge.downstream_artifact_id
            if target in visited:
                continue

            visited.add(target)
            next_path = [*path, target]
            impacted.append(
                ImpactedArtifact(
                    artifact_id=target,
                    depth=depth + 1,
                    via_kind=edge.kind,
                    path=next_path,
                )
            )
            queue.append((target, depth + 1, next_path))

    return ImpactAnalysis(changed_artifact_id=changed_artifact_id, impacted=impacted)


def upstream_of(
    artifact_id: str,
    edges: Iterable[TraceEdge],
) -> list[TraceEdge]:
    """Return the edges this artifact depends on.

    The reverse query, and the one that answers "why does this artifact exist?"
    when a user clicks through the traceability graph.
    """
    return [edge for edge in edges if edge.downstream_artifact_id == artifact_id]
