"""The engineering review layer.

The properties worth defending here are the ones that make a score mean
something: it is mostly measured rather than opined, a model cannot overturn a
measured fact, and a broken reviewer never stops the organization from working.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from pydantic import BaseModel

from app.core.config import DatabaseSettings, ReviewSettings
from app.db.session import Database
from app.domain.agents import TokenUsage
from app.domain.artifacts import Artifact, ArtifactType, ArtifactVersion
from app.domain.lifecycle import AgentRole, LifecycleStage
from app.domain.projects import Project
from app.domain.reviews import ReviewVerdict
from app.llm.provider import CompletionRequest, CompletionResponse, StructuredResponse
from app.memory.sql_repository import SqlSharedMemory
from app.review.checks import is_first_stage, run_checks
from app.review.reviewer import MAX_ADJUSTMENT, EngineeringReviewer

pytestmark = pytest.mark.asyncio


class JudgingProvider:
    """Returns a prepared judgement, recording what it was asked."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise AssertionError("The reviewer must ask for structure, never free text")

    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        self.requests.append(request)
        return StructuredResponse(
            value=schema.model_validate(self._payload),
            raw_json=json.dumps(self._payload),
            usage=TokenUsage(input_tokens=10, output_tokens=20),
            model=self.model,
            provider=self.name,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        yield ""

    async def aclose(self) -> None:
        return None


class BrokenProvider(JudgingProvider):
    async def complete_structured[T: BaseModel](
        self, request: CompletionRequest, schema: type[T]
    ) -> StructuredResponse[T]:
        raise RuntimeError("the reviewing model fell over")


def judgement(**overrides: object) -> dict[str, object]:
    return {
        "summary": "Solid architecture, weak on failure modes.",
        "score_adjustment": 0,
        "strengths": ["Component boundaries follow the requirements."],
        "weaknesses": ["No failure-mode analysis."],
        "suggestions": ["Describe what happens when the queue is unavailable."],
        **overrides,
    }


def artifact_and_version(
    *,
    artifact_type: ArtifactType = ArtifactType.SYSTEM_ARCHITECTURE,
    stage: LifecycleStage = LifecycleStage.ARCHITECTURE,
    body: str | None = None,
    content: dict[str, object] | None = None,
    confidence: float | None = 0.9,
) -> tuple[Artifact, ArtifactVersion]:
    artifact = Artifact(
        project_id="proj-1",
        type=artifact_type,
        title="System Architecture",
        stage=stage,
        owner_role=AgentRole.SOFTWARE_ARCHITECT,
    )
    version = ArtifactVersion(
        artifact_id=artifact.id,
        version=1,
        body_markdown=body if body is not None else "# Architecture\n\n" + "detail. " * 250,
        content=content if content is not None else {"components": ["api"], "style": "modular"},
        confidence=confidence,
    )
    return artifact, version


# --- Deterministic checks -------------------------------------------------


async def test_a_complete_artifact_scores_well() -> None:
    artifact, version = artifact_and_version()

    result = run_checks(artifact, version, upstream_count=2, is_first_stage=False)

    assert result.score >= 90
    assert result.weaknesses == []


async def test_an_artifact_without_upstream_loses_the_traceability_points() -> None:
    """The property the whole platform rests on, so it is the heaviest check."""
    artifact, version = artifact_and_version()

    traced = run_checks(artifact, version, upstream_count=1, is_first_stage=False)
    orphaned = run_checks(artifact, version, upstream_count=0, is_first_stage=False)

    assert traced.score - orphaned.score == 25
    assert any("no upstream" in finding.text for finding in orphaned.weaknesses)


async def test_the_first_stage_is_not_penalised_for_having_no_upstream() -> None:
    artifact, version = artifact_and_version(
        artifact_type=ArtifactType.PRD,
        stage=LifecycleStage.REQUIREMENT_DISCOVERY,
        content={"functional_requirements": ["FR-01"], "objective": "Book appointments"},
    )

    result = run_checks(artifact, version, upstream_count=0, is_first_stage=True)

    assert result.score >= 90
    assert not any("no upstream" in finding.text for finding in result.weaknesses)


async def test_requirement_discovery_is_the_only_originating_stage() -> None:
    assert is_first_stage(LifecycleStage.REQUIREMENT_DISCOVERY)
    assert not is_first_stage(LifecycleStage.ARCHITECTURE)


async def test_a_missing_type_specific_field_is_reported_by_name() -> None:
    """A finding a user can check beats a finding they have to trust."""
    artifact, version = artifact_and_version(content={"components": ["api"]})

    result = run_checks(artifact, version, upstream_count=1, is_first_stage=False)

    assert any("style" in finding.text for finding in result.weaknesses)


async def test_scores_differ_across_artifacts_of_differing_quality() -> None:
    """Otherwise the number is theatre — the point of measuring, not opining."""
    good, good_version = artifact_and_version()
    thin, thin_version = artifact_and_version(body="# Architecture\n", content={})

    good_result = run_checks(good, good_version, upstream_count=3, is_first_stage=False)
    thin_result = run_checks(thin, thin_version, upstream_count=0, is_first_stage=False)

    assert good_result.score > thin_result.score + 40


async def test_low_confidence_is_penalised_and_routed_to_a_human() -> None:
    artifact, version = artifact_and_version(confidence=0.2)

    result = run_checks(artifact, version, upstream_count=1, is_first_stage=False)

    assert any("low confidence" in finding.text for finding in result.weaknesses)
    assert any("human" in finding.text for finding in result.suggestions)


# --- Reasoning layer ------------------------------------------------------


async def test_reasoning_adjusts_the_score_and_contributes_findings() -> None:
    provider = JudgingProvider(judgement(score_adjustment=-5))
    reviewer = EngineeringReviewer(provider, ReviewSettings())
    artifact, version = artifact_and_version()

    review = await reviewer.review(artifact, version, upstream_count=2)

    assert review.quality_score == review.deterministic_score - 5
    assert review.reasoning_applied
    assert review.reviewer_model == "scripted-1"
    assert any(finding.source == "reasoning" for finding in review.weaknesses)
    assert any(finding.source == "check" for finding in review.strengths)


async def test_reasoning_cannot_rescue_a_structurally_broken_artifact() -> None:
    """The cap is the design: a model may sharpen a judgement, not overturn one."""
    provider = JudgingProvider(judgement(score_adjustment=MAX_ADJUSTMENT))
    reviewer = EngineeringReviewer(provider, ReviewSettings())
    artifact, version = artifact_and_version(body="# Architecture\n", content={})

    review = await reviewer.review(artifact, version, upstream_count=0)

    assert review.quality_score <= review.deterministic_score + MAX_ADJUSTMENT
    assert review.verdict is ReviewVerdict.NEEDS_REVISION


async def test_an_adjustment_beyond_the_cap_is_rejected_not_clamped() -> None:
    """Schema-level refusal, so an out-of-range judgement never silently applies."""
    provider = JudgingProvider(judgement(score_adjustment=MAX_ADJUSTMENT + 40))
    reviewer = EngineeringReviewer(provider, ReviewSettings())
    artifact, version = artifact_and_version()

    review = await reviewer.review(artifact, version, upstream_count=2)

    assert not review.reasoning_applied
    assert review.quality_score == review.deterministic_score


async def test_a_broken_reviewer_degrades_to_the_structural_review() -> None:
    reviewer = EngineeringReviewer(BrokenProvider({}), ReviewSettings())
    artifact, version = artifact_and_version()

    review = await reviewer.review(artifact, version, upstream_count=2)

    assert review.quality_score == review.deterministic_score
    assert not review.reasoning_applied
    assert review.reviewer_model is None


async def test_reasoning_can_be_switched_off() -> None:
    provider = JudgingProvider(judgement())
    reviewer = EngineeringReviewer(provider, ReviewSettings(use_reasoning=False))
    artifact, version = artifact_and_version()

    review = await reviewer.review(artifact, version, upstream_count=2)

    assert provider.requests == []
    assert not review.reasoning_applied


async def test_the_fixture_key_is_typed_so_one_recording_covers_every_project() -> None:
    provider = JudgingProvider(judgement())
    reviewer = EngineeringReviewer(provider, ReviewSettings())
    artifact, version = artifact_and_version()

    await reviewer.review(artifact, version, upstream_count=2)

    assert provider.requests[0].fixture_key == "review.system_architecture"


async def test_the_reviewing_model_is_shown_the_structural_evidence() -> None:
    """So its judgement builds on the facts rather than contradicting them."""
    provider = JudgingProvider(judgement())
    reviewer = EngineeringReviewer(provider, ReviewSettings())
    artifact, version = artifact_and_version()

    await reviewer.review(artifact, version, upstream_count=2)

    prompt = provider.requests[0].messages[0].content
    assert "Structural score:" in prompt
    assert "Traced to 2 upstream artifact(s)." in prompt


@pytest.mark.parametrize(
    ("score_adjustment", "expected"),
    [
        (MAX_ADJUSTMENT, ReviewVerdict.APPROVED),
        (0, ReviewVerdict.APPROVED_WITH_SUGGESTIONS),
    ],
)
async def test_the_verdict_follows_the_configured_thresholds(
    score_adjustment: int, expected: ReviewVerdict
) -> None:
    provider = JudgingProvider(judgement(score_adjustment=score_adjustment))
    reviewer = EngineeringReviewer(
        provider, ReviewSettings(strong_threshold=95, revision_threshold=60)
    )
    artifact, version = artifact_and_version(confidence=0.6)

    review = await reviewer.review(artifact, version, upstream_count=2)

    assert review.verdict is expected


async def test_only_a_verdict_at_or_above_the_threshold_is_acceptable() -> None:
    assert ReviewVerdict.APPROVED.is_acceptable
    assert ReviewVerdict.APPROVED_WITH_SUGGESTIONS.is_acceptable
    assert not ReviewVerdict.NEEDS_REVISION.is_acceptable


# --- Persistence ----------------------------------------------------------


@pytest_asyncio.fixture
async def memory() -> AsyncIterator[SqlSharedMemory]:
    database = Database(
        DatabaseSettings(url="sqlite+aiosqlite:///file:reviewdb?mode=memory&cache=shared&uri=true")
    )
    await database.create_schema()
    try:
        yield SqlSharedMemory(database)
    finally:
        await database.aclose()


async def test_a_review_is_stored_per_version_and_replaced_in_place(
    memory: SqlSharedMemory,
) -> None:
    """Re-reviewing a version must correct it, not accumulate duplicates."""
    project = await memory.projects.create(Project(name="Clinic", description="Bookings."))
    artifact = await memory.artifacts.create(
        Artifact(
            project_id=project.id,
            type=ArtifactType.SYSTEM_ARCHITECTURE,
            title="System Architecture",
            stage=LifecycleStage.ARCHITECTURE,
            owner_role=AgentRole.SOFTWARE_ARCHITECT,
        )
    )
    version = await memory.artifacts.append_version(
        artifact.id,
        ArtifactVersion(
            artifact_id=artifact.id,
            version=1,
            body_markdown="# Architecture\n\n" + "detail. " * 250,
            content={"components": ["api"], "style": "modular"},
            confidence=0.9,
        ),
    )

    reviewer = EngineeringReviewer(JudgingProvider(judgement()), ReviewSettings())

    first = await reviewer.review(artifact, version, upstream_count=2)
    await memory.reviews.upsert(first)

    second = await reviewer.review(artifact, version, upstream_count=0)
    await memory.reviews.upsert(second)

    stored = await memory.reviews.list_for_project(project.id)
    assert len(stored) == 1
    assert stored[0].quality_score == second.quality_score

    latest = await memory.reviews.for_artifact(artifact.id)
    assert latest is not None
    assert latest.artifact_version == 1
