# BlunderTrace — Project Handoff

AI chess coach: analyses a player's recent games, finds the mistakes they **keep repeating**, and
explains each top issue in plain English with **cited chess theory** and the better move. Built as a
**production-grade RAG MVP** (portfolio project; course notes: freeCodeCamp "Production RAG with
LangChain & Vector Databases").

Product direction: like recurring-mistake tools such as AuditChess (many games → repeated
mistakes), plus **retrieved, cited theory** on how to fix each top issue. A follow-up coach chat is
the first post-launch item.

## Goals (non-negotiable)
1. **Speed:** working MVP fast, built with AI assistance.
2. **Production grade:** a Docker setup anyone can run with only a correct `.env`. Monitoring + tests.
3. **Showcase RAG honestly:** retrieval used where it adds value, checked rather than trusted, and
   real AI cost logged per report. No comparisons against made-up alternatives.

## Repo layout (current)
```
frontend/             Vue 3 + Vite + TypeScript; all screens built on sample data (Phase 1 done)
backend/              FastAPI app (uv project; `app/`, `tests/`); run `uv run pytest` / `uv run uvicorn app.main:app`
docker-compose.yml    Postgres + pgvector (`docker compose up -d db`); api, worker and caddy added while building
docs/                 PLAN.md (product, stages, post-launch) · DESIGN.md (frontend) · API.md (contract) · BACKEND.md (backend)
pre_build_research/   research: report, corpus, tools, tests, engine_timing/ — its own uv project (run commands inside it)
LICENSE               AGPL-3.0 (required by the vendored lichess-puzzler tagger)
.env / .env.example   API keys, POSTGRES_*, DATABASE_URL (.env is gitignored; never read or print it)
```
- **Frontend design of record: `docs/DESIGN.md`** (direction A, *The Annotated Book*). The frontend
  must match it and the reference files in `docs/design/reference/` **pixel-perfect**: use its
  tokens, never invent values.
- **Backend design of record: `docs/BACKEND.md`**, decided one decision at a time in conversation.
  Section 2 lists every decision with its reason, section 16 is the build order, section 18 records
  the final check (18 Nov), and section 19 is what's left to settle while building.
- **`docs/PLAN.md`** holds the product plan (features, UX, stages, post-launch items, decisions log).
- **`docs/API.md`** is the contract both sides follow.
- Follow these; propose changes rather than drifting.
- Branches: `main` (all work merged); `experiment/retrieval-test` kept as a record of the research.

## Key research findings
### Retrieval (`pre_build_research/README.md`)
- **Embeddings understand language, not chess positions.** PGN/FEN strings can't be embedded
  meaningfully, and embedding plain-English board descriptions failed (best hit@5 31%).
- **Concept-only queries work:** asking about the idea ("what is a pin / how to avoid it") found
  relevant text for 8/8 tested themes, all from Wikipedia, Wikibooks and the Lichess theme glossary.
- **Consequences:**
  - Never embed board state.
  - Position understanding comes from the **chess engine + code**.
  - Retrieval queries are about the **concept / how to avoid the mistake**.
  - Board facts go into the prompt, not into embedded text.

### Engine (`pre_build_research/engine_timing/README.md`)
- **One pass with MultiPV 2 at 100,000 nodes** costs ~5% more than errors-only and finds ~90% of
  "great" moves.
- **Club rapid games take ~11 s per game on one core,** with every reference blunder flagged and no
  false blunders.
- **Stockfish 19 uses ~360 MB of RAM per process.**

## Architecture (summary; details in `docs/BACKEND.md`)
- **Shape:** a modular monolith in two roles. `api` (FastAPI) never runs Stockfish; `worker` ×N
  (default 2) does the slow work. **Caddy** serves the Vue build and passes `/api` to the API.
- **Storage:** Postgres + pgvector for everything: app data, the library, caches, AI call log, and
  the job queue (Procrastinate).
- **Flow:** `prepare_report` (download games) → `analyse_game` × N (one job per game; games are
  shared between reports and users, by chess.com link) → `build_report` (top 3, RAG cards).
  - A report-row lock stops the "last game finished" race.
  - Prepare and build jobs have priority over game jobs.
  - Only temporary errors are retried.
  - A check every 5 minutes repairs or fails reports that can no longer finish.
- **Engine:** pinned Stockfish 19, 1 thread, MultiPV 2, 100k nodes, one pass. Grading by lost win%
  (Lichess thresholds + our own grades).
  - Mistakes are named by the vendored Lichess puzzle tagger (≥ 2 pawns or mate).
  - Cards rank themes by games affected.
  - Line notes are fixed templates, stored as facts and worded for the reader when read.
- **RAG** (the only AI in the product: the 3 weakness cards):
  - The library is built once and shipped: Wikipedia + Wikibooks + glossary, 1,338 passages,
    merged within sections, prefixed "Article › Section:", **AI-tagged once at build time**, with
    vectors.
  - Retrieval: tag filter → ranked by meaning (vector) → top 5. Hybrid (+ full-text, RRF) was
    tested blind and added nothing, so it was dropped.
  - Writing (LangGraph): relevance check → rewrite (max 2) → write → move/citation check → retry
    once → **glossary fallback**. A report never fails because of the AI.
- **Prompts:** chess facts and library text only. **Never usernames or other chess.com text**
  (prompt injection).

## Fixed tech stack
- Python 3.12, `uv`, FastAPI, Pydantic / pydantic-settings, **psycopg 3 (plain SQL, no ORM)**,
  **Procrastinate** (version pinned), LangChain (model calls) + **LangGraph** (flow)
- **Async everywhere** (routes, tasks, DB, httpx, python-chess's engine, LangChain `ainvoke`); pure
  chess math stays plain functions. Never call a sync library that waits inside async code.
- PostgreSQL + **pgvector** (one DB for everything)
- Hosted models only: **Claude Haiku 5.5** (`claude-haiku-5-5`) main, **gpt-6-luna** fallback
  (reasoning effort none/low); `text-embedding-3-small`. gpt-4o-mini shuts down 14 Jan 2027.
  for the library build. **No Ollama / local models.**
- `python-chess` + **Stockfish 19**:
  - Docker: the pinned official release (x86-64 / arm64, checksum-verified);
  - locally: Homebrew's `stockfish` (19, installed).
- **Caddy** (front door), **ruff** (lint + format), **pytest** (+ import-linter). No type checker
  for now.

## Corpus (research corpus, already built)
- Location: `pre_build_research/corpus/*.jsonl` (2,425 rows) + readable copies in `corpus/readable/`.
  Row shape: `id, source, title, section, url, text, fen (studies only), meta`.
- Sources:
  - Lichess studies (6 instructional, 321 rows);
  - Wikipedia (36 concept articles + Glossary of chess, 1,155);
  - Wikibooks "Chess" (10 chapters, 136);
  - Project Gutenberg Capablanca + E. Lasker (prose only, 766);
  - Lichess puzzle-theme glossary (47).
- **The app's library uses only Wikipedia, Wikibooks and the glossary (1,338 rows).**
  - The studies (narration, unclear licence) and the books (never relevant) are left out.
  - Built by `backend/scripts/build_library.py` (BACKEND.md section 8).
- **Known bug:** the theme glossary has no *Fork* row. It is fixed in the library build.
- Thin coverage: trapped piece, exposed king, hanging piece. Make targeted additions only if the
  retrieval check shows a gap.
- Licensing: Wikipedia/Wikibooks are CC BY-SA (attribution); Gutenberg is public domain; Lichess
  study content belongs to its authors. Always cite sources.

## Data sources reference
| Source | Access |
|---|---|
| chess.com games | `https://api.chess.com/pub/player/{username}/games/archives`, no auth. One request at a time (parallel may get 429); send an identifying User-Agent; ETag supported |
| Lichess studies | `GET https://lichess.org/api/study/{id}.pgn?comments=true&variations=false&clocks=false`; 403 = export disabled |
| Wikipedia / Wikibooks | MediaWiki API `action=query&prop=extracts&explaintext=1&redirects=1`; rate-limited (429) — back off |
| Lichess puzzle DB | `database.lichess.org/lichess_db_puzzle.csv.zst` (310 MB; stream the head with zstandard) |
| Openings | From chess.com's opening link in each game (family name); not embedded |

## Evaluation (keep doing this)
- **Research harness:** `pre_build_research/retrieval_test.py` (`build` = dry run unless `--yes`;
  `query`; `score`), 20 tests in `pre_build_research/tests/`.
- **Rules that worked:**
  - test sets fixed (frozen in git) before changes;
  - self-check before trusting scores;
  - a **blind human check** as the main judge; an automatic score only as a rough signal.
- **The app's retrieval check:** for the 9 card themes, the top 5 under meaning-only vs hybrid,
  judged blind (BACKEND.md section 15). Result: 23 vs 22 of 45 relevant (second judge: 32 vs 29),
  so meaning only. Main finding: the library explains *what* a tactic is more than *how to avoid
  it*.
- **Engine measurements:** `pre_build_research/engine_timing/` (script + README with results).
- **Embedding spend so far:** 225,880 tokens, $0.0045 (cached in `pre_build_research/cache/`,
  gitignored).

## Production checklist (see BACKEND.md for the details)
- pydantic-settings config + `.env.example` with machine profiles; strict Pydantic input rules
- **Validation everywhere:** API input, chess.com data, DB constraints, JSON columns, settings,
  engine output, AI output, shipped library
- Output validator (moves legal and in Stockfish's lines; citations valid)
- Caches in Postgres (chess.com with ETags, retrieval per theme, AI answers); token budget
- LangGraph flow with bounded rewrite loop, retries, circuit breaker, Haiku 5.5 → gpt-6-luna →
  glossary fallback
- Structured JSON logs with request ids, `/health`, `/metrics`, capacity warnings; LangSmith optional
- **Cost tracking:** every AI call logged (tokens, cost, time, outcome); cost per report in
  `/metrics`
- pytest: pure logic, engine, real test database, API shapes, one end-to-end run; no real AI or
  chess.com calls in tests
- Docker: non-root, layer caching, HEALTHCHECK, pinned Stockfish 19, worker limits (CPU, memory) from
  `.env`;
  tables created on startup
- Per-visitor rate limits: before any public launch (PLAN.md post-launch item 6)

**Skip:** GraphRAG, ColPali, late chunking, semantic chunking, PII masking, embedding positions,
long-context cost comparisons.

## Cost (expected)
- **Per report:** about 3 AI calls (one per weakness card); relevance and rewrite are cached per
  theme. About $0.0015 per report with Haiku 5.5 or gpt-6-luna ($0.10 / $0.50 per 1M tokens each).
- **Library build (one-time):** AI tags + embeddings, well under $0.20. Run only after a dry run and
  approval.

## Product scope
- **Report:**
  - summary (games, W/D/L, errors per game);
  - top 3 recurring weaknesses as cards with 2–3 real positions each (their move, better move,
    punishing line, explanation, citations);
  - missed tactics, openings, games list.
- **Game view:** every move graded, "Show better move" / "Show why it's bad" with template notes.
- **Out of scope:**
  - accounts/login, puzzles/training mode, Lichess usernames, PGN paste, live games, mobile app;
  - "find similar positions" retrieval (would need chess-specific representations).

## Risks
1. **Mistake-naming quality.** The vendored tagger is proven; check the "quiet move" and "defensive
   move" labels on real games.
2. **Capacity.** Measured ~11 s per game per worker; scale with `WORKERS`; load test with 1/2/4
   workers.
3. **Thin library coverage** for some themes. Check with the retrieval check and patch in a targeted
   way.
4. **Scope.** Cut order if behind: polish first.
5. **"Why RAG?"** Answer with the research report, the retrieval check, citations and honest cost
   logging.

## Next steps
Build the backend in the order of `docs/BACKEND.md` section 16, settling section 19's items along
the way. Docker (OrbStack on the user's Mac) must be running for the database; the user starts it.
- **Who does what during the build:**
  - Claude does all reviews and tests (test users: `adityakanade`, `GothamChess`) and reports
    findings when the app is complete.
  - The user approves every paid AI call (after a dry run with a cost estimate) and marks the blind
    retrieval check.
  - Commits and pushes only when asked.

## Conventions
- Commits: plain messages, **no `Co-Authored-By` trailer** (AI help is credited in the README).
  Commit only when the user asks.
- Never put API keys in commands/logs; `.env` stays gitignored. Paid API calls only with explicit
  approval and a dry run/cost estimate first; embeddings cached by text fingerprint.
- Design decisions are made **one at a time in conversation**. Earlier docs are input, not fixed
  truth; update the docs from the decisions.
- No CI/CD for now; run `uv run pytest` and `ruff check` after every change.
- Explain code and decisions in simple terms — the user is new to Python.
