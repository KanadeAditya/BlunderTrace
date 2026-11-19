"""Stockfish only: "analyse this position" -> scores and lines. Imports nothing else from the app,
so a browser-based engine could replace it later (post-launch item 4 in PLAN.md).
"""

from app.engine.stockfish import (
    EngineCrashed,
    Line,
    Position,
    Stockfish,
    get_engine,
    start_engine,
    stop_engine,
)

__all__ = [
    "EngineCrashed",
    "Line",
    "Position",
    "Stockfish",
    "get_engine",
    "start_engine",
    "stop_engine",
]
