import { Activity, CircleAlert, CircleCheck, CircleSlash } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiUnreachableError, fetchHealth, type HealthReport } from "@/lib/api-client";

/**
 * Live backend readiness, rendered from the API's own readiness probe.
 *
 * This is a real diagnostic rather than a placeholder: it exercises the whole
 * stack — server component to API client to FastAPI to the health registry — so
 * a broken link in that chain is visible immediately instead of at integration
 * time. As later milestones register their own health checks (the memory
 * repository, the LLM providers), each appears here with no change to this file.
 *
 * Component rows are laid out as a table rather than free-flowing text, because
 * the useful reading is a vertical scan of the status column.
 */

const STATE_BY_STATUS = {
  healthy: "active",
  degraded: "waiting",
  unhealthy: "blocked",
} as const;

const ICON_BY_STATUS = {
  healthy: CircleCheck,
  degraded: CircleAlert,
  unhealthy: CircleSlash,
} as const;

const TONE_BY_STATUS = {
  healthy: "text-state-active",
  degraded: "text-state-waiting",
  unhealthy: "text-state-blocked",
} as const;

async function loadHealth(): Promise<HealthReport | { unreachable: true }> {
  try {
    return await fetchHealth();
  } catch (error) {
    if (error instanceof ApiUnreachableError) return { unreachable: true };
    throw error;
  }
}

export async function SystemStatus() {
  const health = await loadHealth();

  if ("unreachable" in health) {
    return (
      <Card state="blocked">
        <CardHeader className="flex-row items-center justify-between gap-4">
          <CardTitle className="flex items-center gap-2">
            <Activity className="size-4 text-content-subtle" aria-hidden="true" />
            Engineering platform
          </CardTitle>
          <StatusBadge state="blocked">API unreachable</StatusBadge>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-content-muted">
            The workspace could not reach the Victorious API. Start it with{" "}
            <code className="rounded bg-canvas-deep px-1.5 py-0.5 font-mono text-xs text-content">
              uvicorn app.main:app --reload
            </code>{" "}
            from <span className="font-mono text-xs text-content">apps/api</span>.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-4">
        <CardTitle className="flex items-center gap-2">
          <Activity className="size-4 text-content-subtle" aria-hidden="true" />
          Engineering platform
        </CardTitle>
        <StatusBadge
          state={STATE_BY_STATUS[health.status]}
          pulse={health.status === "healthy"}
        >
          {health.status}
        </StatusBadge>
      </CardHeader>

      <CardContent className="space-y-4">
        <dl className="flex gap-6 text-xs">
          <div>
            <dt className="text-content-subtle">Version</dt>
            <dd className="mt-0.5 font-mono text-content">{health.version}</dd>
          </div>
          <div>
            <dt className="text-content-subtle">Environment</dt>
            <dd className="mt-0.5 font-mono text-content">{health.environment}</dd>
          </div>
          <div>
            <dt className="text-content-subtle">Components</dt>
            <dd className="mt-0.5 font-mono text-content">{health.components.length}</dd>
          </div>
        </dl>

        <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-canvas/40">
          {health.components.map((component) => {
            const ComponentIcon = ICON_BY_STATUS[component.status];
            return (
              <li
                key={component.name}
                className="flex items-center gap-3 px-3 py-2.5 transition-colors hover:bg-surface-raised/50"
              >
                <ComponentIcon
                  className={`size-3.5 shrink-0 ${TONE_BY_STATUS[component.status]}`}
                  aria-hidden="true"
                />
                <span className="shrink-0 font-mono text-xs text-content">
                  {component.name}
                </span>
                <span className="flex-1 truncate text-xs text-content-muted">
                  {component.message}
                </span>
                {component.latency_ms !== null && (
                  <span className="shrink-0 font-mono text-xs text-content-subtle">
                    {component.latency_ms.toFixed(1)}ms
                  </span>
                )}
              </li>
            );
          })}
        </ul>

        <p className="sr-only">
          Overall platform status is {health.status} with {health.components.length}{" "}
          components reporting.
        </p>
      </CardContent>
    </Card>
  );
}
