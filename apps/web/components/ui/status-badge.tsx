import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Engineering state indicator.
 *
 * The single component responsible for rendering *any* state in the workspace:
 * agent status in the Organization view, stage status on the Engineering
 * Timeline, artifact freshness in the Knowledge Base.
 *
 * Routing every state through one component is what guarantees "waiting" looks
 * identical everywhere — a consistency the platform claims about engineering
 * decisions and should therefore demonstrate in its own interface.
 *
 * The dot carries a text label rather than colour alone, so state survives
 * greyscale and colour-vision deficiency (`10_UI_UX_Plan.md`, Accessibility).
 */
const statusBadge = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      state: {
        complete: "border-state-complete/30 bg-state-complete/10 text-state-complete",
        active: "border-state-active/30 bg-state-active/10 text-state-active",
        waiting: "border-state-waiting/30 bg-state-waiting/10 text-state-waiting",
        approval: "border-state-approval/30 bg-state-approval/10 text-state-approval",
        blocked: "border-state-blocked/30 bg-state-blocked/10 text-state-blocked",
        stale: "border-state-stale/30 bg-state-stale/10 text-state-stale",
        idle: "border-border bg-surface-raised text-content-subtle",
      },
    },
    defaultVariants: { state: "idle" },
  },
);

const dot = cva("size-1.5 rounded-full", {
  variants: {
    state: {
      complete: "bg-state-complete",
      active: "bg-state-active",
      waiting: "bg-state-waiting",
      approval: "bg-state-approval",
      blocked: "bg-state-blocked",
      stale: "bg-state-stale",
      idle: "bg-state-idle",
    },
  },
  defaultVariants: { state: "idle" },
});

export interface StatusBadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadge> {
  /** Whether to pulse the indicator. Reserved for genuinely in-progress work. */
  pulse?: boolean;
}

export function StatusBadge({
  className,
  state,
  pulse = false,
  children,
  ...props
}: StatusBadgeProps) {
  return (
    <span className={cn(statusBadge({ state }), className)} {...props}>
      <span className={cn(dot({ state }), pulse && "animate-pulse")} aria-hidden="true" />
      {children}
    </span>
  );
}
