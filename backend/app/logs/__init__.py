"""Structured logging shared by the API and the workers.

Every log line is one JSON object on standard output, so `docker compose logs` can be searched by
field. Values bound with `bind()` (a request id, a report id, a game id, a job name) are added to
every line logged while they are bound, across `await` points: following one report through the
API and every worker is a single search.
"""

from app.logs.context import bind, current_context
from app.logs.setup import setup_logging

__all__ = ["bind", "current_context", "setup_logging"]
