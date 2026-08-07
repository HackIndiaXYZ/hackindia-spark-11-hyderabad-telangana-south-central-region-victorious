# ADR-0012 — Stale work proposes re-synchronisation rather than blocking

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 7

## Context

`04_Existing_Solutions.md` names the capability no tool on the market provides:

> Which downstream components are affected by this requirement change?
> Are dependencies still valid after recent changes?

Milestone 1 made staleness computable (ADR-0007). Milestone 3 made a stale
derivation a **blocking** conflict, on the reasoning that building on work known
to be out of date compounds the inconsistency.

Implementing the rejection loop showed that rule to be a deadlock. Rejecting a
gate reopens the stage that produced the work; the agent reruns and appends a new
version; that revision necessarily makes everything downstream stale; the stale
conflict then blocks the workflow — including the gate that would have re-approved
the revised work. A project could never recover from a rejection.

The same deadlock applies to the platform's headline scenario. A finished project
whose requirement changes would go permanently blocked, which is the opposite of
answering the question above.

## Decision

### Stale work is recoverable, so it proposes a rebuild

When every blocking conflict is a stale derivation, the Executive AI raises a
`RESYNCHRONISATION` approval gate rather than halting. Approving it reopens the
stages that own stale artifacts, so their specialists rerun against the current
upstream. Declining leaves the stale work in place with its staleness still
visible.

Regenerating work a human already approved is not a decision the organization
should take alone, which is why it is a gate and not automatic —
`12_Risk_Analysis.md` rates Excessive Automation a High risk.

Only stages that actually own a stale artifact are reopened. Selective
regeneration is the difference between propagating a change and starting over.

Any other blocking conflict — two competing approved artifacts, say — still
halts, because no rerun resolves it.

### Conflicts block work, not gates

Conflict detection moved from the top of the assessment into the branch where a
stage is otherwise ready to execute. Raising a gate is not engineering work; it
is asking a human. Blocking that was what made the deadlock possible.

### Conflicts already being fixed are not raised

A stale artifact whose stage is already queued to rerun needs no decision — the
next pass rebuilds it. Asking for approval to fix something already scheduled to
be fixed trains users to click through gates, which is how a safeguard stops
working.

### Superseded edges are history

A rerunning agent declares a *new* edge rather than updating the old one, so the
graph accumulates several declarations of the same dependency. Staleness now
considers only the most recent declaration per (upstream, downstream, kind).

Without this an artifact could never stop being stale: rebuilding adds a fresh
edge, but the superseded edge still cites the old version, so the artifact would
be reported out of date forever no matter how many times it was regenerated.

### A rerun revises rather than duplicates

An agent that runs again reuses the artifact it produced before — identified by
(project, type, stage, title) — and appends a version. Creating a second artifact
would fork the traceability graph and trip the duplicate-authority conflict.
Revised artifacts return to draft, because content nobody has reviewed must not
inherit an earlier approval.

### A rejection applies to the version reviewed

Once the responsible agent has revised the work, the old decision is about a
version that no longer exists, so a fresh gate is raised instead of the project
staying blocked by an answered objection.

## Consequences

**Positive**

- The platform's central claim is demonstrable end to end: on a finished project,
  changing one requirement marks 19 artifacts out of date, the organization
  proposes re-synchronisation, and approving it rebuilds seven stages and clears
  every stale artifact.
- A rejection is now a normal part of the workflow rather than a dead end.
- The user sees the blast radius before deciding, and decides whether to rebuild.

**Negative**

- Re-synchronisation currently reopens whole stages. An agent that owns several
  artifacts regenerates all of them even if one was stale. Finer granularity
  needs per-artifact dispatch, which the agent framework does not support.
- Rebuilt work returns to draft and must be re-approved, so a small requirement
  change costs several approvals. Batching them into one re-synchronisation
  sign-off would be a better experience.
- Because the graph is over-connected (ADR-0010), one requirement change marks
  nearly everything downstream stale. The propagation is correct; its
  *precision* is limited by how sources are declared.

## Alternatives considered

**Regenerate automatically on staleness.** Rejected: it silently discards
approved work, which `12_Risk_Analysis.md` names as the Excessive Automation
risk.

**Let stale work block permanently and require manual intervention.** This was
the Milestone 3 behaviour. Rejected: it makes the platform's headline scenario a
dead end.

**Delete superseded edges on rerun.** Rejected: ADR-0007 keeps edges immutable so
the history of how a project was reasoned about survives. Filtering to the
current declaration achieves the same result without losing that record.
