"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Check, Search, SlidersHorizontal } from "lucide-react";

import type {
  Block,
  ChartSeriesPoint,
  EntitySpec,
  FieldSpec,
  MetricSpec,
} from "@/lib/generation/types";
import { cn } from "@/lib/utils";

/**
 * Renderers for every `Block` in an `AppSpec`.
 *
 * These are the generated *product*, not workspace chrome, so they deliberately
 * do not reuse Victorious's `Card`/`Button`. They style off the `--g-*` custom
 * properties the preview frame sets, which is what lets the generated app carry
 * its own derived palette while sitting inside our page. Reusing our components
 * would make every generated app look like Victorious, which would defeat the
 * demonstration.
 *
 * Interactivity is real where it is cheap and honest: tables sort and filter,
 * forms validate and accept input. Nothing persists — the surrounding UI says so
 * — because writing to a generated schema would be fiction.
 */

const cardClass =
  "rounded-xl border border-[var(--g-border)] bg-[var(--g-surface)] " +
  "shadow-[0_1px_0_0_oklch(1_0_0/0.04)_inset,0_10px_30px_-18px_oklch(0_0_0/0.8)]";

export function BlockRenderer({ block }: { block: Block }) {
  switch (block.kind) {
    case "hero":
      return (
        <Hero
          headline={block.headline}
          sub={block.sub}
          audiences={block.audiences}
          primaryAction={block.primaryAction}
        />
      );
    case "metrics":
      return <Metrics items={block.items} />;
    case "features":
      return <Features title={block.title} items={block.items} />;
    case "table":
      return <EntityTable title={block.title} entity={block.entity} />;
    case "form":
      return <EntityForm title={block.title} entity={block.entity} submitLabel={block.submitLabel} />;
    case "chart":
      return (
        <ChartBlock
          title={block.title}
          caption={block.caption}
          variant={block.variant}
          series={block.series}
        />
      );
    case "flows":
      return <Flows title={block.title} steps={block.steps} />;
    case "checklist":
      return <Checklist title={block.title} caption={block.caption} items={block.items} />;
    case "stack":
      return <Stack title={block.title} items={block.items} />;
    case "prose":
      return <Prose title={block.title} markdown={block.markdown} />;
  }
}

// --- Hero --------------------------------------------------------------------

function Hero({
  headline,
  sub,
  audiences,
  primaryAction,
}: {
  headline: string;
  sub: string;
  audiences: string[];
  primaryAction: string;
}) {
  return (
    <section className="relative overflow-hidden rounded-2xl border border-[var(--g-border)] bg-[var(--g-surface)] px-6 py-12 sm:px-10 sm:py-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(42rem 20rem at 18% -20%, var(--g-accent-soft), transparent 65%)",
        }}
      />
      <div className="relative max-w-2xl space-y-5">
        <span className="inline-flex items-center gap-2 rounded-full border border-[var(--g-accent)]/30 bg-[var(--g-accent-soft)] px-3 py-1 text-xs font-medium text-[var(--g-accent)]">
          <span className="size-1.5 rounded-full bg-[var(--g-accent)]" aria-hidden="true" />
          Now available
        </span>

        <h1 className="text-4xl leading-[1.08] font-semibold tracking-tight text-balance text-[var(--g-content)] sm:text-5xl">
          {headline}
        </h1>

        <p className="text-base leading-relaxed text-[var(--g-content-muted)] sm:text-lg">{sub}</p>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--g-accent)] px-5 py-2.5 text-sm font-medium text-[var(--g-accent-contrast)] transition-transform duration-150 hover:-translate-y-px active:translate-y-0"
          >
            {primaryAction}
            <ArrowRight className="size-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="rounded-lg border border-[var(--g-border)] px-5 py-2.5 text-sm text-[var(--g-content-muted)] transition-colors hover:bg-[var(--g-surface-raised)]"
          >
            Talk to the team
          </button>
        </div>

        {audiences.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-3">
            <span className="text-xs text-[var(--g-content-subtle)]">Built for</span>
            {audiences.map((audience) => (
              <span
                key={audience}
                className="rounded-full border border-[var(--g-border)] bg-[var(--g-surface-raised)] px-2.5 py-0.5 text-xs text-[var(--g-content-muted)]"
              >
                {audience}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

// --- Metrics -----------------------------------------------------------------

const TONE: Record<MetricSpec["tone"], string> = {
  neutral: "text-[var(--g-content)]",
  positive: "text-emerald-400",
  warning: "text-amber-400",
  critical: "text-rose-400",
};

function Metrics({ items }: { items: MetricSpec[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className={cn(cardClass, "p-4")}>
          <p className={cn("font-mono text-2xl leading-none tracking-tight", TONE[item.tone])}>
            {item.value}
            {item.suffix && (
              <span className="text-[var(--g-content-subtle)]">{item.suffix}</span>
            )}
          </p>
          <p className="mt-2 text-xs text-[var(--g-content-muted)]">{item.label}</p>
          <p className="mt-0.5 text-[11px] text-[var(--g-content-subtle)]">{item.hint}</p>
        </div>
      ))}
    </div>
  );
}

// --- Features ----------------------------------------------------------------

function Features({
  title,
  items,
}: {
  title: string;
  items: Array<{ id: string; title: string; description: string; priority: string }>;
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <article
            key={item.id}
            className={cn(cardClass, "group p-5 transition-transform duration-200 hover:-translate-y-0.5")}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px] text-[var(--g-accent)]">{item.id}</span>
              <span className="rounded-full border border-[var(--g-border)] px-2 py-0.5 text-[10px] text-[var(--g-content-subtle)] uppercase">
                {item.priority}
              </span>
            </div>
            <h3 className="mt-3 text-sm font-medium text-[var(--g-content)]">{item.title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--g-content-muted)]">
              {item.description}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

// --- Table -------------------------------------------------------------------

function EntityTable({ title, entity }: { title: string; entity: EntitySpec }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [ascending, setAscending] = useState(true);

  const columns = entity.fields.slice(0, 5);

  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();
    const filtered = term
      ? entity.rows.filter((row) =>
          Object.values(row).some((value) => String(value).toLowerCase().includes(term)),
        )
      : entity.rows;

    if (!sortKey) return filtered;

    return [...filtered].sort((left, right) => {
      const a = left[sortKey];
      const b = right[sortKey];
      if (a === b) return 0;
      const order = String(a) > String(b) ? 1 : -1;
      return ascending ? order : -order;
    });
  }, [entity.rows, query, sortKey, ascending]);

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-[var(--g-content-subtle)]"
              aria-hidden="true"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${entity.plural.toLowerCase()}`}
              aria-label={`Search ${entity.plural.toLowerCase()}`}
              className="h-8 w-48 rounded-lg border border-[var(--g-border)] bg-[var(--g-canvas)] pr-3 pl-8 text-xs text-[var(--g-content)] placeholder:text-[var(--g-content-subtle)] focus:border-[var(--g-accent)] focus:outline-none"
            />
          </div>
          <button
            type="button"
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--g-border)] px-2.5 text-xs text-[var(--g-content-muted)] transition-colors hover:bg-[var(--g-surface-raised)]"
          >
            <SlidersHorizontal className="size-3.5" aria-hidden="true" />
            Filter
          </button>
        </div>
      </div>

      <div className={cn(cardClass, "overflow-hidden")}>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[var(--g-border)] bg-[var(--g-surface-raised)]">
                {columns.map((field) => {
                  const active = sortKey === field.name;
                  return (
                    <th
                      key={field.name}
                      scope="col"
                      // `aria-sort` belongs on the column header, not on the
                      // control inside it — the header is what carries the
                      // sort state to assistive technology.
                      aria-sort={active ? (ascending ? "ascending" : "descending") : "none"}
                      className="px-4 py-2.5 text-left"
                    >
                      <button
                        type="button"
                        onClick={() => {
                          if (active) setAscending((value) => !value);
                          else {
                            setSortKey(field.name);
                            setAscending(true);
                          }
                        }}
                        className="inline-flex items-center gap-1 text-[11px] font-medium tracking-wide text-[var(--g-content)] uppercase transition-colors hover:text-[var(--g-accent)]"
                      >
                        {field.label}
                        <span
                          aria-hidden="true"
                          className={cn(
                            "text-[9px]",
                            active ? "text-[var(--g-accent)]" : "text-[var(--g-content-subtle)]",
                          )}
                        >
                          {active ? (ascending ? "▲" : "▼") : "↕"}
                        </span>
                      </button>
                    </th>
                  );
                })}
                <th scope="col" className="px-4 py-2.5 text-right text-[11px] font-medium tracking-wide text-[var(--g-content)] uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={index}
                  className="border-b border-[var(--g-border)]/60 transition-colors last:border-0 hover:bg-[var(--g-surface-raised)]/60"
                >
                  {columns.map((field) => (
                    <td
                      key={field.name}
                      className={cn(
                        "px-4 py-2.5 align-middle",
                        field.primary
                          ? "font-medium text-[var(--g-content)]"
                          : "text-[var(--g-content-muted)]",
                      )}
                    >
                      <Cell value={row[field.name]} field={field} />
                    </td>
                  ))}
                  <td className="px-4 py-2.5 text-right">
                    <button
                      type="button"
                      className="text-xs text-[var(--g-accent)] transition-opacity hover:opacity-80"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={columns.length + 1}
                    className="px-4 py-10 text-center text-sm text-[var(--g-content-subtle)]"
                  >
                    No {entity.plural.toLowerCase()} match “{query}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-[var(--g-border)] bg-[var(--g-surface-raised)]/50 px-4 py-2 text-[11px] text-[var(--g-content-subtle)]">
          <span>
            {rows.length} of {entity.rows.length} · sample data
          </span>
          {entity.endpoints.length > 0 && (
            <span className="font-mono">
              {entity.endpoints[0]!.method} {entity.endpoints[0]!.path}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function Cell({ value, field }: { value: unknown; field: FieldSpec }) {
  if (field.control === "checkbox") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]",
          value
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            : "border-[var(--g-border)] text-[var(--g-content-subtle)]",
        )}
      >
        {value ? <Check className="size-3" aria-hidden="true" /> : null}
        {value ? "Yes" : "No"}
      </span>
    );
  }

  if (field.control === "select") {
    return (
      <span className="rounded-full border border-[var(--g-accent)]/25 bg-[var(--g-accent-soft)] px-2 py-0.5 text-[11px] text-[var(--g-accent)]">
        {String(value)}
      </span>
    );
  }

  return <span className={field.control === "number" ? "font-mono" : ""}>{String(value)}</span>;
}

// --- Form --------------------------------------------------------------------

function EntityForm({
  title,
  entity,
  submitLabel,
}: {
  title: string;
  entity: EntitySpec;
  submitLabel: string;
}) {
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [submitted, setSubmitted] = useState(false);

  const missing = entity.fields.filter(
    (field) => field.required && field.control !== "checkbox" && !String(values[field.name] ?? "").trim(),
  );

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(true);
        }}
        className={cn(cardClass, "space-y-4 p-5")}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {entity.fields.map((field) => (
            <div
              key={field.name}
              className={cn("space-y-1.5", field.control === "textarea" && "sm:col-span-2")}
            >
              <label
                htmlFor={`${entity.name}-${field.name}`}
                className="block text-xs font-medium text-[var(--g-content-muted)]"
              >
                {field.label}
                {field.required && (
                  <span className="ml-1 text-[var(--g-accent)]" aria-hidden="true">
                    *
                  </span>
                )}
              </label>

              <Control
                id={`${entity.name}-${field.name}`}
                field={field}
                value={values[field.name]}
                onChange={(next) => setValues((current) => ({ ...current, [field.name]: next }))}
              />

              {field.description && (
                <p className="text-[11px] text-[var(--g-content-subtle)]">{field.description}</p>
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-[var(--g-border)] pt-4">
          <button
            type="submit"
            className="rounded-lg bg-[var(--g-accent)] px-4 py-2 text-sm font-medium text-[var(--g-accent-contrast)] transition-transform duration-150 hover:-translate-y-px active:translate-y-0"
          >
            {submitLabel}
          </button>
          <button
            type="button"
            onClick={() => {
              setValues({});
              setSubmitted(false);
            }}
            className="rounded-lg border border-[var(--g-border)] px-4 py-2 text-sm text-[var(--g-content-muted)] transition-colors hover:bg-[var(--g-surface-raised)]"
          >
            Reset
          </button>

          {submitted && (
            <p role="status" className="text-xs text-[var(--g-content-muted)]">
              {missing.length === 0
                ? "Valid — this preview does not persist data."
                : `${missing.length} required field${missing.length === 1 ? "" : "s"} still empty.`}
            </p>
          )}
        </div>
      </form>
    </section>
  );
}

function Control({
  id,
  field,
  value,
  onChange,
}: {
  id: string;
  field: FieldSpec;
  value: string | boolean | undefined;
  onChange: (next: string | boolean) => void;
}) {
  const base =
    "w-full rounded-lg border border-[var(--g-border)] bg-[var(--g-canvas)] px-3 py-2 text-sm " +
    "text-[var(--g-content)] placeholder:text-[var(--g-content-subtle)] " +
    "focus:border-[var(--g-accent)] focus:outline-none transition-colors";

  if (field.control === "checkbox") {
    return (
      <label className="flex cursor-pointer items-center gap-2 text-sm text-[var(--g-content-muted)]">
        <input
          id={id}
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          className="size-4 accent-[var(--g-accent)]"
        />
        Enabled
      </label>
    );
  }

  if (field.control === "select") {
    return (
      <select
        id={id}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        className={base}
      >
        <option value="">Select…</option>
        {field.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (field.control === "textarea") {
    return (
      <textarea
        id={id}
        rows={3}
        value={String(value ?? "")}
        onChange={(event) => onChange(event.target.value)}
        className={cn(base, "resize-y")}
      />
    );
  }

  const inputType =
    field.control === "number"
      ? "number"
      : field.control === "date"
        ? "date"
        : field.control === "datetime"
          ? "datetime-local"
          : "text";

  return (
    <input
      id={id}
      type={inputType}
      value={String(value ?? "")}
      onChange={(event) => onChange(event.target.value)}
      placeholder={field.control === "text" ? field.label : undefined}
      className={base}
    />
  );
}

// --- Charts ------------------------------------------------------------------

/**
 * Charts are hand-drawn SVG rather than a charting library.
 *
 * Two series types are needed and both are a dozen lines; adding a dependency
 * for that would cost more in bundle size than it saves in code, and it would
 * fight the derived palette.
 */
function ChartBlock({
  title,
  caption,
  variant,
  series,
}: {
  title: string;
  caption: string;
  variant: "donut" | "bars";
  series: ChartSeriesPoint[];
}) {
  return (
    <section className={cn(cardClass, "space-y-4 p-5")}>
      <div>
        <h2 className="text-sm font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
        <p className="mt-0.5 text-xs text-[var(--g-content-subtle)]">{caption}</p>
      </div>
      {variant === "donut" ? <Donut series={series} /> : <Bars series={series} />}
    </section>
  );
}

function Donut({ series }: { series: ChartSeriesPoint[] }) {
  const total = series.reduce((sum, point) => sum + point.value, 0) || 1;
  const primary = series[0]?.value ?? 0;
  const percent = Math.round((primary / total) * 100);

  const radius = 46;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className="flex items-center gap-6">
      <div className="relative size-28 shrink-0">
        <svg viewBox="0 0 110 110" className="-rotate-90">
          <circle cx="55" cy="55" r={radius} fill="none" strokeWidth="11" className="stroke-[var(--g-surface-raised)]" />
          <circle
            cx="55"
            cy="55"
            r={radius}
            fill="none"
            strokeWidth="11"
            strokeLinecap="round"
            stroke="var(--g-accent)"
            strokeDasharray={`${(percent / 100) * circumference} ${circumference}`}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-xl text-[var(--g-content)]">{percent}%</span>
        </div>
      </div>

      <dl className="space-y-2">
        {series.map((point, index) => (
          <div key={point.label} className="flex items-center gap-2 text-sm">
            <span
              aria-hidden="true"
              className="size-2.5 rounded-sm"
              style={{
                background: index === 0 ? "var(--g-accent)" : "var(--g-surface-raised)",
              }}
            />
            <dt className="text-[var(--g-content-muted)]">{point.label}</dt>
            <dd className="font-mono text-[var(--g-content)]">{point.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Bars({ series }: { series: ChartSeriesPoint[] }) {
  const max = Math.max(1, ...series.map((point) => point.value));

  return (
    <ul className="space-y-2.5">
      {series.map((point) => (
        <li key={point.label} className="space-y-1">
          <div className="flex items-baseline justify-between gap-3 text-xs">
            <span className="truncate text-[var(--g-content-muted)]">{point.label}</span>
            <span className="shrink-0 font-mono text-[var(--g-content-subtle)]">{point.value}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--g-surface-raised)]">
            <div
              className="h-full rounded-full transition-[width] duration-700"
              style={{
                width: `${(point.value / max) * 100}%`,
                background: "var(--g-accent)",
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

// --- Flows, checklist, stack, prose -----------------------------------------

function Flows({
  title,
  steps,
}: {
  title: string;
  steps: Array<{ role: string; wants: string; soThat: string; criteria: string[] }>;
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {steps.map((step, index) => (
          <article key={index} className={cn(cardClass, "p-5")}>
            <span className="text-[11px] tracking-wide text-[var(--g-accent)] uppercase">
              As a {step.role}
            </span>
            <p className="mt-2 text-sm text-[var(--g-content)]">{step.wants}</p>
            {step.soThat && (
              <p className="mt-1 text-sm text-[var(--g-content-muted)]">so that {step.soThat}</p>
            )}
            {step.criteria.length > 0 && (
              <ul className="mt-3 space-y-1 border-t border-[var(--g-border)] pt-3">
                {step.criteria.map((criterion) => (
                  <li
                    key={criterion}
                    className="flex items-start gap-2 text-xs text-[var(--g-content-muted)]"
                  >
                    <Check className="mt-0.5 size-3 shrink-0 text-[var(--g-accent)]" aria-hidden="true" />
                    {criterion}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function Checklist({
  title,
  caption,
  items,
}: {
  title: string;
  caption: string;
  items: string[];
}) {
  return (
    <section className={cn(cardClass, "space-y-3 p-5")}>
      <div>
        <h2 className="text-sm font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
        <p className="mt-0.5 text-xs text-[var(--g-content-subtle)]">{caption}</p>
      </div>
      <ol className="space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex items-start gap-2.5 text-sm text-[var(--g-content-muted)]">
            <span
              aria-hidden="true"
              className="mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border border-[var(--g-border)] font-mono text-[9px] text-[var(--g-content-subtle)]"
            >
              {index + 1}
            </span>
            {item}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Stack({
  title,
  items,
}: {
  title: string;
  items: Array<{ layer: string; choice: string; rationale: string }>;
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <div key={`${item.layer}-${item.choice}`} className={cn(cardClass, "p-4")}>
            <p className="text-[11px] tracking-wide text-[var(--g-content-subtle)] uppercase">
              {item.layer}
            </p>
            <p className="mt-1 text-sm font-medium text-[var(--g-content)]">{item.choice}</p>
            {item.rationale && (
              <p className="mt-1.5 text-xs leading-relaxed text-[var(--g-content-muted)]">
                {item.rationale}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function Prose({ title, markdown }: { title: string; markdown: string }) {
  return (
    <section className={cn(cardClass, "space-y-2 p-5")}>
      <h2 className="text-sm font-semibold tracking-tight text-[var(--g-content)]">{title}</h2>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-[var(--g-content-muted)]">
        {markdown}
      </p>
    </section>
  );
}
