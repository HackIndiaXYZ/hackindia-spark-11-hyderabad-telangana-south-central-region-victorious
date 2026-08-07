"""Reasoning provider abstraction.

Agents depend on :class:`LLMProvider`; the composition root chooses the adapter.
No module outside this package imports a vendor SDK (ADR-0004).
"""

from app.llm.fixture_provider import FixtureProvider, fixture_name
from app.llm.provider import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    Message,
    Role,
    StructuredResponse,
)
from app.llm.recording import RecordingProvider
from app.llm.registry import ProviderHealthCheck, build_provider
from app.llm.retry import SchemaViolationError, TransientProviderError, with_retries

__all__ = [
    "CompletionRequest",
    "CompletionResponse",
    "FixtureProvider",
    "LLMProvider",
    "Message",
    "ProviderHealthCheck",
    "RecordingProvider",
    "Role",
    "SchemaViolationError",
    "StructuredResponse",
    "TransientProviderError",
    "build_provider",
    "fixture_name",
    "with_retries",
]
