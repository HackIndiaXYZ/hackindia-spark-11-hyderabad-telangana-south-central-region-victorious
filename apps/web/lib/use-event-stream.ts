"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Subscribes to a project's live engineering activity.
 *
 * The stream carries signals; the REST API carries state. On a relevant event
 * this hook calls `onActivity`, and the caller re-reads whatever endpoint it
 * renders. That keeps exactly one projection of agent and artifact state — the
 * API's — instead of a second one assembled here that can drift from it.
 *
 * `EventSource` reconnects on its own and replays `Last-Event-ID`, so a dropped
 * connection recovers without losing events. Nothing here needs to retry.
 */

export type StreamStatus = "connecting" | "live" | "reconnecting";

export interface StreamEvent {
  id: string;
  type: string;
  stage: string | null;
  role: string | null;
  role_title?: string | null;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
}

/** Event types that change what the workspace shows. */
const MEANINGFUL = new Set([
  "stage_started",
  "stage_completed",
  "stage_blocked",
  "agent_started",
  "agent_progress",
  "agent_completed",
  "agent_failed",
  "artifact_created",
  "artifact_revised",
  "artifact_reviewed",
  "artifact_approved",
  "artifact_marked_stale",
  "approval_requested",
  "approval_granted",
  "approval_rejected",
  "conflict_detected",
]);

/** Most recent events kept for display. Enough to fill an activity panel. */
const BUFFER = 60;

/**
 * A burst of events arrives whenever an agent finishes — a completion, several
 * artifact creations, then the next stage starting. Refetching per event would
 * issue a request each; this collapses the burst into one.
 */
const REFETCH_DEBOUNCE_MS = 300;

export function useEventStream(
  projectId: string,
  onActivity?: () => void,
): { status: StreamStatus; events: StreamEvent[]; lastEvent: StreamEvent | null } {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [events, setEvents] = useState<StreamEvent[]>([]);

  // Held in a ref so a changing callback identity never tears down the stream.
  const activityRef = useRef(onActivity);
  activityRef.current = onActivity;

  useEffect(() => {
    // Same-origin by default, through the rewrite proxy in `next.config.ts`.
    // `EventSource` cannot send credentials or custom headers, so it is entirely
    // at the mercy of the API's CORS allowlist when it goes cross-origin — which
    // is why the stream is the first thing to break when the workspace is opened
    // on a host other than the one origin that allowlist names.
    const base = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
    const source = new EventSource(`${base}/api/v1/projects/${projectId}/events/stream`);

    let debounce: ReturnType<typeof setTimeout> | undefined;

    const scheduleRefetch = () => {
      if (debounce) clearTimeout(debounce);
      debounce = setTimeout(() => activityRef.current?.(), REFETCH_DEBOUNCE_MS);
    };

    source.addEventListener("stream_open", () => setStatus("live"));

    source.onopen = () => setStatus("live");

    source.onerror = () => {
      // EventSource retries by itself; this only reflects that in the UI.
      setStatus((current) => (current === "live" ? "reconnecting" : "connecting"));
    };

    source.onmessage = (message) => handle(message);

    for (const type of MEANINGFUL) {
      source.addEventListener(type, (message) => handle(message as MessageEvent));
    }

    function handle(message: MessageEvent<string>) {
      let event: StreamEvent;
      try {
        event = JSON.parse(message.data) as StreamEvent;
      } catch {
        return;
      }

      setStatus("live");
      setEvents((current) => [event, ...current].slice(0, BUFFER));

      if (MEANINGFUL.has(event.type)) scheduleRefetch();
    }

    return () => {
      if (debounce) clearTimeout(debounce);
      source.close();
    };
  }, [projectId]);

  return { status, events, lastEvent: events[0] ?? null };
}
