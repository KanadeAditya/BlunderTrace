// The home page's animated example: the Blackburne Shilling trap (a real, famous trap).
// White's 4. Nxe5?? walks into a double attack; 5. Nxf7?? then allows mate.
import { replay } from '@/lib/chess'

const SANS = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Nd4', 'Nxe5', 'Qg5', 'Nxf7']

export const HERO = {
  moves: replay(SANS),
  /** Annotation glyph shown after each move in the notation line. */
  glyphs: ['', '', '', '', '', '?!', '??', '!', '??'],
  /** White's evaluation in centipawns: start position, then after each move (mate capped at −1000). */
  evals: [20, 30, 30, 35, 30, 35, 110, -150, -150, -1000],
  /** The ply where the game turns: marked on the trace. */
  momentPly: 7,
  momentLabel: '4. Nxe5??',
  /** Arrows shown on the double attack (after 4… Qg5). */
  arrowsAtPly: { 8: [['g5', 'e5'], ['g5', 'g2']] } as Record<number, [string, string][]>,
  lastPly: 9,
}

export function heroCaption(ply: number): string {
  if (ply < 6) return 'Fig. 1 — An ordinary Italian Game.'
  if (ply === 6) return 'Fig. 1 — Black plays the dubious 3… Nd4?!'
  if (ply === 7) return 'Fig. 1 — 4. Nxe5?? grabs a pawn. This is the moment.'
  if (ply === 8) return 'Fig. 1 — 4… Qg5! attacks the knight and g2 at once.'
  return 'Fig. 1 — 5. Nxf7?? and mate follows in three.'
}

export function heroNotation(ply: number): string {
  const out: string[] = []
  for (let i = 0; i < ply; i++) {
    const text = HERO.moves[i].san + HERO.glyphs[i]
    out.push(i % 2 === 0 ? `${i / 2 + 1}. ${text}` : text)
  }
  return out.length ? out.join(' ') : '1. …'
}
