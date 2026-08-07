import { cn } from "@/lib/utils";

/**
 * Engineering progress through the lifecycle.
 *
 * The fill animates its own width, so a stage completing while the page is open
 * reads as movement rather than a jump. The track carries faint stage ticks:
 * progress here is a count of discrete stages, not a continuous percentage, and
 * showing it as a smooth bar alone would misrepresent what is being measured.
 */
export function Progress({
  completed,
  total,
  className,
  showTicks = true,
  tone = "complete",
  label = "Engineering progress",
}: {
  completed: number;
  total: number;
  className?: string;
  showTicks?: boolean;
  tone?: "complete" | "accent";
  label?: string;
}) {
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div
      className={cn(
        "relative h-1.5 w-full overflow-hidden rounded-full bg-surface-overlay",
        "shadow-[0_1px_1px_0_oklch(0_0_0/0.35)_inset]",
        className,
      )}
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`${label}: ${completed} of ${total} stages complete`}
    >
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-700 ease-out",
          tone === "complete"
            ? "bg-gradient-to-r from-state-complete/70 to-state-complete"
            : "bg-gradient-to-r from-accent-strong to-accent",
        )}
        style={{ width: `${percent}%` }}
      />

      {showTicks && total > 1 && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex">
          {Array.from({ length: total - 1 }).map((_, index) => (
            <span
              key={index}
              className="h-full border-r border-canvas/70"
              style={{ width: `${100 / total}%` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
