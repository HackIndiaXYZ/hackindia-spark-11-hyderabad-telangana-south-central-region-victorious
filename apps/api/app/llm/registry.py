"""Provider construction and fallback.

One place decides which adapter is built and what happens when it cannot be.
That keeps the composition root declarative and gives `12_Risk_Analysis.md`'s
"graceful fallback strategies" a concrete implementation rather than a promise.
"""

from __future__ import annotations

from app.core.config import LLMProvider as ProviderName
from app.core.config import LLMSettings
from app.core.health import ComponentHealth, HealthStatus
from app.core.logging import get_logger
from app.domain.errors import ProviderError
from app.llm.fixture_provider import FixtureProvider
from app.llm.provider import LLMProvider
from app.llm.recording import RecordingProvider

logger = get_logger(__name__)


def build_provider(settings: LLMSettings) -> LLMProvider:
    """Construct the configured provider.

    Falls back to the fixture provider when a live provider cannot be built —
    almost always a missing API key. Failing to start would be the wrong
    behaviour: the platform is fully explorable on recorded fixtures, and a
    developer who has not yet obtained a key should still be able to run it.

    The fallback is logged at warning level, and the provider name recorded on
    every agent run makes it unmistakable which backend actually reasoned.
    """
    if settings.provider is ProviderName.FIXTURE:
        return FixtureProvider(settings.fixture_dir)

    try:
        provider = _build_live(settings)
    except ProviderError as exc:
        logger.warning(
            "Falling back to recorded fixtures",
            extra={"requested_provider": settings.provider.value, "reason": exc.message},
        )
        return FixtureProvider(settings.fixture_dir)

    if settings.record_fixtures:
        logger.info("Fixture recording enabled", extra={"directory": settings.fixture_dir})
        return RecordingProvider(provider, settings.fixture_dir)

    return provider


def _build_live(settings: LLMSettings) -> LLMProvider:
    """Construct a network-backed provider.

    Adapters are imported inside the branch so selecting one provider never
    requires the other's SDK to be installed.
    """
    if settings.provider is ProviderName.ANTHROPIC:
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings)

    if settings.provider is ProviderName.GEMINI:
        from app.llm.gemini_provider import GeminiProvider

        return GeminiProvider(settings)

    raise ProviderError(
        "Unsupported reasoning provider", details={"provider": settings.provider.value}
    )


class ProviderHealthCheck:
    """Reports which reasoning backend is live.

    Deliberately does not call the provider: a readiness probe that spends tokens
    on every poll would be expensive and would count against rate limits. It
    reports what is configured and whether the platform fell back to fixtures,
    which is the operationally important fact.
    """

    def __init__(self, provider: LLMProvider, settings: LLMSettings) -> None:
        self._provider = provider
        self._settings = settings

    @property
    def name(self) -> str:
        return "reasoning_provider"

    @property
    def critical(self) -> bool:
        """Non-critical: on fixtures the platform still serves every read path."""
        return False

    async def check(self) -> ComponentHealth:
        configured = self._settings.provider.value
        active = self._provider.name

        if active == configured:
            return ComponentHealth(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"{active} · {self._provider.model}",
            )

        return ComponentHealth(
            name=self.name,
            status=HealthStatus.DEGRADED,
            message=f"Configured for {configured}, running on recorded fixtures",
        )
