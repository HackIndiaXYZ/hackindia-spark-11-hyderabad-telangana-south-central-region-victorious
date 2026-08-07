"""Conflict detection — pure, no database."""

from __future__ import annotations

from app.domain.agents import AgentRun, AgentRunStatus
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.traceability import TraceEdge
from app.orchestration.conflicts import (
    ConflictKind,
    ConflictSeverity,
    blocking,
    detect_conflicts,
)

PROJECT = "prj_test"


def artifact(
    artifact_type: ArtifactType,
    *,
    title: str | None = None,
    status: ArtifactStatus = ArtifactStatus.DRAFT,
    stage: LifecycleStage = LifecycleStage.ARCHITECTURE,
    role: AgentRole = AgentRole.SOFTWARE_ARCHITECT,
) -> Artifact:
    return Artifact(
        project_id=PROJECT,
        type=artifact_type,
        title=title or artifact_type.value,
        stage=stage,
        owner_role=role,
        status=status,
        current_version=1,
    )


def run(
    *,
    role: AgentRole = AgentRole.SOFTWARE_ARCHITECT,
    confidence: float | None = 0.9,
    outputs: list[str] | None = None,
) -> AgentRun:
    return AgentRun(
        project_id=PROJECT,
        role=role,
        stage=LifecycleStage.ARCHITECTURE,
        status=AgentRunStatus.COMPLETED,
        confidence=confidence,
        output_artifact_ids=outputs or [],
    )


def test_clean_project_has_no_conflicts() -> None:
    assert (
        detect_conflicts(artifacts=[], edges=[], current_versions={}, runs=[]) == []
    )


# --- Stale derivation ---------------------------------------------------------


def test_stale_derivation_is_blocking() -> None:
    """Continuing on a stale derivation compounds the inconsistency."""
    prd = artifact(ArtifactType.PRD, title="Requirements")
    architecture = artifact(ArtifactType.SYSTEM_ARCHITECTURE, title="Architecture")

    conflicts = detect_conflicts(
        artifacts=[prd, architecture],
        edges=[
            TraceEdge(
                project_id=PROJECT,
                upstream_artifact_id=prd.id,
                downstream_artifact_id=architecture.id,
                upstream_version=1,
            )
        ],
        current_versions={prd.id: 3, architecture.id: 1},
        runs=[],
    )

    assert len(conflicts) == 1
    assert conflicts[0].kind is ConflictKind.STALE_DERIVATION
    assert conflicts[0].severity is ConflictSeverity.BLOCKING
    assert conflicts[0].detail["versions_behind"] == 2
    assert "Architecture" in conflicts[0].summary
    assert "Requirements" in conflicts[0].summary


def test_current_derivation_is_not_flagged() -> None:
    prd = artifact(ArtifactType.PRD)
    architecture = artifact(ArtifactType.SYSTEM_ARCHITECTURE)

    conflicts = detect_conflicts(
        artifacts=[prd, architecture],
        edges=[
            TraceEdge(
                project_id=PROJECT,
                upstream_artifact_id=prd.id,
                downstream_artifact_id=architecture.id,
                upstream_version=2,
            )
        ],
        current_versions={prd.id: 2},
        runs=[],
    )

    assert conflicts == []


# --- Duplicate authority ------------------------------------------------------


def test_two_approved_artifacts_of_one_type_is_blocking() -> None:
    """15_Development_Guidelines.md: shared memory is *the* single source of truth."""
    first = artifact(ArtifactType.SYSTEM_ARCHITECTURE, status=ArtifactStatus.APPROVED)
    second = artifact(ArtifactType.SYSTEM_ARCHITECTURE, status=ArtifactStatus.APPROVED)

    conflicts = detect_conflicts(
        artifacts=[first, second], edges=[], current_versions={}, runs=[]
    )

    assert len(conflicts) == 1
    assert conflicts[0].kind is ConflictKind.DUPLICATE_AUTHORITY
    assert conflicts[0].severity is ConflictSeverity.BLOCKING
    assert set(conflicts[0].artifact_ids) == {first.id, second.id}


def test_competing_drafts_are_allowed() -> None:
    """Only approved artifacts claim authority; drafts are work in progress."""
    conflicts = detect_conflicts(
        artifacts=[
            artifact(ArtifactType.SYSTEM_ARCHITECTURE),
            artifact(ArtifactType.SYSTEM_ARCHITECTURE),
        ],
        edges=[],
        current_versions={},
        runs=[],
    )

    assert conflicts == []


def test_different_types_do_not_collide() -> None:
    conflicts = detect_conflicts(
        artifacts=[
            artifact(ArtifactType.SYSTEM_ARCHITECTURE, status=ArtifactStatus.APPROVED),
            artifact(ArtifactType.API_CONTRACT, status=ArtifactStatus.APPROVED),
        ],
        edges=[],
        current_versions={},
        runs=[],
    )

    assert conflicts == []


# --- Concerns and confidence --------------------------------------------------


def test_agent_concerns_are_advisory() -> None:
    """Escalating every concern to blocking would deter agents from raising them."""
    architect = run()

    conflicts = detect_conflicts(
        artifacts=[],
        edges=[],
        current_versions={},
        runs=[architect],
        concerns_by_run={architect.id: ["Billing requirements are ambiguous."]},
    )

    assert len(conflicts) == 1
    assert conflicts[0].kind is ConflictKind.UNRESOLVED_CONCERN
    assert conflicts[0].severity is ConflictSeverity.ADVISORY
    assert "Billing requirements are ambiguous." in conflicts[0].summary


def test_low_confidence_is_advisory() -> None:
    """Blocking on low confidence would pressure agents toward inflated scores."""
    conflicts = detect_conflicts(
        artifacts=[], edges=[], current_versions={}, runs=[run(confidence=0.3)]
    )

    assert len(conflicts) == 1
    assert conflicts[0].kind is ConflictKind.LOW_CONFIDENCE
    assert conflicts[0].severity is ConflictSeverity.ADVISORY
    assert "30%" in conflicts[0].summary


def test_confident_runs_are_not_flagged() -> None:
    conflicts = detect_conflicts(
        artifacts=[], edges=[], current_versions={}, runs=[run(confidence=0.85)]
    )

    assert conflicts == []


def test_runs_without_confidence_are_not_flagged() -> None:
    """A run still in flight has no score yet; absence is not low confidence."""
    conflicts = detect_conflicts(
        artifacts=[], edges=[], current_versions={}, runs=[run(confidence=None)]
    )

    assert conflicts == []


# --- Aggregation --------------------------------------------------------------


def test_blocking_conflicts_are_ordered_first() -> None:
    prd = artifact(ArtifactType.PRD)
    architecture = artifact(ArtifactType.SYSTEM_ARCHITECTURE)

    conflicts = detect_conflicts(
        artifacts=[prd, architecture],
        edges=[
            TraceEdge(
                project_id=PROJECT,
                upstream_artifact_id=prd.id,
                downstream_artifact_id=architecture.id,
                upstream_version=1,
            )
        ],
        current_versions={prd.id: 2},
        runs=[run(confidence=0.2)],
    )

    assert len(conflicts) == 2
    assert conflicts[0].severity is ConflictSeverity.BLOCKING
    assert len(blocking(conflicts)) == 1
