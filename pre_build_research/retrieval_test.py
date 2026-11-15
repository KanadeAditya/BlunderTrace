"""
Retrieval experiment: do embedded corpus rows retrieve useful explanations for real blunders?

Commands:
    uv run python pre_build_research/retrieval_test.py build            # dry run: shows what would be embedded + cost
    uv run python pre_build_research/retrieval_test.py build --yes      # embed (the ONLY step that calls the API)
    uv run python pre_build_research/retrieval_test.py query            # rank + auto score + blinded CSV (needs cache)
    uv run python pre_build_research/retrieval_test.py score            # after marking results.csv: blind human score

API safety:
- The only OpenAI call in this file is embeddings.create with the fixed model below (see embed()).
- No chat/completion models are used anywhere. The key is read from .env by the OpenAI client and is
  never printed or logged.
- Hard token budget: the run aborts before any request if the estimate exceeds MAX_TOKENS.
- Every embedding is cached by text hash; `query` and `score` never call the API (query embeddings
  are produced by `build` too).
- Every request's real token usage is appended to pre_build_research/cache/usage.jsonl.
"""
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import chess
import numpy as np

HERE = Path(__file__).resolve().parent            # pre_build_research/
REPO = HERE.parent                                 # repo root (holds .env)
sys.path.insert(0, str(HERE))
from describe import describe, game_phase

CORPUS = HERE / "corpus"
QUERIES = HERE / "queries.jsonl"
CACHE = HERE / "cache"                             # embeddings (paid for once), gitignored
REPORTS = HERE / "results"                         # top5.md + summary.md (committed)
RESULTS = HERE / "results.csv"                     # blind sheet you mark (not committed)
RESULTS_KEY = HERE / "results_key.csv"

EMBEDDING_MODEL = "text-embedding-3-small"     # the only model this script may call
PRICE_PER_M_TOKENS = 0.02
MAX_TOKENS = 400_000                           # hard budget (~$0.008)
BATCH = 256
TOP_K = 5

CONCEPT_SOURCES = ["wikipedia", "wikibooks", "gutenberg", "lichess_themes"]

# Fixed keyword table for the automatic score: does a retrieved text talk about the puzzle's theme?
THEME_KEYWORDS = {
    "fork": r"\bfork|double attack|attacks two",
    "pin": r"\bpin(s|ned|ning)?\b",
    "skewer": r"skewer",
    "discoveredAttack": r"discovered (attack|check)|\bdiscovery\b",
    "hangingPiece": r"hanging|undefended|unprotected|unguarded|en prise|loose piece",
    "backRankMate": r"back[- ]rank|first rank|eighth rank|luft",
    "trappedPiece": r"\btrapped|trap(ping)? (a|the) piece",
    "exposedKing": r"exposed king|king (is |was )?exposed|king safety|unsafe king|pawn shield|"
                   r"attack (on|against) the king|attack the king|king hunt|weakened king",
    "advancedPawn": r"promot|passed pawn|queening|advanced pawn",
}

BLIND_QUERIES = 10       # queries sampled for the human check
BLIND_TOP = 3            # top-k per variant shown to the human
SEED = 7


# ---------- corpus variants (no AI) ----------

def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def study_template(r: dict) -> str:
    board = chess.Board(r["fen"])
    opening = r["meta"]["opening"]
    parts = [f"{r['title']}.", f"{r['section']}."]
    if opening and opening != "?":
        parts.append(f"Opening: {opening}.")
    parts.append(f"Phase: {game_phase(board).lower()}.")
    if r["meta"]["move"] != "-":
        parts.append(f"Move {r['meta']['move_no']} {r['meta']['move']}.")
    return " ".join(parts + [r["text"]])


def study_describe(r: dict) -> str:
    opening = r["meta"]["opening"]
    board_text = describe(chess.Board(r["fen"]), opening=opening if opening != "?" else None)
    return f"{board_text} {r['text']}"


def build_variants() -> dict[str, list[dict]]:
    """Each variant = list of {id, source, title, section, url, text (shown), embed_text}."""
    studies = load_jsonl(CORPUS / "lichess_study.jsonl")
    concepts = [r for s in CONCEPT_SOURCES for r in load_jsonl(CORPUS / f"{s}.jsonl")]

    def rows(src: list[dict], fn) -> list[dict]:
        return [{**r, "embed_text": fn(r)} for r in src]

    a_raw = rows(studies, lambda r: r["text"])
    b_template = rows(studies, study_template)
    b2_describe = rows(studies, study_describe)
    c_concepts = rows(concepts, lambda r: r["text"])
    return {
        "A_raw": a_raw,
        "B_template": b_template,
        "B2_describe": b2_describe,
        "C_concepts": c_concepts,
        "D_mix": b2_describe + c_concepts,
        "D_mix_no_themes": b2_describe + [r for r in c_concepts if r["source"] != "lichess_themes"],
    }


def load_queries() -> list[dict]:
    return load_jsonl(QUERIES)


def all_texts(variants, queries) -> list[str]:
    texts = {r["embed_text"] for rows in variants.values() for r in rows}
    texts |= {q["query"] for q in queries} | {q["query_short"] for q in queries}
    return sorted(texts)


# ---------- embedding (the only API use) ----------

def key(text: str) -> str:
    return hashlib.sha256(f"{EMBEDDING_MODEL}\n{text}".encode()).hexdigest()


def load_cache() -> dict[str, list[float]]:
    path = CACHE / "embeddings.jsonl"
    if not path.exists():
        return {}
    return {row["k"]: row["v"] for row in load_jsonl(path)}


def count_tokens(texts: list[str]) -> int:
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")   # tokenizer used by text-embedding-3-*
    return sum(len(enc.encode(t)) for t in texts)


def embed(texts: list[str]) -> list[list[float]]:
    """The single place that talks to OpenAI: embeddings only, fixed model."""
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(REPO / ".env")
    client = OpenAI()                            # reads OPENAI_API_KEY from env; never printed
    out = []
    with (CACHE / "usage.jsonl").open("a", encoding="utf-8") as usage:
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            assert resp.model.startswith(EMBEDDING_MODEL), resp.model
            usage.write(json.dumps({"model": resp.model, "inputs": len(batch),
                                    "tokens": resp.usage.total_tokens}) + "\n")
            out += [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
            print(f"  embedded {min(i + BATCH, len(texts))}/{len(texts)}")
    return out


def cmd_build(confirm: bool) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    variants, queries = build_variants(), load_queries()
    for name, rows in variants.items():
        print(f"{name:16s} {len(rows):5d} rows")
    texts = all_texts(variants, queries)
    cache = load_cache()
    todo = [t for t in texts if key(t) not in cache]
    tokens = count_tokens(todo)
    print(f"\n{len(texts)} unique texts, {len(texts) - len(todo)} cached, {len(todo)} to embed")
    print(f"{tokens:,} tokens with {EMBEDDING_MODEL} -> ${tokens * PRICE_PER_M_TOKENS / 1e6:.4f}"
          f" (budget {MAX_TOKENS:,})")
    if tokens > MAX_TOKENS:
        sys.exit("ABORT: over token budget, nothing sent.")
    if not todo:
        print("Nothing to embed.")
        return
    if not confirm:
        print("\nDry run: no API call made. Re-run with --yes to embed.")
        return
    vectors = embed(todo)
    with (CACHE / "embeddings.jsonl").open("a", encoding="utf-8") as f:
        for t, v in zip(todo, vectors, strict=True):
            f.write(json.dumps({"k": key(t), "v": v}) + "\n")
    used = sum(json.loads(line)["tokens"] for line in (CACHE / "usage.jsonl").open())
    print(f"Done. Total tokens billed so far (all runs): {used:,} -> ${used * PRICE_PER_M_TOKENS / 1e6:.4f}")


# ---------- retrieval + scoring (no API) ----------

def normalize_rows(m: np.ndarray) -> np.ndarray:
    """Scale every row to length 1, so a dot product equals cosine similarity."""
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def top_k(corpus: np.ndarray, query: np.ndarray, k: int = TOP_K) -> list[tuple[int, float]]:
    """Cosine search: (row index, score) of the k most similar rows, best first.

    `corpus` and `query` must already be normalized (see normalize_rows).
    """
    scores = corpus @ query
    order = np.argsort(-scores, kind="stable")[:k]
    return [(int(i), float(scores[i])) for i in order]


def matrix(rows: list[dict], cache) -> np.ndarray:
    return normalize_rows(np.array([cache[key(r["embed_text"])] for r in rows], dtype=np.float32))


def vec(text: str, cache) -> np.ndarray:
    if key(text) not in cache:
        sys.exit("Missing embedding: run `build --yes` first (query never calls the API).")
    return normalize_rows(np.array(cache[key(text)], dtype=np.float32))


def theme_hit(theme: str, text: str) -> bool:
    return re.search(THEME_KEYWORDS[theme], text, flags=re.IGNORECASE) is not None


def self_check(rows: list[dict], mat: np.ndarray, cache, n: int = 20) -> None:
    """Search with 20 corpus rows' own embeddings: each must come back as #1 (score ~1.0).

    If this fails the search code or the cache is broken and no other number can be trusted.
    Rows with identical text are interchangeable, so a tie with an identical text also passes.
    """
    rng = random.Random(SEED)
    failures = []
    for i in rng.sample(range(len(rows)), n):
        (best, score), = top_k(mat, vec(rows[i]["embed_text"], cache), k=1)
        if rows[best]["embed_text"] != rows[i]["embed_text"] or score < 0.999:
            failures.append((rows[i]["id"], rows[best]["id"], score))
    if failures:
        sys.exit(f"SELF-CHECK FAILED ({len(failures)}/{n}): {failures[:3]}")
    print(f"Self-check passed: {n}/{n} corpus rows found themselves at #1 (score ≈ 1.0)\n")


def require_embeddings(variants, queries, cache) -> None:
    missing = sum(key(t) not in cache for t in all_texts(variants, queries))
    if missing:
        sys.exit(f"{missing} texts have no embedding yet: run `build --yes` first "
                 "(query and score never call the API).")


def cmd_query() -> None:
    variants, queries, cache = build_variants(), load_queries(), load_cache()
    require_embeddings(variants, queries, cache)
    mats = {name: matrix(rows, cache) for name, rows in variants.items()}
    self_check(variants["D_mix"], mats["D_mix"], cache)

    results = {}                    # (variant, qtype, query id) -> list of (score, row)
    for name, rows in variants.items():
        for qtype in ("query", "query_short"):
            for q in queries:
                hits = top_k(mats[name], vec(q[qtype], cache))
                results[(name, qtype, q["id"])] = [(score, rows[i]) for i, score in hits]

    # summary tables: printed and saved to pre_build_research/results/summary.md
    header = (f"# Retrieval test summary\n\nAUTOMATIC SCORE: hit@{TOP_K} = share of queries with "
              f">=1 top-{TOP_K} result mentioning the theme (keyword list in retrieval_test.py)\n")
    out = [header, "```",
           f"{'variant':16s} {'full query':>11s} {'short query':>12s}"]
    for name in variants:
        line = f"{name:16s}"
        for qtype in ("query", "query_short"):
            hits = sum(any(theme_hit(q["target_theme"], r["text"]) for _, r in results[(name, qtype, q["id"])])
                       for q in queries)
            line += f" {hits:>5d}/{len(queries)} {hits / len(queries):4.0%}"
        out.append(line)

    out.append(f"\nPer theme (D_mix, full query) — hits out of {len(queries) // len(THEME_KEYWORDS)}:")
    for theme in THEME_KEYWORDS:
        qs = [q for q in queries if q["target_theme"] == theme]
        hits = sum(any(theme_hit(theme, r["text"]) for _, r in results[("D_mix", "query", q["id"])]) for q in qs)
        out.append(f"  {theme:18s} {hits}/{len(qs)}")

    out.append(f"\nWhich sources fill the top {TOP_K} in D_mix (full / short query):")
    for qtype in ("query", "query_short"):
        counts: dict[str, int] = {}
        for q in queries:
            for _, r in results[("D_mix", qtype, q["id"])]:
                counts[r["source"]] = counts.get(r["source"], 0) + 1
        out.append(f"  {qtype:12s} " + ", ".join(f"{s} {n}" for s, n in sorted(counts.items(), key=lambda x: -x[1])))
    out.append("```")
    print("\n".join(out))
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "summary.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    # readable dump of every result
    dump = REPORTS / "top5.md"
    with dump.open("w", encoding="utf-8") as f:
        f.write(f"# Top-{TOP_K} results for all {len(queries)} queries\n\n✅ = mentions the puzzle's theme "
                "(automatic keyword check). Score = cosine similarity (higher = more similar).\n")
        for q in queries:
            f.write(f"\n## {q['id']} `{q['target_theme']}`\n\n**Full:** {q['query']}\n\n**Short:** {q['query_short']}\n")
            for name in variants:
                for qtype in ("query", "query_short"):
                    f.write(f"\n**{name} / {qtype}**\n\n")
                    for s, r in results[(name, qtype, q["id"])]:
                        mark = "✅" if theme_hit(q["target_theme"], r["text"]) else "  "
                        f.write(f"- {mark} {s:.3f} [{r['source']} · {r['title']} · {r['section']}] {r['text'][:220]}\n")
    print(f"\nAll top-{TOP_K} results: {dump}")

    # blinded sample for the human check
    rng = random.Random(SEED)
    sample = rng.sample(queries, BLIND_QUERIES)
    rows, seen = [], set()
    for q in sample:
        for name in variants:
            for _, r in results[(name, "query", q["id"])][:BLIND_TOP]:
                if (q["id"], r["id"]) in seen:
                    continue
                seen.add((q["id"], r["id"]))
                rows.append((q, r))
    rng.shuffle(rows)
    with RESULTS.open("w", newline="", encoding="utf-8") as f, RESULTS_KEY.open("w", newline="", encoding="utf-8") as k:
        w, wk = csv.writer(f), csv.writer(k)
        w.writerow(["n", "blunder", "query", "retrieved_text", "relevant (1/0)"])
        wk.writerow(["n", "query_id", "row_id"])
        for n, (q, r) in enumerate(rows, 1):
            blunder = f"{q['mistake_by']} played {q['blunder_san']} ({q['game_url']})"
            w.writerow([n, blunder, q["query"], r["text"], ""])
            wk.writerow([n, q["id"], r["id"]])
    print(f"Blind check: {len(rows)} rows in {RESULTS} (variant names hidden; key in {RESULTS_KEY.name})")


def cmd_score() -> None:
    variants, queries, cache = build_variants(), load_queries(), load_cache()
    require_embeddings(variants, queries, cache)
    marks = {}
    with RESULTS.open(encoding="utf-8") as f, RESULTS_KEY.open(encoding="utf-8") as k:
        keyrows = {row["n"]: row for row in csv.DictReader(k)}
        for row in csv.DictReader(f):
            v = row["relevant (1/0)"].strip()
            if v not in ("0", "1"):
                sys.exit(f"Row {row['n']} not marked 1/0.")
            kr = keyrows[row["n"]]
            marks[(kr["query_id"], kr["row_id"])] = v == "1"
    qids = sorted({qid for qid, _ in marks})
    by_id = {q["id"]: q for q in queries}
    print(f"HUMAN SCORE on {len(qids)} queries, top {BLIND_TOP} per variant\n")
    print(f"{'variant':16s} {'hit@' + str(BLIND_TOP):>8s} {'precision@' + str(BLIND_TOP):>13s}")
    for name, rows in variants.items():
        m = matrix(rows, cache)
        hits, rel = 0, 0
        for qid in qids:
            top = top_k(m, vec(by_id[qid]["query"], cache), k=BLIND_TOP)
            judged = [marks[(qid, rows[i]["id"])] for i, _ in top]
            hits += any(judged)
            rel += sum(judged)
        print(f"{name:16s} {hits:>4d}/{len(qids)}   {rel / (len(qids) * BLIND_TOP):>10.0%}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        cmd_build(confirm="--yes" in sys.argv)
    elif cmd == "query":
        cmd_query()
    elif cmd == "score":
        cmd_score()
    else:
        sys.exit(__doc__)
