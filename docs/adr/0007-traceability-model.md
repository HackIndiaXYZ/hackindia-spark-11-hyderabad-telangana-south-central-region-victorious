# ADR-0007 — Traceability edges bind identity and record upstream version

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 1 (model), 8 (propagation)

## Context

`04_Existing_Solutions.md` names the capability gap this platform exists to fill,
as questions no current tool answers:

> Is the architecture still consistent with the latest requirements?
> Which downstream components are affected by this requirement change?
> Are dependencies still valid after recent changes?

`12_Risk_Analysis.md` rates Dependency Propagation and Context Drift as High
risks, mitigated by "traceability between engineering artifacts", "automatic
dependency analysis", and "version-controlled engineering artifacts".

Milestone 8 implements change propagation. Whether that milestone is a two-hour
feature or a rewrite is decided entirely by the data model chosen here, which is
why this decision is taken in Milestone 1 rather than deferred to the milestone
that consumes it.

## Decision

Three choices, which together make propagation fall out of the model.

### 1. Artifacts have stable identity; versions are immutable content

`Artifact` is identity — "the system architecture for project X" — and never
changes. `ArtifactVersion` is content at a point in time and is only ever
appended, never updated. Version numbers are assigned by the repository, not the
caller, and `UNIQUE (artifact_id, version)` enforces it in the database.

Traceability edges therefore point at artifact identity and survive every
revision, while any historical version remains inspectable exactly as the agent
that consumed it saw it.

### 2. Edges record the upstream version they consumed

A `TraceEdge` carries `upstream_artifact_id`, `downstream_artifact_id`, `kind`,
and — critically — `upstream_version`: the version of the upstream artifact that
this derivation actually read.

### 3. Staleness is computed, never stored

An artifact is stale when any inbound edge cites an upstream version lower than
that upstream's current version:

```
stale(D) ⟺ ∃ edge(U → D) where edge.upstream_version < U.current_version
```

There is no `is_stale` column. `ArtifactStatus` deliberately carries only
approval state.

This is the load-bearing choice. A stored flag must be set by whichever code path
revises an artifact — and the failure mode is that some path forgets, leaving the
system quietly asserting consistency it does not have. That is precisely the
documentation-drift failure `01_Problem_Statement.md` describes. A platform whose
thesis is *keeping engineering artifacts consistent* cannot itself depend on
remembering to update a flag.

Change impact is the transitive downstream closure over edges, computed
breadth-first so each artifact is reported at its shortest path — the most direct
explanation of why it is affected.

`TraceKind` distinguishes `DERIVES_FROM`, `IMPLEMENTS`, `VALIDATES`, `TESTS`,
`DOCUMENTS`, and `REFINES`, so Milestone 8 can propose proportionate
re-synchronisation rather than regenerating everything downstream: an architecture
that *derives from* a changed requirement likely needs rework, while an analysis
that *validates* one needs re-examination.

## Consequences

**Positive**

- Staleness cannot drift from reality, because it is not stored.
- The "why does this artifact exist?" query is the same graph read in reverse.
- Milestone 8 needs the propagation engine and its UI only; the data is already
  correct.
- Impact is computed and shown *before* a change is applied, which is what the
  Approval Center's "downstream impact" field in `10_UI_UX_Plan.md` requires.

**Negative**

- Every write path must record edges. An agent that produces an artifact without
  declaring its upstream creates an invisible orphan. Mitigated by the agent base
  class in Milestone 2 requiring inputs and outputs, and by the context builder
  already exposing `artifact_ids` as the upstream half of each edge.
- Staleness is a query, not a column, so it cannot be filtered on in SQL without
  loading the graph. At MVP scale — hundreds of edges — the whole graph is loaded
  and traversed in memory, which is faster than recursive SQL and keeps the
  traversal rules in the pure, directly testable domain layer. This will need
  revisiting at thousands of artifacts per project.

## Alternatives considered

**Version-to-version edges.** Rejected: an edge from architecture v2 to
requirements v1 would need re-creating on every revision, and the graph would
grow with revision count rather than with project structure.

**A stored `is_stale` flag, updated on write.** Rejected for the reason above: it
is the failure mode this platform exists to eliminate.

**Recursive SQL (`WITH RECURSIVE`) for impact analysis.** Rejected for now. It
would put the traversal rules in dialect-specific SQL, splitting them across
SQLite and PostgreSQL and making them far harder to unit test. The pure function
in `app/domain/traceability.py` is covered by fifteen tests that need no database
at all. Worth revisiting only when graph size makes in-memory traversal the
bottleneck.
