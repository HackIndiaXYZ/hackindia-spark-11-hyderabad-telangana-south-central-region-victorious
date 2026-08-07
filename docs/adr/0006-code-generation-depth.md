# ADR-0006 — Generated output is an inspectable scaffold, not a runnable application

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0 (scope), 4 (implementation)

## Context

The specification describes the platform's output three different ways.

`01_Problem_Statement.md`, `02_Proposed_Solution.md`, and
`14_Executive_Summary.md` describe transforming ideas into **production-ready
software**.

`09_MVP_Roadmap.md` narrows this: "Produce an **initial** production-ready
software implementation", with the artifact list naming "**Initial** Source
Code".

`13_Demo_and_Pitch.md` Step 6 is narrower still — the Full Stack Engineer Agent
shows "generated repository structure, Backend, Frontend, APIs, Database schema"
and "development progress inside the workspace". It asks for generated structure
to be *displayed*. It never asks for a generated application to *run*.

`13` also states the tie-break: "Whenever implementation trade-offs arise,
prioritize features that strengthen the demonstration narrative."

## Decision

The Full Stack Engineer Agent produces a **coherent, inspectable repository
scaffold**: directory structure, key backend and frontend source files, database
schema, and API contracts — rendered with syntax highlighting in the Development
Center, and traced back to the requirements and architecture decisions that
produced each file.

It does **not** produce a generated application that builds and runs.

The reasoning is a judgement about where this project's value sits.
`04_Existing_Solutions.md` establishes that AI coding assistants already generate
code well, and that the unaddressed gap is coordination:

> Is the architecture still consistent with the latest requirements?
> Which downstream components are affected by this requirement change?

A generated application that runs would be the least differentiated part of the
demonstration — every AI coding tool does that. The traceability graph and change
propagation are what no existing tool does, and the hours are finite. Spending
them on runnable code generation would produce a worse demonstration of the
platform's actual thesis.

Stated plainly: this is a scope reduction against the strongest reading of `01`,
`02`, and `14`. It is consistent with `09` and with `13`, the document that
governs trade-offs. Confirmed with the project owner before implementation began.

## Consequences

**Positive**

- Preserves the full Milestone 8 budget for traceability and change propagation.
- Generated artifacts remain honest — nothing implies a runnable application.
- Every generated file carries `derived_from` edges, so the demonstration shows
  *why* each file exists, which is a stronger claim than that it compiles.

**Negative**

- A judge asking "can I run the generated app?" gets "no". The answer is that
  the platform coordinates engineering decisions and the generated scaffold is
  traceable to them — but the limitation is real and should be stated directly
  rather than deflected.
- The strongest reading of `01`, `02`, and `14` is not met in V1.

## Alternatives considered

**Generated project as a downloadable archive.** Deferred, not rejected. Roughly
one additional hour. Rejected for now because unrunnable code in a judge's hands
is worse than the same code viewed in context with its traceability intact.

**Fully runnable generated application.** Rejected as not achievable within 24
hours alongside Milestones 0–10, and because it would consume the budget for the
capability that actually differentiates the platform.
