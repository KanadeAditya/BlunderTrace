"""chess.com client: player lookup, monthly archives, game selection, caching with ETags.

Everything here talks to chess.com's public API one request at a time, through the `cache` table.
"""

from app.chesscom.client import (
    ChesscomUnavailable,
    PlayerNotFound,
    close_client,
    fetch_stats,
    get_client,
    open_client,
)
from app.chesscom.models import ChesscomGame, Stats
from app.chesscom.select import MAX_MONTHS, MIN_PLIES, recent_games

__all__ = [
    "MAX_MONTHS",
    "MIN_PLIES",
    "ChesscomGame",
    "ChesscomUnavailable",
    "PlayerNotFound",
    "Stats",
    "close_client",
    "fetch_stats",
    "get_client",
    "open_client",
    "recent_games",
]
