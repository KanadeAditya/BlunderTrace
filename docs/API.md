# BlunderTrace — API Contract (first cut)

The JSON each screen receives. The frontend is built against sample data in exactly these shapes;
the backend is built to return them. Base path: `/api`. All responses are JSON.

## Conventions
- **IDs** are opaque strings (`r_…` reports, `g_…` games).
- **Ply** = half-move index, starting at 1 for White's first move. `move_number` is the usual
  chess move number (ply 35 → move 18, White).
- **Moves** are in SAN (`"Nf3"`, `"exd5"`, `"O-O"`). **Positions** are FEN strings.
- **Evaluation** is always from White's point of view: `{ "cp": -310 }` (centipawns; −310 = Black
  is 3.1 pawns better) or `{ "mate": 3 }` (White mates in 3; negative = Black mates).
- **Lines** are arrays of SAN moves starting from the position *before* the move they belong to.
- **Grades:** `brilliant`, `great`, `best`, `excellent`, `good`, `inaccuracy`, `mistake`,
  `blunder`, `miss`. Errors = `inaccuracy`, `mistake`, `blunder`, `miss`. A move that allowed a
  tactic keeps its error grade (`inaccuracy` / `mistake` / `blunder`); `miss` is an error that let a
  winning tactic slip without allowing one.
- **Themes** use Lichess puzzle-theme keys (`hangingPiece`, `fork`, `pin`, …) with a display `name`.
- Report and game **statuses**: `queued` → `running` → `done`, or `failed`.

---

## 0. Look up a player — `GET /api/players/{username}`

Called by Home while the user types (debounced), to show the player preview and the game counts on
the time-control buttons. Cached on the server for 5 minutes.

```json
{
  "username": "knightowl_42",
  "ratings": { "rapid": 1184, "blitz": 1052 },
  "games": { "rapid": 142, "blitz": 380 }
}
```
- Source: chess.com `GET /pub/player/{username}/stats` — `ratings` from `chess_rapid/chess_blitz.last.rating`
  (omitted if never played); `games` = `record.win + record.loss + record.draw` (the player's
  **all-time** games in that time control, not just recent ones).
- `404 username_not_found` when chess.com has no such player.

---

## 1. Start an analysis — `POST /api/reports`

Request:
```json
{ "username": "adityakanade", "time_control": "rapid", "games": 20 }
```
| Field | Rules |
|---|---|
| `username` | chess.com username format (letters, digits, `_`, `-`), 3–25 chars |
| `time_control` | `rapid` \| `blitz` \| `both` |
| `games` | one of 10, 20, 30, 50 (default 20) — chosen with the inline selector on Home |

Responses:
- `202` `{ "id": "r_8f3k2", "status": "queued" }`: analysis started.
- `202` `{ "id": "r_8f3k2", "status": "running" }`: an identical report is already running, so its
  id is returned (no duplicate).
- `200` `{ "id": "r_8f3k2", "status": "done" }`: an identical report finished in the last 10
  minutes and is reused.
  - "Identical" means the same username (ignoring capitals), `time_control` and `games`.
  - Any difference makes a new report, which still reuses already-analysed games.
- `404` `username_not_found`: checked immediately, before any analysis starts.
- `422` `invalid_input`: a field breaks the rules above.
- `422` `no_games`: the player has no games at all in that time control.
- `503` `chesscom_unavailable`: chess.com isn't responding.
- `503` `busy`: too many reports are already running. Try again in a few minutes.

## 2. Get a report — `GET /api/reports/{id}`

Polled every ~2 s while `status` is `queued` or `running`; the same response is the finished report.

### While running (Analysing screen)
```json
{
  "id": "r_8f3k2",
  "status": "running",
  "username": "adityakanade",
  "time_control": "rapid",
  "progress": { "done": 12, "total": 20 },
  "games": [
    {
      "id": "g_1", "status": "done",
      "opponent": "player123", "result": "win",
      "errors": { "blunder": 2, "mistake": 0, "inaccuracy": 1, "miss": 1 },
      "trace": [20, 30, 30, 35, 30, 35, 110, -150, -150, -1000]
    },
    { "id": "g_2", "status": "running", "opponent": "chessfan99" }
  ]
}
```

### When done (Report screen) — the same object, plus:
```json
{
  "status": "done",
  "notes": ["Only 4 rapid games found; patterns may be weak."],
  "summary": {
    "games": 20, "wins": 11, "draws": 2, "losses": 7,
    "blunders_per_game": 2.4, "mistakes_per_game": 1.1, "misses_per_game": 0.6
  },
  "weaknesses": [
    {
      "theme": "hangingPiece",
      "name": "Hanging piece",
      "count": 9,
      "why": "You move pieces to squares where nothing defends them, and your opponent takes them for free.",
      "how_to_avoid": "Before every move, ask one question: *after this, what can my opponent capture — and is it defended?*[1] …[2]",
      "examples": [
        {
          "game_id": "g_1", "ply": 35, "move_number": 18, "color": "white",
          "opponent": "player123",
          "fen_before": "r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2NB1N2/PP3PPP/R1BQ1RK1 w - - 0 18",
          "played": "Bc4", "grade": "blunder", "better": "Be2",
          "punishing_line": ["Nxc4", "dxc4", "Qd4"],
          "note": "4… Qg5! attacks your knight on e5 and your pawn on g2.",
          "arrows": [["g5", "e5"], ["g5", "g2"]]
        }
      ],
      "sources": [
        { "title": "Glossary of chess — Wikipedia", "url": "https://en.wikipedia.org/wiki/Glossary_of_chess",
          "passage": "hanging: Unprotected and exposed to capture. A hanging piece may also be said to be en prise." }
      ]
    }
  ],
  "missed_tactics": [
    { "theme": "fork", "name": "Fork", "count": 5 }
  ],
  "openings": [
    { "name": "Sicilian Defense", "color": "white", "games": 6,
      "wins": 2, "draws": 0, "losses": 4, "score": 0.33 }
  ],
  "games": [
    {
      "id": "g_1", "status": "done",
      "date": "2026-11-10", "opponent": "player123", "color": "white",
      "result": "win", "opening": "Italian Game",
      "url": "https://www.chess.com/game/live/123456789",
      "errors": { "blunder": 2, "mistake": 0, "inaccuracy": 1, "miss": 1 }
    }
  ]
}
```
- `weaknesses`: top 3 (tactics the user **allowed**). `count` and examples only include the user's
  own moves.
  - `count` is the number of games in which the user allowed this tactic at least once, shown as
    "9 of 20 games". Cards are ranked by it; ties go to the tactic that happened more times.
  - Cards come from the user's blunders and mistakes. If those give fewer than 3 tactics,
    inaccuracies that allowed a tactic fill the remaining slots.
  - There are fewer than 3 cards only when the user's errors contain fewer than 3 tactics in total.
- `why` / `how_to_avoid` are plain text with two inline marks: `*…*` = emphasis (rendered in
  Fraunces italic) and `[n]` = citation of `sources[n-1]` (rendered as a footnote marker whose
  preview shows that source's `passage`).
- `sources[].passage` is the retrieved text the explanation was grounded on. Only the passages the
  text cites are listed, numbered to match its `[n]` marks.
- `examples[].note` is one **deterministic** sentence about the opponent's reply, built with
  python-chess from the user's pieces the reply attacks (template, no AI) — see "Line notes" below;
  `examples[].arrows` are the threats to draw on the example diagram (the position after the reply).
- `games[].trace`: White's evaluation in centipawns after each half-move, start included, mate
  capped at ±1000 — draws the small trace on the Analysing screen. Complete for finished games;
  for the game being analysed, the evaluations so far (the trace grows as the worker goes).
- `games[].plies`: total half-moves in the game, from the PGN (known before analysis), so a
  growing trace can be drawn at its final scale.
- `examples[].grade`: grade of the played move (shown as its glyph, e.g. `Nxe5??`).
- `missed_tactics`: winning tactics the user had but didn't play, most frequent first; `count` is
  the number of times.
- `openings`: only openings played at least 4 times, most played first. `score` = (wins + ½ draws)
  / games.
- `games[].opening` is the opening family from chess.com's link, or "Unknown opening" when the game
  has none; those games are left out of `openings`.
- `punishing_line` starts with the opponent's reply to `played`.

### When failed
```json
{ "id": "r_8f3k2", "status": "failed",
  "error": "no_games", "detail": "No rapid games found for adityakanade. Try 'Both'." }
```
Failure codes: `no_games` (no games found in the last 24 months), `chesscom_unavailable`,
`analysis_failed`.
- A report never fails because of the AI. If the AI is unavailable, the weakness cards use fixed
  glossary text and `notes` says so.
- A single game that can't be analysed is skipped with a note. The report fails with
  `analysis_failed` only if more than half of its games fail.

## 3. Get one game — `GET /api/reports/{id}/games/{game_id}`

Everything is computed in the single analysis pass that runs while the report is being made, so
this is a plain read: errors, positive grades, lines and notes are all present. `grading` is always
`complete`. It is kept so the frontend's existing re-poll logic needs no change. (Earlier drafts
had a second, deeper pass started by this request; the measured single pass made it unnecessary.)

```json
{
  "id": "g_1",
  "white": "adityakanade", "black": "player123",
  "user_color": "white",
  "result": "1-0",
  "opening": "Italian Game",
  "url": "https://www.chess.com/game/live/123456789",
  "start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "grading": "complete",
  "moves": [
    {
      "ply": 35, "move_number": 18, "color": "white",
      "san": "Bc4",
      "fen_after": "r1bq1rk1/pp2bppp/2n1pn2/3p4/2BP4/2N2N2/PP3PPP/R1BQ1RK1 b - - 1 18",
      "eval": { "cp": -310 },
      "grade": "blunder",
      "themes": ["hangingPiece"],
      "better_line": ["Be2", "Nf6", "O-O", "Bd6", "Re1"],
      "refutation_line": ["Nxc4", "dxc4", "Qd4"],
      "better_note": "18. Be2 keeps the position level (+0.2).",
      "refutation_note": "Hanging piece: this line wins your bishop.",
      "refutation_arrows": [["c4", "e3"]]
    }
  ]
}
```
- Every move of **both players** is graded (like chess.com); weakness cards only count the user's.
- `grade` is `null` only for a game that couldn't be analysed (skipped).
- `better_line` / `refutation_line` are filled for error moves; `refutation_line` starts with the
  opponent's reply to `san`. Lines are 3–5 moves.
- `eval` is the evaluation after the move (drives the eval bar).
- `better_note` / `refutation_note`: one short **deterministic** sentence per line (templates
  below, no AI; may be `null`). They are worded for this report's player: "your" for their own
  moves, "White's" / "Black's" for the opponent's. The same game can appear in both players'
  reports.
- `refutation_arrows`: threats to draw once the refutation has played out, as `[from, to]` square
  pairs (e.g. the two targets of a fork); may be `null`.
- "Show why it's bad" plays `san` followed by `refutation_line`, from the position before the move.

---

## Line notes — deterministic templates (no AI)
Built by the backend with python-chess and the engine's evaluations; the wording is fixed so it can
never invent moves or ideas. First matching rule wins.

The facts are saved with the analysis, and the sentence is built when the game is read. "your"
below becomes "White's" / "Black's" when the move belongs to the report player's opponent, e.g.
"Hanging piece: this line wins Black's bishop."

**`refutation_note`** (for the line "played move → refutation"). When the tagger named the tactic,
the sentence starts with its name, e.g. "**Fork:** …"; otherwise the sentence appears on its own.

| Rule | Sentence |
|---|---|
| The line ends in checkmate | "{Theme}: this line ends in checkmate." |
| The line wins material from the user (net loss ≥ 2 pawns) | "{Theme}: this line wins your {most valuable piece lost}." |
| The reply attacks two or more of the user's pieces | "{Theme}: after {reply}, your {piece} on {sq} and your {piece} on {sq} are both attacked." |
| Otherwise | "This drops your winning chances from {before}% to {after}%." |

**`better_note`** (for the better line), from the mover's win % after the better move:
| Win % | Sentence |
|---|---|
| ≥ 60 | "{move} keeps your advantage ({eval})." |
| 40–60 | "{move} keeps the position level ({eval})." |
| < 40 | "{move} limits the damage ({eval})." |

**`examples[].note`** (report examples): "{reply} attacks your {piece} on {sq} and your {piece} on
{sq}." (one or two pieces, most valuable first); with a single target: "{reply} wins your {piece}."
The reply carries its grade glyph (e.g. `Qg5!`) only if the opponent actually played that move in
the game; a move from the engine's line that never happened has no grade, so no glyph.

---

## Errors (all endpoints)
```json
{ "error": "username_not_found", "detail": "No chess.com player called 'xyz'." }
```
| HTTP | `error` | When |
|---|---|---|
| 404 | `username_not_found`, `report_not_found`, `game_not_found` | Unknown user / id. A malformed id (not `r_…` / `g_…`) is also a 404 |
| 422 | `invalid_input` | Bad username format, `games` not 10 / 20 / 30 / 50, unknown `time_control` |
| 422 | `no_games` | The player has no games in that time control |
| 503 | `chesscom_unavailable` | chess.com isn't responding |
| 503 | `busy` | Too many reports are already running |
| 500 | `internal_error` | Anything unexpected; never includes a stack trace |

- `detail` is always a human-readable sentence; the frontend shows it as is.
- Every response carries an `X-Request-ID` header that matches the server's log lines.
- `429 rate_limited` is not used in the first cut (no per-visitor limits). It will be added before
  any public launch.

## Operations (not used by the UI)
These are reached directly on the API's port (localhost), not through the website.

| Endpoint | Returns |
|---|---|
| `GET /health` | Database, library loaded, worker heartbeats |
| `GET /metrics` | Reports by status and time to done; queue length and oldest wait; games analysed and engine seconds per game; cache hit rates; AI calls, tokens and cost per report; fallback rate; average AI time |
