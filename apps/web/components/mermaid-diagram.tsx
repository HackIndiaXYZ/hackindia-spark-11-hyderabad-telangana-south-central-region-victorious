"use client";

import { useEffect, useId, useRef, useState } from "react";

/**
 * Renders a Mermaid diagram.
 *
 * Mermaid is loaded with a dynamic import inside the effect rather than at module
 * scope: it is roughly half a megabyte, and only the Architecture view contains
 * diagrams. Importing it statically would put that weight on every page in the
 * workspace.
 *
 * A malformed diagram falls back to the source text. Agent-generated Mermaid can
 * be syntactically invalid, and a broken diagram must not take the artifact page
 * down with it.
 */
export function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const reactId = useId();
  const domId = `mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`;

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const mermaid = (await import("mermaid")).default;

        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          themeVariables: {
            background: "transparent",
            primaryColor: "#1e2230",
            primaryTextColor: "#e8eaf0",
            primaryBorderColor: "#3a4054",
            lineColor: "#6b7280",
            fontSize: "13px",
          },
        });

        const { svg } = await mermaid.render(domId, chart);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
        }
      } catch {
        if (!cancelled) setFailed(true);
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [chart, domId]);

  if (failed) {
    return (
      <pre className="overflow-x-auto rounded-md border border-border bg-surface-raised p-4 font-mono text-xs text-content-muted">
        <code>{chart}</code>
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Component diagram"
      className="my-4 overflow-x-auto rounded-md border border-border bg-surface-raised p-4 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
    />
  );
}
