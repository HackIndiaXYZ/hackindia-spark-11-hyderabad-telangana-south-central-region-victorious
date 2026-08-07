import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Testing" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <SectionPage
      projectId={id}
      title={"Testing"}
      description={"Test plan, test cases traced to acceptance criteria, and coverage measured against requirements."}
      stages={["testing"]}
      empty={"No test artifacts yet. The QA Engineer runs once there is an implementation to verify."}
    />
  );
}
