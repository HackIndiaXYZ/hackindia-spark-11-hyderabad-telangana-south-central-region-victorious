# Project Victorious

An AI-native **Software Engineering Workspace**, powered by an autonomous AI
Software Engineering Organization.

Specialized engineering agents — a Product Manager, Business Analyst, Software
Architect, Full Stack Engineer, QA Engineer, and Documentation Agent, coordinated
by an Executive AI — transform a software idea into a structured engineering
project. They work over a shared organizational memory, keep every artifact
traceable to the decision that produced it, and stop at human approval gates
before critical decisions.

This is not an AI coding assistant. Coding assistants make implementation fast;
they do not answer *"which downstream artifacts does this requirement change
invalidate?"* That question is what this platform exists to answer.

Built for the **Mutagent Challenge** (HackIndia Spark 11, Hyderabad).

---

## Status

**All ten milestones complete.**

The whole platform runs end to end with **no API key and no network**: create a
project from a name and a description, watch the organization work through nine
lifecycle stages *as it happens*, approve three gates, and read all 22 generated
artifacts in the browser — rendered markdown, tables, Mermaid component diagrams,
code, and full version history.

Agent cards and the Engineering Timeline update live over Server-Sent Events, with
no polling and no page refresh ([ADR-0011](docs/adr/0011-stream-carries-signals-not-state.md)).

**The capability the whole platform exists for now works, verified against a live
server.** On a finished 8-stage project, revising one requirement marks **19
artifacts out of date**; the organization proposes re-synchronisation; approving
it reruns seven stages against the new requirement and clears every stale
artifact. That is the question
[`04_Existing_Solutions.md`](docs/04_Existing_Solutions.md) says nothing on the
market answers. See
[ADR-0012](docs/adr/0012-change-propagation-and-resynchronisation.md).

The **Traceability** view draws that graph — 22 artifacts laid out by lifecycle
stage, with stale derivations highlighted and a click to focus one artifact's
dependencies. Before revising anything, the workspace shows the blast radius:
*19 artifacts depend on this and would go out of date · 7 stages would rerun*.

```bash
cd apps/api && .venv/Scripts/python scripts/seed_demo.py     # seeds the demo project
cd apps/api && .venv/Scripts/python -m uvicorn app.main:app  # http://localhost:8000
cd apps/web && npm run dev                                   # http://localhost:3000
```

Cold start from an empty database to a fully populated workspace: **18 seconds**.
The presentation walkthrough is [`DEMO.md`](DEMO.md).

**Not yet implemented: authentication.** `09_MVP_Roadmap.md` lists it as
Priority 1 and it is not built — the API is currently unauthenticated. See
[Known gaps](#known-gaps).

---

**Milestone 4 — the engineering organization is operational.**

A project now runs end to end: an idea becomes requirements, validated
requirements become an architecture, an approved architecture becomes a plan, a
scaffold, a test suite, documentation, and a deployment plan — through three
human approval gates, with every artifact traced to what it was derived from.

On the `13_Demo_and_Pitch.md` hospital scenario that is **22 artifacts across 8
agent runs and 3 approval gates**, with the full traceability graph connecting
them.

Foundations behind it: architectural boundaries and DI (M0); shared organizational
memory with append-only versioning and the traceability graph (M1); the
provider abstraction and agent execution framework (M2); the Executive AI and its
LangGraph workflow (M3).

The workspace UI arrives in Milestone 5 — until then everything is exercised
through the API and the test suite.

Four properties are load-bearing:

- **Staleness is computed, not stored.** The traceability model answers the
  question [`04_Existing_Solutions.md`](docs/04_Existing_Solutions.md) says
  nothing on the market answers — *which downstream artifacts does this
  requirement change invalidate?* — because an artifact is stale when a
  traceability edge cites an older version than its upstream currently has.
  See [ADR-0007](docs/adr/0007-traceability-model.md).
- **No agent can produce an orphan.** The agent base class rejects any artifact
  that fails to declare the upstream it was derived from, so nothing can be
  invisible to impact analysis.
- **The Executive AI cannot perform engineering work.** It lives in the
  orchestration layer with no artifact-writing path at all, so
  [`15_Development_Guidelines.md`](docs/15_Development_Guidelines.md)'s boundary
  is structural rather than a matter of discipline. A test asserts that no
  artifact and no agent run is ever owned by the Executive role. See
  [ADR-0009](docs/adr/0009-orchestration-state-and-executive-boundary.md).
- **Documents cannot drift from their data.** Agents emit structured fields; the
  readable artifact is *rendered* from those fields rather than written
  separately, so what a human reads and what the next agent consumes are the
  same information. See
  [ADR-0010](docs/adr/0010-agent-roster-and-stage-ownership.md).

See [`docs/09_MVP_Roadmap.md`](docs/09_MVP_Roadmap.md) for scope and
[`docs/adr/`](docs/adr/README.md) for decisions and deviations taken so far.

---

## Running it

Requires Python 3.12+ and Node 22+. No container runtime needed.

**API** — from `apps/api`:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"   # macOS / Linux
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Serves on `http://localhost:8000`. Interactive API docs at `/docs`.

**Web** — from `apps/web`:

```bash
npm install
npm run dev
```

Serves on `http://localhost:3000`.

**Configuration** — copy `.env.example` to `.env`. **No API key is required to
run anything.** Without one the platform falls back to the `fixture` provider,
which replays recorded reasoning from disk; `/health/ready` reports `degraded` and
names the real backend, so the fallback is never silent. See
[ADR-0008](docs/adr/0008-fixture-provider-and-fallback.md).

**Containers** — `docker compose up --build` runs the full stack with PostgreSQL.
This path is written but **not yet verified** (no Docker on the development
machine); see [ADR-0005](docs/adr/0005-runtime-infrastructure-deviations.md).

---

## Quality gates

From `apps/api`:

```bash
.venv/Scripts/python -m pytest        # tests, including architecture rules
.venv/Scripts/python -m ruff check .  # lint
.venv/Scripts/python -m mypy app      # strict type checking
```

From `apps/web`:

```bash
npm run typecheck
npm run lint
npm run build
```

`tests/test_architecture.py` is worth a look: it parses the source tree and fails
the build if a layer imports outward, if the domain layer picks up a framework
dependency, or if the DI container is constructed outside the composition root.
The architecture is enforced, not just documented.

---

## Repository layout

```
apps/
  api/            FastAPI — agents, orchestration, shared memory
    app/
      domain/     Pure domain layer: no frameworks, no I/O
      core/       Config, logging, DI container, errors, health
      db/         SQLAlchemy models, session, Alembic migrations
      memory/     Shared organizational memory + agent context assembly
      events/     Event bus (durable append + live fan-out)
      llm/        Provider abstraction: Anthropic, Gemini, fixture replay
      agents/     The eight engineering agents, their contracts and prompts
      orchestration/  Executive AI, workflow graph, dependency & conflict rules
      api/        HTTP transport only
    tests/
  web/            Next.js — the engineering workspace
docs/             Specification (read-only) — see docs/adr/ for decisions
evaluation/       Mutagent ADL artifacts (Milestone 9)
```

Dependencies point inward: `api → orchestration → agents → memory → domain`.

**Database migrations** — from `apps/api`:

```bash
.venv/Scripts/python -m alembic upgrade head      # apply
.venv/Scripts/python -m alembic downgrade base    # reverse
```

Outside production the app creates any missing tables on startup, so no migration
step is needed for local development.

---

## Documentation

The [`docs/`](docs/) directory is the authoritative specification, treated as
read-only input by this implementation. Start with
[`14_Executive_Summary.md`](docs/14_Executive_Summary.md), then
[`05_AI_Agent_Architecture.md`](docs/05_AI_Agent_Architecture.md) and
[`09_MVP_Roadmap.md`](docs/09_MVP_Roadmap.md).

[`docs/adr/`](docs/adr/README.md) records every decision the specification did
not settle, every deviation from it, and the specification gaps found during
review.

---

## Evaluation

The platform is scored by a runnable harness in [`evaluation/`](evaluation/README.md),
the evidence `02_Proposed_Solution.md` requires of a project built through
Mutagent's Agentic Development Lifecycle. Everything runs offline.

```bash
apps/api/.venv/Scripts/python evaluation/run_evaluation.py   # scorecards
apps/api/.venv/Scripts/python evaluation/adl_cycle.py        # one ADL cycle, measured
```

Eight deterministic scorers over three project briefs, **93.8% overall**. No
scorer asks a language model to judge quality — a hallucinating grader would
report improvement that did not happen.

The documented cycle found that re-synchronisation was **divergent**: rebuilding
stale work left *more* stale derivations than before it, because superseded trace
edges still cited the versions they originally consumed. **167 → 0** after the
fix. See [`evaluation/optimization-report.md`](evaluation/optimization-report.md).

---

## Known gaps

Stated plainly rather than discovered later.

- **No authentication.** `09_MVP_Roadmap.md` lists it Priority 1; it is not
  implemented, so the API accepts any caller. Acceptable for local development
  and a demo, not for deployment. Scheduled before release.
- **Docker compose is unverified.** The Dockerfiles and compose file are written
  but have never been run — Docker is not installed on the development machine.
  See [ADR-0005](docs/adr/0005-runtime-infrastructure-deviations.md).
- **Prompts are untuned against a live model.** Every test and the demo corpus
  run on recorded fixtures. The contracts and plumbing are verified; the quality
  of real model output is not yet.
- **The traceability graph is over-connected.** Agents declare their sources once
  per run, so a late agent that read sixteen artifacts cites all sixteen. The
  edges are accurate but impact analysis is less discriminating downstream. See
  [ADR-0010](docs/adr/0010-agent-roster-and-stage-ownership.md).
- **No syntax highlighting** in rendered code blocks — legible monospace only.
- **The Mutagent evaluator package could not be installed.** `mutagent install
  evaluator` fails on Windows with `spawn npm ENOENT` even with npm on PATH — the
  CLI spawns `npm` rather than `npm.cmd`. Reported through `mutagent feedback
  send`. The ADL methodology was followed regardless, with the evidence produced
  in-repo.

---

## Relationship with Mutagent

Mutagent is the engineering framework used to *develop* Project Victorious,
through its Agentic Development Lifecycle: Specification, Build, Evaluation,
Diagnosis, Optimization.

Project Victorious is the system being developed. It is not another Mutagent, and
it does not reimplement Helix. Mutagent develops AI systems; Victorious develops
software products. Mutagent is not part of the runtime.
