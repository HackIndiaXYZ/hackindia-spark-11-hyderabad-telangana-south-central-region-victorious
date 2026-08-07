import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Loading placeholder.
 *
 * Skeletons here mirror the *shape* of what is arriving — a row of cards, a list
 * of artifacts — rather than showing a generic spinner. A spinner tells a user
 * to wait; a skeleton tells them what they are waiting for, and the page does
 * not jump when the content lands because the space was already reserved.
 *
 * They are announced as busy regions so a screen-reader user learns the same
 * thing a sighted one does.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("skeleton", className)} aria-hidden="true" {...props} />;
}

/** Wraps a set of skeletons and announces the wait once, not per placeholder. */
export function SkeletonRegion({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className}>
      {children}
      <span className="sr-only">{label}</span>
    </div>
  );
}

/** A card-shaped placeholder, matching the real card's padding and radius. */
export function SkeletonCard({ lines = 2, className }: { lines?: number; className?: string }) {
  return (
    <div
      className={cn(
        "rounded-[--radius-card] border border-border bg-surface panel-sheen p-5",
        className,
      )}
    >
      <Skeleton className="h-4 w-2/5" />
      <div className="mt-3 space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton
            key={index}
            className="h-3"
            // The last line runs short, the way real wrapped text does.
            style={{ width: index === lines - 1 ? "55%" : "90%" }}
          />
        ))}
      </div>
    </div>
  );
}

/** A list-row placeholder, matching `ArtifactList`'s row height. */
export function SkeletonRow({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-[--radius-card] border border-border bg-surface panel-sheen px-4 py-3.5",
        className,
      )}
    >
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-1/3" />
        <Skeleton className="h-2.5 w-1/5" />
      </div>
      <Skeleton className="h-5 w-20 rounded-full" />
    </div>
  );
}
