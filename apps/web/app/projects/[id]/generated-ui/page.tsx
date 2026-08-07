import { Wand2 } from "lucide-react";

import { DerivationPanel } from "@/components/generated/derivation-panel";
import { PreviewFrame } from "@/components/generated/preview-frame";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatTile } from "@/components/ui/stat-tile";
import { api, type ArtifactDetail } from "@/lib/api";
import { synthesize } from "@/lib/generation/synthesize";

/**
 * AI Generated UI — an application synthesised from the organization's artifacts.
 *
 * Experimental, and additive: nothing else in the workspace changes, and this
 * page reads the existing API rather than introducing any backend surface.
 *
 * The generation is a pure function of artifacts the agents already produced
 * (`lib/generation/synthesize.ts`). No model call happens here — which is what
 * makes it instant, offline, reproducible, and, most importantly, *traceable*:
 * every generated screen can name the artifact that caused it, and the
 * derivation panel below lists every rule that fired.
 */

export const metadata = { title: "AI Generated UI" };
export const dynamic = "force-dynamic";

/**
 * Artifact *content* only comes from the detail endpoint, so the summaries are
 * fanned out. Bounded by the artifact count of one project (22 on the reference
 * scenario) and issued in parallel, so it costs one round trip in wall time.
 */
async function loadArtifacts(projectId: string): Promise<ArtifactDetail[]> {
  const summaries = await api.listArtifacts(projectId);

  const details = await Promise.all(
    summaries.map(async (summary) => {
      try {
        return await api.getArtifact(projectId, summary.id);
      } catch {
        // One unreadable artifact must not cost the whole generation.
        return null;
      }
    }),
  );

  return details.filter((item): item is ArtifactDetail => item !== null);
}

export default async function GeneratedUiPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [project, artifacts] = await Promise.all([api.getProject(id), loadArtifacts(id)]);

  const header = (
    <PageHeader
      eyebrow="Experimental"
      title="AI Generated UI"
      description={
        <>
          A working frontend synthesised from this project&apos;s own engineering
          artifacts — requirements become features, the data model becomes tables and
          forms, the API contract becomes actions, and the coverage report becomes a
          chart.
          <span className="mt-2 block text-xs text-content-subtle">
            Derived structurally rather than prompted, so it renders instantly, offline,
            and identically on every run — and every element can name the artifact it
            came from.
          </span>
        </>
      }
      className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
    />
  );

  if (artifacts.length === 0) {
    return (
      <div className="space-y-6">
        {header}
        <EmptyState
          icon={Wand2}
          title="Nothing to generate from yet"
          description="Advance the project so the organization produces requirements, a data model, and an API contract. The generated interface is built from those, so it appears as soon as they exist."
        />
      </div>
    );
  }

  const spec = synthesize(project, artifacts);

  return (
    <div className="space-y-8">
      {header}

      <section
        aria-label="Generation summary"
        className="grid animate-[rise_0.45s_var(--ease-out-quint)_both] gap-3 sm:grid-cols-2 lg:grid-cols-4"
        style={{ animationDelay: "60ms" }}
      >
        <StatTile
          label="Artifacts read"
          value={spec.stats.artifactsRead}
          icon={Wand2}
          hint="Everything the organization produced"
        />
        <StatTile
          label="Screens generated"
          value={spec.pages.length}
          icon={Wand2}
          hint={`${spec.stats.blocks} blocks in total`}
        />
        <StatTile
          label="Entities modelled"
          value={spec.stats.entities}
          icon={Wand2}
          hint={`${spec.stats.endpoints} endpoints wired`}
        />
        <StatTile
          label="Requirements used"
          value={spec.stats.requirements}
          icon={Wand2}
          hint={`${spec.stats.userStories} user stories`}
        />
      </section>

      <PreviewFrame spec={spec} />

      <DerivationPanel spec={spec} artifacts={artifacts} projectId={id} />
    </div>
  );
}
