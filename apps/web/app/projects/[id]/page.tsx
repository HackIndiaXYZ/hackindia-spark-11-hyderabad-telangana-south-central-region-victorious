import { LiveTimeline } from "@/components/timeline/live-timeline";
import { api } from "@/lib/api";

/**
 * Project overview: the Engineering Timeline and live activity.
 *
 * Server-rendered for a complete first paint, then live from the event stream.
 */

export const dynamic = "force-dynamic";

export default async function OverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const project = await api.getProject(id);

  return <LiveTimeline projectId={id} initialProject={project} />;
}
