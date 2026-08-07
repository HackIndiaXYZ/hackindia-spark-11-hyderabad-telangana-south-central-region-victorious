import Link from "next/link";
import { ArrowRight, ClipboardCheck, FileText, Users } from "lucide-react";

import { ApprovalDecision } from "@/components/approval-decision";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, badgeState, stageLabel, typeLabel } from "@/lib/api";

/**
 * Approval Center.
 *
 * `10_UI_UX_Plan.md` requires a reviewer to see five things before deciding:
 * what changed, why it changed, which agents were involved, the downstream
 * impact, and the available actions. All five are on this page — the impact in
 * particular is computed *before* the decision, so consequences are visible in
 * advance rather than discovered afterwards.
 *
 * A pending gate is the loudest thing in the workspace, because work downstream
 * of it has genuinely stopped and the only thing that restarts it is a person.
 */

export const metadata = { title: "Approvals" };
export const dynamic = "force-dynamic";

export default async function ApprovalsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const approvals = await api.listApprovals(id);

  const pending = approvals.filter((approval) => approval.status === "pending");
  const decided = approvals.filter((approval) => approval.status !== "pending");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Governance"
        title="Approval Center"
        description="Engineering decisions that need a human. Work downstream of a pending gate genuinely stops until you decide."
        actions={
          pending.length > 0 ? (
            <StatusBadge state="approval" pulse>
              {pending.length} awaiting you
            </StatusBadge>
          ) : undefined
        }
        className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
      />

      {approvals.length === 0 && (
        <EmptyState
          icon={ClipboardCheck}
          title="Nothing is waiting on you"
          description="Gates appear as the organization reaches decisions it should not make alone — approving requirements, an architecture, or code generation."
        />
      )}

      {pending.map((approval, index) => (
        <Card
          key={approval.id}
          state="approval"
          className="animate-[rise_0.45s_var(--ease-out-quint)_both] overflow-hidden"
          style={{ animationDelay: `${index * 60}ms` }}
        >
          <span
            aria-hidden="true"
            className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-state-approval to-transparent"
          />

          <CardHeader className="flex-row items-start justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="text-base">{approval.title}</CardTitle>
              <p className="mt-1 text-xs text-content-subtle">
                Requested by the Executive AI · blocks {stageLabel(approval.stage)}
              </p>
            </div>
            <StatusBadge state="approval" pulse>
              {approval.kind.replace(/_/g, " ")}
            </StatusBadge>
          </CardHeader>

          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="What changed">{approval.what_changed}</Field>
              <Field label="Why">{approval.why}</Field>
            </div>

            {approval.agent_titles.length > 0 && (
              <Field label="Agents involved" icon={Users}>
                {approval.agent_titles.join(", ")}
              </Field>
            )}

            {approval.artifacts.length > 0 && (
              <div className="space-y-2">
                <FieldLabel icon={FileText}>Under review</FieldLabel>
                <ul className="grid gap-1.5 sm:grid-cols-2">
                  {approval.artifacts.map((artifact) => (
                    <li key={artifact.id}>
                      <Link
                        href={`/projects/${id}/artifacts/${artifact.id}`}
                        className="group flex items-center gap-2 rounded-lg border border-border bg-canvas/40 px-3 py-2 transition-colors hover:border-border-strong hover:bg-surface-raised"
                      >
                        <span className="min-w-0 flex-1 truncate text-sm text-content">
                          {artifact.title}
                        </span>
                        <span className="shrink-0 text-[11px] text-content-subtle">
                          {typeLabel(artifact.type)}
                        </span>
                        <ArrowRight
                          className="size-3 shrink-0 text-content-subtle transition-transform duration-200 group-hover:translate-x-0.5"
                          aria-hidden="true"
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {approval.impacted.length > 0 && (
              <div className="space-y-2 rounded-lg border border-border bg-canvas/40 p-3.5">
                <p className="text-xs text-content-muted">
                  <span className="font-medium text-content">
                    Downstream impact
                  </span>{" "}
                  · {approval.impacted.length} artifact
                  {approval.impacted.length === 1 ? "" : "s"} depend on this
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {approval.impacted.slice(0, 12).map((item) => (
                    <li
                      key={item.artifact_id}
                      className="rounded-md border border-border bg-surface-raised px-2 py-0.5 text-[11px] text-content-muted"
                    >
                      {item.title}
                      <span className="ml-1 font-mono text-content-subtle">
                        ·{item.depth}
                      </span>
                    </li>
                  ))}
                  {approval.impacted.length > 12 && (
                    <li className="px-2 py-0.5 text-[11px] text-content-subtle">
                      and {approval.impacted.length - 12} more
                    </li>
                  )}
                </ul>
              </div>
            )}

            <ApprovalDecision approvalId={approval.id} />
          </CardContent>
        </Card>
      ))}

      {decided.length > 0 && (
        <section className="space-y-3">
          <SectionLabel
            trailing={
              <span className="font-mono text-[11px] text-content-subtle">
                {decided.length}
              </span>
            }
          >
            Decided
          </SectionLabel>

          <ul className="space-y-2">
            {decided.map((approval) => (
              <li
                key={approval.id}
                className="flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface panel-sheen px-4 py-3 transition-colors duration-200 hover:border-border-strong"
              >
                <StatusBadge state={badgeState(approval.status)} size="sm">
                  {approval.status.replace(/_/g, " ")}
                </StatusBadge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-content">{approval.title}</p>
                  {approval.feedback && (
                    <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-content-muted italic">
                      “{approval.feedback}”
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function FieldLabel({
  icon: Icon,
  children,
}: {
  icon?: React.ComponentType<{ className?: string }> | undefined;
  children: React.ReactNode;
}) {
  return (
    <p className="flex items-center gap-1.5 text-[10px] font-medium tracking-[0.08em] text-content-subtle uppercase">
      {Icon && <Icon className="size-3" aria-hidden="true" />}
      {children}
    </p>
  );
}

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: React.ComponentType<{ className?: string }> | undefined;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <FieldLabel icon={icon}>{label}</FieldLabel>
      <p className="text-sm leading-relaxed text-content-muted">{children}</p>
    </div>
  );
}
