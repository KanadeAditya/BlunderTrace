# BlunderTrace — Product Plan

Planning happens in stages; nothing is coded until all stages are agreed.

| Stage | Topic | Status |
|---|---|---|
| 1 | MVP features | **Signed off** |
| 2 | UI/UX flow | In progress |
| 3 | Tech stack & architecture (frontend/backend, repos, hosting) | Not started |
| 4 | Code specifics (structure, Stockfish pipeline, RAG pipeline, database) | Not started |

Guiding principle: **bloat-free.** Every feature must earn its place; no toggles or options that
don't clearly help the user.

---

## Stage 1 — MVP features

### What BlunderTrace is
Enter a chess.com username → see the **3 mistakes you make most often**, shown in **your own
games**, with **why it happens** and **how to stop**, backed by cited chess theory. Every move
shown is checked against Stockfish.

- AuditChess tells you *what* your weaknesses are; CARA grades one game at a time.
- BlunderTrace tells you *why* they keep happening and *how to fix them*.

### Features in the MVP

**Core: weakness report**
1. **Input:** chess.com username + time control (Rapid / Blitz / Both).
2. **Number of games:** default 20; user can choose (e.g. 10–50).
3. **Summary:** games analysed, W/D/L, blunders / mistakes / misses per game.
4. **Top 3 weakness cards**, ranked by how often each theme occurs (Lichess theme names: hanging
   piece, fork, pin, …). Each card:
   - theme + count ("Hanging piece: 9 times in 20 games")
   - 2–3 examples from the user's games: board, their move, the better move, the opponent's
     punishing reply
   - **why it happens:** short explanation grounded in those examples
   - **how to avoid it:** a practical habit drawn from retrieved theory
   - **sources:** links to the passages used
5. **Tactics you allowed + tactics you missed:** themes are counted both for what the opponent
   could do after your error and for winning tactics you didn't play.
6. **Opening card:** results per opening ("You score 35% in the Sicilian as White"). From game
   data; no engine, no AI.
7. **Analysed games list:** every analysed game, with its error count, so the user can open one.
8. **Saved report link:** each report has its own URL (`/report/<id>`); reopening is instant;
   re-running the same username shortly after reuses the result.
9. **Clear error states:** username not found, too few games, analysis failed.

**Game view (opened on click)**
10. **Read-only replay:** board + move list; step with ◀ ▶ / arrow keys or click a move. Users
    never move pieces.
11. **Every move graded:** brilliant, great, best, excellent, good, inaccuracy, mistake, blunder,
    miss, shown as icons in the move list.
12. **Popup on an error move**, with two buttons:
    - **Show better move:** Stockfish's best move from that position, continuing 3–5 moves for both
      sides, animated on the board.
    - **Show why it's bad:** the move actually played, followed by the opponent's punishing line.
    - A **Back** button returns to the real game position. Lines are always full engine strength
      (no rating toggle) and replay instantly from saved analysis.

### How analysis is staged (only compute what the user needs)
| Stage | When | What it does |
|---|---|---|
| A — bulk | User clicks Analyse | Every move of every game checked; **errors (blunders, mistakes, misses) found and fixed permanently**; themes tagged; cards + game list built. Depth set high enough for reliable errors — accuracy over speed. |
| B — game | User opens a game | Deeper pass on that game only: adds **positive grades** (brilliant, great, best, excellent, good) and saves the **better-move** and **refutation** lines. **Never re-grades an error**, so cards and game view always agree. Saved; reopening is instant. |
| C — popup | User clicks a button | Replays the saved lines; no new engine work. |

### Not in the MVP
- Question box per example (the full RAG Q&A loop) — first candidate after the MVP
- Drills / puzzles, accounts, saved history across users, Lichess usernames, PGN paste
- Analysing hundreds of games, positional themes (pawn-shield holes, structures)
- Rating-limited ("realistic opponent") lines, user-movable pieces

---

## Decisions log
| Decision | Why |
|---|---|
| No board state in embeddings; retrieval uses concept queries | Pre-build research (`pre_build_research/README.md`) |
| Theme tagging uses lichess-puzzler's tagger (`ornicar/lichess-puzzler`, AGPL-3.0) → **BlunderTrace is licensed AGPL-3.0** | Fastest, proven on millions of puzzles; same theme names as our corpus and tests |
| Errors are fixed by the bulk pass; the game pass only adds | Cards and game view must never disagree |
| Engine lines always at full strength, no toggle | Consistent, trustworthy, teaches the right idea; bloat-free |
| "Show why it's bad" alongside "Show better move" | Seeing why a move fails is the key learning moment |
