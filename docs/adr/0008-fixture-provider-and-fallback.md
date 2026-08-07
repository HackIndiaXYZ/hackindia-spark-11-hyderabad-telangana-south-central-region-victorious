# ADR-0008 — Recorded fixtures are a first-class provider, and the fallback is silent-but-visible

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 2

## Context

`12_Risk_Analysis.md` rates Model Availability a Medium risk and prescribes
"graceful fallback strategies". `13_Demo_and_Pitch.md` requires a polished
end-to-end demonstration and states that trade-offs should favour the
demonstration narrative.

A live provider outage during a judged demo is unrecoverable, and the demo is the
deliverable. Separately, the test suite must never make network calls: tests that
depend on a provider are slow, flaky, and cost money.

Two questions follow. What backs the platform when no live provider is
available? And what should happen at startup when the configured provider cannot
be built — almost always a missing API key?

## Decision

### Fixtures are a provider, not a mock

`FixtureProvider` implements the full `LLMProvider` protocol by replaying
recorded JSON from disk. It is selected the same way as any other provider,
through `VICTORIOUS_LLM__PROVIDER=fixture`.

Fixtures are named by an explicit `fixture_key` the agent supplies — for example
`software_architect.architecture.json` — rather than by a content hash. A
reviewer can open, read, and hand-edit a recording, which a hash filename would
prevent. Recorded token counts are replayed too, so a fixture-backed demo still
shows realistic figures on the agent cards rather than zeros.

`RecordingProvider` wraps any live provider and writes fixtures as it goes,
enabled by `VICTORIOUS_LLM__RECORD_FIXTURES=true`. One live run produces the
entire offline demo corpus. It is a decorator rather than a flag inside each
adapter, so every present and future provider gains recording for free.

Fixture mismatches fail loudly: a recording that no longer validates against its
agent's contract raises rather than silently returning stale data. A contract
change with an unrefreshed recording would otherwise surface as inexplicable demo
behaviour.

### A live provider that cannot be built falls back to fixtures

`build_provider` catches construction failure — a missing API key, most often —
logs a warning, and returns the fixture provider instead of raising.

The alternative, refusing to start, is worse for this project. The platform is
fully explorable on recorded fixtures; a contributor without a key should be able
to run it, and a demo machine with a mistyped environment variable should degrade
rather than show a stack trace on stage.

The obvious risk is a production deployment silently running on stale recordings.
Three things make the fallback visible rather than hidden:

- a warning log naming the requested provider and the reason;
- `ProviderHealthCheck` reporting **degraded** with the message "Configured for
  anthropic, running on recorded fixtures", surfaced by `/health/ready` and by
  the workspace status panel;
- `provider` and `model` recorded on **every** `AgentRun`, so any artifact can be
  traced to the backend that actually produced it.

The health check deliberately does not call the provider. A readiness probe that
spends tokens on every poll would be expensive and would consume rate limit.

## Consequences

**Positive**

- The demo cannot be broken by a provider incident, satisfying `12`'s Model
  Availability mitigation concretely.
- The test suite makes no network calls and needs no credentials.
- A fresh checkout runs with no API key at all.
- Recording is a decorator, so it composes with any future provider.

**Negative**

- A misconfigured production deployment would serve stale reasoning rather than
  failing fast. Mitigated by the three signals above, but they must be *watched* —
  the degraded readiness status is the one that belongs on an alert.
- Fixtures go stale as agent contracts evolve. Mitigated by failing loudly on
  mismatch, and by re-recording being a single flagged run.

## Alternatives considered

**Fail fast on a missing key.** Rejected: it makes the common developer case
hostile and the demo failure mode worse, for a benefit the degraded health status
already provides.

**Fallback to a second live provider.** Attractive, and the abstraction supports
it, but it turns a missing key into a surprise bill on a different account and
does nothing for the offline demo case. Worth revisiting once both providers are
credentialed in a deployed environment.

**In-code mocks for tests instead of fixtures.** Rejected: mocks drift from real
provider behaviour, and they would not have produced the demo insurance that
motivated the work in the first place.
