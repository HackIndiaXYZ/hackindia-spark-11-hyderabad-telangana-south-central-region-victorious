"""Google Gemini reasoning adapter.

`08_Technology_Stack.md` names Gemini as the LLM. ADR-0004 makes Claude the
default on structured-output reliability grounds while keeping Gemini a real,
exercised adapter — provider agnosticism that is never run against a second
provider is a claim, not a property.

Structured output uses the API's native JSON mode with a response schema, which
is Gemini's equivalent of constraining generation rather than hoping prose parses.
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

#: Substrings of vendor error messages that indicate a transient condition.
#: Matched on text because the SDK raises a small number of broad exception
#: types and encodes the distinguishing detail in the message.
_TRANSIENT_MARKERS = ("429", "500", "502", "503", "504", "timeout", "deadline", "unavailable")


class GeminiProvider:
    """Reasoning backed by the Google Gen AI API."""

    def __init__(self, settings: LLMSettings) -> None:
        if not settings.google_api_key:
            raise ProviderError(
                "Gemini provider selected but no API key is configured",
                details={"env_var": "GOOGLE_API_KEY"},
            )

        # Lazy, as in the Anthropic adapter: selecting one provider must not
        # require the other's SDK to be installed.
        from google import genai

        self._settings = settings
        self._client = genai.Client(api_key=settings.google_api_key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._settings.gemini_model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        async def attempt(_: int) -> CompletionResponse:
            response = await self._send(request)
            return CompletionResponse(
                text=response.text or "",
                usage=_usage_of(response),
                model=self.model,
                provider=self.name,
            )

        return await with_retries(
            attempt, max_retries=self._settings.max_retries, description="gemini.complete"
        )

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        last_violation: str | None = None

        async def attempt(attempt_number: int) -> StructuredResponse[T]:
            nonlocal last_violation

            current = request
            if attempt_number > 0 and last_violation is not None:
                current = _with_correction(request, last_violation)

            response = await self._send(current, schema=schema)
            raw = response.text or ""

            try:
                value = schema.model_validate_json(raw)
            except ValidationError as exc:
                last_violation = exc.json(include_url=False)
                raise SchemaViolationError(
                    "Gemini output failed schema validation",
                    details={"schema": schema.__name__, "error_count": exc.error_count()},
                ) from exc
            except json.JSONDecodeError as exc:
                last_violation = f"Output was not valid JSON: {exc}"
                raise SchemaViolationError(
                    "Gemini returned malformed JSON", details={"schema": schema.__name__}
                ) from exc

            return StructuredResponse(
                value=value,
                raw_json=raw,
                usage=_usage_of(response),
                model=self.model,
                provider=self.name,
            )

        return await with_retries(
            attempt,
            max_retries=self._settings.max_retries,
            description=f"gemini.complete_structured[{schema.__name__}]",
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        from google.genai import types

        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=_to_contents(request),
                config=types.GenerateContentConfig(
                    system_instruction=request.system,
                    max_output_tokens=request.max_tokens,
                    temperature=request.temperature,
                ),
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            raise _translate(exc) from exc

    async def aclose(self) -> None:
        """No-op: the Gen AI client holds no connection pool needing disposal."""
        return None

    async def _send(
        self, request: CompletionRequest, *, schema: type[BaseModel] | None = None
    ) -> Any:
        from google.genai import types

        config: dict[str, Any] = {
            "system_instruction": request.system,
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = schema

        try:
            return await self._client.aio.models.generate_content(
                model=self.model,
                contents=_to_contents(request),
                config=types.GenerateContentConfig(**config),
            )
        except Exception as exc:
            raise _translate(exc) from exc


def _to_contents(request: CompletionRequest) -> list[dict[str, Any]]:
    """Map the shared message shape onto Gemini's content format.

    Gemini names the assistant role "model"; the mapping is confined here so no
    caller has to know that.
    """
    role_map = {Role.USER: "user", Role.ASSISTANT: "model"}
    return [
        {"role": role_map[message.role], "parts": [{"text": message.content}]}
        for message in request.messages
    ]


def _with_correction(request: CompletionRequest, violation: str) -> CompletionRequest:
    return CompletionRequest(
        system=request.system,
        messages=[
            *request.messages,
            Message(
                role=Role.USER,
                content=(
                    "Your previous output failed schema validation:\n"
                    f"{violation}\n\n"
                    "Return corrected JSON matching the schema exactly."
                ),
            ),
        ],
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        fixture_key=request.fixture_key,
        metadata=request.metadata,
    )


def _usage_of(response: Any) -> TokenUsage:
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=getattr(metadata, "prompt_token_count", 0) or 0,
        output_tokens=getattr(metadata, "candidates_token_count", 0) or 0,
    )


def _translate(exc: Exception) -> ProviderError:
    message = str(exc).lower()
    name = type(exc).__name__

    if any(marker in message for marker in _TRANSIENT_MARKERS):
        return TransientProviderError(
            f"Gemini request failed transiently: {name}", details={"error_type": name}
        )

    return ProviderError(f"Gemini request failed: {name}", details={"error_type": name})
