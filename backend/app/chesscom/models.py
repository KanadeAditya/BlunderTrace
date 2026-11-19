"""The shapes we accept from chess.com's public API, checked with Pydantic.

chess.com data is outside input: every response is validated before use. Fields we don't use are
ignored; a game that doesn't fit the shape is skipped (and logged), never allowed to crash a report.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Side(_Lenient):
    username: str
    rating: int | None = None
    result: str  # chess.com's word: "win", "resigned", "checkmated", "agreed", ...


class ChesscomGame(_Lenient):
    url: str = Field(pattern=r"^https://www\.chess\.com/game/")
    pgn: str = ""
    time_class: str  # "bullet" / "blitz" / "rapid" / "daily"
    rules: str  # "chess" for standard chess; anything else is a variant
    end_time: int  # Unix seconds
    eco: str | None = None  # the opening's chess.com link, e.g. ".../openings/Italian-Game"
    initial_setup: str | None = None  # the starting position (FEN)
    white: Side
    black: Side


class _Record(_Lenient):
    win: int = 0
    loss: int = 0
    draw: int = 0


class _Last(_Lenient):
    rating: int


class _Mode(_Lenient):
    last: _Last | None = None
    record: _Record | None = None


class Stats(_Lenient):
    chess_rapid: _Mode | None = None
    chess_blitz: _Mode | None = None


class Archives(_Lenient):
    archives: list[str]
