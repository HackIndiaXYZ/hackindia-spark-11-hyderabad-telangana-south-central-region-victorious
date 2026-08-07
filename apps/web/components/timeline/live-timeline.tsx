"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, Minus } from "lucide-react";

import { StreamIndicator } from "@/components/stream-indicator";
import { SectionLabel } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel, type ProjectDetail, type StageSummary } from "@/lib/api";
import { useEventStream } from "@/lib/use-event-stream";
import { cn } from "@/lib/utils";

/**
 * The Engineering Timeline, live.
 *
 * `10_UI_UX_Plan.md`: each stage shows its status, responsible agent, progress,
 * and artifacts, and "completed stages remain visible to preserve engineering
 * history". Every stage is listed, including ones not yet started, so a user can
 * see what happens next rather than only what has happened.
 *
 * Drawn as a true rail — a connecting spine with a node per stage — because the
 * lifecycle is a sequence, and a flat list of cards loses that. The spine is
 * lit up to the current stage and dim beyond it, so how far the project has come
 * is readable without counting.
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
    <div className="grid gap-8 lg:grid-cols-[1.45fr_1fr]">
      <section className="space-y-4">
        <SectionLabel trailing={<StreamIndicator status={status} />}>
          Engineering timeline
        </SectionLabel>

        <ol className="relative">
          {project.stages.map((stage, index) => (
            <StageRow
              key={stage.stage}
              stage={stage}
              isLast={index === project.stages.length - 1}
              index={index}
            />
          ))}
        </ol>
      </section>

      <section className="space-y-4">
        <SectionLabel>Activity</SectionLabel>

        {events.length === 0 ? (
          <div className="rounded-[--radius-card] border border-dashed border-border bg-surface/40 px-5 py-8 text-center">
            <p className="text-sm text-content-muted">
              Nothing has happened yet. Use{" "}
              <strong className="font-medium text-content">Advance engineering</strong>{" "}
              to start the organization.
            </p>
          </div>
        ) : (
          <ul className="space-y-0.5 rounded-[--radius-card] border border-border bg-surface panel-sheen p-2 elevated">
            {events.slice(0, 25).map((event) => (
              <li
                key={event.id}
                className="flex animate-[fade-in_0.3s_ease-out_both] gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-surface-raised/60"
              >
                <span
                  className="mt-1.5 size-1.5 shrink-0 rounded-full bg-border-strong"
                  aria-hidden="true"
                />
                <div className="min-w-0 space-y-0.5">
                  <p className="text-xs leading-relaxed text-content">{event.summary}</p>
                  <p className="font-mono text-[11px] text-content-subtle">
                    {new Date(event.created_at).toLocaleTimeString()}
                    {event.role && ` · ${event.role.replace(/_/g, " ")}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** One stage on the rail: node, connector, and its card. */
function StageRow({
  stage,
  isLast,
  index,
}: {
  stage: StageSummary;
  isLast: boolean;
  index: number;
}) {
  const running = stage.status === "in_progress";
  const done = stage.status === "completed";

  return (
    <li
      className="relative flex animate-[rise_0.4s_var(--ease-out-quint)_both] gap-4 pb-2"
      style={{ animationDelay: `${Math.min(index * 40, 320)}ms` }}
    >
      {/* The spine. Lit through completed work, dim for what is still ahead. */}
      <div className="relative flex w-6 shrink-0 flex-col items-center">
        <span
          aria-hidden="true"
          className={cn(
            "z-10 grid size-6 place-items-center rounded-full border transition-colors duration-300",
            done && "border-state-complete/45 bg-state-complete/15 text-state-complete",
            running &&
              "border-state-active/50 bg-state-active/15 text-state-active shadow-[0_0_14px_-2px_var(--color-state-active)]",
            !done && !running && "border-border bg-surface-raised text-content-subtle",
          )}
        >
          {done ? (
            <Check className="size-3" />
          ) : running ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <Minus className="size-3" />
          )}
        </span>

        {!isLast && (
          <span
            aria-hidden="true"
            className={cn(
              "-mt-px w-px flex-1 transition-colors duration-300",
              done ? "bg-state-complete/35" : "bg-border",
            )}
          />
        )}
      </div>

      <div
        className={cn(
          "mb-2 flex flex-1 items-center gap-4 rounded-[--radius-card] border px-4 py-3",
          "panel-sheen transition-[border-color,background-color] duration-200",
          running
            ? "border-state-active/40 bg-state-active/[0.05]"
            : "border-border bg-surface hover:border-border-strong",
        )}
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm text-content">{stageLabel(stage.stage)}</p>
          <p className="mt-0.5 text-xs text-content-subtle">
            {stage.owner_title ?? "Unassigned"}
            {stage.artifact_count > 0 &&
              ` · ${stage.artifact_count} artifact${stage.artifact_count === 1 ? "" : "s"}`}
          </p>
        </div>

        <StatusBadge state={badgeState(stage.status)} pulse={running}>
          {stage.status.replace(/_/g, " ")}
        </StatusBadge>
      </div>
    </li>
  );
}
