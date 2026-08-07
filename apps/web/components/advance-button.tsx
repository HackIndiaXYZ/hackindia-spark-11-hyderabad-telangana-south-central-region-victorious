"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { CircleAlert, Loader2, Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { ApiError, ApiUnreachableError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/**
 * Asks the organization to make progress.
 *
 * One traversal runs until a human is needed — an approval gate, a blocking
 * conflict, or completion. The button reports what actually happened rather than
 * simply refreshing: `10_UI_UX_Plan.md` requires users to always understand what
 * is happening and what comes next.
 *
 * While running, the button keeps its width and grows a travelling light along
 * its base. A control that resizes mid-action shifts the header around it, and
 * this one lives in a sticky header where that would be especially jarring.
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
    <div className="flex min-w-0 flex-col items-end gap-1.5">
      <Button
        type="button"
        onClick={advance}
        disabled={running}
        size="md"
        className="relative min-w-[13.5rem] overflow-hidden disabled:opacity-100"
        aria-live="off"
      >
        {running ? (
          <Loader2 className="animate-spin" aria-hidden="true" />
        ) : (
          <Play aria-hidden="true" />
        )}
        {running ? "Organization working…" : "Advance engineering"}

        {running && (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 overflow-hidden"
          >
            <span className="block h-full w-1/3 animate-[sweep_1.4s_var(--ease-out-quint)_infinite] bg-canvas/50" />
          </span>
        )}
      </Button>

      {outcome && (
        <p
          role="status"
          className={cn(
            "flex max-w-xs animate-[fade-in_0.25s_ease-out_both] items-start gap-1.5 text-right text-xs leading-relaxed",
            failed ? "text-state-blocked" : "text-content-muted",
          )}
        >
          {failed && (
            <CircleAlert className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
          )}
          {outcome}
        </p>
      )}
    </div>
  );
}
