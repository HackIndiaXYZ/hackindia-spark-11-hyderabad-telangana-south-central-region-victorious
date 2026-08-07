import Link from "next/link";
import { CircleCheck, CircleAlert, Lightbulb, TriangleAlert } from "lucide-react";

import { ScoreRing } from "@/components/review/score-ring";
import { StatusBadge } from "@/components/ui/status-badge";
import { scoreState, stageLabel, type ReviewFindingView, type ReviewView } from "@/lib/api";

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
 */
export function ReviewCard({
  review,
  projectId,
}: {
  review: ReviewView;
  projectId: string;
}) {
  const state = scoreState(review.quality_score);

  return (
    <article className="rounded-[--radius-card] border border-border bg-surface p-4">
      <div className="flex items-start gap-4">
        <ScoreRing score={review.quality_score} size={64} />

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <Link
                href={`/projects/${projectId}/artifacts/${review.artifact_id}`}
                className="text-sm text-content hover:text-accent"
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

          <p className="text-sm text-content-muted">{review.summary}</p>

          <FindingList
            title="Strengths"
            findings={review.strengths}
            icon={<CircleCheck className="size-3 text-state-complete" aria-hidden="true" />}
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

          <p className="pt-1 font-mono text-[11px] text-content-subtle">
            checks {review.deterministic_score}/100
            {review.reasoning_applied ? (
              <>
                {" · "}reasoning applied
                {review.reviewer_model ? ` (${review.reviewer_model})` : ""}
                {" · "}adjusted {formatDelta(review.quality_score - review.deterministic_score)}
              </>
            ) : (
              " · checks only"
            )}
          </p>
        </div>
      </div>
    </article>
  );
}

function formatDelta(delta: number) {
  return delta > 0 ? `+${delta}` : `${delta}`;
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
      <p className="text-[11px] tracking-wide text-content-subtle uppercase">{title}</p>
      <ul className="space-y-1">
        {findings.map((finding, index) => (
          <li
            key={`${title}-${index}`}
            className="flex items-start gap-2 text-xs text-content-muted"
          >
            <span className="mt-0.5 shrink-0">{icon}</span>
            <span>
              {finding.text}
              {finding.source === "check" && (
                <span
                  className="ml-1.5 rounded-sm bg-surface-raised px-1 font-mono text-[10px] text-content-subtle"
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
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <ScoreRing score={review.quality_score} size={56} />
        <div className="min-w-0 space-y-1">
          <StatusBadge state={scoreState(review.quality_score)}>
            {VERDICT_LABEL[review.verdict] ?? review.verdict}
          </StatusBadge>
          <p className="font-mono text-[11px] text-content-subtle">
            v{review.artifact_version} · checks {review.deterministic_score}/100
          </p>
        </div>
      </div>

      <p className="text-xs text-content-muted">{review.summary}</p>

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
    <p className="flex items-center gap-2 text-xs text-content-subtle">
      <TriangleAlert className="size-3" aria-hidden="true" />
      Not reviewed. Reviews are written when an agent produces an artifact; a
      human revision is not reviewed until the artifact is regenerated.
    </p>
  );
}
