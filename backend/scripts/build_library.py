"""Build the shipped theory library (data/library/) from the research corpus. Runs on a developer's
machine, never inside the app (docs/BACKEND.md section 8).

    PYTHONPATH=. uv run python scripts/build_library.py --dry-run          # counts + cost, no calls
    PYTHONPATH=. uv run python scripts/build_library.py --yes --limit 10   # tiny paid test run
    PYTHONPATH=. uv run python scripts/build_library.py --yes              # the full paid run
    ... --yes --only lichess-puzzle-themes                                 # paid test on some ids
    ... --yes --retag-empty   # ask again for passages left empty by the first, too strict wording

Steps: load Wikipedia, Wikibooks and the Lichess theme glossary (adding the missing Fork entry) ->
merge paragraphs within a section, up to ~250 words -> prefix "Article › Section:" -> AI tags
(the main model, numbered passages, only the 11 theme keys; every passage must get an answer and
unknown keys are printed, never silently dropped) -> vectors (text-embedding-3-small) for every
passage and the 11 concept queries -> write the files with a checksummed manifest.

Paid calls (tags, vectors) happen only with --yes. Every result is cached by a fingerprint of its
text in .library_cache/ (gitignored), so re-running costs nothing for unchanged passages.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import tiktoken
from pydantic import BaseModel

from app.analysis import THEMES
from app.analysis.patterns import NOT_A_CARD
from app.config import get_settings
from app.rag.fallback import DEFINITIONS
from app.rag.themes import CONCEPT_QUERIES

BACKEND = Path(__file__).resolve().parents[1]
CORPUS = BACKEND.parent / "pre_build_research" / "corpus"
OUT = BACKEND / "data" / "library"
CACHE = BACKEND / ".library_cache"
SOURCES = ("wikipedia", "wikibooks", "lichess_themes", "web")
# corpus files: one per source, plus hand-picked Wikipedia/Wikibooks sections ("additions") and
# IM Dan Heisman's Novice Nook columns ("heisman", source "web"). The additions, web.jsonl
# (excerpts from coaching articles) and the columns were added after the blind retrieval check, for
# advice on *avoiding* each tactic.
CORPUS_FILES = (*SOURCES, "additions", "heisman")
MAX_WORDS = 250
TAG_BATCH = 20  # passages per tagging call
VERSION = "2"  # 2: targeted additions + the advice label
DIMENSIONS = 1536
FORK_ROW = {  # the research corpus's known gap: the glossary has no Fork entry
    "source": "lichess_themes",
    "title": "Lichess puzzle themes",
    "section": "Fork",
    "url": "https://lichess.org/training/fork",
    "text": f"Fork: {DEFINITIONS['fork'][1]}",
}


@dataclass
class Passage:
    id: str
    source: str
    title: str
    section: str
    url: str
    text: str
    tags: list[str]
    advice: list[str] = field(default_factory=list)

    @property
    def searchable(self) -> str:
        """What gets embedded: the title prefix keeps short paragraphs findable for their topic."""
        return f"{self.title} › {self.section}: {self.text}"


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def load_passages() -> list[Passage]:
    rows = []
    for name in CORPUS_FILES:
        with open(CORPUS / f"{name}.jsonl") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    rows.append(FORK_ROW)

    passages: list[Passage] = []
    current: dict | None = None
    for row in rows:
        key = (row["source"], row["title"], row["section"])
        words = len(row["text"].split())
        same = current is not None and current["key"] == key
        if same and current["words"] + words <= MAX_WORDS:
            current["texts"].append(row["text"])
            current["words"] += words
            continue
        if current is not None:
            passages.append(_finish(current, passages))
        current = {"key": key, "url": row["url"], "texts": [row["text"]], "words": words}
    passages.append(_finish(current, passages))
    return passages


def _finish(current: dict, done: list[Passage]) -> Passage:
    source, title, section = current["key"]
    base = f"{source}:{_slug(title)}:{_slug(section)}"
    n = sum(1 for p in done if p.id.rsplit(":", 1)[0] == base)
    return Passage(
        f"{base}:{n}", source, title, section, current["url"], "\n\n".join(current["texts"]), []
    )


# --- the cache ---------------------------------------------------------------------------------


def load_cache(name: str) -> dict:
    path = CACHE / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_cache(name: str, data: dict) -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / f"{name}.json").write_text(json.dumps(data))


# --- labelling: theme tags and advice --------------------------------------------------------
# Two labels per passage, both chosen by the main model once, at build time:
# - tags:   which of the 11 themes the passage is about (it defines, explains or illustrates it);
# - advice: which of the 9 card themes it gives practical advice on *avoiding* (added after the
#           blind retrieval check showed the library explains what a tactic is far more often
#           than how to avoid it; each card gets passages for both halves).

CARD_THEMES = tuple(t for t in THEMES if t not in NOT_A_CARD)


def _key_list(themes: tuple[str, ...]) -> str:
    return "\n".join(f"- {t}: {DEFINITIONS[t][1]}" for t in themes)


TAG_INSTRUCTIONS = f"""You label passages about chess with the tactics they are about.

The tactics, by key:
{_key_list(THEMES)}

For each numbered passage, give the keys of every tactic from this list that the passage defines,
explains or illustrates, or gives advice on (how it works, how to use it, how to avoid or defend
against it). A short definition counts. Leave the list empty only when the passage is not about any
of these tactics (for example history, rules, openings, players, or other chess topics).
Answer for every passage number, using only the keys above."""

ADVICE_INSTRUCTIONS = f"""You read passages about chess for a club player who keeps falling for
certain tactics, and note which tactics each passage helps them avoid.

The tactics, by key:
{_key_list(CARD_THEMES)}

For each numbered passage, give the keys of every tactic from this list for which the passage tells
the reader something they can do: how to avoid allowing it, how to defend against it, or how to
escape it once it happens. General advice counts when it clearly applies to the tactic. A passage
that only defines a tactic, or only shows how the attacker uses it, gives no advice: leave its list
empty. Answer for every passage number, using only the keys above."""


class TaggedPassage(BaseModel):
    n: int  # the passage's number in this request
    themes: list[Literal[THEMES]]


class TagBatch(BaseModel):
    passages: list[TaggedPassage]


class AdvisedPassage(BaseModel):
    n: int
    themes: list[Literal[CARD_THEMES]]


class AdviceBatch(BaseModel):
    passages: list[AdvisedPassage]


LABELS = {  # cache name -> (instructions, answer schema, allowed keys)
    "tags": (TAG_INSTRUCTIONS, TagBatch, THEMES),
    "advice": (ADVICE_INSTRUCTIONS, AdviceBatch, CARD_THEMES),
}
ASKED_AGAIN = "asked-again:"  # marks tag answers given under the current wording (never re-asked)


def needs_label(p: Passage, cache: dict, retag_empty: bool = False) -> bool:
    """Not labelled yet, or (tags with --retag-empty) left empty under the first, too strict
    wording."""
    key = fingerprint(p.searchable)
    found = cache.get(key)
    return found is None or (retag_empty and found == [] and ASKED_AGAIN + key not in cache)


def label_prompt(batch: list[Passage]) -> str:
    return "\n\n".join(f"[{n}] {p.searchable}" for n, p in enumerate(batch, start=1))


def _ask(labeller, instructions: str, allowed: tuple[str, ...], batch: list[Passage]):
    """One call. The answer is read leniently: a key outside the list is dropped *and printed*,
    instead of failing the whole batch (the schema's list of keys is a request, not enforced)."""
    raw = labeller.invoke([("system", instructions), ("human", label_prompt(batch))])
    usage = getattr(raw, "usage_metadata", None) or {}
    args = raw.tool_calls[0]["args"] if raw.tool_calls else {}
    answers: dict[int, list[str]] = {}
    for item in args.get("passages", []) if isinstance(args, dict) else []:
        n, themes = item.get("n"), item.get("themes") or []
        if not isinstance(n, int) or not isinstance(themes, list):
            continue
        answers[n] = [t for t in themes if t in allowed]
        if dropped := [t for t in themes if t not in allowed]:
            print(f"    passage {n}: dropped unknown keys {dropped}")
    if len(answers) < len(batch):
        stop = raw.response_metadata.get("stop_reason")
        print(f"    only {len(answers)}/{len(batch)} answered (stop reason: {stop})")
        (CACHE / "last_label_reply.json").write_text(
            json.dumps({"tool_calls": raw.tool_calls, "content": str(raw.content)[:4000]})
        )
    return answers, usage


def run_labels(
    name: str, passages: list[Passage], model: str, api_key: str, retag_empty: bool = False
) -> tuple[int, int]:
    """Label every passage not in the cache. Every passage must get an answer: any the model
    skipped is asked again (twice at most), never silently saved as "none"."""
    from langchain_anthropic import ChatAnthropic

    instructions, schema, allowed = LABELS[name]
    cache = load_cache(name)
    todo = [p for p in passages if needs_label(p, cache, retag_empty and name == "tags")]
    llm = ChatAnthropic(model=model, api_key=api_key, max_tokens=4000)  # Haiku 5.5: no temperature
    labeller = llm.bind_tools([schema], tool_choice=schema.__name__)
    tokens_in = tokens_out = 0
    for start in range(0, len(todo), TAG_BATCH):
        pending = todo[start : start + TAG_BATCH]
        for _attempt in range(3):
            answers, usage = _ask(labeller, instructions, allowed, pending)
            tokens_in += usage.get("input_tokens", 0)
            tokens_out += usage.get("output_tokens", 0)
            for n, p in enumerate(pending, start=1):
                if n in answers:
                    cache[fingerprint(p.searchable)] = answers[n]
                    if name == "tags":
                        cache[ASKED_AGAIN + fingerprint(p.searchable)] = True
            pending = [p for n, p in enumerate(pending, start=1) if n not in answers]
            if not pending:
                break
        if pending:
            raise RuntimeError(f"no answer for {len(pending)} passages after 3 tries")
        save_cache(name, cache)
        print(f"  {name}: {min(start + TAG_BATCH, len(todo))}/{len(todo)}", flush=True)
    for p in passages:
        setattr(p, name, cache[fingerprint(p.searchable)])
    return tokens_in, tokens_out


# --- vectors -----------------------------------------------------------------------------------


def run_embeddings(texts: list[str], model: str, api_key: str) -> np.ndarray:
    from langchain_openai import OpenAIEmbeddings

    cache = load_cache("vectors")
    todo = sorted({t for t in texts if fingerprint(t) not in cache})
    if todo:
        embedder = OpenAIEmbeddings(model=model, api_key=api_key, chunk_size=200)
        for start in range(0, len(todo), 200):
            chunk = todo[start : start + 200]
            for text, vector in zip(chunk, embedder.embed_documents(chunk), strict=True):
                cache[fingerprint(text)] = vector
            save_cache("vectors", cache)
            print(f"  embedded {min(start + 200, len(todo))}/{len(todo)}", flush=True)
    vectors = np.array([cache[fingerprint(t)] for t in texts], dtype=np.float32)
    assert vectors.shape == (len(texts), DIMENSIONS), vectors.shape
    return vectors


# --- the dry run -------------------------------------------------------------------------------


def estimate(
    passages: list[Passage], tag_model: str, embed_model: str, retag_empty: bool = False
) -> float:
    enc = tiktoken.get_encoding("cl100k_base")
    prices = get_settings().model_prices
    vec_cache = load_cache("vectors")

    by_source = {s: sum(1 for p in passages if p.source == s) for s in SOURCES}
    words = [len(p.text.split()) for p in passages]
    print(f"Passages: {len(passages)} {by_source}")
    print(f"  words per passage: median {sorted(words)[len(words) // 2]}, max {max(words)}")
    print("  examples:")
    for p in (passages[0], passages[len(passages) // 2], passages[-1]):
        print(f"    {p.id}: {p.searchable[:110]!r}")

    tag_cost = 0.0
    label_lines = []
    for name, (instructions, _, _) in LABELS.items():
        cache = load_cache(name)
        todo = [p for p in passages if needs_label(p, cache, retag_empty and name == "tags")]
        calls = -(-len(todo) // TAG_BATCH)
        tokens_in = calls * len(enc.encode(instructions)) + sum(
            len(enc.encode(f"[{n}] {p.searchable}")) for n, p in enumerate(todo)
        )
        tokens_out = len(todo) * 40  # ~40 tokens of JSON per passage (the first full run: 37)
        cost = (tokens_in * prices[tag_model][0] + tokens_out * prices[tag_model][1]) / 1e6
        tag_cost += cost
        label_lines.append(
            f"  {name}: {len(todo)} passages not cached, {calls} calls, "
            f"~{tokens_in:,} in + ~{tokens_out:,} out tokens -> ~${cost:.4f}"
        )

    texts = [p.searchable for p in passages] + [q for q, _ in CONCEPT_QUERIES.values()]
    to_embed = [t for t in set(texts) if fingerprint(t) not in vec_cache]
    embed_tokens = sum(len(enc.encode(t)) for t in to_embed)
    embed_cost = embed_tokens * prices[embed_model][0] / 1e6

    print(f"\nLabelling with {tag_model}:")
    print("\n".join(label_lines))
    print(
        f"Vectors with {embed_model}: {len(to_embed)} texts not cached "
        f"({len(passages)} passages + {len(CONCEPT_QUERIES)} concept queries)"
    )
    print(f"  ~{embed_tokens:,} tokens -> ~${embed_cost:.4f}")
    print(f"\nEstimated total: ~${tag_cost + embed_cost:.4f} (token counts are approximate)")
    return tag_cost + embed_cost


# --- writing the files -------------------------------------------------------------------------


def write_library(
    passages: list[Passage], vectors: np.ndarray, query_vectors: np.ndarray, meta: dict
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "passages.jsonl", "w") as f:
        for p in passages:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
    np.save(OUT / "vectors.npy", vectors)
    queries = [{"theme": t, "query": q, "keywords": k} for t, (q, k) in CONCEPT_QUERIES.items()]
    (OUT / "concept_queries.json").write_text(json.dumps(queries, indent=1, ensure_ascii=False))
    np.save(OUT / "concept_vectors.npy", query_vectors)
    files = ["passages.jsonl", "vectors.npy", "concept_queries.json", "concept_vectors.npy"]
    manifest = {
        "version": VERSION,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "passages": len(passages),
        "concept_queries": len(queries),
        "dimensions": DIMENSIONS,
        **meta,
        "sha256": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="counts and cost only, no API calls")
    parser.add_argument("--yes", action="store_true", help="make the paid calls")
    parser.add_argument("--limit", type=int, help="only the first N passages (a tiny test run)")
    parser.add_argument(
        "--retag-empty", action="store_true", help="ask again for passages cached with no themes"
    )
    parser.add_argument("--only", help="only passages whose id contains this text (a test run)")
    args = parser.parse_args()

    settings = get_settings()
    tag_model, embed_model = settings.main_model, settings.embedding_model
    passages = load_passages()
    if args.only:
        passages = [p for p in passages if args.only in p.id]
    if args.limit:
        passages = passages[: args.limit]
    estimate(passages, tag_model, embed_model, args.retag_empty)
    if args.dry_run or not args.yes:
        print("\nDry run only: no API calls were made. Add --yes to run for real.")
        return
    if not (settings.anthropic_api_key and settings.openai_api_key):
        sys.exit("ANTHROPIC_API_KEY and OPENAI_API_KEY are needed for the paid run.")

    started = time.perf_counter()
    print("\nLabelling...")
    anthropic_key = settings.anthropic_api_key.get_secret_value()
    tag_in = tag_out = 0
    for name in LABELS:
        used_in, used_out = run_labels(name, passages, tag_model, anthropic_key, args.retag_empty)
        tag_in, tag_out = tag_in + used_in, tag_out + used_out
    print("Embedding...")
    openai_key = settings.openai_api_key.get_secret_value()
    vectors = run_embeddings([p.searchable for p in passages], embed_model, openai_key)
    query_vectors = run_embeddings(
        [q for q, _ in CONCEPT_QUERIES.values()], embed_model, openai_key
    )
    prices = settings.model_prices
    tag_cost = (tag_in * prices[tag_model][0] + tag_out * prices[tag_model][1]) / 1e6
    before = (
        json.loads((OUT / "manifest.json").read_text()) if (OUT / "manifest.json").exists() else {}
    )
    tokens_before = before.get("tag_tokens", {"in": 0, "out": 0})
    meta = {
        "tag_model": tag_model,
        "embedding_model": embed_model,
        "tag_tokens": {"in": tokens_before["in"] + tag_in, "out": tokens_before["out"] + tag_out},
        "tag_cost_usd": round(before.get("tag_cost_usd", 0) + tag_cost, 5),  # all runs together
    }
    if args.limit or args.only:
        print(
            f"\nTest run on {len(passages)} passages done in "
            f"{time.perf_counter() - started:.0f} s; "
            f"tagging cost ${tag_cost:.5f}. Not writing the library (it would be partial)."
        )
        for p in passages:
            print(f"  {p.id}: tags {p.tags}, advice {p.advice}")
        return
    write_library(passages, vectors, query_vectors, meta)
    tagged = sum(1 for p in passages if p.tags)
    advised = sum(1 for p in passages if p.advice)
    print(
        f"\nWrote {OUT} in {time.perf_counter() - started:.0f} s: {len(passages)} passages "
        f"({tagged} tagged, {advised} with advice), labelling cost this run ${tag_cost:.5f}"
    )


if __name__ == "__main__":
    main()
