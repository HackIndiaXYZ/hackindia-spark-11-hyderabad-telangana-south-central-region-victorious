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

**Milestone 3 of 10 complete — Executive AI & lifecycle orchestration.**

In place so far: the architectural boundaries, dependency injection,
configuration, structured logging, error envelope, and health checking (M0); the
shared organizational memory holding projects, artifacts with append-only version
history, the traceability graph, agent runs, approvals, and events (M1); the
reasoning-provider abstraction plus the agent execution framework (M2); and the
Executive AI driving a LangGraph workflow across the nine lifecycle stages, with
dependency gating, deterministic conflict detection, and human approval gates
that genuinely halt (M3).

The seven engineering agents themselves arrive in Milestone 4. Until then the
organization coordinates correctly and reports "no agent is registered to perform
requirement_discovery" — the honest state of the system rather than a silent
no-op.

Three properties are already load-bearing:

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
      agents/     Agent execution framework + prompts (roles land in M4)
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

## Relationship with Mutagent

Mutagent is the engineering framework used to *develop* Project Victorious,
through its Agentic Development Lifecycle: Specification, Build, Evaluation,
Diagnosis, Optimization.

Project Victorious is the system being developed. It is not another Mutagent, and
it does not reimplement Helix. Mutagent develops AI systems; Victorious develops
software products. Mutagent is not part of the runtime.
