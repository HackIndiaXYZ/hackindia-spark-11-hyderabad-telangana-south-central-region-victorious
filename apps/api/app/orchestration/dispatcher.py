"""Agent dispatch.

The Executive AI routes work to specialists without knowing how any of them are
built. `05_AI_Agent_Architecture.md` requires agents to be "independent, reusable
module[s]" that do not modify each other's state; this protocol is the seam that
keeps orchestration and implementation apart.

It also means Milestone 3 is fully testable before Milestone 4 exists: the graph
depends on this protocol, and tests supply stubs where the real organization will
later be registered.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.agents.contracts import AgentResult
from app.core.logging import get_logger
from app.domain.errors import DependencyNotSatisfiedError
from app.domain.lifecycle import STAGE_OWNERS, AgentRole, LifecycleStage

logger = get_logger(__name__)


@runtime_checkable
class AgentDispatcher(Protocol):
    """Routes a stage's work to the agent that owns it."""

    def owns(self, stage: LifecycleStage) -> bool:
        """Whether an agent is registered for this stage."""
        ...

    async def dispatch(
        self, stage: LifecycleStage, project_id: str, *, feedback: str | None = None
    ) -> AgentResult:
        """Run the agent that owns ``stage``.

        Args:
            stage: Stage to execute.
            project_id: Project being worked on.
            feedback: Reviewer feedback from a rejected approval, passed through
                so a rejection teaches rather than repeats.

        Raises:
            DependencyNotSatisfiedError: if no agent owns the stage.
        """
        ...


class RegistryDispatcher:
    """Dispatches to agents registered by the stage they perform.

    Keyed by stage rather than role because a role can own more than one stage:
    the Software Architect performs both architecture and development planning,
    and the Documentation agent both documentation and deployment preparation.
    Keying by role would dispatch development planning to the architecture agent,
    which would then write its artifacts tagged with the wrong stage.

    Agents are registered whole rather than under a supplied key, and the
    registration is validated against :data:`app.domain.lifecycle.STAGE_OWNERS`.
    That keeps one answer to "who owns this stage" — the domain's — and makes a
    mis-registration impossible rather than merely unlikely.
    """

    def __init__(self) -> None:
        self._agents: dict[LifecycleStage, _Runnable] = {}

    def register(self, agent: _Runnable) -> None:
        """Register an agent for the stage it declares.

        Raises:
            ValueError: if the stage is already filled, or if the agent's role
                disagrees with the domain's owner for that stage.
        """
        stage = agent.stage
        role = agent.role

        if stage in self._agents:
            raise ValueError(f"An agent is already registered for stage {stage.value}")

        expected = STAGE_OWNERS.get(stage)
        if expected is None:
            raise ValueError(f"No engineering role owns stage {stage.value}")

        if role is not expected:
            raise ValueError(
                f"{type(agent).__name__} declares role {role.value}, but "
                f"{stage.value} is owned by {expected.value}"
            )

        self._agents[stage] = agent
        logger.debug(
            "Agent registered", extra={"stage": stage.value, "role": role.value}
        )

    def owns(self, stage: LifecycleStage) -> bool:
        return stage in self._agents

    async def dispatch(
        self, stage: LifecycleStage, project_id: str, *, feedback: str | None = None
    ) -> AgentResult:
        agent = self._agents.get(stage)

        if agent is None:
            raise DependencyNotSatisfiedError(
                "No agent is registered to perform this stage",
                details={
                    "stage": stage.value,
                    "role": (owner.value if (owner := STAGE_OWNERS.get(stage)) else None),
                },
            )

        return await agent.run(project_id, feedback=feedback)

    @property
    def registered_stages(self) -> list[LifecycleStage]:
        """Stages currently covered, for diagnostics."""
        return sorted(self._agents, key=lambda stage: stage.value)

    @property
    def registered_roles(self) -> list[AgentRole]:
        """Distinct roles currently filled, for the Organization view."""
        return sorted({agent.role for agent in self._agents.values()})


@runtime_checkable
class _Runnable(Protocol):
    """What the dispatcher needs from an agent: its identity and one method.

    Narrower than :class:`app.agents.base.BaseAgent` on purpose. The dispatcher
    depends on the capability it uses, not on the base class, so a differently
    implemented agent remains dispatchable.
    """

    @property
    def role(self) -> AgentRole: ...

    @property
    def stage(self) -> LifecycleStage: ...

    async def run(self, project_id: str, *, feedback: str | None = None) -> AgentResult: ...
