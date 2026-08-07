"""Engineering lifecycle stages and the agent roles that own them.

The stage sequence is taken verbatim from the Project Lifecycle in
`09_MVP_Roadmap.md`. Encoding it as an ordered enum rather than free-form strings
means the orchestrator can answer "what comes next" and "is this stage ready"
from the model instead of from branching logic scattered across agents.
"""

from __future__ import annotations

from enum import StrEnum


class LifecycleStage(StrEnum):
    """The nine engineering stages a project moves through.

    Declaration order is execution order; ``STAGE_SEQUENCE`` below depends on it.
    """

    IDEA = "idea"
    REQUIREMENT_DISCOVERY = "requirement_discovery"
    BUSINESS_VALIDATION = "business_validation"
    ARCHITECTURE = "architecture"
    DEVELOPMENT_PLANNING = "development_planning"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEPLOYMENT_PREPARATION = "deployment_preparation"


STAGE_SEQUENCE: tuple[LifecycleStage, ...] = tuple(LifecycleStage)


class AgentRole(StrEnum):
    """The MVP engineering organization.

    Exactly the roster in `09_MVP_Roadmap.md`, `11_Future_Roadmap.md`, and
    `14_Executive_Summary.md`. The Full Stack Engineer stands in for the separate
    Frontend, Backend, and Database agents of `05_AI_Agent_Architecture.md` — an
    explicit MVP simplification, not an architectural one; each becomes its own
    role in V2 by adding members here and prompts in ``app/agents/prompts``.
    """

    EXECUTIVE = "executive"
    PRODUCT_MANAGER = "product_manager"
    BUSINESS_ANALYST = "business_analyst"
    SOFTWARE_ARCHITECT = "software_architect"
    FULL_STACK_ENGINEER = "full_stack_engineer"
    QA_ENGINEER = "qa_engineer"
    DOCUMENTATION = "documentation"


#: Human-facing titles. Held here so the API, the Agent Organization view, and
#: generated documentation all name a role identically.
ROLE_TITLES: dict[AgentRole, str] = {
    AgentRole.EXECUTIVE: "Executive AI (Engineering Director)",
    AgentRole.PRODUCT_MANAGER: "Product Manager",
    AgentRole.BUSINESS_ANALYST: "Business Analyst",
    AgentRole.SOFTWARE_ARCHITECT: "Software Architect",
    AgentRole.FULL_STACK_ENGINEER: "Full Stack Engineer",
    AgentRole.QA_ENGINEER: "QA Engineer",
    AgentRole.DOCUMENTATION: "Documentation Engineer",
}

#: Which role performs the engineering work of each stage.
#:
#: The Executive AI is deliberately absent: `15_Development_Guidelines.md` states
#: it "coordinates engineering activities but does not directly perform
#: engineering work". Its absence here is what keeps that true structurally.
STAGE_OWNERS: dict[LifecycleStage, AgentRole] = {
    LifecycleStage.REQUIREMENT_DISCOVERY: AgentRole.PRODUCT_MANAGER,
    LifecycleStage.BUSINESS_VALIDATION: AgentRole.BUSINESS_ANALYST,
    LifecycleStage.ARCHITECTURE: AgentRole.SOFTWARE_ARCHITECT,
    LifecycleStage.DEVELOPMENT_PLANNING: AgentRole.SOFTWARE_ARCHITECT,
    LifecycleStage.IMPLEMENTATION: AgentRole.FULL_STACK_ENGINEER,
    LifecycleStage.TESTING: AgentRole.QA_ENGINEER,
    LifecycleStage.DOCUMENTATION: AgentRole.DOCUMENTATION,
    LifecycleStage.DEPLOYMENT_PREPARATION: AgentRole.DOCUMENTATION,
}


class StageStatus(StrEnum):
    """Progress of one stage within a project."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    BLOCKED = "blocked"


def stage_index(stage: LifecycleStage) -> int:
    """Return the ordinal position of a stage in the lifecycle."""
    return STAGE_SEQUENCE.index(stage)


def next_stage(stage: LifecycleStage) -> LifecycleStage | None:
    """Return the stage following ``stage``, or ``None`` at the end."""
    index = stage_index(stage) + 1
    return STAGE_SEQUENCE[index] if index < len(STAGE_SEQUENCE) else None


def preceding_stages(stage: LifecycleStage) -> tuple[LifecycleStage, ...]:
    """Return every stage that must complete before ``stage`` may run.

    The orchestrator uses this to refuse an agent invocation whose upstream
    context is incomplete, rather than letting it reason over a partial project.
    """
    return STAGE_SEQUENCE[: stage_index(stage)]
