"""SQL-backed shared organizational memory.

Implements every protocol in ``repository.py`` over SQLAlchemy. Mapping between
storage rows and domain models happens here and nowhere else, which is what keeps
the domain layer framework-free.

Each public method opens its own transaction. Multi-step engineering operations
that must be atomic — appending a version *and* recording its trace edges — are
expressed as single methods rather than as several calls the caller must
sequence, so a caller cannot leave memory half-written.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import (
    AgentRunRow,
    ApprovalRow,
    ArtifactReviewRow,
    ArtifactRow,
    ArtifactVersionRow,
    EventRow,
    ProjectRow,
    TraceEdgeRow,
)
from app.db.session import Database
from app.domain.agents import AgentRun, AgentRunStatus, TokenUsage
from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import (
    Artifact,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersion,
    ArtifactWithVersion,
)
from app.domain.errors import ConflictError, NotFoundError
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project, StageState
from app.domain.reviews import ArtifactReview, ReviewFinding, ReviewVerdict
from app.domain.traceability import (
    ImpactAnalysis,
    StaleEdge,
    TraceEdge,
    TraceKind,
    analyse_impact,
    stale_edges,
)

logger = get_logger(__name__)


# --- Mapping -----------------------------------------------------------------
# Row-to-domain conversion lives in module functions rather than on the rows
# themselves, so the SQLAlchemy models stay free of domain knowledge and the
# dependency continues to point one way only.


def _to_project(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        name=row.name,
        description=row.description,
        current_stage=LifecycleStage(row.current_stage),
        stages=[StageState.model_validate(state) for state in row.stages],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_artifact(row: ArtifactRow) -> Artifact:
    return Artifact(
        id=row.id,
        project_id=row.project_id,
        type=ArtifactType(row.type),
        title=row.title,
        stage=LifecycleStage(row.stage),
        owner_role=AgentRole(row.owner_role),
        status=ArtifactStatus(row.status),
        current_version=row.current_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_version(row: ArtifactVersionRow) -> ArtifactVersion:
    return ArtifactVersion(
        id=row.id,
        artifact_id=row.artifact_id,
        version=row.version,
        body_markdown=row.body_markdown,
        content=row.content,
        produced_by_run_id=row.produced_by_run_id,
        summary=row.summary,
        confidence=row.confidence,
        created_at=row.created_at,
    )


def _to_edge(row: TraceEdgeRow) -> TraceEdge:
    return TraceEdge(
        id=row.id,
        project_id=row.project_id,
        upstream_artifact_id=row.upstream_artifact_id,
        downstream_artifact_id=row.downstream_artifact_id,
        kind=TraceKind(row.kind),
        upstream_version=row.upstream_version,
        created_by_run_id=row.created_by_run_id,
        rationale=row.rationale,
        created_at=row.created_at,
    )


def _to_run(row: AgentRunRow) -> AgentRun:
    return AgentRun(
        id=row.id,
        project_id=row.project_id,
        role=AgentRole(row.role),
        stage=LifecycleStage(row.stage),
        status=AgentRunStatus(row.status),
        task=row.task,
        reasoning_summary=row.reasoning_summary,
        confidence=row.confidence,
        input_artifact_ids=list(row.input_artifact_ids),
        output_artifact_ids=list(row.output_artifact_ids),
        blocked_on=list(row.blocked_on),
        provider=row.provider,
        model=row.model,
        token_usage=TokenUsage(
            input_tokens=row.input_tokens, output_tokens=row.output_tokens
        ),
        requires_approval=row.requires_approval,
        approval_reason=row.approval_reason,
        correlation_id=row.correlation_id,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _to_approval(row: ApprovalRow) -> ApprovalRequest:
    return ApprovalRequest(
        id=row.id,
        project_id=row.project_id,
        kind=ApprovalKind(row.kind),
        stage=LifecycleStage(row.stage),
        title=row.title,
        what_changed=row.what_changed,
        why=row.why,
        requested_by=AgentRole(row.requested_by),
        agents_involved=[AgentRole(role) for role in row.agents_involved],
        artifact_ids=list(row.artifact_ids),
        impact=ImpactAnalysis.model_validate(row.impact) if row.impact else None,
        status=ApprovalStatus(row.status),
        feedback=row.feedback,
        decided_at=row.decided_at,
        created_at=row.created_at,
    )


def _to_review(row: ArtifactReviewRow) -> ArtifactReview:
    return ArtifactReview(
        id=row.id,
        project_id=row.project_id,
        artifact_id=row.artifact_id,
        artifact_version=row.artifact_version,
        stage=LifecycleStage(row.stage),
        role=AgentRole(row.role),
        produced_by_run_id=row.produced_by_run_id,
        quality_score=row.quality_score,
        verdict=ReviewVerdict(row.verdict),
        summary=row.summary,
        strengths=[ReviewFinding.model_validate(item) for item in row.strengths],
        weaknesses=[ReviewFinding.model_validate(item) for item in row.weaknesses],
        suggestions=[ReviewFinding.model_validate(item) for item in row.suggestions],
        deterministic_score=row.deterministic_score,
        reasoning_applied=row.reasoning_applied,
        reviewer_provider=row.reviewer_provider,
        reviewer_model=row.reviewer_model,
        created_at=row.created_at,
    )


def _to_event(row: EventRow) -> ProjectEvent:
    return ProjectEvent(
        id=row.id,
        project_id=row.project_id,
        type=EventType(row.type),
        stage=LifecycleStage(row.stage) if row.stage else None,
        role=AgentRole(row.role) if row.role else None,
        summary=row.summary,
        payload=row.payload,
        correlation_id=row.correlation_id,
        created_at=row.created_at,
    )


# --- Repositories -------------------------------------------------------------


class _Base:
    """Shared session access for every repository."""

    def __init__(self, database: Database) -> None:
        self._db = database


class SqlProjectRepository(_Base):
    async def create(self, project: Project) -> Project:
        async with self._db.session() as session:
            session.add(
                ProjectRow(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    current_stage=project.current_stage.value,
                    stages=[state.model_dump(mode="json") for state in project.stages],
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                )
            )
        logger.info("Project created", extra={"project_id": project.id})
        return project

    async def get(self, project_id: str) -> Project:
        async with self._db.session() as session:
            row = await session.get(ProjectRow, project_id)
            if row is None:
                raise NotFoundError("Project not found", details={"project_id": project_id})
            return _to_project(row)

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[Project]:
        async with self._db.session() as session:
            result = await session.execute(
                select(ProjectRow)
                .order_by(ProjectRow.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return [_to_project(row) for row in result.scalars()]

    async def update(self, project: Project) -> Project:
        async with self._db.session() as session:
            row = await session.get(ProjectRow, project.id)
            if row is None:
                raise NotFoundError("Project not found", details={"project_id": project.id})

            row.name = project.name
            row.description = project.description
            row.current_stage = project.current_stage.value
            row.stages = [state.model_dump(mode="json") for state in project.stages]
            row.updated_at = datetime.now(UTC)

            return _to_project(row)

    async def exists(self, project_id: str) -> bool:
        async with self._db.session() as session:
            result = await session.execute(
                select(func.count()).select_from(ProjectRow).where(ProjectRow.id == project_id)
            )
            return (result.scalar_one() or 0) > 0


class SqlArtifactRepository(_Base):
    async def create(self, artifact: Artifact) -> Artifact:
        async with self._db.session() as session:
            session.add(
                ArtifactRow(
                    id=artifact.id,
                    project_id=artifact.project_id,
                    type=artifact.type.value,
                    title=artifact.title,
                    stage=artifact.stage.value,
                    owner_role=artifact.owner_role.value,
                    status=artifact.status.value,
                    current_version=artifact.current_version,
                    created_at=artifact.created_at,
                    updated_at=artifact.updated_at,
                )
            )
        return artifact

    async def get(self, artifact_id: str) -> Artifact:
        async with self._db.session() as session:
            row = await self._require(session, artifact_id)
            return _to_artifact(row)

    async def update(self, artifact: Artifact) -> Artifact:
        async with self._db.session() as session:
            row = await self._require(session, artifact.id)
            row.title = artifact.title
            row.status = artifact.status.value
            row.updated_at = datetime.now(UTC)
            return _to_artifact(row)

    async def list_for_project(
        self,
        project_id: str,
        *,
        stage: LifecycleStage | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> list[Artifact]:
        async with self._db.session() as session:
            query = select(ArtifactRow).where(ArtifactRow.project_id == project_id)
            if stage is not None:
                query = query.where(ArtifactRow.stage == stage.value)
            if artifact_type is not None:
                query = query.where(ArtifactRow.type == artifact_type.value)

            result = await session.execute(query.order_by(ArtifactRow.created_at))
            return [_to_artifact(row) for row in result.scalars()]

    async def find_by_identity(
        self, project_id: str, artifact_type: ArtifactType, stage: LifecycleStage, title: str
    ) -> Artifact | None:
        async with self._db.session() as session:
            result = await session.execute(
                select(ArtifactRow).where(
                    ArtifactRow.project_id == project_id,
                    ArtifactRow.type == artifact_type.value,
                    ArtifactRow.stage == stage.value,
                    ArtifactRow.title == title,
                )
            )
            row = result.scalars().first()
            return _to_artifact(row) if row else None

    async def append_version(
        self, artifact_id: str, version: ArtifactVersion
    ) -> ArtifactVersion:
        """Append a version and advance the artifact's current version.

        The version number is assigned here from the artifact's current value,
        ignoring any number the caller supplied. Two writers racing would
        otherwise both compute the same next number; the unique constraint on
        ``(artifact_id, version)`` turns that into a database error rather than
        silent overwriting, which is surfaced as a ``ConflictError``.
        """
        async with self._db.session() as session:
            artifact_row = await self._require(session, artifact_id)
            next_version = artifact_row.current_version + 1

            stored = ArtifactVersion(
                id=version.id,
                artifact_id=artifact_id,
                version=next_version,
                body_markdown=version.body_markdown,
                content=version.content,
                produced_by_run_id=version.produced_by_run_id,
                summary=version.summary,
                confidence=version.confidence,
                created_at=version.created_at,
            )

            session.add(
                ArtifactVersionRow(
                    id=stored.id,
                    artifact_id=artifact_id,
                    version=stored.version,
                    body_markdown=stored.body_markdown,
                    content=stored.content,
                    produced_by_run_id=stored.produced_by_run_id,
                    summary=stored.summary,
                    confidence=stored.confidence,
                    created_at=stored.created_at,
                )
            )

            artifact_row.current_version = next_version
            artifact_row.updated_at = datetime.now(UTC)

            try:
                await session.flush()
            except Exception as exc:
                raise ConflictError(
                    "Artifact version was written concurrently",
                    details={"artifact_id": artifact_id, "version": next_version},
                ) from exc

        logger.info(
            "Artifact version appended",
            extra={"artifact_id": artifact_id, "version": next_version},
        )
        return stored

    async def get_version(
        self, artifact_id: str, version: int | None = None
    ) -> ArtifactWithVersion:
        async with self._db.session() as session:
            artifact_row = await self._require(session, artifact_id)

            target = version if version is not None else artifact_row.current_version
            if target < 1:
                raise NotFoundError(
                    "Artifact has no versions yet", details={"artifact_id": artifact_id}
                )

            result = await session.execute(
                select(ArtifactVersionRow).where(
                    ArtifactVersionRow.artifact_id == artifact_id,
                    ArtifactVersionRow.version == target,
                )
            )
            version_row = result.scalar_one_or_none()
            if version_row is None:
                raise NotFoundError(
                    "Artifact version not found",
                    details={"artifact_id": artifact_id, "version": target},
                )

            return ArtifactWithVersion(
                artifact=_to_artifact(artifact_row), version=_to_version(version_row)
            )

    async def list_versions(self, artifact_id: str) -> list[ArtifactVersion]:
        async with self._db.session() as session:
            await self._require(session, artifact_id)
            result = await session.execute(
                select(ArtifactVersionRow)
                .where(ArtifactVersionRow.artifact_id == artifact_id)
                .order_by(ArtifactVersionRow.version)
            )
            return [_to_version(row) for row in result.scalars()]

    async def current_versions(self, project_id: str) -> dict[str, int]:
        async with self._db.session() as session:
            result = await session.execute(
                select(ArtifactRow.id, ArtifactRow.current_version).where(
                    ArtifactRow.project_id == project_id
                )
            )
            return dict(result.all())  # type: ignore[arg-type]

    @staticmethod
    async def _require(session: AsyncSession, artifact_id: str) -> ArtifactRow:
        row = await session.get(ArtifactRow, artifact_id)
        if row is None:
            raise NotFoundError("Artifact not found", details={"artifact_id": artifact_id})
        return row


class SqlTraceRepository(_Base):
    async def add_edge(self, edge: TraceEdge) -> TraceEdge:
        async with self._db.session() as session:
            session.add(
                TraceEdgeRow(
                    id=edge.id,
                    project_id=edge.project_id,
                    upstream_artifact_id=edge.upstream_artifact_id,
                    downstream_artifact_id=edge.downstream_artifact_id,
                    kind=edge.kind.value,
                    upstream_version=edge.upstream_version,
                    created_by_run_id=edge.created_by_run_id,
                    rationale=edge.rationale,
                    created_at=edge.created_at,
                )
            )
        return edge

    async def list_for_project(self, project_id: str) -> list[TraceEdge]:
        async with self._db.session() as session:
            result = await session.execute(
                select(TraceEdgeRow)
                .where(TraceEdgeRow.project_id == project_id)
                .order_by(TraceEdgeRow.created_at)
            )
            return [_to_edge(row) for row in result.scalars()]

    async def upstream_of(self, artifact_id: str) -> list[TraceEdge]:
        return await self._by_direction(TraceEdgeRow.downstream_artifact_id, artifact_id)

    async def downstream_of(self, artifact_id: str) -> list[TraceEdge]:
        return await self._by_direction(TraceEdgeRow.upstream_artifact_id, artifact_id)

    async def analyse_impact(
        self, project_id: str, artifact_id: str, *, max_depth: int | None = None
    ) -> ImpactAnalysis:
        """Compute blast radius.

        The whole project's edges are loaded and traversed in memory rather than
        walked with recursive SQL. At MVP scale — hundreds of edges — this is
        faster than N round trips, and it keeps the traversal rules in the pure,
        directly testable domain function.
        """
        edges = await self.list_for_project(project_id)
        return analyse_impact(artifact_id, edges, max_depth=max_depth)

    async def stale_edges(self, project_id: str) -> list[StaleEdge]:
        async with self._db.session() as session:
            edge_result = await session.execute(
                select(TraceEdgeRow).where(TraceEdgeRow.project_id == project_id)
            )
            edges = [_to_edge(row) for row in edge_result.scalars()]

            version_result = await session.execute(
                select(ArtifactRow.id, ArtifactRow.current_version).where(
                    ArtifactRow.project_id == project_id
                )
            )
            current: dict[str, int] = dict(version_result.all())  # type: ignore[arg-type]

        return stale_edges(edges, current)

    async def _by_direction(self, column: Any, artifact_id: str) -> list[TraceEdge]:
        async with self._db.session() as session:
            result = await session.execute(
                select(TraceEdgeRow).where(column == artifact_id).order_by(TraceEdgeRow.created_at)
            )
            return [_to_edge(row) for row in result.scalars()]


class SqlAgentRunRepository(_Base):
    async def create(self, run: AgentRun) -> AgentRun:
        async with self._db.session() as session:
            session.add(self._to_row(run))
        return run

    async def get(self, run_id: str) -> AgentRun:
        async with self._db.session() as session:
            row = await session.get(AgentRunRow, run_id)
            if row is None:
                raise NotFoundError("Agent run not found", details={"run_id": run_id})
            return _to_run(row)

    async def update(self, run: AgentRun) -> AgentRun:
        async with self._db.session() as session:
            row = await session.get(AgentRunRow, run.id)
            if row is None:
                raise NotFoundError("Agent run not found", details={"run_id": run.id})

            row.status = run.status.value
            row.task = run.task
            row.reasoning_summary = run.reasoning_summary
            row.confidence = run.confidence
            row.input_artifact_ids = list(run.input_artifact_ids)
            row.output_artifact_ids = list(run.output_artifact_ids)
            row.blocked_on = list(run.blocked_on)
            row.provider = run.provider
            row.model = run.model
            row.input_tokens = run.token_usage.input_tokens
            row.output_tokens = run.token_usage.output_tokens
            row.requires_approval = run.requires_approval
            row.approval_reason = run.approval_reason
            row.error = run.error
            row.completed_at = run.completed_at

            return _to_run(row)

    async def list_for_project(
        self, project_id: str, *, role: AgentRole | None = None, limit: int = 100
    ) -> list[AgentRun]:
        async with self._db.session() as session:
            query = select(AgentRunRow).where(AgentRunRow.project_id == project_id)
            if role is not None:
                query = query.where(AgentRunRow.role == role.value)

            result = await session.execute(
                query.order_by(AgentRunRow.started_at.desc()).limit(limit)
            )
            return [_to_run(row) for row in result.scalars()]

    async def latest_for_role(self, project_id: str, role: AgentRole) -> AgentRun | None:
        async with self._db.session() as session:
            result = await session.execute(
                select(AgentRunRow)
                .where(
                    AgentRunRow.project_id == project_id,
                    AgentRunRow.role == role.value,
                )
                .order_by(AgentRunRow.started_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return _to_run(row) if row else None

    @staticmethod
    def _to_row(run: AgentRun) -> AgentRunRow:
        return AgentRunRow(
            id=run.id,
            project_id=run.project_id,
            role=run.role.value,
            stage=run.stage.value,
            status=run.status.value,
            task=run.task,
            reasoning_summary=run.reasoning_summary,
            confidence=run.confidence,
            input_artifact_ids=list(run.input_artifact_ids),
            output_artifact_ids=list(run.output_artifact_ids),
            blocked_on=list(run.blocked_on),
            provider=run.provider,
            model=run.model,
            input_tokens=run.token_usage.input_tokens,
            output_tokens=run.token_usage.output_tokens,
            requires_approval=run.requires_approval,
            approval_reason=run.approval_reason,
            correlation_id=run.correlation_id,
            error=run.error,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )


class SqlApprovalRepository(_Base):
    async def create(self, request: ApprovalRequest) -> ApprovalRequest:
        async with self._db.session() as session:
            session.add(
                ApprovalRow(
                    id=request.id,
                    project_id=request.project_id,
                    kind=request.kind.value,
                    stage=request.stage.value,
                    title=request.title,
                    what_changed=request.what_changed,
                    why=request.why,
                    requested_by=request.requested_by.value,
                    agents_involved=[role.value for role in request.agents_involved],
                    artifact_ids=list(request.artifact_ids),
                    impact=request.impact.model_dump(mode="json") if request.impact else None,
                    status=request.status.value,
                    feedback=request.feedback,
                    decided_at=request.decided_at,
                    created_at=request.created_at,
                )
            )
        return request

    async def get(self, approval_id: str) -> ApprovalRequest:
        async with self._db.session() as session:
            row = await session.get(ApprovalRow, approval_id)
            if row is None:
                raise NotFoundError(
                    "Approval request not found", details={"approval_id": approval_id}
                )
            return _to_approval(row)

    async def update(self, request: ApprovalRequest) -> ApprovalRequest:
        async with self._db.session() as session:
            row = await session.get(ApprovalRow, request.id)
            if row is None:
                raise NotFoundError(
                    "Approval request not found", details={"approval_id": request.id}
                )

            row.status = request.status.value
            row.feedback = request.feedback
            row.decided_at = request.decided_at

            return _to_approval(row)

    async def list_for_project(
        self, project_id: str, *, pending_only: bool = False
    ) -> list[ApprovalRequest]:
        async with self._db.session() as session:
            query = select(ApprovalRow).where(ApprovalRow.project_id == project_id)
            if pending_only:
                query = query.where(ApprovalRow.status == ApprovalStatus.PENDING.value)

            result = await session.execute(query.order_by(ApprovalRow.created_at.desc()))
            return [_to_approval(row) for row in result.scalars()]

    async def list_pending(self, *, limit: int = 50) -> list[ApprovalRequest]:
        async with self._db.session() as session:
            result = await session.execute(
                select(ApprovalRow)
                .where(ApprovalRow.status == ApprovalStatus.PENDING.value)
                .order_by(ApprovalRow.created_at)
                .limit(limit)
            )
            return [_to_approval(row) for row in result.scalars()]


class SqlEventRepository(_Base):
    async def append(self, event: ProjectEvent) -> ProjectEvent:
        async with self._db.session() as session:
            session.add(
                EventRow(
                    id=event.id,
                    project_id=event.project_id,
                    type=event.type.value,
                    stage=event.stage.value if event.stage else None,
                    role=event.role.value if event.role else None,
                    summary=event.summary,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    created_at=event.created_at,
                )
            )
        return event

    async def list_for_project(
        self, project_id: str, *, limit: int = 200, after_id: str | None = None
    ) -> list[ProjectEvent]:
        async with self._db.session() as session:
            query = select(EventRow).where(EventRow.project_id == project_id)

            if after_id is not None:
                # Resolve the cursor's sequence number, then take everything
                # after it. An unknown cursor replays from the start rather than
                # returning nothing, so a stale browser reconnect self-heals.
                cursor = await session.execute(
                    select(EventRow.seq).where(EventRow.id == after_id)
                )
                seq = cursor.scalar_one_or_none()
                if seq is not None:
                    query = query.where(EventRow.seq > seq)

            result = await session.execute(query.order_by(EventRow.seq).limit(limit))
            return [_to_event(row) for row in result.scalars()]

    async def list_recent(self, *, limit: int = 50) -> list[ProjectEvent]:
        async with self._db.session() as session:
            result = await session.execute(
                select(EventRow).order_by(EventRow.seq.desc()).limit(limit)
            )
            rows: Sequence[EventRow] = list(result.scalars())
            return [_to_event(row) for row in reversed(rows)]


class SqlReviewRepository(_Base):
    async def upsert(self, review: ArtifactReview) -> ArtifactReview:
        async with self._db.session() as session:
            result = await session.execute(
                select(ArtifactReviewRow).where(
                    ArtifactReviewRow.artifact_id == review.artifact_id,
                    ArtifactReviewRow.artifact_version == review.artifact_version,
                )
            )
            row = result.scalar_one_or_none()

            payload = {
                "quality_score": review.quality_score,
                "verdict": review.verdict.value,
                "summary": review.summary,
                "strengths": [item.model_dump(mode="json") for item in review.strengths],
                "weaknesses": [item.model_dump(mode="json") for item in review.weaknesses],
                "suggestions": [item.model_dump(mode="json") for item in review.suggestions],
                "deterministic_score": review.deterministic_score,
                "reasoning_applied": review.reasoning_applied,
                "reviewer_provider": review.reviewer_provider,
                "reviewer_model": review.reviewer_model,
            }

            if row is None:
                session.add(
                    ArtifactReviewRow(
                        id=review.id,
                        project_id=review.project_id,
                        artifact_id=review.artifact_id,
                        artifact_version=review.artifact_version,
                        stage=review.stage.value,
                        role=review.role.value,
                        produced_by_run_id=review.produced_by_run_id,
                        created_at=review.created_at,
                        **payload,
                    )
                )
            else:
                for key, value in payload.items():
                    setattr(row, key, value)

        return review

    async def list_for_project(self, project_id: str) -> list[ArtifactReview]:
        async with self._db.session() as session:
            result = await session.execute(
                select(ArtifactReviewRow)
                .where(ArtifactReviewRow.project_id == project_id)
                .order_by(ArtifactReviewRow.created_at)
            )
            return [_to_review(row) for row in result.scalars()]

    async def for_artifact(
        self, artifact_id: str, version: int | None = None
    ) -> ArtifactReview | None:
        async with self._db.session() as session:
            query = select(ArtifactReviewRow).where(
                ArtifactReviewRow.artifact_id == artifact_id
            )
            if version is not None:
                query = query.where(ArtifactReviewRow.artifact_version == version)

            result = await session.execute(
                query.order_by(ArtifactReviewRow.artifact_version.desc()).limit(1)
            )
            row = result.scalar_one_or_none()
            return _to_review(row) if row else None


class SqlSharedMemory:
    """Composes every repository into the single memory collaborator.

    What agents and the orchestrator receive. They never see a session, a query,
    or a row.
    """

    def __init__(self, database: Database) -> None:
        self._projects = SqlProjectRepository(database)
        self._artifacts = SqlArtifactRepository(database)
        self._traces = SqlTraceRepository(database)
        self._runs = SqlAgentRunRepository(database)
        self._approvals = SqlApprovalRepository(database)
        self._events = SqlEventRepository(database)
        self._reviews = SqlReviewRepository(database)

    @property
    def projects(self) -> SqlProjectRepository:
        return self._projects

    @property
    def artifacts(self) -> SqlArtifactRepository:
        return self._artifacts

    @property
    def traces(self) -> SqlTraceRepository:
        return self._traces

    @property
    def runs(self) -> SqlAgentRunRepository:
        return self._runs

    @property
    def approvals(self) -> SqlApprovalRepository:
        return self._approvals

    @property
    def events(self) -> SqlEventRepository:
        return self._events

    @property
    def reviews(self) -> SqlReviewRepository:
        return self._reviews
