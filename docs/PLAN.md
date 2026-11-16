# BlunderTrace — Product Plan

Planning happens in stages; nothing is coded until all stages are agreed.

| Stage | Topic | Status |
|---|---|---|
| 1 | MVP features | **Signed off** |
| 2 | UI/UX flow | **Draft — open.** Only these are user-approved: side panel, eval bar, desktop-first, one dark theme. Rest is Claude's proposal; revisit (possibly with visual mockups). |
| 3 | Tech stack, architecture & RAG pipeline | **Draft — awaiting sign-off** |
| 4 | Code specifics (folder structure, API contract, database schema, build order) | Not started |

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
