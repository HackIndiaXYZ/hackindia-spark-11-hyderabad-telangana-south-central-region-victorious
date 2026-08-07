"""Reasoning provider abstraction.

`15_Development_Guidelines.md` requires the platform to stay AI-provider agnostic
and warns against coupling implementation to a single language model.
`12_Risk_Analysis.md` rates Model Availability a Medium risk mitigated by a
provider abstraction layer and multiple providers.

This module is that layer. No agent imports a vendor SDK; every agent depends on
:class:`LLMProvider`, and the composition root decides which adapter backs it
(ADR-0004).

The interface is deliberately narrow. Agents need text generation and validated
structured output — nothing exotic — and a wide interface would only constrain
which providers can implement it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.domain.agents import TokenUsage


class Role(StrEnum):
    """Conversation roles common to every supported provider."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """One turn of a conversation."""

    role: Role
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    """A request for reasoning.

    ``fixture_key`` is carried on the request rather than derived inside the
    fixture provider so recorded responses have stable, human-readable filenames
    (``product_manager.requirement_discovery.json``) that a reviewer can open,
    read, and edit. A content hash would make the demo fixtures opaque.
    """

    system: str
    messages: list[Message]
    max_tokens: int = 8192
    temperature: float = 0.2
    fixture_key: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CompletionResponse:
    """Free-text reasoning output."""

    text: str
    usage: TokenUsage
    model: str
    provider: str


@dataclass(frozen=True)
class StructuredResponse[T: BaseModel]:
    """Reasoning output validated against an agent's output contract."""

    value: T
    raw_json: str
    usage: TokenUsage
    model: str
    provider: str


@runtime_checkable
class LLMProvider(Protocol):
    """A reasoning backend.

    Implementations must translate vendor failures into
    :class:`app.domain.errors.ProviderError`, so retry, fallback, and degradation
    policy stay inside the platform rather than leaking a vendor exception into
    orchestration code.
    """

    @property
    def name(self) -> str:
        """Stable provider identifier, recorded on every agent run."""
        ...

    @property
    def model(self) -> str:
        """Model identifier, recorded on every agent run."""
        ...

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate free-text output."""
        ...

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        """Generate output validated against ``schema``.

        The path every agent uses. Downstream agents read structured content
        rather than parsing prose, so a provider that cannot reliably produce
        valid instances of a schema is not usable here — which is why ADR-0004
        makes structured-output reliability the criterion for the default.

        Raises:
            ProviderError: on transport failure, or when output cannot be
                validated against the schema after retries.
        """
        ...

    # Declared without `async` deliberately: implementations are async
    # generators, whose type is a callable returning an AsyncIterator rather than
    # a coroutine that resolves to one. Marking this `async def` would make every
    # real adapter fail the protocol check.
    def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield output incrementally.

        Used by Milestone 6 to surface agent reasoning as it is produced rather
        than after completion, which `10_UI_UX_Plan.md` requires instead of
        hiding agents behind loading indicators.
        """
        ...

    async def aclose(self) -> None:
        """Release any underlying client. Invoked by the container on shutdown."""
        ...
