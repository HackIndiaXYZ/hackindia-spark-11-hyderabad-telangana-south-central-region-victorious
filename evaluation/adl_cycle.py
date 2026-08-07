"""Reproduces the ADL cycle documented in `optimization-report.md`.

Mutagent's Agentic Development Lifecycle is Specification, Build, Evaluation,
Diagnosis, Optimization. `02_Proposed_Solution.md` requires this project to be
developed through it and to produce the evidence.

This script is the Evaluation step of one such cycle, run against both the
diagnosed defect and the optimization, so the improvement is a measurement rather
than a claim.

**The specification under test:** an artifact must stop being reported as out of
date once it has been rebuilt against the current version of its upstream.

**The defect:** trace edges are immutable, so a rebuilding agent *adds* a new
edge rather than updating the old one. The superseded edge still cited the old
upstream version, so the artifact stayed stale no matter how many times it was
regenerated — and re-synchronisation could never converge.

**The optimization:** staleness considers only the most recent declaration of
each dependency. Superseded edges remain in the graph as history.

Run from the repository root::

    apps/api/.venv/Scripts/python evaluation/adl_cycle.py
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
from app.domain.artifacts import ArtifactType, ArtifactVersion  # noqa: E402
from app.domain.projects import Project  # noqa: E402
from app.domain.traceability import current_edges, stale_edges  # noqa: E402
from app.memory.repository import SharedMemory  # noqa: E402
from app.orchestration.runner import OrchestrationRunner  # noqa: E402

OUTPUT = ROOT / "evaluation" / "scorecards" / "adl_cycle.json"
MAX_PASSES = 14


async def run_cycle() -> dict[str, Any]:
    settings = Settings(
        environment=Environment.TEST,
        database=DatabaseSettings(
            url="sqlite+aiosqlite:///file:adlcycle?mode=memory&cache=shared&uri=true"
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
            Project(
                name="Hospital Management System",
                description="Managing patients, appointments, billing, doctors, and operations.",
            )
        )

        await _drive(memory, runner, project.id)
        baseline = await _measure(memory, project.id)

        # The scenario the platform exists for: a requirement changes after
        # delivery.
        prd = (
            await memory.artifacts.list_for_project(
                project.id, artifact_type=ArtifactType.PRD
            )
        )[0]
        await memory.artifacts.append_version(
            prd.id,
            ArtifactVersion(
                artifact_id=prd.id,
                version=1,
                body_markdown="# Product Requirements (revised)\n\nBilling is its own requirement.",
                summary="Split billing out",
            ),
        )
        after_change = await _measure(memory, project.id)

        # Re-synchronise: the organization reruns the affected specialists.
        await _drive(memory, runner, project.id)
        after_resync = await _measure(memory, project.id)

        return {
            "cycle": "traceability-convergence",
            "generated_at": datetime.now(UTC).isoformat(),
            "specification": (
                "An artifact must stop being reported as out of date once it has "
                "been rebuilt against the current version of its upstream."
            ),
            "measurements": {
                "baseline_after_delivery": baseline,
                "after_requirement_change": after_change,
                "after_resynchronisation": after_resync,
            },
            "result": {
                "optimized_converges": after_resync["stale_current_declaration"] == 0,
                "defect_would_not_converge": after_resync["stale_all_edges"] > 0,
                "stale_before_fix": after_resync["stale_all_edges"],
                "stale_after_fix": after_resync["stale_current_declaration"],
            },
        }
    finally:
        await container.aclose()


async def _drive(memory: SharedMemory, runner: OrchestrationRunner, project_id: str) -> None:
    """Advance to completion, approving every gate."""
    for _ in range(MAX_PASSES):
        outcome = await runner.advance(project_id)

        if outcome.is_complete or outcome.is_blocked:
            return

        if outcome.awaiting_approval:
            for request in await memory.approvals.list_for_project(
                project_id, pending_only=True
            ):
                await runner.executive.record_decision(
                    request.id, ApprovalStatus.APPROVED, None
                )


async def _measure(memory: SharedMemory, project_id: str) -> dict[str, int]:
    """Count stale derivations both ways.

    ``stale_all_edges`` reproduces the defect: every edge ever declared is
    evaluated, including superseded ones. ``stale_current_declaration`` is the
    optimized behaviour. Measuring both from the same graph is what makes the
    improvement a number rather than an assertion.
    """
    edges = await memory.traces.list_for_project(project_id)
    versions = await memory.artifacts.current_versions(project_id)

    return {
        "total_edges": len(edges),
        "current_declarations": len(current_edges(edges)),
        "stale_all_edges": len(
            [
                edge
                for edge in edges
                if (current := versions.get(edge.upstream_artifact_id)) is not None
                and current > edge.upstream_version
            ]
        ),
        "stale_current_declaration": len(stale_edges(edges, versions)),
    }


async def main() -> int:
    report = await run_cycle()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    measurements = report["measurements"]
    result = report["result"]

    print("\nADL cycle — traceability convergence")
    print("=" * 72)
    print(f"\nSpecification: {report['specification']}\n")

    header = f"{'stage':<32}{'edges':>8}{'current':>10}{'stale (defect)':>16}{'stale (fixed)':>15}"
    print(header)
    print("-" * len(header))
    for label, data in measurements.items():
        print(
            f"{label:<32}{data['total_edges']:>8}{data['current_declarations']:>10}"
            f"{data['stale_all_edges']:>16}{data['stale_current_declaration']:>15}"
        )

    print("\n" + "=" * 72)
    print(f"Optimized behaviour converges : {result['optimized_converges']}")
    print(f"Defect would not converge     : {result['defect_would_not_converge']}")
    print(
        f"Stale derivations after rebuild: {result['stale_before_fix']} (defect) "
        f"-> {result['stale_after_fix']} (optimized)"
    )
    print(f"\nWritten to {OUTPUT.relative_to(ROOT)}")

    return 0 if result["optimized_converges"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
