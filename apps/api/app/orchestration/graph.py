"""The engineering workflow graph.

`08_Technology_Stack.md` specifies LangGraph as the agent workflow engine. It is
used here for what it is good at — declarative nodes, conditional routing, and a
compiled executable graph — and deliberately *not* for checkpointing. Persisting
workflow state in a checkpointer would create a second source of truth about
where a project stands, contradicting `15_Development_Guidelines.md` and creating
exactly the Context Drift risk `12_Risk_Analysis.md` warns about. See ADR-0009.

The graph is a loop:

    START ──► coordinate ──► execute ──┐
                  │                    │
                  ├──► gate ──► END    │
                  │                    │
                  └──► END             │
                  ▲                    │
                  └────────────────────┘

Only ``coordinate`` decides anything — it is the Executive AI. ``execute`` and
``gate`` each carry out exactly one instruction and route nowhere of their own
accord. That asymmetry is the structural form of
`15_Development_Guidelines.md`'s rule that the Executive coordinates while
specialists perform.
"""

from __future__ import annotations

from typing import Final, Literal

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.domain.approvals import ApprovalKind
from app.domain.events import EventType
from app.domain.lifecycle import LifecycleStage, StageStatus
from app.orchestration.dispatcher import AgentDispatcher
from app.orchestration.executive import CoordinationAction, ExecutiveAI
from app.orchestration.state import OrchestrationState

logger = get_logger(__name__)

COORDINATE: Final = "coordinate"
EXECUTE: Final = "execute"
GATE: Final = "gate"

#: LangGraph's terminal node name. Bound to a Final so the routing functions can
#: declare precise Literal return types.
TERMINAL: Final = "__end__"


def build_workflow(executive: ExecutiveAI, dispatcher: AgentDispatcher):  # type: ignore[no-untyped-def]
    """Compile the engineering workflow.

    Args:
        executive: Coordinates the organization.
        dispatcher: Routes stage work to the agent that owns it.

    Returns:
        A compiled LangGraph application, invoked via ``ainvoke``.
    """

    async def coordinate(state: OrchestrationState) -> OrchestrationState:
        """Ask the Executive AI what happens next, and record the decision.

        The only node that decides. It also performs the Executive's own routing
        responsibility — publishing the structured assignment that
        `05_AI_Agent_Architecture.md` requires — so the specialist nodes receive
        an instruction rather than deriving one.
        """
        project_id = state["project_id"]
        decision = await executive.assess(project_id)

        conflicts = [conflict.model_dump(mode="json") for conflict in decision.conflicts]
        stage_value = decision.stage.value if decision.stage else None

        await executive.publish(
            project_id,
            EventType.STAGE_BLOCKED if decision.halts else EventType.STAGE_STARTED,
            f"{executive.title}: {decision.rationale}",
            {
                "action": decision.action.value,
                "stage": stage_value,
                "role": decision.role.value if decision.role else None,
                "conflicts": len(conflicts),
            },
            stage=decision.stage,
        )

        base: OrchestrationState = {
            **state,
            "next_action": decision.action.value,
            "stage": stage_value,
            "conflicts": conflicts,
        }

        if decision.action is CoordinationAction.EXECUTE_STAGE:
            assignment = executive.assignment_for(decision, [])
            await executive.publish(
                project_id,
                EventType.AGENT_PROGRESS,
                (
                    f"{executive.title} assigned "
                    f"{assignment.task.rstrip('.')} to "
                    f"{assignment.receiver.value.replace('_', ' ')}"
                ),
                {"assignment": assignment.model_dump(mode="json")},
                stage=decision.stage,
            )
            return base

        if decision.action is CoordinationAction.REQUEST_APPROVAL:
            return {**base, "gate": decision.gate.value if decision.gate else None}

        return {
            **base,
            "halted": True,
            "halt_action": decision.action.value,
            "halt_reason": decision.rationale,
            "pending_approval_id": decision.approval_id,
        }

    async def execute(state: OrchestrationState) -> OrchestrationState:
        """Dispatch the assigned stage to the agent that owns it."""
        project_id = state["project_id"]
        raw_stage = state.get("stage")

        if raw_stage is None:
            return {
                **state,
                "halted": True,
                "halt_action": CoordinationAction.HALT_BLOCKED.value,
                "halt_reason": "No stage was assigned",
            }

        stage = LifecycleStage(raw_stage)

        if not dispatcher.owns(stage):
            await executive.mark_stage(project_id, stage, StageStatus.BLOCKED)
            return {
                **state,
                "halted": True,
                "halt_action": CoordinationAction.HALT_BLOCKED.value,
                "halt_reason": f"No agent is registered to perform {stage.value}",
            }

        await executive.mark_stage(project_id, stage, StageStatus.IN_PROGRESS)
        feedback = await executive.rejection_feedback_for(project_id, stage)

        try:
            await dispatcher.dispatch(stage, project_id, feedback=feedback)
        # Broad by design: any agent failure must halt this traversal gracefully
        # rather than propagate. `12_Risk_Analysis.md` requires the system to fail
        # gracefully and recover predictably, and the next `advance` call retries.
        except Exception as exc:  # noqa: BLE001
            # The agent has already recorded its own failure and published an
            # event. The graph's job here is to stop, not to re-report.
            await executive.mark_stage(project_id, stage, StageStatus.BLOCKED)
            logger.warning(
                "Stage execution failed",
                extra={"project_id": project_id, "stage": stage.value},
            )
            return {
                **state,
                "halted": True,
                "halt_action": CoordinationAction.HALT_BLOCKED.value,
                "halt_reason": f"{stage.value} failed: {type(exc).__name__}",
                "error": f"{type(exc).__name__}: {exc}",
            }

        await executive.mark_stage(project_id, stage, StageStatus.COMPLETED)
        await executive.publish(
            project_id,
            EventType.STAGE_COMPLETED,
            f"{stage.value.replace('_', ' ').title()} completed",
            {"stage": stage.value},
            stage=stage,
        )

        return {
            **state,
            "executed_stages": [*state.get("executed_stages", []), stage.value],
        }

    async def gate(state: OrchestrationState) -> OrchestrationState:
        """Raise the approval request blocking this stage, then stop.

        The traversal genuinely ends here. `12_Risk_Analysis.md` mitigates
        Excessive Automation with "human approval checkpoints"; a gate that
        notified the user while work continued would not be one.
        """
        project_id = state["project_id"]
        raw_stage = state.get("stage")
        raw_gate = state.get("gate")

        if raw_stage is None or raw_gate is None:
            return {
                **state,
                "halted": True,
                "halt_action": CoordinationAction.HALT_BLOCKED.value,
                "halt_reason": "Approval was required but no gate was identified",
            }

        stage = LifecycleStage(raw_stage)
        request = await executive.raise_gate(project_id, stage, ApprovalKind(raw_gate))

        # Only a stage that has not run yet is "awaiting approval". A gate an
        # agent raised about work it just finished must not un-complete that
        # stage, or the specialist would be dispatched again once the gate
        # cleared — doing the same work twice.
        project = await executive.project_state(project_id)
        stage_state = project.stage_state(stage)
        if stage_state is None or stage_state.status is not StageStatus.COMPLETED:
            await executive.mark_stage(project_id, stage, StageStatus.AWAITING_APPROVAL)

        return {
            **state,
            "halted": True,
            "halt_action": CoordinationAction.AWAIT_APPROVAL.value,
            "halt_reason": f"Awaiting human approval: {request.title}",
            "pending_approval_id": request.id,
        }

    def route_after_coordinate(
        state: OrchestrationState,
    ) -> Literal["execute", "gate", "__end__"]:
        """Route on the Executive's recorded decision.

        Reads one field rather than inferring intent from several, so a new
        coordination action cannot accidentally fall through to execution.
        """
        match state.get("next_action"):
            case CoordinationAction.EXECUTE_STAGE.value:
                return EXECUTE
            case CoordinationAction.REQUEST_APPROVAL.value:
                return GATE
            case _:
                return TERMINAL

    def route_after_execute(state: OrchestrationState) -> Literal["coordinate", "__end__"]:
        """Return to coordination unless execution halted the traversal.

        Without this check the edge back to ``coordinate`` is unconditional, and a
        stage that fails — or that no agent owns — is re-dispatched forever: the
        Executive would correctly re-assess it as ready, dispatch it, watch it
        fail, and loop until the recursion limit. Execution must be able to stop
        the traversal, and this is the only place it can.
        """
        return TERMINAL if state.get("halted") else COORDINATE

    graph = StateGraph(OrchestrationState)
    graph.add_node(COORDINATE, coordinate)
    graph.add_node(EXECUTE, execute)
    graph.add_node(GATE, gate)

    graph.add_edge(START, COORDINATE)
    graph.add_conditional_edges(
        COORDINATE, route_after_coordinate, {EXECUTE: EXECUTE, GATE: GATE, END: END}
    )
    # A successful stage returns to coordination. That loop is what makes this a
    # workflow rather than a fixed pipeline: the Executive re-assesses after every
    # unit of work, so a change made mid-run is seen on the next pass.
    graph.add_conditional_edges(
        EXECUTE, route_after_execute, {COORDINATE: COORDINATE, END: END}
    )
    graph.add_edge(GATE, END)

    return graph.compile()
