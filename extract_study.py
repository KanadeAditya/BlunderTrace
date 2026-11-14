"""
Turn a Lichess study PGN export into (position, comment) rows.

Usage:
    uv run python extract_study.py data/raw/studies/<studyId>.pgn [n_samples]
"""
import re
import sys
from collections import Counter

import chess
import chess.pgn

MIN_COMMENT_CHARS = 40                    # drop "!", "Good." etc.
ANNO_RE = re.compile(r"\[%anno[^\]]*\].*", re.DOTALL)  # notes added by other users: drop to end
TAG_RE = re.compile(r"\[%[^\]]*\]")       # strip [%clk ...], [%cal ...], [%csl ...]


def clean(comment: str) -> str:
    comment = ANNO_RE.sub("", comment)    # python-chess joins all comment blocks; author's text comes first
    comment = TAG_RE.sub("", comment)
    return " ".join(comment.split())      # collapse whitespace / newlines


def extract(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        while (game := chess.pgn.read_game(f)) is not None:   # one game = one chapter
            chapter = game.headers.get("ChapterName") or game.headers.get("Event", "?")
            base = {
                "study": game.headers.get("StudyName", "?"),
                "chapter": chapter,
                "url": game.headers.get("ChapterURL", ""),
            }

            intro = clean(game.comment)                         # chapter intro (before any move)
            if len(intro) >= MIN_COMMENT_CHARS:
                rows.append({**base, "move_no": "intro", "move": "-",
                             "fen": game.board().fen(), "comment": intro})

            node = game
            while node.variations:
                node = node.variation(0)                       # follow the main line
                comment = clean(node.comment)
                if len(comment) < MIN_COMMENT_CHARS:
                    continue
                before = node.parent.board()                   # position BEFORE this move
                prefix = "." if before.turn == chess.WHITE else "..."
                rows.append({**base,
                             "move_no": f"{before.fullmove_number}{prefix}",
                             "move": node.san(),
                             "fen": node.board().fen(),        # position AFTER this move
                             "comment": comment})
    return rows


def count_chapters(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.startswith("[Event "))


if __name__ == "__main__":
    path = sys.argv[1]
    n_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    rows = extract(path)
    per_chapter = Counter(r["chapter"] for r in rows)
    lengths = sorted(len(r["comment"]) for r in rows)

    print(f"{rows[0]['study'] if rows else path}")
    print(f"{len(rows)} usable comments across {count_chapters(path)} chapters "
          f"({len(per_chapter)} chapters have >=1)")
    if lengths:
        print(f"comment length: min {lengths[0]}, median {lengths[len(lengths)//2]}, max {lengths[-1]} chars")
    for chapter, n in per_chapter.most_common():
        print(f"  {n:3d}  {chapter}")
    print()
    for r in rows[:n_samples]:
        print(f"[{r['chapter']}] move {r['move_no']} {r['move']}")
        print(f"  FEN:     {r['fen']}")
        print(f"  Comment: {r['comment'][:300]}\n")
