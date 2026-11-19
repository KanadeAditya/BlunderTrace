"""Loading the shipped library into Postgres: checked, loaded once, reloaded when it changes."""

import hashlib
import json

import numpy as np
import pytest

from app.rag import LibraryError, load_library


def write_library(directory, version: str = "1", passages: int = 2) -> None:
    rows = [
        {
            "id": f"w:{i}",
            "source": "wikipedia",
            "title": "Fork (chess)",
            "section": "Intro",
            "url": "https://en.wikipedia.org/wiki/Fork_(chess)",
            "text": f"A fork, part {i}.",
            "tags": ["fork"],
        }
        for i in range(passages)
    ]
    (directory / "passages.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    np.save(directory / "vectors.npy", np.ones((passages, 1536), dtype=np.float32))
    queries = [{"theme": "fork", "query": "How do I avoid forks?", "keywords": ["fork"]}]
    (directory / "concept_queries.json").write_text(json.dumps(queries))
    np.save(directory / "concept_vectors.npy", np.ones((1, 1536), dtype=np.float32))
    files = ["passages.jsonl", "vectors.npy", "concept_queries.json", "concept_vectors.npy"]
    manifest = {
        "version": version,
        "passages": passages,
        "concept_queries": 1,
        "dimensions": 1536,
        "sha256": {f: hashlib.sha256((directory / f).read_bytes()).hexdigest() for f in files},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))


async def count(db, table: str) -> int:
    async with db.connection() as conn:
        return (await (await conn.execute(f"SELECT count(*) AS n FROM {table}")).fetchone())["n"]


async def test_the_library_loads_once_and_reloads_when_it_changes(db, tmp_path):
    write_library(tmp_path)
    assert await load_library(tmp_path) == 2
    assert await count(db, "corpus_chunks") == 2 and await count(db, "concept_queries") == 1
    assert await load_library(tmp_path) == 2  # unchanged: nothing reloaded
    write_library(tmp_path, version="2", passages=3)
    assert await load_library(tmp_path) == 3
    assert await count(db, "corpus_chunks") == 3


async def test_a_tampered_file_is_refused(db, tmp_path):
    write_library(tmp_path)
    (tmp_path / "passages.jsonl").write_text("not what the manifest says\n")
    with pytest.raises(LibraryError):
        await load_library(tmp_path)


async def test_no_library_is_fine(db, tmp_path):
    assert await load_library(tmp_path) == 0  # cards then use the fixed glossary text
