"""Player lookup: the Home page's preview, and the first check when a report starts."""

from typing import Literal

from pydantic import BaseModel

from app.chesscom import fetch_stats

TimeClass = Literal["rapid", "blitz"]


class PlayerSummary(BaseModel):
    """The API.md shape for `GET /api/players/{username}`."""

    username: str
    ratings: dict[TimeClass, int]  # missing when the player never played that time control
    games: dict[TimeClass, int]  # all-time games per time control


async def lookup_player(username: str) -> PlayerSummary:
    stats = await fetch_stats(username)
    ratings: dict[TimeClass, int] = {}
    games: dict[TimeClass, int] = {}
    for time_class, mode in (("rapid", stats.chess_rapid), ("blitz", stats.chess_blitz)):
        if mode is not None and mode.last is not None:
            ratings[time_class] = mode.last.rating
        record = mode.record if mode is not None else None
        games[time_class] = record.win + record.loss + record.draw if record else 0
    return PlayerSummary(username=username.lower(), ratings=ratings, games=games)
