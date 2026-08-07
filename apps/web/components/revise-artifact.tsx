"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, Loader2, Pencil } from "lucide-react";

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
      <button
        type="button"
        onClick={begin}
        className="inline-flex items-center gap-2 rounded-md border border-border-strong px-3 py-1.5 text-xs text-content-muted transition-colors hover:bg-surface-raised"
      >
        <Pencil className="size-3.5" aria-hidden="true" />
        Revise
      </button>
    );
  }

  return (
    <div className="space-y-3 rounded-[--radius-card] border border-border bg-surface p-4">
      <div className="space-y-1">
        <p className="text-sm text-content">Revise this artifact</p>
        <p className="text-xs text-content-muted">
          This appends a new version. Everything derived from the current version
          will be flagged as out of date, and the organization will offer to
          rebuild it.
        </p>
      </div>

      {impact && impact.impacted.length > 0 && (
        <div className="space-y-2 rounded-md border border-state-stale/30 bg-state-stale/5 p-3">
          <p className="flex items-center gap-2 text-xs text-state-stale">
            <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <strong>{impact.impacted.length} artifacts</strong> depend on this and
              would go out of date
              {impact.stages_affected.length > 0 && (
                <> · {impact.stages_affected.length} stages would rerun</>
              )}
            </span>
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {impact.impacted.slice(0, 14).map((item) => (
              <li
                key={item.artifact_id}
                className="rounded border border-border bg-surface-raised px-2 py-0.5 text-[11px] text-content-muted"
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

      <div className="space-y-1.5">
        <label htmlFor="revision-summary" className="block text-xs text-content-subtle">
          What changed?
        </label>
        <input
          id="revision-summary"
          value={summary}
          onChange={(event) => setSummary(event.target.value)}
          maxLength={300}
          placeholder="Split billing into its own requirement"
          className="w-full rounded-md border border-border bg-canvas px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-accent focus:outline-none"
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="revision-body" className="block text-xs text-content-subtle">
          Content
        </label>
        <textarea
          id="revision-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={14}
          className="w-full resize-y rounded-md border border-border bg-canvas px-3 py-2 font-mono text-xs text-content focus:border-accent focus:outline-none"
        />
      </div>

      {error && (
        <p role="alert" className="text-xs text-state-blocked">
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-canvas transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {busy && <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />}
          Save revision
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={busy}
          className="rounded-md border border-border-strong px-3 py-1.5 text-sm text-content-muted transition-colors hover:bg-surface-raised"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
