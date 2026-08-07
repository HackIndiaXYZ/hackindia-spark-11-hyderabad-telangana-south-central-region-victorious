import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel } from "@/lib/api";

/**
 * Project overview: the Engineering Timeline and recent activity.
 *
 * `10_UI_UX_Plan.md` requires each stage to show its status, responsible agent,
 * progress, and artifacts, and requires completed stages to stay visible so
 * engineering history is preserved.
 */

export const dynamic = "force-dynamic";

export default async function OverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [project, events] = await Promise.all([
    api.getProject(id),
    api.listEvents(id, 40),
  ]);

  const recent = [...events].reverse();

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <section className="space-y-3">
        <h2 className="text-sm font-medium tracking-tight">Engineering timeline</h2>

        <ol className="space-y-2">
          {project.stages.map((stage) => (
            <li
              key={stage.stage}
              className="flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm text-content">{stageLabel(stage.stage)}</p>
                <p className="text-xs text-content-subtle">
                  {stage.owner_title ?? "Unassigned"}
                  {stage.artifact_count > 0 && ` · ${stage.artifact_count} artifacts`}
                </p>
              </div>
              <StatusBadge
                state={badgeState(stage.status)}
                pulse={stage.status === "in_progress"}
              >
                {stage.status.replace(/_/g, " ")}
              </StatusBadge>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium tracking-tight">Recent activity</h2>

        <Card>
          <CardContent className="pt-5">
            {recent.length === 0 ? (
              <p className="text-sm text-content-muted">
                Nothing has happened yet. Use <strong>Advance engineering</strong> to
                start the organization.
              </p>
            ) : (
              <ul className="space-y-3">
                {recent.map((event) => (
                  <li key={event.id} className="flex gap-3">
                    <span
                      className="mt-1.5 size-1.5 shrink-0 rounded-full bg-border-strong"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-xs text-content">{event.summary}</p>
                      <p className="font-mono text-[11px] text-content-subtle">
                        {new Date(event.created_at).toLocaleTimeString()}
                        {event.role_title && ` · ${event.role_title}`}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
