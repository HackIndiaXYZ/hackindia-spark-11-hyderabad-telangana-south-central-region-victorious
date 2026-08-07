"use client";

import { useEffect } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Route-level error boundary.
 *
 * `12_Risk_Analysis.md` requires the platform to fail gracefully. An unhandled
 * render error must produce a recoverable screen, never a blank page.
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
    <main className="mx-auto flex min-h-screen max-w-xl items-center px-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Something went wrong</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-content-muted">
            The workspace hit an unexpected error. Your project data is unaffected — engineering
            artifacts are only written through the API.
          </p>
          {error.digest && (
            <p className="font-mono text-xs text-content-subtle">Reference: {error.digest}</p>
          )}
          <button
            type="button"
            onClick={reset}
            className="rounded-md border border-border-strong bg-surface-raised px-3 py-1.5 text-sm text-content transition-colors hover:bg-border"
          >
            Try again
          </button>
        </CardContent>
      </Card>
    </main>
  );
}
