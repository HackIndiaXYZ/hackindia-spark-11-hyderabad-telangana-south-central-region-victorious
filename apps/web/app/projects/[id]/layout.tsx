import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { AdvanceButton } from "@/components/advance-button";
import { WorkspaceNav } from "@/components/workspace-nav";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * Project workspace shell.
 *
 * The header and navigation persist across every section, so the user never
 * leaves the workspace during normal development (`10_UI_UX_Plan.md`).
 */

export const dynamic = "force-dynamic";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let project;
  try {
    project = await api.getProject(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface/50">
        <div className="mx-auto max-w-6xl px-6 pt-5">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1 text-xs text-content-subtle transition-colors hover:text-content"
          >
            <ChevronLeft className="size-3" aria-hidden="true" />
            All projects
          </Link>

          <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <h1 className="truncate text-xl font-semibold tracking-tight">
                {project.name}
              </h1>
              <p className="line-clamp-1 max-w-2xl text-sm text-content-muted">
                {project.description}
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <StatusBadge state={badgeState(project.current_stage)}>
                  {stageLabel(project.current_stage)}
                </StatusBadge>
                <p className="mt-1 font-mono text-xs tabular-nums text-content-subtle">
                  {project.completed_stages}/{project.total_stages} stages ·{" "}
                  {project.artifact_count} artifacts
                </p>
              </div>
              <AdvanceButton projectId={id} />
            </div>
          </div>

          <div className="mt-4">
            <WorkspaceNav projectId={id} pendingApprovals={project.pending_approvals} />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
    </div>
  );
}
