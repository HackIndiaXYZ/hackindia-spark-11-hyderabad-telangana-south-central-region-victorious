"""Stage readiness rules — pure, no database."""

from __future__ import annotations

from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import Artifact, ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.orchestration.dependencies import (
    STAGE_GATES,
    STAGE_INPUTS,
    ProjectSnapshot,
    ReadinessStatus,
    evaluate_readiness,
    gated_artifact_ids,
)

PROJECT = "prj_test"


def artifact(
    artifact_type: ArtifactType,
    *,
    stage: LifecycleStage = LifecycleStage.REQUIREMENT_DISCOVERY,
    version: int = 1,
) -> Artifact:
    return Artifact(
        project_id=PROJECT,
        type=artifact_type,
        title=artifact_type.value,
        stage=stage,
        owner_role=AgentRole.PRODUCT_MANAGER,
        current_version=version,
    )


def approval(
    kind: ApprovalKind,
    status: ApprovalStatus,
    *,
    feedback: str | None = None,
) -> ApprovalRequest:
    return ApprovalRequest(
        project_id=PROJECT,
        kind=kind,
        stage=LifecycleStage.ARCHITECTURE,
        title=f"Approve {kind.value}",
        what_changed="...",
        why="...",
        requested_by=AgentRole.EXECUTIVE,
        status=status,
        feedback=feedback,
    )


# --- Inputs -------------------------------------------------------------------


def test_first_stages_require_nothing() -> None:
    """07_System_Architecture.md: a project starts from a name and description."""
    empty = ProjectSnapshot()

    assert evaluate_readiness(LifecycleStage.REQUIREMENT_DISCOVERY, empty).is_ready


def test_missing_inputs_are_named() -> None:
    readiness = evaluate_readiness(LifecycleStage.BUSINESS_VALIDATION, ProjectSnapshot())

    assert readiness.status is ReadinessStatus.MISSING_INPUTS
    assert ArtifactType.PRD in readiness.missing_inputs
    assert "prd" in readiness.detail


def test_stage_becomes_ready_once_inputs_exist() -> None:
    snapshot = ProjectSnapshot(artifacts=[artifact(ArtifactType.PRD)])

    assert evaluate_readiness(LifecycleStage.BUSINESS_VALIDATION, snapshot).is_ready


def test_artifacts_without_content_do_not_satisfy_inputs() -> None:
    """A created-but-empty artifact is not upstream work."""
    snapshot = ProjectSnapshot(artifacts=[artifact(ArtifactType.PRD, version=0)])

    readiness = evaluate_readiness(LifecycleStage.BUSINESS_VALIDATION, snapshot)

    assert readiness.status is ReadinessStatus.MISSING_INPUTS


def test_inputs_are_checked_before_gates() -> None:
    """Asking a human to approve requirements that do not exist is meaningless."""
    readiness = evaluate_readiness(LifecycleStage.ARCHITECTURE, ProjectSnapshot())

    assert readiness.status is ReadinessStatus.MISSING_INPUTS


# --- Gates --------------------------------------------------------------------


def test_gate_is_requested_when_no_approval_exists() -> None:
    snapshot = ProjectSnapshot(
        artifacts=[artifact(ArtifactType.PRD), artifact(ArtifactType.BUSINESS_ANALYSIS)]
    )

    readiness = evaluate_readiness(LifecycleStage.ARCHITECTURE, snapshot)

    assert readiness.status is ReadinessStatus.APPROVAL_REQUIRED
    assert readiness.gate is ApprovalKind.REQUIREMENTS


def test_pending_approval_blocks_the_stage() -> None:
    snapshot = ProjectSnapshot(
        artifacts=[artifact(ArtifactType.PRD), artifact(ArtifactType.BUSINESS_ANALYSIS)],
        approvals=[approval(ApprovalKind.REQUIREMENTS, ApprovalStatus.PENDING)],
    )

    readiness = evaluate_readiness(LifecycleStage.ARCHITECTURE, snapshot)

    assert readiness.status is ReadinessStatus.AWAITING_APPROVAL
    assert readiness.approval_id is not None


def test_granted_approval_unblocks_the_stage() -> None:
    snapshot = ProjectSnapshot(
        artifacts=[artifact(ArtifactType.PRD), artifact(ArtifactType.BUSINESS_ANALYSIS)],
        approvals=[approval(ApprovalKind.REQUIREMENTS, ApprovalStatus.APPROVED)],
    )

    assert evaluate_readiness(LifecycleStage.ARCHITECTURE, snapshot).is_ready


def test_rejection_blocks_and_carries_the_feedback() -> None:
    snapshot = ProjectSnapshot(
        artifacts=[artifact(ArtifactType.PRD), artifact(ArtifactType.BUSINESS_ANALYSIS)],
        approvals=[
            approval(
                ApprovalKind.REQUIREMENTS,
                ApprovalStatus.CHANGES_REQUESTED,
                feedback="Billing scope is unclear.",
            )
        ],
    )

    readiness = evaluate_readiness(LifecycleStage.ARCHITECTURE, snapshot)

    assert readiness.status is ReadinessStatus.BLOCKED_BY_REJECTION
    assert readiness.detail == "Billing scope is unclear."


def test_latest_approval_of_a_kind_wins() -> None:
    """A re-raised gate must not be decided by a superseded request."""
    older = approval(ApprovalKind.REQUIREMENTS, ApprovalStatus.CHANGES_REQUESTED)
    newer = approval(ApprovalKind.REQUIREMENTS, ApprovalStatus.APPROVED)
    newer.created_at = older.created_at.replace(year=older.created_at.year + 1)

    snapshot = ProjectSnapshot(
        artifacts=[artifact(ArtifactType.PRD), artifact(ArtifactType.BUSINESS_ANALYSIS)],
        approvals=[older, newer],
    )

    assert evaluate_readiness(LifecycleStage.ARCHITECTURE, snapshot).is_ready


# --- Specification conformance ------------------------------------------------


def test_gates_cover_the_structural_approvals_the_mvp_requires() -> None:
    """09_MVP_Roadmap.md: requirements, architecture, and final code generation.

    Technology Stack and Major Engineering Decisions are not stage-shaped and are
    raised by agents through `requires_approval` instead.
    """
    assert set(STAGE_GATES.values()) == {
        ApprovalKind.REQUIREMENTS,
        ApprovalKind.ARCHITECTURE,
        ApprovalKind.CODE_GENERATION,
    }


def test_every_lifecycle_stage_has_declared_inputs() -> None:
    """A stage missing from STAGE_INPUTS would silently be treated as ready."""
    assert set(STAGE_INPUTS) == set(LifecycleStage)


def test_gated_artifacts_are_the_ones_the_stage_consumes() -> None:
    """A reviewer sees what the next stage builds on, not the whole project."""
    prd = artifact(ArtifactType.PRD)
    analysis = artifact(ArtifactType.BUSINESS_ANALYSIS)
    unrelated = artifact(ArtifactType.TEST_PLAN, stage=LifecycleStage.TESTING)

    ids = gated_artifact_ids(
        LifecycleStage.ARCHITECTURE,
        ProjectSnapshot(artifacts=[prd, analysis, unrelated]),
    )

    assert set(ids) == {prd.id, analysis.id}
