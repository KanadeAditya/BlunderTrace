"""Retrieval: the theory passages for one weakness theme, in one SQL query (BACKEND.md section 8).

1. **Filter by tag:** passages tagged with the theme. If fewer than MIN_TAGGED are tagged, search
   the whole library instead (the safety net for thinly covered themes).
2. **Rank by meaning:** pgvector's cosine distance `<=>` to the theme's question vector.
3. **Take the top 5.**

**For a card** (`retrieve_for_card`): the top 3 passages that *explain* the theme (as above) plus
the top 2 that give practical *advice on avoiding it* (passages whose build-time `advice` label
includes the theme), each marked with its role. The blind check showed the library explains what a
tactic is far more often than how to avoid it, so advice gets its own slots. If a theme has fewer
than 2 advice passages, the remaining slots go to explaining passages.

The app uses meaning only. "hybrid" (also ranking by words with the theme's keyword list, then
merging the two rankings with Reciprocal Rank Fusion) is kept for the retrieval check, where it
was tested blind and added nothing: the tag filter already narrows the search to the topic, and
the word ranking mostly pulled in fragments that happen to contain the words (BACKEND.md
section 15).

The question, keywords and library are fixed, so a theme's result never changes until the library
does: it is cached per theme.
"""

from typing import Literal

from app.db import cache_get, cache_put, get_pool

MIN_TAGGED = 8
TOP_K = 5
EXPLAINS, ADVICE = 3, 2  # a card's passages: 3 that explain the theme, 2 with avoidance advice
CANDIDATES = 20  # each ranking keeps its best 20 before merging
RRF_K = 60
WEIGHT_MEANING, WEIGHT_WORDS = 1.0, 0.8

Method = Literal["hybrid", "meaning"]

_SQL = """
WITH q AS (SELECT embedding FROM concept_queries WHERE theme = %(theme)s),
candidates AS MATERIALIZED (
  SELECT c.id, c.embedding, c.tsv FROM corpus_chunks c
   WHERE NOT %(filter)s OR %(theme)s = ANY (c.tags)
),
by_meaning AS (
  SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> q.embedding) AS rank
    FROM candidates c, q
   ORDER BY c.embedding <=> q.embedding
   LIMIT %(n)s
),
by_words AS (
  SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, w.query) DESC, c.id) AS rank
    FROM candidates c, websearch_to_tsquery('english', %(words)s) AS w(query)
   WHERE %(hybrid)s AND c.tsv @@ w.query
   ORDER BY ts_rank_cd(c.tsv, w.query) DESC, c.id
   LIMIT %(n)s
)
SELECT p.id, p.source, p.title, p.section, p.url, p.text,
       coalesce(%(wm)s / (%(k)s + m.rank), 0) + coalesce(%(ww)s / (%(k)s + w.rank), 0) AS score
  FROM by_meaning m
  FULL OUTER JOIN by_words w USING (id)
  JOIN corpus_chunks p USING (id)
 ORDER BY score DESC, p.id
 LIMIT %(top)s
"""


_ADVICE_SQL = """
WITH q AS (SELECT embedding FROM concept_queries WHERE theme = %(theme)s)
SELECT p.id, p.source, p.title, p.section, p.url, p.text, 1 - (p.embedding <=> q.embedding) AS score
  FROM corpus_chunks p, q
 WHERE %(theme)s = ANY (p.advice) AND NOT (p.id = ANY (%(exclude)s))
 ORDER BY p.embedding <=> q.embedding, p.id
 LIMIT %(top)s
"""


def keyword_query(keywords: list[str]) -> str:
    """["fork", "double attack"] -> 'fork OR "double attack"' (websearch syntax: phrases quoted)."""
    return " OR ".join(f'"{k}"' if " " in k or "-" in k else k for k in keywords)


async def retrieve(theme: str, method: Method = "meaning", top: int = TOP_K) -> list[dict]:
    key = f"rag:{await _library_version()}:{theme}:{method}:{top}"
    cached = await cache_get(key)
    if cached is not None and cached.fresh:
        return cached.value
    async with get_pool().connection() as conn:
        query = await (
            await conn.execute("SELECT keywords FROM concept_queries WHERE theme = %s", (theme,))
        ).fetchone()
        if query is None:
            return []
        tagged = await (
            await conn.execute(
                "SELECT count(*) AS n FROM corpus_chunks WHERE %s = ANY (tags)", (theme,)
            )
        ).fetchone()
        rows = await (
            await conn.execute(
                _SQL,
                {
                    "theme": theme,
                    "filter": tagged["n"] >= MIN_TAGGED,
                    "hybrid": method == "hybrid",
                    "words": keyword_query(query["keywords"]),
                    "n": CANDIDATES,
                    "k": RRF_K,
                    "wm": WEIGHT_MEANING,
                    "ww": WEIGHT_WORDS,
                    "top": top,
                },
            )
        ).fetchall()
    passages = [{**r, "score": float(r["score"])} for r in rows]
    await cache_put(key, passages, keep_for=None)  # the key includes the library version
    return passages


async def retrieve_for_card(theme: str) -> list[dict]:
    """The 5 passages a card is written from: 3 that explain the theme, then 2 with avoidance
    advice (role "explains" / "advice")."""
    key = f"rag:{await _library_version()}:{theme}:card"
    cached = await cache_get(key)
    if cached is not None and cached.fresh:
        return cached.value
    explaining = await retrieve(theme, "meaning", TOP_K)
    chosen = [{**p, "role": "explains"} for p in explaining[:EXPLAINS]]
    async with get_pool().connection() as conn:
        rows = await (
            await conn.execute(
                _ADVICE_SQL,
                {"theme": theme, "exclude": [p["id"] for p in chosen], "top": ADVICE},
            )
        ).fetchall()
    chosen += [{**r, "score": float(r["score"]), "role": "advice"} for r in rows]
    spare = [p for p in explaining[EXPLAINS:] if p["id"] not in {c["id"] for c in chosen}]
    chosen += [{**p, "role": "explains"} for p in spare[: TOP_K - len(chosen)]]
    await cache_put(key, chosen, keep_for=None)  # the key includes the library version
    return chosen


async def _library_version() -> str:
    found = await cache_get("library:version")
    return found.value.get("passages", "none")[:12] if found else "none"
