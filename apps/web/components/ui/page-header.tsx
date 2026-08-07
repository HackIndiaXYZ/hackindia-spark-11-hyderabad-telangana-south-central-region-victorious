import { cn } from "@/lib/utils";

/**
 * The heading block every workspace section opens with.
 *
 * Each section previously rolled its own, which let the eyebrow, title, and
 * description drift apart page to page. Routing them through one component is
 * what makes moving between Requirements, Traceability, and Helix Review feel
 * like moving inside one product rather than between five.
 *
 * The eyebrow names the *category* of the view; the title names the view. That
 * pairing is what lets the title stay short without losing context.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex flex-wrap items-start justify-between gap-x-6 gap-y-3",
        className,
      )}
    >
      <div className="min-w-0 space-y-1.5">
        {eyebrow && (
          <p className="text-[11px] font-medium tracking-[0.08em] text-content-subtle uppercase">
            {eyebrow}
          </p>
        )}
        <h2 className="text-base font-semibold tracking-tight text-content">{title}</h2>
        {description && (
          <p className="max-w-3xl text-sm leading-relaxed text-content-muted">
            {description}
          </p>
        )}
      </div>

      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

/**
 * A minor heading inside a section — "Dependencies, artifact by artifact",
 * "Review history". Small, spaced caps with a rule that runs to the edge, so
 * groups separate without another box.
 */
export function SectionLabel({
  children,
  className,
  trailing,
}: {
  children: React.ReactNode;
  className?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <h3 className="text-[11px] font-medium tracking-[0.08em] text-content-subtle uppercase">
        {children}
      </h3>
      <span
        aria-hidden="true"
        className="h-px flex-1 bg-gradient-to-r from-border to-transparent"
      />
      {trailing}
    </div>
  );
}
