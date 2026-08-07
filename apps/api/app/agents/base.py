"""Base class for every engineering agent.

Defines one execution template that all seven MVP agents follow, so an agent
implementation supplies only what is genuinely specific to its role: its output
contract, its prompt, and how it names the artifacts it produces.

Everything that must be true of *every* agent lives here and cannot be skipped:

- an :class:`AgentRun` is recorded before reasoning starts, so an agent that
  fails or hangs is still visible in the Organization view rather than absent;
- reasoning is validated against a typed contract;
- **artifacts cannot be written without declaring their upstream** — the orphan
  guard ADR-0007 requires;
- trace edges are written from those declarations;
- events are published at each transition, feeding the timeline and live stream;
- failures mark the run failed and publish, rather than vanishing.

`05_AI_Agent_Architecture.md` requires each agent to be "an independent, reusable
module with clearly defined inputs, outputs, responsibilities, and communication
interfaces", and that agents not modify each other's state. Agents here reach
shared memory only through this base class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from app.agents.contracts import AgentOutput, AgentResult, ArtifactDraft, TraceLink
from app.agents.prompts import load_prompt
from app.core.logging import get_correlation_id, get_logger
from app.domain.agents import AgentRun, AgentRunStatus
from app.domain.artifacts import Artifact, ArtifactStatus, ArtifactVersion
from app.domain.errors import ValidationError
from app.domain.events import EventType, ProjectEvent
from app.domain.lifecycle import ROLE_TITLES, AgentRole, LifecycleStage
from app.domain.traceability import TraceEdge
from app.events.bus import EventBus
from app.llm.provider import (
    CompletionRequest,
    LLMProvider,
    Message,
    Role,
    StructuredResponse,
)
from app.memory.context_builder import ContextBuilder, ProjectContext
from app.memory.repository import SharedMemory

logger = get_logger(__name__)

SYSTEM_PROMPT = "engineering_organization"


class BaseAgent[TOutput: AgentOutput](ABC):
    """One engineering specialist.

    Subclasses declare their role, stage, output contract, and prompt, then
    implement :meth:`build_task` to describe the work. Execution, persistence,
    traceability, and observability are handled here.
    """

    #: The engineering role this agent fills.
    role: AgentRole

    #: The lifecycle stage it performs.
    stage: LifecycleStage

    #: Pydantic contract its reasoning is validated against.
    output_model: type[TOutput]

    #: Filename stem under ``app/agents/prompts/``.
    prompt_name: str

    def __init__(
        self,
        memory: SharedMemory,
        provider: LLMProvider,
        context_builder: ContextBuilder,
        events: EventBus,
    ) -> None:
        self._memory = memory
        self._provider = provider
        self._context = context_builder
        self._events = events

    @property
    def title(self) -> str:
        """Human-facing role name, used in events and the Organization view."""
        return ROLE_TITLES[self.role]

    @abstractmethod
    def build_task(self, context: ProjectContext) -> str:
        """Return the instruction describing this invocation's work.

        Receives the assembled context so the task can reference what is actually
        present — asking an agent to "revise the architecture" when none exists
        wastes an invocation.
        """

    def describe_task(self) -> str:
        """Return a short label for the Organization view. Overridable."""
        return f"{self.title} · {self.stage.value.replace('_', ' ')}"

    def compose_artifacts(
        self, output: TOutput, context: ProjectContext
    ) -> list[ArtifactDraft]:
        """Turn validated reasoning into the artifacts to persist.

        The default writes whatever the model emitted in ``output.artifacts``.

        Concrete agents override this to render their artifacts from the
        *structured* fields of their own contract instead. Two reasons: a
        rendered document then cannot drift from the data downstream agents
        read, and the model spends its output budget on engineering content
        rather than on re-formatting the same information as prose.
        """
        return list(output.artifacts)

    @staticmethod
    def _links(output: AgentOutput) -> list[TraceLink]:
        """Upstream declarations to attach to every artifact from this run."""
        return list(output.sources)

    async def run(self, project_id: str, *, feedback: str | None = None) -> AgentResult:
        """Execute one unit of engineering work.

        Args:
            project_id: Project to work on.
            feedback: Reviewer feedback from a rejected approval. Supplied on
                re-run so a rejection teaches rather than repeats.

        Returns:
            The persisted result.

        Raises:
            VictoriousError: on reasoning or persistence failure. The run is
                marked failed and an event published before the error propagates.
        """
        context = await self._context.build(project_id, stage=self.stage, role=self.role)

        run = await self._memory.runs.create(
            AgentRun(
                project_id=project_id,
                role=self.role,
                stage=self.stage,
                status=AgentRunStatus.ACTIVE,
                task=self.describe_task(),
                input_artifact_ids=context.artifact_ids,
                provider=self._provider.name,
                model=self._provider.model,
                correlation_id=get_correlation_id(),
            )
        )

        await self._publish(
            project_id,
            EventType.AGENT_STARTED,
            f"{self.title} started: {self.describe_task()}",
            {"run_id": run.id, "input_artifacts": len(context.artifact_ids)},
        )

        try:
            response = await self._reason(context, feedback)
            output = response.value
            drafts = self.compose_artifacts(output, context)
            artifact_ids, edge_ids = await self._persist(
                project_id, run, context, output, drafts
            )
        except Exception as exc:
            await self._fail(run, exc)
            raise

        run.status = AgentRunStatus.COMPLETED
        run.confidence = output.confidence
        run.reasoning_summary = output.reasoning
        run.output_artifact_ids = artifact_ids
        # Recorded per run because `12_Risk_Analysis.md` rates High Token
        # Consumption a Medium risk. Measuring it is the precondition for the
        # caching decision deferred in ADR-0005 — the intent is to decide from
        # data rather than assumption.
        run.token_usage = response.usage
        run.provider = response.provider
        run.model = response.model
        run.completed_at = datetime.now(UTC)
        await self._memory.runs.update(run)

        await self._publish(
            project_id,
            EventType.AGENT_COMPLETED,
            f"{self.title} completed with {len(artifact_ids)} artifact(s)",
            {
                "run_id": run.id,
                "confidence": output.confidence,
                "artifact_ids": artifact_ids,
                "concerns": len(output.concerns),
            },
        )

        if output.concerns:
            await self._publish(
                project_id,
                EventType.CONFLICT_DETECTED,
                f"{self.title} raised {len(output.concerns)} concern(s) about upstream work",
                {"run_id": run.id, "concerns": output.concerns},
            )

        logger.info(
            "Agent completed",
            extra={
                "role": self.role.value,
                "stage": self.stage.value,
                "run_id": run.id,
                "confidence": output.confidence,
                "artifacts": len(artifact_ids),
            },
        )

        return AgentResult(
            run_id=run.id,
            output=output,
            artifact_ids=artifact_ids,
            edge_ids=edge_ids,
        )

    async def _reason(
        self, context: ProjectContext, feedback: str | None
    ) -> StructuredResponse[TOutput]:
        """Invoke the provider and return the validated response.

        Returns the whole response rather than just its value, so token usage and
        the backend that actually served the request are recorded on the run.
        """
        messages = [Message(role=Role.USER, content=self._compose_user_message(context))]

        if feedback:
            messages.append(
                Message(
                    role=Role.USER,
                    content=(
                        "A reviewer rejected your previous output with this feedback:\n\n"
                        f"{feedback}\n\n"
                        "Produce a revised version that addresses it directly."
                    ),
                )
            )

        return await self._provider.complete_structured(
            CompletionRequest(
                system=f"{load_prompt(SYSTEM_PROMPT)}\n\n{load_prompt(self.prompt_name)}",
                messages=messages,
                # Keyed by role and stage so recorded fixtures are named after
                # the work they represent and can be read and edited by hand.
                fixture_key=f"{self.role.value}.{self.stage.value}",
                metadata={"role": self.role.value, "stage": self.stage.value},
            ),
            self.output_model,
        )

    def _compose_user_message(self, context: ProjectContext) -> str:
        """Combine assembled context with this invocation's task."""
        return f"{context.render()}\n\n---\n\n# Your task\n\n{self.build_task(context)}"

    async def _persist(
        self,
        project_id: str,
        run: AgentRun,
        context: ProjectContext,
        output: AgentOutput,
        drafts: list[ArtifactDraft],
    ) -> tuple[list[str], list[str]]:
        """Write artifacts and their trace edges.

        Returns:
            Artifact IDs and edge IDs created.
        """
        available = set(context.artifact_ids)
        artifact_ids: list[str] = []
        edge_ids: list[str] = []

        for draft in drafts:
            self._guard_against_orphan(draft, available)

            artifact = await self._memory.artifacts.create(
                Artifact(
                    project_id=project_id,
                    type=draft.type,
                    title=draft.title,
                    stage=self.stage,
                    owner_role=self.role,
                    status=ArtifactStatus.DRAFT,
                )
            )
            await self._memory.artifacts.append_version(
                artifact.id,
                ArtifactVersion(
                    artifact_id=artifact.id,
                    version=1,
                    body_markdown=draft.body_markdown,
                    content=dict(draft.content),
                    produced_by_run_id=run.id,
                    summary=draft.summary,
                    confidence=output.confidence,
                ),
            )
            artifact_ids.append(artifact.id)

            for link in draft.derived_from:
                upstream = await self._memory.artifacts.get(link.upstream_artifact_id)
                edge = await self._memory.traces.add_edge(
                    TraceEdge(
                        project_id=project_id,
                        upstream_artifact_id=upstream.id,
                        downstream_artifact_id=artifact.id,
                        kind=link.kind,
                        # The version actually consumed. ADR-0007: this is what
                        # makes staleness computable when the upstream advances.
                        upstream_version=upstream.current_version,
                        created_by_run_id=run.id,
                        rationale=link.rationale,
                    )
                )
                edge_ids.append(edge.id)

            await self._publish(
                project_id,
                EventType.ARTIFACT_CREATED,
                f"{self.title} produced {draft.title}",
                {
                    "artifact_id": artifact.id,
                    "artifact_type": draft.type.value,
                    "upstream_count": len(draft.derived_from),
                },
            )

        return artifact_ids, edge_ids

    def _guard_against_orphan(self, draft: ArtifactDraft, available: set[str]) -> None:
        """Reject artifacts that fail to declare their upstream.

        The orphan guard ADR-0007 identified as necessary. An artifact produced
        from context but declaring no sources is invisible to impact analysis, so
        a later requirement change would silently fail to flag it — precisely the
        failure this platform exists to prevent. Better to fail the run.

        The first stage legitimately has no upstream, which is why the guard
        triggers on context being present rather than unconditionally.
        """
        if not available:
            return

        if not draft.derived_from:
            raise ValidationError(
                "Artifact declares no upstream sources despite being produced from context",
                details={
                    "artifact_title": draft.title,
                    "role": self.role.value,
                    "available_upstream": sorted(available),
                },
            )

        unknown = [
            link.upstream_artifact_id
            for link in draft.derived_from
            if link.upstream_artifact_id not in available
        ]
        if unknown:
            raise ValidationError(
                "Artifact cites upstream sources that were not in the agent's context",
                details={
                    "artifact_title": draft.title,
                    "unknown_upstream": unknown,
                    "available_upstream": sorted(available),
                },
            )

    async def _fail(self, run: AgentRun, exc: Exception) -> None:
        """Mark the run failed and publish, so a failure is visible not silent."""
        run.status = AgentRunStatus.FAILED
        run.error = f"{type(exc).__name__}: {exc}"
        run.completed_at = datetime.now(UTC)
        await self._memory.runs.update(run)

        await self._publish(
            run.project_id,
            EventType.AGENT_FAILED,
            f"{self.title} failed: {type(exc).__name__}",
            {"run_id": run.id, "error_type": type(exc).__name__},
        )

        logger.exception(
            "Agent failed",
            extra={"role": self.role.value, "stage": self.stage.value, "run_id": run.id},
        )

    async def _publish(
        self,
        project_id: str,
        event_type: EventType,
        summary: str,
        payload: dict[str, object],
    ) -> None:
        await self._events.publish(
            ProjectEvent(
                project_id=project_id,
                type=event_type,
                stage=self.stage,
                role=self.role,
                summary=summary,
                payload=payload,
                correlation_id=get_correlation_id(),
            )
        )
