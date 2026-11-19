"""Choosing which games a report analyses: the player's newest games in the chosen time control.

Walk the monthly archives newest first, one month at a time, until there are enough games. Past
months are cached forever, so asking again later only downloads the current month.
"""

import io
from datetime import UTC, datetime

import chess.pgn

from app.chesscom.client import fetch_archive_urls, fetch_month, month_of
from app.chesscom.models import ChesscomGame

MAX_MONTHS = 24  # look back at most two years
MIN_PLIES = 10  # skip games over before both sides made 5 moves: nothing to learn from them


def time_classes(time_control: str) -> set[str]:
    return {"rapid", "blitz"} if time_control == "both" else {time_control}


def _month_number(year: int, month: int) -> int:
    return year * 12 + month - 1  # consecutive months get consecutive numbers


def months_to_search(archive_urls: list[str], now: datetime) -> list[str]:
    """Newest first, and only months from the last MAX_MONTHS."""
    oldest = _month_number(now.year, now.month) - (MAX_MONTHS - 1)
    recent = [u for u in archive_urls if _month_number(*month_of(u)) >= oldest]
    return sorted(recent, key=month_of, reverse=True)


def count_plies(pgn: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn))
    return 0 if game is None else sum(1 for _ in game.mainline_moves())


def is_usable(game: ChesscomGame, wanted: set[str]) -> bool:
    return (
        game.rules == "chess"  # standard chess only, no variants
        and game.time_class in wanted
        and bool(game.pgn)
        and count_plies(game.pgn) >= MIN_PLIES
    )


async def recent_games(
    username: str, time_control: str, count: int, now: datetime | None = None
) -> list[ChesscomGame]:
    """Up to `count` usable games, newest first. Fewer if the player doesn't have that many."""
    now = now or datetime.now(UTC)
    wanted = time_classes(time_control)
    picked: list[ChesscomGame] = []
    for url in months_to_search(await fetch_archive_urls(username), now):
        month = sorted(await fetch_month(url, now), key=lambda g: g.end_time, reverse=True)
        picked.extend(g for g in month if is_usable(g, wanted))
        if len(picked) >= count:
            break
    return picked[:count]
