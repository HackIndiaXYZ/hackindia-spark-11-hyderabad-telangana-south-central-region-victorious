import { SectionPage } from "@/components/section-page";

export const metadata = { title: "Development" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <SectionPage
      projectId={id}
      title={"Development"}
      description={"The generated repository scaffold. An inspectable structure traced to the design, not a running application."}
      stages={["implementation"]}
      empty={"Nothing generated yet. The architecture must be approved and code generation authorised first."}
    />
  );
}
