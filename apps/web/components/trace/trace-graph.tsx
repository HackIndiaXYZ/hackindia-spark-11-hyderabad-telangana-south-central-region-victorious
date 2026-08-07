"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { stageLabel, typeLabel, type TraceGraph as TraceGraphData } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * The traceability graph, laid out by lifecycle stage.
 *
 * Drawn as inline SVG rather than with a graph library. A force-directed layout
 * would produce a hairball: this graph has hundreds of edges and, more
 * importantly, it already *has* a meaningful axis. Work flows through the
 * lifecycle, so stages become columns and dependencies read left to right. That
 * is the shape of the engineering process, and it makes the picture explain
 * something rather than merely look complicated.
 *
 * Selecting a node dims everything unrelated and keeps only its upstream and
 * downstream. With this many edges, the useful question is never "show me all of
 * it" but "what does *this* depend on, and what depends on it".
 */

const COLUMN_WIDTH = 210;
const ROW_HEIGHT = 62;
const NODE_WIDTH = 168;
const NODE_HEIGHT = 42;
const PADDING = 28;

interface Positioned {
  id: string;
  title: string;
  type: string;
  stage: string;
  version: number;
  isStale: boolean;
  x: number;
  y: number;
}

export function TraceGraph({
  graph,
  projectId,
}: {
  graph: TraceGraphData;
  projectId: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const { nodes, byId, columns, width, height } = useMemo(() => {
    // Columns follow lifecycle order, taken from the data rather than a hard-coded
    // list so a stage that produced nothing does not leave an empty column.
    const stages = [...new Set(graph.nodes.map((node) => node.stage))];
    const rowCursor = new Map<string, number>();

    const positioned: Positioned[] = graph.nodes.map((node) => {
      const column = stages.indexOf(node.stage);
      const row = rowCursor.get(node.stage) ?? 0;
      rowCursor.set(node.stage, row + 1);

      return {
        id: node.id,
        title: node.title,
        type: node.type,
        stage: node.stage,
        version: node.version,
        isStale: node.is_stale,
        x: PADDING + column * COLUMN_WIDTH,
        y: PADDING + 34 + row * ROW_HEIGHT,
      };
    });

    const tallest = Math.max(1, ...[...rowCursor.values()]);

    return {
      nodes: positioned,
      byId: new Map(positioned.map((node) => [node.id, node])),
      columns: stages,
      width: PADDING * 2 + Math.max(1, stages.length) * COLUMN_WIDTH,
      height: PADDING * 2 + 34 + tallest * ROW_HEIGHT,
    };
  }, [graph]);

  /** Nodes connected to the selection, in either direction. */
  const related = useMemo(() => {
    if (!selected) return null;
    const connected = new Set<string>([selected]);
    for (const edge of graph.edges) {
      if (edge.upstream_artifact_id === selected) connected.add(edge.downstream_artifact_id);
      if (edge.downstream_artifact_id === selected) connected.add(edge.upstream_artifact_id);
    }
    return connected;
  }, [selected, graph.edges]);

  const isDimmed = (id: string) => related !== null && !related.has(id);

  if (graph.nodes.length === 0) {
    return (
      <p className="rounded-[--radius-card] border border-border bg-surface p-8 text-center text-sm text-content-muted">
        No artifacts yet, so nothing to trace.
      </p>
    );
  }

  const selectedNode = selected ? byId.get(selected) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 text-xs text-content-subtle">
        <Legend swatch="bg-state-complete" label="Current" />
        <Legend swatch="bg-state-stale" label="Out of date" />
        <span className="text-content-subtle">
          {selected ? "Showing one artifact's dependencies" : "Select an artifact to focus it"}
        </span>
        {selected && (
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="text-accent hover:text-accent-hover"
          >
            Clear
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-[--radius-card] border border-border bg-surface">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Traceability graph: ${graph.nodes.length} artifacts, ${graph.edges.length} dependencies`}
          className="min-w-full"
        >
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 8 4 L 0 8 z" className="fill-border-strong" />
            </marker>
            <marker
              id="arrow-stale"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="5"
              markerHeight="5"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 8 4 L 0 8 z" className="fill-state-stale" />
            </marker>
          </defs>

          {columns.map((stage, index) => (
            <text
              key={stage}
              x={PADDING + index * COLUMN_WIDTH}
              y={PADDING}
              className="fill-content-subtle text-[10px] uppercase"
              style={{ fontSize: 10, letterSpacing: "0.06em" }}
            >
              {stageLabel(stage as never)}
            </text>
          ))}

          {graph.edges.map((edge) => {
            const from = byId.get(edge.upstream_artifact_id);
            const to = byId.get(edge.downstream_artifact_id);
            if (!from || !to) return null;

            const dimmed =
              related !== null &&
              !(
                related.has(edge.upstream_artifact_id) &&
                related.has(edge.downstream_artifact_id)
              );

            const x1 = from.x + NODE_WIDTH;
            const y1 = from.y + NODE_HEIGHT / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_HEIGHT / 2;
            const midpoint = (x1 + x2) / 2;

            return (
              <path
                key={edge.id}
                d={`M ${x1} ${y1} C ${midpoint} ${y1}, ${midpoint} ${y2}, ${x2} ${y2}`}
                fill="none"
                strokeWidth={edge.is_stale ? 1.6 : 1}
                markerEnd={edge.is_stale ? "url(#arrow-stale)" : "url(#arrow)"}
                className={cn(
                  edge.is_stale ? "stroke-state-stale" : "stroke-border-strong",
                  dimmed ? "opacity-[0.06]" : edge.is_stale ? "opacity-90" : "opacity-40",
                )}
              >
                {edge.is_stale && (
                  <title>
                    Derived from v{edge.upstream_version}, now v
                    {edge.current_upstream_version}
                  </title>
                )}
              </path>
            );
          })}

          {nodes.map((node) => {
            const dimmed = isDimmed(node.id);
            const active = node.id === selected;

            return (
              <g
                key={node.id}
                transform={`translate(${node.x} ${node.y})`}
                className={cn("cursor-pointer", dimmed && "opacity-20")}
                onClick={() => setSelected(active ? null : node.id)}
                role="button"
                tabIndex={0}
                aria-label={`${node.title}, ${typeLabel(node.type)}${node.isStale ? ", out of date" : ""}`}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelected(active ? null : node.id);
                  }
                }}
              >
                <rect
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={6}
                  className={cn(
                    "transition-colors",
                    node.isStale
                      ? "fill-state-stale/10 stroke-state-stale/50"
                      : "fill-surface-raised stroke-border",
                    active && "stroke-accent",
                  )}
                  strokeWidth={active ? 2 : 1}
                />
                <text x={10} y={17} className="fill-content" style={{ fontSize: 11 }}>
                  {truncate(node.title, 24)}
                </text>
                <text
                  x={10}
                  y={31}
                  className="fill-content-subtle"
                  style={{ fontSize: 9.5 }}
                >
                  {truncate(typeLabel(node.type), 18)} · v{node.version}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {selectedNode && (
        <div className="flex flex-wrap items-center gap-3 rounded-[--radius-card] border border-border bg-surface px-4 py-3 text-sm">
          <span className="text-content">{selectedNode.title}</span>
          <span className="text-xs text-content-subtle">
            {typeLabel(selectedNode.type)} · {stageLabel(selectedNode.stage as never)}
          </span>
          {selectedNode.isStale && (
            <span className="text-xs text-state-stale">out of date</span>
          )}
          <Link
            href={`/projects/${projectId}/artifacts/${selectedNode.id}`}
            className="ml-auto text-xs text-accent hover:text-accent-hover"
          >
            Open artifact →
          </Link>
        </div>
      )}
    </div>
  );
}

function Legend({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-2 rounded-sm", swatch)} aria-hidden="true" />
      {label}
    </span>
  );
}

function truncate(text: string, limit: number): string {
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}
