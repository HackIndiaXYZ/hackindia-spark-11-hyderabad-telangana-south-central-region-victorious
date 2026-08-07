import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Form controls.
 *
 * There are only three text inputs in the product — creating a project, giving
 * approval feedback, and revising an artifact — and each previously carried its
 * own copy of the same class list, which is exactly how focus states drift apart.
 *
 * Inputs sit *below* the surface they are on rather than above it: a field is a
 * well you type into, so it takes the deep canvas colour and an inset shadow
 * while cards catch light from above. That inversion is what makes a form read
 * as editable at a glance.
 */
const control = [
  "w-full rounded-lg border border-border bg-canvas-deep px-3 py-2 text-sm text-content",
  "shadow-[0_1px_2px_0_oklch(0_0_0/0.3)_inset]",
  "placeholder:text-content-subtle",
  "transition-[border-color,box-shadow] duration-150",
  "hover:border-border-strong",
  "focus:border-accent focus:outline-none focus:shadow-[0_0_0_3px_var(--color-accent-glow)]",
  "disabled:cursor-not-allowed disabled:opacity-50",
];

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("block text-xs font-medium text-content-muted", className)}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, "resize-y leading-relaxed", className)} {...props} />;
}

/** Label, control, and optional hint as one vertical unit. */
export function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-content-subtle">{hint}</p>}
    </div>
  );
}
