import { Skeleton, SkeletonRegion, SkeletonRow } from "@/components/ui/skeleton";

/**
 * Workspace section loading state.
 *
 * Shared by every project section, because they share a shape: a heading block
 * and then a list or grid. Reserving that space keeps the sticky header and the
 * navigation stable while a section loads — the frame never moves, only the
 * content inside it.
 */
export default function ProjectSectionLoading() {
  return (
    <SkeletonRegion label="Loading this section" className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-2.5 w-16" />
        <Skeleton className="h-4.5 w-52" />
        <Skeleton className="h-3.5 w-full max-w-2xl" />
      </div>

      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <SkeletonRow key={index} />
        ))}
      </div>
    </SkeletonRegion>
  );
}
