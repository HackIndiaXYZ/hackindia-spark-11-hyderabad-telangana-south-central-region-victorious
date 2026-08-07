import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";

import { buttonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * The 404 screen.
 *
 * Reached most often through `notFound()` in the project layout — a project id
 * that does not exist, usually a stale link or a database reset between demo
 * runs. The copy says that plainly, because "page not found" would leave a user
 * wondering whether the workspace itself was broken.
 */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg items-center px-6">
      <Card className="w-full animate-[rise_0.4s_var(--ease-out-quint)_both]">
        <CardContent className="space-y-5 pt-6">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-xl border border-border bg-surface-raised"
          >
            <FileQuestion className="size-5 text-content-subtle" />
          </span>

          <div className="space-y-1.5">
            <h1 className="text-base font-semibold tracking-tight text-content">
              Not found
            </h1>
            <p className="text-sm leading-relaxed text-content-muted">
              This page does not exist. If you followed a link to a project, it may have
              been created against a database that has since been reset.
            </p>
          </div>

          <Link href="/dashboard" className={buttonClass({ variant: "secondary" })}>
            <ArrowLeft aria-hidden="true" />
            Back to the dashboard
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
