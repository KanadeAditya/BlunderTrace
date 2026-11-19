"""`GET /health`: is everything this process depends on working?

- "unhealthy" (HTTP 503): the database is unreachable, so the API can't do its job.
- "degraded" (HTTP 200): the API works, but no worker has sent a heartbeat recently (reports
  would wait), or the library isn't loaded (cards would use the fixed glossary text).
- "healthy": all of the above are fine.
"""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import get_settings
from app.db import database_is_up, get_pool

router = APIRouter()

Status = Literal["healthy", "degraded", "unhealthy"]
HEARTBEAT_WITHIN = "30 seconds"  # workers send one every 10 seconds


class Health(BaseModel):
    status: Status
    version: str
    checks: dict[str, object]


@router.get("/health", response_model=Health)
async def health(response: Response) -> Health:
    pool = get_pool()
    version = get_settings().app_version
    if not await database_is_up(pool):
        response.status_code = 503
        return Health(status="unhealthy", version=version, checks={"database": "unreachable"})

    async with pool.connection() as conn:
        passages = (
            await (await conn.execute("SELECT count(*) AS n FROM corpus_chunks")).fetchone()
        )["n"]
        workers = (
            await (
                await conn.execute(
                    "SELECT count(*) AS n FROM procrastinate_workers"
                    f" WHERE last_heartbeat > now() - interval '{HEARTBEAT_WITHIN}'"
                )
            ).fetchone()
        )["n"]
    checks: dict[str, object] = {
        "database": "ok",
        "library_passages": passages,
        "workers_alive": workers,
    }
    status: Status = "healthy" if passages and workers else "degraded"
    return Health(status=status, version=version, checks=checks)
