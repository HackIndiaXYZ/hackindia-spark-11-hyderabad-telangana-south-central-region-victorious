import { Suspense } from "react";

import { SystemStatus } from "@/components/system-status";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

/**
 * Foundation status page.
 *
 * Reports honestly on what exists so far: which layers are built and wired, and
 * what is still ahead. The marketing landing page arrives with Milestone 5;
 * presenting a finished-looking product over an unfinished one would be exactly
 * the kind of shortcut `15_Development_Guidelines.md` rules out.
 */

const MILESTONE_LABELS = {
  complete: "complete",
  active: "in progress",
  idle: "planned",
} as const;

const MILESTONES = [
  { id: "M0", name: "Foundation & architectural skeleton", state: "complete" },
  { id: "M1", name: "Shared organizational memory & traceability", state: "complete" },
  { id: "M2", name: "Provider abstraction & agent framework", state: "complete" },
  { id: "M3", name: "Executive AI & lifecycle orchestration", state: "complete" },
  { id: "M4", name: "The seven engineering agents", state: "idle" },
  { id: "M5", name: "Workspace UI", state: "idle" },
  { id: "M6", name: "Live agent organization view", state: "idle" },
  { id: "M7", name: "Approval center", state: "idle" },
  { id: "M8", name: "Traceability graph & change propagation", state: "idle" },
  { id: "M9", name: "Mutagent ADL evidence", state: "idle" },
  { id: "M10", name: "Demo hardening", state: "idle" },
] as const;

function StatusSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Engineering platform</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-content-muted">Checking platform readiness…</p>
      </CardContent>
    </Card>
  );
}

export default function FoundationPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-8 px-6 py-16">
      <header className="space-y-3">
        <StatusBadge state="active">Milestone 3</StatusBadge>
        <h1 className="text-2xl font-semibold tracking-tight">Project Victorious</h1>
        <p className="text-content-muted">
          An AI-native software engineering workspace. Specialized engineering agents coordinate
          requirements, architecture, implementation, testing, and documentation over a shared
          organizational memory — with full traceability and human approval at every gate.
        </p>
      </header>

      <Suspense fallback={<StatusSkeleton />}>
        <SystemStatus />
      </Suspense>

      <Card>
        <CardHeader>
          <CardTitle>Implementation progress</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="divide-y divide-border border-t border-border">
            {MILESTONES.map((milestone) => (
              <li key={milestone.id} className="flex items-center gap-4 py-2.5">
                <span className="w-8 shrink-0 font-mono text-xs text-content-subtle">
                  {milestone.id}
                </span>
                <span className="flex-1 text-sm text-content-muted">{milestone.name}</span>
                <StatusBadge state={milestone.state}>
                  {MILESTONE_LABELS[milestone.state]}
                </StatusBadge>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </main>
  );
}
