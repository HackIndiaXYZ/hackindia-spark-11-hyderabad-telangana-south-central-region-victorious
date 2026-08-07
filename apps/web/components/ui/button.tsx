import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * The workspace's one button.
 *
 * Every action in the product routes through this so that "primary" looks the
 * same on the dashboard, in the Approval Center, and on an artifact page.
 * Variants are named for their *role* rather than their colour — `primary`,
 * `approve` — because the role is what stays true when the palette changes.
 *
 * The press feedback is a 1px downward nudge rather than a scale: scaling text
 * resamples it and looks soft, while a nudge reads as a physical key travel.
 */
const button = cva(
  [
    "relative inline-flex select-none items-center justify-center gap-2 rounded-lg font-medium",
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out",
    "active:translate-y-px",
    "disabled:pointer-events-none disabled:opacity-40",
    // Icons should never dictate the button's height.
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: [
          "bg-accent text-canvas",
          "shadow-[0_1px_0_0_oklch(1_0_0/0.18)_inset,0_1px_2px_0_oklch(0_0_0/0.4)]",
          "hover:bg-accent-hover hover:shadow-[0_1px_0_0_oklch(1_0_0/0.22)_inset,0_2px_12px_-2px_var(--color-accent-glow)]",
        ],
        secondary: [
          "border border-border-strong bg-surface-raised text-content",
          "panel-sheen",
          "hover:border-content-subtle hover:bg-surface-overlay",
        ],
        ghost: "text-content-muted hover:bg-surface-raised hover:text-content",
        approve: [
          "border border-state-complete/35 bg-state-complete/12 text-state-complete",
          "hover:border-state-complete/55 hover:bg-state-complete/20",
        ],
        danger: [
          "border border-state-blocked/35 bg-state-blocked/12 text-state-blocked",
          "hover:border-state-blocked/55 hover:bg-state-blocked/20",
        ],
      },
      size: {
        sm: "h-8 px-3 text-xs [&_svg]:size-3.5",
        md: "h-9 px-3.5 text-sm [&_svg]:size-4",
        lg: "h-11 px-5 text-sm [&_svg]:size-4",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(button({ variant, size }), className)} {...props} />;
}

/** The same surface for `<a>`/`<Link>`, so a link-action matches a button. */
export function buttonClass(
  options: VariantProps<typeof button> & { className?: string } = {},
) {
  const { className, ...variants } = options;
  return cn(button(variants), className);
}
