"""Shared organizational memory — the single source of truth.

Every engineering agent reads and writes project knowledge through this layer.
Consumers depend on the protocols in ``repository.py``; the SQL implementation is
bound in the composition root.
"""

from app.memory.context_builder import (
    CHARS_PER_TOKEN,
    DEFAULT_TOKEN_BUDGET,
    ContextBuilder,
    ContextEntry,
    ProjectContext,
)
from app.memory.health import DatabaseHealthCheck
from app.memory.repository import (
    AgentRunRepository,
    ApprovalRepository,
    ArtifactRepository,
    EventRepository,
    ProjectRepository,
    SharedMemory,
    TraceRepository,
)
from app.memory.sql_repository import SqlSharedMemory

__all__ = [
    "CHARS_PER_TOKEN",
    "DEFAULT_TOKEN_BUDGET",
    "AgentRunRepository",
    "ApprovalRepository",
    "ArtifactRepository",
    "ContextBuilder",
    "ContextEntry",
    "DatabaseHealthCheck",
    "EventRepository",
    "ProjectContext",
    "ProjectRepository",
    "SharedMemory",
    "SqlSharedMemory",
    "TraceRepository",
]
