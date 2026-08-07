import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertTriangle, ArrowRight, ChevronLeft, History } from "lucide-react";

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
import { cn } from "@/lib/utils";

/**
 * One engineering artifact, with its content, provenance, and version history.
 *
 * The version list is what makes `12_Risk_Analysis.md`'s "version-controlled
 * engineering artifacts" mitigation visible: an earlier version is readable
 * exactly as the agent that consumed it saw it.
 *
 * The document takes the width and the metadata takes a rail, because this is
 * the one page in the workspace a user comes to *read*. The rail sticks so the
 * review and the version history stay reachable through a long artifact.
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
        className="group inline-flex items-center gap-1 text-xs text-content-subtle transition-colors hover:text-content"
      >
        <ChevronLeft
          className="size-3 transition-transform duration-200 group-hover:-translate-x-0.5"
          aria-hidden="true"
        />
        Knowledge Base
      </Link>

      <header className="animate-[rise_0.4s_var(--ease-out-quint)_both] space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-balance text-content">
            {artifact.title}
          </h1>
          <div className="flex items-center gap-2">
            {artifact.is_stale && <StatusBadge state="stale">stale</StatusBadge>}
            <StatusBadge state={badgeState(artifact.status)}>
              {artifact.status.replace(/_/g, " ")}
            </StatusBadge>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-content-subtle">
          <span className="rounded-md border border-border bg-surface-raised px-2 py-0.5 text-content-muted">
            {typeLabel(artifact.type)}
          </span>
          <Dot />
          <span>{stageLabel(artifact.stage)}</span>
          <Dot />
          <span>{artifact.owner_title}</span>
          <Dot />
          <span className="font-mono">
            v{artifact.version}
            {!artifact.is_latest && " (historical)"}
          </span>
          {artifact.confidence !== null && (
            <>
              <Dot />
              <span className="font-mono">
                {Math.round(artifact.confidence * 100)}% confidence
              </span>
            </>
          )}
        </div>
      </header>

      {artifact.is_stale && (
        <div className="flex animate-[rise_0.45s_var(--ease-out-quint)_both] gap-3 rounded-[--radius-card] border border-state-stale/35 bg-state-stale/[0.07] px-4 py-3.5">
          <AlertTriangle
            className="mt-0.5 size-4 shrink-0 text-state-stale"
            aria-hidden="true"
          />
          <div className="space-y-1">
            <p className="text-sm font-medium text-content">
              Out of date with its upstream
            </p>
            <p className="text-xs leading-relaxed text-content-muted">
              This was derived from an earlier version of something that has since
              changed.{" "}
              <Link
                href={`/projects/${id}/traceability`}
                className="text-accent transition-colors hover:text-accent-hover"
              >
                See what it depends on →
              </Link>
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardContent className="pt-6">
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

        <aside className="space-y-4 lg:sticky lg:top-56 lg:self-start">
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
            <CardHeader className="flex-row items-center gap-2">
              <History className="size-3.5 text-content-subtle" aria-hidden="true" />
              <CardTitle>Version history</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-1">
                {artifact.versions.map((entry) => {
                  const active = entry.version === artifact.version;
                  return (
                    <li key={entry.version}>
                      <Link
                        href={`/projects/${id}/artifacts/${artifactId}?version=${entry.version}`}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "block rounded-lg border px-3 py-2 transition-colors duration-150",
                          active
                            ? "border-accent/40 bg-accent/[0.08]"
                            : "border-transparent hover:border-border hover:bg-surface-raised",
                        )}
                      >
                        <p className="font-mono text-xs text-content">
                          v{entry.version}
                          {entry.version === artifact.current_version && (
                            <span className="text-content-subtle"> · latest</span>
                          )}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-content-subtle">
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
                <p className="leading-relaxed text-content-muted">
                  Produced by the {artifact.owner_title} during{" "}
                  {stageLabel(artifact.stage).toLowerCase()}.
                </p>
                <p className="rounded-md bg-canvas-deep px-2 py-1.5 font-mono break-all text-content-subtle">
                  {artifact.produced_by_run_id}
                </p>
                <Link
                  href={`/projects/${id}/traceability`}
                  className="group/link inline-flex items-center gap-1 text-accent transition-colors hover:text-accent-hover"
                >
                  View in traceability graph
                  <ArrowRight
                    className="size-3 transition-transform duration-200 group-hover/link:translate-x-0.5"
                    aria-hidden="true"
                  />
                </Link>
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}

function Dot() {
  return (
    <span aria-hidden="true" className="text-content-subtle/50">
      ·
    </span>
  );
}
