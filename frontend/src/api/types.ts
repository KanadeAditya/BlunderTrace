// TypeScript shapes of the API — must match docs/API.md exactly.

export type TimeControl = 'rapid' | 'blitz' | 'both'
export type Status = 'queued' | 'running' | 'done' | 'failed'
export type Color = 'white' | 'black'
export type GameResult = 'win' | 'loss' | 'draw'
export type Grade =
  | 'brilliant'
  | 'great'
  | 'best'
  | 'excellent'
  | 'good'
  | 'inaccuracy'
  | 'mistake'
  | 'blunder'
  | 'miss'

/** Evaluation from White's point of view: centipawns, or moves to mate (negative = Black mates). */
export interface Eval {
  cp?: number
  mate?: number
}

export interface ApiError {
  error: string
  detail: string
}

// ---- GET /api/players/{username} ----
export interface Player {
  username: string
  ratings: Partial<Record<'rapid' | 'blitz', number>>
  games: Record<'rapid' | 'blitz', number>
}

// ---- POST /api/reports ----
export interface StartReportRequest {
  username: string
  time_control: TimeControl
  games: number
}
export interface StartReportResponse {
  id: string
  status: Status
}

// ---- GET /api/reports/{id} ----
export interface ErrorCounts {
  blunder: number
  mistake: number
  inaccuracy: number
  miss: number
}

export interface ReportGame {
  id: string
  status: Status
  opponent: string
  result?: GameResult
  date?: string
  color?: Color
  opening?: string
  url?: string
  errors?: ErrorCounts
  /** White's evaluation (cp) after each half-move, start included — draws the Analysing trace. */
  trace?: number[]
}

export interface Source {
  title: string
  url: string
  /** The retrieved passage this source contributed (shown in the footnote preview). */
  passage: string
}

export interface Example {
  game_id: string
  ply: number
  move_number: number
  color: Color
  opponent: string
  fen_before: string
  played: string
  better: string
  punishing_line: string[]
  /** Deterministic sentence about the reply, e.g. "4… Qg5! attacks your knight on e5 and your pawn on g2." */
  note: string
  /** Threats to draw on the example diagram (position after the reply), as [from, to] squares. */
  arrows: [string, string][]
}

export interface Weakness {
  theme: string
  name: string
  count: number
  /** Plain text. Inline marks: `*…*` = emphasis, `[n]` = citation of sources[n-1]. */
  why: string
  how_to_avoid: string
  examples: Example[]
  sources: Source[]
}

export interface ThemeCount {
  theme: string
  name: string
  count: number
}

export interface OpeningScore {
  name: string
  color: Color
  games: number
  wins: number
  draws: number
  losses: number
  score: number
}

export interface Summary {
  games: number
  wins: number
  draws: number
  losses: number
  blunders_per_game: number
  mistakes_per_game: number
  misses_per_game: number
}

export interface Report {
  id: string
  status: Status
  username: string
  time_control: TimeControl
  progress: { done: number; total: number }
  games: ReportGame[]
  notes?: string[]
  summary?: Summary
  weaknesses?: Weakness[]
  missed_tactics?: ThemeCount[]
  openings?: OpeningScore[]
  error?: string
  detail?: string
}

// ---- GET /api/reports/{id}/games/{game_id} ----
export interface Move {
  ply: number
  move_number: number
  color: Color
  san: string
  fen_after: string
  eval: Eval
  grade: Grade | null
  themes: string[]
  better_line: string[] | null
  refutation_line: string[] | null
  /** Deterministic one-line summaries of the two lines (templates, no AI; null when not available). */
  better_note: string | null
  refutation_note: string | null
  /** Threats to draw at the end of the refutation, as [from, to] squares (e.g. a fork's two targets). */
  refutation_arrows: [string, string][] | null
}

export interface Game {
  id: string
  white: string
  black: string
  user_color: Color
  result: '1-0' | '0-1' | '1/2-1/2'
  opening: string
  url: string
  start_fen: string
  grading: 'pending' | 'complete'
  moves: Move[]
}
