"""The connection pool: a few open Postgres connections that every request and job borrows.

Opening a database connection takes milliseconds; borrowing an already-open one takes almost
nothing. Like `new Pool()` in node-postgres: open once at startup, `async with pool.connection()`
to borrow one, and it goes back to the pool when the block ends.
"""

from pgvector.psycopg import register_vector_async
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_pool: AsyncConnectionPool | None = None


async def _configure(conn: AsyncConnection) -> None:
    # Runs once per new connection: rows come back as dicts, and `vector` columns as numpy arrays.
    conn.row_factory = dict_row
    await register_vector_async(conn)


async def open_pool(url: str, max_size: int = 10) -> AsyncConnectionPool:
    """Open the shared pool. Call after `prepare_database`, which creates the vector extension."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            url, min_size=1, max_size=max_size, configure=_configure, open=False
        )
        await _pool.open(wait=True, timeout=10)
    return _pool


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool is not open (open_pool() runs at startup)")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
