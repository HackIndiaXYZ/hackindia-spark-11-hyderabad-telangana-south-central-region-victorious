"""Stage dependency and readiness rules.

`05_AI_Agent_Architecture.md` lists "Track dependencies" among the Executive AI's
responsibilities, and `12_Risk_Analysis.md` prescribes "dependency validation" as
a mitigation for Agent Coordination Failure. These rules are that validation.

Everything here is pure and deterministic. Whether a stage may run is a question
about which artifacts exist and which approvals were granted — a computation, not
a judgement. Asking a language model would introduce hallucination risk into the
one place the platform must be exactly right.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType
from app.domain.lifecycle import LifecycleStage

#: Artifact types each stage requires from upstream before it may run.
#:
#: Derived from the per-agent outputs in `05_AI_Agent_Architecture.md` and the
#: lifecycle in `09_MVP_Roadmap.md`. The first two stages have no requirements:
#: `07_System_Architecture.md` mandates that a project begins from a name and a
#: description alone.
STAGE_INPUTS: dict[LifecycleStage, frozenset[ArtifactType]] = {
    LifecycleStage.IDEA: frozenset(),
    LifecycleStage.REQUIREMENT_DISCOVERY: frozenset(),
    LifecycleStage.BUSINESS_VALIDATION: frozenset({ArtifactType.PRD}),
    LifecycleStage.ARCHITECTURE: frozenset(
        {ArtifactType.PRD, ArtifactType.BUSINESS_ANALYSIS}
    ),
    LifecycleStage.DEVELOPMENT_PLANNING: frozenset({ArtifactType.SYSTEM_ARCHITECTURE}),
    LifecycleStage.IMPLEMENTATION: frozenset(
        {ArtifactType.IMPLEMENTATION_PLAN, ArtifactType.SYSTEM_ARCHITECTURE}
    ),
    LifecycleStage.TESTING: frozenset(
        {ArtifactType.ACCEPTANCE_CRITERIA, ArtifactType.REPOSITORY_STRUCTURE}
    ),
    LifecycleStage.DOCUMENTATION: frozenset(
        {ArtifactType.SYSTEM_ARCHITECTURE, ArtifactType.REPOSITORY_STRUCTURE}
    ),
    LifecycleStage.DEPLOYMENT_PREPARATION: frozenset({ArtifactType.README}),
}

#: Approval that must be granted before a stage may execute.
#:
#: `09_MVP_Roadmap.md` requires human approval of Requirements, Architecture,
#: Technology Stack, Major Engineering Decisions, and Final Code Generation.
#: Three of those are structural properties of the lifecycle and are gated here:
#:
#: - requirements are signed off before anything is designed from them;
#: - the architecture is signed off before work is planned against it;
#: - an explicit go-ahead precedes code generation ("Final Code Generation").
#:
#: Technology Stack and Major Engineering Decisions are not stage-shaped — they
#: arise from what an agent concludes — so agents raise them through
#: `AgentOutput.requires_approval` instead.
STAGE_GATES: dict[LifecycleStage, ApprovalKind] = {
    LifecycleStage.ARCHITECTURE: ApprovalKind.REQUIREMENTS,
    LifecycleStage.DEVELOPMENT_PLANNING: ApprovalKind.ARCHITECTURE,
    LifecycleStage.IMPLEMENTATION: ApprovalKind.CODE_GENERATION,
}


class ReadinessStatus(StrEnum):
    """Whether a stage may execute."""

    READY = "ready"
    MISSING_INPUTS = "missing_inputs"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVAL_REQUIRED = "approval_required"
    """A gate applies and no request exists yet — one must be raised."""

    BLOCKED_BY_REJECTION = "blocked_by_rejection"


@dataclass(frozen=True)
class Readiness:
    """The outcome of evaluating a stage's preconditions."""

    stage: LifecycleStage
    status: ReadinessStatus
    missing_inputs: frozenset[ArtifactType] = frozenset()
    gate: ApprovalKind | None = None
    approval_id: str | None = None
    detail: str = ""

    @property
    def is_ready(self) -> bool:
        return self.status is ReadinessStatus.READY


@dataclass(frozen=True)
class ProjectSnapshot:
    """The facts readiness is evaluated against.

    Passed explicitly rather than fetched inside, so the rules stay pure and each
    orchestration pass reads shared memory exactly once.
    """

    artifacts: list[Artifact] = field(default_factory=list)
    approvals: list[ApprovalRequest] = field(default_factory=list)

    def approved_types(self) -> set[ArtifactType]:
        """Artifact types present with content.

        Presence, not approval, satisfies an *input* requirement: approval is
        gated separately by ``STAGE_GATES``. Requiring both here would make the
        gates unreachable, since a stage could never run to produce what its own
        gate is meant to review.
        """
        return {artifact.type for artifact in self.artifacts if artifact.has_content}

    def approval_for(self, kind: ApprovalKind) -> ApprovalRequest | None:
        """Most recent approval request of a kind, if any."""
        matching = [approval for approval in self.approvals if approval.kind is kind]
        if not matching:
            return None
        return max(matching, key=lambda approval: approval.created_at)


def evaluate_readiness(stage: LifecycleStage, snapshot: ProjectSnapshot) -> Readiness:
    """Decide whether ``stage`` may execute now.

    Inputs are checked before gates: an approval request to review requirements
    that do not exist yet would be meaningless.
    """
    required = STAGE_INPUTS.get(stage, frozenset())
    missing = required - snapshot.approved_types()

    if missing:
        return Readiness(
            stage=stage,
            status=ReadinessStatus.MISSING_INPUTS,
            missing_inputs=frozenset(missing),
            detail=(
                f"{stage.value} requires "
                + ", ".join(sorted(artifact.value for artifact in missing))
            ),
        )

    gate = STAGE_GATES.get(stage)
    if gate is None:
        return Readiness(stage=stage, status=ReadinessStatus.READY)

    approval = snapshot.approval_for(gate)

    if approval is None:
        return Readiness(
            stage=stage,
            status=ReadinessStatus.APPROVAL_REQUIRED,
            gate=gate,
            detail=f"{stage.value} requires human approval of {gate.value}",
        )

    if approval.status is ApprovalStatus.PENDING:
        return Readiness(
            stage=stage,
            status=ReadinessStatus.AWAITING_APPROVAL,
            gate=gate,
            approval_id=approval.id,
            detail=f"Waiting for a decision on {approval.title}",
        )

    if approval.status.unblocks_progress:
        return Readiness(stage=stage, status=ReadinessStatus.READY, gate=gate)

    return Readiness(
        stage=stage,
        status=ReadinessStatus.BLOCKED_BY_REJECTION,
        gate=gate,
        approval_id=approval.id,
        detail=approval.feedback or f"{gate.value} was not approved",
    )


def gated_artifact_ids(
    stage: LifecycleStage, snapshot: ProjectSnapshot
) -> list[str]:
    """Artifacts a stage's gate is asking the reviewer to sign off.

    The artifacts the gate exists to protect are the ones the stage consumes, so
    the Approval Center shows the reviewer exactly what the next stage will build
    on rather than the whole project.
    """
    required = STAGE_INPUTS.get(stage, frozenset())
    return [
        artifact.id
        for artifact in snapshot.artifacts
        if artifact.type in required and artifact.has_content
    ]


def unapproved_artifact_ids(snapshot: ProjectSnapshot) -> list[str]:
    """Artifacts with content that no human has signed off yet."""
    return [
        artifact.id
        for artifact in snapshot.artifacts
        if artifact.has_content and artifact.status is not ArtifactStatus.APPROVED
    ]
