import { LiveOrganization } from "@/components/agents/live-organization";
import { api } from "@/lib/api";

/**
 * The AI Engineering Organization view.
 *
 * `10_UI_UX_Plan.md` calls this "one of the primary features of the product".
 * The server renders the current state so the first paint is complete, and the
 * client subscribes to the live stream from there.
 *
 * The Executive AI is deliberately absent: it coordinates and performs no
 * engineering work (ADR-0009), so it owns no card here.
 */

export const metadata = { title: "Organization" };
export const dynamic = "force-dynamic";

export default async function OrganizationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const agents = await api.getOrganization(id);

  return <LiveOrganization projectId={id} initialAgents={agents} />;
}
