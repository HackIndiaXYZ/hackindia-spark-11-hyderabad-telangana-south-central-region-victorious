"use client";

import { cn } from "@/lib/utils";
import type { StreamStatus } from "@/lib/use-event-stream";

/**
 * Connection state of the live activity stream.
 *
 * Shown because a user watching a static screen cannot otherwise tell whether
 * nothing is happening or the connection dropped. `10_UI_UX_Plan.md` requires
 * users to always understand what is happening — including when the answer is
 * "the workspace lost contact with the API".
 */

const LABELS: Record<StreamStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
};

const DOT: Record<StreamStatus, string> = {
  connecting: "bg-state-waiting",
  live: "bg-state-active",
  reconnecting: "bg-state-blocked",
};

export function StreamIndicator({
  status,
  busy = false,
}: {
  status: StreamStatus;
  busy?: boolean;
}) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-raised px-2.5 py-1 text-xs text-content-muted"
      role="status"
      aria-live="polite"
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          DOT[status],
          status !== "live" && "animate-pulse",
        )}
        aria-hidden="true"
      />
      {LABELS[status]}
      {busy && <span className="text-content-subtle">· updating</span>}
    </span>
  );
}
