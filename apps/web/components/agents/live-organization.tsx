"use client";

import { useCallback, useEffect, useState } from "react";

import { AgentCard } from "@/components/agents/agent-card";
import { StreamIndicator } from "@/components/stream-indicator";
import { api, type AgentCard as AgentCardData } from "@/lib/api";
import { useEventStream } from "@/lib/use-event-stream";

/**
 * The AI Engineering Organization, live.
 *
 * `07_System_Architecture.md` asks users to "observe the complete AI Engineering
 * Organization operating in real time". Cards transition as agents work, with no
 * refresh and no polling — the stream signals, and this re-reads the API.
 *
 * The server-rendered snapshot is the initial state, so the first paint is
 * complete rather than a skeleton. `10_UI_UX_Plan.md` explicitly rules out
 * hiding agent activity behind loading indicators.
 */
export function LiveOrganization({
  projectId,
  initialAgents,
}: {
  projectId: string;
  initialAgents: AgentCardData[];
}) {
  const [agents, setAgents] = useState(initialAgents);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setAgents(await api.getOrganization(projectId));
    } catch {
      // A failed refresh leaves the last known state on screen. The stream will
      // signal again on the next event, and blanking the grid over one dropped
      // request would be a worse experience than a slightly stale card.
    } finally {
      setRefreshing(false);
    }
  }, [projectId]);

  const { status, events } = useEventStream(projectId, refresh);

  // Server-rendered props go stale after a navigation back to this page.
  useEffect(() => setAgents(initialAgents), [initialAgents]);

  const working = agents.filter(
    (agent) => agent.status === "active" || agent.status === "reviewing",
  ).length;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-sm font-medium tracking-tight">
            AI Engineering Organization
          </h2>
          <p className="text-sm text-content-muted">
            {working > 0
              ? `${working} specialist${working === 1 ? "" : "s"} working now.`
              : "Every specialist, and what it is doing right now."}{" "}
            Coordinated by the Executive AI, which assigns work and performs none of it.
          </p>
        </div>
        <StreamIndicator status={status} busy={refreshing} />
      </header>

      <div className="grid gap-3 md:grid-cols-2">
        {agents.map((agent) => (
          <AgentCard key={agent.stage} agent={agent} projectId={projectId} />
        ))}
      </div>

      {events.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs tracking-wide text-content-subtle uppercase">
            Live activity
          </h3>
          <ul className="space-y-1.5 rounded-[--radius-card] border border-border bg-surface p-4">
            {events.slice(0, 10).map((event) => (
              <li key={event.id} className="flex gap-3 text-xs">
                <span className="shrink-0 font-mono text-content-subtle">
                  {new Date(event.created_at).toLocaleTimeString()}
                </span>
                <span className="text-content-muted">{event.summary}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
