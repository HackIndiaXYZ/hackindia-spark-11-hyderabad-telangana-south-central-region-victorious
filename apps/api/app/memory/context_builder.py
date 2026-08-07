"""Assembles the project context an agent reasons over.

`02_Proposed_Solution.md` requires "shared context over isolated tasks": each
stage has access to the decisions and rationale produced by prior stages, so a
requirement defined once is not restated or reinterpreted downstream.

The builder answers a narrow question — *what should this agent read right now?* —
and enforces three rules the platform depends on:

1. **Upstream only.** An agent sees stages before its own. Feeding it downstream
   artifacts would let a later stage's guesses contaminate an earlier decision.
2. **Approved first.** Approved artifacts are included before drafts, so an agent
   reasons over what a human has sanctioned rather than over unreviewed output.
3. **Budgeted.** Context is truncated to a token budget, newest and most relevant
   retained. `12_Risk_Analysis.md` rates High Token Consumption a Medium risk;
   an unbounded context window is how that risk materialises.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactType
from app.domain.lifecycle import AgentRole, LifecycleStage, preceding_stages
from app.memory.repository import ArtifactRepository, ProjectRepository

logger = get_logger(__name__)

#: Characters per token. A deliberate approximation — exact counting is
#: provider-specific and would couple this module to a vendor tokenizer, which
#: ADR-0004's provider abstraction exists to prevent. Conservative by design:
#: over-estimating tokens truncates early, which is the safe direction.
CHARS_PER_TOKEN = 4

DEFAULT_TOKEN_BUDGET = 24_000


@dataclass(frozen=True)
class ContextEntry:
    """One artifact included in an agent's context."""

    artifact: Artifact
    body_markdown: str
    version: int
    included_fully: bool = True

    @property
    def estimated_tokens(self) -> int:
        return len(self.body_markdown) // CHARS_PER_TOKEN


@dataclass
class ProjectContext:
    """Everything an agent reads before reasoning."""

    project_id: str
    project_name: str
    project_description: str
    stage: LifecycleStage
    role: AgentRole

    entries: list[ContextEntry] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    """Titles of artifacts dropped for budget. Reported rather than hidden, so a
    thin answer can be explained by what the agent was not shown."""

    @property
    def estimated_tokens(self) -> int:
        return sum(entry.estimated_tokens for entry in self.entries)

    @property
    def artifact_ids(self) -> list[str]:
        """Inputs recorded on the agent run — the upstream half of a trace edge."""
        return [entry.artifact.id for entry in self.entries]

    def render(self) -> str:
        """Render as the markdown block placed in the agent's prompt."""
        sections = [
            "# Project context",
            "",
            f"**Project:** {self.project_name}",
            f"**Description:** {self.project_description}",
            f"**Current stage:** {self.stage.value}",
            "",
        ]

        if not self.entries:
            sections.append("_No upstream artifacts exist yet. This is the first stage._")
            return "\n".join(sections)

        sections.append("## Upstream engineering artifacts")
        sections.append("")

        for entry in self.entries:
            marker = "" if entry.included_fully else " _(truncated)_"
            sections.extend(
                [
                    f"### {entry.artifact.title}{marker}",
                    f"_Type: {entry.artifact.type.value} · "
                    f"Stage: {entry.artifact.stage.value} · "
                    f"Version: {entry.version} · "
                    f"Status: {entry.artifact.status.value}_",
                    "",
                    entry.body_markdown,
                    "",
                ]
            )

        if self.omitted:
            sections.extend(
                [
                    "## Omitted for context budget",
                    "",
                    *(f"- {title}" for title in self.omitted),
                    "",
                ]
            )

        return "\n".join(sections)


class ContextBuilder:
    """Builds stage-scoped, budgeted context from shared memory."""

    def __init__(
        self,
        projects: ProjectRepository,
        artifacts: ArtifactRepository,
        *,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> None:
        self._projects = projects
        self._artifacts = artifacts
        self._token_budget = token_budget

    async def build(
        self,
        project_id: str,
        *,
        stage: LifecycleStage,
        role: AgentRole,
        include_types: set[ArtifactType] | None = None,
    ) -> ProjectContext:
        """Assemble the context for an agent about to work on ``stage``.

        Args:
            project_id: Project being worked on.
            stage: Stage the agent is performing. Only earlier stages are visible.
            role: Agent role, recorded on the context for traceability.
            include_types: Restrict to specific artifact types. Used when an agent
                needs a focused view — the QA agent wants acceptance criteria, not
                the entire architecture.

        Returns:
            Context within the token budget, with omissions listed.
        """
        project = await self._projects.get(project_id)
        upstream_stages = set(preceding_stages(stage))

        candidates = [
            artifact
            for artifact in await self._artifacts.list_for_project(project_id)
            if artifact.stage in upstream_stages
            and artifact.has_content
            and (include_types is None or artifact.type in include_types)
        ]

        ordered = sorted(candidates, key=self._priority)

        entries: list[ContextEntry] = []
        omitted: list[str] = []
        remaining = self._token_budget

        for artifact in ordered:
            resolved = await self._artifacts.get_version(artifact.id)
            body = resolved.version.body_markdown
            cost = len(body) // CHARS_PER_TOKEN

            if cost <= remaining:
                entries.append(
                    ContextEntry(
                        artifact=artifact,
                        body_markdown=body,
                        version=resolved.version.version,
                    )
                )
                remaining -= cost
                continue

            # Partially include when a meaningful amount still fits. A heading
            # with two lines under it is worse than nothing: it reads as complete
            # while being misleading.
            if remaining > 200:
                cutoff = remaining * CHARS_PER_TOKEN
                entries.append(
                    ContextEntry(
                        artifact=artifact,
                        body_markdown=body[:cutoff],
                        version=resolved.version.version,
                        included_fully=False,
                    )
                )
                remaining = 0
            else:
                omitted.append(artifact.title)

        if omitted:
            logger.warning(
                "Context budget exceeded; artifacts omitted",
                extra={
                    "project_id": project_id,
                    "stage": stage.value,
                    "omitted_count": len(omitted),
                },
            )

        return ProjectContext(
            project_id=project.id,
            project_name=project.name,
            project_description=project.description,
            stage=stage,
            role=role,
            entries=entries,
            omitted=omitted,
        )

    @staticmethod
    def _priority(artifact: Artifact) -> tuple[int, float]:
        """Order candidates by inclusion priority.

        Approved artifacts outrank drafts, and within a status the most recently
        updated comes first — so when the budget binds, what survives is the
        sanctioned and current view of the project.
        """
        status_rank = {
            ArtifactStatus.APPROVED: 0,
            ArtifactStatus.AWAITING_APPROVAL: 1,
            ArtifactStatus.DRAFT: 2,
            ArtifactStatus.REJECTED: 3,
        }
        return (status_rank[artifact.status], -artifact.updated_at.timestamp())
