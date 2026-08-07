import Link from "next/link";

import { ApprovalDecision } from "@/components/approval-decision";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-sm font-medium tracking-tight">Approval Center</h2>
        <p className="text-sm text-content-muted">
          Engineering decisions that need a human. Work downstream of a pending gate
          genuinely stops until you decide.
        </p>
      </header>

      {approvals.length === 0 && (
        <Card>
          <CardContent className="pt-5">
            <p className="text-sm text-content-muted">
              Nothing is waiting on you. Gates appear as the organization reaches
              decisions it should not make alone.
            </p>
          </CardContent>
        </Card>
      )}

      {pending.map((approval) => (
        <Card key={approval.id} className="border-state-approval/30">
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle>{approval.title}</CardTitle>
              <p className="mt-0.5 text-xs text-content-subtle">
                Requested by the Executive AI · blocks {stageLabel(approval.stage)}
              </p>
            </div>
            <StatusBadge state="approval">{approval.kind.replace(/_/g, " ")}</StatusBadge>
          </CardHeader>

          <CardContent className="space-y-4">
            <Field label="What changed">{approval.what_changed}</Field>
            <Field label="Why">{approval.why}</Field>

            {approval.agent_titles.length > 0 && (
              <Field label="Agents involved">{approval.agent_titles.join(", ")}</Field>
            )}

            {approval.artifacts.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-content-subtle">Under review</p>
                <ul className="space-y-1">
                  {approval.artifacts.map((artifact) => (
                    <li key={artifact.id}>
                      <Link
                        href={`/projects/${id}/artifacts/${artifact.id}`}
                        className="text-sm text-accent hover:text-accent-hover"
                      >
                        {artifact.title}
                      </Link>
                      <span className="ml-2 text-xs text-content-subtle">
                        {typeLabel(artifact.type)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {approval.impacted.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs text-content-subtle">
                  Downstream impact · {approval.impacted.length} artifact
                  {approval.impacted.length === 1 ? "" : "s"} depend on this
                </p>
                <ul className="flex flex-wrap gap-1.5">
                  {approval.impacted.slice(0, 12).map((item) => (
                    <li
                      key={item.artifact_id}
                      className="rounded border border-border bg-surface-raised px-2 py-0.5 text-xs text-content-muted"
                    >
                      {item.title}
                      <span className="ml-1 text-content-subtle">·{item.depth}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <ApprovalDecision approvalId={approval.id} />
          </CardContent>
        </Card>
      ))}

      {decided.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs tracking-wide text-content-subtle uppercase">
            Decided
          </h3>
          <ul className="space-y-2">
            {decided.map((approval) => (
              <li
                key={approval.id}
                className="flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface px-4 py-3"
              >
                <StatusBadge state={badgeState(approval.status)}>
                  {approval.status.replace(/_/g, " ")}
                </StatusBadge>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-content">{approval.title}</p>
                  {approval.feedback && (
                    <p className="mt-0.5 line-clamp-2 text-xs text-content-muted">
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

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-content-subtle">{label}</p>
      <p className="text-sm text-content-muted">{children}</p>
    </div>
  );
}
