"""Assembles the AI engineering organization.

One place lists every agent the platform employs. Adding a specialist — the
dedicated Frontend, Backend, Database, Security, and DevOps agents that
`11_Future_Roadmap.md` places in V2 — means adding a class here and an entry in
:data:`app.domain.lifecycle.STAGE_OWNERS`. Nothing else changes, which is the
extensibility `05_AI_Agent_Architecture.md` requires.

Eight agents fill seven roles: the Software Architect performs both architecture
and development planning, and the Documentation Engineer both documentation and
deployment preparation. See ADR-0010.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.business_analyst import BusinessAnalystAgent
from app.agents.documentation import DeploymentPreparationAgent, DocumentationAgent
from app.agents.full_stack_engineer import FullStackEngineerAgent
from app.agents.product_manager import ProductManagerAgent
from app.agents.qa_engineer import QAEngineerAgent
from app.agents.software_architect import (
    ImplementationPlannerAgent,
    SoftwareArchitectAgent,
)
from app.core.logging import get_logger
from app.events.bus import EventBus
from app.llm.provider import LLMProvider
from app.memory.context_builder import ContextBuilder
from app.memory.repository import SharedMemory
from app.review.reviewer import EngineeringReviewer

logger = get_logger(__name__)

#: Every agent class the MVP organization employs, in lifecycle order.
AGENT_CLASSES: tuple[type[BaseAgent], ...] = (  # type: ignore[type-arg]
    ProductManagerAgent,
    BusinessAnalystAgent,
    SoftwareArchitectAgent,
    ImplementationPlannerAgent,
    FullStackEngineerAgent,
    QAEngineerAgent,
    DocumentationAgent,
    DeploymentPreparationAgent,
)


def build_organization(
    memory: SharedMemory,
    provider: LLMProvider,
    context_builder: ContextBuilder,
    events: EventBus,
    reviewer: EngineeringReviewer | None = None,
) -> list[BaseAgent]:  # type: ignore[type-arg]
    """Instantiate every agent with its collaborators.

    Agents receive shared memory, a reasoning provider, a context builder, and
    the event bus — and nothing else. In particular, no agent receives another
    agent: `05_AI_Agent_Architecture.md` requires that agents "avoid directly
    modifying each other's internal state", and the only way they can influence
    one another is by writing artifacts a later agent reads from shared memory.
    """
    agents = [
        agent_class(memory, provider, context_builder, events, reviewer)
        for agent_class in AGENT_CLASSES
    ]

    logger.info(
        "Engineering organization assembled",
        extra={
            "agents": len(agents),
            "roles": sorted({agent.role.value for agent in agents}),
        },
    )
    return agents
