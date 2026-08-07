"""Public entry point for advancing a project's engineering workflow.

One traversal runs until the organization can make no further progress without a
human: an approval gate, a blocking conflict, a stage nobody owns, or completion.

Resumption is simply calling :meth:`OrchestrationRunner.advance` again. Because
every node reads current facts from shared memory rather than from accumulated
graph state, a traversal that begins after an approval is granted sees the new
decision immediately — and works across process restarts, which an in-memory
checkpointer would not. See ADR-0009.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.domain.errors import NotFoundError
from app.domain.lifecycle import LifecycleStage
from app.events.bus import EventBus
from app.llm.provider import LLMProvider
from app.memory.repository import SharedMemory
from app.orchestration.dispatcher import AgentDispatcher
from app.orchestration.executive import CoordinationAction, ExecutiveAI
from app.orchestration.graph import build_workflow
from app.orchestration.state import RECURSION_LIMIT, OrchestrationState

logger = get_logger(__name__)


@dataclass(frozen=True)
class OrchestrationOutcome:
    """The result of one traversal."""

    project_id: str
    executed_stages: list[LifecycleStage] = field(default_factory=list)
    halt_action: CoordinationAction | None = None
    halt_reason: str = ""
    pending_approval_id: str | None = None
    conflicts: list[dict[str, object]] = field(default_factory=list)
    error: str | None = None

    @property
    def awaiting_approval(self) -> bool:
        return self.halt_action is CoordinationAction.AWAIT_APPROVAL

    @property
    def is_complete(self) -> bool:
        return self.halt_action is CoordinationAction.COMPLETE

    @property
    def is_blocked(self) -> bool:
        return self.halt_action is CoordinationAction.HALT_BLOCKED

    @property
    def made_progress(self) -> bool:
        return bool(self.executed_stages)


class OrchestrationRunner:
    """Drives the engineering workflow for a project."""

    def __init__(
        self,
        memory: SharedMemory,
        provider: LLMProvider,
        events: EventBus,
        dispatcher: AgentDispatcher,
    ) -> None:
        self._memory = memory
        self._executive = ExecutiveAI(memory, provider, events)
        self._dispatcher = dispatcher
        # Compiled once: the graph's shape is fixed, and rebuilding it per
        # request would pay compilation cost on every advance.
        self._workflow = build_workflow(self._executive, dispatcher)

    @property
    def executive(self) -> ExecutiveAI:
        """The Executive AI, exposed for direct assessment without a traversal."""
        return self._executive

    async def advance(self, project_id: str) -> OrchestrationOutcome:
        """Advance the project as far as it can go without a human.

        Args:
            project_id: Project to advance.

        Returns:
            What was executed and why it stopped.

        Raises:
            NotFoundError: if the project does not exist.
        """
        if not await self._memory.projects.exists(project_id):
            raise NotFoundError("Project not found", details={"project_id": project_id})

        initial: OrchestrationState = {
            "project_id": project_id,
            "next_action": None,
            "stage": None,
            "gate": None,
            "executed_stages": [],
            "halted": False,
            "halt_action": None,
            "halt_reason": None,
            "pending_approval_id": None,
            "conflicts": [],
            "error": None,
        }

        final: OrchestrationState = await self._workflow.ainvoke(
            initial, config={"recursion_limit": RECURSION_LIMIT}
        )

        halt_action = final.get("halt_action")

        outcome = OrchestrationOutcome(
            project_id=project_id,
            executed_stages=[
                LifecycleStage(stage) for stage in final.get("executed_stages", [])
            ],
            halt_action=CoordinationAction(halt_action) if halt_action else None,
            halt_reason=final.get("halt_reason") or "",
            pending_approval_id=final.get("pending_approval_id"),
            conflicts=final.get("conflicts", []),
            error=final.get("error"),
        )

        logger.info(
            "Orchestration traversal finished",
            extra={
                "project_id": project_id,
                "executed": [stage.value for stage in outcome.executed_stages],
                "halt_action": outcome.halt_action.value if outcome.halt_action else None,
                "conflicts": len(outcome.conflicts),
            },
        )
        return outcome
