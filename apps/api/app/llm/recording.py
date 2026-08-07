"""Fixture recorder.

Wraps a live provider and writes every response to disk in the format
:mod:`app.llm.fixture_provider` replays. Recording once against a real provider
is what makes the offline demo possible.

A decorator rather than a flag inside each adapter: recording is orthogonal to
which provider is in use, and putting it here means both adapters — and any
future one — gain it for free.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic import BaseModel

from app.core.logging import get_logger
from app.llm.fixture_provider import fixture_name
from app.llm.provider import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    StructuredResponse,
)

logger = get_logger(__name__)


class RecordingProvider:
    """Delegates to a real provider and records what it returns."""

    def __init__(self, inner: LLMProvider, fixture_dir: str | Path) -> None:
        self._inner = inner
        self._dir = Path(fixture_dir)

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def model(self) -> str:
        return self._inner.model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        response = await self._inner.complete(request)
        self._write(
            request,
            {
                "text": response.text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "recorded_from": {"provider": response.provider, "model": response.model},
            },
        )
        return response

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        response = await self._inner.complete_structured(request, schema)
        self._write(
            request,
            {
                "value": response.value.model_dump(mode="json"),
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "recorded_from": {
                    "provider": response.provider,
                    "model": response.model,
                    "schema": schema.__name__,
                },
            },
        )
        return response

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Pass streaming through, accumulating the text to record on completion."""
        chunks: list[str] = []

        async for chunk in self._inner.stream(request):
            chunks.append(chunk)
            yield chunk

        self._write(request, {"text": "".join(chunks), "recorded_from": {"stream": True}})

    async def aclose(self) -> None:
        await self._inner.aclose()

    def _write(self, request: CompletionRequest, payload: dict[str, object]) -> None:
        """Write a fixture.

        Recording must never break the call it is observing: a read-only
        directory or a full disk is a recording problem, not an engineering one,
        so failures are logged and swallowed.
        """
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path = self._dir / f"{fixture_name(request)}.json"
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            logger.info("Recorded fixture", extra={"fixture": path.name})
        except OSError:
            logger.exception("Failed to record fixture", extra={"directory": str(self._dir)})
