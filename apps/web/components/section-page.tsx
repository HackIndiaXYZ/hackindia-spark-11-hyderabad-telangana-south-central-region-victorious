import { ArtifactList } from "@/components/artifact-list";
import { PageHeader } from "@/components/ui/page-header";
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
    <div className="space-y-5">
      <PageHeader
        eyebrow="Section"
        title={title}
        description={description}
        actions={
          artifacts.length > 0 ? (
            <span className="rounded-full border border-border bg-surface-raised px-2.5 py-1 font-mono text-[11px] text-content-subtle">
              {artifacts.length} artifact{artifacts.length === 1 ? "" : "s"}
            </span>
          ) : undefined
        }
        className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
      />

      <ArtifactList projectId={projectId} artifacts={artifacts} empty={empty} />
    </div>
  );
}
