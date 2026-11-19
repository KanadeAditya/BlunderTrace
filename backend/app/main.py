"""The API process: `uv run uvicorn app.main:app --reload`.

The equivalent of an Express `app.js`: build the app, plug in middleware and error handlers,
mount the routes. It never runs Stockfish; slow work is left in the database for the workers.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import RequestContextMiddleware, install_error_handlers, router
from app.chesscom import close_client, open_client
from app.config import get_settings
from app.db import close_pool, open_pool, prepare_database
from app.db.queue import queue_app
from app.logs import setup_logging
from app.rag import load_library


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Before the first request: create missing tables, open the connection pool, the chess.com
    # client and the job queue. After the last one (shutdown): close them.
    url = get_settings().database_url
    await prepare_database(url)
    await open_pool(url)
    await load_library()  # only when the tables are empty or the library changed
    open_client()
    await queue_app.open_async()  # the API only queues jobs; the workers run them
    try:
        yield
    finally:
        await queue_app.close_async()
        await close_client()
        await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging("api", settings.log_level)
    app = FastAPI(title="BlunderTrace API", version=settings.app_version, lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
