import Link from "next/link";
import { ArrowRight, ChevronDown, Lock } from "lucide-react";

import { Card, CardActivityBar, CardContent, CardHeader } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { badgeState, stageLabel, type AgentCard as AgentCardData } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * One specialist in the AI Engineering Organization.
 *
 * `10_UI_UX_Plan.md` requires each agent to expose its status, assigned
 * responsibilities, current task, confidence, dependencies, outputs, and recent
 * decisions. All of that is here, with the reasoning behind a disclosure so the
 * grid stays scannable while nothing is hidden.
 *
 * A running agent gets a tinted card, a pulsing badge, and a single pass of
 * light across its top edge. That is the whole "live" vocabulary — the card
 * never resizes, because a grid whose cards change size while you read it feels
 * unstable rather than alive.
 *
 * Confidence is drawn as a bar as well as a figure: it is the one metric here a
 * user is meant to compare across specialists at a glance.
 */
export function AgentCard({
  agent,
  projectId,
}: {
  agent: AgentCardData;
  projectId: string;
}) {
  const running = agent.status === "active" || agent.status === "reviewing";
  const idle = agent.status === "idle";

  return (
    <Card
      state={running ? "active" : "none"}
      className={cn("group flex flex-col", idle && "opacity-[0.72] hover:opacity-100")}
    >
      {running && <CardActivityBar />}

      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium tracking-tight text-content">
            {agent.title}
          </h3>
          <p className="mt-0.5 text-xs text-content-subtle">{stageLabel(agent.stage)}</p>
        </div>
        <StatusBadge state={badgeState(agent.status)} pulse={running}>
          {agent.status.replace(/_/g, " ")}
        </StatusBadge>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3">
        {agent.task ? (
          <p className="text-sm leading-relaxed text-content-muted">{agent.task}</p>
        ) : (
          <p className="text-sm text-content-subtle">
            Waiting for upstream work to reach this stage.
          </p>
        )}

        {agent.blocked_on.length > 0 && (
          <p className="inline-flex items-center gap-1.5 self-start rounded-md border border-state-waiting/25 bg-state-waiting/[0.08] px-2 py-1 text-xs text-state-waiting">
            <Lock className="size-3" aria-hidden="true" />
            Blocked on {agent.blocked_on.length} dependency
            {agent.blocked_on.length === 1 ? "" : "s"}
          </p>
        )}

        {agent.confidence !== null && (
          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between text-xs">
              <span className="text-content-subtle">Confidence</span>
              <span className="font-mono text-content">
                {Math.round(agent.confidence * 100)}%
              </span>
            </div>
            <div
              className="h-1 overflow-hidden rounded-full bg-surface-overlay"
              role="img"
              aria-label={`Confidence ${Math.round(agent.confidence * 100)} percent`}
            >
              <div
                className={cn(
                  "h-full rounded-full transition-[width] duration-700 ease-out",
                  agent.confidence >= 0.75
                    ? "bg-state-complete"
                    : agent.confidence >= 0.5
                      ? "bg-state-waiting"
                      : "bg-state-blocked",
                )}
                style={{ width: `${Math.round(agent.confidence * 100)}%` }}
              />
            </div>
          </div>
        )}

        {agent.reasoning_summary && (
          <details className="group/reason rounded-lg border border-border bg-canvas/40">
            <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-xs text-content-muted transition-colors hover:text-content">
              <ChevronDown
                className="size-3 transition-transform duration-200 group-open/reason:rotate-180"
                aria-hidden="true"
              />
              <span className="group-open/reason:hidden">Show reasoning</span>
              <span className="hidden group-open/reason:inline">Hide reasoning</span>
            </summary>
            <p className="border-t border-border px-3 py-2.5 text-xs leading-relaxed text-content-muted">
              {agent.reasoning_summary}
            </p>
          </details>
        )}

        {(agent.input_artifact_ids.length > 0 ||
          agent.output_artifact_ids.length > 0 ||
          agent.total_tokens > 0) && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-canvas/40 px-3 py-2.5 text-xs sm:grid-cols-4">
            <Metric label="Inputs" value={agent.input_artifact_ids.length} />
            <Metric label="Outputs" value={agent.output_artifact_ids.length} />
            {agent.total_tokens > 0 && (
              <Metric label="Tokens" value={agent.total_tokens.toLocaleString()} />
            )}
            {agent.duration_seconds !== null && (
              <Metric label="Took" value={`${agent.duration_seconds.toFixed(1)}s`} />
            )}
          </dl>
        )}

        <div className="mt-auto flex items-center justify-between gap-3 pt-1">
          {agent.provider ? (
            <p className="truncate font-mono text-[11px] text-content-subtle">
              {agent.provider} · {agent.model}
            </p>
          ) : (
            <span />
          )}

          {agent.output_artifact_ids.length > 0 && (
            <Link
              href={`/projects/${projectId}/knowledge`}
              className="group/link inline-flex shrink-0 items-center gap-1 text-xs text-accent transition-colors hover:text-accent-hover"
            >
              {agent.output_artifact_ids.length} artifact
              {agent.output_artifact_ids.length === 1 ? "" : "s"}
              <ArrowRight
                className="size-3 transition-transform duration-200 group-hover/link:translate-x-0.5"
                aria-hidden="true"
              />
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-content-subtle">{label}</dt>
      <dd className="truncate font-mono text-content">{value}</dd>
    </div>
  );
}
