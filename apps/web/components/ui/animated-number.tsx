"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * A number that counts up to its value.
 *
 * Used for figures a user is meant to *read as a measurement* — artifacts
 * produced, quality scores, stage counts. The count draws the eye to a value
 * that changed, which matters on a dashboard that updates live from the event
 * stream without a page reload.
 *
 * Three things keep it honest rather than decorative:
 *
 * - It animates only on mount and on a genuine change of value, so a re-render
 *   never replays it.
 * - `prefers-reduced-motion` renders the final value immediately.
 * - The accessible name is always the final value, so assistive technology never
 *   reads out an intermediate number.
 */
export function AnimatedNumber({
  value,
  duration = 800,
  className,
  format = (input: number) => input.toLocaleString(),
}: {
  value: number;
  duration?: number;
  className?: string;
  format?: (value: number) => string;
}) {
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const from = fromRef.current;
    fromRef.current = value;

    if (reduced || from === value) {
      setDisplay(value);
      return;
    }

    const start = performance.now();

    function step(now: number) {
      const elapsed = Math.min(1, (now - start) / duration);
      // Ease-out quint: most of the distance is covered early, so the number
      // feels like it is settling rather than crawling.
      const eased = 1 - Math.pow(1 - elapsed, 5);
      setDisplay(Math.round(from + (value - from) * eased));

      if (elapsed < 1) frameRef.current = requestAnimationFrame(step);
    }

    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current !== undefined) cancelAnimationFrame(frameRef.current);
    };
  }, [value, duration]);

  return (
    <span className={cn("tabular-nums", className)}>
      {/* The animating figure is decorative; the real value is announced once. */}
      <span aria-hidden="true">{format(display)}</span>
      <span className="sr-only">{format(value)}</span>
    </span>
  );
}
