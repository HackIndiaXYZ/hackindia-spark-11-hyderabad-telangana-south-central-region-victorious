import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Card surface.
 *
 * `10_UI_UX_Plan.md` specifies card-based layouts as the primary organising
 * pattern — agent cards, artifact cards, approval cards all build on this.
 *
 * Depth comes from light rather than from a heavier border: a hairline highlight
 * along the top edge plus a soft drop shadow, which is how a real panel sits
 * above a surface. Stacking borders instead would make a dense grid read as a
 * spreadsheet.
 */
const card = cva(
  [
    "relative rounded-[--radius-card] border border-border bg-surface panel-sheen",
    "transition-[border-color,box-shadow,transform] duration-200 ease-out",
  ],
  {
    variants: {
      elevation: {
        flat: "",
        raised: "elevated",
      },
      /** Lifts on hover. Only for cards that actually go somewhere. */
      interactive: {
        true: "hover:-translate-y-px hover:border-border-strong hover:elevated-lg",
        false: "",
      },
      /** Tints the card with an engineering state without restating the border. */
      state: {
        none: "",
        active: "border-state-active/35 bg-state-active/[0.045]",
        approval: "border-state-approval/35 bg-state-approval/[0.045]",
        blocked: "border-state-blocked/35 bg-state-blocked/[0.045]",
        stale: "border-state-stale/35 bg-state-stale/[0.045]",
      },
    },
    defaultVariants: { elevation: "raised", interactive: false, state: "none" },
  },
);

export interface CardProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof card> {}

export function Card({ className, elevation, interactive, state, ...props }: CardProps) {
  return (
    <div
      className={cn(card({ elevation, interactive, state }), className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-5 pb-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-sm font-medium tracking-tight text-content", className)}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-content-muted", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-0", className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center gap-2 border-t border-border p-5 py-3", className)}
      {...props}
    />
  );
}

/**
 * A single pass of light across the card's top edge, for a card whose work is
 * happening *now*. Purely decorative and therefore `aria-hidden` — the state is
 * always also carried by a `StatusBadge` with a text label.
 */
export function CardActivityBar() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 top-0 h-px overflow-hidden rounded-t-[--radius-card]"
    >
      <div className="animate-[sweep_2.2s_var(--ease-out-quint)_infinite] h-px w-1/2 bg-gradient-to-r from-transparent via-state-active to-transparent" />
    </div>
  );
}
