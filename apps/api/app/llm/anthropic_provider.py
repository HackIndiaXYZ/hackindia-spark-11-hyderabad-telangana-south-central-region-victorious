"""Anthropic (Claude) reasoning adapter — the default provider per ADR-0004.

Structured output uses forced tool use rather than asking for JSON in the prompt.
The model is given a single tool whose input schema is the agent's output
contract and is required to call it, so the API constrains generation to the
schema instead of the platform hoping prose happens to parse. That reliability is
the reason ADR-0004 makes this the default: an agent returning malformed output
does not degrade gracefully, it halts a lifecycle stage.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.config import LLMSettings
from app.core.logging import get_logger
from app.domain.agents import TokenUsage
from app.domain.errors import ProviderError
from app.llm.provider import (
    CompletionRequest,
    CompletionResponse,
    Message,
    Role,
    StructuredResponse,
)
from app.llm.retry import SchemaViolationError, TransientProviderError, with_retries

logger = get_logger(__name__)

_STRUCTURED_TOOL_NAME = "emit_engineering_output"

#: Vendor exception names worth retrying unchanged. Anything else — bad request,
#: authentication failure — fails identically on retry and is raised at once.
_TRANSIENT_ERRORS = frozenset(
    {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "InternalServerError",
        "APIStatusError",
    }
)


class AnthropicProvider:
    """Reasoning backed by the Anthropic Messages API."""

    def __init__(self, settings: LLMSettings) -> None:
        if not settings.anthropic_api_key:
            raise ProviderError(
                "Anthropic provider selected but no API key is configured",
                details={"env_var": "ANTHROPIC_API_KEY"},
            )

        # Imported lazily so the SDK is only required when this provider is
        # actually selected — the fixture provider must work with no vendor SDK
        # installed at all.
        from anthropic import AsyncAnthropic

        self._settings = settings
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.timeout_seconds,
            max_retries=0,  # Retry policy is ours (app/llm/retry.py), not the SDK's.
        )

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._settings.anthropic_model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        async def attempt(_: int) -> CompletionResponse:
            message = await self._send(request)
            text = "".join(
                block.text
                for block in message.content
                if getattr(block, "type", None) == "text"
            )
            return CompletionResponse(
                text=text,
                usage=_usage_of(message),
                model=self.model,
                provider=self.name,
            )

        return await with_retries(
            attempt,
            max_retries=self._settings.max_retries,
            description="anthropic.complete",
        )

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        tool: dict[str, Any] = {
            "name": _STRUCTURED_TOOL_NAME,
            "description": "Emit the engineering output for this task. Every field is required.",
            "input_schema": schema.model_json_schema(),
        }

        # Held in the closure rather than on the instance: a provider is a
        # shared singleton, and instance state would let two concurrent agents
        # overwrite each other's correction message.
        last_violation: str | None = None

        async def attempt(attempt_number: int) -> StructuredResponse[T]:
            nonlocal last_violation

            # A schema violation is not transient. Repeating the identical
            # request repeats the identical mistake, so the retry carries the
            # validation error back to the model.
            current = request
            if attempt_number > 0 and last_violation is not None:
                current = _with_correction(request, last_violation)

            message = await self._send(current, tool=tool)

            tool_use = next(
                (block for block in message.content if getattr(block, "type", None) == "tool_use"),
                None,
            )
            if tool_use is None:
                last_violation = "No tool call was emitted; the tool must be called."
                raise SchemaViolationError(
                    "Anthropic returned no structured output",
                    details={"schema": schema.__name__},
                )

            try:
                value = schema.model_validate(tool_use.input)
            except ValidationError as exc:
                last_violation = exc.json(include_url=False)
                raise SchemaViolationError(
                    "Anthropic output failed schema validation",
                    details={"schema": schema.__name__, "error_count": exc.error_count()},
                ) from exc

            return StructuredResponse(
                value=value,
                raw_json=json.dumps(tool_use.input),
                usage=_usage_of(message),
                model=self.model,
                provider=self.name,
            )

        return await with_retries(
            attempt,
            max_retries=self._settings.max_retries,
            description=f"anthropic.complete_structured[{schema.__name__}]",
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        try:
            async with self._client.messages.stream(
                model=self.model,
                system=request.system,
                # The SDK types this as a TypedDict union; our dicts satisfy it
                # structurally, but the roles are only known at runtime.
                messages=_to_messages(request),  # type: ignore[arg-type]
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
        except Exception as exc:
            raise _translate(exc) from exc

    async def aclose(self) -> None:
        await self._client.close()

    async def _send(
        self, request: CompletionRequest, *, tool: dict[str, Any] | None = None
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "system": request.system,
            "messages": _to_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if tool is not None:
            kwargs["tools"] = [tool]
            kwargs["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL_NAME}

        try:
            return await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise _translate(exc) from exc


def _to_messages(request: CompletionRequest) -> list[dict[str, str]]:
    return [
        {"role": message.role.value, "content": message.content}
        for message in request.messages
    ]


def _with_correction(request: CompletionRequest, violation: str) -> CompletionRequest:
    """Return the request with the validation failure appended for the retry."""
    return CompletionRequest(
        system=request.system,
        messages=[
            *request.messages,
            Message(
                role=Role.USER,
                content=(
                    "Your previous output failed schema validation:\n"
                    f"{violation}\n\n"
                    "Call the tool again with corrected output."
                ),
            ),
        ],
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        fixture_key=request.fixture_key,
        metadata=request.metadata,
    )


def _usage_of(message: Any) -> TokenUsage:
    usage = getattr(message, "usage", None)
    if usage is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )


def _translate(exc: Exception) -> ProviderError:
    """Convert a vendor exception into a domain error."""
    name = type(exc).__name__

    if name in _TRANSIENT_ERRORS:
        return TransientProviderError(
            f"Anthropic request failed transiently: {name}", details={"error_type": name}
        )

    return ProviderError(f"Anthropic request failed: {name}", details={"error_type": name})
