"""Hybrid retrieval: meaning and words, merged with RRF; the tag filter's safety net."""

import hashlib
import json

import numpy as np

from app.rag import load_library
from app.rag.retrieval import keyword_query, retrieve, retrieve_for_card


def make_library(directory) -> None:
    rng = np.random.default_rng(7)
    vectors = rng.normal(size=(12, 1536)).astype(np.float32)
    rows = []
    for i in range(12):
        text = "A passage about tactics in general."
        if i == 7:
            text = "A double attack hits two targets at once."  # matches the fork keywords
        rows.append(
            {
                "id": f"w:{i}",
                "source": "wikipedia",
                "title": "Tactics",
                "section": f"S{i}",
                "url": "https://en.wikipedia.org/wiki/Chess_tactic",
                "text": text,
                "tags": ["fork"] if i < 9 else [],
                "advice": ["fork"] if i in (10, 11) else [],  # untagged, but advice on forks
            }
        )
    (directory / "passages.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    np.save(directory / "vectors.npy", vectors)
    queries = [
        {"theme": "fork", "query": "forks?", "keywords": ["double attack", "attacks two"]},
        {"theme": "pin", "query": "pins?", "keywords": ["pin"]},
    ]
    (directory / "concept_queries.json").write_text(json.dumps(queries))
    # The fork question "means" exactly passage 3; the pin question means passage 10 (untagged).
    np.save(directory / "concept_vectors.npy", np.stack([vectors[3], vectors[10]]))
    files = ["passages.jsonl", "vectors.npy", "concept_queries.json", "concept_vectors.npy"]
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "version": "t",
                "passages": 12,
                "concept_queries": 2,
                "dimensions": 1536,
                "sha256": {
                    f: hashlib.sha256((directory / f).read_bytes()).hexdigest() for f in files
                },
            }
        )
    )


async def test_hybrid_puts_passages_found_both_ways_on_top(db, tmp_path):
    make_library(tmp_path)
    await load_library(tmp_path)
    meaning = [p["id"] for p in await retrieve("fork", "meaning")]
    hybrid = [p["id"] for p in await retrieve("fork", "hybrid")]
    assert meaning[0] == "w:3"  # closest in meaning
    assert set(hybrid[:2]) == {"w:3", "w:7"}  # w:7 is also found by the words "double attack"
    assert all(int(i.split(":")[1]) < 9 for i in hybrid)  # only fork-tagged passages
    assert [p["id"] for p in await retrieve("fork")] == meaning  # the app uses meaning only


async def test_thin_themes_search_the_whole_library(db, tmp_path):
    make_library(tmp_path)
    await load_library(tmp_path)
    found = [p["id"] for p in await retrieve("pin", "meaning")]
    assert found[0] == "w:10"  # untagged, found because fewer than 8 passages are tagged "pin"


def test_keyword_queries_quote_phrases():
    assert keyword_query(["fork", "double attack", "x-ray"]) == 'fork OR "double attack" OR "x-ray"'


async def test_a_card_gets_3_explaining_and_2_advice_passages(db, tmp_path):
    make_library(tmp_path)
    await load_library(tmp_path)
    card = await retrieve_for_card("fork")
    assert [p["role"] for p in card] == ["explains"] * 3 + ["advice"] * 2
    assert card[0]["id"] == "w:3"  # the closest explaining passage still leads
    assert {p["id"] for p in card[3:]} == {"w:10", "w:11"}  # advice found outside the fork tag


async def test_without_advice_a_card_gets_5_explaining_passages(db, tmp_path):
    make_library(tmp_path)
    await load_library(tmp_path)
    card = await retrieve_for_card("pin")
    assert len(card) == 5 and {p["role"] for p in card} == {"explains"}
