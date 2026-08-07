import Link from "next/link";
import { AlertTriangle, ArrowRight, GitBranch } from "lucide-react";

import { TraceGraph } from "@/components/trace/trace-graph";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, stageLabel, typeLabel } from "@/lib/api";

/**
 * Traceability — every artifact and what it was derived from.
 *
 * This answers the questions `04_Existing_Solutions.md` says no tool on the
 * market answers. The graph is the headline, and the same data follows as
 * navigable text so the relationships are readable rather than only visible.
 */

export const metadata = { title: "Traceability" };
export const dynamic = "force-dynamic";

export default async function TraceabilityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const graph = await api.getTraceability(id);

  const nodes = new Map(graph.nodes.map((node) => [node.id, node]));
  const upstreamOf = new Map<string, typeof graph.edges>();
  for (const edge of graph.edges) {
    const existing = upstreamOf.get(edge.downstream_artifact_id);
    if (existing) existing.push(edge);
    else upstreamOf.set(edge.downstream_artifact_id, [edge]);
  }

  const staleEdges = graph.edges.filter((edge) => edge.is_stale);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Provenance"
        title="Traceability"
        description={
          <>
            {graph.nodes.length} artifacts connected by {graph.edges.length} declared
            dependencies. Staleness is computed from this graph, never stored — an
            artifact is out of date when it cites an older version than its upstream
            currently has.
          </>
        }
        actions={
          staleEdges.length > 0 ? (
            <StatusBadge state="stale">
              {staleEdges.length} out of date
            </StatusBadge>
          ) : graph.edges.length > 0 ? (
            <StatusBadge state="complete">all current</StatusBadge>
          ) : undefined
        }
        className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
      />

      {staleEdges.length > 0 && (
        <section className="animate-[rise_0.45s_var(--ease-out-quint)_both] space-y-2.5 rounded-[--radius-card] border border-state-stale/35 bg-state-stale/[0.06] p-4">
          <h3 className="flex items-center gap-2 text-sm font-medium text-content">
            <AlertTriangle className="size-4 text-state-stale" aria-hidden="true" />
            {staleEdges.length} derivations are out of date
          </h3>
          <ul className="space-y-1.5">
            {staleEdges.map((edge) => {
              const upstream = nodes.get(edge.upstream_artifact_id);
              const downstream = nodes.get(edge.downstream_artifact_id);
              return (
                <li key={edge.id} className="text-sm leading-relaxed">
                  <span className="text-content">{downstream?.title}</span>{" "}
                  <span className="text-content-subtle">
                    was derived from {upstream?.title}{" "}
                    <span className="font-mono">v{edge.upstream_version}</span>, now{" "}
                    <span className="font-mono text-state-stale">
                      v{edge.current_upstream_version}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <TraceGraph graph={graph} projectId={id} />

      <section className="space-y-3">
        <SectionLabel>Dependencies, artifact by artifact</SectionLabel>

        {graph.nodes.length === 0 ? (
          <EmptyState
            icon={GitBranch}
            title="Nothing to trace yet"
            description="Once the organization produces artifacts, every derivation it declares appears here — and changing an upstream artifact immediately shows what it invalidates."
          />
        ) : (
          <ul className="space-y-2">
            {graph.nodes.map((node, index) => {
              const upstream = upstreamOf.get(node.id) ?? [];
              return (
                <li
                  key={node.id}
                  className="animate-[rise_0.35s_var(--ease-out-quint)_both] rounded-[--radius-card] border border-border bg-surface panel-sheen p-4 elevated transition-colors duration-200 hover:border-border-strong"
                  style={{ animationDelay: `${Math.min(index * 25, 220)}ms` }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/projects/${id}/artifacts/${node.id}`}
                        className="text-sm text-content transition-colors hover:text-accent"
                      >
                        {node.title}
                      </Link>
                      <p className="mt-0.5 text-xs text-content-subtle">
                        {typeLabel(node.type)} · {stageLabel(node.stage)} · v
                        {node.version}
                      </p>
                    </div>
                    {node.is_stale && (
                      <StatusBadge state="stale" size="sm">
                        stale
                      </StatusBadge>
                    )}
                  </div>

                  {upstream.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-l-2 border-border pl-3">
                      <p className="text-[10px] font-medium tracking-[0.08em] text-content-subtle uppercase">
                        Derived from
                      </p>
                      <ul className="space-y-1">
                        {upstream.slice(0, 8).map((edge) => {
                          const source = nodes.get(edge.upstream_artifact_id);
                          return (
                            <li
                              key={edge.id}
                              className="flex items-center gap-2 text-xs text-content-muted"
                            >
                              <ArrowRight
                                className="size-3 shrink-0 text-content-subtle"
                                aria-hidden="true"
                              />
                              <Link
                                href={`/projects/${id}/artifacts/${edge.upstream_artifact_id}`}
                                className="truncate transition-colors hover:text-accent"
                              >
                                {source?.title ?? edge.upstream_artifact_id}
                              </Link>
                              <span className="shrink-0 font-mono text-[11px] text-content-subtle">
                                v{edge.upstream_version}
                              </span>
                              {edge.is_stale && (
                                <span className="shrink-0 rounded border border-state-stale/30 bg-state-stale/10 px-1 text-[10px] text-state-stale">
                                  out of date
                                </span>
                              )}
                            </li>
                          );
                        })}
                        {upstream.length > 8 && (
                          <li className="text-xs text-content-subtle">
                            …and {upstream.length - 8} more
                          </li>
                        )}
                      </ul>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
