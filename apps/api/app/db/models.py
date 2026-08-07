"""SQLAlchemy table definitions.

These mirror the domain models but are a separate layer on purpose. Domain models
express engineering meaning and stay free of persistence; these express storage.
Mapping between them happens in ``app/memory/sql_repository.py``.

The duplication is deliberate and bounded: it is what lets the domain layer be
framework-free (ADR-0003) and what allows the storage schema to be indexed,
denormalised, or migrated without any agent noticing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base.

    ``JSON`` is used rather than PostgreSQL's ``JSONB`` so the same schema runs on
    SQLite for native development and PostgreSQL in compose (ADR-0005). Where
    Milestone 8 needs indexed JSON containment queries, a dialect-specific index
    can be added in a migration without changing these definitions.
    """

    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[str]: JSON}


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    artifacts: Mapped[list[ArtifactRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[ProjectRow] = relationship(back_populates="artifacts")
    versions: Mapped[list[ArtifactVersionRow]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="ArtifactVersionRow.version",
    )

    __table_args__ = (
        # The Knowledge Base and every stage-scoped context read filter on these.
        Index("ix_artifacts_project_stage", "project_id", "stage"),
        Index("ix_artifacts_project_type", "project_id", "type"),
    )


class ArtifactVersionRow(Base):
    __tablename__ = "artifact_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    produced_by_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    artifact: Mapped[ArtifactRow] = relationship(back_populates="versions")

    __table_args__ = (
        # Enforces append-only versioning at the storage layer: a duplicate
        # version number is rejected by the database, not merely avoided by
        # application code.
        UniqueConstraint("artifact_id", "version", name="uq_artifact_version"),
    )


class TraceEdgeRow(Base):
    __tablename__ = "trace_edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    upstream_artifact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    downstream_artifact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    upstream_version: Mapped[int] = mapped_column(Integer, nullable=False)

    created_by_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        # Impact analysis walks downstream; "why does this exist?" walks upstream.
        # Both directions are indexed because both are hot paths.
        Index("ix_trace_upstream", "upstream_artifact_id"),
        Index("ix_trace_downstream", "downstream_artifact_id"),
        Index("ix_trace_project", "project_id"),
    )


class AgentRunRow(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)

    task: Mapped[str] = mapped_column(Text, default="")
    reasoning_summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    input_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked_on: Mapped[list[str]] = mapped_column(JSON, default=list)

    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_runs_project_started", "project_id", "started_at"),
        Index("ix_runs_project_role", "project_id", "role"),
    )


class ApprovalRow(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    what_changed: Mapped[str] = mapped_column(Text, nullable=False)
    why: Mapped[str] = mapped_column(Text, nullable=False)

    requested_by: Mapped[str] = mapped_column(String(50), nullable=False)
    agents_involved: Mapped[list[str]] = mapped_column(JSON, default=list)
    artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    impact: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_approvals_project_status", "project_id", "status"),)


class EventRow(Base):
    __tablename__ = "events"

    # Monotonic sequence, separate from the public ID: it gives the live stream a
    # reliable resume cursor. Timestamps alone are not enough — two events can
    # share a millisecond.
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_events_project_seq", "project_id", "seq"),)
