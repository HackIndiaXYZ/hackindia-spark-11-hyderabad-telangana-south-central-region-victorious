import { cn } from "@/lib/utils";

/**
 * A quality score as a ring.
 *
 * One number carries the whole Helix Review view, so it gets a shape rather than
 * a bare figure — an arc is readable at a glance from across a room, which a
 * two-digit number is not.
 *
 * Three details make it read as *measured* rather than styled:
 *
 * - The arc draws itself in from zero, so the score arrives the way a
 *   measurement does. `prefers-reduced-motion` renders it at its final value.
 * - A faint tick marks the 85 threshold where a review counts as strong, so a
 *   score is legible against the bar it is judged by, not just in isolation.
 * - Colour follows the same score bands the badges use, and the numeral is
 *   always rendered — colour alone must never be the only carrier of meaning
 *   (`10_UI_UX_Plan.md`, Accessibility).
 */

const STRONG_THRESHOLD = 85;

export function ScoreRing({
  score,
  size = 96,
  label,
  showThreshold = true,
}: {
  score: number;
  size?: number;
  label?: string;
  showThreshold?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  const stroke = size >= 80 ? 6 : size >= 60 ? 5 : 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (clamped / 100) * circumference;

  const tone =
    clamped >= 85
      ? "stroke-state-complete"
      : clamped >= 70
        ? "stroke-state-active"
        : clamped >= 60
          ? "stroke-state-waiting"
          : "stroke-state-blocked";

  const glow =
    clamped >= 85
      ? "var(--color-state-complete)"
      : clamped >= 70
        ? "var(--color-state-active)"
        : clamped >= 60
          ? "var(--color-state-waiting)"
          : "var(--color-state-blocked)";

  // The 85 tick, positioned on the same -90° rotated axis as the arc.
  const thresholdAngle = (STRONG_THRESHOLD / 100) * 2 * Math.PI - Math.PI / 2;
  const centre = size / 2;

  return (
    <div
      className="inline-flex flex-col items-center gap-1.5"
      role="img"
      aria-label={`${label ? `${label}: ` : ""}quality score ${score} out of 100`}
    >
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90 overflow-visible">
          <circle
            cx={centre}
            cy={centre}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            className="stroke-surface-overlay"
          />

          <circle
            cx={centre}
            cy={centre}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            className={cn(tone, "animate-[draw_0.9s_var(--ease-out-quint)_both]")}
            style={
              {
                // Consumed by the `draw` keyframe: start fully offset (empty
                // ring) and settle at the real value.
                "--draw-from": `${circumference}px`,
                filter: `drop-shadow(0 0 ${stroke * 1.4}px ${glow})`,
                opacity: 0.98,
              } as React.CSSProperties
            }
          />

          {showThreshold && size >= 60 && (
            <line
              x1={centre + Math.cos(thresholdAngle) * (radius - stroke / 2 - 1)}
              y1={centre + Math.sin(thresholdAngle) * (radius - stroke / 2 - 1)}
              x2={centre + Math.cos(thresholdAngle) * (radius + stroke / 2 + 1)}
              y2={centre + Math.sin(thresholdAngle) * (radius + stroke / 2 + 1)}
              className="stroke-content-subtle/50"
              strokeWidth={1}
            >
              <title>85 — the threshold for a strong review</title>
            </line>
          )}
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono leading-none tracking-tight text-content tabular-nums"
            style={{ fontSize: size / 3.2 }}
          >
            {score}
          </span>
          {size >= 80 && (
            <span className="mt-1 text-[10px] text-content-subtle">out of 100</span>
          )}
        </div>
      </div>

      {label && <span className="text-xs text-content-subtle">{label}</span>}
    </div>
  );
}
