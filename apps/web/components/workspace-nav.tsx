"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

/**
 * Persistent workspace navigation.
 *
 * `10_UI_UX_Plan.md`: "Users should never leave this workspace during normal
 * development", and every artifact must be reachable "within two or three
 * interactions". Every section of the project is one click from every other.
 */

const SECTIONS = [
  { segment: "", label: "Overview" },
  { segment: "organization", label: "Organization" },
  { segment: "requirements", label: "Requirements" },
  { segment: "architecture", label: "Architecture" },
  { segment: "development", label: "Development" },
  { segment: "testing", label: "Testing" },
  { segment: "documentation", label: "Documentation" },
  { segment: "knowledge", label: "Knowledge Base" },
  { segment: "traceability", label: "Traceability" },
  { segment: "approvals", label: "Approvals" },
] as const;

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
    <nav aria-label="Project sections" className="border-b border-border">
      <ul className="-mb-px flex gap-1 overflow-x-auto">
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
                  "inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm whitespace-nowrap transition-colors",
                  active
                    ? "border-accent text-content"
                    : "border-transparent text-content-muted hover:text-content",
                )}
              >
                {section.label}
                {section.segment === "approvals" && pendingApprovals > 0 && (
                  <span className="rounded-full bg-state-approval/15 px-1.5 py-0.5 font-mono text-[10px] text-state-approval">
                    {pendingApprovals}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
