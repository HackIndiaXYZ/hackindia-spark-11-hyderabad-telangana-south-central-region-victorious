"""Seeds the demonstration project.

`13_Demo_and_Pitch.md` requires a polished end-to-end demonstration, and
`12_Risk_Analysis.md` rates Model Availability a Medium risk. A demo that opens
on an empty dashboard and depends on a live provider to have anything to show is
one network problem away from failing in front of judges.

This drives the hospital scenario from `13_Demo_and_Pitch.md` through the full
lifecycle on recorded fixtures, so every view has real content the moment the
workspace opens — and the presenter can still create a second project live to
show the organization working.

Run from ``apps/api``::

    .venv/Scripts/python scripts/seed_demo.py            # completed project
    .venv/Scripts/python scripts/seed_demo.py --at-gate  # stopped at the first gate
    .venv/Scripts/python scripts/seed_demo.py --reset    # wipe and reseed
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import build_container  # noqa: E402
from app.core.config import LLMProvider, LLMSettings, Settings, get_settings  # noqa: E402
from app.db.session import Database  # noqa: E402
from app.domain.approvals import ApprovalStatus  # noqa: E402
from app.domain.projects import Project  # noqa: E402
from app.memory.repository import SharedMemory  # noqa: E402
from app.orchestration.runner import OrchestrationRunner  # noqa: E402

DEMO_NAME = "Hospital Management System"
DEMO_DESCRIPTION = (
    "A platform for managing patients, appointments, billing, doctors, "
    "and hospital operations."
)

#: A lifecycle that needs more passes than this is not converging, and a demo
#: seeded from a hung workflow is worse than no seed.
MAX_PASSES = 14


async def seed(*, stop_at_gate: bool, reset: bool) -> int:
    settings = _settings()
    container = build_container(settings)
    database = container.resolve(Database)

    await database.create_schema()

    memory: SharedMemory = container.resolve(SharedMemory)  # type: ignore[type-abstract]
    runner: OrchestrationRunner = container.resolve(OrchestrationRunner)

    try:
        existing = [
            project
            for project in await memory.projects.list_all(limit=100)
            if project.name == DEMO_NAME
        ]

        if existing and not reset:
            print(f"Demo project already seeded: {existing[0].id}")
            print("Pass --reset to wipe and reseed.")
            return 0

        if existing and reset:
            # Deleting is out of scope for the memory protocol — this is a demo
            # helper, not a data-management feature. Removing the database file
            # is the honest way to reset, and the caller is told so.
            print("Reset requested. Delete apps/api/victorious.db and run again.")
            return 1

        project = await memory.projects.create(
            Project(name=DEMO_NAME, description=DEMO_DESCRIPTION)
        )
        print(f"Created {project.name} ({project.id})")

        for pass_number in range(1, MAX_PASSES + 1):
            outcome = await runner.advance(project.id)

            if outcome.executed_stages:
                stages = ", ".join(stage.value for stage in outcome.executed_stages)
                print(f"  pass {pass_number}: {stages}")

            if outcome.is_complete:
                break

            if outcome.is_blocked:
                print(f"  blocked: {outcome.halt_reason}")
                return 1

            if outcome.awaiting_approval:
                pending = await memory.approvals.list_for_project(
                    project.id, pending_only=True
                )

                if stop_at_gate:
                    print(f"  stopped at gate: {pending[0].title}")
                    break

                for request in pending:
                    await runner.executive.record_decision(
                        request.id, ApprovalStatus.APPROVED, None
                    )
                    print(f"  approved: {request.kind.value}")

        await _report(memory, project.id)
        return 0

    finally:
        await container.aclose()


async def _report(memory: SharedMemory, project_id: str) -> None:
    project = await memory.projects.get(project_id)
    artifacts = [a for a in await memory.artifacts.list_for_project(project_id) if a.has_content]
    edges = await memory.traces.list_for_project(project_id)
    runs = await memory.runs.list_for_project(project_id)
    approvals = await memory.approvals.list_for_project(project_id)
    events = await memory.events.list_for_project(project_id, limit=1000)

    print()
    print(f"  stages    {len(project.completed_stages)}/8 complete")
    print(f"  artifacts {len(artifacts)}")
    print(f"  edges     {len(edges)}")
    print(f"  agent runs {len(runs)}")
    print(f"  approvals {len(approvals)}")
    print(f"  events    {len(events)}")
    print()
    print(f"Open http://localhost:3000/projects/{project_id}")


def _settings() -> Settings:
    """Demo settings: recorded fixtures, so seeding needs no network.

    The configured provider is deliberately overridden rather than inherited. A
    seed that quietly spent API credits — or failed because a key was missing —
    would defeat the purpose of having a seed at all.
    """
    base = get_settings()
    return base.model_copy(
        update={
            "llm": LLMSettings(
                provider=LLMProvider.FIXTURE,
                fixture_dir=str(ROOT / "fixtures"),
            )
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the demonstration project.")
    parser.add_argument(
        "--at-gate",
        action="store_true",
        help="Stop at the first approval gate, so the demo opens on a decision.",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Explain how to wipe and reseed."
    )
    args = parser.parse_args()

    return asyncio.run(seed(stop_at_gate=args.at_gate, reset=args.reset))


if __name__ == "__main__":
    raise SystemExit(main())
