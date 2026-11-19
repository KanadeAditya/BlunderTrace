"""A worker process: `uv run python -m app.worker`. Start several for more capacity (WORKERS).

The same code as the API, started in its other role (like `worker.ts` next to `server.ts`). Each
worker runs one job at a time with one Stockfish, so one worker = one CPU core.
"""

import asyncio
import os
import socket

from app import jobs  # noqa: F401  (importing registers the tasks on the queue app)
from app.chesscom import close_client, open_client
from app.config import get_settings
from app.db import close_pool, open_pool, prepare_database
from app.db.queue import queue_app
from app.engine import start_engine, stop_engine
from app.logs import setup_logging


async def run() -> None:
    settings = get_settings()
    setup_logging("worker", settings.log_level)
    await prepare_database(settings.database_url)  # waits its turn if the API is creating tables
    await open_pool(settings.database_url)
    open_client()
    await start_engine(settings.stockfish_path, settings.engine_nodes, settings.engine_hash_mb)
    try:
        async with queue_app.open_async():
            await queue_app.run_worker_async(
                concurrency=1,  # one job at a time: one Stockfish per worker
                name=f"worker-{socket.gethostname()}-{os.getpid()}",
                shutdown_graceful_timeout=25,  # Docker allows 30 s (stop_grace_period)
            )
    finally:
        await stop_engine()
        await close_client()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
