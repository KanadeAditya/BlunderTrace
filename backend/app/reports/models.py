"""The report's stored and returned shapes, field for field as in docs/API.md.

`ReportResult` is what `reports.result` holds once a report is done; it is validated before it is
written and after it is read (JSON columns aren't checked by Postgres itself).
"""

from typing import Literal

from pydantic import BaseModel

Color = Literal["white", "black"]


class Summary(BaseModel):
    games: int
    wins: int
    draws: int
    losses: int
    blunders_per_game: float
    mistakes_per_game: float
    misses_per_game: float


class Example(BaseModel):
    game_id: str
    ply: int
    move_number: int
    color: Color
    opponent: str
    fen_before: str
    played: str
    grade: str
    better: str | None
    punishing_line: list[str]
    note: str
    arrows: list[tuple[str, str]]


class Source(BaseModel):
    title: str
    url: str
    passage: str


class Weakness(BaseModel):
    theme: str
    name: str
    count: int  # games in which the user allowed it
    why: str
    how_to_avoid: str
    examples: list[Example]
    sources: list[Source]


class ThemeCount(BaseModel):
    theme: str
    name: str
    count: int  # times


class OpeningScore(BaseModel):
    name: str
    color: Color
    games: int
    wins: int
    draws: int
    losses: int
    score: float


class ReportResult(BaseModel):
    summary: Summary
    weaknesses: list[Weakness]
    missed_tactics: list[ThemeCount]
    openings: list[OpeningScore]
