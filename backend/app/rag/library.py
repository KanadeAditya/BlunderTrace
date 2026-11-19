"""Loading the shipped library (data/library/) into Postgres when the API starts.

The library is built once by scripts/build_library.py and shipped with the project, so the running
app needs no AI and no API key for it. On startup the files are checked (counts, vector size,
checksums) and loaded into `corpus_chunks` and `concept_queries`, but only when the tables are empty
or the library's version changed; otherwise nothing happens.
"""

import hashlib
import json
import logging
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb

from app.db import get_pool

log = logging.getLogger(__name__)

LIBRARY_DIR = Path(__file__).resolve().parents[2] / "data" / "library"
DIMENSIONS = 1536
VERSION_KEY = "library:version"


class LibraryError(Exception):
    """The shipped files are missing a piece, or don't match their manifest."""


def read_library(
    directory: Path = LIBRARY_DIR,
) -> tuple[dict, list[dict], np.ndarray, list[dict], np.ndarray]:
    manifest = json.loads((directory / "manifest.json").read_text())
    for name, expected in manifest["sha256"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise LibraryError(f"{name} doesn't match its checksum in manifest.json")
    with open(directory / "passages.jsonl") as f:
        passages = [json.loads(line) for line in f if line.strip()]
    vectors = np.load(directory / "vectors.npy")
    queries = json.loads((directory / "concept_queries.json").read_text())
    query_vectors = np.load(directory / "concept_vectors.npy")
    if len(passages) != manifest["passages"] or vectors.shape != (len(passages), DIMENSIONS):
        raise LibraryError("passages and vectors don't match the manifest")
    if query_vectors.shape != (len(queries), DIMENSIONS):
        raise LibraryError("concept queries and their vectors don't match")
    return manifest, passages, vectors, queries, query_vectors


async def load_library(directory: Path = LIBRARY_DIR) -> int:
    """Load the library if needed. Returns the number of passages in the database afterwards."""
    if not (directory / "manifest.json").exists():
        log.warning("no library files found: weakness cards will use the fixed glossary text")
        return 0
    manifest, passages, vectors, queries, query_vectors = read_library(directory)
    stamp = {"version": manifest["version"], "passages": manifest["sha256"]["passages.jsonl"]}

    async with get_pool().connection() as conn, conn.transaction():
        loaded = await (
            await conn.execute("SELECT value FROM cache WHERE key = %s", (VERSION_KEY,))
        ).fetchone()
        row = await (await conn.execute("SELECT count(*) AS n FROM corpus_chunks")).fetchone()
        count = row["n"]
        if loaded and loaded["value"] == stamp and count == len(passages):
            return count
        await conn.execute("DELETE FROM corpus_chunks")
        await conn.execute("DELETE FROM concept_queries")
        await conn.execute("DELETE FROM cache WHERE key LIKE 'rag:%%'")  # old library's results
        async with conn.cursor() as cursor:
            await cursor.executemany(
                "INSERT INTO corpus_chunks"
                " (id, source, title, section, url, text, tags, advice, embedding)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        p["id"],
                        p["source"],
                        p["title"],
                        p["section"],
                        p["url"],
                        p["text"],
                        p["tags"],
                        p.get("advice", []),
                        vectors[i],
                    )
                    for i, p in enumerate(passages)
                ],
            )
            await cursor.executemany(
                "INSERT INTO concept_queries (theme, query, keywords, embedding)"
                " VALUES (%s, %s, %s, %s)",
                [
                    (q["theme"], q["query"], q["keywords"], query_vectors[i])
                    for i, q in enumerate(queries)
                ],
            )
        await conn.execute(
            "INSERT INTO cache (key, value) VALUES (%s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (VERSION_KEY, Jsonb(stamp)),
        )
    log.info("library loaded", extra={"passages": len(passages), "version": manifest["version"]})
    return len(passages)
