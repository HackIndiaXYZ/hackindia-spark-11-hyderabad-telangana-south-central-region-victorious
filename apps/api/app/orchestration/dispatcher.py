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
    """Dispatches to agents registered by role.

    Registration is keyed by role rather than stage, and the stage-to-role
    mapping comes from :data:`app.domain.lifecycle.STAGE_OWNERS`. That keeps a
    single answer to "who owns this stage" — the domain's — rather than letting
    the orchestrator hold a second, divergent opinion.
    """

    def __init__(self) -> None:
        self._agents: dict[AgentRole, _Runnable] = {}

    def register(self, role: AgentRole, agent: _Runnable) -> None:
        """Register the agent filling a role.

        Raises:
            ValueError: if the role is already filled. Two agents for one role
                would make dispatch order decide which engineering opinion wins.
        """
        if role in self._agents:
            raise ValueError(f"An agent is already registered for role {role.value}")

        self._agents[role] = agent
        logger.debug("Agent registered", extra={"role": role.value})

    def owns(self, stage: LifecycleStage) -> bool:
        role = STAGE_OWNERS.get(stage)
        return role is not None and role in self._agents

    async def dispatch(
        self, stage: LifecycleStage, project_id: str, *, feedback: str | None = None
    ) -> AgentResult:
        role = STAGE_OWNERS.get(stage)

        if role is None:
            raise DependencyNotSatisfiedError(
                "No engineering role owns this stage",
                details={"stage": stage.value},
            )

        agent = self._agents.get(role)
        if agent is None:
            raise DependencyNotSatisfiedError(
                "No agent is registered for the role that owns this stage",
                details={"stage": stage.value, "role": role.value},
            )

        return await agent.run(project_id, feedback=feedback)

    @property
    def registered_roles(self) -> list[AgentRole]:
        """Roles currently filled, for diagnostics and the Organization view."""
        return sorted(self._agents)


@runtime_checkable
class _Runnable(Protocol):
    """The single method the dispatcher needs from an agent.

    Narrower than :class:`app.agents.base.BaseAgent` on purpose: the dispatcher
    depends on the capability it uses, not on the base class, so a differently
    implemented agent remains dispatchable.
    """

    async def run(self, project_id: str, *, feedback: str | None = None) -> AgentResult: ...
