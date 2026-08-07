"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, Loader2, Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { api, type ImpactPreview } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * Revise an artifact by hand.
 *
 * The action that makes the platform's central claim demonstrable: change a
 * requirement, and the organization works out what downstream no longer reflects
 * it. Nothing is regenerated here — the impact is surfaced, and the user decides.
 *
 * Appending a version rather than editing in place keeps the version downstream
 * agents actually consumed readable, which is what makes staleness computable at
 * all (ADR-0007).
 *
 * The blast-radius panel is the loudest thing in the editor on purpose. It is
 * the one piece of information that should change a user's mind before they
 * commit, so it sits above the fields rather than beside the save button.
 */
export function ReviseArtifact({
  projectId,
  artifactId,
  currentMarkdown,
}: {
  projectId: string;
  artifactId: string;
  currentMarkdown: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState(currentMarkdown);
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [impact, setImpact] = useState<ImpactPreview | null>(null);

  /**
   * The blast radius, fetched when the editor opens — before anything changes.
   *
   * `10_UI_UX_Plan.md` requires downstream impact to be visible at the point of
   * decision. Reporting it afterwards would make this a record of damage rather
   * than a tool for deciding whether to do it.
   */
  async function begin() {
    setOpen(true);
    try {
      setImpact(await api.getImpact(projectId, artifactId));
    } catch {
      // The editor still works without the preview; a failed read must not stop
      // a user from making a change they have already decided on.
    }
  }

  async function submit() {
    if (body.trim().length === 0) {
      setError("An artifact cannot be emptied.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await api.reviseArtifact(projectId, artifactId, body, summary.trim() || undefined);
      setOpen(false);
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The revision failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button type="button" variant="secondary" size="sm" onClick={begin}>
        <Pencil aria-hidden="true" />
        Revise
      </Button>
    );
  }

  return (
    <div className="animate-[rise_0.35s_var(--ease-out-quint)_both] space-y-4 rounded-[--radius-card] border border-border bg-surface panel-sheen p-5 elevated-lg">
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-content">Revise this artifact</h3>
        <p className="text-xs leading-relaxed text-content-muted">
          This appends a new version. Everything derived from the current version will
          be flagged as out of date, and the organization will offer to rebuild it.
        </p>
      </div>

      {impact && impact.impacted.length > 0 && (
        <div className="space-y-2.5 rounded-lg border border-state-stale/30 bg-state-stale/[0.07] p-3.5">
          <p className="flex items-start gap-2 text-xs leading-relaxed text-state-stale">
            <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <strong className="font-semibold">
                {impact.impacted.length} artifacts
              </strong>{" "}
              depend on this and would go out of date
              {impact.stages_affected.length > 0 && (
                <> · {impact.stages_affected.length} stages would rerun</>
              )}
            </span>
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {impact.impacted.slice(0, 14).map((item) => (
              <li
                key={item.artifact_id}
                className="rounded-md border border-border bg-surface-raised px-2 py-0.5 text-[11px] text-content-muted"
              >
                {item.title}
              </li>
            ))}
            {impact.impacted.length > 14 && (
              <li className="px-2 py-0.5 text-[11px] text-content-subtle">
                and {impact.impacted.length - 14} more
              </li>
            )}
          </ul>
        </div>
      )}

      <Field label="What changed?" htmlFor="revision-summary">
        <Input
          id="revision-summary"
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          maxLength={300}
          placeholder="Split billing into its own requirement"
        />
      </Field>

      <Field label="Content" htmlFor="revision-body">
        <Textarea
          id="revision-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={14}
          className="font-mono text-xs leading-relaxed"
        />
      </Field>

      {error && (
        <p role="alert" className="text-xs text-state-blocked">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={submit} disabled={busy}>
          {busy && <Loader2 className="animate-spin" aria-hidden="true" />}
          Save revision
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setOpen(false)}
          disabled={busy}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
