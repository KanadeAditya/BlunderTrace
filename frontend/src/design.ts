// Design values needed by TypeScript code (DESIGN.md §5, §10).
// Colours are read from the CSS tokens at runtime so there is still only one source of truth.

export const MOTION = {
  moveMs: 300, // chessground piece animation
  heroStepMs: 1100, // home hero: one move per 1.1 s
  heroHoldSteps: 4, // ...then hold ~4.4 s before restarting
  lineStepMs: 950, // "Show better move" / "Show why it's bad" playback
} as const

/** Read a design token (e.g. "accent") from the CSS variables in styles/tokens.css. */
export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--color-${name}`).trim()
}

/** True when the user asked the OS to reduce motion. */
export function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}
