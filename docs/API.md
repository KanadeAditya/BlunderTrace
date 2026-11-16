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
  `blunder`, `miss`. Errors = `inaccuracy`, `mistake`, `blunder`, `miss`.
- **Themes** use Lichess puzzle-theme keys (`hangingPiece`, `fork`, `pin`, …) with a display `name`.
- Report and game **statuses**: `queued` → `running` → `done`, or `failed`.

---

## 0. Look up a player — `GET /api/players/{username}`

Called by Home while the user types (debounced), to show the player preview and the game counts on
the time-control buttons. Cached briefly on the server.

```json
{
  "username": "knightowl_42",
  "avatar_url": "https://images.chesscomfiles.com/…/avatar.png",
  "ratings": { "rapid": 1184, "blitz": 1052 },
  "games": { "rapid": 142, "blitz": 380 }
}
```
- `avatar_url` may be `null`; `ratings` omits time controls never played.
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
| `games` | integer 10–50, default 20 |

Responses:
- `202` `{ "id": "r_8f3k2", "status": "queued" }` — analysis started.
- `200` `{ "id": "r_8f3k2", "status": "done" }` — the same username + settings were analysed
  recently; the existing report is reused.
- `404` `username_not_found` — checked immediately, before any analysis starts.

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
          "played": "Bc4", "better": "Be2",
          "punishing_line": ["Nxc4", "dxc4", "Qd4"],
          "note": "4… Qg5! attacks the knight and g2 at once.",
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
- `weaknesses`: top 3, most frequent first (tactics the user **allowed**). `count` and examples
  only include the user's own moves.
- `why` / `how_to_avoid` are plain text with two inline marks: `*…*` = emphasis (rendered in
  Fraunces italic) and `[n]` = citation of `sources[n-1]` (rendered as a footnote marker whose
  preview shows that source's `passage`).
- `sources[].passage` is the retrieved text the explanation was grounded on.
- `examples[].note` is one sentence about the opponent's reply (shown under the example);
  `examples[].arrows` are the threats to draw on the example diagram (the position after the reply).
- `games[].trace` (finished games only): White's evaluation in centipawns after each half-move,
  start included, mate capped at ±1000 — draws the small trace on the Analysing screen.
- `missed_tactics`: winning tactics the user had but didn't play, most frequent first.
- `score` = (wins + ½ draws) / games.
- `punishing_line` starts with the opponent's reply to `played`.

### When failed
```json
{ "id": "r_8f3k2", "status": "failed",
  "error": "no_games", "detail": "No rapid games found for adityakanade. Try 'Both'." }
```
Failure codes: `no_games`, `chesscom_unavailable`, `analysis_failed`.

## 3. Get one game — `GET /api/reports/{id}/games/{game_id}`

The first request starts the game's deeper analysis (stage B). While `grading` is `pending`, errors
are already filled in; positive grades and lines arrive later — the frontend re-polls until
`grading` is `complete`.

```json
{
  "id": "g_1",
  "white": "adityakanade", "black": "player123",
  "user_color": "white",
  "result": "1-0",
  "opening": "Italian Game",
  "url": "https://www.chess.com/game/live/123456789",
  "start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "grading": "pending",
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
      "better_note": "Keep the bishop defended; the position stays balanced.",
      "refutation_note": "After 18… Nxc4 the bishop is simply lost.",
      "refutation_arrows": [["c4", "e3"]]
    }
  ]
}
```
- Every move of **both players** is graded (like chess.com); weakness cards only count the user's.
- `grade` is `null` and lines are `null` until available.
- `better_line` / `refutation_line` are filled for error moves; `refutation_line` starts with the
  opponent's reply to `san`. Lines are 3–5 moves.
- `eval` is the evaluation after the move (drives the eval bar).
- `better_note` / `refutation_note`: one short sentence explaining each line (may be `null`).
- `refutation_arrows`: threats to draw once the refutation has played out, as `[from, to]` square
  pairs (e.g. the two targets of a fork); may be `null`.
- "Show why it's bad" plays `san` followed by `refutation_line`, from the position before the move.

---

## Errors (all endpoints)
```json
{ "error": "username_not_found", "detail": "No chess.com player called 'xyz'." }
```
| HTTP | `error` | When |
|---|---|---|
| 404 | `username_not_found`, `report_not_found`, `game_not_found` | Unknown user / id |
| 422 | `invalid_input` | Bad username format, `games` outside 10–50, unknown `time_control` |
| 429 | `rate_limited` | Too many requests from one IP |
| 503 | `service_unavailable` | Stockfish or the LLM is down |

## Operations (not used by the UI)
| Endpoint | Returns |
|---|---|
| `GET /health` | DB and Stockfish checks |
| `GET /metrics` | Requests, errors, latency, tokens, cache hit rate, cost per report, RAG vs long-context cost |
| `GET /cache/stats` | Cache hits, misses, entries |
