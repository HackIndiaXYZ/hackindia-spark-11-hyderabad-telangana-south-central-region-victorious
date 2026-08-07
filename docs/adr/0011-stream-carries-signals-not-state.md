# ADR-0011 — The live stream carries signals; the REST API carries state

- **Status:** Accepted
- **Date:** 2026-08-07
- **Milestone:** 6

## Context

`07_System_Architecture.md` requires users to "observe the complete AI
Engineering Organization operating in real time", and `10_UI_UX_Plan.md` forbids
hiding agent execution behind loading indicators. ADR-0005 chose Server-Sent
Events as the transport.

That leaves the question of *what* the stream carries. The obvious approach is to
push full agent-card snapshots, so the browser can render without another
request.

## Decision

The stream carries **event notifications only**. A client that cares about agent
state reacts by re-reading `GET /projects/{id}/agents`; a client rendering the
timeline re-reads `GET /projects/{id}`.

Pushing snapshots would mean the browser holds a second projection of agent and
artifact state, assembled from a different code path than the REST endpoints. The
two would eventually disagree, and the disagreement would show up as a workspace
displaying something the API does not believe — which is exactly the
consistency failure `12_Risk_Analysis.md` calls Context Drift, reproduced in the
client. One projection, in `app/api/views.py`, is worth an extra request.

Three consequences follow:

- **The first paint is server-rendered.** Pages fetch current state on the server
  and hand it to the client component as initial props, so the workspace is never
  a skeleton waiting for a socket.
- **Event bursts are debounced.** An agent finishing emits a completion, several
  artifact creations, and the next stage starting within milliseconds; refetching
  per event would issue a request each. A 300 ms debounce collapses the burst.
- **A failed refetch keeps the last known state.** The next event triggers
  another attempt, and blanking the grid over one dropped request is worse than a
  briefly stale card.

Two supporting details, both learned by testing:

**Subscribe before replaying.** The stream subscribes to the bus *first*, then
reads history. Reading first would drop anything published in between — a window
that opens precisely when the organization is busiest. Subscribing first can
duplicate an event instead, so replayed identifiers are remembered and skipped
until the first live event arrives.

**The heartbeat interval is injectable.** Comment frames every 15 seconds keep
proxies from closing an idle connection. With that value hard-coded, four tests
that exercise the idle path each waited the full interval and the suite took 60
seconds; injecting it brought that to one.

## Consequences

**Positive**

- One projection of state, so the workspace cannot disagree with the API.
- Reconnection is free: `EventSource` retries and replays `Last-Event-ID`, which
  the durable event log already understands as a cursor.
- The stream stays cheap — notifications, not payloads.

**Negative**

- One extra round trip per event burst. Negligible at MVP scale, and the price of
  not maintaining a second projection.
- The bus is in-process, so a multi-worker deployment would have each worker see
  only its own events. Fine for the current single-process deployment; a shared
  broker (Redis pub/sub — the dependency ADR-0005 deferred) is the path when that
  changes. Recorded so it is a known boundary rather than a surprise.

## Alternatives considered

**Push full state snapshots.** Rejected for the duplicate-projection reason
above.

**Poll the REST endpoints on a timer.** Rejected: it is either too slow to feel
live or wasteful when nothing is happening, and it cannot distinguish "idle" from
"disconnected" — which the stream indicator shows the user directly.
