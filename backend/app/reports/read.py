"""Reading results back for the API: a report (progress while running) and one game's moves.

The game's notes are worded here, for this report's player (gap 1 of the final check): "your" for
their own moves, "White's" / "Black's" for the opponent's.
"""

import chess
from pydantic import TypeAdapter

from app.analysis import MoveRecord, better_note, parse_pgn, refutation_note
from app.db import get_pool
from app.reports.errors import GameNotFound, ReportNotFound
from app.reports.models import ReportResult

MOVES = TypeAdapter(list[MoveRecord])

_GAMES = """
SELECT rg.user_color, g.id, g.status, g.white, g.black, g.result, g.opening, g.chesscom_url,
       g.played_at, g.plies, g.trace, g.error_counts
  FROM report_games rg JOIN games g ON g.id = rg.game_id
 WHERE rg.report_id = %s
 ORDER BY rg.position
"""


def _game_summary(row: dict) -> dict:
    color = row["user_color"]
    outcome = None
    if row["result"] == "1/2-1/2":
        outcome = "draw"
    elif row["result"] in ("1-0", "0-1"):
        outcome = "win" if (row["result"] == "1-0") == (color == "white") else "loss"
    game = {
        "id": row["id"],
        "status": row["status"],
        "opponent": row["black"] if color == "white" else row["white"],
        "result": outcome,
        "date": row["played_at"].date().isoformat(),
        "color": color,
        "opening": row["opening"],
        "url": row["chesscom_url"],
        "plies": row["plies"],
    }
    if row["status"] in ("running", "done"):
        game["trace"] = row["trace"]
    if row["status"] == "done" and row["error_counts"]:
        game["errors"] = row["error_counts"][color]
    return game


async def get_report(report_id: str) -> dict:
    async with get_pool().connection() as conn:
        report = await (
            await conn.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
        ).fetchone()
        if report is None:
            raise ReportNotFound(report_id)
        rows = await (await conn.execute(_GAMES, (report_id,))).fetchall()
    games = [_game_summary(r) for r in rows]
    finished = sum(1 for g in games if g["status"] in ("done", "failed"))
    out: dict = {
        "id": report["id"],
        "status": report["status"],
        "username": report["username"],
        "time_control": report["time_control"],
        "progress": {"done": finished, "total": len(games) or report["games_requested"]},
        "games": games,
        "notes": report["notes"],
    }
    if report["status"] == "done":
        out.update(ReportResult.model_validate(report["result"]).model_dump(mode="json"))
    if report["status"] == "failed":
        out.update(error=report["error"], detail=report["detail"])
    return out


def _unanalysed_moves(pgn: str) -> list[dict]:
    """A game that couldn't be analysed: just its moves, ungraded."""
    parsed = parse_pgn(pgn)
    board, moves = chess.Board(parsed.start_fen), []
    for ply, uci in enumerate(parsed.moves_uci, start=1):
        move = chess.Move.from_uci(uci)
        color, number, san = (
            ("white" if board.turn else "black"),
            board.fullmove_number,
            board.san(move),
        )
        board.push(move)
        moves.append(
            {
                "ply": ply,
                "move_number": number,
                "color": color,
                "san": san,
                "fen_after": board.fen(),
                "eval": {},
                "grade": None,
                "themes": [],
                "better_line": None,
                "refutation_line": None,
                "better_note": None,
                "refutation_note": None,
                "refutation_arrows": None,
            }
        )
    return moves


async def get_game(report_id: str, game_id: str) -> dict:
    async with get_pool().connection() as conn:
        row = await (
            await conn.execute(
                "SELECT rg.user_color, g.* FROM report_games rg JOIN games g ON g.id = rg.game_id"
                " WHERE rg.report_id = %s AND rg.game_id = %s",
                (report_id, game_id),
            )
        ).fetchone()
    if row is None:
        raise GameNotFound(game_id)
    reader = row["user_color"]
    if row["status"] == "done":
        moves = []
        for m in MOVES.validate_python(row["moves"]):
            moves.append(
                {
                    "ply": m.ply,
                    "move_number": m.move_number,
                    "color": m.color,
                    "san": m.san,
                    "fen_after": m.fen_after,
                    "eval": m.eval.model_dump(exclude_none=True),
                    "grade": m.grade,
                    "themes": m.themes,
                    "better_line": m.better_line,
                    "refutation_line": m.refutation_line,
                    "better_note": better_note(m.better_facts, m.color, reader)
                    if m.better_facts
                    else None,
                    "refutation_note": (
                        refutation_note(m.refutation_facts, m.color, reader)
                        if m.refutation_facts
                        else None
                    ),
                    "refutation_arrows": m.refutation_arrows,
                }
            )
    else:
        moves = _unanalysed_moves(row["pgn"])
    return {
        "id": row["id"],
        "white": row["white"],
        "black": row["black"],
        "user_color": reader,
        "result": row["result"],
        "opening": row["opening"],
        "url": row["chesscom_url"],
        "start_fen": row["start_fen"],
        "grading": "complete",
        "moves": moves,
    }
