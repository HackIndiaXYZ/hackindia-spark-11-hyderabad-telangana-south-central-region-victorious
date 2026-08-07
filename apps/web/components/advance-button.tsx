"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2, Play } from "lucide-react";

import { api } from "@/lib/api";
import { ApiError, ApiUnreachableError } from "@/lib/api-client";

/**
 * Asks the organization to make progress.
 *
 * One traversal runs until a human is needed — an approval gate, a blocking
 * conflict, or completion. The button reports what actually happened rather than
 * simply refreshing: `10_UI_UX_Plan.md` requires users to always understand what
 * is happening and what comes next.
 */
export function AdvanceButton({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function advance() {
    setRunning(true);
    setOutcome(null);
    setFailed(false);

    try {
      const result = await api.advance(projectId);

      const ran =
        result.executed_stages.length > 0
          ? `Completed ${result.executed_stages.length} stage${
              result.executed_stages.length === 1 ? "" : "s"
            }. `
          : "";

      setOutcome(`${ran}${result.halt_reason || "Lifecycle complete."}`);
      setFailed(result.halt_action === "halt_blocked");
      router.refresh();
    } catch (cause) {
      setFailed(true);
      setOutcome(
        cause instanceof ApiUnreachableError
          ? "Could not reach the API."
          : cause instanceof ApiError
            ? cause.message
            : "The run failed unexpectedly.",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={advance}
        disabled={running}
        className="inline-flex items-center gap-2 rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-canvas transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {running ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <Play className="size-4" aria-hidden="true" />
        )}
        {running ? "Organization working…" : "Advance engineering"}
      </button>

      {outcome && (
        <p
          role="status"
          className={
            failed ? "text-xs text-state-blocked" : "text-xs text-content-muted"
          }
        >
          {outcome}
        </p>
      )}
    </div>
  );
}
