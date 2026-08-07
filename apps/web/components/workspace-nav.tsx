"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  ClipboardCheck,
  Code2,
  FileCheck2,
  FlaskConical,
  GitBranch,
  Layers,
  LayoutDashboard,
  Library,
  ScrollText,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Persistent workspace navigation.
 *
 * `10_UI_UX_Plan.md`: "Users should never leave this workspace during normal
 * development", and every artifact must be reachable "within two or three
 * interactions". Every section of the project is one click from every other.
 *
 * With eleven destinations, an icon per tab is what makes the row scannable
 * without reading it — the shape becomes the landmark on repeat visits. The icon
 * never carries meaning alone: the text label is always present.
 */

const SECTIONS: ReadonlyArray<{
  segment: string;
  label: string;
  icon: LucideIcon;
}> = [
  { segment: "", label: "Overview", icon: LayoutDashboard },
  { segment: "organization", label: "Organization", icon: Boxes },
  { segment: "requirements", label: "Requirements", icon: ScrollText },
  { segment: "architecture", label: "Architecture", icon: Layers },
  { segment: "development", label: "Development", icon: Code2 },
  { segment: "testing", label: "Testing", icon: FlaskConical },
  { segment: "documentation", label: "Documentation", icon: FileCheck2 },
  { segment: "knowledge", label: "Knowledge Base", icon: Library },
  { segment: "traceability", label: "Traceability", icon: GitBranch },
  { segment: "review", label: "Helix Review", icon: ShieldCheck },
  { segment: "approvals", label: "Approvals", icon: ClipboardCheck },
];

export function WorkspaceNav({
  projectId,
  pendingApprovals,
}: {
  projectId: string;
  pendingApprovals: number;
}) {
  const pathname = usePathname();
  const base = `/projects/${projectId}`;

  return (
    <nav aria-label="Project sections" className="relative">
      {/*
        The row scrolls on narrow viewports. A fade at the right edge is the only
        honest way to signal that without adding a control — a hard cut reads as
        the end of the list.
      */}
      <ul className="-mb-px flex gap-0.5 overflow-x-auto pb-px [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {SECTIONS.map((section) => {
          const href = section.segment ? `${base}/${section.segment}` : base;
          const active = section.segment
            ? pathname.startsWith(href)
            : pathname === base;

          return (
            <li key={section.segment || "overview"}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative inline-flex items-center gap-1.5 rounded-t-lg px-3 py-2.5 text-sm whitespace-nowrap",
                  "transition-colors duration-150",
                  active
                    ? "text-content"
                    : "text-content-muted hover:bg-surface/60 hover:text-content",
                )}
              >
                <section.icon
                  className={cn(
                    "size-3.5 transition-colors duration-150",
                    active
                      ? "text-accent"
                      : "text-content-subtle group-hover:text-content-muted",
                  )}
                  aria-hidden="true"
                />
                {section.label}

                {section.segment === "approvals" && pendingApprovals > 0 && (
                  <span className="ml-0.5 rounded-full bg-state-approval/15 px-1.5 py-0.5 font-mono text-[10px] text-state-approval">
                    {pendingApprovals}
                  </span>
                )}

                {/* The active rail. Rendered per-tab rather than as one sliding
                    element so it stays correct when the row is scrolled. */}
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute inset-x-1 -bottom-px h-0.5 rounded-full transition-all duration-200 ease-out",
                    active
                      ? "bg-accent opacity-100 shadow-[0_0_10px_0_var(--color-accent-glow)]"
                      : "bg-border-strong opacity-0 group-hover:opacity-100",
                  )}
                />
              </Link>
            </li>
          );
        })}
      </ul>

      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-canvas to-transparent"
      />
    </nav>
  );
}
