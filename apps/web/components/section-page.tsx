import { ArtifactList } from "@/components/artifact-list";
import { api, type LifecycleStage } from "@/lib/api";

/**
 * A workspace section: the artifacts produced by one or more lifecycle stages.
 *
 * The Requirements, Architecture, Development, Testing, and Documentation
 * centres in `06_Product_Architecture.md` differ only in which stages they show,
 * so they share this component rather than five near-identical pages.
 */
export async function SectionPage({
  projectId,
  title,
  description,
  stages,
  empty,
}: {
  projectId: string;
  title: string;
  description: string;
  stages: LifecycleStage[];
  empty: string;
}) {
  const results = await Promise.all(
    stages.map((stage) => api.listArtifacts(projectId, { stage })),
  );
  const artifacts = results.flat();

  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-sm font-medium tracking-tight">{title}</h2>
        <p className="text-sm text-content-muted">{description}</p>
      </header>

      <ArtifactList projectId={projectId} artifacts={artifacts} empty={empty} />
    </div>
  );
}
