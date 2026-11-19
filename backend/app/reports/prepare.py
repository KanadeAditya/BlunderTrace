"""`prepare_report`: download the player's games, save new ones, link them, queue their analysis.

Safe to run twice (a retry or a repair): games are stored once by their chess.com link, links are
inserted once, and games already analysed are not queued again.
"""

import logging
from datetime import UTC, datetime

from app.analysis import ParsedGame, opening_family, parse_pgn
from app.chesscom import ChesscomGame, recent_games
from app.db import get_pool
from app.logs import bind
from app.reports.complete import add_notes, check_report_complete, fail_report
from app.reports.errors import TIME_LABELS
from app.reports.queueing import queue_game
from app.reports.start import new_id

log = logging.getLogger(__name__)

_SAVE_GAME = """
INSERT INTO games (id, chesscom_url, white, black, white_rating, black_rating, result, time_class,
                   played_at, opening, start_fen, pgn, plies)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (chesscom_url) DO NOTHING
RETURNING id
"""


async def save_game(game: ChesscomGame, parsed: ParsedGame) -> str:
    """Store a chess.com game once (whoever asks first); return its id."""
    values = (
        new_id("g_"),
        game.url,
        game.white.username,
        game.black.username,
        game.white.rating,
        game.black.rating,
        parsed.result,
        game.time_class,
        datetime.fromtimestamp(game.end_time, UTC),
        opening_family(game.eco),
        parsed.start_fen,
        game.pgn,
        len(parsed.moves_uci),
    )
    async with get_pool().connection() as conn:
        row = await (await conn.execute(_SAVE_GAME, values)).fetchone()
        if row is None:  # already stored, by this or another report
            row = await (
                await conn.execute("SELECT id FROM games WHERE chesscom_url = %s", (game.url,))
            ).fetchone()
    return row["id"]


async def prepare_report(report_id: str) -> None:
    async with get_pool().connection() as conn:
        report = await (
            await conn.execute(
                "SELECT username, time_control, games_requested, status FROM reports WHERE id = %s",
                (report_id,),
            )
        ).fetchone()
        if report is None or report["status"] not in ("queued", "running"):
            return
        await conn.execute(
            "UPDATE reports SET status = 'running', started_at = coalesce(started_at, now())"
            " WHERE id = %s",
            (report_id,),
        )
    username, wanted = report["username"], report["games_requested"]
    label = TIME_LABELS[report["time_control"]]

    with bind(report_id=report_id):
        chosen = await recent_games(username, report["time_control"], wanted)
        if not chosen:
            detail = f"No {label} games found for {username} in the last 24 months."
            await fail_report(report_id, "no_games", detail)
            return

        linked: list[tuple[str, str]] = []
        for game in chosen:
            try:
                parsed = parse_pgn(game.pgn)
            except ValueError:
                log.warning("skipped a game whose PGN couldn't be read", extra={"url": game.url})
                continue
            color = "white" if game.white.username.lower() == username else "black"
            linked.append((await save_game(game, parsed), color))
        if not linked:
            await fail_report(report_id, "analysis_failed", "None of these games could be read.")
            return

        async with get_pool().connection() as conn:
            for position, (game_id, color) in enumerate(linked, start=1):
                await conn.execute(
                    "INSERT INTO report_games (report_id, game_id, position, user_color)"
                    " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (report_id, game_id, position, color),
                )
            # A game that failed for an earlier report gets another try (a bug may be fixed).
            await conn.execute(
                "UPDATE games SET status = 'queued', error = NULL WHERE status = 'failed'"
                " AND id IN (SELECT game_id FROM report_games WHERE report_id = %s)",
                (report_id,),
            )
            pending = await (
                await conn.execute(
                    "SELECT g.id FROM report_games rg JOIN games g ON g.id = rg.game_id"
                    " WHERE rg.report_id = %s AND g.status <> 'done' ORDER BY rg.position",
                    (report_id,),
                )
            ).fetchall()

        if len(linked) < wanted:
            weak = "; patterns may be weak." if len(linked) < 5 else "."
            await add_notes(report_id, [f"Only {len(linked)} {label} games found{weak}"])
        for row in pending:
            await queue_game(row["id"])
        log.info("report prepared", extra={"games": len(linked), "to_analyse": len(pending)})
    # Covers games that finished in between, and the case where every game was already analysed.
    await check_report_complete(report_id)
