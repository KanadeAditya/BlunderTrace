"""Startup: create the tables if they're missing, and check the database is reachable."""

import asyncio
import logging
from pathlib import Path

import psycopg
from procrastinate.schema import SchemaManager
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger(__name__)

SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text()
# Procrastinate's own tables (its pinned version's SQL). Applied once, when they don't exist yet;
# upgrading Procrastinate means running its upgrade scripts by hand.
QUEUE_SCHEMA_SQL = SchemaManager.get_schema()

# An arbitrary number that names our startup lock. If the API and a worker start at the same time,
# the second one waits here until the first has finished creating tables.
_STARTUP_LOCK = 7_514_206


async def prepare_database(url: str) -> None:
    """Create the vector extension, the tables and the indexes if missing. Safe to run twice."""
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute("SELECT pg_advisory_lock(%s)", (_STARTUP_LOCK,))
        try:
            await conn.execute(SCHEMA_SQL)  # no parameters, so several statements are allowed
            found = await conn.execute("SELECT to_regclass('procrastinate_jobs') IS NOT NULL")
            if not (await found.fetchone())[0]:
                await conn.execute(QUEUE_SCHEMA_SQL)
                log.info("job queue tables created")
        finally:
            await conn.execute("SELECT pg_advisory_unlock(%s)", (_STARTUP_LOCK,))
    log.info("database ready")


async def database_is_up(pool: AsyncConnectionPool, timeout: float = 2.0) -> bool:
    """For /health: can we borrow a connection and run a trivial query, quickly?"""
    try:
        async with asyncio.timeout(timeout), pool.connection() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        log.warning("database check failed", exc_info=True)
        return False
