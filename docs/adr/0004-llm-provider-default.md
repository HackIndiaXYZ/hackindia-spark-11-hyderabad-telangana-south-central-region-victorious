# ADR-0004 — Claude as the default reasoning provider

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 0 (abstraction), 2 (adapters)

## Context

Two specification documents conflict.

`08_Technology_Stack.md` names the LLM explicitly:

> | LLM | Gemini | Reasoning |

`15_Development_Guidelines.md` requires the opposite of a fixed choice:

> The platform should remain AI-provider agnostic. Avoid tightly coupling
> implementation to a single language model.

`12_Risk_Analysis.md` reinforces this, listing Model Availability as a Medium
risk mitigated by a "provider abstraction layer" and "support multiple LLM
providers".

Additional context: `08_Technology_Stack.md` specifies Claude Code as the
implementation environment, and `02_Proposed_Solution.md` specifies Mutagent's
Agentic Development Lifecycle as the development methodology.

## Decision

Build the provider abstraction first and treat the default as configuration.

- `LLMProvider` protocol in `app/llm/provider.py` (Milestone 2). Every agent
  depends on the protocol; no agent imports a vendor SDK.
- Three adapters ship: **Anthropic**, **Gemini**, and **Fixture**.
- The default is **Anthropic**, selected by `VICTORIOUS_LLM__PROVIDER`.

Anthropic is the default for one concrete reason: all seven agents produce typed
Pydantic contracts, and structured-output reliability is the property the whole
orchestration layer depends on. An agent returning malformed JSON does not
degrade gracefully — it halts a lifecycle stage.

The Gemini adapter is a real, exercised implementation, not a stub. Provider
agnosticism that is never tested against a second provider is a claim, not a
property.

This deviates from the literal text of `08_Technology_Stack.md`. Under the
precedence hierarchy in `15_Development_Guidelines.md`, Technology Stack ranks
9th and Development Guidelines is the document defining that hierarchy; the
provider-agnosticism requirement is also restated in `12_Risk_Analysis.md`. The
deviation is one line of configuration, reversible with an environment variable.

Confirmed with the project owner before implementation began.

## Consequences

**Positive**

- Satisfies both documents: Gemini is supported, and no layer is coupled to it.
- Provider outage is survivable at runtime, addressing the `12` Model
  Availability risk concretely.
- The fixture provider means the test suite makes no network calls and the demo
  cannot be broken by a provider incident — an explicit Milestone 10 requirement.

**Negative**

- Prompts must be validated against two providers, costing time in Milestone 2.
- The abstraction constrains the platform to capabilities both providers share.
  Acceptable: the agents need text and structured output, nothing exotic.

## Alternatives considered

**Gemini as default, per the literal table.** Rejected on structured-output
reliability grounds, which is the property the orchestration layer depends on.

**Runtime provider picker in the UI.** Deferred, not rejected. It is a genuinely
strong demonstration of provider agnosticism and belongs in project settings once
the workspace exists. Costed at roughly 45 minutes and not affordable in the
Milestone 0–4 budget.

**Single provider, no abstraction.** Rejected: contradicts two specification
documents and forecloses the risk mitigation both require.
