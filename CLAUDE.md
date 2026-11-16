# BlunderTrace — Project Handoff

AI chess coach: analyses a player's recent games, finds the mistakes they **keep repeating**, and
explains each top issue in plain English with **cited chess theory** and the better move. Built as a
**production-grade RAG MVP** (portfolio project; course notes: freeCodeCamp "Production RAG with
LangChain & Vector Databases").

Product direction: like recurring-mistake tools such as AuditChess (many games → repeated
mistakes), plus **retrieved, cited theory** on how to fix each top issue, plus a follow-up Ask box.

## Goals (non-negotiable)
1. **Speed:** working MVP fast, built with AI assistance.
2. **Production grade:** a Docker image anyone can run with only a correct `.env`. Monitoring + tests.
3. **Showcase RAG honestly:** retrieval used where it adds value, measured with an eval set; expose
   cost per analysis vs. a long-context baseline.

## Repo layout (current)
```
frontend/             Vue 3 + Vite + TypeScript (scaffold only; design decided before phase 1)
backend/              FastAPI app (uv project; `app/`, `tests/`); run `uv run pytest` / `uv run uvicorn app.main:app`
docker-compose.yml    Postgres + pgvector (`docker compose up -d db`); api/worker/frontend services added later
docs/                 PLAN.md (stages, decisions, build order) · API.md (API contract)
pre_build_research/   research: report, corpus, tools, tests — its own uv project (run commands inside it)
LICENSE               AGPL-3.0 (required by the vendored lichess-puzzler tagger)
.env / .env.example   API keys, POSTGRES_*, DATABASE_URL (.env is gitignored; never read or print it)
```
**The plan of record is `docs/PLAN.md`** (features, UX, stack, RAG pipeline, grading rules, schema,
build order). Follow it; propose changes rather than drifting.
Branches: `main` (all work merged); `experiment/retrieval-test` kept as a record of the research.

## Key research finding (read `pre_build_research/README.md` for the full report)
- **Embeddings understand language, not chess positions.** PGN/FEN strings can't be embedded
  meaningfully, and the workaround (embedding plain-English board descriptions from
  `describe(board)`) failed: best automatic hit@5 was 31%, with board-description queries at 13%.
  Board descriptions matched *other board descriptions*, not the lesson.
- **Concept-only queries work:** asking about the idea ("what is a pin / how to avoid it") retrieved
  relevant text for 8/8 tested themes (27/40 results on-topic), mostly from Wikipedia, Wikibooks
  and the Lichess theme glossary.
- **Consequences for the design:**
  - Never embed board state (PGN, FEN or board descriptions).
  - Position understanding comes from the **chess engine + code**, not from retrieval.
  - Retrieval queries are about the **chess concept / how to avoid the mistake**.
  - Board facts go into the LLM prompt and into metadata filters, not into embedded text.
  - **Do not spend more time on bulk data fetching**; the corpus is sufficient.

## Architecture (engine first, retrieval for theory)
1. **Input:** chess.com username (public API, no auth) or pasted PGN. PGN parsed by python-chess;
   malformed input is rejected before any LLM call.
2. **Find mistakes — Stockfish:** analyse each of ~20 recent games (background job, ~0.1 s/move cap).
   Flag moves with a large evaluation drop. For each: the position, the move played, the **better
   move**, and the **opponent's winning reply** (the line that punishes the mistake).
3. **Name mistakes — heuristics (python-chess, no AI):** label each mistake with a known blunder type
   from the engine line, e.g. punishing move attacks two pieces → "allowed a fork"; punished piece had
   no defenders → "left a piece hanging"; also pin, skewer, discovered attack, back-rank mate,
   trapped piece, exposed king, missed mate, etc. Also record phase and opening (lookup table).
4. **Find patterns:** count mistake types (+ opening, phase) across all games → top 3 recurring
   weaknesses → weakness cards ("You allow forks (11×)").
5. **Retrieve theory — hybrid, inside Postgres:**
   - **Tag filter first:** corpus rows are tagged with the concepts they cover (deterministic keyword
     tagging at ingestion). Filter by the mistake type (+ phase/opening where useful).
   - **Rank within** using a **concept-only query** (one fixed query per mistake type, e.g. "how to
     avoid allowing a knight fork"): pgvector cosine (`<=>`) + Postgres full-text search, merged with
     Reciprocal Rank Fusion (RRF).
6. **Explain — LLM (translation only):** input = engine facts (mistake, better move, winning reply),
   board facts (`describe()`-style text is fine *here*), and retrieved passages with sources. Output =
   plain-English explanation with citations. **The LLM never calculates moves.**
7. **Output validator (domain-specific):** every move the LLM mentions must be legal and present in
   Stockfish's lines; otherwise reject/regenerate.
8. **Ask box:** free-text follow-up questions → retrieval on the user's question (this is where RAG
   is needed most) → grounded, engine-checked answer. Prompt-injection sanitizer on this input only.

## Fixed tech stack
- Python 3.12, `uv`, FastAPI, LangChain + LangGraph
- PostgreSQL + **pgvector** (single DB for app data, corpus rows and vectors; `tsvector` for FTS)
- Hosted models only: **gpt-4o-mini** primary, **Claude Haiku** fallback; `text-embedding-3-small`
  for embeddings. **No Ollama / local models.**
- `python-chess` (rules, PGN parsing, heuristics) + **Stockfish** (installed in the Docker image via
  apt; locally: `brew install stockfish` — not installed yet)

## Corpus (already built — reuse it)
- Location: `pre_build_research/corpus/*.jsonl` (2,425 rows) + readable copies in `corpus/readable/`.
  Row shape: `id, source, title, section, url, text, fen (studies only), meta`.
- Sources: Lichess studies (6 instructional, 321 rows), Wikipedia (36 concept articles + Glossary of
  chess, 1,155), Wikibooks "Chess" (10 chapters, 136), Project Gutenberg #33870 Capablanca *Chess
  Fundamentals* + #5614 E. Lasker *Chess Strategy* (prose only, notation-heavy paragraphs dropped,
  766), Lichess puzzle-theme glossary (47).
- Built by `pre_build_research/build_corpus.py` (raw downloads cached in `pre_build_research/raw/`,
  gitignored). Most useful for mistake explanations: Wikipedia, Wikibooks, theme glossary.
  Study comments / annotated games are weaker (move-by-move narration).
- **Known bug:** theme glossary has no *Fork* row (Lichess key is `forkOpposingPiecesDescription`).
- Thin coverage: trapped piece, exposed king, hanging piece — targeted additions only if the
  re-test shows a gap.
- Licensing: Lichess study content belongs to its authors; Wikipedia/Wikibooks are CC BY-SA
  (attribution); Gutenberg public domain. Always cite sources; check terms before public launch.

## Data sources reference
| Source | Access |
|---|---|
| chess.com games | `https://api.chess.com/pub/player/{username}/games/archives`, no auth |
| Lichess studies | `GET https://lichess.org/api/study/{id}.pgn?comments=true&variations=false&clocks=false`; 403 = export disabled; study search/topic pages are behind a bot check (pick IDs from `/study/all/popular`) |
| Wikipedia / Wikibooks | MediaWiki API `action=query&prop=extracts&explaintext=1&redirects=1`; rate-limited (429) — back off |
| Lichess puzzle DB (eval data) | `database.lichess.org/lichess_db_puzzle.csv.zst` (310 MB; stream the head with zstandard) |
| Lichess openings | lookup table (ECO + name), not embedded |

## Evaluation (keep doing this)
- Research harness: `pre_build_research/retrieval_test.py` (`build` = dry run unless `--yes`;
  `query`; `score`), queries from `sample_puzzles.py`, 20 tests in `pre_build_research/tests/`.
- Rules that worked: queries generated by code from real data (Lichess puzzles + their themes),
  **frozen in git before the corpus/changes**; self-check before trusting scores; blind human check
  (variant names hidden) as the main judge; automatic keyword score only as a rough signal.
- The original 45 queries have been seen → **re-test on a fresh puzzle set (new seed)**.
- Embedding spend so far: 225,880 tokens, $0.0045 (cached in `pre_build_research/cache/`, gitignored).

## Production checklist
**Build:**
- pydantic-settings config + `.env.example`; Pydantic length limits on input
- Prompt-injection sanitizer (Ask box only); output validator (moves legal + in Stockfish lines)
- slowapi rate limiting; TTL cache keyed on (FEN, best move); token budget
- LangGraph: retry → fallback model (Haiku) → graceful error node; bounded query-rewrite loop
  (max_retries=2) if retrieval is graded irrelevant
- Structured JSON logs, `/health` (DB + Stockfish binary), `/metrics`, LangSmith tracing
- **Cost metrics:** cost per analysis, cache hit rate, tokens saved vs. long-context baseline
- pytest for deterministic parts (PGN parsing, mistake labelling, RRF, cache, validator) — no LLM
  calls in unit tests
- Retrieval eval set with reported hit rate (see Evaluation)
- Docker: non-root user, layer caching, HEALTHCHECK; `docker-compose.yml` with app +
  `pgvector/pgvector`; schema created on startup
- Stockfish analysis as a background job with polling; don't block requests

**Skip:** GraphRAG, ColPali, late chunking, semantic chunking, PII masking, embedding positions.

## Cost story (estimates, gpt-4o-mini @ $0.15/1M in, $0.60/1M out; 5 mistakes/game)
- Long-context (stuff ~50K-token corpus per call): ~250K tokens/game ≈ $0.038
- RAG (≈1.5K in + 200 out per call): ≈8.5K tokens/game ≈ $0.0017 (~20× cheaper)
- Position cache: openings repeat across users → further reduction. Expose live in `/metrics`.
- Measured: embedding the whole corpus once ≈ $0.004.

## Product scope
- Report: summary (games analysed, mistakes per game, top 3 recurring weaknesses); weakness cards
  with 2–3 real positions each (their move, better move, explanation, citation); single-game view
  (move list with flagged mistakes); Ask box.
- **Out of scope:** accounts/login, puzzles/training mode, Lichess usernames, live games, mobile app,
  "find similar positions" retrieval (would need chess-specific representations — future work).

## Risks
1. Mistake labelling quality (heuristics on engine lines) — now the core technical piece.
2. Stockfish latency — background jobs + per-move time cap.
3. Thin corpus coverage for some mistake types — measure on the re-test, patch with targeted sources.
4. Scope — cut order if behind: Ask box polish → UI polish.
5. "Why RAG?" — answer with the research report, eval numbers, citations and cost metrics.

## Open decisions
- UI: single HTML page served by FastAPI with a board widget vs. API + Swagger only
- Input: chess.com username, PGN paste, or both (spec assumes both)
- Deploy: live (e.g. Render + Supabase/Neon) vs. published Docker image + compose
- Exact mistake-type list (start from the 9 tested themes + missed mate, hanging piece, etc.)

## Next steps
1. Fix the *Fork* glossary bug; add concept tags to corpus rows.
2. Write the mistake-type list and one fixed concept query per type ("how to avoid …").
3. Freeze a **fresh** puzzle query set (new seed), then re-test retrieval with concept queries
   (blind human check as main measure).
4. Install Stockfish; build the engine → mistake-labelling pipeline (python-chess heuristics) with
   tests on known positions.
5. Then the app: schema + ingestion into pgvector, FastAPI endpoints, LangGraph flow, validator,
   metrics, Docker.

## Conventions
- Commits: plain messages, **no `Co-Authored-By` trailer** (AI help is credited in the README).
- Never put API keys in commands/logs; `.env` stays gitignored. Paid API calls only with explicit
  approval and a dry run/cost estimate first; embeddings cached by text fingerprint.
- Explain code and decisions in simple terms — the user is new to Python.
