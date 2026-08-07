import Link from "next/link";
import { CircleCheck, CircleAlert, Lightbulb, TriangleAlert } from "lucide-react";

import { ScoreRing } from "@/components/review/score-ring";
import { StatusBadge } from "@/components/ui/status-badge";
import { Card } from "@/components/ui/card";
import {
  scoreState,
  stageLabel,
  type ReviewFindingView,
  type ReviewView,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const VERDICT_LABEL: Record<string, string> = {
  approved: "approved",
  approved_with_suggestions: "approved with suggestions",
  needs_revision: "needs revision",
};

/**
 * One artifact's review.
 *
 * Every finding is tagged with where it came from: a deterministic check that
 * ran the same way every time, or the reviewing model's reading of the content.
 * A judge should be able to tell those apart at a glance, because only one of
 * them is reproducible.
 *
 * The score split — checks out of 100, then a bounded reasoning adjustment — is
 * drawn rather than described. A user can see how much of the number was
 * measured and how much was judged without reading the footnote.
 */
export function ReviewCard({
  review,
  projectId,
}: {
  review: ReviewView;
  projectId: string;
}) {
  const state = scoreState(review.quality_score);
  const delta = review.quality_score - review.deterministic_score;

  return (
    <Card interactive className="group p-4">
      <div className="flex items-start gap-4">
        <ScoreRing score={review.quality_score} size={64} showThreshold={false} />

        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <Link
                href={`/projects/${projectId}/artifacts/${review.artifact_id}`}
                className="text-sm font-medium text-content transition-colors hover:text-accent"
              >
                {review.artifact_title}
              </Link>
              <p className="mt-0.5 text-xs text-content-subtle">
                {review.role_title} · {stageLabel(review.stage)} · v
                {review.artifact_version}
              </p>
            </div>
            <StatusBadge state={state}>
              {VERDICT_LABEL[review.verdict] ?? review.verdict}
            </StatusBadge>
          </div>

          <p className="text-sm leading-relaxed text-content-muted">{review.summary}</p>

          <div className="space-y-2.5">
            <FindingList
              title="Strengths"
              findings={review.strengths}
              icon={
                <CircleCheck className="size-3 text-state-complete" aria-hidden="true" />
              }
            />
            <FindingList
              title="Weaknesses"
              findings={review.weaknesses}
              icon={<CircleAlert className="size-3 text-state-stale" aria-hidden="true" />}
            />
            <FindingList
              title="Suggestions"
              findings={review.suggestions}
              icon={<Lightbulb className="size-3 text-state-active" aria-hidden="true" />}
            />
          </div>

          <ScoreProvenance
            deterministic={review.deterministic_score}
            delta={delta}
            reasoningApplied={review.reasoning_applied}
            model={review.reviewer_model}
          />
        </div>
      </div>
    </Card>
  );
}

/**
 * Where the score came from, drawn as a bar.
 *
 * The measured portion is solid; the reasoning adjustment is a hatched cap in
 * the accent, positive or negative. Seeing the cap is the point — it makes the
 * ±12 bound obvious without a legend.
 */
function ScoreProvenance({
  deterministic,
  delta,
  reasoningApplied,
  model,
}: {
  deterministic: number;
  delta: number;
  reasoningApplied: boolean;
  model: string | null;
}) {
  const base = Math.max(0, Math.min(100, deterministic + Math.min(0, delta)));
  const adjustment = Math.abs(delta);

  return (
    <div className="space-y-1.5 border-t border-border pt-2.5">
      <div
        className="flex h-1 overflow-hidden rounded-full bg-surface-overlay"
        role="img"
        aria-label={
          reasoningApplied
            ? `Checks scored ${deterministic} of 100; reasoning adjusted it by ${delta > 0 ? "+" : ""}${delta}`
            : `Checks scored ${deterministic} of 100; no reasoning applied`
        }
      >
        <span className="h-full bg-content-subtle/70" style={{ width: `${base}%` }} />
        {reasoningApplied && adjustment > 0 && (
          <span
            className={cn(
              "h-full",
              delta > 0 ? "bg-accent" : "bg-state-blocked/80",
            )}
            style={{ width: `${adjustment}%` }}
          />
        )}
      </div>

      <p className="font-mono text-[11px] text-content-subtle">
        checks {deterministic}/100
        {reasoningApplied ? (
          <>
            {" · "}reasoning {delta > 0 ? `+${delta}` : delta}
            {model ? ` (${model})` : ""}
          </>
        ) : (
          " · checks only"
        )}
      </p>
    </div>
  );
}

function FindingList({
  title,
  findings,
  icon,
}: {
  title: string;
  findings: ReviewFindingView[];
  icon: React.ReactNode;
}) {
  if (findings.length === 0) return null;

  return (
    <div className="space-y-1">
      <p className="text-[10px] font-medium tracking-[0.08em] text-content-subtle uppercase">
        {title}
      </p>
      <ul className="space-y-1">
        {findings.map((finding, index) => (
          <li
            key={`${title}-${index}`}
            className="flex items-start gap-2 text-xs leading-relaxed text-content-muted"
          >
            <span className="mt-0.5 shrink-0">{icon}</span>
            <span>
              {finding.text}
              {finding.source === "check" && (
                <span
                  className="ml-1.5 rounded border border-border bg-surface-raised px-1 font-mono text-[10px] text-content-subtle"
                  title="Produced by a deterministic check, identical on every run"
                >
                  check
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The compact review, for the artifact page sidebar.
 *
 * Same data as {@link ReviewCard} minus the artifact identification, which the
 * page it sits on already carries.
 */
export function ArtifactReviewPanel({ review }: { review: ReviewView }) {
  return (
    <div className="space-y-3.5">
      <div className="flex items-center gap-3">
        <ScoreRing score={review.quality_score} size={56} showThreshold={false} />
        <div className="min-w-0 space-y-1.5">
          <StatusBadge state={scoreState(review.quality_score)} size="sm">
            {VERDICT_LABEL[review.verdict] ?? review.verdict}
          </StatusBadge>
          <p className="font-mono text-[11px] text-content-subtle">
            v{review.artifact_version} · checks {review.deterministic_score}/100
          </p>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-content-muted">{review.summary}</p>

      <FindingList
        title="Weaknesses"
        findings={review.weaknesses}
        icon={<CircleAlert className="size-3 text-state-stale" aria-hidden="true" />}
      />
      <FindingList
        title="Suggestions"
        findings={review.suggestions}
        icon={<Lightbulb className="size-3 text-state-active" aria-hidden="true" />}
      />
    </div>
  );
}

/** Shown on an artifact page when no review exists — a real state, not an error. */
export function ReviewUnavailable() {
  return (
    <p className="flex items-start gap-2 text-xs leading-relaxed text-content-subtle">
      <TriangleAlert className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
      Not reviewed. Reviews are written when an agent produces an artifact; a human
      revision is not reviewed until the artifact is regenerated.
    </p>
  );
}
