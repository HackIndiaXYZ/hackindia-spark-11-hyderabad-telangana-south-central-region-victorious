"use client";

import { useState } from "react";
import {
  Bell,
  Home,
  LayoutDashboard,
  Search,
  Table2,
  type LucideIcon,
} from "lucide-react";

import { BlockRenderer } from "@/components/generated/blocks";
import { themeStyle } from "@/lib/generation/theme";
import type { AppSpec } from "@/lib/generation/types";
import { cn } from "@/lib/utils";

/**
 * The generated application, rendered from an `AppSpec`.
 *
 * This component is the whole "product" side of the feature: its own sidebar,
 * its own top bar, its own palette. It knows nothing about artifacts — it walks
 * the spec — which is what keeps synthesis swappable and makes a file-emitting
 * backend possible later.
 *
 * The theme is applied as scoped custom properties on the root element rather
 * than as global CSS, so the generated app cannot leak its palette into the
 * workspace chrome surrounding it.
 */

const ICONS: Record<string, LucideIcon> = {
  Home,
  LayoutDashboard,
  Table2,
};

export function GeneratedApp({ spec }: { spec: AppSpec }) {
  const [activePage, setActivePage] = useState(spec.pages[0]?.id ?? "");
  const page = spec.pages.find((item) => item.id === activePage) ?? spec.pages[0];

  if (!page) return null;

  return (
    <div
      style={themeStyle(spec.theme)}
      className="flex min-h-[38rem] bg-[var(--g-canvas)] text-[var(--g-content)]"
    >
      {/* Sidebar. Hidden below `md` — the generated app is responsive, and at
          phone width a permanent rail would eat half the viewport. */}
      <aside className="hidden w-52 shrink-0 flex-col border-r border-[var(--g-border)] bg-[var(--g-surface)] md:flex">
        <div className="flex items-center gap-2.5 border-b border-[var(--g-border)] px-4 py-4">
          <span
            aria-hidden="true"
            className="grid size-8 shrink-0 place-items-center rounded-lg text-xs font-semibold"
            style={{ background: "var(--g-accent)", color: "var(--g-accent-contrast)" }}
          >
            {spec.brand.initials}
          </span>
          <span className="truncate text-sm font-medium">{spec.brand.name}</span>
        </div>

        <nav aria-label="Generated application" className="flex-1 space-y-0.5 p-2">
          {spec.nav.map((item) => {
            const Icon = ICONS[item.icon] ?? Table2;
            const active = item.pageId === page.id;
            return (
              <button
                key={item.pageId || "overview"}
                type="button"
                onClick={() => setActivePage(item.pageId)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                  active
                    ? "bg-[var(--g-accent-soft)] text-[var(--g-accent)]"
                    : "text-[var(--g-content-muted)] hover:bg-[var(--g-surface-raised)] hover:text-[var(--g-content)]",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="border-t border-[var(--g-border)] p-3">
          <p className="text-[10px] leading-relaxed text-[var(--g-content-subtle)]">
            Generated from {spec.stats.artifactsRead} engineering artifacts.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-[var(--g-border)] bg-[var(--g-surface)] px-4 py-3">
          {/* Mobile page switcher, replacing the hidden sidebar. */}
          <label className="md:hidden">
            <span className="sr-only">Page</span>
            <select
              value={page.id}
              onChange={(event) => setActivePage(event.target.value)}
              className="rounded-lg border border-[var(--g-border)] bg-[var(--g-canvas)] px-2 py-1.5 text-xs text-[var(--g-content)]"
            >
              {spec.nav.map((item) => (
                <option key={item.pageId || "overview"} value={item.pageId}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <div className="relative hidden flex-1 sm:block">
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-[var(--g-content-subtle)]"
              aria-hidden="true"
            />
            <input
              placeholder="Search…"
              aria-label="Search the generated application"
              className="h-8 w-full max-w-xs rounded-lg border border-[var(--g-border)] bg-[var(--g-canvas)] pr-3 pl-8 text-xs text-[var(--g-content)] placeholder:text-[var(--g-content-subtle)] focus:border-[var(--g-accent)] focus:outline-none"
            />
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              aria-label="Notifications"
              className="grid size-8 place-items-center rounded-lg border border-[var(--g-border)] text-[var(--g-content-muted)] transition-colors hover:bg-[var(--g-surface-raised)]"
            >
              <Bell className="size-3.5" aria-hidden="true" />
            </button>
            <span
              aria-hidden="true"
              className="grid size-8 place-items-center rounded-full text-[11px] font-medium"
              style={{ background: "var(--g-accent-soft)", color: "var(--g-accent)" }}
            >
              {spec.brand.initials}
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-5 sm:p-6">
          <div className="mx-auto max-w-5xl space-y-8">
            {page.kind !== "landing" && (
              <div className="space-y-1">
                <h1 className="text-xl font-semibold tracking-tight">{page.title}</h1>
                <p className="text-sm text-[var(--g-content-muted)]">{page.description}</p>
              </div>
            )}

            {page.blocks.map((block, index) => (
              <div
                key={`${block.kind}-${index}`}
                className="animate-[rise_0.4s_var(--ease-out-quint)_both]"
                style={{ animationDelay: `${Math.min(index * 60, 300)}ms` }}
              >
                <BlockRenderer block={block} />
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
