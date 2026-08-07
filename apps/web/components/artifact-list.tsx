import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { badgeState, typeLabel, type ArtifactSummary } from "@/lib/api";

/**
 * Artifact index for a workspace section.
 *
 * A stale artifact is called out here rather than only on its own page: the
 * whole point of computing staleness is that a user sees it without having to go
 * looking.
 */
export function ArtifactList({
  projectId,
  artifacts,
  empty,
}: {
  projectId: string;
  artifacts: ArtifactSummary[];
  empty: string;
}) {
  if (artifacts.length === 0) {
    return (
      <Card>
        <CardContent className="pt-5">
          <p className="text-sm text-content-muted">{empty}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <ul className="space-y-2">
      {artifacts.map((artifact) => (
        <li key={artifact.id}>
          <Link
            href={`/projects/${projectId}/artifacts/${artifact.id}`}
            className="flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface px-4 py-3 transition-colors hover:border-border-strong"
          >
            <div className="min-w-0 flex-1 space-y-1">
              <p className="flex items-center gap-2 truncate text-sm text-content">
                {artifact.title}
                {artifact.is_stale && (
                  <AlertTriangle
                    className="size-3.5 shrink-0 text-state-stale"
                    aria-label="Out of date with its upstream"
                  />
                )}
              </p>
              <p className="text-xs text-content-subtle">
                {typeLabel(artifact.type)} · {artifact.owner_title} · v
                {artifact.current_version}
              </p>
            </div>

            {artifact.is_stale && <StatusBadge state="stale">stale</StatusBadge>}
            <StatusBadge state={badgeState(artifact.status)}>
              {artifact.status.replace(/_/g, " ")}
            </StatusBadge>
          </Link>
        </li>
      ))}
    </ul>
  );
}
