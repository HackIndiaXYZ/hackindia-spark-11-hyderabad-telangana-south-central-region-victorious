import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The state a view is in before it has anything to show.
 *
 * Treated as a designed screen rather than a fallback sentence. Each one says
 * three things: what would be here, why it is not here yet, and what the user
 * can do about it. `10_UI_UX_Plan.md` requires users to always understand what
 * is happening and what comes next — an empty view is exactly where that is
 * easiest to get wrong.
 *
 * The icon sits in a dashed, faintly-lit well: it reads as a reserved space
 * awaiting content, not as an error.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-[--radius-card] border border-dashed border-border",
        "bg-surface/40 px-6 py-12 text-center",
        className,
      )}
    >
      <div
        aria-hidden="true"
        className={cn(
          "mb-4 grid size-11 place-items-center rounded-xl",
          "border border-border bg-surface-raised panel-sheen",
          "shadow-[0_0_28px_-10px_var(--color-accent-glow)]",
        )}
      >
        <Icon className="size-5 text-content-subtle" />
      </div>

      <p className="text-sm font-medium text-content">{title}</p>
      <p className="mt-1.5 max-w-md text-sm leading-relaxed text-content-muted">
        {description}
      </p>

      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
