# BlunderTrace — Product Plan

Planning happens in stages; nothing is coded until all stages are agreed.

| Stage | Topic | Status |
|---|---|---|
| 1 | MVP features | **Signed off** |
| 2 | UI/UX flow & design | **Signed off** — direction A, *The Annotated Book*; full spec in [`docs/DESIGN.md`](DESIGN.md) |
| 3 | Tech stack, architecture & RAG pipeline | **Signed off** (refined in stage 4) |
| 4 | Code specifics (folder structure, API contract, database schema, build order) | **Signed off.** Backend design of record: [`docs/BACKEND.md`](BACKEND.md) |

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
   - theme + count ("Hanging piece: 9 of 20 games", the number of games where it happened)
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

**First cut = features 1–12.** Publish that, then build the post-launch items (see the end of this
document), each tracked as a GitHub issue.

### How analysis works
| When | What happens |
|---|---|
| User clicks Analyse | **One engine pass** over every move of every game (two best moves, 100,000 positions per move). It finds the errors and the positive grades (brilliant, great, best, excellent, good), saves the better-move and refutation lines and notes, tags themes, and builds the cards and game list |
| User opens a game | A plain read: everything was computed in the pass above, so it is instant |
| User clicks a line button | Replays the saved lines; no new engine work |

An earlier plan had a second, deeper pass when a game was opened. Measurements showed the single
pass costs only ~5% more than an errors-only pass and finds ~90% of "great" moves
(`pre_build_research/engine_timing/README.md`), so the second pass was dropped.

### Not in the MVP
- Coach chat (first post-launch item, see "Post-launch")
- Drills / puzzles, accounts, saved history across users, Lichess usernames, PGN paste
- Analysing hundreds of games, positional themes (pawn-shield holes, structures)
- Rating-limited ("realistic opponent") lines, user-movable pieces

---

## Stage 2 — UI/UX flow

> **Superseded in detail by [`docs/DESIGN.md`](DESIGN.md)** (approved design, pixel-perfect spec,
> reference files in `docs/design/reference/`). Final screens: Home → Analysing (“Contents”) →
> Report → Game view. The notes below are the original flow proposal, kept for history.

Four screens, no menus, no settings, no sign-in. One dark theme (no theme switching).
Desktop-first; layouts stack on phones (board above move list), no phone-specific features.

```
Home ──Analyse──▶ Analysing ──done──▶ Report ──click a game / example──▶ Game view
                                        ▲                                    │
                                        └──────────── Back to report ────────┘
```

### 1. Home (`/`)
- One form: chess.com username, time control (Rapid / Blitz / Both), number of games (default 20),
  **Analyse**.
- One line under the button: "We'll analyse your last 20 games, about N minutes" (updates with
  the game count).

### 2. Analysing (`/report/<id>`, while running)
- Progress bar ("12 / 20") and a list where **each game ticks off with its error count** as it
  finishes.
- The URL is already the report link: closing the tab and returning resumes or shows the result.
- When done, the page becomes the report.

### 3. Report (`/report/<id>`)
One scrolling page, most important first:
1. **Header:** username · games · time control · W/D/L · blunders per game.
2. **Top 3 weaknesses** (tactics you allowed): card #1 open, #2–#3 collapsed. Each card: why it
   happens · how to avoid it · 2–3 examples (board thumbnails) · sources. Clicking an example opens
   the game view **at that move**.
3. **Tactics you missed:** compact row of counts (e.g. Fork 5× · Hanging piece 4× · Pin 2×).
4. **Openings:** score per opening and colour.
5. **Your games:** table (date, opponent, colour, result, opening, error counts); click → game view.

### 4. Game view (`/report/<id>/game/<n>`)
- **Read-only board** with an **evaluation bar**; ◀◀ ◀ ▶ ▶▶ buttons and arrow keys; clickable move
  list with a grade icon on every move.
- **Side panel under the move list** (never covers the board): on an error move it shows the grade
  and two buttons, **Show better move** / **Show why it's bad**.
- **Line playback:** board animates 3–5 moves (~1 s each) with arrows; a banner shows the line and
  **↩ Back to game**.
- Opening a game is instant: all grades and lines come from the analysis pass made with the report.
- "← Back to report" at the top.

### Error and empty states
| Situation | What the user sees |
|---|---|
| Username not found | Inline message on Home |
| No games in that time control | Message suggesting "Both" |
| Fewer than ~5 games | Report still runs, with a note that patterns are weak |
| Analysis failed | Message with **Retry** |

---

## Stage 3 — Tech stack, architecture & RAG pipeline

### Stack
| Area | Choice |
|---|---|
| Frontend | **Vue 3 + Vite**, TypeScript, `<script setup>` (Composition API) |
| Repo | **One repo**: `frontend/` + `backend/`, one `docker-compose.yml` |
| Backend | Python 3.12 + `uv`, FastAPI, Pydantic / pydantic-settings |
| Database | PostgreSQL + pgvector (app data, corpus and vectors in one DB) |
| Chess | python-chess, **Stockfish on the server**, lichess-puzzler tagger (AGPL-3.0) |
| LLM / RAG | LangChain + **LangGraph**, Claude Haiku 5.5 (main), gpt-6-luna (fallback), `text-embedding-3-small`. Was gpt-4o-mini, which shuts down 14 Jan 2027 |
| Observability | Structured JSON logs, `/metrics`, `/health`, LangSmith |
| Build order | **Data shapes (API contract) → frontend on sample data → backend to match** |

Confirmed in stage 4 (details in [`docs/BACKEND.md`](BACKEND.md)):
- Tailwind CSS; chessground board + chess.js.
- A modular monolith started in two roles, `api` and `worker` (×N, default 2), with the job queue
  in Postgres (Procrastinate) and the frontend polling progress.
- Caddy serves the Vue app and passes `/api` to the API.
- Async code everywhere (FastAPI routes, Procrastinate tasks, the database, chess.com, Stockfish and
  AI calls), like Node.
- No hosting for now: `docker compose up` runs everything.

```
Browser (Vue) ──▶ Caddy ──┬── Vue files
                          └── /api ──▶ FastAPI (api) ──▶ Postgres + pgvector
                                                          (reports, games, library + vectors,
                                                           caches, AI call log, job queue)
                          worker ×N: chess.com → Stockfish → grading + tagger → RAG → LLM ──┘
```

### RAG pipeline — first cut (course chapter in brackets)

Refined in stage 4; the full version is in [`docs/BACKEND.md`](BACKEND.md), section 8.

**1. Ingestion (built once by a script, shipped with the project)**
- **Sources:** Wikipedia, Wikibooks and the Lichess theme glossary from `pre_build_research/`
  (1,338 passages); fix the missing *Fork* glossary row.
  - Dropped: the Lichess studies (move-by-move narration, unclear licence) and the Gutenberg books
    (never relevant in the research).
- **Chunking:** structure-aware. Consecutive paragraphs of the same section are merged up to ~250
  words; no passage crosses a section [Ch 5, 10]. Each passage is prefixed with "Article ›
  Section:".
- **Concept tags:** an AI tags each passage once, at build time, from the 11 theme names
  (validated). Tags are shipped, so the app never calls an AI for them [Ch 7].
- **Embeddings:** `text-embedding-3-small` (1536 dims), batched, cached by text fingerprint
  [Ch 6, 17].
- **Shipped files:** passages, tags, vectors and a checksum manifest. The app loads them into
  Postgres on startup with no API key needed.
- **Storage:** one Postgres table (text, source, url, tags, embedding, full-text column). No vector
  index while the library is small: an exact search is ~1 ms [Ch 16].

**2. Retrieval**
- **Metadata filter** by theme tag first, falling back to the whole library if too few passages are
  tagged [Ch 7].
- **Hybrid search:** Postgres full-text search + pgvector cosine (`<=>`), merged with **weighted
  Reciprocal Rank Fusion** [Ch 11]. (Postgres FTS avoids the BM25 rebuild problem.)
- Retrieval results cached per theme [Ch 17].

**3. Card explanations (LangGraph graph, per top theme)** [Ch 22, 25]
```
retrieve → grade relevance → (irrelevant? rewrite query, retry ≤ 2 → else fallback to theme definition)
        → generate (grounded prompt + citations, with engine facts: move, better move, punishing line)
        → output validator (every move legal and in Stockfish's lines; else regenerate once)
```
- Grounded prompt: "use ONLY the context; say so if it isn't there" + source citations [Ch 2, 8].
- Results cached per theme + examples [Ch 22].

**4. Reliability around every LLM call**
- Token budget pre-flight check [Ch 12].
- Retries with exponential backoff + jitter; **circuit breaker**; **fallback** Claude Haiku 5.5 →
  gpt-6-luna → graceful error node [Ch 19, 22].

**5. Observability**
- Structured JSON logs; metrics (requests, errors, latency, tokens, cache hit rate) [Ch 19].
- `/health` (DB, library, workers) and `/metrics` [Ch 22]. LangSmith tracing is
  optional, switched on by env vars [Ch 13].
- **Cost tracking:** every AI call is logged (tokens, cost, time, outcome), and `/metrics` shows
  cost per report. There is no comparison against stuffing the whole library into a prompt; that
  would be a made-up competitor [Ch 24].

**6. Quality and delivery**
- Test pyramid: fast deterministic unit tests (no LLM), integration tests with fake LLMs and a real
  test database [Ch 23].
- Retrieval check: for each of the 11 fixed theme queries, the top 5 under vector-only vs hybrid,
  judged blind [Ch 13].
- Docker: non-root user, layer caching, HEALTHCHECK, pinned Stockfish 19; compose with Caddy, the
  API, workers and Postgres + pgvector [Ch 23].

### Course concepts deliberately not used
| Concept | Why not |
|---|---|
| PII masking [Ch 21] | Chess games contain no personal data; usernames are public |
| Model routing [Ch 18] | One kind of LLM task; one small model handles it |
| Contextual retrieval [Ch 24] | The "Article › Section:" prefix gives most of the benefit without AI-written text; the only AI step at ingestion is tagging |
| Late chunking [Ch 25] | Needs a different embedding model; chunks are short and self-contained |
| GraphRAG [Ch 26] | No multi-hop entity questions in this product |
| Multimodal / ColPali [Ch 27] | No PDFs, tables or images in the corpus |
| Cross-encoder reranking [Ch 27] | Heavy dependency; the LLM relevance grader fills the role |

---

## Stage 4 — Code specifics

### 4.1 API contract — **agreed**
See [`docs/API.md`](API.md): player lookup plus 3 product endpoints (start analysis, get report,
get game), and `/health`, `/metrics`. Both players' moves are graded in the game view; weakness
cards count only the user's moves.

### 4.2 Move grading — **agreed**
Based on **winning chances**, as Lichess does (formula from `lichess-org/scalachess` `eval.scala`,
MIT; thresholds from `lichess-org/lila` `Advice.scala`):

```
win% = 50 + 50 × (2 / (1 + e^(−0.00368208 × cp)) − 1)      cp capped at ±1000; mate counts as the cap
loss = win% before the move − win% after it, from the mover's point of view
```

| Grade | Rule | Origin |
|---|---|---|
| Blunder | loss ≥ 15 points | Lichess |
| Mistake | loss ≥ 10 points | Lichess |
| Inaccuracy | loss ≥ 5 points | Lichess |
| (mate) | Allowing a forced mate = blunder (mistake/inaccuracy only if already losing by > 7 / > 10 pawns); losing a forced mate = blunder (unless still > 7 / > 10 pawns up) | Lichess mate rules |
| Miss | An error **and** the tagger finds a winning tactic (≥ 2 pawns or mate) in the better line that wasn't played **and** the move itself allowed no tactic (a move that allowed one keeps its error grade) | Ours |
| Best | Played the engine's top move | Ours |
| Excellent | loss < 2 points | Ours |
| Good | loss 2–5 points | Ours |
| Great | Best move **and** the second-best move is ≥ 10 points worse (the "only good move"; not when it was the only legal move; MultiPV 2 in the single analysis pass) | Ours |
| Brilliant | Great or best **and** tagger flags `sacrifice` **and** mover was below 90% before the move | Ours |

Our own thresholds (miss, excellent, good, great, brilliant) are constants in one module and get
tuned on real games.

### 4.3 Theme tagging — **agreed, verified**
- lichess-puzzler's `tagger/cook.py` (AGPL-3.0) is vendored into the backend with its license.
- Input: position before the error → the error → the punishing line (from Stockfish); the "solver"
  is the opponent. For **missed** tactics: the position before the error → the better line.
- A theme is only counted when the line **wins ≥ 2 pawns or mates** (same bar as Lichess puzzles).
- Verified on 2,000 Lichess puzzles: 0 errors; precision 96–100% and recall 92–100% against
  Lichess's labels on all 11 themes we use (fork, pin, skewer, discovered attack, hanging piece,
  back-rank mate, trapped piece, exposed king, advanced pawn, quiet move, defensive move). Lichess
  labels come from the same code, so this verifies our wiring rather than the labels themselves.

### 4.4 RAG's role in the first cut
Only the **3 weakness cards' text** ("why it happens", "how to avoid it", sources) comes from RAG
(stage 3 pipeline): count themes → retrieve passages for "how to avoid <theme>" (tag filter +
hybrid search + RRF) → grade / rewrite → generate from engine facts + passages → validate moves →
cache. Everything else (engine, grading, tagging, counting) is deterministic.

### 4.5 Database schema — **decided** (full columns in [`docs/BACKEND.md`](BACKEND.md), section 5)
PostgreSQL + pgvector, accessed with plain SQL (psycopg). Every row is checked by Pydantic models.
Tables are created on startup if missing; there are no migrations, and big changes get a
hand-written script. Games are stored once and shared between reports, so re-analysing a user reuses
already-analysed games.

| Table | One row is… | Key columns |
|---|---|---|
| `reports` | One analysis request | id, username, time_control, games_requested, status, error, notes (JSON), result (JSON: summary, weaknesses, missed tactics, openings), timestamps |
| `games` | One chess.com game | id, chesscom_url (unique), players, ratings, result, time_class, played_at, opening, pgn, status, **moves (JSON, one object per half-move)**, trace, error_counts, engine version |
| `report_games` | Game ↔ report link | report_id, game_id, position, user_color |
| `corpus_chunks` | One library passage | id, source, title, section, url, text, tags[], embedding vector(1536), tsv (GIN) |
| `concept_queries` | One theme's fixed query | theme, query, embedding |
| `cache` | One cached answer | key, value (JSON), etag, expires_at, hits |
| `llm_calls` | One AI call | report_id, purpose, model, tokens in/out, cost_usd, latency_ms, outcome |

The job queue is Procrastinate's own 4 tables, in the same database.

### 4.6 Folder structure — **decided** (details in [`docs/BACKEND.md`](BACKEND.md), section 4)
```
BlunderTrace/
├── docker-compose.yml        db (pgvector) · api · worker ×N · caddy (serves the built frontend)
├── backend/
│   ├── pyproject.toml · Dockerfile
│   ├── app/
│   │   ├── api/ · reports/ · chesscom/ · engine/ · analysis/ · rag/ · jobs/ · db/
│   │   ├── vendor/lichess_puzzler/   (+ its LICENSE)
│   │   ├── config.py · main.py (api) · worker.py (worker)
│   ├── scripts/build_library.py · data/library/   (shipped passages, tags, vectors)
│   └── tests/
├── frontend/
│   └── src/                  api/ · pages/ · components/ · lib/ · content/
├── pre_build_research/       research, incl. engine_timing/ (Stockfish measurements)
└── docs/                     PLAN.md · DESIGN.md · API.md · BACKEND.md
```
Dependencies point one way (`api` → `reports` → the rest), checked by import-linter.

### 4.7 Build order
**Phase 0 — Setup** ✅ done
1. Restructure the repo into `backend/` + `frontend/`; scaffold Vue 3 + Vite + TypeScript;
   docker-compose with Postgres + pgvector; add the AGPL-3.0 `LICENSE`.

**Phase 1 — Frontend on sample data** (also the visual review of stage 2) ✅ done
- **First: design session** — theme, colours, typography and every UX detail are decided before any screen is built.
2. Typed API client + sample JSON for every state in `docs/API.md` (running, done, failed;
   game pending / complete).
3. Home page.
4. Report page: analysing state (simulated polling), report (summary, cards, missed tactics,
   openings, games table), failed state.
5. Game page: board, move list with grades, eval bar, side panel, line playback + Back.
   → **Stage 2 sign-off** on the real screens.

**Phases 2–4 — Backend** (12 steps; full list in [`docs/BACKEND.md`](BACKEND.md), section 16)
6. Setup → database → chess.com → chess core (engine, grading, tagger, lines, notes).
7. Jobs and reports. **After this step the whole product works end to end with real analysis**
   (cards use fixed text).
8. Library build (AI tags + vectors, paid, with approval) → retrieval + blind check → AI writing
   flow.
9. Monitoring → Docker (Caddy, pinned Stockfish, worker limits) + load test (1 / 2 / 4 workers) → frontend
   wiring → docs.

**Phase 5 — Publish**
10. README (setup, architecture, research, decisions, results), screenshots.
11. Publish the images to GitHub Container Registry, built by hand with no CI.
    - The images: the backend (shared by the API and the workers) and Caddy with the built frontend.
    - Both Intel and ARM, with version tags.
    - The library is baked into the backend image.
    - Add a release compose file that pulls the images, and a "Run it yourself" README section,
      which includes the link to Stockfish's source.
12. Hosting decision + deploy; file the post-launch GitHub issues.

---

## Post-launch (each becomes a GitHub issue after the first cut is published)

**1. Coach chat** — ask questions only about your own report (themes, examples, specific errors);
simple, beginner-friendly answers grounded in the corpus and saved analysis, with sources;
off-topic questions politely redirected; no new engine analysis. Pipeline (LangGraph):
```
input limits [Ch 20] → prompt-injection sanitizer [Ch 21] → scope guard (only this report / chess learning)
  → rate limit [Ch 22] → response cache [Ch 17, 22] → rewrite follow-ups using chat history [Ch 8]
  → multi-query retrieval [Ch 15] → hybrid retrieval → grade / rewrite (≤ 2) [Ch 25]
  → generate (grounded, citations) → output validator (moves checked against saved lines) → answer
```

**2. Retrieval improvements**
- Parent-document retrieval (search paragraphs, return the full section) [Ch 15]
- Embedding dimension experiment, 1536 vs 512 on the eval set [Ch 17]
- Recursive vs semantic chunking benchmark [Ch 14]
- Contextual compression [Ch 15]

**3. Phone layout review** — the first cut is desktop-first and only stacks on phones; review the
order and sizing of each screen on a phone (e.g. board vs form first on Home).

**4. Analyse games in the browser** (Stockfish running on the user's device, like AuditChess). The
first cut runs Stockfish on the server; this was chosen to avoid changing the API and the frontend
now, and is worth revisiting.
- **Why:** every user brings their own CPU, so there is no shared waiting line when many people use
  it at once, and the server needs almost no CPU. That suits a small or free host.
- **What it changes:** API.md (the browser sends engine results to the server instead of the server
  analysing), the Analysing screen (progress comes from the browser), a Web Worker running Stockfish
  compiled to WebAssembly, and an engine download on the first visit (Lichess's is about 10 MB).
- **Problems to solve:** phones are slow and drain the battery; work stops if the tab is closed (so
  save results per game); results come from the user's machine, so they must never be reused for
  other users (shared caches); every device must use the same engine settings for repeatable
  results.
- **Middle path:** analyse in the browser when the device is capable, on the server otherwise.
- **Prepared for in the first cut:** the Stockfish step is its own module that produces "engine
  results for a game", so a browser source can later produce the same shape and plug in.
- **Revisit if** hosting ends up on a server with a small CPU.

**5. AI notes for "Show better move" / "Show why it's bad"**, written on click, with RAG. The
first cut uses fixed templates, which name the tactic and say "This drops your winning chances
from 55% to 30%". This item adds a coach-style note, generated only when the user clicks one of
the two buttons.
- **Flow:**
  1. Code gathers **verified facts** from the engine, python-chess and the tagger: the move, the
     line, the pieces attacked, material won or lost, win% before and after, and the theme.
  2. Retrieval adds the theme's theory passages, which are already cached per theme.
  3. The AI only **rephrases those facts** into a short note with a citation. It is never asked to
     analyse the board.
  4. The move checker validates the note, and any claim not in the facts list is rejected.
- **Showing it:**
  - The line plays immediately.
  - The template note shows at once and is replaced by the AI note when it arrives (~1–3 s).
  - Notes are cached per game, move and button.
  - If the AI fails, the template note stays.
- **What it changes:** a new endpoint for the note of one move and button, a loading state in the
  side panel, and `llm_calls` logging.
- **Why not in the first cut:** a language model describing a specific position is where it is
  least reliable. This needs the facts-only design above and real testing before users see it.

**6. Before any public launch**
- Per-visitor rate limits (slowapi, using the real visitor IP that Caddy passes on). The first cut
  only has the generous "busy" limit.
- Check the content licences once more (Wikipedia and Wikibooks are CC BY-SA: attribution).
- Link to Stockfish's source in the README (GPL).
- Choose hosting. A small server fits about one worker per 2 GB of RAM (Stockfish 19 uses ~360 MB).

**7. Queue position and wait estimate on the Analysing screen.** When the line is busy, show e.g.
"2 reports ahead of you, about 3 minutes" instead of a progress bar that looks frozen.
- **What it changes:**
  - a small backend field (games ahead × ~11 s ÷ workers);
  - an API.md field;
  - a designed element on the Analysing screen.
- **When:** build it once the capacity warnings show people actually waiting.

---

## Decisions log
| Decision | Why |
|---|---|
| No board state in embeddings; retrieval uses concept queries | Pre-build research (`pre_build_research/README.md`) |
| Theme tagging uses lichess-puzzler's tagger (`ornicar/lichess-puzzler`, AGPL-3.0) → **BlunderTrace is licensed AGPL-3.0** | Fastest, proven on millions of puzzles; same theme names as our corpus and tests |
| One analysis pass grades everything (MultiPV 2, 100,000 positions per move); no second pass when a game opens | Measured on real games: ~5% more time than errors-only, ~90% of "great" moves found, every blunder caught (`pre_build_research/engine_timing/`) |
| Engine lines always at full strength, no toggle | Consistent, trustworthy, teaches the right idea; bloat-free |
| "Show why it's bad" alongside "Show better move" | Seeing why a move fails is the key learning moment |
| Error actions in a side panel, not a popup | A popup would cover the position being studied |
| Evaluation bar in the game view | Cheap (evaluations already exist); makes swings visible |
| One dark theme, desktop-first, stacks on phone | Bloat-free; no theme or mobile-specific work |
| Report is one scrolling page, not tabs | Most important information first; fewer clicks |
| Vue 3 + Vite, one repo, Stockfish on the server, contract-first build order | User's stage 3 choices |
| First cut = features 1–12; coach chat is the first post-launch item | Publish sooner; chat brings the free-text RAG concepts (sanitizer, scope guard, conversational RAG, multi-query) afterwards |
| No contextual retrieval | The "Article › Section:" prefix gives most of the benefit; the only AI step at ingestion is tagging, done once and shipped |
| Retrieval extras moved to a post-launch roadmap | Keep the MVP lean; ship first |
| Design direction **A — The Annotated Book** (canvas: claude.ai artifact "BlunderTrace Design Directions") | User's choice: clean, bloat-free, calm game view, room to grow |
| Board: **chessground** (Lichess's board, GPL-3.0, compatible with AGPL-3.0), themed to A | Proven animation (captures, castling, promotion), arrows, highlights, resizing; restyled with CSS so it matches A |
| Components: Reka UI (Radix for Vue) primitives + our own styled kit on Tailwind v4 tokens | User likes Radix; unified custom design language, no imposed look |
| Design improvements included in the first cut: sliding moves, footnote previews of retrieved passages, A-style Analysing screen, keyboard arrows in game view | User: no shortcuts on design. Phone layout review moved to post-launch |
| Number of games: inline selector on "Last **20** games" (10 / 20 / 30 / 50), no dialog | Bloat-free: nothing extra on screen unless clicked; default stays 20 |
| Line notes (`better_note`, `refutation_note`, example notes): **deterministic templates** (python-chess + engine evals), no AI — option A; they name the tactic first ("Fork: …") and use plain wording ("drops your winning chances from 55% to 30%") | Always correct, free, can't hallucinate. AI-written notes on click, with RAG, are post-launch item 5 |
| Player lookup has no avatar | The design shows the player's initial |
| Report chapters II–III: text + "Show example" button revealing one example like chapter I | Detail on request; keeps the report calm |
| Error messages on Home: 15px, `blunder`, shake on failed submit | User's choice; no separate error design needed |
| Miss glyph: `?` in the mistake colour, named "Missed tactic" in the side panel | Chess has no classical glyph for it; easy to change later |
| Board shows the user's colour at the bottom | Half the games are played as Black |
| Pieces: **exactly the canvas set** — Noto Sans Symbols 2 chess glyphs (SIL OFL 1.1), solid shapes with A's fill/outline colours; font self-hosted (or glyphs exported to SVG) so they render identically everywhere | User's choice; license compatible with AGPL-3.0 |
| Backend design: modular monolith, Caddy, Procrastinate, psycopg, Postgres for everything, one engine pass, AI tags, hybrid retrieval, and more | Decided one at a time in conversation; the full list with reasons is in [`docs/BACKEND.md`](BACKEND.md), section 2 |
| AI models: Claude Haiku 5.5 main, gpt-6-luna fallback (both $0.10 / $0.50 per 1M tokens) | gpt-4o-mini is deprecated (shutdown 14 Jan 2027); the little comparison data there is leans toward Haiku for writing |
| Async code everywhere; Docker limits only on the workers | The usual style for a FastAPI service that mostly waits, and the style the user knows from Node. Stockfish is the only hungry part |
| Final backend check: notes worded for the reader, card count = games affected (always 3 cards when possible), "miss" only when nothing was allowed, job priorities, stuck-report check, games shared across users, keyword lists for the word search | Found by comparing the design with the first draft, the frontend and the discussions; [`docs/BACKEND.md`](BACKEND.md), section 18 |
