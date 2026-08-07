# Evaluation

Evidence that Project Victorious was built through Mutagent's Agentic
Development Lifecycle — Specification, Build, Evaluation, Diagnosis, Optimization
— as `02_Proposed_Solution.md` requires.

Everything here runs offline on recorded fixtures. No API key, no network.

```bash
# Scorecards across the evaluation dataset
apps/api/.venv/Scripts/python evaluation/run_evaluation.py

# The documented ADL cycle, measured
apps/api/.venv/Scripts/python evaluation/adl_cycle.py
```

Both exit non-zero on regression, so either can gate a build.

## What is here

| Path | What it is |
|---|---|
| `datasets/project_briefs.json` | Three project briefs, each the two-field input a real user provides |
| `scorers.py` | Eight deterministic scorers over what the organization produced |
| `run_evaluation.py` | Drives each brief through the full lifecycle and scores it |
| `adl_cycle.py` | Reproduces the traceability-convergence cycle with before/after numbers |
| `scorecards/` | Generated output: `latest.json`, timestamped archives, `adl_cycle.json` |
| `optimization-report.md` | The write-up: cycles run, what was diagnosed, what changed |

## The scorers

Each measures an obligation the specification states, normalised 0–1.

| Scorer | Question | Source |
|---|---|---|
| `lifecycle_completion` | Did the organization finish the lifecycle? | `09_MVP_Roadmap.md` |
| `artifact_completeness` | Were all eight required artifacts produced? | `09_MVP_Roadmap.md` |
| `traceability_completeness` | Can every downstream artifact be traced to its source? | `04_Existing_Solutions.md` |
| `internal_consistency` | Is the delivered project free of stale derivations? | `12_Risk_Analysis.md` |
| `requirement_coverage` | What fraction of requirements have tests? | `05_AI_Agent_Architecture.md` |
| `decision_reviewability` | Can a human actually review the technology decisions? | `09_MVP_Roadmap.md` |
| `approval_discipline` | Were the required gates raised? | `09_MVP_Roadmap.md` |
| `agent_transparency` | Did every agent report reasoning and confidence? | `12_Risk_Analysis.md` |

None asks a language model to judge quality. `12_Risk_Analysis.md` rates AI
Hallucination a High risk, and a hallucinating grader would report improvement
that did not happen — the one failure that makes an evaluation harness worse than
none.

The limits of that choice, and of running on domain-independent fixtures, are
stated in [`optimization-report.md`](optimization-report.md#honest-limitations).

## Headline result

The traceability-convergence cycle found that re-synchronisation was
**divergent** — rebuilding stale work left *more* stale derivations than before
it, because superseded trace edges still cited the versions they originally
consumed.

| After re-synchronisation | Stale derivations |
|---|---:|
| With the defect | **167** |
| After the optimization | **0** |

Left unfixed, the demo would have shown the organization rebuilding everything
and the workspace still reporting the project inconsistent — precisely the
failure the platform claims to prevent.
