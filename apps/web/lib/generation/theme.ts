/**
 * Theme derivation.
 *
 * The generated app gets its own palette rather than inheriting the workspace's,
 * because the point of the demo is that this looks like a *different product*
 * that an engineer built — not like another Victorious page.
 *
 * The hue is derived from the project's identity, so it is stable: the same
 * project always generates the same theme, across reloads and machines. A random
 * palette per render would make the feature feel like a toy and would make two
 * screenshots of the same project disagree.
 *
 * Lightness and chroma are fixed to a scale that was tuned once, so every derived
 * hue lands at usable contrast rather than whatever the hash happened to pick.
 * That is what keeps an arbitrary input from producing an unreadable interface.
 */

import type { GeneratedTheme } from "@/lib/generation/types";

/** FNV-1a. Small, dependency-free, and stable across runtimes. */
function hash(input: string): number {
  let value = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    value ^= input.charCodeAt(index);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value;
}

/**
 * Hues that read as "product UI" rather than "warning label".
 *
 * Sampling a continuous 0–360 would eventually land on a muddy olive or a
 * fluorescent chartreuse. Picking from a curated ring keeps every possible
 * outcome defensible while still being derived from the project.
 */
const HUE_RING = [
  { hue: 264, name: "Indigo" },
  { hue: 232, name: "Azure" },
  { hue: 200, name: "Cyan" },
  { hue: 168, name: "Teal" },
  { hue: 146, name: "Emerald" },
  { hue: 300, name: "Violet" },
  { hue: 330, name: "Magenta" },
  { hue: 22, name: "Amber" },
] as const;

export function deriveTheme(seed: string): GeneratedTheme {
  const picked = HUE_RING[hash(seed) % HUE_RING.length]!;
  const { hue, name } = picked;

  return {
    hue,
    name,
    accent: `oklch(0.68 0.17 ${hue})`,
    accentSoft: `oklch(0.68 0.17 ${hue} / 0.14)`,
    accentContrast: `oklch(0.16 0.02 ${hue})`,
    canvas: `oklch(0.145 0.012 ${hue})`,
    surface: `oklch(0.192 0.014 ${hue})`,
    surfaceRaised: `oklch(0.235 0.016 ${hue})`,
    border: `oklch(0.288 0.018 ${hue})`,
    content: `oklch(0.968 0.004 ${hue})`,
    contentMuted: `oklch(0.755 0.014 ${hue})`,
    contentSubtle: `oklch(0.605 0.016 ${hue})`,
  };
}

/**
 * The theme as CSS custom properties.
 *
 * Applied to the preview container rather than injected as a stylesheet, so the
 * generated app is scoped: it cannot leak its palette into the workspace chrome
 * around it, and two previews could sit side by side without fighting.
 */
export function themeStyle(theme: GeneratedTheme): React.CSSProperties {
  return {
    "--g-accent": theme.accent,
    "--g-accent-soft": theme.accentSoft,
    "--g-accent-contrast": theme.accentContrast,
    "--g-canvas": theme.canvas,
    "--g-surface": theme.surface,
    "--g-surface-raised": theme.surfaceRaised,
    "--g-border": theme.border,
    "--g-content": theme.content,
    "--g-content-muted": theme.contentMuted,
    "--g-content-subtle": theme.contentSubtle,
  } as React.CSSProperties;
}
