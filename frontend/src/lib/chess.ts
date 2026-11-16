// Chess helpers shared by every screen. Pure functions (no Vue), so they're easy to test.
import { Chess } from 'chess.js'

import type { Eval } from '@/api/types'

export type Square = `${'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h'}${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8}`

/** An arrow drawn on the board: better line in the accent colour, refutation/threat in red. */
export interface BoardArrow {
  from: string
  to: string
  kind: 'better' | 'refute'
}

export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

/** Centipawns from White's view; a forced mate counts as ±1000 (same cap as the backend, PLAN §4.2). */
export function evalToCp(e: Eval): number {
  if (e.mate !== undefined && e.mate !== null) return e.mate > 0 ? 1000 : -1000
  return Math.max(-1000, Math.min(1000, e.cp ?? 0))
}

/** White's winning chance in % (Lichess formula, PLAN §4.2). */
export function winPercent(cp: number): number {
  const c = Math.max(-1000, Math.min(1000, cp))
  return 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * c)) - 1)
}

/** "+0.3", "−1.5", "−M3" — with a real minus sign (DESIGN.md §12). */
export function formatEval(e: Eval, digits = 1): string {
  if (e.mate === 0) return '#' // the position is checkmate
  if (e.mate !== undefined && e.mate !== null) return (e.mate > 0 ? '+M' : '−M') + Math.abs(e.mate)
  const cp = e.cp ?? 0
  const sign = cp > 0 ? '+' : cp < 0 ? '−' : ''
  return sign + Math.abs(cp / 100).toFixed(digits)
}

/** a1 is dark, a8 and h1 are light: light when (file index + rank) is even. */
export function isLightSquare(sq: string): boolean {
  const file = sq.charCodeAt(0) - 97 // a = 0 … h = 7
  const rank = Number(sq[1]) // 1 … 8
  return (file + rank) % 2 === 0
}

/** "4. Nxe5" for White, "4… Qg5" for Black (ply 1 = White's first move). */
export function moveLabel(ply: number, san: string): string {
  const n = Math.ceil(ply / 2)
  return ply % 2 === 1 ? `${n}. ${san}` : `${n}… ${san}`
}

/** "4. Nxd4 exd4 5. c3 dxc3 6. Nxc3" — a line whose first move is played at `ply`. */
export function lineText(ply: number, sans: string[]): string {
  return sans
    .map((san, k) => {
      const p = ply + k
      const n = Math.ceil(p / 2)
      if (p % 2 === 1) return `${n}. ${san}`
      return k === 0 ? `${n}… ${san}` : san
    })
    .join(' ')
}

export interface ReplayedMove {
  san: string
  from: Square
  to: Square
  fen: string
}

/** Play SAN moves from a position; returns each move with its squares and the FEN after it. */
export function replay(sans: string[], startFen: string = START_FEN): ReplayedMove[] {
  const chess = new Chess(startFen)
  return sans.map((san) => {
    const m = chess.move(san)
    return { san: m.san, from: m.from as Square, to: m.to as Square, fen: chess.fen() }
  })
}

/** Points of an evaluation trace: x across, y = pad + (100 − win%) / 100 × (H − 2·pad). */
export function tracePoints(cps: number[], width: number, height: number, pad: number): [number, number][] {
  const n = Math.max(cps.length - 1, 1)
  return cps.map((cp, i) => [(i / n) * width, pad + ((100 - winPercent(cp)) / 100) * (height - 2 * pad)])
}

/** SVG path "M x y L x y …" through the given points ("" if fewer than 2). */
export function tracePath(points: [number, number][]): string {
  if (points.length < 2) return ''
  return 'M' + points.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L')
}
