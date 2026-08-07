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
from app.domain.agents import AgentMessage, AgentRun, AgentRunStatus
from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import ArtifactStatus, ArtifactType
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import (
    ROLE_TITLES,
    STAGE_OWNERS,
    STAGE_SEQUENCE,
    AgentRole,
    LifecycleStage,
    StageStatus,
    stage_index,
)
from app.domain.projects import Project, StageState
from app.events.bus import EventBus
from app.llm.provider import CompletionRequest, LLMProvider, Message, Role
from app.memory.repository import SharedMemory
from app.orchestration.conflicts import Conflict, ConflictKind, blocking, detect_conflicts
from app.orchestration.dependencies import (
    ProjectSnapshot,
    Readiness,
    ReadinessStatus,
    evaluate_readiness,
    gated_artifact_ids,
)

logger = get_logger(__name__)

#: Gates an agent raises about its own output, rather than gates the lifecycle
#: imposes on a stage's inputs. The distinction decides which artifacts the
#: reviewer is shown.
_AGENT_RAISED_GATES = frozenset(
    {ApprovalKind.TECHNOLOGY_SELECTION, ApprovalKind.ENGINEERING_DECISION}
)


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

        # An agent that judged its own output too consequential to proceed on
        # blocks everything until a human answers. `09_MVP_Roadmap.md` requires
        # approval of technology selection and major engineering decisions, and
        # neither is stage-shaped — they arise from what an agent concludes.
        if (pending := await self._agent_requested_gate(project_id, snapshot)) is not None:
            run, kind = pending
            return CoordinationDecision(
                action=CoordinationAction.REQUEST_APPROVAL,
                stage=run.stage,
                role=run.role,
                gate=kind,
                conflicts=conflicts,
                rationale=(
                    f"The {ROLE_TITLES[run.role]} asked for review before the "
                    f"organization proceeds: {run.approval_reason or 'no reason given'}"
                ),
            )

        next_stage = self._next_incomplete_stage(project)

        if next_stage is None:
            # A finished project is not a frozen one. Changing a requirement
            # after delivery is the case `04_Existing_Solutions.md` says nothing
            # on the market handles, so the check for stale work has to happen
            # here too — not only while stages remain to run.
            if outstanding := self._outstanding(blocking(conflicts), project, snapshot):
                return self._conflict_decision(
                    self._earliest_affected(outstanding, snapshot), outstanding, conflicts
                )

            return CoordinationDecision(
                action=CoordinationAction.COMPLETE,
                conflicts=conflicts,
                rationale="Every lifecycle stage is complete.",
            )

        readiness = evaluate_readiness(next_stage, snapshot)
        role = STAGE_OWNERS.get(next_stage)

        match readiness.status:
            case ReadinessStatus.READY:
                # Conflicts block engineering work, not the act of asking a human.
                # Checking them here rather than before the readiness evaluation
                # is what lets a project recover from a rejection: revising an
                # artifact necessarily makes its downstream stale, and if that
                # halted everything the revised work could never be re-approved.
                outstanding = self._outstanding(blocking(conflicts), project, snapshot)
                if outstanding:
                    return self._conflict_decision(next_stage, outstanding, conflicts)

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

    @staticmethod
    def _outstanding(
        fatal: list[Conflict], project: Project, snapshot: ProjectSnapshot
    ) -> list[Conflict]:
        """Drop blocking conflicts the workflow is already on its way to fixing.

        A stale artifact whose stage is queued to run again is not something a
        human needs to decide about — the specialist that owns it will rebuild it
        against the current upstream on the next pass. Asking for approval to fix
        something already scheduled to be fixed trains users to click through
        gates, which is how a safeguard stops working.

        Only stale derivations are filtered this way. Every other blocking
        conflict describes a state no rerun resolves.
        """
        stage_by_artifact = {
            artifact.id: artifact.stage for artifact in snapshot.artifacts
        }
        settled = {
            state.stage for state in project.stages if state.status is StageStatus.COMPLETED
        }

        def already_scheduled(conflict: Conflict) -> bool:
            if conflict.kind is not ConflictKind.STALE_DERIVATION:
                return False
            downstream = conflict.artifact_ids[0] if conflict.artifact_ids else None
            stage = stage_by_artifact.get(downstream or "")
            return stage is not None and stage not in settled

        return [conflict for conflict in fatal if not already_scheduled(conflict)]

    @staticmethod
    def _earliest_affected(
        conflicts: list[Conflict], snapshot: ProjectSnapshot
    ) -> LifecycleStage:
        """The earliest lifecycle stage a set of conflicts touches.

        Rebuilding starts from the earliest affected stage, because anything
        later derives from it and would otherwise be regenerated twice.
        """
        stage_by_artifact = {artifact.id: artifact.stage for artifact in snapshot.artifacts}
        stages = [
            stage
            for conflict in conflicts
            for artifact_id in conflict.artifact_ids
            if (stage := stage_by_artifact.get(artifact_id)) is not None
        ]
        return min(stages, key=stage_index) if stages else LifecycleStage.IDEA

    @staticmethod
    def _conflict_decision(
        stage: LifecycleStage, fatal: list[Conflict], conflicts: list[Conflict]
    ) -> CoordinationDecision:
        """Decide what a blocking conflict means for the workflow.

        Stale derivations are recoverable: the upstream moved, and the agents
        that built on it can rebuild against the current version. That is a
        re-synchronisation, and `12_Risk_Analysis.md` puts changes of that
        consequence behind a human — regenerating work the user has already
        approved is not a decision the organization should make alone.

        Anything else blocking — two competing approved artifacts, say — is a
        state the organization cannot resolve by rerunning anyone, so it stops
        and says so.
        """
        stale = [
            conflict for conflict in fatal if conflict.kind is ConflictKind.STALE_DERIVATION
        ]

        if len(stale) == len(fatal):
            return CoordinationDecision(
                action=CoordinationAction.REQUEST_APPROVAL,
                stage=stage,
                gate=ApprovalKind.RESYNCHRONISATION,
                conflicts=conflicts,
                rationale=(
                    f"{len(stale)} artifact(s) were derived from work that has since "
                    "changed. Approving re-synchronisation reruns the affected "
                    "specialists against the current version."
                ),
            )

        return CoordinationDecision(
            action=CoordinationAction.HALT_BLOCKED,
            stage=stage,
            conflicts=conflicts,
            rationale=(
                f"{len(fatal)} blocking conflict(s) must be resolved before work "
                f"continues: {fatal[0].summary}"
            ),
        )

    async def _agent_requested_gate(
        self, project_id: str, snapshot: ProjectSnapshot
    ) -> tuple[AgentRun, ApprovalKind] | None:
        """Find an agent's request for review that no human has answered.

        The kind is inferred from what the run produced: a run that selected
        technologies is a Technology Selection gate, anything else a Major
        Engineering Decision. Both are named in `09_MVP_Roadmap.md`, and the
        distinction is what the reviewer sees in the Approval Center.

        Returns ``None`` once a request of that kind exists for the run's stage —
        raised or already decided — so the gate is not raised twice.
        """
        runs = await self._memory.runs.list_for_project(project_id)

        for run in sorted(runs, key=lambda item: item.started_at):
            if not run.requires_approval or run.status is not AgentRunStatus.COMPLETED:
                continue

            produced = [
                artifact
                for artifact in snapshot.artifacts
                if artifact.id in set(run.output_artifact_ids)
            ]
            kind = (
                ApprovalKind.TECHNOLOGY_SELECTION
                if any(a.type is ArtifactType.TECHNOLOGY_DECISION for a in produced)
                else ApprovalKind.ENGINEERING_DECISION
            )

            already = [
                approval
                for approval in snapshot.approvals
                if approval.kind is kind and approval.stage is run.stage
            ]
            if not already:
                return run, kind

        return None

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

    async def project_state(self, project_id: str) -> Project:
        """Current project state, for callers that need to check before acting."""
        return await self._memory.projects.get(project_id)

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

    async def record_decision(
        self, approval_id: str, decision: ApprovalStatus, feedback: str | None
    ) -> ApprovalRequest:
        """Apply a human's decision and reopen work if they rejected it.

        "Handle approvals" from `05_AI_Agent_Architecture.md`. Lives here rather
        than in the API router because deciding a gate is a coordination act with
        several consequences, and the router should not own any of them.

        Approving marks the reviewed artifacts approved: the human signed off on
        exactly those, and leaving them in draft would make the approval
        invisible everywhere else in the workspace.

        Rejecting reopens the stage that *produced* the artifacts, not the stage
        the gate was blocking. The problem is with the work, so the specialist
        that did it runs again — with the reviewer's feedback in its context, so
        the rejection teaches rather than repeats.
        """
        request = await self._memory.approvals.get(approval_id)
        request.status = decision
        request.feedback = feedback
        request.decided_at = datetime.now(UTC)
        await self._memory.approvals.update(request)

        if request.kind is ApprovalKind.RESYNCHRONISATION:
            # Re-synchronisation is not a sign-off on content; it is permission to
            # rebuild. Approving reruns the affected specialists against the
            # current upstream, and declining leaves the stale work in place with
            # the staleness still visible in the workspace.
            if decision.unblocks_progress:
                await self._resynchronise(request)
        elif decision.unblocks_progress:
            await self._approve_artifacts(request)
        else:
            await self._reopen_producing_stages(request)

        await self.publish(
            request.project_id,
            (
                EventType.APPROVAL_GRANTED
                if decision.unblocks_progress
                else EventType.APPROVAL_REJECTED
            ),
            f"{decision.value.replace('_', ' ').title()}: {request.title}",
            {
                "approval_id": request.id,
                "kind": request.kind.value,
                "artifact_ids": request.artifact_ids,
            },
            stage=request.stage,
        )

        logger.info(
            "Approval decided",
            extra={
                "project_id": request.project_id,
                "approval_id": approval_id,
                "decision": decision.value,
            },
        )
        return request

    async def _approve_artifacts(self, request: ApprovalRequest) -> None:
        """Mark everything the gate covered as approved."""
        for artifact_id in request.artifact_ids:
            artifact = await self._memory.artifacts.get(artifact_id)
            artifact.status = ArtifactStatus.APPROVED
            await self._memory.artifacts.update(artifact)

    async def _resynchronise(self, request: ApprovalRequest) -> None:
        """Reopen the stages whose work has fallen out of date.

        Only stages that actually produced a stale artifact are reopened —
        selective regeneration, not rebuilding the project. An artifact whose
        upstream never moved is still valid and is left alone, which is the
        difference between propagating a change and starting over.
        """
        stale = await self._memory.traces.stale_edges(request.project_id)
        if not stale:
            return

        affected: set[LifecycleStage] = set()
        for entry in stale:
            artifact = await self._memory.artifacts.get(entry.edge.downstream_artifact_id)
            affected.add(artifact.stage)

        project = await self._memory.projects.get(request.project_id)
        project.stages = [
            state.model_copy(update={"status": StageStatus.PENDING, "completed_at": None})
            if state.stage in affected
            else state
            for state in project.stages
        ]
        await self._memory.projects.update(project)

        await self.publish(
            request.project_id,
            EventType.ARTIFACT_MARKED_STALE,
            f"Re-synchronising {len(affected)} stage(s) against the revised upstream",
            {
                "stages": sorted(stage.value for stage in affected),
                "stale_edges": len(stale),
            },
        )

        logger.info(
            "Re-synchronisation approved",
            extra={
                "project_id": request.project_id,
                "stages": sorted(stage.value for stage in affected),
            },
        )

    async def _reopen_producing_stages(self, request: ApprovalRequest) -> None:
        """Send the rejected work back to whoever produced it.

        Derived from the artifacts under review rather than declared on the
        request, so a gate covering several stages reopens all of them and
        neither the gate nor the reviewer has to know which.
        """
        project = await self._memory.projects.get(request.project_id)
        reopened: set[LifecycleStage] = set()

        for artifact_id in request.artifact_ids:
            artifact = await self._memory.artifacts.get(artifact_id)
            reopened.add(artifact.stage)

        if not reopened:
            return

        project.stages = [
            state.model_copy(update={"status": StageStatus.PENDING, "completed_at": None})
            if state.stage in reopened
            else state
            for state in project.stages
        ]
        await self._memory.projects.update(project)

        logger.info(
            "Stages reopened after rejection",
            extra={
                "project_id": request.project_id,
                "stages": sorted(stage.value for stage in reopened),
            },
        )

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

        # A stage gate protects what the *next* stage will consume; an
        # agent-requested gate reviews what that agent just *produced*. Showing
        # the reviewer the wrong set would make the decision meaningless.
        artifact_ids = (
            [
                artifact.id
                for artifact in snapshot.artifacts
                if artifact.stage is stage and artifact.has_content
            ]
            if gate in _AGENT_RAISED_GATES
            else gated_artifact_ids(stage, snapshot)
        )

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
