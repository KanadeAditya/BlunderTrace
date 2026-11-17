# BlunderTrace — Backend Architecture

> **Status: DRAFT for review.** Nothing in this document is built yet. Every choice that is still
> open is marked **D-number** and collected in the [Decision register](#21-decision-register),
> with a recommendation. We go through them one by one; once all are decided, this file becomes the
> backend's design of record (as `DESIGN.md` is for the frontend), and code follows it exactly.
>
> Already decided (stage 3, signed off): Python 3.12 + uv, FastAPI, Pydantic, PostgreSQL +
> pgvector, SQLAlchemy 2.0 + Alembic, Stockfish on the server, lichess-puzzler tagger, LangChain +
> LangGraph, gpt-4o-mini primary + Claude Haiku fallback, `text-embedding-3-small`, jobs table +
> worker, frontend polling. This document builds on those; it does not reopen them.

## Contents
1. [What the backend must achieve](#1-what-the-backend-must-achieve)
2. [Requirements](#2-requirements)
3. [Architecture overview](#3-architecture-overview)
4. [The main flows, step by step](#4-the-main-flows-step-by-step)
5. [Data model](#5-data-model)
6. [Background jobs](#6-background-jobs)
7. [Chess analysis core](#7-chess-analysis-core)
8. [RAG: the card explanations](#8-rag-the-card-explanations)
9. [API layer](#9-api-layer)
10. [Caching](#10-caching)
11. [Failure handling](#11-failure-handling)
12. [Security](#12-security)
13. [Observability](#13-observability)
14. [Configuration](#14-configuration)
15. [Testing](#15-testing)
16. [Packaging, running and deployment](#16-packaging-running-and-deployment)
17. [Code organisation](#17-code-organisation)
18. [Libraries](#18-libraries)
19. [Performance and cost budget](#19-performance-and-cost-budget)
20. [Build plan](#20-build-plan)
21. [Decision register](#21-decision-register)
22. [Changes this proposes to API.md and PLAN.md](#22-changes-this-proposes-to-apimd-and-planmd)
23. [Risks](#23-risks)

---

## 1. What the backend must achieve

### 1.1 Goals
1. **Serve the product exactly as designed.** Return the shapes in `docs/API.md` so the finished
   frontend switches from the mock to the real API with one environment variable.
2. **Be correct before being clever.** Positions are understood by the **engine and code**, never
   by an LLM. Every move the product shows comes from Stockfish and is checked by python-chess.
3. **Use RAG honestly.** Retrieval is used only where it adds value (explaining *why* and *how to
   avoid* a mistake, with cited theory); it is measured with an eval set; its cost is shown live
   against a long-context baseline.
4. **Be production-grade.** Runs anywhere with `docker compose up` and a correct `.env`;
   background processing that survives crashes; retries, fallbacks and graceful degradation;
   structured logs, health and metrics; tests that run without network or paid APIs.
5. **Be explainable.** Every design choice has a written reason (this document + the decisions
   log), so any part can be defended and changed deliberately.

### 1.2 Non-goals (first cut)
Accounts or login; Lichess usernames; PGN paste; coach chat (first post-launch item); analysing
hundreds of games; live games; horizontal scaling across machines; multi-region; CI/CD pipelines
(see D30).

### 1.3 What this backend demonstrates
The product is the point, but the way it's built is chosen so that each part is a real,
explainable engineering example. Each row is a concrete place in this design:

| Skill | Where it shows up |
|---|---|
| Contract-first API design | `docs/API.md` → Pydantic models; consistent error shape; correct status codes (202 vs 200, 404, 422, 429, 503); idempotent report creation (§9) |
| Relational data modelling | Normalised core (games, moves) + JSONB documents (summaries, card text); constraints; shared games across reports; raw engine data kept apart from derived grades (§5) |
| SQL beyond CRUD | `FOR UPDATE SKIP LOCKED` queue; partial unique indexes for de-duplication; a row lock that fixes a fan-in race; aggregation with `unnest` + `GROUP BY`; hybrid search in one query with CTEs, `tsvector` and pgvector (§5, §6, §8) |
| Asynchronous processing | Job queue with leases, retries with backoff, dead jobs, idempotent handlers, fan-out / fan-in, priorities, a watchdog (§6) |
| Caching | Six caches, each with a clear key, lifetime and measured hit rate (§10) |
| Reliability | Timeouts, retries, circuit breaker, model fallback, deterministic fallback text; a failure table for every dependency (§11) |
| Security thinking | Threat model including *untrusted data from chess.com*; no user-controlled text reaches an LLM (§12) |
| Observability | JSON logs with request/job ids, `/health` with real checks, `/metrics` with cost per report (§13) |
| Testing | Pyramid: pure unit tests, engine tests, database integration tests, retrieval eval; no paid calls in the test suite (§15) |
| Packaging | One Docker image for API and worker, non-root, health checks, migrations as a step, compose stack (§16) |
| RAG engineering | Concept tags + hybrid retrieval + weighted RRF, self-correcting graph, output validator, eval numbers, cost comparison (§8) |

---

## 2. Requirements

### 2.1 Functional (from `docs/API.md` and `PLAN.md`)
| Endpoint | Behaviour |
|---|---|
| `GET /api/players/{username}` | chess.com stats → ratings + all-time game counts per time control; 404 if unknown; cached briefly |
| `POST /api/reports` | validate input; check the user exists (404 at once); reuse a recent identical report (200) or start a new one (202) |
| `GET /api/reports/{id}` | progress while running (games list growing, partial trace of the game being analysed); the full report when done; error code when failed |
| `GET /api/reports/{id}/games/{game_id}` | every move of both players with eval and grade; errors immediately; lines and positive grades as soon as available; first request triggers the game's deeper pass |
| `GET /health`, `/metrics`, `/cache/stats` | operations (§13) |

Analysis stages (signed off): **A — bulk** (every move, errors fixed permanently, themes tagged,
cards built), **B — game** (on first open; adds grades, never re-grades errors), **C — popup**
(replays saved lines, no engine work).

### 2.2 Non-functional targets
| Quality | Target | How it's met |
|---|---|---|
| Report time | 20 games in ≲ 3 min on a 2-core machine (Home already promises "about 3 min") | node-limited engine search, two worker processes, position cache (§7.3, §19) |
| Game view | errors at once; full grades within ~15 s of first open | stage A stores lines; stage B only adds "great/brilliant" (§7.6, D11) |
| Polling cost | `GET /api/reports/{id}` < 50 ms | stored summaries; indexed joins (§5) |
| LLM cost | ≲ $0.005 per report; shown live vs. long-context baseline | RAG + caches + token budget (§8.9) |
| Reliability | a crashed worker, a chess.com outage or an LLM outage never loses a report or shows a stack trace | leases, retries, fallbacks, failure codes (§11) |
| Reproducibility | the same game analysed twice gives the same grades | single-thread, node-limited Stockfish; versioned analysis (§7.3) |
| Operability | one command to run; one place to look for errors and costs | compose, JSON logs, `/metrics` (§13, §16) |

---

## 3. Architecture overview

### 3.1 The shape

```
                         ┌───────────────────────────── docker compose ─────────────────────────────┐
 Browser                 │                                                                           │
 (Vue app) ──HTTP──▶  web (nginx) ── /api/* ──▶  api (FastAPI, uvicorn)  ──SQL──▶  db (Postgres 17  │
            ◀── static ─┘  serves dist/            │  validates, reads,           │    + pgvector)   │
                         │                         │  enqueues jobs               │  app data, jobs, │
                         │                         │  calls chess.com (lookups)   │  corpus, vectors │
                         │                         ▼                              │                  │
                         │                 chess.com public API ◀──────┐          │                  │
                         │                                             │          │                  │
                         │   worker ×2 (same image as api) ── claims jobs ─SKIP LOCKED─▶            │
                         │     Stockfish (subprocess) · python-chess · lichess tagger                │
                         │     LangGraph → OpenAI / Anthropic (Phase 3)                               │
                         │   migrate (one-shot: alembic upgrade head, then exits)                     │
                         └───────────────────────────────────────────────────────────────────────────┘
```

Five services, one image for the three Python ones:

| Service | Role | Scales by |
|---|---|---|
| `db` | PostgreSQL 17 + pgvector: the only stateful component | — |
| `migrate` | runs `alembic upgrade head`, then exits; `api` and `worker` start after it succeeds | — |
| `api` | HTTP only: validation, reads, enqueueing, fast chess.com lookups. **Never runs Stockfish.** | uvicorn workers |
| `worker` | everything slow: fetching games, Stockfish, tagging, aggregation, RAG | replicas (D2) |
| `web` | serves the built frontend and forwards `/api` to `api` (same origin, no CORS) | — (D25) |

### 3.2 Why this shape
- **The API stays fast and predictable.** Analysis is CPU-heavy and slow (minutes). If it ran inside
  request handlers, one report would tie up the server. The API only records intent ("analyse this")
  and returns 202; workers do the work. This is the same split as an Express API + a queue consumer.
- **Postgres is the queue.** No Redis, no Celery, no RabbitMQ: one less service to run and explain.
  Creating a report and its first job happen in **one transaction**, so a report can never exist
  without its job (or vice versa). `FOR UPDATE SKIP LOCKED` lets several workers pull jobs safely.
  At our volume (tens of jobs per report, a handful of reports at a time) Postgres handles this with
  room to spare.
- **State lives in the database, never in processes.** Any worker can die at any moment; a restart
  picks up where things stopped. That's what makes "close the tab and come back" work.

### 3.3 Alternatives considered
| Option | Why not |
|---|---|
| FastAPI `BackgroundTasks` | Runs inside the API process: lost on restart, no retries, no progress across restarts, competes with requests for CPU |
| Celery / RQ / arq + Redis | Mature, but a second stateful service, a second mental model, and the enqueue isn't in the same transaction as the report insert |
| One process doing everything | Simplest, but a long analysis blocks the event loop or needs threads; can't scale workers independently |
| Serverless functions | Stockfish needs a persistent binary and minutes of CPU; poor fit |

---

## 4. The main flows, step by step

### 4.1 Starting a report

```
Browser                 api                                   db                         worker
  │ POST /api/reports    │                                     │                            │
  │ {username,tc,games}  │                                     │                            │
  │─────────────────────▶│ validate (Pydantic)                 │                            │
  │                      │ chess.com /pub/player/{u}  (cached) │                            │
  │                      │   404 → 404 username_not_found      │                            │
  │                      │ recent identical report? ──────────▶│ SELECT … (reuse window)    │
  │                      │   yes → 200 {id, status}            │                            │
  │                      │ BEGIN                               │                            │
  │                      │  INSERT reports (queued)  ─────────▶│                            │
  │                      │  INSERT jobs (prepare_report) ─────▶│                            │
  │                      │ COMMIT                              │                            │
  │◀─────────────────────│ 202 {id, status: queued}            │                            │
  │                      │                                     │◀── claim prepare_report ───│
  │                      │                                     │   fetch archives (chess.com),
  │                      │                                     │   pick last N games, upsert games,
  │                      │                                     │   link report_games, set total,
  │                      │                                     │   enqueue analyse_game × N (dedupe)
  │                      │                                     │◀── claim analyse_game ─────│ ×N, two at a time
  │                      │                                     │   Stockfish every position,
  │                      │                                     │   grade, tag, notes; save moves
  │                      │                                     │   last game of a report? → enqueue build_report
  │                      │                                     │◀── claim build_report ─────│
  │                      │                                     │   aggregate, rank themes, pick examples,
  │                      │                                     │   openings, summary; RAG card text (Phase 3)
  │                      │                                     │   report → done
```

### 4.2 Polling a report
`GET /api/reports/{id}` reads `reports` + `report_games` + `games` (+ a partial trace for the game in
progress) in a few indexed queries. While running it returns `progress` and the games list; when
done it adds the stored summary, weaknesses, missed tactics and openings. The frontend polls every
second; each poll is a cheap read with no work triggered.

### 4.3 Opening a game
`GET /api/reports/{id}/games/{gid}` returns every move from `moves`. If the game's deep pass hasn't
run, the endpoint enqueues one `deep_game` job (idempotent: a unique index prevents duplicates) and
returns `grading: "pending"`; the frontend re-polls. Deep jobs have **higher priority** than bulk
jobs because a person is looking at the screen.

### 4.4 Player lookup
`GET /api/players/{username}` calls chess.com `/stats` through the HTTP cache (10-minute TTL). Done
in the API process because it's one fast request the user is waiting for.

---

## 5. Data model

### 5.1 Principles
1. **Normalise what is queried and counted; store documents as JSONB.** Moves are counted, filtered
   and joined → real rows and columns. A report's finished summary or a card's sources are read
   whole and never queried inside → JSONB.
2. **Games are shared.** A chess.com game is stored and analysed **once**, whoever asks. Two reports
   that include the same game (re-running a username, or both players using BlunderTrace) reuse it.
3. **Raw engine output is kept separate from derived judgements.** We store evaluations, best moves
   and lines exactly as Stockfish gave them; grades and themes are computed from those by our rules.
   If a grading threshold changes, grades can be recomputed from stored data without re-running
   Stockfish (`grading_version`).
4. **Constraints live in the database.** `CHECK` constraints for statuses, `UNIQUE` for natural keys,
   foreign keys everywhere. Statuses are `text` + `CHECK` rather than Postgres `ENUM` types, which
   are awkward to change in migrations.
5. **All timestamps are `timestamptz` in UTC.**

### 5.2 Tables

**`reports`**: one analysis request.
| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | public id `r_` + 10 random base32 chars (D17) |
| `username` | `text` | lower-cased chess.com username |
| `time_control` | `text` CHECK in (`rapid`,`blitz`,`both`) | |
| `games_requested` | `smallint` CHECK in (10,20,30,50) | |
| `status` | `text` CHECK in (`queued`,`running`,`done`,`failed`) | |
| `error`, `detail` | `text` null | failure code + message (API.md) |
| `games_total` | `smallint` null | known after `prepare_report` |
| `summary` | `jsonb` null | W/D/L, per-game rates, notes, missed tactics, openings |
| `stats` | `jsonb` null | engine positions, cache hits, durations, LLM cost: feeds `/metrics` |
| `created_at`, `started_at`, `finished_at` | `timestamptz` | |

Index: `(username, time_control, games_requested, created_at DESC)` for the reuse check.

**`games`**: one chess.com game, shared.
| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` identity PK | internal only |
| `chesscom_id` | `text` UNIQUE | from the game URL; natural key for upserts |
| `url`, `pgn` | `text` | |
| `white`, `black` | `text` | usernames (untrusted text, §12) |
| `white_rating`, `black_rating` | `smallint` | |
| `result` | `text` CHECK in (`1-0`,`0-1`,`1/2-1/2`) | |
| `time_class` | `text` | `rapid` / `blitz` |
| `played_at` | `timestamptz` | chess.com `end_time` |
| `eco`, `opening` | `text` | from the PGN's `ECO` / `ECOUrl` (§7.8) |
| `start_fen` | `text` | standard start unless the PGN sets one |
| `plies` | `smallint` | known from the PGN before analysis |
| `analysis_status` | `text` CHECK in (`pending`,`running`,`done`,`failed`) | stage A |
| `deep_status` | `text` CHECK in (`none`,`pending`,`done`,`failed`) | stage B |
| `engine_profile` | `text` | e.g. `sf17.1-n150k-v1`: what produced the evals (§7.3) |
| `grading_version` | `smallint` | which rules produced the grades |
| `error_counts` | `jsonb` | `{white: {blunder, mistake, inaccuracy, miss}, black: {…}}`: per colour, so any report picks its user's side |
| `analysed_at` | `timestamptz` | |

**`report_games`**: which games belong to which report.
| Column | Type | Notes |
|---|---|---|
| `report_id` | `text` FK → reports | |
| `position` | `smallint` | 1…N, newest first → public game id `g_{position}` (D18) |
| `game_id` | `bigint` FK → games | |
| `user_color` | `text` CHECK in (`white`,`black`) | |
| PK `(report_id, position)`; UNIQUE `(report_id, game_id)` | | |

**`moves`**: one half-move of one game (≈ 80 rows per game).
| Column | Type | Notes |
|---|---|---|
| `game_id`, `ply` | PK | |
| `color` | `text` | `white` for odd plies |
| `san`, `uci` | `text` | |
| `fen_after` | `text` | |
| `eval_cp`, `eval_mate` | `int` null | evaluation *after* the move, White's view (exactly one set) |
| `best_uci` | `text` | engine's best move in the position *before* this move |
| `best_pv` | `text[]` | engine line from the position before (UCI), full length (for tagging) |
| `reply_pv` | `text[]` | engine line from the position after (UCI): the refutation |
| `win_loss` | `real` | mover's win-% loss (derived) |
| `grade` | `text` null | derived; null until computed |
| `themes` | `text[]` | tactics this move *allowed* (from the refutation) |
| `missed_themes` | `text[]` | tactics this move *missed* (from the better line) |
| `better_line`, `refutation_line` | `text[]` | SAN, 3–5 moves, for display |
| `better_note`, `refutation_note` | `text` null | deterministic templates (API.md "Line notes") |
| `refutation_arrows` | `jsonb` null | `[[from,to],…]` |
| `second_best_win` | `real` null | stage B (MultiPV 2), for "great" |

Indexes: PK covers per-game reads; a GIN index on `themes` is unnecessary at this size (aggregation
always starts from one report's games).

**`report_weaknesses`**: one card (rank 1–3) per report.
| Column | Type | Notes |
|---|---|---|
| `report_id`, `rank` | PK | |
| `theme`, `name` | `text` | |
| `games_count`, `occurrences` | `smallint` | D7 |
| `examples` | `jsonb` | 2–3 example snapshots (API.md shape) |
| `why`, `how_to_avoid` | `text` null | Phase 3; null until written |
| `sources` | `jsonb` | `[{title,url,passage,chunk_id}]` |
| `explanation_status` | `text` | `pending` / `generated` / `cached` / `fallback` |

**`jobs`**: the queue (§6).
| Column | Type | Notes |
|---|---|---|
| `id` | `bigint` identity PK | |
| `kind` | `text` CHECK in (`prepare_report`,`analyse_game`,`build_report`,`deep_game`) | |
| `dedupe_key` | `text` | e.g. the game id; with `kind` prevents duplicate active jobs |
| `payload` | `jsonb` | arguments |
| `status` | `text` CHECK in (`queued`,`running`,`done`,`dead`) | |
| `priority` | `smallint` | higher first: deep 100, prepare/build 50, analyse 10 |
| `attempts`, `max_attempts` | `smallint` | |
| `run_after` | `timestamptz` | backoff: not before this time |
| `locked_by`, `locked_at` | | lease (§6.3) |
| `last_error` | `text` | |
| `created_at`, `finished_at` | `timestamptz` | |

Indexes:
```sql
-- what workers scan: only queued rows, in pick order
CREATE INDEX jobs_pick ON jobs (priority DESC, id) WHERE status = 'queued';
-- at most one active job per (kind, key): makes every enqueue idempotent
CREATE UNIQUE INDEX jobs_active_dedupe ON jobs (kind, dedupe_key) WHERE status IN ('queued','running');
```

**`position_evals`**: engine cache (§10).
| Column | Type | Notes |
|---|---|---|
| `fen_key` | `text` | FEN without the move counters (same position = same key) |
| `engine_profile` | `text` | evals from different settings never mix |
| `multipv` | `smallint` | 1 (bulk) or 2 (deep) |
| `result` | `jsonb` | score(s), best move(s), lines |
| PK `(fen_key, engine_profile, multipv)` | | |

**`http_cache`**: chess.com responses (§10).
`key text PK, status smallint, body jsonb, etag text, fetched_at, expires_at (null = never)`.

**`corpus_chunks`**: teaching text (§8).
| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | stable id from the source row + chunk index |
| `source`, `title`, `section`, `url` | `text` | for citations |
| `content` | `text` | what is embedded and shown |
| `content_hash` | `text` | re-embed only when content changes |
| `tags` | `text[]` | Lichess theme keys, from keyword rules |
| `embedding` | `vector(1536)` | |
| `tsv` | `tsvector`, generated (below) | full-text column, kept in sync by Postgres itself |
| `corpus_version` | `text` | |

```sql
tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || content)) STORED
```

Indexes: `HNSW (embedding vector_cosine_ops)`, `GIN (tsv)`, `GIN (tags)`.

**`theme_queries`**: one row per theme: the fixed concept query text, its FTS keyword query, and
its embedding (computed once at ingestion, so reports never pay for query embeddings).

**`llm_calls`**: one row per LLM or embedding call: `report_id`, `purpose`
(`grade`, `rewrite`, `explain`, `embed`), `provider`, `model`, `input_tokens`, `output_tokens`,
`cost_usd numeric(10,6)`, `latency_ms`, `cache_hit`, `outcome` (`ok`, `retried`, `fallback`,
`error`), `created_at`. This is the source of truth for cost metrics.

**`worker_heartbeats`**: `worker_id PK, started_at, beat_at, current_job`, so `/health` can say
whether any worker is alive.

### 5.3 Sizes
A 20-game report ≈ 20 game rows (often already present), ≈ 1,600 move rows, 3 card rows, ~45 job
rows. Corpus ≈ 2,500 chunks × 6 KB of vector ≈ 15 MB. Everything fits comfortably in a small
Postgres for thousands of reports.

### 5.4 Migrations
Alembic, one migration per change, written by hand (autogenerate as a starting point, reviewed).
The first migration also runs `CREATE EXTENSION IF NOT EXISTS vector`. Migrations run in the
one-shot `migrate` service before `api` and `worker` start (D23).

---

## 6. Background jobs

### 6.1 Job kinds and the fan-out / fan-in

```
prepare_report(report)          1 per report
   └─▶ analyse_game(game)       1 per game, shared between reports (dedupe_key = game id)
          └─▶ build_report(report)   enqueued by whichever analyse_game finishes the report's last game
deep_game(game)                 on first open of a game view (dedupe_key = game id)
```

**Why one job per game rather than one job per report (D1)?** Games are shared between reports, so
the unit of work is naturally the game. A failure retries one game, not the whole report. Two
workers can analyse two games of the same report at once. And "the report is finished when all its
games are" becomes an explicit, testable step.

### 6.2 Claiming a job

Each worker process runs a simple loop: claim one job, run it, record the result, repeat; sleep
~0.5 s when the queue is empty.

```sql
UPDATE jobs
   SET status = 'running', locked_by = :worker_id, locked_at = now(), attempts = attempts + 1
 WHERE id = (
       SELECT id FROM jobs
        WHERE status = 'queued' AND run_after <= now()
        ORDER BY priority DESC, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1)
RETURNING id, kind, payload, attempts, max_attempts;
```

`FOR UPDATE` locks the chosen row; `SKIP LOCKED` makes a second worker running the same query at
the same moment skip that row and take the next one instead of waiting. Two workers can never get
the same job.

### 6.3 Leases, crashes and the watchdog
- A claimed job holds a **lease** (`locked_at`). If a worker dies mid-job, the job stays `running`
  with an old `locked_at`.
- Each worker loop also runs a cheap **watchdog** query every ~30 s:
  - `running` jobs whose lease is older than the timeout (5 min; longer than any job) go back to
    `queued` (or `dead` if out of attempts);
  - reports `running` for more than 20 minutes are marked `failed: analysis_failed`.
- **Handlers are idempotent**, so running a job twice is harmless: moves are upserted by
  `(game_id, ply)`, games by `chesscom_id`, enqueues are de-duplicated by the unique index.
  This is *at-least-once* processing made safe by idempotency, the standard pattern.

### 6.4 Retries and dead jobs
- A handler raises a **retryable** error (chess.com 5xx or timeout, Stockfish crash, DB connection
  drop) → `status = queued`, `run_after = now() + backoff(attempt)` with exponential backoff and
  jitter (e.g. 5 s, 20 s, 80 s ± 20%).
- A **permanent** error (unparseable PGN, chess variant) or attempts exhausted → `status = dead`
  with `last_error`. A dead job is the queue's dead-letter list: kept for inspection, never retried
  automatically.
- What a dead job means for the report: a dead `analyse_game` marks the game `failed`; the report
  continues without it (with a note) unless more than a quarter of its games failed → report
  `failed: analysis_failed`. A dead `prepare_report` fails the report with the right code
  (`no_games`, `chesscom_unavailable`).

### 6.5 The fan-in race, and its fix
When an `analyse_game` finishes, it must check whether that was the **last** unfinished game of each
report containing it, and if so enqueue `build_report`. Done naively, two workers finishing the last
two games at the same moment can both see "one game still unfinished" (each other's, not yet
committed), and **neither** enqueues: the report hangs forever.

The fix is to serialise the check on the report row:

```sql
-- inside the same transaction that marks the game done, for each report containing it:
SELECT 1 FROM reports WHERE id = :report_id FOR UPDATE;      -- second finisher waits here

SELECT count(*) FROM report_games rg JOIN games g ON g.id = rg.game_id
 WHERE rg.report_id = :report_id AND g.analysis_status NOT IN ('done','failed');

-- if 0:
INSERT INTO jobs (kind, dedupe_key, payload, priority)
VALUES ('build_report', :report_id, jsonb_build_object('report_id', :report_id), 50)
ON CONFLICT (kind, dedupe_key) WHERE status IN ('queued','running') DO NOTHING;
```

The second transaction blocks on the row lock until the first commits, then sees the first game as
done. Under Postgres's default READ COMMITTED isolation, each statement sees data committed before
it started, so the count after the wait is correct. The watchdog also re-checks finished-but-unbuilt
reports as a safety net. This bug and its fix get a dedicated integration test (§15).

### 6.6 Priorities and fairness
`deep_game` (100) > `prepare_report` / `build_report` (50) > `analyse_game` (10). Within a priority,
oldest first. A 50-game report queued first will delay a 10-game report queued after it; acceptable
for the MVP, and noted for later (round-robin by report).

### 6.7 Worker model (D2)
Each worker is a **plain synchronous Python process**: one job at a time, one Stockfish subprocess,
no threads, no asyncio. Concurrency comes from running **several worker processes** (compose
`replicas: 2`), coordinated by `SKIP LOCKED`. Stockfish and the tagger are CPU-bound, so processes
(not threads or async) are the right tool in Python; one-job-at-a-time code is easy to read and
debug. Shutdown: on `SIGTERM` the worker finishes (or abandons) its current job and exits; an
abandoned lease is reclaimed by the watchdog.

---

## 7. Chess analysis core

Everything in this section is deterministic code: no AI.

### 7.1 Fetching games from chess.com
- `GET /pub/player/{u}/games/archives` → monthly archive URLs; walk **newest month first**,
  `GET` each until N matching games are collected (usually 1–3 requests).
- Filters (D9): `rules == "chess"` (no Chess960 or variants); `time_class` matches; skip games
  shorter than 10 plies (aborted or early resignations teach nothing); rated and unrated both count.
- chess.com's published guidance: **requests in series, not in parallel**; honour 429 with backoff;
  identify the client in `User-Agent` (D21). Past months never change, so they're cached forever;
  the current month for 5 minutes; conditional requests with `ETag` when refreshing.
- Untrusted input: every field is validated (Pydantic model of the archive response); PGN goes
  through python-chess; a game that doesn't parse is skipped, not fatal.

### 7.2 PGN → positions
python-chess parses the PGN (headers: players, result, ECO, ECOUrl, `FEN` for custom starts) and
walks the main line producing `N+1` positions (start, after each move) and each move's SAN/UCI.

### 7.3 Engine settings and determinism (D4)
- python-chess `SimpleEngine.popen_uci(stockfish_path)`, kept open for the worker's lifetime and
  restarted if it crashes.
- **`Threads = 1`, fixed `Hash`, a fixed node budget per position** (`Limit(nodes=…)`), hash cleared
  between games. Multi-threaded or time-limited searches give slightly different results on every
  run and every machine. A single-threaded, node-limited search gives the **same answer every
  time**, which makes tests stable, makes the position cache valid, and makes "the same game graded
  twice agrees" true.
- The node budget is picked by a benchmark script (D4): the target is ~0.1 s per position on the
  deployment machine (≈ depth 14–16), which reliably catches club-level errors. It's recorded in
  `engine_profile`, e.g. `sf17.1-n150k-v1`.
- Pinned Stockfish version, the same locally (brew) and in Docker (D22). Different versions
  evaluate differently; tests assert grades on clear-cut positions, never exact centipawns.

### 7.4 Stage A: one analysis per position, everything from it
For each of the `N+1` positions, one search (MultiPV 1) gives: the **evaluation** of the position,
the **best move**, and the **principal variation (PV)**. From consecutive positions we get, for the
move between them:

```
position before move k:  eval E_before, best move, PV_before   → better line = PV_before
position after  move k:  eval E_after,              PV_after    → refutation  = PV_after
win% loss for the mover = win%(E_before) − win%(E_after)  (from the mover's side)
```

So stage A already has **everything for the error grades and both lines**, with no extra search.
That's the key efficiency insight of this design: `N+1` searches per game, each reused twice.

Positions are looked up in `position_evals` first (openings repeat constantly across games and
users); only misses are searched, then stored.

Progress is written as the game goes: moves are upserted in batches of ~10 plies, so the Analysing
screen's trace for the running game grows live (API.md `games[].trace`).

### 7.5 Grades (from `PLAN.md` §4.2, unchanged)
`win% = 50 + 50 × (2 / (1 + e^(−0.00368208 × cp)) − 1)`, cp capped ±1000, mate = cap.

| Grade | Rule | Computed in |
|---|---|---|
| blunder / mistake / inaccuracy | loss ≥ 15 / 10 / 5 (+ Lichess mate rules) | A |
| miss | an error **and** the better line contains a winning tactic for the mover (tagger, ≥ 2 pawns or mate) **and** the played move did not itself allow a tagged tactic (D10) | A |
| best | played = engine best | A |
| excellent / good | loss < 2 / 2–5 | A |
| great | best **and** second-best ≥ 10 points worse (needs MultiPV 2) | **B** |
| brilliant | great-or-best **and** tagger flags `sacrifice` **and** mover below 90% before the move | **B** |

All thresholds live in one module (`grading.py`) with a `GRADING_VERSION` constant.

### 7.6 Stage B: the deep pass (D11)
With the design above, stage B only has to add what needs **MultiPV 2**: *great* and *brilliant*.
For each position it runs one MultiPV-2 search (cached in `position_evals` with `multipv = 2`),
stores `second_best_win`, and upgrades `best` → `great`/`brilliant` where the rules say so. It
**never touches error grades**, as signed off. Lines and notes already exist from stage A, so the
game view can show "Show better move" immediately on first open; `grading: pending` only means
"great/brilliant not computed yet".

### 7.7 Tagging (vendored lichess-puzzler)
- `app/vendor/lichess_puzzler/` holds the original `cook.py` and its helper modules, unmodified,
  with their AGPL licence; an adapter (`tagging.py`) is the only code that talks to it.
- **Allowed tactics** (for blunders and mistakes): the "puzzle" is the position after the error,
  the solver is the opponent, the line is `reply_pv`. **Missed tactics** (for errors): the position
  before, the solver is the mover, the line is `best_pv`.
- The ≥ 2 pawns-or-mate bar (same as Lichess puzzles): checked by material count / eval at the end
  of the line; lines that don't clear it get no themes.
- **Both colours are tagged** (D8): games are shared, so tomorrow's report may be the opponent's.
- The 2,000-puzzle verification from the research becomes a test with a 200-puzzle fixture
  (the Lichess puzzle database is CC0).

### 7.8 Line notes, example notes, arrows, openings
- Notes follow the deterministic templates already specified in API.md "Line notes"; implemented
  with python-chess (`board.attacks()`, material counting, piece values). Each template has unit
  tests on hand-built positions.
- Threat arrows: the squares of the user's pieces attacked by the reply that weren't attacked
  before it.
- Openings (D12): chess.com PGNs include `ECOUrl` (e.g. `…/openings/Italian-Game-Two-Knights-Defense`);
  the **family** is the part before the first variation word (`Italian Game`). Grouped by
  `(family, user colour)`, shown when played ≥ 4 times.

### 7.9 Building the report (fan-in job)
Set-based SQL does the counting, Python does the choosing:

```sql
-- themes the user allowed, ranked by games affected, then occurrences
SELECT t.theme,
       count(DISTINCT m.game_id) AS games,
       count(*)                  AS occurrences
  FROM report_games rg
  JOIN moves m ON m.game_id = rg.game_id AND m.color = rg.user_color
  CROSS JOIN LATERAL unnest(m.themes) AS t(theme)
 WHERE rg.report_id = :report_id AND m.grade IN ('blunder', 'mistake')
 GROUP BY t.theme
 ORDER BY games DESC, occurrences DESC
 LIMIT 3;
```

- **Count unit (D7):** the cards say "9 of 20 games", so the ranking unit is *games affected*, with
  occurrences as tie-breaker.
- **Examples:** up to 3 per theme, from **different games**, most costly first (largest win-%
  loss), built into the API.md example shape (position before, played, better, punishing line,
  note, arrows).
- **Missed tactics:** the same query over `missed_themes` for the user's errors.
- **Summary:** W/D/L from results, errors per game from `games.error_counts` for the user's colour;
  notes such as "Only 4 rapid games found; patterns may be weak." (fewer than 5 games).
- Phase 2 stops here (`why`/`how_to_avoid` null); Phase 3 adds the RAG step before the report is
  marked `done`.

---

## 8. RAG: the card explanations

Scope (signed off): **only the three cards' "why it happens", "how to avoid it" and sources** come
from RAG. Everything else is deterministic.

### 8.1 Why RAG here, honestly
- The engine knows *what* went wrong; it can't explain a *concept* or give a habit to fix it. That
  is natural-language teaching material, which is what retrieval is good at.
- The research showed embeddings **can't** match board positions to lessons (best 31% hit@5), but
  **concept queries** retrieve relevant text reliably (8/8 themes). So the design retrieves by
  *concept* (the theme), never by position.
- The corpus (~185K tokens) is too large to put in every prompt cheaply; retrieving ~4 passages
  costs ~25× less (§8.9), and citations come for free.

### 8.2 Ingestion (offline script, idempotent, no LLM)
```
corpus/*.jsonl  →  clean  →  chunk  →  tag  →  hash  →  embed (only new hashes)  →  upsert
```
- **Fix first:** the theme glossary's missing *Fork* row (`forkOpposingPiecesDescription`).
- **Chunking:** most rows are already paragraph-sized; rows over ~350 tokens are split recursively
  (paragraph → sentence) with ~15% overlap; sections stay together; tiny fragments (< 40 tokens)
  merge with a neighbour.
- **Tags:** deterministic keyword rules per theme (the reviewed keyword list from the research,
  with known false friends excluded, e.g. "hanging pawns" ≠ hanging piece).
- **Embeddings:** `text-embedding-3-small`, batched, only for chunks whose `content_hash` is new.
  A `--dry-run` prints the chunk count, tokens and cost first; the real run needs explicit
  approval (project rule). Expected cost ≈ $0.004 for the whole corpus.
- **Theme queries:** each theme gets a fixed natural-language concept query ("how to avoid leaving
  pieces undefended in chess") and a keyword FTS query (`hanging | undefended | unprotected |
  en <-> prise`), both reviewed by you, embedded once, stored in `theme_queries`.

### 8.3 Retrieval: one SQL query
Tag filter → vector ranking and full-text ranking → weighted Reciprocal Rank Fusion:

```sql
WITH candidates AS MATERIALIZED (
  SELECT id, embedding, tsv FROM corpus_chunks WHERE tags @> ARRAY[:theme]
),
vec AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> :query_vec) AS r
    FROM candidates ORDER BY embedding <=> :query_vec LIMIT 20
),
fts AS (
  SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
    FROM candidates, to_tsquery('english', :fts_query) AS q
   WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 20
)
SELECT c.id, c.source, c.title, c.section, c.url, c.content,
       coalesce(:w_vec / (60 + vec.r), 0) + coalesce(:w_fts / (60 + fts.r), 0) AS rrf
  FROM vec FULL OUTER JOIN fts USING (id)
  JOIN corpus_chunks c USING (id)
 ORDER BY rrf DESC
 LIMIT :k;
```

- `<=>` is pgvector's cosine distance; `@@` is Postgres full-text match; RRF adds `w / (60 + rank)`
  from each list, so a passage ranked well by **both** methods wins. Weights `w_vec`, `w_fts` are
  tuned on the eval set (§8.8).
- If the tag filter yields fewer than `k` candidates, the query re-runs without it.
- Results are de-duplicated by `(source, section)` so one article can't fill every slot.
- **`MATERIALIZED` matters.** It makes Postgres build the filtered candidate set first and rank it
  *exactly*. Without it, the planner may use the HNSW index to find the 40 nearest chunks overall
  and *then* apply the tag filter, silently returning fewer (or worse) results. That's the classic
  filtered-vector-search pitfall.
- **An honest note on the HNSW index:** with ~2,500 chunks, a filtered query ranks a few hundred
  rows exactly, which is both faster and more accurate than the index. The HNSW index exists for
  unfiltered searches (fallback now, coach chat later), where it starts to matter as the corpus
  grows; pgvector 0.8's iterative index scans make filtered HNSW searches safe when that day
  comes.
- Retrieval for a theme depends only on the theme and the corpus version, so its result is cached
  (§10).

### 8.4 The explanation graph (LangGraph), per card
```
retrieve ─▶ grade passages ─▶ enough relevant? ──yes──▶ generate ─▶ validate ──ok──▶ done
              ▲                     │no                                │fail
              └── rewrite query ◀───┘ (≤ 2 times)                      └─▶ regenerate once with the
                                    then: glossary fallback                errors ─▶ fail again ─▶ fallback text
```
- **grade:** one LLM call grades all passages at once ("relevant to avoiding <theme>? yes/no each"),
  structured output. Cheap, and it removes off-topic passages before generation.
- **rewrite:** produces an alternative concept query; bounded at 2 loops (course Ch 25). Honest
  expectation: because theme queries are fixed and evaluated, this loop rarely triggers; it's a
  safety net, and the logs will show how often it fires.
- **generate:** gpt-4o-mini (fallback Claude Haiku), `temperature = 0`, structured output:
  `{why: str, how_to_avoid: str}` with the API's inline marks (`*…*`, `[n]`).
- **fallback text:** if generation fails entirely (both providers down, validator rejects twice),
  the card gets a deterministic text built from the theme glossary entry and its citation. **A
  report never fails because of the LLM** (D27); `explanation_status = 'fallback'` and a metric
  record it.
- The three cards run **in parallel** (a thread pool inside the `build_report` job), since each is
  mostly waiting on the network.

### 8.5 The prompt (grounded)
The input is **facts, not free text**:
- the theme and its one-line definition;
- per example: phase, opening family, the move played with its grade, the better move, the
  punishing line (SAN), and the deterministic note ("4… Qg5! attacks your knight on e5 and your pawn
  on g2");
- the retrieved passages, numbered `[1]…[n]`, each with its source title.

Instructions: use **only** these passages for advice and cite them as `[n]`; base "why" on the
examples; mention no move that isn't in the examples; plain English for a club player; two to four
sentences each. Usernames never appear in the prompt (§12).

### 8.6 The output validator (domain guardrail)
Rejects the output if:
1. it mentions a chess move (SAN pattern) that isn't in the set of moves given in the examples,
   or that isn't legal in its example position (python-chess check);
2. a citation `[n]` points outside `1…n`, or "how to avoid" cites nothing;
3. it uses formatting other than `*…*` and `[n]`, or exceeds the length limits;
4. it's empty or not in the expected structure.
One regeneration with the specific errors listed, then the fallback text.

### 8.7 Reliability around every LLM call
- **Token budget pre-flight:** count tokens (tiktoken) before sending; drop the lowest-ranked
  passages until the prompt fits the budget (e.g. 3,000 input tokens).
- **Timeouts and retries:** 20 s timeout; up to 2 retries with exponential backoff + jitter for
  timeouts, 429 and 5xx.
- **Circuit breaker** per provider: after 5 consecutive failures, skip that provider for 60 s and
  go straight to the fallback; one trial call then closes it again. It stops a provider outage from
  making every report wait through every retry.
- **Fallback chain:** gpt-4o-mini → Claude Haiku → deterministic text.
- **Logged:** every call (including cache hits and failures) is a row in `llm_calls` with tokens,
  cost, latency and outcome.

### 8.8 Retrieval evaluation (keep doing what worked)
- A **fresh** query set: new seed from the Lichess puzzle DB, frozen in git **before** the corpus is
  touched, as in the research.
- For each theme's query: hit@k (does a top-k passage teach that theme?), judged by keyword score
  as a rough signal and a **blind human check** as the main measure.
- Compare variants: vector only, FTS only, hybrid; tag filter on/off; RRF weights. The chosen
  configuration and its numbers go into the README.
- Runs as a script (`scripts/eval_retrieval.py`), not in the unit tests: it touches the real corpus
  and (once) the embeddings API.

### 8.9 Cost accounting and the long-context comparison
Per report (gpt-4o-mini at $0.15 / 1M input, $0.60 / 1M output; estimates):

| | Calls | Tokens in / out per call | Cost |
|---|---|---|---|
| RAG (grade + generate × 3 cards) | 6 | ~2,000 / ~300 | ≈ $0.003 |
| Long-context baseline (whole corpus in each generate call) | 3 | ~185,000 / ~300 | ≈ $0.084 |

- `/metrics` shows the **measured** cost of every report (from `llm_calls`) next to the **computed**
  baseline (corpus token count × calls × price), plus the ratio (~28×).
- To keep the baseline honest, it is **measured for real once** on a sample report (≈ $0.09, needs
  your approval), and the result goes into the README (D28).
- Query embeddings cost nothing per report (precomputed); explanation caching makes re-runs free.

### 8.10 Where LangChain is and isn't used (D29)
| Used | Why |
|---|---|
| LangGraph | the self-correcting graph with explicit nodes, edges, bounded loops and a fallback node; traceable in LangSmith |
| `ChatOpenAI`, `ChatAnthropic` | one interface for both providers; `with_structured_output`; `with_fallbacks` |
| `OpenAIEmbeddings` | batching and retries for ingestion |
| LangSmith | optional tracing when a key is set |

| Not used | Why |
|---|---|
| LangChain's PGVector vector store | it imposes its own tables and can't do our tag filter + FTS + RRF in one query; we own the SQL |
| LangChain retrievers / chains for retrieval | same reason; retrieval is one function returning rows |

---

## 9. API layer

### 9.1 Structure
- `create_app()` builds the FastAPI app: routers per resource (`players`, `reports`, `games`,
  `ops`), middleware, exception handlers, lifespan (DB engine, HTTP client).
- **Schemas** (`schemas.py`): Pydantic models that mirror `docs/API.md` field for field. They're
  the response models of the routes, so FastAPI validates every response and the OpenAPI docs at
  `/docs` show the real contract.
- **Dependencies** (`Depends`): DB session per request, settings, the chess.com client. Easy to
  replace in tests.
- **Handlers stay thin**: parse → call a service function → return a schema. Logic lives in
  services (§17).

### 9.2 Async API, sync worker (D3)
- The API is **async** (`async def` routes, SQLAlchemy async session over psycopg 3, async httpx).
  Its work is waiting on the database and chess.com; async handles many waiting requests on one
  thread, the same model as Node's event loop.
- The worker is **sync**: its work is CPU (Stockfish, tagger), where async brings nothing.
- **One driver for both: psycopg 3** (`postgresql+psycopg://`, already in `.env.example`); it
  supports sync and async.

### 9.3 Errors: one shape everywhere
Every error is `{"error": code, "detail": message}` (API.md), plus `request_id`.
- Domain exceptions (`UsernameNotFound`, `ReportNotFound`, …) map to status + code in one handler.
- **FastAPI's default 422 body is a different shape** (`{"detail": [ … ]}`); a custom
  `RequestValidationError` handler converts it to `{"error": "invalid_input", "detail": "…"}`.
- Unexpected exceptions → 500 `{"error": "internal_error"}`, never a stack trace; the trace goes to
  the logs with the request id.

### 9.4 Input validation
- `username`: `^[A-Za-z0-9_-]{3,25}$`, lower-cased.
- `time_control`: enum; `games`: one of 10/20/30/50 (`Literal`).
- Request bodies are limited in size; unknown fields rejected (`extra = "forbid"`).

### 9.5 Idempotent report creation (D16)
`POST /api/reports` with the same `(username, time_control, games)` as a report created in the last
**60 minutes** that isn't `failed` returns that report (`200`, its current status) instead of
starting another. That covers double-clicks, refreshes and "run it again" without a separate
idempotency key, and it's the "reuse a recent result" feature from the plan.

### 9.6 Rate limits and back-pressure (D24)
Two different protections:
- **Per client (slowapi, by IP):** `POST /reports` 5 per 10 minutes; `GET /players` 60 per
  minute; `GET` reports/games 240 per minute (polling at 1 s is ~60/min). Excess → `429 rate_limited`.
- **Global capacity:** if more than 20 reports are queued or running, `POST /reports` returns
  `503 busy` ("Lots of people are analysing right now — try again in a few minutes"). This protects
  the CPU-bound workers, which per-IP limits alone can't do.

### 9.7 Public ids
Report ids are random and unguessable (`r_` + 10 base32 chars ≈ 50 bits). With no accounts, the
report link is the access key, like an unlisted video link. Game ids are positions inside a report
(`g_1` … `g_N`), so no internal id is ever exposed.

### 9.8 Contract safety (D19)
The frontend's `types.ts` and the backend's `schemas.py` describe the same contract by hand. To
catch drift: a backend test validates the JSON examples from `docs/API.md` against the Pydantic
models, and the end-to-end check in Phase 4 runs the real frontend against the real API. (Optional
alternative: generate `types.ts` from FastAPI's OpenAPI schema.)

---

## 10. Caching

| # | Cache | Key | Lifetime | Where | Why it pays |
|---|---|---|---|---|---|
| 1 | chess.com player stats | username | 10 min | `http_cache` | Home looks players up while typing |
| 2 | chess.com monthly archives | URL | past months: forever; current month: 5 min | `http_cache` | Past months never change; re-runs fetch nothing |
| 3 | **Game analysis** | `chesscom_id` | forever (per `engine_profile`) | `games` + `moves` | A game is analysed once, whoever asks: re-running a username is near-instant |
| 4 | **Position evals** | FEN (no clocks) + engine profile + MultiPV | forever | `position_evals` | Openings repeat across games and users; every hit saves a Stockfish search |
| 5 | Retrieval results | theme + corpus version + config hash | until the corpus or config changes | `http_cache`-style table or in-memory | Same theme → same passages |
| 6 | Card explanations | hash(theme, example facts, passage ids, model, prompt version) | 30 days | table | A re-run of the same report costs $0 |

- Everything is in Postgres: no Redis, survives restarts, shared by every process, inspectable with
  SQL.
- Each cache counts hits and misses into the report's `stats` (worker side) or the API's in-memory
  counters, which feed `/cache/stats` and `/metrics`.
- Honest expectations: caches 2–4 hit often; cache 6 rarely hits across *different* users (their
  examples differ), only on re-runs.

---

## 11. Failure handling

| What fails | Detected by | What happens | What the user sees |
|---|---|---|---|
| Username doesn't exist | chess.com 404 on lookup | no report created | Home: "No chess.com player called …" (404) |
| No games in that time control | `prepare_report` finds 0 | report `failed: no_games` | "No rapid games found … Try 'Both'." |
| Few games (< 5) | `prepare_report` | continues, note added | report with "patterns may be weak" |
| chess.com down / 5xx / timeout | httpx error | job retried with backoff (3×), then report `failed: chesscom_unavailable` | Analysing screen waits, then the failure message |
| chess.com 429 | status code | job back to queue with longer backoff | slower, no error |
| Unparseable game | python-chess | game skipped, `failed`; report continues | game missing from the list, note if many |
| Stockfish crashes | `EngineTerminatedError` | engine restarted, job retried | nothing |
| Stockfish binary missing | startup check | worker refuses to start; `/health` unhealthy | ops issue, caught at deploy |
| Worker killed mid-job | lease expires | watchdog re-queues the job | short delay |
| Report stuck (any reason) | watchdog: running > 20 min | `failed: analysis_failed` | failure message + Try again |
| Database down | connection error | API 503 `service_unavailable`; workers retry connecting | error message |
| LLM timeout / 5xx / 429 | client error | retry → other provider → fallback text | card text (maybe the fallback) |
| LLM output invalid | validator | regenerate once → fallback text | card text |
| Provider outage | circuit breaker opens | goes straight to the fallback | nothing |
| Corpus not ingested | startup check | cards use fallback text; `/health` warns | card text from the glossary |
| Too many reports at once | capacity check | `503 busy` | "try again in a few minutes" |

---

## 12. Security

**Threat model.** No accounts and no private data: everything shown is public chess.com data. The
assets to protect are **availability** (CPU, LLM budget), the **API keys**, and the **integrity of
what's shown** (no invented moves, no injected content).

| Threat | Mitigation |
|---|---|
| Abuse of CPU (many reports) | per-IP rate limits + global capacity limit (§9.6) |
| Abuse of LLM budget | LLM runs only inside `build_report` (3 cards per report); explanation cache; token budget |
| **Prompt injection via chess.com data** (an opponent's username, a PGN comment) | Usernames and PGN text **never enter a prompt**; prompts contain only SAN moves, FEN-derived facts and themes, all produced or validated by python-chess. No user free text reaches an LLM in the first cut (the coach chat will add the sanitizer, scope guard and input limits from the course) |
| LLM output inventing moves or adding markup | output validator (§8.6); the frontend renders text, never HTML |
| SQL injection | parameterised queries only (SQLAlchemy); no string-built SQL |
| Guessing report URLs | random 50-bit ids |
| Secret leakage | keys only in env vars; `.env` never in git or the image; keys never logged (log redaction for `Authorization` headers) |
| Container breakout impact | non-root user, minimal image, DB not exposed outside the compose network in production |
| Licence compliance | AGPL-3.0: the UI/README links to the source |

Not needed: PII masking (no personal data), authentication (no accounts), CSRF (no cookies or
sessions).

---

## 13. Observability

### 13.1 Logs
JSON, one object per line, to stdout (Docker collects them): `ts`, `level`, `msg`, `service`
(`api`/`worker`), `request_id` or `job_id`, `report_id`, `duration_ms`, plus event fields. Every
request logs one access line; every job logs start/end/retry/dead; every LLM call logs model,
tokens, cost and outcome. A request id comes from `X-Request-ID` or is generated, and is returned in
the response header and error body.

### 13.2 `/health`
```json
{ "status": "healthy",
  "checks": { "database": true, "pgvector": true, "migrations": true, "stockfish": true,
              "corpus": true, "workers_alive": 2 },
  "queue": { "queued": 4, "running": 2, "dead_24h": 0 },
  "version": "0.1.0" }
```
`unhealthy` (HTTP 503) if the database or Stockfish fails; `degraded` if no worker heartbeat or the
corpus is missing. The Docker `HEALTHCHECK` uses it.

### 13.3 `/metrics` (JSON)
- **API:** requests, errors, p50/p95 latency per route (in-memory, since process start).
- **Reports:** count by status, average and p95 duration, average games per report (SQL).
- **Engine:** positions analysed, position-cache hit rate, average seconds per game.
- **LLM:** calls by purpose and outcome, tokens, total cost, **cost per report**, fallback rate,
  validator rejection rate.
- **RAG vs long context:** measured RAG cost per report, computed baseline, ratio (§8.9).
- `/cache/stats`: hits, misses and entries per cache (§10).

### 13.4 Tracing
LangSmith traces each explanation graph run (nodes, prompts, tokens) when `LANGSMITH_API_KEY` is
set; nothing is sent otherwise.

---

## 14. Configuration
pydantic-settings, validated at startup (a missing required value stops the process with a clear
message). `.env.example` documents every variable.

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — | `postgresql+psycopg://…` |
| `APP_ENV`, `LOG_LEVEL` | `development`, `INFO` | |
| `STOCKFISH_PATH` | `stockfish` | |
| `ENGINE_NODES`, `ENGINE_HASH_MB` | from benchmark, `64` | D4 |
| `WORKER_ID` | hostname | |
| `JOB_LEASE_SECONDS`, `REPORT_TIMEOUT_MINUTES` | `300`, `20` | |
| `REPORT_REUSE_MINUTES`, `MAX_ACTIVE_REPORTS` | `60`, `20` | |
| `RATE_LIMIT_*` | as §9.6 | |
| `CHESSCOM_USER_AGENT` | `BlunderTrace/0.1 (+repo URL)` | D21 |
| `OPENAI_API_KEY` | — | required in Phase 3 |
| `ANTHROPIC_API_KEY` | empty | if empty, the fallback provider is skipped (logged at startup) |
| `PRIMARY_MODEL`, `FALLBACK_MODEL`, `EMBEDDING_MODEL` | `gpt-4o-mini`, `claude-haiku-…`, `text-embedding-3-small` | |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `PROMPT_TOKEN_BUDGET` | `20`, `2`, `3000` | |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | empty | tracing off when empty |

Prices per model live in code (`llm/pricing.py`) with the date they were checked.

---

## 15. Testing

The pyramid (course Ch 23), adapted:

| Level | What | Needs | When it runs |
|---|---|---|---|
| **Unit** | win%, grading rules (incl. mate rules), line-note templates, arrows, opening family parsing, archive/PGN parsing (recorded fixtures), RRF math, validator, token budget, circuit breaker, backoff, schemas vs API.md examples | nothing | always; < 5 s |
| **Engine** | known positions: mate in 1 missed → blunder; hanging queen → blunder + `hangingPiece`; quiet best move → best | Stockfish binary | marker `engine`; always locally |
| **Tagger** | 200-puzzle fixture → themes match Lichess labels | nothing (pure Python) | always |
| **Integration** | migrations apply; job claim with two concurrent sessions (no double claim); **fan-in race** (two finishers, exactly one `build_report`); lease expiry → re-queue; report assembly from seeded moves; API endpoints end-to-end with a fake chess.com and a fake LLM | Postgres (compose `db`, separate test database) | marker `db` |
| **Retrieval eval** | hit@k per theme and variant | ingested corpus | script, on demand |
| **Live smoke** | one real report with a real username | everything + keys | manual, before release |

Rules: **no network and no paid API in the test suite** (chess.com via recorded fixtures with
`respx`; LLMs via LangChain's fake chat model). Every bug fixed gets a test first.

---

## 16. Packaging, running and deployment

### 16.1 The image
One multi-stage Dockerfile for `api`, `worker` and `migrate`:
- **builder:** `uv sync --frozen --no-dev` into a virtualenv (dependency layer cached until
  `uv.lock` changes);
- **runtime:** `python:3.12-slim` + a **pinned Stockfish binary** (D22) + the virtualenv + `app/`;
  non-root `appuser`; `HEALTHCHECK` on `/health` (api only);
- different `command:` per service: `uvicorn app.main:app`, `python -m app.jobs.worker`,
  `alembic upgrade head`.

### 16.2 Compose services
`db` (with volume) → `migrate` (`depends_on: db healthy`, exits 0) → `api` and `worker ×2`
(`depends_on: migrate completed successfully`) → `web` (nginx serving the built frontend and
proxying `/api` to `api`; D25). Only `web` publishes a port in production mode.

### 16.3 Local development
- `docker compose up -d db` for Postgres; `uv run uvicorn app.main:app --reload` and
  `uv run python -m app.jobs.worker` on the host (Stockfish from brew); `npm run dev` for the
  frontend with Vite's proxy forwarding `/api` to port 8000 and `VITE_API_MOCK=false`.
- The corpus is ingested once with `uv run python scripts/ingest_corpus.py --dry-run`, then for
  real after approval.

### 16.4 Hosting
Deferred to Phase 5 (open decision in PLAN.md). The compose stack runs as-is on any single VM;
managed platforms need a worker service and a Postgres with pgvector. Stockfish needs real CPU, so a
small VM with 2–4 cores is the simplest fit.

---

## 17. Code organisation

```
backend/
├── pyproject.toml · uv.lock · Dockerfile · alembic.ini
├── alembic/versions/                 migrations
├── app/
│   ├── main.py                       create_app(): routers, middleware, handlers, lifespan
│   ├── config.py                     Settings (pydantic-settings)
│   ├── schemas.py                    API models = docs/API.md
│   ├── api/                          players.py · reports.py · games.py · ops.py · deps.py · errors.py
│   ├── services/                     reports.py (create/reuse/assemble) · games.py (assemble, trigger deep pass)
│   ├── db/                           base.py · session.py (async + sync) · models.py · queries/*.py (hand-written SQL)
│   ├── jobs/                         queue.py (enqueue/claim/finish/retry) · handlers.py (kind → function) · worker.py (loop, watchdog, heartbeat)
│   ├── chesscom/                     client.py (HTTP, cache, politeness) · models.py (response validation) · select.py (filters, last N)
│   ├── analysis/                     engine.py · positions.py · grading.py · tagging.py · notes.py · openings.py · aggregate.py · pipeline.py
│   ├── rag/                          ingest.py · chunking.py · tag_rules.py · retrieval.py · graph.py · prompts.py · validator.py · fallback.py
│   ├── llm/                          clients.py · pricing.py · budget.py · breaker.py · calls.py (llm_calls logging)
│   ├── observability/                logging.py · metrics.py · health.py
│   └── vendor/lichess_puzzler/       cook.py etc. (unmodified) + LICENSE
├── scripts/                          ingest_corpus.py · eval_retrieval.py · benchmark_engine.py
└── tests/                            unit/ · engine/ · integration/ · fixtures/
```

**Layering rules:**
1. `analysis/`, `rag/validator.py`, `rag/chunking.py` and the grading/notes code are **pure
   functions**: input data → output data, no database, no network. That's where the important
   logic lives, so it's trivially testable ("functional core").
2. `jobs/handlers.py` and `services/` do the I/O: load from the DB, call the pure functions, save
   results ("imperative shell").
3. `api/` only translates HTTP ↔ services.
4. SQLAlchemy ORM for ordinary reads and writes; **hand-written SQL** (in `db/queries/`) where the
   SQL itself is the point: job claiming, fan-in, aggregation, hybrid retrieval.
5. No generic "repository" abstraction layer: it would add indirection without a second database
   to justify it.

---

## 18. Libraries

| Library | For | Notes |
|---|---|---|
| fastapi, uvicorn[standard] | API server | decided |
| pydantic v2, pydantic-settings | schemas, config | decided |
| sqlalchemy 2.0, alembic | ORM, migrations | decided |
| psycopg[binary] 3 | Postgres driver (sync + async) | D3 |
| pgvector (Python) | `vector` column type for SQLAlchemy | |
| httpx | chess.com client (async in api, sync in worker) | |
| chess (python-chess) | PGN, boards, engine protocol | decided |
| tenacity | retries with backoff + jitter | |
| slowapi | per-IP rate limits | course Ch 22 |
| tiktoken | token counting for the budget | |
| langchain-core, langchain-openai, langchain-anthropic, langgraph, langsmith | Phase 3 | decided |
| pytest, respx | tests; HTTP mocking | |
| ruff | lint + format | already in use |
| mypy | static type checking (D26) | optional |

Deliberately not added: Redis, Celery, an ORM-repository framework, structlog (stdlib logging with a
small JSON formatter is enough; D26), Prometheus client (JSON `/metrics` as API.md specifies).

---

## 19. Performance and cost budget

### 19.1 Analysis time (estimates, confirmed by `benchmark_engine.py` in step 8)
| Item | Estimate |
|---|---|
| Positions per game | ~80 (+1) |
| Search per position | ~0.1 s (node budget set to hit this on the target machine) |
| Position-cache hits | ~10–20% (openings) |
| One game | ~7–9 s |
| 20 games, 2 workers | ~70–90 s analysis + ~3 s chess.com + ~5–10 s RAG ≈ **1.5–2 min** |
| Game deep pass (MultiPV 2) | ~10–15 s |

### 19.2 Money per report
LLM ≈ $0.003 (§8.9); embeddings $0 (precomputed); chess.com and Stockfish free. One-time:
corpus embedding ≈ $0.004; the real long-context measurement ≈ $0.09.

---

## 20. Build plan

Phase 2 and later, refined from `PLAN.md` §4.7. Each step ends with its tests passing and its
explainer chapter written (`explainers/backend/`, local only).

| Step | Builds | Done when |
|---|---|---|
| 6 | Project layout, config, JSON logging, error handling, schemas, SQLAlchemy models, first Alembic migration, `/health` (DB + pgvector) | `docker compose up -d db` + migrate + `/health` green; schema tests pass |
| 7 | chess.com client with HTTP cache, filters, `GET /api/players/{u}` | real lookup works; fixture tests pass |
| 8 | Engine wrapper, benchmark script, position cache, grading module | engine tests pass on known positions; node budget chosen |
| 9 | Vendored tagger + adapter, notes, arrows, openings | 200-puzzle test passes; template tests pass |
| 10 | Jobs: queue, worker, watchdog, heartbeats; `prepare_report` → `analyse_game` → `build_report` (no RAG); `POST`/`GET /api/reports` | a real 20-game report via the API; concurrency + fan-in tests pass |
| 11 | `deep_game`, `GET /api/reports/{id}/games/{gid}` | game view data complete; frontend runs on the real API (cards without text) |
| 12 | Corpus ingestion (dry run → approved run) | chunks + tags + embeddings in pgvector |
| 13 | Retrieval + eval on a fresh query set | hit@k numbers recorded |
| 14 | LLM layer: clients, budget, retries, breaker, fallback, `llm_calls` | unit tests with fake models pass |
| 15 | Explanation graph + validator + fallback text + cache | real report with card text; validator tests pass |
| 16 | `/metrics`, `/cache/stats`, LangSmith; long-context measurement (approved) | cost per report and ratio visible |
| 17 | Rate limits, capacity limit, end-to-end error states | each failure row in §11 demonstrated |
| 18 | Production Dockerfile, full compose with `web` | `docker compose up` runs everything from a clean machine |
| 19 | End-to-end check with real usernames | frontend + backend agree on every screen |

---

## 21. Decision register

Each item: the options, my recommendation, and why. Status is **pending** until you decide.

| # | Decision | Options | Recommendation | Why |
|---|---|---|---|---|
| D1 | Job granularity | (a) one job per report; (b) prepare → one job per game → build | **(b)** | games are shared; per-game retries; parallel games; explicit fan-in (§6.1) |
| D2 | Worker concurrency | (a) sync processes × replicas; (b) asyncio worker; (c) threads | **(a)**, 2 replicas | CPU-bound work; simplest code; SKIP LOCKED coordinates (§6.7) |
| D3 | API style + driver | (a) async API + sync worker, psycopg 3; (b) all sync | **(a)** | API waits on I/O (like Node); worker is CPU; one driver (§9.2) |
| D4 | Engine limit | (a) fixed nodes, 1 thread; (b) time per move; (c) depth | **(a)**, value from benchmark | deterministic → stable tests, valid cache (§7.3) |
| D5 | Lines in stage A | store PVs in A (lines + notes ready immediately) vs compute lines in B | **store in A** | free: the searches already produce them; needed for tagging anyway (§7.4) |
| D6 | Position-eval cache | yes / no | **yes** | real, measurable hit rate on openings (§10) |
| D7 | Theme count unit | games affected vs occurrences | **games**, occurrences as tie-break | the UI says "9 of 20 games" (§7.9) |
| D8 | Tag both colours | both vs user only | **both** | games are shared between reports (§7.7) |
| D9 | Game filters | standard chess only; skip < 10 plies; rated + unrated | **as listed** | variants break analysis; tiny games teach nothing |
| D10 | Miss vs blunder precedence | miss only if the move didn't also allow a tagged tactic | **as listed** | a move that both misses and allows a tactic is better described as the blunder |
| D11 | Stage B scope | only great/brilliant (MultiPV 2) | **yes** | everything else already exists after A (§7.6) |
| D12 | Opening names | chess.com `ECOUrl` family vs Lichess openings table | **ECOUrl family** | already in every PGN; no extra data |
| D13 | Queue in Postgres | yes (already planned) | **yes** | one transaction for report + job; no extra service |
| D14 | Lease, not heartbeat-per-job | lease timeout 5 min + watchdog | **yes** | simplest correct crash recovery (§6.3) |
| D15 | Partial results on game failure | continue unless > 25% of games fail | **yes** | one odd game shouldn't sink a report |
| D16 | Reuse window | 60 min, same username + settings, not failed | **yes** | idempotency + "re-run reuses result" (§9.5) |
| D17 | Report id format | `r_` + 10 random base32 | **yes** | unguessable, short |
| D18 | Game id in URLs | `g_{position}` within report vs global id | **position** | short; no internal ids exposed |
| D19 | Contract safety | test API.md examples vs schemas (+ e2e) vs generate TS from OpenAPI | **tests** | keeps hand-written, commented `types.ts`; generation is optional later |
| D20 | Caches in Postgres, no Redis | yes / Redis | **Postgres** | one stateful service; survives restarts (§10) |
| D21 | chess.com `User-Agent` | generic with repo URL vs with your contact email | **repo URL only** | chess.com asks for identification; your email stays private unless you choose it |
| D22 | Stockfish in Docker | pinned official release binary vs Debian package | **pinned official binary** (same version as local) | same evals locally and in Docker; Debian's version can lag |
| D23 | Migrations | one-shot `migrate` service vs on API startup | **migrate service** | never two processes migrating at once; clear failure |
| D24 | Limits | per-IP slowapi + global capacity 503 | **both**, values in §9.6 | per-IP alone can't protect CPU |
| D25 | Serving the frontend | nginx container vs FastAPI static files | **nginx** | standard reverse-proxy setup; API stays API-only |
| D26 | Python tooling | ruff + mypy vs ruff only; stdlib JSON logging vs structlog | **ruff + mypy (lenient), stdlib logging** | type checking catches bugs (like vue-tsc); fewer dependencies |
| D27 | LLM failure policy | fallback text vs fail the report | **fallback text** | a report never fails because of the LLM (§8.4) |
| D28 | Long-context baseline | computed only vs computed + one real measurement | **both** (~$0.09 once, with approval) | the comparison is the headline number; measure it once for real |
| D29 | LangChain scope | models + structured output + fallbacks + LangGraph; own SQL retrieval | **as listed** | use the framework where it adds value (§8.10) |
| D30 | CI/CD | none (as you said earlier) vs one small test workflow | **none for now** | your instruction; can be revisited after the first cut |

---

## 22. Changes this proposes to API.md and PLAN.md
If the decisions above are accepted:
1. **API.md §3:** `grading: "pending"` only means *great/brilliant* aren't computed yet; lines,
   notes and other grades are present from the first response (D5, D11).
2. **API.md §2:** `weaknesses[].count` = number of games affected (D7).
3. **API.md errors:** add `503 busy` for the global capacity limit (D24).
4. **PLAN.md §4.5:** schema replaced by §5 of this document (adds `position_evals`, `http_cache`,
   `theme_queries`, `worker_heartbeats`; renames `report_cards` → `report_weaknesses`).
5. **PLAN.md §4.6:** folder structure replaced by §17.
6. **PLAN.md §4.7:** build order replaced by §20.

---

## 23. Risks
| Risk | Mitigation |
|---|---|
| Grading quality at the chosen node budget | benchmark against known positions; budget is a setting; grades recomputable from stored evals |
| Tagger adapter edge cases (promotion lines, mates at the end) | puzzle fixture test; unit tests per edge case |
| chess.com API changes or blocks | response validation surfaces it immediately; cached data keeps working |
| LLM text quality | validator + grounded prompt + eval of a few real reports by eye |
| Thin corpus for some themes (trapped piece, exposed king) | measured in the retrieval eval; targeted additions only where it shows a gap |
| Scope creep | this document is the scope; changes go through the decision register |
