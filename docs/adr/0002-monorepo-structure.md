# ADR-0002 — Monorepo with separate API and web applications

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0

## Context

`08_Technology_Stack.md` specifies Next.js for the frontend and FastAPI for the
backend but says nothing about repository layout — the document is a table of
contents plus a single stack table.

`06_Product_Architecture.md` requires a clear separation between product features
and system architecture: "Product modules should represent user-facing
capabilities, while internal orchestration, agent communication, memory
management, and infrastructure should remain implementation details."

The two applications are written in different languages with different toolchains
and different deployment targets, but they evolve together: an API contract
change touches both in the same commit.

## Decision

A single repository containing two independently buildable applications:

```
apps/
  api/     FastAPI — agents, orchestration, memory. Owns all engineering logic.
  web/     Next.js — the engineering workspace. Owns no engineering logic.
evaluation/  Mutagent ADL artifacts (Milestone 9)
docs/        Specification (read-only) + docs/adr/
```

Each application owns its dependency manifest, test suite, lint configuration,
and Dockerfile. Neither imports from the other; the HTTP contract is the only
coupling, and it is typed on both sides.

No shared `packages/` directory is introduced. It would carry only TypeScript
type definitions mirroring the API's Pydantic models, and generating those from
the OpenAPI schema — which FastAPI already publishes — is strictly better than
hand-maintaining a third copy.

The web application's `output: "standalone"` build produces a self-contained
server bundle, which is what makes its production image viable without shipping
`node_modules`.

## Consequences

**Positive**

- One commit, one review, one history for a change spanning both tiers.
- Each application builds, tests, and deploys independently.
- The API is usable without the web application, which keeps the "engineering
  organization" genuinely headless and testable.

**Negative**

- Contributors need both Python and Node toolchains. Acceptable: the stack was
  specified, not chosen here.
- Two lockfiles. `outputFileTracingRoot` is pinned in `next.config.ts` because
  Next.js otherwise walks up the tree and can select an unrelated ancestor
  directory as the workspace root — observed during Milestone 0.

## Alternatives considered

**Separate repositories.** Rejected: an API contract change would need two
coordinated pull requests, which is precisely the coordination overhead this
project exists to eliminate.

**Next.js API routes instead of FastAPI.** Rejected: it contradicts
`08_Technology_Stack.md`, and the agent and orchestration layers are
substantially better served by Python's AI tooling.
