# ADR-0005 — Runtime infrastructure deviations from the specified stack

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0

## Context

`08_Technology_Stack.md` and `14_Executive_Summary.md` specify a six-service
runtime: Next.js, FastAPI, LangGraph, PostgreSQL, ChromaDB, Redis.

`15_Development_Guidelines.md` requires "production readiness over
hackathon-only implementations" and forbids sacrificing architectural quality for
speed. `13_Demo_and_Pitch.md` requires the opposite emphasis: "prioritize
building a polished end-to-end demonstration over implementing every planned
feature."

Both are satisfiable, but not by running six services on a 24-hour budget on a
machine where Docker is not installed. The resolution is to keep every layer
architecturally present behind an interface while running the minimum backing
service each one actually needs today.

## Decision

### Redis — deferred

Not implemented in the MVP. `12_Risk_Analysis.md` cites caching solely as a
token-cost mitigation for "large engineering projects". MVP projects are single
runs over a shared memory that is already the source of truth. Adding a cache
before there is a measured cost problem is speculative work that also adds a
service to the demo path.

Reintroduced behind a `CacheProvider` protocol when token cost is measured, not
assumed.

### ChromaDB — embedded, disabled by default

Runs as an embedded persistent client rather than a separate service. Disabled
by `VICTORIOUS_VECTOR_STORE__ENABLED` until the Knowledge Base needs semantic
search. `10_UI_UX_Plan.md` asks for semantic rather than keyword search, so the
capability is genuinely specified — but it is a Milestone 5+ concern, and the
embedded client removes a service without removing the capability.

### PostgreSQL — compose default, SQLite for native development

`docker-compose.yml` runs PostgreSQL, matching the specification. Native
development defaults to SQLite so a fresh checkout needs no services.

Both are reached through SQLAlchemy's async API behind the repository protocols
from ADR-0003; the difference is one URL. This matters for the demo: Docker is
not installed on the presenting machine, and a demo that cannot start is worth
nothing regardless of how production-ready its architecture is.

### SSE instead of WebSockets

`07_System_Architecture.md` requires users to "observe the complete AI
Engineering Organization operating in real time" but specifies no transport;
`08_Technology_Stack.md` lists a "Communication Layer" heading with no content.

Agent activity streaming is strictly one-directional: the server emits lifecycle
and agent events, the client renders them. Server-Sent Events match that shape
exactly, work over plain HTTP with no extra infrastructure, and reconnect
automatically in the browser. WebSockets would add bidirectional machinery for a
unidirectional problem.

## Consequences

**Positive**

- Demo path is `uvicorn` plus `next dev` — no container runtime required.
- Every deferred component sits behind a protocol, so reintroducing it is a
  composition-root change.
- Fewer moving parts on the demo path directly reduces `12_Risk_Analysis.md`
  operational risk.

**Negative**

- The compose path could not be verified during Milestone 0: Docker is not
  installed on the development machine. The Dockerfiles and compose file are
  written and reviewed but **untested**, and must be validated before any claim
  that the platform runs in containers.
- SQLite and PostgreSQL differ in concurrency and type affinity. Mitigated by
  going through SQLAlchemy rather than raw SQL, and by running CI against
  PostgreSQL once the compose path is verified.

## Alternatives considered

**Implement the full six-service stack.** Rejected: it consumes the budget
allocated to change propagation, which is the differentiating capability, and
increases the probability of demo failure.

**Drop PostgreSQL entirely and ship SQLite.** Rejected: it contradicts the
specification for no benefit, since the abstraction supports both at the cost of
one configuration line.
