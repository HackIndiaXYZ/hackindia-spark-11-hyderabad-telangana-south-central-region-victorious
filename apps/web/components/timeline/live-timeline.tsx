"use client";

import { useCallback, useEffect, useState } from "react";

import { StreamIndicator } from "@/components/stream-indicator";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel, type ProjectDetail } from "@/lib/api";
import { useEventStream } from "@/lib/use-event-stream";

/**
 * The Engineering Timeline, live.
 *
 * `10_UI_UX_Plan.md`: each stage shows its status, responsible agent, progress,
 * and artifacts, and "completed stages remain visible to preserve engineering
 * history". Every stage is listed, including ones not yet started, so a user can
 * see what happens next rather than only what has happened.
 */
export function LiveTimeline({
  projectId,
  initialProject,
}: {
  projectId: string;
  initialProject: ProjectDetail;
}) {
  const [project, setProject] = useState(initialProject);

  const refresh = useCallback(async () => {
    try {
      setProject(await api.getProject(projectId));
    } catch {
      // Keep the last known timeline rather than blanking it on one dropped read.
    }
  }, [projectId]);

  const { status, events } = useEventStream(projectId, refresh);

  useEffect(() => setProject(initialProject), [initialProject]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium tracking-tight">Engineering timeline</h2>
          <StreamIndicator status={status} />
        </div>

        <ol className="space-y-2">
          {project.stages.map((stage) => {
            const running = stage.status === "in_progress";
            return (
              <li
                key={stage.stage}
                className={
                  running
                    ? "flex items-center gap-4 rounded-[--radius-card] border border-state-active/40 bg-state-active/[0.03] px-4 py-3"
                    : "flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface px-4 py-3"
                }
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-content">{stageLabel(stage.stage)}</p>
                  <p className="text-xs text-content-subtle">
                    {stage.owner_title ?? "Unassigned"}
                    {stage.artifact_count > 0 &&
                      ` · ${stage.artifact_count} artifact${stage.artifact_count === 1 ? "" : "s"}`}
                  </p>
                </div>
                <StatusBadge state={badgeState(stage.status)} pulse={running}>
                  {stage.status.replace(/_/g, " ")}
                </StatusBadge>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium tracking-tight">Activity</h2>

        <Card>
          <CardContent className="pt-5">
            {events.length === 0 ? (
              <p className="text-sm text-content-muted">
                Nothing has happened yet. Use <strong>Advance engineering</strong> to
                start the organization.
              </p>
            ) : (
              <ul className="space-y-3">
                {events.slice(0, 25).map((event) => (
                  <li key={event.id} className="flex gap-3">
                    <span
                      className="mt-1.5 size-1.5 shrink-0 rounded-full bg-border-strong"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-xs text-content">{event.summary}</p>
                      <p className="font-mono text-[11px] text-content-subtle">
                        {new Date(event.created_at).toLocaleTimeString()}
                        {event.role && ` · ${event.role.replace(/_/g, " ")}`}
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
