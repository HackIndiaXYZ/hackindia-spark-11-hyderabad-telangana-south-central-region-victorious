import { ArtifactList } from "@/components/artifact-list";
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
    <div className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-sm font-medium tracking-tight">Knowledge Base</h2>
        <p className="text-sm text-content-muted">
          Every artifact the organization has produced — {artifacts.length} in total
          {stale > 0 && (
            <>
              , <span className="text-state-stale">{stale} out of date</span> with their
              upstream
            </>
          )}
          .
        </p>
      </header>

      {artifacts.length === 0 ? (
        <ArtifactList
          projectId={id}
          artifacts={[]}
          empty="The organization has not produced anything yet."
        />
      ) : (
        [...byStage.entries()].map(([stage, group]) => (
          <section key={stage} className="space-y-2">
            <h3 className="text-xs tracking-wide text-content-subtle uppercase">
              {stageLabel(stage)}
            </h3>
            <ArtifactList projectId={id} artifacts={group} empty="" />
          </section>
        ))
      )}
    </div>
  );
}
