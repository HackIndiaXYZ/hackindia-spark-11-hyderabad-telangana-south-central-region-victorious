import Link from "next/link";
import { ArrowRight, GitBranch, ShieldCheck, Users } from "lucide-react";

import { SystemStatus } from "@/components/system-status";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

/**
 * Landing page — Step 1 of the demo flow in `13_Demo_and_Pitch.md`.
 *
 * The key message that document asks to land: "This is not another AI coding
 * assistant. It is an AI Software Engineering Organization." Everything on this
 * page argues that, and nothing claims a capability the platform does not have.
 */

export const metadata = {
  title: "AI-native Software Engineering Workspace",
};

const PILLARS = [
  {
    icon: Users,
    title: "A specialist for every role",
    body:
      "A Product Manager, Business Analyst, Software Architect, Full Stack Engineer, " +
      "QA Engineer, and Documentation Engineer, coordinated by an Executive AI that " +
      "assigns work and never performs it.",
  },
  {
    icon: GitBranch,
    title: "Every artifact knows where it came from",
    body:
      "Each requirement, decision, file, and test links back to what produced it. " +
      "Change a requirement and the organization tells you exactly which downstream " +
      "work no longer reflects it — the question no coding assistant answers.",
  },
  {
    icon: ShieldCheck,
    title: "You approve what matters",
    body:
      "Requirements, architecture, and code generation stop at a human gate. The " +
      "workflow genuinely halts: nothing downstream is written until you decide.",
  },
] as const;

export default function LandingPage() {
  return (
    <main id="main" tabIndex={-1} className="mx-auto flex min-h-screen max-w-4xl flex-col gap-12 px-6 py-16">
      <header className="space-y-5">
        <StatusBadge state="active">Project Victorious</StatusBadge>

        <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-content sm:text-4xl">
          An AI-native software engineering workspace
        </h1>

        <p className="max-w-2xl text-base text-content-muted">
          Not another coding assistant. Specialized AI engineering agents coordinate
          requirements, architecture, implementation, testing, and documentation over a
          shared organizational memory — with full traceability and human approval at
          every gate.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-canvas transition-colors hover:bg-accent-hover"
          >
            Open the workspace
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
          <a
            href="https://github.com/saivishal/hackindia-spark-11"
            className="rounded-md border border-border-strong px-4 py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised"
          >
            Read the specification
          </a>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        {PILLARS.map((pillar) => (
          <Card key={pillar.title}>
            <CardHeader>
              <pillar.icon className="size-4 text-accent" aria-hidden="true" />
              <CardTitle className="mt-1">{pillar.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-content-muted">{pillar.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-medium tracking-tight text-content">
          The coordination gap
        </h2>
        <Card>
          <CardContent className="space-y-4 pt-5">
            <p className="text-sm text-content-muted">
              AI has made writing code fast. It has not made <em>coordinating</em> the
              decisions around it fast. Existing tools optimise one stage each, and
              nothing continuously answers:
            </p>
            <ul className="space-y-2 border-l-2 border-accent-muted pl-4 text-sm text-content">
              <li>Is the architecture still consistent with the latest requirements?</li>
              <li>Which downstream components does this requirement change affect?</li>
              <li>Are the dependencies still valid after this change?</li>
            </ul>
            <p className="text-sm text-content-muted">
              Project Victorious occupies that layer. It coordinates the engineering
              lifecycle rather than accelerating one step of it.
            </p>
          </CardContent>
        </Card>
      </section>

      <SystemStatus />

      <footer className="border-t border-border pt-6 text-xs text-content-subtle">
        Built for the Mutagent Challenge · HackIndia Spark 11, Hyderabad
      </footer>
    </main>
  );
}
