"""The AI engineering organization.

One module per engineering role, each a subclass of :class:`BaseAgent`. The
concrete agents arrive in Milestone 4; this package currently provides the
framework they are built on.
"""

from app.agents.base import BaseAgent
from app.agents.contracts import (
    AgentOutput,
    AgentResult,
    ArtifactDraft,
    TraceLink,
)
from app.agents.prompts import PromptError, available_prompts, load_prompt, render_prompt

__all__ = [
    "AgentOutput",
    "AgentResult",
    "ArtifactDraft",
    "BaseAgent",
    "PromptError",
    "TraceLink",
    "available_prompts",
    "load_prompt",
    "render_prompt",
]
