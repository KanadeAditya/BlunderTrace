"""The blind retrieval check (BACKEND.md section 15): is hybrid search better than meaning-only?

    PYTHONPATH=. uv run python scripts/retrieval_check.py sheet   # write the sheet to mark
    PYTHONPATH=. uv run python scripts/retrieval_check.py score   # after marking: the results

For each of the 9 themes that can become a card (quiet and defensive moves never do), the top 5
passages under meaning-only and under hybrid search are pooled, de-duplicated and shuffled, and
which method found each passage is hidden in a separate key file.
The person marking ticks `- [x] relevant` for every passage that explains the theme or how to avoid
it. `score` then un-blinds the marks and counts relevant passages per method and theme.
Needs the library loaded in the local database (the API loads it at startup).
"""

import asyncio
import json
import random
import re
import sys
from pathlib import Path

from app.analysis.patterns import NOT_A_CARD
from app.config import get_settings
from app.db import close_pool, open_pool
from app.rag.fallback import DEFINITIONS
from app.rag.retrieval import retrieve
from app.rag.themes import CONCEPT_QUERIES

OUT = Path(__file__).resolve().parents[2] / "pre_build_research" / "retrieval_check"
SHEET, KEY = OUT / "sheet.md", OUT / "key.json"
SEED = 2026


async def make_sheet() -> None:
    await open_pool(get_settings().database_url)
    rng = random.Random(SEED)
    key: dict[str, dict] = {}
    lines = [
        "# Retrieval check (blind)",
        "",
        "For each theme, tick `- [x] relevant` under every passage that **explains the",
        "tactic or how to avoid it**, well enough to help a club player. Leave `- [ ]` otherwise.",
        "Which search found each passage is hidden. When done, tell Claude to score it.",
        "",
    ]
    item = 0
    for theme, (question, _) in CONCEPT_QUERIES.items():
        if theme in NOT_A_CARD:
            continue
        meaning = {p["id"]: p for p in await retrieve(theme, "meaning")}
        hybrid = {p["id"]: p for p in await retrieve(theme, "hybrid")}
        pooled = list({**meaning, **hybrid}.values())
        rng.shuffle(pooled)
        lines += [f"## {DEFINITIONS[theme][0]}", "", f"*Search: {question}*", ""]
        for passage in pooled:
            item += 1
            key[str(item)] = {
                "theme": theme,
                "id": passage["id"],
                "meaning": passage["id"] in meaning,
                "hybrid": passage["id"] in hybrid,
            }
            text = passage["text"].replace("\n\n", " ")
            lines += [
                f"### {item}. {passage['title']} › {passage['section']}",
                "",
                f"> {text}",
                "",
                "- [ ] relevant",
                "",
            ]
    OUT.mkdir(parents=True, exist_ok=True)
    SHEET.write_text("\n".join(lines))
    KEY.write_text(json.dumps(key, indent=1))
    await close_pool()
    print(f"Wrote {SHEET} ({item} passages to mark). The key is in {KEY.name}; don't open it.")


def score() -> None:
    marks: dict[str, bool] = {}
    current = None
    for line in SHEET.read_text().splitlines():
        if found := re.match(r"### (\d+)\. ", line):
            current = found.group(1)
        elif current and (found := re.match(r"- \[( |x|X)\] relevant", line.strip())):
            marks[current] = found.group(1).lower() == "x"
    key = json.loads(KEY.read_text())
    rows, totals = [], {"meaning": 0, "hybrid": 0}
    card_themes = [t for t in CONCEPT_QUERIES if t not in NOT_A_CARD]
    for theme in card_themes:
        counts = {
            m: sum(1 for i, k in key.items() if k["theme"] == theme and k[m] and marks.get(i))
            for m in ("meaning", "hybrid")
        }
        totals = {m: totals[m] + counts[m] for m in totals}
        rows.append(f"| {DEFINITIONS[theme][0]} | {counts['meaning']}/5 | {counts['hybrid']}/5 |")
    themes = len(card_themes)
    print("| Theme | Meaning only | Hybrid |\n|---|---|---|")
    print("\n".join(rows))
    meaning, hybrid = totals["meaning"], totals["hybrid"]
    print(f"| **All** | **{meaning}/{5 * themes}** | **{hybrid}/{5 * themes}** |")


if __name__ == "__main__":
    if sys.argv[1:] == ["sheet"]:
        asyncio.run(make_sheet())
    elif sys.argv[1:] == ["score"]:
        score()
    else:
        sys.exit("usage: retrieval_check.py sheet|score")
