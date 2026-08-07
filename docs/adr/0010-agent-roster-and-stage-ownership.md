# ADR-0010 — Eight agents fill seven roles, and artifacts are rendered from structured output

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 4

## Context

`09_MVP_Roadmap.md` names seven roles for V1: Executive AI, Product Manager,
Business Analyst, Software Architect, Full Stack Engineer, QA Engineer, and
Documentation Agent. It also defines a nine-stage lifecycle.

Excluding `IDEA` — the state a project starts in rather than work anyone performs
— that leaves eight stages of engineering work and six specialist roles to cover
them, since the Executive AI coordinates without performing engineering work
(ADR-0009). The arithmetic does not divide evenly, and the specification does not
say how to reconcile it.

`11_Future_Roadmap.md` places the dedicated DevOps Engineer Agent in V2, so no
V1 role obviously owns `DEPLOYMENT_PREPARATION`.

## Decision

### Eight agents, six specialist roles

A role may own more than one stage, and each stage gets its own agent class with
its own output contract and its own prompt:

| Stage | Agent | Role |
|---|---|---|
| Requirement discovery | `ProductManagerAgent` | Product Manager |
| Business validation | `BusinessAnalystAgent` | Business Analyst |
| Architecture | `SoftwareArchitectAgent` | Software Architect |
| Development planning | `ImplementationPlannerAgent` | Software Architect |
| Implementation | `FullStackEngineerAgent` | Full Stack Engineer |
| Testing | `QAEngineerAgent` | QA Engineer |
| Documentation | `DocumentationAgent` | Documentation |
| Deployment preparation | `DeploymentPreparationAgent` | Documentation |

Designing a system and sequencing the work to build it are genuinely different
tasks with different outputs, and `09_MVP_Roadmap.md` puts an architecture
approval gate between them. One agent covering both would need a contract that is
the union of two unrelated shapes, and a prompt that switches behaviour on which
stage it happens to be in.

**Deployment preparation is owned by the Documentation role** because the DevOps
Agent is a V2 capability. What `13_Demo_and_Pitch.md` Step 11 asks to display —
a deployment checklist, environment configuration, containerisation — is a set of
documents derived from decisions the organization has already approved, not new
infrastructure engineering. The agent's prompt forbids introducing infrastructure
the organization never chose, and requires listing environment variables by name
and purpose only. When the DevOps Agent lands, it takes this stage over by
changing one entry in `STAGE_OWNERS`.

### Registration is validated, not trusted

`RegistryDispatcher` keys agents by **stage**, not role, and validates on
registration that the agent's declared role matches
`app.domain.lifecycle.STAGE_OWNERS` for that stage. Keying by role — the original
Milestone 3 design — would have dispatched development planning to the
architecture agent, which would then have written its artifacts tagged with the
wrong stage. A mis-wired organization now fails at startup.

### Artifacts are rendered from structured output, not written as prose

Agent contracts carry typed fields — requirements, components, endpoints, test
cases. `BaseAgent.compose_artifacts` renders the markdown document from those
fields; the model does not write the document.

This means the document a human reads and the data a downstream agent consumes
are the same information, and cannot drift. It also spends the model's output
budget on engineering content rather than on formatting the same information
twice, and it makes every project's artifacts consistently structured.

Upstream declarations are made once per run, in `AgentOutput.sources`, and
attached to every artifact the run produces.

## Consequences

**Positive**

- Each agent has one contract, one prompt, and one job.
- Adding the V2 specialists is a class plus a `STAGE_OWNERS` entry.
- Rendered documents cannot disagree with their structured content.
- A mis-registered organization fails at startup rather than producing artifacts
  attributed to the wrong specialist.

**Negative**

- Run-level `sources` over-connects the traceability graph. A late agent that
  reads sixteen upstream artifacts declares all sixteen as sources for each of
  its outputs, which on the hospital scenario produces 205 edges across 22
  artifacts. The edges are *accurate* — the agent genuinely consumed that
  context — but impact analysis becomes less discriminating the further
  downstream you go, because almost everything traces to almost everything.
  Milestone 8 should either ask agents for per-artifact sources or weight impact
  by trace kind and depth. Recorded here so it is a known limitation rather than
  a surprise.
- Two agents sharing the Documentation role means the Agent Organization view
  shows one card for a role that has two distinct current tasks. The view will
  need to key on stage, not role.

## Alternatives considered

**One agent per role, branching on stage.** Rejected: a union contract and a
prompt that switches on stage is exactly the "collection of disconnected AI
agents" `15_Development_Guidelines.md` says the product must not resemble.

**Introduce a DevOps agent early to own deployment preparation.** Rejected:
`09_MVP_Roadmap.md` explicitly excludes it, and `15_Development_Guidelines.md`
says not to implement future roadmap capabilities prematurely.

**Let the model write `body_markdown` directly.** Rejected: the document and the
structured content would be two independent generations of the same information,
free to disagree — the drift this platform exists to eliminate.
