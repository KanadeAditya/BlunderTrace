"""Postgres: the connection pool, the tables (schema.sql), startup, and the shared cache table.

Every query in the app is plain SQL with `%s` parameters, run through a connection borrowed from
the pool. Each folder keeps its own SQL next to the code that uses it.
"""

from app.db.cache import CachedValue, cache_extend, cache_get, cache_put
from app.db.pool import close_pool, get_pool, open_pool
from app.db.startup import database_is_up, prepare_database

__all__ = [
    "CachedValue",
    "cache_extend",
    "cache_get",
    "cache_put",
    "close_pool",
    "database_is_up",
    "get_pool",
    "open_pool",
    "prepare_database",
]
