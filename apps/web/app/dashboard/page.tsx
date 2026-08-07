import Link from "next/link";
import { AlertCircle, FileText, FolderOpen } from "lucide-react";

import { CreateProjectForm } from "@/components/create-project-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel, type ApprovalView, type ProjectSummary } from "@/lib/api";
import { ApiUnreachableError } from "@/lib/api-client";

/**
 * The engineering dashboard — the landing page after entering the workspace.
 *
 * `10_UI_UX_Plan.md` asks it to "communicate the health and status of every
 * project at a glance": active projects, engineering progress, pending
 * approvals, and the current lifecycle stage.
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
      <main id="main" tabIndex={-1} className="mx-auto max-w-5xl px-6 py-12">
        <Card>
          <CardHeader>
            <CardTitle>API unreachable</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-content-muted">
              Start the API with{" "}
              <code className="rounded bg-surface-raised px-1.5 py-0.5 font-mono text-xs">
                uvicorn app.main:app --reload
              </code>{" "}
              from <span className="font-mono text-xs">apps/api</span>.
            </p>
          </CardContent>
        </Card>
      </main>
    );
  }

  const { projects, approvals } = data;

  return (
    <main id="main" tabIndex={-1} className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-12">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Engineering dashboard</h1>
        <p className="text-sm text-content-muted">
          Every project the organization is working on, and everything waiting on you.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Projects" value={projects.length} icon={FolderOpen} />
        <StatTile
          label="Artifacts produced"
          value={projects.reduce((total, project) => total + project.artifact_count, 0)}
          icon={FileText}
        />
        <StatTile
          label="Awaiting your approval"
          value={approvals.length}
          icon={AlertCircle}
          emphasis={approvals.length > 0}
        />
      </section>

      {approvals.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium tracking-tight">Pending approvals</h2>
          <ul className="space-y-2">
            {approvals.map((approval) => (
              <li key={approval.id}>
                <Link
                  href={`/projects/${approval.project_id}/approvals`}
                  className="flex items-center gap-4 rounded-[--radius-card] border border-state-approval/30 bg-state-approval/5 px-4 py-3 transition-colors hover:bg-state-approval/10"
                >
                  <StatusBadge state="approval">{approval.kind.replace(/_/g, " ")}</StatusBadge>
                  <span className="flex-1 truncate text-sm text-content">
                    {approval.title}
                  </span>
                  <span className="hidden truncate text-xs text-content-subtle sm:block">
                    {approval.project_name}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium tracking-tight">Projects</h2>

        {projects.length === 0 ? (
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-content-muted">
                No projects yet. Create one below and the organization starts work
                immediately.
              </p>
            </CardContent>
          </Card>
        ) : (
          <ul className="space-y-2">
            {projects.map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="block rounded-[--radius-card] border border-border bg-surface p-4 transition-colors hover:border-border-strong"
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

                  <div className="mt-3 flex items-center gap-4">
                    <Progress
                      completed={project.completed_stages}
                      total={project.total_stages}
                    />
                    <span className="shrink-0 font-mono text-xs tabular-nums text-content-subtle">
                      {project.completed_stages}/{project.total_stages} stages
                    </span>
                    <span className="shrink-0 font-mono text-xs tabular-nums text-content-subtle">
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

function StatTile({
  label,
  value,
  icon: Icon,
  emphasis = false,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  emphasis?: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-5">
        <Icon
          className={emphasis ? "size-4 text-state-approval" : "size-4 text-content-subtle"}
        />
        <div>
          <p className="font-mono text-xl tabular-nums text-content">{value}</p>
          <p className="text-xs text-content-subtle">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function Progress({ completed, total }: { completed: number; total: number }) {
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div
      className="h-1 flex-1 overflow-hidden rounded-full bg-surface-raised"
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Engineering progress"
    >
      <div className="h-full bg-state-complete" style={{ width: `${percent}%` }} />
    </div>
  );
}
