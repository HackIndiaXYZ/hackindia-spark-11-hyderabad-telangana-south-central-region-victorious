import Link from "next/link";
import { ArrowRight, CornerDownRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { SectionLabel } from "@/components/ui/page-header";
import type { ArtifactDetail } from "@/lib/api";
import { typeLabel } from "@/lib/api";
import type { AppSpec } from "@/lib/generation/types";

/**
 * Every synthesis rule that fired, and the artifact it read.
 *
 * This is the panel that turns the feature from a party trick into a claim the
 * platform can defend. Anyone can render a nice-looking dashboard; the
 * interesting assertion is that *this* dashboard exists because *that*
 * requirement does, and that changing the requirement would change the
 * interface.
 *
 * Rules are shown in the order synthesis emitted them, so reading top to bottom
 * is reading the generation itself.
 */
export function DerivationPanel({
  spec,
  artifacts,
  projectId,
}: {
  spec: AppSpec;
  artifacts: ArtifactDetail[];
  projectId: string;
}) {
  const byId = new Map(artifacts.map((artifact) => [artifact.id, artifact]));

  return (
    <section className="space-y-3">
      <SectionLabel
        trailing={
          <span className="font-mono text-[11px] text-content-subtle">
            {spec.derivation.length} rules
          </span>
        }
      >
        How this was generated
      </SectionLabel>

      <Card>
        <CardContent className="pt-5">
          <ol className="space-y-2.5">
            {spec.derivation.map((item, index) => (
              <li key={index} className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md border border-border bg-surface-raised font-mono text-[10px] text-content-subtle"
                >
                  {index + 1}
                </span>

                <div className="min-w-0 flex-1 space-y-1">
                  <p className="font-mono text-xs leading-relaxed text-content">{item.rule}</p>

                  {item.sourceArtifactIds.length > 0 && (
                    <ul className="flex flex-wrap items-center gap-1.5">
                      <CornerDownRight
                        className="size-3 shrink-0 text-content-subtle"
                        aria-hidden="true"
                      />
                      {item.sourceArtifactIds.map((id) => {
                        const artifact = byId.get(id);
                        if (!artifact) return null;
                        return (
                          <li key={id}>
                            <Link
                              href={`/projects/${projectId}/artifacts/${id}`}
                              className="group inline-flex items-center gap-1 rounded-md border border-border bg-surface-raised px-2 py-0.5 text-[11px] text-content-muted transition-colors hover:border-accent/40 hover:text-accent"
                            >
                              {typeLabel(artifact.type)}
                              <ArrowRight
                                className="size-2.5 transition-transform duration-200 group-hover:translate-x-0.5"
                                aria-hidden="true"
                              />
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </section>
  );
}
