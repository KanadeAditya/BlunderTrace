# BlunderTrace — Backend Design

This is the design of record for the backend. Every decision here was made one at a time in
conversation, from the big picture down to the details, on 17 November 2026, followed by a final
full check on 18 November. The frontend's design of record is [`DESIGN.md`](DESIGN.md), and the API
contract both sides follow is [`API.md`](API.md).

How to read it: section 1 says what the backend does, section 2 lists every decision on one page,
and the remaining sections explain each part in more detail. Section 17 lists the small details
that were settled while writing this document. Section 18 lists what the final check found and how
each point was settled. Section 19 lists what is left to decide while building.

---

## 1. What the backend does

1. Takes a chess.com username and checks the player exists.
2. Downloads the player's recent games.
3. Runs Stockfish over every move of every game and grades each move.
4. Names each mistake (fork, pin, hanging piece…) and counts which ones repeat.
5. For the top 3, retrieves chess theory from a small library and has an AI write "why it
   happens" and "how to avoid it", with citations.
6. Serves all of this to the frontend through the endpoints in API.md, including progress while
   the analysis runs.

Steps 2–5 are slow: about 11 seconds of engine time per game on one core, so they always run in the
background, never inside a web request.

**AI is used in one place only:** the text of the top 3 weakness cards. Everything else (grades,
lines, notes, counts) comes from Stockfish and plain code, so it is always correct and free.

---

## 2. Decisions at a glance

### The big picture

| Decision | Choice | Why |
|---|---|---|
| Monolith or microservices | **Modular monolith**: one codebase with strict folder boundaries | One developer, one product, one database; microservices solve problems we don't have |
| Where Stockfish runs | **On the server** | Deeper, trustworthy analysis that works on any device and survives closing the tab. Browser analysis is saved as post-launch item 4 in PLAN.md |
| Surviving restarts | **All progress is saved in Postgres** | A restart loses at most the one game being analysed, and work resumes by itself |
| Running processes | **One codebase started in two roles:** `api` and `worker` (×N) | The website stays fast while Stockfish runs; more workers = more capacity |
| What serves the website | **Caddy** in front: serves the Vue files and passes `/api` to `api` | One address for the browser (no CORS); Caddy does compression, caching and, if ever hosted, HTTPS automatically |
| Unit of work | **One job per game**, plus a final "build the report" job | Workers share a report; a game is analysed once even if it is in several reports |
| Where data lives | **Postgres for everything**: app data, the library, vectors, caches, the job queue | No Redis; one thing to run and back up |
| When the AI fails | **The report still finishes**, with fixed glossary text instead of AI text | A report never fails because of the AI |
| The library's vectors | **Built once and shipped with the project** | No API key needed to run; everyone gets identical vectors |
| Monitoring | **Built in only**: JSON logs, `/health`, `/metrics` | Simple; no extra services |
| Creating tables | **On startup, if missing** (`CREATE TABLE IF NOT EXISTS`); big changes by hand-written script | No migration tool needed for this project |
| Hosting | **Not now**: runs locally with `docker compose up` | The goal is a working product first |

### The details

| Area | Choice | Why |
|---|---|---|
| Folder layout | **By feature**, every area its own folder, one-way dependencies checked by import-linter | "Very modular": each part can be read and tested on its own |
| A game's moves | **Stored as JSON inside the game's row** | Written and read as one piece, already in API.md's shape |
| Talking to Postgres | **Plain SQL with psycopg**, rows checked by Pydantic | One set of models; our special queries are plain SQL |
| Job queue | **Procrastinate** (a Postgres job queue library) | Proven retries, wake-ups and crash detection; no Redis |
| Job order | **One queue; preparing and building reports go first**; games first come, first served | A report whose games are done never waits behind someone else's games |
| Shared games | **A game is analysed once and shared across reports and users**, identified by its chess.com link | Asking again (more games, Both, next week) only analyses new games |
| A game that keeps failing | **Skipped, with a note** in the report | One bad game shouldn't throw away the rest |
| Retries | **Only temporary errors are retried** (chess.com, the database, a Stockfish crash); anything else fails at once | A bad game costs seconds, not minutes |
| Stuck reports | **A check every 5 minutes** repairs or fails any report that can no longer finish | The Analysing screen never spins forever |
| Engine passes | **One pass**: MultiPV 2, 100,000 positions per move | Measured: costs ~5% more than errors-only and also finds ~90% of "great" moves |
| Code style | **Async everywhere**: FastAPI routes, Procrastinate tasks, the database, chess.com, Stockfish and AI calls all use `await`; pure chess math stays plain functions | The usual style for a FastAPI service that mostly waits; one style for the API and workers, like Node |
| Capacity | **Every number is an `.env` setting**; default **2 workers**, each limited to 1 CPU and 768 MB. Only the workers have Docker limits | Stockfish is the only hungry part. Works on a small server and on a laptop; tuned after a load test |
| Grading | **Lost winning chances (win%)**, Lichess thresholds, plus our own grades | Only flags moves that changed the game |
| Naming mistakes | **Lichess's own puzzle tagger**, only when the line wins ≥ 2 pawns or mates | Proven at scale; cards cover tactical mistakes |
| Weakness cards | **Ranked by games affected** ("9 of 20 games"); always 3 cards when the games allow it | Measures habits, not one bad game |
| Line notes | **Fixed templates, worded when the game is read** from facts stored with each move: "your" for the reader's moves, "White's" / "Black's" for the opponent's | Correct for both players of a shared game; wording can change without re-analysis. AI notes on click are post-launch item 5 |
| The AI writing flow | **Retrieve → check relevance → rewrite (max 2) → write → check moves → retry once → fallback** | Checks retrieval instead of trusting it; cheap because most of it is cached |
| AI models | **Claude Haiku 5.5 main, gpt-6-luna fallback** ($0.10 / $0.50 per million tokens each); `text-embedding-3-small` for vectors. A blind side-by-side on real cards at build step 8 sets the final order | gpt-4o-mini, the earlier choice, shuts down on 14 Jan 2027. Haiku 5.5 is the main model because the little comparison data there is leans toward it for writing; the two are otherwise equal |
| Cost | **Log every AI call honestly** (tokens, cost, time, outcome); no comparison against a made-up alternative | A comparison needs a real competitor |
| LangChain | **For model calls; LangGraph for the flow**; retrieval is our own SQL | Uses LangChain where it saves work, not where it gets in the way |
| Library sources | **Wikipedia, Wikibooks, Lichess theme glossary** (1,338 passages) | Our research found every relevant passage in these three |
| Splitting | **Merge paragraphs within a section, up to ~250 words**, with "Article › Section:" in front | Enough context per passage; short passages stay findable |
| Tagging | **AI tags each passage once, at build time**, from our 11 themes | Best accuracy; tags are shipped, so the running app never calls an AI for them |
| Retrieval | **Tag filter → meaning + words → merged with RRF → top 5**; the word search uses a keyword list per theme | Each search covers the other's blind spot |
| Reusing reports | **An identical request joins a running report or gets one from the last 10 minutes** | No duplicates; new games appear when asked again later |
| Rate limits | **None per visitor in the first cut**; one generous "busy" limit; warnings when it starts choking | Only people the link is shared with will use it |
| Errors | **One shape everywhere**, strict input rules, request ids, no stack traces | Predictable for the frontend; easy to trace in logs |
| Stockfish in Docker | **The pinned official Stockfish 19 build**, checksum-verified | Same version, same results, on every machine |
| Code quality | **ruff** (lint + format); no type checker for now | Pydantic and tests cover what matters |
| Tests | **pytest**, real Postgres in a separate test database, no real AI or chess.com calls | Fast, free and repeatable |

---

## 3. The big picture

### Running pieces

```
Browser ──▶ caddy ──┬── Vue files (index.html, JS, CSS, fonts)
                    └── /api/… ──▶ api ──── writes reports, reads results ──┐
                                                                            ▼
                                   Postgres + pgvector: app data, the library and its vectors,
                                   caches, AI call log, Procrastinate's job tables
                                                                            ▲
             worker ×N ──── takes one job at a time ────────────────────────┘
             (each runs one Stockfish; calls chess.com, Claude Haiku → gpt-6-luna → fixed text)
```

| Piece | What it is | Responsible for |
|---|---|---|
| `caddy` | A small web server in front (a "reverse proxy": it receives every browser request and either answers itself or passes it on) | Serving the built Vue app; passing `/api/…` to `api`; compression; HTTPS if ever hosted |
| `api` | FastAPI, the HTTP layer | Checking input, starting reports, reading results. **Never runs Stockfish** |
| `worker` | The same code as `api`, started with a different command | All slow work: downloading games, Stockfish, grading, naming mistakes, retrieval, AI calls |
| `db` | Postgres 17 with the pgvector extension | Everything that is stored |

`api` and the workers never call each other. The API leaves work in the database and a worker picks
it up.

### One report, step by step

1. **Typing a username (Home).** `api` asks chess.com for the player's stats to show the preview.
   The answer is cached for 5 minutes.
2. **Clicking Analyse** (`POST /api/reports`). `api`:
   1. checks the input;
   2. checks the player exists and has games in that time control;
   3. returns an identical running report, or one finished in the last 10 minutes, if there is one;
   4. checks the "busy" limit;
   5. saves a new report and queues `prepare_report`.

   It answers immediately with the report id.
3. **`prepare_report`** (a worker): downloads the game list from chess.com, saves new games, links
   them to the report and queues one `analyse_game` job per game not analysed yet.
4. **`analyse_game` × N** (any free worker): Stockfish over every position, then grades, names,
   lines and the facts behind each note, saved as JSON in the game's row. The game's eval trace is saved as it goes, so
   the Analysing screen shows it growing.
5. **The last game finishes.** The worker that finishes it notices it was the last one and queues
   `build_report` (section 6 explains how this is done safely).
6. **`build_report`**:
   1. counts the user's repeated mistakes and picks the top 3;
   2. retrieves theory and has the AI write the three cards (with the fallback if needed);
   3. builds the summary, missed tactics and openings;
   4. marks the report `done`.
7. **Meanwhile** the browser asks for the report every couple of seconds; `api` just reads the
   database.
8. **Opening a game** is a database read. Everything was computed in step 4, so it is instant. Only
   the note sentences are put together at this moment, worded for the report's player.

---

## 4. Code layout

```
backend/
  app/
    api/         HTTP only: routes, request/response models (API.md), error handler. No SQL, no chess.
    reports/     The product's steps: start a report, prepare, analyse a game, build a report,
                 read results. The only folder that coordinates the others.
    chesscom/    chess.com client: player lookup, archives, game selection, caching, ETags.
    engine/      Stockfish only: "analyse this position" → scores and lines. Version check.
                 (This is where browser analysis would plug in later.)
    analysis/    Pure chess logic: win%, grading, the tagger adapter, lines, note facts and note
                 wording, arrows, counting patterns, openings. No database, no network.
    rag/         Library loading, retrieval SQL, the LangGraph writing flow, prompts, the move
                 checker, the fallback text, AI call logging.
    jobs/        Procrastinate setup, the three tasks and the repeating tasks (thin: they call
                 into reports/).
    db/          Connection pool, schema.sql, startup (create tables, load the library).
    vendor/lichess_puzzler/   The vendored tagger, with its AGPL licence.
    config.py    Settings from .env (pydantic-settings), validated at startup.
    main.py      Starts the api.
    worker.py    Starts a worker.
  scripts/build_library.py    Builds the shipped library files (section 8).
  data/library/               The shipped library files.
  tests/
```

Each folder's `__init__.py` lists what the rest of the app may use from it, like an `index.ts`
that re-exports a folder's public functions. Everything else in the folder is private to it.

**Dependency rules**, checked by **import-linter** as part of `uv run pytest`:
- Dependencies point one way: `api` → `reports` → the other folders.
- `engine` and `analysis` import nothing else of ours.
- Nothing imports `api`.

If a file breaks a rule, the tests fail with a message such as `app.engine is not allowed to import
app.db`.

**Code style: async everywhere.** Every place that waits uses `await`, as in Node:

| Waiting on | Example |
|---|---|
| The database | `await db.fetch(...)` |
| chess.com | `await http.get(...)` |
| Stockfish | `await engine.analyse(...)` |
| The AI | `await model.ainvoke(...)` |

Pure chess math (grading, the tagger, notes) stays plain functions; it takes milliseconds.

There's one rule: never call a sync-only library that waits (such as `requests` or `time.sleep`)
inside async code, because it would stall everything on that process. Every library we use has an
async version.

**Main libraries:**
- FastAPI, Pydantic and pydantic-settings;
- psycopg 3 (async pool) with the pgvector adapter, and Procrastinate, with its **exact version
  pinned**;
- python-chess, using its async engine API;
- httpx (async client) for chess.com calls;
- LangChain (`langchain-openai`, `langchain-anthropic`) and LangGraph, with tiktoken for the token
  budget;
- for development: pytest with pytest-asyncio, ruff and import-linter.

---

## 5. Database

### Tables

There are 7 tables of our own, plus Procrastinate's 4. All are created on startup if missing. The
database itself enforces the basic rules: required columns, allowed status values, unique keys and
links between tables.

**`reports`**: one row per report request.

| Column | Type | Notes |
|---|---|---|
| `id` | text, primary key | `r_` + random characters |
| `username` | text | Lower-cased |
| `time_control` | text | `rapid` / `blitz` / `both` |
| `games_requested` | int | 10 / 20 / 30 / 50 |
| `status` | text | `queued` / `running` / `done` / `failed` |
| `error`, `detail` | text, nullable | Failure code and message (API.md "When failed") |
| `notes` | jsonb | List of messages shown on the report, e.g. "1 game couldn't be analysed and was skipped" |
| `result` | jsonb, nullable | The finished summary, weaknesses, missed tactics and openings, in API.md's shapes |
| `created_at`, `started_at`, `finished_at` | timestamptz | |

Indexes:
- a **partial unique index** on `(username, time_control, games_requested)` for reports that are
  `queued` or `running`, so two identical requests at the same instant can never create two
  running reports;
- an index for the 10-minute reuse lookup;
- an index on `status` for the busy count.

**`games`**: one row per chess.com game, shared between reports.

| Column | Type | Notes |
|---|---|---|
| `id` | text, primary key | `g_` + random characters |
| `chesscom_url` | text, unique | The full chess.com link identifies the game. Live and daily games are numbered separately, so the number alone isn't enough. A game is never stored twice, whoever asks |
| `white`, `black`, `white_rating`, `black_rating` | text / int | |
| `result` | text | `1-0` / `0-1` / `1/2-1/2` |
| `time_class` | text | `rapid` / `blitz` |
| `played_at` | timestamptz | |
| `opening` | text | Family name from chess.com's opening link (e.g. "Italian Game"); "Unknown opening" when the game has none |
| `start_fen`, `pgn` | text | |
| `plies` | int | Half-moves in the game |
| `status` | text | `queued` / `running` / `done` / `failed` (the same words the API uses) |
| `moves` | jsonb | One object per half-move (shape below) |
| `trace` | jsonb | White's eval after each half-move (for the Analysing screen) |
| `error_counts` | jsonb | Per colour: blunders, mistakes, inaccuracies, misses |
| `engine_version`, `engine_nodes`, `grading_version` | text / int / int | What produced the analysis, so a future upgrade never quietly mixes results |
| `analysis_seconds` | real | Engine time, for `/metrics` |
| `error` | text, nullable | Why it failed, if it did |

**`report_games`**: which games belong to which report.

| Column | Notes |
|---|---|
| `report_id` → `reports`, `game_id` → `games` | Primary key `(report_id, game_id)` |
| `position` | Order in the report (newest first) |
| `user_color` | `white` / `black` |

An index on `game_id` makes "which reports include this game?" fast.

**`corpus_chunks`**: the library's passages.

| Column | Notes |
|---|---|
| `id` | Stable id from the build script |
| `source`, `title`, `section`, `url` | For citations |
| `text` | The passage as shown to the AI and in the footnote preview |
| `tags` | text[]: themes from the 11 (section 8) |
| `embedding` | vector(1536) |
| `tsv` | Full-text search column, generated by Postgres from title, section and text (English) |

There is a GIN index on `tsv` and one on `tags`. There is no vector index (section 17).

**`concept_queries`**: one row per theme: `theme` (primary key), the fixed query text, its vector,
and the theme's keyword list for the word search. Shipped with the library.

**`cache`**: every cache in one table.

| Column | Notes |
|---|---|
| `key` | e.g. `chesscom:<url>`, `rag:<library version>:<theme>`, `llm:write:<hash of the prompt>` |
| `value` | jsonb |
| `etag` | For chess.com's "has this changed?" check |
| `expires_at` | Null = never expires |
| `hits`, `created_at` | `hits` feeds the cache hit rate in `/metrics` |

**`llm_calls`**: one row per AI call.

| Column | Notes |
|---|---|
| `report_id`, `theme` | What it was for |
| `purpose` | `relevance` / `rewrite` / `write` (and `tag` / `embed` at build time) |
| `provider`, `model` | |
| `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms` | |
| `outcome` | `ok` / `cached` / `fallback` / `failed` |
| `created_at` | |

**Procrastinate's tables** (`procrastinate_jobs`, `procrastinate_workers`, `procrastinate_events`,
`procrastinate_periodic_defers`) hold the job queue, worker heartbeats, each job's history and
bookkeeping for repeating tasks. We never write to them by hand; we only read them for `/health`
and `/metrics`. Procrastinate's exact version is pinned, so its tables never change by themselves.
Upgrading it means running its own upgrade scripts by hand, like our other big changes.

### A move inside `games.moves`

Each object has the fields API.md returns for a move (`ply`, `move_number`, `color`, `san`,
`fen_after`, `eval`, `grade`, `themes`, `better_line`, `refutation_line`, `refutation_arrows`),
except the two notes.
- **The notes are stored as facts:** `better_facts` and `refutation_facts`, holding which rule
  matched, the theme, the pieces and squares, and the winning chances before and after.
- **They become sentences when the game is read** (section 7).
- **Internal fields:** `uci`, `best_uci`, `win_before`, `win_after`, `loss`, `second_gap` and
  `missed_themes`.

JSON columns are not checked by Postgres, so a Pydantic model checks every `moves` and `result`
value before it is written and after it is read.

---

## 6. Background work

### The three tasks (Procrastinate)

| Task | Does | Priority | Locks (prevent duplicates) |
|---|---|---|---|
| `prepare_report(report_id)` | Marks the report `running`; downloads and filters games (section 7); saves new games; links them; queues `analyse_game` for each game not `done`; then runs the last-game check itself | High | `report:<id>` |
| `analyse_game(game_id)` | If the game is already `done`, skips straight to the last-game check. Otherwise runs the engine and analysis, saves the result, then runs the last-game check for every running report that includes this game | Normal | `game:<id>`, used twice: as a queueing lock (never two waiting jobs for one game) and as a running lock (never two running at once). "Already queued" is treated as fine |
| `build_report(report_id)` | Counts, picks the top 3, writes the cards, builds the summary, marks `done` | High | `report-build:<id>` |

A worker runs **one job at a time** with **one Stockfish**, which keeps one worker = one core.

**Order:** all workers take from one queue. Higher-priority jobs go first: preparing and building
reports, and the repeating checks below. Games run oldest first. So a report whose games are all
done is built within seconds, even while someone else's games are waiting.

**Shared games:**
- A game is identified by its chess.com link and analysed once, whoever asks, across reports and
  users.
- It's a public game analysed by our own Stockfish, and each report shows only its own player's
  view.
- The main gain is the same player asking again (more games, Both, next week): only new games are
  analysed.
- If browser analysis is ever added, results made on a visitor's device must not be shared.

### Retries and failures

Only **temporary** errors are retried. Any other error would fail the same way again, so it fails
at once.

| Task | Retried for | Waits | Any other error, or the last try failing |
|---|---|---|---|
| `prepare_report` | chess.com timeouts and errors, database hiccups | 5 s, then 30 s | The report fails with `chesscom_unavailable` or `analysis_failed` |
| `analyse_game` | Stockfish crashing, database hiccups | 2 quick retries, a few seconds apart | The game is marked `failed` with the reason, then the last-game check runs. The report continues without it, with a note |
| `build_report` | Database hiccups | 2 quick retries, a few seconds apart | The report fails with `analysis_failed` |

- A retried job keeps its place in the line. Once its wait is over, it goes ahead of newer jobs.
- If **more than half** of a report's games fail, the report fails with `analysis_failed`.
- `build_report` never fails because of the AI (section 8).

### Repeating tasks

Procrastinate runs repeating tasks inside the workers; there is no separate cron.
- Each run happens once, however many workers there are.
- These tasks have the highest priority, so a busy line delays them by one game at most.

| Task | Every | Does |
|---|---|---|
| Crashed workers | 1 minute | Workers send a heartbeat every 10 seconds. Jobs whose worker stopped sending it go back in the queue, so a crash or restart loses at most the game in progress, which is redone |
| Stuck reports | 5 minutes, skipping reports changed in the last 2 | For each queued or running report: is any job for it still waiting, scheduled or running (its prepare step, an unfinished game, its build)? If not, it can never finish. First re-run the last-game check, which repairs it if all its games are done; otherwise mark it `failed` with `analysis_failed`. Either way, log a WARNING, because it means a bug. There is no time limit, so a report waiting in a long line is never failed |
| Housekeeping | Daily | Deletes finished jobs older than 30 days and expired cache rows |

### The last-game check

When a game finishes, the worker must notice if it was the last unfinished game of a report.

**The trap:** two workers finish the last two games at the same instant. Each checks, each sees the
other's game still running, and nobody queues `build_report`. The report hangs forever.

**Only reports still running are checked.** A finished report is never touched again. Otherwise,
an old report that once skipped a game would be rebuilt (with new AI calls and changed cards) when a
newer report finally analyses that game.

**The fix**, for each running report that includes the finished game, in one transaction:
1. **lock the report's row** (`SELECT … FOR UPDATE`), so the two workers take turns;
2. count the report's games that are not yet `done` or `failed`;
3. if none are left, queue `build_report`. Its lock means it can only be queued once.

`prepare_report` runs the same check after linking its games. This covers a game that finished
between being found and being linked, and the case where every game was already analysed. Running
the check twice is harmless because of the lock.

### Progress

`progress.done / total` and each game's status come straight from `report_games` + `games`. The
eval trace of the game being analysed is saved every 10 positions.

---

## 7. Chess analysis

### Choosing the games

- Walk back through the player's monthly archives, newest first, one request at a time, until there
  are enough games.
- Keep only standard chess (`rules = chess`) in the chosen time control. "Both" means rapid and
  blitz mixed, newest first.
- The user's colour comes from comparing usernames, ignoring capitals.
- Look back at most **24 months**. If there are fewer games than asked for, the report runs with
  what exists and says so in a note. If there are none at all, the report fails with `no_games`.

**chess.com caching** (all in the `cache` table):

| What | Kept for |
|---|---|
| Player stats (the Home preview) | 5 minutes |
| The list of months | 1 hour |
| A past month's games | Forever (a finished month never changes) |
| The current month's games | 10 minutes, then re-checked with the ETag (`If-None-Match`); "not modified" costs almost nothing |

chess.com's rules: one request at a time is never rate-limited, and parallel requests may get a
`429`. Every request sends an identifying `User-Agent` with the project's link (never personal
contact details).

### The engine

| Setting | Value | Why |
|---|---|---|
| Version | Stockfish 19 | Same as tested; pinned in Docker (section 11) |
| Threads | 1 | Several threads make results differ run to run; capacity comes from more workers instead |
| Search size | `ENGINE_NODES` = 100,000 positions per move | Measured (below) |
| MultiPV | 2 (the two best moves) | One pass gives errors **and** "great" moves |
| Hash | `ENGINE_HASH_MB` = 64 | |
| Between games | Memory cleared (`ucinewgame`) | A game's result never depends on which game was analysed before it |

Each worker starts one Stockfish when it starts, found through `STOCKFISH_PATH`. It uses that one
for every game and restarts it if it crashes. At startup the worker logs the Stockfish version,
with a warning if it isn't the expected 19. Every analysed game also stores the version that
produced it.

**Why one pass and 100,000.** We measured on 20 club rapid games (both players rated 900–1039) and
20 strong blitz games (see `pre_build_research/engine_timing/README.md`):
- Two-best-moves mode costs only about 5% more time than best-move-only.
- It catches errors just as well and finds about 90% of the reference's "great" moves.
- Doubling to 200,000 gains almost nothing.
- **Club games took about 11 seconds each on one core**, with every reference blunder flagged and
  no false blunders.

### Grading

Stockfish's score is turned into a **winning chance from 0 to 100%** with Lichess's formula:

```
win% = 50 + 50 × (2 / (1 + e^(−0.00368208 × cp)) − 1)      cp capped at ±1000; mate counts as the cap
loss = win% before the move − win% after it, from the mover's point of view
```

| Grade | Rule | From |
|---|---|---|
| Blunder | loss ≥ 15 | Lichess |
| Mistake | loss ≥ 10 | Lichess |
| Inaccuracy | loss ≥ 5 | Lichess |
| (mate cases) | Allowing a forced mate is a blunder; so is throwing away your own forced mate | Lichess |
| Miss | An error **and** the better line contains a winning tactic (≥ 2 pawns or mate) **and** the move itself allowed no tactic | Ours |
| Best | The engine's top move | Ours |
| Excellent | loss < 2 | Ours |
| Good | loss 2–5 | Ours |
| Great | Best move **and** the second-best is ≥ 10 points worse (not when it was the only legal move) | Ours |
| Brilliant | Great or best **and** a sacrifice (from the tagger) **and** the mover was below 90% | Ours |

**Blunder or miss:** a move that allowed a tactic keeps its error grade, even if it also missed one.
Whatever the label, both facts are kept on the move:
- the tactic it allowed counts toward the weakness cards;
- the tactic it missed counts toward "tactics you missed".

The label only decides the glyph and which per-game number the move adds to (blunders or misses).

Both players' moves are graded. The weakness cards count only the user's. Our thresholds live in one
module and get tuned after looking at real games.

### Naming mistakes (the tagger)

Lichess's own puzzle tagger (`lichess-puzzler`'s `cook.py`, AGPL) is vendored in `app/vendor/`.
- **For an error:** the position after the mistake, with the opponent to move, is treated as a
  puzzle, and Stockfish's punishing line is its solution. The tagger names the themes.
- **For a miss:** the position before the move, with the user to move, and the better line as the
  solution.
- **For a possible brilliant:** a best or great move made when the mover was below 90%. The puzzle
  is the position before the move, with the played move and the engine's line as the solution. Only
  the `sacrifice` tag is used.
- A theme counts only if the line **wins ≥ 2 pawns or mates**, the same bar Lichess uses for
  puzzles.

The 11 themes are: fork, pin, skewer, discovered attack, hanging piece, back-rank mate, trapped
piece, exposed king, advanced pawn, quiet move and defensive move.

### Lines, notes and arrows

- **Better line:** Stockfish's best line from the position before the move, 3–5 moves.
- **Punishing line:** Stockfish's best line from the position after the move, starting with the
  opponent's reply, 3–5 moves.
- **Notes** are fixed templates, built **when the game is read** from the facts stored with the move
  (which rule matched, the theme, the pieces and squares, the winning chances before and after).
  - **The wording depends on the reader.** The same game can be read from both players' reports.
    It says "your" for the reader's own moves and "White's" / "Black's" for the opponent's, as the
    frontend already does in its own text.
  - **Changing the wording needs no re-analysis.**
  - **The facts are what the post-launch AI notes would rephrase.**
  - **The first rule that matches wins, and the tactic's name comes first:**

  | Note | Rule → sentence |
  |---|---|
  | Why it's bad | Mate → "**Back-rank mate:** this line ends in checkmate." |
  | | Loses ≥ 2 pawns → "**Hanging piece:** this line wins your bishop." |
  | | The reply attacks 2+ pieces → "**Fork:** after Nc7, your king and rook are both attacked." |
  | | Otherwise → "This drops your winning chances from 55% to 30%." |
  | Better move | ≥ 60% → "Be2 keeps your advantage (+1.2)." · 40–60% → "keeps the position level" · < 40% → "limits the damage" |
  | Report examples | "Qg5 attacks your knight on e5 and your pawn on g2." / "Qg5 wins your bishop." |

  When the tagger found no theme, the sentence appears without the prefix.

  In report examples, the opponent's reply shows a grade symbol (such as "!") only if the opponent
  actually played that move in the game. A move from Stockfish's line that never happened has no
  grade.

  For the opponent's moves, the same rules read like this:
  - "**Hanging piece:** this line wins Black's bishop."
  - "This drops Black's winning chances from 55% to 30%."
  - "Be2 keeps White's advantage (+1.2)."
- **Arrows:** the threats left after the punishing line, e.g. the two targets of a fork.

### Building the report (`build_report`)

- **Weaknesses** (tactics the user allowed):
  - **The count** is the number of games in which the user allowed the theme at least once ("9 of 20
    games"). Themes are ranked by it, and ties go to the theme that happened more times.
  - **Which errors count:** cards come from the user's blunders and mistakes. If those give fewer
    than 3 themes, inaccuracies that allowed a tactic fill the remaining slots.
  - **No minimum:** the top 3 always become cards, so a theme seen in one game says "1 of 20 games".
    There are fewer than 3 cards only when the user's errors contain fewer than 3 themes in total.
  - **Two tactics in one move:** a move that allowed two tactics counts for both.
  - **Examples:** each card gets 2–3 (or as many as exist), the biggest losses from different games
    where possible.
- **Missed tactics:** the winning tactics the user didn't play, counted in times. They come from
  every user error whose better line had one, whatever the move's label.
- **Openings:** results per opening family and colour, only for openings played at least 4 times
  (as the report page says), most played first. Games with "Unknown opening" are left out.
- **Summary:** games, wins/draws/losses, and blunders, mistakes and misses per game (user's moves
  only).
- **Notes:** too few games; skipped games; AI unavailable.

---

## 8. Theory and AI (RAG)

### The library: built once, shipped with the project

`scripts/build_library.py` runs on a developer's machine, never inside the app. Its steps:

1. **Sources:** Wikipedia (36 concept articles + the Glossary of chess), Wikibooks "Chess" and the
   Lichess theme glossary, from `pre_build_research/corpus/`. That is 1,338 passages; the missing
   *Fork* glossary entry is added. The Lichess studies (move-by-move narration, unclear licence)
   and the two Gutenberg books (never relevant in our research, old notation noise) are left out.
   The books can come back if the retrieval check shows gaps.
2. **Splitting:** consecutive paragraphs of the same section are merged into passages of up to ~250
   words. A passage never crosses into another section. Glossary entries stay one per term.
3. **Title prefix:** each passage's searchable text starts with "Article › Section:", e.g. "Pin
   (chess) › Absolute pin: …", so a short paragraph that never says "pin" is still found for pin.
4. **Tags (AI, once):** the main model (Claude Haiku 5.5) reads each passage and returns the themes it covers, **only from
   the 11**, or none. The answer is validated.
5. **Vectors (AI, once):** `text-embedding-3-small` (1,536 numbers per passage) for every passage
   and for the 11 fixed concept queries ("how to avoid allowing a fork", …).
6. **Output:** `data/library/` holds:
   - the passages with their tags (JSON lines);
   - the vectors (a binary array, about 8 MB);
   - the concept queries, each with its keyword list for the word search;
   - a manifest with counts, vector size, model names, a version and checksums.

Steps 4 and 5 are paid calls. Together they cost well under $0.20, and they run only after a
dry run (counts and cost estimate) and explicit approval. Results are cached by a fingerprint of
the text, so re-running costs nothing for unchanged passages.

**On startup**, `api` loads the library into `corpus_chunks` and `concept_queries` when the tables
are empty or the manifest's version changed. It checks counts, vector size and checksums first. No
AI and no API key are involved.

### Retrieval: one SQL query per weakness

1. **Filter by tag:** passages tagged with the theme. If fewer than a minimum number are tagged
   (the thin themes), use the whole library instead (the safety net).
2. **Rank two ways** within those passages:
   - by meaning (pgvector cosine distance to the theme's query vector);
   - by words: Postgres full-text search on `tsv` with the theme's **keyword list**, matching any of
     its words (e.g. fork: *fork*, *double attack*, *attacks two*). The question itself can't be
     used here, because Postgres would require every one of its words.
3. **Merge** with Reciprocal Rank Fusion. Each passage scores `weight / (60 + its rank)` in each
   list; the scores are added, and meaning is weighted a little higher than words. Passages near
   the top of both lists win.
4. **Take the top 5.**

The queries and the library are fixed, so a theme's retrieval result is the same every time. It is
**cached per theme** (key includes the library version).

### Writing a card: the LangGraph flow

```
retrieve ──▶ relevant? ──no──▶ rewrite the query (max 2) ──▶ retrieve again
                │                         └─ still no ──▶ fallback text
               yes
                ▼
             write ──▶ check moves & citations ──fail──▶ write once more ──fail──▶ fallback text
                              │
                             pass ──▶ save the card
```

| Step | AI? | What happens |
|---|---|---|
| Retrieve | No | The SQL above |
| Relevant? | Small AI call | "Which of these passages explain this theme or how to avoid it?" At least 2 must pass |
| Rewrite | Small AI call | A different wording of the query; embedding the new wording is a small paid call. The keyword list stays the same |
| Write | Main AI call | Structured output: `why` and `how_to_avoid`, plain text with `*emphasis*` and `[n]` citations (API.md) |
| Check | No | Every move mentioned must be legal and appear in that example's engine lines. Every `[n]` must point to a given passage. Length limits apply |

Retrieve, relevant and rewrite are cached per theme, so they run once per theme, not once per
report. In practice a report makes about **3 AI calls**, one write per card.

**Sources on the card:** only the passages the text actually cites, renumbered so that `[1]`,
`[2]`… match the list under the card.

**What goes into the prompt:**
- the theme;
- for each example: the move played, its grade, the better move, the punishing line, the pieces
  attacked and material lost (python-chess), and the winning chances before and after;
- the 5 passages, numbered, with their sources.

**Never usernames, and never any other text from chess.com**: a username could be crafted to
hijack the prompt.

**Fallback text** (used when both AI providers fail, when nothing relevant is found, or when the
move check fails twice): the Lichess glossary definition of the theme, cited. A note is added to the
report.

### Reliability

- **Models:** Claude Haiku 5.5 (`claude-haiku-5-5`) first, then gpt-6-luna. Both are LangChain chat
  models combined with `.with_fallbacks`.
  - gpt-6-luna is a "reasoning" model that thinks with hidden extra tokens before answering. For this
    job it runs with its reasoning effort at `none` or `low`, chosen at build step 8.
  - Prices (checked 18 Nov 2026): both $0.10 per million input tokens and $0.50 per million output
    tokens. Haiku's price is for prompts under 100,000 tokens; ours are about 3,000.
  - The earlier choice, gpt-4o-mini, is deprecated and shuts down on 14 January 2027.
- **Choosing the final order:** at build step 8, the same cards are written by both models and
  judged blind. We also count how often each one fails the move and citation check. The winner
  becomes the main model, which is only a settings change.
- **Retries:** each call is retried with growing waits and has a timeout.
- **Circuit breaker:** after 3 failures in a row a provider is skipped for 2 minutes, so we don't
  keep waiting on a dead provider.
- **Token budget:** a prompt over the limit is trimmed (fewer passages) before sending.

### Cost logging

Every AI call is written to `llm_calls` with its purpose, model, tokens, cost (from per-model prices
in settings), time taken and outcome. `/metrics` shows cost and tokens per report, cache hit rate,
fallback rate and average AI time. There is no comparison against a "send the whole library"
baseline, which would only inflate a made-up alternative.

**LangSmith** (a dashboard that traces every step of every AI flow) can be switched on later with
three `.env` lines (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`) and no code
change. Prompts contain only chess facts and library text, so nothing personal leaves.

---

## 9. API behaviour

The endpoints are exactly those in API.md: player lookup, start a report, get a report, get a game.
Section 17 notes a few small changes to API.md.

### Starting a report

```
check input ─▶ player exists? (404) ─▶ any games in that time control? (422 no_games)
  ─▶ identical report running? return it (202) ─▶ identical report done < 10 min ago? return it (200)
  ─▶ more than MAX_ACTIVE_REPORTS queued/running? (503 busy) ─▶ create + queue (202)
```

"Identical" means the same username (ignoring capitals), time control and number of games. Any
difference makes a new report, which still reuses every game already analysed and every cached
chess.com month.

### Reading a game

A plain read of the game's row. The note sentences are built at this point, worded for this
report's player (section 7).

### Input rules (Pydantic)

| Input | Rule |
|---|---|
| `username` | Letters, digits, `_`, `-`; 3–25 characters |
| `time_control` | `rapid` / `blitz` / `both` |
| `games` | 10 / 20 / 30 / 50 |
| Ids in URLs | Must look like `r_…` / `g_…`; anything else is a `404` without touching the database |

### Errors

The error shape is always `{ "error": "…", "detail": "…" }`. The `detail` is written for humans,
and the frontend shows it as is.

| HTTP | `error` | When |
|---|---|---|
| 422 | `invalid_input` | An input rule is broken (FastAPI's own error format is converted to ours) |
| 404 | `username_not_found`, `report_not_found`, `game_not_found` | Unknown player or id |
| 422 | `no_games` | The player has no games at all in that time control |
| 503 | `chesscom_unavailable` | chess.com isn't responding when we check the player |
| 503 | `busy` | Too many active reports ("BlunderTrace is busy right now. Please try again in a few minutes.") |
| 500 | `internal_error` | Anything unexpected. The visitor sees a short message, never a stack trace |

Every response carries an **`X-Request-ID`** header, and every log line for that request carries the
same id.

### Rate limits

There are **no per-visitor limits in the first cut**: only people the link is shared with will use
it. The one safety check is `MAX_ACTIVE_REPORTS` (default 20). Per-visitor limits (slowapi, using
the real visitor IP that Caddy passes on) are added before any public launch.

Reports are kept with no automatic deletion in the first cut.

---

## 10. Settings (`.env`)

All settings are read and validated by `config.py` at startup. A missing or invalid value stops the
app with a clear message.

| Setting | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | (required) | Postgres connection |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | (optional) | Without them, the app still runs and uses fallback text for the cards |
| `MAIN_MODEL`, `FALLBACK_MODEL` | `claude-haiku-5-5`, `gpt-6-luna` | Writing models. Either can be an Anthropic or an OpenAI model, so swapping them after the step-8 comparison is only a settings change |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Library vectors and rewritten questions |
| `WORKERS` | 2 | Number of worker processes (each = one Stockfish = one core) |
| `STOCKFISH_PATH` | `stockfish` | Where the Stockfish program is. The default finds it on the system path (Homebrew's on the Mac, the image's own copy in Docker) |
| `ENGINE_NODES` | 100000 | Positions searched per move (10,000–5,000,000) |
| `ENGINE_HASH_MB` | 64 | Stockfish's memory for positions it has seen |
| `REPORT_REUSE_MINUTES` | 10 | Reuse window for identical reports |
| `MAX_ACTIVE_REPORTS` | 20 | The "busy" limit |
| `WORKER_CPUS`, `WORKER_MEMORY` | 1, 768m | Docker limits per worker. Only the workers have limits: Stockfish is the one part that would take a whole core, and its memory is fixed (~360 MB). The API, Postgres and Caddy are not hungry |
| `LOG_LEVEL` | INFO | |
| `LANGSMITH_*` | (unset) | Optional tracing |

Model prices for cost logging are also settings, so they can be updated without code changes.

**Not settings, on purpose:**
- Stockfish threads (always 1, for repeatable results).
- Automatic machine detection. Containers often see the whole host, so guesses go wrong.

**Example profiles** in `.env.example`:

| Machine | Settings |
|---|---|
| Small server (2 cores, 4 GB) | `WORKERS=2`, `WORKER_MEMORY=768m` |
| Laptop (8+ cores, 16 GB+) | `WORKERS=4`, `WORKER_MEMORY=1g` |
| Bigger server (16 cores, 32 GB) | `WORKERS=12`, `WORKER_MEMORY=1g` |

A 2 GB server fits only one worker: Stockfish 19 alone uses about 360 MB, measured.

---

## 11. Running it

### Developing (on the Mac)

| What | Command |
|---|---|
| Database | `docker compose up -d db` |
| API, reloading on save | `uv run uvicorn app.main:app --reload` |
| Workers | `uv run python -m app.worker` (one per terminal, or a small script for `WORKERS`) |
| Frontend | `npm run dev`; Vite forwards `/api` to port 8000, so the browser sees one address |
| Stockfish | Homebrew's Stockfish 19 (installed) |

### Running the product: `docker compose up`

| Service | Image | Notes |
|---|---|---|
| `db` | `pgvector/pgvector` (Postgres 17) | Data in a named volume; survives restarts. Health check: `pg_isready` |
| `api` | Our backend image, command `uvicorn` | Starts after `db` is healthy. Its port is bound to localhost only (for `/health`, `/metrics`) |
| `worker` | The same image, command `python -m app.worker` | `replicas: ${WORKERS:-2}`; starts after `api` is healthy; `stop_grace_period: 30s`, so a stopping worker finishes its current game first |
| `caddy` | Built from `frontend/`: a Node stage builds the Vue app, then Caddy serves it | The only port meant for browsers |

The backend Dockerfile:
- `python:3.12-slim` (Debian), with dependencies installed by `uv` in a cached layer;
- runs as a non-root user, with a `HEALTHCHECK` on `/health`;
- **Stockfish 19 is downloaded from the official release** for the image's processor type
  (`linux-x86-64` or `linux-arm64`, picked from Docker's `TARGETARCH`) and checked against a pinned
  SHA-256.

This works on Intel and Apple Silicon Macs, Windows, and any 64-bit Linux server. 32-bit machines
are not supported by the project, because the database image doesn't support them either.

The Caddy config:

```
:80 {
  encode gzip
  handle /api/* { reverse_proxy api:8000 }
  handle {
    root * /srv
    try_files {path} /index.html
    file_server
  }
}
```

If the project is ever hosted, replacing `:80` with the domain name gives automatic HTTPS.

### Startup order

1. `db` becomes healthy.
2. `api` starts.
   1. It takes a database lock, so a second starter can't clash.
   2. It creates missing tables (`schema.sql`) and Procrastinate's schema if missing.
   3. It loads the library if needed.
   4. It begins serving.
3. Workers start once `api` is healthy. They also wait and retry until the tables exist.

---

## 12. Logging and monitoring

**Logs:** JSON lines on standard output, read with `docker compose logs`. Each line has a time,
level, message, and whichever of `request_id`, `report_id`, `game_id` and `job` apply. Following one
report across `api` and every worker is a single search.

**`GET /health`** reports:
- the database;
- the library (loaded, passage count);
- worker heartbeats from `procrastinate_workers`.

It returns `200` when the database and library are OK, and "degraded" when no worker has sent a
heartbeat recently. If a worker's Stockfish can't start, that worker fails, which shows up as a
missing heartbeat. The API never runs Stockfish, not even to ask its version.

**`GET /metrics`** (JSON) reports:
- **Reports:** reports by status; average time from request to done.
- **Queue:** jobs waiting, and how long the oldest has waited.
- **Engine:** games analysed; average engine seconds per game.
- **Caches:** hit rates (chess.com, retrieval, AI).
- **AI:** calls, tokens and cost per report; fallback rate; average AI time.

**Capacity warnings** are WARNING-level log lines when the system starts choking, as a signal that
it's time for rate limits or a bigger machine:
- the queue is long;
- reports wait long before starting;
- the busy limit is hit;
- a worker is near its memory cap.

The stuck-report check (section 6) also logs a WARNING whenever it repairs or fails a report,
because that means a bug.

---

## 13. Validation everywhere

| Where | Checked by |
|---|---|
| API input | Pydantic request models (rules in section 9) |
| chess.com responses | Pydantic models. A broken or unexpected game is skipped and noted, never crashes a report |
| The database | `NOT NULL`, `CHECK` on statuses and choices, `UNIQUE`, foreign keys |
| JSON columns | Pydantic models before writing and after reading |
| Settings | pydantic-settings at startup |
| Stockfish output | Moves exist and are legal; scores are sensible |
| AI output | Structured output (Pydantic), plus the move and citation check |
| The shipped library | Counts, vector size and checksums on load |

Type hints are written throughout (FastAPI and Pydantic rely on them) but are not checked by a type
checker for now.

---

## 14. Security basics

- **Secrets** live only in `.env` (gitignored) and are never logged.
- **SQL** always uses parameters (`%s`), never pasted strings.
- **Prompts** contain chess facts and library text only. No usernames or other text from chess.com
  go into a prompt.
- **Errors** never show stack traces or internals to visitors.
- **Containers** run as a non-root user.
- **Network:** only Caddy's port is meant for browsers. The API and database ports are bound to
  localhost.
- **CORS:** there is one origin, so there is no CORS configuration to get wrong.
- **chess.com:** we follow its API rules (one request at a time, identifying User-Agent).
- **Its IP:** board colours, piece designs, sounds and move-classification icons are not copied.
  Our design uses its own palette, font pieces and classical `!!` / `??` symbols.

---

## 15. Tests

`uv run pytest` runs everything below, including the import-linter check, plus `ruff check`.

| Layer | What | Needs |
|---|---|---|
| Pure logic | win% and grading (incl. mate rules, blunder vs miss), note wording for both readers, top-3 counting and the fill-in rule, passage merging, citation renumbering, the move checker, reading chess.com data from saved responses, settings validation | Nothing |
| Engine | Known positions: a famous blunder is graded "blunder"; a known fork is tagged "fork" | Stockfish, small search sizes |
| Database | Tables are created; hybrid retrieval returns the right passages; **two workers finishing the last two games together still build the report exactly once**; a finished report is never rebuilt; a game queued twice is analysed once; a game failing its last try is skipped and the report still finishes; a failing build marks the report failed; the stuck-report check repairs or fails the right reports; the 10-minute reuse; the duplicate-report index | Postgres |
| API | Every endpoint returns API.md's shapes; every error has the `{error, detail}` shape | Postgres, fake chess.com, fake AI |
| End to end | A whole report: saved games in, real Stockfish, real database, fake AI out → finished report | All of the above |

- **Never in tests:** real AI calls or real chess.com calls. Fakes return saved answers, like
  `jest.mock` or msw.
- **The test database:** a separate `blundertrace_test` inside the dev Postgres container, wiped at
  the start of each run. Your real data is never touched.
- **Run by hand, not on every change:**
  - **The retrieval check:** for each of the 11 theme queries, the top 5 under vector-only and
    hybrid, judged blind by you.
  - **The load test:** 1, 2 and 4 workers, measuring CPU, cores used, memory per container
    (`docker stats`) and report time. Then the worker limits and the machine profiles are tuned.

---

## 16. Build order

Each step ends with something that runs. Paid AI calls happen only in steps 6 and 8, each after a
dry run and your approval.

1. **Setup:** dependencies, `config.py`, JSON logging, request ids, the error handler, `/health`;
   pytest and ruff running.
2. **Database:** `schema.sql`, creation on startup, the test-database fixture.
3. **chess.com:** client, cache, game selection, player lookup endpoint. Home's preview now uses real
   data.
4. **Chess core:** engine wrapper, grading, tagger adapter, lines, note facts and wording, arrows,
   trace, with engine tests on known positions. Then run the tagger on the 20 saved club games from
   the engine test and count the themes, to check the 3-card rule on real games.
5. **Jobs and reports:**
   - Procrastinate, the three tasks with their priorities, locks and retry rules, the last-game
     check, the repeating tasks (crashed workers, stuck reports, housekeeping);
   - reuse, the busy limit, the report and game endpoints;
   - `build_report` with fallback card text.

   **The whole product now works end to end with real analysis.**
6. **Library:** `build_library.py` (merge, prefix, AI tags, vectors, the concept queries and their
   keyword lists), the shipped files, loading on startup.
7. **Retrieval:** the hybrid query, its tests, the blind retrieval check.
8. **AI writing:** models with fallbacks, the LangGraph flow, the move checker, caching, `llm_calls`;
   then the blind side-by-side of Haiku 5.5 and gpt-6-luna on real cards, to set the final order.
9. **Monitoring:** `/metrics`, capacity warnings.
10. **Docker:** backend Dockerfile (pinned Stockfish), Caddy + frontend build, compose with worker
    limits; the load test; tune the defaults.
11. **Frontend wiring:**
    - real API instead of sample data, with the Vite proxy;
    - Home's time estimate updated to the measured ~11 s per game;
    - an end-to-end run with a real username.
12. **Docs:** README (setup, architecture, research, decisions, results).

Hosting and the post-launch items follow later (PLAN.md).

---

## 17. Small details settled while writing this document

Please check these.

1. **No vector index for now.** An exact search over ~1,300 passages takes about a millisecond and
   is always exact. An approximate index (HNSW) only pays off with tens of thousands of passages,
   and with a filter it can quietly return fewer results. It can be added if the library grows.
2. **No per-position engine cache in the first cut.** Games are already shared, so the saving would
   mostly be opening moves. A position analysed inside another game can come out a hair different
   from a fresh search, which would break "same game, same grades". It will be revisited with the
   "skip known opening moves" idea, measured in the load test.
3. **The finished report is one JSON column** (`reports.result`). The games list in the report is
   read live from `games`, so statuses are always current.
4. **Two identical requests at the same instant** are stopped by a partial unique index, so they can
   never create two running reports.
5. **`prepare_report` also runs the last-game check** after linking games. This covers games that
   finished in between, or were all already analysed.
6. **The eval trace is saved every 10 positions,** so the Analysing screen's trace grows as
   API.md describes.
7. **The game endpoint's `grading` field stays, always `complete`**, so the frontend needs no change.
   There is no second pass any more.
8. **`/cache/stats` is folded into `/metrics`.** `/health` and `/metrics` are reached directly on the
   API's localhost port, not through Caddy.
9. **Opening names come from chess.com's opening link** in each game (e.g. "Italian Game"), shortened
   to the family name. No separate lookup table is needed.
10. **The retrieval check is per theme now:** 11 fixed queries × top 5 × two methods, judged blind.
    The earlier plan used a fresh puzzle set, back when queries came from puzzles. With fixed
    per-theme queries, the themes themselves are the test set.
11. **API.md changes** (applied):
    - `POST /api/reports` can also return `202` with an existing running report, `422 no_games`,
      `503 chesscom_unavailable` and `503 busy`;
    - the game endpoint no longer starts a second pass;
    - note templates name the tactic and use plain wording;
    - the error table and the operations list are updated;
    - `429` is not used in the first cut.

## 18. Settled in the final check (18 November)

A last full check compared this document with the first draft, PLAN.md, API.md, the frontend and our
discussions. These points were missing or unclear. Each was settled one at a time and is now written
into the sections above.

1. **Note wording on shared games** (section 7): notes are stored as facts and built when read,
   saying "your" for the reader's moves and "White's" / "Black's" for the opponent's.
2. **What a card's count means** (section 7): games affected, with ties going to the theme that
   happened more times. There are always 3 cards when the games allow it; inaccuracies fill in only
   if needed.
3. **Blunder or miss** (section 7): a move that allowed a tactic keeps its error grade; "miss" only
   when it allowed nothing. Both facts still count.
4. **Job order** (section 6): one queue. Preparing and building reports, and the repeating checks,
   go first; games are first come, first served.
5. **Reports that never finish** (section 6):
   - the last failed try marks the game or report failed;
   - only temporary errors are retried;
   - a check every 5 minutes repairs or fails reports that can no longer finish.
6. **The same game analysed twice** (section 6): games are shared across reports and users by
   chess.com link. A game job checks "already done?" first, and only one job per game runs at a
   time.
7. **The word search** (section 8): a keyword list per theme.

**Smaller points:**
- Brilliant moves get a sacrifice check, and "great" skips forced moves (section 7).
- The game search looks back at most 24 months (section 7).
- `STOCKFISH_PATH` (section 10) and the main libraries (section 4).
- Housekeeping of old jobs and expired cache (section 6).
- A 30-second stop period for workers (section 11).
- Cited sources are renumbered to match the text (section 8).
- The queue position and wait estimate on the Analysing screen became post-launch item 7 in PLAN.md.

**A second pass** (also 18 November) settled the rest:
- **Code style:** async everywhere (section 4).
- **Game status:** waiting games are `queued` in the database too, the same word as the API.
- **Last-game check:** it only looks at reports still running, so a finished report is never
  rebuilt (section 6).
- **`/health`:** no Stockfish version; the worker logs it at startup, and each game stores it
  (sections 7 and 12).
- **Openings:** only those played at least 4 times are listed; "Unknown opening" when chess.com
  gives none (sections 5 and 7).
- **Example notes:** the reply gets a grade symbol only if the opponent actually played it
  (section 7).
- **Procrastinate:** its exact version is pinned (section 5).
- **Docker limits:** only the workers have them; the API, Postgres and Caddy run without memory
  limits (section 10).
- **AI models:** gpt-4o-mini shuts down on 14 Jan 2027. Claude Haiku 5.5 is the main model, with
  gpt-6-luna as fallback. A blind side-by-side at build step 8 sets the final order (section 8).

## 19. To settle while building

- The "how to avoid" half of a fallback card: one fixed tip per theme (you review the 11) or the
  best retrieved passage, quoted.
- The 11 fixed concept queries and their keyword lists (drafted, then reviewed by you).
- RRF weights and the minimum tagged passages for the tag filter, chosen from the retrieval check.
- Whether the shipped library files live in git or as a release download.
- Whether the "quiet move" and "defensive move" labels match their card titles on real games.
- Whether the 3-card rule works on real games (checked at build step 4).
- Thresholds for the capacity warnings.
- Whether to skip very short or abandoned games, and below how many moves.
- Final worker limits and machine profiles, after the load test.
- Whether skipping known opening moves is worth it (measured).
