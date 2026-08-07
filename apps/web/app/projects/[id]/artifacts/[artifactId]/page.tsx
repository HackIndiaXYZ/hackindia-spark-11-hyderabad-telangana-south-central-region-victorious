import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertTriangle, ChevronLeft } from "lucide-react";

import { ArtifactBody } from "@/components/artifact-body";
import {
  ArtifactReviewPanel,
  ReviewUnavailable,
} from "@/components/review/review-card";
import { ReviseArtifact } from "@/components/revise-artifact";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel, typeLabel } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * One engineering artifact, with its content, provenance, and version history.
 *
 * The version list is what makes `12_Risk_Analysis.md`'s "version-controlled
 * engineering artifacts" mitigation visible: an earlier version is readable
 * exactly as the agent that consumed it saw it.
 */

export const dynamic = "force-dynamic";

export default async function ArtifactPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string; artifactId: string }>;
  searchParams: Promise<{ version?: string }>;
}) {
  const { id, artifactId } = await params;
  const { version } = await searchParams;

  let artifact;
  try {
    artifact = await api.getArtifact(
      id,
      artifactId,
      version ? Number(version) : undefined,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  return (
    <div className="space-y-6">
      <Link
        href={`/projects/${id}/knowledge`}
        className="inline-flex items-center gap-1 text-xs text-content-subtle transition-colors hover:text-content"
      >
        <ChevronLeft className="size-3" aria-hidden="true" />
        Knowledge Base
      </Link>

      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{artifact.title}</h1>
          <div className="flex items-center gap-2">
            {artifact.is_stale && <StatusBadge state="stale">stale</StatusBadge>}
            <StatusBadge state={badgeState(artifact.status)}>
              {artifact.status.replace(/_/g, " ")}
            </StatusBadge>
          </div>
        </div>

        <p className="text-xs text-content-subtle">
          {typeLabel(artifact.type)} · {stageLabel(artifact.stage)} ·{" "}
          {artifact.owner_title} · version {artifact.version}
          {!artifact.is_latest && " (historical)"}
          {artifact.confidence !== null &&
            ` · ${Math.round(artifact.confidence * 100)}% confidence`}
        </p>
      </header>

      {artifact.is_stale && (
        <div className="flex gap-3 rounded-[--radius-card] border border-state-stale/30 bg-state-stale/5 px-4 py-3">
          <AlertTriangle
            className="mt-0.5 size-4 shrink-0 text-state-stale"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <p className="text-sm text-content">Out of date with its upstream</p>
            <p className="text-xs text-content-muted">
              This was derived from an earlier version of something that has since
              changed.{" "}
              <Link
                href={`/projects/${id}/traceability`}
                className="text-accent hover:text-accent-hover"
              >
                See what it depends on →
              </Link>
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_260px]">
        <div className="space-y-4">
          <Card>
            <CardContent className="pt-5">
              <ArtifactBody markdown={artifact.body_markdown} />
            </CardContent>
          </Card>

          {artifact.is_latest && (
            <ReviseArtifact
              projectId={id}
              artifactId={artifactId}
              currentMarkdown={artifact.body_markdown}
            />
          )}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2">
              <CardTitle>Engineering review</CardTitle>
              <Link
                href={`/projects/${id}/review`}
                className="text-xs text-content-subtle transition-colors hover:text-accent"
              >
                All reviews →
              </Link>
            </CardHeader>
            <CardContent>
              {artifact.review ? (
                <ArtifactReviewPanel review={artifact.review} />
              ) : (
                <ReviewUnavailable />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Version history</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-2">
                {artifact.versions.map((entry) => {
                  const active = entry.version === artifact.version;
                  return (
                    <li key={entry.version}>
                      <Link
                        href={`/projects/${id}/artifacts/${artifactId}?version=${entry.version}`}
                        aria-current={active ? "page" : undefined}
                        className={
                          active
                            ? "block rounded-md border border-accent-muted bg-accent-muted/20 px-3 py-2"
                            : "block rounded-md border border-transparent px-3 py-2 transition-colors hover:bg-surface-raised"
                        }
                      >
                        <p className="font-mono text-xs text-content">
                          v{entry.version}
                          {entry.version === artifact.current_version && " · latest"}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-content-subtle">
                          {entry.summary || "No summary"}
                        </p>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </CardContent>
          </Card>

          {artifact.produced_by_run_id && (
            <Card>
              <CardHeader>
                <CardTitle>Provenance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-xs">
                <p className="text-content-muted">
                  Produced by the {artifact.owner_title} during{" "}
                  {stageLabel(artifact.stage).toLowerCase()}.
                </p>
                <p className="font-mono break-all text-content-subtle">
                  {artifact.produced_by_run_id}
                </p>
                <Link
                  href={`/projects/${id}/traceability`}
                  className="inline-block text-accent hover:text-accent-hover"
                >
                  View in traceability graph →
                </Link>
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
