"use client";

import { useCallback, useEffect, useState } from "react";
import { Radio } from "lucide-react";

import { AgentCard } from "@/components/agents/agent-card";
import { StreamIndicator } from "@/components/stream-indicator";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Organization"
        title="AI Engineering Organization"
        description={
          <>
            {working > 0
              ? `${working} specialist${working === 1 ? "" : "s"} working now.`
              : "Every specialist, and what it is doing right now."}{" "}
            Coordinated by the Executive AI, which assigns work and performs none of it.
          </>
        }
        actions={<StreamIndicator status={status} busy={refreshing} />}
      />

      <div className="grid gap-3 md:grid-cols-2">
        {agents.map((agent, index) => (
          <div
            key={agent.stage}
            className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
            style={{ animationDelay: `${Math.min(index * 45, 360)}ms` }}
          >
            <AgentCard agent={agent} projectId={projectId} />
          </div>
        ))}
      </div>

      {events.length > 0 && (
        <section className="space-y-3">
          <SectionLabel
            trailing={
              <span className="inline-flex items-center gap-1.5 text-[11px] text-content-subtle">
                <Radio className="size-3 text-state-active" aria-hidden="true" />
                streaming
              </span>
            }
          >
            Live activity
          </SectionLabel>

          <ul className="divide-y divide-border overflow-hidden rounded-[--radius-card] border border-border bg-surface panel-sheen elevated">
            {events.slice(0, 10).map((event) => (
              <li
                key={event.id}
                className="flex animate-[fade-in_0.3s_ease-out_both] items-baseline gap-3 px-4 py-2.5 text-xs transition-colors hover:bg-surface-raised/50"
              >
                <time className="shrink-0 font-mono text-content-subtle">
                  {new Date(event.created_at).toLocaleTimeString()}
                </time>
                <span className="text-content-muted">{event.summary}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
