"""Engineering workflow orchestration.

The Executive AI (Engineering Director) and the workflow graph it drives. This
layer coordinates the organization; it performs no engineering work of its own
(`15_Development_Guidelines.md`).
"""

from app.orchestration.conflicts import (
    LOW_CONFIDENCE_THRESHOLD,
    Conflict,
    ConflictKind,
    ConflictSeverity,
    blocking,
    detect_conflicts,
)
from app.orchestration.dependencies import (
    STAGE_GATES,
    STAGE_INPUTS,
    ProjectSnapshot,
    Readiness,
    ReadinessStatus,
    evaluate_readiness,
)
from app.orchestration.dispatcher import AgentDispatcher, RegistryDispatcher
from app.orchestration.executive import (
    ApprovalNarration,
    CoordinationAction,
    CoordinationDecision,
    ExecutiveAI,
)
from app.orchestration.graph import build_workflow
from app.orchestration.runner import OrchestrationOutcome, OrchestrationRunner

__all__ = [
    "LOW_CONFIDENCE_THRESHOLD",
    "STAGE_GATES",
    "STAGE_INPUTS",
    "AgentDispatcher",
    "ApprovalNarration",
    "Conflict",
    "ConflictKind",
    "ConflictSeverity",
    "CoordinationAction",
    "CoordinationDecision",
    "ExecutiveAI",
    "OrchestrationOutcome",
    "OrchestrationRunner",
    "ProjectSnapshot",
    "Readiness",
    "ReadinessStatus",
    "RegistryDispatcher",
    "blocking",
    "build_workflow",
    "detect_conflicts",
    "evaluate_readiness",
]
