# Optimization Report

Evidence that Project Victorious was developed through Mutagent's Agentic
Development Lifecycle, as `02_Proposed_Solution.md` requires:

> Evaluation datasets, scorecards, reasoning traces, architectural decisions, and
> optimization reports should be generated throughout development to demonstrate
> continuous improvement of the platform.

Everything below is reproducible. Run `evaluation/run_evaluation.py` for the
scorecards and `evaluation/adl_cycle.py` for the measured cycle.

---

## Cycle: traceability convergence

The cycle worth documenting in full, because the defect it found would have
silently disabled the platform's central capability.

### Specification

> An artifact must stop being reported as out of date once it has been rebuilt
> against the current version of its upstream.

This is the closing half of the claim `04_Existing_Solutions.md` says nothing on
the market makes. Detecting that work has gone stale is worth little if the
system cannot then tell you it is fixed.

### Build

Milestone 7 added re-synchronisation: when artifacts go stale, the Executive AI
raises a `RESYNCHRONISATION` gate, and approving it reruns the specialists that
own the stale work against the current upstream.

### Evaluation

`evaluation/adl_cycle.py` drives a project to delivery, revises a requirement,
re-synchronises, and counts stale derivations. Staleness is measured **two ways
from the same graph** — evaluating every edge ever declared, and evaluating only
the current declaration of each dependency — so the difference is a measurement
rather than an assertion.

| Stage | Edges | Current declarations | Stale (defect) | Stale (optimized) |
|---|---:|---:|---:|---:|
| Baseline, after delivery | 205 | 205 | 0 | 0 |
| After the requirement change | 205 | 205 | 19 | 19 |
| After re-synchronisation | 410 | 205 | **167** | **0** |

### Diagnosis

The rebuild made things *worse*: 19 stale derivations became 167.

Trace edges are immutable by design (ADR-0007), so the history of how a project
was reasoned about survives. A rebuilding agent therefore **adds** a declaration
rather than updating the existing one — visible above as the edge count doubling
from 205 to 410 while the number of distinct dependencies stayed at 205.

Every superseded edge still cited the version it originally consumed. Evaluating
all of them meant an artifact stayed stale no matter how many times it was
regenerated, and each rebuild added more stale edges than it resolved. The loop
was not merely broken; it was **divergent**.

Left unfixed, the demo would have shown the organization dutifully rebuilding
everything and the workspace still reporting the project inconsistent — the exact
failure the platform claims to prevent.

### Optimization

`current_edges()` in `app/domain/traceability.py`: staleness considers only the
most recent declaration of each `(upstream, downstream, kind)` dependency.
Superseded edges remain in the graph as history, which is what ADR-0007 wanted
them for.

Deleting them was the alternative, and was rejected — the record of how the
project was reasoned about is the thing worth keeping.

### Re-evaluation

**167 → 0.** The rebuild now converges, verified by the table above and by
`test_traceability_api.py::test_current_edges_keeps_only_the_latest_declaration`.

A second consequence surfaced afterwards: the traceability API was returning all
410 edges, so the graph drew each dependency twice with different upstream
versions. Fixed in Milestone 8 by returning only current declarations.

---

## Scorecards

`evaluation/run_evaluation.py` drives three project briefs through the full
lifecycle and scores what the organization produced. Latest run:

| Score | Hospital | College ERP | Event Booking |
|---|---:|---:|---:|
| Lifecycle completion | 100% | 100% | 100% |
| Artifact completeness | 100% | 100% | 100% |
| Traceability completeness | 100% | 100% | 100% |
| Internal consistency | 100% | 100% | 100% |
| Requirement coverage | 50% | 50% | 50% |
| Decision reviewability | 100% | 100% | 100% |
| Approval discipline | 100% | 100% | 100% |
| Agent transparency | 100% | 100% | 100% |
| **Overall** | **94%** | **94%** | **94%** |

`requirement_coverage` at 50% is the QA Engineer correctly reporting that one
requirement has no test because it was written without acceptance criteria. The
scorer reads the coverage report the agent produced, so an agent that quietly
omitted uncovered requirements would score *higher* here while being less
trustworthy — which is why the traceability and orphan scorers sit alongside it.

---

## Other cycles run during development

Shorter, but each followed the same loop. Every one was found by evaluation or by
a test, not by review.

| Specification | Diagnosis | Optimization | Milestone |
|---|---|---|---|
| No artifact may be invisible to impact analysis | Agents could produce artifacts declaring no upstream | Orphan guard fails the run; the first stage is exempt because it legitimately has none | 2 |
| An agent must be able to satisfy its own contract | The rendered context never included artifact IDs, so "cite the upstream you used" was impossible against a real model | Context emits IDs prominently | 3 |
| A failing stage must not be retried forever | The edge back to coordination was unconditional; a failing stage looped to the recursion limit | Conditional edge on the halt flag | 3 |
| Token cost must be measurable before deciding to cache | `BaseAgent` discarded the provider's usage | Usage, provider, and model recorded per run | 4 |
| A project must recover from a rejection | Stale work blocked everything, including the gate that would re-approve the revised work | Conflicts block execution, not gates; stale work proposes re-synchronisation | 7 |
| A stage must not run twice for one gate | An agent-raised gate un-completed the stage that had just finished | Only a stage that has not run is marked awaiting approval | 7 |

---

## Honest limitations

**Fixtures are domain-independent.** The evaluation runs on recorded reasoning
keyed by role and stage, not by project, so all three briefs replay the same
payloads — which is why their scores are identical. What this measures is the
*organization's structural conformance*: does every artifact get produced, traced,
gated, and explained. It does **not** measure whether the requirements written for
a college ERP are good requirements for a college ERP. That needs a live provider
run, and is the first thing to do with an API key.

**The scorers are structural by choice.** None asks a language model to judge
quality, because a hallucinating grader would report improvement that did not
happen — the one failure that makes an evaluation harness worse than none. The
cost is that these scores say nothing about whether a requirement is a good idea.
That judgement stays with the human at the approval gate.

**The Mutagent evaluator package could not be installed.** `mutagent install
evaluator` fails on Windows with `spawn npm ENOENT` even with npm on PATH,
because the CLI spawns `npm` rather than `npm.cmd` and Node cannot resolve a
`.cmd` shim without `shell: true`. Reported to the Mutagent team through
`mutagent feedback send` (feedback id `e67078ea-39c4-4b2f-8366-3c2568ae45c5`).
The ADL *methodology* was followed regardless, with the evidence produced in-repo
by the harness in this directory.
