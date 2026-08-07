import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel } from "@/lib/api";

/**
 * The AI Engineering Organization view.
 *
 * `10_UI_UX_Plan.md` calls this "one of the primary features of the product":
 * every agent's status, responsibilities, current task, confidence, dependencies,
 * outputs, and recent decisions — inspectable without interrupting the workflow.
 *
 * The Executive AI is deliberately absent. It coordinates and performs no
 * engineering work (ADR-0009), so it owns no card here.
 */

export const metadata = { title: "Organization" };
export const dynamic = "force-dynamic";

export default async function OrganizationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const agents = await api.getOrganization(id);

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-sm font-medium tracking-tight">AI Engineering Organization</h2>
        <p className="text-sm text-content-muted">
          Every specialist, and what it is doing right now. Coordinated by the Executive
          AI, which assigns work and performs none of it.
        </p>
      </header>

      <div className="grid gap-3 md:grid-cols-2">
        {agents.map((agent) => (
          <Card key={agent.stage}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div className="min-w-0">
                <CardTitle className="truncate">{agent.title}</CardTitle>
                <p className="mt-0.5 text-xs text-content-subtle">
                  {stageLabel(agent.stage)}
                </p>
              </div>
              <StatusBadge
                state={badgeState(agent.status)}
                pulse={agent.status === "active"}
              >
                {agent.status.replace(/_/g, " ")}
              </StatusBadge>
            </CardHeader>

            <CardContent className="space-y-3">
              {agent.task && <p className="text-sm text-content-muted">{agent.task}</p>}

              {agent.reasoning_summary && (
                <details className="group">
                  <summary className="cursor-pointer text-xs text-accent hover:text-accent-hover">
                    Reasoning
                  </summary>
                  <p className="mt-2 border-l-2 border-border pl-3 text-xs text-content-muted">
                    {agent.reasoning_summary}
                  </p>
                </details>
              )}

              <dl className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
                {agent.confidence !== null && (
                  <div>
                    <dt className="text-content-subtle">Confidence</dt>
                    <dd className="font-mono tabular-nums text-content">
                      {Math.round(agent.confidence * 100)}%
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-content-subtle">Inputs</dt>
                  <dd className="font-mono tabular-nums text-content">
                    {agent.input_artifact_ids.length}
                  </dd>
                </div>
                <div>
                  <dt className="text-content-subtle">Outputs</dt>
                  <dd className="font-mono tabular-nums text-content">
                    {agent.output_artifact_ids.length}
                  </dd>
                </div>
                {agent.total_tokens > 0 && (
                  <div>
                    <dt className="text-content-subtle">Tokens</dt>
                    <dd className="font-mono tabular-nums text-content">
                      {agent.total_tokens.toLocaleString()}
                    </dd>
                  </div>
                )}
                {agent.duration_seconds !== null && (
                  <div>
                    <dt className="text-content-subtle">Duration</dt>
                    <dd className="font-mono tabular-nums text-content">
                      {agent.duration_seconds.toFixed(1)}s
                    </dd>
                  </div>
                )}
              </dl>

              {agent.provider && (
                <p className="font-mono text-[11px] text-content-subtle">
                  {agent.provider} · {agent.model}
                </p>
              )}

              {agent.output_artifact_ids.length > 0 && (
                <Link
                  href={`/projects/${id}/knowledge`}
                  className="inline-block text-xs text-accent hover:text-accent-hover"
                >
                  View produced artifacts →
                </Link>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
