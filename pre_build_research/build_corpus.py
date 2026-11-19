"""
Collect the retrieval-test corpus from all sources into one row format. No AI involved.

Sources (raw downloads cached in pre_build_research/raw/<source>/, re-runs don't re-download):
  lichess_study  - comments from Lichess studies (position + human explanation)
  wikipedia      - chess concept articles, split by section/paragraph
  wikibooks      - "Chess" Wikibook chapters, split by section/paragraph
  gutenberg      - public-domain books (Capablanca, Edward Lasker), prose paragraphs only
  lichess_themes - Lichess puzzle-theme glossary (one line per theme)

Output: pre_build_research/corpus/<source>.jsonl, one row per line:
  {id, source, title, section, url, text, fen (studies only, else null), meta}

Usage:
    uv run python build_corpus.py
"""
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent            # pre_build_research/
sys.path.insert(0, str(HERE))
from extract_study import extract

RAW = HERE / "raw"                                 # downloads, gitignored
OUT = HERE / "corpus"
HEADERS = {"User-Agent": "BlunderTrace corpus builder"}

STUDY_IDS = ["8c8bmUfy", "txE6GcIe", "kKRTP1Ft", "xx2nOKJv", "s4DZZjXo", "gfZY383j"]
MIN_STUDY_ROWS = 10      # skip studies with fewer usable comments

WIKIPEDIA_TITLES = [
    "Chess tactic", "Chess strategy", "Fork (chess)", "Pin (chess)", "Skewer (chess)",
    "Discovered attack", "Double check", "Back-rank checkmate", "Deflection (chess)",
    "Decoy (chess)", "Overloading (chess)", "Interference (chess)", "Zwischenzug",
    "Desperado (chess)", "X-ray (chess)", "Undermining (chess)", "Sacrifice (chess)",
    "Castling", "Pawn structure", "Isolated pawn", "Doubled pawns", "Passed pawn",
    "Backward pawn", "Promotion (chess)", "Opposition (chess)", "Zugzwang", "Chess endgame",
    "Open file", "Outpost (chess)", "Fianchetto", "Chess opening", "Checkmate pattern",
    "Exchange (chess)", "Chess piece relative value", "Tempo (chess)", "Initiative (chess)",
]
GLOSSARY_TITLE = "Glossary of chess"     # parsed per term, not per paragraph
WIKIBOOKS_TITLES = [
    "Chess/Tactics", "Chess/Strategy", "Chess/Checkmates", "Chess/Development", "Chess/Mobility",
    "Chess/Tempo", "Chess/The Endgame", "Chess/The Endgame/Pawn Endings",
    "Chess/The Endgame/Rook and Pawn Endings", "Chess/The Endgame/Minor Piece endings",
]
# Targeted additions (18 Nov, after the blind retrieval check): sections with practical advice on
# *avoiding* a tactic, which the library above lacked for fork, trapped piece, advanced pawn and
# others. Hand-picked section by section; each paragraph was read before adding.
ADDITIONS = {
    ("wikipedia", "Blunder (chess)"): ["Introduction"],
    ("wikipedia", "King and pawn versus king endgame"): ["Introduction", "Rule of the square",
                                                          "Guidelines"],
    ("wikipedia", "Knight (chess)"): ["Value"],
    ("wikipedia", "Queen (chess)"): ["Strategy"],
    ("wikipedia", "Noah's Ark Trap"): ["Introduction", "The trap"],
    ("wikibooks", "Chess Strategy/The positions of the kings"): [
        "King positions", "The castled king position", "The king in the center",
        "Open lines in the attack against the king"],
    ("wikibooks", "Chess Strategy/Minor pieces"): ["Rules of knights"],
    ("wikibooks", "Chess Guide for the Intermediate Player/Tactics for beginners"): ["Defending",
                                                                                     "Exchanging"],
}
# Hand-picked sections are prose that names squares ("pawns on f7, g7 and h7"), which the general
# notation filter drops; here only paragraphs that are mostly a game score are dropped.
ADDITIONS_NOTATION_MAX = 0.35
ADDITIONS_MIN_PARAGRAPH = 60
# IM Dan Heisman's "Novice Nook" columns (ChessCafe, 1999-2013, written for 1000-1400 players),
# from the Internet Archive's copies of the original PDFs. Only the columns about safety and our
# card themes; picked by title and content. Text comes from raw/heisman/text/ (pypdf).
HEISMAN_COLUMNS = {
    5: "The Seeds of Tactical Destruction", 7: "The Most Common Opening Tactics",
    8: "The Underrated Removal of the Guard", 10: "Real Chess, Time Management and Care",
    14: "A Generic Thought Process", 15: "A Counting Primer", 22: "K&P&? vs. K",
    24: "Revisiting the Seeds of Tactical Destruction", 26: "King + Pawn vs. King",
    35: "The Most Important Tactic", 44: "A Defense Primer", 47: "The Big Five",
    48: "A Guide to P-R3", 55: "Quiescence Errors", 56: "When is a King Safe?",
    59: "Initial and Final Candidate Moves", 61: "The Two Move Triggers", 65: "Is it Safe?",
    70: "The Most Common OTB Mistakes", 73: "Slowing Down",
    75: "The Two Types of Counting Problems", 80: "Don't Allow the Floobly!",
    84: "The Inadequately Guarded Piece", 86: "The Three Types of Reasonable Threats",
    87: "The Fundamental Theorem of Safety and Activity", 92: "The Safety Table",
    96: "The Five Ways to Make a Piece Safe", 104: "The Three Show Stoppers",
    106: "The Most Common and Important Use of Tactics", 111: "Hand-Waving is Worse than Hope Chess",
    119: "Counting Material", 125: 'The Three "Times" for Checks, Captures, and Threats',
    132: "Attack it with Something Worth Less", 136: "Sneaky Pins and Invisible Moves",
}
HEISMAN_CHUNK_WORDS = 100          # rows of ~100 words; the library build merges them up to 250
HEISMAN_CLUTTER = re.compile(
    r"^(novice nook|dan heisman|file:///|copyright|\[the chess cafe|\[endgame|\[links|\[online|"
    r"play through and download|the games from|chesscafe\.com in the|dgt game viewer|the complete$|"
    r"dgt product line|\[find us on facebook|translate this page|click here|top of page|about the|"
    r"\"the chess cafe|.*all rights reserved)", re.I)
GUTENBERG_BOOKS = {33870: "Chess Fundamentals (Capablanca)", 5614: "Chess Strategy (Edward Lasker)"}
THEMES_URL = "https://raw.githubusercontent.com/lichess-org/lila/master/translation/source/puzzleTheme.xml"
# Puzzle-meta labels that say nothing about chess ideas
THEME_SKIP = {"advantage", "crushing", "equality", "mate", "mateIn1", "mateIn2", "mateIn3", "mateIn4",
              "mateIn5", "oneMove", "short", "long", "veryLong", "master", "masterVsMaster", "superGM",
              "playerGames", "mix", "healthyMix", "opening", "middlegame", "endgame", "puzzleDownloadInformation"}

SKIP_SECTIONS = {"see also", "references", "notes", "external links", "further reading",
                 "bibliography", "sources", "citations", "footnotes"}
MIN_PARAGRAPH = 100

# Descriptive (P-K4, Kt-KB3, R - R 7) and algebraic (Nf3, exd5, 12.Qh5) move tokens
NOTATION_RE = re.compile(r"\b(?:Kt|[KQRBP])\s?[-x]\s?(?:[KQ]\s?)?(?:Kt|[KQRBP])?\s?\d"   # P-K4, R - R 7
                         r"|\b(?:Q|K)?(?:Kt|[KQRBP])\s?x\s?(?:Q|K)?(?:Kt|[KQRBP])\b"       # KtxB, PxP, QBxKt
                         r"|\b(?:Q|K)?(?:Kt|[RBP])\s?-\s?(?:Q|K)(?:Kt|[RB])?\b"           # B-K, Kt-QB
                         r"|\b[KQRBN]?[a-h]?x?[a-h][1-8]\b|\b\d+\s?\.{1,3}")              # Nf3, exd5, 12.
NOTATION_MAX = 0.1       # share of words that are move notation; above this = drop (0.1-0.2 is still board-dependent game commentary)


# ---------- helpers ----------

def get(client: httpx.Client, url: str, **params) -> httpx.Response:
    for attempt in range(4):
        resp = client.get(url, params=params)
        if resp.status_code == 429 and attempt < 3:        # rate limited: back off and retry
            wait = int(resp.headers.get("Retry-After", 0) or 0) or 30 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s ...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        break
    time.sleep(2)                           # be polite between requests
    return resp


def cached(path: Path, fetch) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fetch(), encoding="utf-8")
    return path.read_text(encoding="utf-8")


def notation_ratio(text: str) -> float:
    words = len(text.split()) or 1
    return 3 * len(NOTATION_RE.findall(text)) / words   # each move ≈ 3 words of text


def split_sections(text: str) -> list[tuple[str, str]]:
    """MediaWiki plain-text extract -> [(section heading, body)]."""
    parts = re.split(r"^(={2,})\s*(.+?)\s*\1\s*$", text, flags=re.MULTILINE)
    sections = [("Introduction", parts[0])]
    for i in range(1, len(parts) - 2, 3):
        sections.append((parts[i + 1], parts[i + 2]))
    return sections


def paragraphs(body: str) -> list[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n|\n", body) if p.strip()]


def mediawiki_extract(client, host: str, title: str, cache_dir: Path) -> str:
    safe = re.sub(r"[^\w.-]", "_", title)
    raw = cached(cache_dir / f"{safe}.json", lambda: get(
        client, f"https://{host}/w/api.php", action="query", prop="extracts", explaintext=1,
        redirects=1, format="json", titles=title).text)
    page = next(iter(json.loads(raw)["query"]["pages"].values()))
    return page.get("extract", "")


# ---------- sources ----------

def lichess_studies() -> list[dict]:
    rows = []
    for sid in STUDY_IDS:
        path = RAW / "studies" / f"{sid}.pgn"
        if not path.exists():
            print(f"  study {sid}: not downloaded, skipped")
            continue
        extracted = extract(str(path))
        if len(extracted) < MIN_STUDY_ROWS:
            print(f"  study {sid}: only {len(extracted)} rows, skipped")
            continue
        for i, r in enumerate(extracted):
            title = r["study"].replace('\\"', "").replace('"', "")     # PGN-escaped quotes
            rows.append({"id": f"study:{sid}:{i}", "source": "lichess_study", "title": title,
                         "section": r["chapter"], "url": r["url"], "text": r["comment"], "fen": r["fen"],
                         "meta": {"move_no": r["move_no"], "move": r["move"], "opening": r["opening"]}})
    return rows


def mediawiki_source(client, source: str, host: str, titles: list[str], url_base: str) -> list[dict]:
    rows = []
    for title in titles:
        text = mediawiki_extract(client, host, title, RAW / source)
        if not text:
            print(f"  {source}: '{title}' empty, skipped")
            continue
        n = 0
        for section, body in split_sections(text):
            if section.lower() in SKIP_SECTIONS:
                continue
            for p in paragraphs(body):
                if len(p) < MIN_PARAGRAPH or notation_ratio(p) > NOTATION_MAX:
                    continue
                rows.append({"id": f"{source}:{title}:{n}", "source": source, "title": title,
                             "section": section, "url": url_base + title.replace(" ", "_"),
                             "text": p, "fen": None, "meta": {}})
                n += 1
    return rows


def additions(client) -> list[dict]:
    hosts = {"wikipedia": "en.wikipedia.org", "wikibooks": "en.wikibooks.org"}
    rows = []
    for (source, title), wanted in ADDITIONS.items():
        found = dict(split_sections(mediawiki_extract(client, hosts[source], title, RAW / source)))
        n = 0
        for section in wanted:
            for p in paragraphs(found[section]):
                if len(p) < ADDITIONS_MIN_PARAGRAPH or notation_ratio(p) > ADDITIONS_NOTATION_MAX:
                    continue
                rows.append({"id": f"{source}:{title}:{n}", "source": source, "title": title,
                             "section": section,
                             "url": f"https://{hosts[source]}/wiki/" + title.replace(" ", "_"),
                             "text": p, "fen": None, "meta": {"addition": True}})
                n += 1
    return rows


def heisman() -> list[dict]:
    rows = []
    for n, title in HEISMAN_COLUMNS.items():
        lines = [l.strip() for l in (RAW / "heisman" / "text" / f"heisman{n:02d}.txt").open(encoding="utf-8")]
        lines = [l for l in lines if l and not HEISMAN_CLUTTER.match(l)]
        quote = next((i for i, l in enumerate(lines[:40]) if re.search(r"(quote|saying) of the month", l, re.I)), None)
        body = re.sub(r"(\w)-\s+(\w)", r"\1\2", " ".join(lines[(quote or 0):]))   # join hyphenated breaks
        sentences = re.split(r"(?<=[.!?”\"])\s+(?=[A-Z“\"])", body)
        chunk: list[str] = []
        def flush() -> None:
            text = " ".join(chunk)
            if len(text) >= MIN_PARAGRAPH and notation_ratio(text) <= NOTATION_MAX:
                rows.append({"id": f"heisman:{n}:{len(rows)}", "source": "web",
                             "title": f"Novice Nook: {title} (Dan Heisman)", "section": title,
                             "url": f"https://web.archive.org/web/2010/http://www.chesscafe.com/text/heisman{n:02d}.pdf",
                             "text": text, "fen": None, "meta": {"addition": True, "column": n}})
        for sentence in sentences:
            chunk.append(sentence)
            if sum(len(c.split()) for c in chunk) >= HEISMAN_CHUNK_WORDS:
                flush(); chunk = []
        if chunk:
            flush()
    return rows


def write_rows(name: str, rows: list[dict]) -> None:
    with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def wikipedia_glossary(client) -> list[dict]:
    text = mediawiki_extract(client, "en.wikipedia.org", GLOSSARY_TITLE, RAW / "wikipedia")
    rows = []
    for section, body in split_sections(text):
        if section.lower() in SKIP_SECTIONS:
            continue
        for block in re.split(r"\n\s*\n", body):
            lines = [x.strip() for x in block.strip().splitlines() if x.strip()]
            if len(lines) < 2 or len(lines[0]) > 60:
                continue
            term, definition = lines[0], " ".join(" ".join(lines[1:]).split())
            if len(definition) < 40 or definition.lower().startswith("see "):
                continue
            rows.append({"id": f"wikipedia:glossary:{term}", "source": "wikipedia", "title": GLOSSARY_TITLE,
                         "section": term, "url": "https://en.wikipedia.org/wiki/Glossary_of_chess",
                         "text": f"{term}: {definition}", "fen": None, "meta": {"glossary": True}})
    return rows


def gutenberg(client) -> list[dict]:
    rows = []
    for book_id, title in GUTENBERG_BOOKS.items():
        text = cached(RAW / "gutenberg" / f"pg{book_id}.txt",
                      lambda b=book_id: get(client, f"https://www.gutenberg.org/cache/epub/{b}/pg{b}.txt").text)
        start = text.find("*** START OF")
        end = text.find("*** END OF")
        body = text[text.find("\n", start) + 1:end if end > 0 else None]
        chapter, n, dropped = "Front matter", 0, 0
        for block in re.split(r"\n\s*\n", body):
            p = " ".join(block.split())
            if re.match(r"^(CHAPTER|PART|BOOK)\b", p) and len(p) < 80:
                chapter = p.title()
                continue
            if len(p) < 150:
                continue
            if notation_ratio(p) > NOTATION_MAX:
                dropped += 1
                continue
            rows.append({"id": f"gutenberg:{book_id}:{n}", "source": "gutenberg", "title": title,
                         "section": chapter, "url": f"https://www.gutenberg.org/ebooks/{book_id}",
                         "text": p.replace("_", ""), "fen": None, "meta": {}})
            n += 1
        print(f"  gutenberg {book_id}: kept {n} prose paragraphs, dropped {dropped} notation-heavy")
    return rows


def lichess_themes(client) -> list[dict]:
    xml = cached(RAW / "lichess_themes" / "puzzleTheme.xml", lambda: get(client, THEMES_URL).text)
    strings = {e.get("name"): (e.text or "").strip() for e in ET.fromstring(xml).iter("string")}
    rows = []
    for key, name in strings.items():
        if key.endswith("Description") or key in THEME_SKIP or f"{key}Description" not in strings:
            continue
        desc = re.sub(r"\s*\([^)]*cp[^)]*\)", "", strings[f"{key}Description"])   # drop eval ranges
        rows.append({"id": f"theme:{key}", "source": "lichess_themes", "title": "Lichess puzzle themes",
                     "section": name, "url": f"https://lichess.org/training/{key}",
                     "text": f"{name}: {desc}", "fen": None, "meta": {"theme": key}})
    return rows


# ---------- main ----------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        sources = {
            "lichess_study": lichess_studies(),
            "wikipedia": mediawiki_source(client, "wikipedia", "en.wikipedia.org", WIKIPEDIA_TITLES,
                                          "https://en.wikipedia.org/wiki/") + wikipedia_glossary(client),
            "wikibooks": mediawiki_source(client, "wikibooks", "en.wikibooks.org", WIKIBOOKS_TITLES,
                                          "https://en.wikibooks.org/wiki/"),
            "gutenberg": gutenberg(client),
            "lichess_themes": lichess_themes(client),
        }
    print()
    for name, rows in sources.items():
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        lengths = sorted(len(r["text"]) for r in rows) or [0]
        print(f"{name:15s} {len(rows):5d} rows  median {lengths[len(lengths) // 2]:4d} chars"
              f"  ~{sum(lengths) // 4:,} tokens")
    total = sum(len(r) for r in sources.values())
    tokens = sum(len(r["text"]) for rows in sources.values() for r in rows) // 4
    print(f"{'TOTAL':15s} {total:5d} rows  ~{tokens:,} tokens  "
          f"(embedding cost ≈ ${tokens * 0.02 / 1e6:.4f})")


if __name__ == "__main__":
    if sys.argv[1:] == ["heisman"]:  # the chosen Novice Nook columns -> corpus/heisman.jsonl
        found = heisman()
        write_rows("heisman", found)
        print(f"heisman: {len(found)} rows from {len(HEISMAN_COLUMNS)} columns")
    elif sys.argv[1:] == ["additions"]:  # only the targeted additions -> corpus/additions.jsonl
        with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as c:
            added = additions(c)
        write_rows("additions", added)
        print(f"additions: {len(added)} rows")
    else:
        main()
