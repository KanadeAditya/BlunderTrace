"""BlunderTrace API — FastAPI application (the equivalent of an Express app.js).

Phase 0: only /health. Product endpoints (docs/API.md) are added in phase 2.
"""
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
app = FastAPI(title="BlunderTrace API", version=settings.app_version)


@app.get("/health")
def health() -> dict:
    # Checks for the database and Stockfish are added when those exist (phase 2).
    return {"status": "healthy", "environment": settings.app_env, "version": settings.app_version}
