"""Typed application configuration.

Every runtime knob is declared here with a type and a default. Nothing in the
codebase reads ``os.environ`` directly — configuration arrives through injection,
which keeps modules testable and makes the full set of tunables discoverable in
one file.

Environment variables use the ``VICTORIOUS_`` prefix with ``__`` as the nesting
delimiter, so the LLM provider is set via ``VICTORIOUS_LLM__PROVIDER``.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment. Controls docs exposure and error verbosity."""

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(StrEnum):
    """Supported reasoning providers.

    ``FIXTURE`` replays recorded responses from disk. It exists so the platform
    can be demonstrated and tested with no network access and no API spend — see
    ADR-0005. It is a first-class provider, not a mock.
    """

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    FIXTURE = "fixture"


class DatabaseSettings(BaseModel):
    """Persistence configuration for the shared organizational memory."""

    url: str = Field(
        default="sqlite+aiosqlite:///./victorious.db",
        description="SQLAlchemy async URL. PostgreSQL in compose, SQLite locally.",
    )
    echo: bool = Field(default=False, description="Log every emitted SQL statement.")
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=10, ge=0, le=50)


class LLMSettings(BaseModel):
    """Reasoning provider configuration.

    ``provider`` selects the default adapter; the abstraction in ``app.llm``
    (Milestone 2) allows any agent to override it per invocation.
    """

    provider: LLMProvider = Field(default=LLMProvider.ANTHROPIC)
    anthropic_api_key: str | None = Field(default=None, repr=False)
    google_api_key: str | None = Field(default=None, repr=False)
    anthropic_model: str = Field(default="claude-sonnet-5")
    gemini_model: str = Field(default="gemini-2.5-pro")
    fixture_dir: str = Field(
        default="./fixtures",
        description="Directory of recorded provider responses used by the fixture provider.",
    )
    record_fixtures: bool = Field(
        default=False,
        description=(
            "Wrap the live provider in a recorder, writing every response to "
            "`fixture_dir`. Run once against a real provider to produce the "
            "offline demo corpus."
        ),
    )
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: float = Field(default=120.0, gt=0)


class VectorStoreSettings(BaseModel):
    """Semantic memory configuration.

    Runs as an embedded persistent client rather than a separate service — see
    ADR-0005.
    """

    enabled: bool = Field(default=False)
    persist_dir: str = Field(default="./.chroma")
    collection: str = Field(default="victorious_memory")


class ReviewSettings(BaseModel):
    """Engineering review configuration.

    Reviewing is on by default because a score on every artifact is the point;
    *blocking* on that score is off by default because a review that halts the
    workflow is a new way for a live demonstration to stall. Turn it on
    deliberately (`VICTORIOUS_REVIEW__BLOCKING=true`) to show the gate.
    """

    enabled: bool = Field(
        default=True, description="Review each artifact as it is produced."
    )
    use_reasoning: bool = Field(
        default=True,
        description=(
            "Let a model contribute prose and a bounded score adjustment. When "
            "false, reviews are purely structural and say so."
        ),
    )
    blocking: bool = Field(
        default=False,
        description=(
            "Whether the Executive AI halts a stage whose upstream reviews fall "
            "below `revision_threshold`. Advisory when false."
        ),
    )
    revision_threshold: int = Field(
        default=60, ge=0, le=100, description="Below this, the verdict is needs_revision."
    )
    strong_threshold: int = Field(
        default=85, ge=0, le=100, description="At or above this, the verdict is approved."
    )


class ObservabilitySettings(BaseModel):
    """Logging and diagnostics configuration."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    json_logs: bool = Field(
        default=True,
        description="Structured JSON output. Disable locally for readable console logs.",
    )


class Settings(BaseSettings):
    """Root settings object, injected wherever configuration is needed."""

    model_config = SettingsConfigDict(
        env_prefix="VICTORIOUS_",
        env_nested_delimiter="__",
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Project Victorious"
    version: str = "0.1.0"
    environment: Environment = Environment.LOCAL

    api_prefix: str = "/api/v1"

    # NoDecode suppresses pydantic-settings' default JSON decoding for complex
    # types, so the validator below can accept a plain comma-separated string.
    # Without it, `VICTORIOUS_CORS_ORIGINS=http://a,http://b` fails as invalid JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(default=["http://localhost:3000"])

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string so a single env var can carry a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def docs_url(self) -> str | None:
        """OpenAPI docs are disabled in production to reduce surface area."""
        return None if self.is_production else "/docs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached because settings are immutable for the lifetime of the process.
    Tests clear the cache via ``get_settings.cache_clear()``.
    """
    return Settings()
