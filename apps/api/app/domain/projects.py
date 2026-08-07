"""Projects and their lifecycle state."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.domain.ids import IdPrefix, new_id
from app.domain.lifecycle import LifecycleStage, StageStatus


class StageState(BaseModel):
    """Progress of one lifecycle stage within a project.

    Mutable rather than frozen: a stage genuinely moves backwards when a reviewer
    rejects its output, and the organization reruns it.
    """

    stage: LifecycleStage
    status: StageStatus = StageStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return self.status is StageStatus.COMPLETED


class Project(BaseModel):
    """A software engineering project.

    Creation asks only for a name and a description. `07_System_Architecture.md`
    is explicit: "Every project begins with minimal onboarding by asking only for
    a project name and a brief description... Rather than forcing users through a
    predefined interview before project creation, the platform should gradually
    collect engineering knowledge while continuously updating project artifacts."

    Everything else on this model is produced by the organization, not asked of
    the user.
    """

    id: str = Field(default_factory=lambda: new_id(IdPrefix.PROJECT))
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(
        min_length=1,
        max_length=4000,
        description="The idea, in the user's own words. The only required input.",
    )

    current_stage: LifecycleStage = LifecycleStage.IDEA
    stages: list[StageState] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def stage_state(self, stage: LifecycleStage) -> StageState | None:
        """Return the recorded state of a stage, if it has one."""
        return next((state for state in self.stages if state.stage is stage), None)

    @property
    def completed_stages(self) -> list[LifecycleStage]:
        return [state.stage for state in self.stages if state.is_complete]
