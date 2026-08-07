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

**Milestone 0 of 10 — Foundation & architectural skeleton.**

The architectural boundaries, dependency injection, configuration, structured
logging, error envelope, and health checking are in place and tested. The
engineering agents themselves arrive in Milestones 2–4.

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

**Configuration** — copy `.env.example` to `.env`. No API key is needed until
Milestone 2; the `fixture` provider replays recorded responses offline.

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
      api/        HTTP transport only
    tests/
  web/            Next.js — the engineering workspace
docs/             Specification (read-only) — see docs/adr/ for decisions
evaluation/       Mutagent ADL artifacts (Milestone 9)
```

Dependencies point inward: `api → orchestration → agents → memory → domain`.

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
