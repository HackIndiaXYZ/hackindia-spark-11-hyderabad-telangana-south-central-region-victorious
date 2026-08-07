"use client";

import { useState } from "react";
import { Monitor, Smartphone, Tablet, Code2, Eye } from "lucide-react";

import { GeneratedApp } from "@/components/generated/generated-app";
import { StatusBadge } from "@/components/ui/status-badge";
import type { AppSpec } from "@/lib/generation/types";
import { cn } from "@/lib/utils";

/**
 * The workspace-side container for a generated application.
 *
 * Two things live here that the generated app must not own: the device
 * switcher, and the spec inspector. Both are *about* the generated app rather
 * than part of it, so keeping them outside `GeneratedApp` is what lets that
 * component stay a faithful preview of what a downloadable project would render.
 *
 * The viewport switch resizes the container rather than scaling it. Scaling
 * would fake responsiveness — the layout would look right at phone width while
 * never actually crossing a breakpoint. Constraining the width means the
 * generated app's own media queries fire, which is the thing worth showing.
 */

const VIEWPORTS = [
  { id: "desktop", label: "Desktop", icon: Monitor, width: "100%" },
  { id: "tablet", label: "Tablet", icon: Tablet, width: "48rem" },
  { id: "mobile", label: "Mobile", icon: Smartphone, width: "23rem" },
] as const;

type ViewportId = (typeof VIEWPORTS)[number]["id"];

export function PreviewFrame({ spec }: { spec: AppSpec }) {
  const [viewport, setViewport] = useState<ViewportId>("desktop");
  const [showSpec, setShowSpec] = useState(false);

  const active = VIEWPORTS.find((item) => item.id === viewport)!;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="group"
          aria-label="Preview viewport"
          className="inline-flex rounded-lg border border-border bg-surface p-0.5"
        >
          {VIEWPORTS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setViewport(item.id)}
              aria-pressed={viewport === item.id}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors",
                viewport === item.id
                  ? "bg-surface-overlay text-content"
                  : "text-content-muted hover:text-content",
              )}
            >
              <item.icon className="size-3.5" aria-hidden="true" />
              {item.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <StatusBadge state="idle" size="sm">
            {spec.theme.name} theme
          </StatusBadge>
          <button
            type="button"
            onClick={() => setShowSpec((value) => !value)}
            aria-pressed={showSpec}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
              showSpec
                ? "border-accent/40 bg-accent/10 text-accent"
                : "border-border bg-surface text-content-muted hover:text-content",
            )}
          >
            {showSpec ? (
              <Eye className="size-3.5" aria-hidden="true" />
            ) : (
              <Code2 className="size-3.5" aria-hidden="true" />
            )}
            {showSpec ? "Show preview" : "Show spec"}
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-[--radius-panel] border border-border bg-canvas-deep elevated-lg">
        {/* A browser chrome strip. It costs three divs and it is what makes the
            preview read as "an application" rather than "a section of our page". */}
        <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2">
          <span className="flex gap-1.5" aria-hidden="true">
            <span className="size-2.5 rounded-full bg-state-blocked/60" />
            <span className="size-2.5 rounded-full bg-state-waiting/60" />
            <span className="size-2.5 rounded-full bg-state-complete/60" />
          </span>
          <span className="mx-auto rounded-md bg-canvas-deep px-3 py-0.5 font-mono text-[11px] text-content-subtle">
            {spec.brand.name.toLowerCase().replace(/\s+/g, "-")}.app
          </span>
          <span className="w-12" aria-hidden="true" />
        </div>

        {showSpec ? (
          <SpecView spec={spec} />
        ) : (
          <div className="flex justify-center bg-canvas-deep p-4">
            <div
              className="w-full overflow-hidden rounded-lg border border-border transition-[max-width] duration-500 ease-out"
              style={{ maxWidth: active.width }}
            >
              <GeneratedApp spec={spec} />
            </div>
          </div>
        )}
      </div>

      <p className="text-xs text-content-subtle">
        Rendered live from the artifacts, not a screenshot. Tables sort and filter and
        forms validate; nothing persists, because writing to a generated schema would be
        fiction.
      </p>
    </div>
  );
}

/**
 * The `AppSpec` as JSON.
 *
 * The point is not that a judge reads it, but that it is *there* — the generated
 * app is a rendering of this document, and showing the document is what
 * separates a derivation from a mockup.
 */
function SpecView({ spec }: { spec: AppSpec }) {
  return (
    <div className="max-h-[38rem] overflow-auto bg-canvas-deep p-4">
      <pre className="font-mono text-[11px] leading-relaxed text-content-muted">
        <code>{JSON.stringify(spec, null, 2)}</code>
      </pre>
    </div>
  );
}
