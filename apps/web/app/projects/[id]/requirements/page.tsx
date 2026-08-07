import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Requirements" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <SectionPage
      projectId={id}
      title={"Requirements"}
      description={"Requirement discovery and business validation: what the product must do, and whether it holds up to scrutiny."}
      stages={["requirement_discovery","business_validation"]}
      empty={"No requirements yet. Advance the engineering workflow to start requirement discovery."}
    />
  );
}
