# BlunderTrace — Product Plan

Planning happens in stages; nothing is coded until all stages are agreed.

| Stage | Topic | Status |
|---|---|---|
| 1 | MVP features | **Signed off** |
| 2 | UI/UX flow & design | **Signed off** — direction A, *The Annotated Book*; full spec in [`docs/DESIGN.md`](DESIGN.md) |
| 3 | Tech stack, architecture & RAG pipeline | **Signed off** (small items deferred to stage 4) |
| 4 | Code specifics (folder structure, API contract, database schema, build order) | In progress |

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

**First cut = features 1–12.** Publish that, then build the post-launch items (see the end of this
document), each tracked as a GitHub issue.

### How analysis is staged (only compute what the user needs)
| Stage | When | What it does |
|---|---|---|
| A — bulk | User clicks Analyse | Every move of every game checked; **errors (blunders, mistakes, misses) found and fixed permanently**; themes tagged; cards + game list built. Depth set high enough for reliable errors — accuracy over speed. |
| B — game | User opens a game | Deeper pass on that game only: adds **positive grades** (brilliant, great, best, excellent, good) and saves the **better-move** and **refutation** lines. **Never re-grades an error**, so cards and game view always agree. Saved; reopening is instant. |
| C — popup | User clicks a button | Replays the saved lines; no new engine work. |

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
- First open: errors show immediately (from the bulk pass); other grades and lines fill in when the
  game's deeper analysis finishes (a few seconds); after that, instant.
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
| LLM / RAG | LangChain + **LangGraph**, gpt-4o-mini (primary), Claude Haiku (fallback), `text-embedding-3-small` |
| Observability | Structured JSON logs, `/metrics`, `/health`, LangSmith |
| Build order | **Data shapes (API contract) → frontend on sample data → backend to match** |

Proposed, to confirm in stage 4: Tailwind CSS; chessground board + chess.js; background analysis as
a Postgres jobs table + one worker process, with the frontend polling progress. Hosting undecided
(`docker compose up` runs everything).

```
Browser (Vue) ──HTTP/JSON──▶ FastAPI ──▶ Postgres + pgvector
                                │          (games, errors, reports, jobs, corpus + vectors)
                                └─ worker: chess.com API → Stockfish → tagger → RAG → LLM
```

### RAG pipeline — first cut (course chapter in brackets)

**1. Ingestion (one-time, offline; no LLM)**
- Sources: the corpus already built in `pre_build_research/` (Wikipedia, Wikibooks, Gutenberg,
  Lichess studies, Lichess theme glossary); fix the missing *Fork* glossary row.
- Chunking: structure-aware (split by section/heading), then recursive splitting with 10–20%
  overlap for long paragraphs [Ch 5, 10].
- **Concept tags:** each chunk tagged with Lichess theme names by deterministic keyword rules
  (metadata for filtering) [Ch 7].
- Embeddings: `text-embedding-3-small` (1536 dims), batched, cached by text fingerprint [Ch 6, 17].
- Storage: one Postgres table (content, source, url, tags, embedding, full-text column); **HNSW
  index** on the embedding [Ch 16]; idempotent upsert so re-running never duplicates [Ch 7].

**2. Retrieval**
- **Metadata filter** by theme tags first [Ch 7].
- **Hybrid search:** Postgres full-text search + pgvector cosine (`<=>`), merged with **weighted
  Reciprocal Rank Fusion** [Ch 11]. (Postgres FTS avoids the BM25 rebuild problem.)
- Retrieval results cached [Ch 17].

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
- Retries with exponential backoff + jitter; **circuit breaker**; **fallback** gpt-4o-mini → Claude
  Haiku → graceful error node [Ch 19, 22].

**5. Observability**
- Structured JSON logs; metrics (requests, errors, latency, tokens, cache hit rate) [Ch 19].
- `/health` (DB + Stockfish), `/metrics`, `/cache/stats` [Ch 22]; LangSmith tracing [Ch 13].
- **Cost story:** `/metrics` shows cost per report and the live comparison against stuffing the
  whole corpus (~185K tokens) into each prompt [Ch 24].

**6. Quality and delivery**
- Test pyramid: fast deterministic unit tests (no LLM), integration tests with mocked LLMs [Ch 23].
- Retrieval eval: a **fresh** puzzle query set (new seed, frozen first), hit rate reported [Ch 13].
- Docker: non-root user, layer caching, HEALTHCHECK; compose with Postgres + pgvector [Ch 23].

### Course concepts deliberately not used
| Concept | Why not |
|---|---|
| PII masking [Ch 21] | Chess games contain no personal data; usernames are public |
| Model routing [Ch 18] | One kind of LLM task; gpt-4o-mini handles it |
| Contextual retrieval [Ch 24] | User decision: corpus stays deterministic (no LLM at ingestion) |
| Late chunking [Ch 25] | Needs a different embedding model; chunks are short and self-contained |
| GraphRAG [Ch 26] | No multi-hop entity questions in this product |
| Multimodal / ColPali [Ch 27] | No PDFs, tables or images in the corpus |
| Cross-encoder reranking [Ch 27] | Heavy dependency; the LLM relevance grader fills the role |

---

## Stage 4 — Code specifics

### 4.1 API contract — **agreed**
See [`docs/API.md`](API.md): 3 product endpoints (start analysis, get report, get game) plus
`/health`, `/metrics`, `/cache/stats`. Both players' moves are graded in the game view; weakness
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
| Miss | An error **and** the tagger finds a winning tactic (≥ 2 pawns or mate) in the better line that wasn't played | Ours |
| Best | Played the engine's top move | Ours |
| Excellent | loss < 2 points | Ours |
| Good | loss 2–5 points | Ours |
| Great | Best move **and** the second-best move is ≥ 10 points worse ("only move"; needs MultiPV 2 in the game pass) | Ours |
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

### 4.5 Database schema — **current (may change while building)**
PostgreSQL + pgvector; SQLAlchemy 2.0 models, Alembic migrations. Games are stored once and shared
between reports, so re-analysing a user reuses already-analysed games.

| Table | One row is… | Key columns |
|---|---|---|
| `reports` | One analysis request | id, username, time_control, games_requested, status, error, progress, summary (JSON), created_at |
| `games` | One chess.com game | id, chesscom_id (unique), pgn, white, black, result, date, opening, time_class, bulk_status, grading |
| `report_games` | Game ↔ report link | report_id, game_id, user_color |
| `moves` | One half-move | (game_id, ply) PK, san, fen_after, eval_cp / eval_mate, win_loss, grade, themes[], better_line[], refutation_line[] |
| `report_cards` | One weakness card | report_id, rank, theme, count, why, how_to_avoid, sources (JSON), examples (JSON) |
| `jobs` | One background task | id, kind, ref_id, status, attempts, locked_at, error — claimed with `FOR UPDATE SKIP LOCKED` |
| `corpus_chunks` | One piece of teaching text | id, source, title, section, url, content, tags[], embedding vector(1536) (HNSW), tsv (GIN) |
| `llm_calls` | One LLM / embedding call | purpose, model, tokens in/out, cost_usd, latency_ms, cached, error — source of `/metrics` |

### 4.6 Folder structure — **current (may change while building)**
```
BlunderTrace/
├── docker-compose.yml        db (pgvector) · api · worker · frontend
├── backend/
│   ├── pyproject.toml · Dockerfile · alembic/
│   ├── app/
│   │   ├── main.py · config.py · schemas.py (= docs/API.md)
│   │   ├── db/ · chesscom/
│   │   ├── analysis/         engine.py · grading.py · tagging.py · aggregate.py
│   │   ├── vendor/lichess_puzzler/   (+ its LICENSE)
│   │   ├── rag/              ingest.py · retrieval.py · explain_graph.py · prompts.py · validator.py
│   │   ├── llm/ · observability/ · worker.py
│   ├── scripts/ingest_corpus.py
│   └── tests/                unit/ · integration/ · eval/
├── frontend/
│   └── src/                  api/ · mocks/ · pages/ · components/
├── pre_build_research/
└── docs/                     PLAN.md · API.md
```

### 4.7 Build order — **draft**
**Phase 0 — Setup** ✅ done
1. Restructure the repo into `backend/` + `frontend/`; scaffold Vue 3 + Vite + TypeScript;
   docker-compose with Postgres + pgvector; add the AGPL-3.0 `LICENSE`.

**Phase 1 — Frontend on sample data** (also the visual review of stage 2)
- **First: design session** — theme, colours, typography and every UX detail are decided before any screen is built.
2. Typed API client + sample JSON for every state in `docs/API.md` (running, done, failed;
   game pending / complete).
3. Home page.
4. Report page: analysing state (simulated polling), report (summary, cards, missed tactics,
   openings, games table), failed state.
5. Game page: board, move list with grades, eval bar, side panel, line playback + Back.
   → **Stage 2 sign-off** on the real screens.

**Phase 2 — Backend core (no LLM)**
6. FastAPI skeleton, config, schemas, DB models + migrations, `/health`.
7. chess.com client (archives, time-control filter, last N games).
8. Stockfish wrapper + win% grading, with unit tests on known positions.
9. Vendored tagger + adapter, with the 2,000-puzzle check as a test.
10. Jobs table + worker: bulk analysis (stage A) → errors, themes, counts, openings, missed tactics;
    `POST`/`GET /api/reports` return real data (card text still empty).
11. Game deep pass (stage B) + game endpoint.

**Phase 3 — RAG**
12. Corpus ingestion into pgvector (fix the *Fork* row; chunking; tags; embeddings; HNSW; FTS).
13. Retrieval (tag filter + hybrid + RRF) with tests; retrieval eval on a fresh puzzle set.
14. LLM client: token budget, retries, circuit breaker, fallback; every call logged to `llm_calls`.
15. Card-explanation graph (LangGraph) + move validator + cache.

**Phase 4 — Production hardening**
16. JSON logs, `/metrics` (cost per report, RAG vs long-context), `/cache/stats`, LangSmith.
17. Rate limiting, input validation, error states end to end.
18. Production Dockerfiles (non-root, layer caching, HEALTHCHECK); full compose stack.
19. Connect the frontend to the real API; end-to-end run with a real username.

**Phase 5 — Publish**
20. README (setup, architecture, research, decisions, results), screenshots.
21. Hosting decision + deploy; file the post-launch GitHub issues.

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

---

## Decisions log
| Decision | Why |
|---|---|
| No board state in embeddings; retrieval uses concept queries | Pre-build research (`pre_build_research/README.md`) |
| Theme tagging uses lichess-puzzler's tagger (`ornicar/lichess-puzzler`, AGPL-3.0) → **BlunderTrace is licensed AGPL-3.0** | Fastest, proven on millions of puzzles; same theme names as our corpus and tests |
| Errors are fixed by the bulk pass; the game pass only adds | Cards and game view must never disagree |
| Engine lines always at full strength, no toggle | Consistent, trustworthy, teaches the right idea; bloat-free |
| "Show why it's bad" alongside "Show better move" | Seeing why a move fails is the key learning moment |
| Error actions in a side panel, not a popup | A popup would cover the position being studied |
| Evaluation bar in the game view | Cheap (evaluations already exist); makes swings visible |
| One dark theme, desktop-first, stacks on phone | Bloat-free; no theme or mobile-specific work |
| Report is one scrolling page, not tabs | Most important information first; fewer clicks |
| Vue 3 + Vite, one repo, Stockfish on the server, contract-first build order | User's stage 3 choices |
| First cut = features 1–12; coach chat is the first post-launch item | Publish sooner; chat brings the free-text RAG concepts (sanitizer, scope guard, conversational RAG, multi-query) afterwards |
| No contextual retrieval | User decision; keeps ingestion deterministic and free |
| Retrieval extras moved to a post-launch roadmap | Keep the MVP lean; ship first |
| Design direction **A — The Annotated Book** (canvas: claude.ai artifact "BlunderTrace Design Directions") | User's choice: clean, bloat-free, calm game view, room to grow |
| Board: **chessground** (Lichess's board, GPL-3.0, compatible with AGPL-3.0), themed to A | Proven animation (captures, castling, promotion), arrows, highlights, resizing; restyled with CSS so it matches A |
| Components: Reka UI (Radix for Vue) primitives + our own styled kit on Tailwind v4 tokens | User likes Radix; unified custom design language, no imposed look |
| Design improvements included in the first cut: sliding moves, footnote previews of retrieved passages, A-style Analysing screen, keyboard arrows in game view | User: no shortcuts on design. Phone layout review moved to post-launch |
| Pieces: **exactly the canvas set** — Noto Sans Symbols 2 chess glyphs (SIL OFL 1.1), solid shapes with A's fill/outline colours; font self-hosted (or glyphs exported to SVG) so they render identically everywhere | User's choice; license compatible with AGPL-3.0 |
