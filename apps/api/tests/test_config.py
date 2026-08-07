"""Configuration parsing and environment overrides."""

from __future__ import annotations

import pytest

from app.core.config import Environment, LLMProvider, Settings, get_settings


def test_defaults_are_safe_for_local_development() -> None:
    settings = Settings()

    assert settings.environment is Environment.LOCAL
    assert settings.llm.provider is LLMProvider.ANTHROPIC
    assert settings.database.url.startswith("sqlite")
    assert settings.vector_store.enabled is False


def test_nested_settings_come_from_delimited_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VICTORIOUS_LLM__PROVIDER", "gemini")
    monkeypatch.setenv("VICTORIOUS_DATABASE__ECHO", "true")

    settings = Settings()

    assert settings.llm.provider is LLMProvider.GEMINI
    assert settings.database.echo is True


def test_cors_origins_accept_a_comma_separated_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single env var must be able to carry a list — compose passes strings."""
    monkeypatch.setenv(
        "VICTORIOUS_CORS_ORIGINS", "http://localhost:3000, https://victorious.app"
    )

    assert Settings().cors_origins == ["http://localhost:3000", "https://victorious.app"]


def test_docs_are_disabled_in_production() -> None:
    assert Settings(environment=Environment.PRODUCTION).docs_url is None
    assert Settings(environment=Environment.LOCAL).docs_url == "/docs"


def test_api_keys_are_hidden_from_repr() -> None:
    """Secrets must not reach logs through an accidental repr."""
    settings = Settings()
    settings.llm.anthropic_api_key = "sk-should-not-appear"

    assert "sk-should-not-appear" not in repr(settings.llm)


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
