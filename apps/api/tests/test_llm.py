"""Provider abstraction: fixtures, recording, retry policy, and registry fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.core.config import LLMProvider as ProviderName
from app.core.config import LLMSettings
from app.core.health import HealthStatus
from app.domain.agents import TokenUsage
from app.domain.errors import ProviderError
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
from app.llm.retry import (
    SchemaViolationError,
    TransientProviderError,
    backoff_delay,
    with_retries,
)


class SampleOutput(BaseModel):
    """Stand-in for an agent output contract."""

    decision: str
    confidence: float


def request(key: str | None = "sample") -> CompletionRequest:
    return CompletionRequest(
        system="You are a specialist.",
        messages=[Message(role=Role.USER, content="Decide something.")],
        fixture_key=key,
    )


def write_fixture(directory: Path, name: str, payload: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


# --- Fixture provider ---------------------------------------------------------


async def test_fixture_provider_replays_text(tmp_path: Path) -> None:
    write_fixture(
        tmp_path,
        "sample",
        {"text": "Recorded answer", "usage": {"input_tokens": 10, "output_tokens": 20}},
    )

    response = await FixtureProvider(tmp_path).complete(request())

    assert response.text == "Recorded answer"
    assert response.usage.total == 30
    assert response.provider == "fixture"


async def test_fixture_provider_replays_structured_output(tmp_path: Path) -> None:
    write_fixture(tmp_path, "sample", {"value": {"decision": "Adopt Postgres", "confidence": 0.9}})

    response = await FixtureProvider(tmp_path).complete_structured(request(), SampleOutput)

    assert response.value.decision == "Adopt Postgres"
    assert response.value.confidence == 0.9


async def test_missing_fixture_explains_how_to_record(tmp_path: Path) -> None:
    with pytest.raises(ProviderError) as exc_info:
        await FixtureProvider(tmp_path).complete(request())

    assert "RECORD_FIXTURES" in json.dumps(exc_info.value.details)


async def test_stale_fixture_fails_loudly(tmp_path: Path) -> None:
    """A contract change with an unrefreshed recording must not pass silently."""
    write_fixture(tmp_path, "sample", {"value": {"decision": "Adopt Postgres"}})

    with pytest.raises(ProviderError, match="no longer matches"):
        await FixtureProvider(tmp_path).complete_structured(request(), SampleOutput)


async def test_fixture_streaming_yields_multiple_chunks(tmp_path: Path) -> None:
    """The UI's incremental rendering path must be exercised on fixtures too."""
    write_fixture(tmp_path, "sample", {"text": "x" * 200})

    chunks = [chunk async for chunk in FixtureProvider(tmp_path).stream(request())]

    assert len(chunks) > 1
    assert "".join(chunks) == "x" * 200


def test_fixture_name_prefers_the_explicit_key() -> None:
    assert fixture_name(request("product_manager.requirement_discovery")) == (
        "product_manager.requirement_discovery"
    )


def test_fixture_name_falls_back_to_a_stable_hash() -> None:
    first = fixture_name(request(None))
    second = fixture_name(request(None))

    assert first == second
    assert first.startswith("anon_")


# --- Recording ----------------------------------------------------------------


class StubProvider:
    """Minimal live-provider stand-in for the recorder."""

    name = "stub"
    model = "stub-1"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        return CompletionResponse(
            text="live answer",
            usage=TokenUsage(input_tokens=5, output_tokens=7),
            model=self.model,
            provider=self.name,
        )

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        value = schema.model_validate({"decision": "live decision", "confidence": 0.75})
        return StructuredResponse(
            value=value,
            raw_json="{}",
            usage=TokenUsage(input_tokens=5, output_tokens=7),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest):  # type: ignore[no-untyped-def]
        for chunk in ("live ", "stream"):
            yield chunk

    async def aclose(self) -> None:
        return None


async def test_recorder_writes_a_replayable_fixture(tmp_path: Path) -> None:
    """The round trip the offline demo depends on."""
    recorder = RecordingProvider(StubProvider(), tmp_path)

    await recorder.complete_structured(request(), SampleOutput)
    replayed = await FixtureProvider(tmp_path).complete_structured(request(), SampleOutput)

    assert replayed.value.decision == "live decision"
    assert replayed.usage.total == 12


async def test_recorder_passes_the_response_through(tmp_path: Path) -> None:
    response = await RecordingProvider(StubProvider(), tmp_path).complete(request())

    assert response.text == "live answer"
    assert response.provider == "stub"


async def test_recording_failure_does_not_break_the_call(tmp_path: Path) -> None:
    """A recording problem is not an engineering problem."""
    unwritable = tmp_path / "file-not-a-directory"
    unwritable.write_text("blocked", encoding="utf-8")

    response = await RecordingProvider(StubProvider(), unwritable).complete(request())

    assert response.text == "live answer"


# --- Retry policy -------------------------------------------------------------


async def test_transient_failures_are_retried() -> None:
    attempts = 0

    async def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TransientProviderError("rate limited")
        return "succeeded"

    assert await with_retries(operation, max_retries=3, description="test") == "succeeded"
    assert attempts == 3


async def test_schema_violations_receive_the_attempt_number() -> None:
    """The retry must be able to vary the request, not repeat it identically."""
    seen: list[int] = []

    async def operation(attempt: int) -> str:
        seen.append(attempt)
        if attempt == 0:
            raise SchemaViolationError("missing field")
        return "corrected"

    assert await with_retries(operation, max_retries=2, description="test") == "corrected"
    assert seen == [0, 1]


async def test_exhausted_retries_raise_provider_error() -> None:
    async def operation(_: int) -> str:
        raise TransientProviderError("still failing")

    with pytest.raises(ProviderError, match="after 3 attempts"):
        await with_retries(operation, max_retries=2, description="test")


async def test_non_retryable_errors_propagate_immediately() -> None:
    """An authentication failure must not be retried three times."""
    attempts = 0

    async def operation(_: int) -> str:
        nonlocal attempts
        attempts += 1
        raise ProviderError("invalid api key")

    with pytest.raises(ProviderError, match="invalid api key"):
        await with_retries(operation, max_retries=3, description="test")

    assert attempts == 1


def test_backoff_grows_and_is_jittered() -> None:
    """Jitter prevents seven agents resynchronising against one rate limit."""
    assert backoff_delay(0) < backoff_delay(5)
    assert backoff_delay(99) <= 8.0
    assert len({backoff_delay(2) for _ in range(20)}) > 1


# --- Registry -----------------------------------------------------------------


def test_registry_builds_the_fixture_provider(tmp_path: Path) -> None:
    provider = build_provider(
        LLMSettings(provider=ProviderName.FIXTURE, fixture_dir=str(tmp_path))
    )

    assert provider.name == "fixture"


def test_registry_falls_back_when_a_key_is_missing(tmp_path: Path) -> None:
    """Missing credentials must not prevent startup — fixtures still work."""
    provider = build_provider(
        LLMSettings(
            provider=ProviderName.ANTHROPIC, anthropic_api_key=None, fixture_dir=str(tmp_path)
        )
    )

    assert provider.name == "fixture"


def test_registry_wraps_in_a_recorder_when_enabled(tmp_path: Path) -> None:
    settings = LLMSettings(
        provider=ProviderName.ANTHROPIC,
        anthropic_api_key="sk-test-not-a-real-key",
        fixture_dir=str(tmp_path),
        record_fixtures=True,
    )

    provider = build_provider(settings)

    assert isinstance(provider, RecordingProvider)
    assert provider.name == "anthropic"


async def test_provider_health_reports_degraded_on_fallback(tmp_path: Path) -> None:
    settings = LLMSettings(provider=ProviderName.ANTHROPIC, fixture_dir=str(tmp_path))
    provider = build_provider(settings)

    health = await ProviderHealthCheck(provider, settings).check()

    assert health.status is HealthStatus.DEGRADED
    assert "recorded fixtures" in (health.message or "")


async def test_provider_health_is_healthy_when_configured_matches(tmp_path: Path) -> None:
    settings = LLMSettings(provider=ProviderName.FIXTURE, fixture_dir=str(tmp_path))
    provider = build_provider(settings)

    health = await ProviderHealthCheck(provider, settings).check()

    assert health.status is HealthStatus.HEALTHY


def test_adapters_satisfy_the_provider_protocol(tmp_path: Path) -> None:
    """Structural conformance, checked without instantiating a network client."""
    from app.llm.anthropic_provider import AnthropicProvider
    from app.llm.gemini_provider import GeminiProvider

    for adapter in (FixtureProvider, RecordingProvider, AnthropicProvider, GeminiProvider):
        for method in ("complete", "complete_structured", "stream", "aclose"):
            assert callable(getattr(adapter, method)), f"{adapter.__name__}.{method}"

    assert isinstance(FixtureProvider(tmp_path), LLMProvider)
