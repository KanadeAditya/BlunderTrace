// A fake backend that runs in the browser, so the screens can be built before the real one exists.
// It returns exactly the shapes in docs/API.md, using the sample data from the approved design.
import { replay, START_FEN } from '@/lib/chess'

import type {
  Color,
  Game,
  GameResult,
  Move,
  Player,
  Report,
  ReportGame,
  StartReportRequest,
  StartReportResponse,
  Weakness,
} from './types'

const MS_PER_GAME = 900 // simulated analysis speed
const GRADING_DELAY_MS = 1500 // simulated deep pass when a game is first opened

class MockError extends Error {
  status: number
  error: string
  constructor(status: number, error: string, detail: string) {
    super(detail)
    this.status = status
    this.error = error
  }
}

// ---------------------------------------------------------------- the sample game (Blackburne Shilling)
const SAMPLE_SANS = ['e4', 'e5', 'Nf3', 'Nc6', 'Bc4', 'Nd4', 'Nxe5', 'Qg5', 'Nxf7', 'Qxg2', 'Rf1', 'Qxe4+', 'Be2', 'Nf3#']
const SAMPLE_EVALS: Move['eval'][] = [
  { cp: 30 }, { cp: 30 }, { cp: 35 }, { cp: 30 }, { cp: 35 }, { cp: 110 }, { cp: -150 }, { cp: -150 },
  { mate: -3 }, { mate: -2 }, { mate: -2 }, { mate: -1 }, { mate: -1 }, { mate: 0 },
]
const SAMPLE_GRADES: Move['grade'][] = [
  'best', 'best', 'best', 'best', 'good', 'inaccuracy', 'blunder', 'great', 'blunder', 'best', 'best', 'best', 'best', 'best',
]
const LINES: Record<number, Pick<Move, 'better_line' | 'refutation_line' | 'better_note' | 'refutation_note' | 'refutation_arrows'>> = {
  7: {
    better_line: ['Nxd4', 'exd4', 'c3', 'dxc3', 'Nxc3'],
    refutation_line: ['Qg5'],
    better_note: '4. Nxd4 keeps the position level (+0.2).',
    refutation_note: 'After 4… Qg5, your knight on e5 and your pawn on g2 are both attacked.',
    refutation_arrows: [['g5', 'e5'], ['g5', 'g2']],
  },
  9: {
    better_line: ['Ng4', 'd5'],
    refutation_line: ['Qxg2', 'Rf1', 'Qxe4+', 'Be2', 'Nf3#'],
    better_note: '5. Ng4 limits the damage (−1.2).',
    refutation_note: 'This line ends in checkmate.',
    refutation_arrows: null,
  },
}
const NO_LINES = { better_line: null, refutation_line: null, better_note: null, refutation_note: null, refutation_arrows: null }

function sampleGame(id: string, opponent: string, userColor: Color, complete: boolean): Game {
  const played = replay(SAMPLE_SANS)
  const moves: Move[] = played.map((m, i) => {
    const ply = i + 1
    const grade = SAMPLE_GRADES[i]
    const isError = grade === 'blunder' || grade === 'mistake' || grade === 'inaccuracy' || grade === 'miss'
    return {
      ply,
      move_number: Math.ceil(ply / 2),
      color: ply % 2 === 1 ? 'white' : 'black',
      san: m.san,
      fen_after: m.fen,
      eval: SAMPLE_EVALS[i],
      // While the deep pass runs, only errors are known (docs/API.md §3).
      grade: complete || isError ? grade : null,
      themes: ply === 7 ? ['hangingPiece'] : ply === 9 ? ['exposedKing'] : [],
      ...(complete ? (LINES[ply] ?? NO_LINES) : NO_LINES),
    }
  })
  return {
    id,
    // As Black, the user is the one setting the trap (and wins); as White, the one falling for it.
    white: userColor === 'white' ? 'knightowl_42' : opponent,
    black: userColor === 'white' ? opponent : 'knightowl_42',
    user_color: userColor,
    result: '0-1',
    opening: 'Italian Game · Blackburne Shilling trap',
    url: 'https://www.chess.com/game/live/123456789',
    start_fen: START_FEN,
    grading: complete ? 'complete' : 'pending',
    moves,
  }
}

// ---------------------------------------------------------------- the 20 sample games
const OPPONENTS = ['player123', 'rook_n_roll', 'e4_enjoyer', 'pawnstorm', 'd4_dave', 'knightmare7', 'castle_queen', 'zugzwanged',
  'fianchetto_fan', 'gambit_gary', 'b4_or_not', 'tempo_tom', 'endgame_ella', 'sac_attack', 'opposite_bishops', 'pin_master',
  'h_file_hero', 'luft_life', 'queenside_q', 'draw_offer_dan']
const RESULTS: GameResult[] = ['loss', 'win', 'loss', 'draw', 'win', 'win', 'loss', 'win', 'win', 'loss', 'win', 'win', 'draw',
  'loss', 'win', 'win', 'loss', 'win', 'loss', 'win']
const BLUNDERS = [2, 0, 3, 0, 1, 4, 2, 3, 1, 5, 2, 3, 2, 4, 1, 3, 2, 4, 3, 3]
const MISTAKES = [0, 1, 1, 0, 0, 1, 2, 0, 1, 1, 0, 2, 1, 0, 0, 1, 2, 1, 0, 1]
const INACCURACIES = [1, 0, 0, 2, 0, 1, 0, 2, 1, 0, 1, 0, 2, 1, 1, 0, 1, 0, 2, 1]
const COLORS = ['white', 'black', 'white', 'black', 'white'] as const
const OPENINGS = ['Italian Game', 'Caro-Kann Defence', 'Sicilian Defence', 'Caro-Kann Defence', 'Italian Game']

/** Deterministic pretend evaluation series (same generator as the design reference). */
function sampleTrace(k: number, blunders: number, result: GameResult): number[] {
  let s = (k + 1) * 7919
  const rnd = () => {
    s = (s * 16807) % 2147483647
    return s / 2147483647
  }
  const n = 22
  let cp = 20
  const out = [cp]
  const drops = new Set<number>()
  for (let j = 0; j < blunders; j++) drops.add(3 + Math.floor(((j + 1) * (n - 8)) / (blunders + 1)))
  for (let j = 1; j <= n; j++) {
    cp += (rnd() - 0.5) * 120
    if (drops.has(j)) cp -= 220 + rnd() * 200
    out.push(cp)
  }
  const target = result === 'win' ? 900 : result === 'loss' ? -900 : 0
  for (let j = n - 5; j <= n; j++) {
    const t = (j - (n - 6)) / 6
    out[j] = out[j] * (1 - t) + target * t
  }
  return out.map((v) => Math.round(v))
}

function reportGame(index: number, state: 'done' | 'running' | 'queued', fraction = 0): ReportGame {
  const k = index % OPPONENTS.length // more than 20 games: the sample data repeats
  const trace = sampleTrace(k, BLUNDERS[k], RESULTS[k])
  const base: ReportGame = {
    id: `g_${index + 1}`,
    status: state === 'done' ? 'done' : state,
    opponent: OPPONENTS[k],
    plies: trace.length - 1,
  }
  if (state === 'queued') return base
  // The game being analysed: the evaluations so far.
  if (state === 'running') return { ...base, trace: trace.slice(0, Math.max(1, Math.floor(fraction * trace.length))) }
  return {
    ...base,
    result: RESULTS[k],
    date: `2026-11-${String(14 - Math.floor(k / 3)).padStart(2, '0')}`,
    color: COLORS[k % 5],
    opening: OPENINGS[k % 5],
    url: `https://www.chess.com/game/live/${123456789 + index}`,
    errors: { blunder: BLUNDERS[k], mistake: MISTAKES[k], inaccuracy: INACCURACIES[k], miss: 0 },
    trace,
  }
}

// ---------------------------------------------------------------- the finished report's content
/** Summary line numbers, counted from the games (20 games give the reference's 11/2/7 and 2.4). */
function summarise(games: ReportGame[]) {
  const n = games.length
  const count = (r: GameResult) => games.filter((g) => g.result === r).length
  const perGame = (key: 'blunder' | 'mistake' | 'miss') =>
    Math.round((games.reduce((sum, g) => sum + (g.errors?.[key] ?? 0), 0) / n) * 10) / 10
  return {
    games: n, wins: count('win'), draws: count('draw'), losses: count('loss'),
    blunders_per_game: perGame('blunder'), mistakes_per_game: perGame('mistake'), misses_per_game: perGame('miss'),
  }
}

function weaknesses(): Weakness[] {
  const before = replay(SAMPLE_SANS.slice(0, 6)) // position before 4. Nxe5
  const beforeNxf7 = replay(SAMPLE_SANS.slice(0, 8)) // position before 5. Nxf7
  return [
    {
      theme: 'hangingPiece',
      name: 'Hanging piece',
      count: 9,
      why: 'You move a piece to a square where nothing defends it, and your opponent takes it for free. In your games it usually happens right after a capture: the piece that just captured is left standing alone.',
      how_to_avoid:
        'Before every move, ask one question: *after this, what can my opponent capture — and is it defended?*[1] If the answer is “something, and no”, choose a different move. Pieces that protect each other are hard to win.[2]',
      examples: [
        {
          game_id: 'g_1', ply: 7, move_number: 4, color: 'white', opponent: 'player123',
          fen_before: before[before.length - 1].fen, played: 'Nxe5', grade: 'blunder', better: 'Nxd4', punishing_line: ['Qg5'],
          note: '4… Qg5! attacks your knight on e5 and your pawn on g2.', arrows: [['g5', 'e5'], ['g5', 'g2']],
        },
        // Every sample game replays the same trap, so the extra examples repeat the position.
        ...[['g_3', 'e4_enjoyer'], ['g_10', 'gambit_gary']].map(([game_id, opponent]) => ({
          game_id, ply: 7, move_number: 4, color: 'white' as const, opponent,
          fen_before: before[before.length - 1].fen, played: 'Nxe5', grade: 'blunder' as const, better: 'Nxd4', punishing_line: ['Qg5'],
          note: '4… Qg5! attacks your knight on e5 and your pawn on g2.', arrows: [['g5', 'e5'], ['g5', 'g2']] as [string, string][],
        })),
      ],
      sources: [
        { title: 'Glossary of chess — Wikipedia', url: 'https://en.wikipedia.org/wiki/Glossary_of_chess',
          passage: 'hanging: Unprotected and exposed to capture. A hanging piece may also be said to be en prise.' },
        { title: 'Chess/Tactics, “Guarding” — Wikibooks', url: 'https://en.wikibooks.org/wiki/Chess/Tactics',
          passage: 'When one of your pieces is placed so that it attacks a square occupied by another of your pieces, the former is said to be guarding the latter. When your opponent captures the guarded piece, you can recapture with the guarding piece.' },
      ],
    },
    {
      theme: 'fork',
      name: 'Fork',
      count: 6,
      why: 'A knight or queen attacked two of your pieces at once, and you could only save one. Five of the six were knight forks on your king and queen.',
      how_to_avoid: 'Keep your king and queen off squares one knight jump apart, and look at every square an enemy knight can reach next move before you commit.',
      examples: [
        {
          game_id: 'g_1', ply: 7, move_number: 4, color: 'white', opponent: 'player123',
          fen_before: before[before.length - 1].fen, played: 'Nxe5', grade: 'blunder', better: 'Nxd4', punishing_line: ['Qg5'],
          note: '4… Qg5! attacks your knight on e5 and your pawn on g2.', arrows: [['g5', 'e5'], ['g5', 'g2']],
        },
      ],
      sources: [],
    },
    {
      theme: 'exposedKing',
      name: 'Exposed king',
      count: 4,
      why: 'Your king was left with too few defenders, and an attack on it decided the game.',
      how_to_avoid: 'Before grabbing material, count the defenders around your king. If enemy pieces are aimed at it, defend first.',
      examples: [
        {
          game_id: 'g_1', ply: 9, move_number: 5, color: 'white', opponent: 'player123',
          fen_before: beforeNxf7[beforeNxf7.length - 1].fen, played: 'Nxf7', grade: 'blunder', better: 'Ng4',
          punishing_line: ['Qxg2', 'Rf1', 'Qxe4+', 'Be2', 'Nf3#'],
          note: '5… Qxg2 attacks your rook on h1 and your pawn on e4.', arrows: [['g2', 'h1'], ['g2', 'e4']],
        },
      ],
      sources: [],
    },
  ]
}

// ---------------------------------------------------------------- in-memory state
const reportsStartedAt = new Map<string, number>()
const reportsGameCount = new Map<string, number>()
const gamesOpenedAt = new Map<string, number>()
reportsStartedAt.set('r_sample', 0) // a finished sample report is always available at /report/r_sample

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

export const mockApi = {
  async getPlayer(username: string): Promise<Player> {
    await delay(250)
    if (username.toLowerCase() === 'notfound') throw new MockError(404, 'username_not_found', `No chess.com player called '${username}'.`)
    return { username, ratings: { rapid: 1184, blitz: 1052 }, games: { rapid: 142, blitz: 380 } }
  },

  async startReport(req: StartReportRequest): Promise<StartReportResponse> {
    await delay(300)
    if (req.username.toLowerCase() === 'notfound') throw new MockError(404, 'username_not_found', `No chess.com player called '${req.username}'.`)
    const id = `r_${Math.random().toString(36).slice(2, 7)}`
    reportsStartedAt.set(id, Date.now())
    reportsGameCount.set(id, req.games)
    return { id, status: 'queued' }
  },

  async getReport(id: string): Promise<Report> {
    await delay(120)
    const started = reportsStartedAt.get(id)
    if (started === undefined) throw new MockError(404, 'report_not_found', 'This report does not exist.')
    const total = reportsGameCount.get(id) ?? 20
    const done = started === 0 ? total : Math.min(total, Math.floor((Date.now() - started) / MS_PER_GAME))
    const finished = done >= total
    const fraction = started === 0 ? 1 : ((Date.now() - started) % MS_PER_GAME) / MS_PER_GAME
    const games = Array.from({ length: total }, (_, k) =>
      reportGame(k, k < done ? 'done' : k === done ? 'running' : 'queued', fraction),
    )
    const report: Report = {
      id, status: finished ? 'done' : 'running', username: 'knightowl_42', time_control: 'rapid',
      progress: { done, total }, games,
    }
    if (!finished) return report
    return {
      ...report,
      notes: [],
      summary: summarise(games),
      // Counts are for 20 games; scale them to the number of games requested.
      weaknesses: weaknesses().map((w) => ({ ...w, count: Math.min(total, Math.max(1, Math.round((w.count * total) / 20))) })),
      missed_tactics: [
        { theme: 'fork', name: 'Fork', count: 5 },
        { theme: 'hangingPiece', name: 'Hanging piece', count: 4 },
        { theme: 'pin', name: 'Pin', count: 2 },
      ],
      openings: [
        { name: 'Italian Game', color: 'white', games: 7, wins: 5, draws: 0, losses: 2, score: 0.71 },
        { name: 'Caro-Kann Defence', color: 'black', games: 4, wins: 1, draws: 2, losses: 1, score: 0.5 },
        { name: 'Sicilian Defence', color: 'white', games: 6, wins: 2, draws: 0, losses: 4, score: 0.33 },
      ],
    }
  },

  async getGame(reportId: string, gameId: string): Promise<Game> {
    await delay(150)
    if (!reportsStartedAt.has(reportId)) throw new MockError(404, 'report_not_found', 'This report does not exist.')
    const index = Number(gameId.replace('g_', '')) - 1
    const total = reportsGameCount.get(reportId) ?? 20
    if (!(index >= 0 && index < total)) throw new MockError(404, 'game_not_found', 'This game is not in the report.')
    const k = index % OPPONENTS.length
    const key = `${reportId}/${gameId}`
    if (!gamesOpenedAt.has(key)) gamesOpenedAt.set(key, Date.now())
    const complete = Date.now() - gamesOpenedAt.get(key)! >= GRADING_DELAY_MS
    // Every sample game replays the same famous trap; only the opponent's name changes.
    return sampleGame(gameId, OPPONENTS[k], COLORS[k % COLORS.length], complete)
  },
}

export { MockError }
