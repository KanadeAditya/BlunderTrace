-- BlunderTrace tables (docs/BACKEND.md, section 5).
-- Run on every startup: every statement is "create if missing", so running it twice is harmless.
-- Bigger changes to an existing table are done by a hand-written one-off script, not here.

CREATE EXTENSION IF NOT EXISTS vector;

-- The 11 weakness themes, as Lichess puzzle-theme keys.
CREATE OR REPLACE FUNCTION is_theme_list(themes text[]) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
  SELECT themes <@ ARRAY['fork', 'pin', 'skewer', 'discoveredAttack', 'hangingPiece',
                         'backRankMate', 'trappedPiece', 'exposedKing', 'advancedPawn',
                         'quietMove', 'defensiveMove']::text[]
$$;

-- Keeps `updated_at` current on every UPDATE, so no query has to remember to set it
-- (unless the UPDATE sets it explicitly).
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
    NEW.updated_at := now();
  END IF;
  RETURN NEW;
END
$$;

-- One row per report request.
CREATE TABLE IF NOT EXISTS reports (
  id               text PRIMARY KEY CHECK (id ~ '^r_[a-z0-9]{6,32}$'),
  username         text NOT NULL CHECK (username ~ '^[a-z0-9_-]{3,25}$'),  -- lower-cased
  time_control     text NOT NULL CHECK (time_control IN ('rapid', 'blitz', 'both')),
  games_requested  smallint NOT NULL CHECK (games_requested IN (10, 20, 30, 50)),
  status           text NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'running', 'done', 'failed')),
  error            text CHECK (error IN ('no_games', 'chesscom_unavailable', 'analysis_failed')),
  detail           text,
  notes            jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(notes) = 'array'),
  result           jsonb CHECK (result IS NULL OR jsonb_typeof(result) = 'object'),
  created_at       timestamptz NOT NULL DEFAULT now(),
  started_at       timestamptz,
  finished_at      timestamptz,
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK ((status = 'failed') = (error IS NOT NULL)),       -- an error code exactly when failed
  CHECK (status <> 'done' OR result IS NOT NULL)            -- a finished report has its result
);
-- Two identical requests at the same instant can never create two active reports.
CREATE UNIQUE INDEX IF NOT EXISTS reports_one_active
  ON reports (username, time_control, games_requested) WHERE status IN ('queued', 'running');
-- "An identical report finished in the last 10 minutes?"
CREATE INDEX IF NOT EXISTS reports_recent_done
  ON reports (username, time_control, games_requested, finished_at DESC) WHERE status = 'done';
CREATE INDEX IF NOT EXISTS reports_status ON reports (status);
CREATE OR REPLACE TRIGGER reports_touch BEFORE UPDATE ON reports
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- One row per chess.com game, shared by every report (and every user) that includes it.
CREATE TABLE IF NOT EXISTS games (
  id                text PRIMARY KEY CHECK (id ~ '^g_[a-z0-9]{6,32}$'),
  chesscom_url      text NOT NULL UNIQUE CHECK (chesscom_url ~ '^https://www\.chess\.com/game/'),
  white             text NOT NULL,
  black             text NOT NULL,
  white_rating      integer,
  black_rating      integer,
  result            text NOT NULL CHECK (result IN ('1-0', '0-1', '1/2-1/2')),
  time_class        text NOT NULL CHECK (time_class IN ('rapid', 'blitz')),
  played_at         timestamptz NOT NULL,
  opening           text NOT NULL DEFAULT 'Unknown opening',
  start_fen         text NOT NULL,
  pgn               text NOT NULL,
  plies             smallint NOT NULL CHECK (plies >= 0),
  status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
  moves             jsonb CHECK (moves IS NULL OR jsonb_typeof(moves) = 'array'),
  trace             jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(trace) = 'array'),
  error_counts      jsonb CHECK (error_counts IS NULL OR jsonb_typeof(error_counts) = 'object'),
  engine_version    text,
  engine_nodes      integer,
  grading_version   integer,
  analysis_seconds  real,
  error             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'done' OR (moves IS NOT NULL AND error_counts IS NOT NULL))
);
CREATE OR REPLACE TRIGGER games_touch BEFORE UPDATE ON games
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Which games belong to which report, in order, and which colour the report's player had.
CREATE TABLE IF NOT EXISTS report_games (
  report_id   text NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
  game_id     text NOT NULL REFERENCES games (id),
  position    smallint NOT NULL CHECK (position >= 1),   -- 1 = newest
  user_color  text NOT NULL CHECK (user_color IN ('white', 'black')),
  PRIMARY KEY (report_id, game_id),
  UNIQUE (report_id, position)
);
-- "Which reports include this game?" (the last-game check).
CREATE INDEX IF NOT EXISTS report_games_game ON report_games (game_id);

-- The theory library: one row per passage, with its vector and its full-text column.
CREATE TABLE IF NOT EXISTS corpus_chunks (
  id         text PRIMARY KEY,
  source     text NOT NULL,
  title      text NOT NULL,
  section    text NOT NULL DEFAULT '',
  url        text NOT NULL,
  text       text NOT NULL CHECK (length(text) > 0),
  tags       text[] NOT NULL DEFAULT '{}' CHECK (is_theme_list(tags)),
  -- the card themes this passage gives practical advice on avoiding (a second build-time label)
  advice     text[] NOT NULL DEFAULT '{}' CHECK (is_theme_list(advice)),
  embedding  vector(1536) NOT NULL,
  tsv        tsvector GENERATED ALWAYS AS
               (to_tsvector('english', title || ' ' || section || ' ' || text)) STORED
);
CREATE INDEX IF NOT EXISTS corpus_chunks_tsv ON corpus_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS corpus_chunks_tags ON corpus_chunks USING gin (tags);
-- Library version 2 (18 Nov): the advice label and the "web" source. For databases made earlier:
ALTER TABLE corpus_chunks ADD COLUMN IF NOT EXISTS advice text[] NOT NULL DEFAULT '{}'
  CHECK (is_theme_list(advice));
ALTER TABLE corpus_chunks DROP CONSTRAINT IF EXISTS corpus_chunks_source_check;
ALTER TABLE corpus_chunks ADD CONSTRAINT corpus_chunks_source_check
  CHECK (source IN ('wikipedia', 'wikibooks', 'lichess_themes', 'web'));
-- No vector index: an exact search over ~1,300 passages is fast and always exact (section 17).

-- One fixed search per theme: the question (for meaning) and the keywords (for words).
CREATE TABLE IF NOT EXISTS concept_queries (
  theme      text PRIMARY KEY CHECK (is_theme_list(ARRAY[theme])),
  query      text NOT NULL,
  keywords   text[] NOT NULL CHECK (cardinality(keywords) > 0),
  embedding  vector(1536) NOT NULL
);

-- Every cache in one table: chess.com answers, retrieval per theme, AI answers.
CREATE TABLE IF NOT EXISTS cache (
  key         text PRIMARY KEY,
  value       jsonb NOT NULL,
  etag        text,
  expires_at  timestamptz,            -- null = never expires
  hits        integer NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cache_expires ON cache (expires_at) WHERE expires_at IS NOT NULL;

-- One row per AI call: the source of the cost numbers in /metrics.
CREATE TABLE IF NOT EXISTS llm_calls (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  report_id   text REFERENCES reports (id) ON DELETE SET NULL,
  theme       text,
  purpose     text NOT NULL CHECK (purpose IN ('relevance', 'rewrite', 'write', 'tag', 'embed')),
  provider    text NOT NULL CHECK (provider IN ('anthropic', 'openai')),
  model       text NOT NULL,
  tokens_in   integer NOT NULL DEFAULT 0 CHECK (tokens_in >= 0),
  tokens_out  integer NOT NULL DEFAULT 0 CHECK (tokens_out >= 0),
  cost_usd    numeric(12, 6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
  latency_ms  integer CHECK (latency_ms >= 0),
  outcome     text NOT NULL CHECK (outcome IN ('ok', 'cached', 'fallback', 'failed')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS llm_calls_report ON llm_calls (report_id);
