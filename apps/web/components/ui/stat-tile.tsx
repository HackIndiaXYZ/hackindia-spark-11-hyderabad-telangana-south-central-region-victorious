import type { LucideIcon } from "lucide-react";

import { AnimatedNumber } from "@/components/ui/animated-number";
import { cn } from "@/lib/utils";

/**
 * A single headline figure.
 *
 * The number leads and the label follows, because a user scanning a row of tiles
 * is looking for the value, not for its name. Figures count up on arrival so a
 * dashboard that updates live from the event stream shows *which* number moved.
 *
 * `emphasis` is reserved for a figure that means someone has to act — approvals
 * waiting, artifacts needing revision. It tints the icon and lights the icon
 * well rather than recolouring the number, so the row still scans as one set.
 */
export function StatTile({
  label,
  value,
  icon: Icon,
  hint,
  emphasis = false,
  suffix,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  hint?: string;
  emphasis?: boolean;
  suffix?: string;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-[--radius-card] border bg-surface panel-sheen p-4 elevated",
        "transition-[border-color,box-shadow] duration-200",
        emphasis
          ? "border-state-approval/35 hover:border-state-approval/55"
          : "border-border hover:border-border-strong",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-2xl leading-none tracking-tight text-content">
            <AnimatedNumber value={value} />
            {suffix && <span className="text-content-subtle">{suffix}</span>}
          </p>
          <p className="mt-2 truncate text-xs text-content-muted">{label}</p>
          {hint && <p className="mt-0.5 truncate text-[11px] text-content-subtle">{hint}</p>}
        </div>

        <span
          aria-hidden="true"
          className={cn(
            "grid size-8 shrink-0 place-items-center rounded-lg border transition-colors",
            emphasis
              ? "border-state-approval/30 bg-state-approval/10 text-state-approval"
              : "border-border bg-surface-raised text-content-subtle group-hover:text-content-muted",
          )}
        >
          <Icon className="size-4" />
        </span>
      </div>

      {/* A faint floor-glow on the tile that needs attention. */}
      {emphasis && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-state-approval/60 to-transparent"
        />
      )}
    </div>
  );
}
