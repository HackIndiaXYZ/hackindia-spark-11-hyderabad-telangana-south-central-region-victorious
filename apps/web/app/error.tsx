"use client";

import { useEffect } from "react";
import { RotateCw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Route-level error boundary.
 *
 * `12_Risk_Analysis.md` requires the platform to fail gracefully. An unhandled
 * render error must produce a recoverable screen, never a blank page.
 *
 * The copy leads with what is *safe* rather than what broke. A user who hits
 * this mid-demo needs to know their project survived before they need to know
 * the cause — and it did, because artifacts are only ever written through the
 * API.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled workspace error", error);
  }, [error]);

  return (
    <main className="mx-auto flex min-h-screen max-w-lg items-center px-6">
      <Card className="w-full animate-[rise_0.4s_var(--ease-out-quint)_both]">
        <CardContent className="space-y-5 pt-6">
          <span
            aria-hidden="true"
            className="grid size-10 place-items-center rounded-xl border border-state-blocked/30 bg-state-blocked/10"
          >
            <TriangleAlert className="size-5 text-state-blocked" />
          </span>

          <div className="space-y-1.5">
            <h1 className="text-base font-semibold tracking-tight text-content">
              Something went wrong
            </h1>
            <p className="text-sm leading-relaxed text-content-muted">
              The workspace hit an unexpected error. Your project data is unaffected —
              engineering artifacts are only written through the API.
            </p>
          </div>

          {error.digest && (
            <p className="rounded-md bg-canvas-deep px-2.5 py-1.5 font-mono text-xs break-all text-content-subtle">
              Reference: {error.digest}
            </p>
          )}

          <Button type="button" variant="secondary" onClick={reset}>
            <RotateCw aria-hidden="true" />
            Try again
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
