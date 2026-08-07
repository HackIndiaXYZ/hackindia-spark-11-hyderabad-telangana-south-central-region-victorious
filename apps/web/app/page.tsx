import Link from "next/link";
import { ArrowRight, GitBranch, ShieldCheck, Sparkles, Users } from "lucide-react";

import { SystemStatus } from "@/components/system-status";
import { buttonClass } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * Landing page — Step 1 of the demo flow in `13_Demo_and_Pitch.md`.
 *
 * The key message that document asks to land: "This is not another AI coding
 * assistant. It is an AI Software Engineering Organization." Everything on this
 * page argues that, and nothing claims a capability the platform does not have.
 *
 * The hero is deliberately quiet — one gradient wash, one accent action. A
 * product that claims to bring order to engineering should not open with noise.
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

const UNANSWERED = [
  "Is the architecture still consistent with the latest requirements?",
  "Which downstream components does this requirement change affect?",
  "Are the dependencies still valid after this change?",
] as const;

export default function LandingPage() {
  return (
    <main
      id="main"
      tabIndex={-1}
      className="mx-auto flex min-h-screen max-w-5xl flex-col gap-16 px-6 py-20 sm:py-24"
    >
      <header className="animate-[rise_0.5s_var(--ease-out-quint)_both] space-y-6">
        <span className="inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/[0.07] px-3 py-1 text-xs font-medium text-accent">
          <Sparkles className="size-3" aria-hidden="true" />
          Project Victorious
        </span>

        <h1 className="text-gradient max-w-3xl text-4xl leading-[1.08] font-semibold tracking-[-0.02em] text-balance sm:text-5xl">
          An AI-native software engineering workspace
        </h1>

        <p className="max-w-2xl text-base leading-relaxed text-content-muted sm:text-lg">
          Not another coding assistant. Specialized AI engineering agents coordinate
          requirements, architecture, implementation, testing, and documentation over a
          shared organizational memory — with full traceability and human approval at
          every gate.
        </p>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Link href="/dashboard" className={cn(buttonClass({ size: "lg" }), "group")}>
            Open the workspace
            <ArrowRight
              className="transition-transform duration-200 group-hover:translate-x-0.5"
              aria-hidden="true"
            />
          </Link>
          <a
            href="https://github.com/saivishal/hackindia-spark-11"
            className={buttonClass({ variant: "secondary", size: "lg" })}
          >
            Read the specification
          </a>
        </div>
      </header>

      <section
        aria-label="What the platform does"
        className="grid gap-4 sm:grid-cols-3"
      >
        {PILLARS.map((pillar, index) => (
          <Card
            key={pillar.title}
            className="animate-[rise_0.5s_var(--ease-out-quint)_both] group"
            style={{ animationDelay: `${80 + index * 70}ms` }}
          >
            <CardContent className="space-y-3 pt-5">
              <span
                aria-hidden="true"
                className="grid size-9 place-items-center rounded-lg border border-border bg-surface-raised text-accent transition-colors duration-200 group-hover:border-accent/40"
              >
                <pillar.icon className="size-4" />
              </span>
              <h2 className="text-sm font-medium tracking-tight text-content">
                {pillar.title}
              </h2>
              <p className="text-sm leading-relaxed text-content-muted">{pillar.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="space-y-4">
        <h2 className="text-[11px] font-medium tracking-[0.08em] text-content-subtle uppercase">
          The coordination gap
        </h2>

        <Card>
          <CardContent className="space-y-5 pt-6">
            <p className="max-w-2xl text-sm leading-relaxed text-content-muted">
              AI has made writing code fast. It has not made <em>coordinating</em> the
              decisions around it fast. Existing tools optimise one stage each, and
              nothing continuously answers:
            </p>

            <ul className="space-y-2.5">
              {UNANSWERED.map((question) => (
                <li
                  key={question}
                  className="flex items-start gap-3 rounded-lg border border-border/70 bg-canvas/40 px-4 py-3 text-sm text-content"
                >
                  <span
                    aria-hidden="true"
                    className="mt-1.5 size-1.5 shrink-0 rounded-full bg-accent"
                  />
                  {question}
                </li>
              ))}
            </ul>

            <p className="max-w-2xl text-sm leading-relaxed text-content-muted">
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
