import Link from "next/link";
import { AlertTriangle, ChevronRight, FileText } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { badgeState, typeLabel, type ArtifactSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Artifact index for a workspace section.
 *
 * A stale artifact is called out here rather than only on its own page: the
 * whole point of computing staleness is that a user sees it without having to go
 * looking. It gets a tinted row and a left rail as well as a badge, so it is
 * findable while scrolling a long list rather than only while reading one.
 *
 * `empty` is sometimes deliberately blank — the Knowledge Base groups artifacts
 * by stage and renders no group that has none — so an empty string suppresses
 * the empty state rather than showing a bare box.
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
    if (!empty) return null;
    return <EmptyState icon={FileText} title="Nothing here yet" description={empty} />;
  }

  return (
    <ul className="space-y-2">
      {artifacts.map((artifact, index) => (
        <li
          key={artifact.id}
          className="animate-[rise_0.35s_var(--ease-out-quint)_both]"
          style={{ animationDelay: `${Math.min(index * 30, 240)}ms` }}
        >
          <Link
            href={`/projects/${projectId}/artifacts/${artifact.id}`}
            className={cn(
              "group relative flex items-center gap-4 overflow-hidden rounded-[--radius-card] border px-4 py-3.5",
              "panel-sheen elevated transition-[border-color,box-shadow,transform] duration-200",
              "hover:-translate-y-px hover:elevated-lg",
              artifact.is_stale
                ? "border-state-stale/35 bg-state-stale/[0.045] hover:border-state-stale/55"
                : "border-border bg-surface hover:border-border-strong",
            )}
          >
            {artifact.is_stale && (
              <span
                aria-hidden="true"
                className="absolute inset-y-0 left-0 w-0.5 bg-state-stale"
              />
            )}

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
              <p className="truncate text-xs text-content-subtle">
                {typeLabel(artifact.type)} · {artifact.owner_title} · v
                {artifact.current_version}
              </p>
            </div>

            {artifact.is_stale && (
              <StatusBadge state="stale" size="sm">
                stale
              </StatusBadge>
            )}
            <StatusBadge state={badgeState(artifact.status)} size="sm">
              {artifact.status.replace(/_/g, " ")}
            </StatusBadge>

            <ChevronRight
              className="size-4 shrink-0 text-content-subtle transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-content-muted"
              aria-hidden="true"
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}
