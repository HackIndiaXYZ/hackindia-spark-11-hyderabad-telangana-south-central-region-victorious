# ADR-0013 — Engineering review runs natively; Helix drives its lifecycle

- **Status:** Accepted
- **Date:** 2026-08-08
- **Milestone:** 11 (post-MVP)

## Context

Mutagent's Helix package was installed into the repository as the ADL (agent
development lifecycle) conductor — spec → build → evaluate → diagnose → optimize.
The obvious reading is that Helix should review the organization's output at
runtime: every specialist produces an artifact, Helix scores it, the workspace
shows the scores.

Inspecting the package rules that out. Helix ships **zero `.py` files**, every
package is `"private": true`, there is no server, daemon, HTTP surface, or
importable library, and its orchestrator is a **markdown agent definition** meant
to be adopted by a coding agent at a developer's keyboard. There is nothing for
a FastAPI request handler to call.

This matches the specification rather than contradicting it.
`07_System_Architecture.md` states plainly that Mutagent is not part of the
runtime execution path, and `15_Development_Guidelines.md` treats it as
development tooling.

Separately, the platform needed a quality signal it did not have. Confidence
scores are self-reported by the agent that produced the work —
`12_Risk_Analysis.md` rates AI Hallucination a High risk, and an agent's opinion
of its own output is the weakest possible mitigation for it.

## Decision

### The reviewer is a first-party layer, not a Helix call

`app/review/` is a sibling of `app/agents/`, built on the same `LLMProvider`
abstraction the specialists use. Nothing in it imports Mutagent, and
`tests/test_architecture.py` enforces that boundary alongside the others.

Helix keeps the role the documentation gives it: at development time it specs,
evaluates, and optimizes this reviewer. That is a genuine use of the ADL, and it
is honest about where the tool sits.

### The score is mostly measured, and reasoning is capped

Five deterministic checks over the artifact and its trace edges carry the full
100 points:

| Check | Points | What it measures |
| --- | ---: | --- |
| Traceability | 25 | Declares upstream, so impact analysis can reach it |
| Structured content | 25 | Downstream agents can read fields, not prose |
| Substance | 20 | Not a heading with nothing under it |
| Confidence | 15 | What the producing agent reported |
| Type completeness | 15 | Carries the fields its artifact type requires |

A reasoning pass then reads the artifact **and the evidence from the checks**,
and may move the score by at most **±12**, in writing.

The cap is the whole design. A model can sharpen a judgement; it cannot overturn
a measured fact, and it cannot manufacture a high score for an artifact that
declares no upstream and carries no structured content. It also keeps the demo
honest: on recorded fixtures a purely generative reviewer would score every
artifact alike, and the number would be theatre. Structural checks read the
actual artifact, so scores genuinely differ — the reference project spans 81–100
across eleven distinct values.

Every finding records whether it came from a `check` or from `reasoning`, and the
workspace labels them, because only one of the two is reproducible.

### Reviewing is fail-open

If the provider errors, times out, or returns an unusable judgement, the
structural review stands and the agent run completes normally. An organization
that stops working because its reviewer is unavailable would be worse than one
that does not review at all. `reasoning_applied` records that no model
contributed, so the workspace shows an honest score rather than a
confident-looking one produced by nothing.

### The Executive consults reviews, advisory by default

Before committing a specialist to build on upstream work, the Executive AI checks
the reviews of the artifacts **that stage actually reads** — scoped to
`STAGE_INPUTS`, so a weak deployment plan cannot block architecture.

Default is advisory: it logs and proceeds. `13_Demo_and_Pitch.md` favours a
demonstration that runs, and a quality score is a signal to weigh, not an
authority to obey. `VICTORIOUS_REVIEW__BLOCKING=true` promotes it to a gate for
teams that want one.

### Reviews are stored per artifact **version**

`(artifact_id, artifact_version)` is unique. A review therefore travels with the
version it judged, exactly as ADR-0007 keeps versions readable as the agent that
consumed them saw them. A human revision produces a version no agent reviewed, so
its review is `null` — a real state, not an error, and not something to paper
over by showing the previous version's score.

## Consequences

**Positive**

- A quality signal that does not depend on an agent grading itself.
- Scores differ across artifacts because most of the number is measured, so the
  review is evidence rather than decoration.
- The Helix relationship is stated accurately in the product surface instead of
  being implied by a label — the "Helix Review" page says the reviewer runs
  natively and Helix drives its development lifecycle.
- Existing behaviour is untouched: the review layer is optional at every seam
  (`BaseAgent` takes `reviewer: EngineeringReviewer | None`), and all 282 tests
  pass, including the architecture-boundary suite.

**Negative**

- The check weights are judgement calls, not calibrated against a labelled
  corpus. They are defensible and documented, but they are not measured.
- Type completeness only covers the seventeen artifact types with declared field
  expectations; documentation artifacts are credited in full rather than checked,
  because inventing a field requirement would penalise correct output.
- A per-version review means re-reviewing a revised artifact requires the agent
  to run again. There is no "review this by hand" path.
- The Executive's consultation is advisory by default, so in the shipped
  configuration a low score informs but does not protect.

## Alternatives considered

**Call Helix at runtime.** Rejected: there is nothing to call, and
`07_System_Architecture.md` forbids it. Shelling out to a coding agent from a
request handler would be a fabrication dressed as an integration.

**Score purely with an LLM (LLM-as-judge).** Rejected on two grounds:
`12_Risk_Analysis.md` rates hallucination High, and on recorded fixtures it would
produce a uniform score — the demo would show a number that measured nothing.

**Block the lifecycle on a failed review by default.** Rejected as the shipped
default: it turns a heuristic into an authority and risks a demo that stalls.
Available behind one setting.

**Store the review on the artifact row.** Rejected: it would be overwritten on
revision, losing the judgement of the version downstream work was actually built
on — the same reasoning as ADR-0007.
