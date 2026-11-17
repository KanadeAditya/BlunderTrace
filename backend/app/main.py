"""The API process: `uv run uvicorn app.main:app --reload`.

The equivalent of an Express `app.js`: build the app, plug in middleware and error handlers,
mount the routes. It never runs Stockfish; slow work is left in the database for the workers.
"""

from fastapi import FastAPI

from app.api import RequestContextMiddleware, install_error_handlers, router
from app.config import get_settings
from app.logs import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging("api", settings.log_level)
    app = FastAPI(title="BlunderTrace API", version=settings.app_version)
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
