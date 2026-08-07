import { Lightbulb } from "lucide-react";

import { ReviewCard } from "@/components/review/review-card";
import { ScoreRing } from "@/components/review/score-ring";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Helix Review — the organization's engineering quality, scored.
 *
 * Every artifact a specialist produces is reviewed the moment it lands: five
 * deterministic checks worth 100 points, then a reasoning pass that can move the
 * score by at most ±12 and must justify the move in writing. The split is
 * visible on every card because it is the difference between a number you can
 * reproduce and a number you have to trust.
 *
 * The reviewer runs natively inside the API, on the same `LLMProvider`
 * abstraction the specialists use. Helix — Mutagent's agent development
 * lifecycle conductor — specifies, evaluates, and optimizes that reviewer at
 * development time, and stays out of the runtime path exactly as
 * `07_System_Architecture.md` requires.
 */

export const metadata = { title: "Helix Review" };
export const dynamic = "force-dynamic";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const summary = await api.getReviews(id);

  if (summary.artifacts_reviewed === 0) {
    return (
      <div className="space-y-6">
        <Header />
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-content-muted">
              Nothing reviewed yet. Advance the project and every artifact the
              organization produces will be scored as it lands.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Header />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-8 pt-5">
          <ScoreRing score={summary.overall_score} size={112} label="Overall project" />

          <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3">
            <Stat label="Artifacts reviewed" value={String(summary.artifacts_reviewed)} />
            <Stat label="Specialists scored" value={String(summary.by_role.length)} />
            <Stat
              label="Reasoning coverage"
              value={`${summary.reasoning_coverage}%`}
            />
            <Stat
              label="Needing revision"
              value={String(summary.needs_revision)}
              alarming={summary.needs_revision > 0}
            />
          </dl>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h3 className="text-xs tracking-wide text-content-subtle uppercase">
          Per-specialist scores
        </h3>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {summary.by_role.map((role) => (
            <li
              key={role.role}
              className="flex items-center gap-3 rounded-[--radius-card] border border-border bg-surface p-3"
            >
              <ScoreRing score={role.average_score} size={52} />
              <div className="min-w-0">
                <p className="truncate text-sm text-content">{role.role_title}</p>
                <p className="text-xs text-content-subtle">
                  {`${role.artifacts_reviewed} artifact${
                    role.artifacts_reviewed === 1 ? "" : "s"
                  } · lowest ${role.lowest_score}`}
                </p>
                {role.needs_revision > 0 && (
                  <StatusBadge state="blocked" className="mt-1">
                    {role.needs_revision} need revision
                  </StatusBadge>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      {summary.recommendations.length > 0 && (
        <Card>
          <CardHeader className="flex-row items-center gap-2">
            <Lightbulb className="size-4 text-state-active" aria-hidden="true" />
            <CardTitle>Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {summary.recommendations.map((recommendation, index) => (
                <li key={index} className="text-sm text-content-muted">
                  {recommendation.text}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <section className="space-y-3">
        <h3 className="text-xs tracking-wide text-content-subtle uppercase">
          Review history
        </h3>
        <ul className="space-y-2">
          {summary.reviews.map((review) => (
            <li key={review.id}>
              <ReviewCard review={review} projectId={id} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Header() {
  return (
    <header className="space-y-1">
      <h2 className="text-sm font-medium tracking-tight">Helix Review</h2>
      <p className="text-sm text-content-muted">
        An engineering review layer that scores every artifact the moment a
        specialist produces it — five deterministic checks worth 100 points,
        adjusted by at most ±12 by a reasoning pass that has to justify the move.
      </p>
      <p className="text-xs text-content-subtle">
        The reviewer runs inside the API on the same model abstraction the
        specialists use. Helix, Mutagent&apos;s agent development lifecycle
        conductor, specs and evaluates it at development time and stays out of
        the runtime path — as{" "}
        <code className="font-mono">07_System_Architecture.md</code> requires.
      </p>
    </header>
  );
}

function Stat({
  label,
  value,
  alarming = false,
}: {
  label: string;
  value: string;
  alarming?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-content-subtle">{label}</dt>
      <dd
        className={cn(
          "font-mono text-lg tabular-nums",
          alarming ? "text-state-stale" : "text-content",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
