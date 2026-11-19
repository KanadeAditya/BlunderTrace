"""The shared `cache` table: chess.com answers, retrieval results and AI answers all live here.

A row is a key, a JSON value, an optional ETag, and an expiry (null = never expires). It's an
ordinary table, so the cache survives restarts and is shared by the API and every worker.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from psycopg.types.json import Jsonb

from app.db.pool import get_pool


@dataclass
class CachedValue:
    value: Any
    etag: str | None
    fresh: bool  # False when expired: usable only after a "not modified" answer


async def cache_get(key: str) -> CachedValue | None:
    async with get_pool().connection() as conn:
        cursor = await conn.execute(
            "SELECT value, etag, (expires_at IS NULL OR expires_at > now()) AS fresh"
            " FROM cache WHERE key = %s",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        if row["fresh"]:
            await conn.execute("UPDATE cache SET hits = hits + 1 WHERE key = %s", (key,))
    return CachedValue(row["value"], row["etag"], row["fresh"])


async def cache_put(
    key: str, value: Any, keep_for: timedelta | None, etag: str | None = None
) -> None:
    """Store a value. `keep_for=None` keeps it forever."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "INSERT INTO cache (key, value, etag, expires_at) VALUES (%s, %s, %s, now() + %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, etag = EXCLUDED.etag,"
            " expires_at = EXCLUDED.expires_at, created_at = now()",
            (key, Jsonb(value), etag, keep_for),
        )


async def cache_extend(key: str, keep_for: timedelta | None) -> None:
    """The stored value is still right (e.g. a "304 Not Modified"): keep it for longer."""
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE cache SET expires_at = now() + %s, hits = hits + 1 WHERE key = %s",
            (keep_for, key),
        )
