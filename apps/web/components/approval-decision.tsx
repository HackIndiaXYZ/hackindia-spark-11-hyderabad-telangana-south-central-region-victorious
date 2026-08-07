"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, CircleAlert, Loader2, MessageSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

/**
 * The decision controls of the Approval Center.
 *
 * Requesting changes requires feedback, enforced here as well as by the API: the
 * feedback is fed into the agent's context on re-run, so a rejection without a
 * reason leaves the organization to guess what to do differently.
 *
 * The two actions are deliberately unequal in weight. Approving is the common
 * path and gets the solid control; requesting changes is a considered act and
 * opens a field first, so it cannot happen on a stray click.
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
        <div className="animate-[rise_0.3s_var(--ease-out-quint)_both]">
          <Field
            label="What needs to change?"
            htmlFor={`feedback-${approvalId}`}
            hint="This goes into the agent's context on its next attempt."
          >
            <Textarea
              id={`feedback-${approvalId}`}
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              rows={3}
              autoFocus
              placeholder="Billing scope is unclear — split it into its own requirement."
            />
          </Field>
        </div>
      )}

      {error && (
        <p
          role="alert"
          className="flex animate-[fade-in_0.25s_ease-out_both] items-center gap-2 text-xs text-state-blocked"
        >
          <CircleAlert className="size-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="approve"
          size="sm"
          onClick={() => decide("approved")}
          disabled={busy}
        >
          {busy ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : (
            <Check aria-hidden="true" />
          )}
          Approve
        </Button>

        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() =>
            showFeedback ? decide("changes_requested") : setShowFeedback(true)
          }
          disabled={busy}
        >
          <MessageSquare aria-hidden="true" />
          Request changes
        </Button>
      </div>
    </div>
  );
}
