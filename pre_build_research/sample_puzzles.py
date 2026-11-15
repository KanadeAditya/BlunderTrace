"""
Build retrieval-test queries from REAL blunders in the Lichess open puzzle database.

Why: queries must not be hand-written by someone who has seen the corpus (test leakage).
Here the blunder, the position and the label (theme) all come from Lichess; the query text
is produced by our deterministic describe(). Sampling uses a fixed seed.

Each puzzle row: FEN = position BEFORE the blunder, Moves[0] = the blunder actually played,
Moves[1:] = the punishing solution, Themes = Lichess's labels for the tactic.
Query = describe(position AFTER the blunder) + mistake phrase from the fixed table below.

Usage:
    uv run python pre_build_research/sample_puzzles.py
Outputs: pre_build_research/queries.jsonl (machine) + queries.md (for reading).
"""
import csv
import io
import json
import random
from pathlib import Path

import chess
import httpx
import zstandard

# pre_build_research/describe.py (the script folder is on the import path)
from describe import describe

URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
HERE = Path(__file__).resolve().parent            # pre_build_research/
HEAD_CSV = HERE / "raw" / "puzzles_head.csv"       # cached slice, gitignored
OUT_JSONL = HERE / "queries.jsonl"
OUT_MD = HERE / "queries.md"

N_ROWS = 200_000          # stream only the first rows of the 310 MB file
SEED = 42
PER_THEME = 5
RATING_MIN, RATING_MAX = 1000, 1800       # club-level blunders
MIN_POPULARITY, MIN_PLAYS = 80, 500       # well-liked, well-tested puzzles

# Fixed before the corpus exists. Lichess theme -> mistake phrase (stands in for our future
# engine-based mistake detector).
THEMES = {
    "fork": "allowed a fork",
    "pin": "allowed a pin",
    "skewer": "allowed a skewer",
    "discoveredAttack": "allowed a discovered attack",
    "hangingPiece": "left a piece undefended",
    "backRankMate": "left the back rank weak and allowed checkmate",
    "trappedPiece": "allowed a piece to be trapped",
    "exposedKing": "left the king exposed to attack",
    "advancedPawn": "allowed an advanced pawn to promote",
}


def download_head() -> None:
    HEAD_CSV.parent.mkdir(parents=True, exist_ok=True)
    print(f"Streaming first {N_ROWS:,} rows of {URL} ...")
    with httpx.stream("GET", URL, headers={"User-Agent": "BlunderTrace retrieval test"},
                      timeout=60, follow_redirects=True) as resp:
        resp.raise_for_status()
        reader = zstandard.ZstdDecompressor().stream_reader(_IterStream(resp.iter_bytes()))
        text = io.TextIOWrapper(reader, encoding="utf-8")
        with HEAD_CSV.open("w", encoding="utf-8") as out:
            for i, line in enumerate(text):
                if i > N_ROWS:          # header + N_ROWS rows
                    break
                out.write(line)
    print(f"Saved {HEAD_CSV}")


class _IterStream(io.RawIOBase):
    """Wrap an iterator of bytes as a readable file object for zstandard."""

    def __init__(self, it):
        self._it, self._buf = it, b""

    def readable(self):
        return True

    def readinto(self, b):
        while not self._buf:
            try:
                self._buf = next(self._it)
            except StopIteration:
                return 0
        n = min(len(b), len(self._buf))
        b[:n], self._buf = self._buf[:n], self._buf[n:]
        return n


def opening_name(tags: str) -> str | None:
    return tags.split()[0].replace("_", " ") if tags.strip() else None


def build_query(row: dict, theme: str) -> dict:
    board = chess.Board(row["FEN"])
    blunder = chess.Move.from_uci(row["Moves"].split()[0])
    blunder_san = board.san(blunder)
    mistake_by = board.turn
    board.push(blunder)
    args = {"opening": opening_name(row["OpeningTags"]), "mistake": THEMES[theme], "mistake_by": mistake_by}
    return {
        "id": row["PuzzleId"],
        "target_theme": theme,
        "all_themes": row["Themes"].split(),
        "rating": int(row["Rating"]),
        "mistake_by": "White" if mistake_by == chess.WHITE else "Black",
        "blunder_san": blunder_san,
        "fen_after_blunder": board.fen(),
        "game_url": row["GameUrl"],
        "query": describe(board, **args),                      # full board description
        "query_short": describe(board, **args, brief=True),    # mistake + phase + opening only
    }


def main() -> None:
    if not HEAD_CSV.exists():
        download_head()
    with HEAD_CSV.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if RATING_MIN <= int(r["Rating"]) <= RATING_MAX
                and int(r["Popularity"]) >= MIN_POPULARITY and int(r["NbPlays"]) >= MIN_PLAYS]
    print(f"{len(rows):,} candidate puzzles after rating/popularity filter")

    rng = random.Random(SEED)
    chosen, used = [], set()
    for theme in THEMES:
        pool = sorted((r for r in rows if theme in r["Themes"].split() and r["PuzzleId"] not in used),
                      key=lambda r: r["PuzzleId"])
        picks = rng.sample(pool, PER_THEME)
        used.update(r["PuzzleId"] for r in picks)
        chosen += [build_query(r, theme) for r in picks]
        print(f"  {theme:18s} pool {len(pool):6,}  picked {PER_THEME}")

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for q in chosen:
            f.write(json.dumps(q) + "\n")

    lines = [f"# Retrieval test queries ({len(chosen)})",
             "", f"Source: Lichess puzzle DB, seed {SEED}, rating {RATING_MIN}-{RATING_MAX}.", ""]
    for i, q in enumerate(chosen, 1):
        lines += [f"## {i}. `{q['target_theme']}` — puzzle {q['id']} (rating {q['rating']})",
                  (f"Blunder: {q['mistake_by']} played **{q['blunder_san']}** · "
                  f"[game]({q['game_url']}) · Lichess themes: {', '.join(q['all_themes'])}"),
                  "", f"**Full:** {q['query']}", "", f"**Short:** {q['query_short']}", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSONL} and {OUT_MD}")


if __name__ == "__main__":
    main()
