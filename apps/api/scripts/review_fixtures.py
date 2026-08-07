"""Recorded review judgements, one per artifact type.

Written by ``generate_fixtures.py`` so the review layer produces real prose and a
real score spread with no network (ADR-0008).

Each entry names something concrete in the artifact it reviews — `FR-01`, the
PostgreSQL-over-MongoDB trade-off, `TC-01` — because a finding that could apply
to any project is not a finding. The adjustments are mostly small or zero: the
structural score already reflects most artifacts, and a reviewer that nudges
every score teaches the reader to ignore the number.

Replaced wholesale the first time the reviewer runs against a live provider with
``VICTORIOUS_LLM__RECORD_FIXTURES=true``.
"""

from __future__ import annotations

from typing import Any

REVIEW_JUDGEMENTS: dict[str, dict[str, Any]] = {
    "prd": {
        "summary": (
            "Requirements are specific and prioritised; access control is named but not defined."
        ),
        "score_adjustment": 2,
        "strengths": [
            "FR-02 states the double-booking rejection explicitly — the case most likely to be "
            "implemented wrongly.",
            "Every requirement carries a rationale, so a later reader can tell why it exists.",
            "`out_of_scope` names insurance claims, which makes the MVP boundary checkable.",
        ],
        "weaknesses": [
            "NFR-01 requires confidentiality but names no roles or permission model, so two "
            "engineers would implement it differently.",
        ],
        "suggestions": [
            "Define the role set on NFR-01 before the architect designs authorisation from it.",
        ],
    },
    "user_stories": {
        "summary": "US-01 is testable end to end; coverage of the billing workflow is absent.",
        "score_adjustment": 0,
        "strengths": [
            "US-01's acceptance criteria state both the success and the conflict path, so QA can "
            "write against them directly.",
        ],
        "weaknesses": [
            "Billing appears in the project brief but no story covers it, so it will not reach the "
            "architecture.",
        ],
        "suggestions": ["Add a billing story or record billing as explicitly deferred."],
    },
    "acceptance_criteria": {
        "summary": "Criteria are binary and traceable; FR-01 has none.",
        "score_adjustment": -3,
        "strengths": ["Each criterion maps to a requirement id, so coverage is measurable."],
        "weaknesses": [
            "FR-01 (patient registration) has no acceptance criteria at all, which is why QA later "
            "reports it untestable.",
        ],
        "suggestions": ["Write criteria for FR-01 covering duplicate records and required fields."],
    },
    "business_analysis": {
        "summary": "Genuine scrutiny — questions NFR-01 rather than validating everything.",
        "score_adjustment": 4,
        "strengths": [
            "Questions NFR-01 instead of rubber-stamping it; an analyst that validates everything "
            "provides no signal.",
            "The regulatory risk follows from the domain rather than being generic project risk.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "gap_analysis": {
        "summary": "The access-control gap is correctly identified and correctly rated high.",
        "score_adjustment": 0,
        "strengths": [
            "The recommendation is an action — define roles — not a restatement of the gap."
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "risk_register": {
        "summary": "Domain-specific risk with a real mitigation, though thin at one entry.",
        "score_adjustment": -2,
        "strengths": [
            "The certification risk is specific to clinical data, not boilerplate schedule risk."
        ],
        "weaknesses": [
            "A single risk under-represents a system handling patient data and payments."
        ],
        "suggestions": ["Add data-retention and third-party-integration risks."],
    },
    "system_architecture": {
        "summary": (
            "The modular-monolith choice is argued from the requirements rather than assumed."
        ),
        "score_adjustment": 5,
        "strengths": [
            "The style rationale reasons from team size and coupling instead of reaching for "
            "microservices.",
            "Every component links to the requirement it serves, so nothing exists without a "
            "reason.",
        ],
        "weaknesses": [
            "Authorisation is listed as a security note but no component owns it, leaving NFR-01 "
            "unassigned.",
        ],
        "suggestions": [
            "Assign authorisation to a component or state that it is cross-cutting middleware."
        ],
    },
    "technology_decision": {
        "summary": "Reviewable: names the rejected alternative and the cost accepted.",
        "score_adjustment": 6,
        "strengths": [
            "PostgreSQL over MongoDB is argued from transactional integrity across appointment "
            "tables.",
            "The trade-off is stated — clinical notes need a JSONB column — so a human can approve "
            "it on its merits.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "api_contract": {
        "summary": "Correct HTTP semantics; the requirement set is only partly served.",
        "score_adjustment": -4,
        "strengths": ["POST /api/v1/appointments uses the right verb and links to FR-02."],
        "weaknesses": [
            "No endpoint serves FR-01, so patient registration is unreachable through the API.",
            "No error responses are described for the conflict path FR-02 requires.",
        ],
        "suggestions": [
            "Add the patient registration endpoint and document the 409 conflict response.",
        ],
    },
    "database_schema": {
        "summary": "Entities and relationships are sound; indexing and retention are unaddressed.",
        "score_adjustment": -2,
        "strengths": ["The patient-to-appointment relationship is stated explicitly."],
        "weaknesses": [
            "No index is defined for the slot lookup the booking conflict check depends on.",
            "Nothing addresses retention for clinical data despite the regulatory risk on the "
            "register.",
        ],
        "suggestions": [
            "Add a uniqueness constraint on (doctor, slot) to enforce FR-02 in the schema."
        ],
    },
    "implementation_plan": {
        "summary": "Sequenced by risk — the schema first, the conflict logic second.",
        "score_adjustment": 3,
        "strengths": [
            "T-02 tackles booking conflicts early rather than deferring the least certain work.",
            "Dependencies are real and acyclic.",
        ],
        "weaknesses": ["No task covers the FR-01 endpoint the API contract also omits."],
        "suggestions": [
            "Add a task for patient registration so the gap does not reach implementation."
        ],
    },
    "repository_structure": {
        "summary": "Honest about scope — names what it does not implement.",
        "score_adjustment": 4,
        "strengths": [
            "`not_implemented` names authentication and migrations rather than leaving a reviewer "
            "to discover them.",
            "The layout mirrors the approved components.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "source_file": {
        "summary": "Realises the approved model; no validation or error handling.",
        "score_adjustment": -3,
        "strengths": ["Field types match the approved schema."],
        "weaknesses": ["No validation on the fields NFR-01 implies should be constrained."],
        "suggestions": ["Add field validation and a docstring naming the requirement it serves."],
    },
    "test_plan": {
        "summary": "Correctly targets the highest-risk behaviour first.",
        "score_adjustment": 2,
        "strengths": [
            "The strategy names booking conflicts as the priority, matching where the design is "
            "least certain.",
            "The scaffold defect it reports — no FR-01 endpoint — is real and verifiable.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "test_cases": {
        "summary": "TC-01 is implementable as written and traced to its criterion.",
        "score_adjustment": 0,
        "strengths": ["Given/when/then is concrete enough to implement without asking a question."],
        "weaknesses": ["Only one case, so most of the requirement set is unexercised."],
        "suggestions": ["Add cases for invalid input and unauthorised access."],
    },
    "coverage_report": {
        "summary": "Reports the gap rather than hiding it behind a percentage.",
        "score_adjustment": 5,
        "strengths": [
            "FR-01 is reported uncovered with the reason — no acceptance criteria — which is "
            "actionable.",
            "Coverage is measured per requirement, so a gap is visible as a gap.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
    "readme": {
        "summary": "Accurate about the scaffold; light on how to run it.",
        "score_adjustment": 0,
        "strengths": [
            "States plainly that this is a scaffold, consistent with the engineer's own notes."
        ],
        "weaknesses": ["No concrete setup commands, so a new reader cannot get started."],
        "suggestions": ["Add the exact commands to install dependencies and start the service."],
    },
    "api_documentation": {
        "summary": "Derived from the approved contract; inherits its gaps.",
        "score_adjustment": -2,
        "strengths": ["Documents the endpoint that exists rather than one that does not."],
        "weaknesses": [
            "No error responses documented, so a client cannot handle the conflict path."
        ],
        "suggestions": ["Document status codes, including the 409 the booking conflict produces."],
    },
    "architecture_document": {
        "summary": "Explains the reasoning rather than restating the component table.",
        "score_adjustment": 4,
        "strengths": [
            "Explains why a modular monolith was chosen — the part a reader cannot "
            "recover from the code.",
        ],
        "weaknesses": [
            "Does not say what would have to change if the scale assumption proved wrong."
        ],
        "suggestions": ["Record the signal that would justify splitting the monolith."],
    },
    "developer_guide": {
        "summary": "Covers setup; thin on the gotchas that matter most.",
        "score_adjustment": -3,
        "strengths": ["Names the migration ordering requirement."],
        "weaknesses": [
            "No gotchas beyond migrations, and gotchas are the highest-value content in this "
            "document.",
        ],
        "suggestions": [
            "Document the booking conflict semantics, which are easy to implement wrongly."
        ],
    },
    "changelog": {
        "summary": "Factual and appropriately brief for an initial entry.",
        "score_adjustment": 0,
        "strengths": ["States what was built without overstating completeness."],
        "weaknesses": [],
        "suggestions": [],
    },
    "deployment_plan": {
        "summary": "Names what blocks production instead of implying readiness.",
        "score_adjustment": 5,
        "strengths": [
            "`outstanding` names missing authentication and the FR-01 gap as real "
            "release blockers.",
            "Environment variables are listed by name and purpose with no values.",
            "The rollback note distinguishes what a redeploy cannot undo.",
        ],
        "weaknesses": [],
        "suggestions": [],
    },
}
