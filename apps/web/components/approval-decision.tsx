"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, Loader2, MessageSquare } from "lucide-react";

import { api } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * The decision controls of the Approval Center.
 *
 * Requesting changes requires feedback, enforced here as well as by the API: the
 * feedback is fed into the agent's context on re-run, so a rejection without a
 * reason leaves the organization to guess what to do differently.
 */
export function ApprovalDecision({ approvalId }: { approvalId: string }) {
  const router = useRouter();
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "approved" | "changes_requested") {
    if (decision === "changes_requested" && feedback.trim().length === 0) {
      setShowFeedback(true);
      setError("Say what needs to change — the agent uses this on its next attempt.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await api.decideApproval(approvalId, decision, feedback.trim() || undefined);
      router.refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "The decision failed.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 border-t border-border pt-4">
      {showFeedback && (
        <div className="space-y-1.5">
          <label htmlFor={`feedback-${approvalId}`} className="block text-xs text-content-subtle">
            What needs to change?
          </label>
          <textarea
            id={`feedback-${approvalId}`}
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            rows={3}
            placeholder="Billing scope is unclear — split it into its own requirement."
            className="w-full resize-y rounded-md border border-border bg-canvas px-3 py-2 text-sm text-content placeholder:text-content-subtle focus:border-accent focus:outline-none"
          />
        </div>
      )}

      {error && (
        <p role="alert" className="text-xs text-state-blocked">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => decide("approved")}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-state-complete/15 px-3 py-1.5 text-sm text-state-complete transition-colors hover:bg-state-complete/25 disabled:opacity-40"
        >
          {busy ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Check className="size-3.5" aria-hidden="true" />
          )}
          Approve
        </button>

        <button
          type="button"
          onClick={() =>
            showFeedback ? decide("changes_requested") : setShowFeedback(true)
          }
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md border border-border-strong px-3 py-1.5 text-sm text-content-muted transition-colors hover:bg-surface-raised disabled:opacity-40"
        >
          <MessageSquare className="size-3.5" aria-hidden="true" />
          Request changes
        </button>
      </div>
    </div>
  );
}
