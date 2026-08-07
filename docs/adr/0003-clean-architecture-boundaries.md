# ADR-0003 — Clean architecture boundaries, enforced by tests

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0

## Context

`15_Development_Guidelines.md` mandates SOLID, Clean Architecture, Separation of
Concerns, Dependency Injection, and Provider Abstraction, and closes with:
"Never sacrifice architectural quality for implementation speed."

`05_AI_Agent_Architecture.md` requires that agents "avoid directly modifying each
other's internal state" and that the implementation prioritise "loose coupling,
high cohesion, scalability, observability, and provider-agnostic AI integration
so that individual agents, reasoning models, or external services can be upgraded
or replaced without affecting the overall system architecture."

These are strong claims. Under a 24-hour deadline they are also the first things
to erode — an import added at hour 18 to save five minutes is invisible in review
and permanent thereafter.

## Decision

### Layering

Dependencies point inward only:

```
api  ->  orchestration  ->  agents  ->  memory  ->  domain
core ->  (cross-cutting: config, logging, DI, errors, health)
```

- **`domain`** is the innermost ring: artifacts, lifecycle stages, traceability
  edges, agent contracts, approvals, errors. It imports no framework, no I/O, and
  nothing from any outer layer — not even `core`.
- **`memory`** owns persistence behind repository protocols.
- **`llm`** owns provider adapters behind a provider protocol.
- **`agents`** own reasoning. They depend on memory and llm protocols, never on
  concrete implementations.
- **`orchestration`** owns the Executive AI, the lifecycle graph, and dependency
  resolution.
- **`api`** owns HTTP only, and contains no engineering logic.
- **`core`** is cross-cutting infrastructure, usable by any layer above `domain`.

### Enforcement

`apps/api/tests/test_architecture.py` parses the source tree with `ast` and fails
the build when a rule is violated. It checks that:

- no layer imports from a layer above it,
- `domain` imports no framework (`fastapi`, `sqlalchemy`, `anthropic`,
  `langgraph`, `chromadb`, and others),
- `domain` is non-empty, so the rules cannot pass vacuously,
- the DI container is constructed only in `app/core/bootstrap.py`.

Rules for layers that do not yet exist are inert, so the file is written once and
begins enforcing each layer the moment its milestone lands.

### Composition

A single composition root, `app/core/bootstrap.py`, is the only place that binds
a protocol to an implementation. Every other module depends on protocols. Swapping
Anthropic for Gemini, or the SQL memory repository for another store, is a change
to that one file.

## Consequences

**Positive**

- The architectural claim is verified on every test run rather than asserted in a
  document.
- A violation fails CI with the offending file and import named.
- The provider-swap and memory-swap requirements are structurally guaranteed, not
  aspirational.

**Negative**

- More indirection than a 24-hour build strictly needs. This is the explicit
  instruction of `15_Development_Guidelines.md`.
- Static analysis only: it cannot catch a runtime coupling introduced through a
  dynamic import. Acceptable — it catches the realistic failure mode, which is an
  ordinary import statement added in a hurry.

## Alternatives considered

**Convention plus code review.** Rejected: no second reviewer exists on this
timeline, and convention is exactly what deadline pressure erodes.

**`import-linter` as a dependency.** Rejected: the rule set fits in one readable
test file with no new dependency, and a reviewer can audit it in a minute.
