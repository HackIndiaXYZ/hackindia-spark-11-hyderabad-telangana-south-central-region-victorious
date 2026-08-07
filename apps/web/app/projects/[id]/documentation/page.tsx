import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Documentation" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <SectionPage
      projectId={id}
      title={"Documentation"}
      description={"README, API reference, architecture narrative, developer guide, and the deployment plan."}
      stages={["documentation","deployment_preparation"]}
      empty={"No documentation yet. It is generated from what the organization actually built."}
    />
  );
}
