"""The Executive AI (Engineering Director).

`05_AI_Agent_Architecture.md` gives it nine responsibilities: receive user
requests, maintain project state, route work between agents, track dependencies,
resolve conflicts, maintain the project timeline, synchronize project context,
handle approvals, and monitor the overall workflow. Its outputs are task
assignments, updated workflow, and shared project state.

`15_Development_Guidelines.md` is explicit about the boundary:

    The Executive AI (Engineering Director) coordinates engineering activities
    but does not directly perform engineering work.

That rule is enforced structurally rather than by discipline. This class lives in
``app.orchestration``, not ``app.agents``; it does not extend
:class:`app.agents.base.BaseAgent`, and so it has no artifact-writing path at
all. It cannot produce a PRD or an architecture even if a future change tried to
make it — there is no code path from here to ``artifacts.create``.

**Routing decisions are computed, not reasoned.** Whether a stage may run is a
question about which artifacts exist and which approvals were granted, and
:mod:`app.orchestration.dependencies` answers it deterministically.
`12_Risk_Analysis.md` rates AI Hallucination a High risk; putting a language
model in charge of dependency validation would place that risk in the mechanism
whose job is preventing it.

The Executive uses reasoning for exactly one thing: writing the prose a human
reads at an approval gate. Even there, a provider failure falls back to
deterministic text — `09_MVP_Roadmap.md` makes approval non-negotiable, so the
gate cannot depend on a working model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.logging import get_correlation_id, get_logger
from app.domain.agents import AgentMessage
from app.domain.approvals import ApprovalKind, ApprovalRequest
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import (
    ROLE_TITLES,
    STAGE_OWNERS,
    STAGE_SEQUENCE,
    AgentRole,
    LifecycleStage,
    StageStatus,
)
from app.domain.projects import Project, StageState
from app.events.bus import EventBus
from app.llm.provider import CompletionRequest, LLMProvider, Message, Role
from app.memory.repository import SharedMemory
from app.orchestration.conflicts import Conflict, blocking, detect_conflicts
from app.orchestration.dependencies import (
    ProjectSnapshot,
    Readiness,
    ReadinessStatus,
    evaluate_readiness,
    gated_artifact_ids,
)

logger = get_logger(__name__)


class CoordinationAction(StrEnum):
    """What the Executive AI has decided should happen next."""

    EXECUTE_STAGE = "execute_stage"
    REQUEST_APPROVAL = "request_approval"
    AWAIT_APPROVAL = "await_approval"
    HALT_BLOCKED = "halt_blocked"
    COMPLETE = "complete"


@dataclass(frozen=True)
class CoordinationDecision:
    """One coordination decision, with the reasoning that produced it.

    Every field a user would need to understand *why* the workflow did what it
    did. `12_Risk_Analysis.md` mitigates Loss of User Trust with "explainable
    reasoning" and "transparent decision history"; an opaque router would fail
    that regardless of how correct it was.
    """

    action: CoordinationAction
    stage: LifecycleStage | None = None
    role: AgentRole | None = None
    readiness: Readiness | None = None
    gate: ApprovalKind | None = None
    approval_id: str | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    rationale: str = ""

    @property
    def halts(self) -> bool:
        return self.action in {
            CoordinationAction.AWAIT_APPROVAL,
            CoordinationAction.HALT_BLOCKED,
            CoordinationAction.COMPLETE,
        }


class ApprovalNarration(BaseModel):
    """Prose the Executive AI writes for an approval gate.

    The three fields `10_UI_UX_Plan.md` requires a reviewer to see. The remaining
    two — which agents were involved, and the downstream impact — are facts, not
    prose, and are computed rather than written.
    """

    title: str = Field(max_length=200, description="What is being approved.")
    what_changed: str = Field(description="Plain-language description of the work under review.")
    why: str = Field(description="Why the organization produced it this way.")


class ExecutiveAI:
    """Coordinates the engineering organization. Performs no engineering work."""

    role = AgentRole.EXECUTIVE

    def __init__(
        self,
        memory: SharedMemory,
        provider: LLMProvider,
        events: EventBus,
    ) -> None:
        self._memory = memory
        self._provider = provider
        self._events = events

    @property
    def title(self) -> str:
        return ROLE_TITLES[AgentRole.EXECUTIVE]

    # --- Assessment -----------------------------------------------------------

    async def assess(self, project_id: str) -> CoordinationDecision:
        """Decide what the organization should do next.

        Reads shared memory once and evaluates deterministically. Blocking
        conflicts take precedence over everything: proceeding while an
        architecture is known to be derived from superseded requirements would
        compound the inconsistency rather than surface it.
        """
        project = await self._memory.projects.get(project_id)
        snapshot = await self._snapshot(project_id)

        conflicts = await self._detect(project_id)
        if fatal := blocking(conflicts):
            return CoordinationDecision(
                action=CoordinationAction.HALT_BLOCKED,
                conflicts=conflicts,
                rationale=(
                    f"{len(fatal)} blocking conflict(s) must be resolved before work "
                    f"continues: {fatal[0].summary}"
                ),
            )

        next_stage = self._next_incomplete_stage(project)
        if next_stage is None:
            return CoordinationDecision(
                action=CoordinationAction.COMPLETE,
                conflicts=conflicts,
                rationale="Every lifecycle stage is complete.",
            )

        readiness = evaluate_readiness(next_stage, snapshot)
        role = STAGE_OWNERS.get(next_stage)

        match readiness.status:
            case ReadinessStatus.READY:
                return CoordinationDecision(
                    action=CoordinationAction.EXECUTE_STAGE,
                    stage=next_stage,
                    role=role,
                    readiness=readiness,
                    conflicts=conflicts,
                    rationale=(
                        f"{next_stage.value.replace('_', ' ').title()} is ready; "
                        f"assigning to the {ROLE_TITLES[role] if role else 'organization'}."
                    ),
                )

            case ReadinessStatus.APPROVAL_REQUIRED:
                return CoordinationDecision(
                    action=CoordinationAction.REQUEST_APPROVAL,
                    stage=next_stage,
                    role=role,
                    readiness=readiness,
                    gate=readiness.gate,
                    conflicts=conflicts,
                    rationale=readiness.detail,
                )

            case ReadinessStatus.AWAITING_APPROVAL:
                return CoordinationDecision(
                    action=CoordinationAction.AWAIT_APPROVAL,
                    stage=next_stage,
                    readiness=readiness,
                    gate=readiness.gate,
                    approval_id=readiness.approval_id,
                    conflicts=conflicts,
                    rationale=readiness.detail,
                )

            case _:
                return CoordinationDecision(
                    action=CoordinationAction.HALT_BLOCKED,
                    stage=next_stage,
                    readiness=readiness,
                    conflicts=conflicts,
                    rationale=readiness.detail,
                )

    async def _detect(self, project_id: str) -> list[Conflict]:
        """Run every conflict detector against current project state."""
        artifacts = await self._memory.artifacts.list_for_project(project_id)
        edges = await self._memory.traces.list_for_project(project_id)
        versions = await self._memory.artifacts.current_versions(project_id)
        runs = await self._memory.runs.list_for_project(project_id)

        return detect_conflicts(
            artifacts=artifacts,
            edges=edges,
            current_versions=versions,
            runs=runs,
        )

    async def _snapshot(self, project_id: str) -> ProjectSnapshot:
        return ProjectSnapshot(
            artifacts=await self._memory.artifacts.list_for_project(project_id),
            approvals=await self._memory.approvals.list_for_project(project_id),
        )

    @staticmethod
    def _next_incomplete_stage(project: Project) -> LifecycleStage | None:
        """First stage in lifecycle order that has not completed.

        ``IDEA`` is skipped: it is the state a project starts in, not work the
        organization performs. `07_System_Architecture.md` has the Executive
        begin requirement discovery as soon as a project exists.
        """
        completed = {state.stage for state in project.stages if state.is_complete}

        return next(
            (
                stage
                for stage in STAGE_SEQUENCE
                if stage is not LifecycleStage.IDEA and stage not in completed
            ),
            None,
        )

    # --- Routing --------------------------------------------------------------

    def assignment_for(
        self, decision: CoordinationDecision, snapshot_artifact_ids: list[str]
    ) -> AgentMessage:
        """Build the structured assignment sent to a specialist.

        `05_AI_Agent_Architecture.md` requires agents to communicate through
        structured messages routed by the Executive AI rather than free-form
        conversation, with every interaction carrying sender, receiver, task,
        context, dependencies, decision, confidence, and required actions. This
        is that message, and it is recorded on the routing event so the workspace
        can show the actual assignment rather than a description of one.
        """
        if decision.stage is None or decision.role is None:
            raise ValueError("Only an execute decision produces an assignment")

        return AgentMessage(
            sender=AgentRole.EXECUTIVE,
            receiver=decision.role,
            task=f"Perform {decision.stage.value.replace('_', ' ')} for this project.",
            context_artifact_ids=snapshot_artifact_ids,
            dependencies=sorted(
                artifact.value
                for artifact in (
                    decision.readiness.missing_inputs if decision.readiness else frozenset()
                )
            ),
            decision=decision.rationale,
            required_actions=[
                "Produce the artifacts your role owns for this stage.",
                "Declare the upstream artifacts each output was derived from.",
                "Raise concerns about upstream work rather than working around them.",
            ],
        )

    # --- Project state --------------------------------------------------------

    async def mark_stage(
        self, project_id: str, stage: LifecycleStage, status: StageStatus
    ) -> Project:
        """Record a stage transition on the project.

        "Maintain project state" and "maintain project timeline" from
        `05_AI_Agent_Architecture.md`. The Engineering Timeline reads this.
        """
        project = await self._memory.projects.get(project_id)
        now = datetime.now(UTC)

        existing = project.stage_state(stage)
        if existing is None:
            existing = StageState(stage=stage)
            project.stages.append(existing)

        existing.status = status
        if status is StageStatus.IN_PROGRESS and existing.started_at is None:
            existing.started_at = now
        if status is StageStatus.COMPLETED:
            existing.completed_at = now

        project.current_stage = stage
        return await self._memory.projects.update(project)

    # --- Approvals ------------------------------------------------------------

    async def rejection_feedback_for(
        self, project_id: str, stage: LifecycleStage
    ) -> str | None:
        """Return reviewer feedback from the most recent rejection of a stage.

        "Handle approvals" from `05_AI_Agent_Architecture.md`. Passed into the
        agent on re-run so a rejection teaches rather than repeats.
        """
        approvals = await self._memory.approvals.list_for_project(project_id)

        for approval in sorted(approvals, key=lambda a: a.created_at, reverse=True):
            if approval.stage is stage and approval.feedback:
                return approval.feedback
        return None

    async def raise_gate(
        self, project_id: str, stage: LifecycleStage, gate: ApprovalKind
    ) -> ApprovalRequest:
        """Create the approval request blocking a stage.

        Computes the downstream impact before the reviewer decides, which is what
        `10_UI_UX_Plan.md` requires the Approval Center to show — the
        consequences of approving, seen in advance rather than discovered after.
        """
        snapshot = await self._snapshot(project_id)
        artifact_ids = gated_artifact_ids(stage, snapshot)

        narration = await self._narrate(project_id, stage, gate, artifact_ids)

        impact = None
        if artifact_ids:
            impact = await self._memory.traces.analyse_impact(project_id, artifact_ids[0])

        involved = sorted(
            {
                artifact.owner_role
                for artifact in snapshot.artifacts
                if artifact.id in set(artifact_ids)
            }
        )

        request = await self._memory.approvals.create(
            ApprovalRequest(
                project_id=project_id,
                kind=gate,
                stage=stage,
                title=narration.title,
                what_changed=narration.what_changed,
                why=narration.why,
                requested_by=AgentRole.EXECUTIVE,
                agents_involved=involved,
                artifact_ids=artifact_ids,
                impact=impact,
            )
        )

        await self.publish(
            project_id,
            EventType.APPROVAL_REQUESTED,
            f"{self.title} requested approval: {narration.title}",
            {
                "approval_id": request.id,
                "kind": gate.value,
                "stage": stage.value,
                "artifact_ids": artifact_ids,
                "impacted_count": len(impact.impacted) if impact else 0,
            },
            stage=stage,
        )

        logger.info(
            "Approval gate raised",
            extra={
                "project_id": project_id,
                "approval_id": request.id,
                "kind": gate.value,
                "stage": stage.value,
            },
        )
        return request

    async def _narrate(
        self,
        project_id: str,
        stage: LifecycleStage,
        gate: ApprovalKind,
        artifact_ids: list[str],
    ) -> ApprovalNarration:
        """Write the reviewer-facing prose for a gate.

        Falls back to deterministic text on any provider failure. A human
        approval gate that cannot be raised because a language model is
        unavailable would defeat the safeguard entirely.
        """
        fallback = self._fallback_narration(stage, gate, artifact_ids)

        try:
            project = await self._memory.projects.get(project_id)
            summaries: list[str] = []

            for artifact_id in artifact_ids[:6]:
                resolved = await self._memory.artifacts.get_version(artifact_id)
                summaries.append(
                    f"- **{resolved.artifact.title}** "
                    f"({resolved.artifact.type.value}, v{resolved.version.version}): "
                    f"{resolved.version.summary or 'no summary'}"
                )

            response = await self._provider.complete_structured(
                CompletionRequest(
                    system=(
                        "You are the Engineering Director of an AI software engineering "
                        "organization. Write the summary a human reviewer reads before "
                        "approving a stage transition. Be specific and factual about what "
                        "the organization produced and why. Do not invent detail that is "
                        "not present. Do not recommend approval or rejection — the human "
                        "decides."
                    ),
                    messages=[
                        Message(
                            role=Role.USER,
                            content=(
                                f"Project: {project.name}\n"
                                f"Description: {project.description}\n\n"
                                f"Approval required: {gate.value}\n"
                                f"Blocking stage: {stage.value}\n\n"
                                "Artifacts under review:\n" + ("\n".join(summaries) or "- none")
                            ),
                        )
                    ],
                    fixture_key=f"executive.gate.{gate.value}",
                    metadata={"role": "executive", "gate": gate.value},
                ),
                ApprovalNarration,
            )
            return response.value

        except Exception:
            logger.warning(
                "Approval narration unavailable; using deterministic text",
                extra={"project_id": project_id, "gate": gate.value},
                exc_info=True,
            )
            return fallback

    @staticmethod
    def _fallback_narration(
        stage: LifecycleStage, gate: ApprovalKind, artifact_ids: list[str]
    ) -> ApprovalNarration:
        """Deterministic gate prose, used when reasoning is unavailable."""
        gate_label = gate.value.replace("_", " ")
        stage_label = stage.value.replace("_", " ")

        return ApprovalNarration(
            title=f"Approve {gate_label} before {stage_label}",
            what_changed=(
                f"The organization produced {len(artifact_ids)} artifact(s) that "
                f"{stage_label} will build on."
            ),
            why=(
                f"{stage_label.title()} consumes this work directly. Approving it "
                "here prevents downstream engineering from being derived from "
                "output you have not reviewed."
            ),
        )

    # --- Observability --------------------------------------------------------

    async def publish(
        self,
        project_id: str,
        event_type: EventType,
        summary: str,
        payload: dict[str, object],
        *,
        stage: LifecycleStage | None = None,
    ) -> None:
        """Record a coordination event."""
        await self._events.publish(
            ProjectEvent(
                project_id=project_id,
                type=event_type,
                stage=stage,
                role=AgentRole.EXECUTIVE,
                summary=summary,
                payload=payload,
                correlation_id=get_correlation_id(),
            )
        )
