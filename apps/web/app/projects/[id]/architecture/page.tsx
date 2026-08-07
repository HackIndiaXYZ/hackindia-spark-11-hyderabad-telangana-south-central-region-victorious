import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Architecture" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <SectionPage
      projectId={id}
      title={"Architecture"}
      description={"System design, technology decisions, the API contract, and the data model."}
      stages={["architecture","development_planning"]}
      empty={"No architecture yet. Requirements must be approved before the architect designs from them."}
    />
  );
}
