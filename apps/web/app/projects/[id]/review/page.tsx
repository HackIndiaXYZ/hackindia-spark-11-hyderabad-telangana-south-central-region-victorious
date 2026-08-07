import { Lightbulb, ShieldCheck } from "lucide-react";

import { ReviewCard } from "@/components/review/review-card";
import { ScoreRing } from "@/components/review/score-ring";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, type RoleScore } from "@/lib/api";
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
        <EmptyState
          icon={ShieldCheck}
          title="Nothing reviewed yet"
          description="Advance the project and every artifact the organization produces will be scored as it lands — five deterministic checks, then a bounded reasoning pass."
        />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Header />

      {/* Headline. The overall score gets the whole left side because it is the
          one number a judge is here to see. */}
      <Card
        className="animate-[rise_0.45s_var(--ease-out-quint)_both] overflow-hidden"
        elevation="raised"
      >
        <CardContent className="flex flex-col gap-8 pt-6 sm:flex-row sm:items-center">
          <div className="flex items-center gap-5">
            <ScoreRing score={summary.overall_score} size={116} />
            <div className="space-y-1">
              <p className="text-[11px] font-medium tracking-[0.08em] text-content-subtle uppercase">
                Overall project
              </p>
              <p className="text-sm text-content">
                {summary.overall_score >= 85
                  ? "Strong across the organization"
                  : summary.overall_score >= 70
                    ? "Sound, with room to tighten"
                    : "Needs attention before shipping"}
              </p>
              <p className="max-w-xs text-xs leading-relaxed text-content-subtle">
                Mean of every artifact review. The tick on the ring marks 85 — the
                threshold for a strong review.
              </p>
            </div>
          </div>

          <dl className="grid flex-1 grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 sm:border-l sm:border-border sm:pl-8">
            <Stat label="Artifacts reviewed" value={summary.artifacts_reviewed} />
            <Stat label="Specialists scored" value={summary.by_role.length} />
            <Stat
              label="Reasoning coverage"
              value={summary.reasoning_coverage}
              suffix="%"
            />
            <Stat
              label="Needing revision"
              value={summary.needs_revision}
              alarming={summary.needs_revision > 0}
            />
          </dl>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <SectionLabel>Per-specialist scores</SectionLabel>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {summary.by_role.map((role, index) => (
            <li
              key={role.role}
              className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
              style={{ animationDelay: `${Math.min(index * 50, 300)}ms` }}
            >
              <RoleTile role={role} />
            </li>
          ))}
        </ul>
      </section>

      {summary.recommendations.length > 0 && (
        <section className="space-y-3">
          <SectionLabel>Recommendations</SectionLabel>
          <Card>
            <CardContent className="pt-5">
              <ul className="space-y-2.5">
                {summary.recommendations.map((recommendation, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-3 text-sm leading-relaxed text-content-muted"
                  >
                    <Lightbulb
                      className="mt-0.5 size-3.5 shrink-0 text-state-active"
                      aria-hidden="true"
                    />
                    {recommendation.text}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </section>
      )}

      <section className="space-y-3">
        <SectionLabel
          trailing={
            <span className="font-mono text-[11px] text-content-subtle">
              {summary.reviews.length}
            </span>
          }
        >
          Review history
        </SectionLabel>

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

function RoleTile({ role }: { role: RoleScore }) {
  return (
    <div className="flex h-full items-center gap-3 rounded-[--radius-card] border border-border bg-surface panel-sheen p-3.5 elevated transition-[border-color,box-shadow] duration-200 hover:border-border-strong">
      <ScoreRing score={role.average_score} size={52} showThreshold={false} />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-content">{role.role_title}</p>
        <p className="mt-0.5 text-xs text-content-subtle">
          {`${role.artifacts_reviewed} artifact${role.artifacts_reviewed === 1 ? "" : "s"} · lowest ${role.lowest_score}`}
        </p>
        {role.needs_revision > 0 && (
          <StatusBadge state="blocked" size="sm" className="mt-1.5">
            {role.needs_revision} need revision
          </StatusBadge>
        )}
      </div>
    </div>
  );
}

function Header() {
  return (
    <PageHeader
      eyebrow="Quality"
      title="Helix Review"
      description={
        <>
          An engineering review layer that scores every artifact the moment a
          specialist produces it — five deterministic checks worth 100 points,
          adjusted by at most ±12 by a reasoning pass that has to justify the move.
          <span className="mt-2 block text-xs text-content-subtle">
            The reviewer runs inside the API on the same model abstraction the
            specialists use. Helix, Mutagent&apos;s agent development lifecycle
            conductor, specs and evaluates it at development time and stays out of the
            runtime path — as{" "}
            <code className="font-mono text-content-muted">
              07_System_Architecture.md
            </code>{" "}
            requires.
          </span>
        </>
      }
      className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
    />
  );
}

function Stat({
  label,
  value,
  suffix,
  alarming = false,
}: {
  label: string;
  value: number;
  suffix?: string;
  alarming?: boolean;
}) {
  return (
    <div>
      <dd
        className={cn(
          "font-mono text-xl leading-none tracking-tight",
          alarming ? "text-state-stale" : "text-content",
        )}
      >
        <AnimatedNumber value={value} />
        {suffix && <span className="text-content-subtle">{suffix}</span>}
      </dd>
      <dt className="mt-1.5 text-xs text-content-muted">{label}</dt>
    </div>
  );
}
