"""Runs the AI Engineering Organization against the evaluation dataset.

The Evaluate stage of Mutagent's Agentic Development Lifecycle, which
`02_Proposed_Solution.md` requires this project to follow. Each brief is driven
through the full lifecycle exactly as a user would — create, advance, approve,
repeat — and scored deterministically.

Run from the repository root::

    apps/api/.venv/Scripts/python evaluation/run_evaluation.py

Runs on recorded fixtures by default, so it needs no API key and no network.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "evaluation"))

from scorers import Scorecard, score_project  # noqa: E402

from app.core.bootstrap import build_container  # noqa: E402
from app.core.config import (  # noqa: E402
    DatabaseSettings,
    Environment,
    LLMProvider,
    LLMSettings,
    ObservabilitySettings,
    Settings,
)
from app.db.session import Database  # noqa: E402
from app.domain.approvals import ApprovalStatus  # noqa: E402
from app.domain.projects import Project  # noqa: E402
from app.memory.repository import SharedMemory  # noqa: E402
from app.orchestration.runner import OrchestrationRunner  # noqa: E402

DATASET = ROOT / "evaluation" / "datasets" / "project_briefs.json"
SCORECARD_DIR = ROOT / "evaluation" / "scorecards"

#: A run that needs more passes than this is not converging, and reporting a
#: score for it would be reporting a score for a hung workflow.
MAX_PASSES = 12


async def evaluate_case(case: dict[str, Any]) -> Scorecard:
    """Drive one brief through the lifecycle and score the result."""
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url=f"sqlite+aiosqlite:///file:eval_{case['id']}?mode=memory&cache=shared&uri=true"
        ),
        llm=LLMSettings(
            provider=LLMProvider.FIXTURE,
            fixture_dir=str(ROOT / "apps" / "api" / "fixtures"),
        ),
        observability=ObservabilitySettings(log_level="ERROR", json_logs=False),
    )

    container = build_container(settings)
    await container.resolve(Database).create_schema()

    memory: SharedMemory = container.resolve(SharedMemory)  # type: ignore[type-abstract]
    runner: OrchestrationRunner = container.resolve(OrchestrationRunner)

    try:
        project = await memory.projects.create(
            Project(name=case["name"], description=case["description"])
        )

        for _ in range(MAX_PASSES):
            outcome = await runner.advance(project.id)

            if outcome.is_complete:
                break

            if outcome.awaiting_approval:
                # The human in the loop, played by the harness. Approving
                # everything is the optimistic path; it is what makes the score
                # a measure of the organization rather than of the reviewer.
                for request in await memory.approvals.list_for_project(
                    project.id, pending_only=True
                ):
                    request.status = ApprovalStatus.APPROVED
                    await runner.executive.record_decision(
                        request.id, ApprovalStatus.APPROVED, None
                    )
                continue

            if outcome.is_blocked:
                break

        scores = await score_project(memory, project.id)
        return Scorecard(case_id=case["id"], project_name=case["name"], scores=scores)

    finally:
        await container.aclose()


async def main() -> int:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    cards = [await evaluate_case(case) for case in dataset["cases"]]

    SCORECARD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    payload = {
        "dataset": dataset["name"],
        "generated_at": datetime.now(UTC).isoformat(),
        "overall": round(sum(card.overall for card in cards) / len(cards), 4) if cards else 0.0,
        "cases": [card.to_dict() for card in cards],
    }

    latest = SCORECARD_DIR / "latest.json"
    archived = SCORECARD_DIR / f"{timestamp}.json"
    for path in (latest, archived):
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    _print_report(payload)

    # Non-zero on regression, so this can gate a build. The threshold is
    # deliberately high: every scorer measures an obligation the specification
    # states, not a nice-to-have.
    return 0 if payload["overall"] >= 0.85 else 1


def _print_report(payload: dict[str, Any]) -> None:
    print(f"\nEvaluation — {payload['dataset']}")
    print("=" * 72)

    for case in payload["cases"]:
        print(f"\n{case['project_name']}  ({case['overall']:.0%})")
        for score in case["scores"]:
            mark = "PASS" if score["value"] >= 0.85 else "WARN" if score["value"] >= 0.5 else "FAIL"
            print(f"  {mark:5} {score['name']:28} {score['value']:>6.0%}  {score['detail']}")

    print("\n" + "=" * 72)
    print(f"Overall: {payload['overall']:.1%}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
