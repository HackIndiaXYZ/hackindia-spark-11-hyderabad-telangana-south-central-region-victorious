import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { badgeState, stageLabel, type AgentCard as AgentCardData } from "@/lib/api";

/**
 * One specialist in the AI Engineering Organization.
 *
 * `10_UI_UX_Plan.md` requires each agent to expose its status, assigned
 * responsibilities, current task, confidence, dependencies, outputs, and recent
 * decisions. All of that is here, with the reasoning behind a disclosure so the
 * grid stays scannable while nothing is hidden.
 */
export function AgentCard({
  agent,
  projectId,
}: {
  agent: AgentCardData;
  projectId: string;
}) {
  const running = agent.status === "active" || agent.status === "reviewing";

  return (
    <Card
      className={
        running ? "border-state-active/40 bg-state-active/[0.03]" : undefined
      }
    >
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="truncate">{agent.title}</CardTitle>
          <p className="mt-0.5 text-xs text-content-subtle">
            {stageLabel(agent.stage)}
          </p>
        </div>
        <StatusBadge state={badgeState(agent.status)} pulse={running}>
          {agent.status.replace(/_/g, " ")}
        </StatusBadge>
      </CardHeader>

      <CardContent className="space-y-3">
        {agent.task ? (
          <p className="text-sm text-content-muted">{agent.task}</p>
        ) : (
          <p className="text-sm text-content-subtle">
            Waiting for upstream work to reach this stage.
          </p>
        )}

        {agent.blocked_on.length > 0 && (
          <p className="text-xs text-state-waiting">
            Blocked on {agent.blocked_on.length} dependency
            {agent.blocked_on.length === 1 ? "" : "s"}
          </p>
        )}

        {agent.reasoning_summary && (
          <details className="group">
            <summary className="cursor-pointer list-none text-xs text-accent hover:text-accent-hover">
              <span className="group-open:hidden">Show reasoning</span>
              <span className="hidden group-open:inline">Hide reasoning</span>
            </summary>
            <p className="mt-2 border-l-2 border-border pl-3 text-xs leading-relaxed text-content-muted">
              {agent.reasoning_summary}
            </p>
          </details>
        )}

        {(agent.confidence !== null ||
          agent.output_artifact_ids.length > 0 ||
          agent.total_tokens > 0) && (
          <dl className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
            {agent.confidence !== null && (
              <Metric label="Confidence" value={`${Math.round(agent.confidence * 100)}%`} />
            )}
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

        {agent.provider && (
          <p className="font-mono text-[11px] text-content-subtle">
            {agent.provider} · {agent.model}
          </p>
        )}

        {agent.output_artifact_ids.length > 0 && (
          <Link
            href={`/projects/${projectId}/knowledge`}
            className="inline-block text-xs text-accent hover:text-accent-hover"
          >
            {agent.output_artifact_ids.length} artifact
            {agent.output_artifact_ids.length === 1 ? "" : "s"} produced →
          </Link>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-content-subtle">{label}</dt>
      <dd className="font-mono tabular-nums text-content">{value}</dd>
    </div>
  );
}
