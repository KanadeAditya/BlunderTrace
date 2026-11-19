"""Shared test setup. pytest loads this file before any test, like a Jest `setupFiles` entry.

Environment variables beat `.env`, so setting them here means tests never use the real database or
real API keys: any accidental AI call would fail to authenticate instead of costing money.
"""

import asyncio
import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = (
    "postgresql://blundertrace:blundertrace@localhost:5432/blundertrace_test"
)
os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["OPENAI_API_KEY"] = "test-key-not-real"

import psycopg  # noqa: E402  (imported after the environment is set on purpose)
import pytest  # noqa: E402

from app.db import close_pool, get_pool, open_pool, prepare_database  # noqa: E402

TEST_URL = os.environ["DATABASE_URL"]
TEST_DB = TEST_URL.rsplit("/", 1)[1]
ADMIN_URL = TEST_URL.rsplit("/", 1)[0] + "/postgres"  # the server's default database
TABLES = (
    "reports, games, report_games, corpus_chunks, concept_queries, cache, llm_calls,"
    " procrastinate_jobs, procrastinate_workers, procrastinate_periodic_defers"
)


def _fresh_test_database() -> None:
    """Create blundertrace_test if needed, wipe it completely, then create the tables."""
    with psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=3) as conn:
        found = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
        if found.fetchone() is None:
            conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    asyncio.run(prepare_database(TEST_URL))


def wipe_tables() -> None:
    """Empty every table (for tests that run the whole app instead of using the `db` fixture)."""
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        conn.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")


@pytest.fixture(scope="session")
def database() -> str:
    """The test database, freshly wiped once per test run. Skips if Postgres isn't running."""
    try:
        _fresh_test_database()
    except psycopg.OperationalError:
        pytest.skip("Postgres isn't running: start it with `docker compose up -d db`")
    return TEST_URL


@pytest.fixture
async def db(database):
    """The app's connection pool on the test database, with every table emptied first."""
    await open_pool(database)
    async with get_pool().connection() as conn:
        await conn.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    yield get_pool()
    await close_pool()
