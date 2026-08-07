# ADR-0009 — Workflow state lives in shared memory, and the Executive AI cannot perform engineering work

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 3

## Context

`08_Technology_Stack.md` specifies LangGraph as the agent workflow engine.
LangGraph's headline durability feature is a checkpointer that persists graph
state between invocations and powers its `interrupt` primitive.

`15_Development_Guidelines.md` states that shared memory "is the single source of
truth", and `12_Risk_Analysis.md` rates Context Drift a High risk — "engineering
agents may operate using outdated or inconsistent project knowledge" — mitigated
by "centralized shared project memory".

The same document draws a second hard line:

> The Executive AI (Engineering Director) coordinates engineering activities but
> does not directly perform engineering work.

Both needed deciding before the workflow was built.

## Decision

### 1. LangGraph structures execution; shared memory holds the truth

LangGraph is used for declarative nodes, conditional routing, and a compiled
executable graph. It is deliberately **not** given a checkpointer.

Workflow state (:class:`app.orchestration.state.OrchestrationState`) carries only
what one traversal needs to route itself: the project id, the current decision,
which stages this traversal executed, and why it stopped. It holds no project
knowledge. Every node re-reads current facts — artifacts, approvals, traceability
edges, agent runs — from shared memory.

A checkpointer would mean two places answer "where does this project stand". When
they disagree — and they eventually would, since a human can approve a gate or
revise a requirement between traversals — the workflow would act on stale state
while the Knowledge Base showed something else. That is Context Drift
manufactured by the architecture rather than mitigated by it.

Resumption is therefore just calling `advance()` again. Because state is read
rather than restored, a traversal starting after an approval sees the new
decision immediately, and resumption works across process restarts — which an
in-memory checkpointer would not survive.

### 2. Routing is computed; reasoning is used only for prose

Whether a stage may run is a question about which artifacts exist and which
approvals were granted. :mod:`app.orchestration.dependencies` and
:mod:`app.orchestration.conflicts` answer it with pure functions.

`12_Risk_Analysis.md` rates AI Hallucination a High risk. Putting a language
model in charge of dependency validation or conflict detection would place that
risk inside the mechanism whose purpose is catching inconsistency. Every detector
— stale derivation, duplicate authority, unresolved concern, low confidence — is
deterministic and unit-tested without a database or a provider.

The Executive AI uses reasoning for exactly one thing: writing the prose a human
reads at an approval gate. Even there a provider failure falls back to
deterministic text, because `09_MVP_Roadmap.md` makes approval non-negotiable and
a gate that cannot be raised without a working model is not a safeguard.

### 3. The Executive AI lives in `orchestration`, not `agents`

`ExecutiveAI` is defined in `app/orchestration/executive.py`. It does **not**
extend `BaseAgent`, and it has no code path to `artifacts.create`.

This is a deviation from the file layout in the implementation roadmap, which
placed it at `app/agents/executive.py`. Keeping it among the agents would have
left it one inherited method away from producing a PRD. Placing it in the
orchestration layer makes the specification's boundary structural: the Executive
*cannot* perform engineering work, rather than being trusted not to.

A test asserts the consequence — after a full traversal, no artifact and no agent
run is owned by the Executive role — so a future change that gave it an artifact
path fails the build.

### 4. Only `coordinate` decides

The graph has three nodes. `coordinate` is the Executive AI and is the only node
that makes a decision; `execute` and `gate` each carry out one instruction. That
asymmetry is the graph-shaped form of the same boundary.

## Consequences

**Positive**

- One source of truth for project state, as the specification requires.
- Resumable across process restarts and across runner instances.
- Dependency and conflict rules are pure, fast, and testable without I/O.
- The Executive's boundary is enforced by structure and verified by test.
- Approval gates survive a provider outage.

**Negative**

- Each traversal re-reads shared memory, so a long run performs more queries than
  a checkpointed graph would. Acceptable at MVP scale, and it is the direct cost
  of not having a second source of truth.
- LangGraph's `interrupt` primitive is unused; gates halt the traversal and
  resumption is a fresh invocation. Slightly more code than `interrupt`, and it
  keeps the halt reason in shared memory where the Approval Center reads it.
- A failed stage is retried on the next `advance()` rather than being marked
  permanently failed. Deliberate — most provider failures are transient — but it
  means a persistently failing agent is retried once per advance, and a retry
  budget will be needed before this is exposed to unattended scheduling.

## Alternatives considered

**LangGraph checkpointer as the source of truth.** Rejected: it contradicts
`15_Development_Guidelines.md` and manufactures the Context Drift risk
`12_Risk_Analysis.md` names.

**No LangGraph; a hand-rolled stage machine.** Tempting, since the checkpointer
is unused. Rejected because `08_Technology_Stack.md` names LangGraph, and its
declarative routing genuinely earns its place — the graph's shape is readable in
one screen, and the node/edge structure is what made the infinite-loop bug in the
first implementation obvious once a failing stage was tested.

**An LLM-driven Executive that decides routing by reasoning.** Rejected on
hallucination-risk grounds. It would also be slower, non-deterministic, and
untestable without a provider, for decisions that have exactly one correct answer.
