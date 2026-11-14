# BlunderTrace — Project Handoff

AI chess coach: finds the mistakes a player keeps repeating across their games, explains *why* in plain English with cited chess theory, and shows the better move. Built as a **one-day, production-grade RAG MVP** to demonstrate production RAG skills (from the freeCodeCamp "Production RAG with LangChain & Vector Databases" course — notes in `Production_RAG_Systems_-_Comprehensive_Masterclass_Manual.txt`). Original brainstorm with Gemini is in `gemini-conversation-*.md` (treat its technical claims with caution — some were wrong, see "Known corrections").

## Goals (non-negotiable)
1. **Speed:** working MVP in one day, built with AI assistance.
2. **Production grade:** a Docker image anyone can run with only a correct `.env`. Monitoring + tests included.
3. **Showcase RAG cost-efficiency:** measure and expose cost per analysis vs. a long-context baseline.

## Fixed tech stack
- Python, FastAPI, LangChain + LangGraph, `uv`
- PostgreSQL + **pgvector** (single DB for app data + vectors)
- Cheap hosted models only: **gpt-4o-mini** primary, **Claude Haiku** fallback; `text-embedding-3-small` for embeddings. **No Ollama / local models.**
- `python-chess` (rules, PGN parsing, board features) + **Stockfish** (installed in the Docker image via apt)

## Product (what a user sees)
1. Enter a chess.com username (or paste one PGN) → Analyse.
2. Progress while ~20 recent games are analysed (~1–2 min).
3. Report:
   - **Summary:** games analysed, mistakes per game, top 3 recurring weaknesses.
   - **Weakness cards:** e.g. "You leave pieces undefended (11×)", "You lose in the Sicilian (W1/L5)". Each has 2–3 real positions from the user's games: their move, better move, plain-English explanation, source citation.
   - **Single-game view:** move list with flagged mistakes.
   - **Ask box:** free-text follow-up ("why is Nd5 better here?"), grounded + engine-checked.
- **Out of scope:** accounts/login, puzzles/training mode, Lichess usernames, live games, mobile app.
- Why not just copy chess.com's Game Review: per-move heuristics are a solved problem. Value here = **cross-game patterns + grounded explanations + follow-up Q&A**.

## Core architecture: the embedding problem and its fix
- Embedding models read language, not chess. **Never embed PGN or FEN** (similar strings ≠ similar positions).
- **User games are NOT stored in the vector DB.** They are input: analysed by Stockfish, stored as normal relational rows.
- **Corpus** = chess teaching text collected once before launch. Only the corpus is embedded.
- **`describe(board)`** — a deterministic, pure-Python translator (no AI; same board → same text). Run on BOTH corpus positions and user positions so both land in the same vector space. Answers a fixed list of questions:
  - game phase (piece count), material balance
  - opening name (lookup table, not embedded)
  - pawn structure: isolated / doubled / passed / backward pawns
  - open / semi-open files
  - king safety: castling side, pawn shield
  - mistake type (from engine line): hanging piece, allowed fork, missed mate, etc.
  - Example output: `"Middlegame. Sicilian Defence. Material equal. White has an isolated d-pawn. The c-file is open. White castled kingside, Black queenside. Mistake type: piece left undefended."`

### Indexing (one-time)
Lichess study comment → replay with python-chess to that move → `describe(board)` + human comment → embed → store row.

Row shape (table e.g. `chess_knowledge`): `id, source, fen (display only), phase, opening, tags[], content (description + comment, the embedded text), embedding vector(1536)`. Optionally add a `tsvector` column on `content` for keyword search.

### Query time
User blunder FEN → `describe()` → embed → hybrid retrieval → LLM explains.
- **Hybrid retrieval inside Postgres:** metadata `WHERE` filter (phase, opening) + Postgres full-text search (keyword/motif matching) + pgvector cosine (`<=>`), merged with Reciprocal Rank Fusion (RRF code from the course). Postgres FTS avoids the `rank_bm25` "rebuild on every insert" problem the course mentions.
- **LLM role is translation only:** Stockfish supplies what was wrong and the best move; python-chess supplies board facts; retrieval supplies theory; the LLM writes the explanation. It must never calculate moves.

### Cross-game patterns
Group each user's mistakes by tags (mistake type, opening, phase) → top recurring weaknesses → weakness cards.

## Data sources
| Source | Gives | Embedded? | How |
|---|---|---|---|
| **Lichess studies** (main) | position + human explanation | Yes | `GET https://lichess.org/api/study/{studyId}.pgn?comments=true&variations=false&clocks=false` — public, no auth, rate-limited (on 429 wait a minute). Hand-pick 20–40 popular instructional studies from lichess.org/study (+ Lichess Practice section). Check Lichess content terms before public launch; always cite source study. |
| Concept articles (Wikipedia chess strategy pages; prose from Capablanca's *Chess Fundamentals*, Project Gutenberg #33870) | general explanations, no position | Yes (text + tags) | download once, split by section. Capablanca uses old descriptive notation — prose only. |
| Lichess openings dataset | ECO code + name from move sequence | No (lookup table) | one file download |
| chess.com public API | user's games | No | `https://api.chess.com/pub/player/{username}/games/archives`, no auth |

Target corpus: ~500–1,500 rows. Embedding cost < $0.01.
Filtering rules (already in `extract_study.py`): drop comments < 40 chars, strip `[%clk]`, `[%cal]`, `[%csl]` tags.

## Production checklist (mapped to the course)
**Build:**
- pydantic-settings config + `.env.example`
- Input validation: PGN parsed by python-chess (malformed → rejected before any LLM call); Pydantic length limits
- Prompt-injection sanitizer on the free-text Ask box only
- **Output validator (domain-specific):** every move mentioned by the LLM must be legal and present in Stockfish's lines; otherwise reject/regenerate
- slowapi rate limiting; TTL response cache + cache keyed on (FEN, best move); token budget
- LangGraph: retry → fallback model (Haiku) → graceful error node; bounded query-rewrite loop (max_retries=2) if retrieval is graded irrelevant
- Structured JSON logs, `/health` (DB + Stockfish binary checks), `/metrics`, LangSmith tracing
- **Cost metrics:** cost per analysis, cache hit rate, tokens saved vs. long-context baseline
- Contextual retrieval at ingestion (cheap for small corpus)
- pytest for deterministic parts (PGN parsing, `describe()`, RRF, cache, output validator) — no LLM calls in unit tests
- Retrieval eval set: ~20 positions with expected relevant rows → report hit rate
- Docker: non-root user, layer caching, HEALTHCHECK; `docker-compose.yml` with app + `pgvector/pgvector` image; schema created on startup
- Stockfish analysis as a background job with polling (cap ~0.1 s/move → ~5–8 s per game); don't block requests

**Skip:** GraphRAG, ColPali, late chunking, semantic chunking, PII masking (no PII in chess games).

## Cost story (estimates, gpt-4o-mini @ $0.15/1M in, $0.60/1M out; 5 mistakes/game)
- Long-context (stuff ~50K-token corpus per call): ~250K tokens/game ≈ $0.038
- RAG (≈1.5K in + 200 out per call): ≈8.5K tokens/game ≈ $0.0017 (~20× cheaper)
- + position cache: openings repeat across users → further reduction. Expose these live in `/metrics`.

## Known corrections to the Gemini chat
- pgvector: `<->` is L2 distance; cosine is `<=>`.
- Its "95%+ good response" claim is unfounded — measure with the eval set.
- *My System* (Nimzowitsch) is NOT on Project Gutenberg (only a Wikisource transcription project). *Chess Fundamentals* is.
- No Lichess API to bulk-fetch studies by topic; pick study IDs by hand.

## Risks
1. Corpus quality (biggest) — cap corpus work at ~2 h.
2. Stockfish latency — background jobs + per-move time cap.
3. Scope — cut order if behind: Ask box polish → practice positions (already out) → UI polish.
4. "Why RAG?" challenge — answer with citations, retrieval eval numbers, and cost metrics.

## Open decisions
- UI: single HTML page served by FastAPI with a board widget (~1.5 h) vs. API + Swagger only
- Input: chess.com username, PGN paste, or both (spec assumes both)
- Deploy: live (e.g. Render + Supabase/Neon) vs. published Docker image + compose

## Current status / next step
- `extract_study.py` exists: turns a Lichess study PGN into (chapter, move, FEN, comment) rows. Tested on a sample file.
- **Next (validation spike, ~1 h, before full build):**
  1. Download 2–3 real Lichess studies; run `python extract_study.py study.pgn`; check usable comments per study (≥30 good, <10 skip) and whether comments stand alone.
  2. Implement `describe(board)`.
  3. Embed ~50 rows into pgvector.
  4. Take a blunder from a real game, `describe()` it, query, and judge whether retrieved comments are relevant.
  5. If retrieval is sensible → write hour-by-hour build plan (schema, LangGraph node layout) and build.
