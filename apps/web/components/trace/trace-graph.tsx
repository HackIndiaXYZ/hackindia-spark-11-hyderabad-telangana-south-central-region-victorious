"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowRight, Crosshair, X } from "lucide-react";

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
 *
 * Alternating column bands do the work a grid would: they let the eye follow one
 * stage down the canvas without a line per row.
 */

const COLUMN_WIDTH = 218;
const ROW_HEIGHT = 66;
const NODE_WIDTH = 174;
const NODE_HEIGHT = 46;
const PADDING = 30;
const HEADER_HEIGHT = 38;

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
  const [hovered, setHovered] = useState<string | null>(null);

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
        y: PADDING + HEADER_HEIGHT + row * ROW_HEIGHT,
      };
    });

    const tallest = Math.max(1, ...[...rowCursor.values()]);

    return {
      nodes: positioned,
      byId: new Map(positioned.map((node) => [node.id, node])),
      columns: stages,
      width: PADDING * 2 + Math.max(1, stages.length) * COLUMN_WIDTH,
      height: PADDING * 2 + HEADER_HEIGHT + tallest * ROW_HEIGHT,
    };
  }, [graph]);

  /** Nodes connected to the focus, in either direction. */
  const focus = selected ?? hovered;
  const related = useMemo(() => {
    if (!focus) return null;
    const connected = new Set<string>([focus]);
    for (const edge of graph.edges) {
      if (edge.upstream_artifact_id === focus) connected.add(edge.downstream_artifact_id);
      if (edge.downstream_artifact_id === focus) connected.add(edge.upstream_artifact_id);
    }
    return connected;
  }, [focus, graph.edges]);

  const isDimmed = (id: string) => related !== null && !related.has(id);

  if (graph.nodes.length === 0) return null;

  const selectedNode = selected ? byId.get(selected) : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-content-subtle">
        <Legend swatch="bg-content-subtle" label="Current" />
        <Legend swatch="bg-state-stale" label="Out of date" />

        <span className="inline-flex items-center gap-1.5">
          <Crosshair className="size-3" aria-hidden="true" />
          {selected
            ? "Showing one artifact's dependencies"
            : "Hover to preview · select to focus"}
        </span>

        {selected && (
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-raised px-2 py-0.5 text-content-muted transition-colors hover:border-border-strong hover:text-content"
          >
            <X className="size-3" aria-hidden="true" />
            Clear
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-[--radius-card] border border-border bg-surface panel-sheen elevated">
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

          {/* Column bands. Every other stage gets a faint wash so a long column
              stays readable without ruling lines across the canvas. */}
          {columns.map((stage, index) =>
            index % 2 === 1 ? (
              <rect
                key={`band-${stage}`}
                x={PADDING + index * COLUMN_WIDTH - 14}
                y={PADDING - 6}
                width={COLUMN_WIDTH}
                height={height - PADDING * 2 + 12}
                rx={8}
                className="fill-canvas/40"
              />
            ) : null,
          )}

          {columns.map((stage, index) => (
            <text
              key={stage}
              x={PADDING + index * COLUMN_WIDTH}
              y={PADDING + 6}
              className="fill-content-subtle"
              style={{ fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}
            >
              {stageLabel(stage as never).toUpperCase()}
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
                  "transition-opacity duration-200",
                  edge.is_stale ? "stroke-state-stale" : "stroke-border-strong",
                  dimmed ? "opacity-[0.05]" : edge.is_stale ? "opacity-90" : "opacity-40",
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
            const isHovered = node.id === hovered;

            return (
              <g
                key={node.id}
                transform={`translate(${node.x} ${node.y})`}
                className={cn(
                  "cursor-pointer transition-opacity duration-200",
                  dimmed && "opacity-[0.18]",
                )}
                onClick={() => setSelected(active ? null : node.id)}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(node.id)}
                onBlur={() => setHovered(null)}
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
                {/* A soft plate under the active node, so the focus reads even
                    against a dense field of edges. */}
                {(active || isHovered) && (
                  <rect
                    x={-3}
                    y={-3}
                    width={NODE_WIDTH + 6}
                    height={NODE_HEIGHT + 6}
                    rx={10}
                    className={cn(
                      active ? "fill-accent/20" : "fill-content/[0.06]",
                    )}
                  />
                )}

                <rect
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={8}
                  className={cn(
                    "transition-[fill,stroke] duration-150",
                    node.isStale
                      ? "fill-state-stale/[0.12] stroke-state-stale/50"
                      : "fill-surface-raised stroke-border",
                    active && "stroke-accent",
                    !active && isHovered && "stroke-border-strong",
                  )}
                  strokeWidth={active ? 1.75 : 1}
                />

                {/* Stale artifacts carry a left rail as well as a tint, so the
                    state survives a greyscale print of this graph. */}
                {node.isStale && (
                  <rect
                    x={0}
                    y={0}
                    width={3}
                    height={NODE_HEIGHT}
                    rx={1.5}
                    className="fill-state-stale"
                  />
                )}

                <text x={12} y={19} className="fill-content" style={{ fontSize: 11.5 }}>
                  {truncate(node.title, 23)}
                </text>
                <text
                  x={12}
                  y={34}
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
        <div className="flex animate-[rise_0.3s_var(--ease-out-quint)_both] flex-wrap items-center gap-3 rounded-[--radius-card] border border-accent/30 bg-accent/[0.06] px-4 py-3 text-sm">
          <span className="font-medium text-content">{selectedNode.title}</span>
          <span className="text-xs text-content-subtle">
            {typeLabel(selectedNode.type)} · {stageLabel(selectedNode.stage as never)}
          </span>
          {selectedNode.isStale && (
            <span className="rounded border border-state-stale/30 bg-state-stale/10 px-1.5 py-0.5 text-[11px] text-state-stale">
              out of date
            </span>
          )}
          <Link
            href={`/projects/${projectId}/artifacts/${selectedNode.id}`}
            className="group ml-auto inline-flex items-center gap-1 text-xs text-accent transition-colors hover:text-accent-hover"
          >
            Open artifact
            <ArrowRight
              className="size-3 transition-transform duration-200 group-hover:translate-x-0.5"
              aria-hidden="true"
            />
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
