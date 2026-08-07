import Link from "next/link";
import { AlertTriangle, ArrowRight } from "lucide-react";

import { TraceGraph } from "@/components/trace/trace-graph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, stageLabel, typeLabel } from "@/lib/api";

/**
 * Traceability — every artifact and what it was derived from.
 *
 * This answers the questions `04_Existing_Solutions.md` says no tool on the
 * market answers. The graph *visualisation* arrives in Milestone 8; this view
 * already shows the same underlying data as navigable text, including which
 * derivations have gone out of date and by how many versions.
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
    <div className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-sm font-medium tracking-tight">Traceability</h2>
        <p className="text-sm text-content-muted">
          {graph.nodes.length} artifacts connected by {graph.edges.length} declared
          dependencies. Staleness is computed from this graph, never stored — an
          artifact is out of date when it cites an older version than its upstream
          currently has.
        </p>
      </header>

      {staleEdges.length > 0 && (
        <Card className="border-state-stale/30">
          <CardHeader className="flex-row items-center gap-2">
            <AlertTriangle className="size-4 text-state-stale" aria-hidden="true" />
            <CardTitle>{staleEdges.length} derivations are out of date</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {staleEdges.map((edge) => {
                const upstream = nodes.get(edge.upstream_artifact_id);
                const downstream = nodes.get(edge.downstream_artifact_id);
                return (
                  <li key={edge.id} className="text-sm">
                    <span className="text-content">{downstream?.title}</span>{" "}
                    <span className="text-content-subtle">
                      was derived from {upstream?.title} v{edge.upstream_version}, now v
                      {edge.current_upstream_version}
                    </span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      <TraceGraph graph={graph} projectId={id} />

      <h3 className="text-xs tracking-wide text-content-subtle uppercase">
        Dependencies, artifact by artifact
      </h3>

      {graph.nodes.length === 0 ? (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-content-muted">
              No artifacts yet, so nothing to trace.
            </p>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-2">
          {graph.nodes.map((node) => {
            const upstream = upstreamOf.get(node.id) ?? [];
            return (
              <li
                key={node.id}
                className="rounded-[--radius-card] border border-border bg-surface p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      href={`/projects/${id}/artifacts/${node.id}`}
                      className="text-sm text-content hover:text-accent"
                    >
                      {node.title}
                    </Link>
                    <p className="mt-0.5 text-xs text-content-subtle">
                      {typeLabel(node.type)} · {stageLabel(node.stage)} · v{node.version}
                    </p>
                  </div>
                  {node.is_stale && <StatusBadge state="stale">stale</StatusBadge>}
                </div>

                {upstream.length > 0 && (
                  <div className="mt-3 space-y-1 border-l-2 border-border pl-3">
                    <p className="text-xs text-content-subtle">Derived from</p>
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
                              className="truncate hover:text-accent"
                            >
                              {source?.title ?? edge.upstream_artifact_id}
                            </Link>
                            <span className="shrink-0 font-mono text-[11px] text-content-subtle">
                              v{edge.upstream_version}
                            </span>
                            {edge.is_stale && (
                              <span className="shrink-0 text-[11px] text-state-stale">
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
    </div>
  );
}
