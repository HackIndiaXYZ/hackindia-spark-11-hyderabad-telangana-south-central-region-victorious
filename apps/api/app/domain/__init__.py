"""Pure domain layer — the innermost ring of the architecture.

Holds the vocabulary of the engineering organization: projects, lifecycle stages,
artifacts and their versions, traceability edges, agent runs, approvals, events,
and the errors that describe engineering failures.

This package must remain free of frameworks, I/O, and persistence. Anything here
can be exercised without a database, a network, or an event loop, which is what
makes the orchestration rules testable in isolation.

Enforced by ``tests/test_architecture.py``.
"""

from app.domain.agents import (
    AgentMessage,
    AgentRun,
    AgentRunStatus,
    TokenUsage,
)
from app.domain.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.domain.artifacts import (
    Artifact,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersion,
    ArtifactWithVersion,
)
from app.domain.errors import (
    ApprovalRequiredError,
    ConflictError,
    DependencyNotSatisfiedError,
    NotFoundError,
    ProviderError,
    ValidationError,
    VictoriousError,
)
from app.domain.events import EventType, ProjectEvent
from app.domain.ids import IdPrefix, is_id_of, new_id, prefix_of
from app.domain.lifecycle import (
    ROLE_TITLES,
    STAGE_OWNERS,
    STAGE_SEQUENCE,
    AgentRole,
    LifecycleStage,
    StageStatus,
    next_stage,
    preceding_stages,
    stage_index,
)
from app.domain.projects import Project, StageState
from app.domain.traceability import (
    ImpactAnalysis,
    ImpactedArtifact,
    StaleEdge,
    TraceEdge,
    TraceKind,
    analyse_impact,
    stale_artifact_ids,
    stale_edges,
    upstream_of,
)

__all__ = [
    "ROLE_TITLES",
    "STAGE_OWNERS",
    "STAGE_SEQUENCE",
    "AgentMessage",
    "AgentRole",
    "AgentRun",
    "AgentRunStatus",
    "ApprovalKind",
    "ApprovalRequest",
    "ApprovalRequiredError",
    "ApprovalStatus",
    "Artifact",
    "ArtifactStatus",
    "ArtifactType",
    "ArtifactVersion",
    "ArtifactWithVersion",
    "ConflictError",
    "DependencyNotSatisfiedError",
    "EventType",
    "IdPrefix",
    "ImpactAnalysis",
    "ImpactedArtifact",
    "LifecycleStage",
    "NotFoundError",
    "Project",
    "ProjectEvent",
    "ProviderError",
    "StageState",
    "StageStatus",
    "StaleEdge",
    "TokenUsage",
    "TraceEdge",
    "TraceKind",
    "ValidationError",
    "VictoriousError",
    "analyse_impact",
    "is_id_of",
    "new_id",
    "next_stage",
    "preceding_stages",
    "prefix_of",
    "stage_index",
    "stale_artifact_ids",
    "stale_edges",
    "upstream_of",
]
