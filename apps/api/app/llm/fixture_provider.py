"""Fixture provider — replays recorded reasoning from disk.

A first-class provider, not a mock. It exists for two reasons the specification
makes explicit:

- **Demo resilience.** `12_Risk_Analysis.md` rates Model Availability a Medium
  risk, and `13_Demo_and_Pitch.md` requires a polished end-to-end demonstration.
  A provider outage during a live demo is otherwise unrecoverable. With recorded
  fixtures the entire platform runs with no network at all.
- **Deterministic tests.** The suite exercises real agent code paths without
  network access, latency, or API spend.

Fixtures are plain JSON on disk with human-readable names. A reviewer can open,
read, and edit one — which a content-hash filename would prevent.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.domain.agents import TokenUsage
from app.domain.errors import ProviderError
from app.llm.provider import CompletionRequest, CompletionResponse, StructuredResponse

logger = get_logger(__name__)

#: Streaming replays in slices of this size so the UI exercises its incremental
#: rendering path during a fixture-backed demo rather than receiving one blob.
_STREAM_CHUNK_CHARS = 48

#: Placeholder a fixture uses in place of project-specific upstream artifact IDs.
UPSTREAM_TOKEN = "$upstream"  # noqa: S105 - a substitution token, not a credential

_ARTIFACT_ID = re.compile(r"art_[0-9a-f]{32}")


class FixtureProvider:
    """Replays recorded provider responses from a directory."""

    def __init__(self, fixture_dir: str | Path, *, model: str = "fixture") -> None:
        self._dir = Path(fixture_dir)
        self._model = model

    @property
    def name(self) -> str:
        return "fixture"

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        payload = self._load(request)
        text = payload.get("text")
        if not isinstance(text, str):
            raise ProviderError(
                "Fixture is missing a string 'text' field",
                details={"fixture": self._path_for(request).name},
            )

        return CompletionResponse(
            text=text,
            usage=_usage_of(payload),
            model=self.model,
            provider=self.name,
        )

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        payload = self._load(request)
        value_data = payload.get("value")

        if value_data is None:
            raise ProviderError(
                "Fixture is missing a 'value' object for structured output",
                details={"fixture": self._path_for(request).name, "schema": schema.__name__},
            )

        if isinstance(value_data, dict):
            value_data = _expand_upstream(value_data, request)

        try:
            value = schema.model_validate(value_data)
        except ValidationError as exc:
            # A stale fixture is a real failure worth surfacing loudly: it means
            # the agent's contract changed and the recording was not refreshed,
            # which would otherwise show up as inexplicable demo behaviour.
            raise ProviderError(
                "Recorded fixture no longer matches the agent output contract",
                details={
                    "fixture": self._path_for(request).name,
                    "schema": schema.__name__,
                    "error_count": exc.error_count(),
                },
            ) from exc

        return StructuredResponse(
            value=value,
            raw_json=json.dumps(value_data),
            usage=_usage_of(payload),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        response = await self.complete(request)
        for start in range(0, len(response.text), _STREAM_CHUNK_CHARS):
            yield response.text[start : start + _STREAM_CHUNK_CHARS]

    async def aclose(self) -> None:
        return None

    def _load(self, request: CompletionRequest) -> dict[str, Any]:
        path = self._path_for(request)

        if not path.is_file():
            raise ProviderError(
                "No recorded fixture for this request",
                details={
                    "fixture": path.name,
                    "directory": str(self._dir),
                    "hint": (
                        "Record fixtures by running with a live provider and "
                        "VICTORIOUS_LLM__RECORD_FIXTURES=true."
                    ),
                },
            )

        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "Fixture file is not valid JSON", details={"fixture": path.name}
            ) from exc

        if not isinstance(loaded, dict):
            raise ProviderError(
                "Fixture must be a JSON object", details={"fixture": path.name}
            )
        return loaded

    def _path_for(self, request: CompletionRequest) -> Path:
        return self._dir / f"{fixture_name(request)}.json"


def fixture_name(request: CompletionRequest) -> str:
    """Return the filename stem for a request.

    Prefers the explicit ``fixture_key`` an agent supplies, so demo fixtures are
    named after the work they represent. Falls back to a content hash only when
    no key is given, which keeps ad-hoc calls recordable without inventing names.
    """
    if request.fixture_key:
        return request.fixture_key

    digest = hashlib.sha256()
    digest.update(request.system.encode("utf-8"))
    for message in request.messages:
        digest.update(message.role.value.encode("utf-8"))
        digest.update(message.content.encode("utf-8"))
    return f"anon_{digest.hexdigest()[:16]}"


def _expand_upstream(value: dict[str, Any], request: CompletionRequest) -> dict[str, Any]:
    """Resolve the ``$upstream`` token in a recorded ``sources`` field.

    Artifact IDs are minted per project, so a recording made against one project
    cites IDs that exist in no other. Without substitution a replayed fixture
    could never declare its upstream, and the agent base class would reject every
    downstream artifact as an orphan — making an offline demo impossible.

    A fixture therefore records ``"sources": "$upstream"``, and this expands it to
    the artifact IDs actually present in the current request's context. The
    resulting edges are truthful: those are the artifacts the agent was shown.
    """
    if value.get("sources") != UPSTREAM_TOKEN:
        return value

    context = " ".join(message.content for message in request.messages)
    artifact_ids = sorted(set(_ARTIFACT_ID.findall(context)))

    return {
        **value,
        "sources": [
            {
                "upstream_artifact_id": artifact_id,
                "kind": "derives_from",
                "rationale": "Supplied as upstream engineering context for this stage.",
            }
            for artifact_id in artifact_ids
        ],
    }


def _usage_of(payload: dict[str, Any]) -> TokenUsage:
    """Read recorded usage, defaulting to zero.

    Recorded counts are preserved so a fixture-backed demo still shows realistic
    token figures on the agent cards rather than zeros.
    """
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return TokenUsage()
    return TokenUsage(
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
    )
