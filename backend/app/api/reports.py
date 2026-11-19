"""The report endpoints (docs/API.md, sections 1–3)."""

import re
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from app.reports import GameNotFound, ReportNotFound, get_game, get_report, start_report
from app.reports.models import OpeningScore, Summary, ThemeCount, Weakness

router = APIRouter(prefix="/api")

Status = Literal["queued", "running", "done", "failed"]
Color = Literal["white", "black"]
REPORT_ID = re.compile(r"^r_[a-z0-9]{6,32}$")
GAME_ID = re.compile(r"^g_[a-z0-9]{6,32}$")


class StartReport(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields are an error, not ignored

    username: str = Field(pattern=r"^[A-Za-z0-9_-]{3,25}$")
    time_control: Literal["rapid", "blitz", "both"]
    games: Literal[10, 20, 30, 50] = 20


class Started(BaseModel):
    id: str
    status: Literal["queued", "running", "done"]


class Progress(BaseModel):
    done: int
    total: int


class ReportGame(BaseModel):
    id: str
    status: Status
    opponent: str
    result: Literal["win", "loss", "draw"] | None = None
    date: str | None = None
    color: Color | None = None
    opening: str | None = None
    url: str | None = None
    errors: dict[str, int] | None = None
    plies: int | None = None
    trace: list[int] | None = None


class Report(BaseModel):
    id: str
    status: Status
    username: str
    time_control: Literal["rapid", "blitz", "both"]
    progress: Progress
    games: list[ReportGame]
    notes: list[str] = []
    summary: Summary | None = None
    weaknesses: list[Weakness] | None = None
    missed_tactics: list[ThemeCount] | None = None
    openings: list[OpeningScore] | None = None
    error: str | None = None
    detail: str | None = None


class Move(BaseModel):
    ply: int
    move_number: int
    color: Color
    san: str
    fen_after: str
    eval: dict[str, int]
    grade: str | None
    themes: list[str]
    better_line: list[str] | None
    refutation_line: list[str] | None
    better_note: str | None
    refutation_note: str | None
    refutation_arrows: list[tuple[str, str]] | None


class Game(BaseModel):
    id: str
    white: str
    black: str
    user_color: Color
    result: Literal["1-0", "0-1", "1/2-1/2"]
    opening: str
    url: str
    start_fen: str
    grading: Literal["pending", "complete"]
    moves: list[Move]


@router.post("/reports", response_model=Started, status_code=202)
async def create_report(body: StartReport, response: Response) -> Started:
    """202 for a new or running report; 200 when a recent identical report is reused."""
    report_id, status = await start_report(body.username, body.time_control, body.games)
    if status == "done":
        response.status_code = 200
    return Started(id=report_id, status=status)


@router.get("/reports/{report_id}", response_model=Report, response_model_exclude_none=True)
async def read_report(report_id: str) -> dict:
    if not REPORT_ID.match(report_id):  # malformed ids are a 404 without touching the database
        raise ReportNotFound(report_id)
    return await get_report(report_id)


@router.get("/reports/{report_id}/games/{game_id}", response_model=Game)
async def read_game(report_id: str, game_id: str) -> dict:
    if not REPORT_ID.match(report_id):
        raise ReportNotFound(report_id)
    if not GAME_ID.match(game_id):
        raise GameNotFound(game_id)
    return await get_game(report_id, game_id)
