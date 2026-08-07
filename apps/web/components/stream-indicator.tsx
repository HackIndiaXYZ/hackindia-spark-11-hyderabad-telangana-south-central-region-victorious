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
 *
 * The dot pings only while *not* live: a healthy connection should be quiet, and
 * animating it constantly would train the eye to ignore the one state that
 * needs attention.
 */

const LABELS: Record<StreamStatus, string> = {
  connecting: "Connecting",
  live: "Live",
  reconnecting: "Reconnecting",
};

const TONE: Record<StreamStatus, { dot: string; text: string; ring: string }> = {
  connecting: {
    dot: "bg-state-waiting",
    text: "text-state-waiting",
    ring: "border-state-waiting/30 bg-state-waiting/[0.08]",
  },
  live: {
    dot: "bg-state-active",
    text: "text-content-muted",
    ring: "border-border bg-surface-raised",
  },
  reconnecting: {
    dot: "bg-state-blocked",
    text: "text-state-blocked",
    ring: "border-state-blocked/30 bg-state-blocked/[0.08]",
  },
};

export function StreamIndicator({
  status,
  busy = false,
}: {
  status: StreamStatus;
  busy?: boolean;
}) {
  const tone = TONE[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap",
        "transition-colors duration-200",
        tone.ring,
        tone.text,
      )}
      role="status"
      aria-live="polite"
    >
      <span className="relative size-1.5 shrink-0" aria-hidden="true">
        <span className={cn("absolute inset-0 rounded-full", tone.dot)} />
        {status !== "live" && (
          <span
            className={cn("absolute inset-0 animate-ping rounded-full opacity-75", tone.dot)}
          />
        )}
      </span>

      {LABELS[status]}

      {busy && (
        <span className="text-content-subtle" aria-hidden="true">
          · updating
        </span>
      )}
    </span>
  );
}
