"""Writes the demo fixture corpus.

The organization needs recorded reasoning to run without a provider (ADR-0008).
This generates that corpus from the worked payloads in
``tests/test_organization.py`` — the same data the end-to-end test verifies —
so the offline demo and the test suite cannot drift apart.

Once a live provider has been run with ``VICTORIOUS_LLM__RECORD_FIXTURES=true``,
those recordings replace these and this script becomes a fallback.

Run from ``apps/api``::

    python scripts/generate_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_organization import PAYLOADS  # noqa: E402

from app.llm.fixture_provider import UPSTREAM_TOKEN  # noqa: E402

FIXTURE_DIR = ROOT / "fixtures"

#: Written by the Executive AI when it raises an approval gate. Keyed by gate
#: kind, matching `ExecutiveAI._narrate`'s fixture key.
GATE_NARRATIONS: dict[str, dict[str, str]] = {
    "requirements": {
        "title": "Approve the requirements before the architecture is designed",
        "what_changed": (
            "The Product Manager defined the functional and non-functional "
            "requirements, user stories, and acceptance criteria. The Business "
            "Analyst validated them and flagged access control as underspecified."
        ),
        "why": (
            "Everything the architect designs derives from these requirements. "
            "Approving them here prevents a design being built on scope you have "
            "not reviewed."
        ),
    },
    "architecture": {
        "title": "Approve the architecture before work is planned against it",
        "what_changed": (
            "The Software Architect proposed a modular monolith with patients and "
            "scheduling components, selected PostgreSQL over MongoDB, and defined "
            "the API contract and data model."
        ),
        "why": (
            "The implementation plan and the generated scaffold both derive from "
            "this design. The technology selection in particular is expensive to "
            "reverse once code exists."
        ),
    },
    "code_generation": {
        "title": "Authorise code generation",
        "what_changed": (
            "The implementation plan sequences the approved architecture into "
            "dependency-ordered tasks, starting with the data model and the "
            "booking conflict logic."
        ),
        "why": (
            "This is the last gate before the organization writes the repository "
            "scaffold. Everything generated will trace back to this plan."
        ),
    },
}


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    for key, payload in PAYLOADS.items():
        value = {
            **payload,
            "reasoning": _reasoning_for(key),
            "confidence": 0.86,
            # Expanded at replay time to the artifact IDs actually present in the
            # agent's context — artifact IDs are per-project, so a recording
            # cannot name them.
            "sources": UPSTREAM_TOKEN,
            "artifacts": [],
            "concerns": _concerns_for(key),
            "requires_approval": key == "software_architect.architecture",
            "approval_reason": (
                "Technology selection commits the project to PostgreSQL."
                if key == "software_architect.architecture"
                else ""
            ),
        }
        _write(
            f"{key}.json",
            {"value": value, "usage": {"input_tokens": 2400, "output_tokens": 1800}},
        )
        written += 1

    for gate, narration in GATE_NARRATIONS.items():
        _write(
            f"executive.gate.{gate}.json",
            {"value": narration, "usage": {"input_tokens": 900, "output_tokens": 220}},
        )
        written += 1

    print(f"Wrote {written} fixtures to {FIXTURE_DIR}")
    return 0


def _reasoning_for(key: str) -> str:
    reasoning = {
        "product_manager.requirement_discovery": (
            "The brief names patients, appointments, billing, doctors, and operations. "
            "I scoped the MVP to patient registration and appointment booking because "
            "billing depends on both and neither exists yet. Clinical data drove the "
            "confidentiality requirement; the regulatory regime is not stated, so I "
            "raised it as an open question rather than assuming one."
        ),
        "business_analyst.business_validation": (
            "FR-01 and FR-02 are specific and testable. NFR-01 names no roles and no "
            "permission model, so two engineers would implement it differently — I "
            "questioned it rather than letting the architect guess. The regulatory "
            "exposure follows from the domain and belongs on the risk register."
        ),
        "software_architect.architecture": (
            "One team, no independent scaling requirement, and two closely coupled "
            "domains: a modular monolith with clean seams is correct here, and "
            "distribution would be a cost with no matching benefit. PostgreSQL over "
            "MongoDB because appointments need transactional integrity across tables; "
            "the cost is that flexible clinical notes need a JSONB column."
        ),
        "software_architect.development_planning": (
            "The patient schema comes first because everything references it, and the "
            "booking conflict logic second because it is the least certain part of the "
            "design. Deferring it would mean discovering a design problem at the point "
            "where changing it is most expensive."
        ),
        "full_stack_engineer.implementation": (
            "I wrote the patient model because it is where the approved data design "
            "becomes concrete, and left package manifests and lint configuration to the "
            "tree. Authentication and migrations are genuinely absent and recorded as "
            "such — this is a scaffold, not a running system."
        ),
        "qa_engineer.testing": (
            "Double booking is the highest-risk behaviour in the design, so it gets the "
            "first integration test. FR-01 has no acceptance criteria written against "
            "it, so I reported it uncovered rather than inventing an interpretation. "
            "The scaffold has no patient endpoint despite FR-01 being a must — that is "
            "a real defect, not speculation."
        ),
        "documentation.documentation": (
            "I documented what the organization actually decided: the modular monolith "
            "and why, the PostgreSQL trade-off, and the endpoints in the approved "
            "contract. The README states that this is a scaffold, because the QA "
            "coverage report and the engineer's own notes both say so."
        ),
        "documentation.deployment_preparation": (
            "The plan follows the approved PostgreSQL and container decisions and "
            "introduces no infrastructure the organization did not choose. Environment "
            "variables are listed by name and purpose only. Authentication being absent "
            "and FR-01 having no endpoint genuinely block a production release."
        ),
    }
    return reasoning.get(key, "Completed this stage from the upstream context provided.")


def _concerns_for(key: str) -> list[str]:
    """Concerns raised about upstream work.

    Populated for the stages where the specification expects an agent to push
    back, so the demo shows cross-validation actually happening rather than every
    agent silently agreeing.
    """
    concerns = {
        "software_architect.architecture": [
            "NFR-01 still names no roles, so the access-control design rests on an "
            "assumption rather than a stated requirement."
        ],
        "qa_engineer.testing": [
            "FR-01 has no acceptance criteria, so patient registration cannot be "
            "verified against anything."
        ],
    }
    return concerns.get(key, [])


def _write(name: str, payload: dict[str, object]) -> None:
    path = FIXTURE_DIR / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
