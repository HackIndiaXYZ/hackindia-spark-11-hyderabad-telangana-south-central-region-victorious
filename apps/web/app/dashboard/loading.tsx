import { Skeleton, SkeletonCard, SkeletonRegion } from "@/components/ui/skeleton";

/**
 * Dashboard loading state.
 *
 * Mirrors the real layout — three stat tiles, then a project list — so the page
 * does not reflow when data lands. The alternative, a centred spinner, tells the
 * user nothing about what is coming and guarantees a jump when it does.
 */
export default function DashboardLoading() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-12">
      <SkeletonRegion label="Loading the engineering dashboard" className="space-y-2">
        <Skeleton className="h-2.5 w-20" />
        <Skeleton className="h-5 w-64" />
        <Skeleton className="h-3.5 w-96 max-w-full" />
      </SkeletonRegion>

      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div
            key={index}
            className="rounded-[--radius-card] border border-border bg-surface panel-sheen p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 space-y-2.5">
                <Skeleton className="h-6 w-14" />
                <Skeleton className="h-2.5 w-24" />
              </div>
              <Skeleton className="size-8 rounded-lg" />
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        <Skeleton className="h-2.5 w-24" />
        {Array.from({ length: 3 }).map((_, index) => (
          <SkeletonCard key={index} lines={2} />
        ))}
      </div>
    </main>
  );
}
