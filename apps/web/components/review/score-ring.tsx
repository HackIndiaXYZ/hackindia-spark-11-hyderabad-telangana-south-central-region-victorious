import { cn } from "@/lib/utils";

/**
 * A quality score as a ring.
 *
 * One number carries the whole Helix Review view, so it gets a shape rather than
 * a bare figure. Colour follows the same score bands the badges use, and the
 * numeral is always rendered — colour alone must never be the only carrier of
 * meaning (`10_UI_UX_Plan.md`, Accessibility).
 */
export function ScoreRing({
  score,
  size = 96,
  label,
}: {
  score: number;
  size?: number;
  label?: string;
}) {
  const stroke = size >= 80 ? 7 : 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.max(0, Math.min(100, score)) / 100) * circumference;

  const tone =
    score >= 85
      ? "stroke-state-complete"
      : score >= 70
        ? "stroke-state-active"
        : score >= 60
          ? "stroke-state-waiting"
          : "stroke-state-blocked";

  return (
    <div
      className="inline-flex flex-col items-center gap-1"
      role="img"
      aria-label={`${label ? `${label}: ` : ""}quality score ${score} out of 100`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            className="stroke-surface-raised"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            className={cn(tone, "transition-[stroke-dasharray] duration-500")}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono tabular-nums text-content"
            style={{ fontSize: size / 3.4 }}
          >
            {score}
          </span>
          {size >= 80 && (
            <span className="text-[10px] text-content-subtle">/ 100</span>
          )}
        </div>
      </div>
      {label && <span className="text-xs text-content-subtle">{label}</span>}
    </div>
  );
}
