// Move grades as chess annotation glyphs (DESIGN.md §7).
import type { Grade } from '@/api/types'

const GLYPH: Partial<Record<Grade, string>> = {
  brilliant: '!!',
  great: '!',
  inaccuracy: '?!',
  mistake: '?',
  blunder: '??',
  miss: '?', // no classical glyph for "missed tactic"; shown as a mistake, named in the side panel
}

const COLOR_CLASS: Partial<Record<Grade, string>> = {
  brilliant: 'text-accent',
  great: 'text-accent',
  inaccuracy: 'text-inaccuracy',
  mistake: 'text-mistake',
  blunder: 'text-blunder',
  miss: 'text-mistake',
}

const NAME: Partial<Record<Grade, string>> = {
  brilliant: 'Brilliant',
  great: 'Great move',
  inaccuracy: 'Inaccuracy',
  mistake: 'Mistake',
  blunder: 'Blunder',
  miss: 'Missed tactic',
}

/** "??" for a blunder, "" for unmarked grades (best, excellent, good) and null. */
export const gradeGlyph = (g: Grade | null): string => (g ? (GLYPH[g] ?? '') : '')
export const gradeColorClass = (g: Grade | null): string => (g ? (COLOR_CLASS[g] ?? '') : '')
export const gradeName = (g: Grade | null): string => (g ? (NAME[g] ?? '') : '')
export const isError = (g: Grade | null): boolean =>
  g === 'blunder' || g === 'mistake' || g === 'inaccuracy' || g === 'miss'

/** Token name of the grade's colour (for SVG fills), e.g. "blunder". */
export function gradeToken(g: Grade | null): string {
  if (g === 'blunder') return 'blunder'
  if (g === 'mistake' || g === 'miss') return 'mistake'
  if (g === 'inaccuracy') return 'inaccuracy'
  return 'accent'
}
