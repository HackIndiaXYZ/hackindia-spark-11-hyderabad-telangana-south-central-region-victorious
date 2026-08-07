import Link from "next/link";
import {
  AlertCircle,
  ChevronRight,
  FileText,
  FolderOpen,
  PlugZap,
  Sparkles,
} from "lucide-react";

import { CreateProjectForm } from "@/components/create-project-form";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
import { Progress } from "@/components/ui/progress";
import { StatTile } from "@/components/ui/stat-tile";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  api,
  badgeState,
  stageLabel,
  type ApprovalView,
  type ProjectSummary,
} from "@/lib/api";
import { ApiUnreachableError } from "@/lib/api-client";

/**
 * The engineering dashboard — the landing page after entering the workspace.
 *
 * `10_UI_UX_Plan.md` asks it to "communicate the health and status of every
 * project at a glance": active projects, engineering progress, pending
 * approvals, and the current lifecycle stage.
 *
 * The order of the page is the order of a user's attention: what needs *you*
 * first, then what the organization is doing, then how to start something new.
 */

export const metadata = { title: "Dashboard" };
export const dynamic = "force-dynamic";

async function load(): Promise<
  { projects: ProjectSummary[]; approvals: ApprovalView[] } | { unreachable: true }
> {
  try {
    const [projects, approvals] = await Promise.all([
      api.listProjects(),
      api.listPendingApprovals(),
    ]);
    return { projects, approvals };
  } catch (error) {
    if (error instanceof ApiUnreachableError) return { unreachable: true };
    throw error;
  }
}

export default async function DashboardPage() {
  const data = await load();

  if ("unreachable" in data) {
    return (
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-6 py-16">
        <EmptyState
          icon={PlugZap}
          title="The workspace cannot reach the API"
          description={
            <>
              Start it with{" "}
              <code className="rounded bg-surface-raised px-1.5 py-0.5 font-mono text-xs text-content">
                uvicorn app.main:app --reload
              </code>{" "}
              from <span className="font-mono text-xs text-content">apps/api</span>, then
              reload this page.
            </>
          }
        />
      </main>
    );
  }

  const { projects, approvals } = data;
  const artifacts = projects.reduce((total, project) => total + project.artifact_count, 0);

  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-12"
    >
      <PageHeader
        eyebrow="Workspace"
        title="Engineering dashboard"
        description="Every project the organization is working on, and everything waiting on you."
        className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
      />

      <section
        aria-label="Workspace summary"
        className="grid animate-[rise_0.45s_var(--ease-out-quint)_both] gap-3 sm:grid-cols-3"
        style={{ animationDelay: "60ms" }}
      >
        <StatTile
          label="Projects"
          value={projects.length}
          icon={FolderOpen}
          hint={projects.length === 0 ? "None yet" : "In the workspace"}
        />
        <StatTile
          label="Artifacts produced"
          value={artifacts}
          icon={FileText}
          hint="Across every project"
        />
        <StatTile
          label="Awaiting your approval"
          value={approvals.length}
          icon={AlertCircle}
          emphasis={approvals.length > 0}
          hint={approvals.length > 0 ? "Work downstream has stopped" : "Nothing blocked"}
        />
      </section>

      {approvals.length > 0 && (
        <section
          className="animate-[rise_0.5s_var(--ease-out-quint)_both] space-y-3"
          style={{ animationDelay: "110ms" }}
        >
          <SectionLabel>Pending approvals</SectionLabel>

          <ul className="space-y-2">
            {approvals.map((approval) => (
              <li key={approval.id}>
                <Link
                  href={`/projects/${approval.project_id}/approvals`}
                  className="group flex items-center gap-4 rounded-[--radius-card] border border-state-approval/30 bg-state-approval/[0.06] px-4 py-3.5 transition-[background-color,border-color,transform] duration-200 hover:-translate-y-px hover:border-state-approval/50 hover:bg-state-approval/[0.1]"
                >
                  <StatusBadge state="approval" pulse>
                    {approval.kind.replace(/_/g, " ")}
                  </StatusBadge>
                  <span className="flex-1 truncate text-sm text-content">
                    {approval.title}
                  </span>
                  <span className="hidden truncate text-xs text-content-subtle sm:block">
                    {approval.project_name}
                  </span>
                  <ChevronRight
                    className="size-4 shrink-0 text-content-subtle transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-content-muted"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section
        className="animate-[rise_0.55s_var(--ease-out-quint)_both] space-y-3"
        style={{ animationDelay: "160ms" }}
      >
        <SectionLabel
          trailing={
            projects.length > 0 ? (
              <span className="font-mono text-[11px] text-content-subtle">
                {projects.length}
              </span>
            ) : undefined
          }
        >
          Projects
        </SectionLabel>

        {projects.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No projects yet"
            description="Give the organization a name and a description below. It works out the requirements from there and starts immediately."
          />
        ) : (
          <ul className="space-y-2">
            {projects.map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="group block rounded-[--radius-card] border border-border bg-surface panel-sheen p-4 elevated transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-px hover:border-border-strong hover:elevated-lg"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 space-y-1">
                      <p className="truncate text-sm font-medium text-content">
                        {project.name}
                      </p>
                      <p className="line-clamp-1 text-xs text-content-muted">
                        {project.description}
                      </p>
                    </div>
                    <StatusBadge state={badgeState(project.current_stage)}>
                      {stageLabel(project.current_stage)}
                    </StatusBadge>
                  </div>

                  <div className="mt-4 flex items-center gap-4">
                    <Progress
                      completed={project.completed_stages}
                      total={project.total_stages}
                      className="flex-1"
                    />
                    <span className="shrink-0 font-mono text-[11px] text-content-subtle">
                      {project.completed_stages}/{project.total_stages} stages
                    </span>
                    <span
                      aria-hidden="true"
                      className="hidden h-3 w-px bg-border sm:block"
                    />
                    <span className="hidden shrink-0 font-mono text-[11px] text-content-subtle sm:block">
                      {project.artifact_count} artifacts
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <CreateProjectForm />
    </main>
  );
}
