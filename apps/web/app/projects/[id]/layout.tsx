import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { AdvanceButton } from "@/components/advance-button";
import { WorkspaceNav } from "@/components/workspace-nav";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * Project workspace shell.
 *
 * The header and navigation persist across every section, so the user never
 * leaves the workspace during normal development (`10_UI_UX_Plan.md`).
 *
 * It sticks to the top and blurs what scrolls beneath it. In a workspace where
 * artifacts run long, the project's identity, its progress, and the one control
 * that moves it forward should never scroll out of reach.
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
      <header className="sticky top-0 z-30 border-b border-border bg-canvas/80 backdrop-blur-xl">
        <div className="mx-auto max-w-6xl px-6 pt-4">
          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-1 text-xs text-content-subtle transition-colors hover:text-content"
          >
            <ChevronLeft
              className="size-3 transition-transform duration-200 group-hover:-translate-x-0.5"
              aria-hidden="true"
            />
            All projects
          </Link>

          <div className="mt-2.5 flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="truncate text-xl font-semibold tracking-tight text-content">
                  {project.name}
                </h1>
                <StatusBadge state={badgeState(project.current_stage)}>
                  {stageLabel(project.current_stage)}
                </StatusBadge>
              </div>

              <p className="line-clamp-1 max-w-2xl text-sm text-content-muted">
                {project.description}
              </p>

              <div className="flex max-w-md items-center gap-3 pt-1">
                <Progress
                  completed={project.completed_stages}
                  total={project.total_stages}
                  className="flex-1"
                />
                <span className="shrink-0 font-mono text-[11px] text-content-subtle">
                  {project.completed_stages}/{project.total_stages} stages
                </span>
                <span aria-hidden="true" className="h-3 w-px bg-border" />
                <span className="shrink-0 font-mono text-[11px] text-content-subtle">
                  {project.artifact_count} artifacts
                </span>
              </div>
            </div>

            <AdvanceButton projectId={id} />
          </div>

          <div className="mt-4">
            <WorkspaceNav projectId={id} pendingApprovals={project.pending_approvals} />
          </div>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-6 py-8">
        {children}
      </main>
    </div>
  );
}
