import { Library } from "lucide-react";

import { ArtifactList } from "@/components/artifact-list";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader, SectionLabel } from "@/components/ui/page-header";
import { api, stageLabel, type LifecycleStage } from "@/lib/api";

/**
 * Knowledge Base — the organizational memory of the project.
 *
 * `10_UI_UX_Plan.md`: "The Knowledge Base should function as the organizational
 * memory of every project." Everything the organization has produced, grouped by
 * the stage that produced it, so the whole project is browsable in one place.
 */

export const metadata = { title: "Knowledge Base" };
export const dynamic = "force-dynamic";

export default async function KnowledgePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const artifacts = await api.listArtifacts(id);

  const byStage = new Map<LifecycleStage, typeof artifacts>();
  for (const artifact of artifacts) {
    const existing = byStage.get(artifact.stage);
    if (existing) existing.push(artifact);
    else byStage.set(artifact.stage, [artifact]);
  }

  const stale = artifacts.filter((artifact) => artifact.is_stale).length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Memory"
        title="Knowledge Base"
        description={
          <>
            Every artifact the organization has produced — {artifacts.length} in total
            {stale > 0 && (
              <>
                , <span className="text-state-stale">{stale} out of date</span> with
                their upstream
              </>
            )}
            .
          </>
        }
        actions={
          stale > 0 ? (
            <span className="rounded-full border border-state-stale/30 bg-state-stale/[0.08] px-2.5 py-1 font-mono text-[11px] text-state-stale">
              {stale} stale
            </span>
          ) : undefined
        }
        className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
      />

      {artifacts.length === 0 ? (
        <EmptyState
          icon={Library}
          title="The organizational memory is empty"
          description="The organization has not produced anything yet. Use Advance engineering and artifacts will appear here, grouped by the stage that produced them."
        />
      ) : (
        [...byStage.entries()].map(([stage, group]) => (
          <section key={stage} className="space-y-3">
            <SectionLabel
              trailing={
                <span className="font-mono text-[11px] text-content-subtle">
                  {group.length}
                </span>
              }
            >
              {stageLabel(stage)}
            </SectionLabel>
            <ArtifactList projectId={id} artifacts={group} empty="" />
          </section>
        ))
      )}
    </div>
  );
}
