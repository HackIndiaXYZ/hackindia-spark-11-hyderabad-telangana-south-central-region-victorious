# ADR-0001 — Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0

## Context

`15_Development_Guidelines.md` establishes a precedence hierarchy over the twelve
specification documents and states that lower-priority documents must never
contradict higher-priority ones. It also requires that architectural integrity
take priority over implementation speed.

Two problems follow from building against that specification:

1. `07_System_Architecture.md` and `08_Technology_Stack.md` — ranked 8th and 9th,
   above the MVP Roadmap — are near-empty. Both consist almost entirely of tables
   of contents. Every concrete technology decision therefore has to be made
   during implementation, not read out of the specification.
2. Several MVP decisions necessarily deviate from the specification's literal
   text. `06_Product_Architecture.md` lists OAuth and team invitations under the
   Authentication Module, while `09_MVP_Roadmap.md` defers multi-user
   collaboration entirely.

An undocumented deviation is indistinguishable from a mistake. `06` requires the
Knowledge Base to store Architectural Decision Records for the *user's* projects;
this repository should hold itself to the same standard.

## Decision

Every architectural decision that is not directly readable from the
specification is recorded as an ADR in `docs/adr/`.

An ADR is written when a decision:

- deviates from the literal text of a specification document,
- resolves a conflict between two specification documents,
- fills a gap left by an incomplete specification document, or
- would otherwise leave a future reader asking "why is it built this way?"

`docs/adr/` is the only path inside `docs/` this implementation writes to. The
twelve specification documents are treated as read-only input.

Format: context, decision, consequences, and — where relevant — the alternatives
rejected and why. Superseded ADRs are marked, never deleted; the reasoning is
the artifact, and losing it would defeat the point.

## Consequences

**Positive**

- Deviations are visible and reviewable rather than discovered by reading code.
- The traceability guarantee the platform makes about user projects is
  demonstrated on the platform's own construction.
- A reviewer can audit the specification-to-implementation gap in one directory.

**Negative**

- Writing time competes directly with a 24-hour build budget. Mitigated by
  keeping ADRs short and writing them only for decisions meeting the bar above.

## Alternatives considered

**Amend the specification documents directly.** Rejected: the specification is
the authored input to this work, and editing it would erase the distinction
between what was specified and what was decided during implementation.

**Inline code comments only.** Rejected: comments explain a file, but these
decisions span the whole system and need to be findable without knowing which
file to open.
