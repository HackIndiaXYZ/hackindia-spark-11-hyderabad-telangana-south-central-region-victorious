# Architecture Decision Records

Decisions taken while implementing Project Victorious that are not directly
readable from the specification. See [ADR-0001](0001-record-architecture-decisions.md)
for when an ADR is written.

`docs/adr/` is the only path inside `docs/` this implementation writes to. The
fifteen specification documents are read-only input.

| ADR | Decision | Status | Milestone |
|-----|----------|--------|-----------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 0 |
| [0002](0002-monorepo-structure.md) | Monorepo with separate API and web applications | Accepted | 0 |
| [0003](0003-clean-architecture-boundaries.md) | Clean architecture boundaries, enforced by tests | Accepted | 0 |
| [0004](0004-llm-provider-default.md) | Claude as the default reasoning provider | Accepted | 0, 2 |
| [0005](0005-runtime-infrastructure-deviations.md) | Runtime infrastructure deviations from the specified stack | Accepted | 0 |
| [0006](0006-code-generation-depth.md) | Generated output is an inspectable scaffold, not a runnable application | Accepted | 0, 4 |
| [0007](0007-traceability-model.md) | Traceability edges bind identity and record upstream version | Accepted | 1, 8 |
| [0008](0008-fixture-provider-and-fallback.md) | Recorded fixtures are a first-class provider, and the fallback is silent-but-visible | Accepted | 2 |
| [0009](0009-orchestration-state-and-executive-boundary.md) | Workflow state lives in shared memory, and the Executive AI cannot perform engineering work | Accepted | 3 |
| [0010](0010-agent-roster-and-stage-ownership.md) | Eight agents fill seven roles, and artifacts are rendered from structured output | Accepted | 4 |
| [0011](0011-stream-carries-signals-not-state.md) | The live stream carries signals; the REST API carries state | Accepted | 6 |
| [0012](0012-change-propagation-and-resynchronisation.md) | Stale work proposes re-synchronisation rather than blocking | Accepted | 7 |
| [0013](0013-engineering-review-layer.md) | Engineering review runs natively; Helix drives its lifecycle | Accepted | 11 |

## Deviations from the specification

Consolidated view of where the implementation departs from the literal
specification text, and why.

| Specification says | Implementation does | ADR |
|---|---|---|
| LLM: Gemini (`08`) | Claude default, Gemini adapter shipped | [0004](0004-llm-provider-default.md) |
| Redis cache (`08`, `14`) | Deferred until token cost is measured | [0005](0005-runtime-infrastructure-deviations.md) |
| ChromaDB service (`08`, `14`) | Embedded client, disabled by default | [0005](0005-runtime-infrastructure-deviations.md) |
| PostgreSQL (`08`, `14`) | PostgreSQL in compose, SQLite for native development | [0005](0005-runtime-infrastructure-deviations.md) |
| "Production-ready software" (`01`, `02`, `14`) | Inspectable generated scaffold | [0006](0006-code-generation-depth.md) |
| LangGraph as the workflow engine (`08`) | Used for graph structure and routing; its checkpointer is deliberately unused so shared memory stays the single source of truth | [0009](0009-orchestration-state-and-executive-boundary.md) |
| Executive AI listed among the agents (`05`) | Implemented in the orchestration layer with no artifact-writing path, so `15`'s "does not perform engineering work" is structural | [0009](0009-orchestration-state-and-executive-boundary.md) |

## Unresolved specification gaps

Recorded during the Milestone 0 specification review. These are gaps in the
input documents, not decisions — listed so they are not mistaken for oversights.

- **`07_System_Architecture.md` and `08_Technology_Stack.md` are near-empty.**
  Both are almost entirely tables of contents. `15_Development_Guidelines.md`
  ranks them 8th and 9th in precedence — above the MVP Roadmap — so the two
  documents with the most authority over implementation carry the least content.
  Every technology decision they should have settled is made in an ADR instead.
- **UI/UX Designer Agent has no MVP home.** `05_AI_Agent_Architecture.md` defines
  it; `09`, `11`, and `14` omit it from the V1 roster. `06_Product_Architecture.md`
  nonetheless specifies a Design Center module. The Design Center is therefore
  out of MVP scope, with no agent to populate it until V2.
- **Nine stages, six specialist roles.** `09_MVP_Roadmap.md` defines both the
  lifecycle and the V1 roster but does not say which role owns which stage, and
  the counts do not divide evenly. Resolved in
  [ADR-0010](0010-agent-roster-and-stage-ownership.md): a role may own more than
  one stage, and deployment preparation sits with Documentation until the V2
  DevOps agent lands.
- **Git integration is doubly placed.** `06_Product_Architecture.md` lists Git
  Integration, Pull Requests, and CI Status under the Development Center;
  `11_Future_Roadmap.md` places all three in Version 2. Treated as V2.
- **Authentication scope conflict.** `06` specifies OAuth, team invitations, and
  role management; `09` defers multi-user collaboration and `11` places RBAC in
  Version 3. MVP implements email/password only.
