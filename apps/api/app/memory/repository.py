"""Shared organizational memory — persistence protocols.

`15_Development_Guidelines.md`: "Shared memory is the single source of truth...
Every engineering agent should operate using the same validated project
knowledge."

Protocols are declared per aggregate so a consumer depends only on what it uses:
the Documentation Agent needs artifacts, not approvals. :class:`SharedMemory`
composes them into the single collaborator agents and the orchestrator receive.

No implementation detail appears here — no session, no transaction, no SQL. The
SQL implementation lives in ``sql_repository.py`` and is bound in the composition
root, so swapping the backing store touches one file.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.agents import AgentRun
from app.domain.approvals import ApprovalRequest
from app.domain.artifacts import (
    Artifact,
    ArtifactType,
    ArtifactVersion,
    ArtifactWithVersion,
)
from app.domain.events import ProjectEvent
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project
from app.domain.traceability import ImpactAnalysis, StaleEdge, TraceEdge


@runtime_checkable
class ProjectRepository(Protocol):
    """Projects and their lifecycle state."""

    async def create(self, project: Project) -> Project: ...

    async def get(self, project_id: str) -> Project:
        """Return a project.

        Raises:
            NotFoundError: if no such project exists.
        """
        ...

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[Project]: ...

    async def update(self, project: Project) -> Project: ...

    async def exists(self, project_id: str) -> bool: ...


@runtime_checkable
class ArtifactRepository(Protocol):
    """Artifacts and their append-only version history."""

    async def create(self, artifact: Artifact) -> Artifact: ...

    async def get(self, artifact_id: str) -> Artifact:
        """Return artifact identity without content.

        Raises:
            NotFoundError: if no such artifact exists.
        """
        ...

    async def update(self, artifact: Artifact) -> Artifact:
        """Persist status changes. Never mutates version content."""
        ...

    async def list_for_project(
        self,
        project_id: str,
        *,
        stage: LifecycleStage | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> list[Artifact]: ...

    async def find_by_identity(
        self, project_id: str, artifact_type: ArtifactType, stage: LifecycleStage, title: str
    ) -> Artifact | None:
        """Find an artifact an agent has produced before.

        Identity is (project, type, stage, title). Title is part of the key
        because a stage can legitimately produce several artifacts of one type —
        the Full Stack Engineer writes many source files — while still producing
        exactly one of each *named* artifact.

        Used when an agent re-runs after a rejection: the revised work becomes a
        new *version* of what it produced before rather than a second competing
        artifact, which is what keeps the traceability graph pointing at one
        stable identity across revisions (ADR-0007).
        """
        ...

    async def append_version(
        self, artifact_id: str, version: ArtifactVersion
    ) -> ArtifactVersion:
        """Append a new version and advance the artifact's current version.

        The only way content enters memory. Version numbers are assigned by the
        repository, not the caller, so two concurrent writers cannot mint the
        same number.

        Raises:
            NotFoundError: if the artifact does not exist.
        """
        ...

    async def get_version(
        self, artifact_id: str, version: int | None = None
    ) -> ArtifactWithVersion:
        """Return an artifact with one version — the latest when unspecified.

        Raises:
            NotFoundError: if the artifact or the requested version is absent.
        """
        ...

    async def list_versions(self, artifact_id: str) -> list[ArtifactVersion]:
        """Return every version, oldest first."""
        ...

    async def current_versions(self, project_id: str) -> dict[str, int]:
        """Return artifact ID to current version for a whole project.

        The single query that makes staleness computable across the project in
        one pass rather than N.
        """
        ...


@runtime_checkable
class TraceRepository(Protocol):
    """The traceability graph."""

    async def add_edge(self, edge: TraceEdge) -> TraceEdge: ...

    async def list_for_project(self, project_id: str) -> list[TraceEdge]: ...

    async def upstream_of(self, artifact_id: str) -> list[TraceEdge]:
        """Return edges this artifact depends on — "why does this exist?"."""
        ...

    async def downstream_of(self, artifact_id: str) -> list[TraceEdge]:
        """Return edges depending on this artifact — one hop of blast radius."""
        ...

    async def analyse_impact(
        self, project_id: str, artifact_id: str, *, max_depth: int | None = None
    ) -> ImpactAnalysis:
        """Compute the transitive downstream impact of changing an artifact."""
        ...

    async def stale_edges(self, project_id: str) -> list[StaleEdge]:
        """Return derivations whose upstream has advanced past the cited version."""
        ...


@runtime_checkable
class AgentRunRepository(Protocol):
    """Agent execution records."""

    async def create(self, run: AgentRun) -> AgentRun: ...

    async def get(self, run_id: str) -> AgentRun: ...

    async def update(self, run: AgentRun) -> AgentRun: ...

    async def list_for_project(
        self, project_id: str, *, role: AgentRole | None = None, limit: int = 100
    ) -> list[AgentRun]: ...

    async def latest_for_role(self, project_id: str, role: AgentRole) -> AgentRun | None:
        """Return the most recent run for a role.

        Drives the Agent Organization view, which shows each agent's current
        state whether or not it is running right now.
        """
        ...


@runtime_checkable
class ApprovalRepository(Protocol):
    """Human approval gates."""

    async def create(self, request: ApprovalRequest) -> ApprovalRequest: ...

    async def get(self, approval_id: str) -> ApprovalRequest: ...

    async def update(self, request: ApprovalRequest) -> ApprovalRequest: ...

    async def list_for_project(
        self, project_id: str, *, pending_only: bool = False
    ) -> list[ApprovalRequest]: ...

    async def list_pending(self, *, limit: int = 50) -> list[ApprovalRequest]:
        """Return pending approvals across all projects, for the dashboard."""
        ...


@runtime_checkable
class EventRepository(Protocol):
    """Append-only engineering activity record."""

    async def append(self, event: ProjectEvent) -> ProjectEvent: ...

    async def list_for_project(
        self, project_id: str, *, limit: int = 200, after_id: str | None = None
    ) -> list[ProjectEvent]:
        """Return events oldest first.

        ``after_id`` supports stream resumption: a browser that reconnects to the
        live agent feed replays only what it missed.
        """
        ...

    async def list_recent(self, *, limit: int = 50) -> list[ProjectEvent]:
        """Return recent events across all projects, for the dashboard."""
        ...


class SharedMemory(Protocol):
    """The single source of truth, as one injectable collaborator.

    Agents and the orchestrator depend on this rather than on six separate
    repositories, which keeps their signatures honest: an agent that can read the
    project can read all of it.
    """

    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def artifacts(self) -> ArtifactRepository: ...

    @property
    def traces(self) -> TraceRepository: ...

    @property
    def runs(self) -> AgentRunRepository: ...

    @property
    def approvals(self) -> ApprovalRepository: ...

    @property
    def events(self) -> EventRepository: ...
