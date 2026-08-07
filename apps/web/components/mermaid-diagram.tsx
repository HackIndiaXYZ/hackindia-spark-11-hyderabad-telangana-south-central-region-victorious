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
          // Matched to the workspace tokens in `globals.css`. Mermaid needs
          // literal hex, so these are the resolved values of
          // --color-surface-raised, --color-content, --color-border-strong and
          // --color-content-muted. Without this a diagram renders in Mermaid's
          // default light palette and blows a hole in a dark artifact page.
          themeVariables: {
            background: "transparent",
            primaryColor: "#242836",
            primaryTextColor: "#f3f4f8",
            primaryBorderColor: "#4b5165",
            secondaryColor: "#1c1f2b",
            tertiaryColor: "#171a24",
            lineColor: "#6d7386",
            textColor: "#b6bac7",
            fontSize: "13px",
            fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
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
      <pre className="my-4 overflow-x-auto rounded-lg border border-border bg-canvas-deep p-4 font-mono text-xs leading-relaxed text-content-muted">
        <code>{chart}</code>
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Component diagram"
      className="my-5 overflow-x-auto rounded-lg border border-border bg-surface-raised panel-sheen p-5 elevated [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
    />
  );
}
